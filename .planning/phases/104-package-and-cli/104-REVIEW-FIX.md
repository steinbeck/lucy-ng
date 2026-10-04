---
phase: 104-package-and-cli
fixed_at: 2026-10-04T00:00:00Z
review_path: .planning/phases/104-package-and-cli/104-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 4
skipped: 1
status: partial
---

# Phase 104: Code Review Fix Report

**Fixed at:** 2026-10-04T00:00:00Z
**Source review:** .planning/phases/104-package-and-cli/104-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (fix_scope: all — WR-01, WR-02, IN-01, IN-02, IN-03)
- Fixed: 4 (WR-01 and WR-02 were already fixed in a prior run of this phase; IN-01 and IN-02 are
  new in this run)
- Skipped: 1 (IN-03)

## Fixed Issues

### WR-01: Dual-filename precedence inversion in `identity.py`'s untested import-fallback path

**Files modified:** `src/ailsa/identity.py`, `tests/test_identity_resolve_fallback.py`
**Commit:** `16f1d8a` (previously fixed — not redone in this run)
**Applied fix:** Swapped the loop nesting in `_resolve_db_path()`'s Dropbox-dev-tier fallback
(reachable only when `from ailsa.database.finder import DatabaseFinder` itself raises) from
`for project_dir: for name` to `for name: for project_dir`, matching
`DatabaseFinder.find_derep_database()`'s own tier 5 exactly, as the REVIEW.md fix suggested.

### WR-02: `cli/fragment.py` duplicates (and narrows) `DatabaseFinder`'s dual-filename logic

**Files modified:** `src/ailsa/database/finder.py`, `src/ailsa/cli/fragment.py`,
`tests/test_cli_database.py`
**Commit:** `53e889a` (previously fixed — not redone in this run)
**Applied fix:** Extracted `DatabaseFinder`'s location-tier search and narrow "prefer new, fall
back to legacy, else new" logic into two generic, name-parameterized static methods —
`find_database(names)` and `resolve_default_path(new_name, legacy_name)`. `cli/fragment.py` now
delegates to these instead of hand-rolling a narrower copy.

### IN-01: Two leftover "Lucy"-prefixed module docstrings missed by the mechanical rename

**Files modified:** `src/ailsa/cli/nus.py`, `src/ailsa/cli/webview.py`
**Commit:** `1333976`
**Applied fix:** Re-read both module docstrings; they were unchanged since the review
(`"""Lucy NUS (Non-Uniform Sampling) reconstruction CLI commands.` and `"""Lucy webview dashboard
server CLI commands.`). Renamed to lowercase `ailsa`, matching the style already used by the
other renamed CLI modules (`cli/database.py`: "CLI commands for database management.",
`cli/main.py`: "Main CLI entry point for ailsa.", `cli/__init__.py`: "Command-line interface for
ailsa.") rather than the review's alternative all-caps "AILSA" suggestion, since that would have
been inconsistent with every other module in `cli/`. Verified via `ast.parse` (Tier 2) and
re-read (Tier 1); no other text in either docstring changed.

### IN-02: `fragment search`/`fragment build` default-resolution branches are untested

**Files modified:** `tests/test_cli_database.py`
**Commit:** `0b837a5`
**Applied fix:** Re-read `TestFragmentDualFilename` and found the WR-02 fix (commit `53e889a`)
had already added `test_fragment_search_no_argument_finds_db_outside_data_reference` (search,
`~/.lucy/` tier) as a side effect, but `fragment build`'s default-resolution branch
(`resolve_default_fragments_db()`) still had no test, and search's `data/reference/`-local
legacy-present case (the most direct mirror of the existing `fragment info` coverage the
REVIEW.md pointed at) was also missing. Added `test_fragment_search_no_db_legacy_present`
(legacy fragments DB in `data/reference/`, `--shifts` with no `--db` → exit 0, zero results) and
`test_fragment_build_fragment_db_default_legacy_present` (legacy fragments DB in
`data/reference/`, a minimal empty compound DB, `fragment build COMPOUND_DB` with no explicit
`FRAGMENT_DB` → exit 0, reuses the legacy file in place, does not create `ailsa-fragments.db`
alongside it). Both new tests pass; ran
`uv run --extra dev pytest tests/test_cli_database.py -q -k fragment` (6 passed) and the full
required subset (`tests/test_cli_database.py tests/test_database_finder.py`: 25 passed, 4
skipped) as Tier 2 verification.

## Skipped Issues

### IN-03: `database build`'s default output path is inconsistent with `download`/`generate-hose-stats`

**File:** `src/ailsa/cli/database.py:46-52`
**Reason:** The REVIEW.md itself classifies this as pre-existing behaviour, not a defect
introduced by this phase (confirmed against `git show 6c50104:src/lucy_ng/cli/database.py`,
where the same asymmetry already existed under the old names) and explicitly marks it
"Out of scope for this phase; flag for a future consistency pass." Changing `database build`'s
default `--output` path is a user-visible CLI behaviour change unrelated to the rename this
phase is about, so no code change was made here per the task's explicit scope guidance.
**Original issue:** `build`'s `--output` defaults to `Path(DatabaseFinder.NEW_DB_NAME)` (bare
`ailsa-derep.db` in the current working directory) while `download`/`generate-hose-stats`
default to `DatabaseFinder.DEFAULT_DB_PATH` (`data/reference/ailsa-derep.db`).

## Verification

- `uv run --extra dev pytest tests/test_cli_database.py tests/test_database_finder.py -q`: 25
  passed, 4 skipped, 0 failed.
- `uv run --extra dev mypy src/ailsa`: 33 errors — matches the required baseline exactly.
- `uv run --extra dev ruff check src tests`: 278 errors — matches the required baseline exactly
  (not exceeded).
- No files under `data/reference/` were renamed, moved, or deleted.
- All changes committed directly to `master` on the main working tree per this run's explicit
  instructions (no isolated worktree was created for this run).

---

_Fixed: 2026-10-04T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
