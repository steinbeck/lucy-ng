---
phase: 102-cli-peak-pick-bridge-qc-reuse
plan: 03
subsystem: cli
tags: [jcamp-dx, click-cli, qc-gate, peak-pick-bridge, write-boundary]

# Dependency graph
requires:
  - phase: 102-cli-peak-pick-bridge-qc-reuse (wave 1, plan 01)
    provides: "JcampReader.read/read_1d/read_2d with the homonuclear procs_index fix (COSY/NOESY readable)"
  - phase: 102-cli-peak-pick-bridge-qc-reuse (wave 1, plan 02)
    provides: "bridge_peak_pick_1d()/peak_json_filename() -- the thin 1D peak-pick bridge"
provides:
  - "lucy jcamp <dir-or-files> -- the single top-level CLI command delivering JCLI-01/JCLI-02: read -> pick -> QC -> write in one invocation"
  - "Directory discovery (*.dx, case-insensitive) and explicit-file-list input modes, mutually exclusive by design"
  - "D-06 non-fatal skip path for NOESY/unsupported experiments, with named read-failure tracking that is always fatal"
  - "Staged/final two-call QC wiring (run_qc_checks() invoked exactly once over the whole staged directory) and the D-07 write boundary (FAIL quarantines, never creates analysis/nmr_peaks/)"
