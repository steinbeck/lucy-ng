# Phase 102: CLI + Peak-Pick Bridge + QC Reuse - Research

**Researched:** 2026-07-25
**Domain:** CLI glue over an existing bridge/QC pipeline (Click CLI, Pydantic v2 models, nmrglue-adjacent readers) — no new algorithms
**Confidence:** HIGH for the reuse wiring; **HIGH but ALARMING** for one specific finding (see Pitfall #1 — a real, verified reader bug blocks COSY, one of this phase's three named experiments)

## Summary

Phase 102 is almost entirely glue: `JcampReader.read_2d()` already returns a `Spectrum2D` that plugs directly into the **unchanged** `nus.bridge.bridge_peak_pick(spectrum, experiment=..., qc_report=..., recon_meta=...)` — there is no `build_spectrum2d()` step to reuse or reimplement, because that function exists specifically to reconstruct a `Spectrum2D` from an NMRPipe `.ft2` file, which JCAMP does not produce. The JCAMP path is *shorter* than the NUS path: `JcampReader.read_2d()` IS the `Spectrum2D` builder. The one genuinely new component is the 1D bridge (D-03), and its exact output contract is now fully pinned down by reading `nus/qc.py::_load_1d_shifts()`: it expects a top-level `"peaks"` key (not `"cross_peaks"`) with per-peak `"ppm"` floats — i.e. **the 1D bridge must reproduce `cli/pick.py::pick_1d`'s JSON shape exactly**, not the 2D per-experiment schema.

During verification against the real (external, uncommitted) `C20H32O2-jcamp` dataset, this research found a **real, load-bearing bug** in the Phase-101 reader: `readers/jcamp.py::_resolve_dim()` raises `ValueError` for any homonuclear 2D experiment (both dimensions the same nucleus) because it disambiguates dimensions by unique nucleus match, and a homonuclear file's `$NUC1` list contains the same nucleus string twice. Both the real `C20H32O2_COSY.dx` and `C20H32O2_NOESY.dx` files were inspected directly and confirmed to have `$NUC1 = ['<1H>', '<1H>']` (two identical entries, verified via `grep` on the actual file, not inferred). `JcampReader.read_2d()` — and therefore Phase 102's whole chain — **will raise before ever reaching `bridge_peak_pick()`** for COSY, not just for NOESY. Phase 102's own success criteria require COSY output (`bridge_peak_pick` supports HSQC/HMBC/COSY); D-06 only anticipated skipping NOESY. This is not a hypothetical risk — it is a concrete, reproducible defect the planner must decide how to handle (extend `_resolve_dim`'s degeneracy branch with positional resolution, matching the already-established heteronuclear `$NUC1` "procs-then-proc2s" ordering convention, rather than raising). `readers/jcamp.py` is **not** in the byte-unchanged protected set (only `cli/pick.py`, `case.md`, and the 5-agent-team files are), so fixing it is within this phase's remit.

**Primary recommendation:** Build `lucy jcamp <dir-or-files>` as a single new Click command (not a group) in a new `src/lucy_ng/cli/jcamp.py`, mirroring `cli/nus.py`'s deferred-import convention (no new packaging surface needed — nmrglue and click are already core deps). Per file: `JcampReader.read()` → dispatch on returned type → for `Spectrum2D`, call `_detect_experiment_type`-derived routing to skip unsupported types (D-06) and call `bridge_peak_pick()` twice (staged pre-QC, then post-QC rebuild) exactly as `cli/nus.py::pipeline` already does; for `Spectrum1D`, call a new thin 1D bridge function that reproduces `cli/pick.py::pick_1d`'s exact JSON shape and writes to `13C.json`/`1H.json` (keyword-glob-discoverable by the unchanged `qc.py`). Before any of this can work end-to-end on the real dataset, the planner must resolve the COSY/NOESY homonuclear-dimension bug in `readers/jcamp.py` — this is arguably Phase 102's real first task, ahead of the CLI wiring itself.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JCLI-01 | `lucy jcamp <dir-or-files>` runs the full chain (read → `Spectrum2D`/`Spectrum1D` → existing `PeakPicker2D` → `analysis/nmr_peaks/*.json`), reusing the Phase-99 bridge pattern, not a new picker; every subcommand supports `--format json` | `bridge_peak_pick()`'s exact signature pinned (no `build_spectrum2d()` needed for JCAMP — `JcampReader.read_2d()` already returns `Spectrum2D`); 1D bridge contract pinned against `nus/qc.py::_load_1d_shifts()` + `cli/pick.py::pick_1d`'s JSON shape; CLI registration pattern pinned against `cli/nus.py`/`cli/main.py` |
| JCLI-02 | JCAMP-derived peaks pass through the unchanged QC gate (PASS/PARTIAL/FAIL); edited-HSQC sign survives the round-trip; `case.md` + 5-agent team stay byte-unchanged | QC wiring order pinned against `cli/nus.py::pipeline`'s exact staged/final two-call pattern; edited-sign preservation traced through `bridge_peak_pick()`'s `detect_multiplicity_edited(spectrum.data)` call (depends only on `Spectrum2D.data`'s sign, which `JcampReader.read_2d()`'s Y-FACTOR scaling already preserves); byte-unchanged mechanism researched (no prior committed test exists; SHA-256 golden-hash approach recommended, baseline hashes computed below) |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01** — Single top-level `lucy jcamp <dir-or-files>` command, full-chain (read → pick → QC → write in one invocation). Accepts a directory (auto-discover `*.dx`) *and* an explicit file list. `--format json` on the command. No `lucy jcamp qc` subcommand — standalone QC re-use rides the existing `lucy nus qc <peaks-dir>` (same `nmr_peaks` schema).
- **D-02** — Output default `<input-dir>/analysis/nmr_peaks/`, with `--out <dir>` override. Mirrors the NUS pattern.
- **D-03** — `lucy jcamp` peak-picks the 1D JCAMP files itself via a **new thin 1D bridge** — a direct in-memory call to the existing `processing/peak_picker.py` 1D picker (no new picker, no shell-out to `cli/pick.py`). 1D outputs named so the QC gate's keyword-glob finds them (`13c_*` / `1h_*`). This makes the all-JCAMP dataset self-sufficient (1D lists serve both as CASE input and as the QC gate's trusted 1D reference).
- **D-04** — prot/quaternary classification uses the QC gate's existing `detection/` fallback (Phase-99 D-03), fed from the picked 1D-13C list. `C20H32O2-jcamp` has no DEPT, so the DEPT branch does not apply; the built-in multiplicity/hybridisation fallback is used — non-circular (does NOT use the HSQC-under-test), zero change to the byte-unchanged `qc.py`. A config/CLI known-quaternary override (the 5 §8 shifts 142.0/135.86/79.35/36.23/37.86) is kept only as an escape-hatch, never the default.
- **D-05** — Phase-102 QC depth = wired + mechanically discriminating; full green is Phase 103. Phase 102 must show the unchanged QC gate **runs** over the JCAMP peaks and **discriminates** (PASS/PARTIAL/FAIL reachable; verdict + soft violations surfaced in the peak-JSON metadata block). Driving the real dataset to QC PASS / §8 quality is Phase 103 / JVAL — do not pull JVAL validation into 102.
- **D-06** — NOESY & any non-{HSQC/HMBC/COSY/1H/13C} file: read but do not pick, skip with a visible warning, non-fatal. `bridge_peak_pick` supports only HSQC/HMBC/COSY (raises otherwise); the command must catch/route around that, log which files were skipped and why, and still produce consumable lists for the supported experiments.

