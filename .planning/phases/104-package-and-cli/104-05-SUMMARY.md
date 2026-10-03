---
phase: 104-package-and-cli
plan: 05
subsystem: infra
tags: [packaging, hatchling, uv, twine, pypi, click, conda]

# Dependency graph
requires:
  - phase: 104-01
    provides: "Diffable pre-rename baseline (sorted failing node IDs, mypy/ruff finding lines, two byte-deterministic golden --format json files)"
  - phase: 104-02
    provides: "src/ailsa module/project/CLI rename"
  - phase: 104-03
    provides: "Deprecated lucy console-script alias + webview launcher widening"
  - phase: 104-04
    provides: "DatabaseFinder.resolve_default_derep_path()/resolve_default_fragments_db() dual-filename resolution"
provides:
  - "pyproject.toml with no direct-URL dependency (nmrglue>=0.12 from PyPI) and an explicit sdist include list scoped to src/ailsa + top-level metadata files"
  - "A twine-check-PASSED wheel and sdist, proven to contain only the package (no data/.planning/.claude leakage)"
  - "A full-phase regression gate recorded against the Plan 01 baseline: no new failing pytest node ID, no new mypy/ruff finding, the slow real-data test outcome unchanged, PKG-02's lucy_ng grep empty, the out-of-scope diff empty"
  - "The global /opt/miniconda3 editable install reinstalled under ailsa (--no-deps), with both ailsa and lucy on PATH byte-identical to the Plan 01 golden stdout"
