---
phase: 13-database-query-api
plan: 01
type: summary
---

# Phase 13-01 Summary: Database Query API

## Objective
Implement query interface for formula-based compound lookup that integrates with existing dereplication infrastructure.

## Completed Tasks

### Task 1: Database Query Module ✓
Created `src/lucy_ng/database/query.py` with:
- **DatabaseQueryService**: Main class for database queries
  - `get_by_formula()`: Query by exact molecular formula
  - `get_by_formulas_batch()`: Efficient batch queries
  - `get_compound_count()`: Total compounds
  - `get_formula_count()`: Unique formulas
  - `compound_to_entry()`: Convert CompoundRecord to NMRShiftDBEntry
- Context manager support for connection management
- Conversion of `ShiftRecord.hydrogen_count` (int) to `HydrogenCount` enum
- Property access pattern matching `NMRShiftDBLoader` interface

### Task 2: Module Exports ✓
Updated `src/lucy_ng/database/__init__.py`:
- Export `DatabaseQueryService`

### Task 3: Tests ✓
Created `tests/test_database_query.py` with 13 unit tests:
- **TestCompoundConversion**: Basic conversion, shifts to signals, hydrogen count mapping, default values
- **TestDatabaseQueryService**: Empty DB, single/multiple results, batch queries, formula normalization, context manager, error handling, counts

## Verification Results
- ✅ `python -c "from lucy_ng.database import DatabaseQueryService"` succeeds
- ✅ `pytest tests/test_database_query.py -v` - 13 tests pass
- ✅ `ruff check` - no linting errors
- ✅ `mypy` - no type errors

## Files Created/Modified
- `src/lucy_ng/database/query.py` (new)
- `src/lucy_ng/database/__init__.py` (modified - exports)
- `tests/test_database_query.py` (new)
- `.planning/phases/13-database-query-api/13-01-PLAN.md` (new)

## Commits
1. `0399ae9` - feat(13-01): add DatabaseQueryService for formula-based compound lookup

## Usage Examples

```python
from lucy_ng.database import DatabaseQueryService

# Query single formula
with DatabaseQueryService("compounds.db") as query:
    candidates = query.get_by_formula("C13H18O2")
    for entry in candidates:
        print(f"{entry.name}: {entry.shifts}")

# Batch query
with DatabaseQueryService("compounds.db") as query:
    results = query.get_by_formulas_batch(["C10H12O2", "C13H18O2"])
    for formula, entries in results.items():
        print(f"{formula}: {len(entries)} candidates")

# Use with existing SpectrumMatcher
from lucy_ng.dereplication.matcher import SpectrumMatcher, ObservedPeak

with DatabaseQueryService("compounds.db") as query:
    candidates = query.get_by_formula("C13H18O2")
    matcher = SpectrumMatcher()
    observed = [ObservedPeak(shift=s) for s in [15.1, 22.4, 30.5]]
    results = matcher.match_all(observed, candidates)
```

## Design Notes

- `DatabaseQueryService.get_by_formula()` returns `list[NMRShiftDBEntry]` for full compatibility with existing `SpectrumMatcher`
- The existing `NMRShiftDBLoader` is preserved for backward compatibility with direct SD file access
- Phase 14 will update CLI to use database by default with fallback to SD files

## Next Steps
Phase 14: CLI Integration
- Update `lucy dereplicate c13` to use database backend
- Database path configuration (default location, env var, CLI flag)
- Fallback behavior if database not built
