"""Webview server lifecycle engine.

Provides the process-lifecycle functions for the ailsa webview server:
- :func:`_build_launcher` — choose the ``ailsa`` CLI subprocess command
  (two-tier: ``ailsa`` on PATH, else ``python -m ailsa.cli``; never a
  lone, possibly-stale ``lucy`` script).
- :func:`_pick_free_port` — bind ephemeral port 0, return the assigned port.
- :func:`start` — launch a detached uvicorn subprocess; idempotent.
- :func:`stop` — send SIGTERM (then SIGKILL) and remove state file.
- :func:`status` — return live :class:`~ailsa.webview.state.WebviewState`
  or ``None`` (and remove stale state files).

This module MUST NOT import fastapi, uvicorn, or
``ailsa.webview.app`` at module level.  It launches uvicorn in a
subprocess so that the core ``ailsa`` CLI stays importable without the
webview optional extra (WV-08).
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from ailsa.webview.state import WebviewState


def _build_launcher() -> list[str]:
    """Return the subprocess command prefix for launching the ``ailsa`` CLI.

    Two-tier check: the ``ailsa`` entry point on PATH, otherwise
    ``python -m ailsa.cli``. Deliberately **not** a three-tier check that
    also falls back to a lone ``lucy`` script: a ``lucy`` found on PATH
    with no ``ailsa`` beside it can only be a stale pre-rename
    ``lucy-ng`` install, and launching it would run old code against this
    package's webview server (T-104-07).

    Returns:
        The command prefix to prepend to the webview subcommand args.
    """
    if shutil.which("ailsa"):
        return ["ailsa"]
    return [sys.executable, "-m", "ailsa.cli"]


def _pick_free_port(host: str = "127.0.0.1") -> int:
    """Return an ephemeral TCP port that is currently unbound on *host*.

    Binds an ``AF_INET`` socket to ``(host, 0)``, lets the OS assign a
    port, records it, and immediately closes the socket.  There is an
    inherent TOCTOU gap between this call and the subprocess bind, but
    for a local-only development tool on a low-port-pressure machine
    the window is negligible.

    Args:
        host: Interface address to probe.  Defaults to loopback.

    Returns:
        An available port number in the range ``[1024, 65535]``.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, 0))
        return int(s.getsockname()[1])


