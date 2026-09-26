# Phase 98: Reconstruction + Processing - Research

**Researched:** 2026-07-13
**Domain:** Headless NMRPipe+SMILE subprocess orchestration for Bruker NUS 2D reconstruction (bruk2pipe → nusExpand.tcl → SMILE → FT/phase/baseline), FnMODE-aware (echo-antiecho vs QF), fail-loud per-stage wrapper
**Confidence:** MEDIUM-HIGH — SMILE CLI flags and worked pipeline scripts are now directly verified against the official SMILE manual (primary source, fetched in this research pass, resolving the milestone research's own flagged gap). Architecture/backend/pitfalls are HIGH (inherited from milestone research + this repo's own code). The single biggest remaining uncertainty is empirical (does SMILE clear the quality bar on this compound's data), which only an actual reconstruction run can answer — that is explicitly out of this phase's automatable-plumbing scope and belongs to the Phase 98 exit criterion / Phase 100 validation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Pipeline orchestration & subprocess strategy (D-01):** Drive the NMRPipe/SMILE chain
**Python-orchestrated, one external subprocess per stage** (`bruk2pipe` → `nusExpand.tcl` →
SMILE → FT/PS/baseline), each writing an intermediate file that the next stage reads — **not**
as a single csh pipe chain. Rationale: csh-piped NMRPipe stages do not reliably propagate
per-stage exit codes (Pitfall 14), which is exactly what RECON-04 must guard against; running
each stage as its own subprocess makes the fail-loud check (exit code **and** output-file
non-emptiness) native and per-stage. Command strings stay logged/auditable. Follow the
`LSDRunner` subprocess/`is_available()` precedent for the wrapper shape (`lsd/runner.py`).

**Phasing & ppm calibration (D-02):** **Deterministic known-phase, no blind auto-phase**, with
an **optional CLI override**. F2 phase from the reliable 1D reference (P0/P1); F1 default for
echo-antiecho HSQC/HMBC (standard 0/0); COSY processed in **magnitude mode** (no phase). ppm
axes are **reversed and calibrated against the §10 ground-truth 1D shifts** (RECON-02,
Pitfall 6) — calibration cross-check is the trusted 1D data, not the reconstruction itself.

**Intermediate-file location & retention (D-03):** Reconstruction intermediates
(`test.fid`/converted FID, `nusExpand` output, `.ft2`, etc.) are written to a **persistent
per-experiment subfolder under `analysis/`** (e.g. `analysis/nus_recon/<expN>/`) and **kept**.
A cleanup flag may be offered, default **keep**.

**Test strategy (D-04):** **Mocks in CI + a backend-gated integration test against the
external data path.** CI-safe unit tests cover the orchestration logic with the subprocess
boundary mocked: the hard F2-before-F1 ordering gate (an out-of-order attempt must raise
before any reconstruction runs), the fail-loud wrapper (a deliberately truncated/empty
intermediate must abort), and the FnMODE branching (echo-antiecho vs QF). A real end-to-end
integration test drives the actual `bruk2pipe`→SMILE chain but points at the **external**
C20H32O2 data path and is `skipif`-guarded when the backend or data is absent. **Do not copy
the large `ser` binaries into the repo.**

### Claude's Discretion

- **RECON-05 knob defaults** — iteration-count upper bound, threshold, virtual-echo toggle
  default, exposed as CLI flags.
- GRPDLY/DECIM digital-filter removal method (bruk2pipe built-in vs an nmrPipe stage) —
  must be correct, not necessarily user-facing.
- Exact `nus/runner.py` API surface, how the F2-before-F1 ordering gate is mechanically
  enforced, and the split of responsibilities between `runner.py` and `postprocess.py`.
- Apodization/ZF parameter choices (SP window etc.) — standard NMRPipe processing defaults.

### Deferred Ideas (OUT OF SCOPE)

- Peak-pick bridge → `analysis/nmr_peaks/*.json` and the mandatory automated QC gate →
  **Phase 99**.
- Full platform preflight matrix / Rosetta / csh availability probe → **Phase 100 / PORT**.
- End-to-end §8-gate validation on C20H32O2 and CASE convergence → **Phase 100 / VAL**.
- hmsIST/mddnmr fallback backends → deferred (v1.x).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RECON-01 | `lucy nus reconstruct <expdir>` runs bruk2pipe → nusExpand.tcl → SMILE fully automatically, no GUI step | § SMILE-manual-verified pipeline scripts (Standard Stack, Code Examples); § FnMODE-dependent stage ORDER correction (Critical Finding 1) |
| RECON-02 | F2-before-F1 hard ordering gate; reversed, 1D-calibrated ppm axes | § Architecture Patterns (Pattern 1: ordering gate); § Common Pitfalls (Pitfall: ppm calibration); § Phasing discussion |
| RECON-03 | FnMODE-aware (echo-antiecho vs QF) at 25%/33% density from one entrypoint | § Critical Finding 1 (FnMODE-dependent expand-vs-convert order); § Code Examples (per-FnMODE bruk2pipe/SMILE invocations) |
| RECON-04 | Fail-loud wrapper: exit code + output-file non-emptiness, every external call | § Architecture Patterns (Pattern 2: fail-loud `run_stage()`); § Don't Hand-Roll; § Testing strategy |
| RECON-05 | Iteration/threshold/virtual-echo CLI flags with sane, convergence-based defaults | § Standard Stack (SMILE Parameters table, `-maxIter`/`-thresh`/`-nSigma`/`-sigma`); § Recommended defaults |
</phase_requirements>

## Summary

Phase 98 wires the actual external NMRPipe+SMILE binary chain behind `lucy nus reconstruct`,
consuming Phase 97's already-parsed `NusAcquisitionParams`/`NusSchedule` (no second parse pass)
and producing a processed, phase-corrected, ppm-calibrated 2D spectrum in NMRPipe format for
each of the three C20H32O2 NUS experiments (COSY exp2 QF/magnitude, HSQC exp3 and HMBC exp4
echo-antiecho). This research fetched the official SMILE User's Manual directly (a gap the
milestone-level research had flagged as unverified — PDF fetch previously failed) and extracted
concrete, primary-source-verified command-line flags and two complete worked pipeline scripts
(2D TROSY 20% NUS, CT-HSQC-as-LP-alternative). This resolves the open flag-syntax question and
surfaces one important correction the milestone research did not have: **the bruk2pipe ↔
nusExpand.tcl invocation ORDER is FnMODE-dependent**, not a fixed sequence — the manual's own
recommended (and only fully worked) approach runs `nusExpand.tcl` **before** `bruk2pipe` for
phase-sensitive (echo-antiecho) experiments, but explicitly states this "does not work for any
data acquired in magnitude mode (QF flag on Bruker)" — i.e. COSY (exp2, FnMODE=1) needs the
**reverse** order (`bruk2pipe` first, expansion after). `nus/runner.py` must branch this
ordering by FnMODE, not assume one fixed 4-stage sequence for all three experiments.

The fail-loud wrapper (RECON-04) does not need to eliminate NMRPipe's own internal `|`
function-chaining (that is idiomatic, expected NMRPipe usage and rewriting it away would be
hand-rolling); the correct unit of atomicity is **one `subprocess.run()` call per pipeline
stage** (bruk2pipe / nusExpand.tcl / SMILE / post-processing), with each stage's output file
independently verified (exists, non-empty, and where computable, of the expected shape via
`nmrglue.fileio.pipe.read()`) in addition to checking the subprocess return code — this is the
concrete, correct interpretation of D-01 and directly closes Pitfall 14.

