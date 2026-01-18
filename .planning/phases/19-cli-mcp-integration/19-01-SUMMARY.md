---
phase: 19-cli-mcp-integration
plan: 01
type: summary
completed: 2026-01-18
---

# Phase 19-01 Summary: CLI/MCP Integration for Database Prediction

## Accomplishments

### Task 1: Update _get_predictor Helper
- Updated MCP server's `_get_predictor()` helper to prefer database
- Backend priority matches CLI: explicit db → explicit table → auto-detect db → auto-detect table
- Caching with separate keys for database vs table backends
- Graceful fallback when no backend available

### Task 2: Update predict_c13_shifts MCP Tool
- Added `db_path` parameter (preferred over table_path)
- Kept `table_path` for backward compatibility
- Updated docstring with database info (~7.9M stats from 895K compounds)
- Updated error message to recommend `lucy database download`

### Task 3: New get_hose_stats_info MCP Tool
- Returns database availability and statistics for AI agents
- Fields: available, db_path, total_stats, compound_count, description
- Useful for agents to check prediction capability before using
- Handles missing database gracefully with helpful error message

### Task 4: MCP Tests
- 6 new tests added to TestPredictionTools class:
  - `test_predict_c13_shifts_with_db` - explicit database
  - `test_predict_c13_shifts_auto_detect` - auto-detection
  - `test_predict_c13_shifts_invalid_smiles` - error handling
  - `test_get_hose_stats_info_with_db` - stats retrieval
  - `test_get_hose_stats_info_auto_detect` - auto-detection
  - `test_get_hose_stats_info_not_found` - missing database

## Files Modified

- `src/lucy_ng/mcp/server.py` - Updated _get_predictor, predict_c13_shifts, added get_hose_stats_info
- `tests/test_mcp_server.py` - Added TestPredictionTools class with 6 tests

## Decisions Made

1. **Database-first for MCP**: Same priority as CLI for consistency
2. **New info tool**: get_hose_stats_info lets agents check before predicting
3. **Backward compatibility**: table_path parameter still works
4. **Descriptive errors**: Error messages guide users to database download

## Verification Results

All checks pass:
- `pytest tests/test_mcp_server.py::TestPredictionTools -v` - 6 passed
- MCP tools work with database backend
- Auto-detection prefers database when available

## Milestone Completion

Phase 19 completes the v1.2 HOSE Database Prediction milestone:
- Phase 16: Schema Migration ✅
- Phase 17: HOSE Generation ✅
- Phase 18: Prediction API ✅
- Phase 19: CLI/MCP Integration ✅

**Milestone deliverables:**
- 7.9M HOSE statistics from 895K compounds
- DatabaseHOSELookup adapter for database-backed predictions
- C13Predictor with dual-backend support (JSON table or database)
- CLI --db option with auto-detection
- MCP get_hose_stats_info tool for agents
- 633 tests all passing
