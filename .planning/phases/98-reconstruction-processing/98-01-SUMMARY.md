---
phase: 98-reconstruction-processing
plan: 01
subsystem: testing
tags: [nus, pytest, test-scaffold, red-by-skip, subprocess-mock, nmrpipe, smile]

# Dependency graph
requires:
  - phase: 97-backend-integration
    provides: "NusAcquisitionParams/NusSchedule models, read_nus_params/read_nus_schedule, NmrPipeSmileBackend detection, tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc}"
provides:
  - "Collectable tests/nus/ package (importable on a machine with no NMRPipe)"
  - "Shared conftest.py: run_stage mock seam (mock_run_stage) + mock_subprocess_run + valid/empty/truncated fake-intermediate factories + nus_fixture_dir accessor"
  - "One RED-by-skip stub file per RECON requirement (RECON-01..05) with docstring RED contracts"
  - "Skipif-guarded Manual-Only end-to-end integration test stub (external-data gated, D-04)"
affects: [98-02, 98-03, 98-04, 98-05, 98-06, 99-peak-pick-qc]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RED-by-skip Wave 0 scaffold: every later plan turns a named, pre-existing skipped test GREEN rather than inventing coverage after the fact"
    - "Collection-safe deferred imports: no top-level import of not-yet-existing lucy_ng.nus.runner/postprocess; all lucy_ng.nus.* imports deferred into test/fixture bodies; monkeypatch by string target with raising=False"
    - "D-04 mocked subprocess boundary: run_stage mock seam + fake valid/empty/truncated NMRPipe-intermediate factories; real chain is a separate skipif backend/data-gated test with no ser binary committed"

key-files:
  created:
    - "tests/nus/__init__.py"
    - "tests/nus/conftest.py"
    - "tests/nus/test_runner_faillloud.py"
    - "tests/nus/test_fnmode_branching.py"
    - "tests/nus/test_reconstruct_chain.py"
    - "tests/nus/test_processing_order.py"
    - "tests/nus/test_reconstruct_orchestration.py"
    - "tests/nus/test_cli_reconstruct.py"
    - "tests/nus/test_reconstruct_integration.py"
  modified: []

key-decisions:
  - "conftest.py imports nothing from lucy_ng.nus.runner/postprocess at module level — those modules ship in Plans 02-05; importing them at collection time would break the whole tests/nus/ tree on a machine without them"
  - "mock_run_stage monkeypatches lucy_ng.nus.runner.run_stage by STRING target with raising=False so the fixture is safe both before and after that module exists"
  - "The integration test uses @pytest.mark.skipif (not plain skip) gated on NmrPipeSmileBackend.is_available() AND the external LUCY_NUS_TEST_DATA path existing — it SKIPS (not fails) in CI, which is correct per D-04"
  - "No ser binary committed to the repo — the real end-to-end chain is validated via external-path integration only (closes Phase-97 D-03-deferred ser-fixture decision)"

patterns-established:
  - "RED contract in docstrings: each stub function docstring states the exact behavior its implementing plan must satisfy + names that plan (Plan NN)"
  - "Fake-intermediate factory trio (valid / empty / truncated-all-zero) maps 1:1 to run_stage's three fail-loud checks (exit code, non-emptiness, non-all-zero data)"

requirements-completed: [RECON-01, RECON-02, RECON-03, RECON-04, RECON-05]

# Metrics
duration: 18min
completed: 2026-07-13
---

# Phase 98 Plan 01: Nyquist Wave 0 Test Scaffolding Summary

**A collectable `tests/nus/` package with a subprocess-mock-seam conftest and one RED-by-skip stub per RECON requirement — the coverage contract every later Phase-98 plan turns from skipped to green, with the real NMRPipe+SMILE chain isolated behind a single skipif-guarded external-data integration test.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-07-13T11:38Z
- **Completed:** 2026-07-13
- **Tasks:** 2 completed
- **Files created:** 9

## Accomplishments

- Created `tests/nus/` as a collectable package that imports cleanly on a machine with no NMRPipe installed (verified: 24 tests collected, zero import/collection errors).
- Authored `conftest.py` with the six shared fixtures the entire phase depends on — the `run_stage` mock seam (`mock_run_stage`), the `subprocess.run` recorder (`mock_subprocess_run`), the three fake-intermediate factories (valid / empty / truncated-all-zero), and the pure-pathlib `nus_fixture_dir` accessor — none of which import a not-yet-existing Phase-98 module at collection time.
- Laid down 7 stub files (24 tests) covering RECON-01..05, each function docstring-specifying the exact RED contract its implementing plan must satisfy, so Plans 02-06 flip named skipped tests to green rather than inventing coverage retroactively.
- Isolated the real backend chain into one `@pytest.mark.skipif`-guarded Manual-Only integration test that SKIPS (not fails) without NMRPipe + external data — no `ser` binary committed to the repo (D-04).

