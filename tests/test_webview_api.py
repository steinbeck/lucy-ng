"""Tests for Phase 91 API endpoints, depiction, frontend, and packaging.

Wave 0 Nyquist scaffold — these tests are RED until Plans 02/03/04 land.
Each class maps to a target plan for traceability.

Test status legend:
  RED  = ImportError / AssertionError expected until implementation ships
  SKIP = webview extra absent or target modules not yet available

Import rule (WV-08): ALL imports of fastapi and lucy_ng.webview.* are
INSIDE test function bodies — never at module level — so this file
collects cleanly even before the router modules exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tomllib

# ---------------------------------------------------------------------------
# TestStatusEndpoint [→ Plan 02]
# ---------------------------------------------------------------------------


class TestStatusEndpoint:
    """WV-03 / WV-06: GET /api/status returns live status or waiting payload."""

    def test_waiting_when_empty(self, empty_analysis_dir: Path) -> None:
        """Empty analysis dir → state == 'waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import status  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or status router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(status.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/status")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["state"] == "waiting", f"Expected state=waiting: {r.json()}"

    def test_live_from_timing_jsonl(self, live_analysis_dir: Path) -> None:
        """Live run (timing.jsonl only) → state in {running,waiting}, iteration set."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import status  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or status router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(status.make_router(live_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/status")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["state"] in ("running", "waiting"), (
            f"Expected state in {{running,waiting}}: {data}"
        )
        assert data.get("iteration") is not None, (
            f"Expected iteration to be set from timing.jsonl: {data}"
        )

    def test_complete_from_timing_json(self, final_analysis_dir: Path) -> None:
        """Finalized run (timing.json) → state == 'complete', elapsed_s == 5400."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import status  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or status router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(status.make_router(final_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/status")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["state"] == "complete", f"Expected state=complete: {data}"
        assert data.get("elapsed_s") == 5400, (
            f"Expected elapsed_s=5400 from timing.json total_duration_s: {data}"
        )


# ---------------------------------------------------------------------------
# TestLogEndpoint [→ Plan 02]
# ---------------------------------------------------------------------------


class TestLogEndpoint:
    """WV-05 / WV-06: GET /api/log returns CASE-PROGRESS.md content or waiting."""

    def test_log_returns_content(self, live_analysis_dir: Path) -> None:
        """Live dir with CASE-PROGRESS.md → state=='ok', content contains 'Iteration 1'."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import log  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or log router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(log.make_router(live_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/log")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("state") == "ok", f"Expected state=ok: {data}"
        assert "Iteration 1" in data.get("content", ""), (
            f"Expected 'Iteration 1' in log content: {data}"
        )

    def test_log_waiting_when_empty(self, empty_analysis_dir: Path) -> None:
        """Empty dir → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import log  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or log router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(log.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/log")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["state"] == "waiting", f"Expected state=waiting: {r.json()}"


# ---------------------------------------------------------------------------
# TestStructuresEndpoint [→ Plan 03]
# ---------------------------------------------------------------------------


class TestStructuresEndpoint:
    """WV-04 / WV-06: GET /api/structures and GET /api/structure/{i}.svg."""

    def test_unranked_from_solutions_smi(self, live_analysis_dir: Path) -> None:
        """Live dir (no ranking_results.json) → source=='unranked', <=10 structures."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                structures,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or structures router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(structures.make_router(live_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/structures")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["source"] == "unranked", f"Expected source=unranked: {data}"
        assert len(data["structures"]) <= 10, (
            f"Expected at most 10 structures: {len(data['structures'])}"
        )

    def test_ranked_from_ranking_results(self, final_analysis_dir: Path) -> None:
        """Final dir (ranking_results.json) → source=='ranked', first rank==1, mae set."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                structures,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or structures router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(structures.make_router(final_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/structures")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["source"] == "ranked", f"Expected source=ranked: {data}"
        assert len(data["structures"]) >= 1, "Expected at least one ranked structure"
        first = data["structures"][0]
        assert first["rank"] == 1, f"Expected first rank==1: {first}"
        assert first["mae"] is not None, f"Expected mae set for ranked: {first}"

    def test_ranked_with_null_rank_does_not_drop_tier(self, tmp_path: Path) -> None:
        """A present-but-null rank must NOT crash the ranked tier into unranked (CR-01)."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                structures,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or structures router not yet available")

        import json as _json

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        solutions = [
            {"rank": 2, "solution_index": 1, "smiles": "CCO", "mae": 0.3, "quality": "ok"},
            {"rank": None, "solution_index": 2, "smiles": "CCN", "mae": None, "quality": None},
            {"rank": 1, "solution_index": 0, "smiles": "c1ccccc1", "mae": 0.1, "quality": "ok"},
        ]
        (tmp_path / "ranking_results.json").write_text(
            _json.dumps({"solutions": solutions, "total_solutions": 3}),
            encoding="utf-8",
        )

        app = FastAPI()
        app.include_router(structures.make_router(tmp_path))

        with TestClient(app) as client:
            r = client.get("/api/structures")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["source"] == "ranked", f"null rank must not drop ranked tier: {data}"
        assert data["structures"][0]["rank"] == 1, "rank 1 must sort first"
        assert data["structures"][-1]["rank"] is None, "null rank must sort last"

    def test_out_of_range_svg_returns_404(self, live_analysis_dir: Path) -> None:
        """GET /api/structure/999.svg → 404 when index is out of range."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                structures,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or structures router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(structures.make_router(live_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/structure/999.svg")

        assert r.status_code == 404, f"Expected 404 for out-of-range index, got {r.status_code}"

    def test_malformed_smiles_returns_placeholder_svg(self, live_analysis_dir: Path) -> None:
        """Index 2 (malformed SMILES) → 200, image/svg+xml, placeholder content."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                structures,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or structures router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(structures.make_router(live_analysis_dir))

        with TestClient(app) as client:
            # Index 2 is "not_a_real_smiles_XXXX" in the live fixture
            r = client.get("/api/structure/2.svg")

        assert r.status_code == 200, (
            f"Expected 200 for malformed SMILES placeholder, got {r.status_code}"
        )
        assert "image/svg+xml" in r.headers.get("content-type", ""), (
            f"Expected image/svg+xml content-type: {r.headers.get('content-type')}"
        )
        # Placeholder SVG contains grey rect or question mark
        assert "?" in r.text or "rect" in r.text, (
            f"Expected placeholder SVG with '?' or 'rect': {r.text[:200]}"
        )

    def test_valid_smiles_returns_real_svg(self, live_analysis_dir: Path) -> None:
        """Index 0 (aspirin — valid SMILES) → 200, image/svg+xml, RDKit path elements."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                structures,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or structures router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(structures.make_router(live_analysis_dir))

        with TestClient(app) as client:
            # Index 0 is "CC(=O)Oc1ccccc1C(=O)O" (aspirin) — valid SMILES
            r = client.get("/api/structure/0.svg")

        assert r.status_code == 200, f"Expected 200 for valid SMILES, got {r.status_code}"
        assert "image/svg+xml" in r.headers.get("content-type", ""), (
            f"Expected image/svg+xml content-type: {r.headers.get('content-type')}"
        )
        # Real RDKit SVG contains path or line drawing elements
        assert "<path" in r.text or "<line" in r.text, (
            f"Expected RDKit SVG drawing elements: {r.text[:300]}"
        )


# ---------------------------------------------------------------------------
# TestDepiction [→ Plan 03]
# ---------------------------------------------------------------------------


