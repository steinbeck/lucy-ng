---
phase: 94-data-tables
plan: 02
subsystem: webview
tags: [fastapi, webview, tables, backend, tdd]

# Dependency graph
requires:
  - phase: 94-01
    provides: TestTablesEndpoint (14 test methods, RED-by-skip) + tables_analysis_dir/tables_iterations_dir fixtures matching the CONTEXT.md LOCKED peaks-JSON schema
provides:
  - src/lucy_ng/webview/routers/tables.py — make_router(analysis_dir) with 5 GET routes
    (/api/tables/{carbon,hsqc,hmbc,cosy,constraints}), all never-500, degrading to
    state=waiting (HTTP 200) on any failure
  - _newest_compound_lsd (prefix-match iteration_(\d+) + mtime tiebreak, family-suffix aware)
  - _extract_inventory_block (webview-local, never-raises sibling of cli/lsd.py's parser)
  - Router docked in app.py::create_app() via lazy import + include_router
affects: [94-03-PLAN.md (frontend — fetches these 5 endpoints and renders into the Tables tab)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "make_router(analysis_dir) -> APIRouter(prefix='/api') factory, mirrors log.py/status.py/structures.py"
    - "Broad except tuple (FileNotFoundError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) for JSON-parsing readers — narrower log.py-style tuple is insufficient"
    - "Prefix-match iteration_(\\d+) regex (no $ anchor) + mtime tiebreak for family-suffixed iteration dirs"
    - "Webview-local reimplementation of cli/lsd.py::_extract_inventory_block — never imports the CLI module (its validator raises SystemExit)"

key-files:
  created:
    - src/lucy_ng/webview/routers/tables.py
  modified:
    - src/lucy_ng/webview/app.py

key-decisions:
  - "Task 1 and Task 2 both edit the same new file (tables.py); committed as two atomic commits by writing the full file once, then temporarily removing the Task-2 (constraints) additions for the first commit and re-adding them for the second — giving each commit an independently-verifiable, meaningful diff rather than an artificial split."
  - "Counts per source: carbon -> {formula, dbe, solvent, count}; hsqc/cosy -> {count}; hmbc -> {kept_count, raw_count} — all .get()-defensive per D-05."
  - "HMBC row `flag` field returned completely unmodified (no reshaping) — colouring is a Plan 03 frontend concern per D-03."

requirements-completed: [TBL-01, TBL-02, TBL-03]

# Metrics
duration: 25min
completed: 2026-07-09
---

# Phase 94 Plan 02: tables.py Router (5 GET routes, never-500) Summary

**New `tables.py` FastAPI router with 5 independent GET routes (carbon/hsqc/hmbc/cosy/constraints), each degrading to `state=waiting` HTTP 200 on any failure — docked into `create_app()`; turns Plan 01's 14-method `TestTablesEndpoint` from SKIP to GREEN.**

## Performance

- **Duration:** 25 min
- **Tasks:** 2 completed
- **Files modified:** 2 (`src/lucy_ng/webview/routers/tables.py` created, `src/lucy_ng/webview/app.py` modified)

## Accomplishments

- `_read_carbon`/`_read_hsqc`/`_read_hmbc`/`_read_cosy` — four peaks-JSON readers mirroring `structures.py`'s broad except-tuple JSON-parse shape (not `log.py`'s narrower one), each returning `{"state","note","counts","rows"}` on success or the waiting tuple on any failure.
- `_newest_compound_lsd` — prefix-match `re.match(r"iteration_(\d+)", name)` (no `$` anchor) across `iteration_*` directories, with `st_mtime` as the tiebreak, correctly selecting `iteration_02_anchor_recovery` over `iteration_01` in the fixture (D-02).
- `_extract_inventory_block` — a webview-local sibling of `cli/lsd.py::_extract_inventory_block()`, reimplemented (not imported) so the router never risks the CLI's `SystemExit`-raising validator; strips the `; ` prefix via a fixed 2-char slice, maps bare `;` lines to `""`, and returns `None` on any malformed/absent block.
- `_read_constraints` — selects the newest `compound.lsd`, extracts and `json.loads`-parses the inventory block, returns `{"state":"ok","note","inventory"}` or the waiting payload; never raises.
- `make_router(analysis_dir) -> APIRouter(prefix="/api")` registering all 5 routes, docked into `app.py::create_app()` via one lazy import + one `include_router` line, matching the existing 3-router convention; module docstring extended with all 5 new routes.

## Task Commits

Each task was committed atomically:

1. **Task 1: 4 peaks routes (carbon/hsqc/hmbc/cosy) + app.py docking** - `a7c9399` (feat)
2. **Task 2: /api/tables/constraints (highest-iteration LSD inventory parse)** - `f9a7467` (feat)

## Files Created/Modified

- `src/lucy_ng/webview/routers/tables.py` (NEW) — `make_router` + 5 route handlers + 6 internal helpers
- `src/lucy_ng/webview/app.py` — one lazy import + one `include_router` line + docstring route list extended

## Decisions Made

- Both tasks touch the identical new file with content that logically layers on top of each other (Task 2's constraints route/helpers are appended after Task 1's peaks routes). To preserve atomic, independently-verifiable per-task commits (rather than one combined commit as Plan 01 did for a tightly-coupled fixture+test pair), the full implementation was written once, then the Task-2 additions were temporarily removed, Task 1's subset was verified (5 tests + ruff + mypy) and committed, and the Task-2 additions were restored, verified (3 tests + full 14-method class + ruff + mypy), and committed separately.
- Per-source `counts` fields follow D-05 exactly: carbon exposes `formula`/`dbe`/`solvent`/`count`; hsqc/cosy expose `count`; hmbc exposes `kept_count`/`raw_count` — all read with `.get()` defensively since the schema documents `additionalProperties: true` in practice (real LSD inventory files carry extra undocumented keys per RESEARCH.md).
- HMBC rows are returned as-is from `data.get("peaks", [])` with no reshaping — the `flag` value (`ok`/`potential_4J`/`1J_artifact`) passes through byte-for-byte; per D-03 colouring is entirely a Plan 03 frontend concern.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' acceptance criteria are met verbatim: the broad except tuple is used for all 4 peaks readers, the prefix-match regex (no `$` anchor) plus mtime tiebreak is used for iteration selection, the inventory parser is a local reimplementation (never imports `cli.lsd`), and the full `TestTablesEndpoint` class (14/14) is green.

## Issues Encountered

- `mypy src/lucy_ng` reports 66 pre-existing errors across 19 unrelated files (`prediction/stats_generator.py`, `lsd/generator.py`, `lsd/orchestrator.py`, `ranking/ranker.py`, etc.) — none are in `webview/routers/tables.py` or `webview/app.py` (confirmed via `grep -i webview` on the mypy output, which returned nothing). Out of scope per the executor's scope-boundary rule; not touched.
- `ruff check src tests` (whole-tree) reports 282 pre-existing errors, including the E501 at `tests/test_webview_api.py:293` already logged in Plan 01's `deferred-items.md`. `ruff check` scoped to this plan's two changed files (`tables.py`, `app.py`) reports zero errors — confirmed separately.
- A loose grep pattern in the plan's own acceptance criteria (`grep -c "cli.lsd\|cli import lsd"`) matches 1 line — but that line is the docstring comment `Webview-local sibling of cli/lsd.py::_extract_inventory_block`, not an actual import statement (the `.` in the grep pattern matches the `/` in `cli/lsd.py`). Confirmed via `grep -n "^import\|^from"` that no import of `lucy_ng.cli.lsd` (or `cli import lsd`) exists anywhere in the file — the acceptance intent (no coupling to the SystemExit-raising CLI validator) is fully satisfied.

## Verification Output

```
$ pytest tests/test_webview_api.py::TestTablesEndpoint -q
======================= 14 passed, 26 warnings in 0.21s =======================

$ pytest tests/test_webview_api.py -q
======================= 35 passed, 26 warnings in 0.36s =======================

$ ruff check src/lucy_ng/webview/routers/tables.py src/lucy_ng/webview/app.py
All checks passed!

$ mypy src/lucy_ng 2>&1 | grep -i webview
(no output — zero errors attributable to the webview package)

$ grep -n "^import\|^from" src/lucy_ng/webview/routers/tables.py
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any
from fastapi import APIRouter
(confirms: no import of lucy_ng.cli.lsd)
```

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 5 `/api/tables/*` routes are implemented and green; `TestTablesEndpoint` (14/14) passes.
- Plan 03 (frontend) can now fetch these 5 endpoints and render into the Tables tab placeholder from Phase 93, following the `buildTable`/`appendInline`/fetch-poll patterns documented in 94-PATTERNS.md.
- No blockers.

---
*Phase: 94-data-tables*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: src/lucy_ng/webview/routers/tables.py
- FOUND: .planning/phases/94-data-tables/94-02-SUMMARY.md
- FOUND: a7c9399 (commit exists in git log)
- FOUND: f9a7467 (commit exists in git log)
- FOUND: a4b0b3d (commit exists in git log)
