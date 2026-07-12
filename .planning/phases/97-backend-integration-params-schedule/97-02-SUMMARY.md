---
phase: 97-backend-integration-params-schedule
plan: 02
subsystem: nus
tags: [nmrglue, pydantic, bruker, nus, params-parsing]

# Dependency graph
requires:
  - phase: 97-backend-integration-params-schedule (plan 01)
    provides: NusAcquisitionParams/NusSchedule Pydantic models + tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc} fixtures
provides:
  - "read_nus_params(expdir) -> NusAcquisitionParams: pure-Python Bruker NUS acquisition + calibration parameter reader"
affects: [97-03 (nus/schedule.py), 98-reconstruction-processing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bruker NUS metadata parsing via nmrglue's low-level read_acqus_file()/read_procs_file() (not the monolithic ng.bruker.read(), which requires a fid/ser binary that NUS param/schedule fixtures intentionally omit)"
    - "fnmode_f1 always read from acqu2s, never acqus (acqus FnMODE is a vestigial 0 for every experiment)"
    - "SF/OFFSET calibration fields read from pdata/1/procs+proc2s, legitimately None pre-reconstruction (not a parse failure)"

key-files:
  created: [src/lucy_ng/nus/params.py, tests/test_nus_params.py]
  modified: []

key-decisions:
  - "read_nus_params uses ng.bruker.read_acqus_file()/read_procs_file() instead of the RESEARCH.md/PLAN's literal ng.bruker.read(expdir) example -- the latter requires a fid/ser binary to be present to determine data shape, which the D-03 test fixtures deliberately exclude (metadata-only, per D-03's own stated rationale). The low-level readers parse the identical acqus/acqu2s/procs/proc2s files with identical bracket-stripping/coercion and zero binary dependency, working correctly against both the fixtures and real not-yet-reconstructed NUS experiment directories."

patterns-established:
  - "require(param_dict, key) helper wraps _get_param_2d with an explicit ValueError for genuinely-required acquisition fields, while SF/OFFSET calibration fields use the bare _get_param_2d call (None is valid pre-reconstruction)."

requirements-completed: [NUS-02]

# Metrics
duration: 14min
completed: 2026-07-12
---

# Phase 97 Plan 02: Bruker NUS Params Reader Summary

**`read_nus_params(expdir)` parses Bruker NUS acquisition + calibration parameters into a validated `NusAcquisitionParams`, using nmrglue's metadata-only readers so it works against both the real C20H32O2 fixtures (no `ser` binary) and live not-yet-reconstructed experiment directories.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-12T13:48:10Z (approx, following Plan 01 completion)
- **Completed:** 2026-07-12T14:02:08Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2 created

## Accomplishments
- `read_nus_params(expdir) -> NusAcquisitionParams` implemented in `src/lucy_ng/nus/params.py`, reusing `readers/bruker.py`'s `_get_param_2d` (no duplication)
- `fnmode_f1`/`nus_td` correctly sourced from `acqu2s`, never the vestigial `acqus FnMODE` (always 0) -- guarded by an explicit regression test per fixture
- `SF`/`OFFSET` correctly sourced from `pdata/1/procs`/`pdata/1/proc2s`, not `acqus`/`acqu2s`
- All three real C20H32O2 fixtures (exp2 COSY, exp3 HSQC, exp4 HMBC) parse to research-verified values: FnMODE 1/6/6, TD 188/100/232, NusTD 750/400/700, GRPDLY kept as an unrounded float, NusAMOUNT 25/25/33
- `FileNotFoundError` raised before any nmrglue call for a nonexistent `expdir`
- 24 tests added, all green; full project suite (1243 passed, 7 skipped, 1 xfailed) unaffected

## Task Commits

Each task was committed atomically (TDD RED/GREEN):

1. **Task 1: read_nus_params + NUS-02 fixture tests (RED)** - `cab8787` (test)
2. **Task 1: read_nus_params + NUS-02 fixture tests (GREEN)** - `839df61` (feat)

**Plan metadata:** (this commit, following SUMMARY.md write)

## Files Created/Modified
- `src/lucy_ng/nus/params.py` - `read_nus_params(expdir) -> NusAcquisitionParams`; metadata-only Bruker reader (acqus/acqu2s/procs/proc2s), no fid/ser dependency
- `tests/test_nus_params.py` - 24 tests: per-experiment field assertions (COSY/HSQC/HMBC), acqu2s-vs-acqus FnMODE regression, nonexistent-expdir error handling

## Decisions Made
- Chose nmrglue's low-level `read_acqus_file()`/`read_procs_file()` over the plan's literal `ng.bruker.read(expdir)` code example, because the latter unconditionally requires a `fid`/`ser` binary file to determine data shape/endianness -- a hard requirement the D-03 test fixtures (`tests/fixtures/nus/*/`) deliberately do not satisfy (D-03: "params/schedule parsing reads only the text metadata, so `ser` is unnecessary weight here"). Verified directly: `ng.bruker.read()` against the shipped fixtures raises `OSError: No Bruker binary file could be found`. The low-level readers parse the exact same files with identical semantics and no binary dependency, so this is a strict improvement, not a workaround -- it also matches real not-yet-reconstructed NUS directories (Phase 98 will introduce the first binary-dependent read).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `ng.bruker.read(expdir)` fails against the D-03 test fixtures**
- **Found during:** Task 1, initial implementation per the plan/RESEARCH.md code example
- **Issue:** `ng.bruker.read()` raises `OSError: No Bruker binary file could be found` when no `fid`/`ser` binary exists in `expdir` -- true for all three `tests/fixtures/nus/*` directories by D-03's own design (metadata-only, no large binaries). Implementing the literal RESEARCH.md example would make NUS-02/NUS-04's fixture-verification requirement unsatisfiable.
- **Fix:** Used `ng.bruker.read_acqus_file(expdir)` + `ng.bruker.read_procs_file(expdir)` instead -- nmrglue's lower-level, metadata-only readers, verified to return byte-identical parsed values (`acqu2s FnMODE`, `TD`, `NusTD`, `SF`, `OFFSET`, etc.) for all three fixtures without touching any binary file.
- **Files modified:** `src/lucy_ng/nus/params.py`
- **Verification:** All 24 fixture-value tests pass; `grep -n 'read_pdata' src/lucy_ng/nus/params.py` returns nothing (acceptance criterion satisfied); full suite green (1243 passed)
- **Committed in:** `839df61` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, necessary for the plan's own acceptance criteria to be satisfiable against the shipped fixtures)
**Impact on plan:** Strict improvement over the literal code example -- no scope creep, same public contract (`read_nus_params(expdir) -> NusAcquisitionParams`), same file set read (`acqus`/`acqu2s`/`pdata/1/procs`/`pdata/1/proc2s`).

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- NUS-02 complete: `nus/params.py` ready for Plan 03 (`nus/schedule.py`, which will similarly need to avoid `ng.bruker.read()`'s binary-file requirement -- likely via `ng.bruker.read_nuslist(expdir)`, already verified metadata-only in this plan's exploration) and for Phase 98 (reconstruction/processing consumes `NusAcquisitionParams` directly, no second parse pass).
- No blockers.

---
*Phase: 97-backend-integration-params-schedule*
*Completed: 2026-07-12*
