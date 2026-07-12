# Project Milestones: lucy-ng

## v9.3 CASE Web-View Stage 2 (Shipped: 2026-07-12)

**Phases completed:** 4 phases, 16 plans, 23 tasks

**Delivered:** The read-only CASE web-view dashboard grew from a run-status monitor into a full spectral-inspection suite — a persistent tab bar over a formatted run log, data tables, and real rendered 1D + 2D NMR spectra with picked peaks overlaid for visual QC.

**Key accomplishments:**

- **Phase 93 — Formatted log + tab framework:** persistent 4-tab bar (Run Log / 1D / 2D Spectra / Tables) with no page reload; CASE-PROGRESS.md rendered as formatted markdown via a hand-rolled createElement/textContent DOM renderer (headings/bold/pipe-tables/code) that preserves the v9.2 XSS discipline (never `innerHTML` of server content); `webview.js` extracted to a served static asset.
- **Phase 94 — Data tables:** `tables.py` router with 5 never-500 GET routes rendering the ¹³C signal table, HSQC/HMBC/COSY correlation tables (HMBC flag colour-coding), and the LSD constraint inventory parsed from the latest `compound.lsd`; each panel degrades to a "waiting for data" state during a live run.
- **Phase 95 — 1D real spectra:** `spectra.py` router renders real ¹³C/¹H Bruker traces (BrukerReader + nmrglue + matplotlib Agg) on a reversed ppm axis with picked peaks overlaid; introduced the `.run_manifest.json` raw-data path wiring (written by `case.md` at run-start) and the matplotlib `[webview]`-extra + lazy-import discipline (WV-08).
- **Phase 96 — 2D real spectra:** three `/api/spectra/2d/{hsqc,hmbc,cosy}` routes render real HSQC/HMBC/COSY contour plots with cross-peak overlays (open circles; HMBC flag colours; COSY diagonal), block-max decimation to ≤512×512, MAD-threshold geometric contour levels, and an mtime-keyed PNG cache; three stacked `<img>` populate the 2D tab.
- **Cross-cutting quality:** matplotlib OO-API only (never pyplot), lazy imports confined to `make_router()`, base `lucy` install imports without the `[webview]` extra; "dumb server, never-500, graceful unavailable" contract across every tab. Two defects were caught and fixed at Phase 96 verification — a 2D F1/y-axis inversion (found via the manual browser checkpoint + real-CASE1 render) and a placeholder-figsize layout-jump (code review CR-01).

**Stats:** ~107 commits, 72 files changed (+16,988 / −287). Validation-only across CASE1–9 (no new milestone UAT).

**Known deferred items at close:** 2 pending todos, both outside v9.3 webview scope (CASE4 azulene-regiochemistry enumeration gap [skill]; ranking-tests hard-fail without hosegen [tests]) — see STATE.md § Deferred Items.

---

## v9.2 CASE Web-View (Shipped: 2026-07-07)

**Delivered:** A read-only web dashboard that makes a CASE run observable live and after the fact — three auto-refreshing widgets (run status, top RDKit-rendered candidate structures with MAE/rank, scrollable run log), auto-launched by the orchestrator and kept alive past the run. Ships as an optional extra (`lucy-ng[webview]`); the core CLI stays dependency-free. Live-validated on a CASE1 run (ibuprofen solved, Rank 1 MAE 0.25).

**Phases completed:** 3 phases (90–92), 10 plans, 17 tasks. All 8 requirements (WV-01..08) met.

**Key accomplishments:**

