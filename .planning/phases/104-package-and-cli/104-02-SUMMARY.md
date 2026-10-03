---
phase: 104-package-and-cli
plan: 02
subsystem: infra
tags: [packaging, hatchling, uv, click, rename]

# Dependency graph
requires:
  - phase: 104-01
    provides: "Diffable pre-rename baseline (sorted failing node IDs, mypy/ruff finding lines, two byte-deterministic golden --format json files) and a clean, committed uv.lock"
provides:
  - "The Python package lives at src/ailsa (git mv from src/lucy_ng, 126 tracked files), and every import in src/, tests/ (excluding tests/case-benchmark/) and the two generic scripts comes from ailsa"
  - "pyproject.toml names the project ailsa, with a single ailsa = \"ailsa.cli:cli\" console-script entry, updated wheel packages/artifacts and [tool.mypy] packages"
  - "User-facing CLI text (help, docstrings, hints, the schema $id, the nmrxiv User-Agent) says ailsa; src/ailsa/cli/main.py's prog_name is \"ailsa\""
  - "The protected tokens (data-folder path, skill-tree paths, both database filenames, the quoted directory-name path segments in finder.py/identity.py) are byte-unchanged, verified against the Plan 01 baseline SHA"
affects: [104-03, 104-04, 104-05, 104-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Protected-token masking before a scripted text rename: mask exact strings (data paths, skill paths, DB filenames, the quoted directory-name segment) with placeholders, apply the rename rules, then unmask — keeps a blanket find/replace from corrupting strings that must survive to a later phase"
    - "comm -13 node-ID/finding-line regression gate needs a second look when a rename changes line length: a pre-existing over-limit line that merely shifts length (even shrinking) produces a textually different finding line and a false-positive comm -13 diff; confirm via git diff whether any line newly crosses the threshold before treating the diff as a regression"

key-files:
  created: []
  modified:
    - "src/ailsa/ (git mv from src/lucy_ng/, 126 tracked files, every lucy_ng import rewritten to ailsa)"
    - "src/ailsa/cli/main.py (prog_name=\"ailsa\", group docstring)"
    - "pyproject.toml (name = \"ailsa\", [project.scripts] ailsa = \"ailsa.cli:cli\", wheel packages/artifacts, [tool.mypy] packages)"
    - "uv.lock (project self-entry renamed to ailsa 0.1.0)"
    - "tests/ (~89 files, lucy_ng import rewrite; tests/test_cli_main.py's \"lucy-ng\" assertion corrected to \"ailsa\")"
    - "scripts/verify_case_solution.py, scripts/render_jcamp_spectra.py"
    - "schemas/constraint_inventory_v2.json, src/ailsa/data/schemas/constraint_inventory_v2.json (kept byte-identical, $id now https://ailsa/...)"

key-decisions:
  - "Followed the plan's literal pyproject.toml Rule 0 + manual-edit split: Rule 0's mechanical lucy_ng->ailsa pass left [project.scripts] as `lucy = \"ailsa.cli:cli\"` (module renamed, script name untouched); the manual step then renamed the script key itself to a single `ailsa = \"ailsa.cli:cli\"` entry, with no `lucy` alias (Plan 03's job)"
  - "Protected the exact quoted token \"lucy-ng\" globally during the Rules A-C text pass, then discovered and corrected one over-protection: tests/test_cli_main.py:27's `assert \"lucy-ng\" in result.output` was masked along with the two legitimate directory-name occurrences in database/finder.py and identity.py. Fixed by hand to `assert \"ailsa\" in result.output`, matching the plan's explicit test-assertion list."
  - "webview/server.py's shutil.which(\"lucy\") launcher logic was left untouched per the plan (Plan 03 widens it to a 3-tier check); only its docstring/comment text was rewritten by Rules A-C, so the comment now says \"ailsa\" one plan ahead of the code it describes — expected and explicitly sanctioned by this plan's own instructions"
  - "4 ruff E501 findings on lines that shrank by exactly 2 characters (lucy_ng.*->ailsa.* module-path references inside already-over-100-char lines in tests/test_inventory_schema.py and tests/test_lsd_orchestrator.py) produced false-positive comm -13 diffs, because the normalised finding-line text embeds the exact overflow count. Verified via git diff that every one of these lines was already flagged in the Plan 01 baseline at a longer length and that no line newly crosses the 100-char threshold; left unmodified rather than rewrapped (Pitfall 4 — do not touch pre-existing findings)."

patterns-established:
  - "Pattern: protected-token masking must be scoped per-file when a token has mixed legitimate/illegitimate occurrences across the file set (the quoted \"lucy-ng\" token is a real path segment in two library files but a test assertion string everywhere else) — a single global mask/unmask pass over the whole set is not safe without a manual post-check."

requirements-completed: [PKG-01, PKG-02, PKG-04]

# Metrics
duration: 15min
completed: 2026-10-03
---

# Phase 104 Plan 02: Rename lucy_ng to ailsa (module, project, CLI text) Summary

**Moved `src/lucy_ng` to `src/ailsa` (126 files), rewrote every `lucy_ng` import across src/tests/scripts, renamed the pyproject.toml project/console-script to `ailsa`, and rewrote user-facing CLI/docstring/schema text from `lucy-ng`/`lucy` to `ailsa` — all while keeping six protected tokens (data paths, skill paths, both DB filenames, the quoted directory-name segments) byte-unchanged and the test/mypy/ruff regression gate clean against the Plan 01 baseline.**

## Performance

- **Duration:** ~15 min (Task 1+2, one combined commit per plan design)
- **Started:** 2026-10-03T07:03Z (prior commit b33cfb4)
- **Completed:** 2026-10-03T07:17Z (commit 2ffb0cf)
- **Tasks:** 2 completed (landed in one commit, per the plan's own instruction)
- **Files modified:** 227 (126 renamed via `git mv` + content edits, ~90 tests/scripts/config content-only)

## Accomplishments
- `git mv src/lucy_ng src/ailsa` (126 tracked files, no leftovers), then a word-boundary `lucy_ng`→`ailsa` rewrite across every file under `src/ailsa/`, ~89 test files (excluding `tests/case-benchmark/`), and the two generic scripts — `grep -rn --exclude-dir=__pycache__ "lucy_ng" src tests scripts pyproject.toml` returns nothing.
- `pyproject.toml`: `name = "ailsa"`, single `[project.scripts]` entry `ailsa = "ailsa.cli:cli"`, wheel `packages`/`artifacts` and `[tool.mypy] packages` all point at `ailsa`; version stayed `0.1.0` per the plan's own decision (D-01).
- Regenerated `uv.lock` (`uv lock`) and the dev venv (`uv sync --extra dev`): the project's own lock entry is now `ailsa 0.1.0`, `import ailsa` resolves to `src/ailsa/__init__.py`, `import lucy_ng` raises `ModuleNotFoundError`, and `.venv/bin/ailsa` is the only generated script (no stale `lucy_ng` dist-info).
- Rules A-C text pass (scripted, protected-token-masked): `lucy-ng`→`ailsa` in docstrings/help/hints/the schema `$id` (both schema copies stay byte-identical)/the nmrxiv User-Agent; `` `lucy <subcommand>` ``→`` `ailsa <subcommand>` ``; backticked `` `lucy` ``/``` ``lucy`` ```→`ailsa`/``ailsa``; `src/ailsa/cli/main.py`'s `prog_name` is now `"ailsa"`.
- Six protected tokens verified intact: `active-lucy-ng-testprojects`, `commands/lucy-ng`, `/lucy-ng:`, `lucy-ng-derep`, `lucy-ng-fragments`, and the quoted `"lucy-ng"` directory-name segments in `database/finder.py`/`identity.py` (3+1 occurrences) — all real, on-disk-path-resolving strings left for Plan 04.
- Regression gate green against the Plan 01 baseline: quick pytest suite 74 failed/1344 passed with the *identical* failing node-ID set (`comm -13` empty); mypy 33 errors (`comm -13` empty after path/module normalisation); ruff 279 findings, `comm -13` empty once 4 false-positive diffs (explained below) are accounted for; `tests/test_skill_files_unchanged.py` and `tests/test_case_md_wv07.py` pass; `git diff --name-only` against the Plan 01 baseline SHA over `.claude/`, `README.md`, `docs/`, `CLAUDE.md`, `tests/case-benchmark/` and the host/launchd scripts is empty.
- Golden JSON cross-check (not literally required by this plan, cheap to verify): `ailsa detect hhb C10H14O2 --format json` and `ailsa identify --smiles CCO --format json` are byte-identical to the Plan 01 baseline's golden stdout files.

## Task Commits

1. **Task 1+2 (landed together per plan design): rename `lucy_ng`→`ailsa` module/project and the user-facing CLI text** - `2ffb0cf` (refactor)

_No plan-metadata commit yet; STATE.md/ROADMAP.md updates follow after this summary per the execute-plan workflow._

## Files Created/Modified
- `src/ailsa/` — the entire package (126 files), `git mv`'d from `src/lucy_ng/` and rewritten in place
- `src/ailsa/cli/main.py` — `prog_name="ailsa"`, group docstring now says `ailsa: AI-powered Computer-Assisted Structure Elucidation`
- `src/ailsa/database/finder.py`, `src/ailsa/identity.py` — unchanged logic; the quoted `"lucy-ng"` directory-name segments and the `lucy-ng-derep.db` filename are explicitly preserved for Plan 04
- `src/ailsa/webview/server.py` — docstring/comments rewritten to `ailsa`; the `shutil.which("lucy")` launcher logic itself is untouched (Plan 03)
- `pyproject.toml` — `name = "ailsa"`, `[project.scripts] ailsa = "ailsa.cli:cli"`, wheel packages/artifacts, `[tool.mypy] packages = ["ailsa"]`
- `uv.lock` — project self-entry renamed `lucy-ng`→`ailsa`, staged per BASELINE.md's `UV_LOCK_DISPOSITION: committed` disposition
- `tests/` (~89 files) — `lucy_ng`→`ailsa` import rewrite; `tests/test_cli_main.py`, `tests/test_cli_webview.py`, `tests/test_cli_jcamp.py` assertions updated to the new CLI text per the plan's explicit list
- `scripts/verify_case_solution.py`, `scripts/render_jcamp_spectra.py` — import + text rewrite
- `schemas/constraint_inventory_v2.json`, `src/ailsa/data/schemas/constraint_inventory_v2.json` — `$id` now `https://ailsa/schemas/constraint_inventory_v2.json`, both copies kept byte-identical

## Decisions Made
- **pyproject.toml scripts split (literal plan-following):** Rule 0's mechanical pass only touches the module name, leaving `lucy = "ailsa.cli:cli"`; the manual step that follows renames the script key to `ailsa = "ailsa.cli:cli"` with no `lucy` entry — Plan 03 adds the deprecated alias back.
- **webview/server.py left one plan ahead of its own code:** the docstring/comment text now says `ailsa` (Rules A-C fired on backticked/plain text) while the actual `shutil.which("lucy")` check is untouched, exactly as the plan specifies ("Plan 03 rewrites it. Only docstring/comment text changes via the rules.").
- **ruff false-positive diff, verified not a regression:** 4 `E501` lines in `tests/test_inventory_schema.py`/`tests/test_lsd_orchestrator.py` were already over the 100-char limit in the Plan 01 baseline; the `lucy_ng.*`→`ailsa.*` module-path substitution inside them is 2 characters *shorter*, so every one of these lines shrank. The normalised-diff recipe's `comm -13` still flags them because the embedded overflow count in the finding text changed (e.g. `117 > 100`→`115 > 100`). Confirmed via `git diff` that these are the only changed lines in both files and that none crosses the 100-char threshold in the wrong direction (fine/to-bad); left unmodified rather than rewrapped, since rewrapping an already-flagged, shrinking line is out of this task's scope (Pitfall 4).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected an over-broad protected-token mask that accidentally shielded a test assertion from the required text rename**
- **Found during:** Task 2, regression-gate review (comparing the rename script's "changed files" output against the plan's explicit test-assertion list)
- **Issue:** The Rules A-C masking step protected every exact occurrence of the quoted token `"lucy-ng"` across the whole file set, per the research's literal wording ("the exact 9-character quoted token `"lucy-ng"` in `src/ailsa/database/finder.py` and `src/ailsa/identity.py`"). Applied globally, this also masked `tests/test_cli_main.py:27`'s `assert "lucy-ng" in result.output` — which the plan explicitly lists as a test assertion that "becomes `"ailsa"`" as a direct consequence of the CLI text change.
- **Fix:** Verified the token's four other occurrences (3 in `database/finder.py`, 1 in `identity.py`) are the legitimate protected directory-name path segments and left them untouched; manually changed `tests/test_cli_main.py:27` to `assert "ailsa" in result.output`.
- **Files modified:** `tests/test_cli_main.py`
- **Verification:** `grep -rn '"lucy-ng"' src/ailsa tests schemas scripts/...` now shows only the 4 legitimate protected occurrences; `uv run --extra dev pytest tests/test_cli_main.py` passes (`test_help` included).
- **Committed in:** `2ffb0cf` (the single Task 1+2 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug, found and fixed before the task's own verification gate, not after)
**Impact on plan:** Necessary correction so the plan's own literal acceptance criterion (the test-assertion list) is met exactly. No scope creep — only the one listed assertion was touched.

## Issues Encountered
- The `comm -13` ruff regression check initially showed 4 non-empty lines (described above under Decisions Made). Root-caused by direct comparison against `git diff` rather than treated as a failure: all 4 are pre-existing baseline violations whose length shrank (never grew past the threshold) as a side effect of the module-path rename. No code change was needed; documented here so a future reviewer doesn't re-litigate it.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `ailsa` is now the module, the project, and the CLI name in the venv (`ailsa --version`, `ailsa --help` both confirmed); `lucy_ng` is fully gone from `src/`, `tests/`, `scripts/`, `pyproject.toml`.
- Plan 03 can now add the deprecated `lucy` CLI alias and widen `webview/server.py`'s launcher to a 3-tier check against the `ailsa` entry point this plan created.
- Plan 04 can now implement the dual-filename `DatabaseFinder`/`cli/database.py`/`cli/fragment.py` widening against the exact protected strings (`lucy-ng-derep.db`, `lucy-ng-fragments.db`, the quoted `"lucy-ng"` directory segments) this plan deliberately left untouched.
- No blockers. `.claude/`, `README.md`, `docs/`, `CLAUDE.md`, `tests/case-benchmark/` and the host/launchd scripts are verified byte-unchanged against the Plan 01 baseline SHA. Nothing pushed (D-05 respected; sequential executor, not yet pushed per this session's own protocol).

## Self-Check: PASSED

All claimed files (`src/ailsa/__init__.py`, `src/ailsa/cli/main.py`) and the task commit hash
(`2ffb0cf`) verified present on disk / in `git log`.

---
*Phase: 104-package-and-cli*
*Completed: 2026-10-03*
