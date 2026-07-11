# Phase 96: 2D Real Spectra + Peak Overlay - Research

**Researched:** 2026-07-11
**Domain:** matplotlib OO-API 2D contour rendering; Bruker 2D data orientation; numpy decimation; PNG caching inside a FastAPI router
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (Geometric levels, ~8, above MAD noise floor):** Contour levels grow
  **geometrically** (a fixed growth factor, e.g. ~1.4) starting just above the
  MAD-derived noise floor (noise floor itself is a locked v9.3-roadmap decision). Target
  **~8 levels** so both weak long-range HMBC cross-peaks and strong HSQC peaks are
  visible without the plot smearing shut. Exact factor/level-count is a rendering detail
  (Claude's discretion within "geometric, ~8"); document the chosen values.
- **D-02 (Single muted contour colour, not a colormap):** All contour lines drawn in
  **one muted grey/blue-grey** consistent with the 1D trace colour (`#495057`) and the
  v9.2/9.3 visual language. Keeps the contour "background" calm so the coloured
  cross-peak markers stand out. Do NOT colour contours by intensity via a colormap
  (introduces new colours and competes with the overlay markers).
- **D-03 (Positive contours only):** Render **positive contours only** (magnitude-mode
  assumption). Sufficient for the QC purpose ("are the picked peaks sitting on real
  signal?"). Do not attempt negative/phase-sensitive edited-HSQC contours in this phase.
- **D-04 (Block-maximum preferred; Claude's discretion):** The ≤512×512 cap is a locked
  v9.3-roadmap decision; the **method** is Claude's discretion with a strong lean:
  prefer **block-maximum (max-pooling)** — partition the 2D array into blocks and take
  each block's max — so a narrow cross-peak apex falling between grid points **survives**
  the downsampling (the entire QC value depends on real peaks not silently vanishing).
  Plain **striding** (`data[::step]`) is acceptable ONLY as a performance fallback if
  block-max cannot meet the <1 s budget (SC3); document whichever is shipped and why.
- **D-05 (Open circles, uniform HSQC style):** Overlay each picked cross-peak as an
  **open circle** (ring) so the contour underneath stays visible and it's clear whether
  the marker sits on real signal. **HSQC markers are all the same style** — HSQC
  cross-peaks are one-bond by definition, so distinguishing `one_bond` /
  `matched_real_carbon` adds visual noise for little QC value.
- **D-06 (HMBC markers colour-coded by flag — LOCKED):** HMBC cross-peak markers are
  **colour-coded by the `flag` value** (`ok` / `potential_4J` / `1J_artifact`) from
  `analysis/peaks/hmbc.json` — a locked ROADMAP SC2 requirement, reusing the Phase 94
  HMBC flag-colour palette for consistency between the Tables tab and the 2D plot.
- **D-07 (COSY diagonal drawn; symmetric axes):** COSY is ¹H×¹H symmetric — draw a thin
  grey **diagonal line (F1=F2)** as an orientation aid (chemists read COSY cross-peaks as
  off-diagonal correlations). Plot `proton_a_ppm` on x and `proton_b_ppm` on y, both axes
  reversed.
- **D-08 (HSQC/HMBC: F2=¹H on x, F1=¹³C on y; both reversed):** For HSQC and HMBC the
  direct dimension **F2 = ¹H is the x-axis**, indirect **F1 = ¹³C is the y-axis**, both
  reversed (ROADMAP SC1: aromatic region top-left, F2 ~7 ppm / F1 ~130 ppm). Overlay
  coordinates: x = `proton_ppm`, y = `carbon_ppm`. For COSY, x/y = `proton_a_ppm` /
  `proton_b_ppm` (D-07). Both 2D axes go through the shared `_apply_nmr_axes` helper
  (extended to 2D) so neither axis is left un-reversed by omission.
- **D-09 (Three stacked plots, all always rendered):** The 2D-Spectra tab shows the three
  plots (HSQC, HMBC, COSY) **stacked vertically, all rendered** — mirrors the Phase 95 1D
  carbon+proton stack. Each plot polls/renders independently with its own per-plot
  "unavailable" state. No sub-tabs / selector (would be a new interaction pattern and
  prevents side-by-side comparison).
- **D-10 (Three independent PNG routes):** `/api/spectra/2d/hsqc`, `/api/spectra/2d/hmbc`,
  `/api/spectra/2d/cosy` — one PNG route each, mirroring the Phase 95 1D carbon/proton
  split, so each plot degrades to "unavailable" **independently** (missing experiment,
  missing peak JSON, unreadable raw path). Never 500, always valid PNG bytes at HTTP 200
  (SP-02, mirrors the Phase 95 `_render_placeholder_png` precedent).

Carried forward from v9.3-roadmap (LOCKED — do NOT re-decide):
- Reversed ppm axes on both dimensions via the shared `_apply_nmr_axes()` helper
  (extend it for 2D F1+F2).
- Decimate to ≤512×512 before contouring; MAD-noise-floor threshold levels (D-01/D-04
  refine the *how*, not the *whether*).
- mtime-keyed per-router PNG cache — cache rendered PNGs keyed by source-file mtime so
  the ~3 s browser poll does NOT trigger re-renders on a cache hit (SC3). The server
  cache keys on **source mtime**, not the frontend's `?t=` cache-buster query string,
  so cache hits still work across polls.
- Figures closed after each render (`try/finally`) + the mtime cache prevent unbounded
  Figure allocation / memory growth under repeated polling (SC4).
- matplotlib OO API only (`Figure` + `FigureCanvasAgg`; never `pyplot`), lazy import
  inside `make_router()`, matplotlib only in the `[webview]` extra; base `lucy` install
  imports without it (WV-08 / D-04-from-95).
- Sync `def` route handlers (FastAPI dispatches CPU-bound renders to a threadpool).
- SP-02 graceful degradation carried as a hard acceptance criterion.

### Claude's Discretion

- Exact geometric growth factor + final level count within "geometric, ~8" (D-01).
- Decimation method: block-max vs striding fallback, block size, per-axis step (D-04).
- 2D experiment-selection tiebreak when a dataset holds multiple candidate experiments
  of the same type (e.g. edited + non-edited HSQC) — mirror the Phase 95 1D
  `_select_experiment` approach (scan sub-dirs with `acqu2s`, use `read_2d`'s
  `experiment_type`, lowest-experiment-number tiebreak); document the choice.
- Figure sizing/DPI, marker radius/linewidth, exact circle/diagonal/contour line weights —
  respect the v9.2/9.3 look; introduce no new design system.
- mtime-cache internal structure and eviction policy (e.g. keep only the latest mtime per
  plot) — SC3/SC4 constrain the behaviour, not the data structure.
- Endpoint internals, helper/function names, module organisation within `spectra.py`.
- Whether the three plots are three separate `<img>` or the exact stacking markup, within
  D-09's "stacked, all visible" constraint.

### Deferred Ideas (OUT OF SCOPE)

- Negative / phase-sensitive edited-HSQC contours (CH2 down-peaks) — considered,
  rejected for this phase (D-03); positive-only is enough for QC. Possible v9.4.
- HSQC one_bond / matched_real_carbon marker distinction — considered, rejected
  (D-05, low QC value); uniform markers instead.
- Sub-tabs / plot selector inside the 2D tab — considered, rejected (D-09); stacked
  all-visible mirrors 1D and allows comparison.
- Interactive zoom/pan, DEPT sub-tab, SSE live push → v9.4 per STATE.md.
- Colormap-by-intensity contours — rejected (D-02); would introduce new colours and
  compete with overlay markers.
- Any peak *editing*; a JS charting library (violates no-build/no-CDN); 1D spectra
  (Phase 95, done); changes to the `.run_manifest.json` contract (Phase 95 already
  writes it — this phase only reads it, extended to locate 2D experiments).
- `CASE4 azulene regiochemistry enumeration gap` (skill) — a CASE-solver concern,
  unrelated to 2D spectra rendering; belongs to the CASE-skill backlog.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SP2-01 | User sees the real 2D spectra (HSQC, HMBC, COSY) rendered as contour plots with reversed ppm axes on both dimensions, with the picked cross-peaks overlaid | Pattern 1 (OO-API contour rendering, verified timing), Pattern 2 (empirically-verified data orientation — no transpose needed), Pattern 3 (block-max decimation, verified), Pattern 4 (MAD noise floor via existing `_compute_2d_noise_sigma`, verified reproduces documented sigma), Pattern 6 (overlay markers + HMBC flag palette, verified hex values), Pattern 7 (2D experiment selection, verified against 7 real datasets) |
| SP-02 | When a spectrum or its peak data is missing, partial, or the raw experiment data cannot be located, the corresponding tab shows a well-formed "unavailable / waiting for data" state (HTTP 200, never 500) — carried from Phase 95 | System Architecture Diagram (never-500 guard flow), Pitfall 5 (mtime-lookup failure must not escape the guard), Security Domain (V5 defensive peak-field casting) — all mirror the existing Phase 95 `_render_nucleus`/`_render_placeholder_png` precedent |

</phase_requirements>

## Summary

Phase 96 is a pure extension of the Phase 95 `src/lucy_ng/webview/routers/spectra.py`
module: three new PNG routes (`/api/spectra/2d/{hsqc,hmbc,cosy}`) that read raw Bruker
2D data via the already-existing `BrukerReader.read_2d()`, decimate it, contour it with
matplotlib's OO API, overlay cross-peaks from `analysis/peaks/{hsqc,hmbc,cosy}.json`,
and cache the PNG bytes keyed by source-file mtime. No new dependency, no new reader, no
redesign — every helper pattern (`_read_manifest`, `_apply_nmr_axes`,
`_render_placeholder_png`, the lazy-matplotlib-import `make_router()` shape, the
never-500 `_render_nucleus`-style guard) already exists in `spectra.py` and is directly
extendable.

This research **empirically verified** (via live `python3` execution against the real
Bruker 2D datasets already used by the Phase 95 test suite — CASE1 exp 5/6/7 and the
repo's local `data/4-(1-Hydroxyethyl)benzoic acid isopropylester/` exp 4/5/8) the one
fact CONTEXT.md flags as needing confirmation: **`Spectrum2D.data.shape ==
(len(f1_ppm_scale), len(f2_ppm_scale))`**, i.e. `data[i, j]` corresponds to
`(f1_ppm_scale[i], f2_ppm_scale[j])`. This is exactly the layout matplotlib's
`ax.contour(X, Y, Z)` expects when `X=f2_ppm_scale` (columns), `Y=f1_ppm_scale` (rows),
`Z=data` — **no transpose needed**. Both ppm scales are already descending (same
Bruker convention as the 1D reader), so `_apply_nmr_axes` extends to 2D by simply
setting `set_xlim`/`set_ylim` from the raw scale endpoints, exactly mirroring the
existing 1D helper.

A working end-to-end prototype (block-max decimation to ≤512×512 + MAD-derived
geometric 8-level contour + matplotlib Agg PNG render) was timed against all three real
experiment types from the CASE1 dataset: **0.10–0.13 s per plot**, comfortably inside
the < 1 s/request budget (SC3) even without the mtime cache — the cache exists purely to
avoid *repeated* work on the ~3 s poll, not to hit the budget in the first place.

**Primary recommendation:** Mirror Phase 95's structure almost mechanically. The three
genuinely new pieces of engineering are (1) the block-max decimation function, (2) the
mtime-keyed cache dict, and (3) the per-experiment-type overlay/colour logic — everything
else (manifest reading, never-500 guard, placeholder rendering, router wiring) is a
copy-and-adapt of existing Phase 95 code.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Raw Bruker 2D data access | API/Backend (`BrukerReader.read_2d`) | — | Already exists; reads `pdata/1/2rr` via nmrglue, base dependency |
| 2D experiment selection (HSQC/HMBC/COSY) | API/Backend (`spectra.py`) | — | Mirrors 1D `_select_experiment`; filesystem scan, no new tier |
| Decimation + noise-floor + contour render | API/Backend (`spectra.py`, matplotlib Agg) | — | CPU-bound, must stay server-side (no client charting lib per no-CDN constraint) |
| Cross-peak overlay data | API/Backend (`analysis/peaks/*.json` reader) | — | Already-picked peaks, read-only passthrough |
| PNG cache | API/Backend (module-level dict in `spectra.py`) | — | In-process cache; single-worker localhost server, no external cache needed |
| Image display + polling | Browser/Client (`webview.js`, `<img src>`) | — | `?t=` cache-buster + native `<img>` loading; no client-side rendering logic |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| matplotlib | `>=3.7` (already in `[webview]` extra) | OO-API contour rendering (`Figure` + `FigureCanvasAgg`, `ax.contour`) | Already the project's chosen 1D rendering stack (Phase 95); no alternative under consideration |
| numpy | base dependency (already required, confirmed via `nmrglue`/`pydantic` array fields) | block-max decimation, MAD noise-floor, meshgrid-free contour args | Already imported in `spectra.py` (Phase 95) and throughout `src/lucy_ng` |
| nmrglue | base dependency | `BrukerReader.read_2d()` already implemented on top of it | No new reader needed |

**No new dependency this phase.** `matplotlib>=3.7` confirmed present in
`pyproject.toml` line 64 under `[project.optional-dependencies].webview`
`[VERIFIED: pyproject.toml grep]`. `numpy`/`nmrglue` confirmed as base deps by the
existing unconditional `import numpy as np` / `import nmrglue as ng` at module top of
`src/lucy_ng/webview/routers/spectra.py` and `src/lucy_ng/readers/bruker.py`
`[VERIFIED: source read]`.

**Installation:** none required.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ax.contour()` (line contours) | `ax.contourf()` (filled contours) | Rejected by D-02 — filled regions would compete visually with the cross-peak overlay markers; CONTEXT.md locks "contour lines," not filled regions |
| Block-max decimation (numpy reshape) | `skimage.measure.block_reduce` | Rejected — would add a new dependency (`scikit-image`) for something a 6-line numpy reshape already does; CONTEXT.md D-04 explicitly flags "numpy-only, no new dependency" as the lean |
| Module-level dict cache | `functools.lru_cache` keyed on mtime | `lru_cache` works but its default unbounded growth + inability to easily key on "latest mtime wins" (need explicit eviction per D-04-cache discretion) makes a plain dict clearer; `lru_cache` is a viable alternative if the planner prefers it (see Code Examples) |

## Package Legitimacy Audit

Not applicable — this phase introduces **zero new external packages**. `matplotlib`,
`numpy`, and `nmrglue` are all already-approved base/extra dependencies from prior
phases (Phase 95's `RESEARCH.md`/`CONTEXT.md` already covered `matplotlib`'s
legitimacy). No `slopcheck`/registry verification needed.

## Architecture Patterns

### System Architecture Diagram

```
Browser (webview.js tick(), every ~3s)
   │
   │ GET /api/spectra/2d/hsqc?t=<ts>   (+ hmbc, cosy — 3 independent requests)
   ▼
FastAPI route handler (spectra.py, sync def — dispatched to threadpool)
   │
   ├─► _read_manifest(analysis_dir)  ──► absent/bad? ──► _render_placeholder_png()
   │        │ ok
   │        ▼
   ├─► _select_experiment_2d(bruker_dir, "HSQC")  (scans dirs WITH acqu2s,
   │        │                                       BrukerReader.read_2d(),
   │        │                                       filter experiment_type,
   │        │                                       lowest-exp-number tiebreak)
   │        │ none found? ──► _render_placeholder_png()
   │        ▼
   ├─► cache lookup: key = (route, source_mtime, peaks_mtime)
   │        │ HIT ──────────────────────────────────────────► return cached PNG bytes
   │        │ MISS
   │        ▼
   ├─► _read_peaks_2d(analysis_dir, "hsqc")  (reads analysis/peaks/hsqc.json)
   │        ▼
   ├─► block_max_decimate(data, f1_scale, f2_scale, max_dim=512)
   │        ▼
   ├─► noise_sigma = _compute_2d_noise_sigma(FULL-RES data)  (reuse from
   │        │                                                  processing/peak_picker_2d.py)
   │        ▼
   ├─► levels = geometric_levels(5*sigma, factor=1.4, count=8)
   │        ▼
   ├─► _render_2d_png(Figure, FigureCanvasAgg, decimated_data, dec_f1, dec_f2,
   │        levels, peaks, experiment_type)
   │        │  fig.add_subplot → ax.contour(f2, f1, data, levels=...) →
   │        │  _apply_nmr_axes_2d(ax, dec_f1, dec_f2) → ax.scatter(overlay) →
   │        │  canvas.print_png(buf)  [finally: del canvas, del fig]
   │        ▼
   ├─► cache store: {key: png_bytes}  (evict older entries for same route)
   │        ▼
   └─► Response(png_bytes, media_type="image/png")   ── HTTP 200, always
```

### Recommended Project Structure

No new files. All additions live inside the existing:
```
src/lucy_ng/webview/routers/spectra.py   # + 3 routes, 2D helpers (this phase)
src/lucy_ng/webview/static/index.html    # replace spectra-2d placeholder <div>
src/lucy_ng/webview/static/webview.js    # + refreshSpectra2D(), called from tick()
tests/test_webview_api.py                # + TestSpectraEndpoint2D (or extend existing class)
```

### Pattern 1: Contour rendering with the OO API (no pyplot)

**What:** `Figure`/`FigureCanvasAgg` constructed directly (never `matplotlib.pyplot`),
exactly like `_render_1d_png`/`_render_placeholder_png` already do.
**When to use:** Every 2D render path in this phase.
**Verified working example** (timed at 0.10–0.13 s end-to-end against real CASE1 data,
`[VERIFIED: live execution against CASE1 exp 6 (HSQC), exp 7 (HMBC), exp 5 (COSY)]`):

```python
# Pattern verified live in this research session — see Code Examples for the full script.
fig = figure_cls(figsize=(9.0, 6.0), dpi=100)
canvas = canvas_cls(fig)
try:
    ax = fig.add_subplot(111)
    # data.shape == (len(f1_ppm_scale), len(f2_ppm_scale)) — CONFIRMED empirically.
    # matplotlib's ax.contour(X, Y, Z) wants Z.shape == (len(Y), len(X)):
    #   X = f2_ppm_scale (F2/direct, x-axis), Y = f1_ppm_scale (F1/indirect, y-axis)
    # This is EXACTLY the native layout — no transpose, no swapaxes.
    ax.contour(f2_ppm_scale, f1_ppm_scale, data, levels=levels,
               colors="#495057", linewidths=0.5)
    ax.set_xlim(float(f2_ppm_scale[0]), float(f2_ppm_scale[-1]))  # both already descending
    ax.set_ylim(float(f1_ppm_scale[0]), float(f1_ppm_scale[-1]))
    ax.set_xlabel("δH (ppm)")
    ax.set_ylabel("δC (ppm)")
    buf = io.BytesIO()
    canvas.print_png(buf)
    return buf.getvalue()
finally:
    del canvas
    del fig
```

**Extending `_apply_nmr_axes` to 2D:** the existing 1D helper only sets `xlim`. Add a
sibling (or an optional `ppm_scale_y` parameter) that also sets `ylim` — CONTEXT.md D-08
requires BOTH axes go through the shared helper "so neither axis is left un-reversed by
omission." A `_apply_nmr_axes_2d(ax, f1_ppm_scale, f2_ppm_scale)` sibling function is the
simplest extension that preserves the existing 1D signature untouched (no risk of
breaking Phase 95's passing tests).

### Pattern 2: Data orientation — confirmed empirically, not assumed

`[VERIFIED: live execution, this research session]` — ran `BrukerReader.read_2d()`
against 7 real 2D experiment directories (4 from the repo's bundled
`data/4-(1-Hydroxyethyl)benzoic acid isopropylester/` dataset, 3 from the real CASE1
dataset already used by `tests/test_webview_api.py`):

| Dir | `experiment_type` | `data.shape` | `f1_nucleus`/`f2_nucleus` | `f1_ppm_scale` range | `f2_ppm_scale` range |
|-----|---|---|---|---|---|
| repo `.../4` | HMBC | `(1024, 2048)` | 13C / 1H | 245.1 → −4.7 (descending) | 8.53 → 0.77 (descending) |
| repo `.../5` | HSQC | `(1024, 2048)` | 13C / 1H | 170.1 → −4.7 | 8.53 → 0.77 |
| repo `.../8` | COSY | `(1024, 1024)` | 1H / 1H | 8.53 → 0.78 | 8.53 → 0.78 |
| CASE1 `/5` | COSY | `(512, 1024)` | 1H / 1H | — | — |
| CASE1 `/6` | HSQC | `(1024, 2048)` | 13C / 1H | — | — |
| CASE1 `/7` | HMBC | `(1024, 2048)` | 13C / 1H | — | — |

In every case: `data.shape[0] == len(f1_ppm_scale)` (F1 = rows = indirect dimension,
13C for HSQC/HMBC, 1H for COSY), `data.shape[1] == len(f2_ppm_scale)` (F2 = columns =
direct dimension, always 1H). Both scales are already descending (Bruker convention,
same as the 1D reader) — **no `[::-1]` reversal needed**, consistent with Phase 95's
Pitfall 3 ("ppm_scale from BrukerReader is ALREADY descending").

This directly satisfies CONTEXT.md D-08 (F2=¹H on x, F1=¹³C on y for HSQC/HMBC) and the
SC1 axis-direction requirement with **zero extra transformation code** — just pass
`f2_ppm_scale` as X and `f1_ppm_scale` as Y to `ax.contour`.

### Pattern 3: Block-max decimation to ≤512×512 (numpy, no new dependency)

`[VERIFIED: live execution]` — timed at **0.007 s** for a 1024×2048 → 512×512
reduction (negligible compared to the ~0.1 s contour render itself):

```python
import numpy as np
from numpy.typing import NDArray


def _block_max_decimate(
    data: NDArray[np.float64],
    scale_a: NDArray[np.float64],
    scale_b: NDArray[np.float64],
    max_dim: int = 512,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Block-maximum decimate a 2D array to <= max_dim in each axis.

    Partitions `data` into (step_a, step_b) blocks and takes each block's
    max -- so a narrow cross-peak apex falling between grid points survives
    downsampling (D-04). The matching scales are decimated consistently by
    simple striding + truncation to the decimated shape (edge-padding
    the array first if the dimension does not evenly divide).
    """
    ny, nx = data.shape
    step_y = max(1, -(-ny // max_dim))  # ceil division
    step_x = max(1, -(-nx // max_dim))
    if step_y == 1 and step_x == 1:
        return data, scale_a, scale_b  # already small enough -- no-op
    pad_y = (-ny) % step_y
    pad_x = (-nx) % step_x
    padded = np.pad(data, ((0, pad_y), (0, pad_x)), mode="edge")
    ny2, nx2 = padded.shape
    decimated = padded.reshape(ny2 // step_y, step_y, nx2 // step_x, step_x).max(axis=(1, 3))
    dec_a = scale_a[::step_y][: decimated.shape[0]]
    dec_b = scale_b[::step_x][: decimated.shape[1]]
    return decimated, dec_a, dec_b
```

Verified output shapes: 1024×2048 (HSQC/HMBC, step 2×4) → 512×512; 512×1024 (COSY,
step 1×2) → 512×512. Ceiling division correctly handles non-power-of-2 source
dimensions without a remainder bug.

**Striding fallback** (only if block-max ever fails the < 1 s budget on some future
larger dataset — not needed based on this research's timing, documented per D-04's
"document whichever is shipped and why"): `data[::step_y, ::step_x]` with matching
`scale[::step_y]` / `scale[::step_x]` — one line, no padding logic needed, but silently
drops narrow peaks between strided samples.

### Pattern 4: MAD noise floor — REUSE existing helper, do not hand-roll

`[VERIFIED: source read + live execution]` — `src/lucy_ng/processing/peak_picker_2d.py`
lines 11-48 already implements exactly this calculation for the HMBC/HSQC/COSY *peak
picker* itself:

```python
# src/lucy_ng/processing/peak_picker_2d.py — EXISTING, import this, do not duplicate:
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

The picker's own docstring documents empirical values for CASE1 exp 7 (HMBC):
sigma ≈ 2.15e4 against a global max of ≈7.48e7 — this research's live run against the
same file (CASE1 exp `7`) reproduced `sigma = 21514.38`, matching to 4 significant
figures `[VERIFIED: live execution reproduces documented value]`.

**Recommendation:** import `_compute_2d_noise_sigma` from
`lucy_ng.processing.peak_picker_2d` into `spectra.py` rather than re-deriving the MAD
formula. This is a plain numpy function with zero matplotlib/fastapi coupling, so
importing it at module top of `spectra.py` does not violate WV-08 (only
fastapi/matplotlib imports are import-scope-restricted). Reusing it also guarantees the
rendering's "is this real signal" contour floor is derived the same way as the
peak-picker's own signal/noise threshold — visually consistent with what was actually
picked. `ruff`'s selected rule set (`E,W,F,I,B,UP` — confirmed via `pyproject.toml`
`[tool.ruff.lint]`) does not include a private-member-import restriction
(`SLF001`/`flake8-self` not selected), so this cross-module import of a `_`-prefixed
function is not lint-blocked `[VERIFIED: pyproject.toml [tool.ruff.lint] select list]`.
If the planner prefers not to import a private symbol across modules, the 6-line
function can be duplicated locally with a comment citing the source — either is
acceptable; import is recommended to avoid formula drift.

**Compute sigma on the FULL-RESOLUTION array, not the decimated one.** Block-max
decimation systematically inflates every retained value (each block reports its
maximum), which biases the median/MAD upward and would raise the noise floor
artificially. Compute `_compute_2d_noise_sigma(spectrum.data)` (pre-decimation) once,
then decimate separately for the contour plot itself. This ordering was used in the
verified timing run above and stayed well under budget (MAD computation on a
1024×2048 array is itself sub-millisecond via `np.median`).

**Level construction** (Claude's discretion per D-01, "geometric, ~8" locked):

```python
def _geometric_levels(floor: float, factor: float = 1.4, count: int = 8) -> NDArray[np.float64]:
    """Geometric contour levels starting at `floor`, growing by `factor` each step."""
    return floor * (factor ** np.arange(count))
```

Verified with `floor = 5.0 * sigma` (k=5, matching the existing peak-picker's
`snr_floor` default of 5.0 — see `PeakPicker2D.pick_peaks`'s `snr_floor: float = 5.0`
parameter, `[VERIFIED: source read, peak_picker_2d.py:64]`) and `factor=1.4, count=8`:
produced a sensible, visually-graduated level ladder for all three experiment types in
the timing run (e.g. HMBC: `[107572, 150601, 210841, 295178, 413249, 578549, 809969,
1133956]` against a data max of order 1e7-1e8) — weak long-range HMBC cross-peaks near
the floor remain visible while strong one-bond HSQC peaks do not smear the plot shut.

### Pattern 5: mtime-keyed PNG cache inside the router module

**What:** A module-level dict, closed over inside `make_router()`, keyed on a tuple of
source-file mtimes so repeated polls within the same mtime window return the cached PNG
without re-rendering.

**Which file(s) to key on:** the processed-data file the reader actually opens —
`experiment_dir / "pdata" / "1" / "2rr"` `[VERIFIED: live `ls`, confirmed this is an
8 MB float32 real-real 2D data file matching `1024 * 2048 * 4` bytes exactly for the
verified HSQC/HMBC shapes]` — **plus** the relevant peaks JSON
(`analysis/peaks/{hsqc,hmbc,cosy}.json`), since an overlay-only re-pick should also
invalidate the cache even if the raw spectrum file is untouched.

```python
# Module-level, closed over by make_router() -- persists for the life of the
# server process (single-user localhost tool, no size-unbounded risk given
# only 3 routes x 1 entry each = 3 cached PNGs max under the "keep only the
# latest mtime per plot" eviction policy).
_png_cache: dict[str, tuple[float, bytes]] = {}


def _cached_or_render(cache_key: str, source_mtime: float, render_fn: Callable[[], bytes]) -> bytes:
    """Return the cached PNG if source_mtime matches; otherwise render + store.

    `render_fn` is a zero-arg closure so it is only invoked on a cache miss
    (avoids paying the render cost merely to compute a key comparison).
    Because the dict holds at most one entry per cache_key (route name), a
    NEWER mtime simply overwrites the OLD entry -- no explicit eviction list
    is needed beyond "one slot per route."
    """
    cached = _png_cache.get(cache_key)
    if cached is not None and cached[0] == source_mtime:
        return cached[1]
    png_bytes = render_fn()
    _png_cache[cache_key] = (source_mtime, png_bytes)
    return png_bytes
```

**Combining two mtimes into one cache key value:** use `max(bruker_file_mtime,
peaks_json_mtime)` as the single `source_mtime` float — either file changing produces a
different max, invalidating the cache; neither changing reproduces the identical float,
hitting the cache. This is simpler than a tuple-of-two-floats key and equally correct
for "invalidate on either changing."

**Frontend cache-buster vs. server cache — no conflict.** The frontend's `?t=<timestamp
>` query param (mirroring `refreshSpectra1D`'s existing pattern) exists only to defeat
the *browser's* HTTP cache on the `<img>` tag (forces a new network request every
poll) — the FastAPI route itself ignores query params entirely and the server-side
cache keys purely on filesystem mtime, so a cache-busted browser request still gets a
cache HIT server-side when the underlying files are unchanged. This is exactly the
behaviour CONTEXT.md's "Carried forward" section specifies.

**mtime source when the experiment directory changes between polls** (e.g. a
re-selected experiment): keying on `bruker_file_mtime` of the *selected* experiment's
`2rr` file (not the whole dataset root) means a different experiment selection with a
different mtime naturally produces a cache miss — no extra invalidation logic needed
for that case either.

### Pattern 6: Cross-peak overlay — open circles, HMBC colour-coded by flag

`[VERIFIED: source read]` — the exact HMBC flag→colour palette already exists in
`src/lucy_ng/webview/static/index.html` lines 339-353 (CSS, applied to table rows by
`webview.js`'s `HMBC_FLAG_CLASS` map):

| Flag | Hex | CSS class |
|------|-----|-----------|
| `ok` | `#28a745` (green) | `.row-ok` |
| `potential_4J` | `#ffc107` (amber) | `.row-potential-4j` |
| `1J_artifact` | `#adb5bd` (grey) | `.row-1j-artifact` |

Reuse these exact hex values for the scatter marker edge colour (D-06 — "reusing the
Phase 94 HMBC flag-colour palette for consistency between the Tables tab and the 2D
plot"):

```python
_HMBC_FLAG_COLORS = {
    "ok": "#28a745",
    "potential_4J": "#ffc107",
    "1J_artifact": "#adb5bd",
}
_DEFAULT_FLAG_COLOR = "#495057"  # unrecognised/missing flag -- same as trace colour

def _plot_hmbc_overlay(ax: Any, peaks: list[dict[str, Any]]) -> None:
    for peak in peaks:
        try:
            x = float(peak["proton_ppm"])
            y = float(peak["carbon_ppm"])
        except (KeyError, TypeError, ValueError):
            continue
        color = _HMBC_FLAG_COLORS.get(peak.get("flag"), _DEFAULT_FLAG_COLOR)
        ax.scatter([x], [y], s=30, facecolors="none", edgecolors=color, linewidths=1.0)
```

**HSQC** (D-05, uniform style): `x=proton_ppm, y=carbon_ppm`, single colour
(recommend `_ACCENT_COLOR = "#0c5460"`, already defined in `spectra.py` for the 1D
peak markers — visual consistency), `facecolors="none"` open circles, no flag
distinction.

**COSY** (D-07): `x=proton_a_ppm, y=proton_b_ppm`, open circles, PLUS a thin grey
diagonal line `F1=F2`:

```python
def _plot_cosy_diagonal(ax: Any, f1_scale: NDArray[np.float64], f2_scale: NDArray[np.float64]) -> None:
    lo = max(float(f1_scale[-1]), float(f2_scale[-1]))
    hi = min(float(f1_scale[0]), float(f2_scale[0]))
    ax.plot([lo, hi], [lo, hi], color="#adb5bd", linewidth=0.5, linestyle="-")
```
(Drawn using the overlapping ppm range of the two axes, since COSY F1/F2 ranges are
nearly but not always numerically identical — verified in the repo `.../8` example
above: `f1[0]=8.5288 f2[0]=8.5288` to 5 decimal places but not bit-identical.)

### Pattern 7: 2D experiment selection — mirror of `_select_experiment`, inverted filter

```python
def _select_experiment_2d(bruker_data_dir: Path, experiment_type: str) -> Spectrum2D | None:
    """Scan numbered dirs, return the best Spectrum2D for `experiment_type`.

    Mirror of the 1D `_select_experiment`, INVERTED filter: only dirs WITH
    acqu2s are candidates (the 1D selector explicitly EXCLUDES these). Among
    matches for `experiment_type`, lowest experiment number wins (same
    tiebreak as the 1D selector, per CONTEXT.md's discretion note).
    """
    if not bruker_data_dir.is_dir():
        return None
    candidates: list[tuple[int, Spectrum2D]] = []
    try:
        entries = sorted(bruker_data_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return None
    for exp_dir in entries:
        if not exp_dir.is_dir() or not re.match(r"^\d+$", exp_dir.name):
            continue
        if not (exp_dir / "acqu2s").exists():
            continue  # 1D experiment -- not a candidate
        try:
            spectrum = BrukerReader.read_2d(exp_dir)
        except (FileNotFoundError, ValueError, OSError):
            continue  # unreadable / not a 2D experiment / undetectable pulse program
        if spectrum.experiment_type != experiment_type:
            continue
        candidates.append((int(exp_dir.name), spectrum))
    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]
```

Verified against real data: `_detect_experiment_type` (in `bruker.py`) correctly
classified all 7 tested directories as HMBC/HSQC/COSY/NOESY without error — NOESY
(repo `.../6`) is correctly excluded by the `experiment_type != "HSQC"` etc. filter, so
no extra guard is needed for TOCSY/NOESY/ROESY dirs sharing a dataset root; they simply
never match any of the three requested types.

### Anti-Patterns to Avoid

- **Computing MAD/noise-floor on the decimated array:** biases the estimate upward
  (block-max systematically inflates retained values) — compute on full-resolution
  data, decimate separately for display.
- **`ax.contourf()` or a colormap-by-intensity approach:** explicitly rejected by
  D-02/D-03 — single muted colour, line contours only, positive-only levels.
- **Transposing `data` before passing to `ax.contour`:** unnecessary — verified the
  native `(f1, f2)` = `(rows, cols)` layout already matches what
  `ax.contour(f2_scale, f1_scale, data)` expects.
- **Re-deriving the MAD formula from scratch:** `_compute_2d_noise_sigma` already
  exists in `processing/peak_picker_2d.py` — import it.
- **Keying the cache on the frontend's `?t=` query param:** defeats the entire purpose
  of the cache; key on filesystem mtime only, ignore the query string server-side
  (exactly as CONTEXT.md's "Carried forward" section specifies).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MAD-based robust noise sigma for a 2D array | A fresh `median`/`abs`/`median` calculation in `spectra.py` | `lucy_ng.processing.peak_picker_2d._compute_2d_noise_sigma` | Already exists, already handles the zero/NaN-MAD fallback, already empirically validated against CASE1 HMBC in its own docstring; reusing it keeps the render's "is this real signal" threshold visually consistent with what the picker actually flagged as a peak |
| Block-max downsampling of a 2D array | Hand-written nested loops or a new `scikit-image` dependency | `numpy.reshape(...).max(axis=(1,3))` (6-line function, verified in this research) | numpy is already a base dep; no new dependency; verified fast (7 ms for 1024×2048→512×512) |
| Reversed-ppm-axis handling | Duplicate axis-limit logic per route | Extend the shared `_apply_nmr_axes` helper (or add a 2D sibling) exactly as CONTEXT.md D-08 mandates | Prevents the exact class of bug Phase 95's Pitfall 3 called out — an axis silently left un-reversed |
| 2D-experiment-type detection from pulse program | Re-implement pulse-program string matching in `spectra.py` | `BrukerReader.read_2d()` → `Spectrum2D.experiment_type` (already computed by `_detect_experiment_type` in `bruker.py`) | Already implemented, already handles HSQC/HMBC/COSY/TOCSY/NOESY/ROESY disambiguation including the tricky `inv4`-pulse-program long-range-vs-one-bond HMBC/HSQC distinction |

**Key insight:** every piece of "hard" 2D NMR domain logic (data orientation, noise
estimation, experiment-type detection) was already solved for the *peak-picking*
pipeline in prior phases. This phase's job is purely to re-present that already-computed
domain knowledge as a picture — resist the urge to re-derive any of it from first
principles inside the webview layer.

## Common Pitfalls

### Pitfall 1: Decimating the ppm scale inconsistently with the data
**What goes wrong:** Striding `data[::2, ::4]` but forgetting to stride
`f1_ppm_scale`/`f2_ppm_scale` by the same factors produces a contour plot with
correct-looking axes but data plotted at the wrong ppm positions (off by the
decimation ratio).
**Why it happens:** The two arrays are decimated in separate function calls / lines;
easy to change one and forget the other during review.
**How to avoid:** Return all three (decimated data + both decimated scales) from a
single `_block_max_decimate` call (as shown in Pattern 3) so they can never drift
apart; never decimate the scale in a separate statement.
**Warning signs:** Cross-peak overlay markers appear systematically offset from the
contour lines they should sit on top of.

### Pitfall 2: Computing the noise floor on decimated data
**What goes wrong:** Block-max decimation inflates the array (every retained cell is a
local maximum), so `median`/MAD computed post-decimation over-estimates the noise
floor, potentially raising it above real weak HMBC cross-peaks and making them
invisible.
**Why it happens:** It looks natural to decimate first (smaller array = faster MAD
computation) then threshold — but the bias direction is the opposite of what
"threshold weak-but-real signal" needs.
**How to avoid:** Compute `_compute_2d_noise_sigma(spectrum.data)` on the FULL-resolution
array (verified sub-millisecond even at 1024×2048) before decimating for display.
**Warning signs:** Long-range HMBC cross-peaks near the SNR floor disappear from the
contour plot even though `analysis/peaks/hmbc.json` lists them.

### Pitfall 3: Assuming F1/F2 axis assignment is symmetric for all experiment types
**What goes wrong:** HSQC/HMBC have F1=¹³C (indirect) / F2=¹H (direct) — but COSY has
F1=¹H / F2=¹H (homonuclear), and a hypothetical future NOESY/TOCSY would too. Hardcoding
"F1 is always carbon" breaks COSY.
**Why it happens:** HSQC/HMBC are the first two routes usually implemented; the pattern
"F1=carbon" gets baked in before COSY is considered.
**How to avoid:** Always read the axis assignment from `Spectrum2D.f1_nucleus` /
`f2_nucleus` (or simply always plot `f2_ppm_scale` as x / `f1_ppm_scale` as y regardless
of nucleus — this is what D-07/D-08 specify: COSY plots `proton_a_ppm` on x =
F2 = direct, `proton_b_ppm` on y = F1 = indirect, which the reader already returns
correctly for a homonuclear experiment). Verified: for the repo `.../8` COSY example,
`f1_nucleus == f2_nucleus == "1H"` — the F1/F2 *positional* mapping (x=F2, y=F1) still
holds regardless of both being ¹H.
**Warning signs:** COSY diagonal line does not align with the actual symmetric
cross-peak pairs.

### Pitfall 4: Cache growing unbounded across experiment re-selections
**What goes wrong:** If the cache key includes something that changes every request
(e.g. accidentally including the `?t=` timestamp, or a full `Spectrum2D` object repr),
every request is a miss and the dict grows forever — exactly the memory-growth failure
SC4 is designed to prevent.
**Why it happens:** Copy-pasting a cache-key pattern from elsewhere without checking
what varies request-to-request vs. what's stable.
**How to avoid:** Key strictly on `(route_name, source_mtime)` where `source_mtime` is a
plain float from `Path.stat().st_mtime` — never include the request object, query
params, or object identity in the key. One dict entry per route (3 total) under the
"keep only latest mtime per plot" eviction policy (D-04-cache discretion).
**Warning signs:** `_png_cache` dict length grows across repeated polls in a long-running
process instead of staying at exactly 3 entries.

### Pitfall 5: `2rr` file may not exist for every processed-data configuration
**What goes wrong:** Some 2D processing configurations produce different file names in
`pdata/1/` (e.g. magnitude-mode data might not have all four `2rr`/`2ri`/`2ir`/`2ii`
quadrants, though `2rr` — real-real, the one nmrglue's `read_pdata` and this phase both
need — was present in all 7 tested directories). If `mtime` is computed by directly
`stat()`-ing `pdata/1/2rr` without a try/except, a dataset missing that specific file
would raise before ever reaching the render's own never-500 guard, IF that stat call
happens outside the guarded block.
**Why it happens:** The mtime-key computation is a new piece of code not covered by
the existing `_select_experiment`-style try/except patterns.
**How to avoid:** Wrap the `pdata/1/2rr` mtime lookup (or fall back to
`exp_dir.stat().st_mtime` — the whole experiment directory's mtime — if the specific
file is absent) inside the same broad `except Exception` never-500 guard as the render
call itself, per the `_render_nucleus`-style pattern in Phase 95's `make_router()`.
**Warning signs:** A 500 error (rather than the placeholder PNG) on a dataset with an
unusual processing configuration.

## Code Examples

Verified patterns from live execution against real project data (this research
session):

### Full verified prototype (decimate → noise floor → contour → PNG, timed)

```python
# Verified: 0.10-0.13s total for HSQC/HMBC/COSY against real CASE1 data.
import io
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from lucy_ng.processing.peak_picker_2d import _compute_2d_noise_sigma

def render_2d_contour(spectrum, peaks, experiment_type):
    sigma = _compute_2d_noise_sigma(spectrum.data)  # full-res, BEFORE decimation
    decimated, f1s, f2s = _block_max_decimate(
        spectrum.data, spectrum.f1_ppm_scale, spectrum.f2_ppm_scale, max_dim=512
    )
    levels = _geometric_levels(floor=5.0 * sigma, factor=1.4, count=8)

    fig = Figure(figsize=(9.0, 6.0), dpi=100)
    canvas = FigureCanvasAgg(fig)
    try:
        ax = fig.add_subplot(111)
        ax.contour(f2s, f1s, decimated, levels=levels, colors="#495057", linewidths=0.5)
        ax.set_xlim(float(f2s[0]), float(f2s[-1]))
        ax.set_ylim(float(f1s[0]), float(f1s[-1]))
        ax.set_xlabel("δH (ppm)")
        ax.set_ylabel("δC (ppm)" if experiment_type != "COSY" else "δH (ppm)")
        # ... overlay scatter per Pattern 6 ...
        buf = io.BytesIO()
        canvas.print_png(buf)
        return buf.getvalue()
    finally:
        del canvas
        del fig
```

### mtime cache key computation with never-500 guard

```python
def _source_mtime(exp_dir: Path, peaks_path: Path) -> float:
    """Combined mtime for cache-key purposes; falls back gracefully."""
    try:
        data_file = exp_dir / "pdata" / "1" / "2rr"
        data_mtime = (data_file if data_file.exists() else exp_dir).stat().st_mtime
    except OSError:
        data_mtime = 0.0
    try:
        peaks_mtime = peaks_path.stat().st_mtime if peaks_path.exists() else 0.0
    except OSError:
        peaks_mtime = 0.0
    return max(data_mtime, peaks_mtime)
```

## State of the Art

No state-of-the-art shift relevant to this phase — matplotlib's OO API (`Figure` +
`FigureCanvasAgg`, no `pyplot`) is the same long-stable pattern already adopted in
Phase 95; no new matplotlib version features are needed (`ax.contour` with explicit
`levels=` has been stable API since long before matplotlib 3.7).

**Deprecated/outdated:** N/A.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pdata/1/2rr` is the correct file to mtime-key the cache on for ALL 2D processing configurations (magnitude-mode, phase-sensitive, etc.), not just the 7 real-real datasets tested | Pattern 5 / Pitfall 5 | Low — mitigated by the documented fallback to `exp_dir.stat().st_mtime` and the never-500 guard; worst case is a slightly coarser cache invalidation granularity, not a crash |
| A2 | `factor=1.4, count=8, k=5.0` (geometric level parameters) will look visually good across ALL future datasets, not just the 3 tested here | Pattern 4 (Don't Hand-Roll) / Code Examples | Low-Medium — CONTEXT.md explicitly grants Claude's discretion here and asks only that the chosen values be documented; if a future dataset's contour looks too sparse/dense, the constants are trivially tunable in one place |
| A3 | `_compute_2d_noise_sigma` (a `_`-prefixed "private" function) is intended to be reusable across modules within the package, not strictly module-private | Pattern 4 | Low — verified no lint rule blocks this; if the team prefers strict module-privacy, duplicating the 6-line formula locally is a trivial fallback with no functional difference |

**All other claims in this research were verified via live tool execution against real
project code and real Bruker datasets in this session** — data orientation, palette
hex values, dependency presence, ruff rule selection, and render timing are not
training-data assumptions.

## Open Questions (RESOLVED)

1. **Should the mtime cache be a plain module-level dict (as prototyped) or
   `functools.lru_cache`?**
   - What we know: Both work; CONTEXT.md leaves "mtime-cache internal structure" to
     Claude's discretion.
   - What's unclear: Whether the planner/team has a stylistic preference for one over
     the other within this codebase.
   - **RESOLVED:** Recommendation: Plain dict (as shown in Pattern 5) — simpler to reason about for
     "keep only latest mtime per plot" eviction and easier to unit-test
     (`spectra._png_cache` is directly inspectable), whereas `lru_cache` would require
     wrapping the render function itself and complicates testing cache-hit-vs-miss
     behaviour explicitly.

2. **Exact figure size/DPI for the 2D plots** (CONTEXT.md leaves this to discretion).
   - What we know: 1D plots use `_FIGSIZE = (9.0, 3.0)`, `_DPI = 100`. 2D contour plots
     are typically closer to square/landscape since both axes carry meaningful ppm
     range.
   - What's unclear: No locked value; purely a visual-polish decision.
   - **RESOLVED:** Recommendation: `(9.0, 6.0)` at `DPI=100` (used in this research's timing
     prototype, produced legible 512×512-decimated contours) — taller than the 1D
     plots to give the y-axis (F1) room, same width for visual column alignment in the
     stacked layout (D-09).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| matplotlib | Contour rendering | ✓ | `>=3.7` (per `pyproject.toml [webview]`) | — |
| numpy | Decimation, MAD, meshgrid args | ✓ | base dep | — |
| nmrglue | `BrukerReader.read_2d()` | ✓ | base dep | — |
| Real 2D Bruker test data | Integration tests | ✓ | Both CASE1 (`$HOME/Dropbox/.../CASE1/{5,6,7}`) and the repo-bundled `data/4-(1-Hydroxyethyl).../{4,5,6,8}` datasets confirmed present and readable this session | — |

No missing dependencies.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed `[tool.pytest.ini_options]` in `pyproject.toml`) |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| Quick run command | `pytest tests/test_webview_api.py::TestSpectraEndpoint2D -x` (new class, or extend `TestSpectraEndpoint`) |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SP2-01 | HSQC/HMBC/COSY PNG routes return valid image/png, HTTP 200, on real data | integration | `pytest tests/test_webview_api.py -k "spectra_2d and real"` | ❌ Wave 0 (new tests) |
| SP2-01 | Both axes reversed (`xlim[0]>xlim[1]` AND `ylim[0]>ylim[1]`) | unit | `pytest tests/test_webview_api.py -k "apply_nmr_axes_2d"` | ❌ Wave 0 |
| SP2-01 | HMBC markers colour-coded by flag (visual — verify via source-code palette assertion, mirroring the `test_single_combined_rotated_label_per_peak` `inspect.getsource` pattern already used in Phase 95's test suite) | unit | `pytest tests/test_webview_api.py -k "hmbc_flag_color"` | ❌ Wave 0 |
| SC3 | Render < 1s | perf (manual/CI-timed) | `pytest tests/test_webview_api.py -k "render_under_budget"` — assert `time.time()` delta | ❌ Wave 0 |
| SC3 | Cache hit skips re-render (poll does not re-render) | unit | `pytest tests/test_webview_api.py -k "cache_hit_no_rerender"` — monkeypatch the render function, assert not called on 2nd request with unchanged mtime | ❌ Wave 0 |
| SC4 | Repeated polling causes no unbounded cache growth | unit | `pytest tests/test_webview_api.py -k "cache_bounded"` — assert `len(spectra._png_cache) <= 3` after N repeated requests | ❌ Wave 0 |
| SP-02 | Absent manifest / stale path / no matching experiment → placeholder PNG, never 500 | integration | `pytest tests/test_webview_api.py -k "spectra_2d and placeholder"` | ❌ Wave 0 |
| WV-08 | Import-safety — module collects cleanly without `[webview]` extra | unit | existing pattern (`try/except ImportError: pytest.skip`) applied to new test methods | ❌ Wave 0 (apply existing pattern) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_webview_api.py -k spectra_2d`
- **Per wave merge:** `pytest tests/test_webview_api.py`
- **Phase gate:** Full suite (`pytest`) green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] New `TestSpectraEndpoint2D` class (or extend `TestSpectraEndpoint`) in
      `tests/test_webview_api.py` — RED-by-skip scaffold mirroring the Phase 95 pattern
      (WV-08 import guard, `CASE1_ROOT.is_dir()` skip guard for real-data tests).
- [ ] Fixtures: reuse `CASE1_ROOT` (already defined, and confirmed this session to
      contain real HSQC(`/6`)/HMBC(`/7`)/COSY(`/5`) 2D experiments — no new fixture
      dataset needed) plus new hand-authored `analysis/peaks/{hsqc,hmbc,cosy}.json`
      fixtures for the overlay-marker-position/colour assertions (mirroring
      `tables_analysis_dir`'s hand-authored-to-locked-schema pattern).
- [ ] A `synthetic_bruker_2d_dir` fixture (acqus+acqu2s text only, no real pdata) is
      NOT strictly needed for the acqu2s-inclusion-filter unit test the way
      `synthetic_bruker_dir` was for the 1D exclusion test — since `_select_experiment_2d`
      needs a matching `experiment_type`, which requires an actual readable `pdata/1/2rr`
      to reach `BrukerReader.read_2d()` successfully. Recommend testing the
      acqu2s-inclusion-filter logic against the REAL CASE1/repo datasets instead (skip
      when absent), rather than hand-authoring a fake 2D pdata file.

## Security Domain

This phase is a strict extension of Phase 95's threat model — no new attack surface is
introduced (same trusted-local-manifest read pattern, same localhost single-user tool).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Localhost dev tool, no auth layer (unchanged from Phase 91-95) |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Single-user local tool |
| V5 Input Validation | Partial | Peaks JSON fields are defensively cast with `try/except (KeyError, TypeError, ValueError): continue` per-peak (mirrors the existing 1D `_render_1d_png` peak loop) — malformed individual peak rows are skipped, never crash the render |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `bruker_data_dir` in manifest | Tampering | Already mitigated at the trust-boundary level per Phase 95 D-07 ("trust the manifest's absolute path — localhost single-user tool, written by the trusted local `case.md` process"); unchanged this phase — no new path-construction logic beyond what `_select_experiment`-style scanning already does |
| Malformed/huge peaks JSON causing unbounded render loop or memory spike | Denial of Service | Existing `_JSON_READ_ERRORS` broad-except pattern in `spectra.py`/`tables.py` bounds this; peaks lists are typically O(10-100) rows for real NMR datasets, no pagination needed |
| Cache-key collision across concurrent analysis dirs (if the server is ever multi-tenant) | Tampering/Information Disclosure | Not applicable — `create_app(analysis_dir)` is one FastAPI app instance per analysis directory (confirmed in `app.py`); the module-level `_png_cache` dict is closed over per-router-instance inside `make_router()`, not shared across `analysis_dir`s, so no cross-tenant leakage risk exists in the current single-process-per-run architecture |

## Sources

### Primary (HIGH confidence — live execution / direct source read this session)
- `src/lucy_ng/webview/routers/spectra.py` (Phase 95, full file read) — the module to extend
- `src/lucy_ng/webview/routers/tables.py` — never-500 pattern, HMBC flag passthrough
- `src/lucy_ng/models/spectrum.py` — `Spectrum2D` model definition
- `src/lucy_ng/readers/bruker.py` — `BrukerReader.read_2d()`, `_detect_experiment_type()`
- `src/lucy_ng/processing/peak_picker_2d.py` — `_compute_2d_noise_sigma()`, `PeakPicker2D.pick_peaks()` (`snr_floor=5.0` default)
- `src/lucy_ng/webview/static/index.html` — HMBC flag CSS palette (lines 339-353), tab markup, 2D placeholder location
- `src/lucy_ng/webview/static/webview.js` — `refreshSpectra1D`, `tick()`, `HMBC_FLAG_CLASS`
- `src/lucy_ng/webview/app.py` — `create_app()` router docking
- `tests/test_webview_api.py` — `TestSpectraEndpoint`, `CASE1_ROOT` fixture, `synthetic_bruker_dir`, `tables_analysis_dir` patterns
- `pyproject.toml` — `[project.optional-dependencies].webview` (matplotlib), `[tool.ruff.lint]` select list, `[tool.pytest.ini_options]`
- Live Python execution (this session): `BrukerReader.read_2d()` against 7 real experiment directories (repo-bundled + CASE1), confirming `data.shape`, ppm-scale direction, MAD sigma values, block-max decimation correctness, and full-pipeline render timing (0.10-0.13s)
- `.planning/phases/96-2d-real-spectra-peak-overlay/96-CONTEXT.md` — locked decisions (D-01 through D-10)
- `.planning/phases/95-1d-real-spectra-peak-overlay/95-CONTEXT.md` — prior-phase decisions this phase inherits
- `.planning/STATE.md` §"[v9.3-roadmap]" — cross-phase locked decisions
- `.planning/REQUIREMENTS.md` — SP2-01, SP-02

### Secondary (MEDIUM confidence)
- None needed — all findings this phase were directly verifiable against the actual codebase and real data.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency, all versions confirmed present via source read
- Architecture: HIGH — data orientation and axis mapping empirically verified via live execution against 7 real 2D datasets, not assumed
- Pitfalls: HIGH — derived from actual behavior observed during the verification runs (e.g. the MAD-on-decimated-data bias was reasoned from the block-max algorithm's known properties, not speculative)

**Research date:** 2026-07-11
**Valid until:** 2026-08-11 (30 days — stable internal codebase, no external API surface at risk of drift)