- **Phase 90 — server, CLI, packaging:** `lucy webview serve/stop/status` (FastAPI/uvicorn) with a PID-aware `.webview.json` lifecycle (`WebviewState` Pydantic v2 model), idempotent start, detached process (`start_new_session=True`) so it outlives the caller; shipped as the optional `lucy-ng[webview]` extra with the core CLI kept dependency-free (WV-08 import safety verified).
- **Phase 91 — endpoints + depictions + frontend:** four JSON/SVG endpoints on `create_app()` (`/api/status`, `/api/log`, `/api/structures`, `/api/structure/{i}.svg`) with graceful degradation (missing/partial/mid-write files → HTTP 200 "waiting", never 500; out-of-range → 404; malformed SMILES → placeholder); clean RDKit SVG depictions (no atom indices); single-file vanilla-JS dashboard (3 s polling, `textContent`-only, no build step) shipped in the wheel via hatch artifacts.
- **Phase 92 — orchestrator integration:** `case.md` auto-launches the dashboard at run-start (before the first `[BEGIN]`), prints the URL + manual `lucy webview stop` hint, and leaves the server running past `terminate_team`; browser is not auto-opened by design.
- **Post-code-review hardening (Phase 91):** three verified correctness fixes — null-rank no longer drops the ranked tier, `render_smiles` can never 500 on a kekulize failure, and the frontend no longer re-fetches SVGs every tick for empty-SMILES tiles — each locked by a regression test.
- **Live-run refinement (Phase 92):** the CASE-PROGRESS.md header is now written at run-start (compound path, formula, dashboard URL) so the dashboard Run Log fills from t=0 instead of staying empty until `[SETUP-COMPLETE]`.

**Verification:** every phase `VERIFICATION.md` passed; phases 91 and 92 additionally live-validated in-browser by the user. Full test suite green (1174 collected).

**Deferred to Stage 2 (v9.3):** formatted run log (markdown rendering) + rendered spectra tabs + data tables — see STATE.md § Deferred Items.

---

## v9.1 CASE Final-Answer Correctness & Verification Gates (Shipped: 2026-06-29)

**Delivered:** Closed three "clean-but-wrong" CASE failure classes with verification gates, then proved the fixes hold end-to-end on independent blind CASE runs.

**Phases completed:** 4 phases (86–89), 9 plans. Timeline: 2026-06-23 → 2026-06-29 (~52 commits). Tests: full suite 1131 passing.

**Key accomplishments:**

- **RANK (86) — ranker path unification:** `lucy lsd rank` and `lucy predict c13` now share one DB-first prediction path (`resolve_c13_predictor` / `SolutionRanker`), so ranking uses the same backend as prediction — fixing the rank-scoring defect (ibuprofen MAE 2.23→0.24).
- **IDENT (87) — tool-derived identity gate:** new installed `lucy identify` CLI (shared deterministic core in `src/lucy_ng/identity.py`, reachable from any CASE data dir) derives identity from the solved SMILES; the analyst marks unconfirmed names `(tentative, unverified)`; a post-solution devils-advocate `G-IDENT` gate independently cross-checks name↔structure — stopping parametric naming hallucination (the CASE4/CASE5 mode).
- **MULT (88) — aliphatic multiplicity coverage:** when multiplicity is not hard-determinable, the nmr-chemist emits `[MULTIPLICITY-AMBIGUOUS]` and the lsd-engineer searches EACH viable whole-molecule family as its own fully-constrained LSD run (deduped union ranking); a deterministic MAE-independent pre-accept `coverage_gate` (SEARCHED-not-RANKED) + a binding devils-advocate `G-MULT` flag close the CASE4 wrong-class exclusion. New `lucy pick hsqc multiplicity_edited` detector underpins the trigger.
- **Blind-UAT gate (89) — independent end-to-end validation:** five blind CASE runs on fresh blind instances, each RDKit-verified by InChIKey: CASE5 indigo, CASE6 citronellol, CASE7 virgiline, CASE8 eugenol all PASS; CASE4 chamazulene v9.1-PASS (conditional). Live-confirmed: `lucy identify` reachable + all three verdict branches; `G-IDENT` both branches ([PASSED]/[FLAGGED]); MULT machinery fires-when-ambiguous / dormant-when-firm.

**Known deferred items at close:** 1 (CASE4 azulene-regiochemistry-enumeration gap — a NEW 4th defect class surfaced by UAT-01; the exact chamazulene regiochemistry remains unreachable while the di-methyl-ethyl class is now searched. Carried to a future milestone. See STATE.md Deferred Items + todo `2026-06-25-case4-azulene-regiochemistry-enumeration-gap`).

---

## v9.0 CASE Reliability & Skill Consolidation (Shipped: 2026-06-17)

