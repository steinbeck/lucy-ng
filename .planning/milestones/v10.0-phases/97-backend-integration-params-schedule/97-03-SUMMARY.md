---
phase: 97-backend-integration-params-schedule
plan: 03
subsystem: nus
tags: [nmrglue, pydantic, bruker, nus, sampling-schedule, hard-fail-assertion]

# Dependency graph
requires:
  - phase: 97-backend-integration-params-schedule (plan 01)
    provides: NusSchedule Pydantic model (REAL_FNMODES/COMPLEX_FNMODES/VALID_FNMODES constants) + tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc} fixtures
  - phase: 97-backend-integration-params-schedule (plan 02)
    provides: read_nus_params(expdir) -> NusAcquisitionParams (acqu2s FnMODE/TD/NusTD parsing)
provides:
  - "expected_sample_count(fnmode, td_f1) -> int: pure FnMODE-derived real/complex sample-count rule"
  - "validate_schedule(fnmode, td_f1, nuslist): hard-fail assertion (ValueError on mismatch, NotImplementedError on unknown FnMODE)"
  - "read_nus_schedule(expdir) -> NusSchedule: acquisition-order-preserving nuslist reader, validated before construction"
affects: [98-reconstruction-processing (consumes NusSchedule directly, no second parse pass)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "nuslist parsed via nmrglue's read_nuslist() (on-disk row order == acquisition order, one 1-tuple per row) rather than the monolithic ng.bruker.read(), which requires a fid/ser binary the D-03 fixtures intentionally omit -- same rationale as Plan 02's params.py deviation"
    - "read_nus_schedule delegates FnMODE/TD/NusTD extraction to read_nus_params (Plan 02) instead of re-parsing acqu2s directly -- one parse path for acquisition parameters, zero divergence risk"
    - "REAL_FNMODES/COMPLEX_FNMODES imported from models.nus (not redefined) so schedule.py's hard assertion and NusAcquisitionParams.fnmode_f1's validator can never disagree on the allowed-FnMODE set"

key-files:
  created: [src/lucy_ng/nus/schedule.py, tests/test_nus_schedule.py]
  modified: []

key-decisions:
  - "read_nus_schedule uses ng.bruker.read_nuslist(expdir) instead of the RESEARCH.md/PLAN's literal ng.bruker.read(expdir)['nuslist'] example, for the identical reason Plan 02 diverged for acqus/acqu2s: ng.bruker.read() unconditionally requires a fid/ser binary, which the D-03 fixtures deliberately exclude. read_nuslist() reads the same nuslist file, in the same on-disk (acquisition) order, with zero binary dependency -- verified directly against all three fixtures (first-8-rows match RESEARCH.md's documented values exactly)."

patterns-established:
  - "Hard-fail assertion order: expected_sample_count() raises NotImplementedError for an unrecognized FnMODE (no silent guess), validate_schedule() raises ValueError for a length mismatch (no silent truncate/pad) -- both propagate uncaught through read_nus_schedule(), consistent with the project's fail-loud convention (LSDRunner precedent)."

requirements-completed: [NUS-03]

# Metrics
duration: 12min
completed: 2026-07-12
---

# Phase 97 Plan 03: NUS Sampling-Schedule Parser Summary

**`nus/schedule.py` parses the Bruker `nuslist` sampling schedule in strict acquisition order and enforces the FnMODE-derived `n_sampled == len(nuslist)` hard-fail assertion (RAISES, never warns) across all three real C20H32O2 fixtures -- the correctness crux of NUS-03.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-12T14:07:02Z (following Plan 02 completion)
- **Completed:** 2026-07-12T14:19:00Z (approx)
- **Tasks:** 1 (TDD-style: implementation + tests written together, verified green before commit)
- **Files modified:** 2 created

## Accomplishments
- `expected_sample_count(fnmode, td_f1)` implements the real/complex derivation rule verbatim per RESEARCH.md: `REAL_FNMODES={1,2}` -> `td_f1`, `COMPLEX_FNMODES={4,5,6}` -> `td_f1 // 2`, any other value -> `NotImplementedError` (no silent guess)
- `validate_schedule(fnmode, td_f1, nuslist)` raises `ValueError` on any `n_sampled != len(nuslist)` mismatch, with a message explicit that the schedule must never be sorted, regenerated, truncated, or padded
- `read_nus_schedule(expdir) -> NusSchedule` reuses `read_nus_params` (Plan 02) for FnMODE/TD/NusTD and `ng.bruker.read_nuslist` for the schedule itself, validates before constructing the model
- All three real fixtures pass the hard assertion: exp2 COSY (FnMODE=1, QF) `188 == 188`; exp3 HSQC (FnMODE=6, Echo-AntiEcho) `50 == 100 // 2`; exp4 HMBC (FnMODE=6) `116 == 232 // 2`
- Acquisition-order regressions confirm `nuslist` is never sorted for all three experiments (exp2 starts `[0,124,431,670,369,53,211,120]`, exp3 `[0,33,115,178,98,14,199,56]`, exp4 `[0,58,201,312,172,24,348,98]`)
- `NusTD` real-vs-complex grid note covered by a dedicated exp3 test (`max(nuslist)==199` while `NusTD==400` is expected, not a bug, per RESEARCH.md's documented explanation)
- `REAL_FNMODES`/`COMPLEX_FNMODES` imported from `models.nus`, not redefined -- schedule.py and the `NusAcquisitionParams.fnmode_f1` validator share one allowed-FnMODE set (97-01's design decision, honored)
- 26 tests added, all green; `grep -n 'sorted(' src/lucy_ng/nus/schedule.py` shows no sorting applied to the parsed nuslist; full project suite (1269 passed, 7 skipped, 1 xfailed) unaffected

## Task Commits

1. **Task 1: expected_sample_count + validate_schedule + read_nus_schedule + NUS-03 tests** - `c554353` (feat)

**Plan metadata:** (this commit, following SUMMARY.md write)

## Files Created/Modified
- `src/lucy_ng/nus/schedule.py` - `expected_sample_count`, `validate_schedule`, `read_nus_schedule(expdir) -> NusSchedule`
- `tests/test_nus_schedule.py` - 26 tests: FnMODE derivation (real/complex/unrecognized), hard-fail assertion (pass/mismatch/unrecognized-mode), per-experiment `read_nus_schedule` behavior including acquisition-order regressions and the NusTD real-vs-complex grid note

## Decisions Made
- Used `ng.bruker.read_nuslist(expdir)` instead of the RESEARCH.md/PLAN's literal `ng.bruker.read(expdir)["nuslist"]` example. Same root cause as Plan 02's deviation: `ng.bruker.read()` requires a `fid`/`ser` binary file that the D-03 metadata-only fixtures intentionally omit. `read_nuslist()` reads the identical `nuslist` file in identical on-disk (acquisition) order with zero binary dependency -- verified directly, first-8-row values match RESEARCH.md's documented acquisition-order table exactly for all three experiments.
- `read_nus_schedule` delegates FnMODE/TD/NusTD extraction entirely to `read_nus_params` (Plan 02) rather than re-parsing `acqu2s` independently, keeping exactly one acquisition-parameter parse path in the codebase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `ng.bruker.read(expdir)["nuslist"]` would fail against the D-03 test fixtures**
- **Found during:** Task 1, initial implementation per the plan/RESEARCH.md code example
- **Issue:** `ng.bruker.read()` raises `OSError: No Bruker binary file could be found` when no `fid`/`ser` binary exists in `expdir` -- true for all three `tests/fixtures/nus/*` directories by D-03's design. Implementing the literal example would make the NUS-03 fixture-verification requirement unsatisfiable, exactly mirroring Plan 02's params.py finding.
- **Fix:** Used `ng.bruker.read_nuslist(expdir)` (nmrglue's dedicated, metadata-only `nuslist` reader) instead, combined with `read_nus_params(expdir)` (Plan 02) for FnMODE/TD/NusTD.
- **Files modified:** `src/lucy_ng/nus/schedule.py`
- **Verification:** All 26 tests pass; `nuslist[:8]` values for all three fixtures match RESEARCH.md's verified acquisition-order table exactly; full suite green (1269 passed)
- **Committed in:** `c554353` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (bug fix, necessary for the plan's own acceptance criteria to be satisfiable against the shipped fixtures; consistent with Plan 02's identical deviation)
**Impact on plan:** Strict improvement over the literal code example -- no scope creep, same public contract (`read_nus_schedule(expdir) -> NusSchedule`), same underlying file read (`nuslist`, acquisition order preserved).

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- NUS-03 complete: `nus/schedule.py` ready for Phase 98 (reconstruction consumes `NusSchedule` directly -- the sampled-index grid drives `nusExpand.tcl`'s zero-fill step).
- `nus/backends/` (97-04, NUS-01) and `cli/nus.py` (97-05, NUS-01/04/05) remain to close out Phase 97.
- No blockers.

---
*Phase: 97-backend-integration-params-schedule*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created files and commit hashes verified present in the repository.
