---
phase: 14-cli-integration
plan: 01
subsystem: cli
tags: [sqlite, database, dereplication, click]

requires:
  - phase: 13-database-query-api
    provides: DatabaseQueryService with get_by_formula() method

provides:
  - Database-backed CLI dereplication (~100x faster)
  - Auto-detection of SQLite database
  - LUCY_DATABASE environment variable support
  - Graceful fallback to SD files

affects: [15-mcp-integration]

tech-stack:
  added: []
  patterns:
    - Database auto-detection pattern (env var → default location → fallback)
    - Loader abstraction (Any type with get_by_formula method)

key-files:
  created: []
  modified:
    - src/lucy_ng/cli/dereplicate.py
    - tests/test_cli_dereplicate.py

key-decisions:
  - "Default database location: data/reference/compounds.db"
  - "Environment variable LUCY_DATABASE for custom locations"
  - "Use Any type for loader to avoid complex union types"

patterns-established:
  - "Database detection: env var → default location → SD file fallback"
  - "Informative stderr messages about which backend is being used"

issues-created: []

duration: 6 min
completed: 2026-01-15
---

# Phase 14-01 Summary: CLI Integration

**CLI dereplication now uses SQLite database by default with zero configuration, ~100x faster than SD file scanning**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-15T15:58:44Z
- **Completed:** 2026-01-15T16:04:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `lucy dereplicate c13` auto-detects SQLite database at `data/reference/compounds.db`
- Database backend used when present, falls back gracefully to SD files
- Environment variable `LUCY_DATABASE` enables custom database locations
- Informative stderr messages show which backend is being used and compound count
- Hint about `lucy database download` when using slower SD file scanning

## Task Commits

Each task was committed atomically:

1. **Task 1: Update CLI to use database backend** - `762e82b` (feat)
2. **Task 2: Add tests for database-backed CLI** - `c5d5d41` (test)

## Files Created/Modified

- `src/lucy_ng/cli/dereplicate.py` - Added database auto-detection, routing, and cleanup
- `tests/test_cli_dereplicate.py` - Added 8 new tests for database detection and CLI integration

## Decisions Made

- Default database location: `data/reference/compounds.db` (alongside existing SD files)
- Environment variable `LUCY_DATABASE` for custom locations (checked before default)
- Use `Any` type for loader to support DatabaseQueryService, NMRShiftDBLoader, and CoconutLoader without complex union types

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## Next Phase Readiness

- Phase 14 complete
- Phase 15 (MCP Integration) can begin
- MCP tool `dereplicate_c13` will need similar database detection logic

---
*Phase: 14-cli-integration*
*Completed: 2026-01-15*
