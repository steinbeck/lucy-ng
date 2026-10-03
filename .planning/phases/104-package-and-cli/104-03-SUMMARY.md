---
phase: 104-package-and-cli
plan: 03
subsystem: cli
tags: [click, packaging, deprecation, webview, subprocess]

# Dependency graph
requires:
  - phase: 104-02
    provides: "The ailsa module/project/CLI-text rename landed: src/ailsa, pyproject.toml name=ailsa, single ailsa = \"ailsa.cli:cli\" console-script entry, prog_name=\"ailsa\""
provides:
  - "A second console-script entry, `lucy = \"ailsa.cli:lucy_deprecated\"`, that warns once on stderr and then delegates to the identical `cli` group, proven byte-identical to `ailsa` on stdout (including `--format json`) by a real-subprocess test and by the Plan 01 golden-stdout files"
  - "`ailsa.webview.server._build_launcher()` — a two-tier subprocess-launcher helper (ailsa on PATH, else `python -m ailsa.cli`) that never falls back to a lone, possibly-stale `lucy` script"
  - "tests/test_cli_deprecated_alias.py (6 tests) and tests/test_webview_launcher.py (4 tests), both passing against the regression gate with zero new pytest/mypy/ruff findings beyond the Plan 02 baseline"
affects: [104-04, 104-05, 104-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deprecated top-level CLI alias: a bare module function (not a click.Command) that writes one err=True line then calls cli.main(args=..., prog_name=\"lucy\") — mirrors this repo's existing per-subcommand deprecation idiom in cli/pylsd.py, lifted to the whole group"
    - "CliRunner() without mix_stderr, reading result.stdout/result.stderr separately — the repo's installed Click 8.4.2 removed the mix_stderr kwarg; new tests use plain CliRunner() or capsys/subprocess instead"
    - "Launcher-selection helper extracted to a pure function (_build_launcher) specifically so it is monkeypatchable in tests without touching the stateful start() subprocess-launch path"

key-files:
  created:
    - tests/test_cli_deprecated_alias.py
    - tests/test_webview_launcher.py
  modified:
    - src/ailsa/cli/main.py
    - src/ailsa/cli/__init__.py
    - src/ailsa/cli/__main__.py
    - src/ailsa/webview/server.py
    - pyproject.toml

key-decisions:
  - "2-tier webview launcher (ailsa -> python -m ailsa.cli), not research's proposed 3-tier (ailsa -> lucy -> python -m ailsa.cli): a lone `lucy` on PATH with no `ailsa` beside it can only be a stale pre-rename lucy-ng install, so launching it would silently run OLD code against the new package's webview server. This is a plan-authored deviation from the research pitfall, called out explicitly in the plan's own <action> text, not something this execution discovered."
  - "uv.lock left untouched after `uv sync --extra dev` (no new runtime dependency; the git status diff on uv.lock was empty, so there was no committed/not-committed decision to make)"

patterns-established:
  - "A bare wrapper function intended as a console-script entry point (not a click.Command) is tested with capsys + pytest.raises(SystemExit) for the stderr/stdout-separation contract, and with a real subprocess for byte-identity across process boundaries — CliRunner cannot invoke it directly since it isn't a click.Command"

requirements-completed: [PKG-03]

# Metrics
duration: 25min
completed: 2026-10-03
---

# Phase 104 Plan 03: Deprecated `lucy` Alias + Webview Launcher Summary

**Added the `lucy` console-script alias (one stderr deprecation line, byte-identical stdout to `ailsa`, proven against real subprocesses and the Plan 01 golden JSON files) and extracted `ailsa.webview.server._build_launcher()` so the webview dashboard subprocess always prefers the renamed `ailsa` entry point and never launches a stale `lucy` binary.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-10-03T07:06Z (prior commit a5b399c)
- **Completed:** 2026-10-03T07:31Z (commit dff5591)
- **Tasks:** 2 completed
- **Files modified:** 7 (5 modified, 2 created)

## Accomplishments
- `lucy_deprecated()` in `src/ailsa/cli/main.py`: writes the single-line `LUCY_DEPRECATION_MESSAGE` to stderr via `click.echo(..., err=True)`, then calls `cli.main(args=..., prog_name="lucy")` — never short-circuits, never touches stdout. `pyproject.toml` now registers both `ailsa = "ailsa.cli:cli"` and `lucy = "ailsa.cli:lucy_deprecated"`; `src/ailsa/cli/__init__.py` exports both names so the entry-point string resolves.
- Proved byte-identity end to end: a real-subprocess test compares `python -c "from ailsa.cli import lucy_deprecated; lucy_deprecated()"` against `python -m ailsa.cli` for `identify --smiles CCO --format json` — identical return code, identical stdout bytes, valid JSON, deprecation line present only on the alias's stderr. Separately smoke-checked `uv run lucy detect hhb C10H14O2 --format json` and `uv run ailsa identify --smiles CCO --format json` against the Plan 01 golden files with `cmp` — both byte-identical.
- Every registered subcommand's `--help` matches between `lucy_deprecated([name, "--help"])` and `cli.main(args=[name, "--help"], prog_name="ailsa")` (modulo the `Usage: lucy ` / `Usage: ailsa ` prog-name prefix) — proves all 15 command groups are reachable through both names.
- `ailsa.webview.server._build_launcher()`: two-tier check (`ailsa` on PATH, else `[sys.executable, "-m", "ailsa.cli"]`), covered by 4 new tests including the explicit "a lone stale `lucy` is never chosen" case. `start()` now calls this helper instead of its old inline `if shutil.which("lucy"): ...` — which, notably, never checked `ailsa` at all (a leftover from Plan 02, explicitly deferred to this plan).
- Regression gate: quick pytest suite `74 failed / 1353 passed / 86 skipped / 1 deselected / 1 xfailed` — the failing-node-ID set is byte-identical to the Plan 01 baseline (`comm -13` empty); the 9 new passing tests account for the `1344 -> 1353` delta. `mypy src/ailsa`: 33 errors, `comm -13` against the normalised baseline empty. `ruff check src tests`: 279 findings, matching Plan 02's own post-rename count exactly (the 4 `comm -13` lines are the same pre-existing `test_inventory_schema.py`/`test_lsd_orchestrator.py` shrinking-line false positives Plan 02 already documented, untouched by this plan).

## Task Commits

1. **Task 1 RED: failing tests for the deprecated lucy alias** - `a9ce281` (test)
2. **Task 1 GREEN: deprecated lucy console script** - `3618490` (feat)
3. **Task 2 RED: failing tests for webview launcher selection** - `cd3258e` (test)
4. **Task 2 GREEN: webview launcher prefers ailsa, falls back to python -m ailsa.cli** - `dff5591` (feat)

_No plan-metadata commit yet; STATE.md/ROADMAP.md updates follow after this summary per the execute-plan workflow._

## Files Created/Modified
- `src/ailsa/cli/main.py` — added `LUCY_DEPRECATION_MESSAGE` constant and `lucy_deprecated()` wrapper
- `src/ailsa/cli/__init__.py` — exports `lucy_deprecated` alongside `cli`
- `src/ailsa/cli/__main__.py` — docstring cross-reference updated to `_build_launcher`
- `src/ailsa/webview/server.py` — new `_build_launcher()` function; `start()` calls it; module docstring and comment updated
- `pyproject.toml` — `[project.scripts]` gains `lucy = "ailsa.cli:lucy_deprecated"`
- `tests/test_cli_deprecated_alias.py` — 6 tests (capsys stderr/stdout separation, real-subprocess byte-identity, per-subcommand help parity, entry-point metadata, single-line message constant)
- `tests/test_webview_launcher.py` — 4 tests (prefers ailsa, never chooses a stale lucy, falls back to `python -m ailsa.cli`, import-safety against fastapi leaking)

## Decisions Made
- **2-tier webview launcher, not 3-tier:** the plan itself (not a deviation found during execution) overrides research's Pitfall 8 recommendation of an `ailsa -> lucy -> python -m` fallback chain. A `lucy` found alone on PATH during the deprecation window can only be a stale pre-rename `lucy-ng` install (since the current package registers both `ailsa` and `lucy` together), so launching it would silently run old code against the new webview server. Documented in the plan's `<action>` text and carried through verbatim.
- **uv.lock unchanged:** `uv sync --extra dev` after the `pyproject.toml` edit produced no `uv.lock` diff (no new runtime dependency was added — only a second console-script entry in an already-locked project), so there was nothing to stage or explain per D-06.

## Deviations from Plan

None - plan executed exactly as written. (The 2-tier-vs-3-tier launcher choice above is the plan's own explicit instruction, not an executor-discovered deviation; recorded here for traceability since the plan asked for it to be called out in the SUMMARY.)

## Issues Encountered
- Ruff flagged `tests/test_webview_launcher.py` for an unsorted import block (`import sys` before `import subprocess`) immediately after creating the file — a genuinely new finding introduced by this plan's own new test file, not a pre-existing baseline issue. Fixed inline (reordered to `subprocess` then `sys`) before the Task 2 GREEN commit; `ruff check tests/test_webview_launcher.py` is clean and the full-tree `ruff check src tests` count returned to exactly 279, matching Plan 02's baseline with zero net new findings.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `ailsa` is the primary CLI everywhere; `lucy` works identically for one more release with a one-line stderr deprecation hint, and both are console-script-registered (`.venv/bin/ailsa`, `.venv/bin/lucy` present after `uv sync --extra dev`).
- The webview dashboard subprocess launcher is now future-proof against a stale `lucy` lingering on a developer's PATH during the transition window.
- Plan 04 (database filename fallback) can proceed independently — this plan did not touch `src/ailsa/database/finder.py`, `src/ailsa/identity.py`, `src/ailsa/cli/database.py`, `src/ailsa/cli/fragment.py`, `tests/test_database_finder.py`, or `tests/test_cli_database.py`.
- No blockers. `.claude/`, `README.md`, `docs/`, `CLAUDE.md`, `tests/case-benchmark/` are untouched (verified via `git diff --stat` against the pre-Plan-03 commit). Nothing pushed (D-05 respected).

## Self-Check: PASSED

All claimed files (`tests/test_cli_deprecated_alias.py`, `tests/test_webview_launcher.py`,
`src/ailsa/cli/main.py`, `src/ailsa/webview/server.py`) and all 4 task commit hashes
(`a9ce281`, `3618490`, `cd3258e`, `dff5591`) verified present on disk / in `git log`.

---
*Phase: 104-package-and-cli*
*Completed: 2026-10-03*
