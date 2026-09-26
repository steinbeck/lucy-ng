---
phase: 99-peak-pick-bridge-qc-gate-cli
plan: 04
subsystem: nus
tags: [click, cli, qc-gate, nus, write-boundary, pydantic]

# Dependency graph
requires:
  - phase: 99-peak-pick-bridge-qc-gate-cli
    provides: "Plan 02's nus/qc.py run_qc_checks()/QcConfig/QcReport (QC-01/QC-02); Plan 03's nus/bridge.py build_spectrum2d()/bridge_peak_pick()/write_peak_json() with the pre-QC/post-QC two-call qc_report hook (PICK-01/PICK-03)"
provides:
  - "src/lucy_ng/cli/nus.py: qc <peaks-dir> (standalone QC-02 gate, D-08) and pipeline <expdir> (params -> schedule -> reconstruct -> peak-pick -> QC -> write, D-07) commands"
  - "PICK-02 satisfied: lucy nus pipeline is the reusable end-to-end command; every lucy nus subcommand (including qc/pipeline) supports --format json"
  - "QC-03 satisfied: D-07 write boundary -- FAIL quarantines to analysis/nus_recon/<expN>/qc_failed/ and exits non-zero, nothing consumable ever reaches analysis/nmr_peaks/; PASS/PARTIAL write the verdict-annotated payload there"