class TestDepiction:
    """WV-04: lucy_ng.webview.depiction render/placeholder functions."""

    def test_render_valid_smiles_returns_svg_string(self) -> None:
        """render_smiles('c1ccccc1') returns a str containing 'svg'."""
        try:
            from lucy_ng.webview.depiction import (
                render_smiles,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("lucy_ng.webview.depiction not yet available")

        result = render_smiles("c1ccccc1")
        assert result is not None, "Expected SVG string for valid benzene SMILES"
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert "svg" in result.lower(), "Expected 'svg' in render result"

    def test_render_malformed_smiles_returns_none(self) -> None:
        """render_smiles('not_a_real_smiles_XXXX') returns None."""
        try:
            from lucy_ng.webview.depiction import (
                render_smiles,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("lucy_ng.webview.depiction not yet available")

        result = render_smiles("not_a_real_smiles_XXXX")
        assert result is None, f"Expected None for malformed SMILES, got: {result!r}"

    def test_render_never_raises_on_draw_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """render_smiles returns None (never raises) if RDKit drawing fails (CR-02).

        A SMILES can parse via MolFromSmiles yet fail 2D preparation (e.g.
        KekulizeException); the endpoint must degrade to a placeholder, not 500.
        """
        try:
            from lucy_ng.webview import depiction  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("lucy_ng.webview.depiction not yet available")

        def _boom(*_a: object, **_k: object) -> None:
            raise RuntimeError("simulated kekulize/draw failure")

        monkeypatch.setattr(depiction, "PrepareMolForDrawing", _boom)
        result = depiction.render_smiles("c1ccccc1")
        assert result is None, f"Expected None when drawing raises, got: {result!r}"

    def test_placeholder_svg_returns_svg_string(self) -> None:
        """placeholder_svg() returns a str containing 'svg'."""
        try:
            from lucy_ng.webview.depiction import (
                placeholder_svg,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("lucy_ng.webview.depiction not yet available")

        result = placeholder_svg()
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert "svg" in result.lower(), "Expected 'svg' in placeholder result"


# ---------------------------------------------------------------------------
# TestFrontend [→ Plan 04]
# ---------------------------------------------------------------------------


class TestFrontend:
    """WV-06: GET / serves index.html with Content-Type text/html."""

    def test_index_html_served(self, live_analysis_dir: Path) -> None:
        """GET / → HTTP 200, Content-Type starts with 'text/html'."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.app import create_app  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or create_app not yet available")

        with TestClient(create_app(live_analysis_dir)) as client:
            r = client.get("/")

        assert r.status_code == 200, f"Expected 200 for GET /, got {r.status_code}: {r.text[:200]}"
        content_type = r.headers.get("content-type", "")
        assert content_type.startswith("text/html"), (
            f"Expected content-type to start with text/html: {content_type!r}"
        )

    def test_webview_js_served(self, live_analysis_dir: Path) -> None:
        """GET /webview.js → HTTP 200, Content-Type starts with 'application/javascript'."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.app import create_app  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or create_app not yet available")

        with TestClient(create_app(live_analysis_dir)) as client:
            r = client.get("/webview.js")

        assert r.status_code == 200, (
            f"Expected 200 for GET /webview.js, got {r.status_code}: {r.text[:200]}"
        )
        content_type = r.headers.get("content-type", "")
        assert content_type.startswith("application/javascript") or content_type.startswith(
            "text/javascript"
        ), f"Expected content-type to start with application/javascript: {content_type!r}"


# ---------------------------------------------------------------------------
# TestWiring [→ Plan 04]
# ---------------------------------------------------------------------------


class TestWiring:
    """WV-03/04/05: create_app() docks all three routers — each returns 200."""

    def test_all_api_endpoints_reachable(self, live_analysis_dir: Path) -> None:
        """GET /api/status, /api/structures, /api/log each return 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.app import create_app  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or create_app not yet available")

        with TestClient(create_app(live_analysis_dir)) as client:
            r_status = client.get("/api/status")
            r_structures = client.get("/api/structures")
            r_log = client.get("/api/log")

        assert r_status.status_code == 200, (
            f"GET /api/status expected 200, got {r_status.status_code}: {r_status.text}"
        )
        assert r_structures.status_code == 200, (
            f"GET /api/structures expected 200, got {r_structures.status_code}: {r_structures.text}"
        )
        assert r_log.status_code == 200, (
            f"GET /api/log expected 200, got {r_log.status_code}: {r_log.text}"
        )


# ---------------------------------------------------------------------------
# TestPackaging [→ Plan 04]
# ---------------------------------------------------------------------------


class TestPackaging:
    """WV-08: pyproject.toml hatch artifacts include src/lucy_ng/webview/static/*."""

    def test_hatch_artifacts_include_static(self) -> None:
        """[tool.hatch.build.targets.wheel].artifacts contains 'src/lucy_ng/webview/static/*'."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as fh:
            pyproject = tomllib.load(fh)

        artifacts: list[str] = (
            pyproject.get("tool", {})
            .get("hatch", {})
            .get("build", {})
            .get("targets", {})
            .get("wheel", {})
            .get("artifacts", [])
        )

        assert "src/lucy_ng/webview/static/*" in artifacts, (
            f"'src/lucy_ng/webview/static/*' not found in hatch wheel artifacts.\n"
            f"Current artifacts: {artifacts}"
        )

    def test_webview_js_present_in_static(self) -> None:
        """webview.js exists at the flat static/ level so the existing hatch glob packages it."""
        static_dir = Path(__file__).parent.parent / "src" / "lucy_ng" / "webview" / "static"
        assert (static_dir / "webview.js").exists(), (
            "webview.js must exist at the flat static/ level for the existing hatch glob "
            "to cover it"
        )


# ---------------------------------------------------------------------------
# TestMarkdownRendererSafety [→ Plan 02]
# ---------------------------------------------------------------------------


class TestMarkdownRendererSafety:
    """LOG-01 / D-02: static/webview.js must never assign server content via innerHTML."""

    def test_no_innerhtml_in_source(self) -> None:
        """'innerHTML' must not appear anywhere in static/webview.js (regression guard)."""
        js_path = (
            Path(__file__).parent.parent
            / "src" / "lucy_ng" / "webview" / "static" / "webview.js"
        )
        if not js_path.exists():
            pytest.skip("webview.js not yet extracted")
        source = js_path.read_text(encoding="utf-8")
        assert "innerHTML" not in source, (
            "webview.js must never use innerHTML (XSS guard, D-02) — "
            "found the literal substring 'innerHTML' in the source"
        )


# ---------------------------------------------------------------------------
# Phase 94 fixtures — hand-authored to the CONTEXT.md LOCKED peaks-JSON schema.
#
# No on-disk analysis/ directory on this machine matches these exact field
# names (RESEARCH.md Assumptions A1-A5) — these fixtures are built by hand to
# the canonical_refs schema, not copied from any real run.
# ---------------------------------------------------------------------------


@pytest.fixture
def tables_analysis_dir(tmp_path: Path) -> Path:
    """analysis_dir with peaks/{carbon_signals,hsqc,hmbc,cosy}.json (LOCKED schema).

    Hand-authored to CONTEXT.md's `<canonical_refs>` "Data shapes" field names.
    Includes at least one HMBC row per flag value (ok/potential_4J/1J_artifact)
    and one large intensity (5559614) to exercise the compact-intensity
    formatter target downstream (frontend, Plan 03).
    """
    import json as _json

    peaks_dir = tmp_path / "peaks"
    peaks_dir.mkdir()

    (peaks_dir / "carbon_signals.json").write_text(
        _json.dumps(
            {
                "formula": "C14H16",
                "dbe": 6,
                "solvent": "CDCl3",
                "note": "9 signals, 2 overlapping aromatic CH pairs",
                "signals": [
                    {
                        "atom": 1,
                        "ppm": 172.4,
                        "mult": "s",
                        "nC": 1,
                        "assignment": "C=O",
                        "confidence": "high",
                    },
                    {
                        "atom": 2,
                        "ppm": 128.9,
                        "mult": "d",
                        "nC": 2,
                        "assignment": "ArCH",
                        "confidence": "medium",
                    },
                    {
                        "atom": 3,
                        "ppm": 21.3,
                        "mult": "q",
                        "nC": 1,
                        "assignment": "ArCH3",
                        "confidence": "high",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (peaks_dir / "hsqc.json").write_text(
        _json.dumps(
            {
                "experiment": "hsqcedetgp",
                "count": 3,
                "note": "3 one-bond C-H correlations, all matched to real carbons",
                "peaks": [
                    {
                        "carbon_ppm": 128.9,
                        "proton_ppm": 7.31,
                        "intensity": 5559614,
                        "matched_real_carbon": True,
                        "one_bond": True,
                    },
                    {
                        "carbon_ppm": 21.3,
                        "proton_ppm": 2.35,
                        "intensity": 1520340,
                        "matched_real_carbon": True,
                        "one_bond": True,
                    },
                    {
                        "carbon_ppm": 55.2,
                        "proton_ppm": 3.68,
                        "intensity": 980210,
                        "matched_real_carbon": False,
                        "one_bond": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (peaks_dir / "hmbc.json").write_text(
        _json.dumps(
            {
                "experiment": "hmbcgplpndqf",
                "raw_count": 913,
                "kept_count": 29,
                "flag_rules": "1J_artifact = matches an HSQC one-bond pair; "
                "potential_4J = 4-bond aromatic candidate",
                "note": "29 kept of 913 raw correlations after curation",
                "peaks": [
                    {
                        "carbon_ppm": 172.4,
                        "carbon_ppm_observed": 172.5,
                        "proton_ppm": 7.31,
                        "intensity": 445210,
                        "flag": "ok",
                    },
                    {
                        "carbon_ppm": 128.9,
                        "carbon_ppm_observed": 128.8,
                        "proton_ppm": 2.35,
                        "intensity": 210330,
                        "flag": "potential_4J",
                    },
                    {
                        "carbon_ppm": 21.3,
                        "carbon_ppm_observed": 21.2,
                        "proton_ppm": 2.35,
                        "intensity": 5559614,
                        "flag": "1J_artifact",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (peaks_dir / "cosy.json").write_text(
        _json.dumps(
            {
                "experiment": "cosygpqf",
                "count": 2,
                "note": "2 vicinal proton-proton correlations",
                "peaks": [
                    {"proton_a_ppm": 7.31, "proton_b_ppm": 7.28, "intensity": 335120},
                    {"proton_a_ppm": 3.68, "proton_b_ppm": 2.35, "intensity": 118400},
                ],
            }
        ),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def tables_iterations_dir(tmp_path: Path) -> Path:
    """analysis_dir with a multi-iteration compound.lsd set (D-02 selection target).

    iteration_01/compound.lsd    — bare, iteration=1
    iteration_02_anchor_recovery/compound.lsd — family-suffixed, iteration=2,
    HIGHER numeric prefix, exercising the "highest iteration_(\\d+), across
    families" selection logic (D-02).
    """

    def _inventory_block(iteration: int) -> str:
        lines = [
            "; === CONSTRAINT INVENTORY v2 ===",
            f'; {{"version": 2, "iteration": {iteration}, "formula": "C14H16",',
            '; "timestamp": "2026-07-09T10:00:00Z",',
            f'; "mult_count": {9 + iteration}, "hsqc_count": {3 + iteration},',
            '; "hmbc_batches": [{"batch": 1, "count": 2, "correlations": ["1 2", "2 3"]}],',
            f'; "hmbc_total": {2 + iteration},',
            '; "bond_constraints": ["1 2"],',
            '; "cosy_equiv_pairs": [],',
            '; "applied_from_detection": ["no heteroatom constraints (pure-carbon formula)"],',
            '; "pending_from_detection": ["deferred 4J pair still held out"],',
            '; "deff_fexp": {"status": "none", "fragment_smiles": null},',
            '; "elim_budget": 0,',
            '; "ring_exclusion_enabled": true}',
            "; === END CONSTRAINT INVENTORY ===",
            ";",
            "MULT 1 C 3 3    ; CH3",
            "",
        ]
        return "\n".join(lines)

    iter1_dir = tmp_path / "iteration_01"
    iter1_dir.mkdir()
    (iter1_dir / "compound.lsd").write_text(_inventory_block(1), encoding="utf-8")

    iter2_dir = tmp_path / "iteration_02_anchor_recovery"
    iter2_dir.mkdir()
    (iter2_dir / "compound.lsd").write_text(_inventory_block(2), encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# TestTablesEndpoint [→ Plan 02]
#
# RED-by-skip until src/lucy_ng/webview/routers/tables.py exists (WV-08).
# Covers TBL-01/02/03 and the SC4 degradation contract independently for
# all 5 panels (carbon, hsqc, hmbc, cosy, constraints).
# ---------------------------------------------------------------------------


class TestTablesEndpoint:
    """TBL-01/02/03: GET /api/tables/{carbon,hsqc,hmbc,cosy,constraints}."""

    def test_carbon_returns_rows(self, tables_analysis_dir: Path) -> None:
        """/api/tables/carbon → state=='ok', rows expose ppm/mult/nC/assignment/confidence."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(tables_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/carbon")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("state") == "ok", f"Expected state=ok: {data}"
        rows = data.get("rows", [])
        assert len(rows) > 0, f"Expected non-empty rows: {data}"
        for field in ("ppm", "mult", "nC", "assignment", "confidence"):
            assert field in rows[0], f"Expected {field!r} in carbon row: {rows[0]}"

    def test_carbon_waiting_when_absent(self, empty_analysis_dir: Path) -> None:
        """/api/tables/carbon on an empty analysis dir → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/carbon")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_hsqc_cosy_return_ok(self, tables_analysis_dir: Path) -> None:
        """/api/tables/hsqc and /api/tables/cosy both → state=='ok' with their field sets."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(tables_analysis_dir))

        with TestClient(app) as client:
            r_hsqc = client.get("/api/tables/hsqc")
            r_cosy = client.get("/api/tables/cosy")

        assert r_hsqc.status_code == 200, f"Expected 200, got {r_hsqc.status_code}: {r_hsqc.text}"
        hsqc_data = r_hsqc.json()
        assert hsqc_data.get("state") == "ok", f"Expected state=ok: {hsqc_data}"
        hsqc_rows = hsqc_data.get("rows", [])
        assert len(hsqc_rows) > 0, f"Expected non-empty hsqc rows: {hsqc_data}"
        for field in ("carbon_ppm", "proton_ppm", "intensity", "matched_real_carbon", "one_bond"):
            assert field in hsqc_rows[0], f"Expected {field!r} in hsqc row: {hsqc_rows[0]}"

        assert r_cosy.status_code == 200, f"Expected 200, got {r_cosy.status_code}: {r_cosy.text}"
        cosy_data = r_cosy.json()
        assert cosy_data.get("state") == "ok", f"Expected state=ok: {cosy_data}"
        cosy_rows = cosy_data.get("rows", [])
        assert len(cosy_rows) > 0, f"Expected non-empty cosy rows: {cosy_data}"
        for field in ("proton_a_ppm", "proton_b_ppm", "intensity"):
            assert field in cosy_rows[0], f"Expected {field!r} in cosy row: {cosy_rows[0]}"

    def test_hmbc_preserves_flag_verbatim(self, tables_analysis_dir: Path) -> None:
        """/api/tables/hmbc rows retain each flag value UNMODIFIED (colouring is frontend-only)."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(tables_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/hmbc")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("state") == "ok", f"Expected state=ok: {data}"
        rows = data.get("rows", [])
        flags = {row.get("flag") for row in rows}
        assert flags == {"ok", "potential_4J", "1J_artifact"}, (
            f"Expected flag set {{'ok','potential_4J','1J_artifact'}}, got {flags}: {data}"
        )

    def test_malformed_json_returns_waiting(self, tmp_path: Path) -> None:
        """Invalid JSON in carbon_signals.json → /api/tables/carbon state=='waiting', never 500."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        peaks_dir = tmp_path / "peaks"
        peaks_dir.mkdir()
        (peaks_dir / "carbon_signals.json").write_text("{not valid", encoding="utf-8")

        app = FastAPI()
        app.include_router(tables.make_router(tmp_path))

        with TestClient(app) as client:
            r = client.get("/api/tables/carbon")

        assert r.status_code == 200, f"Expected 200 (never 500), got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_constraints_selects_highest_iteration(self, tables_iterations_dir: Path) -> None:
        """/api/tables/constraints selects iteration_02_anchor_recovery (highest numeric prefix)."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(tables_iterations_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/constraints")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("state") == "ok", f"Expected state=ok: {data}"
        inventory = data.get("inventory", {})
        assert inventory.get("iteration") == 2, (
            f"Expected the family-suffixed iteration_02_anchor_recovery (iteration==2) "
            f"to win by highest numeric prefix: {data}"
        )

    def test_constraints_waiting_when_malformed(self, tmp_path: Path) -> None:
        """START delimiter present but no END delimiter → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        iter_dir = tmp_path / "iteration_01"
        iter_dir.mkdir()
        (iter_dir / "compound.lsd").write_text(
            '; === CONSTRAINT INVENTORY v2 ===\n'
            '; {"version": 2, "iteration": 1\n'
            "MULT 1 C 3 3    ; CH3\n",
            encoding="utf-8",
        )

        app = FastAPI()
        app.include_router(tables.make_router(tmp_path))

        with TestClient(app) as client:
            r = client.get("/api/tables/constraints")

        assert r.status_code == 200, f"Expected 200 (never 500), got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_constraints_waiting_when_absent(self, empty_analysis_dir: Path) -> None:
        """No iteration_NN/compound.lsd at all → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/constraints")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_hsqc_waiting_when_absent(self, empty_analysis_dir: Path) -> None:
        """/api/tables/hsqc on an empty analysis dir → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/hsqc")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_hsqc_waiting_when_malformed(self, tmp_path: Path) -> None:
        """Invalid JSON in hsqc.json → state=='waiting', never 500."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        peaks_dir = tmp_path / "peaks"
        peaks_dir.mkdir()
        (peaks_dir / "hsqc.json").write_text("{not valid", encoding="utf-8")

        app = FastAPI()
        app.include_router(tables.make_router(tmp_path))

        with TestClient(app) as client:
            r = client.get("/api/tables/hsqc")

        assert r.status_code == 200, f"Expected 200 (never 500), got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_hmbc_waiting_when_absent(self, empty_analysis_dir: Path) -> None:
        """/api/tables/hmbc on an empty analysis dir → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/hmbc")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_hmbc_waiting_when_malformed(self, tmp_path: Path) -> None:
        """Invalid JSON in hmbc.json → state=='waiting', never 500."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        peaks_dir = tmp_path / "peaks"
        peaks_dir.mkdir()
        (peaks_dir / "hmbc.json").write_text("{not valid", encoding="utf-8")

        app = FastAPI()
        app.include_router(tables.make_router(tmp_path))

        with TestClient(app) as client:
            r = client.get("/api/tables/hmbc")

        assert r.status_code == 200, f"Expected 200 (never 500), got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_cosy_waiting_when_absent(self, empty_analysis_dir: Path) -> None:
        """/api/tables/cosy on an empty analysis dir → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(tables.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/tables/cosy")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"

    def test_cosy_waiting_when_malformed(self, tmp_path: Path) -> None:
        """Invalid JSON in cosy.json → state=='waiting', never 500."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import tables  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or tables router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        peaks_dir = tmp_path / "peaks"
        peaks_dir.mkdir()
        (peaks_dir / "cosy.json").write_text("{not valid", encoding="utf-8")

        app = FastAPI()
        app.include_router(tables.make_router(tmp_path))

        with TestClient(app) as client:
            r = client.get("/api/tables/cosy")

        assert r.status_code == 200, f"Expected 200 (never 500), got {r.status_code}: {r.text}"
        assert r.json().get("state") == "waiting", f"Expected state=waiting: {r.json()}"


# ---------------------------------------------------------------------------
# Phase 95 fixtures — TestSpectraEndpoint [→ Plan 02]
#
# CASE1_ROOT is the real Bruker dataset used for the SC2 reversed-axis /
# carbonyl-left-of-aliphatic check (RESEARCH.md). Tests relying on it must
# skip (not fail) when the local Dropbox path is absent — same local-dataset
# caveat already recorded for Phase 94 in STATE.md (Assumption A2).
# ---------------------------------------------------------------------------

CASE1_ROOT = (
    Path.home()
    / "Dropbox"
    / "develop"
    / "data"
    / "nmrdata"
    / "active-lucy-ng-testprojects"
    / "CASE1"
)


@pytest.fixture
def spectra_stale_manifest_dir(tmp_path: Path) -> Path:
    """analysis_dir with a well-formed manifest pointing at a MISSING bruker dir (D-05)."""
    import json as _json

    (tmp_path / ".run_manifest.json").write_text(
        _json.dumps(
            {
                "bruker_data_dir": "/nonexistent/path/does/not/exist",
                "formula": "C13H18O2",
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def spectra_case1_manifest_dir(tmp_path: Path) -> Path:
    """analysis_dir with a manifest pointing at the REAL CASE1 dataset + hand-authored peaks.

    Skips (not fails) when the local CASE1 Dropbox path is absent on this
    machine — do not hard-fail CI on a missing local dataset.
    """
    if not CASE1_ROOT.is_dir():
        pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")

    import json as _json

    (tmp_path / ".run_manifest.json").write_text(
        _json.dumps({"bruker_data_dir": str(CASE1_ROOT), "formula": "C13H18O2"}),
        encoding="utf-8",
    )

    peaks_dir = tmp_path / "peaks"
    peaks_dir.mkdir()
    (peaks_dir / "carbon_signals.json").write_text(
        _json.dumps(
            {
                "formula": "C13H18O2",
                "dbe": 5,
                "solvent": "CDCl3",
                "note": "hand-authored subset for the SC2 axis-direction check (ibuprofen)",
                "signals": [
                    {
                        "atom": 1,
                        "ppm": 180.9,
                        "mult": "s",
                        "nC": 1,
                        "assignment": "C=O",
                        "confidence": "high",
                    },
                    {
                        "atom": 2,
                        "ppm": 45.0,
                        "mult": "d",
                        "nC": 1,
                        "assignment": "CH",
                        "confidence": "high",
                    },
                    {
                        "atom": 3,
                        "ppm": 18.4,
                        "mult": "q",
                        "nC": 1,
                        "assignment": "CH3",
                        "confidence": "medium",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def synthetic_bruker_dir(tmp_path: Path) -> Path:
    """A fake Bruker dataset root: numbered experiment dirs, acqus text only.

    No real FID/pdata is required — the acqu2s-presence exclusion branch must
    run BEFORE any read_1d() call, so a pure-unit test on that branch does not
    need readable spectral data (mirrors CASE1's real exp layout: exp 1 = 1H
    zg30, exp 2 = 13C zgpg30, exp 3 = 13C dept135, exp 5 = 2D w/ acqu2s).
    """
    root = tmp_path / "bruker_root"
    root.mkdir()

    def _write_acqus(exp_dir: Path, nucleus: str, pulse_program: str) -> None:
        exp_dir.mkdir()
        (exp_dir / "acqus").write_text(
            f"##$NUC1= <{nucleus}>\n##$PULPROG= <{pulse_program}>\n",
            encoding="utf-8",
        )

    _write_acqus(root / "1", "1H", "zg30")
    _write_acqus(root / "2", "13C", "zgpg30")
    _write_acqus(root / "3", "13C", "dept135")

    # 2D experiment — acqu2s present, must be excluded BEFORE read_1d is ever called.
    exp5 = root / "5"
    exp5.mkdir()
    (exp5 / "acqus").write_text("##$NUC1= <1H>\n##$PULPROG= <cosygpqf>\n", encoding="utf-8")
    (exp5 / "acqu2s").write_text("##$NUC1= <1H>\n", encoding="utf-8")

    return root


# ---------------------------------------------------------------------------
# TestSpectraEndpoint [→ Plan 02]
#
# RED-by-skip until src/lucy_ng/webview/routers/spectra.py exists (WV-08).
# Covers SP1-01 (real 13C/1H trace, reversed axis, peak overlay, 2D/DEPT
# exclusion) and SP-02 (never-500 "unavailable" on absent manifest / stale
# raw path / missing peaks) — the 8 RESEARCH.md test-map rows plus the SC3
# import guard and the 2D/DEPT-exclusion unit test.
# ---------------------------------------------------------------------------


class TestSpectraEndpoint:
    """SP1-01/SP-02: GET /api/spectra/1d/{carbon,proton} PNG endpoints."""

    def test_apply_nmr_axes_reverses_descending_scale(self) -> None:
        """_apply_nmr_axes(ax, descending_ppm_scale) leaves xlim[0] > xlim[1] (SC2)."""
        try:
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]
                _apply_nmr_axes,
            )
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        import numpy as np
        from matplotlib.figure import Figure  # pyright: ignore[reportMissingModuleSource]

        fig = Figure()
        ax = fig.add_subplot(111)
        ppm_scale = np.array([231.0, 150.0, 80.0, 20.0, -12.0])

        _apply_nmr_axes(ax, ppm_scale)

        xlim = ax.get_xlim()
        assert xlim[0] > xlim[1], f"Expected reversed axis (xlim[0] > xlim[1]), got {xlim}"

    def test_carbon_returns_png_on_case1(self, spectra_case1_manifest_dir: Path) -> None:
        """/api/spectra/1d/carbon on the real CASE1 dataset -> 200 image/png bytes (SP1-01)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_case1_manifest_dir))
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/1d/carbon")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty PNG bytes"

    def test_case1_carbonyl_left_of_aliphatic(self) -> None:
        """Real CASE1 13C axes: reversed (SC2) + carbonyl (~181ppm) left of aliphatic CH3."""
        if not CASE1_ROOT.is_dir():
            pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")
        try:
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]
                _apply_nmr_axes,
                _select_experiment,
            )
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        from matplotlib.figure import Figure  # pyright: ignore[reportMissingModuleSource]

        spectrum = _select_experiment(CASE1_ROOT, "13C")
        assert spectrum is not None, "Expected a 13C Spectrum1D from the real CASE1 dataset"

        fig = Figure()
        ax = fig.add_subplot(111)
        _apply_nmr_axes(ax, spectrum.ppm_scale)

        xlim = ax.get_xlim()
        assert xlim[0] > xlim[1], f"Expected reversed axis, got {xlim}"
        assert xlim[0] > 181 > 14 > xlim[1], (
            f"Expected xlim[0] > 181 > 14 > xlim[1] (carbonyl left of aliphatic CH3), got {xlim}"
        )

    def test_select_experiment_excludes_2d_and_dept(
        self, synthetic_bruker_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_select_experiment never calls read_1d on an acqu2s dir; excludes DEPT (Pitfalls 1/2)."""
        try:
            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        from lucy_ng.readers.bruker import BrukerReader

        called_dirs: list[Path] = []
        original_read_1d = BrukerReader.read_1d

        def _spy_read_1d(experiment_dir: str | Path) -> object:
            called_dirs.append(Path(experiment_dir))
            return original_read_1d(experiment_dir)

        monkeypatch.setattr(BrukerReader, "read_1d", staticmethod(_spy_read_1d))

        spectra._select_experiment(synthetic_bruker_dir, "1H")

        acqu2s_dir = synthetic_bruker_dir / "5"
        assert acqu2s_dir not in called_dirs, (
            f"Expected the acqu2s-bearing dir {acqu2s_dir} to be excluded BEFORE read_1d, "
            f"but read_1d was called on: {called_dirs}"
        )

        if not CASE1_ROOT.is_dir():
            pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")

        spectrum = spectra._select_experiment(CASE1_ROOT, "13C")
        assert spectrum is not None, "Expected a 13C Spectrum1D from the real CASE1 dataset"
        pulse_program = str(spectrum.metadata.get("pulse_program", "")).lower()
        assert "dept" not in pulse_program, (
            f"Expected the standard (non-DEPT) 13C experiment, got pulse_program={pulse_program!r}"
        )

    def test_proton_present_and_carbon_independent(
        self, empty_analysis_dir: Path, tmp_path: Path
    ) -> None:
        """Per-nucleus routes are independently expressible; never-500 holds regardless (SP-02)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        # Unconditional: absent manifest -> BOTH nucleus routes independently return
        # valid PNG bytes, HTTP 200 (SP-02 never-500), regardless of CASE1 availability.
        app_empty = FastAPI()
        app_empty.include_router(spectra.make_router(empty_analysis_dir))
        with TestClient(app_empty) as client:
            r_carbon = client.get("/api/spectra/1d/carbon")
            r_proton = client.get("/api/spectra/1d/proton")

        for label, r in (("carbon", r_carbon), ("proton", r_proton)):
            assert r.status_code == 200, (
                f"Expected 200 for {label}, got {r.status_code}: {r.text[:200]}"
            )
            assert r.headers["content-type"] == "image/png", (
                f"Expected image/png for {label}, got {r.headers.get('content-type')}"
            )
            assert len(r.content) > 0, f"Expected non-empty PNG bytes for {label}"

        # Skippable: with real CASE1 data present, both nuclei should render as "present".
        if not CASE1_ROOT.is_dir():
            pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT} — skipping present-check")

        import json as _json

        manifest_dir = tmp_path / "case1_manifest"
        manifest_dir.mkdir()
        (manifest_dir / ".run_manifest.json").write_text(
            _json.dumps({"bruker_data_dir": str(CASE1_ROOT), "formula": "C13H18O2"}),
            encoding="utf-8",
        )
        app_case1 = FastAPI()
        app_case1.include_router(spectra.make_router(manifest_dir))
        with TestClient(app_case1) as client:
            r_carbon2 = client.get("/api/spectra/1d/carbon")
            r_proton2 = client.get("/api/spectra/1d/proton")

        assert r_carbon2.status_code == 200, (
            f"Expected 200 for carbon, got {r_carbon2.status_code}: {r_carbon2.text[:200]}"
        )
        assert r_carbon2.headers["content-type"] == "image/png"
        assert r_proton2.status_code == 200, (
            f"Expected 200 for proton, got {r_proton2.status_code}: {r_proton2.text[:200]}"
        )
        assert r_proton2.headers["content-type"] == "image/png"

    def test_peak_overlay_positions(self, tmp_path: Path) -> None:
        """PNG bytes differ between an overlay render and a bare-trace render (SP1-01 overlay)."""
        if not CASE1_ROOT.is_dir():
            pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        import json as _json

        def _make_manifest_dir(with_peaks: bool) -> Path:
            d = tmp_path / ("with_peaks" if with_peaks else "without_peaks")
            d.mkdir()
            (d / ".run_manifest.json").write_text(
                _json.dumps({"bruker_data_dir": str(CASE1_ROOT), "formula": "C13H18O2"}),
                encoding="utf-8",
            )
            if with_peaks:
                peaks_dir = d / "peaks"
                peaks_dir.mkdir()
                (peaks_dir / "carbon_signals.json").write_text(
                    _json.dumps(
                        {
                            "signals": [
                                {
                                    "atom": 1,
                                    "ppm": 180.9,
                                    "mult": "s",
                                    "nC": 1,
                                    "assignment": "C=O",
                                    "confidence": "high",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
            return d

        dir_with = _make_manifest_dir(True)
        dir_without = _make_manifest_dir(False)

        app_with = FastAPI()
        app_with.include_router(spectra.make_router(dir_with))
        app_without = FastAPI()
        app_without.include_router(spectra.make_router(dir_without))

        with TestClient(app_with) as client:
            r_with = client.get("/api/spectra/1d/carbon")
        with TestClient(app_without) as client:
            r_without = client.get("/api/spectra/1d/carbon")

        assert r_with.status_code == 200, (
            f"Expected 200, got {r_with.status_code}: {r_with.text[:200]}"
        )
        assert r_without.status_code == 200, (
            f"Expected 200, got {r_without.status_code}: {r_without.text[:200]}"
        )
        assert r_with.content != r_without.content, (
            "Expected the overlay render to differ from the bare-trace render "
            "(peak markers/labels should change the rendered PNG bytes)"
        )

    def test_single_combined_rotated_label_per_peak(self, tmp_path: Path) -> None:
        """95-05: one rotated ppm+assignment label per peak, no separate horizontal one.

        Gap closure for the Wave-3 checkpoint defect (dense-region assignment-label
        collision): assert the source no longer draws a separate horizontal
        assignment-only `ax.text(...)` call anchored at `y_max`, and that the
        combined label folds the assignment into the rotated ppm label. Also
        confirms the endpoint still returns a real, non-empty PNG for two
        near-collinear peaks that both carry assignments (aromatic-region style
        collision case).
        """
        import inspect

        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        source = inspect.getsource(spectra._render_1d_png)
        # The peak loop must call ax.text(...) exactly once per peak now --
        # previously it called it twice (rotated ppm label + separate
        # horizontal assignment label anchored at y_max, the collision
        # source). Count ax.text( occurrences inside the peak loop body
        # (after the "for peak in peaks:" line) as a proxy for "one call".
        loop_start = source.index("for peak in peaks:")
        loop_body = source[loop_start:]
        assert loop_body.count("ax.text(") == 1, (
            f"Expected exactly one ax.text(...) call per peak in the loop body, "
            f"found {loop_body.count('ax.text(')} -- the separate horizontal "
            f"assignment label (anchored at y_max) must be removed"
        )
        assert ", y_max," not in loop_body, (
            "Expected no ax.text(...) call anchored at y_max inside the peak loop "
            "(that was the separate horizontal assignment label -- the collision source)"
        )
        assert "assignment" in loop_body and "f\"{ppm:" in loop_body, (
            "Expected the combined label to be built from an f-string joining ppm and assignment"
        )

        if not CASE1_ROOT.is_dir():
            pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")

        import json as _json

        d = tmp_path / "collision_case"
        d.mkdir()
        (d / ".run_manifest.json").write_text(
            _json.dumps({"bruker_data_dir": str(CASE1_ROOT), "formula": "C13H18O2"}),
            encoding="utf-8",
        )
        peaks_dir = d / "peaks"
        peaks_dir.mkdir()
        (peaks_dir / "carbon_signals.json").write_text(
            _json.dumps(
                {
                    "signals": [
                        {"atom": 1, "ppm": 22.4, "mult": "q", "nC": 1, "assignment": "2xCH3"},
                        {"atom": 2, "ppm": 18.1, "mult": "q", "nC": 1, "assignment": "CH3"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        app = FastAPI()
        app.include_router(spectra.make_router(d))
        with TestClient(app) as client:
            r = client.get("/api/spectra/1d/carbon")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 0, "Expected non-empty PNG bytes"

    def test_missing_manifest_returns_placeholder(self, empty_analysis_dir: Path) -> None:
        """Absent .run_manifest.json -> HTTP 200, placeholder PNG, never 500 (D-01)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )

            app = FastAPI()
            app.include_router(spectra.make_router(empty_analysis_dir))
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/1d/carbon")

        assert r.status_code == 200, (
            f"Expected 200 (never 500), got {r.status_code}: {r.text[:200]}"
        )
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty placeholder PNG bytes"

    def test_stale_bruker_path_returns_placeholder(
        self, spectra_stale_manifest_dir: Path
    ) -> None:
        """Manifest present but bruker_data_dir missing/stale -> HTTP 200 placeholder (D-05)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_stale_manifest_dir))
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/1d/carbon")

        assert r.status_code == 200, (
            f"Expected 200 (never 500), got {r.status_code}: {r.text[:200]}"
        )
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty placeholder PNG bytes"

    def test_missing_peaks_json_renders_bare_trace(self, tmp_path: Path) -> None:
        """Manifest+raw present, no peaks/carbon_signals.json -> trace still renders (SP-02)."""
        if not CASE1_ROOT.is_dir():
            pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
        except ImportError:
            pytest.skip("webview extra or spectra router not yet available")

        import json as _json

        (tmp_path / ".run_manifest.json").write_text(
            _json.dumps({"bruker_data_dir": str(CASE1_ROOT), "formula": "C13H18O2"}),
            encoding="utf-8",
        )
        # Deliberately no peaks/carbon_signals.json — SP-02 partial degradation.

        app = FastAPI()
        app.include_router(spectra.make_router(tmp_path))

        with TestClient(app) as client:
            r = client.get("/api/spectra/1d/carbon")

        assert r.status_code == 200, (
            f"Expected 200 (never 500), got {r.status_code}: {r.text[:200]}"
        )
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty PNG bytes (bare trace, no overlay)"

    def test_no_module_level_matplotlib_import(self) -> None:
        """matplotlib is imported only inside make_router() — never at module level (WV-08/D-04)."""
        spectra_path = (
            Path(__file__).parent.parent
            / "src" / "lucy_ng" / "webview" / "routers" / "spectra.py"
        )
        if not spectra_path.is_file():
            pytest.skip("src/lucy_ng/webview/routers/spectra.py does not exist yet")

        lines = spectra_path.read_text(encoding="utf-8").splitlines()
        make_router_line: int | None = None
        for i, line in enumerate(lines):
            if line.lstrip().startswith("def make_router"):
                make_router_line = i
                break
        assert make_router_line is not None, "Expected a 'def make_router' line in spectra.py"

        for line in lines[:make_router_line]:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            assert not (
                stripped.startswith("import matplotlib") or stripped.startswith("from matplotlib")
            ), f"Found a matplotlib import before 'def make_router': {line!r}"

    def test_cli_imports_without_matplotlib(self) -> None:
        """from lucy_ng.cli import cli succeeds on a base install (SC3 — standing guard)."""
        from lucy_ng.cli import cli  # pyright: ignore[reportMissingModuleSource]  # noqa: F401

        assert cli is not None


# ---------------------------------------------------------------------------
# Phase 96 fixtures — hand-authored to the LOCKED Phase-94 2D peaks-JSON
# schema (96-CONTEXT.md canonical_refs "Cross-peak JSON schemas").
#
# CASE1_ROOT (defined above, Phase 95) already contains real HSQC (exp 6),
# HMBC (exp 7), and COSY (exp 5) 2D experiments (96-RESEARCH.md Pattern 2,
# empirically verified) — no new raw-data fixture is needed, only the
# picked-peaks JSON overlay, which this plan hand-authors per the Wave-0
# gap note (do NOT hand-author a fake 2D pdata/1/2rr).
# ---------------------------------------------------------------------------


@pytest.fixture
def spectra_case1_manifest_dir_2d(tmp_path: Path) -> Path:
    """analysis_dir with a manifest pointing at the REAL CASE1 dataset (2D exps)
    plus hand-authored analysis/peaks/{hsqc,hmbc,cosy}.json fixtures to the
    LOCKED Phase-94 schema (96-CONTEXT.md canonical_refs).

    Skips (not fails) when the local CASE1 Dropbox path is absent on this
    machine — do not hard-fail CI on a missing local dataset (mirrors
    `spectra_case1_manifest_dir`, Phase 95). CASE1 exp 6 = HSQC, exp 7 =
    HMBC, exp 5 = COSY (96-RESEARCH.md Pattern 2, verified via live
    `BrukerReader.read_2d()` execution against the real dataset).
    """
    if not CASE1_ROOT.is_dir():
        pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")

    import json as _json

    (tmp_path / ".run_manifest.json").write_text(
        _json.dumps({"bruker_data_dir": str(CASE1_ROOT), "formula": "C13H18O2"}),
        encoding="utf-8",
    )

    peaks_dir = tmp_path / "peaks"
    peaks_dir.mkdir()

    (peaks_dir / "hsqc.json").write_text(
        _json.dumps(
            {
                "experiment": "hsqcedetgp",
                "count": 2,
                "note": "hand-authored 2D overlay fixture (96-01 Wave 0) — "
                "one aromatic, one aliphatic one-bond C-H correlation",
                "peaks": [
                    {
                        "carbon_ppm": 127.8,
                        "proton_ppm": 7.24,
                        "intensity": 5200000,
                        "matched_real_carbon": True,
                        "one_bond": True,
                    },
                    {
                        "carbon_ppm": 22.1,
                        "proton_ppm": 1.22,
                        "intensity": 1800000,
                        "matched_real_carbon": True,
                        "one_bond": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (peaks_dir / "hmbc.json").write_text(
        _json.dumps(
            {
                "experiment": "hmbcgplpndqf",
                "raw_count": 40,
                "kept_count": 3,
                "flag_rules": "1J_artifact = matches an HSQC one-bond pair; "
                "potential_4J = 4-bond aromatic candidate",
                "note": "hand-authored 2D overlay fixture (96-01 Wave 0) — "
                "covers all three flag values for the SC2 palette assertion",
                "peaks": [
                    {
                        "carbon_ppm": 180.9,
                        "carbon_ppm_observed": 180.8,
                        "proton_ppm": 2.35,
                        "intensity": 445210,
                        "flag": "ok",
                    },
                    {
                        "carbon_ppm": 127.8,
                        "carbon_ppm_observed": 127.7,
                        "proton_ppm": 1.22,
                        "intensity": 210330,
                        "flag": "potential_4J",
                    },
                    {
                        "carbon_ppm": 22.1,
                        "carbon_ppm_observed": 22.0,
                        "proton_ppm": 1.22,
                        "intensity": 1800000,
                        "flag": "1J_artifact",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (peaks_dir / "cosy.json").write_text(
        _json.dumps(
            {
                "experiment": "cosygpqf",
                "count": 2,
                "note": "hand-authored 2D overlay fixture (96-01 Wave 0) — "
                "two vicinal proton-proton correlations",
                "peaks": [
                    {"proton_a_ppm": 7.24, "proton_b_ppm": 7.21, "intensity": 335120},
                    {"proton_a_ppm": 1.22, "proton_b_ppm": 0.88, "intensity": 118400},
                ],
            }
        ),
        encoding="utf-8",
    )

    return tmp_path


# ---------------------------------------------------------------------------
# TestSpectraEndpoint2D [→ Plan 02]
#
# RED-by-skip until src/lucy_ng/webview/routers/spectra.py grows the three
# 2D routes + 2D helpers (WV-08). Every 2D-route-dependent method probes for
# a Plan-02-only symbol (e.g. `_select_experiment_2d`, `_render_2d_png`,
# `_plot_hmbc_overlay`, `_apply_nmr_axes_2d`) via a specific-name import
# INSIDE the same try/except ImportError guard used to detect the fastapi
# [webview] extra — since that symbol does not exist yet, the import raises
# ImportError (not the module import itself), so the method SKIPS cleanly
# rather than failing on a 404 from the not-yet-registered route. Covers all
# 9 96-RESEARCH.md/96-VALIDATION.md Test-Map rows: SP2-01 (real PNG,
# both-axes-reversed, HMBC flag palette), SC3 (render<1s, cache-hit-no-
# rerender), SC4 (cache bounded <=3), SP-02 (never-500 on absent manifest /
# stale path / no matching 2D experiment).
# ---------------------------------------------------------------------------


class TestSpectraEndpoint2D:
    """SP2-01/SC1/SC2/SC3/SC4/SP-02: GET /api/spectra/2d/{hsqc,hmbc,cosy}."""

    def test_spectra_2d_apply_nmr_axes_2d_reverses_both_scales(self) -> None:
        """_apply_nmr_axes_2d places downfield at the top-left corner (SC1).

        F2 (1H, x): high ppm on the LEFT -> xlim[0] > xlim[1].
        F1 (13C, y): high ppm at the TOP -> matplotlib get_ylim() returns
        (bottom, top), so the top endpoint must be the MAX -> ylim[1] > ylim[0].
        The aromatic region (F2 ~7 ppm, F1 ~130 ppm) must land top-left; an
        inverted y (high ppm at the bottom) would put aromatic carbons at the
        bottom, violating SC1.
        """
        try:
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]
                _apply_nmr_axes_2d,
            )
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        import numpy as np
        from matplotlib.figure import Figure  # pyright: ignore[reportMissingModuleSource]

        fig = Figure()
        ax = fig.add_subplot(111)
        f1_ppm_scale = np.array([160.0, 120.0, 40.0, 0.0])  # 13C, descending
        f2_ppm_scale = np.array([9.0, 6.0, 3.0, 0.0])  # 1H, descending

        _apply_nmr_axes_2d(ax, f1_ppm_scale, f2_ppm_scale)

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        # x: high ppm on the left.
        assert xlim[0] > xlim[1], f"Expected high-ppm-left x-axis (xlim[0] > xlim[1]), got {xlim}"
        # y: high ppm at the top (aromatic F1 ~130 top-left, SC1).
        assert ylim[1] > ylim[0], f"Expected high-ppm-top y-axis (ylim[1] > ylim[0]), got {ylim}"
        assert ylim[1] == 160.0, f"Expected downfield endpoint (160) at the top, got top={ylim[1]}"

    def test_spectra_2d_hsqc_returns_png_on_case1_real(
        self, spectra_case1_manifest_dir_2d: Path
    ) -> None:
        """/api/spectra/2d/hsqc on the real CASE1 dataset -> 200 image/png bytes (SP2-01)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_case1_manifest_dir_2d))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/2d/hsqc")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty PNG bytes"

    def test_spectra_2d_hmbc_returns_png_on_case1_real(
        self, spectra_case1_manifest_dir_2d: Path
    ) -> None:
        """/api/spectra/2d/hmbc on the real CASE1 dataset -> 200 image/png bytes (SP2-01)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_case1_manifest_dir_2d))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/2d/hmbc")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty PNG bytes"

    def test_spectra_2d_cosy_returns_png_on_case1_real(
        self, spectra_case1_manifest_dir_2d: Path
    ) -> None:
        """/api/spectra/2d/cosy on the real CASE1 dataset -> 200 image/png bytes (SP2-01)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_case1_manifest_dir_2d))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/2d/cosy")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty PNG bytes"

    def test_spectra_2d_hmbc_flag_color_palette(self) -> None:
        """HMBC overlay colours match the LOCKED flag palette verbatim (SC2/D-06)."""
        import inspect

        try:
            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _plot_hmbc_overlay,
            )
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        # The LOCKED hex palette may live in a module-level dict
        # (_HMBC_FLAG_COLORS) referenced by _plot_hmbc_overlay's source, or be
        # inlined directly in the function body -- inspect both possible
        # locations (96-CONTEXT.md D-06).
        haystack = inspect.getsource(spectra._plot_hmbc_overlay)
        flag_colors = getattr(spectra, "_HMBC_FLAG_COLORS", None)
        if flag_colors is not None:
            haystack += repr(flag_colors)

        for flag, hexcode in (
            ("ok", "#28a745"),
            ("potential_4J", "#ffc107"),
            ("1J_artifact", "#adb5bd"),
        ):
            assert hexcode in haystack, (
                f"Expected LOCKED HMBC hex {hexcode!r} for flag {flag!r} in "
                f"_plot_hmbc_overlay source or _HMBC_FLAG_COLORS, got:\n{haystack}"
            )

    def test_spectra_2d_select_experiment_2d_keeps_only_acqu2s(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_select_experiment_2d never calls read_2d on a non-acqu2s dir; returns matching type."""
        if not CASE1_ROOT.is_dir():
            pytest.skip(f"Real CASE1 dataset not found at {CASE1_ROOT}")
        try:
            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        from lucy_ng.readers.bruker import BrukerReader

        called_dirs: list[Path] = []
        original_read_2d = BrukerReader.read_2d

        def _spy_read_2d(experiment_dir: str | Path) -> object:
            called_dirs.append(Path(experiment_dir))
            return original_read_2d(experiment_dir)

        monkeypatch.setattr(BrukerReader, "read_2d", staticmethod(_spy_read_2d))

        hsqc = spectra._select_experiment_2d(CASE1_ROOT, "HSQC")
        assert hsqc is not None, "Expected a Spectrum2D HSQC from the real CASE1 dataset"
        assert hsqc.experiment_type == "HSQC", (
            f"Expected experiment_type == 'HSQC', got {hsqc.experiment_type!r}"
        )

        cosy = spectra._select_experiment_2d(CASE1_ROOT, "COSY")
        assert cosy is not None, "Expected a Spectrum2D COSY from the real CASE1 dataset"
        assert cosy.experiment_type == "COSY", (
            f"Expected experiment_type == 'COSY', got {cosy.experiment_type!r}"
        )

        for exp_dir in sorted(p for p in CASE1_ROOT.iterdir() if p.is_dir()):
            if not (exp_dir / "acqu2s").exists():
                assert exp_dir not in called_dirs, (
                    f"Expected the non-acqu2s dir {exp_dir} to be excluded BEFORE "
                    f"read_2d, but read_2d was called on: {called_dirs}"
                )

    def test_spectra_2d_render_under_budget(
        self, spectra_case1_manifest_dir_2d: Path
    ) -> None:
        """A single real 2D render completes in < 1.0s (SC3 perf)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_case1_manifest_dir_2d))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        import time

        with TestClient(app) as client:
            start = time.time()
            r = client.get("/api/spectra/2d/hsqc")
            elapsed = time.time() - start

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        assert elapsed < 1.0, f"Expected a single 2D render < 1.0s, took {elapsed:.3f}s"

    def test_spectra_2d_cache_hit_no_rerender(
        self, spectra_case1_manifest_dir_2d: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two identical GETs (unchanged source mtime) call the render fn exactly once (SC3)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]
                _render_2d_png as _original_render,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_case1_manifest_dir_2d))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        spectra._png_cache.clear()

        call_count = {"n": 0}

        def _spy_render(*args: object, **kwargs: object) -> bytes:
            call_count["n"] += 1
            return _original_render(*args, **kwargs)

        monkeypatch.setattr(spectra, "_render_2d_png", _spy_render)

        with TestClient(app) as client:
            r1 = client.get("/api/spectra/2d/hsqc")
            r2 = client.get("/api/spectra/2d/hsqc")

        assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text[:200]}"
        assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text[:200]}"
        assert call_count["n"] == 1, (
            f"Expected the render function to be called exactly once across two "
            f"unchanged-mtime requests (cache hit on the 2nd), got {call_count['n']} calls"
        )

    def test_spectra_2d_cache_bounded(self, spectra_case1_manifest_dir_2d: Path) -> None:
        """Repeated polling across all three 2D routes keeps _png_cache <= 3 entries (SC4)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_case1_manifest_dir_2d))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        spectra._png_cache.clear()

        with TestClient(app) as client:
            for _ in range(2):
                client.get("/api/spectra/2d/hsqc")
                client.get("/api/spectra/2d/hmbc")
                client.get("/api/spectra/2d/cosy")

        assert len(spectra._png_cache) <= 3, (
            f"Expected _png_cache bounded to <= 3 entries after repeated polling "
            f"across all three routes, got {len(spectra._png_cache)}: "
            f"{list(spectra._png_cache.keys())}"
        )

    def test_spectra_2d_missing_manifest_placeholder(self, empty_analysis_dir: Path) -> None:
        """Absent .run_manifest.json -> /api/spectra/2d/hsqc -> HTTP 200 placeholder PNG (SP-02)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(empty_analysis_dir))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/2d/hsqc")

        assert r.status_code == 200, (
            f"Expected 200 (never 500), got {r.status_code}: {r.text[:200]}"
        )
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty placeholder PNG bytes"
        # CR-01: the 2D "unavailable" placeholder MUST share the real 2D render's
        # dimensions (900x600 = _FIGSIZE_2D (9.0, 6.0) x _DPI 100), NOT the 1D
        # placeholder's 900x300 -- otherwise the panel jumps height when a plot
        # flips between "unavailable" and real data (96-UI-SPEC.md: no layout jump).
        import struct

        width, height = struct.unpack(">II", r.content[16:24])
        assert (width, height) == (900, 600), (
            f"Expected 2D placeholder at 900x600 (matches real 2D render), got {width}x{height}"
        )

    def test_spectra_2d_stale_path_placeholder(
        self, spectra_stale_manifest_dir: Path
    ) -> None:
        """Manifest present but bruker_data_dir missing/stale -> HTTP 200 placeholder (SP-02)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )

            app = FastAPI()
            app.include_router(spectra.make_router(spectra_stale_manifest_dir))
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        with TestClient(app) as client:
            r = client.get("/api/spectra/2d/hmbc")

        assert r.status_code == 200, (
            f"Expected 200 (never 500), got {r.status_code}: {r.text[:200]}"
        )
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty placeholder PNG bytes"

    def test_spectra_2d_no_matching_experiment_placeholder(self, tmp_path: Path) -> None:
        """Manifest points at a real but empty dir (no 2D experiment) -> placeholder PNG (SP-02)."""
        try:
            from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import (
                spectra,  # pyright: ignore[reportMissingModuleSource]
            )
            from lucy_ng.webview.routers.spectra import (  # pyright: ignore[reportMissingModuleSource]  # noqa: F401
                _select_experiment_2d,
            )
        except ImportError:
            pytest.skip("webview extra or spectra 2D routes not yet available")

        import json as _json

        manifest_dir = tmp_path / "analysis"
        manifest_dir.mkdir()
        bruker_dir = tmp_path / "empty_bruker_root"
        bruker_dir.mkdir()  # real, empty -- no numbered experiment dirs at all
        (manifest_dir / ".run_manifest.json").write_text(
            _json.dumps({"bruker_data_dir": str(bruker_dir), "formula": "C13H18O2"}),
            encoding="utf-8",
        )

        app = FastAPI()
        app.include_router(spectra.make_router(manifest_dir))

        with TestClient(app) as client:
            r = client.get("/api/spectra/2d/cosy")

        assert r.status_code == 200, (
            f"Expected 200 (never 500), got {r.status_code}: {r.text[:200]}"
        )
        assert r.headers["content-type"] == "image/png", (
            f"Expected image/png, got {r.headers.get('content-type')}"
        )
        assert len(r.content) > 0, "Expected non-empty placeholder PNG bytes"

    def test_spectra_2d_no_module_level_matplotlib_import(self) -> None:
        """2D helpers/imports (matplotlib-free) added by this phase respect WV-08/D-04."""
        spectra_path = (
            Path(__file__).parent.parent
            / "src" / "lucy_ng" / "webview" / "routers" / "spectra.py"
        )
        if not spectra_path.is_file():
            pytest.skip("src/lucy_ng/webview/routers/spectra.py does not exist yet")

        lines = spectra_path.read_text(encoding="utf-8").splitlines()
        make_router_line: int | None = None
        for i, line in enumerate(lines):
            if line.lstrip().startswith("def make_router"):
                make_router_line = i
                break
        assert make_router_line is not None, "Expected a 'def make_router' line in spectra.py"

        for line in lines[:make_router_line]:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            assert not (
                stripped.startswith("import matplotlib") or stripped.startswith("from matplotlib")
            ), f"Found a matplotlib import before 'def make_router': {line!r}"