def start(
    analysis_dir: Path,
    port: int | None = None,
    host: str = "127.0.0.1",
) -> WebviewState:
    """Start a detached webview server subprocess for *analysis_dir*.

    Idempotent: if a live server is already running for the directory,
    returns its existing :class:`WebviewState` without launching a new
    process.

    Security mitigations applied (threat register T-90-03, T-90-04, T-90-05):
    - *analysis_dir* is resolved to an absolute path and verified with
      ``is_dir()`` before use (path-traversal guard).
    - Subprocess is launched with the ``LIST`` form of :func:`subprocess.Popen`
      — the ``shell`` keyword is never set to ``True`` (injection guard).
    - A 0.5 s startup poll checks ``proc.poll()`` and raises
      :exc:`RuntimeError` if the process exits early (port-squat guard).

    Args:
        analysis_dir: Path to the CASE analysis directory.
        port: TCP port to listen on.  ``None`` picks a free port
            automatically via :func:`_pick_free_port`.
        host: Bind address.  Defaults to ``"127.0.0.1"`` (loopback only).

    Returns:
        The :class:`WebviewState` written to
        ``<analysis_dir>/.webview.json``.

    Raises:
        ValueError: If *analysis_dir* does not exist or is not a directory.
        RuntimeError: If the subprocess exits within the startup window
            (indicates a port-bind failure or configuration error).
    """
    resolved = Path(analysis_dir).resolve()
    if not resolved.is_dir():
        raise ValueError(
            f"analysis_dir does not exist or is not a directory: {resolved}"
        )

    # Idempotency: return existing live state unchanged.
    existing = status(resolved)
    if existing is not None:
        return existing

    if port is None:
        port = _pick_free_port(host)

    # Build subprocess command.  Use ``ailsa`` from PATH when available so
    # that installed packages work; fall back to ``python -m ailsa.cli``
    # for editable/dev installs. Never falls back to a lone ``lucy`` --
    # see _build_launcher()'s docstring (T-104-07).
    launcher = _build_launcher()

    cmd: list[str] = [
        *launcher,
        "webview",
        "_run",
        str(resolved),
        "--port",
        str(port),
        "--host",
        host,
    ]

    log_path = resolved / ".webview.log"
    log_file = open(log_path, "w")  # noqa: SIM115

    proc = subprocess.Popen(
        cmd,
        start_new_session=True,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    # Close the parent-side copy immediately — the subprocess keeps its own
    # inherited fd (WR-02).  log_path.read_text() below opens a fresh fd.
    log_file.close()

    # Port-squat guard: give uvicorn 0.5 s to bind; if it already exited,
    # the port was stolen (T-90-05).
    time.sleep(0.5)
    if proc.poll() is not None:
        # Read the tail of the log for the error message.
        try:
            tail = log_path.read_text()[-2000:]
        except OSError:
            tail = "<log unreadable>"
        raise RuntimeError(
            f"Webview subprocess exited immediately (returncode={proc.returncode}). "
            f"The port may have been taken by another process.\n"
            f"Log tail:\n{tail}"
        )

    state = WebviewState.create(proc.pid, port, host, resolved)
    state.save(resolved)
    return state


def status(analysis_dir: Path) -> WebviewState | None:
    """Return the current server state for *analysis_dir*, or ``None``.

    Probes PID liveness via :meth:`~WebviewState.is_alive`.  If the state
    file exists but the recorded PID is dead (stale file left by a crash or
    SIGKILL), removes the file and returns ``None`` (T-90-06 mitigation).

    Args:
        analysis_dir: Path to the CASE analysis directory.

    Returns:
        :class:`WebviewState` if a live server is running, else ``None``.
    """
    state_file = Path(analysis_dir) / ".webview.json"
    if not state_file.exists():
        return None

    try:
        state = WebviewState.load(Path(analysis_dir))
    except Exception:
        # Corrupt or unreadable state file (partial write, schema change, etc.)
        # — treat as stale so status() returns None rather than crashing.
        state_file.unlink(missing_ok=True)
        return None

    if state.is_alive():
        return state

    # Stale file — remove it so subsequent calls start fresh.
    state_file.unlink(missing_ok=True)
    return None


def stop(analysis_dir: Path) -> tuple[bool, int | None]:
    """Stop the webview server for *analysis_dir*.

    Sends ``SIGTERM`` first, polls for up to ~3 s (15 × 0.2 s), then
    escalates to ``SIGKILL`` if the process is still alive.  Always
    removes ``.webview.json`` on a successful stop (T-90-06 mitigation).

    Args:
        analysis_dir: Path to the CASE analysis directory.

    Returns:
        A ``(stopped, pid)`` tuple where *stopped* is ``True`` if a
        running server was found and terminated, and *pid* is its PID
        (or ``None`` if no server was found).
    """
    state_file = Path(analysis_dir) / ".webview.json"
    if not state_file.exists():
        return (False, None)

    try:
        state = WebviewState.load(Path(analysis_dir))
    except Exception:
        # Corrupt or unreadable state file — clean up rather than crashing.
        state_file.unlink(missing_ok=True)
        return (False, None)
    pid = state.pid

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        # Process already dead — clean up the stale file and report.
        state_file.unlink(missing_ok=True)
        return (False, pid)
    except PermissionError:
        # PID recycled to a process owned by a different user (WR-01).
        # Treat as not-ours — do not escalate, just clean up the stale file.
        state_file.unlink(missing_ok=True)
        return (False, pid)

    # Poll up to ~3 s for the process to exit.
    for _ in range(15):
        time.sleep(0.2)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break  # Process has exited.
        except PermissionError:
            # PID recycled to another user's process — stop signalling it
            # and do not escalate to SIGKILL (CR-01).
            break
    else:
        # Process still alive after 3 s — escalate to SIGKILL.
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass  # Died between poll and SIGKILL, or belongs to different user.

    state_file.unlink(missing_ok=True)
    return (True, pid)
