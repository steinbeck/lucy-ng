---
phase: 95-1d-real-spectra-peak-overlay
plan: 01
subsystem: testing
tags: [fastapi, matplotlib, pytest, webview, bruker, nmrglue]

# Dependency graph
requires:
  - phase: 94-data-tables
    provides: TestTablesEndpoint pattern (make_router(analysis_dir), never-500 JSON idiom,
      hand-authored fixture style) mirrored here for the binary/PNG analog
provides:
  - matplotlib>=3.7 declared in the [webview] optional-dependency extra only (D-04)
  - Frozen executable contract for Plan 02's spectra.py router: endpoint shapes
    (/api/spectra/1d/carbon, /api/spectra/1d/proton), helper signatures
    (_read_manifest, _select_experiment, _apply_nmr_axes), and the two
    RESEARCH-verified discriminators (set_xlim-only reversal, acqu2s/dept
    exclusion) as a RED-by-skip test scaffold
affects: [95-02-PLAN, 96 (2D spectra reuses _apply_nmr_axes + the same manifest contract)]

# Tech tracking
tech-stack:
  added: [matplotlib>=3.7 (webview extra only)]
  patterns:
    - "PNG endpoint never-500 contract (binary analog of tables.py's {state} JSON idiom):
      every failure path returns valid image/png bytes, HTTP 200, never a JSON body"
    - "WV-08 lazy-import discipline extended to matplotlib: imports live inside
      make_router()/request handlers only, verified by a structural (source-grep)
      unit test rather than at collection time"

key-files:
  created: []
  modified:
    - pyproject.toml
    - tests/test_webview_api.py

key-decisions:
  - "matplotlib>=3.7 added to [project.optional-dependencies].webview only — base deps
    and dev extra remain untouched (D-04), verified by a tomllib guard script"
  - "Peak-overlay test asserts a PNG byte-delta between an overlay render and a bare-trace
    render (unit-level) rather than spying on an unstated internal helper name — keeps the
    test implementation-agnostic to Plan 02's exact function decomposition"
  - "2D/DEPT exclusion test uses a BrukerReader.read_1d monkeypatch spy to prove the
    acqu2s-bearing directory is never opened, rather than asserting on speculative metadata
    fields not yet defined by any interface contract"
  - "Wrapped one pre-existing long assertion line in TestStructuresEndpoint (outside this
    plan's scope) so `ruff check tests/test_webview_api.py` — the plan's own verify command
    — passes cleanly; a one-line incidental fix in a file this task already edits"

patterns-established:
  - "Pattern: PNG endpoint never-500 — spectra.py's future implementation must return
    Response(content=png_bytes, media_type='image/png') on every code path, verified here
    by 6 independent test methods across absent-manifest/stale-path/missing-peaks/proton-vs-carbon"

requirements-completed: [SP1-01, SP-02]

# Metrics
duration: 12min
completed: 2026-07-09
---

# Phase 95 Plan 01: Wave-0 Test Scaffold (matplotlib extra + TestSpectraEndpoint) Summary

