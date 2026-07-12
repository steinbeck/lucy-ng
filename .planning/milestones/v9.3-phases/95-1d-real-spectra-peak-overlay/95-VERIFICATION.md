---
phase: 95-1d-real-spectra-peak-overlay
verified: 2026-07-09T15:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 95: 1D Real Spectra + Peak Overlay Verification Report

**Phase Goal:** Users see real ¹³C (and ¹H if present) spectrum traces rendered from the raw Bruker data with the picked peaks overlaid as markers, enabling visual validation of peak-picking quality against the actual signal.
**Verified:** 2026-07-09
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Merged from ROADMAP.md Success Criteria (SC1-SC4) + PLAN frontmatter must_haves across all 5 plans.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: ¹³C spectrum renders as a real continuous trace (BrukerReader+nmrglue) with reversed ppm axis + picked peaks overlaid as vertical markers from `carbon_signals.json` | VERIFIED | `src/lucy_ng/webview/routers/spectra.py::_render_1d_png` plots `spectrum.ppm_scale` vs `spectrum.data` (real trace, not sticks) and overlays each peak as a vertical marker + combined ppm/assignment label. `test_carbon_returns_png_on_case1` and `test_peak_overlay_positions` PASS against the real CASE1 dataset (not skipped — dataset present on this machine). Human browser checkpoint (95-04-SUMMARY.md) independently confirmed a real continuous trace with noise floor visible and markers aligned to real peaks. |
| 2 | SC2: On CASE1, carbonyl (~181 ppm) appears far left, aliphatic CH3 on the right; `ax.get_xlim()[0] > ax.get_xlim()[1]` holds in tests | VERIFIED | `_apply_nmr_axes` uses `set_xlim(ppm_scale[0], ppm_scale[-1])` only (no `invert_xaxis`, confirmed absent via grep — exit 1/no match). `test_apply_nmr_axes_reverses_descending_scale` and `test_case1_carbonyl_left_of_aliphatic` both PASS. Human checkpoint independently confirmed carbonyl (180.9) far left, aliphatic CH3 (22.4/18.1) right, in a live browser render. |
| 3 | SC3: clean `pip install lucy-ng[webview]` can serve the tab (matplotlib in `[webview]` extra); `from lucy_ng.cli import cli` on base install does not raise; matplotlib imports lazy inside `make_router()` (WV-08) | VERIFIED | `pyproject.toml` `[project.optional-dependencies].webview = ["fastapi>=0.100", "uvicorn>=0.20", "matplotlib>=3.7"]`; base `[project].dependencies` has no matplotlib entry (grep confirmed). `python -c "from lucy_ng.cli import cli"` succeeds directly in this environment. `grep -n "^import matplotlib\|^from matplotlib"` on spectra.py returns no matches — only `from matplotlib...` inside `make_router()` (lines 322-323). `test_no_module_level_matplotlib_import` and `test_cli_imports_without_matplotlib` PASS. |
| 4 | SC4/SP-02: absent `.run_manifest.json` or missing peak JSON shows "unavailable/waiting" — HTTP 200, never 500 | VERIFIED | `make_router`'s `_render_nucleus` wraps the whole body in `except Exception` (never-500) and returns `_render_placeholder_png(...)` at HTTP 200 for: no manifest (`_MSG_NO_MANIFEST`), stale/unreadable bruker path (`_MSG_STALE_PATH`), no matching experiment, and any unexpected render error. `_read_peaks` degrades to `[]` (bare trace, not a failure) on missing/malformed peaks JSON. `test_missing_manifest_returns_placeholder`, `test_stale_bruker_path_returns_placeholder`, `test_missing_peaks_json_renders_bare_trace` all PASS. Human checkpoint independently confirmed both degradation paths return the exact locked copy strings as HTTP 200 image/png (no broken-image icon, no error banner). |
| 5 | ¹H spectrum renders when present, independent per-nucleus placeholder otherwise | VERIFIED | `get_proton_1d` route independent of `get_carbon_1d`; `_select_experiment(bruker_dir, "1H")` is called separately. `test_proton_present_and_carbon_independent` PASSES. Human checkpoint confirmed a real ¹H trace rendered (ibuprofen isopropyl doublet ~0.9 ppm visible). |
| 6 | 2D (`acqu2s`) and DEPT (`pulse_program` contains "dept") experiments are excluded from 1D selection; lowest-numbered standard experiment wins | VERIFIED | `_select_experiment` checks `(exp_dir / "acqu2s").exists()` BEFORE calling `read_1d` (2D exclusion, never opens the file) and checks `"dept" in pulse_program.lower()` after read (DEPT exclusion); `min()` by experiment number picks the lowest. `test_select_experiment_excludes_2d_and_dept` PASSES against real CASE1 (confirms `zgpg30` selected, not `dept135/90`). Human checkpoint independently confirmed carbonyl present in the rendered trace (a DEPT would drop it). |
| 7 | Frontend: 1D Spectra tab shows ¹³C + ¹H `<img>` sections fed by the PNG endpoints, refreshed every ~3s tick | VERIFIED | `index.html` lines 424/430-432: `<img id="img-spectrum-carbon" ... src="/api/spectra/1d/carbon">` and `img-spectrum-proton` equivalent, both inside always-present `<section class="tables-section">` blocks; `.spectrum-img` CSS present. `webview.js` defines `function refreshSpectra1D()` (line 722) reassigning both `.src` with a `?t=`+`Date.now()` cache-bust, and calls it inside `tick()` (line 775). Human browser checkpoint confirmed both `<img>` load live in the tab with no console errors. |
| 8 | `case.md` writes `analysis/.run_manifest.json` at run-start (before webview launch) so the router can locate the raw data | VERIFIED | `case.md` lines 244-250: `cat > "<compound_path>/analysis/.run_manifest.json" <<JSON` heredoc writing `bruker_data_dir` + `formula`, positioned after the `run_start` timing stamp's `mkdir -p .../analysis` (line 236) and before the `lucy webview serve` launch (line 259-262) — confirmed positionally correct in the file. |