## Task Commits

Each task was committed atomically:

1. **Task 1: tests/nus package + conftest.py shared fixtures** - `683d83b` (test)
2. **Task 2: one RED-by-skip stub file per RECON requirement** - `1fca61a` (test)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `tests/nus/__init__.py` - Package marker so the subdir is importable (mirrors `tests/__init__.py`).
- `tests/nus/conftest.py` - Shared fixtures: `nus_fixture_dir`, `make_valid_intermediate`, `make_empty_intermediate`, `make_truncated_intermediate`, `mock_run_stage`, `mock_subprocess_run`. No top-level `lucy_ng.nus.runner`/`postprocess` import.
- `tests/nus/test_runner_faillloud.py` - RECON-04: `run_stage` fail-loud (nonzero exit / empty / truncated-all-zero raise; valid passes).
- `tests/nus/test_fnmode_branching.py` - RECON-03: `_ordering_for_fnmode` (FnMODE 6 → expand_first, FnMODE 1 → convert_first, unknown → NotImplementedError).
- `tests/nus/test_reconstruct_chain.py` - RECON-01/02/03: `convert()` FnMODE-branched dispatch order, `nus_td` (not `f1_td`) grid size, exact non-integer GRPDLY, SMILE default knobs, and SMILE's input being the F2-processed (not raw-converted) FID.
- `tests/nus/test_processing_order.py` - RECON-02: `process_direct` F2 chain → TP → SMILE input, deterministic phase constants, magnitude branch skips phase, reversed + 1D-calibrated ppm axes.
- `tests/nus/test_reconstruct_orchestration.py` - RECON-01/02: F2-before-F1 gate raises before any subprocess, whole-pipeline convert→direct→SMILE→indirect sequencing, result object with stage paths.
- `tests/nus/test_cli_reconstruct.py` - RECON-05: `lucy nus reconstruct --help` lists knob flags; flags thread through to SMILE argv.
- `tests/nus/test_reconstruct_integration.py` - Manual-Only: single `@pytest.mark.skipif`-guarded external-data end-to-end test (backend + `LUCY_NUS_TEST_DATA` present).

## Verification

- `pytest tests/nus/ -q --co` → 24 tests collected, zero import errors.
- `pytest tests/nus/ -q --no-header` → 24 skipped, 0 failed, 0 errors, exit 0.
- Acceptance checks passed: all six named conftest fixtures present; `grep -c 'import lucy_ng.nus.runner'` on non-comment lines = 0; both new `.py` files `ast.parse` clean; all required test names present in `--collect-only`; integration test matches `grep -l skipif`.

_Note: the full `pytest -q` regression run was intentionally NOT executed to completion here — headless orchestration must not background-and-wait. This plan adds only skipped test stubs + a collection-safe conftest, so it cannot affect the existing suite's pass/fail (the new tests are all `skip`/`skipif`, and no production code changed). The full-suite gate belongs to `/gsd-verify-work` per 98-VALIDATION.md._

## Deviations from Plan

None - plan executed exactly as written. Both tasks' acceptance criteria met verbatim.

## Known Stubs

All 24 tests in `tests/nus/` are intentional RED-by-skip stubs (`@pytest.mark.skip`) or the one skipif-guarded integration test — this is the plan's entire purpose (Wave 0 coverage contract). Each becomes GREEN in its named implementing plan:

- RECON-04 → Plan 02 (`run_stage`)
- RECON-03 → Plan 02 (`_ordering_for_fnmode`)
- RECON-01/02/03 → Plan 03 (`convert()`/`reconstruct_indirect()`)
- RECON-02 → Plan 04 (`postprocess.py`)
- RECON-01/02 → Plan 05 (`NusRunner.reconstruct` + integration)
- RECON-05 → Plan 06 (`cli/nus.py::reconstruct`)

These stubs are the intended, documented deliverable, not incomplete work — the requirements are marked complete for the Wave-0 scaffolding contract they fulfill (every RECON requirement now has a named, pre-existing, docstring-specified test).

## Self-Check: PASSED
