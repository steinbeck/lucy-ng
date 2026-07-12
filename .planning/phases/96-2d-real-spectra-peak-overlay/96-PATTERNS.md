# Phase 96: 2D Real Spectra + Peak Overlay - Pattern Map

**Mapped:** 2026-07-11
**Files analyzed:** 5 (1 primary module extended in place + 3 secondary edits + 1 test file)
**Analogs found:** 5 / 5 — this phase is a mechanical mirror of Phase 95; every new
piece of work has a 1:1 existing analog in the same modules.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/lucy_ng/webview/routers/spectra.py` (+3 routes, 2D helpers) | route/controller (FastAPI) | request-response (PNG render) | same file, Phase 95 1D routes (`get_carbon_1d`/`get_proton_1d`, `_render_nucleus`, `_render_1d_png`) | exact — same module, same shape, extend in place |
| `src/lucy_ng/webview/app.py` (docstring update only, ~lines 37-38) | config/wiring | request-response | same file — router already docked at line 66 | exact — no new `include_router` line needed |
| `src/lucy_ng/webview/static/index.html` (`data-panel="spectra-2d"` block, ~line 435) | component (static markup) | request-response (img polling) | same file, `data-panel="spectra-1d"` block (~lines 421-434) | exact |
| `src/lucy_ng/webview/static/webview.js` (`refreshSpectra2D`, `tick()`) | hook/controller (frontend poll) | request-response (img polling) | same file, `refreshSpectra1D` (~lines 716-728) + `tick()` (~line 767) | exact |
| `tests/test_webview_api.py` (`TestSpectraEndpoint2D` or 2D methods on `TestSpectraEndpoint`) | test | request-response / integration | same file, `TestSpectraEndpoint` class (lines 1221-1660) + `CASE1_ROOT`/`spectra_case1_manifest_dir`/`tables_analysis_dir` fixtures | exact |

No new files, no new dependency, no new router registration. `pyproject.toml` needs no change (`matplotlib>=3.7` already present at line 64 under `[project.optional-dependencies].webview`).

## Pattern Assignments

### `src/lucy_ng/webview/routers/spectra.py` — the file to extend

**Analog:** itself (Phase 95 1D routes in the same module) — read in full at
`/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/webview/routers/spectra.py` (373 lines).

**Module docstring / imports pattern** (lines 1-42):
```python
"""GET /api/spectra/1d/{carbon,proton} router (SP1-01/SP-02). ..."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter
from fastapi.responses import Response
from numpy.typing import NDArray

from lucy_ng.models import Spectrum1D
from lucy_ng.readers.bruker import BrukerReader
```
Extend: add `Spectrum2D` to the `lucy_ng.models` import; import
`_compute_2d_noise_sigma` from `lucy_ng.processing.peak_picker_2d` at module top
(plain numpy function, no matplotlib/fastapi coupling — RESEARCH.md confirms this does
not violate WV-08 and is not lint-blocked by `[tool.ruff.lint]`'s selected rules). Update
the module docstring to describe the three new 2D routes and their contract, mirroring
the existing docstring's shape (route list + "never a 500" contract paragraph + WV-08
import-safety paragraph).

**`_JSON_READ_ERRORS` tuple — reuse verbatim** (lines 44-54):
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
Use this exact tuple for the new `_read_peaks_2d(analysis_dir, kind)` helper (reads
`analysis/peaks/{hsqc,hmbc,cosy}.json`, mirrors `_read_peaks` at lines 144-160).

**Locked copy strings pattern** (lines 56-63) — add sibling constants, do not reword
existing ones:
```python
_MSG_NO_MANIFEST = (
    "Waiting for a live CASE run — spectra will appear once analysis starts."
)
_MSG_STALE_PATH = "Raw Bruker data not found at the recorded path."
_MSG_NO_CARBON = "No ¹³C experiment found in this dataset."
_MSG_NO_PROTON = "No ¹H experiment in this dataset."
_MSG_PEAKS_UNAVAILABLE = "peak positions unavailable"
```
Add `_MSG_NO_HSQC`/`_MSG_NO_HMBC`/`_MSG_NO_COSY` (no-experiment-found messages, same
style as `_MSG_NO_CARBON`/`_MSG_NO_PROTON`) — `_MSG_NO_MANIFEST` and `_MSG_STALE_PATH`
are reused as-is for the 2D routes too (same manifest, same bruker_data_dir).

**Styling constants — reuse verbatim, do not introduce new colours** (lines 65-72):
```python
_FIGSIZE = (9.0, 3.0)
_DPI = 100
_TRACE_COLOR = "#495057"
_ACCENT_COLOR = "#0c5460"
_PLACEHOLDER_COLOR = "#6c757d"
```
`_TRACE_COLOR` (`#495057`) is exactly D-02's "single muted contour colour". `_DPI = 100`
is reused unchanged. Add a 2D-specific `_FIGSIZE_2D = (9.0, 6.0)` sibling (RESEARCH.md
Open Question 2's verified/recommended value) rather than overloading `_FIGSIZE` — the
1D routes' existing figure size must stay untouched (no regression risk to Phase 95's
passing tests).

**`_read_manifest` — reuse verbatim, unmodified** (lines 82-97): both 2D and 1D routes
share the same `analysis/.run_manifest.json` / `bruker_data_dir` contract. Call this
exact function from the new 2D `_render_nucleus`-style guard; no 2D variant needed.

**`_select_experiment` (1D) → write `_select_experiment_2d` (INVERTED acqu2s filter)**
(lines 100-141, the function to mirror):
```python
def _select_experiment(bruker_data_dir: Path, nucleus: str) -> Spectrum1D | None:
    if not bruker_data_dir.is_dir():
        return None
    candidates: list[tuple[int, Spectrum1D]] = []
    try:
        entries = sorted(bruker_data_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return None
    for exp_dir in entries:
        if not exp_dir.is_dir() or not re.match(r"^\d+$", exp_dir.name):
            continue
        if (exp_dir / "acqu2s").exists():
            continue  # 2D experiment -- Pitfall 1
        try:
            spectrum = BrukerReader.read_1d(exp_dir)
        except (FileNotFoundError, ValueError, OSError):
            continue  # unreadable / not a 1D experiment
        if spectrum.nucleus != nucleus:
            continue
        pulse_program = str(spectrum.metadata.get("pulse_program", "")).lower()
        if "dept" in pulse_program:
            continue  # DEPT-edited -- Pitfall 2
        candidates.append((int(exp_dir.name), spectrum))
    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]  # lowest experiment number wins
```
The 2D sibling **keeps only** dirs WITH `acqu2s` (inverted condition), calls
`BrukerReader.read_2d(exp_dir)` instead of `read_1d`, filters on
`spectrum.experiment_type != experiment_type` (values `"HSQC"`/`"HMBC"`/`"COSY"`, no DEPT
filter needed — `Spectrum2D` has no DEPT concept), same lowest-experiment-number tiebreak
via `min(candidates, key=lambda t: t[0])[1]`. RESEARCH.md Pattern 7 gives the full
verified implementation (`_select_experiment_2d`) — copy that shape, catching
`(FileNotFoundError, ValueError, OSError)` from `read_2d` exactly as the 1D selector
catches from `read_1d`.

**`_apply_nmr_axes` (1D, x-only) → extend to 2D** (lines 175-184):
```python
def _apply_nmr_axes(ax: Any, ppm_scale: NDArray[np.float64]) -> None:
    """Set xlim from an already-descending Bruker ppm_scale. ..."""
    ax.set_xlim(float(ppm_scale[0]), float(ppm_scale[-1]))
    ax.set_xlabel("δ (ppm)")
```
Do NOT modify this function (Phase 95 tests depend on its exact 1D signature — see
`test_apply_nmr_axes_reverses_descending_scale`). Add a **sibling**
`_apply_nmr_axes_2d(ax, f1_ppm_scale, f2_ppm_scale)` that sets both `set_xlim` (from
`f2_ppm_scale`, direct/¹H) and `set_ylim` (from `f1_ppm_scale`, indirect) — both scales
are already descending (verified empirically in RESEARCH.md Pattern 2), so, exactly like
the 1D helper, no `[::-1]` reversal is needed, just pass the raw descending endpoints to
`set_xlim`/`set_ylim`.

**`_render_1d_png` → `_render_2d_png` (structure to mirror)** (lines 187-265, the
`try/finally` figure-release discipline, peak-loop defensive casting, and PNG-bytes
return are the parts to copy):
```python
def _render_1d_png(figure_cls, canvas_cls, spectrum, peaks, *, annotate_missing_peaks=True) -> bytes:
    fig = figure_cls(figsize=_FIGSIZE, dpi=_DPI)
    canvas = canvas_cls(fig)
    try:
        ax = fig.add_subplot(111)
        ax.plot(spectrum.ppm_scale, spectrum.data, color=_TRACE_COLOR, linewidth=1.0)
        _apply_nmr_axes(ax, spectrum.ppm_scale)
        ...
        for peak in peaks:
            if not isinstance(peak, dict):
                continue
            try:
                ppm = float(peak["ppm"])
            except (KeyError, TypeError, ValueError):
                continue
            ...
        buf = io.BytesIO()
        canvas.print_png(buf)
        return buf.getvalue()
    finally:
        del canvas
        del fig
```
`_render_2d_png` follows the identical shape: `figure_cls(figsize=_FIGSIZE_2D, dpi=_DPI)`,
`canvas_cls(fig)`, `try/finally` releasing both, `ax.contour(f2s, f1s, decimated,
levels=..., colors=_TRACE_COLOR, linewidths=0.5)` (D-02: single muted colour — reuse
`_TRACE_COLOR`, not a colormap), `_apply_nmr_axes_2d(ax, f1s, f2s)`, then the per-experiment
overlay call (`_plot_hmbc_overlay`/HSQC-uniform-scatter/`_plot_cosy_diagonal` +
COSY-scatter — see RESEARCH.md Pattern 6 for the exact overlay function bodies, already
using the same defensive `try/except (KeyError, TypeError, ValueError): continue`
per-peak casting idiom shown above), then the identical `io.BytesIO()` /
`canvas.print_png(buf)` / `finally: del canvas; del fig` tail.

**`_render_placeholder_png` — reuse verbatim, unmodified** (lines 267-295): call this
exact function (same signature: `figure_cls, canvas_cls, message`) from the 2D
never-500 guard for every failure branch (no manifest, stale path, no matching
experiment, any unexpected exception). No 2D variant needed — it is already
message-parameterised and figsize/DPI-generic via the injected `figure_cls`/`canvas_cls`
(pass `_FIGSIZE_2D` if a taller placeholder is desired for visual consistency with the
real 2D plots, or reuse `_FIGSIZE` — Claude's discretion per CONTEXT.md, document
whichever is chosen).

**`make_router()` — lazy matplotlib import + never-500 `_render_nucleus` guard shape to
mirror** (lines 303-372, the exact pattern for the three new routes):
```python
def make_router(analysis_dir: Path) -> APIRouter:
    from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: PLC0415
    from matplotlib.figure import Figure  # noqa: PLC0415

    router = APIRouter(prefix="/api")

    def _render_nucleus(nucleus: str, no_experiment_message: str) -> bytes:
        try:
            manifest = _read_manifest(analysis_dir)
            if manifest is None:
                return _render_placeholder_png(Figure, FigureCanvasAgg, _MSG_NO_MANIFEST)
            bruker_dir = Path(manifest["bruker_data_dir"])
            if not bruker_dir.is_dir():
                return _render_placeholder_png(Figure, FigureCanvasAgg, _MSG_STALE_PATH)
            spectrum = _select_experiment(bruker_dir, nucleus)
            if spectrum is None:
                return _render_placeholder_png(Figure, FigureCanvasAgg, no_experiment_message)
            ...
        except Exception:  # noqa: BLE001 -- never-500 guard (SP-02/T-95-02-01)
            return _render_placeholder_png(Figure, FigureCanvasAgg, no_experiment_message)

    @router.get("/spectra/1d/carbon")
    def get_carbon_1d() -> Response:
        png_bytes = _render_nucleus("13C", _MSG_NO_CARBON)
        return Response(content=png_bytes, media_type="image/png")
    ...
    return router
```
Add a parallel `_render_2d(experiment_type: str, no_experiment_message: str) -> bytes`
closure inside the SAME `make_router()` (same lazy-import block — do not add a second
`from matplotlib... import` line, reuse `Figure`/`FigureCanvasAgg` already imported
above), same manifest/stale-path guard, `_select_experiment_2d(bruker_dir,
experiment_type)`, then the mtime-cache lookup (new, see Pattern 5 below) wrapping
`_render_2d_png`, all inside the same broad `except Exception: return
_render_placeholder_png(...)`. Register three routes:
```python
@router.get("/spectra/2d/hsqc")
def get_hsqc_2d() -> Response: ...
@router.get("/spectra/2d/hmbc")
def get_hmbc_2d() -> Response: ...
@router.get("/spectra/2d/cosy")
def get_cosy_2d() -> Response: ...
```
inside the existing `router` object returned by this same `make_router()` — no new
`APIRouter()` instance, no new `include_router` call needed at `app.py` level (D-10 +
`app.py` already docks `_spectra.make_router()`).

**New: mtime-keyed PNG cache** — no existing analog in the codebase (this is the first
cache in the webview layer per RESEARCH.md); use the verified Pattern 5 design from
RESEARCH.md verbatim:
```python
_png_cache: dict[str, tuple[float, bytes]] = {}

def _cached_or_render(cache_key: str, source_mtime: float, render_fn: Callable[[], bytes]) -> bytes:
    cached = _png_cache.get(cache_key)
    if cached is not None and cached[0] == source_mtime:
        return cached[1]
    png_bytes = render_fn()
    _png_cache[cache_key] = (source_mtime, png_bytes)
    return png_bytes
```
Key on `(route_name, source_mtime)` where `source_mtime =
max(bruker_2rr_mtime, peaks_json_mtime)` — see RESEARCH.md Code Examples'
`_source_mtime(exp_dir, peaks_path)` helper (wrapped in its own `try/except OSError`
fallback to `exp_dir.stat().st_mtime`, per Pitfall 5 — must sit INSIDE the same
never-500 guard as the render call, not before it).

**Reusable helper — do not re-derive: `_compute_2d_noise_sigma`**. Import from
`lucy_ng.processing.peak_picker_2d` (module read at
`/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/processing/peak_picker_2d.py`
lines 11-48):
```python
def _compute_2d_noise_sigma(data: "np.ndarray[Any, Any]") -> float:
    """sigma = 1.4826 * median(|data - median(data)|), with a zero/NaN fallback."""
    if data.size == 0:
        return 1.0
    med = float(np.median(data))
    mad = float(np.median(np.abs(data - med)))
    sigma_mad = 1.4826 * mad
    if not np.isfinite(sigma_mad) or sigma_mad == 0.0:
        max_abs = float(np.max(np.abs(data)))
        return (0.05 * max_abs / 5.0) if max_abs > 0 else 1.0
    return sigma_mad
```
Compute on the FULL-resolution `spectrum.data` BEFORE block-max decimation (Pitfall 2 —
decimating first biases the MAD upward).

---

### `src/lucy_ng/webview/app.py` — docstring update only

**Analog:** itself (already docks the router; no new `include_router` line).

**Router docking — already complete, no change needed** (lines 54-66):
```python
from lucy_ng.webview.routers import spectra as _spectra  # noqa: PLC0415
...
app.include_router(_spectra.make_router(analysis_dir))
```
Only the route-list docstring (lines 37-38, immediately after the two existing
`GET /api/spectra/1d/{carbon,proton}` bullets) needs three new bullets documenting
`GET /api/spectra/2d/{hsqc,hmbc,cosy}` (SP2-01, Phase 96), mirroring the exact bullet
format already used:
```
- ``GET /api/spectra/1d/carbon`` → real 13C 1D trace + peak overlay (SP1-01, Phase 95)
- ``GET /api/spectra/1d/proton`` → real 1H 1D trace, when present (SP1-01, Phase 95)
```

---

### `src/lucy_ng/webview/static/index.html` — replace the `spectra-2d` placeholder

**Analog:** the `data-panel="spectra-1d"` block in the same file (lines 421-434):
```html
<div data-panel="spectra-1d">
<section class="tables-section" id="spectrum-carbon">
  <h2 class="tables-heading">&sup1;&sup3;C Spectrum</h2>
  <img id="img-spectrum-carbon" class="spectrum-img"
       alt="13C 1D spectrum with peak overlay"
       src="/api/spectra/1d/carbon">
</section>
<section class="tables-section" id="spectrum-proton">
  <h2 class="tables-heading">&sup1;H Spectrum</h2>
  <img id="img-spectrum-proton" class="spectrum-img"
       alt="1H 1D spectrum with peak overlay"
       src="/api/spectra/1d/proton">
</section>
</div>
```
**Placeholder to replace** (line 435):
```html
<div class="placeholder" data-panel="spectra-2d">2D Spectra — coming in Phase 96</div>
```
Replace with a `data-panel="spectra-2d"` div containing three stacked
`<section class="tables-section">` blocks (HSQC/HMBC/COSY), each with an `<img
class="spectrum-img" src="/api/spectra/2d/{hsqc,hmbc,cosy}">` — exact same
`tables-section`/`tables-heading`/`spectrum-img` class reuse as the 1D block (D-09:
"introduce no new design system"). IDs: `img-spectrum-hsqc`, `img-spectrum-hmbc`,
`img-spectrum-cosy` (mirrors `img-spectrum-carbon`/`img-spectrum-proton` naming).

**`.spectrum-img` CSS class — reuse verbatim, no change** (lines 371-379):
```css
/* ---- 1D Spectra tab (Phase 95: SP1-01/SP-02) ---- */
.spectrum-img {
  width: 100%;
  height: auto;
  display: block;
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
}
```
No new CSS class needed for the `<img>` elements themselves.

**HMBC flag-colour palette — reuse exact hex values for scatter marker colours**
(lines 339-353, CSS applied to Tables-tab rows by `webview.js`):
```css
.row-ok {
  border-left: 3px solid #28a745;
}
.row-potential-4j {
  background: #fff3cd;
  color: #856404;
  border-left: 3px solid #ffc107;
}
.row-1j-artifact {
  background: #f1f3f5;
  color: #adb5bd;
  border-left: 3px solid #adb5bd;
}
```
D-06 requires reusing these exact colours (`ok`→`#28a745`, `potential_4J`→`#ffc107`,
`1J_artifact`→`#adb5bd`) for the HMBC overlay marker `edgecolors` in
`spectra.py::_plot_hmbc_overlay` — do not invent new hex values.

---

### `src/lucy_ng/webview/static/webview.js` — add `refreshSpectra2D`

**Analog:** `refreshSpectra1D` in the same file (lines 716-728):
```javascript
// ------------------------------------------------------------------
// refreshSpectra1D — 1D Spectra tab (Phase 95: SP1-01/SP-02).
// The PNG endpoint is never-500 (placeholder chart baked into the
// pixels on failure), so no fetch/catch is needed — the browser's
// native <img> loading handles the binary payload directly. Cache-bust
// unconditionally every tick (D-06: no SMILES-diff dedupe needed here).
// ------------------------------------------------------------------
function refreshSpectra1D() {
  var t = Date.now();
  var carbonImg = document.getElementById('img-spectrum-carbon');
  if (carbonImg) { carbonImg.src = '/api/spectra/1d/carbon?t=' + t; }
  var protonImg = document.getElementById('img-spectrum-proton');
  if (protonImg) { protonImg.src = '/api/spectra/1d/proton?t=' + t; }
}
```
`refreshSpectra2D` is a mechanical copy: one `var t = Date.now()`, three `img.src =
'/api/spectra/2d/{hsqc,hmbc,cosy}?t=' + t;` guarded by `if (img)` — same shape, same
`?t=` cache-buster convention (RESEARCH.md confirms the server-side mtime cache does NOT
conflict with this — the query string is ignored server-side).

**`tick()` — add the call in the same list** (line 767-778):
```javascript
function tick() {
  refreshStatus();
  refreshStructures();
  refreshLog();
  refreshCarbon();
  refreshHsqc();
  refreshHmbc();
  refreshCosy();
  refreshSpectra1D();
  refreshConstraints();
  flashDot();
}
```
Add `refreshSpectra2D();` immediately after `refreshSpectra1D();` in this list (no
special ordering requirement — each function is independent and fire-and-forget).

**`initTabs()` — already handles `data-tab="spectra-2d"` generically, no change
needed** (lines 733-755): the tab-switch logic reads `data-panel` attributes
generically; the existing `<button data-tab="spectra-2d">2D Spectra</button>` (index.html
line 417) and the new `<div data-panel="spectra-2d">` wiring is already compatible with
zero JS changes to `initTabs`.

---

### `tests/test_webview_api.py` — extend `TestSpectraEndpoint`

**Analog:** `TestSpectraEndpoint` class (lines 1221-1660) in the same file, plus its
supporting fixtures.

**`CASE1_ROOT` fixture — reuse verbatim, already covers HSQC/HMBC/COSY** (lines
1091-1099):
```python
CASE1_ROOT = (
    Path.home()
    / "Dropbox"
    / "develop"
    / "data"
    / "nmrdata"
    / "active-lucy-ng-testprojects"
    / "CASE1"
)
```
Per RESEARCH.md's live verification, `CASE1_ROOT / "6"` = HSQC, `/"7"` = HMBC, `/"5"` =
COSY — no new dataset fixture needed. Follow the exact `if not CASE1_ROOT.is_dir():
pytest.skip(...)` guard used throughout (e.g. line 1126-1127, 1271-1272, 1326-1327) for
every real-data test.

**`spectra_case1_manifest_dir` fixture pattern — mirror for 2D peaks** (lines
1119-1175): the 1D fixture writes `.run_manifest.json` + hand-authored
`peaks/carbon_signals.json`. The 2D sibling (e.g. `spectra_case1_manifest_dir_2d` or
extend the same fixture) additionally hand-authors
`peaks/{hsqc,hmbc,cosy}.json` following the LOCKED schema documented in
CONTEXT.md's `<canonical_refs>` (fields: `carbon_ppm`/`proton_ppm`/`intensity` for HSQC;
`carbon_ppm`/`carbon_ppm_observed`/`proton_ppm`/`intensity`/`flag` for HMBC — include at
least one row per flag value `ok`/`potential_4J`/`1J_artifact`, mirroring
`tables_analysis_dir`'s existing HMBC fixture at ~line 550 which already does exactly
this for the Tables-tab tests); `proton_a_ppm`/`proton_b_ppm`/`intensity` for COSY.

**`test_apply_nmr_axes_reverses_descending_scale` — pattern to mirror for 2D axes**
(lines 1224-1243):
```python
def test_apply_nmr_axes_reverses_descending_scale(self) -> None:
    try:
        from lucy_ng.webview.routers.spectra import _apply_nmr_axes
    except ImportError:
        pytest.skip("webview extra or spectra router not yet available")
    import numpy as np
    from matplotlib.figure import Figure
    fig = Figure()
    ax = fig.add_subplot(111)
    ppm_scale = np.array([231.0, 150.0, 80.0, 20.0, -12.0])
    _apply_nmr_axes(ax, ppm_scale)
    xlim = ax.get_xlim()
    assert xlim[0] > xlim[1], f"Expected reversed axis (xlim[0] > xlim[1]), got {xlim}"
```
A 2D sibling test for `_apply_nmr_axes_2d` asserts BOTH `xlim[0] > xlim[1]` AND
`ylim[0] > ylim[1]` on two independent descending arrays (SC1/D-08).

**`test_carbon_returns_png_on_case1` — pattern to mirror for the three 2D routes**
(lines 1245-1267):
```python
def test_carbon_returns_png_on_case1(self, spectra_case1_manifest_dir: Path) -> None:
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from lucy_ng.webview.routers import spectra
        app = FastAPI()
        app.include_router(spectra.make_router(spectra_case1_manifest_dir))
    except ImportError:
        pytest.skip("webview extra or spectra router not yet available")
    with TestClient(app) as client:
        r = client.get("/api/spectra/1d/carbon")
    assert r.status_code == 200, ...
    assert r.headers["content-type"] == "image/png", ...
    assert len(r.content) > 0, "Expected non-empty PNG bytes"
```
Mirror for `GET /api/spectra/2d/{hsqc,hmbc,cosy}` — same `TestClient`/`FastAPI()`/
`include_router` wiring, same three assertions.

**`test_select_experiment_excludes_2d_and_dept` → mirror as
`test_select_experiment_2d_keeps_only_acqu2s`** (lines 1296-1334): the `synthetic_bruker_dir`
fixture (lines 1179-1207) already includes an `acqu2s`-bearing dir (`root / "5"`,
`cosygpqf` pulse program) alongside three 1D dirs — RESEARCH.md's Wave-0-gaps note
explicitly recommends testing the 2D inclusion filter against the REAL CASE1/repo
datasets rather than hand-authoring a fake 2D `pdata`, since `_select_experiment_2d`
needs a real readable `pdata/1/2rr` to reach `BrukerReader.read_2d()` successfully (a
synthetic acqus-only dir is sufficient to prove the 1D EXCLUSION branch never calls
`read_1d`, but not to prove the 2D INCLUSION branch, which must actually call
`read_2d()` and get an `experiment_type` back).

**Never-500 placeholder tests — mirror pattern** (lines 1541-1567,
`test_missing_manifest_returns_placeholder` / `test_stale_bruker_path_returns_placeholder`):
same `empty_analysis_dir` / `spectra_stale_manifest_dir` fixtures apply unchanged to the
2D routes (same manifest contract) — assert HTTP 200 + `image/png` + non-empty bytes on
missing manifest, stale path, no matching experiment_type, and malformed peaks JSON.

**WV-08 import-safety test — mirror unchanged, extend the scan target** (lines
1631-1655, `test_no_module_level_matplotlib_import`): the line-scan up to `def
make_router` already covers ALL of `spectra.py`'s module-level code including any new
2D helpers added above `make_router` — no test change needed as long as the new
`_compute_2d_noise_sigma`/`numpy` imports at module top stay matplotlib-free (they do —
`peak_picker_2d.py` has zero matplotlib coupling per its own imports: `nmrglue`, `numpy`,
`lucy_ng.models` only).

**Cache-hit / cache-bounded tests — new, no direct 1D analog (first cache in the
webview layer)**: use `monkeypatch` to patch the render closure (or a module-level
render function) and assert it is called exactly once across two identical-mtime
requests (`SC3` — mirrors the general monkeypatch-spy idiom already used in
`test_select_experiment_excludes_2d_and_dept`'s `_spy_read_1d` at lines 1309-1316);
assert `len(spectra._png_cache) <= 3` after N repeated polls across all three routes
(`SC4`).

## Shared Patterns

### Never-500 guard (SP-02)
**Source:** `src/lucy_ng/webview/routers/spectra.py::make_router()._render_nucleus`
(lines 327-360) and `src/lucy_ng/webview/routers/tables.py`'s per-reader `try/except
_JSON_READ_ERRORS: return waiting` idiom (e.g. `_read_carbon`, lines 84-108).
**Apply to:** all three new 2D routes' `_render_nucleus`-style closures — wrap the ENTIRE
body (manifest read, experiment selection, cache-mtime lookup, decimation, MAD, contour
render) in one broad `except Exception: return _render_placeholder_png(...)`, per
Pitfall 5's warning that the mtime lookup specifically must sit inside this same guard.

### `_JSON_READ_ERRORS` broad-except tuple
**Source:** `src/lucy_ng/webview/routers/spectra.py` lines 44-54 (identical tuple also
in `tables.py` lines 33-40).
**Apply to:** any new `_read_peaks_2d(analysis_dir, kind)` JSON reader.

### matplotlib OO-API + lazy import (WV-08/D-04)
**Source:** `src/lucy_ng/webview/routers/spectra.py::make_router()` lines 321-323
(`from matplotlib.backends.backend_agg import FigureCanvasAgg` / `from matplotlib.figure
import Figure`, both with `# noqa: PLC0415`, both INSIDE `make_router()`, never at
module level).
**Apply to:** the new 2D render path reuses the SAME two imports already present in
`make_router()` — do not add a second lazy-import block; `Figure`/`FigureCanvasAgg` are
already in scope for the 2D closures defined later in the same function body.

### Figure release discipline
**Source:** `_render_1d_png`/`_render_placeholder_png` (lines 187-295), the
`try: ... finally: del canvas; del fig` shape.
**Apply to:** `_render_2d_png` — identical shape, same rationale (no `pyplot`, so nothing
is registered in a global figure manager to "close"; `del` is the release mechanism).

### HMBC flag-colour palette
**Source:** `src/lucy_ng/webview/static/index.html` lines 339-353 (CSS) /
`src/lucy_ng/webview/static/webview.js` lines 489-493 (`HMBC_FLAG_CLASS` JS map).
**Apply to:** `spectra.py::_plot_hmbc_overlay`'s Python-side `_HMBC_FLAG_COLORS` dict
(RESEARCH.md Pattern 6) — same three hex values, same flag-name keys
(`ok`/`potential_4J`/`1J_artifact`), so the Tables tab and the 2D plot render the exact
same visual language for the same underlying flag.

### `?t=` cache-buster vs. server-side mtime cache (no conflict)
**Source:** `webview.js::refreshSpectra1D` (lines 716-728) for the frontend half;
RESEARCH.md Pattern 5 for the server half (new this phase).
**Apply to:** `refreshSpectra2D` (frontend) + the new `_png_cache` dict (backend) — the
frontend always appends `?t=<timestamp>` to defeat the BROWSER's HTTP cache; the backend
route handler must ignore all query params and key its own cache purely on
`Path.stat().st_mtime` of the source files, exactly as documented in CONTEXT.md's
"Carried forward" section.

## No Analog Found

None — every file/change in this phase has a direct, exact analog already in the
codebase (this phase is explicitly scoped as "purely additive... mirror the 1D
implementation for 2D"). The two genuinely new pieces of code with no prior in-repo
precedent are:

| New element | Role | Data Flow | Reason no analog exists | Where the design comes from instead |
|---|---|---|---|---|
| mtime-keyed PNG cache (`_png_cache` dict + `_cached_or_render`) | utility (module-level cache) | request-response (memoization) | First cache in the webview layer (Phase 95 explicitly deferred this to Phase 96, D-06-from-95) | RESEARCH.md Pattern 5 (verified design, not a codebase analog) |
| `_block_max_decimate` / `_geometric_levels` numpy helpers | utility (transform) | transform (array→array) | No prior 2D-array decimation/level-generation code exists outside the peak-picker's own internal thresholding (`peak_picker_2d.py`, a different concern — picking, not rendering) | RESEARCH.md Pattern 3/4 (verified via live execution against real CASE1 data, timed at 0.007s/0.10-0.13s respectively) |

## Metadata

**Analog search scope:** `src/lucy_ng/webview/` (routers, static), `src/lucy_ng/readers/bruker.py`,
`src/lucy_ng/models/spectrum.py`, `src/lucy_ng/processing/peak_picker_2d.py`,
`tests/test_webview_api.py`, `pyproject.toml`.
**Files scanned:** 9 (spectra.py, tables.py, app.py, index.html, webview.js,
bruker.py, spectrum.py, peak_picker_2d.py, test_webview_api.py) — all read directly,
no Glob/Grep-only matches used (RESEARCH.md already performed and empirically verified
the codebase survey; this pass re-reads the cited files/line-ranges to extract exact
excerpts for the planner).
**Pattern extraction date:** 2026-07-11