**Primary recommendation:** Build `nus/runner.py` as a thin `NusRunner` class mirroring
`LSDRunner` (classmethod-style `is_available()`/`SEARCH_PATHS` already exist in
`NmrPipeSmileBackend`; add a `run_stage()` instance/module helper that wraps every
`subprocess.run()` call with exit-code + output-file-non-emptiness checks), branch the
bruk2pipe/nusExpand ordering by `params.fnmode_f1` (QF vs echo-antiecho), read GRPDLY/DECIM/
byte-order/NusTD-vs-TD directly from the already-parsed `NusAcquisitionParams`/`NusSchedule`
(zero re-parsing), default SMILE knobs to `-nSigma 5-6` / `-thresh 0.8` / `-maxIter 200-500` as
an **upper bound** (never the sole stopping criterion — the manual's own `-sigma`/`-nSigma`
noise-threshold convergence check is the real stopping rule), and treat F2/F1 phase values as
CLI-overridable named constants determined once per acquisition configuration (not
algorithmically derived) rather than any blind auto-phase search.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bruker→NMRPipe conversion (bruk2pipe) | External tool integration (`nus/backends/nmrpipe_smile.py`) | — | Deterministic format conversion; delegated to the external binary per the locked backend decision, never re-implemented |
| NUS sparse→full-grid expansion (nusExpand.tcl) | External tool integration (`nus/backends/nmrpipe_smile.py`) | — | Same — a mechanical grid-fill operation with a documented, non-trivial FnMODE-order subtlety (Critical Finding 1) |
| Indirect-dimension reconstruction (SMILE) | External tool integration (`nus/backends/nmrpipe_smile.py`) | — | The algorithmic core; explicitly never reimplemented (milestone-level decision, reaffirmed here) |
| Stage orchestration + fail-loud wrapper | Application logic (`nus/runner.py`) | — | Pure Python control flow: sequencing, per-stage subprocess invocation, exit-code/file checks, FnMODE branching — no NMR domain math |
| Apodization/ZF/FT/phase/baseline | External tool integration (`nus/postprocess.py`, still nmrPipe subprocess) | Application logic (parameter selection) | The actual DSP math stays in nmrPipe (backend-delegated); `postprocess.py` only selects/threads parameters (P0/P1, window function) computed/looked-up in Python |
| ppm-axis reversal + 1D calibration cross-check | Application logic (`nus/postprocess.py` / a small calibration helper) | — | Simple arithmetic (SF/OFFSET/O1 → ppm scale) plus a comparison against the already-parsed §10 ground truth; no external tool needed for this part |
| CLI surface (`reconstruct` command) | Application logic (`cli/nus.py`) | — | Thin Click wrapper, deferred imports, mirrors `cli/webview.py`/existing `cli/nus.py` convention |

## Standard Stack

### Core

| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| NMRPipe | current (post-2015-11-24 SMILE-plugin release) | FT/apodization/phase/baseline processing engine; hosts the SMILE plugin | De-facto standard NUS/NMR processing pipeline; already the locked backend (Phase 97 research) `[CITED: spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf]` |
| SMILE (`nmrPipe -fn SMILE`) | plugin bundled with NMRPipe, "plugin.smile.tZ" (File 4) | Sparse Multidimensional Iterative Lineshape Enhanced — indirect-dim reconstruction | Most literature-validated NUS reconstruction algorithm; runs as an NMRPipe plugin function (`nusPipe` executable), never a standalone `which()`-able binary `[CITED: SMILE manual §1-2]` |
| `bruk2pipe` | bundled with NMRPipe | Bruker→NMRPipe binary format conversion | Standard NMRPipe Bruker converter, already detected in Phase 97 (`NmrPipeSmileBackend.REQUIRED_TOOLS`) `[VERIFIED: repo code]` |
| `nusExpand.tcl` | bundled with NMRPipe (Delaglio, released alongside SMILE) | Sparse→full-grid NUS schedule expansion (zero-fill on schedule) | Purpose-built companion tool to SMILE; already detected in Phase 97 `[CITED: SMILE manual §1]` |
| `nmrglue` | 0.12-dev (git master; already a core dependency — see `pyproject.toml` comment on the NumPy 2 compatibility pin) | Reading NMRPipe-format (`.fid`/`.ft2`) files back into Python for the fail-loud non-emptiness/shape check | Already installed and used throughout this codebase (`readers/bruker.py`, Phase 97's `nus/params.py`); `nmrglue.fileio.pipe.read()` is a pure-Python NMRPipe-format reader with zero new dependency `[VERIFIED: local `python3 -c "import nmrglue"` — version 0.12-dev]` |

**No new pip-installable Python packages are required for this phase.** The `[nus]` extra
(`pyproject.toml`) remains empty, exactly as Phase 97 left it — this phase's work is 100%
external-binary subprocess orchestration (bruk2pipe/nusExpand.tcl/SMILE) plus pure-Python
control flow reusing already-core `nmrglue`. Do not add a pip dependency to satisfy this phase.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `shutil` (stdlib) | — | `run_stage()` fail-loud wrapper's own use of the already-detected `REQUIRED_TOOLS` paths | Already used in `NmrPipeSmileBackend`/`LSDRunner` |
| `subprocess` (stdlib) | — | Per-stage external tool invocation | `LSDRunner` precedent: fixed arg list, `capture_output=True`, explicit `timeout`, never `shell=True` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-stage `subprocess.run()` + independent output-file check | A single monolithic `.com` csh script piping all 4 stages together | Rejected by D-01 explicitly: a single long `|` chain re-introduces Pitfall 14 (only the last command's exit code is visible); the per-stage boundary is what makes the fail-loud check meaningful |
| nmrPipe's own FT/PS/POLY for post-processing | `nmrglue.process.pipe_proc` (`ft`, `ps`, `cbf`, `med` — pure-Python re-implementations of the same NMRPipe processing verbs, already importable, zero subprocess) | `pipe_proc` is a legitimate, already-available pure-Python alternative for the FT/phase/baseline stage specifically (it reads/writes the same NMRPipe binary format nmrglue already handles) and would shrink the fail-loud-wrapper's subprocess surface for that one stage. **Recommendation: do not switch to it in this phase** — D-01 already scopes "FT/PS/baseline" as one of the four subprocess stages, and mixing "some stages via nmrPipe subprocess, others via nmrglue Python calls" adds inconsistency without a clear correctness win; keep it as a documented, low-risk future simplification (flag in Assumptions Log, not adopted). |
| SMILE knob CLI naming (`--iterations`, `--threshold`, `--virtual-echo`) | Exposing raw SMILE flag names 1:1 (`--max-iter`, `--thresh`, `--n-sigma`) | Recommend exposing lucy-ng's own descriptive flag names (RECON-05 says "iteration count, threshold, virtual-echo toggle") that map internally to SMILE's `-maxIter`/`-thresh`/`-nSigma`+`-EA` — clearer for a non-NMRPipe-expert caller, and insulates the CLI contract from SMILE's own flag renames across versions |

**Installation:** No new installs beyond what Phase 97 already established (`lucy nus check`
verifies `nmrPipe`/`bruk2pipe`/`nusExpand.tcl` on PATH + the SMILE plugin capability probe).

**Version verification:** N/A — no new pip packages. The external NMRPipe/SMILE binary
versioning is governed entirely by the user's own NMRPipe install (free registration,
`~/.nmrpipe`), matching the LSD precedent in `CLAUDE.md`'s "Local prerequisites" section.

## Package Legitimacy Audit

**Not applicable this phase.** No new pip-installable Python packages are introduced. The
external tools this phase drives (`nmrPipe`, `bruk2pipe`, `nusExpand.tcl`, the SMILE plugin)
are not PyPI packages — they are large, registration-gated academic binary distributions
detected at runtime via `shutil.which()`/subprocess capability probes (Phase 97's
`NmrPipeSmileBackend`), exactly like the existing `LSDRunner` pattern. There is nothing for
`slopcheck`/`npm view`/`pip index versions` to check. If a future phase adds a genuinely
pip-installable dependency to the `[nus]` extra (e.g. a QC-plotting library in Phase 99), run
the full Package Legitimacy Gate protocol at that time.

## Critical Finding 1: bruk2pipe ↔ nusExpand.tcl order is FnMODE-dependent (verified, SMILE manual §4)

This is the single most important correction this research surfaces relative to the phase
description's implied fixed order ("Bruker→NMRPipe conversion (bruk2pipe), NUS expansion
(nusExpand.tcl), SMILE reconstruction").

**What the SMILE manual (official, primary source) actually says** `[CITED: smile_manual.pdf §4]`:

> "SMILE requires the non-uniformly sampled Bruker or Varian data to be sorted and expanded,
> with the unsampled points filled with zeros. Although this can be done using the
> nusExpand.tcl script either before or after the time-domain data is converted to the NMRPipe
> format, doing this prior to the data conversion is advantageous because the expanded data can
> be converted by a conventional script without any unusual changes. For example, if any
> indirect dimension is acquired with the Echo-AntiEcho quadrature mode, the time-domain data
> reshuffling can be done directly during the conversion. If the conversion is done before the
> expansion, the data must be first treated in a complex mode, and then be sorted and expanded,
> followed by an NMRPipe macro to extract the real and imaginary components from each
> Echo-AntiEcho pair... **another disadvantage is that this approach does not work for any data
> acquired in the magnitude mode (QF flag on Bruker). However, as SMILE is intended for
> phase-sensitive experiments, it should not be a problem to always run nusExpand.tcl before the
> data conversion**, although the other approach can be used too."

**Concrete implication for `nus/runner.py`:**

- **exp3 (HSQC, FnMODE=6 echo-antiecho) and exp4 (HMBC, FnMODE=6 echo-antiecho):** run
  `nusExpand.tcl` **first** (on the raw Bruker `ser`+`nuslist`, producing an expanded
  `ser_full`), **then** `bruk2pipe` (converting the already-sorted/expanded `ser_full`, which
  correctly handles the Echo-AntiEcho N/P reshuffling *during* conversion). This is the fully
  worked, officially-documented path (both 2D and 3D examples in the manual use exactly this
  order for their echo-antiecho indirect dimensions).
- **exp2 (COSY, FnMODE=1, magnitude/QF mode):** the manual explicitly states the
  expand-then-convert approach "does not work" for magnitude-mode Bruker data. Only the
  reverse order (`bruk2pipe` first, `nusExpand.tcl` on the resulting `.fid` afterward, or an
  equivalent NMRPipe-macro-based post-conversion expansion) is viable — **the manual does not
  give a fully worked script for this branch** (COSY/magnitude is explicitly out of SMILE's
  primary intended-use envelope: "SMILE is intended for phase-sensitive experiments"). Treat
  this as a **flagged assumption** (see Assumptions Log A1) requiring a short implementation-time
  spike: confirm the exact convert-then-expand invocation order for exp2 empirically against
  the real C20H32O2 data before committing to a hard-coded per-FnMODE branch in `runner.py`.

**Design consequence:** `nus/runner.py` must branch the **stage order itself** on
`params.fnmode_f1` (using the already-shared `REAL_FNMODES`/`COMPLEX_FNMODES` constants from
`models/nus.py`), not just branch processing parameters within a fixed stage sequence. This is
a materially different design than a single linear 4-stage pipeline function — recommend a
small `_ordering_for_fnmode(fnmode: int) -> Literal["expand_first", "convert_first"]` helper (or
equivalent) that `runner.py` consults before dispatching stage 1/2, with a hard
`NotImplementedError` for any FnMODE outside the two branches actually verified here (mirrors
the existing `expected_sample_count()` refuse-to-guess convention in `nus/schedule.py`).

## Critical Finding 2: NusTD (full grid), not TD (sparse), drives bruk2pipe's F1 conversion size

The SMILE manual's own worked `bruk2pipe` invocation (2D TROSY example, run **after**
`nusExpand.tcl` has already produced the expanded `ser_full`) uses `-yN 3700 -yT 1850` — i.e.
the **full expanded grid size**, not the original sparse `acqu2s TD`. Concretely, for this
project's own data (already parsed into `NusAcquisitionParams`/`NusSchedule` in Phase 97):

| Exp | `f1_td` (acqu2s TD, sparse) | `nus_td` (full grid) | bruk2pipe `-yN`/`-yT` should use |
|-----|------------------------------|------------------------|------------------------------------|
| exp3 HSQC | 100 | 400 | `nus_td` (400 real points / 200 complex pairs) |
| exp4 HMBC | 232 | 700 | `nus_td` (700 real points / 350 complex pairs) |
| exp2 COSY | 188 | 750 | `nus_td` (750 real points, QF real-only) |

**This must be read from `NusSchedule.nus_td` / `NusAcquisitionParams.nus_td` (already parsed,
Phase 97), never re-derived from `max(nuslist)+1`** — this repeats the existing
`nus/schedule.py` docstring warning (the real-vs-complex grid-scale note) one level up into the
conversion-parameter selection, and is exactly the kind of "silent, graceful degradation into a
plausible-looking wrong reconstruction" failure Pitfall 2 describes if gotten wrong.

## Architecture Patterns

### System Architecture Diagram