**Delivered:** Made the CASE pipeline actually work end-to-end via the intended mechanism (no manual bypass) — validated by a blind UAT in which CASE9 (UAT-04) was solved and CASE1 (UAT-03) reached a CLEAN EMERGENT PASS on Opus 4.8, with the benzene ring emerging from constraints rather than forced ring-BONDs.

**Phases completed:** 14 phases (72–85), 34 plans, 41 tasks

**Key accomplishments:**

- **Design re-validation (Phase 72):** answered the 4 open v8.0 design questions — single solver path, native-only constraint translation, emergent aromatic ring (D-04).
- **Solution plumbing fixed (73, 77):** `lucy lsd run` / outlsd conversion produces real ranked SMILES and fails loud on error; deterministic cross-ring COSY pair derivation (`lucy detect aromatic-cosy`) so the ring emerges without manual atom-index reasoning.
- **Native-only constraints + preservation (74, 75):** SYME→BOND/COSY and DEFF NOT→DEFF F/FEXP across all paths; full constraint set carried to every permutation; all agent skills + devils-advocate gates (G5–G8) synchronized to actual LSD-3.4.9 behavior.
- **Peak-picking integrity (81 FIX-08, 85 FIX-12):** SNR-floor for 13C (weak ester carbonyl no longer masked) and HMBC (ring-diagnostic 3J-meta cross-peaks retained) + overcount guard — the two upstream defects that had excluded the correct structures.
- **Constraint-hardness guard (83 FIX-10):** an uncertain structural inference can no longer become a hard, solution-excluding LSD constraint.
- **Blind-UAT skill hygiene (82 FIX-09):** runtime CASE skills decontaminated of answer-key/dev-meta so a fresh instance learns nothing about the test.
- **Validation (UAT-03/04):** CASE9 solved (`CC(C)OC(=O)c1ccc(C(C)O)cc1`, MAE 1.17) and CASE1 a clean emergent pass (ibuprofen rank 1, exact InChIKey, 0 ring-BONDs/SKEL/SYME/DEFF-NOT). A substantial earlier-failure root cause was model-driven (a stale `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` override, now `inherit`).

**Stats:**

- 14 phases (72–85), 34 plans, 41 tasks
- Git range: `0113035` (v9.0 roadmap) → `207fe11` (ship-ready)
- Test suite: 1081 passing at close (Phase 84)

**Known deferred items at close:** 12 (see STATE.md Deferred Items) — all superseded, older-milestone artifacts, or the intentional `lucy lsd rank` scoring-defect todo carried to v9.1.

---

## v7.0 Statistical 4J Detection (ABANDONED: 2026-03-12)

**Delivered:** Nothing — milestone abandoned after calibration revealed fundamental non-viability of statistical approach. All code reverted (commit `ee797e0`).

**Phases:** 59-64 (6 phases planned, 5 executed, all code reverted)

**Post-mortem finding:** After generating 3.78M coupling_path_stats entries from 895K compounds, calibration showed a 100% false positive rate. The `p_long_range = j4 + j5_plus` metric does not discriminate because j5_plus (5+ bond paths) dominates universally (67-90%) for ALL shift pairs. No threshold combination produces correct behavior.

**Root cause:** The generator records all (carbon, H-carbon) atom pair distances in each molecule, but most pairs are 5+ bonds apart regardless of chemical environment. Aggregate statistics cannot distinguish "this HMBC correlation is likely 4J" from "these atoms happen to be far apart in most molecules."

**Decision:** 4J problem will be addressed differently — pyLSD integration (constraint solver explores 4J possibilities directly) rather than statistical pre-filtering.

**Stats:**

- 6 phases, 9 plans executed then reverted, 0 requirements met
- ~3,600 lines written and deleted
- 3 days (2026-03-10 → 2026-03-12)
- Net code change: 0 lines (full revert)

**Git range:** `23cbf91` → `ee797e0` (revert)

**Calibration data:** `.planning/phases/63-full-generation-run/calibration-results.md`

**What's next:** pyLSD integration for 4J handling, multi-compound UAT

---

## v6.0 Skill Quality Overhaul (Shipped: 2026-03-10)

**Delivered:** Comprehensive quality overhaul of all skill and agent definitions — factored oversized orchestrator, added 4J HMBC coupling awareness, optimized skill triggering, archived legacy agent, improved error handling, and added smoke test infrastructure.

