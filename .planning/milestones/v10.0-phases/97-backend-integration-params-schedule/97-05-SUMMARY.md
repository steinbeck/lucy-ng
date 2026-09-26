---
phase: 97-backend-integration-params-schedule
plan: 05
subsystem: cli
tags: [click, cli, nus, nmrpipe, smile, import-safety, optional-extra]

requires:
  - phase: 97 (plan 01)
    provides: NusAcquisitionParams / NusSchedule models + nus package skeleton
  - phase: 97 (plan 02)
    provides: nus/params.py read_nus_params
  - phase: 97 (plan 03)
    provides: nus/schedule.py read_nus_schedule
  - phase: 97 (plan 04)
    provides: nus/backends NmrPipeSmileBackend + get_backend/list_available_backends
provides:
  - "lucy nus CLI group: check / params / schedule (all --format json)"
  - "Root-CLI registration of the nus group (add_command)"
  - "Empty [nus] optional-dependencies extra (D-02/NUS-05)"
  - "Import-safety guarantee: lucy_ng.cli imports with no [nus] extra installed"
affects: [phase-98-reconstruction, phase-99-peakpick-bridge, phase-100-portability]

tech-stack:
  added: []
  patterns:
    - "Import-safe CLI subgroup (deferred imports in command bodies, mirroring cli/webview.py)"
    - "click.Path(exists=True) + Path.resolve() on filesystem-path CLI args (threat T-97-01)"

key-files:
  created:
    - src/lucy_ng/cli/nus.py
  modified:
    - src/lucy_ng/cli/main.py
    - src/lucy_ng/nus/__init__.py
    - pyproject.toml
    - tests/test_cli_nus.py
    - tests/test_cli_main.py

key-decisions:
  - "Only the implemented check/params/schedule subcommands are registered — no dead reconstruct/pipeline stubs (D-02)"
  - "[nus] extra ships empty (no new pip deps this phase), following the prediction=[] precedent"
  - "Import-safety verified via a subprocess smoke check (no optional third-party leak to detect, unlike webview)"

patterns-established:
  - "NUS CLI mirrors cli/lsd.py check shape + cli/webview.py import-safety"

requirements-completed: [NUS-01, NUS-04, NUS-05]

duration: ~8min
completed: 2026-07-12
---

# Phase 97 (Plan 05): NUS CLI Integration Summary

**`lucy nus check/params/schedule` group wired to the wave-2 backend/params/schedule modules, import-safe, with an empty `[nus]` extra and a dependency-free core CLI**

## Performance

- **Duration:** ~8 min (execution + orchestrator recovery close-out)
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments
- `src/lucy_ng/cli/nus.py` — `lucy nus` Click group exposing `check`, `params`, `schedule`, each with `--format json`, deferred imports inside command bodies (import-safe), `click.Path(exists=True)` + `Path.resolve()` on `expdir` args, and fail-loud `SystemExit(1)` on an unusable backend.
- Root-CLI registration in `cli/main.py` via `add_command(nus)`; `lucy nus --help` lists exactly check/params/schedule and NOT reconstruct/pipeline (D-02).
- Empty-but-present `[nus]` optional-dependencies extra in `pyproject.toml` (NUS-05), with an inline note that Phase 97 needs no new pip deps.
- `nus/__init__.py` completed re-export surface (`read_nus_params`, `read_nus_schedule`, `NusBackend`, `get_backend`, `list_available_backends`).
- Import-safety smoke test proving `lucy_ng.cli` imports with no `[nus]` extra installed.

## Task Commits

1. **Task 1: lucy nus group (check/params/schedule), import-safe, --format json** — `f7d3d33` (feat)
2. **Task 2: register nus group + [nus] extra + import-safety test** — `3f49eee` (feat)

## Files Created/Modified
- `src/lucy_ng/cli/nus.py` — the `lucy nus` command group (check/params/schedule)
- `src/lucy_ng/cli/main.py` — imports + `add_command(nus)` registration
- `src/lucy_ng/nus/__init__.py` — full re-export list for the nus package
- `pyproject.toml` — empty `[nus]` optional extra
- `tests/test_cli_nus.py` — 13 CLI tests (check exit code, params/schedule JSON over all 3 fixtures)
- `tests/test_cli_main.py` — nus in top-level help + import-safety smoke test

## Decisions Made
- Followed plan as specified; D-02 (no dead stubs) and NUS-05 (dependency-free core) honored.

## Deviations from Plan

None in the implementation itself. **Process note (orchestrator recovery):** the executor
completed both tasks' work but returned without a `## PLAN COMPLETE` marker and left Task 2's
changes (main.py registration, `[nus]` extra, `nus/__init__` re-exports, import-safety test)
staged in the working tree, uncommitted, with SUMMARY.md unwritten. The orchestrator verified
the uncommitted changes were correct and complete, ran the targeted tests (22 passed) and the
full suite (1304 passed, 7 skipped, 1 xfailed — no regressions), then committed Task 2 as
`3f49eee` and authored this SUMMARY. No work was lost or duplicated.

## Issues Encountered
- Executor completion-signal drop on the final plan (see Deviations). Resolved via the
  workflow's filesystem/git spot-check recovery path — no re-execution needed.

## User Setup Required
None — no external service configuration. `lucy nus check` reports the (absent) NMRPipe+SMILE
backend and prints install/source guidance; a real install is only needed for Phase 98
reconstruction.

## Next Phase Readiness
- Phase 97 complete: backend detection + params/schedule parsing all shipped and CLI-exposed.
- Phase 98 (reconstruction) can now call `read_nus_params` / `read_nus_schedule` / `get_backend`
  and drive NMRPipe+SMILE. The `[nus]` extra is ready to receive Phase 98/99 pip-installable pieces.

---
*Phase: 97-backend-integration-params-schedule*
*Completed: 2026-07-12*
