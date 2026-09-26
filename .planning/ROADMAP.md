# lucy-ng Roadmap

## Milestones

- [v1.0 Core CASE Pipeline](milestones/v1.0-ROADMAP.md) - Phases 1-10 (shipped 2026-01-12)
- [v1.1 Database-Backed Dereplication](milestones/v1.1-ROADMAP.md) - Phases 11-15 (shipped 2026-01-15)
- [v1.2 HOSE Database Prediction](milestones/v1.2-ROADMAP.md) - Phases 16-19 (shipped 2026-01-18)
- **v2.0 Robust Multi-Agent CASE** - Phases 20-26 (shipped 2026-02-08)
- **v2.1 Working Multi-Agent CASE** - Phases 27-33 (shipped 2026-02-09)
- [v3.0 Statistical Detection](milestones/v3.0-ROADMAP.md) - Phases 34-40 (shipped 2026-02-16)
- [v4.0 Team-Based CASE](milestones/v4.0-ROADMAP.md) - Phases 41-48 (shipped 2026-02-18)
- [v5.0 Fragment Library](milestones/v5.0-ROADMAP.md) - Phases 49-54 (shipped 2026-02-21)
- [v6.0 Skill Quality Overhaul](milestones/v6.0-ROADMAP.md) - Phases 55-58 (shipped 2026-03-10)
- [v7.0 Statistical 4J Detection](milestones/v7.0-ROADMAP.md) - Phases 59-64 (ABANDONED 2026-03-12)
- **v8.0 pyLSD Integration** - Phases 65-71 (superseded by v9.0 before UAT passed)
- ✅ [v9.0 CASE Reliability & Skill Consolidation](milestones/v9.0-ROADMAP.md) - Phases 72-85 (shipped 2026-06-17)
- ✅ [v9.1 CASE Final-Answer Correctness & Verification Gates](milestones/v9.1-ROADMAP.md) - Phases 86-89 (shipped 2026-06-29)
- ✅ [v9.2 CASE Web-View](milestones/v9.2-ROADMAP.md) - Phases 90-92 (shipped 2026-07-07)
- ✅ [v9.3 CASE Web-View Stage 2](milestones/v9.3-ROADMAP.md) - Phases 93-96 (shipped 2026-07-12)
- 🟡 **v10.0 Automatic NUS 2D Reconstruction** - Phases 97-100 (PARTIAL, paused 2026-07-20 — PORT shipped, VAL blocked by SMILE memory abort, RECON-F1 tracked)
- 🟡 [v10.1 JCAMP-DX 2D Ingestion](milestones/v10.1-ROADMAP.md) - Phases 101-103 (PARTIAL, closed 2026-07-28 — reader + `lucy jcamp` shipped, JVAL real-data validation not achieved; JVAL-F2/JVAL-F3 tracked)
- 🚧 **v11.0 AILSA Rename** - Phases 104-107 (in progress, started 2026-09-26 — Phases 106-107 gated on the Opus-5 baseline re-run finishing, expected after the 2026-09-29 quota reset)

---

**v9.2 outcome:** A read-only web dashboard makes a CASE run observable live and after the fact —
`lucy webview serve/stop/status`, four JSON/SVG endpoints with graceful degradation, RDKit SVG
depictions, single-file vanilla-JS dashboard, auto-launched by `case.md`. Live-validated on CASE1
(ibuprofen, Rank 1 MAE 0.25). Full archive: [`milestones/v9.2-ROADMAP.md`](milestones/v9.2-ROADMAP.md).

---

**v9.3 outcome:** The read-only CASE web-view grew from a status monitor into a full
spectral-inspection suite — a persistent 4-tab bar (Run Log / 1D / 2D Spectra / Tables) over a
markdown-rendered run log, data tables (¹³C signals, HSQC/HMBC/COSY correlations, LSD constraint
inventory), and **real rendered 1D + 2D NMR spectra with the picked peaks overlaid** for visual
peak-picking QC. New `tables.py` + `spectra.py` routers; `.run_manifest.json` raw-Bruker-path
wiring; matplotlib in the `[webview]` extra (OO-API/lazy/WV-08); block-max decimation + MAD
contour levels + mtime PNG cache for 2D. Full archive:
[`milestones/v9.3-ROADMAP.md`](milestones/v9.3-ROADMAP.md).