### Claude's Discretion

- Provenance semantics in the reused `reconstruction` metadata block for the JCAMP path (e.g. `backend="jcamp"` / external-mddnmr-TopSpin origin) and the `caveat` text — planner discretion within the stable per-peak schema.
- Exact location/name of the new 1D-bridge helper (whether it lives beside `nus/bridge.py`, in a new module, or under `readers/`) — note the function is generic, only the `nus/` package name is NUS-flavoured.
- Where the `lucy jcamp` command module lives and how it is registered on the `lucy` group (mirror the import-safe `cli/nus.py` registration pattern).
- The `case.md` + 5-agent-team byte-unchanged guarantee (JCLI-02 / criterion 4) should be asserted by a diff-based test — planner picks the mechanism.

### Deferred Ideas (OUT OF SCOPE)

- **NOESY consumption by the CASE constraint model** (JC-F1) — NOESY reads and could be picked, but CASE has no NOESY constraint path yet; not this milestone.
- **Full C20H32O2-jcamp green QC + CASE convergence** — Phase 103 / JVAL-01/02 (D-05 boundary), not 102.
- **JCAMP writing / other vendor formats** (JC-F3 / JC-F2) — out of scope this milestone.
- **RECON-F1** (hmsIST/mddnmr in-lucy-ng NUS fallback) — carried from v10.0; unrelated to reading already-reconstructed JCAMP here.

