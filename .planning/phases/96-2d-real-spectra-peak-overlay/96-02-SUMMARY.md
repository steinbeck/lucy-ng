---
phase: 96-2d-real-spectra-peak-overlay
plan: 02
subsystem: api
tags: [fastapi, matplotlib, nmrglue, numpy, webview, nmr-2d]

# Dependency graph
requires:
  - phase: 96-2d-real-spectra-peak-overlay (Plan 01)
    provides: TestSpectraEndpoint2D RED-by-skip scaffold + spectra_case1_manifest_dir_2d fixture (hand-authored hsqc/hmbc/cosy peaks JSON to the LOCKED Phase-94 schema)
  - phase: 95-1d-real-spectra-peak-overlay
    provides: spectra.py router module (_read_manifest, _select_experiment, _render_1d_png, _render_placeholder_png, make_router's lazy-matplotlib + never-500 guard shape) to extend in place
provides:
  - Three GET /api/spectra/2d/{hsqc,hmbc,cosy} PNG routes rendering real Bruker 2D contour plots with cross-peak overlays
  - _select_experiment_2d / _selected_2d_pdata_path 2D experiment selection (acqu2s-filtered)
  - _apply_nmr_axes_2d (both-axes-reversed F1/F2 helper)
  - _block_max_decimate (block-max decimation to <=512x512) + _geometric_levels (D-01 contour levels)
  - _plot_hmbc_overlay/_plot_uniform_overlay/_plot_cosy_diagonal/_plot_hmbc_legend overlay renderers
  - _render_2d_png (full contour+overlay render) + module-level mtime-keyed _png_cache/_cached_or_render
affects: [97-frontend-2d-spectra-tab (or equivalent next plan wiring index.html/webview.js to these routes)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "2D PNG route mirrors the 1D never-500 _render_nucleus guard shape exactly (_render_2d closure inside make_router)"
    - "mtime-keyed PNG cache: module-level dict, one slot per route, keyed on (route_name, source_mtime) independent of the frontend's ?t= cache-buster"
    - "Noise floor computed on full-resolution data BEFORE block-max decimation to avoid upward bias"

key-files:
  created: []
  modified:
    - src/lucy_ng/webview/routers/spectra.py
    - src/lucy_ng/webview/app.py

key-decisions:
  - "Contour levels: geometric, floor=5.0*sigma, factor=1.4, count=8 (D-01, per 96-RESEARCH.md verified prototype)"
  - "Decimation: block-maximum (max-pooling) to <=512x512, ceil-division + edge-pad (D-04) -- narrow HMBC apexes survive downsampling"
  - "_selected_2d_pdata_path added as an internal helper (not a return-contract change) so the mtime cache can key on the real pdata/1/2rr file without touching _select_experiment_2d's frozen Wave-0 signature"
  - "_render_placeholder_png reused verbatim (9.0x3.0 figsize) for 2D placeholder branches per the plan's explicit interface note, even though 96-UI-SPEC.md's figure-sizing table describes matching figsize as an ideal -- no test enforces placeholder figsize, and the plan's canonical_refs explicitly lists it as reuse-verbatim/do-not-modify"

patterns-established:
  - "2D overlay dispatch is mutually exclusive with the peaks-unavailable annotation, mirroring the 1D _render_1d_png branch shape"

requirements-completed: [SP2-01, SP-02]

# Metrics
duration: 25min
completed: 2026-07-11
---

# Phase 96 Plan 02: 2D Real Spectra Backend Routes Summary

**Three new `/api/spectra/2d/{hsqc,hmbc,cosy}` PNG routes render real HSQC/HMBC/COSY contour plots from raw Bruker 2D data with cross-peak overlays, block-max decimation, geometric MAD-threshold levels, and an mtime-keyed cache — the backend half of SP2-01.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-11T12:19:26Z
- **Tasks:** 2/2 completed
- **Files modified:** 2

## Accomplishments
- Extended `spectra.py` in place with 2D-analog helpers for every 1D pattern (`_select_experiment_2d`, `_apply_nmr_axes_2d`, `_read_peaks_2d`, `_render_2d_png`) plus three genuinely new pieces: block-max decimation, the mtime-keyed PNG cache, and the per-experiment-type overlay/colour logic
- All three routes wired into the existing `make_router()` factory (no new `APIRouter`/`include_router`), reusing the single lazy `Figure`/`FigureCanvasAgg` import
- `app.py` docstring extended to document the three new SP2-01 routes
- Zero regressions to Phase 95's 1D routes/tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Add module-level 2D helpers** - `feceecd` (feat)
2. **Task 2: Wire the three 2D routes into make_router + update app.py docstring** - `63f899b` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `src/lucy_ng/webview/routers/spectra.py` - +2D helpers (selection, axes, decimation, levels, overlays, cache) and three routes registered in `make_router()`
- `src/lucy_ng/webview/app.py` - docstring lists the three new `/api/spectra/2d/*` routes

## Decisions Made
- Contour level constants (`floor=5.0*sigma`, `factor=1.4`, `count=8`) and decimation method (block-max) match 96-RESEARCH.md's verified prototype exactly, so timing/visual behavior is reproducible from the research session (0.10-0.13s end-to-end per plot on real CASE1 data, well under the 1s SC3 budget).
- Added `_selected_2d_pdata_path` as a small internal re-scan helper (identical scan + tiebreak logic to `_select_experiment_2d`) purely to source the mtime cache key from the real `pdata/1/2rr` file, without changing `_select_experiment_2d`'s Wave-0-frozen `Spectrum2D | None` return contract (protects the frozen `test_spectra_2d_select_experiment_2d_keeps_only_acqu2s` test, which is out of this plan's `files_modified`).
- `_render_placeholder_png` and other Phase-95 1D functions/constants were reused byte-for-byte unmodified, per the plan's explicit "reuse verbatim" interface list.

## Deviations from Plan

None — plan executed exactly as written. All helper names, signatures, and constants match the plan's `<action>` specifications and 96-RESEARCH.md's verified patterns.

## Issues Encountered

Two minor mypy/ruff findings surfaced during Task 1's own verification loop (not deviations from the plan's design, just implementation-detail fixes within the same task before its commit):
- `_geometric_levels`'s return type needed an explicit `.astype(np.float64)` cast (numpy's `float ** int-array` infers `floating[Any]`, not concretely `float64`).
- `_plot_hmbc_overlay`'s `peak.get("flag")` needed an `isinstance(flag, str)` guard before the `_HMBC_FLAG_COLORS.get(flag, ...)` lookup (mypy: dict.get expects a `str` key, not `Any | None`).
- `Callable` import moved from `typing` to `collections.abc` per ruff's `UP035`.

All three were resolved before Task 1's commit; `mypy src/lucy_ng/webview/routers/spectra.py` (strict) and `ruff check` both pass clean on the final state.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Backend is complete and test-covered (13/13 `TestSpectraEndpoint2D`, 12/12 `TestSpectraEndpoint` regression-free, 60/60 full `test_webview_api.py` suite green).
- Ready for the frontend plan (Plan 03/04 per the phase's plan sequence) to replace the `data-panel="spectra-2d"` placeholder in `index.html` with the three stacked `<img>` elements and add `refreshSpectra2D()` to `webview.js`, per 96-UI-SPEC.md's Layout & Interaction Contract — no backend blockers.
- `_png_cache` is empty at server start and bounded to <=3 entries under repeated polling (verified by `test_spectra_2d_cache_bounded`); no memory-growth risk carried forward.

---
*Phase: 96-2d-real-spectra-peak-overlay*
*Completed: 2026-07-11*
