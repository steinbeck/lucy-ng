# Phase 95: 1D Real Spectra + Peak Overlay - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 7 (1 new router, 1 new test class, 4 modified, 1 packaging line)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `src/lucy_ng/webview/routers/spectra.py` (NEW) | route/controller (image endpoint) | file-I/O + transform (Bruker→PNG) | `src/lucy_ng/webview/routers/tables.py` (never-500 shape) + `src/lucy_ng/webview/routers/structures.py` (binary/image endpoint) | exact (composite of two analogs) |
| `src/lucy_ng/webview/app.py` (MODIFIED) | provider/wiring | request-response | itself, Phase 94 `_tables` docking block (lines 52-62) | exact (same file, same pattern, one more line) |
| `src/lucy_ng/webview/static/index.html` (MODIFIED) | template/markup | request-response | itself — `spectra-1d`/`spectra-2d` placeholder divs (lines 405-413) + the `tables` panel `<section>` shape (lines 413-424) | exact |
| `src/lucy_ng/webview/static/webview.js` (MODIFIED) | frontend controller/poll | request-response (poll) | itself — `refreshCarbon`/`renderCarbon` (TBL-01, lines 403-443) for the fetch→render→catch shape; `renderStructures`'s `<img>` cache-busted `src` swap (lines 111-145) for the image-tag pattern | exact |
| `tests/test_webview_api.py::TestSpectraEndpoint` (NEW) | test | request-response | `TestTablesEndpoint` (lines 740-825+) + its `tables_analysis_dir` hand-authored fixture (lines 547-686) | exact |
| `pyproject.toml` `[project.optional-dependencies].webview` (MODIFIED) | config | — | itself — existing `webview = [...]` block (lines 61-64) | exact |
| `.claude/commands/lucy-ng/case.md` (MODIFIED) | orchestration script | event-driven (run-start write) | itself — `timing` step's `run_start` / `mkdir -p analysis` mechanism (lines 317-346) + `spawn_case_team` Step 5 webview-launch window (lines 232-268) | exact |

## Pattern Assignments

### `src/lucy_ng/webview/routers/spectra.py` (NEW — route/controller, file-I/O + transform)

**Analog 1 (never-500 JSON shape to adapt):** `src/lucy_ng/webview/routers/tables.py`
**Analog 2 (binary/image endpoint precedent):** `src/lucy_ng/webview/routers/structures.py`

**Module docstring + WV-08 import-safety banner convention** (`tables.py` lines 1-19; every router module in this package repeats this banner verbatim, only the route list changes):
```python
"""GET /api/tables/{carbon,hsqc,hmbc,cosy,constraints} router (TBL-01/02/03).
...
WV-08 import-safety: this module imports fastapi at module level, which is
permitted because it is ONLY ever imported from inside create_app() and
from test bodies.  It must NOT be imported from webview/__init__.py,
webview/server.py, or webview/state.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter
```
For `spectra.py`, matplotlib must NOT join this module-level import block (D-04/WV-08) — it goes inside `make_router()` instead (see below). `json`, `re`, `Path`, `fastapi.APIRouter` at module level are fine (mirrors `tables.py` exactly — those are already lightweight/base-safe).

