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
- 🚧 **v10.1 JCAMP-DX 2D Ingestion** - Phases 101-103 (in progress)

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

## v10.1 JCAMP-DX 2D Ingestion

**Goal:** Lucy-ng reads already-reconstructed 1D/2D NMR spectra from JCAMP-DX files and produces
the consumable CASE peak lists — with **no external binaries** — so CASE can run on NUS (or any)
data reconstructed elsewhere (TopSpin/mddnmr, nmrXiv, any vendor JCAMP export). This is a
**complementary input path, not a replacement** for v10.0's NUS self-reconstruction (which
remains PARTIAL — PORT shipped, VAL blocked by SMILE's memory abort, RECON-F1 tracked). It
reuses the entire downstream Phase-99 pipeline (`Spectrum2D`/`Spectrum1D` → `PeakPicker2D` →
`analysis/nmr_peaks/*.json` → QC gate → CASE) **unchanged**. Because there is no external
binary, the reader is fully CI-testable — a deliberate contrast to v10.0, whose external SMILE
binary could not be CI-tested and whose mock-only "verification" missed real bugs (D-BUG-1/2).
Motivating dataset: `C20H32O2-jcamp` (6 `.dx` files, 2D grids 2048×2048), reconstructed in
TopSpin via `mddnmr` compressed sensing (IRLS) — independently proving CS reconstruction
succeeds on this exact sample.

### Phases

- [ ] **Phase 101: JCAMP-DX Reader** — pure-Python 2D NTUPLES DIFDUP decoder into `Spectrum2D` + 1D reader into `Spectrum1D`, no external binary, verified ppm axes, CI-runnable fixture test
- [ ] **Phase 102: CLI + Peak-Pick Bridge + QC Reuse** — `lucy jcamp` command reusing the Phase-99 bridge pattern and the unchanged QC gate, `case.md` byte-unchanged
- [ ] **Phase 103: End-to-End Validation (C20H32O2-jcamp)** — real dataset read, peak-picked, QC-graded to §8 quality, and a fresh `/lucy-ng:case C20H32O2` run converges on a rankable solution set

### Phase Details

#### Phase 101: JCAMP-DX Reader

**Goal**: Lucy-ng can decode both 1D and 2D JCAMP-DX spectra — including the DIFDUP-compressed NTUPLES pages nmrglue itself cannot assemble — into the existing `Spectrum1D`/`Spectrum2D` models, with no external binary and with ppm axes proven correct rather than assumed.
**Depends on**: Phase 100 (v10.0 PARTIAL close — base codebase; JCAMP reader is independent of the NUS `nus/` package)
**Requirements**: JC-01, JC-02, JC-03, JC-04
**Success Criteria** (what must be TRUE):
  1. A 2D JCAMP-DX NTUPLES file (HSQC/HMBC/COSY) is decoded into a full `(n_f1, n_f2)` intensity matrix and loaded into a `Spectrum2D` model — the DIFDUP-compressed per-F1-row `##DATA TABLE=` pages are assembled by lucy-ng's own thin 2D-assembly layer, closing the exact gap where nmrglue returns `None`.
  2. The decoded `Spectrum2D`'s ppm axes are reversed and correct on both dimensions, derived from the NTUPLES metadata (`VAR_DIM`, `FIRST`/`LAST`/`FACTOR`, `.NUCLEUS`, `.OBSERVE FREQUENCY`) and explicitly cross-checked against the trusted 1D reference / §10 ground-truth shifts — not eyeballed, guarding against the WR-04-class Hz-vs-ppm axis error.
  3. A 1D JCAMP-DX file (¹H or ¹³C) decodes through the same reader module into a `Spectrum1D` model.
  4. A committed, CI-runnable unit test decodes a small real JCAMP fixture via the vendored/wrapped line decoder (DIFDUP/SQZ/PAC) with no external binary and no dependency on nmrglue's private API — passes in CI, so "verified" means verified for this milestone (the Phase-100 mock-only-verification lesson applied).
**Plans**: 4 plans (3 waves)
- [ ] 101-01-PLAN.md — Nyquist Wave 0: trimmed real HSQC fixture + two 1D references + COSY/NOESY spot-check + RED hand-oracle & integration tests (wave 1)
- [ ] 101-02-PLAN.md — Vendored DIFDUP/SQZ/DUP/PAC decoder (9-object closure, New-BSD attribution), JC-04 oracle green (wave 2)
- [ ] 101-03-PLAN.md — jcamp.py shared helpers (OFFSET+SF ppm formula, .NUCLEUS dim mapping, fail-loud assertion, metadata access) + read_1d (JC-03) (wave 2)
- [ ] 101-04-PLAN.md — read_2d NTUPLES page assembly + Y-FACTOR + reversed ppm axes + 1D cross-check + read() dispatcher (JC-01, JC-02) (wave 3)

#### Phase 102: CLI + Peak-Pick Bridge + QC Reuse

**Goal**: A JCAMP-DX file or directory can be turned into CASE-consumable, QC-graded peak lists via one command, reusing the Phase-99 bridge and QC gate exactly as they are — zero changes to `case.md` or the 5-agent team.
**Depends on**: Phase 101
**Requirements**: JCLI-01, JCLI-02
**Success Criteria** (what must be TRUE):
  1. `lucy jcamp <dir-or-files>` runs the full chain — read JCAMP → `Spectrum2D`/`Spectrum1D` → existing `PeakPicker2D` → `analysis/nmr_peaks/*.json` in the existing per-peak schema — reusing the Phase-99 `build_spectrum2d`-style direct-call bridge pattern, not a new picker; every subcommand supports `--format json`.
  2. JCAMP-derived peak lists pass through the **unchanged** Phase-99 QC gate and receive a PASS/PARTIAL/FAIL verdict exactly like NUS-reconstructed peaks do.
  3. The edited-HSQC sign (+/−) survives the JCAMP round-trip so downstream multiplicity derivation still works.
  4. `case.md` and the 5-agent team agent files are byte-unchanged after this phase (verifiable by diff).
**Plans**: TBD

#### Phase 103: End-to-End Validation (C20H32O2-jcamp)

**Goal**: The `C20H32O2-jcamp` dataset proves the JCAMP ingestion path is not just mechanically correct but usable for real CASE structure elucidation.
**Depends on**: Phase 102
**Requirements**: JVAL-01, JVAL-02
**Success Criteria** (what must be TRUE):
  1. All six `C20H32O2-jcamp` `.dx` files are read and peak-picked via `lucy jcamp`, producing §8-quality peak lists (clean 1-bond HSQC, ridge-free HMBC, a real aliphatic COSY network) — the first real (non-fixture) spectra to clear this bar via the JCAMP path.
  2. The QC gate reports PASS, or PARTIAL with only soft-check violations plus a brief chemist confirmation that the PARTIAL result is acceptable.
  3. A fresh `/lucy-ng:case C20H32O2` run on the JCAMP-derived peak lists converges on a finite, rankable solution set — the milestone's actual success bar, proving the connectivity from externally-reconstructed spectra is usable for CASE.
**Plans**: TBD

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|-----------------|--------|-----------|
| 101. JCAMP-DX Reader | 0/4 | Not started | - |
| 102. CLI + Peak-Pick Bridge + QC Reuse | 0/TBD | Not started | - |
| 103. End-to-End Validation (C20H32O2-jcamp) | 0/TBD | Not started | - |
</content>
