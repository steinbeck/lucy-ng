---
phase: 99-peak-pick-bridge-qc-gate-cli
plan: 01
subsystem: testing
tags: [pydantic, qc-gate, nus, peak-picking, fixtures, tdd-scaffold]

# Dependency graph
requires:
  - phase: 98-reconstruction-processing
    provides: NusReconstructionResult model convention (to_dict/from_dict/summary), GUIDE_S10_C13 20-shift ground-truth list, tests/nus/conftest.py mock seam
provides:
  - QcVerdict/QcCheckResult/QcReport Pydantic v2 models in models/nus.py (the shared QC data contract)
  - Committed known-bad (QC-02 FAIL side) + hand-authored synthetic-clean (QC-02 PASS side) peak-list fixtures
  - Six RED-by-skip stub test files covering QC-01/QC-02/QC-03/PICK-01/PICK-02/PICK-03
  - known_bad_peaks_dir/clean_peaks_dir conftest fixtures + KNOWN_QUATERNARY_SHIFTS constant
affects: [99-02-qc-checks, 99-03-bridge, 99-04-cli-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "str-Enum QcVerdict JSON-serializes to plain string (T-99-02 mitigation)"
    - "@pytest.mark.skip RED-by-skip convention (Phase 98's established pattern): real imports live inside skipped test bodies, never at module top-level, so tests/nus/ stays collectable before the implementing modules exist"

key-files:
  created:
    - src/lucy_ng/models/nus.py (QcVerdict/QcCheckResult/QcReport, additive)
    - tests/fixtures/nus/known_bad_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2,13C_exp7_wide,13C_exp6_narrow,1H_exp1}.json
    - tests/fixtures/nus/clean_peaks_synthetic/{HSQC_exp3,HMBC_exp4,COSY_exp2,13C_exp7_wide,1H_exp1}.json
    - tests/nus/test_qc_checks.py
    - tests/nus/test_qc_regression.py
    - tests/nus/test_bridge.py
    - tests/nus/test_bridge_metadata.py
    - tests/nus/test_write_boundary.py
    - tests/nus/test_cli_pipeline.py
  modified:
    - tests/nus/conftest.py (added known_bad_peaks_dir/clean_peaks_dir fixtures + KNOWN_QUATERNARY_SHIFTS)

key-decisions:
  - "QcReport models mirror NusReconstructionResult's exact convention (ConfigDict, to_dict/from_dict, summary()) plus two convenience methods (violated_checks/critical_violations) anticipating D-02's critical/soft aggregation"
  - "Adopted Phase-98's @pytest.mark.skip stub convention (imports inside skipped bodies) instead of module-level pytest.importorskip, after discovering importorskip collapses each stub file into a single collection-time skip rather than collecting each test individually"

requirements-completed: [QC-01, QC-02, PICK-03]

# Metrics
duration: 17min
completed: 2026-07-16
---

# Phase 99 Plan 01: Nyquist Wave 0 Scaffold Summary

**QcVerdict/QcCheckResult/QcReport Pydantic contract + committed known-bad/synthetic-clean peak-list fixture pair + six RED-by-skip stub test files, unblocking parallel Plans 02-04**

## Performance

- **Duration:** 17 min
- **Started:** 2026-07-16T18:31:43+02:00
- **Completed:** 2026-07-16T18:48:11+02:00
- **Tasks:** 3
- **Files modified:** 18 (1 model file, 11 fixture JSON files, 6 test files including conftest.py)

## Accomplishments
- Added `QcVerdict`/`QcCheckResult`/`QcReport` to `models/nus.py` — the shared data contract Plans 02-04 all implement against — JSON-round-trips cleanly (`verdict` serializes to plain `"PASS"`, never `"QcVerdict.PASS"`), mypy-clean, byte-unchanged existing classes.
- Committed the real known-bad home-IST HSQC/HMBC/COSY + trusted-1D peak lists (verbatim, byte-identical to the on-disk C20H32O2 originals) as the QC-02 FAIL-side regression floor.
- Hand-authored a synthetic clean HSQC/HMBC/COSY + 1D-reference fixture set satisfying §8 exactly (zero HSQC hits at the 5 quaternary shifts, self-consistent edited signs, diagonal-symmetric COSY, no single-axis ridge) — the load-bearing QC-02 PASS-side proof, since no real clean C20H32O2 reconstruction exists until Phase 100.
- Wrote six RED-by-skip stub test files (24 tests) covering every downstream Phase-99 behavior, following the exact `@pytest.mark.skip` convention Phase 98 Plan 01 established.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add QcVerdict/QcCheckResult/QcReport models** - `842efb8` (feat)
2. **Task 2: Commit known-bad + synthetic-clean fixtures** - `04d7377` (test)
3. **Task 3: Extend conftest + write six RED-by-skip stub files** - `941e4c7` (test)

**Follow-up fixup:** `5e7967b` (style — ruff import-sort auto-fix on Task 3 files, no behavioral change)

_Note: This is not a TDD plan — commit types follow the standard feat/test convention, not RED/GREEN/REFACTOR gates._

