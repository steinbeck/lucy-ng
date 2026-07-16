---
gsd_state_version: 1.0
milestone: v10.0
milestone_name: Automatic NUS 2D Reconstruction
status: executing
stopped_at: Phase 99 Plan 03 complete
last_updated: "2026-07-16T17:43:11.208Z"
last_activity: 2026-07-16
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 15
  completed_plans: 14
  percent: 50
---

# lucy-ng State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-12)

**Core value:** AI agent autonomously determines compound structures from NMR, with a multi-agent team that uses the intended solver pipeline — not a manual bypass
**Current focus:** Phase 99 — Peak-Pick Bridge + QC Gate + CLI

## Current Position

Phase: 99 (Peak-Pick Bridge + QC Gate + CLI) — EXECUTING
Plan: 4 of 4
Status: Ready to execute
Last activity: 2026-07-16

Progress: [█████████░] 93%

## Milestone v10.0 Phases

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 97. Backend Integration + Params/Schedule | `lucy nus check` backend detection (LSD precedent) + `nus/params.py`/`nus/schedule.py` Bruker parsing, fixture-tested against real C20H32O2 data | NUS-01..05 | — |
| 98. Reconstruction + Processing | Real NMRPipe+SMILE subprocess chain (bruk2pipe → nusExpand.tcl → SMILE → FT/phase/baseline), FnMODE-aware, fail-loud wrapper | RECON-01..05 | 97 |
| 99. Peak-Pick Bridge + QC Gate + CLI | `nus/bridge.py` → existing `PeakPicker2D`; mandatory automated QC gate (PASS/PARTIAL/FAIL) blocking CASE handoff on FAIL; full `lucy nus` CLI group | PICK-01..03, QC-01..03 | 98 |
| 100. Cross-Platform Hardening + End-to-End Validation | Portability matrix (macOS/Linux native, Windows WSL2 gap documented); C20H32O2 exp2/3/4 reconstruction passing §8 gate; `/lucy-ng:case C20H32O2` convergence | PORT-01..02, VAL-01..02 | 99 |

**Sequencing:** Phase 97 (backend detection + pure-Python params/schedule parsing) ships first — zero external-binary dependency, fixture-testable from day one, and front-loads the FnMODE/nuslist bookkeeping correctness (a single hard-coded divisor would silently corrupt one of the three real C20H32O2 experiments). Phase 98 (reconstruction + processing) is the highest-uncertainty phase — needs the real NMRPipe+SMILE binary and answers the milestone's open empirical question (does SMILE clear the quality bar at 25-33% sampling). Phase 99 (peak-pick bridge + QC gate + CLI) is where the crux risk (fabricated cross-peaks becoming hard LSD constraints) gets its mandatory automated defense — the QC gate is its own deliverable, not folded into peak-picking. Phase 100 (cross-platform hardening + validation) is milestone-closing: portability documentation and the actual success criterion (`/lucy-ng:case C20H32O2` convergence) both depend on everything upstream being stable.

## Deferred Items

Items acknowledged and deferred at **v9.3 CASE Web-View Stage 2 milestone close on 2026-07-12**:

| Category | Item | Status | Note |
|----------|------|--------|------|
| todo | 2026-06-25-case4-azulene-regiochemistry-enumeration-gap | deferred (re-confirmed) | CASE-solver backlog; unrelated to the v9.3 webview scope. Still open. |
| todo | 2026-06-30-ranking-tests-hardfail-without-hosegen | deferred (re-confirmed) | v9.1 test-infra backlog; unrelated to the v9.3 webview scope. |

Items acknowledged and deferred at **v9.2 CASE Web-View milestone close on 2026-07-07** (carried into v9.3 or later):

