---
phase: 15-mcp-integration
plan: 01
subsystem: mcp
tags: [sqlite, database, dereplication, fastmcp]

requires:
  - phase: 13-database-query-api
    provides: DatabaseQueryService with get_by_formula() method
  - phase: 14-cli-integration
    provides: Database detection helpers (_find_database_path, _is_sqlite_database)

provides:
  - Database-backed MCP dereplication (~100x faster)
  - Auto-detection of SQLite database in MCP tools
  - database_type and compound_count in return values
  - Graceful fallback to SD files

affects: []

tech-stack:
  added: []
  patterns:
    - Reuse CLI helpers in MCP layer
    - database_type field for backend transparency

key-files:
  created: []
  modified:
    - src/lucy_ng/mcp/server.py
    - tests/test_mcp_server.py

key-decisions:
  - "Reuse _find_database_path and _is_sqlite_database from CLI module"
  - "Add database_type field for agent transparency about backend used"
  - "Add compound_count field when using SQLite database"

patterns-established:
  - "MCP tools reuse CLI module helpers for consistent behavior"
  - "Return database_type to inform agents about backend performance"

issues-created: []

duration: 5 min
completed: 2026-01-15
---

# Phase 15-01 Summary: MCP Integration

**MCP `dereplicate_c13` tool now auto-detects SQLite database for ~100x faster dereplication, with database_type field for agent transparency**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-15T16:16:12Z
- **Completed:** 2026-01-15T16:22:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- MCP `dereplicate_c13` auto-detects SQLite database at `data/reference/compounds.db`
- Database backend used when present, falls back gracefully to SD files
- Returns `database_type` field ("sqlite", "nmrshiftdb_sd", or "coconut_sd") for agent transparency
- Returns `compound_count` when using SQLite database
- Reuses CLI helper functions for consistent behavior across interfaces

## Task Commits

Each task was committed atomically:

1. **Task 1: Update MCP dereplicate_c13 to use database backend** - `1b2545c` (feat)
2. **Task 2: Add tests for database-backed MCP tool** - `de12f54` (test)

## Files Created/Modified

- `src/lucy_ng/mcp/server.py` - Added database auto-detection, routing, and cleanup
- `tests/test_mcp_server.py` - Added 6 new tests for database detection and MCP integration

## Decisions Made

- Reuse `_find_database_path()` and `_is_sqlite_database()` from CLI module rather than duplicating logic
- Add `database_type` field to help AI agents understand which backend is being used (affects performance expectations)
- Add `compound_count` field when using SQLite database (helps agents understand coverage)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## Milestone Complete

v1.1 Database-Backed Dereplication milestone is complete:
- Phase 11: Database Schema ✓
- Phase 12: Database Import ✓
- Phase 13: Database Query API ✓
- Phase 14: CLI Integration ✓
- Phase 15: MCP Integration ✓

---
*Phase: 15-mcp-integration*
*Completed: 2026-01-15*
