# lucy-ng

**AI-agent powered Computer-Assisted Structure Elucidation for organic natural products**

## What This Is

Lucy-ng is an AI-agent skill for Computer-Assisted Structure Elucidation (CASE) of organic natural products from NMR spectroscopy data. The AI agent is the intelligence layer -- it reasons about spectra, detects problems, and drives the elucidation process. The Python tools are thin wrappers around external libraries (nmrglue, LSD, RDKit) that give the agent access to NMR data and solvers. The skill (CLAUDE.md) encodes domain expertise and workflow strategy.

## Core Value

An AI agent can autonomously determine the structure of an unknown organic compound from its NMR spectra, with a multi-agent architecture that prevents unproductive loops and keeps the elucidation on track.

## Current Milestone: v10.1 JCAMP-DX 2D Ingestion

**Goal:** lucy-ng reads already-reconstructed 1D/2D NMR spectra from JCAMP-DX files and produces the consumable CASE peak lists — with no external binaries — so CASE can run on NUS (or any) data reconstructed elsewhere (TopSpin/mddnmr, nmrXiv, any vendor JCAMP export).

**Target features:**
- **JCAMP-DX 2D NTUPLES reader** — decode the DIFDUP-compressed `##DATA TABLE=` pages (one per F1 row) into the existing `Spectrum2D` model; reuse nmrglue's line decoders (vendored to avoid depending on a private API).
- **Correct ppm axes** — map NTUPLES metadata (`VAR_DIM`, `FIRST`/`LAST`/`FACTOR`, `.NUCLEUS`, `.OBSERVE FREQUENCY`) to reversed ppm axes, cross-checked against the trusted 1D reference / the §10 shift list (the WR-04-class axis risk must be verified, not assumed). ⚠ **§10 is not ground truth** — it is a prior CASE agent's hypothesis about the unsolved C20H32O2 sample, so it can cross-check the *ppm axis across two readers* but cannot confirm an assignment; see tracked item **PROV-01**.
- **1D path** (¹H/¹³C) through the same reader into `Spectrum1D`.
- **CLI + bridge** — `lucy jcamp …` → existing `PeakPicker2D` → `analysis/nmr_peaks/*.json` → the **unchanged** Phase-99 QC gate; `case.md` byte-unchanged.
- **Validation** — the `C20H32O2-jcamp` dataset yields §8-quality peak lists and a fresh `/lucy-ng:case C20H32O2` converges on a finite rankable set.

**Key context:**
- Motivated by the v10.0 outcome: NUS self-reconstruction (NMRPipe+SMILE) is installed and the pipeline runs correctly *into* SMILE, but SMILE aborts with a ~6 GB `Cannot allocate memory` on the dev host (Phase 100 closed PARTIAL; RECON-F1 tracked). JCAMP ingestion is a **complementary input path, not a replacement** — it bypasses reconstruction by consuming spectra reconstructed elsewhere.
- The `C20H32O2-jcamp` data (6 `.dx` files, 2D grids 2048×2048) was reconstructed in TopSpin via `mddnmr` compressed sensing (IRLS) — i.e. the RECON-F1 algorithm, run manually — independently proving CS reconstruction succeeds on this exact sample.
- Feasibility spike done: nmrglue reads the 1D `.dx` files directly and its `_parse_data` decoder handles the 2D DIFDUP pages cleanly; the only gap is that nmrglue returns `None` for 2D NTUPLES assembly.
- **No external-binary dependency** → a real JCAMP fixture can be committed and run in CI — directly addressing the Phase-100 meta-learning that mock-only "verified" gave false confidence for an external-tool pipeline.

## v10.0 Automatic NUS 2D Reconstruction — PARTIAL 🟡 (paused 2026-07-20)

