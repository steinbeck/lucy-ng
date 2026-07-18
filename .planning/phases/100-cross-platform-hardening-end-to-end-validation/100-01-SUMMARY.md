---
phase: 100-cross-platform-hardening-end-to-end-validation
plan: 01
subsystem: infra
tags: [platform-detection, preflight-gate, cli, click, nus, rosetta, csh]

# Dependency graph
requires:
  - phase: 99-peak-pick-bridge-qc-gate-cli
    provides: "lucy nus check/reconstruct/pipeline CLI group + NusRunner.reconstruct() orchestrator + NmrPipeSmileBackend.diagnose()"
provides:
  - "detect_platform() stdlib-only arch/Rosetta/csh-tcsh detection helper"
  - "NmrPipeSmileBackend.diagnose() additive platform key"
  - "NusRunner.reconstruct() PORT-01 hard preflight gate (raises before any subprocess dispatch on a critical platform/tool gap)"
  - "lucy nus check platform section (text+json) with D-05 critical/soft exit-code semantics"
  - "--n-sigma CLI flag on lucy nus reconstruct/pipeline (D-04 tuning budget fully CLI-drivable)"
affects: [100-02, 100-03, VAL-01, VAL-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Preflight-gate-before-dispatch: resolve a diagnosis dict -> check for critical issues -> raise RuntimeError before any subprocess (mirrors the existing RECON-02 F2-plan gate shape)"
    - "diagnose()-style dict extended additively under a new namespaced key, never rewritten"

key-files:
  created:
    - src/lucy_ng/nus/platform_check.py
    - tests/nus/test_platform_check.py
    - tests/nus/test_platform_preflight_gate.py
    - tests/nus/test_cli_check.py
  modified:
    - src/lucy_ng/nus/backends/nmrpipe_smile.py
    - src/lucy_ng/nus/runner.py
    - src/lucy_ng/cli/nus.py
    - tests/nus/test_reconstruct_orchestration.py
    - tests/nus/test_cli_reconstruct.py

key-decisions:
  - "Preflight gate lives in NusRunner.reconstruct() itself (not only cli/nus.py) so every caller (CLI, tests, future VAL scripts) inherits the hard block, per RESEARCH Pitfall 1"
  - "Missing csh AND tcsh is classified critical (fail-loud block); Rosetta translation with tools present is soft-only (warn, never block), per D-05"
  - "sysctl -n sysctl.proc_translated non-'0'/'1' output (including any exception) resolves to None, never coerced to False, per RESEARCH Pitfall 3"
  - "--n-sigma added to both reconstruct and pipeline CLI commands (RESEARCH Open Question 1, resolved: CLI-drivable, not a separate tuning script)"

patterns-established:
  - "Pattern: PORT-01 preflight gate as literal first statement of an orchestrator method, before even resolving expdir/reading params"

requirements-completed: [PORT-01]

# Metrics
duration: 15min
completed: 2026-07-18
---

# Phase 100 Plan 01: Platform Preflight Gate + --n-sigma CLI Flag Summary

**Stdlib-only arch/Rosetta/csh-tcsh detection merged additively into `NmrPipeSmileBackend.diagnose()`, wired as a hard preflight gate that aborts `NusRunner.reconstruct()` before any subprocess dispatch on a critical platform/tool gap, plus `--n-sigma` exposed on `reconstruct`/`pipeline`.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-18T12:15:52Z (approx, from prior commit `1ee877a`)
- **Completed:** 2026-07-18T12:30:30Z
- **Tasks:** 2 completed
- **Files modified:** 9 (4 created, 5 modified)

## Accomplishments
- `detect_platform()` (new `src/lucy_ng/nus/platform_check.py`) classifies arch/OS/Rosetta-translation/csh-tcsh presence into `critical_platform_issues`/`soft_platform_warnings`, correctly resolving Rosetta status to `None` (not `False`) on any indeterminate/error/non-Darwin case
- `NmrPipeSmileBackend.diagnose()` additively carries this under a new `"platform"` key; all four pre-existing keys (`status`/`missing_tools`/`smile_available`/`hint`) stay byte-identical
- `NusRunner.reconstruct()` now hard-blocks (raises `RuntimeError`, "PORT-01 preflight gate") as its literal first statement whenever `self.backend.diagnose()` reports a critical missing-tool or platform gap — before params/schedule are even read, let alone any subprocess dispatched
- `lucy nus check` reports the platform section in both text and JSON output; exits 1 on a critical platform issue (in addition to the existing backend-unusable case) but never on a soft-only Rosetta warning (D-05)
- `--n-sigma` added to both `lucy nus reconstruct` and `lucy nus pipeline`, forwarded to `NusRunner.reconstruct(n_sigma=...)` — the D-04 tuning budget is now fully CLI-drivable without a separate script
- Repaired all four existing tests the new unconditional `diagnose()` call perturbs, per plan Task 2 mandatory test-repair list

## Task Commits

Each task was committed atomically:

1. **Task 1: detect_platform() helper + additive diagnose() platform key** - `757d0a9` (feat)
2. **Task 2: reconstruct() preflight gate + lucy nus check platform section + --n-sigma flag (+ repair 4 existing tests)** - `b901a18` (feat)

_No TDD RED/GREEN split was used — both tasks wrote implementation + tests together per the plan's `tdd="true"` behavior-first authoring, not a strict commit-per-phase RED/GREEN cycle._

## Files Created/Modified
- `src/lucy_ng/nus/platform_check.py` - New: `detect_platform()` (arch/os/rosetta_translated/csh_available/tcsh_available/critical_platform_issues/soft_platform_warnings), private `_rosetta_translated()` sysctl probe
- `src/lucy_ng/nus/backends/nmrpipe_smile.py` - `diagnose()` additively merges `detect_platform()`'s output under a new `"platform"` key
- `src/lucy_ng/nus/runner.py` - `NusRunner.reconstruct()` gains the PORT-01 preflight gate as its first statement
- `src/lucy_ng/cli/nus.py` - `check()` extended with a platform sub-report + D-05 exit-code fold-in; `--n-sigma` added to `reconstruct`/`pipeline`; both commands catch the new preflight `RuntimeError` for a clean one-line error + exit 1
- `tests/nus/test_platform_check.py` - New: 7 tests covering native arm64, Rosetta-translated, missing csh/tcsh, genuine-Intel/indeterminate sysctl, Linux, TimeoutExpired, diagnose() extension
- `tests/nus/test_platform_preflight_gate.py` - New: 4 tests covering the gate firing on missing tools, critical platform issues, passing through cleanly, and defensive handling of a diagnose() dict with no `"platform"` key
- `tests/nus/test_cli_check.py` - New: 5 tests covering JSON platform object, soft-only exit 0, critical exit 1, text-mode platform section, `--n-sigma` presence in `--help`
- `tests/nus/test_reconstruct_orchestration.py` - `_RecordingBackend` gained a clean gate-passing `diagnose()`; `test_f2_before_f1_gate_raises_before_any_subprocess` neutralizes `runner.backend.diagnose` before its own F2-specific assertion
- `tests/nus/test_cli_reconstruct.py` - `test_flags_thread_through_to_smile_invocation` monkeypatches `NmrPipeSmileBackend.diagnose` (classmethod) to a clean gate-passing dict so the CLI's real `NusRunner().reconstruct(...)` still reaches `run_stage`/SMILE argv assertions

## Decisions Made
- Preflight gate placed inside `NusRunner.reconstruct()` itself, not only in `cli/nus.py`, so every caller (CLI, any future VAL script, tests) inherits the hard block (RESEARCH Pitfall 1's explicit warning)
- `.get("platform", {})`/`.get("missing_tools", [])` used defensively throughout so a minimal test-double `diagnose()` dict (missing the `"platform"` key entirely) still works without a `KeyError`
- `--n-sigma` chosen as a genuine CLI flag (not a Python-only tuning script) per RESEARCH's Open Question 1 resolution, keeping the whole D-04 sweep drivable through `lucy nus pipeline`

## Deviations from Plan

None - plan executed exactly as written, including the mandatory four-test-repair list (all four repaired per the plan's explicit instructions, not weakened to accommodate the new gate).

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. (NMRPipe+SMILE local install remains a separate, already-documented manual prerequisite tracked by Plan 02/D-01, out of this plan's scope.)

## Next Phase Readiness
- PORT-01 fully satisfied: platform preflight reported (via `lucy nus check`) AND hard-enforced (via `NusRunner.reconstruct()`) before any run
- `lucy nus check` is now the literal gate Plan 02/VAL will use to confirm the local NMRPipe+SMILE install is ready before the real C20H32O2 reconstruction run
- `--n-sigma` ready for Plan 03's D-04 bounded tuning-budget sweep if the real reconstruction needs it
- No blockers for Plan 02 (portability matrix docs) or VAL-01/02 (real reconstruction + CASE convergence)

---
*Phase: 100-cross-platform-hardening-end-to-end-validation*
*Completed: 2026-07-18*

## Self-Check: PASSED

All created files verified present on disk; all task/plan commit hashes (757d0a9, b901a18, 4c9ce5c) verified present in git log.