**matplotlib added to the `[webview]` extra only, plus an 11-method `TestSpectraEndpoint` RED-by-skip scaffold that freezes the `spectra.py` router contract (reversed-axis, 2D/DEPT exclusion, peak overlay, never-500) ahead of Plan 02's implementation.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-09T13:14:02Z
- **Completed:** 2026-07-09T13:25:56Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- `matplotlib>=3.7` declared in `[project.optional-dependencies].webview` only, verified by a `tomllib`-based guard that base `[project].dependencies` contains no matplotlib entry (D-04)
- 3 new module-level pytest fixtures: `spectra_stale_manifest_dir` (D-05 stale-path case), `spectra_case1_manifest_dir` (real CASE1 dataset, skip-guarded, hand-authored `carbon_signals.json` including a ~181 ppm `C=O` signal), `synthetic_bruker_dir` (fake acqus/acqu2s tree, no real FID needed)
- `TestSpectraEndpoint` (11 methods) covering: SC2 reversed-axis unit assertion (`ax.get_xlim()[0] > ax.get_xlim()[1]`), the real-CASE1 carbonyl-left-of-aliphatic check, 2D/DEPT experiment-exclusion (via a `BrukerReader.read_1d` monkeypatch spy proving the `acqu2s` dir is never opened), per-nucleus independent PNG rendering, peak-overlay byte-delta, three SP-02 never-500 paths (absent manifest / stale bruker path / missing peaks JSON), the WV-08 module-level-matplotlib-import structural guard, and the standing SC3 `from lucy_ng.cli import cli` guard
- All 10 spectra-router-dependent methods collect and SKIP cleanly (spectra.py does not exist until Plan 02); `test_cli_imports_without_matplotlib` PASSES immediately as a standing guard
- Full test suite unaffected: 1176 passed, 25 skipped, 1 xfailed (no new failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add matplotlib to the [webview] optional-dependency extra** - `ce36945` (feat)
2. **Task 2: Add TestSpectraEndpoint + spectra fixtures (RED-by-skip until spectra.py exists)** - `a553b43` (test)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `pyproject.toml` - Added `"matplotlib>=3.7"` as a third entry in `[project.optional-dependencies].webview`; base `[project].dependencies` unchanged
- `tests/test_webview_api.py` - Added `CASE1_ROOT` constant, 3 fixtures, `TestSpectraEndpoint` (11 methods); wrapped one pre-existing long line in `TestStructuresEndpoint` to keep the file's ruff check clean

## Decisions Made
- matplotlib is webview-extra-only (D-04), enforced by both the `pyproject.toml` placement and a `tomllib` guard script run during verification
- Test for peak overlay uses a PNG byte-delta comparison (implementation-agnostic) rather than spying on an unstated Plan-02 internal function name
- Test for 2D/DEPT exclusion uses a `BrukerReader.read_1d` monkeypatch spy to prove the acqu2s directory is never opened, rather than asserting on speculative metadata fields
- Fixed one pre-existing E501 in `TestStructuresEndpoint` (unrelated to this plan's scope) because it blocked the plan's own `ruff check tests/test_webview_api.py` verify command in a file this task already touches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wrapped a pre-existing long assertion line to unblock the plan's ruff verify command**
- **Found during:** Task 2 verification (`ruff check tests/test_webview_api.py`)
- **Issue:** `TestStructuresEndpoint::test_malformed_smiles_returns_placeholder` (Phase 91, unrelated to this plan) had a 106-character assertion line that failed `ruff check tests/test_webview_api.py` — the plan's own literal acceptance criterion for this file
- **Fix:** Wrapped the single assertion across three lines (no logic change)
- **Files modified:** tests/test_webview_api.py (line ~293)
- **Verification:** `ruff check tests/test_webview_api.py` → "All checks passed!"; full test suite still 1176 passed/25 skipped/1 xfailed
- **Committed in:** `a553b43` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Trivial one-line formatting fix in a file already under edit; no behavior change, no scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. matplotlib installs via the existing `pip install "lucy-ng[webview]"` path; already present in this dev environment (3.10.7).

## Next Phase Readiness
- `spectra.py`'s exact contract is now frozen as an executable test target: `make_router(analysis_dir)`, `_read_manifest`, `_select_experiment(bruker_data_dir, nucleus)`, `_apply_nmr_axes(ax, ppm_scale)`, and the `/api/spectra/1d/{carbon,proton}` PNG routes
- Plan 02 can implement `spectra.py` against this scaffold with zero field/behaviour drift; running `pytest tests/test_webview_api.py::TestSpectraEndpoint -q` will flip SKIPPED → PASSED method-by-method as the router lands
- No blockers. The real CASE1 dataset (`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/CASE1`) is present on this machine, so the CASE1-dependent tests will exercise real data (not just synthetic fixtures) once Plan 02 ships

---
*Phase: 95-1d-real-spectra-peak-overlay*
*Completed: 2026-07-09*