affects: [100-cross-platform-hardening-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared _build_qc_config() helper (deferred-import QcConfig internally) so qc and pipeline's D-04 threshold-override semantics never diverge"
    - "Causal re-build: bridge_peak_pick() called twice -- once pre-QC (qc_report=None, staged/verdict-less) to produce peaks for run_qc_checks() to grade, once post-QC (qc_report=report) to rebuild the FINAL verdict-annotated payload actually written -- never the staged payload"
    - "FAIL branch builds its quarantine 'reconstruction' block by hand from QcReport rather than re-invoking bridge_peak_pick(), since Plan 03's confidence_from_verdict() intentionally raises ValueError on a FAIL verdict (no honest confidence exists for un-consumable peaks)"
    - "mock_pipeline_stages test fixture (conftest.py): mocks NusRunner.reconstruct()/read_nus_params()/build_spectrum2d()/run_qc_checks() (no real NMRPipe+SMILE binary or Bruker data needed) while keeping bridge_peak_pick()/write_peak_json() genuinely real, isolating D-07's write-boundary logic (this plan's scope) from QC-01/QC-02's check algorithms (already proven real in Plan 02)"

key-files:
  created: []
  modified:
    - src/lucy_ng/cli/nus.py
    - tests/nus/conftest.py
    - tests/nus/test_cli_pipeline.py
    - tests/nus/test_write_boundary.py
    - tests/test_cli_nus.py

key-decisions:
  - "FAIL branch does not re-call bridge_peak_pick() (as the plan's Task 2 action text's 'Approach (a)' literally describes) because that call raises ValueError for a FAIL QcReport (Plan 03's confidence_from_verdict() design). Instead, the quarantine payload is the staged (verdict-less) cross-peaks with a hand-built 'reconstruction' block carrying the real FAIL verdict/violated-checks/thresholds -- satisfying the acceptance criterion (reconstruction.qc_verdict == the computed verdict) without violating Plan 03's no-confidence-for-FAIL invariant."
  - "Experiment-type detection reuses readers/bruker.py::_detect_experiment_type() (imported cross-module) rather than reimplementing pulse-program-to-experiment-type mapping -- Don't-Hand-Roll; readers/bruker.py is not in the byte-unchanged protected set (only cli/pick.py and case.md are)."
  - "lucy nus peak-pick standalone subcommand NOT added (D-08 planner discretion) -- pipeline's internal staged/final bridge_peak_pick() calls cover the need; keeps the CLI surface to exactly qc + pipeline as scoped by PICK-02/QC-03."
  - "Pipeline CLI tests mock reconstruction/params/build_spectrum2d and the QC verdict itself (not real HSQC/HMBC/COSY fixture data), keeping bridge_peak_pick()/write_peak_json()/the write-boundary branching genuinely real -- QC-01/QC-02's six check algorithms already have their own real-fixture proof in Plan 02's test_qc_checks.py/test_qc_regression.py, so this plan's tests target its own scope (CLI wiring + D-07) rather than re-proving the check algorithms a second time."

requirements-completed: [PICK-02, QC-03]

# Metrics
duration: 33min
completed: 2026-07-16
---

# Phase 99 Plan 04: Peak-Pick Bridge + QC Gate CLI Summary

**`lucy nus qc <peaks-dir>` (standalone QC-02 gate) and `lucy nus pipeline <expdir>` (full reconstruct -> peak-pick -> QC -> D-07 write/quarantine boundary) added to the import-safe `lucy nus` CLI group, closing PICK-02/QC-03**

## Performance

- **Duration:** 33 min
- **Started:** 2026-07-16T19:44:17+02:00 (immediately after Plan 03 close)
- **Completed:** 2026-07-16T20:17:08+02:00
- **Tasks:** 2
- **Files modified:** 5 (1 CLI module extended, 4 test files)

## Accomplishments
- Built `lucy nus qc <peaks-dir>`: keyword-glob-matched QC gate runnable against any peaks directory, D-04 CLI-overridable thresholds (`--ridge-fail`/`--coverage-floor`/`--c13-tol`/`--h1-tol`), `--format json`/text, exits non-zero on FAIL. Proven directly against the real known-bad (FAIL) and synthetic-clean (PASS) fixtures via the CLI, not just `run_qc_checks()` directly.
- Built `lucy nus pipeline <expdir>`: the full `NusRunner.reconstruct()` -> staged (verdict-less) `bridge_peak_pick()` -> `run_qc_checks()` (the SAME code path `qc` calls standalone) -> causal-rebuild `bridge_peak_pick()` -> D-07 write-boundary chain in one process.
- Implemented D-07: PASS/PARTIAL write the verdict-annotated consumable payload to `analysis/nmr_peaks/*.json` (PARTIAL also warns on violated soft checks to stderr); FAIL writes nothing consumable and quarantines the verdict-annotated payload + `qc_report.json` to `analysis/nus_recon/<expN>/qc_failed/`, exiting non-zero -- extending the FIX-10 constraint-hardness-guard spirit to reconstruction-derived peaks.
- Verified the causal-ordering fix end-to-end: the file actually written under `analysis/nmr_peaks/` carries the real computed `reconstruction.qc_verdict` and verdict-derived per-peak `confidence` ("high" for PASS, "low" for PARTIAL) -- proving the FINAL rebuilt payload was written, never the step-3 staged/verdict-less one.
- `case.md` and `cli/pick.py` remain byte-unchanged (`git diff --exit-code` == 0 for both, asserted in every task verify command).

## Task Commits

Each task was committed atomically:

1. **Task 1: `lucy nus qc` standalone QC-02 gate command** - `211f04a` (feat)
2. **Task 2: `lucy nus pipeline` + D-07 write/quarantine boundary** - `c69e711` (feat)

_Note: both tasks modify the same file (`src/lucy_ng/cli/nus.py`) with a natural implementation dependency (Task 2's `pipeline` reuses Task 1's `_build_qc_config()` helper and calls `run_qc_checks()`). Following Phase 99 Plan 02's established precedent for this exact situation, the full implementation was written in one pass, then the file (and its accompanying test files) were temporarily truncated back to a Task-1-only state, independently verified against Task 1's own verify command, committed, then restored to the full Task 2 state and independently verified again before the second commit. Both commits are individually correct and pass their respective plan-specified verify commands standalone._

## Files Created/Modified
- `src/lucy_ng/cli/nus.py` - `_build_qc_config()` shared threshold-override helper, `qc` command (Task 1), `pipeline` command + D-07 write/quarantine branching (Task 2)
- `tests/nus/conftest.py` - `mock_pipeline_stages` fixture: mocks `NusRunner.reconstruct()`/`read_nus_params()`/`build_spectrum2d()`/`run_qc_checks()` for deterministic, no-external-binary `pipeline` CLI tests while keeping `bridge_peak_pick()`/`write_peak_json()` real
- `tests/nus/test_cli_pipeline.py` - `qc`/`pipeline` command tests: JSON/text format, threshold overrides, help text, `--format json` coverage across all six `lucy nus` subcommands (Wave-0 stubs replaced)
- `tests/nus/test_write_boundary.py` - Real PASS/PARTIAL/FAIL write-boundary assertions, including the verdict-content and staged-payload-never-leaks assertions (Wave-0 stubs replaced)
- `tests/test_cli_nus.py` - Updated `test_nus_group_help_lists_only_implemented_subcommands` to include `qc` then `pipeline` (fixed alongside a pre-existing latent bug in this test -- see Deviations)

## Decisions Made
- See `key-decisions` in frontmatter: the FAIL-branch quarantine payload is hand-built from the `QcReport` rather than re-invoking `bridge_peak_pick()` (which would raise on a FAIL verdict by Plan 03's own design); experiment-type detection reuses `readers/bruker.py::_detect_experiment_type()`; no standalone `lucy nus peak-pick` subcommand added; pipeline CLI tests mock the reconstruction/QC-verdict seam while keeping the write-boundary code path real.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_all_nus_subcommands_support_format_json`'s Wave-0 assertion checked the wrong click.Parameter attribute**
- **Found during:** Task 2 (writing `test_cli_pipeline.py`'s `--format json` coverage test)
- **Issue:** The Plan 01 Wave-0 stub asserted `"format" in [p.name for p in command.params]`. Click's `--format` option is bound to the Python variable `output_format` (`click.option("--format", "output_format", ...)`), so `p.name` is `"output_format"` for every command -- the literal stub assertion would fail for `check`/`params`/`schedule`/`reconstruct` too, not just the new `qc`/`pipeline` commands, and was never actually exercised while skipped in Wave 0.
- **Fix:** Rewrote the assertion to check the actual CLI flag string via `p.opts` (`any("--format" in p.opts for p in command.params)`), which correctly reflects what a user types.
- **Files modified:** `tests/nus/test_cli_pipeline.py`
- **Verification:** `pytest tests/nus/test_cli_pipeline.py -q -k all_nus_subcommands` passes for all six commands.
- **Committed in:** `c69e711` (Task 2 commit)

**2. [Rule 1 - Bug] Pre-existing `test_nus_group_help_lists_only_implemented_subcommands` assertion went stale**
- **Found during:** Task 1 (adding `qc` to the `nus` group)
- **Issue:** `tests/test_cli_nus.py` (from Phase 98 Plan 06) hard-coded the exact set of registered subcommands (`{"check", "params", "schedule", "reconstruct"}`) as a "no dead stubs" guard. Adding `qc`/`pipeline` legitimately grows this set, so the existing assertion started failing on the full-suite run (caught immediately after Task 2, before any commit).
- **Fix:** Updated the assertion to the new, legitimately-larger set at each task's own commit point (`qc` added in Task 1's interim state; `qc` + `pipeline` in Task 2's final state), preserving the test's original intent (guard against dead/unregistered stubs) rather than weakening or deleting it.
- **Files modified:** `tests/test_cli_nus.py`
- **Verification:** `pytest tests/test_cli_nus.py -q` passes; full suite green (1373 passed, 8 skipped, 1 xfailed) after both commits.
- **Committed in:** `211f04a` (Task 1), `c69e711` (Task 2)

---

**Total deviations:** 2 auto-fixed (2 bugs -- both in test assertions, not production code; no functional/architectural changes)
**Impact on plan:** None on functionality. Both fixes correct pre-existing test-suite defects surfaced by legitimately adding new commands; neither touches `cli/nus.py`'s production logic.

## Issues Encountered
- `mypy src/lucy_ng/cli/nus.py` reports zero errors in the module itself; the 76 errors surfaced by a bare `mypy src/lucy_ng/cli/nus.py` invocation are pre-existing repo-wide errors mypy picks up by following transitive imports (`prediction/`, `visualization/`, `nus/bridge.py`'s untyped-nmrglue note, `cli/database.py`) -- identical baseline behavior documented in Plan 02/03's summaries, none touched by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- PICK-02/QC-03 are now complete. `lucy nus pipeline <expdir>` is the reusable end-to-end NUS CASE-run command (`params -> schedule -> reconstruct -> peak-pick -> QC -> write`); every `lucy nus` subcommand (`check`/`params`/`schedule`/`reconstruct`/`qc`/`pipeline`) supports `--format json`.
- **Phase 99 (Peak-Pick Bridge + QC Gate + CLI) is now fully complete**: PICK-01/02/03 and QC-01/02/03 all satisfied across Plans 01-04. `nus/bridge.py`, `nus/qc.py`, and `cli/nus.py::qc`/`pipeline` are ready for Phase 100's real C20H32O2 end-to-end validation.
- `case.md` and `cli/pick.py` remain byte-unchanged throughout the phase (asserted at every plan's commit point).
- The A1/A2 QC-threshold LOW-MEDIUM-confidence flags from 99-RESEARCH.md (signal-to-ridge FAIL threshold, HSQC-coverage floor) remain unvalidated against a real clean reconstruction -- Phase 100's own deliverable per the research's Assumptions Log. `--ridge-fail`/`--coverage-floor` are already CLI-overridable (D-04) if Phase 100's real C20H32O2 run needs recalibration.
- Full test suite green: 1373 passed, 8 skipped, 1 xfailed -- up from Plan 03's 1360 passed/14 skipped baseline; the delta is the 18 newly-activated/added PICK-02/QC-03 tests plus 2 pre-existing test-assertion fixes (net figure includes some Wave-0 stub tests being replaced 1:1 rather than purely added).
- No blockers or concerns for Phase 100.

---
*Phase: 99-peak-pick-bridge-qc-gate-cli*
*Completed: 2026-07-16*

## Self-Check: PASSED

All 5 modified files verified present on disk (`src/lucy_ng/cli/nus.py`,
`tests/nus/conftest.py`, `tests/nus/test_cli_pipeline.py`,
`tests/nus/test_write_boundary.py`, `tests/test_cli_nus.py`); all three
commit hashes (`211f04a`, `c69e711`, `ae58123`) verified present in git log.
