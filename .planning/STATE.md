---
gsd_state_version: 1.0
milestone: v10.1
milestone_name: JCAMP-DX 2D Ingestion
status: milestone_complete
stopped_at: Milestone complete (Phase 103 was final phase)
last_updated: 2026-07-28T12:36:08.932Z
last_activity: 2026-07-28
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 9
  completed_plans: 27
  percent: 100
---

# lucy-ng State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-21)

**Core value:** AI agent autonomously determines compound structures from NMR, with a multi-agent team that uses the intended solver pipeline — not a manual bypass
**Current focus:** Milestone complete

## Current Position

Phase: 103
Plan: Not started
Status: Milestone complete
Last activity: 2026-07-28

## Milestone v10.1 Phases

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 101. JCAMP-DX Reader | Pure-Python 2D NTUPLES DIFDUP decoder into `Spectrum2D` + 1D reader into `Spectrum1D`, no external binary, verified ppm axes, CI-runnable fixture test | JC-01..04 | 100 |
| 102. CLI + Peak-Pick Bridge + QC Reuse | `lucy jcamp` command reusing the Phase-99 bridge pattern and the unchanged QC gate, `case.md` byte-unchanged | JCLI-01..02 | 101 |
| 103. End-to-End Validation (C20H32O2-jcamp) | Real dataset read, peak-picked, QC-graded to §8 quality, fresh `/lucy-ng:case C20H32O2` converges on a rankable solution set | JVAL-01..02 | 102 |

**Sequencing:** Phase 101 (reader) ships first — pure-Python, no external binary, so it is the highest-confidence and most CI-testable phase; it also carries the milestone's one real technical risk (JC-02 ppm-axis correctness, the same defect class as v10.0's WR-04) so it must be verified against ground truth before anything downstream trusts its output. Phase 102 (CLI + bridge + QC reuse) is mechanically low-risk by design — it reuses the Phase-99 bridge and QC gate byte-for-byte, so its job is wiring, not new logic. Phase 103 (end-to-end validation) is milestone-closing and partly human-gated (chemist confirmation on a soft-PARTIAL, and the `/lucy-ng:case` run itself) — it is where the milestone's actual success bar (CASE convergence) is proven.

## Milestone v10.0 Phases (PARTIAL — historical reference)

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 97. Backend Integration + Params/Schedule | `lucy nus check` backend detection (LSD precedent) + `nus/params.py`/`nus/schedule.py` Bruker parsing, fixture-tested against real C20H32O2 data | NUS-01..05 | — |
| 98. Reconstruction + Processing | Real NMRPipe+SMILE subprocess chain (bruk2pipe → nusExpand.tcl → SMILE → FT/phase/baseline), FnMODE-aware, fail-loud wrapper | RECON-01..05 | 97 |
| 99. Peak-Pick Bridge + QC Gate + CLI | `nus/bridge.py` → existing `PeakPicker2D`; mandatory automated QC gate (PASS/PARTIAL/FAIL) blocking CASE handoff on FAIL; full `lucy nus` CLI group | PICK-01..03, QC-01..03 | 98 |
| 100. Cross-Platform Hardening + End-to-End Validation | Portability matrix (macOS/Linux native, Windows WSL2 gap documented); C20H32O2 exp2/3/4 reconstruction passing §8 gate; `/lucy-ng:case C20H32O2` convergence — **PARTIAL**: PORT-01/02 shipped, VAL-01/02 not achieved (SMILE memory abort, RECON-F1 tracked) | PORT-01..02, VAL-01..02 | 99 |

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

Items acknowledged and deferred at **v10.0 milestone close (PARTIAL) on 2026-07-20**:

| Category | Item | Status | Note |
|----------|------|--------|------|
| RECON-F1 | hmsIST/mddnmr fallback backend for in-lucy-ng NUS self-reconstruction | tracked | SMILE cannot complete on the dev host (~6.5 GB memory abort, D-04 tuning budget exhausted). Named next step to close v10.0's VAL-01/02. Note: v10.1's `C20H32O2-jcamp` data was itself produced by `mddnmr`, so this is the natural follow-on. |
| todo | 2026-06-25-case4-azulene-regiochemistry-enumeration-gap | carried (from v9.1) | Still open; unrelated to NUS/JCAMP scope. |

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
| v10.0 Automatic NUS 2D Reconstruction | 97-100 | PARTIAL 2026-07-20 (PORT shipped; VAL blocked, RECON-F1 tracked) |

## Performance Metrics

**Velocity:**

