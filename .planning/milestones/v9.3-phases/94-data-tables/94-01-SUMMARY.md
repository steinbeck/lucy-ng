---
phase: 94-data-tables
plan: 01
subsystem: testing
tags: [fastapi, pytest, tdd-scaffold, webview, tables]

# Dependency graph
requires:
  - phase: 93-formatted-log-tab-framework
    provides: Tables tab placeholder in index.html, tab navigation, XSS-discipline test precedent
provides:
  - Hand-authored tables_analysis_dir/tables_iterations_dir pytest fixtures matching the
    CONTEXT.md LOCKED peaks-JSON schema (carbon_signals/hsqc/hmbc/cosy) and a multi-iteration
    compound.lsd set (family-suffixed dir exercising D-02 selection)
  - TestTablesEndpoint (14 test methods) as the executable acceptance target for Plan 02's
    tables.py router — RED-by-skip until tables.py exists
affects: [94-02-PLAN.md (tables.py router — must satisfy this test class), 94-03-PLAN.md (frontend)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "WV-08 import-safety: fastapi/router imports inside test bodies, try/except ImportError: pytest.skip"
    - "Hand-authored fixtures for a locked target schema not yet produced by any real on-disk run"

key-files:
  created: []
  modified:
    - tests/test_webview_api.py

key-decisions:
  - "Fixtures built by hand to CONTEXT.md's canonical_refs schema, not copied from any real analysis/ dir (RESEARCH.md Assumptions A1-A5 — no on-disk file matches the target schema)."
  - "Task 1 (fixtures) and Task 2 (TestTablesEndpoint) committed as a single commit — both edit the identical file with directly dependent content (test class calls the fixtures added moments earlier); splitting the diff would require reconstructing an artificial intermediate file state with no verification value."

patterns-established:
  - "TestTablesEndpoint mirrors TestStatusEndpoint/TestLogEndpoint/TestStructuresEndpoint exactly: try/except ImportError guard, FastAPI() + include_router(make_router(dir)), TestClient context manager."

requirements-completed: [TBL-01, TBL-02, TBL-03]

# Metrics
duration: 4min
completed: 2026-07-09
---

# Phase 94 Plan 01: Wave-0 Test Scaffold Summary

**Hand-authored CONTEXT.md-schema fixtures + a 14-method TestTablesEndpoint class that collects and SKIPs cleanly (never ImportError/FAILED) ahead of the Plan-02 `tables.py` router.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-09T08:12:58Z
- **Completed:** 2026-07-09T08:16:31Z
- **Tasks:** 2 completed
- **Files modified:** 1 (`tests/test_webview_api.py`)

## Accomplishments
- `tables_analysis_dir` fixture — hand-authored `peaks/{carbon_signals,hsqc,hmbc,cosy}.json` matching the CONTEXT.md LOCKED schema exactly (field names, one row per HMBC flag value, one `5559614` intensity value for the downstream compact-format target).
- `tables_iterations_dir` fixture — `iteration_01/compound.lsd` (bare) + `iteration_02_anchor_recovery/compound.lsd` (family-suffixed, higher numeric prefix), each with a real-shaped CONSTRAINT INVENTORY v2 block, to exercise the D-02 "highest iteration_(\d+), across families" selection logic.
- `TestTablesEndpoint` — 14 test methods covering TBL-01/02/03 and independently proving SC4 (absent + malformed → `state="waiting"`, HTTP 200, never 500) for all 5 panels (carbon, hsqc, hmbc, cosy, constraints).
- Verified the whole file collects cleanly and all 14 new methods report SKIPPED (not FAILED/ERROR) while `tables.py` is absent — confirming the WV-08 RED-by-skip contract.
- Verified the existing 21-test suite in this file is unaffected (21 passed, 14 skipped).

## Task Commits

Each task was committed atomically:

1. **Task 1 + Task 2 combined: fixtures + TestTablesEndpoint** - `aa70ae9` (test)

**Plan metadata:** (pending — see final commit below)

_Note: Tasks 1 and 2 both modify the identical file with directly dependent content (Task 2's
test methods call the fixtures Task 1 defines); they were committed together as a single `test`
commit rather than split into two commits against an artificial intermediate file state. See
Deviations below._

## Files Created/Modified
- `tests/test_webview_api.py` - Added `tables_analysis_dir`/`tables_iterations_dir` fixtures and `TestTablesEndpoint` (14 methods)

## Decisions Made
- Fixtures hand-authored strictly to CONTEXT.md's `<canonical_refs>` field names — no on-disk `analysis/` directory was used as a template, per RESEARCH.md Assumptions A1-A5 (no real run on this machine currently matches the exact locked schema).
- `_newest_compound_lsd`-style selection is exercised via `iteration_02_anchor_recovery` (numeric prefix 2) vs. bare `iteration_01` (numeric prefix 1) — Plan 02's router must select iteration 2.

## Deviations from Plan

**1. [Process note, not a Rule 1-4 deviation] Combined Task 1 + Task 2 into one commit**
- **Found during:** Task 2 (writing TestTablesEndpoint)
- **Issue:** Both tasks specified `files: tests/test_webview_api.py` and Task 2's test methods directly reference the fixtures Task 1 defines in the same file. There is no natural intermediate git state between "fixtures only" and "fixtures + test class" that would represent real, independently-verifiable progress — Task 1 alone doesn't exercise anything (fixtures aren't called until Task 2's tests reference them).
- **Fix:** Wrote both in a single Edit, committed once as `test(94-01): Wave-0 TestTablesEndpoint scaffold + hand-authored fixtures`.
- **Files modified:** tests/test_webview_api.py
- **Committed in:** `aa70ae9`

---

**Total deviations:** 1 process note (commit granularity only — no code/behavior deviation).
**Impact on plan:** None on scope or correctness; both tasks' acceptance criteria are fully met by the single commit.

## Issues Encountered
- A pre-existing `ruff` E501 (line too long) at `tests/test_webview_api.py:293`, inside `TestStructuresEndpoint::test_malformed_smiles_returns_placeholder_svg` (introduced in Phase 93, commit `0c1a8b8`), is unrelated to this plan's changes. Per the executor's scope-boundary rule, this was left unfixed and logged to `.planning/phases/94-data-tables/deferred-items.md` rather than auto-fixed. `ruff check` on the code added by this plan (the new fixtures + `TestTablesEndpoint`) is clean.

## Verification Output

```
$ pytest tests/test_webview_api.py::TestTablesEndpoint -x -q
collected 14 items
tests/test_webview_api.py ssssssssssssss                                 [100%]
======================= 14 skipped, 26 warnings in 0.28s =======================

$ ruff check tests/test_webview_api.py
E501 Line too long (106 > 100)
   --> tests/test_webview_api.py:293:101   (pre-existing, unrelated to this plan — see Issues Encountered)
Found 1 error.

$ pytest tests/test_webview_api.py -q
================= 21 passed, 14 skipped, 26 warnings in 0.38s ==================

$ python -c "import ast; ast.parse(open('tests/test_webview_api.py').read()); print('parse-ok')"
parse-ok
```

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `TestTablesEndpoint` is now the fixed, executable acceptance target for Plan 02 (`tables.py` router implementation) — Plan 02 must make all 14 methods pass (not skip) by implementing `src/lucy_ng/webview/routers/tables.py` with `make_router(analysis_dir) -> APIRouter`.
- No blockers. `ruff`'s one pre-existing unrelated error (line 293) does not block Plan 02.

---
*Phase: 94-data-tables*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: tests/test_webview_api.py
- FOUND: .planning/phases/94-data-tables/94-01-SUMMARY.md
- FOUND: aa70ae9 (commit exists in git log)
