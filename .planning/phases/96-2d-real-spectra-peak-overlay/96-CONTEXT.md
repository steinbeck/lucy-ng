# Phase 96: 2D Real Spectra + Peak Overlay - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Populate the **2D Spectra** tab (3rd tab of the webview right panel, currently a
`"coming in Phase 96"` placeholder in `index.html`) with **real HSQC, HMBC, and COSY
contour plots rendered from the raw Bruker 2D data**, with the picked cross-peaks
overlaid as scatter markers — completing the full spectral inspection suite so a
chemist can visually validate 2D peak-picking quality against the actual 2D signal.

**Purely additive to Phase 95** — same `spectra.py` router module, same
`analysis/.run_manifest.json` path-wiring, same matplotlib-Agg (OO-API) pipeline, same
`_apply_nmr_axes` reversed-axis discipline. New work: three PNG routes under
`/api/spectra/2d/{hsqc,hmbc,cosy}`; `BrukerReader.read_2d()` access; contour rendering;
decimation to ≤512×512; MAD-derived threshold contour levels; an **mtime-keyed PNG
cache** (the expensive-render cache deferred to this phase from Phase 95 D-06); and the
2D-Spectra frontend tab (three stacked `<img>` + `refreshSpectra2D`).

**Not in scope:** any peak *editing*; interactive zoom/pan (v9.4); a JS charting library
(violates no-build/no-CDN); DEPT sub-tab / SSE live push (v9.4); 1D spectra (Phase 95,
done); changes to the `.run_manifest.json` contract (Phase 95 already writes it — this
phase only reads it, extended to locate 2D experiments).

</domain>

<decisions>
## Implementation Decisions

### Contour rendering
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