| Category | Item | Status | Note |
|----------|------|--------|------|
| stage-2 | Formatted run log (render CASE-PROGRESS.md markdown: headings/bold/tables) | ACTIVE → Phase 93 | Deferred in Phase 91 with an explicit "revisit if the raw log proves hard to read" trigger — trigger met on the live CASE1 run. Reverses D-13. |
| stage-2 | Rendered spectra tabs + data tables (1D ¹³C/¹H, 2D HSQC/HMBC/COSY; peak lists, constraint inventory) | ACTIVE → Phases 94-96 | Explicit Stage 2 per design spec. Architecture built to accommodate. |
| defer-v9.4 | DEPT sub-tab (CH/CH2/CH3 signed bar chart) | deferred → v9.4 | Conditional on `multiplicity_edited` field in hsqc.json; P2 deliverable |
| defer-v9.4 | Interactive spectrum zoom/pan | deferred | Would require a JS charting library; conflicts with no-build/no-CDN constraint |
| defer-v9.4 | SSE/WebSocket live push replacing 3 s polling | deferred | Optional optimization; no functional gain |
| todo | 2026-06-30-ranking-tests-hardfail-without-hosegen | deferred | Test-infra todo from v9.1; unrelated to webview |
| todo | 2026-06-25-case4-azulene-regiochemistry-enumeration-gap | carried (from v9.1) | Still open; unrelated to webview |

Items acknowledged and deferred at **v9.1 milestone close on 2026-06-29**:

| Category | Item | Status | Note |
|----------|------|--------|------|
| todo | 2026-06-25-case4-azulene-regiochemistry-enumeration-gap | deferred | NEW 4th defect class from v9.1 UAT-01; di-methyl-ethyl class now searched, exact chamazulene regiochemistry still unreachable. Carried-seed. |

## Completed Milestones

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Core CASE Pipeline | 1-10 | 2026-01-12 |
| v1.1 Database-Backed Dereplication | 11-15 | 2026-01-15 |
| v1.2 HOSE Database Prediction | 16-19 | 2026-01-18 |
| v2.0 Robust Multi-Agent CASE | 20-26 | 2026-02-08 |
| v2.1 Working Multi-Agent CASE | 27-33 | 2026-02-09 |
| v3.0 Statistical Detection | 34-40 | 2026-02-16 |
| v4.0 Team-Based CASE | 41-48 | 2026-02-18 |
| v5.0 Fragment Library | 49-54 | 2026-02-21 |
| v6.0 Skill Quality Overhaul | 55-58 | 2026-03-10 |
| v7.0 Statistical 4J Detection | 59-64 | ABANDONED 2026-03-12 |
| v8.0 pyLSD Integration | 65-71 | Superseded by v9.0 (UAT failed as mechanism validation) |
| v9.0 CASE Reliability & Skill Consolidation | 72-85 | 2026-06-17 |
| v9.1 CASE Final-Answer Correctness & Verification Gates | 86-89 | 2026-06-29 |
| v9.2 CASE Web-View | 90-92 | 2026-07-07 |
| v9.3 CASE Web-View Stage 2 | 93-96 | 2026-07-12 |

## Performance Metrics

**Velocity:**

- Total plans completed: 203 across 12 milestones (11 shipped + 1 abandoned) at v9.2 close
  - v9.2: 3 phases (90-92), 10 plans, shipped 2026-07-07; tests: 1174 passing at close
  - v9.1: 4 phases (86-89), 9 plans, shipped 2026-06-29; tests: 1131 passing at close
