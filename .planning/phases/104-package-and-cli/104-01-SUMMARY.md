---
phase: 104-package-and-cli
plan: 01
subsystem: infra
tags: [uv, pytest, mypy, ruff, baseline, packaging]

# Dependency graph
requires: []
provides:
  - "Committed uv.lock, clean and consistent with pyproject.toml (dev/webview/nus extras caught up)"
  - "Diffable pre-rename baseline directory (.planning/phases/104-package-and-cli/baseline/) with sorted pytest failing node IDs, mypy/ruff finding counts, and byte-deterministic golden --format json stdout for two database-backed commands"
  - "Documented comparison recipe (comm -13 on normalised node IDs/finding lines) for Plans 02-05 to prove PKG-04's 'no new findings' requirement"
affects: [104-02, 104-03, 104-04, 104-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Diffable baseline capture (sorted node IDs / finding lines, not raw counts) for mechanical-rename regression gates"

key-files:
  created:
    - .planning/phases/104-package-and-cli/baseline/BASELINE.md
    - .planning/phases/104-package-and-cli/baseline/pytest-failed.txt
    - .planning/phases/104-package-and-cli/baseline/pytest-summary.txt
    - .planning/phases/104-package-and-cli/baseline/mypy.txt
    - .planning/phases/104-package-and-cli/baseline/ruff.txt
    - .planning/phases/104-package-and-cli/baseline/golden-detect-hhb-C10H14O2.json
    - .planning/phases/104-package-and-cli/baseline/golden-identify-CCO.json
  modified:
    - uv.lock

key-decisions:
  - "uv.lock's pre-existing dirty state was proven to be pure extras catch-up (HEAD's lock fails uv lock --check, the dirty version passes, only a provides-extras metadata line was removed) and committed standalone before any rename edit, per D-06"
  - "Corrected the plan's slow-test node ID: test_import_coconut_real lives on TestDatabaseImporterIntegration, not TestDatabaseImporter as the plan stated (Rule 1 — blocking bug, the literal node ID collected 0 tests)"
  - "The identity-leak check's 6 matches in pytest-failed.txt (ibuprofen/pulegone) were reviewed and accepted as pre-existing, already-public strings baked into tests/test_ranking.py's own parametrize IDs since Phase 86/v9.1, not a new disclosure under D-05 -- not redacted, to preserve exact node-ID fidelity for later comm -13 comparisons"

patterns-established:
  - "Pattern: normalise mypy/ruff output (sed path/module rename + line-number strip) before comm -13, since literal line-for-line baseline/post-rename diffs will never match once every path and module name changes"

requirements-completed: [PKG-04]

# Metrics
duration: 15min
completed: 2026-10-03
---

# Phase 104 Plan 01: Pre-Rename Baseline Summary

**Captured a diffable pre-rename baseline (74 failing pytest node IDs, 33 mypy errors, 282 ruff findings, two byte-deterministic golden JSON stdout files) and cleanly settled the pre-existing dirty uv.lock as pure extras catch-up, before any rename edit landed.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-10-03T06:48:09Z (per STATE.md; first task commit 08:49:01+02:00)
- **Completed:** 2026-10-03T06:57:04Z (08:57:04+02:00)
- **Tasks:** 2 completed
- **Files modified:** 8 (1 modified, 7 created)

## Accomplishments
- Settled the pre-existing `uv.lock` modification (D-06): proved it is pure catch-up for the `dev`/`webview`/`nus` extras already in `pyproject.toml`, not an unrelated or suspicious change, and committed it standalone.
- Captured the exact pre-rename baseline — pytest (74 failed/1344 passed/86 skipped/1 deselected/1 xfailed), the one slow real-data test (passed, 307.88s), mypy (33 errors), ruff (282 findings) — all matching the research/validation session's measured baseline exactly.
- Captured two byte-deterministic `--format json` golden stdout files (`lucy detect hhb C10H14O2`, `lucy identify --smiles CCO`), using intentionally neutral inputs per D-05, each verified deterministic by a second run + `cmp`.
- Recorded the global editable install state for Plan 05's reinstall, and wrote a documented comparison recipe (`comm -13` on normalised node IDs / finding lines) that Plans 02-05 will use to prove "no new findings" after the rename.

## Task Commits

1. **Task 1: Settle the pre-existing uv.lock modification (D-06)** - `9b1091d` (build)
2. **Task 2: Capture the diffable pre-rename baseline** - `4697e95` (docs)

_No plan-metadata commit yet; STATE.md/ROADMAP.md updates follow after this summary per the execute-plan workflow._

## Files Created/Modified
- `uv.lock` - synced with the dev/webview/nus extras already declared in pyproject.toml (558 insertions, 1 metadata-only deletion)
- `.planning/phases/104-package-and-cli/baseline/BASELINE.md` - narrative baseline record: SHA, uv.lock disposition, all counts, global-install state, identity-leak review, comparison recipe
- `.planning/phases/104-package-and-cli/baseline/pytest-failed.txt` - 74 sorted, deduplicated failing node IDs from the quick suite
- `.planning/phases/104-package-and-cli/baseline/pytest-summary.txt` - final pytest summary line
- `.planning/phases/104-package-and-cli/baseline/mypy.txt` - 33 sorted mypy error lines
- `.planning/phases/104-package-and-cli/baseline/ruff.txt` - 282 sorted ruff finding lines
- `.planning/phases/104-package-and-cli/baseline/golden-detect-hhb-C10H14O2.json` - golden stdout, `lucy detect hhb C10H14O2 --format json`
- `.planning/phases/104-package-and-cli/baseline/golden-identify-CCO.json` - golden stdout, `lucy identify --smiles CCO --format json`

## Decisions Made
- **uv.lock disposition (D-06):** committed standalone (`9b1091d`) rather than left uncommitted, because all three verification steps passed (HEAD's lock stale, dirty lock consistent, only metadata removed). This means later plans may stage `uv.lock` changes of their own (the PKG-01 rename's own lock entry update) without inheriting this unrelated diff.
- **Slow-test node ID correction (Rule 1):** the plan named `TestDatabaseImporter::test_import_coconut_real`; the actual class is `TestDatabaseImporterIntegration` (line 288 of `tests/test_database_importer.py`). Used the corrected node ID; the real 4.74 GB `predicted_coconut.sdf` is present on this machine so the test ran for real (not skipped) and passed in 307.88s.
- **Identity-leak review (D-05):** the runtime-built name list from `.planning/CASE-DATASET-IDENTITIES.md` matched 6 lines in `pytest-failed.txt` (ibuprofen/pulegone). Reviewed and determined these are pre-existing, already-public strings literal in `tests/test_ranking.py`'s own parametrize IDs since Phase 86 (v9.1), and already public throughout many other tracked files (PROJECT.md, README, infographics) — CASE1/CASE3 are long-validated, non-blind members of the original test set. No redaction applied, to preserve exact node-ID fidelity for the `comm -13` regression checks in Plans 02-05.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the slow-test class name in the plan**
- **Found during:** Task 2 (capturing the baseline)
- **Issue:** The plan's step 3 named `tests/test_database_importer.py::TestDatabaseImporter::test_import_coconut_real`. That class does not define this method — `test_import_coconut_real` is on the sibling class `TestDatabaseImporterIntegration`. Running the literal node ID collected 0 tests (pytest exit 4, "ERROR: not found").
- **Fix:** Used the corrected node ID `tests/test_database_importer.py::TestDatabaseImporterIntegration::test_import_coconut_real`, confirmed the real reference SDF exists on this machine, and re-ran in the background. Result: `1 passed in 307.88s (0:05:07)`.
- **Files modified:** None (test code unchanged; only the baseline-capture command was corrected)
- **Verification:** `SLOW_TEST: passed` recorded in BASELINE.md with the exact pytest output line
- **Committed in:** `4697e95` (Task 2 commit; BASELINE.md documents the correction explicitly)

---

**Total deviations:** 1 auto-fixed (1 blocking/Rule 1)
**Impact on plan:** Necessary correction to complete the task as intended; no scope creep. The plan's own acceptance criteria (SLOW_TEST line present and recorded) are met.

## Issues Encountered
- A background-job race: `SLOW_TEST` was briefly drafted into BASELINE.md as "passed" before the real-data test had actually finished. Caught before committing — reverted to "pending" and only finalized once the backgrounded process was confirmed exited and its log showed `1 passed`. No incorrect claim reached the commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `baseline/` is committed and provides the exact reference (sorted node IDs, finding-line sets, golden byte-identical stdout) that Plans 02-05 need for their own `comm -13` regression gates and the D-04 byte-identity proof.
- `uv.lock` is clean (`uv lock --check` exits 0) and carries no unrelated diff, so Plan 02's `pyproject.toml` rename edits will produce a lockfile diff that is entirely attributable to the rename.
- No blockers. `.claude/` was not touched (D-03 respected). Nothing was pushed (D-05).

---
*Phase: 104-package-and-cli*
*Completed: 2026-10-03*