**Phases completed:** 55-58 (7 plans total)

**Key accomplishments:**

- Factored case.md orchestrator from 1,093 to 497 lines with 3 extracted reference files (progress-format, loop-patterns, advisory-templates)
- Added 4J HMBC coupling awareness: nmr-chemist flags, lsd-engineer defers, solution-analyst verifies via 13C prediction
- Orchestrator message validation with required fields enforcement and RESEND-REQUIRED protocol
- Optimized all 5 skill descriptions with natural-language trigger phrases and routing decision tree
- Added dry-run confirmation gate to sanitise, HOSE miss recovery to predict, 0-match guidance to dereplicate
- Version compatibility check in status skill and smoke test mode (--smoke-test) in CASE orchestrator

**Stats:**

- 4 phases, 7 plans, 20 commits
- All changes to .md skill/agent files (no Python code)
- 1 day (2026-03-10)

**Git range:** `90f82fb` → `77d71a8`

**Tech debt:** None. Two minor integration gaps noted in audit (INTL-03 aromatic expectation relay, INTL-04 4J status field validation) — cosmetic, no behavioral impact.

**What's next:** Statistical 4J HMBC coupling detection, multi-compound UAT

---

## v3.0 Statistical Detection (Shipped: 2026-02-16)

**Delivered:** Data-driven statistical detection replacing agent guesswork in structure elucidation — hybridisation, neighbourhood, HHB detection from 7.9M HOSE statistics, two-tier ranking preventing MAE hallucinations, badlist strained ring exclusion, and full CASE agent integration with chemistry-first hierarchy.

**Phases completed:** 34-40 (21 plans total)

**Key accomplishments:**

- Hybridisation detection: sp1/sp2/sp3 state from HOSE database frequency distributions per 13C shift
- Neighbourhood detection: forbidden (<1%) and mandatory (>95%) bond partners from HOSE sphere 1
- Hetero-hetero bond detection: formula-level bond pair frequencies from bond_pair_stats table
- Signal grouping: complete linkage clustering identifies close 13C shifts for combinatorial LSD atom exchange
- Two-tier ranking: match count priority prevents MAE hallucination; badlist excludes 3/4-membered strained rings
- Agent integration: CASE agent uses statistical detection CLI with chemistry-first hierarchy (DEPT > HSQC > HMBC > shifts > detection)
- Database regenerated with v6 schema (7.89M HOSE stats, 8h39m), 762 tests passing, live UAT: ibuprofen rank #1 (MAE=2.23)

**Stats:**

- 7 phases, 21 plans, 51 commits
- 88 files changed, +19,700 / -214 lines
- 18,855 lines Python, 762 tests
- 2 days (2026-02-11 → 2026-02-12)

**Git range:** `feat(34-01)` → `docs(40-03)`

**Tech debt:** Agent behavior gaps (DEFF NOT dropped across iterations, signal grouping detected but not applied as SYME, grouped notation lost) — prompting issues, not code bugs. Deferred to next milestone.

**What's next:** Agent workflow refinement, COSY integration, fragment library

---

## v2.1 Working Multi-Agent CASE (Shipped: 2026-02-09)

**Delivered:** Working multi-agent orchestration replacing v2.0's paper-only architecture — sub-command skills, real agent spawning, progress monitoring, loop detection, advisory intervention, diagnostic specialist delegation, AI-driven sanitisation.

**Phases completed:** 27-33 (9 plans total)

**Key accomplishments:**

