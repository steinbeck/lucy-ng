---
phase: 99-peak-pick-bridge-qc-gate-cli
plan: 02
subsystem: nus
tags: [qc-gate, nus, peak-picking, quality-control, pydantic]

# Dependency graph
requires:
  - phase: 99-peak-pick-bridge-qc-gate-cli
    provides: "Plan 01's QcVerdict/QcCheckResult/QcReport Pydantic contract, known-bad/synthetic-clean peak-list fixture pair, six RED-by-skip stub test files"
provides:
  - "src/lucy_ng/nus/qc.py: the complete headless QC-01/QC-02 gate (six check functions, QcConfig, QcReferenceData, aggregate_verdict(), run_qc_checks())"
  - "QC-01 satisfied: six named checks (quaternary_exclusion, ppm_calibration, signal_to_ridge, hsqc_coverage critical; edited_sign_consistency, cosy_diagonal_symmetry soft) computing the documented algorithms against peak-list dicts only"
  - "QC-02 discrimination floor proven: run_qc_checks() on the known-bad home-IST fixture verdicts FAIL, on the synthetic-clean fixture verdicts PASS"
affects: [99-03-bridge, 99-04-cli-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Honest three-tier D-03 reference resolution (DEPT -> explicit override -> insufficient_reference_data) -- tier-3 returns passed=False with an explicit detail string, never a silent PASS on missing reference data"
    - "Dual API surface per check: an internal check_*(peaks, ref, config) form used by run_qc_checks(), plus a short-named standalone wrapper (e.g. quaternary_exclusion(peaks, known_shifts, tol)) matching the Plan 01 test-stub's direct-call contract"
    - "Keyword-based case-insensitive substring glob (_glob_by_keyword) instead of Path.glob(\"*KEYWORD*\") -- avoids double-matching on case-insensitive filesystems (macOS/APFS) while never hardcoding an _expN suffix"
    - "Reuse-not-reimplement: qc_check_ppm_calibration wraps nus/postprocess.py::check_calibration()/GUIDE_S10_C13 directly"

key-files:
  created:
    - src/lucy_ng/nus/qc.py
  modified:
    - tests/nus/test_qc_checks.py (Wave-0 skip decorators removed, all 12 tests active)
    - tests/nus/test_qc_regression.py (Wave-0 skip decorators removed, both tests active)

key-decisions:
  - "hsqc_coverage's protonated-carbon reference is derived from the actual trusted 1D files read from <peaks-dir> (deduplicated via _dedupe_shifts, filtered against ref.quaternary_shifts), falling back to the hardcoded PROTONATED_REFERENCE only when no 1D file exists at all -- D-03 compliant (no re-derivation from the guide as the normal path)"
  - "Any per-file JSON load error in run_qc_checks() unconditionally blocks a PASS verdict (bumped to FAIL), not just errors touching a specific critical experiment -- simpler and more conservative than partial detection, matching T-99-01's 'never silently PASS on malformed input'"
  - "signal_to_ridge (critical) evaluates ridge_fraction() across all six relevant axes (COSY h1a/h1b, HSQC c13/h1, HMBC c13/h1) and takes the worst, rather than only the axis the caller happened to pass -- catches ridges in any experiment type, not just COSY"

requirements-completed: [QC-01, QC-02]

# Metrics
duration: 19min
completed: 2026-07-16
---

# Phase 99 Plan 02: QC Gate Check Functions + Verdict Aggregation Summary

**`nus/qc.py`: six headless QC checks (quaternary-exclusion/ppm-calibration/signal-to-ridge/HSQC-coverage critical, edited-sign/COSY-symmetry soft), D-02 aggregate_verdict(), and run_qc_checks() proving the known-bad-FAILs/synthetic-clean-PASSes QC-02 discrimination floor**

## Performance

- **Duration:** 19 min
- **Started:** 2026-07-16T18:54:00+02:00 (immediately after Plan 01 close)
- **Completed:** 2026-07-16T19:13:34+02:00
- **Tasks:** 2
- **Files modified:** 3 (1 new module, 2 test files un-skipped)

## Accomplishments
- Built the complete `nus/qc.py` module: `QcConfig` (D-04 centralized, CLI-overridable thresholds), `QcReferenceData.resolve()` (D-03's honest three-tier DEPT/explicit-override/insufficient-reference-data resolution, deliberately never calling `detection.detect_hybridisation()` per RESEARCH.md Pitfall 1), `ridge_fraction()` (the genuinely-new peak-list-only t1-ridge metric), and all six named checks.
- Wired `aggregate_verdict()` (D-02's single auditable critical/soft aggregation) and `run_qc_checks(peaks_dir)` (keyword-based HSQC/HMBC/COSY glob, trusted-1D cross-reference, fail-loud per-file JSON parsing) into a complete `QcReport`.
- Proved the QC-02 regression floor directly against the real fixtures: `run_qc_checks()` on the known-bad home-IST HSQC/HMBC/COSY lists verdicts `FAIL` (quaternary_exclusion, hsqc_coverage, and signal_to_ridge all trip critical); on the hand-authored synthetic-clean fixture it verdicts `PASS` with zero violated checks.
- Activated all 14 of Plan 01's RED-by-skip stub tests (`test_qc_checks.py` 12, `test_qc_regression.py` 2) by removing the skip decorators — no test bodies needed rewriting, confirming the Plan 01 stub contract was implementable as specified.

## Task Commits

Each task was committed atomically:

1. **Task 1: QcConfig + QcReferenceData + the six check functions** - `c319a3f` (feat)
2. **Task 2: aggregate_verdict() + run_qc_checks(peaks_dir) orchestration + QC-02 discrimination** - `9d757e8` (feat)

_Note: Tasks were tagged `tdd="true"` in the plan, but the underlying tests already existed (RED-by-skip) from Plan 01 — this plan's job was to make them GREEN by implementing the module, not to write new tests first. Following the established project convention from Phase 98 (STATE.md), this shipped as two standard `feat` commits rather than split RED/GREEN/REFACTOR commits._

## Files Created/Modified
- `src/lucy_ng/nus/qc.py` - The complete QC-01/QC-02 gate: `QcConfig`, `QcReferenceData`, `ridge_fraction()`, six `check_*()` functions (+ short-named standalone wrappers), `aggregate_verdict()`, `run_qc_checks()`
- `tests/nus/test_qc_checks.py` - Removed Wave-0 `@pytest.mark.skip` decorators; all 12 tests now active and green
- `tests/nus/test_qc_regression.py` - Removed Wave-0 `@pytest.mark.skip` decorators; both QC-02 discrimination tests now active and green

## Decisions Made
- **hsqc_coverage's protonated reference derivation**: rather than either (a) using the compound-specific hardcoded `GUIDE_S10_C13`-derived `PROTONATED_REFERENCE` list unconditionally (violates D-03's "read the actual 1D files, no second source of truth"), or (b) using the raw noisy 1D peak-picker output as-is (RESEARCH.md Pitfall 2 warns this over-inflates the denominator with spurious peaks), implemented a middle path: read the trusted 1D shifts from `<peaks-dir>`, deduplicate near-identical readings across multiple 1D files (`_dedupe_shifts`, clusters within `c13_tol`), then filter out the known/DEPT-derived quaternary shifts. Falls back to the hardcoded list only when no 1D file exists at all (empty `<peaks-dir>` edge case). Verified empirically that this design still correctly discriminates: on the known-bad fixture, `hsqc_coverage` also trips critical (a bonus signal beyond the originally-expected quaternary_exclusion/signal_to_ridge), and on the clean fixture it passes cleanly.
- **Malformed-input handling is unconditional, not experiment-scoped**: the plan's action text suggested blocking PASS only "if load errors touched a critical experiment." Implemented a simpler, more conservative rule — any parse error anywhere in `<peaks-dir>` blocks a PASS verdict. This is a strictly safer interpretation of T-99-01 ("never silently PASS on malformed input") and was verified directly (a corrupted `HSQC_exp3.json` copy yields `verdict=FAIL`, `errors=["HSQC_exp3.json: ..."]`).
- **signal_to_ridge checks all six axes, not just the caller-specified one**: the internal `check_signal_to_ridge(peaks_by_type, config)` computes `ridge_fraction()` independently across COSY h1a/h1b and HSQC/HMBC c13/h1, taking the worst — broader coverage than a single-axis check, at no extra API-surface cost since the standalone `signal_to_ridge(peaks, axis_key)` wrapper still exposes the single-axis form used by `test_qc_checks.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task commit granularity required manual file-content bisection since both tasks share one file**
- **Found during:** Task commit protocol (after writing the complete `qc.py` in one pass)
- **Issue:** The plan's two tasks both modify `src/lucy_ng/nus/qc.py` with a natural implementation dependency (Task 2's `run_qc_checks()` calls Task 1's six check functions). Writing the whole module in one pass and then wanting two atomic per-task commits required deliberately truncating the file back to a Task-1-only state (removing `CRITICAL_CHECKS`/`SOFT_CHECKS`, `_load_peaks()`, `aggregate_verdict()`, `run_qc_checks()`), re-running Task 1's isolated verification (`pytest tests/nus/test_qc_checks.py`, the `ridge_fraction` one-liner, the `detect_hybridisation`/`_exp[0-9]` greps, `mypy`) to confirm the Task-1-only slice stood on its own, committing, then restoring the full module and re-running Task 2's verification before the second commit.
- **Fix:** No code fix needed — this was a process/tooling step, not a defect. Both commits independently pass their respective plan-specified verify commands.
- **Files modified:** `src/lucy_ng/nus/qc.py` (temporarily truncated, then restored — net diff across both commits equals the single intended implementation)
- **Verification:** `git diff` between the two commits shows exactly the expected Task 2 additions (`CRITICAL_CHECKS`/`SOFT_CHECKS`, `_load_peaks()`, `aggregate_verdict()`, `run_qc_checks()`); both commits' isolated test suites pass; full repo suite green after both commits (1343 passed, 18 skipped, 1 xfailed — identical to the single-shot result).
- **Committed in:** c319a3f (Task 1), 9d757e8 (Task 2)

---

**Total deviations:** 1 auto-fixed (1 bug — process-only, no code defect; documented for traceability of the commit-splitting mechanics)
**Impact on plan:** None on functionality. Both commits are individually correct and independently verifiable; the split was purely to honor the plan's per-task atomic-commit requirement.

## Issues Encountered
None beyond the commit-splitting mechanics documented above. `mypy src/lucy_ng/nus/qc.py` reports zero errors in the module itself (43 pre-existing repo-wide errors surface only because mypy follows transitive imports from unrelated modules — same baseline behavior confirmed in Plan 01's summary, reproduced here for `dereplication/`, `lsd/analyzer.py`, `database/manager.py`, `nmrxiv/`, `prediction/` — none touched by this plan).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- QC-01/QC-02 are now complete. `lucy_ng.nus.qc.run_qc_checks(peaks_dir)` is a fully working, importable, pure (no file writes) headless QC gate with a proven FAIL/PASS discrimination floor.
- Plan 03 (`nus/bridge.py` — Spectrum2D construction + `PeakPicker2D` call + peak-JSON emission, PICK-01/PICK-03) and Plan 04 (`cli/nus.py::qc`/`pipeline` commands + D-07 write/quarantine boundary, PICK-02/QC-03) can now proceed against a fully implemented `qc.py`, not just its data contract.
- `run_qc_checks()`'s signature (`peaks_dir: Path | str, config: QcConfig | None = None`) and `QcReport` return type are stable for Plan 04's `lucy nus qc <peaks-dir>` CLI wrapper.
- Full test suite green: 1343 passed, 18 skipped, 1 xfailed — zero regressions from this plan's additions (up from Plan 01's 1329 passed/32 skipped baseline; the delta is exactly the 14 newly-activated QC-01/QC-02 tests).
- No blockers or concerns for downstream plans.

---
*Phase: 99-peak-pick-bridge-qc-gate-cli*
*Completed: 2026-07-16*

## Self-Check: PASSED

All 3 created/modified files verified present on disk (`src/lucy_ng/nus/qc.py`,
`tests/nus/test_qc_checks.py`, `tests/nus/test_qc_regression.py`); both task
commit hashes (c319a3f, 9d757e8) verified present in git log.