- Total plans completed: 229 across 13 milestones (11 shipped + 1 abandoned + 1 partial) at v10.0 pause
  - v9.2: 3 phases (90-92), 10 plans, shipped 2026-07-07; tests: 1174 passing at close
  - v9.1: 4 phases (86-89), 9 plans, shipped 2026-06-29; tests: 1131 passing at close
  - v9.3: 4 phases (93-96), 16 plans, shipped 2026-07-12 (~107 commits, +16,988/-287 lines)
  - v10.0: 4 phases (97-100), 13 plans complete (97: 5, 98: 6, 99: 4, 100: 2 of 3 — VAL plan 100-03 closed with an honest partial-stop, no code shipped from it beyond the VALIDATION.md record); full suite 1396 passing at pause. PORT-01/02 verified; VAL-01/02 not achieved (SMILE memory abort, see VALIDATION.md).
- v10.1: Phase 101 complete (4 of 4 plans done) — 101-01 (Wave-0 fixtures + RED tests), 101-02 (vendored JCAMP-DX DIFDUP/SQZ/DUP/PAC decoder, JC-04 complete), 101-03 (`readers/jcamp.py` shared ppm/metadata helpers + `JcampReader.read_1d`, JC-02/JC-03 complete), and 101-04 (`JcampReader.read_2d` + `read()` dispatcher, JC-01/JC-02 complete) shipped 2026-07-23; full suite 1408 passing, 0 RED remaining in test_jcamp.py — all 4 requirements (JC-01..04) satisfied and CI-verified on committed real fixture data. Phase 102 (CLI + Peak-Pick Bridge + QC Reuse, JCLI-01/02) complete 2026-07-25, full suite 1457 passing. Phase 103 (End-to-End Validation, 1 of 1 plans) **CLOSED PARTIAL 2026-07-28** — JVAL-01/JVAL-02 honest partial close (D-10); full suite 1468 passing, zero regressions. **v10.1 milestone therefore closes PARTIAL overall** (JC-01..04, JCLI-01..02 fully shipped; JVAL-01/JVAL-02 partial, tracked next steps JVAL-F2/JVAL-F3), mirroring v10.0's own Phase-100 PARTIAL close.

## Accumulated Context

### Roadmap Evolution

- v9.3 roadmap created (2026-07-07): phases 93-96. Derived from 8 requirements (LOG-01, TAB-01, TBL-01..03, SP1-01, SP2-01, SP-02) with authoritative override: spectra = **real Bruker traces + peak overlay** (not peak-only sticks). Research HIGH confidence across all phases; no research gate needed for any phase.
- v10.0 roadmap created (2026-07-12): phases 97-100, continuing numbering from the last shipped phase (96). Derived from 20 requirements (NUS-01..05, RECON-01..05, QC-01..03, PICK-01..03, PORT-01..02, VAL-01..02), following the research-converged build order (SUMMARY.md § Implications for Roadmap): backend+params/schedule → reconstruction+processing (highest-uncertainty) → peak-pick bridge+QC gate+CLI (crux-risk mitigation as its own deliverable) → cross-platform hardening+end-to-end validation. 20/20 requirements mapped, no orphans. Closed 2026-07-20 as PARTIAL (VAL-01/02 blocked by SMILE memory abort; see VALIDATION.md).
- v10.1 roadmap created (2026-07-21): phases 101-103, continuing numbering from the last v10.0 phase (100). Derived from 8 requirements (JC-01..04, JCLI-01..02, JVAL-01..02) following the suggested three-stage shape from the milestone brief: reader (no external binary, highest-risk = ppm-axis correctness) → CLI/bridge/QC reuse (mechanically low-risk — reuses Phase-99 unchanged) → end-to-end validation on `C20H32O2-jcamp` (partly human-gated). 8/8 requirements mapped, no orphans. v10.0's Phase-100 PARTIAL section is preserved unchanged as historical record; v10.1 does not touch or supersede it.

### Key Design Decisions for v10.1