affects: [104-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "uv build --out-dir SCRATCH/dist-probe + unzip/tar/twine as the PyPI-uploadability proof, before any real upload (Plan 06's job)"

key-files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - .gitignore

key-decisions:
  - "The plan's literal Task 1 verify command includes `! grep -q 'git+https' pyproject.toml`, which is a false positive: pyproject.toml line 57 has carried a pre-existing, unrelated comment (`# Install manually: pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps`) documenting the optional, broken-on-3.12 `prediction` extra since before PHASE_START_SHA (confirmed via `git show 9b1091d:pyproject.toml`). This string is a comment, not a dependency specifier; it does not appear in built METADATA (`Requires-Dist` grep for ` @ ` is empty) and `twine check` passes. Left the comment untouched (out of Task 1's scope, unrelated to nmrglue) rather than editing an unrelated line to satisfy an overly broad literal grep."
  - "Added `/SCRATCH/` to .gitignore (the plan directs probe builds into `SCRATCH/dist-probe/`; this directory was not previously gitignored and would otherwise be left untracked after every plan that uses it)"
  - "Global editable reinstall used --no-deps as instructed; the conda env's nmrglue stayed at 0.12.dev0 (git build), which does not satisfy the new `nmrglue>=0.12` PyPI specifier under PEP 440 version ordering (a dev release sorts before the final release it precedes) — recorded here per the plan's explicit instruction, not upgraded. All four golden-command comparisons (ailsa/lucy x detect/identify) were byte-identical to the Plan 01 .venv-produced golden files despite this version difference, so no cross-interpreter fallback comparison was needed."

requirements-completed: [PKG-01, PKG-03, PKG-04]

# Metrics
duration: 35min
completed: 2026-10-03
---

# Phase 104 Plan 05: PyPI-Uploadable Packaging + Full Gate + Global CLI Reinstall Summary

**Removed the nmrglue git-URL dependency and scoped the sdist to the package only (twine check PASSED on both artifacts), ran the complete PKG-02/PKG-04 regression gate against the Plan 01 baseline with zero new findings and the slow real-data test still passing, and reinstalled the `/opt/miniconda3` global editable CLI under `ailsa` with both `ailsa` and `lucy` byte-identical to the pre-rename golden JSON stdout.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-10-03T09:50Z (prior commit ba053b9)
- **Completed:** 2026-10-03T10:05Z (commit 70cb3fd)
- **Tasks:** 3 completed
- **Files modified:** 3 (pyproject.toml, uv.lock, .gitignore) + no-repo-file global install step

## Accomplishments

- `pyproject.toml`: `nmrglue @ git+https://github.com/jjhelmus/nmrglue.git` replaced with `nmrglue>=0.12` (PyPI, NumPy-2 compatible since 2026-08); `[tool.hatch.metadata] allow-direct-references = true` removed; new `[tool.hatch.build.targets.sdist] include = ["/src/ailsa", "/README.md", "/LICENSE", "/pyproject.toml"]`; `description` updated to the AILSA placeholder wording. `uv lock` moved nmrglue from the git source to PyPI `0.12`; `uv run python -c "import nmrglue; print(nmrglue.__version__)"` prints `0.12`.
- Probe build into `SCRATCH/dist-probe` (gitignored): wheel `METADATA` has `Name: ailsa`, `Version: 0.1.0`, and no `Requires-Dist` line containing ` @ ` (confirmed `Requires-Dist: nmrglue>=0.12`); the sdist (`tar tzf`) lists nothing outside `ailsa-0.1.0/src/ailsa/` and the top-level metadata files; both artifacts are well under 5 MB (364 KB wheel, 300 KB sdist); `uvx twine check` reports `PASSED` for both.
- Quick pytest suite after the nmrglue switch: `74 failed / 1372 passed / 86 skipped / 1 deselected / 1 xfailed` — `comm -13` against `baseline/pytest-failed.txt` is empty (0 new failures). 1372 passed matches baseline 1344 + the 28 tests added across Plans 03/04 (19 in `test_cli_deprecated_alias.py`/`test_webview_launcher.py`/`test_database_finder.py`, 9 in `test_cli_database.py`'s dual-filename classes).
- Full phase gate (Task 2): the slow real-data test (`TestDatabaseImporterIntegration::test_import_coconut_real`) passed in 279.45s, matching baseline's `SLOW_TEST: passed`. `mypy src/ailsa`: 33 errors, `comm -13` against the normalised baseline empty (exact match). `ruff check src tests`: 278 findings (≤ baseline's 282), `comm -13` shows exactly the same 4 pre-existing `test_inventory_schema.py`/`test_lsd_orchestrator.py` shrinking-line false positives Plan 02 already documented (confirmed via `git diff` that this plan touched neither file). `grep -rn --exclude-dir=__pycache__ "lucy_ng" src tests scripts pyproject.toml` is empty; `src/lucy_ng` does not exist. The out-of-scope `git diff --name-only` against `.claude`, `README.md`, `docs`, `CLAUDE.md`, `tests/case-benchmark`, and the host/launchd scripts is empty; `tests/test_skill_files_unchanged.py` passes (8/8). `tests/test_prediction.py` (HOSE invariant) shows the same 20 pre-existing failures as baseline. The identity-leak scan (`SCRATCH/identity-names.txt` built from the gitignored `CASE-DATASET-IDENTITIES.md`) found zero hits in any tracked/changed file; the only hits (20, in a gitignored `SCRATCH/` pytest log) are the same pre-existing `ibuprofen`/`pulegone` test-parametrize-ID strings Plan 01 already reviewed and accepted.
- Global editable reinstall (Task 3): `/opt/miniconda3/bin/pip uninstall -y lucy-ng` then `pip install --no-deps -e /Users/steinbeck/Dropbox/develop/lucy-ng`. `pip show ailsa` now reports the editable location of this repo; `pip show lucy-ng` reports not found. `which -a ailsa lucy` lists both `/opt/miniconda3/bin/ailsa` and `/opt/miniconda3/bin/lucy`; the `lucy` script now imports `from ailsa.cli import lucy_deprecated`. All four golden-command checks (`ailsa`/`lucy` x `detect hhb C10H14O2`/`identify --smiles CCO`, each `--format json`) are byte-identical (`cmp` exit 0) to the Plan 01 golden files. `lucy --version` stderr carries exactly one line containing "deprecated"; stdout (`ailsa, version 0.1.0`) does not. `cd /tmp && lucy database info <abs-path-to-lucy-ng-derep.db>` exits 0 and prints the real 928,443-compound stats.

## Gate Table (PKG-02 / PKG-04, against the Plan 01 baseline)

| Check | Baseline | Now | Verdict |
|---|---|---|---|
| pytest quick suite (failed/passed/skipped) | 74 / 1344 / 86 | 74 / 1372 / 86 | PASS — `comm -13` empty; +28 = the tests added in Plans 03/04 |
| Slow real-data test (`test_import_coconut_real`) | passed (307.88s) | passed (279.45s) | PASS |
| mypy `src/ailsa` | 33 errors | 33 errors | PASS — `comm -13` empty |
| ruff `check src tests` | 282 findings | 278 findings | PASS — `comm -13` shows only the 4 pre-existing Plan-02-documented shrinking-line false positives, confirmed untouched by this plan |
| `lucy_ng` grep (`src tests scripts pyproject.toml`) | n/a | empty | PASS |
| `src/lucy_ng` exists | n/a | absent | PASS |
| Out-of-scope `git diff --name-only` (.claude, README, docs, CLAUDE.md, host/launchd scripts) | n/a | empty | PASS |
| `tests/test_skill_files_unchanged.py` | n/a | 8/8 passed | PASS |
| `tests/test_prediction.py` (HOSE invariant) | 20 failed / 28 passed | 20 failed / 28 passed | PASS — identical outcome |
| Identity-leak scan over all changed/tracked files | 0 (reviewed baseline exception excluded) | 0 | PASS |
| Golden JSON (`detect hhb`, `identify CCO`) | byte-deterministic | byte-identical (.venv and global conda, both `ailsa` and `lucy`) | PASS |

## Task Commits

1. **Task 1: PyPI-uploadable metadata (nmrglue from PyPI, sdist include list, description)** - `70cb3fd` (build)
2. **Task 2: Full phase gate against the baseline** - no file changes; gate results recorded in this SUMMARY
3. **Task 3: Reinstall the global editable CLI** - no repo file changes; `/opt/miniconda3` site-packages/bin scripts only

_No plan-metadata commit yet; STATE.md/ROADMAP.md updates follow after this summary per the execute-plan workflow._

## Files Created/Modified

- `pyproject.toml` — `nmrglue>=0.12` (was the git-URL dependency), `[tool.hatch.metadata] allow-direct-references` removed, new `[tool.hatch.build.targets.sdist]` include list, `description` updated
- `uv.lock` — nmrglue's lock entry moved from the git commit to PyPI `0.12`
- `.gitignore` — added `/SCRATCH/` (the probe-build/verification scratch directory this plan and future plans build into)
- `/opt/miniconda3/lib/python3.12/site-packages/` — `lucy_ng-0.1.0.dist-info` removed, `ailsa-0.1.0.dist-info` (editable) added; `/opt/miniconda3/bin/lucy` and `/opt/miniconda3/bin/ailsa` regenerated (no repo files)

## Decisions Made

- **nmrglue version source switch accepted as the plan intends** (T-104-SC in the threat model): PyPI 0.12 is from the same jjhelmus/nmrglue maintainers as the git dependency it replaces, imports cleanly, and the full regression gate shows zero behavioural difference (identical pytest/mypy/ruff counts, byte-identical golden JSON).
- **Pre-existing `git+https` comment left untouched** (see key-decisions in frontmatter) — Task 1's own verify command's blanket file-wide `grep -q 'git+https'` is a false positive on an unrelated, pre-existing `prediction`-extra install comment; the actual PyPI-uploadability criteria (no `Requires-Dist` direct-URL line, twine PASSED) are independently confirmed and are the real acceptance bar.
- **`/SCRATCH/` added to `.gitignore` rather than left untracked**, per the task-commit protocol's rule that generated/runtime output must not be left as an untracked artifact.
- **Global reinstall used `--no-deps` exactly as instructed**, leaving the conda env's `nmrglue==0.12.dev0` in place rather than upgrading it — the plan explicitly says "do not upgrade" if a version mismatch warning appears; `pip install --no-deps` does not even surface such a warning, but the mismatch is recorded here for completeness since it is a real (if practically inconsequential, per the golden-JSON byte-identity proof) fact about this machine's global environment.

## Deviations from Plan

### Auto-fixed Issues

None — no code bug, missing functionality, or blocking issue was found that required an auto-fix under Rules 1-3.

### Noted Discrepancy (not a deviation under Rules 1-4, no plan/code change made)

**1. Task 1's literal verify command has a false-positive sub-check**
- **Found during:** Task 1, running the full automated `<verify>` command
- **Issue:** `! grep -q 'git+https' pyproject.toml` fails because of a single pre-existing, unrelated comment line (`# Install manually: pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps`, documenting the broken-on-3.12 `prediction` extra) that has been in the file since before `PHASE_START_SHA` (confirmed via `git show 9b1091d:pyproject.toml`) — it is not a dependency specifier and was never part of this task's edit scope (the `dependencies` array, confirmed by direct inspection, has no `git+https` strings remaining).
- **Resolution:** No edit made. Every acceptance criterion this check exists to protect — no direct-URL `Requires-Dist` in the built wheel METADATA, `twine check` PASSED on both artifacts — was independently verified true. Editing the unrelated comment to satisfy an overly broad literal grep would be scope creep onto a line this task does not own.
- **Files modified:** None
- **Verification:** `unzip -p *.whl '*/METADATA' | grep 'Requires-Dist: .* @ '` → empty; `uvx twine check` → PASSED for both artifacts

---

**Total deviations:** 0 auto-fixed; 1 noted discrepancy (plan verify-script false positive, documented, no code/plan change needed)
**Impact on plan:** None on the actual deliverable — the package is PyPI-uploadable by every substantive measure (METADATA, twine, sdist contents).

## Issues Encountered

None beyond the documented false-positive verify sub-check above.

## User Setup Required

None - no external service configuration required. The real PyPI upload remains Plan 06's human-gated step; nothing was uploaded here.

## Next Phase Readiness

- The artifacts Plan 06 will build and upload are proven PyPI-uploadable (no direct-URL dependency, scoped sdist, twine check PASSED) — Plan 06 can proceed straight to the human-gated publish checkpoint.
- The full phase gate (PKG-02, PKG-04) shows zero regression from the Plan 01 baseline across pytest (quick + slow), mypy, ruff, the skill-files-unchanged guard, and the identity-leak scan.
- The global `/opt/miniconda3` `lucy`/`ailsa` CLI the CASE skill actually calls on this Mac works again under both names, byte-identical to the pre-rename golden JSON.
- No blockers. Nothing pushed (the repository is public and D-05 governs; push decision stays with the user per the global push policy — this session made no push). `data/reference/*.db` untouched (confirmed via `git status --short`, gitignored, never touched by this plan's commands).

## Self-Check: PASSED

Verified on disk / in `git log`:
- `pyproject.toml` contains `"nmrglue>=0.12"`, no `allow-direct-references`, and the new `[tool.hatch.build.targets.sdist]` section — confirmed by direct read after edit.
- Commit `70cb3fd` exists in `git log --oneline` and contains exactly `pyproject.toml`, `uv.lock`, `.gitignore`.
- `/opt/miniconda3/bin/ailsa` and `/opt/miniconda3/bin/lucy` both exist and resolve to `ailsa.cli:cli` / `ailsa.cli:lucy_deprecated` respectively — confirmed by `head` on both scripts.
- `SCRATCH/dist-probe/ailsa-0.1.0-py3-none-any.whl` and `.tar.gz` exist on disk at the time of this check (gitignored, not committed, per design).

---
*Phase: 104-package-and-cli*
*Completed: 2026-10-03*
