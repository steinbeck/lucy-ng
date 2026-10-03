"""GET /api/log router — raw CASE-PROGRESS.md passthrough (WV-05).

Returns:
  {"state": "ok",      "content": "<raw markdown text>"}  when the file exists
  {"state": "waiting", "content": ""}                     when it does not

No server-side markdown rendering (D-12).  The endpoint never raises a 500;
all file-read errors degrade to the waiting payload (D-04).

WV-08 import-safety: this module imports fastapi at module level, which is
permitted because it is ONLY ever imported from inside create_app() and
from test bodies.  It must NOT be imported from webview/__init__.py,
webview/server.py, or webview/state.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter


def make_router(analysis_dir: Path) -> APIRouter:
    """Return an APIRouter(prefix='/api') with a GET /log route.

    Args:
        analysis_dir: Path to the CASE analysis directory (already resolved
            by create_app; do NOT call .resolve() here again).

    Returns:
        An APIRouter with GET /log closed over analysis_dir.
    """
    router = APIRouter(prefix="/api")

    @router.get("/log")
    def get_log() -> dict[str, Any]:
        return _read_log(analysis_dir)

    return router


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_log(analysis_dir: Path) -> dict[str, Any]:
    """Read CASE-PROGRESS.md and return its raw text.

    Returns:
        {"state": "ok", "content": <raw text>}  on success.
        {"state": "waiting", "content": ""}     when the file is absent or
        unreadable (D-04 — never raises a 500).
    """
    progress_md = analysis_dir / "CASE-PROGRESS.md"
    try:
        content = progress_md.read_text(encoding="utf-8")
        return {"state": "ok", "content": content}
    except (FileNotFoundError, OSError):
        return {"state": "waiting", "content": ""}