## Files Created/Modified
- `src/lucy_ng/models/nus.py` - Added QcVerdict (str-Enum PASS/PARTIAL/FAIL), QcCheckResult, QcReport (to_dict/from_dict/summary/violated_checks/critical_violations)
- `tests/fixtures/nus/known_bad_peaks/*.json` (6 files) - Verbatim copies of the real home-IST peak lists (QC-02 FAIL side)
- `tests/fixtures/nus/clean_peaks_synthetic/*.json` (5 files) - Hand-authored §8-compliant clean peak lists (QC-02 PASS side)
- `tests/nus/conftest.py` - Added `known_bad_peaks_dir`/`clean_peaks_dir` fixtures + `KNOWN_QUATERNARY_SHIFTS` constant
- `tests/nus/test_qc_checks.py` - 6 check classes x 2 tests each (clean-pass + violation-trip), QC-01
- `tests/nus/test_qc_regression.py` - FAIL/PASS discrimination anchor, QC-02
- `tests/nus/test_bridge.py` - Spectrum2D construction + peak-pick schema, PICK-01
- `tests/nus/test_bridge_metadata.py` - D-05 metadata block + D-06 confidence mapping, PICK-03
- `tests/nus/test_write_boundary.py` - D-07 write/quarantine boundary, QC-03
- `tests/nus/test_cli_pipeline.py` - `qc`/`pipeline` CLI surface, PICK-02/D-08

## Decisions Made
- Mirrored `NusReconstructionResult`'s exact Pydantic convention for the new QC models rather than inventing a new shape — keeps the whole `models/nus.py` module internally consistent.
- Added `violated_checks()`/`critical_violations()` convenience methods to `QcReport` beyond the plan's literal spec, anticipating D-02's critical/soft aggregation logic Plan 02 will implement — these are pure accessors over already-required fields, no new state, low-risk forward-compatibility addition.
- Synthetic-clean HSQC gives two carbons (67.06, 51.63) two diastereotopic peaks each (with identical `multiplicity_hint` per carbon) rather than a strict one-peak-per-carbon list — this exercises the edited-sign self-consistency check's clean-pass path more realistically than a maximally trivial fixture would.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RED-by-skip stub tests used `pytest.importorskip` at module level, which collapses per-test collection into a single per-file skip**
- **Found during:** Task 3 (verification step — `pytest tests/nus/ --collect-only -q` showed 26 collected / 6 skipped instead of 26+24=50 collected)
- **Issue:** The plan's action text said "each test skips RED-by-skip using `pytest.importorskip(...)` at the top" — but `importorskip` at module scope raises during collection when the target module doesn't exist, so pytest marks the *entire file* as one skip rather than collecting each test function individually. This diverges from Phase 98 Plan 01's actual established convention (verified via `git show` on the original `1fca61a` commit) and from this plan's own acceptance criterion of collecting all new tests individually.
- **Fix:** Rewrote all six stub files to use `@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan N")` per-test-function decorators, with the real `from lucy_ng.nus.X import Y` imports placed inside each (never-executed) test body — the exact pattern Phase 98's `test_reconstruct_orchestration.py` used.
- **Files modified:** tests/nus/test_qc_checks.py, tests/nus/test_qc_regression.py, tests/nus/test_bridge.py, tests/nus/test_bridge_metadata.py, tests/nus/test_write_boundary.py, tests/nus/test_cli_pipeline.py
- **Verification:** `pytest tests/nus/ --collect-only -q` now reports 50 collected (26 existing + 24 new); running the six new files directly reports "24 skipped" with 0 passed/failed/errors.
- **Committed in:** 941e4c7 (Task 3 commit — this was fixed inline before the task's single commit, not a separate commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix — corrected the RED-by-skip mechanism to match the established project convention)
**Impact on plan:** Necessary correctness fix; the plan's own acceptance criteria (individual test collection) could not otherwise be satisfied. No scope creep — same six files, same test coverage, corrected mechanism only.

## Issues Encountered
- `mypy src/lucy_ng/models/nus.py` reports 42 pre-existing errors from unrelated files (`lsd/parser.py`, `prediction/hose.py`, `dereplication/*.py`, etc.) because mypy follows imports transitively from the single target file — confirmed this is pre-existing repo-wide tech debt (same behavior reproduced on `nus/postprocess.py` as a baseline), not caused by this plan's changes. `models/nus.py` itself has zero mypy errors.
- `ruff check` flagged 5 I001 (unsorted import block) warnings across the new Task 3 test files (imports split across two `from` lines instead of one sorted block) — auto-fixed via `ruff check --fix`, verified tests still pass after the fix, committed separately as `5e7967b`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plans 02 (`nus/qc.py` — the six check functions + `run_qc_checks()`), 03 (`nus/bridge.py`), and 04 (`cli/nus.py::qc`/`pipeline`) can now proceed against a fixed `QcReport` data contract and a committed FAIL/PASS regression floor.
- All 24 new stub tests currently skip; they will activate automatically once the corresponding modules exist (Plan 02 turns `test_qc_checks.py`/`test_qc_regression.py` GREEN by removing the skip decorators and implementing `lucy_ng.nus.qc`).
- Full test suite green: 1329 passed, 32 skipped, 1 xfailed, zero regressions from this plan's additions.
- No blockers or concerns for downstream plans.

---
*Phase: 99-peak-pick-bridge-qc-gate-cli*
*Completed: 2026-07-16*

## Self-Check: PASSED

All 18 created/modified files verified present on disk; all 4 task/fixup commit hashes (842efb8, 04d7377, 941e4c7, 5e7967b) verified present in git log.