**`make_router(analysis_dir)` shape + lazy heavy import inside factory** (`structures.py` lines 36-54, the RDKit-lazy-import precedent that spectra.py's matplotlib-lazy-import must copy):
```python
def make_router(analysis_dir: Path) -> APIRouter:
    """Return an APIRouter(prefix='/api') with structures routes.

    Imports lucy_ng.webview.depiction (which loads RDKit) inside this factory
    so RDKit is never pulled in at webview package import time (WV-08).
    ...
    """
    # Lazy RDKit import — only reached via create_app() (WV-08)
    from lucy_ng.webview.depiction import placeholder_svg, render_smiles

    router = APIRouter(prefix="/api")

    @router.get("/structures")
    def get_structures() -> dict[str, Any]:
        ...

    return router
```
`spectra.py` copies this shape exactly, substituting the RDKit import for:
```python
def make_router(analysis_dir: Path) -> APIRouter:
    from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: PLC0415
    from matplotlib.figure import Figure  # noqa: PLC0415

    router = APIRouter(prefix="/api")

    @router.get("/spectra/1d/carbon")
    def get_carbon_1d() -> Response: ...

    @router.get("/spectra/1d/proton")
    def get_proton_1d() -> Response: ...

    return router
```
(RESEARCH.md's own verified code example at lines 530-541 already gives this exact skeleton — treat it as pre-vetted, do not deviate on the lazy-import placement.)

**Binary/image endpoint response + never-500-via-placeholder pattern** (`structures.py` lines 65-79, `depiction.py`'s `placeholder_svg()` lines 63-86 — the PNG analog of this same idiom):
```python
@router.get("/structure/{i}.svg")
def get_structure_svg(i: int) -> Response:
    _source, all_structs, _total = _load_all_structures(analysis_dir)
    if i < 0 or i >= len(all_structs):
        raise HTTPException(status_code=404, detail="Structure not found")
    smiles = all_structs[i]["smiles"]
    svg = render_smiles(smiles)
    if svg is None:
        svg = placeholder_svg()  # D-11: malformed SMILES -> placeholder
    return Response(content=svg, media_type="image/svg+xml")
```
For `spectra.py` the **entire** route body degrades to a placeholder instead of ever 404/500ing (D-01/D-05/SP-02 — stricter than `structures.py`, which does 404 on an out-of-range index). Model on `depiction.py`'s `placeholder_svg()`:
```python
def placeholder_svg(width: int = 300, height: int = 300) -> str:
    """Return a minimal placeholder SVG for an entry that cannot be rendered.
    ...
    Returns:
        A self-contained SVG string.
    """
    cx = width // 2
    cy = height // 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="#f0f0f0" stroke="#ccc" stroke-width="1"/>'
        f'<text x="{cx}" y="{cy}" text-anchor="middle" '
        f'dominant-baseline="middle" font-size="48" fill="#999">?</text>'
        f"</svg>"
    )
```
`spectra.py`'s `_render_placeholder_png(message)` is the PNG-Figure equivalent (RESEARCH.md lines 261-274 gives the exact verified-executable body — copy it, but per D-04's anti-pattern note, avoid the `import matplotlib.pyplot as _plt; _plt.close(fig)` line in that snippet's `finally` block; use `del canvas, fig` instead to keep the "NEVER matplotlib.pyplot" rule with zero exceptions).

**Never-500 broad-except tuple for JSON reads** (`tables.py` lines 30-40 — reuse this exact tuple for reading `.run_manifest.json` and `carbon_signals.json`):
```python
_JSON_READ_ERRORS = (
    FileNotFoundError,
    json.JSONDecodeError,
    OSError,
    KeyError,
    TypeError,
    ValueError,
)
```

**Manifest reader** (RESEARCH.md lines 463-473, adapted from `tables.py::_read_carbon` lines 84-108 — same try/except-collapse-to-None-or-waiting shape):
```python
def _read_manifest(analysis_dir: Path) -> dict[str, Any] | None:
    """Read analysis/.run_manifest.json. Returns None on any failure (D-01/D-05) — never raises."""
    p = analysis_dir / ".run_manifest.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data.get("bruker_data_dir"), str):
            return None
        return data
    except _JSON_READ_ERRORS:
        return None
```

**Newest-dir-selection idiom to reuse for iteration/experiment scanning conventions** (`tables.py::_newest_compound_lsd` lines 170-185 — same `sorted`/`max`-by-key-tuple shape the new `_select_experiment()` should follow, per RESEARCH.md's verified `_select_experiment` at RESEARCH.md lines 486-507):
```python
def _newest_compound_lsd(analysis_dir: Path) -> Path | None:
    candidates: list[tuple[int, float, Path]] = []
    for p in analysis_dir.glob("iteration_*/compound.lsd"):
        m = re.match(r"iteration_(\d+)", p.parent.name)
        if m:
            candidates.append((int(m.group(1)), p.stat().st_mtime, p))
    if not candidates:
        return None
    return max(candidates, key=lambda t: (t[0], t[1]))[2]
```

**Peak-overlay data source (already-audited schema)** — read `carbon_signals.json` via the exact same `_read_carbon`-style call (`tables.py` lines 84-108); the `signals[]` rows carry `ppm`, `mult`, `nC`, `assignment`, `confidence` (confirmed live at `tables_analysis_dir` fixture, `tests/test_webview_api.py` lines 561-597) — these are the fields `spectra.py`'s peak-overlay drawing step consumes (`ppm` for marker position, `assignment` for the label per D-03).

**Raw-data read** — `src/lucy_ng/readers/bruker.py::BrukerReader.read_1d` (lines 133-195):
```python
@staticmethod
def read_1d(experiment_dir: str | Path) -> Spectrum1D:
    ...
    pdata_dir = experiment_dir / "pdata" / "1"
    dic, data = ng.bruker.read_pdata(str(pdata_dir))
    acqus_dic, _ = ng.bruker.read(str(experiment_dir))
    dic.update(acqus_dic)
    nucleus = _get_param(dic, "NUC1")
    if nucleus is None:
        raise ValueError("NUC1 parameter not found in acqus")
    frequency = _get_param(dic, "SFO1")
    ...
    pulse_program = _get_param(dic, "PULPROG")
    ...
    udic = ng.bruker.guess_udic(dic, data)
    uc = ng.fileiobase.uc_from_udic(udic, dim=0)
    ppm_scale = uc.ppm_scale()
    metadata: dict[str, Any] = {}
    if pulse_program:
        metadata["pulse_program"] = pulse_program
    ...
    return Spectrum1D(
        data=np.array(data, dtype=np.float64),
        ppm_scale=np.array(ppm_scale, dtype=np.float64),
        nucleus=nucleus,
        frequency=float(frequency),
        solvent=solvent,
        metadata=metadata,
    )
```
Raises `FileNotFoundError` (dir missing) or `ValueError` (missing `NUC1`/`SFO1`) — `spectra.py`'s `_select_experiment()` must catch `(FileNotFoundError, ValueError, OSError)` around every candidate `read_1d()` call (matches RESEARCH.md's verified `_select_experiment` snippet, lines 486-507).

**`Spectrum1D` model fields** (`src/lucy_ng/models/spectrum.py` lines 10-20) — the exact field names `spectra.py` will access:
```python
class Spectrum1D(BaseModel):
    data: NDArray[np.float64]
    ppm_scale: NDArray[np.float64]
    nucleus: str
    frequency: float
    solvent: str | None = None
    metadata: dict[str, Any] = {}
```
`nucleus` is validated against `{"1H", "13C", "15N", "31P", "19F", "2H"}` (line 34) — so `_select_experiment(bruker_data_dir, "13C")` / `"1H"` string args match `Spectrum1D.nucleus` directly, no translation needed. `ppm_scale` is CONFIRMED already-descending (RESEARCH.md verified execution) — do not reverse it, do not call `invert_xaxis()` (Pitfall 3).

**Shared `_apply_nmr_axes()` helper** (RESEARCH.md lines 509-521, verified executable) — this is new code (no direct existing-codebase analog; STATE.md's v9.3-roadmap decision names it, but it does not exist on disk yet). Write exactly:
```python
def _apply_nmr_axes(ax, ppm_scale: "NDArray[np.float64]") -> None:
    """Set xlim from an already-descending Bruker ppm_scale. Do NOT call invert_xaxis()."""
    ax.set_xlim(float(ppm_scale[0]), float(ppm_scale[-1]))
    ax.set_xlabel("δ (ppm)")
```
Phase 96's 2D router will import this same helper from `spectra.py` (or a shared module Claude's discretion) — do not inline it only as a local closure.

---

### `src/lucy_ng/webview/app.py` (MODIFIED — provider/wiring, request-response)

**Analog:** itself — the existing Phase 94 `_tables` docking block

**Lazy-import + include_router pattern** (lines 52-62, the EXACT site to extend):
```python
    # Phase 91: lazy imports — these modules import fastapi/RDKit and must only
    # be reached via create_app(), never at package import time (WV-08).
    from lucy_ng.webview.routers import log as _log  # noqa: PLC0415
    from lucy_ng.webview.routers import status as _status  # noqa: PLC0415
    from lucy_ng.webview.routers import structures as _structures  # noqa: PLC0415
    from lucy_ng.webview.routers import tables as _tables  # noqa: PLC0415

    app.include_router(_status.make_router(analysis_dir))
    app.include_router(_structures.make_router(analysis_dir))
    app.include_router(_log.make_router(analysis_dir))
    app.include_router(_tables.make_router(analysis_dir))
```
Add one more lazy import line (`from lucy_ng.webview.routers import spectra as _spectra  # noqa: PLC0415`) and one more `app.include_router(_spectra.make_router(analysis_dir))` line, following the same alphabetical-ish grouping already used. Also extend the `create_app()` docstring's bullet list (lines 26-39) with the two new `GET /api/spectra/1d/{carbon,proton}` routes, matching the existing bullet style exactly (e.g. `- ``GET /api/tables/carbon`` → 13C signal table (TBL-01, Phase 94)`).

---

### `src/lucy_ng/webview/static/index.html` (MODIFIED — template/markup)

**Analog:** itself — the placeholder divs to replace, and the sibling `tables` panel structure to imitate for markup shape

**Placeholder to replace** (lines 405-412):
```html
      <button data-tab="log">Run Log</button>
      <button data-tab="spectra-1d">1D Spectra</button>
      <button data-tab="spectra-2d">2D Spectra</button>
      <button data-tab="tables">Tables</button>
    </div>
    <div id="log-panel" data-panel="log">Waiting for log data...</div>
    <div class="placeholder" data-panel="spectra-1d">1D Spectra — coming in Phase 95</div>
    <div class="placeholder" data-panel="spectra-2d">2D Spectra — coming in Phase 96</div>
```
Replace ONLY the `spectra-1d` line's content (keep `data-tab`/`data-panel` wiring identical — `initTabs()` in `webview.js` finds panels purely by `[data-panel]` attribute, no hardcoded IDs) with an `<img>`-bearing container, e.g. (exact IDs are this phase's discretion, but must be unique and match what `webview.js` will target):
```html
    <div data-panel="spectra-1d">
      <div id="spectra-1d-waiting" class="placeholder" style="display:none;">Waiting for spectrum data...</div>
      <img id="spectra-1d-carbon" alt="13C 1D spectrum" />
      <img id="spectra-1d-proton" alt="1H 1D spectrum" style="display:none;" />
    </div>
```
Leave `spectra-2d`'s placeholder line completely untouched (Phase 96 scope).

**Sibling panel structure for style consistency** (lines 413-424, the `tables` panel — CSS class conventions `tables-section`/`tables-heading`/`tables-caption` to imitate if `spectra.py`'s panel wants captions):
```html
    <div data-panel="tables">
    <section class="tables-section" id="table-carbon">
      <h2 class="tables-heading">&sup1;&sup3;C Signals</h2>
      <div class="tables-caption" id="table-carbon-caption"></div>
      <div id="table-carbon-body"></div>
    </section>
```
Reuse the existing inline `<style>` token block (CONTEXT.md canonical_refs explicitly says "reuse; no new design system") — do not add new CSS classes beyond what's needed for image sizing (e.g. `max-width: 100%`).

---

### `src/lucy_ng/webview/static/webview.js` (MODIFIED — frontend controller/poll)

**Analog 1 (fetch→render→catch shape to copy):** `refreshCarbon`/`renderCarbon` (TBL-01, lines 403-443)
**Analog 2 (`<img>` cache-busted swap to copy):** `renderStructures`'s tile-image logic (lines 111-145)

**URL constant + fetch→render→catch triplet** (lines 7-11, 403-408 — the pattern every panel repeats):
```javascript
  var CARBON_URL      = '/api/tables/carbon';
  ...
  function refreshCarbon() {
    fetch(CARBON_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderCarbon(data); })
      .catch(function (e) { console.warn('carbon fetch failed:', e); });
  }
```
For `spectra.py`'s PNG endpoints, there is no JSON `fetch`/`render` split needed — the `<img src>` IS the fetch (browser-native), matching `renderStructures`'s image-tag idiom instead:
```javascript
      // Re-fetch SVG only if SMILES changed (D-10: no flicker).
      var smiles = item.smiles || '';
      if (smiles !== lastSmiles[idx]) {
        var img2 = document.getElementById('img-' + idx);
        if (img2) {
          img2.src = '/api/structure/' + idx + '.svg?t=' + Date.now();
        }
        lastSmiles[idx] = smiles;
      }
```
`refreshSpectra1D()` should simply set (every tick — D-06 says no caching needed, so unconditional `src` reassignment each poll is acceptable, unlike the SMILES-diff-gated image in `renderStructures`):
```javascript
  var SPECTRA_CARBON_URL = '/api/spectra/1d/carbon';
  var SPECTRA_PROTON_URL = '/api/spectra/1d/proton';

  function refreshSpectra1D() {
    var carbonImg = document.getElementById('spectra-1d-carbon');
    if (carbonImg) { carbonImg.src = SPECTRA_CARBON_URL + '?t=' + Date.now(); }
    var protonImg = document.getElementById('spectra-1d-proton');
    if (protonImg) { protonImg.src = SPECTRA_PROTON_URL + '?t=' + Date.now(); }
  }
```
Note: since the PNG endpoint is "never-500 / always valid image bytes" (placeholder chart on failure — RESEARCH.md Pitfall 5), there is no `.catch()` needed the way JSON panels need one — a broken image would only occur on a network-level failure, not an application-level "waiting" state (that state is baked INTO the pixels of the placeholder PNG itself).

**`tick()` registration site** (lines 752-762 — add the new call here, alongside the other panel refreshers):
```javascript
  function tick() {
    refreshStatus();
    refreshStructures();
    refreshLog();
    refreshCarbon();
    refreshHsqc();
    refreshHmbc();
    refreshCosy();
    refreshConstraints();
    flashDot();
  }
```
Add `refreshSpectra1D();` to this list (any position; matches "each panel renders independently" per RESEARCH.md's Established Patterns).

---

### `tests/test_webview_api.py::TestSpectraEndpoint` (NEW — test, request-response)

**Analog:** `TestTablesEndpoint` (lines 740-825+) + its `tables_analysis_dir` fixture (lines 547-686)

**WV-08 import-safety skip idiom** (repeated verbatim in every test method in this file, e.g. lines 745-755):
```python
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
```
`TestSpectraEndpoint` copies this shape exactly, importing `from lucy_ng.webview.routers import spectra` inside the `try`, and additionally needs `matplotlib` importable — but per D-04 that import lives inside `spectra.make_router()`, so the test's own `try/except ImportError` around the `spectra` module import already covers "matplotlib absent" transitively (importing `spectra` itself never imports matplotlib at module level — only calling `make_router()` does — so the skip must wrap the `make_router()` call too, not just the module import, OR simply let the ImportError surface from inside `make_router()` and catch it there as well).

Response assertions differ from JSON `state`/`rows` checks — for a PNG endpoint, assert:
```python
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 0
```
And for the reversed-axis (SC2) test, since the route returns raw bytes (not xlim numbers), either (a) decode the PNG and inspect pixel content (fragile, avoid), or (b) — the RECOMMENDED approach per RESEARCH.md's test map (row `test_case1_carbonyl_left_of_aliphatic`) — import `_apply_nmr_axes`/`_render_1d_png` directly as unit-level helpers and assert `ax.get_xlim()[0] > ax.get_xlim()[1]` on the `Axes` object BEFORE the PNG is even encoded, mirroring how `TestDepiction` (lines 337-401) tests `render_smiles`/`placeholder_svg` as plain functions rather than only through the HTTP layer.

**Hand-authored fixture pattern to mirror** (`tables_analysis_dir`, lines 547-686 — builds a `tmp_path`-based `peaks/*.json` tree by hand, NOT copied from any real run):
```python
@pytest.fixture
def tables_analysis_dir(tmp_path: Path) -> Path:
    """analysis_dir with peaks/{carbon_signals,hsqc,hmbc,cosy}.json (LOCKED schema).
    ...
    """
    import json as _json

    peaks_dir = tmp_path / "peaks"
    peaks_dir.mkdir()

    (peaks_dir / "carbon_signals.json").write_text(
        _json.dumps({...}), encoding="utf-8",
    )
    ...
    return tmp_path
```
`spectra_manifest_dir` (new fixture, per RESEARCH.md Wave 0 Gaps) needs TWO variants:
1. A `tmp_path`-based `.run_manifest.json` pointing at the REAL CASE1 directory (`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/CASE1`) for the SC2 real-data reversed-axis/carbonyl test — `pytest.importorskip`/`skipif` if that Dropbox path is absent (do NOT hard-fail CI on a missing local dataset).
2. A synthetic Bruker-dir-shaped `tmp_path` fixture with fake `acqus`/`acqu2s` files (no real FID data needed) for the pure-unit-level 2D/DEPT-exclusion tests on `_select_experiment()`, so those don't depend on any external path.

**Base fixtures already available and directly reusable:** `empty_analysis_dir` (`tests/conftest.py` lines 263-268 — "Analysis dir with no files at all") is the correct fixture for the "absent manifest → placeholder" test (D-01/D-05), exactly as `TestTablesEndpoint::test_carbon_waiting_when_absent` already uses it (line 768) for the JSON-endpoint analog.

---

### `pyproject.toml` `[project.optional-dependencies].webview` (MODIFIED — config)

**Analog:** itself, lines 61-64:
```toml
webview = [
    "fastapi>=0.100",
    "uvicorn>=0.20",
]
```
Add `"matplotlib>=3.7",` as a third entry (D-04 — webview extra ONLY, never `dependencies` (base) nor `dev`). Do not touch the `[tool.hatch.build.targets.wheel]` `artifacts` list (lines 69-75) — no new static-asset globs are needed; `matplotlib` ships its own package data independently.

---

### `.claude/commands/lucy-ng/case.md` (MODIFIED — orchestration script, event-driven run-start write)

**Analog:** itself — the `timing` step's `run_start`/`mkdir -p analysis` mechanism (lines 317-346) and `spawn_case_team` Step 5's webview-launch window (lines 232-268)

**Exact insertion window** (between the `run_start` timing stamp described at lines 236, 345-346, and the webview-launch Bash block at lines 245-256):
```
**First, stamp timing** (see the timing step): take the `run_start` stamp (this one also does
`mkdir -p <compound_path>/analysis`), then a `phase_start` stamp for `peak-picking` — both BEFORE
the push below.

<!-- WV-07: Launch webview dashboard before the first [BEGIN] push. ... -->

**Launch the webview dashboard (non-blocking — exits in ~0.5 s):**
```bash
WEBVIEW_OUTPUT=$(lucy webview serve "<compound_path>/analysis" 2>&1)
...
```
```
The `run_start` timing stamp itself (lines 339-346) is the existing pattern to mirror for "one atomic Bash call that creates `analysis/` and writes a file into it":
```bash
printf '{"utc":"%s","epoch":%s,"event":"%s","phase":"%s","agent":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(date -u +%s)" "<event>" "<phase>" "<agent>" \
  >> <compound_path>/analysis/timing.jsonl
```
```
(The very first call — `run_start` — must create the dir first: prefix it with
`mkdir -p <compound_path>/analysis && `.)
```
Insert a NEW Bash step, immediately after the `run_start` timing-stamp call and BEFORE the webview-launch block (so both `<compound_path>` and `<formula>` — already known and interpolated into the `SendMessage` prompts a few lines below at line 274 — are in scope), writing:
```bash
cat > "<compound_path>/analysis/.run_manifest.json" <<JSON
{"bruker_data_dir": "<compound_path (absolute)>", "formula": "<formula>"}
JSON
```
No CLI signature change, no `.webview.json` schema change (`create_app(analysis_dir: Path)` — `src/lucy_ng/webview/app.py` line 18 — takes only the analysis dir; `spectra.py` reads the manifest from inside that same dir).

## Shared Patterns

### WV-08 lazy-import discipline (matplotlib analog of the existing RDKit rule)
**Source:** `src/lucy_ng/webview/routers/structures.py` lines 17-21, 51-52; `src/lucy_ng/webview/app.py` lines 52-57
**Apply to:** `spectra.py` (matplotlib imports inside `make_router()` only) and every test in `TestSpectraEndpoint` (module-level imports of `fastapi`/`lucy_ng.webview.*` wrapped in `try/except ImportError: pytest.skip(...)`)
```python
# app.py — the lazy-import + include_router idiom every new router follows
from lucy_ng.webview.routers import spectra as _spectra  # noqa: PLC0415
app.include_router(_spectra.make_router(analysis_dir))
```

### Never-500 degradation (JSON variant vs PNG variant)
**Source:** `src/lucy_ng/webview/routers/tables.py` (`_JSON_READ_ERRORS`, `{"state": "waiting", ...}`) and `src/lucy_ng/webview/depiction.py` (`placeholder_svg()`)
**Apply to:** `spectra.py` — the PNG endpoint must NEVER emit a JSON body (Pitfall 5); every failure path (absent manifest, stale path, no matching experiment, malformed peaks JSON) collapses to `_render_placeholder_png("...")`, always `Response(content=png_bytes, media_type="image/png")`, HTTP 200.

### Reversed ppm axis via shared helper (NEW this phase, becomes shared for Phase 96)
**Source:** RESEARCH.md verified `_apply_nmr_axes()` (lines 509-521); STATE.md v9.3-roadmap decision
**Apply to:** `spectra.py` now; Phase 96's 2D contour router reuses the same helper — do not inline the `set_xlim` call separately in that phase.

### Frontend poll-per-panel independence
**Source:** `src/lucy_ng/webview/static/webview.js` `tick()` (lines 752-762) and every `refreshXxx()` function
**Apply to:** `webview.js`'s new `refreshSpectra1D()` — added to the `tick()` list, fails independently (image `onerror` is not even wired, matching the "PNG always valid" contract — no JS-side error branch needed, unlike the JSON panels' `.catch()`).

## No Analog Found

None — every file in this phase's Integration Points has at least one strong existing-codebase analog (see table above). The only genuinely NEW logic with no direct precedent is:
- `_select_experiment()`'s 2D/DEPT experiment-discrimination filter (acqus `acqu2s` presence + `pulse_program` substring check) — RESEARCH.md Pattern 2 provides a verified, executable reference implementation to use in place of a codebase analog.
- `_apply_nmr_axes()` — named by a locked STATE.md decision but not yet implemented anywhere on disk; RESEARCH.md's verified snippet is the source of truth.

## Metadata

**Analog search scope:** `src/lucy_ng/webview/` (routers/, static/, app.py, depiction.py), `src/lucy_ng/readers/bruker.py`, `src/lucy_ng/models/spectrum.py`, `tests/test_webview_api.py`, `tests/conftest.py`, `pyproject.toml`, `.claude/commands/lucy-ng/case.md`
**Files scanned:** 11 read in full or targeted ranges (tables.py, log.py, structures.py, depiction.py, app.py, webview.js, index.html [targeted], test_webview_api.py [targeted], conftest.py [targeted], bruker.py [targeted], spectrum.py [targeted]), plus pyproject.toml and case.md [targeted]
**Pattern extraction date:** 2026-07-09

## PATTERN MAPPING COMPLETE

**Phase:** 95 - 1D Real Spectra + Peak Overlay
**Files classified:** 7
**Analogs found:** 7 / 7

### Coverage
- Files with exact analog: 7
- Files with role-match analog: 0
- Files with no analog: 0 (two internal HELPER functions within the new file are net-new logic, covered by RESEARCH.md's verified snippets instead of a codebase analog — see "No Analog Found")

### Key Patterns Identified
- Every router module follows the identical shape: module-level `fastapi`-only imports + WV-08 banner docstring + `make_router(analysis_dir) -> APIRouter(prefix="/api")` + heavy/optional deps (RDKit for structures.py, matplotlib for spectra.py) imported lazily INSIDE `make_router()`, never at module level.
- Never-500 is enforced by two sibling idioms depending on content-type: JSON routes return `{"state": "ok"|"waiting", ...}` (tables.py/log.py), binary/image routes always return valid bytes of the correct media type, varying only whether the image is a real render or a placeholder (structures.py's `placeholder_svg()` -> spectra.py's `_render_placeholder_png()`).
- `app.py` docks every new router via one lazy `from lucy_ng.webview.routers import X as _X` line plus one `app.include_router(_X.make_router(analysis_dir))` line, in the same function body, in insertion order — a strictly additive, low-risk edit.
- `webview.js`'s `tick()` calls one `refreshXxx()` per panel; JSON panels do `fetch→.then(render)→.catch(warn)`, image panels just reassign an `<img>.src` with a cache-busting `?t=Date.now()` query param (no fetch/catch needed since the PNG endpoint itself never errors).
- `BrukerReader.read_1d()` already returns a fully-formed `Spectrum1D` (`data`, `ppm_scale` [already descending], `nucleus`, `frequency`, `solvent`, `metadata["pulse_program"]`) — no new Bruker-parsing code is needed in `spectra.py`, only an experiment-directory SELECTION filter on top of repeated `read_1d()` calls.
- `case.md`'s `.run_manifest.json` write is a single new `cat > ... <<JSON` Bash block inserted between two already-documented steps (`run_start` timing stamp and the webview-launch call), using variables (`<compound_path>`, `<formula>`) already in scope at that point in `spawn_case_team` Step 5.

### File Created
`/Users/steinbeck/Dropbox/develop/lucy-ng/.planning/phases/95-1d-real-spectra-peak-overlay/95-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files.