### Decimation
- **D-04 (Block-maximum preferred; Claude's discretion):** The ≤512×512 cap is a locked
  v9.3-roadmap decision; the **method** is Claude's discretion with a strong lean:
  prefer **block-maximum (max-pooling)** — partition the 2D array into blocks and take
  each block's max — so a narrow cross-peak apex falling between grid points **survives**
  the downsampling (the entire QC value depends on real peaks not silently vanishing).
  Plain **striding** (`data[::step]`) is acceptable ONLY as a performance fallback if
  block-max cannot meet the <1 s budget (SC3); document whichever is shipped and why.

### Cross-peak overlay markers
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

### Axis mapping (per experiment)
- **D-08 (HSQC/HMBC: F2=¹H on x, F1=¹³C on y; both reversed):** For HSQC and HMBC the
  direct dimension **F2 = ¹H is the x-axis**, indirect **F1 = ¹³C is the y-axis**, both
  reversed (ROADMAP SC1: aromatic region top-left, F2 ~7 ppm / F1 ~130 ppm). Overlay
  coordinates: x = `proton_ppm`, y = `carbon_ppm`. For COSY, x/y = `proton_a_ppm` /
  `proton_b_ppm` (D-07). Both 2D axes go through the shared `_apply_nmr_axes` helper
  (extended to 2D) so neither axis is left un-reversed by omission.

### Layout & endpoints
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

### Carried forward from v9.3-roadmap (LOCKED — do NOT re-decide)
- **Reversed ppm axes on both dimensions** via the shared `_apply_nmr_axes()` helper
  (extend it for 2D F1+F2).
- **Decimate to ≤512×512 before contouring; MAD-noise-floor threshold levels** (D-01/D-04
  refine the *how*, not the *whether*).
- **mtime-keyed per-router PNG cache** — cache rendered PNGs keyed by source-file mtime so
  the ~3 s browser poll does NOT trigger re-renders on a cache hit (SC3). Note the Phase 95
  frontend cache-busts with `?t=<timestamp>`; the server cache keys on **source mtime**,
  not the query string, so cache hits still work across polls.
- **Figures closed after each render (`try/finally`)** + the mtime cache prevent unbounded
  Figure allocation / memory growth under repeated polling (SC4).
- **matplotlib OO API only** (`Figure` + `FigureCanvasAgg`; never `pyplot`), **lazy import
  inside `make_router()`**, matplotlib only in the `[webview]` extra; base `lucy` install
  imports without it (WV-08 / D-04-from-95).
- **Sync `def` route handlers** (FastAPI dispatches CPU-bound renders to a threadpool).
- **SP-02 graceful degradation** carried as a hard acceptance criterion.

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing spectra router (the base to EXTEND — do NOT redesign)
- `src/lucy_ng/webview/routers/spectra.py` — the Phase 95 module to extend in place:
  `_read_manifest`, `_select_experiment` (1D; write a 2D analog that keeps only dirs with
  `acqu2s`), `_read_peaks`, `_apply_nmr_axes` (extend to 2D F1+F2), `_render_1d_png`,
  `_render_placeholder_png`, `make_router()` with the lazy matplotlib import + never-500
  `_render_nucleus` guard. Mirror all of these for the 2D routes.
- `src/lucy_ng/webview/app.py` — `create_app()` already docks `_spectra.make_router()`
  (line ~66); the three 2D routes are added inside the SAME router, so no new
  `include_router` line is needed. Update the route docstring list (lines ~37-38).
- `src/lucy_ng/webview/routers/tables.py` — the never-500 `make_router(analysis_dir)`
  pattern + multi-file defensive reading; also the Phase 94 HMBC **flag-colour palette**
  (reuse for D-06 marker colours).

### Raw Bruker 2D data access
- `src/lucy_ng/readers/bruker.py` — `BrukerReader.read_2d(experiment_dir) -> Spectrum2D`
  (lines ~198-284): reads `pdata/1/`, `nmrglue` guess_udic, generates `f1_ppm_scale`
  (dim 0, indirect) + `f2_ppm_scale` (dim 1, direct), detects `experiment_type`
  (HSQC/HMBC/COSY/…). A 2D experiment dir has `acqu2s` (the 1D selector explicitly skips
  these — the 2D selector keeps ONLY these).
- `src/lucy_ng/models/spectrum.py` — `Spectrum2D` (line 56): `data` (2D array),
  `f1_ppm_scale`, `f2_ppm_scale`, `f1_nucleus`, `f2_nucleus`, `experiment_type`,
  `frequency`, `metadata`.

### Cross-peak JSON schemas (from Phase 94)
- `analysis/peaks/hsqc.json` — `experiment`/`count`/`note` + `peaks[]` with `carbon_ppm`,
  `proton_ppm`, `intensity`, `matched_real_carbon`, `one_bond`.
- `analysis/peaks/hmbc.json` — `experiment`/`raw_count`/`kept_count`/`flag_rules`/`note` +
  `peaks[]` with `carbon_ppm`, `carbon_ppm_observed`, `proton_ppm`, `intensity`, `flag`
  (`ok`/`potential_4J`/`1J_artifact`).
- `analysis/peaks/cosy.json` — `experiment`/`count`/`note` + `peaks[]` with `proton_a_ppm`,
  `proton_b_ppm`, `intensity`.

### Frontend (the 2D tab to populate)
- `src/lucy_ng/webview/static/index.html` — line ~435 `data-panel="spectra-2d"` placeholder
  (`"2D Spectra — coming in Phase 96"`) to replace with three stacked `<img>`; reuse the
  1D-spectra style block (~line 371) and inline `<style>` tokens; no new design system.
- `src/lucy_ng/webview/static/webview.js` — the ~3 s `tick()` poll; `refreshSpectra1D`
  (~line 716-727) with the `?t=<timestamp>` cache-buster + independent per-panel img `.src`
  update — mirror as `refreshSpectra2D` for the three 2D imgs; call it from `tick()`.

### Tests
- `tests/test_webview_api.py` — WV-08 import-safety pattern (fastapi/webview imports inside
  test bodies; `try/except ImportError: pytest.skip`); the Phase 95 `TestSpectraEndpoint`
  fixture style to extend for the 2D routes (hand-authored 2D fixture or a small synthetic
  `Spectrum2D`; assert never-500, reversed axes `xlim[0]>xlim[1]` and `ylim[0]>ylim[1]`,
  cache-hit does not re-render).

### Packaging
- `pyproject.toml` — `matplotlib>=3.7` already in `[project.optional-dependencies].webview`
  (added Phase 95); `nmrglue`/`numpy` base deps. No new dependency this phase.

### Locked-decision sources
- `.planning/STATE.md` §"[v9.3-roadmap]" bullets — reversed axes / 2D performance
  (decimate ≤512×512, MAD threshold, mtime cache, sync `def`) / matplotlib OO-only /
  SP-02 assignment. These are the LOCKED decisions carried forward above.
- `.planning/ROADMAP.md` §"Phase 96" — goal + SC1–SC4.
- `.planning/REQUIREMENTS.md` — SP2-01 (real 2D HSQC/HMBC/COSY contour plots, reversed
  axes both dims, cross-peaks overlaid); SP-02 (graceful "unavailable", carried from 95).

### Prior-phase decisions carried forward
- `.planning/phases/95-1d-real-spectra-peak-overlay/95-CONTEXT.md` — D-01 (strict
  "unavailable", no synthetic fallback), D-03 (marker + label overlay style), D-04
  (matplotlib OO/lazy/`[webview]`), D-05 (stale path → unavailable), D-06 (cache deferred
  HERE), D-07 (trust manifest absolute path). Its `_apply_nmr_axes`/`_render_*`/
  `_select_experiment`/never-500 patterns are the direct templates.
- `.planning/phases/94-data-tables/94-CONTEXT.md` — D-03 (HMBC flag colours: `ok` /
  `potential_4J` / `1J_artifact`) — the palette to reuse for D-06.

### Conventions
- `CLAUDE.md` (repo) — `pytest`, `mypy src/lucy_ng` (strict), `ruff check src tests`.
- WV-08 — fastapi/webview/matplotlib imports inside function/test bodies only; base
  `lucy` install must import without the `[webview]` extra.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BrukerReader.read_2d(experiment_dir) -> Spectrum2D` — 2D raw-data reader; nmrglue
  handles pdata + both ppm scales + `experiment_type` detection. No new reader needed.
- `spectra.py` Phase 95 helpers — `_read_manifest`, `_render_placeholder_png`,
  `_apply_nmr_axes`, the `make_router()` lazy-import + `_render_nucleus` never-500 guard:
  all directly reusable / extendable for 2D.
- Phase 94 `tables.py` HMBC flag-colour palette — reuse for D-06 marker colours (keeps
  Tables tab and 2D plot visually consistent).
- `webview.js` `refreshSpectra1D` — copy shape for `refreshSpectra2D`.

### Established Patterns
- One `spectra.py` router; PNG image endpoints (no client-side charting); frontend
  `fetch/img.src → catch` on the shared ~3 s poll, each panel independent.
- "Dumb server reads files, degrades to a placeholder PNG, never 500" (SP-02).
- WV-08 lazy imports; matplotlib OO-API only (`Figure`+`FigureCanvasAgg`, never `pyplot`);
  `try/finally` figure release.
- 1D selector skips `acqu2s` dirs → the 2D selector is its mirror image (keep only
  `acqu2s` dirs, match `Spectrum2D.experiment_type`).

### Integration Points
- Extend `src/lucy_ng/webview/routers/spectra.py` with three 2D routes (same router; no new
  `include_router` line — already docked).
- Replace the `data-panel="spectra-2d"` placeholder in `index.html` with three stacked
  `<img>`; add `refreshSpectra2D` to `webview.js`, called from `tick()`.
- New mtime-keyed PNG cache inside `spectra.py` (first cache in the webview; expensive 2D
  renders are why it exists — SC3/SC4).
- Extend `tests/test_webview_api.py::TestSpectraEndpoint` (or a `2D` sibling) — never-500,
  reversed axes both dims, cache-hit-no-rerender, WV-08 import-safety.
- `pyproject.toml` — no change (matplotlib already in `[webview]`).

</code_context>

<specifics>
## Specific Ideas

- Real **contour plots** from raw Bruker 2D processed data with picked cross-peaks
  overlaid as **open-circle** markers — the 2D analog of Phase 95's QC value (are peaks
  sitting on real signal?).
- **Both axes reversed**, aromatic region top-left (F2 ~7 ppm / F1 ~130 ppm) — concrete
  axis-direction check `xlim[0]>xlim[1]` AND `ylim[0]>ylim[1]`.
- **HMBC markers coloured by flag** (matches the Tables-tab flag palette); **COSY draws
  the diagonal**; **HSQC markers uniform**.
- **Geometric ~8 contour levels**, single muted colour, positive-only.
- **Block-maximum decimation** preferred so narrow cross-peaks survive the ≤512×512 cap.
- **mtime-keyed PNG cache** so the ~3 s poll never re-renders on a cache hit (server keys
  on source mtime, independent of the frontend `?t=` cache-buster).

</specifics>

<deferred>
## Deferred Ideas

- **Negative / phase-sensitive edited-HSQC contours** (CH2 down-peaks) — considered,
  rejected for this phase (D-03); positive-only is enough for QC. Possible v9.4.
- **HSQC one_bond / matched_real_carbon marker distinction** — considered, rejected
  (D-05, low QC value); uniform markers instead.
- **Sub-tabs / plot selector inside the 2D tab** — considered, rejected (D-09); stacked
  all-visible mirrors 1D and allows comparison.
- **Interactive zoom/pan, DEPT sub-tab, SSE live push** → v9.4 per STATE.md.
- **Colormap-by-intensity contours** — rejected (D-02); would introduce new colours and
  compete with overlay markers.

### Reviewed Todos (not folded)
- `CASE4 azulene regiochemistry enumeration gap` (skill) — a CASE-solver concern
  (keyword-only match on "phase, 2026"); nothing to do with 2D spectra rendering. Same
  disposition as Phase 95. Belongs to the CASE-skill backlog.

</deferred>

---

*Phase: 96-2d-real-spectra-peak-overlay*
*Context gathered: 2026-07-10*