- Sub-command skills: /lucy-ng:case, /lucy-ng:sanitise, /lucy-ng:dereplicate, /lucy-ng:predict, /lucy-ng:status
- CASE orchestrator that spawns autonomous CASE agent via Task(), monitors CASE-PROGRESS.md, detects 4 loop patterns
- Autonomous CASE agent with 613 lines of inlined NMR/LSD knowledge
- Diagnostic specialist delegation after 2 failed basic interventions
- AI-driven dataset sanitisation (no CLI — requires AI semantic reasoning)
- First live CASE test: Ibuprofen identified (rank #1) but with wrong topology (cyclohexadiene, not aromatic)

**Stats:**

- 7 phases, 9 plans
- 1 day from start to shipped (2026-02-08 → 2026-02-09)

**What's next:** v3.0 Statistical Detection — data-driven constraints to replace agent guesswork

---

## v2.0 Robust Multi-Agent CASE (Shipped: 2026-02-08)

**Delivered:** AI-first skill architecture with thin tool wrappers, supervisor/diagnostic specialist agents (paper definitions), comprehensive CASE workflow knowledge (3,780 lines)

**Phases completed:** 20-26 (16 plans total)

**Key accomplishments:**

- System audit: all 16 MCP tools + 7 CLI groups classified
- CLAUDE.md split into project-level + SKILL.md (1,079 lines) + supervisor SKILL.md + diagnostic SKILL.md (1,874 lines)
- MCP server removed entirely — CLI-only architecture
- Incremental HMBC strategy, error tolerance, confidence scoring encoded in skills
- Supervisor and diagnostic specialist agent definitions (paper architecture)
- Thin CLI tools validated with Ibuprofen de novo CASE

**Stats:**

- 7 phases, 16 plans
- 3 weeks (2026-01-18 → 2026-02-08)

---

## v1.2 HOSE Database Prediction (Shipped: 2026-01-18)

**Delivered:** Database-backed 13C shift prediction using 7.9M HOSE statistics from 895K compounds, enabling accurate solution ranking with O(1) lookups

**Phases completed:** 16-19 (4 plans total)

**Key accomplishments:**

- hose_stats table with 7.9M pre-computed statistics (mean, std, count) per HOSE code at radii 1-6
- HOSELookupProtocol for interchangeable prediction backends
- DatabaseHOSELookup adapter for O(1) database queries
- C13Predictor with dual-backend support (database preferred, JSON table fallback)
- ResumableHOSEStatsGenerator with checkpoint/resume for large dataset processing
- CLI `--db` option with intelligent auto-detection
- MCP `get_hose_stats_info` tool for agent capability checking
- Single database now powers both dereplication AND 13C prediction

**Stats:**

- 17,552 lines of Python
- 642 tests
- 4 phases, 4 plans, 16 tasks
- 3 days from v1.1 to v1.2 (2026-01-15 → 2026-01-18)

**Git range:** `feat(16-01)` → `feat(19-01)`

---

## v1.1 Database-Backed Dereplication (Shipped: 2026-01-15)

**Delivered:** SQLite database backend enabling ~100x faster dereplication against 928K compounds (COCONUT + NMRShiftDB)

**Phases completed:** 11-15 (5 plans total)

**Key accomplishments:**

- SQLite database schema for storing 928K compounds with formula-indexed queries
- Database importer for batch loading from NMRShiftDB and COCONUT SDF files
- DatabaseQueryService API for formula-based compound lookup
- CLI auto-detection of database with `LUCY_DATABASE` env var support
- MCP tool integration with `database_type` field for agent transparency
- ~100x faster dereplication vs. SD file scanning

**Stats:**

- 42 files created/modified
- 11,196 lines of Python
- 5 phases, 5 plans
- 7 days from v1.0 to v1.1 (2026-01-08 → 2026-01-15)

**Git range:** `feat(11-01)` → `feat(15-01)`

---

## v1.0 Core CASE Pipeline (Shipped: 2026-01-12)

**Delivered:** Complete Computer-Assisted Structure Elucidation pipeline with 13 MCP tools, 7 CLI command groups, and LSD solver integration

**Phases completed:** 1-10 (12 plans total, including decimal phases 2.1, 4.1, 4.2, 5.1, 5.2)

**Key accomplishments:**

- Bruker 1D/2D NMR spectrum reading (1H, 13C, DEPT, HSQC, HMBC, COSY)
- DEPT-guided adaptive HSQC peak picking with multiplicity detection
- HMBC-guided peak picking to filter noise correlations
- Symmetry detection for molecular equivalence handling
- LSD solver integration with constraint generation and solution parsing
- HOSE-based 13C shift prediction for solution ranking
- NMRXiv dataset fetching for research evaluation
- 13 MCP tools for Claude agent integration
- 7 CLI command groups for scripting and testing

**Stats:**

- 100+ files created
- ~8,000 lines of Python (before v1.1)
- 12 phases (10 integer + 5 decimal insertions), 12 plans
- 5 days from start to v1.0 (2026-01-08 → 2026-01-12)

**Git range:** `feat(01-01)` → `feat(10-01)`

---

## v4.0 Team-Based CASE (Shipped: 2026-02-18)

**Delivered:** 5-agent collaborative CASE team replacing monolithic agent — coordinator, nmr-chemist, lsd-engineer, solution-analyst, devils-advocate with real-time peer review, constraint inventory persistence, pre-run validation gates, aromatic ring awareness, and all v3.0 constraint-loss bugs fixed.

**Phases completed:** 41-48 + 46.1 (21 plans total)

**Key accomplishments:**

- 5-agent CASE team: orchestrator spawns coordinator, nmr-chemist, lsd-engineer, solution-analyst, devils-advocate via TeamCreate with 3,460 lines of distributed agent/skill definitions
- Constraint inventory system: JSON-based tracking in LSD file headers prevents DEFF NOT, SYME, grouped notation, and detection result loss across iterations
- Devils-advocate pre-run validation: three-check inventory reconciliation (accuracy, regression, content) gates every LSD solver run
- Aromatic ring awareness: nmr-chemist flags aromatic expectation from sp2 clusters, solution-analyst verifies `has_aromatic_ring` on solutions, recommends 4J HMBC removal when mismatch detected
- Coordinator-as-sole-writer pattern: agents post via SendMessage, coordinator writes CASE-PROGRESS.md — prevents file corruption from concurrent writes
- All 5 v3.0 constraint-loss bugs verified fixed in UAT: DEFF NOT persistence, SYME applied, grouped notation preserved, PROP/BOND used, detection constraints translated

**Stats:**

- 9 phases (8 + 46.1), 21 plans, 48 commits
- 3,460 lines agent/skill definitions
- 18,963 lines Python, 768 tests
- 2 days (2026-02-17 → 2026-02-18)

**Git range:** `719f158` → `9055a62`

**Tech debt:** 3 WARNING-level integration gaps (write_progress aromatic field templates, lsd-engineer step 8 message source wording). Accepted as non-blocking — no behavioral impact, narrative documentation gaps only.

**What's next:** Statistical 4J coupling detection, multi-compound UAT, COSY integration

---

## v5.0 Fragment Library (Shipped: 2026-02-21)

**Delivered:** Substructure-subspectrum correlation (SSC) fragment library with 2.4M fragments from 928K compounds, two-phase search engine, DEFF/FEXP goodlist injection validated against LSD solver, and full CASE agent team integration — the last major feature gap for Sherlock parity.

**Phases completed:** 49-54 (12 plans total)

**Key accomplishments:**

- Fragment database: 2,385,146 SSCs extracted from 928K compounds via BFS sphere fragmentation with bond-preservation rules (605 MB, schema v7, checkpointed 3.5-hour pipeline)
- Fragment search engine: 256-bit fingerprint pre-screening + greedy fine matching (DEV 2 ppm, AVGDEV 1 ppm), ranked by atom count then deviation, sub-second search on 2.4M SSCs
- DEFF/FEXP goodlist: SMILES-to-SSTR/LINK fragment file conversion validated with LSD smoke test (toluene: 4 solutions → 1 with benzene ring goodlist)
- Agent integration: lsd-engineer searches fragments per iteration, devils-advocate verifies fragment files, orchestrator logs fragment status per iteration
- Self-search recall: 100% on 100-compound sample (fingerprint indexing validated)
- Full test suite: 867 tests (860 passing, 7 skipped), 20,974 lines Python

**Stats:**

- 6 phases, 12 plans, 47 commits
- 61 files changed, +13,861 / -2,338 lines
- 20,974 lines Python, 867 tests
- 3 days (2026-02-19 → 2026-02-21)

**Git range:** `feat(49-01)` → `docs(54)`

**Known gaps:** VALD-01 (multi-compound CASE comparison) deferred — all 6 local test compounds have 4J HMBC coupling risk, making controlled A/B fragment comparison unreliable. Self-search validation (VALD-02) PASSED.

**What's next:** Statistical 4J HMBC detection, non-aromatic test compounds for fragment UAT, COSY integration

---
