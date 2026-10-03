---
phase: 104-package-and-cli
plan: 04
subsystem: database
tags: [click, sqlite, packaging, rename, backward-compat]

# Dependency graph
requires:
  - phase: 104-02
    provides: "The ailsa module/project/CLI-text rename landed: src/ailsa, pyproject.toml name=ailsa, single ailsa = \"ailsa.cli:cli\" console-script entry"
provides:
  - "DatabaseFinder.find_derep_database()/find_hose_database() resolve either ailsa-derep.db or the legacy lucy-ng-derep.db at every search tier (env var, project location, ~/.lucy + ~/ailsa + ~/lucy-ng, mdfind, Dropbox dev path), new name winning when both exist"
  - "DatabaseFinder.resolve_default_derep_path() — the single source of truth CLI defaults use to prefer an existing legacy install over a fresh download"
  - "ailsa database download/info and generate-hose-stats --db all accept the legacy filename at their default path, with an explicit path/--output always honoured as given"
  - "The identical dual-filename treatment for the fragments DB (ailsa-fragments.db / legacy lucy-ng-fragments.db) in cli/fragment.py's info/search/build commands"
affects: [104-05, 104-06, 104-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "click ParameterSource.DEFAULT check before resolving a path-typed option's default, so an explicit user-supplied value is never second-guessed"
    - "Dual-filename default-path resolution: widen each existing search tier's filename check to try the new name first then the legacy name, without adding tiers or changing tier order"

key-files:
  created:
    - tests/test_database_finder.py
  modified:
    - src/ailsa/database/finder.py
    - src/ailsa/identity.py
    - src/ailsa/cli/database.py
    - src/ailsa/cli/fragment.py
    - tests/test_cli_database.py

key-decisions:
  - "Test-isolation bug caught before it could hide behind a false RED: the first draft of tests/test_database_finder.py compared DatabaseFinder's relative-path return value (tier 2/cwd tiers return Path(\"data/reference\")/name, not an absolute path) against an absolute tmp_path-based expected value. Fixed by comparing .resolve()'d paths for every tier that returns a cwd-relative Path, keeping the absolute-returning tiers (home-based, Dropbox-dev) as direct equality checks."
  - "Applied the fragments-DB widening as a discretionary consistency extension (research Pitfall 7 / Assumption A4, reaffirmed by the plan's own purpose statement) since the real 605 MB lucy-ng-fragments.db on this machine has the identical defect and is not covered by PKG-05's literal wording."

patterns-established:
  - "A test asserting a DatabaseFinder-returned Path against an expected absolute Path must resolve() both sides whenever the implementation intentionally returns a cwd-relative Path for a given search tier."

requirements-completed: [PKG-05]

# Metrics
duration: 35min
completed: 2026-10-03
---

# Phase 104 Plan 04: Dual-Filename Database Resolution Summary

**Widened `DatabaseFinder` and the `database`/`fragment` CLI commands so every default-path lookup of the reference databases accepts both the new filenames (`ailsa-derep.db`, `ailsa-fragments.db`) and the legacy ones (`lucy-ng-derep.db`, `lucy-ng-fragments.db`), proven against the real ~4 GB legacy database and ~605 MB legacy fragments file on this machine — nothing renamed, moved, or re-downloaded.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-10-03 (after Plan 03's `dff5591`)
- **Completed:** 2026-10-03
- **Tasks:** 2 completed
- **Files modified:** 5 (4 modified, 1 created)

## Accomplishments

- `DatabaseFinder.find_derep_database()` widened in place: every one of its 5 search tiers (env var, project location, `~/.lucy`/`~/ailsa`/`~/lucy-ng` common locations, `mdfind`, Dropbox dev path) now tries `ailsa-derep.db` first, then `lucy-ng-derep.db`, without adding tiers or changing tier order. `find_hose_database()`'s cwd check got the identical treatment. Added `resolve_default_derep_path()` — the single helper every CLI default now calls, returning the existing new-named file, else the existing legacy-named file, else the new default path.
- `src/ailsa/identity.py`'s import-fallback candidate list (the branch that runs exactly when `DatabaseFinder` itself fails to import) widened with the same name/directory-name cross product, using literals since it cannot import the constants it is a fallback for.
- `ailsa database download` resolves its default `--output` through `resolve_default_derep_path()` via a `click.get_current_context().get_parameter_source("output") == ParameterSource.DEFAULT` check — an existing legacy file short-circuits the "already exists" path exactly as before, and `--force` on a legacy-only install overwrites that file in place rather than creating a second ~4 GB copy under the new name. An explicit `--output` is always honoured and downloads as given (proven with a simulated network failure).
- `ailsa database info` now takes an optional `db_path` argument; with no argument it calls `DatabaseFinder.find_derep_database()` and raises a `click.ClickException` naming both filenames when nothing is found. `generate-hose-stats --db` gets the identical default-resolution treatment.
- Applied the identical widening to the fragments DB (`src/ailsa/cli/fragment.py`): new `NEW_FRAGMENTS_DB_NAME`/`LEGACY_FRAGMENTS_DB_NAME` constants and a `resolve_default_fragments_db()` helper, wired into `info`, `search`, and `build`'s default-path resolution.
- Ten new isolated tests in `tests/test_database_finder.py` (env var, cwd, `Path.home()` and `subprocess.run`/`mdfind` all patched, so the real 3.97 GB database on this machine is never found by accident during the test) plus eight new CLI tests across `TestDatabaseDualFilename`/`TestFragmentDualFilename` in `tests/test_cli_database.py`.
- Regression gate green against the Plan 01 baseline: quick pytest suite `74 failed / 1372 passed / 86 skipped / 1 deselected / 1 xfailed` with the failing-node-ID set byte-identical to baseline (`comm -13` empty); `mypy src/ailsa` 33 errors, `comm -13` empty; `ruff check src tests` 278 findings, `comm -13` empty modulo the same 4 pre-existing shrinking-line false positives Plan 02 already documented. Golden `detect hhb C10H14O2 --format json` stdout stays byte-identical to the Plan 01 golden file.
- Real-data proof on this machine (from the repo root, no args): `database info` prints `Database: data/reference/lucy-ng-derep.db` with the real compound/formula counts; `database download` returns "already exists" with zero network access; `fragment info` prints the real fragment-DB stats. `ls data/reference/` is byte-for-byte unchanged (confirmed via `git status --short`, which showed nothing — the directory is gitignored for `*.db`/`*.sdf`/`*.db.zip`).

## Task Commits

1. **Task 1 RED: failing dual-filename DatabaseFinder tests** - `dd8680c` (test)
2. **Task 1 GREEN: resolve reference DB under both filenames** - `f1146f1` (feat)
3. **Task 2 RED: failing CLI tests for legacy database filenames** - `50a9d3c` (test)
4. **Task 2 GREEN: database/fragment CLI defaults accept legacy filenames** - `0ac22f6` (feat)

_No plan-metadata commit yet; STATE.md/ROADMAP.md updates follow after this summary per the execute-plan workflow._

## Files Created/Modified

- `src/ailsa/database/finder.py` — `NEW_DB_NAME`/`LEGACY_DB_NAME`/`DB_NAMES`/`PROJECT_DIR_NAMES` constants, every search tier widened, new `resolve_default_derep_path()` static method
- `src/ailsa/identity.py` — import-fallback candidate list widened with literal new/legacy filenames and project-dir names
- `src/ailsa/cli/database.py` — `DEFAULT_DB_PATH` now sourced from `DatabaseFinder`; `build --output` defaults to the new filename; `download`/`generate-hose-stats --db` resolve their default via `ParameterSource.DEFAULT` + `resolve_default_derep_path()`; `info`'s `db_path` argument is now optional with auto-detection and a clear error naming both filenames
- `src/ailsa/cli/fragment.py` — `NEW_FRAGMENTS_DB_NAME`/`LEGACY_FRAGMENTS_DB_NAME` constants, `resolve_default_fragments_db()` helper, wired into `info`/`search`/`build`
- `tests/test_database_finder.py` (new) — 10 isolated tests covering all 5 search tiers plus `resolve_default_derep_path()`
- `tests/test_cli_database.py` — `TestDatabaseDualFilename` (A, B, C, D, E, F, H) and `TestFragmentDualFilename` (G), plus a shared `isolated_cwd` fixture

## Decisions Made

- **Test-isolation bug, caught and fixed before it reached the GREEN commit:** the plan's own sketch pattern (mirrored in `104-PATTERNS.md`) compares `DatabaseFinder.find_derep_database()`'s return value directly against an absolute `tmp_path`-based `Path`. Because tiers 2 (project location) and the `find_hose_database()` cwd check intentionally return a path relative to the current working directory (matching the pre-rename behaviour exactly — never widened to return absolute paths), a naive `==` comparison against an absolute expected path fails even when the resolution logic is completely correct. Caught during the first RED run (8/10 tests failed, 2 for the right reason and 6 for this wrong one, once GREEN was implemented 4 of the 8 were still failing on this exact issue). Fixed by comparing `.resolve()`'d paths for every assertion against a tier that is documented to return a cwd-relative `Path`, while keeping direct equality for the home-based and Dropbox-dev tiers (which already return absolute paths since `Path.home()` is absolute).
- **Fragments-DB widening taken up as discretionary scope (D-01, per the plan's own instruction):** PKG-05's literal wording only names the derep DB, but the real 605 MB `lucy-ng-fragments.db` on this machine has the identical single-filename defect, and `104-PATTERNS.md` and the plan's own objective explicitly flag it as a Pitfall-7/Assumption-A4 consistency extension. Implemented with a parallel `resolve_default_fragments_db()` rather than importing `DatabaseFinder`'s derep-specific logic, keeping the two database types independent per the existing `FragmentDatabaseManager` module-docstring invariant ("ZERO imports from `ailsa.database`").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected a test-isolation bug in the RED test file before it could mask the real implementation question**
- **Found during:** Task 1, the first RED run (and again, more subtly, in the first post-GREEN run)
- **Issue:** `tests/test_database_finder.py`'s tests for tiers that return a cwd-relative `Path` (project location, `find_hose_database()`'s bare-cwd check, `resolve_default_derep_path()`) asserted equality against an absolute `tmp_path`-constructed `Path`. Both paths point at the same file on disk but are different `Path` objects, so the assertion fails regardless of whether the underlying resolution logic is correct — a false signal that would have looked like "the widening doesn't work" when the real defect was in the test's own comparison.
- **Fix:** Resolved both sides (`found.resolve() == expected.resolve()`) for every tier documented to return a relative path, leaving direct equality for tiers that return absolute paths (home-based, Dropbox-dev) since those already matched byte-for-byte.
- **Files modified:** `tests/test_database_finder.py`
- **Verification:** All 10 tests pass after the fix, against the unmodified widened `finder.py`.
- **Committed in:** `dd8680c` (the RED commit already contains the corrected comparisons, since the bug was found and fixed before the RED commit was made)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug, found and fixed before it reached a commit as a false failure)
**Impact on plan:** No scope creep — the fix only corrected the test's own comparison logic to match the plan's explicitly stated (and intentional) relative-path return behaviour for certain tiers; the implementation itself needed no correction beyond the plan's own specification.

## Issues Encountered

None beyond the test-isolation bug documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- A user with only the existing `data/reference/lucy-ng-derep.db` (and, if present, `lucy-ng-fragments.db`) keeps working under `ailsa` with zero action required: auto-detection finds either filename at every tier, `download` never re-downloads when the legacy file exists, and `info` works bare, with the legacy path, or with the new path.
- Plan 05 (and any later plan touching `src/ailsa/database/`, `src/ailsa/identity.py`, `src/ailsa/cli/database.py`, or `src/ailsa/cli/fragment.py`) can build on `DatabaseFinder.resolve_default_derep_path()` and `resolve_default_fragments_db()` as the canonical default-path resolvers.
- No blockers. Nothing pushed (per this session's own sequential-executor protocol — push decision deferred to the user per the global push policy, not because of any risk found here). `data/reference/` is byte-for-byte unchanged from before this plan (verified: no renames, no new files, `git status --short` empty throughout since the directory's `*.db`/`*.sdf`/`*.db.zip` entries are gitignored).

## Self-Check: PASSED

All 5 claimed files (`src/ailsa/database/finder.py`, `src/ailsa/identity.py`,
`src/ailsa/cli/database.py`, `src/ailsa/cli/fragment.py`,
`tests/test_database_finder.py`) and all 4 task commit hashes (`dd8680c`,
`f1146f1`, `50a9d3c`, `0ac22f6`) verified present on disk / in `git log`.

---
*Phase: 104-package-and-cli*
*Completed: 2026-10-03*
