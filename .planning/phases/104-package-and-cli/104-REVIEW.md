---
phase: 104-package-and-cli
reviewed: 2026-10-03T13:27:16Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - src/ailsa/cli/main.py
  - src/ailsa/cli/__init__.py
  - src/ailsa/cli/__main__.py
  - src/ailsa/webview/server.py
  - src/ailsa/database/finder.py
  - src/ailsa/identity.py
  - src/ailsa/cli/database.py
  - src/ailsa/cli/fragment.py
  - pyproject.toml
  - .gitignore
  - tests/test_cli_deprecated_alias.py
  - tests/test_webview_launcher.py
  - tests/test_database_finder.py
  - tests/test_cli_database.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 104: Code Review Report

**Reviewed:** 2026-10-03T13:27:16Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

This phase mechanically renames the `lucy_ng` package to `ailsa`, adds a deprecated `lucy`
console-script alias, teaches the webview launcher to prefer `ailsa` over a stale `lucy` binary,
and gives dereplication/fragment DB lookup dual-filename (new-wins) backward compatibility. I
read every listed file in full, re-derived the pre-rename baseline via `git show 6c50104:...`
for each one to separate "newly introduced in this phase" from "carried forward unchanged," ran
the actual test suite (`tests/test_cli_deprecated_alias.py`, `test_webview_launcher.py`,
`test_database_finder.py`, `test_cli_database.py` — 30 passed, 4 skipped, none failed), verified
the `ailsa`/`lucy` console-script entry points resolve correctly via `importlib.metadata`, and
manually exercised an untested code path (`fragment build`'s explicit second positional
argument) to confirm it isn't silently overridden by the new default-resolution logic.