- [v10.1-roadmap]: **New reader module `src/lucy_ng/readers/jcamp.py`, sibling of `bruker.py`** — a new front-end only; the entire downstream (Phase-99 bridge, `PeakPicker2D`, QC gate, `case.md`) is reused unchanged, per the milestone's explicit "reuse the Phase-99 downstream unchanged" constraint.
- [v10.1-roadmap]: **No external binary dependency anywhere in this milestone** — pure-Python JCAMP-DX parsing (own DIFDUP/SQZ/PAC decoder, vendored or wrapped rather than depending on nmrglue's private API). This is what makes Phase 101 fully CI-testable with a committed real fixture, directly addressing the Phase-100 meta-learning that mock-only "verified" gave false confidence for an external-tool pipeline (D-BUG-1/D-BUG-2 were both invisible to mocked tests).
- [v10.1-roadmap]: **JC-02 ppm-axis correctness is the milestone's one real technical risk**, flagged for extra verification emphasis in Phase 101 — same defect class as v10.0's WR-04 (Bruker OFFSET treated as Hz). Must be checked against the trusted 1D reference / §10 ground truth, not eyeballed; carried as an explicit success-criterion clause, not folded silently into JC-01.
- [v10.1-roadmap]: **JCLI-02's "`case.md` byte-unchanged" is carried as its own Phase-102 success criterion**, mirroring the v10.0 "CASE pipeline unchanged" invariant (Phase 97-99) — verifiable by diff, not by trust.
- [Phase 101 Plan 01]: Fixture header-pruning matches literal Bruker JCAMP-DX key prefixes (`##TITLE=`, `##$SF=`, `##.PULSE SEQUENCE=`, ...) as they appear in the real export, rather than nmrglue's normalized `_getkey()` form — simpler and deterministic to verify directly against the source file. F1 page window fixed at `[1735:1751]` (16 pages) per 101-RESEARCH.md's verified oracle coordinates (contains 2 of the 3 known real gem-dimethyl/methyl cross-peaks). The Pitfall-2 Y-FACTOR scaling test and the D-04 ppm-axis-assertion test target reader-level helpers (`_apply_yfactor`, `_assert_plausible_ppm_axis`) directly in `test_jcamp.py`, since the real fixture's own Y_FACTOR happens to be 1 and would not otherwise catch a missing multiplication.
- [Phase 101 Plan 02]: Vendored `src/lucy_ng/readers/_jcampdx_decode.py` (9-object nmrglue `jcampdx.py` DIFDUP/SQZ/DUP/PAC decoder closure, lines 208-453, New-BSD Jonathan J. Helmus 2010-2015) with zero nmrglue import (JC-04) and full license attribution; entry point renamed `_parse_data` -> public `parse_data`. Added type annotations as a non-behavioral typing-only layer (function signatures, `NDArray[np.float64]` return, two targeted `assert`/`# type: ignore[index]` spots, one `Any`-typed dual-purpose local) to satisfy CLAUDE.md's `mypy --strict` gate on the new module, verified zero decode-behavior change via the unchanged D-08 hand-oracle test results before/after. The plan's own literal `grep -c nmrglue == 0` acceptance criterion conflicts with its own action text (which requires a provenance/license note naming nmrglue) — resolved by checking the substantive JC-04 requirement instead (no `import nmrglue`/`from nmrglue import` statement), documented as a plan-bug deviation in 101-02-SUMMARY.md.
- [Phase 101 Plan 03]: `src/lucy_ng/readers/jcamp.py` implements the JC-02 crux `_ppm_scale` (verified `OFFSET + SF` formula, not naive SFO) plus `_assert_plausible_ppm_axis` (D-04 fail-loud safety net) and `_resolve_dim` (WR-04-class homonuclear-degeneracy guard), then `JcampReader.read_1d` (JC-03) on top — both committed 1H/13C references decode correctly. `_resolve_dim` indexes `$SF`/`$OFFSET` via `$NUC1`'s own list position (not `.NUCLEUS`'s), since direct inspection of the real trimmed HSQC fixture showed `$NUC1`/`$SF`/`$OFFSET` are co-indexed by nmrglue's parse order while `.NUCLEUS` uses the reversed SYMBOL-declared F1/F2 order (101-RESEARCH.md Pitfall 4). `_clean_nucleus_label` strips BOTH caret (`^1H`, used by `.OBSERVE NUCLEUS`) and angle-bracket (`<1H>`, used by real `$NUC1`) wrapping — the plan's literal wording named only caret-stripping, but real fixture data showed `$NUC1` is angle-bracket-wrapped, not caret-prefixed; fixed as a Rule-1 robustness deviation so Plan 04's `read_2d` gets a correctly-matching shared helper. Full suite: 1405 passed, 3 RED remaining (Plan 04 scope: `read_2d`/`_apply_yfactor`).
- [Phase 101 Plan 04]: `JcampReader.read_2d` assembles the DIFDUP-compressed NTUPLES pages into a `(16, 2048)` Y-FACTOR-scaled `Spectrum2D`, with `JcampReader.read()` dispatching on `##NUM DIM=` (absent -> 1D, since real 1D files carry no such key). The JC-02 load-bearing cross-check caught a real bug in the F1 axis formula: the committed trimmed fixture's `$OFFSET` anchors the file's ORIGINAL, untrimmed NTUPLES axis (fixture generation preserves the global header verbatim, only slicing the PAGE/DATATABLE window), not the trimmed window's own first page — using the window's first page Hz value as the anchor (as 101-RESEARCH.md's literal Pitfall-3 formula suggested) produced an F1 axis off by ~150 ppm. Fixed by re-basing the local anchor through the same verified `OFFSET+SF` formula before calling the shared `_ppm_scale` helper. Phase 101 (JC-01..04) now fully complete; full suite 1408 passed, 0 RED remaining, zero regressions.
- [Phase 102]: `lucy jcamp` (read -> pick -> QC -> write in one command) shipped reusing the byte-unchanged Phase-99 `bridge_peak_pick` + QC gate, plus a new thin 1D bridge (`processing/jcamp_1d_bridge.py`); fixed a real Phase-101 `_resolve_dim` defect that blocked every homonuclear 2D experiment (COSY, not just NOESY); first committed SHA-256 byte-unchanged guard for `case.md` + the 5 agent files. Full detail: `102-cli-peak-pick-bridge-qc-reuse/102-VALIDATION.md`.
- [Phase 103 Plan 01, CLOSED PARTIAL 2026-07-28]: D-09 widened `_PPM_PLAUSIBILITY_BOUNDS["13C"]` 230.0 -> 250.0 so the real `C20H32O2-jcamp` HMBC file (legitimate ~234.81 ppm window) reads at all; D-01/D-04 added repeatable `--threshold`/`--snr-floor` `KEY=value` CLI options (bare form byte-identical to the old default). Ran the full, pre-defined 31-cell D-03 knob matrix directly against the real dataset (all 6 `.dx` files, zero read failures via one governed `lucy jcamp` invocation, NOESY skipped per D-06) and found the QC verdict is a genuinely **knob-independent** critical FAIL: every one of the 8 HSQC matrix cells shows the same ~37.9 ppm HSQC correlation within tolerance of the QC gate's compiled-in (and §10-flagged MEDIUM-confidence) 37.86 ppm quaternary shift, so `quaternary_exclusion` cannot pass within the matrix; `hsqc_coverage` (69% vs 80% floor) is additionally capped by a CDCl3 solvent-triplet artifact and a real 1D-13C acquisition-window gap. **Coordinator requested and received a read-only diagnostic** (raw JCAMP header + the untouched sibling Bruker tree's `acqus`/`procs` for `exp6`/`exp7`) before accepting the honest close, confirming the narrow `[-10.14, 110.14]` ppm 1D-13C window is a real, pre-existing dataset property (`exp6`/"narrow" vs `exp7`/"wide", the latter never exported to JCAMP-DX) — the JC-02/WR-04 ppm-axis risk class is explicitly cleared, not just assumed. **v10.1 closes PARTIAL**: JVAL-01 (critical FAIL, matrix exhausted, tracked via **JVAL-F2**) and JVAL-02 (not attempted — no consumable peaks for a fresh CASE session, Task 6 correctly skipped rather than run against empty data). **JVAL-F3** (re-export `exp7`/wide) filed as an additional, explicitly non-sufficient tracked next step. Full detail: `103-end-to-end-validation-c20h32o2-jcamp/103-VALIDATION.md` + `103-01-SUMMARY.md`.