- v9.3: 4 phases (93-96), 16 plans, shipped 2026-07-12 (~107 commits, +16,988/-287 lines)
- v10.0: 4 phases planned (97-100); 6 plans complete — Phase 97 Plan 01 (fixtures + NUS models), 4 min, 2 tasks, 18 files, tests 1219 passing at close; Phase 97 Plan 02 (nus/params.py, NUS-02), 14 min, 1 task, 2 files, tests 1243 passing at close; Phase 97 Plan 03 (nus/schedule.py, NUS-03), 12 min, 1 task, 2 files, tests 1269 passing at close; Phase 97 Plan 04 (nus/backends/nmrpipe_smile.py + registry, NUS-01), 6 min, 2 tasks, 3 files, tests 1289 passing at close; Phase 98 Plan 01 (tests/nus/ Nyquist Wave 0 scaffold — conftest run_stage mock seam + fake-intermediate factories + 7 RED-by-skip RECON stub files), ~18 min, 2 tasks, 9 files, tests/nus/ 24 collected/24 skipped at close (RECON-01..05 remain Pending — GREEN in Plans 02-06); Phase 98 Plan 02 (nus/runner.py run_stage() fail-loud wrapper + FnMODE recipe/_ordering_for_fnmode() + NusReconstructionResult model, RECON-03/RECON-04), ~25 min, 3 tasks, 4 files, tests/nus/ 20 passed/17 skipped at close (RECON-03/RECON-04 now complete; RECON-01/02/05 remain Pending — GREEN in Plans 03-06); Phase 98 Plan 03 (nus/backends/nmrpipe_smile.py::convert()+reconstruct_indirect(), FnMODE-branched bruk2pipe/nusExpand.tcl/SMILE dispatch, RECON-01/02/03), ~45 min, 2 tasks, 2 files, tests/nus/ 27 passed/11 skipped at close (RECON-01/02/03 now complete; RECON-04/05 already complete from Plan 02; the QF/magnitude COSY convert_first branch stays PROVISIONAL per 98-RESEARCH.md A1/A3 pending an implementation-time spike); Phase 98 Plan 04 (nus/postprocess.py::process_direct()+process_indirect() F2/F1 processing stages + ppm_scale()/ppm_axis_for_dimension()/calibrate_against_1d_reference() ppm calibration, RECON-02), ~18 min, 2 tasks, 2 files, tests/nus/ 19 passed/6 skipped at close (RECON-02 complete; all 5 Plan-01 RECON-02 stubs now GREEN); Phase 98 Plan 05 (nus/runner.py::NusRunner.reconstruct() four-stage orchestration + F2-before-F1 hard gate, RECON-01/02), ~20 min, 2 tasks, 3 files, tests/nus/ 22 passed/3 skipped at close (RECON-01/02 now complete; rewrote Plan-01's 3 orchestration stubs to patch at the four-stage-callable boundary since the stub's mock_run_stage/result.output_file shape didn't match the real NusReconstructionResult model; RECON-05/CLI wiring deferred to Plan 06); Phase 98 Plan 06 (cli/nus.py::reconstruct command — RECON-05 knob flags --iterations/--threshold/--virtual-echo + D-02 phase-override flags, --format json), ~15 min, 2 tasks, 3 files, tests/nus/ + tests/test_cli_nus.py 37 passed/1 skipped at close (RECON-05 now complete; **Phase 98 fully closed, RECON-01..05 all complete** -- ready for `/gsd-verify-work 98`); Phase 99 Plan 01 (models/nus.py QcVerdict/QcCheckResult/QcReport contract + committed known-bad/synthetic-clean peak-list fixture pair + six RED-by-skip stub test files, QC-01/QC-02/PICK-03 scaffold), 17 min, 3 tasks, 18 files, tests/nus/ 50 collected (26 existing + 24 new, all new skip cleanly), full suite 1329 passed/32 skipped/1 xfailed at close (zero regressions; QC-01/QC-02/PICK-03 remain Pending — GREEN in Plans 02-04, mirroring Phase 98 Plan 01's RECON-01..05 precedent; corrected the plan's `pytest.importorskip`-at-module-level instruction to Phase-98's established `@pytest.mark.skip`-per-test convention so all 24 new tests collect individually); Phase 99 Plan 02 (nus/qc.py — QcConfig + QcReferenceData D-03 three-tier resolution + six named checks + aggregate_verdict() + run_qc_checks(), QC-01/QC-02), 19 min, 2 tasks, 3 files, tests/nus/test_qc_checks.py + test_qc_regression.py 14/14 activated and green, full suite 1343 passed/18 skipped/1 xfailed at close (zero regressions; QC-01/QC-02 now complete; QC-02 discrimination floor proven directly against the real fixtures — known-bad FAIL via quaternary_exclusion/hsqc_coverage/signal_to_ridge, synthetic-clean PASS with zero violated checks; qc.py stays pure, no file writes); Phase 99 Plan 03 (nus/bridge.py — build_spectrum2d() processed .ft2 → Spectrum2D + bridge_peak_pick() direct PeakPicker2D call transformed into the per-experiment CASE schema + D-05/D-06 metadata/confidence, PICK-01/PICK-03; processing/edited_sign.py importable detect_multiplicity_edited() twin preserving cli/pick.py byte-unchanged), 24 min, 2 tasks, 5 files, tests/nus/test_bridge.py + test_bridge_metadata.py 17/17 activated and green, full suite 1360 passed/14 skipped/1 xfailed at close (zero regressions; PICK-01/PICK-03 now complete; rewrote both files' Wave-0 stub tests since they called `build_spectrum2d(path, params=None, ...)`/`bridge_peak_pick(path, experiment_type=...)` against a `.ft2` never written to disk and a `"verdict"` key superseded by Task 2's own `"qc_verdict"` naming — same class of Wave-0-stub correction as Phase 98 Plans 03/05/06; bridge_peak_pick() accepts optional qc_report/recon_meta so Plan 04's pipeline can call it twice, pre-QC and post-QC)

## Accumulated Context

### Roadmap Evolution

- v9.3 roadmap created (2026-07-07): phases 93-96. Derived from 8 requirements (LOG-01, TAB-01, TBL-01..03, SP1-01, SP2-01, SP-02) with authoritative override: spectra = **real Bruker traces + peak overlay** (not peak-only sticks). Research HIGH confidence across all phases; no research gate needed for any phase.
- v10.0 roadmap created (2026-07-12): phases 97-100, continuing numbering from the last shipped phase (96). Derived from 20 requirements (NUS-01..05, RECON-01..05, QC-01..03, PICK-01..03, PORT-01..02, VAL-01..02), following the research-converged build order (SUMMARY.md § Implications for Roadmap): backend+params/schedule → reconstruction+processing (highest-uncertainty) → peak-pick bridge+QC gate+CLI (crux-risk mitigation as its own deliverable) → cross-platform hardening+end-to-end validation. 20/20 requirements mapped, no orphans.

### Key Design Decisions for v10.0

- [v10.0-roadmap]: **Backend = NMRPipe+SMILE, runtime-detected external binary** — never a core `pyproject.toml` dependency, mirrors the `LSDRunner`/`lucy lsd check` precedent exactly. Windows is an accepted, documented WSL2/VM gap (Phase 100), not a blocker.
- [v10.0-roadmap]: **New `nus/` package, sibling of `lsd/`/`webview/`** — pre-CASE "dumb tool"; zero changes to `case.md` or the 5-agent team; the diff to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` must stay empty (enforceable-by-inspection constraint carried into Phase 97's success criteria).
- [v10.0-roadmap]: **QC gate is its own phase deliverable (Phase 99), not folded into peak-picking** — it is the mandatory automated defense against fabricated cross-peaks silently becoming hard LSD constraints (the milestone's crux risk per research).
- [Phase 97 Plan 01]: `NusAcquisitionParams.fnmode_f1` validator shares the `REAL_FNMODES`/`COMPLEX_FNMODES`/`VALID_FNMODES` module constants with `nus/schedule.py` (plan 03) so the two never maintain divergent FnMODE allowlists.
- [Phase 97 Plan 01]: Fixture set expanded beyond D-03's original acqus/acqu2s/nuslist trio to also copy `pdata/1/procs`+`pdata/1/proc2s` per RESEARCH.md's SF/OFFSET-live-in-procs correction — otherwise SF/OFFSET fields would have zero fixture coverage.
- [Phase 97 Plan 02]: `read_nus_params` uses nmrglue's low-level `read_acqus_file()`/`read_procs_file()` instead of the monolithic `ng.bruker.read()` — the latter unconditionally requires a `fid`/`ser` binary to determine data shape, which the D-03 test fixtures deliberately omit (metadata-only). The low-level readers parse the identical `acqus`/`acqu2s`/`procs`/`proc2s` files with zero binary dependency, correct for both the fixtures and real not-yet-reconstructed NUS directories.
- [Phase 97 Plan 03]: `read_nus_schedule` uses `ng.bruker.read_nuslist(expdir)` instead of `ng.bruker.read(expdir)["nuslist"]` — same rationale as Plan 02: the latter requires a `fid`/`ser` binary the D-03 fixtures omit. `read_nuslist()` reads the identical file in identical acquisition (never sorted) order with zero binary dependency; FnMODE/TD/NusTD are sourced from `read_nus_params` (Plan 02), keeping exactly one acquisition-parameter parse path.
- [Phase 97 Plan 04]: `NmrPipeSmileBackend.REQUIRED_TOOLS = [nmrPipe, bruk2pipe, nusExpand.tcl]` via `shutil.which`, plus a distinct SMILE-plugin capability probe (`nmrPipe -fn SMILE -help`, fixed arg list, no `shell=True`) — research verified SMILE is an nmrPipe plugin dispatched internally, never a standalone `which()`-able binary (the milestone architecture research's `smileNus` tool name was wrong and is not used anywhere, including comments). `diagnose()` gives 4 distinct states (available/smile_plugin_missing/installed_not_sourced/not_installed) with install-URL hints. `NusBackend` (repo's first `typing.Protocol`) + `get_backend()`/`list_available_backends()` registry expose backends generically for Phase 97-05's CLI and Phase 98's reconstruction pipeline.
- [Phase 98 Plan 02]: `run_stage()`'s all-zero/truncated-data check wraps `nmrglue.fileio.pipe.read()` in try/except and falls back to a raw byte-level all-zero comparison on parse failure — needed because the Plan-01 conftest's fake valid/truncated intermediate fixtures are deliberately not real NMRPipe-format headers, and both raise the identical `nmrglue` `IndexError` when parsed directly (verified empirically). FnMODE 1/2 (QF/QSEQ) `bruk2pipe -yMODE` recipe values are documented in-source as PROVISIONAL (98-RESEARCH.md Assumptions Log A3) pending an implementation-time spike against real exp2 COSY data in Plan 03/05.
- [Phase 98 Plan 03]: Dropped the plan's literal `missing_tools()` hard preflight raise from `convert()`/`reconstruct_indirect()` — this dev machine (and CI) has no `nmrPipe`/`bruk2pipe`/`nusExpand.tcl` on PATH, so a hard preflight raise would make every D-04 mocked-subprocess unit test in `test_reconstruct_chain.py` impossible to pass; `run_stage()` remains the single fail-loud enforcement point (D-01) for every external call. `reconstruct_indirect()` takes an explicit `fnmode: int = 6` keyword (not `params`/`schedule`) to match the Plan-01 test scaffold's already-fixed call signature while keeping `-EA` gating genuinely FnMODE-driven. The QF/magnitude COSY `convert_first` branch sizes bruk2pipe from the sparse `f1_td` (not `nus_td`, since bruk2pipe runs before expansion in that branch) and stays explicitly PROVISIONAL per 98-RESEARCH.md Assumptions Log A1/A3.
- [Phase 98 Plan 04]: `process_direct()`/`process_indirect()` each dispatch their entire nmrPipe verb chain (SP/ZF/FT/PS/POLY/TP) as ONE `nmrPipe` invocation with multiple chained `-fn` blocks — idiomatic NMRPipe multi-verb processing-script usage, not unix-pipe chaining — keeping each stage as ONE `run_stage()`-checked `subprocess.run()` call with zero shell interpretation. Matched the Plan-01 test scaffold's exact ppm-helper names (`ppm_axis_for_dimension()`, `calibrate_against_1d_reference()`) and optional `params` argument over the plan's illustrative interface sketch (same class of deviation as Plan 03's `reconstruct_indirect()` signature match) — `ppm_scale()` is kept as the real 4-argument implementation satisfying the plan's own literal acceptance-grep, with `ppm_axis_for_dimension()` as the tests' imported entry point. `process_indirect()` writes a best-effort `processed_ppm_axis.json` sidecar (raw + calibrated F1 axis) only when `params` carries F1 SF/OFFSET calibration fields.
- [Phase 98 Plan 05]: `NusRunner.reconstruct()` reads params/schedule once, then dispatches `backend.convert()` → `postprocess.process_direct()` (F2+TP) → `backend.reconstruct_indirect()` (SMILE) → `postprocess.process_indirect()` (F1+calib) in strict physical order, with `_resolve_f2_plan()`/`F2Plan` (a thin `magnitude`-flag wrapper over `recipe_for_fnmode()`) implementing the RECON-02 hard gate: it returns `None` (never raises) on an unrecognized FnMODE so `reconstruct()` itself raises the RuntimeError before any subprocess dispatch. F2 phase defaults (`f2_p0=0.0`/`f2_p1=0.0`) are explicitly PROVISIONAL (no manual-verified universal value exists, unlike F1's already-provisional 90.0/0.0 default) — CLI override deferred to Plan 06. Rewrote all three Plan-01 orchestration test stubs (they referenced a non-existent `result.output_file` and used the low-level `mock_run_stage` seam, which cannot distinguish `process_direct()`'s output from `convert()`'s internal bruk2pipe/nusExpand.tcl outputs) to patch at the four-stage-callable boundary instead, per the plan's own Task 1 action text. Same fix applied to the real end-to-end integration test's assertions (`result.processed_spectrum`, still skips cleanly, no `ser` binary added).
- [Phase 98 Plan 06]: `cli/nus.py::reconstruct` mirrors the existing `params`/`schedule` command shape exactly (deferred `NusRunner` import, `Path(expdir).resolve()`, `--format json`); RECON-05 knobs named `--iterations`/`--threshold`/`--virtual-echo`/`--no-virtual-echo` (descriptive lucy-ng names per RESEARCH.md's own recommendation, not SMILE's raw `-maxIter`/`-thresh`/`-EA` flag names), plus D-02 phase-override flags `--f2-p0`/`--f2-p1`/`--f1-p0`/`--f1-p1` defaulting to `NusRunner.reconstruct()`'s own provisional constants (one source of truth, no duplicate hard-coding). Rewrote both Plan-01 `test_cli_reconstruct.py` stubs: the stub guessed `--max-iter` (superseded by the plan's own `--iterations` naming decision) and looked up the SMILE stage by the wrong casing (`"smile"` vs. the real `run_stage("SMILE", ...)` call) — both fixed, plus the CLI-invocation test now copies its fixture into `tmp_path` first (mirrors Plan 05's `_copy_fixture`) so `NusRunner._stage_dir()`'s real `mkdir()`/JSON-sidecar side effects never touch the tracked `tests/fixtures/nus/` tree. Phase 98 (RECON-01..05) is now fully complete.
- [Phase 99 Plan 01]: `QcVerdict`/`QcCheckResult`/`QcReport` mirror `NusReconstructionResult`'s exact Pydantic convention (`ConfigDict`, `to_dict`/`from_dict`, `summary()`); added `violated_checks()`/`critical_violations()` convenience accessors anticipating D-02's critical/soft aggregation Plan 02 implements. The synthetic-clean fixture set (§8-compliant, zero HSQC hits at the 5 quaternary shifts 142.00/135.86/79.35/36.23/37.86, self-consistent edited signs, diagonal-symmetric COSY, no ridge) is the phase's own load-bearing QC-02 PASS-side proof since no real clean C20H32O2 reconstruction exists until Phase 100. Corrected the plan's literal `pytest.importorskip`-at-module-level RED-by-skip instruction to Phase-98's actually-established `@pytest.mark.skip`-per-test convention (real imports inside skipped bodies) after `importorskip` was found to collapse per-test collection into one per-file skip, violating the plan's own individual-collection acceptance criterion.
- [Phase 99 Plan 02]: `nus/qc.py`'s six checks each expose two forms: an internal `check_*(peaks, ref, config)` used by `run_qc_checks()`, plus a short-named standalone wrapper (`quaternary_exclusion`, `qc_check_ppm_calibration`, `signal_to_ridge`, `hsqc_coverage`, `edited_sign_consistency`, `cosy_diagonal_symmetry`) matching Plan 01's already-fixed test-stub call signatures. `QcReferenceData.resolve()`'s D-03 three-tier prot/quaternary resolution never calls `detection.detect_hybridisation()` (confirmed no CH-count field, RESEARCH.md Pitfall 1); tier-3 (no DEPT, no override) returns `passed=False` with an `"insufficient_reference_data"` detail rather than a silent PASS (T-99-03). `hsqc_coverage`'s protonated-carbon reference is derived from the real trusted 1D files in `<peaks-dir>` (deduplicated across overlapping 1D experiments) rather than the hardcoded `GUIDE_S10_C13` list, falling back to the hardcoded list only when no 1D file exists. Any per-file JSON load error in `run_qc_checks()` unconditionally blocks a PASS verdict. QC-02 discrimination proven directly: known-bad fixture verdicts FAIL (quaternary_exclusion + hsqc_coverage + signal_to_ridge all trip critical), synthetic-clean fixture verdicts PASS with zero violated checks.
- [Phase 99 Plan 03]: `nus/bridge.py::build_spectrum2d()` reads a processed `.ft2` via `ng.pipe.read`/`guess_udic`/`uc_from_udic` (mirrors `readers/bruker.py::read_2d()`'s Bruker idiom), preferring the `processed_ppm_axis.json` sidecar's calibrated F1 axis when present; `bridge_peak_pick()` calls `PeakPicker2D.pick_peaks()` unmodified and transforms its raw output into the CASE HSQC/HMBC/COSY schema, with a D-05 additive `"reconstruction"` metadata block (`backend`/`iterations`/`qc_verdict`/`violated_checks`/`thresholds_used`) and D-06 verdict-derived confidence (`confidence_from_verdict()`: PASS→"high", PARTIAL→"low", raises on FAIL). `bridge_peak_pick()` accepts optional `qc_report`/`recon_meta` (both default `None`, emitting an honest `"pending_qc"`/`"UNKNOWN"` placeholder when absent) so Plan 04's pipeline can call it twice — pre-QC to produce peaks for the QC gate to grade, post-QC to rebuild the final confidence-corrected payload — resolving the causal-ordering problem where peaks must exist before QC can grade them. The HARD `cli/pick.py`-byte-unchanged invariant is preserved via `processing/edited_sign.py`, a verbatim importable twin of `cli/pick.py`'s module-private `_detect_multiplicity_edited()`, rather than promoting/exporting from the frozen file. Rewrote both `test_bridge.py`/`test_bridge_metadata.py`'s Wave-0 (Plan 01) stub tests — they called `build_spectrum2d(path, params=None, ...)`/`bridge_peak_pick(path, experiment_type=...)` against a `.ft2` path never written to disk (unpassable as literally written) and expected a `"verdict"` metadata key superseded by Task 2's own `"qc_verdict"` naming — replaced with a real `make_valid_ft2` conftest fixture factory and deterministic synthetic-`Spectrum2D` tests mirroring `test_hmbc_peak_picking_integrity.py`'s established synthetic-peak pattern (same class of Wave-0-stub correction as Phase 98 Plans 03/05/06). HMBC's `suspected_1J_artifact` is conservatively `False` for every bridge-picked peak (present in the schema but not computed — a real 1J-leak flag needs the sibling HSQC list, out of scope for a single per-experiment call).

### Key Design Decisions for v9.3

- [v9.3-roadmap]: **Spectra source = real Bruker data** — BrukerReader/nmrglue renders the actual processed spectrum; picked peaks from `analysis/peaks/*.json` are overlaid on top. This is the QC value: user sees whether peaks were placed correctly relative to the real signals.
- [v9.3-roadmap]: **Bruker-path wiring via `.run_manifest.json`** — `case.md` writes `{"bruker_data_dir": "<abs>", "formula": "<formula>"}` into `analysis/.run_manifest.json` at run-start. The spectra router reads this file. If absent (manual `lucy webview serve`, pre-v9.3 run), spectra tab shows "unavailable" gracefully. No CLI signature change; no `.webview.json` model change.
- [v9.3-roadmap]: **matplotlib OO API only** — `Figure` + `FigureCanvasAgg`; never `matplotlib.pyplot` in any webview module. All matplotlib imports lazy inside `make_router()` per WV-08. `matplotlib>=3.7` added to `[webview]` extra.
- [v9.3-roadmap]: **Reversed ppm axes everywhere** — `ax.set_xlim(ppm_scale[0], ppm_scale[-1])` where `ppm_scale[0]` is the highest ppm (Bruker convention). Both F1 and F2 axes reversed on 2D plots. Shared `_apply_nmr_axes()` helper prevents omission.
- [v9.3-roadmap]: **2D performance** — decimate to ≤512×512 before contouring; threshold-based contour levels (MAD noise floor); mtime-keyed per-router PNG cache; sync `def` route handlers (FastAPI dispatches to thread-pool, never blocks event loop).
- [v9.3-roadmap]: **Markdown log = hand-rolled DOM renderer** — createElement + textContent throughout; never `innerHTML` of server content. Covers the exact CASE-PROGRESS.md subset (## headings, **bold**, `code`, pipe-tables, code fences, --- hr). No CDN, no bundled JS library.
- [v9.3-roadmap]: **SP-02 graceful degradation** — assigned to Phase 95 (first spectra phase, where the "unavailable" pattern for missing raw data is established); carried as a hard acceptance criterion to Phase 96 and recommended acceptance concern for Phase 94 tables.

### Decisions (inherited from v9.2)

Decisions are logged in PROJECT.md Key Decisions table.

- [v9.2-roadmap]: FastAPI + uvicorn shipped as `lucy-ng[webview]` optional extra; core `lucy` CLI stays dependency-free. Frontend is static HTML + vanilla JS — no build toolchain. Server is "dumb" (reads files only, no agent-team coupling).
- [Phase 91]: All fastapi/webview imports in test files are inside test function bodies (WV-08 collect-safety).
- [Phase 91]: Epoch values in timing.jsonl test fixtures are JSON strings matching case.md shell printf %s output.
- [Phase 94 Plan 01]: `tables_analysis_dir`/`tables_iterations_dir` fixtures in `tests/test_webview_api.py` are hand-authored to CONTEXT.md's LOCKED peaks-JSON schema — no on-disk `analysis/` run on this machine currently matches those exact field names (RESEARCH.md Assumptions A1-A5), so no existing file could be used as a template.
- [Phase 94 Plan 01]: TBL-01/02/03 remain Pending in REQUIREMENTS.md — Plan 01 only ships the Wave-0 RED-by-skip test scaffold (`TestTablesEndpoint`, 14 methods); requirements complete only once Plan 02's `tables.py` router makes all 14 pass.
- [Phase 94 Plan 02]: `tables.py` router ships all 5 GET routes (carbon/hsqc/hmbc/cosy/constraints), never-500, docked in `app.py`; `TestTablesEndpoint` (14/14) now GREEN — TBL-01/02/03 complete. Constraints route selects highest numeric `iteration_(\d+)` across family-suffixed dirs (mtime tiebreak, D-02); inventory parser reimplemented webview-local (never imports `cli/lsd.py`, whose validator raises SystemExit).

### Pending Todos

- **[2026-06-25] CASE4 azulene-regiochemistry-enumeration gap** — carried seed; not in v10.0 scope. See `.planning/todos/pending/2026-06-25-case4-azulene-regiochemistry-enumeration-gap.md`.

### Blockers/Concerns

None. Phase 97 may begin planning immediately (`/gsd-plan-phase 97`).

### Strategic Reference

See `background/sherlock-analysis.md` for full Sherlock vs lucy-ng comparison. v9.0 closed the end-to-end mechanism gap; v9.1 closed the three "clean-but-wrong" defect classes. v9.2 adds live observability; v9.3 deepens the inspector with spectra and data tables. v10.0 closes the NUS 2D reconstruction gap that timed out the first C20H32O2 CASE run.

Key v9.0 constraint (still in force): SYME and DEFF NOT are lucy-ng abstractions. Native LSD-3.4.9 commands are: MULT, LIST, PROP, BOND, COSY, HMBC, ELIM, DEFF, FEXP, HSQC, ELEM.

## Session Continuity

Last session: 2026-07-16T17:43:11.204Z
Stopped at: Phase 99 Plan 03 complete
Resume with: `/gsd-execute-phase 99` (continue with Plan 04)

---
*Last updated: 2026-07-16 — Phase 99 Plan 03 complete (nus/bridge.py — build_spectrum2d() + bridge_peak_pick() direct PeakPicker2D call transformed into the per-experiment CASE schema + D-05/D-06 metadata/confidence; processing/edited_sign.py preserves cli/pick.py byte-unchanged); PICK-01/PICK-03 now complete, Plan 04 unblocked*

## Operator Next Steps

- Continue Phase 99 execution: Plan 04 (`cli/nus.py::qc`/`pipeline` commands + D-07 write/quarantine boundary, PICK-02/QC-03) via `/gsd-execute-phase 99`