---

## v10.0 Automatic NUS 2D Reconstruction

**Goal:** Lucy-ng reconstructs non-uniformly-sampled (NUS) 2D NMR spectra fully automatically and
without any GUI step — from Bruker `ser`+`nuslist` through a real compressed-sensing / IST / SMILE
reconstruction to clean JSON peak lists — so that CASE runs on NUS data get reliable
HSQC/HMBC/COSY connectivity. Backend locked to NMRPipe+SMILE (native macOS Apple Silicon + Linux,
100% CLI/headless); Windows is an accepted, documented WSL2/VM gap. Builds a new `nus/` package
(sibling of `lsd/`, `webview/`) that runs as a pre-CASE "dumb tool" — zero changes to `case.md` or
the 5-agent team.

### Phases

- [x] **Phase 97: Backend Integration + Params/Schedule** — `lucy nus check` backend detection (LSD precedent) + pure-Python `NusAcquisitionParams`/`NusSchedule` parsing, fixture-tested against real C20H32O2 data (completed 2026-07-12)
- [x] **Phase 98: Reconstruction + Processing** — real NMRPipe+SMILE subprocess chain (bruk2pipe → nusExpand.tcl → SMILE → FT/phase/baseline), FnMODE-aware, fail-loud wrapper (completed 2026-07-13)
- [x] **Phase 99: Peak-Pick Bridge + QC Gate + CLI** — bridge to existing `PeakPicker2D`, mandatory automated QC gate (PASS/PARTIAL/FAIL) blocking CASE handoff on FAIL, full `lucy nus` CLI group (completed 2026-07-16)
- [~] **Phase 100: Cross-Platform Hardening + End-to-End Validation** — **PARTIAL (closed 2026-07-20).** PORT-01/PORT-02 delivered (platform preflight + portability matrix, both verified). **VAL-01/VAL-02 NOT achieved** — honest stop per CONTEXT decision D-04: SMILE aborts with a ~5–7 GB `Cannot allocate memory` on this host and the bounded tuning budget is exhausted; success criteria 3 and 4 are therefore NOT true. Tracked next step: **RECON-F1**. See the limitation note under *Phase Details* + `phases/100-.../VALIDATION.md`.

### Phase Details

#### Phase 97: Backend Integration + Params/Schedule

**Goal**: Lucy-ng can detect the NUS reconstruction backend on the local machine and correctly parse any NUS experiment's Bruker acquisition parameters and sampling schedule, ready to drive reconstruction.
**Depends on**: Phase 96 (v9.3 shipped — base codebase for the new `nus/` package)
**Requirements**: NUS-01, NUS-02, NUS-03, NUS-04, NUS-05
**Success Criteria** (what must be TRUE):
  1. `lucy nus check` correctly reports NMRPipe+SMILE availability on PATH and fails loud with install guidance when missing — mirroring `lucy lsd check`; the backend is never a core `pyproject.toml` dependency.
  2. `lucy nus params <expdir> --format json` extracts a validated `NusAcquisitionParams` model (SFO1, SW_h, TD per dimension, FnMODE, GRPDLY/DECIM, byte order/dtype) from `acqus`/`acqu2s`, read per-experiment and never hard-coded, verified against the real C20H32O2 exp2/exp3/exp4 fixtures.
  3. `lucy nus schedule <expdir> --format json` builds the sampling schedule from the Bruker `nuslist` with correct 0-based, acquisition-order-preserved indexing (never sorted/regenerated), and the hard `n_sampled == len(nuslist)` assertion derived from FnMODE passes for all three real experiments (FnMODE 1 COSY, FnMODE 6 HSQC/HMBC).
  4. A clean `pip install lucy-ng` (core, no extras) still succeeds and the CLI imports without error — any genuinely pip-installable NUS pieces live behind an optional `[nus]` extra with lazy imports, following the `[webview]` precedent.
