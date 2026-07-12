# lucy-ng

**AI-agent powered Computer-Assisted Structure Elucidation for organic natural products**

## What This Is

Lucy-ng is an AI-agent skill for Computer-Assisted Structure Elucidation (CASE) of organic natural products from NMR spectroscopy data. The AI agent is the intelligence layer -- it reasons about spectra, detects problems, and drives the elucidation process. The Python tools are thin wrappers around external libraries (nmrglue, LSD, RDKit) that give the agent access to NMR data and solvers. The skill (CLAUDE.md) encodes domain expertise and workflow strategy.

## Core Value

An AI agent can autonomously determine the structure of an unknown organic compound from its NMR spectra, with a multi-agent architecture that prevents unproductive loops and keeps the elucidation on track.

## Current Milestone: v10.0 Automatic NUS 2D Reconstruction — IN PROGRESS 🚧

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

**Version:** v9.3 shipped 2026-07-12 (v9.2 2026-07-07, v9.1 2026-06-29, v9.0 2026-06-17)

**What shipped in v9.3 (CASE Web-View Stage 2, phases 93–96):** The read-only dashboard grew into a full spectral-inspection suite — a persistent 4-tab bar (Run Log / 1D / 2D Spectra / Tables) over a markdown-rendered run log (hand-rolled XSS-safe DOM renderer), data tables (¹³C signals, HSQC/HMBC/COSY correlations with HMBC flag colours, LSD constraint inventory), and **real rendered 1D + 2D NMR spectra with the picked peaks overlaid** (reversed ppm axes; HMBC flag-coloured markers; COSY diagonal). New `tables.py` + `spectra.py` routers; `.run_manifest.json` raw-Bruker-path wiring; matplotlib in the `[webview]` extra (OO-API/lazy, WV-08, base CLI dependency-free); 2D block-max decimation + MAD contour levels + mtime PNG cache. Validation-only across CASE1–9 (no new milestone UAT).
**Codebase:** Python package (`src/lucy_ng/`) + `src/lucy_ng/webview/` (optional `[webview]` extra), test suite **1174 tests** at v9.2 close
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
*Last updated: 2026-07-12 — Phase 97 (Backend Integration + Params/Schedule) COMPLETE & verified (VERIFICATION passed, 9/9 must-haves, NUS-01..05 validated). Shipped `lucy nus check/params/schedule`, `NusAcquisitionParams`/`NusSchedule` models, and `NmrPipeSmileBackend` detection; core CLI dependency-free behind an empty `[nus]` extra; validated against real C20H32O2 exp2/3/4 fixtures. Next: Phase 98 (reconstruction + processing).*

*Prior: 2026-07-12 shipped v9.3 CASE Web-View Stage 2 (phases 93–96, LOG-01/TAB-01/TBL-01..03/SP1-01/SP2-01/SP-02) — archived to `milestones/v9.3-ROADMAP.md` + `milestones/v9.3-REQUIREMENTS.md`, tagged `v9.3`. Delivered the full spectral-inspection suite: formatted run log + tab framework, data tables, and real rendered 1D + 2D NMR spectra with picked peaks overlaid.*