None — discussion stayed within phase scope (no todos surfaced for folding).
</user_constraints>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JCAMP file discovery (dir/file-list) + routing per experiment type | CLI (`cli/jcamp.py`) | — | New command's own responsibility; no existing discovery logic to reuse (NUS path takes a single `expdir`, not a directory of independent files) |
| 2D spectrum decode (DIFDUP/NTUPLES assembly, ppm axes) | Reader (`readers/jcamp.py`) | — | Already shipped (Phase 101); Phase 102 is a pure consumer EXCEPT for the homonuclear-dimension bug fix (Pitfall #1), which also belongs here |
| 2D peak-picking + CASE-schema serialization | Domain/bridge (`nus/bridge.py::bridge_peak_pick`) | — | **Reused unchanged** — this is the entire point of the phase; a `Spectrum2D` in, a schema-correct dict out |
| 1D peak-picking + CASE-schema serialization | Domain/bridge (**new** 1D bridge function) | CLI (`cli/jcamp.py` calls it) | Genuinely new glue (D-03); must match `cli/pick.py::pick_1d`'s JSON shape exactly since the QC gate parses that shape verbatim |
| QC grading (PASS/PARTIAL/FAIL) | Domain (`nus/qc.py::run_qc_checks`) | — | **Reused byte-unchanged** — discovers its inputs purely by filename keyword-glob over the output directory; the CLI's only job is to name files correctly |
| Write/quarantine boundary (D-07 spirit) | CLI (`cli/jcamp.py`) | — | Mirrors `cli/nus.py::pipeline`'s exact staged-then-final two-call pattern; this phase's CLI owns replicating that pattern, not inventing a new one |
| `case.md` / 5-agent-team orchestration | Orchestrator (`.claude/commands/lucy-ng/case.md` + `.claude/agents/lucy-*.md`) | — | **Explicitly out of scope** — Phase 102 must not touch this tier at all (success criterion 4); the "CASE pipeline unchanged" invariant continues unbroken |

## Standard Stack

No new external packages this phase. Everything needed is already a core dependency:

| Library | Version (installed) | Purpose | Why no new dep |
|---------|---------|---------|--------------|
| `nmrglue` | 0.12-dev (already core, imported by `readers/bruker.py` and `readers/jcamp.py`) | JCAMP-DX parsing (via `readers/jcamp.py`) | Phase 101 already established this — no `[jcamp]` extra needed (101-CONTEXT.md D-11 note) |
| `click` | already core | CLI framework | Matches every existing `lucy` subcommand |
| `numpy` | already core | Array ops (`Spectrum2D.data`, ppm scales) | — |
| `pydantic` v2 | already core | `Spectrum1D`/`Spectrum2D`/`QcReport` models | — |

### Alternatives Considered

None — this is a pure-glue phase over an already-locked stack; no library choice is open.

**Installation:** none required.

## Package Legitimacy Audit

**Not applicable.** This phase introduces zero new external packages (confirmed above: nmrglue/click/numpy/pydantic are all pre-existing core dependencies). The Package Legitimacy Gate protocol is skipped per its own "whenever this phase installs external packages" trigger condition — no packages to check.

## Architecture Patterns

### System Architecture Diagram

```
                          lucy jcamp <dir-or-files> [--out DIR] [--format json]
                                          │
                                          ▼
                          ┌───────────────────────────────┐
                          │  Discover *.dx (dir mode) or   │
                          │  use the given file list       │
                          └───────────────┬───────────────┘
                                          │  per .dx file
                                          ▼
                          ┌───────────────────────────────┐
                          │  JcampReader.read(path)         │  (Phase 101, unchanged
                          │  dispatch on ##NUM DIM=         │   EXCEPT the homonuclear
                          └──────┬─────────────────┬───────┘   dim-resolution fix,
                                 │                  │            Pitfall #1)
                     Spectrum1D  │                  │  Spectrum2D
                                 ▼                  ▼
                  ┌───────────────────────┐  ┌─────────────────────────────┐
                  │  experiment = 1H/13C? │  │ experiment_type in           │
                  │  (nucleus-derived)    │  │ {HSQC,HMBC,COSY}?             │
                  └──────────┬────────────┘  │   NO  → log skip, continue   │  (D-06)
                             │ YES           │   (NOESY / unrecognized)     │
                             ▼               └──────────────┬───────────────┘
                  ┌───────────────────────┐                  │ YES
                  │  NEW: 1d bridge         │                  ▼
                  │  (direct call to        │      ┌─────────────────────────────┐
                  │  AdaptivePeakPicker      │      │ bridge_peak_pick(spectrum,   │
                  │  .pick_peaks())          │      │   experiment=...,             │
                  │  → cli/pick.py's exact   │      │   qc_report=None,             │  STAGED pass
                  │    1D JSON shape         │      │   recon_meta={backend:jcamp}) │  (no verdict yet)
                  └──────────┬──────────────┘      └──────────────┬───────────────┘
                             │                                    │
                             ▼                                    ▼
                  write_peak_json(out, "13C"/"1H", payload)   write_peak_json(staged_dir, ...)
                             │                                    │
                             └──────────────┬─────────────────────┘
                                            ▼
                          ┌───────────────────────────────┐
                          │  nus.qc.run_qc_checks(out_dir)  │  (Phase 99, BYTE-UNCHANGED)
                          │  keyword-globs 13c/1h/hsqc/      │  discovers 1D refs + 2D
                          │  hmbc/cosy by filename substring  │  correlations purely by
                          └───────────────┬───────────────┘  filename, no code change
                                          │  QcReport(verdict, checks, ...)
                                          ▼
                          ┌───────────────────────────────┐
                          │  PASS/PARTIAL → bridge_peak_pick│  FINAL rebuild (same
                          │  again with qc_report=report →  │  positions, verdict-derived
                          │  write to analysis/nmr_peaks/    │  confidence) — mirrors
                          │  FAIL → quarantine, exit non-zero│  cli/nus.py::pipeline
                          └───────────────────────────────┘  exactly (Q3 below)
```

### Recommended Project Structure

```
src/lucy_ng/
├── cli/
│   └── jcamp.py          # NEW: `lucy jcamp` command (single command, mirrors cli/nus.py's
│                          #   deferred-import convention; NOT a click.group() — D-01 wants
│                          #   one top-level command, not a subcommand group)
├── nus/
│   └── bridge.py          # UNCHANGED — bridge_peak_pick() reused directly for HSQC/HMBC/COSY
│   └── qc.py               # UNCHANGED — run_qc_checks() reused directly
├── readers/
│   └── jcamp.py            # MODIFIED (planner discretion location) — fix the homonuclear
│                            #   _resolve_dim degeneracy bug (Pitfall #1); NOT byte-protected
├── processing/
│   ├── peak_picker.py       # UNCHANGED — AdaptivePeakPicker.pick_peaks(), 1D bridge's target
│   └── jcamp_1d_bridge.py   # NEW (or wherever discretion places it) — the thin 1D bridge
│                            #   producing cli/pick.py::pick_1d's exact JSON shape
```

### Pattern 1: 2D reuse is a direct plug-in, no adapter needed

**What:** `JcampReader.read_2d(path) -> Spectrum2D` and `nus.bridge.bridge_peak_pick(spectrum: Spectrum2D, *, experiment: str, ...) -> dict` share the exact `Spectrum2D` type. There is no `build_spectrum2d()`-equivalent translation step for JCAMP — that function exists in `nus/bridge.py` specifically to reconstruct `Spectrum2D` from a raw NMRPipe `.ft2` file (a Phase-98 artifact), which JCAMP does not produce.

**When to use:** Every 2D `.dx` file whose `experiment_type` is HSQC/HMBC/COSY.

**Example:**
```python
# Source: src/lucy_ng/nus/bridge.py (verified signature, read 2026-07-25)
from lucy_ng.readers.jcamp import JcampReader
from lucy_ng.nus.bridge import bridge_peak_pick, write_peak_json

spectrum = JcampReader.read_2d(path)          # Spectrum2D, experiment_type already set
if spectrum.experiment_type not in {"HSQC", "HMBC", "COSY"}:
    # D-06: log + skip, non-fatal
    ...
    continue

recon_meta = {"backend": "jcamp", "iterations": None}
staged = bridge_peak_pick(spectrum, experiment=spectrum.experiment_type,
                           qc_report=None, recon_meta=recon_meta)
write_peak_json(staged_dir, spectrum.experiment_type, staged)
```

### Pattern 2: Two-call staged/final QC wiring (D-05 causal-ordering fix, already solved by Phase 99 — reuse identically)

**What:** `bridge_peak_pick()` is called **twice**: once with `qc_report=None` (peaks must exist before QC can grade them — produces a "pending_qc" placeholder payload written to a *staged* subdirectory only QC reads), then again with the real `QcReport` once `run_qc_checks()` has run against the staged directory, to rebuild the FINAL verdict-annotated payload that is actually written to the consumable `analysis/nmr_peaks/` location. Peak positions are deterministic for the same spectrum, so the rebuild reproduces identical cross-peaks, just with the correct confidence/metadata stamped in.

**When to use:** Exactly this ordering, every time — this is `cli/nus.py::pipeline`'s existing, already-battle-tested solution to a problem Phase 102 does NOT need to re-solve.

**Example:**
```python
# Source: src/lucy_ng/cli/nus.py::pipeline (verified, lines ~584-637, read 2026-07-25)
# STAGED pass (verdict-less): peaks must exist before QC can grade them.
staged_payload = bridge_peak_pick(
    spectrum, experiment=experiment_type, qc_report=None, recon_meta=recon_meta
)
staged_dir = stage_dir / "staged"
write_peak_json(staged_dir, experiment_type, staged_payload)

# QC gate — the SAME code path `lucy nus qc` calls standalone.
report = run_qc_checks(staged_dir, config)

if report.verdict == QcVerdict.FAIL:
    # hand-build the quarantine payload (confidence_from_verdict() intentionally
    # raises for FAIL — there is no honest confidence to emit)
    ...
else:
    # CAUSAL RE-BUILD — reproduces identical cross-peaks, now with the real verdict.
    final_payload = bridge_peak_pick(
        spectrum, experiment=experiment_type, qc_report=report, recon_meta=recon_meta
    )
    write_peak_json(nmr_peaks_dir, experiment_type, final_payload)
```

For a JCAMP *directory* (multiple 2D + 1D files), the staged directory must accumulate **all** staged files (1D references AND 2D correlations) before `run_qc_checks()` is invoked once — the QC gate needs the 1D reference lists present in the same directory it grades the 2D correlations from (`_glob_by_keyword`/`_load_1d_shifts` read from the same `peaks_dir`). Concretely: pick ALL files first (staged), THEN run `run_qc_checks()` ONCE, THEN rebuild all 2D files' final payloads — not once per file.

### Pattern 3: 1D bridge output MUST match `cli/pick.py::pick_1d`'s schema, not the 2D per-experiment schema

**What:** `nus/qc.py::_load_1d_shifts()` reads `data.get("peaks", [])` and each peak's `"ppm"` key. This is `cli/pick.py::pick_1d`'s JSON output shape (`{"count":.., "peaks": [{"ppm":.., "intensity":.., "snr":..}]}`), **not** the 2D `cross_peaks` shape `nus/bridge.py` produces. The new 1D bridge must reproduce this exact top-level/per-peak key structure so the byte-unchanged `qc.py` can discover it.

**When to use:** Every 1D `.dx` file (`nucleus == "1H"` or `"13C"`).

**Example:**
```python
# Source: src/lucy_ng/cli/pick.py::pick_1d (verified exact JSON shape, read 2026-07-25)
data = {
    "count": len(peaks.peaks),
    "noise_sigma": peaks.noise_sigma,
    "negative_detected": has_significant_negative,
    "snr_floor_used": snr_floor_used,
    "peaks": [
        {"ppm": p.position, "intensity": p.intensity, "snr": p.snr}
        for p in peaks.peaks
    ],
}
```
The new 1D bridge should call `AdaptivePeakPicker.pick_peaks(spectrum, use_snr=True)` (the same default `cli/pick.py::pick_1d` uses) directly and serialize into this exact shape, writing to `<out>/13C.json` / `<out>/1H.json` (or any filename whose lowercased form contains `"13c"`/`"1h"` — `_glob_by_keyword` is a case-insensitive substring match, not an exact-name match).

### Anti-Patterns to Avoid

- **Building a `build_spectrum2d()`-style adapter for JCAMP:** Not needed — `JcampReader.read_2d()` already IS the `Spectrum2D` builder. Writing an adapter here would be needless indirection contradicting the "reuse, don't reimplement" spirit of the phase.
- **Reusing the 2D `cross_peaks` schema for 1D output:** The unchanged `qc.py` explicitly reads `peaks[].ppm`, not `cross_peaks[].c13_ppm`/`h1_ppm`. A 1D bridge that emits the 2D schema will make the QC gate's `_load_1d_shifts()` silently return an empty list (no exception — see Pitfall #4), producing a confusing false "insufficient_reference_data" result rather than a clear failure.
- **Running `run_qc_checks()` once per experiment file:** The QC gate reads the WHOLE peaks directory each call (it globs by keyword across all files present). Calling it once per 2D file mid-loop, before all 1D reference files have been staged, risks a spurious `insufficient_reference_data` result for files processed early. Stage everything first, then QC once.
- **Adding a duplicate `lucy jcamp qc` subcommand:** Explicitly rejected by D-01 — the schema is identical to the NUS path, so `lucy nus qc <peaks-dir>` already covers standalone re-grading of JCAMP-derived peaks.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 2D peak picking from a `Spectrum2D` | A new picker or a JCAMP-specific pick function | `nus.bridge.bridge_peak_pick()` (calls the existing `PeakPicker2D.pick_peaks()` unmodified) | This is the entire point of the phase — Phase 99 already solved schema serialization, edited-sign gating, and metadata embedding |
| QC grading | A JCAMP-specific QC module | `nus.qc.run_qc_checks()` (byte-unchanged) | Discovers its inputs purely by filename keyword-glob; zero coupling to *how* the peaks were produced (NUS vs JCAMP) |
| Edited-HSQC sign detection | A JCAMP-specific sign detector | `processing.edited_sign.detect_multiplicity_edited()` (already the importable twin of `cli/pick.py`'s private detector, used internally by `bridge_peak_pick()`) | Already solved, already the exact function the reused bridge calls — no new code needed at all |
| 1D peak picking | A JCAMP-specific 1D picker | `processing.peak_picker.AdaptivePeakPicker.pick_peaks()` | Existing, solvent-aware, SNR/MAD-based 1D picker; only the JSON *serialization* is new (D-03) |
| Experiment-type detection from pulse program | A JCAMP-specific classifier | `readers.bruker._detect_experiment_type()` (already imported/re-exported by `readers/jcamp.py` per Phase-101 D-10, and already used inside `JcampReader.read_2d()`) | Single source of truth for pulse-program → experiment-type mapping, already exercised on real HSQC/HMBC/COSY/NOESY pulse programs |
| Byte-unchanged verification for `case.md`/agents | A custom git-plumbing test | Frozen SHA-256 content hash comparison (see Pitfall #5) OR `git diff --exit-code <baseline-ref> -- <paths>` | Neither exists yet in the repo (verified: no prior test asserts this); pick the simplest mechanism, don't invent a new verification framework |

**Key insight:** Every single piece of "hard" logic in this phase already exists and is proven (peak-picking, QC checks, sign detection, experiment classification). The only genuinely new production code is: (1) the CLI's file-discovery + routing loop, (2) the 1D bridge's JSON serialization, and (3) — newly discovered by this research — a fix to `readers/jcamp.py`'s homonuclear dimension resolution.

## Common Pitfalls

### Pitfall 1 (CRITICAL): `readers/jcamp.py::_resolve_dim` raises for homonuclear 2D experiments — COSY is currently unreadable, not just NOESY

**What goes wrong:** `_resolve_dim()` finds the target nucleus's `(offset, sf)` pair by locating a UNIQUE match in the file's `$NUC1` list. For a heteronuclear experiment (HSQC/HMBC: `$NUC1 = ['<1H>', '<13C>']`) this works. For a **homonuclear** experiment (COSY/NOESY: both dimensions are `1H`), `$NUC1` contains the *same* nucleus string twice, and `_resolve_dim` explicitly raises `ValueError` on ambiguity ("Ambiguous nucleus '1H' appears 2 times ... deferred to Phase 103") rather than silently picking one. `JcampReader.read_2d()` calls `_resolve_dim` for BOTH the F1 and F2 axis — so `read_2d()` itself raises before `bridge_peak_pick()` is ever called.

**Why it happens:** `101-03-SUMMARY.md`'s own decision log documents this as a known, deliberate deferral at Phase 101 close ("homonuclear axis resolution ... is out of scope for this phase"), but the deferral target ("Phase 103") does not match Phase 103's actual scope in ROADMAP.md (end-to-end *validation*, not reader fixes) — this looks like a stale forward-reference in the summary, not an intentional scope boundary honored by the roadmap.

**Evidence (verified directly against the real, external dataset, 2026-07-25):**
```
$ grep -n '\$NUC1\|\$SF=\|\$OFFSET' ~/.../C20H32O2-jcamp/C20H32O2_COSY.dx
2092:##$NUC1= <1H>
2358:##$OFFSET= 7.050608
2378:##$SF= 499.92
2423:##$NUC1= <1H>
2511:##$OFFSET= 7.051546
2531:##$SF= 499.92
```
Two `$NUC1= <1H>` entries, with two *different* `$OFFSET` values (7.050608 vs 7.051546) but the same `$SF` (499.92) — confirming the two dimensions ARE distinguishable positionally (different calibration per dimension) even though nucleus-content matching can't tell them apart. `C20H32O2_NOESY.dx` shows the identical pattern. `C20H32O2_HMBC.dx` (heteronuclear) by contrast shows `$NUC1= <1H>` then `$NUC1= <13C>` — no ambiguity, confirming the bug is specific to homonuclear files.

**How to avoid:** Extend `_resolve_dim`'s ambiguous branch to fall back to **positional** resolution instead of raising, using the same "procs-then-proc2s" ordering convention Phase 101 already established and verified for the heteronuclear case (`101-03-SUMMARY.md`: "`$NUC1` is co-indexed with `$SF`/`$OFFSET`, both in 'procs-then-proc2s' parse order" — i.e. index 0 = F2/direct dimension, index 1 = F1/indirect dimension). Since `SYMBOL`'s declared F1/F2 order is already resolved separately for `.NUCLEUS`, the homonuclear case can reuse the *same* positional convention: when the nucleus match count is 2 and the nuclei are identical, treat index 0 as F2's pair and index 1 as F1's pair (matching the already-verified real-file evidence that index 0's `$OFFSET` (7.050608) equals the real 1H reference spectrum's own `$OFFSET` from the HSQC F2 dimension — cross-checkable against the committed `C20H32O2_1H.dx` fixture).

**Warning signs:** Any Phase-102 CLI test/spike that attempts `JcampReader.read_2d()` on a real or realistic COSY/NOESY `.dx` file and gets a `ValueError: Ambiguous nucleus '1H' appears 2 times` — this is NOT a CLI wiring bug, it is this exact reader defect. Do not "fix" it by catching and skipping COSY under D-06 without an explicit planning decision — D-06 is scoped to NOESY-and-unrecognized, not to a name-checked required experiment (COSY) that Phase 102's own success criteria require working.

### Pitfall 2: 1D bridge schema mismatch is a silent failure, not a loud one

**What goes wrong:** If the new 1D bridge accidentally emits `cross_peaks`/`c13_ppm`/`h1_ppm` (the 2D schema) instead of `peaks`/`ppm` (the 1D schema), `nus/qc.py::_load_1d_shifts()` does not raise — it simply finds no `"peaks"` key (`data.get("peaks", [])` defaults to `[]`) and returns an empty shift list. Downstream, `QcReferenceData.resolve()` proceeds with `trusted_c13=[]`, and `check_hsqc_coverage()` falls back to the hardcoded `PROTONATED_REFERENCE` (a *different*, silently-substituted behavior, not a crash) — masking the schema bug behind a plausible-looking but wrong QC run.

**Why it happens:** The 2D and 1D schemas share superficial vocabulary ("ppm", "peaks") but different top-level/per-peak key names; it is easy to reuse the wrong helper by analogy to the 2D bridge just built.

**How to avoid:** Write a unit test asserting the new 1D bridge's raw dict has a top-level `"peaks"` key whose elements have a `"ppm"` key (matching `cli/pick.py::pick_1d`'s exact shape), and a second test that runs the real `run_qc_checks()`/`QcReferenceData.resolve()` against a directory containing ONLY the 1D bridge's output and asserts `classification_source != "insufficient_reference_data"` for the c13 shift list specifically (i.e. `trusted_c13` is non-empty).

**Warning signs:** QC verdict comes back with `hsqc_coverage`'s `details` referencing the hardcoded reference count rather than a count derived from the actual picked 1D file — a strong sign the 1D reference file was not discovered.

### Pitfall 3: Filename keyword-glob is case-insensitive substring matching, not experiment-name equality

**What goes wrong:** `_glob_by_keyword` does `keyword in p.name.lower()`. Naming a file e.g. `HSQC_edited.json` still matches keyword `"hsqc"` (fine), but naming a stray diagnostic file e.g. `hsqc_debug_1h_trace.json` would ALSO match BOTH the `"hsqc"` 2D glob AND the `"1h"` 1D glob simultaneously, double-counting it in two different roles.

**How to avoid:** Name output files simply and exactly: `HSQC.json`, `HMBC.json`, `COSY.json`, `13C.json`, `1H.json` (matching `bridge_peak_pick`'s own `write_peak_json(out_dir, experiment, payload)` convention of `f"{experiment}.json"`). Do not write any other `.json` files into the same `analysis/nmr_peaks/` output directory (e.g. don't drop a debug/manifest file there — put it elsewhere or exclude it explicitly).

### Pitfall 4: `QcConfig.default()`'s "escape-hatch" quaternary override is already the compiled-in default — there is currently no CLI flag to disable it

**What goes wrong:** CONTEXT.md's D-04 describes the known-quaternary override "kept only as an escape-hatch, never the default" — but `nus/qc.py::QcConfig`'s dataclass default is `known_quaternary_shifts: tuple[float, ...] = DEFAULT_QUATERNARY_SHIFTS` (the 5 §8 shifts), which is **already** compound-specific (C20H32O2's own known quaternaries) and **already** the default whenever no DEPT file is present — i.e. exactly the `C20H32O2-jcamp` scenario. Since `qc.py` cannot be edited, `lucy jcamp`'s QC pass will use `classification_source="override"` with these 5 hardcoded shifts by default, not `"insufficient_reference_data"` — this is a byte-unchanged-qc.py-inherited behavior, not something Phase 102 chooses.

**Why it happens:** The wording in CONTEXT.md describes intent from the *user's* perspective (this override shouldn't be silently generalized to other compounds), but the actual code makes it the unconditional fallback default whenever DEPT is absent, for any compound.

**How to avoid:** Document this explicitly rather than trying to "fix" it (fixing it means editing `qc.py`, which is prohibited). Also note: neither `lucy nus qc` nor `lucy nus pipeline`'s existing `_build_qc_config()` (in `cli/nus.py`) exposes a CLI flag to override `known_quaternary_shifts` at all today — the only way to reach `"insufficient_reference_data"` tier-3 is to construct a `QcConfig(known_quaternary_shifts=())` programmatically. If a genuine escape hatch is wanted, it would require adding a new CLI flag to `cli/nus.py` (not byte-protected) — but this expands scope beyond JCLI-01/02 and should be flagged to the user as an explicit, separate decision, not silently added.

### Pitfall 5: No prior committed test verifies "byte-unchanged" for `case.md` or the agent files — this mechanism must be built fresh

**What goes wrong:** Searching the full test suite (`grep -rln "case.md\|cli/pick.py\|hashlib\|git diff" tests/`) found `tests/test_case_md_wv07.py` (asserts specific SUBSTRINGS are present/absent in `case.md` — a content-contract test, not a byte-unchanged test) and `tests/nus/test_write_boundary.py` (asserts `git diff --exit-code src/lucy_ng/cli/pick.py` returns 0, as a **verify-command run manually during planning**, never committed as a pytest test). There is no existing pytest test anywhere in the repo that asserts `case.md` or any `.claude/agents/lucy-*.md` file is unchanged.

**How to avoid:** Build a new, self-contained pytest test using a frozen SHA-256 content hash (recommended over a git-ref diff, since content hashing needs no git subprocess and is immune to shallow-clone/history concerns). Concrete baseline hashes as of Phase 101 close (commit `22f2b52`, clean working tree, verified 2026-07-25):

| File | SHA-256 |
|------|---------|
| `.claude/commands/lucy-ng/case.md` | `8299791ead74294fa31424bae990de62d7bf73260d5dbdbe1e776539e7148d8b` |
| `.claude/agents/lucy-nmr-chemist.md` | `4dd7766e3746074062e5f05cefc4462ce85ee444c264c426298fb830c2760839` |
| `.claude/agents/lucy-lsd-engineer.md` | `0e9ffcbe4856f9980ed19b5384fb9c7050b20d6427901d0e1ae3ffc1a8507f3b` |
| `.claude/agents/lucy-solution-analyst.md` | `dbe9da127ed576aca22fd9d34bf6b599b2e7765b29dffb90fcae83e29dc290f2` |
| `.claude/agents/lucy-devils-advocate.md` | `ee80ace79e5785b810e6d9da295f1d31e01ecfa6758f71a3b77d7768c5cbb34f` |
| `.claude/agents/lucy-diagnostic.md` | `74bd725c4067be5f076c78424632b7f9d6b4111322d9947fbcbe804a8cfcdbb2` |

Note: `.claude/agents/supervisor.md` exists in the repo but is **not** named as part of "the 5-agent team" by either the CLAUDE.md description (`lucy-nmr-chemist`, `lucy-lsd-engineer`, `lucy-solution-analyst`, `lucy-devils-advocate` + `lucy-diagnostic` on escalation) or the CONTEXT.md's own list — do not include it in the byte-unchanged guard unless the planner confirms it belongs.

Read these files with **repo-relative paths** (`.claude/commands/lucy-ng/case.md`, not the `~/.claude/...` symlink target — confirmed both point to the same physical file, so either works, but repo-relative matches the existing `test_case_md_wv07.py` convention and needs no `$HOME` expansion).

**Warning signs:** none applicable in advance — this is a preventive mechanism, not a bug to detect.

### Pitfall 6: `PeakPicker2D`/`bridge_peak_pick` were designed and tested against synthetic/small arrays and a 2048×2048 NMRPipe `.ft2` — verify against the REAL 2048×2048 JCAMP-derived matrix, not just the 16-row trimmed fixture

**What goes wrong:** The only committed 2D fixture is `C20H32O2_HSQC_trimmed.dx` (16 F1 rows × 2048 F2 points). This is sufficient to prove the reader/bridge wiring is *structurally* correct, but the trimmed fixture's tiny F1 dimension means noise statistics (`_compute_2d_noise_sigma`'s global MAD) are computed over a much smaller, non-representative sample than the real 2048×2048 matrix. A CI test built only against the trimmed fixture cannot prove the picker's SNR-floor behavior generalizes to the full real spectrum.

**How to avoid:** Be explicit in the plan and VALIDATION.md about which claims are proven by the trimmed CI fixture (schema wiring, QC-gate discovery, byte-unchanged invariants) versus which claims require the real, external, uncommitted dataset (peak-count plausibility, QC PASS/PARTIAL discrimination on a real spectrum) — the latter is explicitly Phase 103 / JVAL's job (D-05), not Phase 102's. Do not let a green CI suite on the trimmed fixture alone stand in for "verified on real data" (the Phase-100 meta-lesson this whole milestone was designed to avoid).

## Code Examples

### CLI registration pattern (mirror exactly)

```python
# Source: src/lucy_ng/cli/main.py (verified, read 2026-07-25)
from lucy_ng.cli.jcamp import jcamp
...
cli.add_command(jcamp)
```

`cli/jcamp.py` should follow `cli/nus.py`'s exact deferred-import convention (all `lucy_ng.readers.jcamp`/`lucy_ng.nus.bridge`/`lucy_ng.nus.qc` imports deferred into the command body) — even though none of these need an optional extra today, this keeps the pattern consistent and future-proof if a heavier JCAMP-only dependency is ever added.

```python
# Source: src/lucy_ng/cli/nus.py module docstring (verified pattern, read 2026-07-25)
"""...This module is import-safe: it does NOT import ``lucy_ng.nus.params``... at
the top level. All ``lucy_ng.nus.*`` imports are deferred into command bodies..."""
```

D-01 wants a single top-level command (`@click.command()`), not a `@click.group()` — unlike `cli/nus.py`'s `nus` group (which has 6 subcommands), `lucy jcamp` has exactly one entry point. Register it directly with `cli.add_command(jcamp)`, matching how a bare `@click.command()` is added elsewhere if any exists, or simply give it a trivial one-command "group" if Click ergonomics prefer — planner discretion, but D-01 is explicit that no `lucy jcamp qc`/`lucy jcamp <subcommand>` surface should exist.

### `--format json` convention (mirror exactly across all 20+ existing subcommands)

```python
# Source: src/lucy_ng/cli/nus.py (verified, every subcommand repeats this exact option block)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| NUS reconstruction chain (`bruk2pipe`/SMILE, external binary, memory-abort-prone) | JCAMP ingestion (already-reconstructed, no external binary) | v10.1 (this milestone) | Phase 102's whole job is proving the SAME downstream (bridge + QC) generalizes across two entirely different upstream sources — a direct test of Phase 99's design generality |
| `build_spectrum2d()` (NMRPipe `.ft2` → `Spectrum2D`) | `JcampReader.read_2d()` (JCAMP `.dx` → `Spectrum2D` directly) | Phase 101 (2026-07-23) | Phase 102 does NOT need an equivalent adapter — one fewer moving part than the NUS path had |

**Deprecated/outdated:** none within this phase's scope — everything reused is the CURRENT, just-shipped Phase 99/101 code, not a legacy path.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_resolve_dim`'s homonuclear ambiguity should be resolved via the "procs-then-proc2s" positional convention (index 0 = F2/direct, index 1 = F1/indirect), by analogy with the already-verified heteronuclear case | Pitfall 1 | If the positional convention doesn't actually hold for homonuclear COSY/NOESY files (only verified for heteronuclear HSQC/HMBC so far), the fix could silently swap F1/F2 axes for COSY — would need its own explicit cross-check against the real 1D `1H` reference (mirroring JC-02's existing verification pattern) before trusting it |
| A2 | The "5-agent team" byte-unchanged guard covers exactly `lucy-nmr-chemist.md`, `lucy-lsd-engineer.md`, `lucy-solution-analyst.md`, `lucy-devils-advocate.md`, `lucy-diagnostic.md` (5 files) — NOT `supervisor.md` | Pitfall 5 | If `supervisor.md` is actually meant to be included (CONTEXT.md doesn't clarify), the byte-unchanged test would have a gap; low risk since this phase's own work has no reason to touch any `.claude/` file at all |
| A3 | `lucy jcamp` does not need its own QC-threshold-override CLI flags (`--ridge-fail`/`--coverage-floor`/etc.) mirroring `lucy nus qc`'s — users needing custom thresholds re-run `lucy nus qc <same-out-dir>` afterward | Don't Hand-Roll table / Pattern 2 | If the planner or user wants `lucy jcamp` itself to be threshold-configurable in one invocation, this assumption under-scopes the CLI surface; low risk since D-01 already establishes standalone QC lives on `lucy nus qc`, not a duplicate `lucy jcamp qc` |
| A4 | A single new `@click.command()` (not a `@click.group()`) is the right Click construct for `lucy jcamp`, registered directly via `cli.add_command(jcamp)` | Code Examples | If Click's `add_command` requires a Group specifically (it does not — `click.Command` instances register fine on a parent `Group` via `add_command`), this would need adjustment; LOW risk, standard Click usage |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Should Phase 102 fix the homonuclear `_resolve_dim` bug itself, or should the phase boundary be renegotiated?**
   - What we know: The bug is real, verified against the actual external dataset, and blocks COSY (a named, required experiment for this phase's own success criteria) — not just NOESY (which D-06 already plans to skip).
   - What's unclear: Whether the planner treats this as "Phase 102 extends the reader" (in scope, since `readers/jcamp.py` isn't byte-protected) or escalates it as a discussion topic before planning proceeds, given it touches a file Phase 101 already closed out.
   - Recommendation: Treat as in-scope for Phase 102 (the file isn't protected, and Phase 102 cannot meet its own success criteria without it) — but flag it explicitly as the phase's first, highest-risk task, verified against the real 1D references the same way JC-02 was verified, before building the CLI wiring around it.

2. **Does the 1D bridge need its own "negative peak" auto-detection (mirroring `cli/pick.py::pick_1d`'s `has_significant_negative` heuristic), or is it always `False` for 1H/13C JCAMP files?**
   - What we know: `C20H32O2-jcamp` has no DEPT `.dx` file, so no 1D file in this dataset is expected to have genuine negative peaks.
   - What's unclear: Whether to hardcode `detect_negative=False` for simplicity (since only 1H/13C are read) or replicate `pick_1d`'s exact auto-detect logic for parity/future-proofing (e.g. if a DEPT `.dx` is added later per JC-F1-adjacent scope).
   - Recommendation: Replicate `pick_1d`'s exact auto-detect logic (cheap to copy, keeps behavior byte-identical to the proven CLI path, and future-proofs for any 1D file with genuine negative signal).

3. **Where exactly should the 1D bridge function live?** (CONTEXT.md leaves this as Claude's Discretion.)
   - What we know: It needs to import `AdaptivePeakPicker` from `processing/peak_picker.py` and produce `cli/pick.py`-shaped JSON; it has no dependency on `nus/` at all (unlike the 2D path).
   - What's unclear: Whether co-locating it in a new `processing/` module (e.g. `processing/jcamp_1d_bridge.py`) or beside the CLI command itself is cleaner.
   - Recommendation: A small new module under `processing/` (parallel to `processing/edited_sign.py`'s precedent of "importable twin" modules) keeps it testable in isolation and mirrors the project's existing "thin tools around nmrglue/RDKit" layering — the CLI module then only orchestrates, it doesn't contain business logic.

## Environment Availability

Skipped — this phase has no new external dependencies beyond what Phase 101 (nmrglue, already core) and Phase 99 (click, numpy, pydantic, already core) already established. No new binary, service, or optional extra is introduced.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `pytest tests/test_cli_jcamp.py tests/readers/test_jcamp.py -q` |
| Full suite command | `pytest` (baseline at Phase 101 close: 1408 passed, 8 skipped, 1 xfailed) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JCLI-01 | `lucy jcamp <dir>` discovers `.dx` files, routes 1D→1D-bridge / 2D-HSQC-HMBC-COSY→`bridge_peak_pick`, writes `analysis/nmr_peaks/*.json` in the existing schema | integration (CLI, `CliRunner`) | `pytest tests/test_cli_jcamp.py -k test_jcamp_directory_mode -x` | ❌ Wave 0 (new test file) |
| JCLI-01 | `--format json` works on the command | unit | `pytest tests/test_cli_jcamp.py -k format_json -x` | ❌ Wave 0 |
| JCLI-01 (1D bridge) | 1D bridge output matches `cli/pick.py::pick_1d`'s exact JSON shape (`peaks[].ppm`, not `cross_peaks`) | unit | `pytest tests/processing/test_jcamp_1d_bridge.py -x` | ❌ Wave 0 (new test file) |
| JCLI-02 | QC gate runs unchanged over JCAMP-derived peaks and reaches a verdict | integration | `pytest tests/test_cli_jcamp.py -k test_jcamp_qc_wiring -x` | ❌ Wave 0 |
| JCLI-02 | Edited-HSQC sign survives the round-trip (a synthetic Spectrum2D with known negative CH2 peaks, picked via the real chain, still reports the correct `multiplicity_hint`) | unit/integration (synthetic Spectrum2D, mirrors `test_hmbc_peak_picking_integrity.py`'s pattern) | `pytest tests/test_cli_jcamp.py -k edited_sign -x` | ❌ Wave 0 |
| JCLI-02 (criterion 4) | `case.md` + 5-agent-team files are byte-unchanged (frozen SHA-256 hash comparison) | unit (golden-hash) | `pytest tests/test_case_byte_unchanged.py -x` | ❌ Wave 0 (new test file; baseline hashes listed in Pitfall 5) |
| (reader fix, blocking prerequisite) | `readers/jcamp.py::read_2d()` succeeds on a homonuclear (COSY/NOESY-shaped) fixture without raising | unit | `pytest tests/readers/test_jcamp.py -k homonuclear -x` | ❌ Wave 0 (extends existing test file; needs a new small COSY/NOESY-shaped fixture — see Wave 0 Gaps) |

### Sampling Rate

- **Per task commit:** `pytest tests/test_cli_jcamp.py tests/readers/test_jcamp.py tests/processing/test_jcamp_1d_bridge.py -q`
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_cli_jcamp.py` — CLI integration tests (directory mode, explicit-file-list mode, `--out` override, `--format json`, D-06 non-fatal skip on an unsupported/NOESY-shaped file, byte-unchanged `cli/pick.py`/`nus/qc.py`/`nus/bridge.py` diffs asserted at commit time as a manual verify step, not necessarily a pytest test)
- [ ] `tests/processing/test_jcamp_1d_bridge.py` (or wherever the 1D bridge lands) — schema-shape tests + a `run_qc_checks()` discovery test proving the QC gate finds the 1D bridge's output as trusted reference
- [ ] `tests/test_case_byte_unchanged.py` — golden-hash test for `case.md` + the 5 agent files (Pitfall 5)
- [ ] `tests/readers/test_jcamp.py` extension — a homonuclear-shaped fixture (small, synthetic or trimmed-real COSY/NOESY, mirroring `_generate_fixture.py`'s existing HSQC-trimming approach) proving `_resolve_dim`'s fix resolves F1/F2 correctly for a same-nucleus 2D file, cross-checked against the real 1H reference the same way JC-02 was (not just "doesn't raise")
- [ ] A small synthetic or trimmed-real COSY/HMBC/NOESY `.dx` fixture set is needed for full directory-mode CLI testing — currently ONLY the trimmed HSQC + full 1H/13C fixtures are committed (`tests/fixtures/jcamp/`); no HMBC/COSY/NOESY fixture exists yet. Without at least a minimal synthetic HMBC/COSY fixture, the D-06 multi-experiment directory-mode test can only mock rather than genuinely exercise `bridge_peak_pick` for those experiment types — flag any such test explicitly as mock-covered, not fixture-covered, per the Phase-100 meta-lesson.

## Security Domain

`security_enforcement` is absent from `.planning/config.json` (treated as enabled). This is a local, offline CLI tool with no network/auth/session surface, so most ASVS categories do not apply; the relevant one is input validation on untrusted file content.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — no authentication surface |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A — local filesystem tool, runs as the invoking user |
| V5 Input Validation | Yes | Malformed/truncated `.dx` files must fail loud (`ValueError`/`FileNotFoundError`, already `JcampReader`'s established convention) rather than being silently skipped or crashing the whole directory run uncontrolled; `--out`/directory arguments should be resolved (`Path.resolve()`, already the `cli/nus.py` convention) before use |
| V6 Cryptography | No | N/A — the recommended SHA-256 golden-hash mechanism (Pitfall 5) is an integrity check, not a security control; no secrets involved |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via a crafted `--out` argument | Tampering | `Path(out).resolve()` before any write (already the established convention in `cli/nus.py`'s `Path(expdir).resolve()`); no user-facing service boundary makes this low-severity for a local CLI, but the convention costs nothing to follow |
| A malformed `.dx` file in directory mode silently corrupting the whole batch | Tampering / Denial of Service | Per-file try/except around `JcampReader.read()` inside the directory loop (mirroring `nus/qc.py::_load_peaks()`'s per-file error-collection pattern) — one bad file must not abort the whole directory run, but must also not be silently treated as "0 peaks, all clean" (log it as a named failure, distinct from D-06's "unsupported experiment, skipped" case) |

## Sources

### Primary (HIGH confidence)

- `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/nus/bridge.py` — `bridge_peak_pick`, `write_peak_json`, `confidence_from_verdict`, `_VALID_BRIDGE_EXPERIMENTS`, HSQC/HMBC/COSY serializers, `_reconstruction_metadata_block` (read in full, 2026-07-25)
- `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/nus/qc.py` — `_glob_by_keyword`, `_load_1d_shifts`, `QcReferenceData.resolve`, `run_qc_checks`, `aggregate_verdict`, `CRITICAL_CHECKS`/`SOFT_CHECKS` (read in full, 2026-07-25)
- `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/readers/jcamp.py` — `JcampReader.read`/`read_1d`/`read_2d`, `_resolve_dim`, `_ppm_scale`, `_apply_yfactor` (read in full, 2026-07-25)
- `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/processing/peak_picker.py` — `AdaptivePeakPicker.pick_peaks`/`pick_peaks_instance` (read in full, 2026-07-25; note: the phase brief's "processing/peak_picker.py's 1D PeakPicker" is a misnomer — the actual class is `AdaptivePeakPicker`)
- `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/cli/pick.py` — `pick_1d`'s exact JSON shape, `_detect_multiplicity_edited` (read in full, 2026-07-25)
- `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/cli/nus.py` — full `qc`/`pipeline` command source, deferred-import convention, staged/final two-call pattern (read in full, 2026-07-25)
- `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/cli/main.py`, `/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/cli/read.py` — CLI group registration pattern (read in full, 2026-07-25)
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/C20H32O2_COSY.dx`, `C20H32O2_NOESY.dx`, `C20H32O2_HMBC.dx` — direct `grep` inspection of the real, external, uncommitted dataset confirming the homonuclear `$NUC1` ambiguity (Pitfall 1), 2026-07-25
- `.planning/phases/101-jcamp-dx-reader/101-03-SUMMARY.md`, `101-04-SUMMARY.md` — exact shipped decisions/deviations for the reader (read in full, 2026-07-25)
- `.planning/phases/99-peak-pick-bridge-qc-gate-cli/99-02-SUMMARY.md`, `99-03-SUMMARY.md`, `99-04-SUMMARY.md` — exact shipped decisions/deviations for the bridge/QC/CLI (read in full, 2026-07-25)
- `git log`/`shasum -a 256` on `.claude/commands/lucy-ng/case.md` and `.claude/agents/lucy-*.md` — verified current baseline hashes and confirmed symlink targets (2026-07-25)

### Secondary (MEDIUM confidence)

None — every claim in this document was verified directly against the on-disk source or the real dataset rather than inferred from documentation or web search.

### Tertiary (LOW confidence)

None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, fully verified as already-core.
- Architecture (2D reuse path): HIGH — verified by reading `bridge_peak_pick`/`JcampReader.read_2d` source directly; the two types match exactly.
- Architecture (1D bridge contract): HIGH — verified by reading `qc.py::_load_1d_shifts` and `cli/pick.py::pick_1d` source directly.
- Pitfalls: HIGH for Pitfall 1 (verified against the real external dataset with `grep`, not inferred) and Pitfall 5 (verified by searching the whole test suite); MEDIUM for Pitfall 4 (verified code behavior, but the "right" fix is a judgment call outside this phase's stated scope).

**Research date:** 2026-07-25
**Valid until:** Effectively pinned to the current commit (`22f2b52`) — the byte-unchanged baseline hashes in Pitfall 5 become stale the instant `case.md` or any agent file changes for any other reason; re-verify those hashes at plan time if any time has passed since this research.
