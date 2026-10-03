"""Persistent server state model for the ailsa webview server.

``WebviewState`` is written to ``<analysis_dir>/.webview.json`` by
``server.start()`` and read back by ``server.status()`` / ``server.stop()``.
No fastapi or uvicorn imports are allowed here (WV-08 import-safety).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


class WebviewState(BaseModel):
    """Persistent state written to <analysis_dir>/.webview.json."""

    pid: int
    port: int
    host: str
    url: str
    analysis_dir: str  # absolute path, stored as str for JSON portability
    started_at: str  # ISO 8601 UTC, e.g. "2026-07-03T07:00:00+00:00"

    @classmethod
    def create(
        cls,
        pid: int,
        port: int,
        host: str,
        analysis_dir: Path,
    ) -> WebviewState:
        """Build a new state object from process parameters.

        Args:
            pid: PID of the server process (or its detached child).
            port: TCP port the server is listening on.
            host: Bind address (e.g. ``"127.0.0.1"``).
            analysis_dir: Path to the CASE analysis directory.

        Returns:
            A populated :class:`WebviewState` ready to be serialised.
        """
        url = f"http://{host}:{port}"
        return cls(
            pid=pid,
            port=port,
            host=host,
            url=url,
            analysis_dir=str(analysis_dir.resolve()),
            started_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def save(self, analysis_dir: Path) -> None:
        """Write this state to ``<analysis_dir>/.webview.json`` (indent=2)."""
        (analysis_dir / ".webview.json").write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, analysis_dir: Path) -> WebviewState:
        """Read and deserialise state from ``<analysis_dir>/.webview.json``."""
        return cls.model_validate_json(
            (analysis_dir / ".webview.json").read_text()
        )

    def is_alive(self) -> bool:
        """Return ``True`` if the server process is still running.

        Uses POSIX signal 0 (no actual signal delivered) to probe the PID.
        ``PermissionError`` means the PID exists but belongs to a different
        user — treat as not-our-process (dead from our perspective) so that
        a stale ``.webview.json`` whose PID was recycled to a foreign process
        does not permanently block :func:`~ailsa.webview.server.start`.
        """
        try:
            os.kill(self.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # PID recycled to a process owned by another user.
            return False
