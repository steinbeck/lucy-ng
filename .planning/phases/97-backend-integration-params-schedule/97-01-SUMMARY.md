---
phase: 97-backend-integration-params-schedule
plan: 01
subsystem: nmr-data-model
tags: [pydantic-v2, bruker, nus, nmrglue, tdd]

# Dependency graph
requires: []
provides:
  - "tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc}/ — real C20H32O2 NUS metadata fixtures (acqus/acqu2s/nuslist/pdata/1/{procs,proc2s}), no binary ser"
  - "NusAcquisitionParams + NusSchedule Pydantic v2 models (src/lucy_ng/models/nus.py), re-exported from lucy_ng.models"
  - "lucy_ng.nus / lucy_ng.nus.backends package markers (docstring-only, ready for wave-2 submodules)"
affects: ["97-02", "97-03", "97-04", "97-05"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "F1/F2 disambiguation via field naming (fnmode_f1, never bare fnmode) — acqus FnMODE is vestigial 0, only acqu2s FnMODE governs schedule length"
    - "SF/OFFSET calibration fields as Optional[float]=None (legitimate pre-reconstruction state, not a parse failure)"
    - "Shared VALID_FNMODES module constant so schedule.py (plan 03) can reuse the same allowed set, not duplicate divergent logic"

key-files:
  created:
    - src/lucy_ng/models/nus.py
    - src/lucy_ng/nus/__init__.py
    - src/lucy_ng/nus/backends/__init__.py
    - tests/test_nus_models.py
    - tests/fixtures/nus/exp2_cosy/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}
    - tests/fixtures/nus/exp3_hsqc/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}
    - tests/fixtures/nus/exp4_hmbc/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}
  modified:
    - src/lucy_ng/models/__init__.py

key-decisions:
  - "Fixture set expanded beyond D-03's original acqus/acqu2s/nuslist trio to also include pdata/1/procs+proc2s per RESEARCH.md's SF/OFFSET-live-in-procs correction — SF/OFFSET fields would otherwise have zero fixture coverage"
  - "fnmode_f1 validator restricted to {1,2,4,5,6} sharing the exact REAL_FNMODES|COMPLEX_FNMODES constant nus/schedule.py (plan 03) must agree with, not a separately-maintained allowlist"

patterns-established:
  - "NusAcquisitionParams/NusSchedule follow Spectrum1D's ConfigDict + field_validator + to_dict/from_dict convention exactly (models/spectrum.py)"

requirements-completed: [NUS-02, NUS-03]

# Metrics
duration: 4min
completed: 2026-07-12
---

# Phase 97 Plan 01: Fixtures + NUS Models Foundation Summary

**Real C20H32O2 NUS metadata fixtures (exp2 COSY/exp3 HSQC/exp4 HMBC) plus validated `NusAcquisitionParams`/`NusSchedule` Pydantic v2 contracts, TDD-built and fixture-verified against every FnMODE/NusTD/nuslist-length value in RESEARCH.md.**

## Performance

- **Duration:** 4 min (15:34–15:38 local)
- **Started:** 2026-07-12T13:34:25Z (approx, first commit)
- **Completed:** 2026-07-12T13:38:01Z
- **Tasks:** 2 (Task 2 executed as TDD: RED → GREEN, no REFACTOR needed)
- **Files modified:** 18 (15 fixture files, 2 nus package markers, models/nus.py, models/__init__.py, test_nus_models.py)

## Accomplishments
- Copied the real C20H32O2 exp2/exp3/exp4 NUS metadata (acqus, acqu2s, nuslist, pdata/1/procs, pdata/1/proc2s) into `tests/fixtures/nus/` — no binary `ser` — with every acceptance-criteria value independently re-verified (FnMODE 1/6/6, NusTD 750/400/700, nuslist lengths 188/50/116)
- Defined `NusAcquisitionParams` (D-04 superset: raw acquisition params + pre-reconstruction-nullable SF/OFFSET calibration) and `NusSchedule` (acquisition-ordered nuslist + FnMODE-aware n_sampled) as validated Pydantic v2 models
- Made the F1/F2 FnMODE trap structurally impossible to get wrong at the model layer: the field is named `fnmode_f1` and its validator only accepts `{1,2,4,5,6}`
- Established `lucy_ng.nus`/`lucy_ng.nus.backends` as importable package markers for wave-2 plans to fill in without touching shared `__init__` files

## Task Commits

Each task was committed atomically:

1. **Task 1: Copy real C20H32O2 metadata fixtures + create nus package markers** - `0ea9535` (feat)
2. **Task 2: NusAcquisitionParams + NusSchedule Pydantic models + model tests** - `20d6ba8` (test, RED) → `a94327d` (feat, GREEN)

**Plan metadata:** (this commit, docs)

_Note: Task 2 is a TDD task — RED (failing import) then GREEN (11/11 passing), no REFACTOR commit needed (implementation was clean on first pass)._

## Files Created/Modified
- `tests/fixtures/nus/exp2_cosy/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}` - real COSY (FnMODE=1, TD=188, NusTD=750) metadata
- `tests/fixtures/nus/exp3_hsqc/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}` - real HSQC (FnMODE=6, TD=100, NusTD=400) metadata
- `tests/fixtures/nus/exp4_hmbc/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}` - real HMBC (FnMODE=6, TD=232, NusTD=700) metadata
- `src/lucy_ng/nus/__init__.py` - package marker, docstring only (submodules land in later plans)
- `src/lucy_ng/nus/backends/__init__.py` - package marker, docstring only (Protocol + registry land in plan 04)
- `src/lucy_ng/models/nus.py` - `NusAcquisitionParams` + `NusSchedule` Pydantic v2 models
- `src/lucy_ng/models/__init__.py` - re-exports the two new models
- `tests/test_nus_models.py` - 11 tests: fixture-value construction, round-trip, nucleus/FnMODE validator rejection, SF/OFFSET None-default, unsorted-order preservation

## Decisions Made
- Followed RESEARCH.md's explicit recommendation to also copy `pdata/1/procs`/`pdata/1/proc2s` per experiment (beyond D-03's original acqus/acqu2s/nuslist trio) since D-04 requires SF/OFFSET fields and those live in the processing-param files, not the acquisition files — without this, SF/OFFSET would have zero fixture coverage
- `fnmode_f1`'s validator allowed set (`{1,2,4,5,6}`) is defined as module-level constants (`REAL_FNMODES`, `COMPLEX_FNMODES`, `VALID_FNMODES`) in `models/nus.py` specifically so `nus/schedule.py` (plan 03) can import and share them rather than re-deriving a possibly-divergent allowlist

## Deviations from Plan

None - plan executed exactly as written. The interface block's exact field names, TDD behavior list, and acceptance criteria were all implemented and verified as specified.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `models/nus.py`'s `NusAcquisitionParams`/`NusSchedule` contracts are now stable and importable — plans 02/03/05 (params.py, schedule.py, cli/nus.py) can construct and serialize these exact models without ambiguity
- `lucy_ng.nus`/`lucy_ng.nus.backends` package markers exist and are importable — wave-2 plans can add `params.py`, `schedule.py`, `backends/nmrpipe_smile.py` without touching these `__init__.py` files (only the final re-export list, added in plan 05, will touch `nus/__init__.py` again)
- Fixture tree is complete and CI-portable (no binary `ser`) for all three real C20H32O2 NUS experiments — no blockers for plans 02/03

---
*Phase: 97-backend-integration-params-schedule*
*Completed: 2026-07-12*
