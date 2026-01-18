---
phase: 18-prediction-api
plan: 01
type: summary
completed: 2026-01-18
---

# Phase 18-01 Summary: Database-Backed Prediction API

## Accomplishments

### Task 1: Protocol for HOSE Lookup Backends
- Added `HOSELookupProtocol` using `typing.Protocol` with runtime_checkable
- Methods: `lookup_stats_at_radius()`, `has_code_at_radius()`
- Added `HOSEStatsResult` dataclass to models.py (mean, std, count)
- Updated `HOSELookupTable` to implement the protocol

### Task 2: DatabaseHOSELookup Adapter
- Created `DatabaseHOSELookup` class in `db_lookup.py`
- Implements `HOSELookupProtocol` for database-backed lookups
- `from_db_path()` classmethod for convenient instantiation
- O(1) lookup with pre-computed statistics from hose_stats table

### Task 3: C13Predictor Dual-Backend Support
- Updated `__init__` to accept either `HOSELookupTable` or `DatabaseHOSELookup`
- `_predict_for_atom()` uses `lookup_stats_at_radius()` for radius fallback
- `_create_prediction_from_stats()` creates predictions from `HOSEStatsResult`
- Added `from_database()` classmethod factory
- Kept `from_table_file()` for backward compatibility

### Task 4: CLI with Database Option
- Added `--db` option to `lucy predict c13` command
- Backend priority: explicit db → explicit table → auto-detect db → auto-detect table
- Default paths: `data/reference/lucy-ng-derep.db` and `data/reference/hose_nmrshiftdb.json.gz`
- Updated help text and error messages

### Task 5: Database Backend Tests
- 18 new tests added to test_prediction.py:
  - `TestHOSEStatsResult` (2 tests)
  - `TestHOSELookupProtocol` (3 tests)
  - `TestDatabaseHOSELookup` (6 tests)
  - `TestC13PredictorWithDatabase` (4 tests)
  - `TestCLIPredictWithDatabase` (3 tests)
- All using pytest fixtures with temp database

### Task 6: Exports and Documentation
- Exported `DatabaseHOSELookup`, `HOSEStatsResult` from prediction module
- Updated CLAUDE.md with 13C Shift Prediction section
- Documented CLI and Python API usage

## Files Created/Modified

### Created
- `src/lucy_ng/prediction/db_lookup.py` - DatabaseHOSELookup adapter

### Modified
- `src/lucy_ng/prediction/models.py` - Added HOSEStatsResult
- `src/lucy_ng/prediction/lookup.py` - Added HOSELookupProtocol
- `src/lucy_ng/prediction/predictor.py` - Dual-backend support
- `src/lucy_ng/prediction/__init__.py` - New exports
- `src/lucy_ng/cli/predict.py` - --db option
- `tests/test_prediction.py` - 18 new tests
- `CLAUDE.md` - Prediction documentation

## Decisions Made

1. **Protocol pattern**: Used typing.Protocol for interchangeable backends
2. **Database-first**: Auto-detection prefers database over JSON table
3. **Stats vs raw shifts**: Database stores pre-computed stats (mean/std/count) not raw lists
4. **Backward compatibility**: JSON table backend unchanged, from_table_file() preserved
5. **Separate caching keys**: Cache uses different keys for database vs table backends

## Verification Results

All checks pass:
- `pytest tests/test_prediction.py -v` - 46 passed
- `lucy predict c13 "CCO" --db data/reference/lucy-ng-derep.db` - Works
- Manual verification:
  - Ethanol: CH3 ~14.6 ppm, CH2 ~65.6 ppm ✓
  - Benzene: aromatic ~128.6 ppm ✓
  - Acetone: CH3 ~29.2 ppm, C=O ~200.0 ppm ✓

## Next Phase Readiness

Phase 18 complete. Database-backed prediction API ready:
- C13Predictor supports both JSON table and database backends
- CLI has --db option with auto-detection
- All 46 prediction tests passing

**Ready for**: Phase 19 (CLI/MCP Integration) to update MCP tools
