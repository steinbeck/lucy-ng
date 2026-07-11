"""FastAPI application factory for the lucy-ng webview dashboard.

This is the ONLY module in the webview package that imports FastAPI at
module level.  All other modules (server.py, state.py, __init__.py) must
remain fastapi-free so that the core ``lucy`` CLI stays importable without
the webview optional extra (WV-08).

Phase 91 will dock additional routers here via ``app.include_router()``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI


def create_app(analysis_dir: Path) -> FastAPI:
    """Create the webview FastAPI application for a given analysis directory.

    Args:
        analysis_dir: Path to the CASE analysis directory to serve.
            Resolved to an absolute path immediately.

    Returns:
        A :class:`FastAPI` application with:
        - ``GET /health`` → ``{"status": "ok", "analysis_dir": "<path>"}``
        - ``GET /api/status`` → live run status (WV-03)
        - ``GET /api/structures`` → candidate structure list (WV-04)
        - ``GET /api/structure/{i}.svg`` → RDKit SVG depiction (WV-04)
        - ``GET /api/log`` → raw CASE-PROGRESS.md content (WV-05)
        - ``GET /api/tables/carbon`` → 13C signal table (TBL-01, Phase 94)
        - ``GET /api/tables/hsqc`` → HSQC correlation table (TBL-02, Phase 94)
        - ``GET /api/tables/hmbc`` → HMBC correlation table (TBL-02, Phase 94)
        - ``GET /api/tables/cosy`` → COSY correlation table (TBL-02, Phase 94)
        - ``GET /api/tables/constraints`` → LSD constraint inventory (TBL-03, Phase 94)
        - ``GET /api/spectra/1d/carbon`` → real 13C 1D trace + peak overlay (SP1-01, Phase 95)
        - ``GET /api/spectra/1d/proton`` → real 1H 1D trace, when present (SP1-01, Phase 95)
        - ``GET /api/spectra/2d/hsqc`` → real HSQC contour + cross-peak overlay (SP2-01, Phase 96)
        - ``GET /api/spectra/2d/hmbc`` → real HMBC contour + flag-coloured overlay
          (SP2-01, Phase 96)
        - ``GET /api/spectra/2d/cosy`` → real COSY contour + diagonal + overlay (SP2-01, Phase 96)
        - ``GET /`` → single-file dashboard (index.html, WV-06)
        - ``GET /webview.js`` → extracted dashboard script (Phase 93)
        - Swagger/ReDoc UI suppressed (``docs_url=None``, ``redoc_url=None``)

    All router and FileResponse imports are inside this function body so that
    ``from lucy_ng.webview import server`` never transitively imports fastapi
    or RDKit on core (non-webview-extra) installs (WV-08).
    """
    app = FastAPI(title="lucy-ng webview", docs_url=None, redoc_url=None)
    analysis_dir = analysis_dir.resolve()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "analysis_dir": str(analysis_dir)}

    # Phase 91: lazy imports — these modules import fastapi/RDKit and must only
    # be reached via create_app(), never at package import time (WV-08).
    from lucy_ng.webview.routers import log as _log  # noqa: PLC0415
    from lucy_ng.webview.routers import spectra as _spectra  # noqa: PLC0415
    from lucy_ng.webview.routers import status as _status  # noqa: PLC0415
    from lucy_ng.webview.routers import structures as _structures  # noqa: PLC0415
    from lucy_ng.webview.routers import tables as _tables  # noqa: PLC0415

    app.include_router(_status.make_router(analysis_dir))
    app.include_router(_structures.make_router(analysis_dir))
    app.include_router(_log.make_router(analysis_dir))
    app.include_router(_tables.make_router(analysis_dir))
    app.include_router(_spectra.make_router(analysis_dir))

    # Serve the single-page frontend at GET / and its extracted script at GET /webview.js
    from fastapi.responses import FileResponse  # noqa: PLC0415

    _static_file = Path(__file__).parent / "static" / "index.html"
    _webview_js = Path(__file__).parent / "static" / "webview.js"

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(_static_file), media_type="text/html")

    @app.get("/webview.js")
    def webview_js() -> FileResponse:
        return FileResponse(str(_webview_js), media_type="application/javascript")

    return app