**Status:** PORT-01/PORT-02 shipped (platform preflight in `lucy nus check` + `docs/NUS-PORTABILITY.md` matrix, both verified). **VAL-01/VAL-02 NOT achieved** — honest stop per CONTEXT decision D-04: NMRPipe+SMILE was installed natively and the pipeline runs correctly through `nusExpand.tcl` → `bruk2pipe` → F2 processing *into* SMILE, but SMILE aborts (~6 GB `Cannot allocate memory`, proven independent of data size / threads / maxIter) on the dev host. **RECON-F1** (hmsIST/mddnmr fallback) is the tracked next step for self-reconstruction. The first real-binary run also found and fixed two genuine Phase-98 defects (nusExpand `-acqus`/`-acqu2s` paths; `nmrPipe` multi-`-fn` verb chaining — F2 was never FT'd/transposed). Full record: `phases/100-cross-platform-hardening-end-to-end-validation/VALIDATION.md`. The original v10.0 goal/features below remain the reference for the deferred self-reconstruction work.

**Goal:** Lucy-ng reconstructs non-uniformly-sampled (NUS) 2D NMR spectra fully automatically and without any GUI step — from Bruker `ser`+`nuslist` through a real compressed-sensing / IST / SMILE reconstruction to clean JSON peak lists — so that CASE runs on NUS data get reliable HSQC/HMBC/COSY connectivity.

**Target features:**
- **NUS reconstruction backend** (research-selected: NMRPipe+SMILE vs. hmsIST/mddnmr vs. Python-native CS/IST) — scriptable, no manual TopSpin GUI. TopSpin acceptable only if headless-drivable via API/CLI.
- **Automatic Bruker→backend conversion** — read `ser`, `nuslist`, `acqus`/`acqu2s`; build the sampling schedule and handle FnMODE (echo-antiecho HSQC/HMBC, QF COSY) with no manual step.
- **Fully automated reconstruction + processing pipeline** — NUS expansion, apodization, ZF, FT, phasing, baseline → 2D spectrum.
- **Peak picking → JSON peak lists** in the existing schema (HSQC edited-sign, HMBC, COSY) into `analysis/nmr_peaks/`.
- **Reusable `lucy` step/CLI** — usable by any NUS CASE run, not just C20H32O2.
- **Cross-platform portability** — backend + pipeline brought up as broadly as possible on macOS/Linux/Windows; unavoidable platform gaps are carefully investigated and documented in a portability matrix (what runs where, why not, workaround) rather than silently accepted. Primary dev/test platform stays local macOS Apple Silicon.
- **End-to-end validation** — C20H32O2 exp2/3/4 reconstructed, §8 quality gate passed, `/lucy-ng:case C20H32O2` converges on a small rankable solution set.

**Key context:**
- Full automation is a hard constraint; the first CASE run (2026-07-09, 5.5 h) failed on data quality, not method — the NUS 2D spectra were only approximated by an ad-hoc per-column IST in `nmrglue`, leaving HMBC/COSY too artefact-ridden (t1 ridges) to pin ring connectivity, so LSD could not prune the ~10⁶-candidate space for a tetracyclic C20 diterpene.
- Backend chosen by research with a recommendation; target environment as broad as possible (macOS/Linux/Windows), documented limitations allowed.
- Test case: `C20H32O2` (tetracyclic C20 diterpene, DBE 5) at `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/`. Task brief: `analysis/NUS-RECONSTRUCTION-GUIDE.md`.

## v9.3 CASE Web-View Stage 2 — SHIPPED ✅ (2026-07-12)

**Outcome:** All four target features shipped and verified (each phase VERIFICATION passed): formatted markdown run log + 4-tab framework (Phase 93), data tables (Phase 94), 1D real spectra + peak overlay (Phase 95), 2D real spectra + peak overlay (Phase 96). New `tables.py` + `spectra.py` routers on the v9.2 "tabs dock in without a rewrite" architecture; `.run_manifest.json` raw-Bruker-path wiring; matplotlib in the `[webview]` extra (OO-API/lazy, WV-08). Full archive: `milestones/v9.3-ROADMAP.md`, tagged `v9.3`. Two defects caught & fixed at Phase 96 verification (2D F1-axis inversion via the manual browser checkpoint; placeholder-figsize layout-jump via code review).

**Goal (shipped):** Grow the read-only CASE webview from a status monitor into a full run inspector — a formatted run log plus rendered spectra and data tables in tabs.

**Target features:**
- **Formatted run log** — render `CASE-PROGRESS.md` markdown in the log panel (headings, bold, tables, monospace code) instead of raw text (reverses v9.2 D-13; deferred-with-trigger in Phase 91, trigger met on the live CASE1 run).
- **1D spectra tabs** — non-interactive rendered ¹³C/¹H/DEPT plots from the Bruker data via the existing readers.
- **2D spectra tabs** — HSQC/HMBC/COSY contour plots (builds on the 1D plotting infrastructure).
- **Data tables** — peak lists, LSD constraint inventory, HMBC usage as tabbed tables.

**Key context:**
- Builds on the v9.2 architecture (design spec: "*endpoint structure scales cleanly to Stage 2*", "*tabs dock in without a rewrite*"). Design spec: `docs/superpowers/specs/2026-07-02-case-webview-design.md` § Stage 2.
- Spectra rendering needs **new plotting infrastructure** from Bruker data (new endpoints serving plot images + a tabbed frontend); 2D builds on 1D. The "dumb server" boundary holds — unit-testable from fixtures, no live agent-team run needed.
- **Deferred (not this milestone):** SSE/WebSocket live push to replace 3 s polling (optional optimization, no functional gain).

### v9.2 CASE Web-View — SHIPPED ✅ (2026-07-07)

**Goal (met):** A read-only web dashboard makes a CASE run observable live and after the fact — purely informative, no control functions.

**Outcome:** Stage 1 shipped and live-validated (CASE1: ibuprofen, Rank 1 MAE 0.25). `lucy webview serve/stop/status` (FastAPI, optional `lucy-ng[webview]` extra, core CLI dependency-free); four JSON/SVG endpoints with graceful degradation (200 not 500 on partial files); RDKit SVG depictions; single-file vanilla-JS auto-refresh dashboard (no build step); `case.md` auto-launches the dashboard at run-start and the detached server outlives the team. WV-01..08 all met. Full archive: `milestones/v9.2-ROADMAP.md`. Stage 2 (this milestone) carries the deferred formatted-log + spectra-tabs + data-tables work.

**Carried seed:** CASE4 azulene-regiochemistry-enumeration gap (4th defect class surfaced by the v9.1 blind UAT) — the di-methyl-ethyl class is now searched, but the exact chamazulene regiochemistry is not enumerated. See `.planning/todos/pending/2026-06-25-case4-azulene-regiochemistry-enumeration-gap.md`.

### v9.1 CASE Final-Answer Correctness & Verification Gates — SHIPPED ✅ (2026-06-29)

**Goal (met):** Close the three "clean-but-wrong" CASE failure classes (low MAE, plausible, but wrong) with verification gates, proven end-to-end by blind UATs.

**Outcome:** Three defect classes fixed + blind-validated. **RANK** — `lucy lsd rank` + `lucy predict c13` unified onto one DB-first prediction path. **IDENT** — installed `lucy identify` (shared deterministic core, reachable from any CASE data dir) + analyst tentative-naming + post-solution devils-advocate `G-IDENT` gate stop parametric naming hallucination. **MULT** — per-family multiplicity search + MAE-independent SEARCHED-not-RANKED `coverage_gate` + binding DA `G-MULT` flag close the wrong-class exclusion. **Blind-UAT gate** — five blind runs (RDKit-verified): CASE5 indigo / CASE6 citronellol / CASE7 virgiline / CASE8 eugenol PASS; CASE4 chamazulene conditional. Live-confirmed: `lucy identify` all 3 verdict branches; `G-IDENT` both branches; MULT fires/dormant correctly. Full archive: `milestones/v9.1-ROADMAP.md` + audit `milestones/v9.1-MILESTONE-AUDIT.md`. One deferred follow-up (the carried seed above).

### v9.0 CASE Reliability & Skill Consolidation — SHIPPED ✅

**Goal (met):** Make the CASE system work end-to-end via the intended mechanism — fix the tooling bugs the v8.0 UAT exposed, consolidate the skill/tool architecture, and re-answer the open 4J/aromatic design question — verified by a passing blind UAT on CASE1 **and** CASE9.

**Outcome:** AND-gate met cleanly on Opus 4.8. CASE9 (UAT-04) solved (`CC(C)OC(=O)c1ccc(C(C)O)cc1`, MAE 1.17). CASE1 (UAT-03) a CLEAN EMERGENT PASS — ibuprofen rank 1 (exact InChIKey, RDKit-verified), benzene ring emerged from constraints with **0 ring-BONDs / SKEL / SYME / DEFF NOT**, no manual bypass. **D-04 resolved to "emergent."** A substantial earlier-failure root cause turned out to be model-driven (a stale `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` override, now `inherit`). Full archive: `milestones/v9.0-ROADMAP.md`.

## Current State

**Version:** v10.1 closed PARTIAL and archived 2026-07-28 (tag `v10.1` on origin); v9.3 shipped 2026-07-12 (v9.2 2026-07-07, v9.1 2026-06-29, v9.0 2026-06-17)

**Since the v10.1 close (2026-07-31 → present) — milestone-less validation work, 26 commits.**
Not in any ROADMAP or phase directory by design. Full account in STATE.md
§ Post-Milestone Validation Work; the three things that change how the sections below read:

1. **A blind CASE benchmark is running on Sheldon** over a 258-dataset set, RDKit-graded.
   Snapshot 2026-08-25: 69 runs finished, **65 graded — 80 % top-1, 89 % correct at any
   rank**. ⚠ Two caveats travel with that number, permanently. Compare only against the
   **size-matched** baseline row (31 % / 55 %), never the all-sizes row — the set is ordered
   smallest-first. And the 65 span **two skill states and two team models** (`f9aa7b3`
   switched the team from Opus 4.8 to Opus 5 on 08-07; `d62d833` added the heteroatom-proton
   rule on 08-09). That mixing was **accepted deliberately on cost grounds** — a homogeneous
   re-run was judged too expensive for a result this unambiguous — so it is a property to
   state alongside the number, not an open defect. See STATE.md § Key Decisions (2026-08).
2. **PROV-01 concluded (2026-08-02) and it re-reads Phase 103's PARTIAL.** 37.86 ppm is a
   **CH**, not a quaternary carbon — the knob-independent `quaternary_exclusion` FAIL was the
   gate correctly reporting a wrong *input assumption*, not a reconstruction or threshold
   problem. The PARTIAL stands; its stated cause does not, and **JVAL-F2 is mis-scoped**.
   The JCAMP reader, by contrast, came out *validated by real use* — a much stronger result
   than Phase 103's circular "17/20 vs §10". The peak picker is the weak link, not the reader.
3. **On the harder benchmark cases the truth is outside the search space** — LSD never
   generates the correct structure (CASE175: absent from 600,707 candidates). A generation
   problem, not a ranking problem; verified with a positive control on three solved cases.

**In progress (v10.1):** Phase 103 (End-to-End Validation on `C20H32O2-jcamp`, JVAL-01/02) **CLOSED PARTIAL** 2026-07-28 — verification `passed` (9/9) for the phase's *own* deliverables, but both requirements close **NOT achieved** by the plan's D-10 honest-partial-close branch, on a user-approved checkpoint decision. What worked: all six real `.dx` files read in **one** governed `lucy jcamp` invocation with zero read failures — HMBC included, unblocked by a D-09 reader fix (13C ppm ceiling 230→250; the real HMBC legitimately reaches 234.81 ppm) — NOESY correctly skipped; the full 31-cell D-03 knob matrix recorded including losing cells; a 20-row §10 cross-check at **17/20** within ±0.5 ppm. **JVAL-01 NOT achieved:** QC verdict is a critical FAIL on `quaternary_exclusion` (a ~37.9 ppm HSQC hit reproduced in *all 8* HSQC matrix cells — knob-independent, not under-tuned) and `hsqc_coverage` (11/16 = 69 %). **JVAL-02 NOT attempted:** the FAIL correctly wrote no consumable peaks via the D-07 write boundary, so the fresh blind CASE handoff had nothing to read — recorded as not attempted, not as failed or achieved. A coordinator-ordered read-only ppm-axis diagnostic **cleared the JC-02/WR-04 risk class**: the narrow 1D-13C window is a genuine dataset property (raw Bruker `exp6`/narrow `$SW=120.28` vs `exp7`/wide `$SW=160.37`, only exp6 exported to JCAMP), confirmed against `acqus`/`procs` independently of our own reader. Tracked next steps: **JVAL-F2** (noise/quaternary-override recalibration) and **JVAL-F3** (re-export exp7/wide). Code review found 3 Critical: **CR-01** was this phase's own (a bare `--threshold` silently discarded a keyed `--snr-floor`) — fixed fail-loud, pinned by a mutation-confirmed regression test, plus three previously-vacuous tests repaired; **CR-02/CR-03** (jcamp `--out` purge runs before any input is read; unvalidated `work_root` `rmtree`) are Phase-102 data-loss defects, filed as tracked follow-ups rather than silently fixed. Full suite 1469 passed; byte-frozen paths (`nus/qc.py`, both pickers, `cli/pick.py`, `.claude/`) and the known-bad QC fixtures unchanged by diff.

Phase 102 (CLI + Peak-Pick Bridge + QC Reuse, JCLI-01/02) **COMPLETE & verified** 2026-07-25 (4/4 must-haves) — `lucy jcamp <dir-or-files>` runs read → pick → QC → write in one invocation, reusing the Phase-99 `bridge_peak_pick` and the byte-unchanged QC gate; new thin 1D bridge (`processing/jcamp_1d_bridge.py`) direct-calls the existing `AdaptivePeakPicker` and reproduces `cli/pick.py::pick_1d`'s exact payload shape, so the unchanged gate discovers it as trusted 1D reference (proven un-mocked). Also fixed a real Phase-101 reader defect: `_resolve_dim` raised `ValueError` for every homonuclear 2D experiment, which blocked **COSY**, not just NOESY — resolved with a narrowed positional fallback proven on the heteronuclear HSQC fixture (fail-loud default preserved). Shipped the repo's first committed SHA-256 byte-unchanged guard for `case.md` + the 5-agent team. Code review found and fixed one Critical (stale staging/consumable state survived across re-runs, silently defeating the D-07 write boundary). Full suite 1457 passed; `nus/`, `cli/pick.py`, both pickers and `.claude/` byte-unchanged by diff.

Phase 101 (JCAMP-DX Reader, JC-01..04) **COMPLETE & verified** 2026-07-23 — pure-Python `readers/jcamp.py` decodes 1D→`Spectrum1D` and 2D NTUPLES DIFDUP pages→`Spectrum2D` (closing nmrglue's `None` gap) via a vendored New-BSD line decoder (`_jcampdx_decode.py`, zero nmrglue-private-API), with verified reversed ppm axes (OFFSET+SF formula) cross-checked against the trusted 1D reference — a check that caught a real F1-anchor bug. CI-runnable committed real fixture; full suite 1408 passed. Next: Phase 103 (End-to-End Validation on `C20H32O2-jcamp`) — driving the real, uncommitted 2048×2048 dataset to a green §8 verdict and CASE convergence is explicitly Phase-103/JVAL work, deliberately not claimed by Phase 102 (D-05).

**What shipped in v9.3 (CASE Web-View Stage 2, phases 93–96):** The read-only dashboard grew into a full spectral-inspection suite — a persistent 4-tab bar (Run Log / 1D / 2D Spectra / Tables) over a markdown-rendered run log (hand-rolled XSS-safe DOM renderer), data tables (¹³C signals, HSQC/HMBC/COSY correlations with HMBC flag colours, LSD constraint inventory), and **real rendered 1D + 2D NMR spectra with the picked peaks overlaid** (reversed ppm axes; HMBC flag-coloured markers; COSY diagonal). New `tables.py` + `spectra.py` routers; `.run_manifest.json` raw-Bruker-path wiring; matplotlib in the `[webview]` extra (OO-API/lazy, WV-08, base CLI dependency-free); 2D block-max decimation + MAD contour levels + mtime PNG cache. Validation-only across CASE1–9 (no new milestone UAT).
**Codebase:** Python package (`src/lucy_ng/`) + `src/lucy_ng/webview/` (optional `[webview]` extra), test suite **1482 tests** collected (2026-08-25; 1468 at the Phase-103 close, 1174 at v9.2 close)
**Database:** SQLite with 928K compounds, 7.9M HOSE statistics + fragment library (2.4M SSCs)
**Agent definitions:** 4-agent CASE team + case.md orchestrator (in `repo/.claude/`, symlinked into `~/.claude`)
**New CLI (v9.1):** `lucy identify` (structure→identity gate); `lucy pick hsqc` now reports `multiplicity_edited`; `lucy lsd rank` unified onto the shared 13C predictor.

**What shipped in v9.2 (CASE Web-View, phases 90–92):** A read-only web dashboard that makes a CASE run observable live and after the fact — `lucy webview serve/stop/status` (FastAPI, optional `lucy-ng[webview]` extra; core CLI stays dependency-free), four JSON/SVG endpoints with graceful degradation (missing/partial files → HTTP 200, never 500), RDKit SVG depictions, and a single-file vanilla-JS dashboard (3 s polling, no build step). The `case.md` orchestrator auto-launches the dashboard at run-start and reports the URL; the detached server (`start_new_session=True`) outlives the team. Live-validated on a CASE1 run (ibuprofen, Rank 1 MAE 0.25). Stage 2 (formatted log + spectra tabs + data tables) deferred to v9.3.

**What shipped in v9.1:** Three "clean-but-wrong" CASE failure classes closed with verification gates, blind-validated end-to-end. RANK (ranker↔predict unified, ibuprofen MAE 2.23→0.24); IDENT (`lucy identify` + post-solution `G-IDENT` gate stop naming hallucination); MULT (per-family multiplicity search + MAE-independent `coverage_gate` + binding `G-MULT` flag). Validated by 5 blind UATs (CASE5/6/7/8 PASS, CASE4 conditional), each RDKit-verified.

**What shipped in v9.0:** End-to-end CASE reliability — `lucy lsd run`/outlsd plumbing; native-only constraint translation (SYME→BOND/COSY, DEFF NOT→DEFF F/FEXP); peak-picking SNR-floors (FIX-08/12); constraint-hardness guard (FIX-10); blind-UAT skill decontamination (FIX-09). Validated: CASE9 solved + CASE1 clean emergent pass.

**Known deferred:** CASE4 azulene-regiochemistry-enumeration gap (4th defect class; exact chamazulene regiochemistry not yet reachable). See STATE.md Deferred Items.

## Architecture

- **Skill** (CLAUDE.md/SKILL.md): Domain expertise, workflow strategy, error handling knowledge -- the intelligence layer
- **Thin Tools**: Minimal Python CLI wrappers around nmrglue, LSD, RDKit, SQLite
- **Multi-Agent**: CASE agent (autonomous elucidation) + CASE orchestrator (loop detection, advisory intervention) + diagnostic specialist (deep LSD failure analysis)
- **Database**: SQLite with 928K compounds and 7.9M HOSE statistics

## Requirements

### Validated

- Read 1D Bruker NMR files (1H, 13C) — v1.0
- Read 2D Bruker NMR files (HSQC, HMBC, COSY) — v1.0
- Automated peak picking for 1D spectra — v1.0
- Automated peak picking for 2D spectra (DEPT-guided, HMBC-guided) — v1.0
- Generate LSD/pyLSD input file format — v1.0
- Execute LSD/pyLSD and parse results — v1.0
- CLI interface for all operations (7 command groups) — v1.0
- MCP server exposing tools for Claude (13 tools) — v1.0
- HOSE-based 13C shift prediction for solution ranking — v1.0
- NMRXiv dataset fetching — v1.0
- SQLite database for 928K compounds (COCONUT + NMRShiftDB) — v1.1
- Database-backed dereplication (~100x faster) — v1.1
- Database-backed 13C prediction with 7.9M HOSE statistics — v1.2
- MCP tool for checking prediction capability (get_hose_stats_info) — v1.2
- Sub-command skills following GSD pattern (sanitise, dereplicate, case, predict, status) — v2.1
- CASE orchestrator with real agent spawning, progress monitoring, loop detection, diagnostic delegation — v2.1
- Autonomous CASE agent definition with full skill knowledge and CASE-PROGRESS.md writing — v2.1
- AI-driven dataset sanitisation (compound identity removal, no CLI) — v2.1
- Diagnostic specialist agent reworked for orchestrator integration — v2.1
- Statistical hybridisation detection from HOSE database (sp1/sp2/sp3) — v3.0
- Statistical neighbourhood detection (forbidden/mandatory bond partners) — v3.0
- Hetero-hetero bond allowance detection from bond pair statistics — v3.0
- Signal grouping detection (close shifts within 0.25 ppm tolerance) — v3.0
- Two-tier ranking (match count priority prevents MAE hallucination) — v3.0
- Badlist filters (3/4-membered strained ring exclusion via DEFF NOT) — v3.0
- CASE agent integration with statistical detection and chemistry-first hierarchy — v3.0

### Validated (v4.0)

- 5-agent CASE team architecture (coordinator, nmr-chemist, lsd-engineer, solution-analyst, devils-advocate) — v4.0
- Team-based orchestrator skill replacing single-agent Task() spawning — v4.0
- Constraint inventory managed by lsd-engineer (read previous file, never reconstruct from memory) — v4.0
- Pre-run LSD validation by devils-advocate (diff vs previous, sp2, H budget, DEFF NOT, SYME) — v4.0
- Post-run solution quality review by solution-analyst (chemical plausibility, aromatic ring verification) — v4.0
- Real-time peer feedback protocol (any agent can flag issues in any other agent's work) — v4.0
- CASE-PROGRESS.md updated for team workflow (multi-agent contributions per iteration) — v4.0
- Aromatic ring awareness: nmr-chemist flags expectation, solution-analyst verifies, remediation guidance for 4J — v4.0
- Diagnostic specialist integration with team context (constraint inventory, analysis/ paths) — v4.0

### Validated (v5.0)

- Fragment library: 2.4M SSCs from 928K compounds with two-phase search engine — v5.0
- DEFF/FEXP goodlist injection validated with LSD smoke test — v5.0
- Agent team integration: lsd-engineer fragment search, devils-advocate file verification — v5.0
- Self-search recall 100% (fingerprint indexing validated) — v5.0

### Validated (v6.0)

- Factored case.md orchestrator (<500 lines) with extracted reference files (progress-format, loop-patterns, advisory-templates) — v6.0
- Archived legacy monolithic lucy-case-agent.md with deprecation header — v6.0
- Shared NMR reference tables (nmr-basics.md) referenced by agents instead of inlined — v6.0
- 4J HMBC coupling awareness: nmr-chemist flags, lsd-engineer defers, solution-analyst verifies via prediction — v6.0
- Orchestrator structured message validation with RESEND-REQUIRED protocol — v6.0
- Natural-language trigger phrases in all 5 skill descriptions + routing decision tree — v6.0
- Dry-run confirmation gate in sanitise, HOSE miss recovery in predict, 0-match guidance in dereplicate — v6.0
- Version compatibility check in status skill, smoke test mode in CASE orchestrator — v6.0

### Validated (v9.0 / v9.1)

- End-to-end CASE reliability: lsd-run/outlsd plumbing, native-only constraints, peak-picking SNR-floors, constraint-hardness guard, blind-UAT skill decontamination — v9.0
- Ranker↔predict unification: one DB-first 13C prediction path (RANK-01/02/03) — v9.1
- Tool-derived identity gate: installed `lucy identify` + analyst tentative-naming + post-solution devils-advocate `G-IDENT` (IDENT-01/02/03) — v9.1
- Aliphatic multiplicity coverage: per-family LSD search + MAE-independent `coverage_gate` + binding `G-MULT` flag + `pick hsqc multiplicity_edited` detector (MULT-01/02/03/04) — v9.1
- Blind-UAT validation gate: 5 RDKit-verified blind runs (CASE5/6/7/8 pass, CASE4 conditional) (UAT-01/02/03) — v9.1

### Validated (v9.2 — CASE Web-View)

- `lucy webview serve/stop/status`: read-only FastAPI dashboard server with PID-aware `.webview.json` lifecycle, idempotent start, detached process that outlives the caller; optional `lucy-ng[webview]` extra, core CLI dependency-free (WV-01/02/08) — v9.2
- Dashboard endpoints + UI: `/api/status|/api/log|/api/structures|/api/structure/{i}.svg` with graceful degradation (200 not 500 on partial files; 404 out-of-range; placeholder on malformed SMILES), RDKit SVG depictions, single-file vanilla-JS auto-refresh frontend, no build step (WV-03/04/05/06) — v9.2
- Orchestrator auto-launch: `case.md` starts the dashboard at run-start, reports URL + stop hint, server outlives `terminate_team`; live-validated on CASE1 (WV-07) — v9.2

### Validated (v9.3 — CASE Web-View Stage 2)

- Formatted run log + 4-tab framework: persistent Run Log / 1D / 2D Spectra / Tables bar; CASE-PROGRESS.md rendered as markdown via a hand-rolled createElement/textContent DOM renderer (XSS-safe, no innerHTML of server content); `webview.js` served as a static asset (LOG-01, TAB-01) — v9.3
- Data tables: `tables.py` router, 5 never-500 routes — ¹³C signals, HSQC/HMBC/COSY correlations (HMBC flag colours), LSD constraint inventory from the latest `compound.lsd`; per-panel "waiting for data" state (TBL-01/02/03) — v9.3
- 1D real spectra + peak overlay: `spectra.py` router renders real ¹³C/¹H Bruker traces (BrukerReader/nmrglue + matplotlib Agg) on a reversed ppm axis with picked peaks overlaid; `.run_manifest.json` raw-data path wiring; matplotlib in `[webview]` extra, lazy imports (SP1-01, SP-02, WV-08) — v9.3
- 2D real spectra + peak overlay: three `/api/spectra/2d/{hsqc,hmbc,cosy}` routes render real HSQC/HMBC/COSY contour plots with cross-peak overlays (open circles; HMBC flag colours; COSY diagonal; reversed axes both dims), block-max decimation ≤512×512, MAD-threshold geometric levels, mtime PNG cache, never-500 degradation (SP2-01, SP-02) — v9.3

### Validated (v10.0 — Automatic NUS 2D Reconstruction)

- NUS backend detection + params/schedule parsing (Phase 97): `lucy nus check` detects the NMRPipe+SMILE toolchain (`nmrPipe`/`bruk2pipe`/`nusExpand.tcl` on PATH + `nmrPipe -fn SMILE -help` capability probe, NOT a `smileNus` binary), separates `not_installed` from `installed_not_sourced`, fails loud exit 1; `lucy nus params/schedule <expdir> --format json` parse validated `NusAcquisitionParams`/`NusSchedule` per-experiment (FnMODE read from `acqu2s` F1, SF/OFFSET from `pdata/1/procs`, nuslist never sorted, hard `n_sampled==len(nuslist)` assertion), verified against real C20H32O2 exp2/3/4 fixtures; core CLI stays dependency-free behind an empty `[nus]` extra (NUS-01..05) — v10.0
- NUS reconstruction + processing pipeline (Phase 98): `lucy nus reconstruct <expdir>` runs the full headless chain via `NusRunner.reconstruct()` — FnMODE-branched `convert()` (bruk2pipe/nusExpand order flips echo-antiecho vs QF, `nus_td` full grid, exact `-grpdly`) → `process_direct()` (F2 apod/ZF/FT/PS/baseline + `TP`) → SMILE `reconstruct_indirect()` (consumes the F2-processed transposed FID, `-maxIter` upper bound + `-nSigma` convergence) → `process_indirect()` (F1 + reversed 1D-calibrated ppm axes); single fail-loud `run_stage()` per subprocess stage checks exit code + output-file non-emptiness/not-all-zero across `.fid`/`.ft1`/`.ft2` (RECON-04); CLI exposes `--iterations`/`--threshold`/`--virtual-echo` + phase overrides (RECON-05); intermediates kept under `analysis/nus_recon/<expN>/`; QF/COSY branch + F1 phase defaults annotated PROVISIONAL pending Phase-100 real-data spike; CI via mocked subprocess boundary + skipif backend-gated integration test, no `ser` in repo (RECON-01..05) — v10.0
- Peak-pick bridge + QC gate + CLI (Phase 99): `nus/bridge.py` builds a `Spectrum2D` from the processed `.ft2` in memory and calls the existing `PeakPicker2D` directly (mirrors `_perform_ranking()`), transforming picker output into the per-experiment `analysis/nmr_peaks/*.json` schema (HSQC `c13_ppm`/`h1_ppm`/`edited_sign`/`multiplicity_hint`; HMBC `rel_intensity`/`rank_in_carbon`/`suspected_1J_artifact`; COSY `h1a_ppm`/`h1b_ppm`) with an additive top-level `reconstruction` metadata block (backend/iterations/qc verdict) + verdict-derived per-peak confidence replacing the blanket `"low"` (PICK-01/03); `nus/qc.py` runs a headless six-check gate cross-checking every correlation against the trusted 1D lists — critical (quaternary-exclusion, ppm-calibration reusing `postprocess.check_calibration()`, signal-to-ridge, HSQC-coverage) ⇒ FAIL, soft (edited-sign consistency, COSY diagonal symmetry) ⇒ PARTIAL — with an honest 3-tier prot/quaternary resolver (DEPT → explicit `known_quaternary_shifts` override → insufficient-reference-data flag, never `detect_hybridisation`), proven discriminating against the real known-bad home-IST fixtures (FAIL) vs a synthetic-clean set (PASS) (QC-01/02); `lucy nus qc <peaks-dir>` (standalone, keyword-glob, exit≠0 on FAIL) + `lucy nus pipeline <expdir>` (full chain, D-07 write boundary: PASS/PARTIAL write consumable peaks, FAIL quarantines to `analysis/nus_recon/<expN>/qc_failed/` + exits non-zero) with `--format json` throughout (PICK-02/QC-03); `case.md` + `cli/pick.py` byte-unchanged (CASE-pipeline-unchanged invariant held); full suite 1373 passed. Real-data clean-reconstruction PASS + full external NMRPipe+SMILE run deferred to Phase 100/VAL (PICK-01..03, QC-01..03) — v10.0

### Validated (v10.1 — JCAMP-DX 2D Ingestion, CLOSED PARTIAL)

- JCAMP-DX reader (Phase 101): pure-Python `readers/jcamp.py` decodes 1D `.dx` → `Spectrum1D` and 2D NTUPLES DIFDUP pages → `Spectrum2D` — closing the gap where nmrglue returns `None` for 2D NTUPLES assembly — via a vendored New-BSD line decoder (`_jcampdx_decode.py`, zero nmrglue private-API), with reversed ppm axes from the verified OFFSET+SF formula (not the naive SFO divisor) cross-checked against the trusted 1D reference, a fail-loud plausibility guard, and a committed CI-runnable real fixture. The cross-check caught a real F1-anchor bug — the check earned its keep (JC-01..04) — v10.1
- `lucy jcamp` CLI + peak-pick bridge + QC reuse (Phase 102): one `@click.command("jcamp")` discovers a directory or explicit file list, routes 2D HSQC/HMBC/COSY through the byte-unchanged Phase-99 `bridge_peak_pick()` and 1D ¹H/¹³C through a new thin `processing/jcamp_1d_bridge.py` whose payload matches `cli/pick.py::pick_1d` exactly (proven un-mocked, so the unchanged gate discovers it as trusted 1D reference), runs the byte-unchanged QC gate **exactly once** over the fully staged set, and enforces the D-07 write/quarantine boundary — proving the Phase-99 bridge+QC design generalizes to a second, entirely different upstream source. Also fixed a real Phase-101 defect (`_resolve_dim` raised for every homonuclear 2D, blocking COSY) and shipped the repo's first committed SHA-256 byte-unchanged guard for `case.md` + the 5-agent team (JCLI-01/02) — v10.1

### Not achieved in v10.1 (tracked, not silently dropped)

- [~] **JVAL-01** — real `C20H32O2-jcamp` spectra never cleared the QC gate. All six `.dx` read in one governed run with zero failures and the full 31-cell knob matrix exhausted, but the verdict is a **critical FAIL**: `quaternary_exclusion` (a ~37.9 ppm HSQC hit reproduced in *all 8* HSQC matrix cells — knob-independent, not under-tuned) and `hsqc_coverage` (69 %). Tracked: **JVAL-F2** (noise/quaternary-override recalibration), **JVAL-F3** (re-export `exp7`/wide — completes §10 coverage but does not fix `quaternary_exclusion`).
- [~] **JVAL-02** — **not attempted**, not failed. The FAIL correctly produced no consumable peaks via the D-07 boundary, so a fresh blind CASE session had nothing to read.
- [x] **CR-02 / CR-03** — two real data-loss paths in `lucy jcamp`, attributable to Phase 102 (`f6de196`): the `--out` purge ran before any input was read, and `work_root` could `rmtree` a caller-owned directory. Found by Phase 103's code review, filed rather than fixed at the close — **fixed 2026-08-03 in `7dfe2ce`**, outside any phase.

Ruled out and worth remembering: the **JC-02/WR-04 ppm-axis defect class is cleared** for this dataset. The narrow 1D-¹³C window is a genuine export property — `exp6`/narrow (`$SW=120.28`) was exported to JCAMP, `exp7`/wide (`$SW=160.37`) was not — proven against raw Bruker `acqus`/`procs` independently of our own reader, rather than trusting the reader's self-report.

### Deferred
- [ ] CASE4 azulene-regiochemistry-enumeration gap — exact chamazulene regiochemistry not reachable (di-methyl-ethyl class is searched). 4th defect class surfaced by v9.1 UAT-01. (todo `2026-06-25-case4-azulene-regiochemistry-enumeration-gap`)
- [ ] 4J HMBC coupling handling via pyLSD (Priority 1 — v7.0 statistical approach failed, pyLSD solver-based approach next)
- [ ] Multi-compound CASE comparison UAT (blocked on 4J handling or non-aromatic test compounds)
- [ ] Support for COSY correlations in LSD constraints (Priority 3)
- [ ] NP-likeness scoring for solution filtering (Priority 4 — RDKit built-in)
- [ ] Multi-fragment sequential injection (FRAG-05)
- [ ] Solvent-aware 13C prediction
- [ ] Stereochemistry handling (E/Z, R/S)
- [ ] Interactive CASE mode with user feedback loop

### Out of Scope

- NMR spectrum prediction from structures - use HOSE codes instead
- GUI or web visualization - purely programmatic interface
- Non-Bruker vendor formats (Varian, JEOL, etc.) - Bruker only for v1
- SENECA integration - requires Java GUI rebuild, deferred

## Constraints

- Python 3.10+ required
- Open source only - no proprietary dependencies
- Open data formats - no vendor lock-in
- Must interface with existing LSD/pyLSD CLI tools

## Context

### Background

Lucy was the original CASE software created by the project author and sold to Bruker. Lucy-ng represents a complete reimagining for the AI-agent era, prioritizing programmatic interfaces over GUI interactions.

### Strategic Reference

See `background/sherlock-analysis.md` — deep comparison of Sherlock CASE (Wenk PhD thesis) vs lucy-ng capabilities. Updated post-v4.0 with gap closure status and prioritized next milestones. Key finding: 4 of 5 critical gaps closed (v3.0/v4.0); fragment library (24.5M SSCs) is the remaining major gap for Sherlock parity.

### Problem

Existing NMR processing tools like nmrium are GUI-focused, making it difficult for AI agents to interact with them programmatically. An unattended system that can iterate through structure elucidation without human intervention requires a different architecture.

### Target Users

- Cheminformatics researchers
- Natural products chemists
- AI/ML researchers working on structure elucidation

### NMR Data Requirements

Minimum viable spectral data for v1:
- 1D: 1H and 13C spectra
- 2D: HSQC (direct C-H correlations) and HMBC (long-range correlations)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid CLI + MCP interface | MCP provides structured tools for agent iteration; CLI enables testing and scripting | Good |
| Bruker-only for v1 | Focus on most common format, expand vendor support later | Good |
| LSD/pyLSD as primary solvers | Established CASE tools with CLI interface | Good |
| nmrglue for NMR parsing | Most mature, BSD licensed, native Bruker support | Good |
| Pydantic v2 for models | Type safety, validation, JSON serialization | Good |
| DEPT-guided adaptive thresholding | Lower HSQC threshold until all DEPT carbons matched | Good |
| HMBC-guided peak picking | Filter by requiring C match in 13C/DEPT and H match in HSQC | Good |
| N:1 shift matching for ranking | Handles molecular symmetry correctly | Good |
| SQLite for dereplication DB | Portable, no server, formula-indexed for fast lookup | Good |
| HOSE codes for prediction | Pure Python, no external services, reasonable accuracy | Good |
| AI as intelligence layer | v2.0: Domain knowledge belongs in skill, not Python code | Good |
| Multi-agent CASE | v2.0: Supervisor prevents loops, specialists handle subtasks | Revisit — v2.0 defined on paper only, v2.1 delivers working orchestration |
| Error tolerance as skill knowledge | v2.0: Teach AI to detect close shifts, ambiguity -- not Python machinery | Good |
| MCP removed, CLI-only | v2.0: Single interface, AI uses thin CLI via Bash | Good |
| GSD-pattern sub-commands | v2.1: Skills as ~/.claude/commands/lucy-ng/*.md with Task() agent spawning | Good |
| /lucy-ng:case NEVER dereplicates | v2.1: Absolute separation — dereplication is a separate sub-command | Good |
| Sanitisation is AI-only | v2.1: No CLI for sanitise — requires AI reasoning to identify compound identifiers | Good |
| Orchestration via Task() | v2.1: Orchestrator spawns agents using Task() with model: inherit | Good |
| Hybrid context inlining | v2.1: ~500-700 lines critical knowledge inlined in agents, detailed references via file paths | Good |
| Per-pattern intervention counters | v2.1: Track failures separately per loop pattern, 10-cycle escalation | Good |
| Diagnostic delegation threshold | v2.1: Specialist spawned after 2 failed basic interventions with same pattern | Good |
| Data-driven statistical detection | v3.0: Replace agent guesswork with HOSE database statistics (inspired by Sherlock CASE) | Good |
| Chemistry-first hierarchy | v3.0: NMR evidence (DEPT/HSQC/HMBC) always overrides statistical detection | Good |
| Two-tier ranking | v3.0: Match count primary, MAE secondary — prevents hallucination from wrong structures with coincidentally low MAE | Good |
| Badlist via DEFF NOT | v3.0: Hardcoded strained ring exclusion in agent knowledge rather than automated filtering | Good — but agent drops across iterations |
| Schema migration chain | v3.0: ALTER TABLE v3→v4→v5→v6 with backward-compatible queries | Good |
| Team-based CASE | v4.0: 5-agent team (coordinator, nmr-chemist, lsd-engineer, solution-analyst, devils-advocate) replacing single autonomous agent. Peer feedback eliminates constraint loss. | Good — all v3.0 bugs fixed |
| Constraint inventory in LSD headers | v4.0: JSON block tracking all constraint types, read-previous-never-reconstruct rule, DA reconciliation | Good |
| Coordinator-as-sole-writer | v4.0: Agents post via SendMessage, coordinator writes CASE-PROGRESS.md — prevents corruption | Good |
| Aromatic ring awareness | v4.0: Post-ranking sanity check when NMR evidence shows aromatic pattern but solutions lack rings | Good — caught in UAT |
| Separate fragment DB | v5.0: lucy-ng-fragments.db (605 MB) independent from main DB (2.8 GB) — prevents Dropbox sync contention | Good |
| 2 ppm fingerprint bins | v5.0: 256-bit fingerprint with 2 ppm bins validated by 100% self-search recall on 1K sample | Good |
| DEFF goodlist over badlist | v5.0: DEFF/FEXP constrains structures TO contain fragment (positive constraint, more powerful than exclusion) | Good — LSD smoke test confirms |
| Fragment persistence rule | v5.0: Copy DEFF F1/FEXP from previous LSD file, never reconstruct — same as DEFF NOT rule | Good |
| UAT deferral for 4J risk | v5.0: All 6 compounds have 4J HMBC risk, deferred CASE comparison to avoid confounding variables | Pending — need non-aromatic compounds |
| Factored case.md with references | v6.0: Extract progress-format, loop-patterns, advisory-templates to references/ for on-demand loading | Good |
| 4J heuristic flagging | v6.0: nmr-chemist flags potential 4J in aromatic systems, lsd-engineer defers, solution-analyst verifies via prediction | Good — heuristic, statistical detection still needed |
| Message validation protocol | v6.0: Orchestrator enforces required fields with RESEND-REQUIRED fallback | Good |
| Trigger phrase pattern | v6.0: "Use when:" prefix in skill descriptions for NL intent routing | Good |
| Dry-run gate in sanitise | v6.0: READ-ONLY scan, manifest report, exact "proceed" required before writes | Good |
| Smoke test mode | v6.0: --smoke-test flag for 1-iteration CASE pipeline validation | Good |
| Statistical 4J detection abandoned | v7.0: HOSE pair distance statistics produce 100% false positive rate — j5_plus dominates universally. Approach fundamentally non-viable. | Failed |
| pyLSD for 4J handling | v7.0 post-mortem: Use constraint solver to explore 4J possibilities directly rather than statistical pre-filtering | Pending |

## Technical State

**Version:** v6.0 (shipped 2026-03-10)
**Codebase:** ~20,974 lines Python, 867 tests
**Tech stack:** Python 3.10+, Pydantic v2, nmrglue, RDKit, NumPy, SQLite, Click
**Database:** v6 schema with 928K compounds, 7.89M HOSE statistics + fragment library (2.4M SSCs, 605 MB)
**Agent definitions:** ~3,600 lines across 6 files (5 agents + orchestrator skill)

**Capabilities:**
- 11 CLI command groups, 30+ commands (thin data-access wrappers)
- 4 statistical detection commands: hybridisation, neighbours, hhb, grouping
- Fragment library: build, search, to-lsd, info commands
- Two-tier ranking with badlist strained ring exclusion + aromatic ring sanity check
- SQLite databases: compound DB (928K compounds, COCONUT + NMRShiftDB) + fragment DB (2.4M SSCs)
- 7.89M HOSE statistics for 13C prediction and statistical detection
- Full CASE pipeline: peak picking → statistical detection → fragment search → LSD generation → solving → ranking
- Sub-command skills: status, dereplicate, predict, sanitise, case (in ~/.claude/commands/lucy-ng/)
- 5-agent CASE team with fragment integration: lsd-engineer searches+injects fragments, devils-advocate verifies files
- Diagnostic specialist: lucy-diagnostic.md (constraint inventory-aware, team context)
- CASE orchestrator: spawns 5-agent team via TeamCreate, monitors CASE-PROGRESS.md, detects 4 loop patterns
- Constraint inventory: JSON tracking in LSD file headers, DA reconciliation gate, DEFF/FEXP tracking

**Known tech debt:**
- 4J HMBC couplings through aromatic rings: heuristic flagging in v6.0, statistical approach failed in v7.0 — next approach: pyLSD integration
- Multi-compound CASE UAT deferred — all test compounds have 4J risk
- 2 minor integration gaps from v6.0 audit (INTL-03 aromatic expectation relay, INTL-04 4J status field validation) — cosmetic

---
### v9.0 Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Single solver path (D-02) | v8.0 agent reverted to better-documented normal-LSD; one path removes the ambiguity | Good |
| Native-only constraint translation (D-03) | SYME/DEFF NOT are lucy-ng abstractions, not native LSD-3.4.9; translate to BOND/COSY + DEFF F/FEXP at the boundary | Good |
| Emergent aromatic ring (D-04) | Ring should arise from sp2 MULT + HMBC anchors + cross-ring COSY + ring-size exclusion, not a forced SKEL/ring-BOND | Good — confirmed by CASE1 UAT-03 (0 ring-BONDs) |
| SNR-floor peak picking (FIX-08/FIX-12) | Fraction-of-max masks weak quaternary carbonyls (13C) and ring-diagnostic 3J-meta cross-peaks (HMBC) | Good |
| Constraint-hardness guard (FIX-10) | An uncertain inference must never become a hard, solution-excluding LSD constraint | Good |
| `CLAUDE_CODE_SUBAGENT_MODEL=inherit` | A stale `=sonnet` override silently forced all subagents to Sonnet 4.6 and drove earlier CASE failures | Good — Opus 4.8 then solved both cases |

---
*Last updated: 2026-07-28 — **Phase 103 (End-to-End Validation, JVAL-01/02) CLOSED PARTIAL.** Verification `passed` (9/9) on the phase's own deliverables; both requirements close NOT achieved via the plan's D-10 honest-partial-close, on a user-approved checkpoint decision. Six real `.dx` files read in one governed `lucy jcamp` run, zero read failures (HMBC unblocked by the D-09 230→250 ppm ceiling widening; the real HMBC reaches 234.81 ppm), full 31-cell D-03 matrix logged including losing cells, §10 cross-check 17/20 within ±0.5 ppm. JVAL-01 fails the QC gate critically on `quaternary_exclusion` (reproduced in all 8 HSQC matrix cells — knob-independent) and `hsqc_coverage` (69 %); JVAL-02 not attempted because the FAIL correctly wrote no consumable peaks. The JC-02/WR-04 ppm-axis risk class is **cleared** by a read-only diagnostic against raw Bruker `acqus`/`procs`: the narrow 13C window is a real dataset property (exp6/narrow exported, exp7/wide not), not a reader defect. Tracked: JVAL-F2, JVAL-F3. Code review: CR-01 (this phase's own silent-ignore defect in the new per-experiment knobs) fixed fail-loud and pinned by a mutation-confirmed test, three vacuous tests repaired; CR-02/CR-03 (Phase-102 `rmtree`/purge data-loss paths) filed, not fixed. Full suite 1469 passed; byte-frozen paths and known-bad fixtures unchanged. Next: `/gsd-complete-milestone` for v10.1 — note the milestone closes PARTIAL, like v10.0.*

Previously: *2026-07-25 — **Phase 102 (CLI + Peak-Pick Bridge + QC Reuse, JCLI-01/02) COMPLETE & verified** (4/4 must-haves). Shipped `lucy jcamp` (read → pick → QC → write in one command, dir or explicit file list, `--format json`, `--out` override) reusing the byte-unchanged Phase-99 `bridge_peak_pick` + QC gate, plus a new thin 1D bridge (`processing/jcamp_1d_bridge.py`) whose payload matches `cli/pick.py::pick_1d` exactly so the unchanged gate finds it as trusted 1D reference (proven with a real, un-mocked `QcReferenceData.resolve()` run). Fixed a real Phase-101 reader defect — `_resolve_dim` raised `ValueError` for every homonuclear 2D experiment, blocking COSY (a required experiment), not just NOESY — via a narrowed positional fallback proven on the heteronuclear HSQC fixture, fail-loud default preserved. Committed trimmed COSY/HMBC/NOESY fixtures so directory mode is fixture-covered, not mock-covered. First committed SHA-256 byte-unchanged guard for `case.md` + the 5 `lucy-*.md` agent files. Code review found 1 Critical (stale staging/consumable state survived re-runs, silently defeating the D-07 write boundary — a PASS run's output kept advertising `qc_verdict: PASS` after a later FAIL); fixed with regression tests for both proven scenarios. Observed fixture verdict is FAIL for an honest, stated reason (16 trimmed F1 rows cannot reach the 0.8 `hsqc_coverage` floor) — recorded as observed, not spun as success. Edited-HSQC sign proven on real fixture data (115 cross-peaks, 70 CH_or_CH3 / 45 CH2, zero ambiguous). Full suite 1457 passed, mypy/ruff at pre-existing baseline, byte-frozen paths unchanged by diff. Next: Phase 103 (End-to-End Validation, JVAL-01/02) — the real 2048×2048 dataset, green §8 verdict and CASE convergence live there (D-05), deliberately not claimed here.*