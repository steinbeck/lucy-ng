"""Tests for the webview subprocess launcher selection (PKG-03, T-104-07).

``_build_launcher()`` decides which executable the webview server's
detached subprocess uses. It must never choose a lone, possibly-stale
``lucy`` script -- only the renamed ``ailsa`` entry point, or the
``python -m ailsa.cli`` fallback that always runs the current code.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import ailsa.webview.server as server


class TestBuildLauncher:
    """Tests for ``ailsa.webview.server._build_launcher``."""

    def test_prefers_ailsa_when_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_which(name: str) -> str | None:
            return "/x/bin/ailsa" if name == "ailsa" else None

        monkeypatch.setattr(server.shutil, "which", fake_which)
        assert server._build_launcher() == ["ailsa"]

    def test_never_chooses_a_stale_lucy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A `lucy` on PATH with no `ailsa` beside it can only be a stale
        pre-rename install -- it must never be chosen."""

        def fake_which(name: str) -> str | None:
            return "/x/bin/lucy" if name == "lucy" else None

        monkeypatch.setattr(server.shutil, "which", fake_which)
        launcher = server._build_launcher()
        assert launcher == [sys.executable, "-m", "ailsa.cli"]
        assert launcher != ["lucy"]

    def test_falls_back_to_python_module_when_neither_on_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(server.shutil, "which", lambda name: None)
        assert server._build_launcher() == [sys.executable, "-m", "ailsa.cli"]

    def test_importing_server_does_not_leak_fastapi(self) -> None:
        check_code = (
            "import ailsa.webview.server, sys; "
            "leaked = {k for k in sys.modules if k == 'fastapi' or k.startswith('fastapi.')}; "
            "assert not leaked, f'fastapi leaked into webview.server import: {leaked}'"
        )
        result = subprocess.run(
            [sys.executable, "-c", check_code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"ailsa.webview.server import leaked fastapi.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