affects: [102-04-fixture-backed-integration-tests, 103-jcamp-e2e-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Staged/final two-call QC wiring copied verbatim from cli/nus.py::pipeline (lines 584-637): bridge_peak_pick(qc_report=None) for every file first, run_qc_checks() exactly once, then a causal re-build (or FAIL hand-build) before any consumable write"
    - "Work root sits beside out_root (out_root.parent / 'jcamp_ingest'), never inside it, so staged/quarantine JSON can never be picked up by a later `lucy nus qc <out_root>` run"
    - "Additive 'source' provenance block ({format, file, reader, reconstruction_origin}) attached to every payload -- resolves the CONTEXT.md 'Claude's Discretion' provenance item without touching the stable per-peak schema"

key-files:
  created:
    - src/lucy_ng/cli/jcamp.py
    - tests/test_cli_jcamp.py
  modified:
    - src/lucy_ng/cli/main.py

key-decisions:
  - "RECON_BACKEND = \"jcamp\" (short, deliberate) -- the unchanged bridge interpolates this into every per-peak note; a long provenance string would multiply across hundreds of peaks. Full provenance lives in the additive `source` block instead."
  - "Duplicate-experiment guard shares one `staged_types` set across both 1D nuclei (\"1H\"/\"13C\") and 2D experiment types (\"HSQC\"/\"HMBC\"/\"COSY\") -- no namespace collision is possible between the two vocabularies, so one set suffices without extra bookkeeping."
  - "The command docstring documents (does not fix) the inherited QcConfig.default() quaternary-override behaviour (Pitfall 4): classification_source will read \"override\" using the five compiled-in Sec.8 shifts whenever no DEPT file is present, because qc.py is byte-protected this phase."
  - "Exit-code rule: FAIL verdict OR any non-empty `failed` list forces SystemExit(1), even on PASS/PARTIAL -- a file that could not be read must never be reported as a clean run. A non-empty `skipped` list alone (D-06) stays non-fatal."

requirements-completed: [JCLI-01, JCLI-02]

# Metrics
duration: 15min
completed: 2026-07-25
---

# Phase 102 Plan 03: `lucy jcamp` CLI Command Summary

**Single `@click.command("jcamp")` (not a group) that discovers a JCAMP-DX directory or explicit file list, routes 1D 1H/13C through the Plan-02 bridge and 2D HSQC/HMBC/COSY through the byte-unchanged Phase-99 `bridge_peak_pick()`, runs the byte-unchanged QC gate exactly once over the whole staged set, and enforces the D-07 write/quarantine boundary -- proving the Phase-99 bridge+QC design generalizes to a second, entirely different upstream source.**

## Performance

- **Duration:** ~15 min (base merge 2026-07-25T12:07:49+02:00 to final commit 2026-07-25T12:16:47+02:00, plus prior context-reading)
- **Started:** 2026-07-25T10:00:00Z (approx, first Read call)
- **Completed:** 2026-07-25T10:16:53Z
- **Tasks:** 2 completed
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- `lucy jcamp <dir-or-files>` exists as a single registered top-level command with `--out`, `--snr-floor`, and `--format json`, and no subcommands (D-01 verified: `isinstance(jcamp, click.Group)` is `False`; `runner.invoke(jcamp, ["qc", "/tmp"])` exits non-zero).
- Directory discovery (`suffix.lower() == ".dx"`, avoiding double-matching a `.DX` file on a case-insensitive filesystem) and an explicit file-list mode are both implemented; mixing a directory with explicit files is rejected with `SystemExit(2)`.
- 2D HSQC/HMBC/COSY files route through the unchanged `nus/bridge.py::bridge_peak_pick()`; 1D 1H/13C files route through the Plan-02 `bridge_peak_pick_1d()`; NOESY and any other unrecognized experiment is read but skipped with a named, non-fatal warning (D-06). A read failure (`JcampReader.read()` raising) is tracked distinctly in `failed` and always forces a non-zero exit, even on an otherwise-clean PASS/PARTIAL verdict.
- The QC gate (`run_qc_checks()`) is invoked **exactly once** over the fully-staged directory -- verified both by a passing test suite and by `grep -c "run_qc_checks(" src/lucy_ng/cli/jcamp.py` printing `1`.
- The D-07 write boundary is implemented: `out_root` is never created before the verdict is known; a FAIL verdict quarantines the verdict-annotated payloads plus `qc_report.json` to `<out_root>.parent/jcamp_ingest/qc_failed/` and exits non-zero, writing nothing to the consumable location.
- Every reused module (`nus/`, `cli/pick.py`, `processing/peak_picker*.py`, `.claude/`) is provably byte-unchanged since `22f2b52` (`git diff --exit-code` exits 0).
- Full test suite: **1424 passed, 15 skipped, 1 xfailed** (up from the 1408-passed Phase-101 baseline via wave-1's + this plan's 9 new tests, net of environmental skip-count deltas already documented in the wave-1 summaries). `mypy src/lucy_ng` and `ruff check src tests` report the exact same pre-existing baseline counts (119 / 282) with zero new errors attributable to this plan's files.

## Task Commits

Each task was committed atomically:

1. **Task 1: `src/lucy_ng/cli/jcamp.py` -- discovery, routing, staged QC, write boundary** - `b840083` (feat)
2. **Task 2: Register jcamp on the lucy group + CLI-surface and import-safety tests** - `465f839` (test)

## Files Created/Modified

- `src/lucy_ng/cli/jcamp.py` - The `lucy jcamp` command: import-safe module (all `lucy_ng.readers.jcamp`/`lucy_ng.nus.bridge`/`lucy_ng.nus.qc`/`lucy_ng.processing.jcamp_1d_bridge`/`lucy_ng.models` imports deferred into the command body), `SUPPORTED_2D`/`SUPPORTED_1D`/`RECON_BACKEND` module constants, `_source_block()` helper, and the full discovery -> stage -> QC-once -> write-boundary -> output -> exit-code body.
- `src/lucy_ng/cli/main.py` - `from lucy_ng.cli.jcamp import jcamp` added in alphabetical position (between `identify` and `lsd`); `cli.add_command(jcamp)` added after `nus`; one new line in the `cli()` group docstring's `\b`-fenced command list.
- `tests/test_cli_jcamp.py` - `TestJcampCliSurface` (7 tests: help text, top-level registration, D-01 no-subcommand invariant, missing-argument/nonexistent-path validation, empty-directory rejection with no `analysis/` tree created, directory-mixed-with-files rejection using the real committed `C20H32O2_13C.dx` fixture) + `TestJcampImportSafety` (2 tests: clean import, no eager `lucy_ng.nus.qc`/`lucy_ng.readers.jcamp` module leak) -- 9 tests total.

## Decisions Made

- **`_source_block()` provenance shape** (resolves CONTEXT.md's "Claude's Discretion" provenance item): `{"format": "JCAMP-DX", "file": <name>, "reader": "lucy_ng.readers.jcamp.JcampReader", "reconstruction_origin": "external -- spectrum was already reconstructed outside lucy-ng (e.g. TopSpin/mddnmr compressed sensing); lucy-ng only read and peak-picked it"}`, attached as an additive top-level `"source"` key on both 1D and 2D payloads. Verified safe against the byte-unchanged gate: `nus/qc.py::_load_peaks` only requires `cross_peaks`, and `_load_1d_shifts` only reads `peaks` -- extra top-level keys are ignored.
- **Work-root layout:** `work_root = out_root.parent / "jcamp_ingest"`, with `staged_dir = work_root / "staged"` and `quarantine_dir = work_root / "qc_failed"` -- deliberately beside `out_root`, never inside it, so a later `lucy nus qc <out_root>` run can never accidentally glob staged/quarantine JSON (102-RESEARCH.md Pitfall 3), and so a FAIL run leaves `analysis/nmr_peaks/` genuinely absent.
- **Two exit-code rules, both documented inline:** (1) `SystemExit(1)` on a FAIL verdict; (2) `SystemExit(1)` whenever `failed` is non-empty, even on PASS/PARTIAL -- a file that could not be read must never be reported as a clean run. A non-empty `skipped` list alone (D-06 unsupported-experiment skips) stays non-fatal and exits 0.
- **No CLI threshold-override flags on this command** (Assumption A3, as the plan specified): standalone re-grading with custom thresholds is `lucy nus qc <out-dir>`, named explicitly in the command's docstring.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rephrased an inline comment to satisfy the plan's own literal `grep -c` acceptance criterion**
- **Found during:** Task 1, post-implementation verification.
- **Issue:** The plan's acceptance criteria require `grep -c "run_qc_checks(" src/lucy_ng/cli/jcamp.py` to print exactly `1` (the QC gate invoked exactly once). The first draft included an explanatory comment ("never call `run_qc_checks()` once per file") immediately above the real call, which itself contains the literal substring `run_qc_checks(`, making the grep count `2` -- a self-contradiction between the plan's own action text (which asks for a comment naming the anti-pattern) and its acceptance criterion's literal substring match. Same class of plan self-contradiction already documented in 102-02-SUMMARY.md's deviation log.
- **Fix:** Reworded the comment to "never invoke the QC gate once per file" -- identical meaning, no literal `run_qc_checks(` substring.
- **Files modified:** `src/lucy_ng/cli/jcamp.py`.
- **Verification:** `grep -c "run_qc_checks(" src/lucy_ng/cli/jcamp.py` -> `1`; `mypy`/`ruff` re-passed clean; behavior unchanged (the fix was to prose only).
- **Committed in:** `b840083` (Task 1 commit) -- fixed before the commit, no separate fix-up commit needed.

---

**Total deviations:** 1 auto-fixed (Rule 1, plan-wording self-contradiction, cosmetic only).
**Impact on plan:** None on behavior -- comment wording only, no scope creep.

## Issues Encountered

- **Worktree base drift at agent startup:** this worktree's HEAD was found on an older, unrelated commit (`dfac9bb`, a stale v9.3-milestone-archive point) rather than the expected wave-1-merged base (`fa51783`). Corrected per the mandatory `<worktree_branch_check>` protocol via `git reset --hard fa517836c47af8a6e615a0ee365b6cb1c2214971` before any file was read or written -- not a plan deviation, an agent-harness environment hazard, resolved before Task 1 began.
- **`PYTHONPATH` shadowing** (same as both wave-1 plans' own summaries note): this worktree's ambient `PYTHONPATH`/editable install resolves to the main repo checkout by default. All verification commands in this plan were run with `PYTHONPATH="$(pwd)/src"` explicitly prepended.
- **mypy/ruff baseline is not zero-error, unrelated to this plan** (same pre-existing condition documented in both wave-1 summaries): 119 mypy errors / 282 ruff errors, identical counts to the wave-1-close baseline, none attributable to `src/lucy_ng/cli/jcamp.py` or `tests/test_cli_jcamp.py` (both files individually clean under `mypy`/`ruff`).

## Proof-Level Honesty (per 102-RESEARCH.md Pitfall 6 / this plan's `<verification>` section)

This plan proves the CLI SURFACE only -- registration, help text, option names, argument validation, import safety, and the absence of a subcommand surface, plus the QC-gate-called-exactly-once and byte-unchanged-modules structural invariants. It proves NOTHING about end-to-end behaviour on real spectra (no test in this plan invokes `lucy jcamp` against a real directory of committed fixtures and asserts a written peak list or a real QC verdict) -- that is explicitly Plan 04's job (committed trimmed fixtures) and Phase 103 / JVAL's job (the real uncommitted 2048x2048 dataset), matching the plan's own stated phase boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `lucy jcamp` is fully wired and registered; Plan 04 can now build fixture-backed integration tests directly against this command using the already-committed trimmed HSQC/COSY/HMBC/NOESY fixtures and the real 1H/13C fixtures (all present in `tests/fixtures/jcamp/` from wave 1).
- The staged/final two-call QC pattern and the D-07 write boundary are implemented and structurally verified (QC gate invoked exactly once; `out_root` never created before the verdict is known); Plan 04 should assert the PASS/PARTIAL/FAIL behavior end-to-end against the real fixture set, and Phase 103/JVAL against the real dataset.
- No blockers for Plan 04 from this plan's scope.

## Self-Check: PASSED

- FOUND: `src/lucy_ng/cli/jcamp.py`
- FOUND: `tests/test_cli_jcamp.py`
- FOUND: `src/lucy_ng/cli/main.py` modified (jcamp import + registration + docstring line)
- FOUND commit: `b840083` (Task 1)
- FOUND commit: `465f839` (Task 2)

---
*Phase: 102-cli-peak-pick-bridge-qc-reuse*
*Completed: 2026-07-25*