```
Bruker ser + nuslist + acqus/acqu2s (per experiment dir: expdir/2, expdir/3, expdir/4)
    │
    ▼
[Phase 97, ALREADY BUILT — consumed, never re-parsed]
NusAcquisitionParams (nus/params.py) ──┐
NusSchedule (nus/schedule.py) ─────────┤
    │                                   │
    ▼                                   ▼
nus/runner.py: NusRunner.reconstruct(expdir)
    │
    ├─ 1. read params/schedule once (Phase 97) + branch on params.fnmode_f1 (Critical Finding 1)
    │
    ├─ 2. F2-before-F1 ordering gate (RECON-02, hard precondition — _resolve_f2_plan(params)
    │      raises BEFORE any reconstruction subprocess runs if the direct-dimension phase/apod
    │      plan is unresolved). This gate is now PHYSICALLY correct, not just symbolic: SMILE
    │      requires the direct (F2) dimension to be fully processed and transposed first.
    │
    ├─ 3. backend.convert(): FnMODE-branched Bruker→NMRPipe conversion + NUS expansion
    │      ├─ echo-antiecho (FnMODE=6, HSQC/HMBC): nusExpand.tcl FIRST → bruk2pipe SECOND
    │      └─ QF/magnitude (FnMODE=1, COSY):        bruk2pipe FIRST → expand SECOND (spike, A1)
    │      └─► analysis/nus_recon/<expN>/converted.fid   (fail-loud run_stage)
    │
    ├─ 4. postprocess.process_direct(): DIRECT-dimension (F2) processing — apod/ZF/FT/
    │      PS[deterministic p0/p1]/POLY/EXT, THEN transpose (TP)
    │      └─► analysis/nus_recon/<expN>/f2_processed.fid   (SMILE's ACTUAL input — a transposed,
    │          F2-processed FID, NOT a raw time-domain FID; fail-loud run_stage)
    │      ▲ This step is the literal, mechanical enforcement of RECON-02's F2-before-F1 gate —
    │        SMILE manual §4/§6.1: "the direct dimension must be first apodized, zero filled,
    │        Fourier transformed, and phased... before... SMILE... can be called."
    │
    ├─ 5. backend.reconstruct_indirect(): run_stage("nmrPipe -fn SMILE ...") on the transposed
    │      F2-processed FID ──► analysis/nus_recon/<expN>/reconstructed.ft1
    │        │ (fail-loud; SMILE knobs: -maxIter, -thresh, -nSigma/-sigma, -EA per axis)
    │
    ├─ 6. postprocess.process_indirect(): post-SMILE INDIRECT-dimension (F1) processing —
    │      ZF/FT/PS[deterministic p0/p1], final transpose (TP), reversed 1D-calibrated ppm axes
    │        └─► analysis/nus_recon/<expN>/processed.ft2 (fail-loud)
    │
    └─ 7. Return NusReconstructionResult (backend, params used, stage log paths, output file)
              — consumed by Phase 99's nus/bridge.py (NOT built in this phase)
```

### Recommended Project Structure

```
src/lucy_ng/nus/
├── params.py            # EXISTING (Phase 97) — unchanged
├── schedule.py           # EXISTING (Phase 97) — unchanged
├── runner.py             # NEW — NusRunner: stage orchestration, FnMODE branching,
│                         #   F2-before-F1 gate, owns analysis/nus_recon/<expN>/ lifecycle
├── postprocess.py        # NEW — process_direct() (F2 apod/ZF/FT/PS/POLY/EXT + TP, runs
│                         #   BEFORE SMILE) + process_indirect() (post-SMILE F1 ZF/FT/PS +
│                         #   final TP + ppm calibration) — still nmrPipe subprocess stages
└── backends/
    └── nmrpipe_smile.py  # EXISTING (Phase 97 detection) — ADD convert() (FnMODE-branched
                          #   conversion) + reconstruct_indirect() (SMILE on the transposed
                          #   F2-processed FID) methods here
```

### Pattern 1: Hard F2-before-F1 ordering gate as an explicit precondition, not implicit ordering

**What:** Before dispatching ANY subprocess for a given experiment, `runner.py` asserts that
the direct-dimension (F2) processing plan is fully resolved (phase P0/P1 known,
apodization/ZF parameters known) *before* the indirect-dimension (F1)/SMILE reconstruction
stage is invoked — implemented as an explicit precondition check/assertion at the top of the
orchestration function, not as "just call functions in this order and hope nothing calls out of
order."
**When to use:** Every `reconstruct()` call — this is SMILE's own hard requirement (§4: "Once
the data is expanded and converted, the direct dimension must be first apodized, zero filled,
Fourier transformed, and phased... before processing of the direct (fully sampled) dimension,
the SMILE function can be called").
**Example (illustrative, planner-owned exact API):**
```python
# Source: SMILE manual §4 ("direct dimension must be first apodized... phased...
# before... SMILE... can be called") + this repo's own LSDRunner precondition style
def reconstruct(self, expdir: Path) -> NusReconstructionResult:
    params = read_nus_params(expdir)   # Phase 97, no re-parse
    schedule = read_nus_schedule(expdir)
    stage_dir = self._stage_dir(expdir)

    # Hard precondition: F2 plan must exist before ANY subprocess is dispatched.
    f2_plan = self._resolve_f2_plan(params)   # raises if phase/apod params unresolved
    if f2_plan is None:
        raise RuntimeError(
            "F2 (direct-dimension) processing plan not resolved — refusing to start "
            "F1/SMILE reconstruction out of order (RECON-02 hard gate)."
        )
    ...
```
**Trade-offs:** Slightly more upfront validation code, but makes the ordering gate unit-testable
with zero backend installed (D-04) — a mocked `_resolve_f2_plan` returning `None` is exactly
the "out-of-order attempt must raise" test case CONTEXT.md's D-04 asks for.

### Pattern 2: `run_stage()` — the single fail-loud subprocess wrapper (RECON-04's correctness anchor)

**What:** One shared helper, used by every stage (`bruk2pipe`, `nusExpand.tcl`, SMILE,
post-processing), that (1) runs the subprocess with a fixed arg list (never `shell=True`,
mirrors `NmrPipeSmileBackend.smile_plugin_available()`'s own safety pattern), (2) checks
`returncode == 0`, (3) checks the declared output file exists and is non-empty, and (4) where
the expected NMRPipe-format shape is computable (via `nmrglue.fileio.pipe.read()`), verifies the
data array is non-empty and not all-zero — raising a clear, stage-named `RuntimeError` with
captured stderr on any failure, per D-01's rationale and Pitfall 14's mitigation.
**When to use:** Every external-tool invocation in this phase, with no exceptions — this is the
phase's own stated correctness anchor.
**Example:**
```python
# Source: Pitfall 14 mitigation + LSDRunner's subprocess.run(..., capture_output=True,
# text=True, timeout=..., cwd=...) precedent; nmrglue.fileio.pipe.read for the shape check
import subprocess
from pathlib import Path
import nmrglue as ng

def run_stage(name: str, argv: list[str], cwd: Path, expected_output: Path,
              timeout: int = 600) -> None:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(
            f"NUS stage '{name}' failed (exit {proc.returncode}): {proc.stderr[:500]!r}"
        )
    if not expected_output.exists() or expected_output.stat().st_size == 0:
        raise RuntimeError(
            f"NUS stage '{name}' reported success but output file "
            f"{expected_output} is missing or empty — refusing to continue "
            "(csh-piped NMRPipe stages can silently pass through truncated data, Pitfall 14)."
        )
    if expected_output.suffix in {".fid", ".ft2"}:
        _dic, data = ng.fileio.pipe.read(str(expected_output))
        if data.size == 0 or not data.any():
            raise RuntimeError(
                f"NUS stage '{name}' output {expected_output} parses but is all-zero/empty "
                "data — treat as a hard failure, not a legitimate empty result."
            )
```
**Trade-offs:** The `nmrglue.fileio.pipe.read()` shape/non-zero check adds a small per-stage
import/parse cost but is the concrete, already-available implementation of the "expected byte
size derivable from point counts × dtype size" check Pitfall 11/14 call for — no new dependency.

### Pattern 3: FnMODE-driven per-experiment recipe table, not per-experiment if/else sprawl

**What:** A small, explicit lookup structure (e.g. a `dataclass`/`NamedTuple` keyed by
`fnmode_f1`) that captures, per FnMODE, the four things that differ: (a) expand-vs-convert
stage order (Critical Finding 1), (b) `bruk2pipe -yMODE` value, (c) whether F1 phase correction
applies at all (COSY = magnitude, no phase) or a fixed default applies (echo-antiecho), and
(d) whether SMILE's `-EA` flag is passed for that axis.
**When to use:** Central to RECON-03 ("FnMODE-aware... from one entrypoint").
**Trade-offs:** Slightly more indirection than inline branching, but makes "which FnMODE values
are actually supported" auditable in one place and gives the `NotImplementedError`-on-unknown-
FnMODE convention (already used in `nus/schedule.py`) a natural home in this module too.

### Anti-Patterns to Avoid

- **Eliminating NMRPipe's own internal `|` function-chaining entirely:** D-01's "one subprocess
  per stage" means one `subprocess.run()` call per *pipeline stage* (bruk2pipe / nusExpand.tcl /
  SMILE / post-processing), not one call per individual NMRPipe function. The manual's own
  post-SMILE processing script chains `SP → ZF → FT → PS → POLY` inside a single `.com`/csh
  invocation — this is idiomatic NMRPipe usage, not a violation of D-01, provided the *stage's*
  own final output file is independently verified (Pattern 2). Rewriting this as N separate
  Python-invoked single-function subprocess calls would be non-standard NMRPipe usage and adds
  no correctness benefit over the output-file check.
