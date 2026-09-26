---
phase: 98-reconstruction-processing
plan: 06
subsystem: nus-reconstruction
tags: [click, cli, smile, nmrpipe, subprocess]

requires:
  - phase: 98-reconstruction-processing (Plan 05)
    provides: NusRunner.reconstruct(expdir) whole-pipeline orchestration entrypoint
  - phase: 97-nus-cli-integration
    provides: cli/nus.py import-safe group + deferred-import/--format json convention
provides:
  - "lucy nus reconstruct <expdir> CLI command"
  - RECON-05 knob flags (--iterations/--threshold/--virtual-echo) with convergence-based defaults
  - D-02 phase-override flags (--f2-p0/--f2-p1/--f1-p0/--f1-p1)
affects: [99 (peak-pick bridge / lucy nus pipeline will likely reuse this command's flag surface), 100 (end-to-end §8-gate validation runs this command)]

tech-stack:
  added: []
  patterns:
    - "reconstruct command mirrors params/schedule exactly: click.Path(exists=True) expdir arg, --format text|json, deferred `from lucy_ng.nus.runner import NusRunner` inside the command body, Path(expdir).resolve() before use"
    - "Descriptive lucy-ng flag names (--iterations/--threshold/--virtual-echo) map internally to SMILE's -maxIter/-thresh/-EA -- insulates the CLI contract from SMILE's own flag-name churn (RESEARCH.md Alternatives Considered)"

key-files:
  created: []
  modified:
    - src/lucy_ng/cli/nus.py
    - tests/nus/test_cli_reconstruct.py
    - tests/test_cli_nus.py

key-decisions:
  - "Flag named --iterations (not the Plan-01 stub's --max-iter guess) per RESEARCH.md's own Alternatives Considered recommendation: expose lucy-ng's own descriptive flag names, not SMILE's raw flag names 1:1"
  - "Rewrote tests/nus/test_cli_reconstruct.py's two Wave-0 stubs: fixed the stage-name lookup from lowercase \"smile\" to \"SMILE\" (matching NmrPipeSmileBackend.reconstruct_indirect's actual run_stage('SMILE', ...) call name) and added a tmp_path fixture copy before invoking the CLI, since a literal expdir=nus_fixture_dir(...) invocation would have NusRunner._stage_dir() write a real analysis/nus_recon/ directory into the tracked tests/fixtures/nus/ tree (mirrors Plan 05's own _copy_fixture fix for the same root cause)"

patterns-established:
  - "D-02 phase-override CLI flags (--f2-p0/--f2-p1/--f1-p0/--f1-p1) default to NusRunner.reconstruct()'s own provisional constants (0.0/0.0/90.0/0.0), keeping the CLI defaults and the library defaults as one source of truth rather than a second hard-coded copy"

requirements-completed: [RECON-05]

duration: ~15min
completed: 2026-07-13
---

# Phase 98 Plan 06: `lucy nus reconstruct` CLI Command Summary

**`lucy nus reconstruct <expdir>` thin Click wrapper around `NusRunner.reconstruct()`, exposing RECON-05's --iterations/--threshold/--virtual-echo knobs plus D-02's four phase-override flags, with --format json and the Phase-97 import-safety convention preserved; the D-02 "no dead stubs" regression guard now expects `reconstruct` in the registered command set.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-13T12:54:10Z
- **Tasks:** 2/2 completed
- **Files modified:** 3

## Accomplishments

- Added `@nus.command("reconstruct")` to `src/lucy_ng/cli/nus.py`: `click.argument("expdir", type=click.Path(exists=True))`, the existing `--format text|json` option, RECON-05 knob options (`--iterations` int default 500 with an upper-bound-not-sole-stopping-rule help string, `--threshold` float default 0.8, `--virtual-echo/--no-virtual-echo` default on), and D-02 phase-override options (`--f2-p0`/`--f2-p1`/`--f1-p0`/`--f1-p1`, defaults `0.0`/`0.0`/`90.0`/`0.0` matching `NusRunner.reconstruct()`'s own provisional constants).
- Command body uses a deferred `from lucy_ng.nus.runner import NusRunner` (top-level import safety preserved -- verified via `python -c "import lucy_ng.cli.nus"` and the existing `test_no_top_level_nus_submodule_import` test), resolves `Path(expdir).resolve()`, calls `NusRunner().reconstruct(...)` threading all flags through by name, and emits `json.dumps(result.to_dict(), indent=2)` for `--format json` or a short human summary (backend/success/stage_dir/processed_spectrum) otherwise.
- Rewrote the two RECON-05 Wave-0 stub tests in `tests/nus/test_cli_reconstruct.py` (both previously `@pytest.mark.skip`'d): `test_reconstruct_help_lists_knob_flags` now asserts the full real flag surface (`--iterations`, `--threshold`, `--virtual-echo`/`--no-virtual-echo`, all four phase-override flags, `--format`); `test_flags_thread_through_to_smile_invocation` copies the `exp3_hsqc` fixture into `tmp_path` before invoking the CLI (avoiding a real-file side effect on the tracked fixture tree), invokes `lucy nus reconstruct <expdir> --iterations 750 --threshold 0.9 --no-virtual-echo`, and asserts both values land in the SMILE `run_stage` call's argv and that `-EA` is correctly omitted when `--no-virtual-echo` is passed for this echo-antiecho (FnMODE=6) fixture.
- Companion edit: `tests/test_cli_nus.py::TestImportSafety::test_nus_group_help_lists_only_implemented_subcommands` now asserts `set(nus.commands) == {"check", "params", "schedule", "reconstruct"}` (still an exact-set equality, not weakened to a subset check) plus a `"reconstruct" in result.output` `--help` assertion.

## Task Commits

1. **Task 1: reconstruct command with RECON-05 knob flags + phase overrides + --format json** - `fe0e2fc` (feat)
2. **Task 2: Companion edit -- update the import-safety regression guard** - `1d93bbd` (test)

## Files Created/Modified

- `src/lucy_ng/cli/nus.py` - Added the `reconstruct` command (deferred `NusRunner` import, RECON-05 knob flags, D-02 phase-override flags, `--format json`); updated the module docstring to describe the new deferred-import target.
- `tests/nus/test_cli_reconstruct.py` - Rewrote both Wave-0 stub tests to match the real flag surface (`--iterations`, correct `"SMILE"` stage-name casing) and to copy the fixture into `tmp_path` before invoking the CLI.
- `tests/test_cli_nus.py` - Updated the D-02 no-dead-stubs regression guard's expected command set and `--help` assertions to include `"reconstruct"`.

## Decisions Made

- **`--iterations`, not `--max-iter`:** the Plan-01 Wave-0 stub guessed `--max-iter` as the flag name, but 98-RESEARCH.md's own Alternatives Considered table explicitly recommends lucy-ng's own descriptive flag names over SMILE's raw flag names 1:1 (`--iterations` maps internally to `-maxIter`) -- implemented per the plan's own action text (`--iterations`), and the stub test was rewritten to match rather than literally filling in the stale guessed name.
- **Stage-name casing fix (`"SMILE"` not `"smile"`):** `NmrPipeSmileBackend.reconstruct_indirect()` (Plan 03) calls `run_stage("SMILE", argv, ...)` -- the Wave-0 stub's `call[0] == "smile"` lookup would never have matched, silently returning `next()`'s `StopIteration`. Fixed to the actual casing used by the shipped code.
- **Fixture copy to `tmp_path` before CLI invocation:** the stub's literal `expdir=nus_fixture_dir("exp3_hsqc")` (no copy) would have caused `NusRunner._stage_dir()` to `mkdir(parents=True, exist_ok=True)` a real `analysis/nus_recon/exp3_hsqc/` directory under the tracked `tests/fixtures/nus/exp3_hsqc/` tree, and `process_indirect()`'s `_write_ppm_calibration_sidecar()` would write a `processed_ppm_axis.json` sidecar there too -- both real filesystem side effects on tracked fixtures. Copied to `tmp_path` first (mirroring Plan 05's own `_copy_fixture` fix for the identical root cause in `test_reconstruct_orchestration.py`). Verified via `git status --short` showing no untracked files after the full `tests/nus/` + `tests/test_cli_nus.py` run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed two latent bugs in the Plan-01 Wave-0 stub tests before turning them GREEN**
- **Found during:** Task 1, implementing the RECON-05 stub tests in `tests/nus/test_cli_reconstruct.py`
- **Issue:** The as-written stubs (a) asserted `--max-iter` (a guessed flag name never actually specified by RESEARCH.md's own naming recommendation, which the plan's own action text overrides to `--iterations`), and (b) looked up `call[0] == "smile"` (lowercase) against `mock_run_stage["calls"]`, which would never match the actual `"SMILE"` (uppercase) stage name `NmrPipeSmileBackend.reconstruct_indirect()` passes to `run_stage()`. Additionally, invoking the CLI directly against `nus_fixture_dir("exp3_hsqc")` without a `tmp_path` copy would write real `analysis/nus_recon/` output into the tracked fixture tree.
- **Fix:** Renamed the flag assertions/CLI args to `--iterations`; corrected the stage-name lookup to `"SMILE"`; added a `_copy_fixture()` helper (mirroring Plan 05's own) so the fixture is copied to `tmp_path` before the CLI invocation.
- **Files modified:** `tests/nus/test_cli_reconstruct.py`
- **Verification:** `pytest tests/nus/test_cli_reconstruct.py -q` passes both tests (0 skipped); `git status --short` after the full `tests/nus/` suite run shows no untracked files under `tests/fixtures/nus/`.
- **Committed in:** `fe0e2fc` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug fix, three related sub-issues in the same stub file).
**Impact on plan:** All fixes were necessary for the plan's own stated acceptance criteria (`--iterations`, `--threshold`, `--virtual-echo/--no-virtual-echo` in `--help`; flags threading through to the actual SMILE argv) to be verifiable at all -- no scope creep beyond what Task 1's action text already specified.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `lucy nus reconstruct <expdir>` is a complete, tested CLI entrypoint: `--help` lists all RECON-05 knobs, D-02 phase overrides, and `--format`; flag values verifiably thread through to `NusRunner.reconstruct()` and SMILE's own argv.
- Phase 98 (Reconstruction + Processing) requirements RECON-01 through RECON-05 are now all closed across Plans 02-06 (RECON-01/02 by Plan 05's orchestration, RECON-03 by Plans 02/03's FnMODE branching, RECON-04 by the shared `run_stage()` fail-loud wrapper, RECON-05 by this plan's CLI flags).
- No blockers for Phase 99 (peak-pick bridge, `nus/bridge.py`, `lucy nus pipeline`): `NusReconstructionResult.processed_spectrum`/`stage_dir`/`stage_outputs` are the concrete artefact-path contract Phase 99 will consume, and this plan's CLI flag surface establishes the pattern a future `lucy nus pipeline` command would extend.
- The QF/magnitude COSY `convert_first` branch (Plan 03's PROVISIONAL A1/A3 flag) and the F1/F2 phase-constant defaults (A2, this plan's own CLI-overridable defaults) remain empirically unverified pending real NMRPipe+SMILE access -- unchanged from Plan 05, not a new blocker introduced by this plan's CLI wiring.

---
*Phase: 98-reconstruction-processing*
*Completed: 2026-07-13*

## Self-Check: PASSED

- FOUND: src/lucy_ng/cli/nus.py
- FOUND: tests/nus/test_cli_reconstruct.py
- FOUND: tests/test_cli_nus.py
- FOUND: SUMMARY.md (this file)
- FOUND commit: fe0e2fc (Task 1)
- FOUND commit: 1d93bbd (Task 2)
