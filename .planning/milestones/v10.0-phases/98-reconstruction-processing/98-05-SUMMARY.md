---
phase: 98-reconstruction-processing
plan: 05
subsystem: nus-reconstruction
tags: [nmrpipe, smile, orchestration, subprocess, pydantic]

requires:
  - phase: 98-reconstruction-processing (Plan 02)
    provides: run_stage() fail-loud wrapper + recipe_for_fnmode()/FnModeRecipe table
  - phase: 98-reconstruction-processing (Plan 03)
    provides: NmrPipeSmileBackend.convert()/reconstruct_indirect()
  - phase: 98-reconstruction-processing (Plan 04)
    provides: postprocess.process_direct()/process_indirect()
provides:
  - NusRunner.reconstruct(expdir) whole-pipeline orchestration entrypoint
  - F2Plan / _resolve_f2_plan() hard-gate precondition (RECON-02)
  - Real end-to-end skipif-guarded integration test (D-04)
affects: [98-06 (CLI reconstruct command), 99 (peak-pick bridge consumes NusReconstructionResult)]

tech-stack:
  added: []
  patterns:
    - "Four-stage orchestration dispatched in physical order: backend.convert() -> postprocess.process_direct() -> backend.reconstruct_indirect() -> postprocess.process_indirect(), with the F2-before-F1 gate checked as an explicit precondition before any stage dispatch"
    - "Backend duck-typed as Any in NusRunner.__init__ -- both a classmethod-based backend class (production) and a plain instance test double are legitimate callers; contract enforced at the registry boundary (NusBackend Protocol), not in NusRunner"

key-files:
  created: []
  modified:
    - src/lucy_ng/nus/runner.py
    - tests/nus/test_reconstruct_orchestration.py
    - tests/nus/test_reconstruct_integration.py

key-decisions:
  - "F2 phase constants (f2_p0/f2_p1) default to 0.0/0.0 in NusRunner.reconstruct() -- explicitly documented PROVISIONAL, no universal value exists across pulse sequences; CLI override deferred to a later plan (mirrors f1_p0=90.0's existing PROVISIONAL default from Plan 03)"
  - "Rewrote all three Wave-0 stub tests in test_reconstruct_orchestration.py: the as-written stubs referenced result.output_file (not a NusReconstructionResult field) and used mock_run_stage's low-level (name, argv, cwd, expected_output) recorder, which cannot distinguish process_direct()'s output from convert()'s internal bruk2pipe/nusExpand.tcl outputs (all .fid-suffixed). Rewrote to patch at the four-stage-callable boundary (fake backend double + runner-module process_direct/process_indirect patches) per the plan's own Task 1 action text, which explicitly describes this alternate mocking strategy."
  - "Fixed test_reconstruct_integration.py's exp3 assertion from result.output_file (does not exist on the model) to result.processed_spectrum (existence + non-emptiness) -- same root cause as above."

patterns-established:
  - "F2Plan dataclass (frozen, single `magnitude: bool` field) is the RECON-02 hard-gate seam: _resolve_f2_plan() returns None (never raises) on an unrecognized FnMODE so reconstruct() itself raises the specific, test-asserted RuntimeError before any subprocess dispatch."

requirements-completed: [RECON-01, RECON-02]

duration: ~20min
completed: 2026-07-13
---

# Phase 98 Plan 05: NusRunner Orchestration Summary

**`NusRunner.reconstruct(expdir)` wires Phase 97 params/schedule parsing + Plans 02-04's stage primitives into one whole-pipeline entrypoint: convert -> process_direct(F2+TP) -> SMILE -> process_indirect(F1+calib), gated by a hard F2-before-F1 precondition that raises before any subprocess runs.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-13T12:46:38Z
- **Tasks:** 2/2 completed
- **Files modified:** 3

## Accomplishments