- **Re-deriving `n_sampled`/grid size from `nuslist` contents:** never infer full-grid size from
  `max(nuslist)+1` — always read `NusSchedule.nus_td` (Critical Finding 2, repeating Phase 97's
  own documented warning).
- **Blind/iterative auto-phase search:** explicitly rejected by D-02 and Pitfall 10 — F2 phase
  is a fixed, CLI-overridable constant validated against the 1D reference, never a numerical
  search over the reconstructed (non-linear, CS/IST-processed) data.
- **Treating a fixed `-maxIter` as the stopping rule:** per RECON-05 and the Technical-Debt
  table, `-maxIter` is an upper bound only; the real stopping condition is SMILE's own
  `-sigma`/`-nSigma` noise-threshold convergence check (§ Recommended Defaults below).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sparse→full-grid NUS expansion | A custom Python zero-fill-by-schedule routine | `nusExpand.tcl` (already detected, Phase 97) | Purpose-built, SMILE-paired tool with documented FnMODE-specific behavior (Critical Finding 1); a hand-rolled version reproduces exactly the ad-hoc per-column IST bug class this milestone exists to fix |
| Indirect-dimension CS/IST reconstruction | Any Python sparse-recovery implementation | `nmrPipe -fn SMILE` | Milestone-level decision, reaffirmed; no mature pip package exists, and this project's own prior hand-rolled attempt is the documented root-cause failure |
| Digital-filter (GRPDLY) removal | A custom integer-truncation shift | `bruk2pipe -grpdly <value>` (built-in, confirmed via the manual's own worked scripts — always passes the exact non-integer `GRPDLY` value from `acqus`) | GRPDLY is non-integer (67.985...) here; bruk2pipe's own interpolation-aware removal is the standard, verified path — Pitfall 3's discretion item is resolved: use bruk2pipe's built-in flag, not a separate nmrPipe stage |
| NMRPipe-format file reading (for the fail-loud shape check) | A custom binary parser for `.fid`/`.ft2` | `nmrglue.fileio.pipe.read()` (already a core dependency) | Already-verified, already-imported elsewhere in this codebase; no new dependency |
| Subprocess exit-code + output validation | Ad-hoc per-call try/except scattered across `runner.py`/`postprocess.py`/the backend module | One shared `run_stage()` helper (Pattern 2) | Single place to get the fail-loud contract right; every future stage (Phase 99's peak-picking, Phase 100's preflight) can reuse it |

**Key insight:** Every piece of actual NMR signal-processing math in this phase is delegated to
NMRPipe/SMILE/bruk2pipe/nusExpand.tcl — lucy-ng's own code in this phase is 100% orchestration,
sequencing, parameter selection, and validation. Any temptation to "just fix this one edge case
in Python" for a DSP step is exactly the anti-pattern that caused the 2026-07-09 failure.

## Common Pitfalls

(Full detail already researched at milestone level in `.planning/research/PITFALLS.md`,
Pitfalls 1–10 and 14 directly in-scope for this phase per CONTEXT.md's canonical refs. This
section adds phase-specific operational detail not already covered there.)

### Pitfall: FnMODE-dependent stage order silently "completing" in the wrong order

**What goes wrong:** Running `nusExpand.tcl` before `bruk2pipe` for COSY (QF/magnitude,
FnMODE=1) does not necessarily crash — it can produce a plausible-looking but incorrect
conversion, per the manual's own warning that this order "does not work" for magnitude data.
**Why it happens:** A single fixed 4-stage pipeline function, generalized from the
echo-antiecho-only worked examples in the manual, silently mis-orders the one FnMODE (QF) the
manual itself flags as an exception.
**How to avoid:** Branch stage order on `fnmode_f1` explicitly (Critical Finding 1 / Pattern 3);
add a regression test asserting the QF branch never calls `nusExpand.tcl` before `bruk2pipe`.
**Warning signs:** A COSY reconstruction with plausible cross-peak shapes but a systematically
wrong-looking symmetry/intensity pattern relative to the known aliphatic H-H network.

### Pitfall: bruk2pipe's F1 conversion size computed from sparse TD instead of NusTD

**What goes wrong:** Using `params.f1_td` (the sparse acquisition count) instead of
`params.nus_td` (full grid) for bruk2pipe's `-yN`/`-yT` after expansion silently truncates or
mis-shapes the converted FID.
**Why it happens:** `f1_td` and `nus_td` are both plausible-looking integers on the same
parameter model; picking the wrong one doesn't raise a type error.
**How to avoid:** Critical Finding 2 — always use `nus_td` for the post-expansion conversion
size; add an assertion/test using this project's own three real values (400/700/750).
**Warning signs:** A converted FID whose reported point count doesn't match the full,
zero-filled expanded schedule length.

### Pitfall: SMILE's `-maxIter` treated as the primary stopping criterion

**What goes wrong:** Reconstruction "completes" after exactly `-maxIter` iterations regardless
of whether the noise-threshold convergence (`-sigma`/`-nSigma`) was actually reached —
under-converging (residual ridges) if `-maxIter` is too low for this data's true convergence
point, or needlessly slow (though not incorrect) if set very high with a tight `-nSigma`.
**Why it happens:** `-maxIter`'s default (200) is a generic cross-dataset default, not tuned to
this compound's 25-33%-sampled, dynamic-range-heavy HSQC/HMBC data.
**How to avoid:** Set `-maxIter` as a generous upper bound (SMILE manual: "for the final
reconstruction, a high number of iterations is recommended... to ensure the iterative process
doesn't truncate prematurely" — the manual's own 3D/4D examples use 500-2048) and rely on
`-sigma`/`-nSigma` as the actual stopping rule; log the final iteration count reached
(`-report 1`'s `smile.log`) so under- vs at-convergence can be distinguished after the fact.
**Warning signs:** `smile.log` (if `-report 1`/`-report 2` is enabled) shows the reconstruction
ran to exactly `-maxIter` without the residual RMS approaching the input noise floor.

## Code Examples

Verified patterns from the official SMILE manual (primary source, fetched in this research
pass):

### Echo-AntiEcho branch: nusExpand.tcl BEFORE bruk2pipe (matches exp3 HSQC / exp4 HMBC, FnMODE=6)

```csh
#!/bin/csh
# Source: SMILE manual §6.1 (2D TROSY 20% NUS reconstruction worked example), p.14
nusExpand.tcl -mode bruker -sampleCount 370 -off 0 \
 -in ./ser -out ./ser_full -sample ./nuslist

bruk2pipe -in ./ser_full \
  -bad 0.0 -aswap -AMX -decim 1920 -dspfvs 20 -grpdly 67.9841918945312 \
  -xN            8192  -yN            3700  \
  -xT            4096  -yT            1850  \
  -xMODE         DQD   -yMODE  Echo-AntiEcho \
  -xSW       10416.667 -ySW       1818.182   \
  -xOBS        800.134 -yOBS        81.086   \
  -xCAR          4.868 -yCAR        118.782  \
  -xLAB             HN -yLAB             15N \
  -ndim              2 -aq2D          States \
  -out ./test.fid -verb -ov
```

- `-grpdly` is the **exact, non-integer** `GRPDLY` read straight from `acqus` (Pitfall 3,
  resolved: bruk2pipe's own built-in flag handles this — no separate digital-filter stage).
- `-yN`/`-yT` are the **full expanded grid** sizes (Critical Finding 2), not the sparse
  `acqu2s TD`.
- `-yMODE Echo-AntiEcho` is the literal string bruk2pipe accepts for this FnMODE
  `[VERIFIED: SMILE manual's own generated script]`.

### Reconstruction + post-processing (SMILE call, F2-before-F1 order enforced by the script itself)

```csh
#!/bin/csh
# Source: SMILE manual §6.1, p.14-15 (direct-dimension processing happens FIRST,
# then transpose, THEN SMILE — this is the F2-before-F1 gate, RECON-02, made concrete)
nmrPipe -in test.fid \
| nmrPipe  -fn POLY -time \
| nmrPipe  -fn GMB -lb -4 -gb 0.8 -c 1.0 \
| nmrPipe  -fn ZF -zf 2 -auto \
| nmrPipe  -fn FT \
| nmrPipe  -fn PS -p0 -24 -p1 0 -di \
| nmrPipe  -fn POLY -auto -ord 2 -x1 10ppm -xn 6ppm \
| nmrPipe  -fn EXT -x1 8.8ppm -xn 7.8ppm -sw -round 2 \
| nmrPipe  -fn TP \
| nmrPipe  -fn SMILE -nDim 2 -sample nuslist -maxIter 500 \
           -nSigma 4 -xP0 90 -xP1 0 -report 1 \
| nmrPipe  -fn ZF -zf 2 -auto \
| nmrPipe  -fn FT \
| nmrPipe  -fn PS -p0 90 -p1 0 -di \
| nmrPipe  -fn TP \
  -verb -ov -out smile.ft2
```

- **F2 phase is a hard-coded numeric constant** (`-p0 -24 -p1 0`), determined once (empirically,
  against the reliable direct-dimension data) — never a blind auto-phase search, matching D-02
  exactly.
- **The direct dimension (F2) is fully processed — apodized, zero-filled, FT'd, phased,
  baseline-corrected, extracted — BEFORE the transpose (`TP`) and SMILE call.** This is the
  literal, mechanical enforcement of RECON-02's F2-before-F1 gate: it is not just a design
  convention lucy-ng imposes, it is SMILE's own hard requirement, confirmed by the manual's
  explicit statement (§4) and reflected in every worked example's script order.
- **`-sample nuslist`** — SMILE reads the **same, unmodified Bruker `nuslist` file** already
  used by `nusExpand.tcl` (0-based, one index per line, acquisition order — confirmed against
  this project's own fixture: `tests/fixtures/nus/exp2_cosy/nuslist` is exactly this format).
  **No reformatting is needed** between the Bruker `nuslist` and what `-sample` expects —
  resolves one of the phase's explicit open questions.
- **`-xP0 90 -xP1 0`** in the SMILE call itself: SMILE's own worked echo-antiecho example uses
  **90°**, not 0°, for the indirect-dimension zero-order phase passed to the reconstruction
  algorithm. This is a direct, primary-source-verified **correction** to CONTEXT.md's own
  phrasing ("F1 default for echo-antiecho HSQC/HMBC (standard 0/0)") — flagged explicitly as
  Assumptions Log A2, since the *correct* value is pulse-sequence-specific (this project's own
  `hsqcedetgpsp.3`/`hmbcetgpl3nd` recipes were not independently verified against this manual's
  unrelated TROSY example) and must be empirically confirmed (or taken from this project's own
  prior processing attempt) rather than assumed as a universal default.
- The post-SMILE `-p0 90 -p1 0 -di` phase-shift step matches the SMILE-call's own `-xP0 90`
  value — i.e. once SMILE is told the correct F1 phase for reconstruction, the *same* phase
  value is reapplied conventionally afterward.

### GRPDLY / byte-order / NUS-parameter sourcing — direct reuse of Phase 97 model, no re-parsing

```python
# Source: this repo's own Phase 97 code (src/lucy_ng/nus/params.py,
# src/lucy_ng/nus/schedule.py) — reconstruction CONSUMES these, never re-parses acqus/acqu2s.
from lucy_ng.nus.params import read_nus_params
from lucy_ng.nus.schedule import read_nus_schedule

params = read_nus_params(expdir)      # grpdly, decim, dspfvs, byte_order, dtype_code,
                                       # f2_sfo1/f2_sw_h/f2_td, f1_sfo1/f1_sw_h/f1_td,
                                       # fnmode_f1, nus_td, f2_sf/f2_offset/f1_sf/f1_offset
schedule = read_nus_schedule(expdir)   # nuslist (acquisition order, 0-based), n_sampled
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Ad-hoc per-column IST in nmrglue (this project's own prior approach) | Established, literature-validated SMILE/NMRPipe backend | This milestone (v10.0) | Root-cause fix for the 2026-07-09 CASE failure (t1-ridge artifacts) |
| Blind/manual GUI-driven phasing (conventional NMRPipe tutorial workflow) | Deterministic, CLI-overridable, pre-determined phase constants | This phase (D-02) | Removes the human-in-the-loop step the milestone must eliminate, while avoiding Pitfall 10's silent auto-phase failure risk |
| Fixed iteration count as sole reconstruction stopping rule | `-maxIter` as upper bound + `-sigma`/`-nSigma` convergence check | This phase (RECON-05) | Avoids both under- and over-converged fabricated-peak failure modes (Pitfall 7) |

**Deprecated/outdated:** None identified specific to this phase; SMILE itself is described in
its own manual as "Beta version" (contact: Jinfa Ying) — treat SMILE's own CLI surface as stable
enough for this project's scope but not to be assumed unchanging release-to-release.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact bruk2pipe→nusExpand.tcl invocation order and flags for the QF/magnitude COSY branch (exp2, FnMODE=1) — the SMILE manual only fully documents the echo-antiecho (expand-first) path and merely states the reverse order "can be used too" without a worked script | Critical Finding 1 | If the convert-then-expand COSY path is implemented incorrectly, exp2's COSY reconstruction may silently degrade (plausible-looking but wrong H-H network) rather than crash — exactly Pitfall 2's "graceful degradation into artifact" failure mode. Mitigation: a short implementation-time spike against the real C20H32O2 exp2 data, cross-checked against the COSY diagonal-symmetry pitfall check, before trusting the automated path unattended. |
| A2 | F1 zero-order phase default for this project's specific echo-antiecho pulse sequences (`hsqcedetgpsp.3`, `hmbcetgpl3nd`) — the only concretely-verified SMILE-manual example uses `-xP0 90` for an *unrelated* TROSY pulse sequence, not these two; CONTEXT.md's own "standard 0/0" phrasing is also unverified against a primary source | Code Examples, Pitfall (auto-phase) | A wrong F1 phase constant produces systematically wrong edited-HSQC signs (Pitfall 10) that could silently propagate to CH/CH2/CH3 mis-assignment; mitigation is D-02's own CLI override plus the Phase-99 QC gate's edited-sign self-consistency check — but the *default* value used for the first automated run should be treated as provisional, not asserted as correct without a visual/QC cross-check on the first real reconstruction. |
| A3 | bruk2pipe's exact `-yMODE` string value for QF/magnitude-mode COSY (only `Echo-AntiEcho` and `Complex`/`States` were directly confirmed via the manual's own worked scripts; a secondary source (nmrscience.com bruk2pipe reference page) gives an ambiguous/garbled mode-value list that does not clearly name a QF/magnitude string) | Standard Stack / Critical Finding 1 | If the wrong `-yMODE` string is passed for exp2, bruk2pipe may error loudly (low risk, since RECON-04's fail-loud wrapper catches non-zero exit codes) — lower risk than A1/A2 since a wrong string is more likely to hard-fail than silently corrupt data, but still worth an explicit `bruk2pipe -help`/`bruk2pipe -yMODE -help` check at implementation time. |

**If this table is empty:** N/A — see above; all three items are genuine open verification
gaps this research pass could not close from available primary sources within scope, each with
a concrete, low-cost mitigation (a short implementation-time spike against the real data).

## Open Questions (RESOLVED)

> **RESOLVED (2026-07-13, planning close):** all three questions below are deferred to an implementation-time spike and mitigated in the plans — Q1 via the Plan-03 QF branch carrying a PROVISIONAL (A1/A3) annotation + an early empirical spike against real exp2 data; Q2 via D-02's CLI phase-override flags (Plan 06) + the PROVISIONAL (A2) default annotation (Plan 04); Q3 explicitly not adopted this phase (kept as a documented future simplification). No open question blocks planning.

1. **Exact COSY (QF/magnitude) bruk2pipe↔nusExpand.tcl invocation** (ties to A1/A3)
   - What we know: the correct *order* (convert first, expand after) and that SMILE is "not
     primarily intended" for magnitude-mode data but the manual doesn't forbid it outright.
   - What's unclear: the precise flag set/mode string for this specific branch — no worked
     script exists in the manual for this case.
   - Recommendation: implement the echo-antiecho branch first (fully worked, high confidence),
     then spike the COSY branch against the real exp2 data early in Phase 98's execution,
     verifying with the COSY diagonal-symmetry check before considering it done.

2. **F1 phase default values for this project's actual pulse sequences** (ties to A2)
   - What we know: SMILE needs *some* deterministic F1 P0/P1 fed via `-xP0`/`-xP1` (or `-yP0`/
     `-yP1` depending on axis), and the post-SMILE conventional processing reapplies the same
     value.
   - What's unclear: the numerically correct value for `hsqcedetgpsp.3`/`hmbcetgpl3nd`
     specifically — not derivable from this manual's unrelated TROSY example.
   - Recommendation: expose CLI overrides (D-02 already mandates this) and determine the actual
     default empirically during Phase 98's first real reconstruction run, cross-checked against
     the edited-HSQC CH/CH3-vs-CH2 sign pattern from the reliable 1D DEPT data (Pitfall 10's own
     recommended validation), then hard-code the confirmed value as the new default.

3. **Whether `nmrglue.process.pipe_proc`'s pure-Python FT/PS/baseline functions should replace
   the nmrPipe-subprocess post-processing stage in a later iteration**
   - What we know: they exist, are already importable (core dependency), and implement the
     identical algorithms nmrPipe's own `-fn FT`/`-fn PS`/`-fn CBF`/`-fn MED` use.
   - What's unclear: whether doing so would meaningfully reduce Pitfall-14 risk for that one
     stage (it would — no csh/pipe involved at all) enough to justify the inconsistency of
     mixing subprocess- and Python-native stages within one pipeline.
   - Recommendation: not adopted this phase (see Alternatives Considered); revisit only if the
     nmrPipe-subprocess post-processing stage proves troublesome in practice (e.g. cross-platform
     brittleness surfacing in Phase 100).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `nmrPipe` | All stages | ✗ (this dev machine, per Phase 97's own `NmrPipeSmileBackend.diagnose()` test assertions) | — | None for the real integration test (skipif-guarded per D-04); mocked unit tests cover orchestration logic without it |
| `bruk2pipe` | Conversion stage | ✗ (bundled with NMRPipe, same install) | — | Same as above |
| `nusExpand.tcl` | Expansion stage | ✗ (bundled with NMRPipe) | — | Same as above |
| SMILE plugin | Reconstruction stage | ✗ (requires separate `plugin.smile.tZ` download per the manual's own §2) | — | Same as above; `lucy nus check` (Phase 97) already distinguishes "nmrPipe present but SMILE plugin missing" from "nmrPipe absent entirely" |
| `nmrglue` | Fail-loud shape check | ✓ | 0.12-dev (git master) | N/A — already a core dependency |
| Real C20H32O2 `ser`/`nuslist`/`acqus`/`acqu2s` data | Integration test only | ✓ (external path, not in repo) | — | `.../active-lucy-ng-testprojects/C20H32O2/{2,3,4}/` |

**Missing dependencies with no fallback:** None that block this phase's *code* delivery — the
external binaries are runtime-detected exactly like LSD; their absence gates the real
integration test (skipif) and the actual empirical reconstruction-quality question (deferred to
whenever the backend is installed, per D-04), not the orchestration code itself.

**Missing dependencies with fallback:** All of `nmrPipe`/`bruk2pipe`/`nusExpand.tcl`/SMILE —
mocked-subprocess unit tests (D-04) fully exercise the orchestration logic, FnMODE branching,
ordering gate, and fail-loud wrapper without the real backend present.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥7.0 (already core dev dependency) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing, `testpaths = ["tests"]`) |
| Quick run command | `pytest tests/test_nus_runner.py tests/test_nus_postprocess.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RECON-01 | `reconstruct()` dispatches bruk2pipe/nusExpand.tcl/SMILE with mocked subprocess | unit | `pytest tests/test_nus_runner.py::TestReconstructDispatch -x` | ❌ Wave 0 |
| RECON-01 | Real end-to-end chain against external C20H32O2 data | integration (skipif-guarded, D-04) | `pytest tests/test_nus_runner.py::TestReconstructIntegration -x` | ❌ Wave 0 |
| RECON-02 | F2-before-F1 ordering gate raises before any subprocess when F2 plan unresolved | unit | `pytest tests/test_nus_runner.py::TestOrderingGate -x` | ❌ Wave 0 |
| RECON-02 | ppm axes reversed + calibrated against §10 ground truth | unit | `pytest tests/test_nus_postprocess.py::TestPpmCalibration -x` | ❌ Wave 0 |
| RECON-03 | FnMODE branching: echo-antiecho uses expand-first order, QF uses convert-first order | unit | `pytest tests/test_nus_runner.py::TestFnmodeBranching -x` | ❌ Wave 0 |
| RECON-04 | `run_stage()` raises on non-zero exit code | unit | `pytest tests/test_nus_runner.py::TestRunStage::test_nonzero_exit_raises -x` | ❌ Wave 0 |
| RECON-04 | `run_stage()` raises on a deliberately truncated/empty intermediate (exit 0 but empty file) | unit | `pytest tests/test_nus_runner.py::TestRunStage::test_empty_output_raises -x` | ❌ Wave 0 |
| RECON-05 | CLI flags for iteration count/threshold/virtual-echo thread through to SMILE invocation | unit | `pytest tests/test_cli_nus.py::TestReconstructCommand -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_nus_runner.py tests/test_nus_postprocess.py tests/test_cli_nus.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`; the real backend-gated integration
  test is expected to `SKIP` (not fail) on any machine without NMRPipe installed — this is
  correct, not a gap, per D-04.

### Wave 0 Gaps

- [ ] `tests/test_nus_runner.py` — covers RECON-01/02/03/04 (mocked subprocess boundary +
  skipif-guarded real-backend integration class)
- [ ] `tests/test_nus_postprocess.py` — covers RECON-02's ppm calibration/reversal logic
- [ ] Extend `tests/test_cli_nus.py` (exists from Phase 97) — add `TestReconstructCommand` for
  RECON-05's CLI flag surface
- No new test framework install needed — pytest already configured.

## Security Domain

> `security_enforcement` not found as explicitly `false` in `.planning/config.json` — treating
> as enabled per the harness default, though this phase's actual attack surface is minimal
> (local subprocess orchestration of a user-installed scientific tool, no network/auth/input
> from untrusted sources).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth surface in this phase |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes (narrow) | `expdir` path validated via `click.Path(exists=True)` (existing `cli/nus.py` convention); subprocess argv built entirely from typed, already-validated Pydantic model fields (`NusAcquisitionParams`/`NusSchedule`), never raw string interpolation from user-controlled shell input |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shell/argument injection via subprocess | Tampering | Fixed arg-list `subprocess.run()` calls, never `shell=True`, matching the existing `NmrPipeSmileBackend.smile_plugin_available()` and `LSDRunner` precedent throughout this codebase — no stage in this phase deviates from that pattern |
| Path traversal via a maliciously crafted `expdir` | Tampering | `expdir` is resolved via `Path(expdir).resolve()` (existing convention in `nus/params.py`/`nus/schedule.py`); intermediates are written under a per-experiment subfolder derived from the resolved path, not from unsanitized user string concatenation |

## Sources

### Primary (HIGH confidence)

- SMILE User's Manual — `https://spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf`
  (fetched directly in this research pass, 25 pages; sections read: 1-6.4 — Introduction,
  installation, hardware/OS requirements, general considerations §4, full command-line option
  reference §5, and two fully worked example pipeline scripts §6.1/§6.2/§6.3) — the primary
  source for all SMILE flag names/defaults, the FnMODE-dependent expand/convert ordering
  (Critical Finding 1), the F2-before-F1 mechanical enforcement, and the `-sample`/`nuslist`
  format confirmation.
- This repo's own Phase 97 code: `src/lucy_ng/lsd/runner.py` (`LSDRunner` subprocess/
  fail-loud/`is_available()` precedent), `src/lucy_ng/nus/params.py`, `src/lucy_ng/nus/
  schedule.py`, `src/lucy_ng/nus/backends/nmrpipe_smile.py`, `src/lucy_ng/nus/backends/
  __init__.py`, `src/lucy_ng/models/nus.py`, `src/lucy_ng/cli/nus.py`, `tests/test_nus_backends.py`,
  `tests/test_lsd_runner.py`, `tests/fixtures/nus/exp2_cosy/nuslist` (0-based acquisition-order
  format directly confirmed).
- `.planning/research/SUMMARY.md`, `.planning/research/ARCHITECTURE.md`,
  `.planning/research/PITFALLS.md` (milestone-level research, 2026-07-12) — architecture module
  layout, the 16-pitfall catalogue, backend decision rationale.
- `analysis/NUS-RECONSTRUCTION-GUIDE.md` (this project's own task brief, §5/§8/§10) — the
  recommended pipeline outline, verification criteria, and ground-truth ¹³C shift list.
- Direct local verification: `nmrglue.__version__ == "0.12-dev"` (git master, matching
  `pyproject.toml`'s documented NumPy-2 compatibility pin), `nmrglue.fileio.pipe` module surface
  (`read`, `read_2D`, `write`, etc.) and `nmrglue.process.pipe_proc` module surface (`ft`, `ps`,
  `zf`, `sp`, `cbf`, `med`, etc.) confirmed via local `python3 -c "import nmrglue"` introspection.

### Secondary (MEDIUM confidence)

- `http://www.nmrscience.com/ref/prog/bruk2pipe.html` (WebFetch summary) — general bruk2pipe
  flag inventory (`-grpdly`, `-decim`, `-dspfvs`, `-aswap`/`-noaswap`); the summarized
  `-xMODE`/`-yMODE` value list was garbled/ambiguous and is NOT relied on for the QF/magnitude
  mode string (see Assumptions Log A3) — the `Echo-AntiEcho`/`Complex`/`States` mode strings
  used in this document are instead taken directly from the SMILE manual's own generated
  scripts (primary source).

### Tertiary (LOW confidence)

- General WebSearch results on "bruk2pipe -yMODE" cross-referencing FnMODE 1/2=magnitude,
  3=TPPI, 4=States, 5=States-TPPI, 6=Echo-AntiEcho — directionally consistent with this
  project's own already-verified `REAL_FNMODES`/`COMPLEX_FNMODES` split (Phase 97,
  `models/nus.py`) but not independently re-derived from an official Bruker or NMRPipe source in
  this pass.

## Metadata

**Confidence breakdown:**
- Standard stack (SMILE/bruk2pipe/nusExpand.tcl flags): MEDIUM-HIGH — primary-source manual
  fetched and read directly in this pass, resolving the milestone research's own flagged gap;
  the one remaining low-confidence area is the QF/magnitude-mode branch, which the manual itself
  does not fully work through (Assumptions Log A1/A3).
- Architecture (stage orchestration, fail-loud wrapper, FnMODE branching): HIGH — derived
  directly from this repo's own already-shipped Phase 97 code plus the SMILE manual's explicit
  ordering requirements.
- Pitfalls: HIGH (inherited, milestone-level, already grounded against this project's own real
  acqus/acqu2s/nuslist data) plus this phase's own two new, concretely-sourced findings
  (FnMODE-dependent stage order; NusTD-vs-TD conversion-size selection).

**Research date:** 2026-07-13
**Valid until:** 30 days (stable domain — NMRPipe/SMILE CLI surface changes infrequently; the
empirical reconstruction-quality question is time-invariant research-wise but must still be
answered by an actual run, not re-researched)
