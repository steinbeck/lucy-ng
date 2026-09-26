---
phase: 98-reconstruction-processing
plan: "04"
subsystem: nus-reconstruction
tags: [nus, subprocess, nmrpipe, phase, ppm-calibration, postprocess]

# Dependency graph
requires:
  - phase: 98-reconstruction-processing
    plan: "02"
    provides: "run_stage() fail-loud subprocess wrapper"
  - phase: 98-reconstruction-processing
    plan: "03"
    provides: "NmrPipeSmileBackend.convert() (producing converted.fid) + reconstruct_indirect() (SMILE call, producing reconstructed.ft1)"
provides:
  - "src/lucy_ng/nus/postprocess.py::process_direct() -- F2 apod/ZF/FT/PS/POLY + TP as ONE run_stage-checked stage, SMILE's actual input"
  - "src/lucy_ng/nus/postprocess.py::process_indirect() -- post-SMILE F1 ZF/FT/PS + final TP as ONE run_stage-checked stage, producing processed.ft2"
  - "src/lucy_ng/nus/postprocess.py::ppm_scale()/ppm_axis_for_dimension()/calibrate_against_1d_reference()/check_calibration() -- reversed ppm-axis + 1D ground-truth calibration cross-check (pure arithmetic)"
affects: [98-05, 98-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Each processing stage is ONE nmrPipe subprocess invocation with multiple chained -fn blocks (SP/ZF/FT/PS/POLY/TP in one argv) rather than unix-piped separate invocations -- keeps the whole stage as ONE run_stage()-checked subprocess.run() call with zero shell interpretation, while still satisfying idiomatic NMRPipe multi-verb processing scripts"
    - "run_stage()/recipe_for_fnmode() imported via a deferred import inside each function body (matches Plan 03's convert()/reconstruct_indirect() precedent) -- both avoids a runner<->postprocess import cycle and lets tests/nus/conftest.py's mock_run_stage fixture (which monkeypatches lucy_ng.nus.runner.run_stage) take effect, since the deferred import resolves the patched attribute at call time"
    - "process_indirect() writes a best-effort processed_ppm_axis.json sidecar (raw + calibrated F1 ppm axis, offset applied) only when params carries F1 SF/OFFSET calibration fields -- silently skipped pre-reconstruction, matching NusAcquisitionParams' own None-is-legitimate convention"

key-files:
  created:
    - "src/lucy_ng/nus/postprocess.py"
  modified:
    - "tests/nus/test_processing_order.py"

key-decisions:
  - "Deviated from the plan's literal ppm helper names (ppm_scale(sf, offset, size) / check_calibration()) to match the Plan-01 test scaffold's already-fixed import names (ppm_axis_for_dimension(sf, offset, sw_h, size), calibrate_against_1d_reference()) -- same precedent as Plan 03's reconstruct_indirect() signature deviation: the committed test file is authoritative over the plan's illustrative interface sketch. ppm_scale() is kept as the actual 4-argument implementation (satisfying the plan's literal 'def ppm_scale(' acceptance grep) with ppm_axis_for_dimension() as a same-signature named wrapper the tests import; check_calibration() is also implemented as the plan's described pass/fail wrapper, additive to (not replacing) calibrate_against_1d_reference()."
  - "process_direct()/process_indirect() both accept an optional params: NusAcquisitionParams | None = None positional parameter (not required, no default in the plan's sketch) because the committed test stubs call process_direct() without a params argument at all -- required per the same test-scaffold-is-authoritative precedent. params is used only by process_indirect()'s optional ppm-calibration sidecar; process_direct()'s apodization/ZF parameters are fixed defaults (per CONTEXT.md's 'Apodization/ZF parameter choices -- planner/executor discretion')."
  - "Split the single-file implementation into two atomic task commits by writing the Task-1-only content first (process_direct()/process_indirect() without the ppm helpers, with the two ppm test stubs temporarily re-skipped), committing, then adding the ppm helpers + un-skipping the ppm tests as a second commit -- preserves the plan's per-task atomic-commit contract despite both tasks touching the same two files."

patterns-established:
  - "One-nmrPipe-invocation-per-stage (multiple chained -fn blocks in one argv, never unix pipes or per-verb subprocess.run calls) is the concrete shape 98-05's NusRunner.reconstruct() orchestration should expect from both process_direct() and process_indirect() when wiring convert() -> process_direct() -> reconstruct_indirect() -> process_indirect()."

requirements-completed: [RECON-02]

# Metrics
duration: 18min
completed: 2026-07-13
---

# Phase 98 Plan 04: F2/F1 Processing + ppm Calibration Summary

**`nus/postprocess.py` now brackets the SMILE call with `process_direct()` (F2 apod/ZF/FT/PS/POLY + transpose, SMILE's actual input) and `process_indirect()` (post-SMILE F1 ZF/FT/PS + final transpose + optional ppm-calibration sidecar), each dispatched as ONE run_stage-checked `nmrPipe` invocation with deterministic, never-searched phase constants.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-07-13 (continuing directly after Plan 03)
- **Completed:** 2026-07-13
- **Tasks:** 2 completed
- **Files modified:** 2 (`src/lucy_ng/nus/postprocess.py` created, `tests/nus/test_processing_order.py` modified)

## Accomplishments

- Implemented `process_direct(converted_fid, stage_dir, params=None, *, f2_p0, f2_p1, magnitude, timeout=600) -> Path`: builds ONE `nmrPipe` invocation chaining `SP -> ZF -> FT -> [PS -p0/-p1 -di, unless magnitude] -> POLY -> TP`, verified via `run_stage("process_direct", ...)`. Output (`f2_processed.fid`) is the transposed, F2-processed FID that becomes SMILE's actual input (Plan 03's `reconstruct_indirect()`); this function never calls SMILE itself, mechanically enforcing RECON-02's F2-before-F1 gate.
- Implemented `process_indirect(reconstructed_fid, stage_dir, params=None, *, f1_p0, f1_p1, magnitude, timeout=600) -> Path`: builds ONE `nmrPipe` invocation chaining `ZF -> FT -> [PS -p0/-p1 -di, unless magnitude] -> TP`, verified via `run_stage("process_indirect", ...)`, producing `processed.ft2`. Runs strictly after SMILE.
- Both functions thread deterministic, CLI-overridable phase constants (`f2_p0`/`f2_p1`, `f1_p0`/`f1_p1`) directly into the `PS` verb's argv -- never derived by a search loop; the magnitude (COSY) branch omits the `PS` verb entirely.
- Implemented `ppm_scale()`/`ppm_axis_for_dimension()` (reversed, highest-ppm-first axis from SF/OFFSET/SW_h/size) and `calibrate_against_1d_reference()`/`check_calibration()` (cross-check + calibrate a computed axis against the `GUIDE_S10_C13` NUS-RECONSTRUCTION-GUIDE.md Sec.10 ground-truth 13C shift list) -- pure Python arithmetic, no external tool. `process_indirect()` writes these results to a best-effort `processed_ppm_axis.json` sidecar whenever `params` carries F1 SF/OFFSET calibration fields.
- Un-skipped all 5 Plan-01 stub tests in `tests/nus/test_processing_order.py` (3 direct-processing stubs against the `mock_run_stage` argv-capture seam + 2 ppm-calibration stubs), all green.

## Task Commits

Each task was committed atomically:

1. **Task 1: process_direct()/process_indirect() F2/F1 processing stages** - `7633741` (feat)
2. **Task 2: ppm-axis reversal + 1D calibration cross-check (RECON-02)** - `caaecb0` (feat)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `src/lucy_ng/nus/postprocess.py` - New module: `process_direct()`, `process_indirect()`, `_write_ppm_calibration_sidecar()`, `ppm_scale()`, `ppm_axis_for_dimension()`, `calibrate_against_1d_reference()`, `check_calibration()`, `GUIDE_S10_C13` ground-truth constant.
- `tests/nus/test_processing_order.py` - Un-skipped all 5 Plan-01 stubs (`test_f2_direct_chain_runs_before_transpose_before_smile_input`, `test_f2_phase_constants_thread_through`, `test_magnitude_branch_skips_phase`, `test_ppm_axes_reversed`, `test_ppm_calibrated_to_1d_reference`); removed the now-unused `import pytest`.

## Decisions Made

See frontmatter `key-decisions` — summarized: (1) matched the Plan-01 test scaffold's exact function names/signatures (`ppm_axis_for_dimension`, `calibrate_against_1d_reference`, `process_direct()`/`process_indirect()` with optional `params`) over the plan's illustrative interface sketch, keeping `ppm_scale()` as the real implementation to also satisfy the plan's literal acceptance-grep; (2) split the single-file implementation into two atomic commits (Task-1-only content committed first, ppm helpers added second) to preserve the per-task commit contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Matched test-scaffold function names/signatures over the plan's interface sketch**
- **Found during:** Task 1, before writing `process_direct()`
- **Issue:** The plan's `<action>` describes `ppm_scale(sf, offset, size)` and `check_calibration(...)`, but the already-committed Plan-01 test stubs in `tests/nus/test_processing_order.py` import `ppm_axis_for_dimension(sf, offset, sw_h, size)` and `calibrate_against_1d_reference(computed_axis, reference_shifts)`, and call `process_direct()` without any `params` argument at all. Following the plan's literal signatures would make the committed tests un-importable/un-callable.
- **Fix:** Implemented `ppm_scale()` as the real 4-argument function (satisfying the plan's `grep -c 'def ppm_scale('` acceptance criterion), with `ppm_axis_for_dimension()` as a same-signature wrapper matching what the tests import; implemented `calibrate_against_1d_reference()` matching the tests' 2-positional-argument call, plus `check_calibration()` as the plan's described pass/fail wrapper (additive). Gave `process_direct()`/`process_indirect()` an optional `params: NusAcquisitionParams | None = None` parameter so the test calls (which omit it) work unchanged.
- **Files modified:** `src/lucy_ng/nus/postprocess.py`
- **Verification:** `pytest tests/nus/test_processing_order.py -q` — 5 passed, 0 skipped.
- **Committed in:** `7633741` (Task 1), `caaecb0` (Task 2)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug fix; matches the identical class of deviation Plan 03 made for the same reason).
**Impact on plan:** No scope creep — the fix was required to make the plan's own committed test scaffold (and thus its own acceptance criteria) satisfiable.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required. (NMRPipe/SMILE remain a runtime-detected external binary per the Phase-97 precedent; no pip dependency was added.)

## Next Phase Readiness

- `process_direct()` + `process_indirect()` are complete and independently unit-tested against the fully mocked `run_stage()` boundary (D-04), with the F2-before-F1 physical ordering enforced by the type-level two-function split established in Plan 03.
- `ppm_scale()`/`ppm_axis_for_dimension()`/`calibrate_against_1d_reference()`/`check_calibration()` are ready for Plan 05's `NusRunner.reconstruct()` to wire the full chain: `convert()` -> `process_direct()` -> `reconstruct_indirect()` -> `process_indirect()`.
- The F2/F1 phase defaults threaded through by this plan remain PROVISIONAL per 98-RESEARCH.md Assumptions Log A2 (inherited from Plan 03) — D-02's CLI override flags (Plan 06) are the mitigation path; the first real reconstruction run should cross-check these defaults empirically.
- No touch to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py`, `.claude/` — confirmed via `git diff --name-only HEAD~2 HEAD` across both task commits (only the two plan-scoped files changed).

## Self-Check: PASSED

- `src/lucy_ng/nus/postprocess.py` — FOUND, contains `def process_direct(`, `def process_indirect(`, `def ppm_scale(`.
- `tests/nus/test_processing_order.py` — FOUND, 5 tests, 0 skipped.
- Commit `7633741` — FOUND in `git log --oneline`.
- Commit `caaecb0` — FOUND in `git log --oneline`.

---
*Phase: 98-reconstruction-processing*
*Completed: 2026-07-13*
