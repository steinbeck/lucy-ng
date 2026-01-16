---
phase: 17-hose-generation
plan: 01
type: summary
completed: 2026-01-16
---

# Phase 17-01 Summary: HOSE Generation Infrastructure

## Accomplishments

### Task 1: Compound Iteration Method
- Added `iter_compounds_with_shifts()` to DatabaseManager
- Memory-efficient iterator using `fetchmany()` with configurable batch size
- Yields `(compound_id, smiles, [(atom_index, shift_ppm), ...])` tuples
- Skips compounds without SMILES or without shifts
- 4 tests covering iteration, filtering, and batch processing

### Task 2: HOSEStatsGenerator Service
- Created `HOSEStatsGenerator` class for batch HOSE code generation
- `generate_all()`: Iterates compounds, generates HOSE codes at radii 1-N, aggregates shifts
- `compute_stats()`: Converts aggregates to HOSEStatsRecord (mean, std, count)
- `populate_database()`: Full pipeline with batch insertion
- Statistics tracking: compounds_processed, compounds_failed, shifts_processed
- Progress bar via tqdm
- Graceful error handling for invalid SMILES, invalid atom indices, None indices
- 11 tests covering core functionality and edge cases

### Task 3: CLI Command
- Added `lucy database generate-hose-stats` command
- Options: `--db PATH`, `--max-radius INT`, `--batch-size INT`
- Progress bar during generation
- Reports final statistics: stats generated, compounds processed, failures, time
- 6 CLI tests

## Files Created/Modified

### Created
- `src/lucy_ng/prediction/stats_generator.py` - HOSEStatsGenerator class
- `tests/test_hose_stats_generator.py` - 11 tests
- `tests/test_cli_database.py` - 6 CLI tests

### Modified
- `src/lucy_ng/database/manager.py` - Added iter_compounds_with_shifts()
- `src/lucy_ng/prediction/__init__.py` - Export HOSEStatsGenerator
- `src/lucy_ng/cli/database.py` - Added generate-hose-stats command
- `tests/test_database.py` - 4 iteration tests

## Decisions Made

1. **Memory-efficient iteration**: Used fetchmany() to avoid loading all 895K compounds at once
2. **Aggregation strategy**: Collect shifts per (hose_code, radius) key, then compute stats once
3. **Error handling**: Skip failures gracefully rather than abort; report count at end
4. **Single observation handling**: std=0.0 when count=1 (can't compute variance)
5. **INSERT OR REPLACE**: Enables idempotent reruns of generation

## Verification Results

All checks pass:
- `pytest tests/test_database.py -v` - 45 passed
- `pytest tests/test_hose_stats_generator.py -v` - 11 passed
- `pytest tests/test_cli_database.py -v` - 6 passed
- `lucy database generate-hose-stats --help` - Shows correct usage
- mypy: Only pre-existing tqdm stubs issue (no new errors)

## Commits

1. `c016ad9` - feat(17-01): add iter_compounds_with_shifts to DatabaseManager
2. `dd7ddc3` - feat(17-01): create HOSEStatsGenerator service
3. `741401c` - feat(17-01): add generate-hose-stats CLI command

## Next Phase Readiness

Phase 17-01 is complete. The infrastructure for HOSE generation is ready:
- DatabaseManager can iterate compounds with shifts
- HOSEStatsGenerator can process compounds and generate statistics
- CLI command can run batch generation on the full database

**Ready for**: Running `lucy database generate-hose-stats` on the production database (895K compounds) to populate hose_stats table. This is an operational step, not a development task.

**Phase 18 prerequisite met**: Once hose_stats is populated, Phase 18 (Prediction API) can query the table for shift predictions.
