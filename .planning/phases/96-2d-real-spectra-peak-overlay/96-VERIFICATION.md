---
phase: 96-2d-real-spectra-peak-overlay
verified: 2026-07-12T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 96: 2D Real Spectra + Peak Overlay Verification Report

**Phase Goal:** Users see real HSQC, HMBC, and COSY contour plots rendered from the raw Bruker 2D data with the picked cross-peaks overlaid, completing the full spectral inspection suite.
**Verified:** 2026-07-12
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Merged from ROADMAP.md Success Criteria (SC1-SC4) + REQUIREMENTS.md (SP2-01, carried SP-02) + WV-08.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 (SC1) | HSQC contour plot with BOTH ppm axes reversed, aromatic region top-left (F2 ~7 ppm x, F1 ~130 ppm top), HSQC cross-peaks from `analysis/peaks/hsqc.json` overlaid as scatter markers | VERIFIED | `_apply_nmr_axes_2d` (spectra.py:415-436): `ax.set_xlim(f2[0], f2[-1])` (high-ppm-left) + `ax.set_ylim(f1[-1], f1[0])` (high-ppm-TOP, second-arg-is-top-spine). This is the FIXED direction — commit `00cd505` corrected an original inversion bug found during the 96-04 manual browser checkpoint (originally `set_ylim(f1[0], f1[-1])`, which put downfield at the BOTTOM). Diff confirmed via `git show 00cd505`. Test `test_spectra_2d_apply_nmr_axes_2d_reverses_both_scales` asserts `xlim[0] > xlim[1]` AND `ylim[1] > ylim[0]` (the corrected direction) and `ylim[1] == 160.0` (downfield endpoint at top) — PASSES. `_plot_uniform_overlay(ax, peaks, "proton_ppm", "carbon_ppm", ...)` overlays HSQC peaks as open circles (`facecolors="none"`). Live test `test_spectra_2d_hsqc_returns_png_on_case1_real` PASSES against the real CASE1 HSQC dataset (not skipped). |
| 2 (SC2) | HMBC + COSY contour plots with cross-peaks overlaid; HMBC markers colour-coded by flag from `analysis/peaks/hmbc.json` | VERIFIED | `_plot_hmbc_overlay` (spectra.py:459-478) looks up `_HMBC_FLAG_COLORS = {"ok": "#28a745", "potential_4J": "#ffc107", "1J_artifact": "#adb5bd"}` per-peak by `flag`, falling back to `_DEFAULT_FLAG_COLOR` for unknown/missing — same palette as the Phase 94 Tables tab (locked D-06). `_plot_hmbc_legend` draws the 3-line legend. `_plot_cosy_diagonal` draws the F1=F2 orientation line; `_plot_uniform_overlay(ax, peaks, "proton_a_ppm", "proton_b_ppm", ...)` overlays COSY cross-peaks. `test_spectra_2d_hmbc_flag_color_palette` (source + optional dict inspection) and the three `..._returns_png_on_case1_real` tests all PASS against real CASE1 HSQC/HMBC/COSY data. |
| 3 (SC3) | Render < 1s/request: decimate ≤512×512 before contouring, MAD-noise-floor threshold levels, PNGs cached keyed by source-file mtime — the ~3s poll does not re-render on a cache hit | VERIFIED | `_block_max_decimate` (spectra.py:317-346) block-maxes to `max_dim=512` via ceil-division + edge-pad; `_geometric_levels(5.0*sigma, factor=1.4, count=8)` builds MAD-derived (`_compute_2d_noise_sigma`, computed on full-res data BEFORE decimation) geometric levels. `_cached_or_render` (spectra.py:373-388) keys strictly on `(f"{analysis_dir}:{kind}", source_mtime)`, independent of the frontend's `?t=` cache-buster. `test_spectra_2d_render_under_budget` (real CASE1 HSQC, single request) asserts `elapsed < 1.0` — PASSES. `test_spectra_2d_cache_hit_no_rerender` monkeypatches `_render_2d_png` and asserts exactly 1 call across 2 identical-mtime requests — PASSES. |
| 4 (SC4) | Repeated polling causes no memory growth — figures closed after each render (`try/finally`), mtime cache bounded | VERIFIED | `_render_2d_png` (spectra.py:596-660) wraps the whole body in `try/finally: del canvas; del fig` (no `pyplot`, so nothing is registered in a global figure manager to leak). `_png_cache` is a bounded dict (one entry per `(analysis_dir, kind)` route-key; a newer mtime simply overwrites the old entry — no unbounded growth). `test_spectra_2d_cache_bounded` polls all 3 routes repeatedly and asserts `len(_png_cache) <= 3` — PASSES. |
| 5 (SP2-01/SP-02) | Per-plot graceful "unavailable" placeholder, HTTP 200 never 500, for absent manifest / stale path / no matching 2D experiment | VERIFIED | `_render_2d` (spectra.py:792-846) wraps the whole body in a broad `except Exception` never-500 guard, returning `_render_placeholder_png(..., _FIGSIZE_2D)` at HTTP 200 for every failure mode. Three dedicated tests (`test_spectra_2d_missing_manifest_placeholder`, `..._stale_path_placeholder`, `..._no_matching_experiment_placeholder`) all assert `status_code == 200` + `image/png` — PASS. |
| 6 (WV-08) | matplotlib lazy inside `make_router()` only; base `lucy` install (`from lucy_ng.cli import cli`) does not ImportError; matplotlib OO-API only (no `pyplot`) | VERIFIED | `grep "^import matplotlib\|^from matplotlib"` on spectra.py returns zero matches before `def make_router`; the two matplotlib imports live inside `make_router()` (lines 742-743). `grep pyplot` finds only two doc-comment mentions ("no matplotlib.pyplot import anywhere" / "nothing to close" in pyplot's figure manager) — no actual `import matplotlib.pyplot` or `plt.` usage anywhere in the file (confirmed by direct read). `python -c "from lucy_ng.cli import cli"` succeeds directly in this environment (base install, no `[webview]` extra installed as a distinguishing condition — but the import-order/lazy-scoping guarantee is structurally confirmed). `test_spectra_2d_no_module_level_matplotlib_import` PASSES. |
| 7 (Code-review CR-01 fix) | 2D placeholder figsize matches the real 2D render figsize (no layout jump between "unavailable" and real states) | VERIFIED | `_render_placeholder_png` now takes a `figsize` parameter (default `_FIGSIZE` for 1D callers); all three `_render_2d` placeholder call sites pass `_FIGSIZE_2D` (900×600 @ 100 dpi) explicitly (spectra.py:663-704, :807-846). Regression test `test_spectra_2d_missing_manifest_placeholder` unpacks the PNG IHDR chunk and asserts `(width, height) == (900, 600)` — PASSES (this is the exact regression guard the code review recommended and it was added). Fix commit `3021ca1` confirmed in git log. |
| 8 (Code-review WR-01 fix) | PNG cache scoped by `analysis_dir` (not a bare cross-instance-aliasing global) | VERIFIED | Cache key is `f"{analysis_dir}:{kind}"` (spectra.py:833), not just `(kind, mtime)` as the review originally flagged. Same commit `3021ca1`. |
| 9 (Manual checkpoint, 96-04) | Live browser render confirms real contours, reversed axes (aromatic top-left), HMBC flag colours, COSY diagonal, no flicker/memory growth, graceful placeholders | VERIFIED (human-executed, documented) | 96-04-SUMMARY.md documents a live `lucy webview serve` checkpoint against real CASE1 data with all 5 must-haves confirmed, including the F1-axis defect found and fixed in the same session (commit `00cd505`, independently confirmed above). This is prior human verification already performed as part of phase execution — no further human action needed. |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lucy_ng/webview/routers/spectra.py` | 2D helpers + 3 routes, ≥250 new lines | VERIFIED | 864 lines total; contains `_select_experiment_2d`, `_selected_2d_pdata_path`, `_read_peaks_2d`, `_apply_nmr_axes_2d`, `_block_max_decimate`, `_geometric_levels`, `_plot_uniform_overlay`, `_plot_hmbc_overlay`, `_plot_hmbc_legend`, `_plot_cosy_diagonal`, `_render_2d_png`, `_cached_or_render`/`_png_cache`, and 3 registered routes inside `make_router()`. No module-level matplotlib import. `mypy`/`ruff` both clean on this file specifically (see below). |
| `src/lucy_ng/webview/app.py` | 3 new routes docked, docstring updated | VERIFIED | `app.include_router(_spectra.make_router(analysis_dir))` (already present from Phase 95, no new line needed); docstring lists all 3 `/api/spectra/2d/*` routes (lines 39-42). |
| `src/lucy_ng/webview/static/index.html` | `spectra-2d` placeholder replaced with 3 stacked `<img>` sections | VERIFIED | `data-panel="spectra-2d"` div (lines 435-454) contains 3 `<section class="tables-section">` blocks (`spectrum-hsqc`/`-hmbc`/`-cosy`), each with an `<img id="img-spectrum-{hsqc,hmbc,cosy}" class="spectrum-img" src="/api/spectra/2d/{hsqc,hmbc,cosy}">`. No new CSS class introduced (D-09 honoured). |
| `src/lucy_ng/webview/static/webview.js` | `refreshSpectra2D()` defined + called in `tick()` | VERIFIED | Function at line 739 mirrors `refreshSpectra1D` (Date.now() cache-buster, 3 guarded `getElementById`/`.src` updates); called from `tick()` at line 795, immediately after `refreshSpectra1D()`. |
| `tests/test_webview_api.py::TestSpectraEndpoint2D` | 13 test methods, all real (not skipped) against CASE1 | VERIFIED | 13/13 collected and PASS in this environment (CASE1 dataset present, so all real-data-dependent tests execute against real data, not synthetic-only fixtures). Full suite: 60 passed, 0 skipped/failed. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `index.html` `<img>` | `/api/spectra/2d/{hsqc,hmbc,cosy}` | `src=` attribute | WIRED | Confirmed all 3 `src=` attributes point at the correct routes. |
| `webview.js` `refreshSpectra2D` | `tick()` | direct call | WIRED | Called unconditionally every ~3s poll tick. |
| `app.py` | `spectra.make_router()` | `include_router` | WIRED | Already docked (single router shared with Phase 95's 1D routes); docstring updated. |
| `_render_2d` route closure | `_select_experiment_2d` / `BrukerReader.read_2d` | direct call | WIRED | Reads real Bruker 2D data (`pdata/1/`), confirmed via live-passing `..._returns_png_on_case1_real` tests. |
| `_render_2d_png` | `analysis/peaks/{hsqc,hmbc,cosy}.json` | `_read_peaks_2d` | WIRED | Peaks list feeds `_plot_uniform_overlay`/`_plot_hmbc_overlay`/`_plot_cosy_diagonal`, dispatched by `experiment_type`. |
| `_render_2d` | `_png_cache` | `_cached_or_render` | WIRED | Cache-key scoped by `analysis_dir` + `kind` + `source_mtime`; verified cache-hit test passes with exactly 1 render call across 2 requests. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SP2-01 | 96-02, 96-03 | Real 2D HSQC/HMBC/COSY contour plots, both-axes-reversed, cross-peaks overlaid | SATISFIED | Backend routes + frontend wiring both present and test-covered (see Truths 1-2 above). |
| SP-02 (carried) | 96-02 | Graceful "unavailable" state, never 500 | SATISFIED | 3 placeholder tests PASS; CR-01 figsize-jump defect additionally fixed. |

**Documentation note (non-blocking):** `.planning/REQUIREMENTS.md`'s traceability table still lists `SP2-01 | Phase 96 | Pending` (unchecked `[ ]`) despite the phase being functionally complete and ROADMAP.md marking Phase 96 "Complete". The same staleness pattern exists for `LOG-01`/`TAB-01` (Phase 93, also marked "Pending" despite that phase being complete) — this appears to be a pre-existing project-wide bookkeeping gap in REQUIREMENTS.md's traceability table rather than a Phase-96-specific regression. Recommend updating the checkbox and traceability row at milestone close; does not block this phase's goal achievement.

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` debt markers in any of the 5 files modified by this phase (the `_PLACEHOLDER_COLOR` constant and `_render_placeholder_png` function names are legitimate identifiers for the SP-02 degraded-state feature, not debt markers). `ruff check` and `mypy` (module-scoped) both clean on `spectra.py`.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full webview test suite green | `pytest tests/test_webview_api.py -q` | 60 passed, 0 skipped/failed | PASS |
| 2D-specific suite green, real CASE1 data | `pytest tests/test_webview_api.py -k spectra_2d -v` | 13 passed (none skipped) | PASS |
| No regressions in wider test suite | `pytest -q -k "not lsd and not database"` | 801 passed, 5 skipped, 410 deselected | PASS |
| Lint clean | `ruff check src/lucy_ng/webview/routers/spectra.py tests/test_webview_api.py` | All checks passed! | PASS |
| No `pyplot` usage | `grep -n pyplot src/lucy_ng/webview/routers/spectra.py` | 2 matches, both doc-comments, zero actual imports/calls | PASS |
| Base install import safety (WV-08) | `python -c "from lucy_ng.cli import cli"` | succeeds | PASS |
| mypy clean on the modified module | `mypy src/lucy_ng/webview/routers/spectra.py` | 0 errors attributed to spectra.py (66 pre-existing errors in 19 unrelated transitively-imported files) | PASS |
| Both fix commits present in history | `git log --oneline` | `00cd505` (F1 axis fix) and `3021ca1` (CR-01/WR-01 fix) both present, diffs match claimed changes | PASS |

### Human Verification Required

None. The one item that would normally require human/visual verification (contour rendering quality, axis orientation, marker/legend readability in-browser) was already performed during phase execution as the mandatory 96-04 manual browser checkpoint, which is documented with a specific defect found (F1/y-axis inversion) and independently confirmed fixed via the corresponding commit's diff (see Truth 1 and 9 above). No new unresolved visual-only items remain.

### Gaps Summary

No gaps. All 4 ROADMAP success criteria (SC1-SC4), SP2-01, carried SP-02, and WV-08 are verified against the actual codebase (not just SUMMARY.md narrative). Both defects found during Phase 96's own execution (the SC1 F1/y-axis inversion, and code-review CR-01's placeholder-figsize layout jump) are confirmed present as fixes in the current code via direct diff inspection, not just SUMMARY claims. Full regression suite (801 tests outside lsd/database) and the full webview suite (60/60) pass with zero skips in the 2D-specific class, meaning the tests exercised real CASE1 Bruker data rather than merely synthetic fixtures. One non-blocking documentation-staleness item is noted (REQUIREMENTS.md traceability table not yet flipped to Complete for SP2-01) — recommended for milestone-close cleanup, not a functional gap.

---

_Verified: 2026-07-12_
_Verifier: Claude (gsd-verifier)_