The rename itself is clean: a full case-insensitive grep of `src/` for stray "lucy" turned up
only the deliberately-protected categories (legacy DB filenames, `~/.lucy`, `LUCY_*` env vars,
the `lucy` alias's own identifiers) plus two leftover module docstrings that the mechanical
rewrite missed (listed under Info). No security issues, no behavioral regressions in the
explicitly-tested alias/launcher/dual-filename paths, and the packaging metadata
(`project.scripts`, wheel `artifacts`, new sdist `include`) is internally consistent and
mechanically correct.

The two real findings are both about an asymmetry introduced in this phase, not about the
primary derep-DB dual-filename logic (which is correct, well-tested, and matches its own
documented invariant): (1) the untested `ailsa.database.finder` import-failure fallback inside
`identity.py` orders its Dropbox-tier search loop differently from `DatabaseFinder`'s own tier
5, inverting the "new name always wins" guarantee it exists to preserve; (2) `cli/fragment.py`
hand-rolls its own copy of the dual-filename resolver instead of reusing/extending
`DatabaseFinder`, with narrower location coverage than the derep-DB path gets, and no test
exercises the corresponding `fragment search`/`fragment build` default-resolution branches
(only `fragment info`'s is tested).

## Warnings

### WR-01: Dual-filename precedence inversion in `identity.py`'s untested import-fallback path

**File:** `src/ailsa/identity.py:62-74`
**Issue:** `_resolve_db_path()`'s fallback (taken only when `from ailsa.database.finder import
DatabaseFinder` itself raises, `# pragma: no cover`) is meant to mirror `DatabaseFinder`'s
search tiers inline. For the `data/reference` tier it correctly loops `for name in (new,
legacy)` so the new name wins. But for the Dropbox-dev tier it loops the opposite way:

```python
for project_dir in ("ailsa", "lucy-ng"):      # outer: directory
    for name in ("ailsa-derep.db", "lucy-ng-derep.db"):  # inner: filename
        candidates.append(...)
```

`DatabaseFinder.find_derep_database()`'s own tier 5 (`src/ailsa/database/finder.py:96-102`)
loops the other way — `for name in DB_NAMES: for project_dir in PROJECT_DIR_NAMES:` — so it
tries the new filename across *every* directory before trying the legacy filename in *any*
directory. `identity.py`'s fallback does the opposite: for a given directory it checks both
filenames before moving to the next directory. With a cross-matched layout (e.g.
`~/Dropbox/develop/ailsa/data/reference/lucy-ng-derep.db` existing but
`~/Dropbox/develop/lucy-ng/data/reference/ailsa-derep.db` also existing), this fallback would
return the legacy-named file while `DatabaseFinder` itself would return the new-named file for
the identical layout — a real precedence inversion relative to the "new name always wins"
invariant both places claim to implement. The scenario is contrived and the path is marked
`pragma: no cover` (only reachable if the `ailsa` package itself fails to import), which is why
this is a Warning rather than a Blocker — but it is also completely untested, so nothing would
catch a regression here.
**Fix:** Swap the loop nesting to match `DatabaseFinder`'s tier 5:
```python
for name in ("ailsa-derep.db", "lucy-ng-derep.db"):
    for project_dir in ("ailsa", "lucy-ng"):
        candidates.append(
            Path.home() / "Dropbox" / "develop" / project_dir / "data" / "reference" / name
        )
```

### WR-02: `cli/fragment.py` duplicates (and narrows) `DatabaseFinder`'s dual-filename logic

**File:** `src/ailsa/cli/fragment.py:16-36`
**Issue:** Before this phase, `fragment.py` had a single static `DEFAULT_FRAGMENTS_DB` constant
and no dual-filename handling at all (confirmed via `git show 6c50104:src/lucy_ng/cli/
fragment.py`). This phase adds `resolve_default_fragments_db()`, a hand-written copy of
`DatabaseFinder.resolve_default_derep_path()`'s "prefer new, fall back to legacy, else new"
logic — but scoped to a single location (`data/reference/`), whereas `DatabaseFinder.
find_derep_database()` (used for the derep DB) also searches `~/.lucy/`, `~/<project>/data/
reference/`, `~/.local/share/<project>/`, macOS Spotlight (`mdfind`), and `~/Dropbox/develop/
<project>/...`. The comment at line 18 acknowledges this is deliberately narrower ("not
literally required by PKG-05's wording"), but the result is two independently-maintained
implementations of the same invariant with different coverage: a user whose legacy fragments DB
lives anywhere other than `data/reference/` (e.g. `~/.lucy/lucy-ng-fragments.db`, mirroring
where a legacy derep DB might also live) will NOT get it auto-detected by `fragment info`/
`search`/`build`, even though the equivalent derep-DB layout would be found by `database info`/
`download`. If `DatabaseFinder`'s tiers are ever extended, `fragment.py`'s copy won't follow.
**Fix:** Either extend `DatabaseFinder` with a generic `find_pair(new_name, legacy_name,
project_dir_names=...)` helper that both `resolve_default_derep_path()` and
`resolve_default_fragments_db()` call, or at minimum have `resolve_default_fragments_db()`
delegate to `DatabaseFinder`'s existing tier list instead of re-implementing a subset of it.

## Info

### IN-01: Two leftover "Lucy"-prefixed module docstrings missed by the mechanical rename

**File:** `src/ailsa/cli/nus.py:1`, `src/ailsa/cli/webview.py:1`
**Issue:** Per the required mechanical sanity check (`grep -rniE "\blucy\b" src/` minus the
protected categories), these two module docstrings still read `"""Lucy NUS (Non-Uniform
Sampling) reconstruction CLI commands.` and `"""Lucy webview dashboard server CLI commands.`
respectively — pre-rename capitalized "Lucy" that the ~126-file mechanical rewrite didn't catch
(likely because the regex/sed pass targeted `lucy_ng`/`lucy-ng`/lowercase `lucy` tokens, not the
capitalized prose form). Neither file is in this review's explicit file list, so this is
reported only because the task asked for a project-wide grep sanity check; it is not part of the
depth-standard per-file review above.
**Fix:** `"""ailsa NUS (Non-Uniform Sampling) reconstruction CLI commands.` and `"""ailsa
webview dashboard server CLI commands.` (or capitalize consistently with how other renamed
docstrings read, e.g. "AILSA").

### IN-02: `fragment search`/`fragment build` default-resolution branches are untested

**File:** `tests/test_cli_database.py` (class `TestFragmentDualFilename`, lines 296-320)
**Issue:** The new `TestFragmentDualFilename` class exercises only `fragment info`'s
`resolve_default_fragments_db()` branch (legacy-present and nothing-found cases). The identical
`if click.get_current_context().get_parameter_source(...) == ParameterSource.DEFAULT:` pattern
in `fragment search` (`src/ailsa/cli/fragment.py:176-177`) and `fragment build`
(`src/ailsa/cli/fragment.py:314-315`) has no corresponding test. I manually verified (via a
throwaway `CliRunner` invocation) that `fragment build`'s explicit-argument path is not
accidentally overridden, so there is no evidence of an actual bug — but the dual-filename
contract for two of the three commands that claim to support it is currently unverified by the
test suite.
**Fix:** Add `test_fragment_search_no_db_legacy_present` and
`test_fragment_build_fragment_db_default_legacy_present` analogous to the existing `info` tests.

### IN-03: `database build`'s default output path is inconsistent with `download`/`generate-hose-stats`

**File:** `src/ailsa/cli/database.py:46-52`
**Issue:** `build`'s `--output` defaults to `Path(DatabaseFinder.NEW_DB_NAME)` — i.e.
`ailsa-derep.db` in the **current working directory** — while `download` and
`generate-hose-stats` default to `DatabaseFinder.DEFAULT_DB_PATH` (`data/reference/
ailsa-derep.db`). This predates the rename (confirmed via `git show 6c50104:src/lucy_ng/cli/
database.py`, where `build`'s default was already the bare `lucy-ng-derep.db` while
`DEFAULT_DB_PATH` was already `data/reference/lucy-ng-derep.db`) and is therefore not a defect
introduced by this phase. Noting it here only because a future cleanup pass on this file might
otherwise mistake it for rename fallout.
**Fix:** Out of scope for this phase; flag for a future consistency pass if `database build`'s
defaults are revisited.

---

_Reviewed: 2026-10-03T13:27:16Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
