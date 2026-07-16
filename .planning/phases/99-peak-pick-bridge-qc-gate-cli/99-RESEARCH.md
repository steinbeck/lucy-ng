# Phase 99: Peak-Pick Bridge + QC Gate + CLI - Research

**Researched:** 2026-07-16
**Domain:** In-process NMR peak-picking bridge (existing `PeakPicker2D`) + a headless, machine-readable structural-QC gate for reconstructed 2D NMR correlations, gating a CASE-agent handoff
**Confidence:** MEDIUM — architecture/reuse patterns are HIGH confidence (grounded directly in existing, tested code); the QC checks' exact numeric thresholds and the prot/quaternary classification path are MEDIUM-LOW confidence (no "clean reconstruction" fixture exists yet to calibrate against — that is Phase 100's own deliverable)

## Summary

This phase is almost entirely **glue + new domain logic over existing, already-tested primitives** — there is no new external dependency, no new peak picker, and no new file format. `nus/bridge.py` builds a `Spectrum2D` from Phase 98's `processed.ft2` (read via `nmrglue.pipe.read()` + `guess_udic()`/`uc_from_udic()`, the exact pattern `BrukerReader.read_2d()` already uses for Bruker data) and calls the existing `PeakPicker2D.pick_peaks()` directly — mirroring `_perform_ranking()` in `cli/lsd.py`. The per-peak JSON keys `cli/pick.py` already emits (`c13_ppm`/`h1_ppm`/`edited_sign`/`multiplicity_hint`/`confidence`/`note` for HSQC, `f1_position`/`f2_position`/`snr` shape for HMBC/COSY-equivalent) must be reproduced structurally; a repo-wide grep confirms **no Python code anywhere parses `analysis/nmr_peaks/*.json`** — the only consumer is the LLM-driven `nmr-chemist` CASE agent reading the file as free-form JSON. This means D-05's additive top-level metadata block is safe *by construction*, not just by convention: there is no fixed schema parser to break.

The QC gate is the phase's genuinely new engineering: six checks (per QC-01/D-02) split critical (quaternary exclusion, ppm calibration, signal-to-ridge, HSQC coverage) vs. soft (edited-sign self-consistency, COSY diagonal symmetry). Inspecting the real known-bad fixtures on disk gives concrete, reproducible calibration numbers (see Common Pitfalls / Code Examples): the known-bad HSQC has 4/27 peaks (14.8%) sitting exactly on confirmed-quaternary shifts (the quaternary-exclusion check's natural trigger — the HSQC-coverage check alone does *not* fail on this fixture, since all 15 true protonated carbons are still found); the known-bad COSY has 7/7 peaks (100%) sharing one H1 coordinate (5.32 ppm) — a textbook t1-ridge, cleanly detectable via peak-list-only column/row clustering (no raw spectrum matrix needed, which matters because `lucy nus qc <peaks-dir>` per D-08 takes only a peaks directory). The one substantive gap versus CONTEXT.md's D-03 assumption: `detection/` has **no** protonated-vs-quaternary (CH-count) classifier — `StatisticalDetector.detect_hybridisation()` only returns sp3/sp2/sp1 fractions, never hydrogen count. A real CH-count fallback exists only via `DEPTGuidedPicker` (needs an actual DEPT-135 spectrum), and C20H32O2 has no DEPT experiment on disk. This is flagged prominently below with a recommended, honest fallback design.

