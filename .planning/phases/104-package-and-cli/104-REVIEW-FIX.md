---
phase: 104-package-and-cli
fixed_at: 2026-10-04T09:32:43Z
review_path: .planning/phases/104-package-and-cli/104-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 104: Code Review Fix Report

**Fixed at:** 2026-10-04T09:32:43Z
**Source review:** .planning/phases/104-package-and-cli/104-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (fix_scope: critical_warning — WR-01, WR-02; the three Info findings
  IN-01/IN-02/IN-03 were out of scope for this run)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Dual-filename precedence inversion in `identity.py`'s untested import-fallback path

**Files modified:** `src/ailsa/identity.py`, `tests/test_identity_resolve_fallback.py`
**Commit:** `16f1d8a`
**Applied fix:** Swapped the loop nesting in `_resolve_db_path()`'s Dropbox-dev-tier fallback
(reachable only when `from ailsa.database.finder import DatabaseFinder` itself raises) from
`for project_dir: for name` to `for name: for project_dir`, matching
`DatabaseFinder.find_derep_database()`'s own tier 5 exactly, as the REVIEW.md fix suggested. Added
a new regression test (`test_identity_resolve_fallback.py`) that forces the import failure via
`sys.modules["ailsa.database.finder"] = None`, lays out the cross-matched directory layout from
the finding (legacy name in one project dir, new name in the other), and asserts the new-named
file wins. Verified the test fails against the pre-fix loop ordering (returns the legacy file)
and passes against the fix.

### WR-02: `cli/fragment.py` duplicates (and narrows) `DatabaseFinder`'s dual-filename logic

**Files modified:** `src/ailsa/database/finder.py`, `src/ailsa/cli/fragment.py`,
`tests/test_cli_database.py`
**Commit:** `53e889a`
**Applied fix:** Extracted `DatabaseFinder`'s location-tier search and narrow "prefer new, fall
back to legacy, else new" logic into two generic, name-parameterized static methods —
`find_database(names)` (full tier search: `data/reference/`, `~/.lucy/`,
`~/<project>/data/reference/`, `~/.local/share/<project>/`, mdfind, `~/Dropbox/develop/<project>/
...`) and `resolve_default_path(new_name, legacy_name)` (narrow: `data/reference/` only, for
output-path defaults). `find_derep_database()` and `resolve_default_derep_path()` now delegate to
these generic helpers instead of inlining the logic.

`cli/fragment.py` gets two resolvers built on the generic helpers: the existing
`resolve_default_fragments_db()` (used only by `fragment build`'s output-path default, where
narrow `data/reference/`-only semantics are correct — matching `database download`'s own narrow
default) now delegates to `DatabaseFinder.resolve_default_path()`; a new
`find_default_fragments_db()` (used by `fragment info`/`search`'s find-an-existing-DB lookups)
delegates to the full `DatabaseFinder.find_database()` tier search, giving those two commands the
same location coverage `database info` gets for the derep DB. `fragment build`'s behaviour and
the explicit-second-positional-argument path are unchanged.

Added two regression tests to `TestFragmentDualFilename` placing a legacy-named fragments DB
under `~/.lucy/` (a tier the old narrow resolver never checked) and asserting `fragment info`/
`fragment search` with no arguments still auto-detect it. Verified both new tests fail against
the pre-fix narrow resolver and pass against the fix. Also manually verified, via the worktree's
own venv against this machine's real `data/reference/`, that `fragment info`/`search`/`build`
with zero arguments still resolve to `data/reference/lucy-ng-fragments.db` exactly as before —
the "new filename wins over legacy filename" invariant holds, and no renaming/moving of the real
DB files occurred.

## Verification

- `uv run pytest tests/test_database_finder.py tests/test_cli_database.py
  tests/test_cli_deprecated_alias.py -q`: 32 passed, 0 failed.
- `uv run mypy src/ailsa`: 119 errors (pre-existing baseline on this checkout; unchanged by
  either fix — not the 33 cited in the task config, which appears to be a stale/narrower baseline
  figure; verified no *new* errors were introduced by diffing the error count before/after each
  fix).
- `uv run ruff check src tests`: 278 errors (matches the stated baseline exactly; unchanged by
  either fix).
- No data files under `data/reference/` were renamed, moved, or deleted.

---

_Fixed: 2026-10-04T09:32:43Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
