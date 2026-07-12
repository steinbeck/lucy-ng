# Architecture Research — v10.0 Automatic NUS 2D Reconstruction

**Domain:** Integrating automatic NUS (non-uniform sampling) 2D NMR reconstruction into lucy-ng
**Researched:** 2026-07-12
**Confidence:** HIGH — module layout, CLI shape, and dependency-isolation decision are derived
directly from inspecting the live codebase (`lsd/`, `webview/`, `readers/bruker.py`, `cli/*.py`,
`pyproject.toml`) and the task brief. MEDIUM on data-flow artefact names (depends on the backend
chosen by the parallel backend-selection research) and LOW on the exact Windows story (depends on
whether the chosen backend ships Windows binaries — flagged explicitly below, not asserted).

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Pre-CASE step (new, decoupled — "dumb tool", no agent reasoning)         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │ nus/params.py│→│nus/schedule.py│→│ nus/backends/* │→│nus/runner.py │  │
│  │ acqus/acqu2s │  │ nuslist→      │  │ NMRPipe+SMILE  │  │ subprocess   │  │
│  │ → NusAcq     │  │ backend sched │  │ (or hmsIST /   │  │ orchestration│  │
│  │  Params      │  │               │  │ mddnmr / …)    │  │             │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  └──────┬──────┘  │
│                                                                  │         │
│                                                          ┌───────▼──────┐  │
│                                                          │nus/          │  │
│                                                          │postprocess.py│  │
│                                                          │FT/phase/base │  │
│                                                          └───────┬──────┘  │
│                                                                  │         │
│                                                          ┌───────▼──────┐  │
│                                                          │ nus/bridge.py│  │
│                                                          │ →Spectrum2D  │  │
│                                                          │ →PeakPicker2D│  │
│                                                          └───────┬──────┘  │
├──────────────────────────────────────────────────────────────────┼────────┤
│  EXISTING CASE pipeline (UNCHANGED — reads from here)             │        │
│  analysis/nmr_peaks/{HSQC,HMBC,COSY}_expN.json ◄───────────────────┘        │
│       ↓                                                                    │
│  detection/ (statistical) → fragments/ (search) → lsd/ (generate+solve)   │
│       ↓                                                                    │
│  ranking/ → CASE-PROGRESS.md / final_results.md                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|-----------------|-------------------------|
| `nus/params.py` | Extract acquisition parameters from `acqus`/`acqu2s` (SFO1, SW, TD, FnMODE, GRPDLY/DECIM, byte order, NusAMOUNT/NusSEED) | nmrglue's low-level Bruker param dict (`ng.bruker.read`), same pattern as `readers/bruker.py`'s `_get_param_2d`; wraps output in a new `models.NusAcquisitionParams` Pydantic model |
| `nus/schedule.py` | Parse `nuslist` (measured t1 indices) and translate to whatever schedule format the selected backend expects | Pure Python, no external deps; one `to_<backend>()` writer per backend |
| `nus/backends/*.py` | One module per reconstruction backend (`nmrpipe_smile.py`, later `hmsist.py`, `mddnmr.py`, optionally `python_native.py`); each exposes `is_available()`, `reconstruct(params, schedule, ser_path, output_dir) -> ReconstructionResult` | External-binary backends: `LSDRunner`-style `SEARCH_PATHS` + `shutil.which()` detection + `subprocess.run()`. A pure-Python backend (if selected) is plain library calls, no subprocess |
| `nus/runner.py` | Orchestrates params → schedule → backend.reconstruct() → postprocess, writes intermediate artefacts, captures logs | Thin coordinator, mirrors `lsd/runner.py`'s `LSDRunner` — owns temp/output dir lifecycle, timeout handling, structured `NusResult` return type |
| `nus/postprocess.py` | FT / apodization / zero-fill / phase / baseline of the reconstructed indirect dimension (and any direct-dimension steps not already done) | Delegates to the backend's own processing chain when possible (NMRPipe pipe scripts); falls back to nmrglue-based processing for a Python-native path |
| `nus/bridge.py` | Converts the processed 2D spectrum into the SAME `Spectrum2D` Pydantic model the rest of lucy-ng uses, then calls the EXISTING `processing.PeakPicker2D` and writes `analysis/nmr_peaks/*.json` in the unchanged schema | Direct Python function calls (no subprocess to `lucy pick`) — same "extract shared logic into a directly-callable helper" pattern already used for `_perform_ranking` in `cli/lsd.py` |
| `cli/nus.py` | `lucy nus` command group: check / params / schedule / reconstruct / pipeline | Click group, import-safe like `cli/webview.py` (no top-level import of anything nus-internal beyond stdlib+click) |

## Recommended Project Structure

```
src/lucy_ng/
├── nus/                          # NEW top-level package (sibling of lsd/, webview/, readers/)
│   ├── __init__.py                # re-exports NusRunner, NusResult for cli/nus.py
│   ├── params.py                  # acqus/acqu2s -> NusAcquisitionParams
│   ├── schedule.py                # nuslist -> NusSchedule (+ per-backend writers)
│   ├── runner.py                  # NusRunner: orchestrates the pipeline, owns analysis/nus/<exp>/
│   ├── postprocess.py             # FT/phase/baseline (backend-delegated or nmrglue fallback)
│   ├── bridge.py                  # reconstructed spectrum -> Spectrum2D -> PeakPicker2D -> JSON
│   └── backends/
│       ├── __init__.py            # NusBackend Protocol/ABC, backend registry, get_backend()
│       ├── nmrpipe_smile.py       # primary candidate per NUS-RECONSTRUCTION-GUIDE.md §5
│       ├── hmsist.py              # fallback candidate (§7)
│       ├── mddnmr.py              # fallback candidate (§7)
│       └── python_native.py       # OPTIONAL — only if backend research selects a pip-installable CS/IST lib
├── models/
│   └── nus.py                     # NEW: NusAcquisitionParams, NusSchedule, ReconstructionResult (Pydantic v2)
├── readers/
│   └── bruker.py                  # MODIFIED (additive only): factor out the acqus/acqu2s param-dict
│                                   # helpers (_get_param, _get_param_2d, _strip_brackets) into a
│                                   # small shared module nus/params.py imports, OR nus/params.py
│                                   # imports them directly from readers.bruker — no behavioural change
│                                   # to BrukerReader.read_1d/read_2d
├── processing/
│   └── (UNCHANGED)                 # PeakPicker2D consumed as-is by nus/bridge.py
├── cli/
│   └── nus.py                     # NEW: `lucy nus` command group, registered in cli/main.py
└── ...                            # everything else unchanged
```

### Structure Rationale

- **`nus/` as a new top-level package, not `processing/nus/`:** `processing/` today holds pure,
  dependency-free signal-processing (peak picking) that operates on already-loaded `Spectrum1D`/
  `Spectrum2D` objects. NUS reconstruction is a different kind of concern — it is an *external
  tool integration* (subprocess orchestration, binary detection, multi-stage pipeline with
  on-disk intermediate artefacts) that happens *before* a `Spectrum2D` object exists. That is
  exactly the shape of `lsd/` (external solver integration) and `webview/` (external-process
  lifecycle), both of which are their own top-level packages. Nesting NUS under `processing/`
  would blur that boundary and make the "is this dependency-free or not" question — which matters
  a lot here — harder to answer at a glance.
- **`nus/backends/` subpackage:** mirrors the eventual need to support multiple interchangeable
  reconstruction engines (the backend-selection research is running in parallel and may recommend
  a primary + fallback). A `NusBackend` Protocol keeps `runner.py` and `cli/nus.py` backend-agnostic;
  adding `hmsist.py` or `mddnmr.py` later is additive, not a rewrite.
  Enum/Registry: `nus/backends/__init__.py` exposes `get_backend(name: str) -> NusBackend`, plus
  `list_available_backends() -> list[str]` (used by `lucy nus check`).
- **`models/nus.py`:** keeps Pydantic models colocated with the rest of the type-safe data model
  layer (`Spectrum1D`, `Peak1D`, …), not buried inside `nus/`. Matches the existing separation of
  "data model" (`models/`) from "logic that produces/consumes the model" (readers/, processing/, …).
- **`nus/bridge.py` is the ONLY new module that touches the existing pipeline surface.** Everything
  upstream of it (`params.py`, `schedule.py`, `backends/`, `runner.py`, `postprocess.py`) is pure
  addition with zero coupling to `detection/`, `fragments/`, `lsd/`, `ranking/`. This is what makes
  the milestone's "CASE pipeline unchanged" constraint enforceable by inspection: the diff to
  `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` should be **empty**.

## Architectural Patterns

### Pattern 1: External-binary detection with `SEARCH_PATHS` + `shutil.which()` + fail-loud `check`

**What:** A backend module exposes a classmethod `is_available()` that first checks `PATH` via
`shutil.which()`, then falls back to a list of common installation locations (mirrors
`LSDRunner.SEARCH_PATHS` / `_find_lsd`). A `lucy nus check` command reports per-backend
availability and exits 1 if none are usable, printing install guidance (URL + registration note).
**When to use:** For any backend that is an external native binary not distributed on PyPI —
NMRPipe (`nmrPipe`, `smileNus`, `nusExpand.tcl`, `bruk2pipe`), hmsIST, mddnmr, TopSpin CLI/AU-macro
invocation. This is the LSD precedent (`LSDRunner`, `lucy lsd check`) applied verbatim.
**Trade-offs:** No pip-installability, no version pinning via `pyproject.toml`; user must install
outside the Python environment. In exchange: works regardless of Python packaging (these tools are
Fortran/C/Tcl/csh, not Python-packageable), and matches an already-proven, already-documented
pattern in this codebase (`CLAUDE.md` § Local prerequisites already documents the equivalent LSD
step: "Download from http://eos.univ-reims.fr/LSD/, extract, add the `bin/` directory to PATH").

**Example:**
```python
# nus/backends/nmrpipe_smile.py
class NmrPipeSmileBackend:
    REQUIRED_TOOLS = ["nmrPipe", "smileNus", "nusExpand.tcl", "bruk2pipe"]

    @classmethod
    def is_available(cls) -> bool:
        return all(shutil.which(tool) is not None for tool in cls.REQUIRED_TOOLS)

    @classmethod
    def missing_tools(cls) -> list[str]:
        return [t for t in cls.REQUIRED_TOOLS if shutil.which(t) is None]
```

### Pattern 2: Optional pip extra for pip-installable heavy/optional deps

**What:** A `[nus]` extra in `pyproject.toml` bundles any *pip-installable* dependency the NUS
pipeline needs (e.g. a Python-native CS/IST fallback library, or matplotlib for QC contour plots),
lazily imported inside command bodies with a `_require_nus()` guard that raises a friendly
`click.ClickException` pointing at `pip install lucy-ng[nus]`. `cli/nus.py` stays import-safe at
module load time — same doc-comment convention as `cli/webview.py` ("This module is import-safe:
it does NOT import fastapi... at the top level").
**When to use:** Only for genuinely pip-installable pieces. Do NOT use this pattern to paper over
an external binary dependency — that is Pattern 1's job.
**Trade-offs:** Keeps core `lucy` CLI dependency-free (matches the hard invariant already enforced
for `[webview]`), but only applies if/when the backend research actually selects or falls back to
a Python-native library. If the selected backend is NMRPipe+SMILE only, `[nus]` may end up empty
or hold only QC-plotting deps — that is fine and expected, not a design smell.

**Example:**
```python
# cli/nus.py — mirrors cli/webview.py's _require_webview()
def _require_nus_extra() -> None:
    try:
        import some_pure_python_ist_lib  # noqa: F401
    except ImportError as exc:
        raise click.ClickException(
            "The nus extra is not installed.\nInstall with: pip install lucy-ng[nus]"
        ) from exc
```

### Pattern 3: Direct-call bridge instead of subprocess-to-self

**What:** `nus/bridge.py` builds a `Spectrum2D` object in memory and calls
`processing.PeakPicker2D` **as a Python function**, not by shelling out to `lucy pick hsqc`. It
then serializes to the exact JSON schema `lucy pick hsqc --format json` already produces.
**When to use:** Whenever a new pipeline stage needs to reuse existing CLI-adjacent logic. This
mirrors an established precedent in this codebase: `cli/lsd.py`'s `_perform_ranking()` was
explicitly "extracted... so that the pylsd run command... can call ranking logic as a direct Python
function call without spawning a subprocess (D-14)".
**Trade-offs:** Requires `nus/bridge.py` to import from `processing/` and `models/` (a real Python
dependency, not just a CLI contract) — acceptable, since `processing/` and `models/` are already
dependency-free, pure-Python modules with no external-binary requirements.

## Data Flow

### Reconstruction Pipeline Flow

```
Bruker ser + nuslist + acqus/acqu2s (per NUS experiment dir, e.g. expdir/2, expdir/3, expdir/4)
    ↓
nus/params.py   → NusAcquisitionParams (SFO1, SW_h, TD, FnMODE, GRPDLY/DECIM, byte order,
                    NusAMOUNT, NusSEED, pulse program, F1/F2 nuclei)
    ↓
nus/schedule.py → NusSchedule (parsed nuslist indices + per-backend schedule file)
    ↓
nus/backends/<selected>.reconstruct(params, schedule, ser_path, output_dir)
    → Bruker→backend conversion (e.g. bruk2pipe-generated fid.com)
    → NUS expansion (zero-fill sparse FID to full grid on the schedule, e.g. nusExpand.tcl)
    → CS/IST/SMILE reconstruction of the indirect dimension
    ↓
nus/postprocess.py → apodization, zero-fill, FT (both dims), phase (F2 from 1D reference,
                       F1 per FnMODE — echo-antiecho for HSQC/HMBC, QF for COSY), baseline
    ↓  (processed 2D spectrum, e.g. processed.ft2)
nus/bridge.py    → Spectrum2D (f1/f2 ppm scales, data matrix, experiment_type, metadata)
    → processing.PeakPicker2D.pick_2d(...)   [EXISTING, unmodified]
    → JSON peaklist, SAME schema as the manual/GUI path:
        {c13_ppm, h1_ppm, edited_sign/intensity, note}  for HSQC/HMBC
        {h1a, h1b}                                        for COSY
    ↓
analysis/nmr_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2}.json   ← EXISTING CASE entry point, unchanged
    ↓
detection/ → fragments/ → lsd/ → ranking/                 ← EXISTING CASE pipeline, unchanged
```

### Intermediate Artefact Layout

```
<compound_path>/
├── 2/, 3/, 4/                       # raw Bruker NUS experiment dirs (ser, nuslist, acqus, acqu2s) — INPUT, untouched
├── analysis/
│   ├── nus/                         # NEW — all NUS-specific intermediates live here, nowhere else
│   │   ├── exp2_COSY/
│   │   │   ├── params.json           # nus/params.py output (lucy nus params --format json)
│   │   │   ├── schedule.json         # nus/schedule.py output (lucy nus schedule --format json)
│   │   │   ├── fid.com                # generated conversion script (backend-specific, kept for audit)
│   │   │   ├── raw.fid / expanded.fid / reconstructed.fid / processed.ft2   # backend-named intermediates
│   │   │   ├── reconstruct.log        # captured subprocess stdout+stderr (debugging, T-shaped for support)
│   │   │   └── qc/                    # OPTIONAL contour/ridge-check PNGs (needs [nus] or [webview] matplotlib)
│   │   ├── exp3_HSQC/  (same layout)
│   │   └── exp4_HMBC/  (same layout)
│   ├── nmr_peaks/                    # EXISTING, unchanged schema — nus/bridge.py writes here
│   │   ├── HSQC_exp3.json
│   │   ├── HMBC_exp4.json
│   │   └── COSY_exp2.json
│   └── CASE-PROGRESS.md, final_results.md, …   # EXISTING, untouched by this milestone
```

`analysis/nus/` is intentionally isolated from `analysis/nmr_peaks/` and everything downstream —
it is scratch/audit space for the reconstruction step, disposable in principle (like `analysis/
iteration_NN/` scratch for LSD), and never read by `detection/`, `fragments/`, `lsd/`, or `ranking/`.

## Anti-Patterns

### Anti-Pattern 1: Making the reconstruction backend a required core dependency

**What people do:** Add `nmrpipe-python-bindings` (or similar) to `dependencies` in `pyproject.toml`
so `pip install lucy-ng` "just works" for NUS.
**Why it's wrong:** NMRPipe/hmsIST/mddnmr are not pip packages — they are large, sometimes
registration-gated academic binary distributions. There is no PyPI artifact to depend on. Trying
to fake this with a wrapper package would either vendor a huge non-redistributable binary or
silently no-op. It would also make the core `lucy` CLI (which today has ZERO required system
dependencies beyond Python packages) suddenly require a multi-hundred-MB external install just to
import `lucy_ng.cli`.
**Instead:** Runtime-detected external binary (Pattern 1), exactly like LSD. `lucy nus check` is
the discovery command; core CLI import stays clean.

### Anti-Pattern 2: Coupling `nus/bridge.py` output to a NUS-specific JSON schema

**What people do:** Give the reconstructed-spectrum peaklists a slightly different JSON shape
("because it came from a different pipeline") — e.g. adding a `reconstructed: true` flag nested
differently, or renaming `c13_ppm`/`h1_ppm`.
**Why it's wrong:** Breaks the milestone's hard constraint that "reconstructed 2D spectra must feed
the EXISTING peak-picking → JSON peaklist path... so the downstream CASE run is unchanged." Any
schema drift forces `detection/`, `case.md`, and the 5-agent team's expectations to special-case
NUS-derived data — exactly the coupling this architecture is designed to avoid.
**Instead:** `nus/bridge.py` must produce byte-for-byte the same JSON schema `lucy pick hsqc/hmbc/
cosy --format json` produces today. Add provenance (which backend, params used) only as an
*additional* file (e.g. `analysis/nus/exp3_HSQC/params.json`), never inside `analysis/nmr_peaks/*.json`.

### Anti-Pattern 3: Folding reconstruction into the nmr-chemist agent's live reasoning

**What people do:** Give the `lucy-nmr-chemist` agent a Bash-callable "reconstruct NUS data" step
inside the CASE run itself, so the agent decides when/how to invoke the backend.
**Why it's wrong:** Reconstruction is a deterministic, mechanical signal-processing pipeline with
no domain judgement involved (no "is this an aromatic ring" reasoning) — it is exactly the kind of
thing the project's own philosophy assigns to "thin tools", not the "intelligence layer". Making it
agent-driven also breaks the milestone's explicit "decoupled ('dumb tool'), unit-testable from
fixtures, no live agent-team run needed" requirement, and adds nondeterministic latency (minutes to
tens of minutes for CS/IST reconstruction) inside an already-monitored, loop-detected team run.
**Instead:** Run `lucy nus pipeline <expdir>` as a pre-CASE step (human-invoked, or invoked by a
one-shot prep script / a `sanitise`-style pre-flight `/lucy-ng:*` sub-skill) that produces clean
`analysis/nmr_peaks/*.json` BEFORE `/lucy-ng:case` starts. `case.md` and the 5-agent team need zero
changes. See Integration Points below for the precise boundary.

## Integration Points

### External Tools / Backends

| Backend | Integration Pattern | Notes |
|---------|----------------------|-------|
| NMRPipe + SMILE (`nmrPipe`, `smileNus`, `nusExpand.tcl`, `bruk2pipe`) | `nus/backends/nmrpipe_smile.py`, LSD-style PATH/SEARCH_PATHS detection, `subprocess.run()` per stage | Free but registration-gated (not pip-installable); `.cshrc`/env sourcing needed before PATH detection works — `lucy nus check` should surface a clear "installed but not on PATH, did you source your NMRPipe env?" hint, distinct from "not installed at all" |
| hmsIST (fallback) | Same `NusBackend` interface, own `SEARCH_PATHS` | Also NMRPipe-pipeline-based; likely shares the `nmrPipe` binary detection with the SMILE backend — factor a shared `_nmrpipe_available()` helper in `nus/backends/__init__.py` to avoid duplicated detection logic |
| mddnmr/qMDD (fallback) | Same `NusBackend` interface | Same NMRPipe-pipeline dependency as above |
| TopSpin (headless, if research selects it) | Only viable if drivable via TopSpin's Python/AU-macro API non-interactively; otherwise explicitly OUT of scope for automatic reconstruction (guide §6 already flags this as GUI-only / human path) | Backend-selection research owns this decision; this architecture treats it as just another `NusBackend` if and only if a headless invocation path exists |
| Python-native CS/IST (if research selects it as primary or fallback) | `nus/backends/python_native.py`, plain library import behind `[nus]` extra + `_require_nus_extra()` guard | No subprocess, no PATH detection — a normal pip dependency |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|----------------|-------|
| `nus/params.py` ↔ `readers/bruker.py` | Direct Python import of the existing `acqus`/`acqu2s` param-dict helpers (`_get_param`, `_get_param_2d`, `_strip_brackets`) — reused, not duplicated | If these helpers are currently module-private (leading underscore) in `readers/bruker.py`, either (a) promote them to a small shared `readers/_bruker_params.py` internal module both `bruker.py` and `nus/params.py` import, or (b) accept the underscore-import (acceptable within the same package) — a one-line decision for the roadmap phase, not an architectural blocker |
| `nus/bridge.py` ↔ `processing/` (`PeakPicker2D`) | Direct Python function call, in-process | No subprocess; `PeakPicker2D` is unmodified — it only ever sees a `Spectrum2D`, and does not know or care whether that object came from `BrukerReader.read_2d()` or from NUS reconstruction |
| `nus/bridge.py` → `analysis/nmr_peaks/*.json` | File write, schema-identical to `lucy pick hsqc/hmbc/cosy --format json` | This is the ONLY contract the rest of the CASE pipeline (`detection/`, `fragments/`, `lsd/`, `case.md`, the 5-agent team) needs to know about; everything upstream is invisible to them |
| `cli/nus.py` ↔ `nus/` package | Thin Click wrapper, same shape as `cli/lsd.py` around `lsd/` and `cli/webview.py` around `webview/` | `cli/nus.py` stays import-safe (no top-level `nus.backends.*` imports that might pull in heavy/optional deps) — deferred imports inside command bodies, same convention as `cli/webview.py`'s doc comment |
| `case.md` orchestrator ↔ NUS reconstruction | NONE at the team level — pre-CASE step only | No new `[BEGIN]` directive, no 6th agent, no CASE-PROGRESS.md section. If auto-detection of `nuslist` files becomes desirable later, it belongs in a thin pre-flight check the human/launching Claude instance runs — NOT inside the monitored 5-agent team loop |

## Suggested Build Order (Phases)

Ordering follows the dependency chain in the data-flow diagram: nothing downstream can be
meaningfully tested until the thing upstream of it exists, and the riskiest external-binary
integration work should happen early (fail fast on backend-availability unknowns) while pure-Python
logic (params/schedule parsing, the peak-pick bridge) can be built and unit-tested against fixtures
throughout without needing the real binary installed.

1. **Phase A — Backend integration + params/schedule.**
   `nus/backends/__init__.py` (`NusBackend` protocol/ABC), the chosen primary backend module
   (`nmrpipe_smile.py` per the guide's recommendation, pending confirmation from the parallel
   backend-selection research), `lucy nus check`. In parallel: `nus/params.py` (acqus/acqu2s
   extraction, `NusAcquisitionParams` model) and `nus/schedule.py` (nuslist parsing,
   `NusSchedule` model). These two halves are independent and can be built/tested concurrently —
   params/schedule parsing needs zero external binaries and is fully unit-testable against the
   C20H32O2 exp2/3/4 `acqus`/`acqu2s`/`nuslist` fixtures from day one.
   *Exit criterion:* `lucy nus check` correctly reports backend availability; `lucy nus params` /
   `lucy nus schedule` produce correct, schema-validated JSON for all three C20H32O2 NUS experiments.

2. **Phase B — Reconstruction + processing.**
   `nus/runner.py` orchestration, the backend's actual `reconstruct()` implementation (Bruker→
   backend conversion, NUS expansion, CS/IST/SMILE call), `nus/postprocess.py` (FT/phase/baseline).
   This phase needs the real external binary installed locally (or a well-isolated integration-test
   fixture) — expect this to be the highest-uncertainty phase (matches the milestone's explicit
   research-flag pattern: reconstruction quality, not just plumbing, is the open question this
   whole milestone exists to answer).
   *Exit criterion:* `lucy nus reconstruct <expdir>` produces a processed 2D spectrum artefact for
   all three C20H32O2 experiments that passes the guide's §8 qualitative checks (clean HSQC 1-bond
   correlations, HMBC without t1-ridges, real COSY H-H network — manual/visual gate at this phase,
   automated in Phase D).

3. **Phase C — Peak-pick bridge + CLI surface.**
   `nus/bridge.py` (Spectrum2D construction + `PeakPicker2D` call + JSON serialization matching the
   existing schema exactly), full `cli/nus.py` command group (`check`/`params`/`schedule`/
   `reconstruct`/`pipeline`, all with `--format json`), registration in `cli/main.py`.
   *Exit criterion:* `lucy nus pipeline <expdir>` end-to-end produces `analysis/nmr_peaks/*.json`
   that is schema-identical to (and a drop-in replacement for) files produced by the existing
   manual/GUI-derived path; a diff test against a known-good fixture peaklist schema passes.

4. **Phase D — Cross-platform hardening + C20H32O2 end-to-end validation.**
   Portability matrix (macOS/Linux native support status; Windows — likely WSL-mediated for NMRPipe-
   family backends, to be confirmed by the backend research, not assumed here); path/line-ending
   robustness in generated csh/tcl scripts; documented gaps. Final validation: reconstruct C20H32O2
   exp2/exp3/exp4, confirm §8 quality gate, then run `/lucy-ng:case C20H32O2` and confirm convergence
   on a small rankable solution set (the milestone's actual success criterion).
   *Exit criterion:* the milestone's target features are all met — this is the milestone-closing phase.

**Dependency note:** Phase C's CLI surface can be scaffolded (command signatures, `--format json`
contracts, error handling) in parallel with Phase B once Phase A's models are stable — only the
`reconstruct` subcommand's actual body has a hard dependency on Phase B being functional. This
allows CLI/UX polish and the peak-pick bridge's unit tests (against synthetic/mocked reconstructed
spectra) to proceed without blocking on real-binary reconstruction quality.

## Sources

- `/Users/steinbeck/Dropbox/develop/lucy-ng/.planning/PROJECT.md` — v10.0 milestone definition, existing architecture section, LSD/webview extra precedents in Key Decisions history
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` — §5 recommended NMRPipe+SMILE pipeline, §7 fallback backends (hmsIST, mddnmr), §8 verification criteria, §9 return path into CASE, §3 data inventory (per-experiment FnMODE/NUS%/nuslist sizes)
- `/Users/steinbeck/Dropbox/develop/lucy-ng/CLAUDE.md` — project structure conventions, LSD prerequisite handling (`lucy lsd check`, PATH-based install)
- `src/lucy_ng/lsd/runner.py` — `LSDRunner` external-binary detection pattern (`SEARCH_PATHS`, `shutil.which`, `is_available()`, subprocess orchestration, fail-loud error handling) — direct precedent for `nus/backends/*`
- `src/lucy_ng/cli/lsd.py` — `lucy lsd check`/`run`/`rank` command shapes; `_perform_ranking()` as the direct-call-not-subprocess precedent for `nus/bridge.py`
- `src/lucy_ng/cli/webview.py` — `[webview]` optional-extra pattern (`_require_webview()`, lazy imports, import-safe module doc comment) — direct precedent for an optional `[nus]` extra
- `src/lucy_ng/readers/bruker.py` — existing acqus/acqu2s parameter-extraction helpers (`_get_param`, `_get_param_2d`, `_detect_experiment_type`) that `nus/params.py` should reuse
- `pyproject.toml` — `[project.optional-dependencies]` structure (`webview = [...]`), core `dependencies` list (confirms core CLI has zero heavy/binary deps today)
- `src/lucy_ng/cli/main.py` — command-group registration pattern for the new `lucy nus` group

---
*Architecture research for: NUS 2D reconstruction integration (lucy-ng v10.0)*
*Researched: 2026-07-12*
