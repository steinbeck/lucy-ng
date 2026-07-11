---
phase: 96-2d-real-spectra-peak-overlay
plan: 01
subsystem: webview-tests
tags: [pytest, webview, spectra-2d, tdd-scaffold, wave-0]
requires: []
provides:
  - TestSpectraEndpoint2D
  - spectra_case1_manifest_dir_2d fixture
  - hand-authored analysis/peaks/{hsqc,hmbc,cosy}.json overlay fixtures (Wave-0 scaffold)
affects:
  - tests/test_webview_api.py
tech-stack:
  added: []
  patterns:
    - "Plan-02-only-symbol import probe inside the WV-08 try/except ImportError guard (forces clean SKIP instead of a 404-driven FAIL on not-yet-registered routes)"
key-files:
  created: []
  modified:
    - tests/test_webview_api.py
decisions:
  - "2D-route-dependent test methods probe for a Plan-02-only symbol (_select_experiment_2d / _render_2d_png / _plot_hmbc_overlay / _apply_nmr_axes_2d) via a specific-name import inside the same try/except ImportError guard used for the fastapi [webview] extra, so absence of the not-yet-implemented 2D routes produces a clean SKIP rather than a 404-driven assertion FAILURE"
  - "HMBC flag-palette assertion (SC2) inspects both inspect.getsource(_plot_hmbc_overlay) and an optional module-level _HMBC_FLAG_COLORS dict repr, since Plan 02 may implement either shape"
  - "Cache-hit-no-rerender test assumes the render helper is named _render_2d_png (per 96-RESEARCH.md's verified interface/System-Architecture-Diagram naming) and monkeypatches it directly"
metrics:
  duration_minutes: 35
  completed: 2026-07-11
  tasks_completed: 2
  tasks_total: 2
  files_changed: 1
---

# Phase 96 Plan 01: 2D Real Spectra + Peak Overlay — Wave-0 Test Scaffold Summary

**One-liner:** Froze the executable contract for the 2D spectra routes (three PNG
endpoints, reversed-axis + HMBC-palette + cache behaviour) as a 13-method RED-by-skip
pytest scaffold plus hand-authored HSQC/HMBC/COSY peak-overlay fixtures, so Plan 02 is
written against a fixed target with zero field/behaviour drift.

## What Was Built

Two atomic commits against `tests/test_webview_api.py`, adding **zero new source
files** — this is a pure test/fixture scaffold, no implementation code:

1. **`spectra_case1_manifest_dir_2d` fixture** — writes a `.run_manifest.json` pointing
   at the real local CASE1 dataset (`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/CASE1`,
   which contains real HSQC/exp-6, HMBC/exp-7, COSY/exp-5 2D experiments) plus
   hand-authored `analysis/peaks/{hsqc,hmbc,cosy}.json` to the LOCKED Phase-94 schema.
   The `hmbc.json` fixture includes one row for each of the three flag values
   (`ok`, `potential_4J`, `1J_artifact`). Skips (not fails) when the local CASE1
   path is absent on the running machine.

2. **`TestSpectraEndpoint2D`** — 13 test methods covering all 9 rows of the
   96-VALIDATION.md/96-RESEARCH.md Wave-0 test map:
   - `test_spectra_2d_apply_nmr_axes_2d_reverses_both_scales` (SC1 — both-axes-reversed contract, no real data)
   - `test_spectra_2d_{hsqc,hmbc,cosy}_returns_png_on_case1_real` (SP2-01 happy path, 3 methods)
   - `test_spectra_2d_hmbc_flag_color_palette` (SC2 — LOCKED hex palette `#28a745`/`#ffc107`/`#adb5bd`)
   - `test_spectra_2d_select_experiment_2d_keeps_only_acqu2s` (2D experiment selection, spy-based acqu2s-exclusion proof, mirrors the 1D `test_select_experiment_excludes_2d_and_dept` pattern)
   - `test_spectra_2d_render_under_budget` (SC3 perf, < 1.0s)
   - `test_spectra_2d_cache_hit_no_rerender` (SC3 cache, monkeypatch-spy on `_render_2d_png`, asserts exactly one call across two unchanged-mtime requests)
   - `test_spectra_2d_cache_bounded` (SC4, `len(_png_cache) <= 3` after repeated polling across all three routes)
   - `test_spectra_2d_missing_manifest_placeholder` / `test_spectra_2d_stale_path_placeholder` / `test_spectra_2d_no_matching_experiment_placeholder` (SP-02 never-500, 3 methods)
   - `test_spectra_2d_no_module_level_matplotlib_import` (WV-08 standing guard; this one already PASSES since it only source-scans the existing Phase-95 file)

## Key Design Decision: the Skip Probe

The plan's core acceptance bar was "collects cleanly and SKIPS (not ERROR) for every
2D-router-dependent method before the 2D routes exist." Simply mirroring the Phase-95
WV-08 pattern verbatim (`from lucy_ng.webview.routers import spectra` inside
`try/except ImportError`) would NOT skip today, because `lucy_ng.webview.routers.spectra`
**already exists** (Phase 95 shipped it) — only the 2D-specific symbols and routes are
missing. A bare `spectra.make_router(...)` call succeeds; the failure would surface as
an HTTP 404 on `GET /api/spectra/2d/hsqc`, which is an assertion **FAILURE**, not a skip.

Fix: every 2D-route-dependent method also does a **specific-name import** of a
Plan-02-only symbol (e.g. `from lucy_ng.webview.routers.spectra import
_select_experiment_2d`) inside the same `try/except ImportError` block, before calling
`make_router()`. `from module import name` raises `ImportError` (not `AttributeError`)
when `name` doesn't exist in an already-imported module, so this correctly triggers the
skip today and will naturally stop skipping once Plan 02 defines those symbols — with no
test-code changes required at that point.

## Verification

```
pytest tests/test_webview_api.py::TestSpectraEndpoint2D -q
  -> 1 passed, 12 skipped, 0 failed/errored

pytest tests/test_webview_api.py -q
  -> 48 passed, 12 skipped, 0 failed/errored (existing suite unbroken)

ruff check tests/test_webview_api.py
  -> All checks passed!
```

All required `-k` sub-selectors confirmed to match >=1 test each: `spectra_2d`,
`"spectra_2d and real"`, `apply_nmr_axes_2d`, `hmbc_flag_color`, `render_under_budget`,
`cache_hit_no_rerender`, `cache_bounded`, `"spectra_2d and placeholder"`.

## Deviations from Plan

None — plan executed exactly as written. The `test_spectra_2d_no_module_level_matplotlib_import`
method mentioned as optional ("if a dedicated 2D assertion is desired") in Task 2's
action text was added, since it is a zero-cost standing guard consistent with the
existing 1D precedent.

## Known Assumptions Carried Into Plan 02

- `_render_2d_png` is assumed to be the render-function name that `_cached_or_render`
  invokes (per 96-RESEARCH.md's System Architecture Diagram and interfaces block).
  `test_spectra_2d_cache_hit_no_rerender` monkeypatches this exact name. If Plan 02
  names it differently, that one test will need a matching rename (not a redesign).
- `_HMBC_FLAG_COLORS` is checked as an *optional* module-level dict in addition to
  scanning `_plot_hmbc_overlay`'s source — either shape satisfies the SC2 assertion.

## Self-Check: PASSED

- `tests/test_webview_api.py` contains `class TestSpectraEndpoint2D` — FOUND
- Commit `1730369` (Task 1, fixture) — FOUND in `git log --oneline`
- Commit `2a7a9f6` (Task 2, test class) — FOUND in `git log --oneline`