### Key Design Decisions for v10.0

- [v10.0-roadmap]: **Backend = NMRPipe+SMILE, runtime-detected external binary** — never a core `pyproject.toml` dependency, mirrors the `LSDRunner`/`lucy lsd check` precedent exactly. Windows is an accepted, documented WSL2/VM gap (Phase 100), not a blocker.
- [v10.0-roadmap]: **New `nus/` package, sibling of `lsd/`/`webview/`** — pre-CASE "dumb tool"; zero changes to `case.md` or the 5-agent team; the diff to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` must stay empty (enforceable-by-inspection constraint carried into Phase 97's success criteria).
- [v10.0-roadmap]: **QC gate is its own phase deliverable (Phase 99), not folded into peak-picking** — it is the mandatory automated defense against fabricated cross-peaks silently becoming hard LSD constraints (the milestone's crux risk per research).
- [v10.0 D-04 / Phase 100 close]: **SMILE's ~6.5 GB memory abort is independent of every caller-side knob** (direct-dim size, thread count, `-maxIter`) — characterized as a property of this macOS-arm64 `nusPipe` build, not a lucy-ng defect. RECON-F1 (hmsIST/mddnmr) is the tracked fallback; v10.1's JCAMP data happens to have been produced by `mddnmr` externally, making it the natural complementary path shipped first.
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

- **[2026-06-25] CASE4 azulene-regiochemistry-enumeration gap** — carried seed; not in v10.1 scope. See `.planning/todos/pending/2026-06-25-case4-azulene-regiochemistry-enumeration-gap.md`.
- **RECON-F1** — hmsIST/mddnmr fallback backend for in-lucy-ng NUS self-reconstruction (tracked from v10.0 close). Not in v10.1 scope (JCAMP ingestion is complementary, not the fallback itself), but noted as the natural next reconstruction-side step given `C20H32O2-jcamp` was itself produced by `mddnmr`.
- **JVAL-F2** (tracked from Phase 103 PARTIAL close) — real-data recalibration of the 2D noise/threshold model and/or the QC gate's quaternary-override mechanism for CS-reconstructed matrices; needs edits to files byte-frozen in Phase 103 (`nus/qc.py`, `PeakPicker2D`). See `.planning/REQUIREMENTS.md` § Future Requirements.
- **JVAL-F3** (tracked from Phase 103 PARTIAL close) — re-export `exp7`/wide as JCAMP-DX into `C20H32O2-jcamp` to complete the §10 1D-13C coverage gap; explicitly would NOT by itself fix `quaternary_exclusion` (JVAL-F2's job). See `.planning/REQUIREMENTS.md` § Future Requirements.

### Blockers/Concerns

None blocking further work. v10.1 milestone effectively closes PARTIAL: JC-01..04/JCLI-01..02
(Phases 101-102) fully shipped; JVAL-01/JVAL-02 (Phase 103) partial, with **JVAL-F2**
and **JVAL-F3** tracked as the named next steps (see Pending Todos above). Milestone-close
bookkeeping (`/gsd-complete-milestone`, infographic-deck refresh) is a separate command,
not yet run.

### Strategic Reference

See `background/sherlock-analysis.md` for full Sherlock vs lucy-ng comparison. v9.0 closed the end-to-end mechanism gap; v9.1 closed the three "clean-but-wrong" defect classes. v9.2 adds live observability; v9.3 deepens the inspector with spectra and data tables. v10.0 closes (partially — PORT shipped, VAL blocked) the NUS 2D reconstruction gap that timed out the first C20H32O2 CASE run. v10.1 opens a complementary, no-external-binary ingestion path (JCAMP-DX) that decouples CASE from the SMILE blocker entirely, and itself closes PARTIAL at Phase 103 (JVAL-01/JVAL-02, tracked via JVAL-F2/JVAL-F3) — mirroring v10.0's own honest-partial-close shape.

Key v9.0 constraint (still in force): SYME and DEFF NOT are lucy-ng abstractions. Native LSD-3.4.9 commands are: MULT, LIST, PROP, BOND, COSY, HMBC, ELIM, DEFF, FEXP, HSQC, ELEM.

## Session Continuity

Last session: 2026-07-28T07:14:28.707Z
Stopped at: Phase 103 closed PARTIAL (JVAL-01/JVAL-02 honest partial close, D-10)
Resume with: `/gsd-verify-phase 103` (to verify the honest-partial-close evidence), then consider `/gsd-complete-milestone` for v10.1 (PARTIAL) or a future phase to address JVAL-F2/JVAL-F3

---
*Last updated: 2026-07-28 — Phase 103 (End-to-End Validation, C20H32O2-jcamp) CLOSED PARTIAL. All six real `.dx` files read via one governed `lucy jcamp` invocation with zero read failures (HMBC unblocked by the D-09 reader fix); the full 31-cell D-03 knob matrix run and logged; QC verdict is a genuinely knob-independent critical FAIL (`quaternary_exclusion` hits at every one of the 8 HSQC matrix cells; `hsqc_coverage` capped by a verified real 1D-13C acquisition-window gap). A coordinator-requested read-only diagnostic against the raw JCAMP header and the untouched sibling Bruker tree's `acqus`/`procs` files (exp6/narrow vs exp7/wide) confirmed the window is a genuine dataset property, not a lucy-ng ppm-axis defect (JC-02/WR-04 risk class cleared). JVAL-01 and JVAL-02 both close PARTIAL; JVAL-F2 and JVAL-F3 filed as tracked next steps. Full suite 1468 passing, zero regressions. v10.1 milestone now effectively closes PARTIAL overall.*

## Operator Next Steps

- Phase 103 (end-to-end-validation-c20h32o2-jcamp) closed PARTIAL: run `/gsd-verify-phase 103` to verify the honest-partial-close evidence, then `/gsd-complete-milestone` to formally close v10.1 as PARTIAL (mirroring v10.0), or open a new phase/milestone to address JVAL-F2/JVAL-F3.

</content>