- `NusRunner` class added to `src/lucy_ng/nus/runner.py`: `__init__` resolves the backend via `get_backend()` (no re-implemented discovery), `_stage_dir()` owns the persistent `analysis/nus_recon/<expN>/` lifecycle (D-03 keep, no rmtree), `_resolve_f2_plan()` + `F2Plan` implement the RECON-02 hard gate as an explicit precondition.
- `reconstruct()` reads `NusAcquisitionParams`/`NusSchedule` exactly once, then dispatches the four stages in the SMILE-manual-mandated physical order (`backend.convert()` -> `postprocess.process_direct()` -> `backend.reconstruct_indirect()` -> `postprocess.process_indirect()`), with `reconstruct_indirect()` fed `process_direct()`'s own return value (never `convert()`'s raw output) -- returns a fully populated `NusReconstructionResult`.
- Rewrote the three Plan-01 Wave-0 orchestration test stubs to patch at the four-stage-callable boundary (a `_RecordingBackend` double + monkeypatched `runner_module.process_direct`/`process_indirect`) so the ordering test can assert both call sequence AND that SMILE receives the F2-processed FID specifically -- something the lower-level `run_stage()` mock seam cannot distinguish (both `convert()`'s internal stages and `process_direct()` write `.fid`-suffixed intermediates).
- Fixed the real end-to-end skipif-guarded integration test's result assertions (`result.processed_spectrum`, not the non-existent `result.output_file`) so it is a correct (if currently skipped) test of the actual `NusReconstructionResult` contract.

## Task Commits

1. **Task 1: NusRunner.reconstruct() four-stage orchestration + F2-before-F1 hard gate** - `152de93` (feat)
2. **Task 2: Real end-to-end skipif integration test (D-04)** - `15d33f4` (test)

## Files Created/Modified

- `src/lucy_ng/nus/runner.py` - Added `F2Plan` dataclass + `NusRunner` class (`__init__`, `_stage_dir`, `_resolve_f2_plan`, `reconstruct`); module-level imports extended to pull in `get_backend`, `read_nus_params`/`read_nus_schedule`, `process_direct`/`process_indirect`, and the `NusAcquisitionParams`/`NusReconstructionResult` models.
- `tests/nus/test_reconstruct_orchestration.py` - Rewrote all three tests (gate-raises, ordering+f2-input, result-shape) to use a fake backend double + runner-module-level patches instead of the Plan-01 stub's `mock_run_stage`/`result.output_file` shape.
- `tests/nus/test_reconstruct_integration.py` - Fixed the exp3 end-to-end test's result assertions to use `result.processed_spectrum` (still `@pytest.mark.skipif`-guarded, unchanged skip condition).

## Decisions Made

- **F2 phase defaults (0.0/0.0), explicitly PROVISIONAL:** No SMILE-manual-verified universal F2 phase constant exists (unlike F1, which already carries a manual-sourced-but-provisional 90.0/0.0 default from Plan 03). Documented in the docstring as provisional; CLI override is deferred to a later plan (CLI wiring is explicitly out of this plan's task list — confirmed via `cli/nus.py`'s own docstring, which reserves `reconstruct` for a dedicated later plan).
- **Backend typed `Any` in `NusRunner.__init__`, not a narrower Protocol:** both the production classmethod-based backend class (`NmrPipeSmileBackend`, returned by `get_backend()`) and a plain instance test double (this plan's `_RecordingBackend`) are legitimate callers with different calling conventions (class-with-classmethods vs. instance-with-bound-methods) — the real `convert()`/`reconstruct_indirect()` signature contract is enforced by the `NusBackend` Protocol at the registry boundary, not re-declared here.
- **Rewrote (not merely filled in) the Plan-01 test stubs:** the as-written stubs referenced a `result.output_file` attribute that does not exist on `NusReconstructionResult` (Plan-01's own model has `stage_outputs`/`processed_spectrum`) and used `mock_run_stage`'s `(name, argv, cwd, expected_output)`-level recorder, which cannot distinguish `process_direct()`'s F2-processed output from `convert()`'s own internal `bruk2pipe`/`nusExpand.tcl` outputs (both `.fid`-suffixed). This plan's own Task 1 action text explicitly directs "patch the four stage callables with an ordered recorder" as the correct strategy, so the stub rewrite follows the plan's own instruction rather than the Plan-01 scaffold's literal fixture usage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed non-existent `object` attribute-access mypy errors on `self.backend`**
- **Found during:** Task 1, running `mypy src/lucy_ng/nus/runner.py` as the task's own verification step
- **Issue:** `NusRunner.__init__(self, backend: object | None = None)` typed `self.backend` as `object`, which has no `.convert`/`.reconstruct_indirect` attributes — mypy flagged both call sites (`attr-defined`).
- **Fix:** Retyped the `backend` parameter and `self.backend` as `Any` with a docstring explaining the duck-typed contract (classmethod-based class vs. instance test double), consistent with how the registry (`nus/backends/__init__.py`) already enforces the real Protocol.
- **Files modified:** `src/lucy_ng/nus/runner.py`
- **Verification:** `mypy src/lucy_ng/nus/runner.py` now reports zero errors specific to this file (only the pre-existing, already-accepted `nmrglue` "Skipping analyzing" import-untyped note, present since Plan 02's own commit of this file — verified by checking out that commit and re-running mypy against it).
- **Committed in:** `152de93` (Task 1 commit)

### Interpretation notes (not code deviations)

- **Literal `grep -c 'read_nus_params'`/`grep -c 'read_nus_schedule'` acceptance text:** the plan's acceptance criteria state these greps should "each return 1." In practice each returns 4 (docstring prose mentions the function names twice, plus one `import` line, plus one call site) because `runner.py`'s docstrings reference both names by name. The underlying correctness invariant — each parser is *called* exactly once per `reconstruct()` invocation, never re-parsed — is satisfied and verified by inspection (`grep -n 'params = read_nus_params\|schedule = read_nus_schedule'` shows exactly one call site each). Interpreted the literal grep-count instruction as shorthand for this invariant rather than a literal file-wide occurrence count, since a single call-site with any docstring documentation cannot satisfy a literal count of 1 for a well-documented module.

---

**Total deviations:** 1 auto-fixed (Rule 1 bug fix), plus 1 documented interpretation note on a literal acceptance-grep count.
**Impact on plan:** The mypy fix was necessary for the plan's own stated verification gate to pass cleanly; no scope creep. The grep-count interpretation note does not affect functional correctness.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required. (The real backend/data-gated integration test remains SKIPPED on this dev machine, as expected per D-04 — no NMRPipe+SMILE install on this system.)

## Next Phase Readiness

- `NusRunner.reconstruct()` is a complete, orchestration-tested whole-pipeline entrypoint ready for Plan 06's `lucy nus reconstruct` CLI command to wrap directly (deferred imports + `--format json`, matching `cli/nus.py`'s existing `params`/`schedule` command shape).
- `NusReconstructionResult.processed_spectrum` (plus `stage_dir`/`stage_outputs`) is the concrete artefact-path contract Phase 99's `nus/bridge.py` peak-pick bridge will consume.
- No blockers. The QF/magnitude COSY `convert_first` branch (Plan 03's PROVISIONAL A1/A3 flag) and the F1/F2 phase-constant defaults (A2, plus this plan's own F2 default) remain empirically unverified pending real NMRPipe+SMILE access — tracked, not blocking, since the real integration test is explicitly designed to surface this the moment a backend becomes available.

---
*Phase: 98-reconstruction-processing*
*Completed: 2026-07-13*

## Self-Check: PASSED

- FOUND: src/lucy_ng/nus/runner.py
- FOUND: SUMMARY.md (this file)
- FOUND commit: 152de93 (Task 1)
- FOUND commit: 15d33f4 (Task 2)