**Primary recommendation:** Build `nus/bridge.py` as the ONLY new module that imports `processing.PeakPicker2D`/`models.Spectrum2D` directly (in-process call, no subprocess); build `nus/qc.py` as a self-contained, peak-list-only module whose six check functions take plain peak-list dicts (never the raw spectrum matrix) plus a small `QcReferenceData` object (trusted-1D shifts + prot/quaternary classification with an explicit, honest "insufficient reference data" fallback state — not a fabricated classification); wire both into `lucy nus pipeline` via `NusRunner`, with the write-boundary enforcement (D-07) living in the `pipeline` CLI command, not inside `NusRunner.reconstruct()` itself (keeps `NusRunner`'s existing contract — a processed spectrum — unchanged).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Spectrum2D construction from `processed.ft2` | Backend/CLI tool (`nus/bridge.py`) | — | Pure in-process Python; no server/client split in this CLI tool |
| Peak picking (HSQC/HMBC/COSY) | Backend/CLI tool (`processing/peak_picker_2d.py`, reused unmodified) | — | Existing, tested, format-agnostic on `Spectrum2D` |
| QC check computation (6 checks) | Backend/CLI tool (`nus/qc.py`, new) | — | Pure Python/numpy arithmetic on peak-list dicts; no external service |
| QC verdict aggregation (critical/soft split) | Backend/CLI tool (`nus/qc.py`) | — | D-02's aggregation logic; single auditable function |
| Write-boundary enforcement (PASS/PARTIAL write, FAIL quarantine) | Backend/CLI tool (`cli/nus.py::pipeline`) | `nus/runner.py` (orchestration only, no gating) | D-07: enforcement point is the pipeline command, not deep in the reconstruction orchestrator — keeps `NusRunner.reconstruct()`'s contract unchanged and testable in isolation |
| CASE handoff consumption of peak JSON | External consumer (LLM agent, `nmr-chemist`) | — | Confirmed via repo-wide grep: no Python-side schema parser exists for `analysis/nmr_peaks/*.json`; the only structured Python consumer of *any* peaks JSON is `webview/routers/tables.py`, which reads a **different** path (`analysis/peaks/hsqc.json` etc.) — untouched by this phase |
| Reference-data provisioning (trusted 1D, prot/quaternary) | Backend/CLI tool (`nus/qc.py` reads `analysis/nmr_peaks/13C_exp*.json`/`1H_exp1.json`) | `detection/` (hybridisation-only fallback, insufficient alone — see Pitfalls) | D-03; no re-pick, no second parse pass |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 — PARTIAL passes with a warning; only FAIL blocks.** FAIL refuses CASE handoff (QC-03). PARTIAL writes peaks and proceeds into CASE, with the `partial` verdict + violated-checks list surfaced in the peak-JSON metadata block (no `case.md` change required).
- **D-02 — Verdict aggregation = critical vs. soft checks** (not a flat count, not per-check worst-of).
  - **Critical (any violation ⇒ FAIL):** (1) quaternary-carbon exclusion, (2) ppm calibration, (3) signal-to-ridge ratio, (4) HSQC coverage.
  - **Soft (violation ⇒ PARTIAL):** edited-sign self-consistency; COSY diagonal symmetry.
  - **PASS** = no violations; **PARTIAL** = only soft violations; **FAIL** = any critical violation.
- **D-03 — Trusted 1D reference comes from the existing 1D peak lists.** Read `analysis/nmr_peaks/13C_exp*.json` + `1H_exp1.json`. No re-pick, no second parse pass, no second source of truth. Protonated-vs-quaternary classification prefers a picked DEPT/edited experiment if present; otherwise fall back to the existing `detection/` multiplicity/hybridisation statistics — kept independent of the HSQC under test (non-circular).
- **D-04 — Sensible defaults derived from §8 + existing peak-list tolerances, centralised in a QC-config/constants object, overridable via CLI flags/config.** Seed tolerances: **13C ±0.5 ppm, 1H ±0.05 ppm.** Signal-to-ridge FAIL threshold and HSQC-coverage FAIL floor are NOT seriously fixable without data calibration — calibrated against the QC-02 anchor (known-bad ⇒ FAIL, clean ⇒ PASS).
- **D-05 — Reconstruction metadata lives in a new top-level additive block** (e.g. `"reconstruction"`/`"nus_metadata"`) alongside `experiment`/`cross_peaks`, bundling backend, iterations, QC verdict, violated checks, thresholds used. Existing per-peak keys stay structurally unchanged. *(Claude's discretion on exact block name.)*
- **D-06 — Per-peak `confidence` is derived from the QC verdict**: PASS → high/medium, PARTIAL → low; FAIL peaks never reach the consumable location (D-07), so no FAIL confidence is emitted to CASE. Replaces the blanket `"confidence": "low"`.
- **"byte-for-byte" clarification:** PICK-01's "byte-for-byte" means **structurally schema-identical for the per-peak keys the CASE pipeline parses**, NOT a literal byte-diff. `caveat`/per-peak `confidence` necessarily change. A verifier must NOT fail this phase on a literal byte comparison.
- **D-07 — Enforcement sits at the pipeline/write boundary.** `lucy nus pipeline` writes productive `nmr_peaks/*.json` only when QC ∈ {PASS, PARTIAL}. On FAIL: no consumable peaks written — instead written to a quarantine/diagnostic path — and the command exits non-zero. `case.md` is NOT touched (no second orchestrator-side gate).
- **D-08 — CLI: standalone `lucy nus qc <peaks-dir>` + `lucy nus pipeline <expdir>`.** `qc` independently runnable against arbitrary peak lists (needed for QC-02's FAIL/PASS discrimination proof). `pipeline` orchestrates the full chain and calls the same qc code internally. A thin `lucy nus peak-pick` bridge stage may be exposed too (planner discretion). Every `lucy nus` subcommand supports `--format json`.

### Claude's Discretion

- Exact top-level metadata block name/shape (`reconstruction` vs `nus_metadata`), and the exact `caveat` regeneration/removal (D-05/D-06).
- Whether `lucy nus peak-pick` is a separately exposed subcommand or only an internal stage (D-08).
- The precise confidence mapping (PASS→high vs medium) and quarantine directory path/name (D-07).
- The exact numeric signal-to-ridge and HSQC-coverage-floor defaults — data-calibrated by research against the QC-02 anchor (D-04). **This research's concrete recommendations are below (Common Pitfalls / Code Examples) — treat as a starting point, not a final calibration; no "clean reconstruction" fixture exists yet to validate the PASS side (that's Phase 100).**
- `nus/bridge.py` API surface and its split from the QC module.

### Deferred Ideas (OUT OF SCOPE)

- Platform preflight matrix (Apple-Silicon `arch`/Rosetta, `csh`/`tcsh`), portability doc → Phase 100 / PORT.
- End-to-end §8-gate validation on C20H32O2 exp2/3/4 and `/lucy-ng:case C20H32O2` convergence → Phase 100 / VAL.
- Per-peak reconstruction-confidence scoring feeding LSD constraint weighting directly (RECONUX-F1); webview rendering of reconstructed 2D + QC report (RECONUX-F2) → deferred (v1.x).
- Defense-in-depth second QC gate inside `case.md`/DA — explicitly rejected; single pipeline-boundary barrier (D-07).
- Combined QC+SNR per-peak confidence — deferred; per-peak confidence is QC-verdict-derived only (D-06).
- **"Held-out cross-validation"** — appears in the *milestone-level* SUMMARY.md/PITFALLS.md research as a candidate 7th check, but is **not** one of QC-01's six locked checks and is **not** in D-02's critical/soft split. Do not add it as a 7th mandatory check in this phase; it would silently expand scope beyond what CONTEXT.md locked.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PICK-01 | Bridge builds `Spectrum2D` in memory, reuses `PeakPicker2D` via direct Python call, writes `analysis/nmr_peaks/*.json` schema-identical (per-peak keys) to today's output | `nus/bridge.py` design (Architecture Patterns); confirmed exact per-peak JSON shape from `cli/pick.py`; confirmed `.ft2` → `Spectrum2D` construction pattern from `readers/bruker.py::read_2d()` |
| PICK-02 | `lucy nus pipeline <expdir>` runs params→schedule→reconstruct→process→peak-pick→QC end-to-end, reusable for any NUS CASE run; all `lucy nus` subcommands support `--format json` | `NusRunner.reconstruct()` (Phase 98, unchanged) + new `pipeline` CLI command design (Architecture Patterns); existing `check`/`params`/`schedule`/`reconstruct` already support `--format json` — `qc`/`pipeline` must match |
| PICK-03 | Reconstruction-quality metadata (backend, iterations, QC verdict) embedded in emitted peak JSON, replacing blanket `"confidence": "low"` | D-05/D-06 additive top-level block design; `NusReconstructionResult` (Phase 98) already carries `backend`/`smile_iterations` — bridge reads these directly, no re-derivation |
| QC-01 | Automated QC gate cross-checks every reconstructed correlation against trusted 1D shift data (6 named checks), emits machine-readable PASS/PARTIAL/FAIL, no human in the loop | `nus/qc.py` design (Architecture Patterns); concrete algorithms + calibration numbers for all 6 checks (Common Pitfalls, Code Examples) |
| QC-02 | QC gate FAILs on known-bad t1-ridge home-IST lists, PASSes on a clean reconstruction | Real known-bad fixtures inspected on disk (concrete numbers below); PASS side requires a **synthetic** clean fixture in Phase 99's own tests (no real clean reconstruction exists until Phase 100 — see Validation Architecture) |
| QC-03 | CASE handoff refuses to start on QC FAIL, extending FIX-10 spirit to reconstruction-derived peaks | Confirmed FIX-10 is a skill-level (agent-instruction) convention, **not** Python code — "extending" it means D-07's write-boundary enforcement (fail-loud at data-creation time), not modifying `case.md` or any FIX-10-labeled function (none exists in `src/`) |
</phase_requirements>

## Standard Stack

### Core

No new external packages. This phase is 100% new/adapted Python over already-vendored dependencies:

| Library | Version (repo-pinned) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `nmrglue` | `git+https://github.com/jjhelmus/nmrglue.git` (core dep, pinned via git per NumPy-2.0 compat note in `pyproject.toml`) | Reads `processed.ft2` (`ng.pipe.read`), builds ppm scales (`ng.pipe.guess_udic` + `ng.fileiobase.uc_from_udic`) | Already the project's sole NMR-file-format library; `readers/bruker.py` and `nus/postprocess.py` already use it for the identical operation on different file formats |
| `numpy` | project-pinned (core dep) | Peak-list clustering (ridge detection), coverage/consistency arithmetic | Already core |
| `pydantic` v2 | project-pinned (core dep) | `QcVerdict`/`QcCheckResult`/`QcReport` models in `models/nus.py` | Project-wide convention (every `models/*.py` module) |
| `click` | project-pinned (core dep) | `qc`/`pipeline` (and optional `peak-pick`) subcommands in `cli/nus.py` | Project-wide CLI convention |

### Supporting

None. `processing.PeakPicker2D` and `models.Spectrum2D`/`Peak2D`/`PeakList2D` are **reused unmodified** — this phase adds zero new peak-picking logic (PICK-01's explicit constraint).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Peak-list-only ridge detection (column/row clustering on already-picked peaks) | Raw-spectrum-matrix ridge detection (variance/median-per-row on `Spectrum2D.data`) | Matrix-based detection is more sensitive/precise, but **contradicts D-08's CLI contract** (`lucy nus qc <peaks-dir>` takes only a peaks directory — no raw spectrum path) and QC-02's regression fixtures are JSON-only files with no accompanying `.ft2`. Peak-list-only is the only approach compatible with the locked CLI surface. |
| Reusing `nus/postprocess.py::check_calibration()`/`calibrate_against_1d_reference()` for the ppm-calibration check | Reimplementing calibration cross-check in `nus/qc.py` | These functions already exist, are already tested (Phase 98), and already implement exactly the "cross-check reconstructed shifts against §10 ground truth, flag systematic offset beyond tolerance" logic QC-01's ppm-calibration check needs. Reuse via import, do not duplicate. |
| `detection/` hybridisation stats as prot/quaternary fallback (as CONTEXT.md D-03 anticipated) | An explicit `QcReferenceData` override / "insufficient data" soft-fail state | `detection.detector.StatisticalDetector.detect_hybridisation()` returns only sp3/sp2/sp1 fractions — **it cannot distinguish CH/CH2/CH3 from quaternary (Cq)** (confirmed: HOSE-stats DB schema has `sp3_count`/`sp2_count`/`sp1_count` columns only, no hydrogen-count column). This is a genuine gap versus the CONTEXT.md assumption — see Common Pitfalls. |

**Installation:** none required — no new dependency.

**Version verification:** N/A — no version-pinned new package introduced this phase.

## Package Legitimacy Audit

**Not applicable.** This phase introduces zero new external packages. All libraries used (`nmrglue`, `numpy`, `pydantic`, `click`) are pre-existing core dependencies already vetted in prior phases (97/98). The Package Legitimacy Gate protocol (slopcheck / registry verification) is skipped — there is nothing new to verify.

## Architecture Patterns

### System Architecture Diagram

```
                         Phase 98 output
                              │
                    analysis/nus_recon/<expN>/processed.ft2
                    analysis/nus_recon/<expN>/processed_ppm_axis.json (F1 sidecar, optional)
                              │
                              ▼
                 ┌─────────────────────────┐
                 │   nus/bridge.py (NEW)    │
                 │  build_spectrum2d(...)   │  ng.pipe.read() + guess_udic()/uc_from_udic()
                 │  bridge_peak_pick(...)   │  → Spectrum2D  → PeakPicker2D.pick_peaks() (REUSED, unmodified)
                 └────────────┬─────────────┘
                              │  PeakList2D (in-memory, F1=13C, F2=1H)
                              ▼
                 ┌─────────────────────────┐        analysis/nmr_peaks/13C_exp*.json
                 │    nus/qc.py (NEW)       │◄───────analysis/nmr_peaks/1H_exp1.json   (D-03 trusted 1D)
                 │  6 check functions       │◄───────analysis/nmr_peaks/DEPT*.json     (if present, D-03 preferred)
                 │  aggregate_verdict()     │◄───────detection.StatisticalDetector      (fallback, LIMITED — see Pitfalls)
                 │  → QcReport (PASS/       │
                 │    PARTIAL/FAIL)         │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌─────────────────────────────────────────┐
                 │  cli/nus.py :: pipeline (NEW)             │
                 │  1. NusRunner.reconstruct()  (Phase 98)   │
                 │  2. nus.bridge.bridge_peak_pick()         │
                 │  3. nus.qc.run_qc_checks() → QcReport     │
                 │  4. WRITE-BOUNDARY (D-07):                │
                 │     PASS/PARTIAL → analysis/nmr_peaks/*.json (+ D-05 metadata block)
                 │     FAIL         → analysis/nus_recon/<expN>/qc_failed/*.json, exit 1
                 └─────────────────────────────────────────┘
                              │  (PASS/PARTIAL only)
                              ▼
                 analysis/nmr_peaks/HSQC_exp3.json etc.  ── consumed by ──▶  nmr-chemist CASE agent
                 (schema-identical per-peak keys; new         (LLM reads JSON directly — NO Python
                  top-level "reconstruction" metadata block)   schema parser exists for this path)
```

### Recommended Project Structure

```
src/lucy_ng/nus/
├── runner.py        # UNCHANGED (Phase 98) — NusRunner.reconstruct() contract stays exactly as-is
├── postprocess.py    # UNCHANGED (Phase 98) — check_calibration()/calibrate_against_1d_reference() REUSED by qc.py
├── bridge.py         # NEW — Spectrum2D construction from processed.ft2 + PeakPicker2D call + JSON write (per-peak schema)
├── qc.py             # NEW — 6 check functions + QcReferenceData + aggregate_verdict()
└── backends/          # UNCHANGED

src/lucy_ng/models/nus.py
└── (add) QcVerdict (str Enum: PASS/PARTIAL/FAIL), QcCheckResult, QcReport   # joins existing NusReconstructionResult etc.

src/lucy_ng/cli/nus.py
└── (add) qc, pipeline (+ optional peak-pick) commands — deferred-import convention preserved
```

### Pattern 1: `Spectrum2D` construction from a processed NMRPipe `.ft2` (mirrors `BrukerReader.read_2d`)

**What:** Build the in-memory `Spectrum2D` the bridge feeds to `PeakPicker2D` directly from `processed.ft2`'s own NMRPipe header, using the exact same nmrglue idiom `readers/bruker.py` already uses for Bruker `pdata` — just swapping `ng.bruker.read_pdata`/`ng.bruker.guess_udic` for `ng.pipe.read`/`ng.pipe.guess_udic`. `uc_from_udic(udic, dim=0/1)` is format-agnostic (operates on the universal dictionary), so the downstream `.ppm_scale()` call is identical.

**When to use:** F2 (direct) axis — this is a genuinely-acquired (not NUS-reconstructed) dimension; its NMRPipe header calibration from `bruk2pipe`'s own SF/OFFSET conversion is already correct, no cross-check needed.

**F1 (indirect) axis caveat:** prefer `analysis/nus_recon/<expN>/processed_ppm_axis.json`'s `calibrated_ppm_axis` (written by `postprocess.process_indirect()`, Phase 98) over the raw NMRPipe-header F1 axis when the sidecar exists — it already carries the §10 1D-cross-check calibration offset that a NUS-reconstructed indirect dimension needs and the direct dimension does not. Fall back to `ng.pipe.guess_udic`'s own F1 axis only if the sidecar is missing (e.g. calibration params weren't available at Phase-98 time).

**Example:**
```python
# Source: readers/bruker.py::read_2d() (existing, verified pattern) + nus/postprocess.py
# (existing _read_processed_f1_size / _write_ppm_calibration_sidecar, Phase 98)
import json
from pathlib import Path
import nmrglue as ng
import numpy as np
from lucy_ng.models import Spectrum2D

def build_spectrum2d(processed_ft2: Path, params, experiment_type: str) -> Spectrum2D:
    dic, data = ng.pipe.read(str(processed_ft2))
    udic = ng.pipe.guess_udic(dic, data)  # dim 0 = F1 (indirect), dim (ndim-1) = F2 (direct)

    uc_f2 = ng.fileiobase.uc_from_udic(udic, dim=1)
    f2_ppm_scale = np.array(uc_f2.ppm_scale(), dtype=np.float64)

    sidecar = processed_ft2.parent / "processed_ppm_axis.json"
    if sidecar.exists():
        f1_ppm_scale = np.array(json.loads(sidecar.read_text())["calibrated_ppm_axis"], dtype=np.float64)
    else:
        uc_f1 = ng.fileiobase.uc_from_udic(udic, dim=0)
        f1_ppm_scale = np.array(uc_f1.ppm_scale(), dtype=np.float64)

    return Spectrum2D(
        data=np.array(data, dtype=np.float64),
        f1_ppm_scale=f1_ppm_scale,   # 13C
        f2_ppm_scale=f2_ppm_scale,   # 1H
        f1_nucleus=params.f1_nucleus,
        f2_nucleus=params.f2_nucleus,
        experiment_type=experiment_type,   # from FnMODE/pulse_program, reuse readers.bruker._detect_experiment_type()
        frequency=params.f2_sfo1,
    )
```

### Pattern 2: Direct-call bridge, mirroring `_perform_ranking()`

**What:** `nus/bridge.py` calls `PeakPicker2D.pick_peaks(spectrum, ...)` as a plain Python function call — no subprocess, no `lucy pick` CLI invocation. `_perform_ranking()` in `cli/lsd.py` is the confirmed precedent: "build model in memory → direct Python call to existing subsystem," extracted specifically so a pipeline command can call it without spawning a subprocess.

**When to use:** Every stage of `lucy nus pipeline` after reconstruction — peak-picking, QC — must be in-process for the same reason `_perform_ranking()` was extracted: a single `pipeline` command owns one Python process end-to-end.

### Pattern 3: Peak-list-only ridge detection (column/row clustering)

**What:** Cluster picked peaks by a shared coordinate in ONE dimension (within a small ppm tolerance), independent of the raw spectrum matrix. A genuine t1-ridge in a NUS reconstruction shows up as an anomalously large fraction of all cross-peaks sharing (almost) the same F1 or F2 coordinate — this is directly visible in the known-bad COSY fixture (see Code Examples).

**When to use:** The signal-to-ridge check (critical, D-02) and as a supporting signal for HMBC ridge streaks. This is genuinely new code — SUMMARY.md itself flags "the ridge-detection metric... needs its own design spike, this is genuinely new code, not adapted from an existing pattern." Treat the concrete formula below as a starting design, not a final calibration (no clean-reconstruction fixture exists yet to validate the PASS side).

**Example:** see Code Examples below (`ridge_fraction()`).

### Anti-Patterns to Avoid

- **Re-picking or re-parsing the trusted 1D data with new logic:** D-03 explicitly forbids a second parse pass. Read `analysis/nmr_peaks/13C_exp*.json`/`1H_exp1.json` as-is (already-picked JSON, same format `cli/pick.py --format json` produces).
- **Fabricating a prot/quaternary classification when neither DEPT nor an explicit override is available:** silently guessing (e.g. "assume everything below 60 ppm sp3 with high hybridisation confidence is protonated") would produce a QC gate that *looks* headless (QC-01) but is actually lying about its own reference data. Prefer an honest "insufficient reference data for this check" soft-skip over a fabricated hard verdict — see Common Pitfalls.
- **Computing ridge/coverage/calibration checks against the raw `Spectrum2D.data` matrix:** contradicts D-08's `lucy nus qc <peaks-dir>` contract (peaks-dir only, no spectrum path) and breaks QC-02's JSON-only regression fixtures.
- **Putting the write-boundary gate (D-07) inside `NusRunner.reconstruct()`:** `NusRunner`'s Phase-98 contract returns a `NusReconstructionResult` with `processed_spectrum` — it has no concept of peaks or QC. Keep it that way; put the gate in the `pipeline` CLI command, which is the only caller that knows about both reconstruction AND peak-picking AND QC.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 2D peak picking (local maxima, SNR/MAD thresholding, edited-sign detection) | A new NUS-aware picker | `processing.PeakPicker2D.pick_peaks()` (unmodified) | PICK-01's explicit constraint; the picker doesn't know or care whether `Spectrum2D` came from `BrukerReader` or NUS reconstruction — it only sees the model |
| ppm-axis 1D-reference calibration cross-check | A second calibration-offset calculator in `nus/qc.py` | `nus/postprocess.py::check_calibration()` / `calibrate_against_1d_reference()` (already exists, already tested in Phase 98) | Exactly implements "detect systematic offset vs. §10 ground truth, flag beyond tolerance" — the ppm-calibration check's whole job |
| Multiplicity-edited sign detection | New sign-classification logic in the bridge | `cli/pick.py::_detect_multiplicity_edited()` (module-private today — planner may need to promote it to an importable location, e.g. move to `processing/` or export from `cli/pick.py`) | Already proven (ported from FIX-08's `negative_detected` 1D detector); reuse rather than reinvent the `-0.05 * max_abs` cutoff heuristic |
| Molecular-formula H-count reasoning | A quaternary-carbon inference engine from scratch | `analysis/hydrogen_budget.py::HydrogenBudgetAnalyzer` (existing, but requires `DEPTGuidedResult` input — not directly usable without a DEPT spectrum) | Illustrates the project's existing convention for H-count reasoning; useful precedent even though it can't be called directly without DEPT input for this compound |

**Key insight:** Every genuinely reusable building block in this domain already exists in the codebase from prior phases (85-98) — `PeakPicker2D`, `check_calibration`, `_perform_ranking`'s direct-call pattern, `BrukerReader`'s nmrglue idiom. The only *net-new* algorithm this phase must design from scratch is peak-list-only ridge detection (Pattern 3) and the QC verdict-aggregation function (D-02) — everything else is composition, not invention.

## Common Pitfalls

### Pitfall 1: `detection/` cannot classify protonated-vs-quaternary carbons (contradicts a CONTEXT.md D-03 assumption)

**What goes wrong:** D-03 says "otherwise fall back to the existing `detection/` multiplicity/hybridisation statistics" for prot/quaternary classification when no DEPT is present. `StatisticalDetector.detect_hybridisation(shift_ppm)` (verified: `detection/detector.py`) queries the HOSE-stats DB and returns only an `sp3`/`sp2`/`sp1` frequency distribution — **it has no hydrogen-count field at all**. Confirmed at the schema level: `database/schema.py`'s `hose_stats` table (v4) has `sp3_count`/`sp2_count`/`sp1_count` columns, nothing else. There is no code path in `detection/` that can say "this shift is a quaternary carbon" vs. "this shift is a CH."

**Why it happens:** The milestone's own CONTEXT.md D-03 discussion conflated "hybridisation statistics" (which does exist) with "multiplicity/CH-count statistics" (which does not) — an easy mix-up since both terms appear together in the `detection/` docstrings and both are HOSE-database-driven.

**How to avoid:** Design `nus/qc.py`'s reference-data resolution with three tiers, in this order:
1. **DEPT/edited experiment present** (`analysis/nmr_peaks/DEPT*.json` or similar, glob-detected) — real ground truth, per D-03's preferred path. (Not present for the C20H32O2 fixture set today.)
2. **Explicit override** (QC-config field / CLI flag, per D-04's "centralised in a QC-config/constants object, overridable via CLI flags/config") — e.g. a `known_quaternary_shifts: list[float]` the operator supplies. For the C20H32O2 regression fixtures this is the practical path: the 5 quaternary shifts (142.00, 135.86, 79.35, 36.23, 37.86) are already a hardcoded, chemist-derived fact in the guide's own §8/§10 (and already partially mirrored as `GUIDE_S10_C13` in `nus/postprocess.py` for the *full* 20-shift list) — the planner should NOT invent a new derivation, just thread an explicit, documented constant/config value through.
3. **Neither available:** mark the HSQC-coverage and quaternary-exclusion checks `"insufficient_reference_data"` in the `QcReport` rather than executing them against a fabricated classification — this must NOT silently downgrade to PASS; treat as a check that could not run and say so explicitly in the machine-readable report (still satisfies "no human in the loop," QC-01, because the report itself is the honest signal, not a human).

**Warning signs:** A `nus/qc.py` implementation that calls `detect_hybridisation()` and interprets `sp3=1.0` as "protonated" — this is simply wrong; a quaternary sp3 carbon (e.g. 36.23, the gem-dimethyl quaternary) has `sp3` hybridisation too.

### Pitfall 2: The "trusted 1D" peak lists contain solvent/noise peaks in the same SNR range as real signals

**What goes wrong:** `13C_exp6_narrow.json`/`13C_exp7_wide.json` are raw `lucy pick 1d --format json` output — 43 and 32 peaks respectively, versus 20 real carbons. Inspected directly: the CDCl3 solvent triplet (~77.0-77.3 ppm) has SNR ~1200-1215 (obviously excludable), but several **non-real** extra peaks sit at SNR 13-20 — directly overlapping the SNR range of real, legitimate carbons (e.g. the real 79.35 ppm quaternary has SNR 15.3, while the spurious 32.74 ppm peak has SNR 15.7). **A plain SNR floor cannot cleanly separate real carbons from noise in this list.**

**Why it happens:** The 1D peak picker has no molecular-formula-aware carbon-count constraint; it just reports everything above its noise floor.

**How to avoid:** Do not attempt to derive "the clean N-carbon list" generically from the raw 1D JSON via SNR filtering alone. For the check algorithms that need trusted-1D shifts (coverage, quaternary-exclusion, calibration), match RECONSTRUCTED HSQC/HMBC/COSY correlations *against* the raw 1D list within tolerance (nearest-neighbor lookup) rather than trying to *derive* a canonical clean list from the 1D data first — spurious 1D peaks that never appear as a real 2D correlation simply never get matched, so they are harmless as long as the matching direction is "does this 2D peak have a nearby 1D reference," not "list all real 1D peaks."

**Warning signs:** A QC report claiming "23 protonated carbons expected" (matching a raw peak count) instead of the correct compound-specific 15 (20 total − 5 quaternary, confirmed against `GUIDE_S10_C13`).

### Pitfall 3: HSQC-coverage alone does NOT catch the known-bad fixture — only quaternary-exclusion does

**What goes wrong:** Naively assuming the QC-02 regression floor requires tuning the HSQC-coverage floor tightly. Direct inspection of `HSQC_exp3.json` (known-bad): 27 cross-peaks, 17 unique ¹³C shifts. Two of those 17 (36.23, 37.86) are false hits at confirmed-quaternary shifts; the remaining **15 are exactly the 15 true protonated carbons** (20 total − 5 quaternary), each with ≥1 correlation. **Coverage of true protonated carbons is 100% even on the known-bad fixture.** It is the *quaternary-exclusion* check (4/27 peaks, 14.8%, sitting on quaternary shifts) that must fail this fixture.

**Why it happens:** The home-grown per-column IST approximation that produced this fixture hallucinated *extra* peaks at quaternary shifts rather than *dropping* real protonated-carbon peaks — an over-fabrication failure mode, not an under-coverage one.

**How to avoid:** Set the HSQC-coverage floor generously (e.g. ≥80% of trusted protonated carbons must show ≥1 correlation) — it does not need to be tight to correctly fail this fixture, and an over-tight floor risks false-FAILing a genuinely complete-but-imperfect clean reconstruction later. Rely on the quaternary-exclusion check (zero-tolerance: ANY 1-bond correlation within ±0.5 ppm of a known quaternary shift ⇒ FAIL) as the primary defense for this specific failure mode — this matches D-02's explicit design of 4 *independent* critical checks rather than one combined metric.

### Pitfall 4: Edited-sign self-consistency shows real, computable violations in the known-bad fixture

**What goes wrong / concrete numbers:** Among the known-bad HSQC's 7 carbons with 2 picked peaks each (excluding the 2 false-quaternary hits), 3/7 (43%) show **inconsistent** `multiplicity_hint` between their two component peaks: 22.63 ppm (`CH_or_CH3` + `CH2`), 23.43 ppm (`CH2` + `CH_or_CH3`), 67.06 ppm (`CH2` + `CH_or_CH3`). A genuine CH2's two diastereotopic protons should both report the same sign/multiplicity class.

**How to avoid:** Implement the soft edited-sign self-consistency check as: for every carbon shift with >1 picked peak, all peaks at that shift must share the same `multiplicity_hint`/sign class; any mismatch ⇒ soft violation (contributes to PARTIAL, per D-02). Zero-tolerance is appropriate here (any single inconsistency is a real chemistry contradiction, not a borderline case) — this is a boolean flag, not a numeric floor.

### Pitfall 5: Signal-to-ridge detection is genuinely new code — the known-bad COSY gives a clean, extreme calibration anchor

**What goes wrong / concrete numbers:** `COSY_exp2.json` (known-bad): **all 7 of 7 cross-peaks** (100%) share `h1a_ppm = 5.32` (±0.02 ppm) with varying `h1b_ppm`. This is a textbook t1-ridge along one column — computable directly from the peak list (no spectrum matrix needed) by clustering peaks on one axis within a small tolerance and measuring the largest cluster's fraction of total peaks. `HMBC_exp4.json` shows a softer version: 20/64 peaks (31%, using a coarse 0.1 ppm bin) cluster near H1≈1.6 ppm — a plausible but noisier ridge signature, complicated by the fact that legitimate gem-dimethyl HMBC correlations *also* cluster tightly in H1 (this is exactly why SUMMARY.md flags this check as needing its own design spike).

**How to avoid:** Implement `ridge_fraction(peaks, axis="f1"|"f2", tol=0.05) -> float` = (size of the largest same-axis-coordinate cluster) / (total peak count), independently for both axes, take the max. Recommended starting FAIL threshold: **`ridge_fraction > 0.5`** — the known-bad COSY (1.0) fails with a large margin; a genuine HMBC methyl cluster of, say, 6-8 peaks out of 60+ total peaks (10-15%) would not trigger a false FAIL. Flag explicitly: **this exact threshold is unvalidated against a real clean reconstruction** (none exists yet — Phase 100). Treat as MEDIUM-LOW confidence, expose as an overridable QC-config value (D-04), and write the Phase-99 test suite's PASS-side proof against a **hand-authored synthetic clean fixture** (see Validation Architecture), not a real one.

### Pitfall 6: The CASE consumer is an LLM reading raw JSON — no Python schema parser exists for `analysis/nmr_peaks/*.json`

**What goes wrong (if NOT accounted for):** Assuming a Python-side consumer must be grepped/updated when the additive metadata block is added.

**What was actually verified:** A repo-wide grep for `nmr_peaks`, `cross_peaks`, `c13_ppm`, `h1_ppm` across `src/lucy_ng/` and `.claude/agents/*.md`/`.claude/commands/lucy-ng/**/*.md` returns **zero hits** referencing this specific path/schema in Python code. The only Python code touching *any* peaks JSON is `webview/routers/tables.py`, which reads a structurally different, differently-named path (`analysis/peaks/hsqc.json`/`cosy.json`/`hmbc.json` — no `_expN` suffix, no `nmr_peaks/` directory) — entirely unrelated to this phase's output. The CASE team's consumption of `analysis/nmr_peaks/*.json` is purely the `nmr-chemist` LLM agent reading the file's raw JSON text with its own judgment.

**How to avoid / implication:** D-05's claim ("the CASE consumer ignores unknown top-level keys") is **provably safe**, not just conventionally safe — there is no fixed-schema code path that could break. This significantly de-risks the additive-metadata-block design; no `case.md`/agent-markdown change is needed to make an LLM tolerate an extra top-level key it wasn't told to look for.

**Warning signs (converse risk):** Because the consumer is an LLM, a *malformed* or wildly-oversized metadata block (e.g. embedding the full raw QC check computation trace) could burn context/attention budget in the CASE run without adding value — keep the D-05 metadata block small and focused (backend, iterations, verdict, violated-check names, thresholds used — not full per-check numeric traces).

## Code Examples

### `ridge_fraction()` — peak-list-only signal-to-ridge metric (Pattern 3)

```python
# New code — no direct upstream precedent (SUMMARY.md flags this as needing its own design).
# Grounded against the real known-bad COSY fixture inspected during this research.
from collections import Counter

def ridge_fraction(peaks: list[dict], axis_key: str, tol: float = 0.05) -> float:
    """Fraction of peaks sharing one axis coordinate within `tol` ppm.

    axis_key: "h1a_ppm" (COSY), "f1_position"/"c13_ppm" (HSQC/HMBC F1), etc.
    Returns 0.0 for an empty peak list (no ridge signal to report).
    """
    if not peaks:
        return 0.0
    # Bin to `tol`-wide buckets; count peaks per bucket.
    buckets = Counter(round(p[axis_key] / tol) for p in peaks)
    largest = max(buckets.values())
    return largest / len(peaks)

# Known-bad COSY_exp2.json: ridge_fraction(peaks, "h1a_ppm", tol=0.05) == 1.0  (7/7)
# -> FAIL at any threshold <= 1.0, e.g. recommended default 0.5
```

### Reusing Phase 98's calibration check (Don't Hand-Roll)

```python
# Source: src/lucy_ng/nus/postprocess.py (existing, Phase 98, already tested)
from lucy_ng.nus.postprocess import check_calibration, GUIDE_S10_C13, DEFAULT_CALIBRATION_TOL

def qc_check_ppm_calibration(hsqc_c13_shifts: list[float]) -> bool:
    """QC-01's ppm-calibration check: reuse, do not reimplement."""
    return check_calibration(hsqc_c13_shifts, GUIDE_S10_C13, tol=DEFAULT_CALIBRATION_TOL)
    # DEFAULT_CALIBRATION_TOL == 0.5, matching D-04's seed 13C tolerance exactly.
```

### Multiplicity self-consistency (Pitfall 4) — concrete algorithm

```python
from collections import defaultdict

def edited_sign_self_consistent(hsqc_peaks: list[dict], tol: float = 0.5) -> tuple[bool, list[float]]:
    """Soft check (D-02): every carbon with >1 peak must show ONE multiplicity_hint.

    Returns (is_consistent, [violating c13 shifts]).
    """
    by_carbon: dict[float, set[str]] = defaultdict(set)
    for p in hsqc_peaks:
        # bucket by tol to merge near-identical shifts picked as separate peaks
        key = round(p["c13_ppm"] / tol) * tol
        by_carbon[key].add(p["multiplicity_hint"])
    violations = [c for c, hints in by_carbon.items() if len(hints) > 1]
    return (len(violations) == 0, violations)

# Known-bad HSQC_exp3.json: violations at 22.63, 23.43, 67.06 (3 of 7 multi-peak carbons)
```

## State of the Art

Not directly applicable — this phase's "state of the art" question (CS/IST NUS reconstruction quality metrics) was already researched in Phase 97/98's research; no external published QC-gate design is being adopted wholesale here. The six checks are locked by CONTEXT.md D-02/QC-01, derived from the project's own `NUS-RECONSTRUCTION-GUIDE.md` §8, not from a generic literature survey.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Manual/GUI-driven "does this look right" visual QC (the workflow this milestone explicitly removes) | Automated, structured, PASS/PARTIAL/FAIL machine-readable QC gate blocking CASE handoff on FAIL | This phase (99) | Closes the milestone's crux risk (fabricated cross-peaks silently becoming hard LSD constraints) |
| Blanket `"confidence": "low"` on every reconstructed peak (the current home-IST fixtures) | Per-peak confidence derived from the QC verdict (D-06) | This phase | CASE agents get an honest, differentiated confidence signal instead of a uniform low-trust flag |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ridge_fraction > 0.5` is a safe default FAIL threshold for the signal-to-ridge check | Common Pitfalls #5, Code Examples | If too low, a real clean reconstruction with legitimate methyl clustering could false-FAIL (QC-02's PASS side, currently unvalidated — no real clean fixture exists). If too high, a genuinely ridge-laden reconstruction could false-PASS. Must be re-validated in Phase 100 once a real clean C20H32O2 reconstruction exists. |
| A2 | HSQC-coverage floor of ≥80% of trusted protonated carbons is a safe default | Common Pitfalls #3 | Same class of risk as A1 — untested against any real clean reconstruction; the known-bad fixture alone doesn't constrain this value tightly (it already passes coverage at 100%). |
| A3 | Explicit override (tier 2) is the practical prot/quaternary classification path for the C20H32O2 fixtures, since no DEPT experiment exists and `detection/` cannot supply CH-count | Common Pitfalls #1, Standard Stack (Alternatives Considered) | If the planner instead tries to force `detection/`'s hybridisation-only data into a prot/quaternary role, both the HSQC-coverage and quaternary-exclusion critical checks would be built on a false premise (sp3 hybridisation ≠ protonated) — likely producing silently-wrong FAIL/PASS verdicts on real data. |
| A4 | `analysis/nus_recon/<expN>/qc_failed/` is a reasonable quarantine path for D-07's FAIL branch (reuses `NusRunner._stage_dir()`'s existing directory, keeps quarantined output away from `analysis/nmr_peaks/` so CASE globbing never accidentally picks it up) | Architecture Patterns | Low risk — this is explicitly "planner discretion" per CONTEXT.md; any consistent, forensically-inspectable location satisfies D-07. |
| A5 | `_detect_multiplicity_edited()` (currently module-private in `cli/pick.py`) should be promoted/exported for reuse by `nus/bridge.py` rather than reimplemented | Don't Hand-Roll | Low risk — a straightforward refactor (move or export), not a design gap; flagged so the planner doesn't miss that it's currently not importable from outside `cli/pick.py`. |

**If this table is empty:** N/A — see entries above; all five need explicit planner attention, none block planning outright.

## Open Questions (RESOLVED)

> Both questions are resolved by the Phase-99 plan set: Q1 → Plan 04 follows Rec 1 (qc.py pure/verdict-only, write+quarantine branching in `cli/nus.py::pipeline`); Q2 → Plan 02 follows Rec 2 (keyword glob `*HSQC*`/`*HMBC*`/`*COSY*`, enforced by the `! grep "_exp[0-9]"` acceptance gate). Retained below for provenance.

1. **(RESOLVED) What is the correct quarantine/write-boundary implementation shape — a `QcGate` class the `pipeline` command calls, or inline logic in `cli/nus.py::pipeline`?**
   - What we know: D-07 fixes the *policy* (write PASS/PARTIAL, quarantine+exit-1 on FAIL) and fixes *where* it lives (pipeline boundary, not `NusRunner`).
   - What's unclear: whether `nus/qc.py` should own the write-boundary function itself (e.g. `qc.write_or_quarantine(report, peaks, ...)`) or whether that logic belongs purely in the CLI command body (matching the `reconstruct` command's current thin-wrapper style).
   - Recommendation: keep `nus/qc.py` pure (compute `QcReport`, no file I/O beyond reading reference JSON); put the write/quarantine branching in `cli/nus.py::pipeline` — matches the existing `reconstruct` command's convention of thin CLI + fat library.

2. **(RESOLVED) Should `lucy nus qc <peaks-dir>` accept a directory of already-existing peak JSON files (D-08's literal contract) or a single experiment's JSON file?**
   - What we know: D-08 says "standalone `lucy nus qc <peaks-dir>`... independently runnable against arbitrary peak lists" and the QC-02 regression target is a *directory* containing `HSQC_exp3.json`/`HMBC_exp4.json`/`COSY_exp2.json` together (checks like coverage need all three cross-referenced, e.g. a carbon confirmed quaternary by HSQC absence might still show HMBC correlations).
   - What's unclear: exact glob pattern for locating the three experiment types within an arbitrary directory (filename convention isn't fully fixed — the known-bad fixtures use `{TYPE}_exp{N}.json`, but a fresh `pipeline` run's fixture naming should be verified for consistency).
   - Recommendation: accept a directory, glob-match on experiment-type keywords in filenames (`*HSQC*`/`*hsqc*`, similarly HMBC/COSY) rather than a hardcoded `_expN` suffix, so `lucy nus qc` works regardless of experiment numbering.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `nmrglue` | `nus/bridge.py` (`.ft2` reading), `nus/qc.py` (none directly) | ✓ (core dep, already installed) | git-pinned per `pyproject.toml` | — |
| NMRPipe + SMILE backend | `lucy nus pipeline` (via `NusRunner.reconstruct()`, Phase 98) | ✗ (confirmed not installed on this dev machine, per Phase 97/98 `lucy nus check` — real integration tests are `skipif`-guarded) | — | CI-safe unit tests exercise `bridge.py`/`qc.py` against fixture `.ft2`/JSON files with the backend fully mocked or bypassed; `lucy nus qc <peaks-dir>` itself has **no** backend dependency at all (peaks-dir-only contract, D-08) |
| Reference SQLite DB (`lucy database download`) | `detection.StatisticalDetector` (tier-2 fallback path, Pitfall 1) | Not verified this session — assume same as other phases (project-wide prerequisite per repo `CLAUDE.md`) | — | If absent, tier-2 fallback simply has no data either — degrades to tier-3 ("insufficient reference data") automatically, no special-casing needed |

**Missing dependencies with no fallback:**
- None. `lucy nus qc` (the QC-02 regression-proof command) has zero external-tool dependency by design (D-08's peaks-dir-only contract). `lucy nus pipeline` degrades gracefully to `skipif`-guarded integration tests when the backend is absent, matching Phase 98's established D-04 test strategy.

**Missing dependencies with fallback:**
- NMRPipe+SMILE backend — mocked/skipped in unit tests, real backend only needed for the actual end-to-end `pipeline` run (out of this research's CI-verification scope).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (repo-installed) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["src"]` |
| Quick run command | `pytest tests/nus/ -x -q` |
| Full suite command | `pytest` (1338 tests collected at research time, all passing per Phase 98 close) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PICK-01 | Bridge builds `Spectrum2D` from a fixture `.ft2`, calls `PeakPicker2D` unmodified, emits schema-identical per-peak keys | unit | `pytest tests/nus/test_bridge.py -x` | ❌ Wave 0 |
| PICK-02 | `lucy nus pipeline <expdir>` CLI wires all stages, `--format json` on `qc`/`pipeline` | unit (mocked backend) + `skipif`-guarded integration | `pytest tests/nus/test_cli_pipeline.py -x` | ❌ Wave 0 |
| PICK-03 | Metadata block (backend/iterations/verdict) present, per-peak `confidence` derived from verdict (D-06) | unit | `pytest tests/nus/test_bridge_metadata.py -x` | ❌ Wave 0 |
| QC-01 | Each of the 6 check functions computes the documented algorithm on synthetic peak-list fixtures (clean-pass and violation-trip cases per check) | unit | `pytest tests/nus/test_qc_checks.py -x` | ❌ Wave 0 |
| QC-02 | `lucy nus qc` on the real `HSQC_exp3.json`/`HMBC_exp4.json`/`COSY_exp2.json` (known-bad, external path) reports FAIL; on a **hand-authored synthetic clean fixture** reports PASS | integration (real fixture, external path, no `skipif` needed — these JSON files are small and can be copied into `tests/fixtures/nus/known_bad_peaks/`) + unit (synthetic clean) | `pytest tests/nus/test_qc_regression.py -x` | ❌ Wave 0 |
| QC-03 | `pipeline` on a FAIL verdict exits non-zero, writes nothing to `analysis/nmr_peaks/`, writes to quarantine path instead | unit (mocked reconstruction+peak-pick, real QC-gate logic) | `pytest tests/nus/test_write_boundary.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/nus/ -x -q`
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work 99`

### Wave 0 Gaps

- [ ] `tests/fixtures/nus/known_bad_peaks/` — copy of the real `HSQC_exp3.json`/`HMBC_exp4.json`/`COSY_exp2.json` (small files, ~5-13 KB each per `ls -la` — safe to commit into the repo fixture tree, unlike the large `ser` binaries Phase 98 deliberately excluded) — covers QC-02's FAIL side
- [ ] `tests/fixtures/nus/clean_peaks_synthetic/` — hand-authored synthetic peak lists respecting §8's criteria (15 protonated carbons each with correct multiplicity/1-2 correlations, 5 quaternaries with zero HSQC correlations, no ridge clustering, COSY diagonal-symmetric pairs) — covers QC-02's PASS side. **This is the load-bearing new fixture for this phase** — without it, QC-02's "PASS on a clean reconstruction" cannot be proven at all in Phase 99 (no real clean reconstruction exists until Phase 100).
- [ ] `tests/nus/test_qc_checks.py` — one test class per check (6), each with a violation-trip case + a clean-pass case
- [ ] `tests/nus/test_bridge.py` — `.ft2` → `Spectrum2D` construction (may need a minimal synthetic NMRPipe-format fixture, or reuse Phase 98's `make_valid_intermediate`-style factories from `tests/nus/conftest.py`)
- [ ] Framework install: none — pytest already present, no new test-only dependency needed

## Security Domain

`security_enforcement` is absent from `.planning/config.json` → treat as enabled. This is a local CLI tool operating on filesystem paths and JSON files, not a network-facing service — most ASVS categories are not applicable, but input validation on file paths/JSON parsing is relevant given this phase reads externally-produced files (reconstruction output, arbitrary peak-list directories via `lucy nus qc <peaks-dir>`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local CLI tool, no auth boundary |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Pydantic v2 models (`QcVerdict`/`QcCheckResult`/`QcReport`) validate all QC-gate data structures; `json.loads()` on peak-list files should be wrapped with a clear error message on malformed JSON (matches existing `read_nus_params`/`read_nus_schedule` fail-loud convention) rather than propagating a raw `JSONDecodeError` |
| V6 Cryptography | no | N/A — no secrets/crypto in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `lucy nus qc <peaks-dir>` glob-reading arbitrary attacker-controlled paths | Tampering/Information Disclosure (low severity — local single-user CLI tool, not a service) | `Path(peaks_dir).resolve()` (existing project convention, e.g. `cli/nus.py`'s `reconstruct` command) before any glob; no `shell=True`/string-interpolated subprocess calls introduced by this phase (bridge/QC are pure-Python, no new subprocess calls at all) |
| Malformed/adversarial JSON peak-list content (e.g. non-numeric `c13_ppm`) crashing the QC gate mid-report | Denial of Service (local) | Pydantic field validation on `QcCheckResult` inputs; wrap per-file JSON parsing in a try/except that reports a clear per-file error in the `QcReport` rather than crashing the whole `qc`/`pipeline` command |

## Sources

### Primary (HIGH confidence — direct code inspection this session)

- `src/lucy_ng/processing/peak_picker_2d.py` — `PeakPicker2D.pick_peaks()` full signature/behavior
- `src/lucy_ng/cli/pick.py` — exact per-peak JSON shape (HSQC/HMBC), `_detect_multiplicity_edited()`
- `src/lucy_ng/models/spectrum.py` — `Spectrum2D` field contract
- `src/lucy_ng/nus/runner.py`, `src/lucy_ng/nus/postprocess.py`, `src/lucy_ng/models/nus.py`, `src/lucy_ng/cli/nus.py` — Phase 97/98 delivered code, read in full
- `src/lucy_ng/readers/bruker.py` (`read_2d`) — the nmrglue `guess_udic`/`uc_from_udic` pattern this phase's bridge mirrors for `.ft2`
- `src/lucy_ng/detection/detector.py`, `src/lucy_ng/detection/models.py`, `src/lucy_ng/database/schema.py` — confirmed `detect_hybridisation()` returns sp3/sp2/sp1 only, no CH-count field
- `src/lucy_ng/processing/dept_guided_picker.py`, `src/lucy_ng/analysis/hydrogen_budget.py` — confirmed real prot/quaternary classification exists ONLY via DEPT, nowhere else
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/nmr_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2,13C_exp6_narrow,13C_exp7_wide,1H_exp1}.json` — direct data inspection (Python one-liners this session) producing all concrete calibration numbers cited above
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` §8/§10 — the authoritative check-definition source
- `.planning/research/SUMMARY.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` — milestone-level research (Pitfall 16, Architecture's `nus/bridge.py` section)
- Repo-wide grep confirming no Python consumer of `analysis/nmr_peaks/*.json` exists outside the CASE LLM agent path (Pitfall 6)

### Secondary (MEDIUM confidence)

- `.claude/agents/lucy-lsd-engineer.md`, `.claude/agents/lucy-devils-advocate.md`, `.claude/agents/lucy-nmr-chemist.md` — FIX-10 confirmed as a skill-level/agent-instruction convention, not a Python function; grounds QC-03's "extending FIX-10" as a data-layer analogy, not literal code extension

### Tertiary (LOW confidence)

- Recommended numeric thresholds (`ridge_fraction > 0.5`, HSQC-coverage floor 0.8) — grounded in the one known-bad fixture available, explicitly flagged as unvalidated against any clean reconstruction (Assumptions Log A1/A2)

## Metadata

**Confidence breakdown:**
- Standard stack / reuse patterns: HIGH — every component is existing, tested code, directly read this session
- Architecture (bridge + QC module boundaries): HIGH — directly grounded in `_perform_ranking()`/`BrukerReader.read_2d()` precedents and D-07/D-08's explicit CLI contract
- QC check algorithms (design): MEDIUM — six algorithms are concretely specified and grounded in real fixture data, but this is genuinely new code (per SUMMARY.md's own flag) with no prior implementation to verify against
- QC numeric thresholds: LOW-MEDIUM — calibrated only against the known-bad (FAIL) side; the PASS side has no real fixture until Phase 100, explicitly flagged in Assumptions Log

**Research date:** 2026-07-16
**Valid until:** Effectively until Phase 100 produces a real clean C20H32O2 reconstruction (at which point A1/A2's thresholds MUST be re-validated) — no external-library staleness risk since no new dependency was introduced.