**Score:** 8/8 truths verified

### Gap-Closure Verification (95-05)

The Wave-3 human-verify checkpoint (95-04) flagged one cosmetic defect: assignment-text labels drawn horizontally collided in dense-peak regions (aromatic ~127-141, methyls ~18-22). Plan 95-05 folded ppm + assignment into a single rotated per-peak label. Verified in code: `_render_1d_png`'s peak loop (spectra.py lines 246-257) contains exactly one `ax.text(...)` call per peak using `label = f"{ppm:.1f}  {assignment}" if assignment else f"{ppm:.1f}"` at `rotation=90` — no separate horizontal `ax.text(ppm, y_max, str(assignment), ...)` block remains (confirmed by reading the file directly). `test_single_combined_rotated_label_per_peak` PASSES.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | matplotlib>=3.7 in `[webview]` extra only | VERIFIED | Confirmed: `webview = ["fastapi>=0.100", "uvicorn>=0.20", "matplotlib>=3.7"]`; base deps clean (tomllib guard + direct grep both pass). |
| `src/lucy_ng/webview/routers/spectra.py` | `make_router` + 6 helpers, ≥120 lines | VERIFIED | 373 lines. Contains `_read_manifest`, `_select_experiment`, `_read_peaks`, `_apply_nmr_axes`, `_render_1d_png`, `_render_placeholder_png`, `make_router`. No module-level matplotlib import; no `invert_xaxis` anywhere. |
| `src/lucy_ng/webview/app.py` | spectra router docked via `include_router` | VERIFIED | `from lucy_ng.webview.routers import spectra as _spectra` + `app.include_router(_spectra.make_router(analysis_dir))`; docstring lists both new routes. |
| `src/lucy_ng/webview/static/index.html` | `img-spectrum-carbon`/`img-spectrum-proton` + `.spectrum-img` CSS | VERIFIED | Both `<img>` present, sourced at the correct routes; `.spectrum-img` CSS rule present; `spectra-2d` "coming in Phase 96" placeholder untouched. |
| `src/lucy_ng/webview/static/webview.js` | `refreshSpectra1D` defined + called in `tick()` | VERIFIED | Function defined (line 722), called in `tick()` (line 775). |
| `.claude/commands/lucy-ng/case.md` | run-start `.run_manifest.json` write block | VERIFIED | Present, correctly positioned between `mkdir -p analysis` and webview launch. |
| `tests/test_webview_api.py::TestSpectraEndpoint` | 12 test methods (11 from Plan 01 + 1 gap-closure from Plan 05) | VERIFIED | All 12 collected and PASS (none skipped — real CASE1 dataset present on this machine, so CASE1-dependent methods exercised real data, not just synthetic fixtures). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/test_webview_api.py` | `lucy_ng.webview.routers.spectra` | try/except ImportError guard | VERIFIED (moot — module exists) | Module exists; import succeeds directly, no skip triggered. |
| `spectra.py` | `lucy_ng.readers.bruker.BrukerReader.read_1d` | per-candidate read in `_select_experiment` | WIRED | `BrukerReader.read_1d(exp_dir)` called inside the candidate loop, wrapped in `(FileNotFoundError, ValueError, OSError)` catch. |
| `spectra.py` | `analysis/peaks/carbon_signals.json` | `_read_peaks` JSON read | WIRED | `_read_peaks` reads `analysis_dir / "peaks" / "carbon_signals.json"`, extracts `signals` list, feeds `_render_1d_png`. |
| `app.py` | `lucy_ng.webview.routers.spectra` | lazy import + `include_router` | WIRED | Confirmed both lines present in app.py. |
| `index.html` | `/api/spectra/1d/carbon` \| `/proton` | `<img src>` | WIRED | Both `<img>` elements src-ed at the correct endpoints. |
| `webview.js` | `refreshSpectra1D` | `tick()` registration | WIRED | Defined and called; appears >=2 times as required. |
| `case.md` | `analysis/.run_manifest.json` | `cat > ... <<JSON` heredoc | WIRED | Confirmed positioned correctly relative to `mkdir -p analysis` and webview launch. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `get_carbon_1d`/`get_proton_1d` routes | `spectrum.ppm_scale`/`spectrum.data` | `BrukerReader.read_1d(exp_dir)` on the real numbered experiment directory under `bruker_data_dir` (itself sourced from the trusted `.run_manifest.json`, written by `case.md` from the real CASE run's compound path) | Yes — `test_carbon_returns_png_on_case1` and `test_case1_carbonyl_left_of_aliphatic` exercised the REAL CASE1 dataset (not skipped) and PASSED; independently confirmed visually in the 95-04 human browser checkpoint (real trace with noise floor, correct carbonyl position, real ¹H isopropyl pattern) | FLOWING |
| Peak overlay markers | `peaks` list | `_read_peaks(analysis_dir)` reading `analysis/peaks/carbon_signals.json`'s `signals` list | Yes — hand-authored fixture in tests includes a ~181 ppm `C=O` signal that PASSED alignment assertions; human checkpoint confirmed markers align with real peaks in the trace (mis-picks would be visible) | FLOWING |

No hardcoded-empty or hollow-prop patterns found — the render path reads live filesystem data at request time on every poll tick (no caching stub in this phase; Phase 96 is where mtime caching is scoped).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SC3 base import guard | `python -c "from lucy_ng.cli import cli"` | Succeeds, prints "SC3 OK" | PASS |
| No module-level matplotlib import / no invert_xaxis | `grep -n "invert_xaxis\|^import matplotlib\|^from matplotlib" spectra.py` | No matches (exit 1) | PASS |
| TestSpectraEndpoint full run | `pytest tests/test_webview_api.py::TestSpectraEndpoint -v` | 12 passed, 0 skipped | PASS |
| Full webview test suite regression | `pytest tests/test_webview_api.py -q` | 47 passed | PASS |
| Full repo test suite regression | `pytest -q` | 1195 passed, 7 skipped, 1 xfailed, 0 failed | PASS |
| Static type/lint on touched files | `mypy`/`ruff` on `spectra.py`+`app.py`+`test_webview_api.py` | ruff: all checks passed; mypy: 0 errors attributed to spectra.py/app.py (66 pre-existing errors confined to unrelated modules: lsd/generator.py, lsd/orchestrator.py, lsd/runner.py, prediction/predictor.py, analysis/intensity_reporter.py, ranking/ranker.py) | PASS |

### Probe Execution

Not applicable — this is a feature phase (webview router + frontend + skill-script edit), not a migration/tooling phase. No `scripts/*/tests/probe-*.sh` declared in PLAN/SUMMARY files for this phase. SKIPPED (no probes declared).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|-------------|--------|----------|
| SP1-01 | 95-01 through 95-05 (all plans) | Real 1D ¹³C/¹H spectrum with reversed axis + peak overlay | SATISFIED | All observable truths above confirm implementation + tests + human visual confirmation. |
| SP-02 | 95-01, 95-02, 95-03 | Graceful "unavailable" HTTP-200 degradation on missing spectrum/peak data/raw path | SATISFIED | Never-500 guard confirmed in code + 3 independent test methods + human checkpoint confirmed both degradation paths render the locked placeholder image. |

**Note (non-blocking, documentation staleness):** `.planning/REQUIREMENTS.md` still shows `SP1-01`/`SP-02` as unchecked `[ ]` with Traceability status "Pending" (lines 24, 26, 54-55). This is stale relative to the actual implementation state verified above — REQUIREMENTS.md checkbox/traceability updates are typically a milestone-close bookkeeping step, not a phase-goal blocker. Flagged here for the next `/gsd-complete-milestone` pass to reconcile; does not affect this phase's `passed` status since the underlying functional requirement is fully implemented, tested, and human-verified.

**No orphaned requirements:** Only SP1-01 and SP-02 map to Phase 95 in REQUIREMENTS.md's Traceability table; both are claimed by the plans' `requirements` frontmatter. SP2-01 correctly maps to Phase 96 (out of scope here).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TODO/FIXME/XXX/TBD/placeholder-text/stub patterns found in `spectra.py` | — | None — grep for debt markers and empty-implementation patterns returned no matches in the phase's new/modified source file. |

No blockers. The only "placeholder" strings present are the intentional, UI-SPEC-locked degradation copy (`_MSG_NO_MANIFEST`, `_MSG_STALE_PATH`, etc.), which is the correct, spec'd behavior for SP-02 — not a code smell.

### Human Verification Required

None outstanding. The phase's human-verify checkpoint (95-04) was already executed by the orchestrator via live browser automation against the real CASE1/ibuprofen dataset, and the user approved after the one cosmetic defect (label collision) was fixed by gap-closure plan 95-05 (see 95-04-SUMMARY.md and 95-05-SUMMARY.md). No unresolved visual/UX items remain for this phase.

### Gaps Summary

No gaps. All 8 derived observable truths (ROADMAP SC1-4 plus the frontend/case.md wiring truths from PLAN frontmatter) are VERIFIED against the actual codebase, not just SUMMARY claims:

- The reversed-axis contract (`set_xlim` only, no `invert_xaxis`) is real and tested against the actual CASE1 carbonyl/aliphatic positions.
- The 2D/DEPT exclusion logic is real, checks `acqu2s` before ever opening the file, and is proven against the real CASE1 experiment layout.
- The never-500 degradation contract is implemented as a genuine broad-exception guard around the whole render path, not a partial guard — verified for all three failure modes (no manifest, stale path, missing peaks).
- matplotlib is genuinely lazy-imported only inside `make_router` — verified by direct source inspection (no grep match for a module-level import) and by the base CLI import succeeding.
- The frontend wiring (`<img>` mounts, `refreshSpectra1D`, `case.md` manifest write) is real and correctly positioned, not stubbed.
- The Wave-3 human-verify checkpoint was genuinely executed via live browser automation against real data (not simulated), and its one captured defect was genuinely fixed and re-tested in 95-05.
- Full regression suite (1195 passed, 0 failed) confirms no unintended side effects elsewhere in the codebase.

The only non-blocking observation is the stale REQUIREMENTS.md checkbox/traceability status, noted above for milestone-close bookkeeping — it does not reflect a gap in the actual implementation.

---

_Verified: 2026-07-09_
_Verifier: Claude (gsd-verifier)_