**Plans**: 5 plans (3 waves)
- [x] 97-01-PLAN.md — Fixtures + NusAcquisitionParams/NusSchedule Pydantic contracts + package skeleton (wave 1)
- [x] 97-02-PLAN.md — nus/params.py acqus/acqu2s/procs/proc2s extraction (NUS-02, wave 2)
- [x] 97-03-PLAN.md — nus/schedule.py FnMODE-derived hard-fail assertion (NUS-03, wave 2)
- [x] 97-04-PLAN.md — NmrPipeSmileBackend detection + SMILE capability probe + registry (NUS-01, wave 2)
- [x] 97-05-PLAN.md — lucy nus CLI group + registration + [nus] extra + import-safety (NUS-01/04/05, wave 3)

#### Phase 98: Reconstruction + Processing

**Goal**: Lucy-ng runs the full external reconstruction pipeline — Bruker→NMRPipe conversion, NUS expansion, SMILE reconstruction, and post-processing — fully automatically with no GUI step, for any NUS 2D experiment.
**Depends on**: Phase 97
**Requirements**: RECON-01, RECON-02, RECON-03, RECON-04, RECON-05
**Success Criteria** (what must be TRUE):
  1. `lucy nus reconstruct <expdir>` runs the whole chain (`bruk2pipe` → `nusExpand.tcl` → SMILE → FT/phase/baseline) with no GUI step or manual intervention, producing a processed 2D spectrum for all three C20H32O2 experiments (exp2 COSY, exp3 HSQC, exp4 HMBC).
  2. Direct-dimension-first (F2 before F1) processing order is enforced as a hard pipeline gate — an out-of-order attempt raises before any reconstruction runs — and output ppm axes are reversed and calibrated to match the reliable 1D reference.
  3. The pipeline is FnMODE-aware from one entrypoint: echo-antiecho phase-sensitive processing for HSQC/HMBC vs QF magnitude-mode for COSY, correct at both 25% and 33% sampling densities.
  4. Every external-tool subprocess invocation runs through a fail-loud wrapper checking both exit code and output-file non-emptiness; a deliberately truncated/empty intermediate aborts the pipeline with a clear error instead of silently passing through (guards against csh-piped NMRPipe stages that don't reliably propagate exit codes).
  5. `lucy nus reconstruct` exposes iteration count, threshold, and virtual-echo toggle as CLI flags with sane defaults, and stopping is convergence/residual-based rather than a fixed iteration count alone.
**Plans**: 6 plans (5 waves)
- [x] 98-01-PLAN.md — Nyquist Wave 0 test scaffolding: tests/nus/ package + conftest (run_stage mock seam, fake intermediates) + one RED-by-skip stub per RECON requirement (wave 1)
- [x] 98-02-PLAN.md — Fail-loud run_stage() wrapper (RECON-04) + FnMODE recipe/ordering helper (RECON-03) + NusReconstructionResult model (wave 2)
- [x] 98-03-PLAN.md — NmrPipeSmileBackend.reconstruct() chain: bruk2pipe/nusExpand.tcl/SMILE, FnMODE-branched order, nus_td grid, GRPDLY, convergence knobs (RECON-01/03, wave 3)
- [x] 98-04-PLAN.md — nus/postprocess.py: F2-first FT/apod/phase/baseline stage + reversed 1D-calibrated ppm axes (RECON-02, wave 3)
- [x] 98-05-PLAN.md — NusRunner.reconstruct orchestration + F2-before-F1 hard gate + skipif end-to-end integration test (RECON-01/02, wave 4)
- [x] 98-06-PLAN.md — lucy nus reconstruct CLI command + iteration/threshold/virtual-echo flags + import-safety companion edit (RECON-05, wave 5)

#### Phase 99: Peak-Pick Bridge + QC Gate + CLI

**Goal**: Reconstructed 2D spectra are automatically peak-picked into the existing JSON schema, and every reconstruction is gated by a mandatory, automated quality check before the CASE pipeline is allowed to consume it.
**Depends on**: Phase 98
**Requirements**: PICK-01, PICK-02, PICK-03, QC-01, QC-02, QC-03
**Success Criteria** (what must be TRUE):
  1. `lucy nus pipeline <expdir>` runs the whole chain end-to-end (params → schedule → reconstruct → process → peak-pick → QC) as one reusable command for any NUS CASE run, producing `analysis/nmr_peaks/*.json` byte-for-byte schema-identical to today's manual/GUI-derived output (built via a direct `Spectrum2D` → existing `PeakPicker2D` call, not a new picker).
  2. The QC gate emits a machine-readable PASS/PARTIAL/FAIL report cross-checking every reconstructed correlation against the trusted 1D shift data (protonated-carbon HSQC coverage, quaternary-carbon exclusion, edited-sign self-consistency, COSY diagonal symmetry, ppm calibration, signal-to-ridge ratio) with no human in the loop.
  3. Running the QC gate against the existing known-bad t1-ridge home-IST peak lists reports FAIL, and against a clean reconstruction reports PASS — proving it discriminates (regression floor, QC-02).
  4. When the QC gate reports FAIL, the CASE handoff refuses to start — extending the v9.0 constraint-hardness guard (FIX-10) to reconstruction-derived peaks so a fabricated cross-peak can never silently become a hard LSD constraint.
  5. Every `lucy nus` subcommand supports `--format json`, and emitted peak JSON embeds reconstruction-quality metadata (backend, iterations, QC verdict), replacing the current blanket `"confidence": "low"`.
**Plans**: 4 plans (3 waves)
- [x] 99-01-PLAN.md — Nyquist Wave 0: QcVerdict/QcCheckResult/QcReport models + known-bad & synthetic-clean fixtures + RED-by-skip stubs (wave 1)
- [x] 99-02-PLAN.md — nus/qc.py: 6 checks + aggregate_verdict + run_qc_checks + 3-tier prot/quaternary resolver (QC-01/QC-02, wave 2)
- [x] 99-03-PLAN.md — nus/bridge.py: Spectrum2D→PeakPicker2D bridge + per-experiment schema + metadata block + shared edited-sign helper (PICK-01/PICK-03, wave 2)
- [x] 99-04-PLAN.md — cli/nus.py: lucy nus qc + pipeline commands + D-07 write-boundary enforcement (PICK-02/QC-03, wave 3)

#### Phase 100: Cross-Platform Hardening + End-to-End Validation

**Goal**: The NUS reconstruction pipeline is preflight-checked and documented across supported platforms, and proven end-to-end on the milestone's real test case all the way through to CASE convergence.
**Depends on**: Phase 99
**Requirements**: PORT-01, PORT-02, VAL-01, VAL-02
**Success Criteria** (what must be TRUE):
  1. `lucy nus check` performs a platform preflight (Apple Silicon `arch`/Rosetta check, `csh`/`tcsh` availability, backend binaries) and reports clear readiness or failure before a run starts, never discovered mid-pipeline.
  2. A documented portability matrix (macOS Apple Silicon native, Linux native, Windows WSL2/VM gap with concrete workaround steps) exists in the repo — every known platform gap is investigated and written down, not silently accepted.
  3. C20H32O2 exp2 (COSY), exp3 (HSQC), exp4 (HMBC) are reconstructed end-to-end via `lucy nus pipeline` and pass the guide's §8 quality gate (clean 1-bond HSQC with correct edited signs, ridge-free HMBC, a real aliphatic COSY network).
  4. A fresh `/lucy-ng:case C20H32O2` run on the newly reconstructed peak lists converges on a small, rankable solution set — proving the reconstruction fixed the connectivity gap that timed out the original 2026-07-09 run at ~10⁶ candidates.
**Plans**: 3 plans (2 waves)
- [x] 100-01-PLAN.md — nus/platform_check.py detect_platform() + additive diagnose() 'platform' key + NusRunner.reconstruct() fail-loud preflight gate + lucy nus check platform section + --n-sigma flag (PORT-01, wave 1)
- [x] 100-02-PLAN.md — docs/NUS-PORTABILITY.md matrix (macOS-arm64/Linux/Windows-WSL2) + CLAUDE.md NMRPipe+SMILE prerequisite + README link + doc test (PORT-02, wave 1)
- [~] 100-03-PLAN.md — VAL end-to-end: install backend → reconstruct exp2/3/4 → §8/QC grade (D-04 tuning budget) → fresh /lucy-ng:case C20H32O2 convergence → VALIDATION.md (VAL-01/VAL-02, wave 2, autonomous:false) — **HONEST STOP per D-04, see limitation below**

> **⚠ Phase-100 limitation (VAL-01/VAL-02 NOT achieved) — recorded per CONTEXT decision D-04.**
> The NMRPipe+SMILE backend was installed natively on Apple Silicon and the reconstruction
> chain now runs correctly through `nusExpand.tcl` → `bruk2pipe` → F2 processing and **into**
> SMILE. Three real defects found by this first-ever real-binary run were fixed and committed
> (D-BUG-1 nusExpand `acqus` paths; D-BUG-2 `nmrPipe` multi-`-fn` verb chaining — F2 was never
> FT'd/transposed; plus install/XQuartz/quarantine environment work). **SMILE itself cannot
> complete on this host:** `nusPipe` reaches a ~5–7 GB working set and aborts with
> `Cannot allocate memory`, and that allocation is independent of direct-dimension size
> (2048/1024/256), `OMP_NUM_THREADS` (8/4/2/1) and `-maxIter` (5/50/500) — the bounded D-04
> tuning budget is therefore **exhausted**. VAL-02 was not reached (no reconstructed peaks;
> the D-07 write boundary correctly wrote nothing). PORT-01/PORT-02 shipped independently, as
> D-04 provides for.
> **Tracked next step: RECON-F1** (hmsIST/mddnmr fallback behind the existing `NusBackend`
> protocol). Secondary: re-run on a host with ≥ 8 GB free RAM, and expose/raise the hard-coded
> 600 s `run_stage` timeout. Full evidence: `phases/100-.../VALIDATION.md` +
> `100-03-VAL-EXECUTION-LOG.md`.

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|-----------------|--------|-----------|
| 97. Backend Integration + Params/Schedule | 5/5 | Complete    | 2026-07-12 |
| 98. Reconstruction + Processing | 6/6 | Complete    | 2026-07-13 |
| 99. Peak-Pick Bridge + QC Gate + CLI | 4/4 | Complete    | 2026-07-16 |
| 100. Cross-Platform Hardening + End-to-End Validation | 3/3 | Complete   | 2026-07-20 |

---

**v10.1 outcome — CLOSED PARTIAL (2026-07-28).** A binary-free JCAMP-DX input path: pure-Python
2D NTUPLES/DIFDUP decoding into the existing `Spectrum2D`/`Spectrum1D` models with verified
reversed ppm axes (vendored New-BSD line decoder, zero nmrglue private-API), plus a single
`lucy jcamp` command running read → pick → QC → write by reusing the Phase-99 peak-pick bridge
and the byte-unchanged QC gate. JC-01..04 and JCLI-01/02 all met; `case.md` and the 5-agent team
byte-unchanged, now guarded by a committed SHA-256 check.

**Not achieved — the milestone's actual success bar.** On the real `C20H32O2-jcamp` dataset all
six `.dx` files read in one governed run with zero failures and the full 31-cell knob matrix was
exhausted, but the QC verdict is a critical FAIL (`quaternary_exclusion` — knob-independent
across all 8 HSQC cells — and `hsqc_coverage` 69 %), so **JVAL-01 was not met** and **JVAL-02 was
never attempted** (the D-07 write boundary correctly produced no consumable peaks). Ruled out:
the ppm-axis defect class — the narrow 13C window is a genuine export property (`exp6`/narrow
shipped, `exp7`/wide did not), proven against raw Bruker `acqus`/`procs`. Tracked: **JVAL-F2**,
**JVAL-F3**, plus **CR-02/CR-03** (Phase-102 `lucy jcamp` data-loss paths, filed not fixed). Full
archive: [`milestones/v10.1-ROADMAP.md`](milestones/v10.1-ROADMAP.md).

---

## v11.0 AILSA Rename

**Goal:** The project is renamed from the working title *lucy-ng* to **AILSA** (*AI + LSD +
Agents*) everywhere it is visible — package, CLI, documentation, skill system, repository and
hosts — without breaking the running Opus-5 baseline re-run or rewriting the historical record.
Package and documentation can move first; the skill system and the repository/hosts phases are
**gated** on the Opus-5 baseline re-run finishing on the compute host (the blind runner there
still calls `/lucy-ng:case`, and the watchdog on the Mac runs from the absolute path
`…/lucy-ng/scripts/`), expected after the 2026-09-29 quota reset.

### Phases

- [ ] **Phase 104: Package and CLI** — PyPI package `ailsa`, module `ailsa` replacing `lucy_ng`, CLI `ailsa` with `lucy` kept as a deprecated alias for one release; full suite/mypy/ruff green on the renamed tree
- [ ] **Phase 105: Documentation and outside face** — README, `docs/`, CLAUDE.md, the figshare record and the infographic deck under the new name; LSD and Nuzillard credited up front
- [ ] **Phase 106: Skill system** (GATED — not before the Opus-5 baseline re-run finishes) — `/ailsa:*` commands and `ailsa-*` agents replacing `/lucy-ng:*`/`lucy-*`, `~/.claude` symlinks updated, proven by a blind CASE run on the compute host
- [ ] **Phase 107: Repository and hosts** (GATED — not before the Opus-5 baseline re-run finishes) — GitHub repo renamed with a redirect, local folder/LaunchAgent/remotes/compute-host checkout/auto-memory moved, planning documents speak the new name, a `v11.0` release tag

### Phase Details

#### Phase 104: Package and CLI

**Goal**: A user installs and runs the project under its real name — `pip install ailsa` gives the actual package, the `ailsa` module and CLI replace `lucy_ng`/`lucy`, and the renamed tree is exactly as green as before the rename.
**Depends on**: Nothing (first phase of v11.0; not gated — package/docs can move before the Opus-5 re-run finishes)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05
**Success Criteria** (what must be TRUE):
  1. `pip install ailsa` installs the real package (not the 0.0.1 name-reservation placeholder), and `pyproject.toml` names the project `ailsa`.
  2. Every import in `src/`, `tests/` and `scripts/` comes from the `ailsa` module; no `lucy_ng` module or import remains anywhere in the tree.
  3. A user runs every subcommand as `ailsa …`; `lucy …` still works for one release and prints a one-line deprecation hint pointing at `ailsa`.
  4. The full test suite passes on the renamed tree with the same pass count as before the rename (1345 passed / 74 environment failures, per STATE.md 2026-09-23), and `mypy --strict` and `ruff` report no new findings.
  5. A user with the existing database file `data/reference/lucy-ng-derep.db` keeps working — `ailsa database download` and `ailsa database info` accept the old file name as well as the new default.
**Plans**: TBD

#### Phase 105: Documentation and outside face

**Goal**: Everything a reader sees from outside the code — README, docs, the skill's own project memory, the figshare record and the infographic deck — presents the project as AILSA, with the old name acknowledged once and LSD credited up front.
**Depends on**: Phase 104 (docs describe the actually-renamed package and CLI, not a still-pending rename)
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. A reader of the README sees the project as AILSA, with the expansion *AI + LSD + Agents*, LSD and Jean-Marc Nuzillard credited up front, and a short note that the project was formerly called lucy-ng.
  2. `docs/` (ARCHITECTURE, USER_GUIDE, BENCHMARK, NUS-PORTABILITY and the rest) and `CLAUDE.md` refer to the project, package, CLI and commands by the new names; no living document still instructs the reader to type `lucy`.
  3. The figshare record of the reference database carries the new project name in title and description; the DOI and the uploaded file are unchanged.
  4. The infographic deck (`docs/infographics/build.py`) is rebuilt under the new name with the current headline numbers, clearing the outstanding "stale deck" backlog item.
**Plans**: TBD

#### Phase 106: Skill system

**Goal**: The autonomous CASE skill and its five-agent team run under the AILSA name end to end — commands, agent files, symlinks and a live blind run all prove the renamed chain works exactly like the old one.
**Depends on**: Phase 105. **GATED: must not start before the Opus-5 baseline re-run on the compute host has finished** (expected after the 2026-09-29 quota reset) — the blind runner there calls `/lucy-ng:case` and must not be disturbed mid-campaign.
**Requirements**: SKILL-01, SKILL-02, SKILL-03, SKILL-04
**Success Criteria** (what must be TRUE):
  1. A user runs `/ailsa:case`, `/ailsa:dereplicate`, `/ailsa:predict`, `/ailsa:sanitise` and `/ailsa:status`; the `/lucy-ng:*` commands are gone and the `~/.claude/commands` symlinks point at the new directory.
  2. The five agents are named `ailsa-nmr-chemist`, `ailsa-lsd-engineer`, `ailsa-solution-analyst`, `ailsa-devils-advocate` and `ailsa-diagnostic`; `case.md`, the supervisor and the SHA-256 byte-unchanged guard reference the new files, and the `~/.claude/agents` symlinks are updated.
  3. One blind CASE run on the compute host, started through the renamed command with the renamed agents, completes and grades correctly — proof that the chain works under the new name.
  4. The blind runner script and the watchdog scripts call the new command and paths, and the LaunchAgent (label, program path, log name) is re-registered under the new name.
**Plans**: TBD

#### Phase 107: Repository and hosts

**Goal**: Every place the project physically lives — GitHub, the local Mac folder, the compute host's checkout, the LaunchAgent and the planning documents — carries the new name, with the historical record left untouched.
**Depends on**: Phase 106 (skill renamed and proven on a live run before the paths its assets live under are moved). **GATED: must not start before the Opus-5 baseline re-run on the compute host has finished** (same gate as Phase 106) — the compute host's checkout and remotes must not move while the re-run is reading from them.
**Requirements**: REPO-01, REPO-02, REPO-03, REPO-04
**Success Criteria** (what must be TRUE):
  1. The GitHub repository is `steinbeck/ailsa`; the old `steinbeck/lucy-ng` URL redirects; the remotes of the local clone and of the compute host's checkout point at the new name.
  2. The local working copy lives at `~/Dropbox/develop/ailsa`; the auto-memory directory is moved with it so the next session starts with its memory; every absolute path on the Mac (LaunchAgent, symlinks, scripts) is updated.
  3. `.planning/PROJECT.md`, `STATE.md`, `ROADMAP.md`, `MEMORY.md` and the CASE identity/UAT files speak the new name; `.planning/phases/` history, `milestones/`, git history and the compute host's result directories are untouched.
  4. A release tag `v11.0` marks the first release under the new name, with a changelog entry explaining the rename.
**Plans**: TBD

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|-----------------|--------|-----------|
| 104. Package and CLI | 0/? | Not started | - |
| 105. Documentation and outside face | 0/? | Not started | - |
| 106. Skill system (GATED) | 0/? | Not started | - |
| 107. Repository and hosts (GATED) | 0/? | Not started | - |
</content>
