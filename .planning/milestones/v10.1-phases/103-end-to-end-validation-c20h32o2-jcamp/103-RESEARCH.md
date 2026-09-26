# Phase 103: End-to-End Validation (C20H32O2-jcamp) - Research

**Researched:** 2026-07-26
**Domain:** Proof/validation phase — real-data peak-pick tuning, QC grading, and CASE-orchestrator handoff for an already-shipped JCAMP-DX ingestion chain
**Confidence:** HIGH for the CLI/knob/QC mechanics (verified against real data in this session); MEDIUM for the CASE-convergence handoff (a documented, previously-unexercised integration gap was found — see Open Questions #1)

## Summary

Phase 103 runs the already-shipped `lucy jcamp` chain (Phase 102) against the real, external, 55 MB `C20H32O2-jcamp` dataset for the first time, tunes two already-existing knobs (`threshold`, `snr_floor`) per experiment, grades the result against the unchanged Phase-99 QC gate plus an independent §10 cross-check, and hands off to a fresh `/lucy-ng:case C20H32O2` run. Almost no new picking/QC logic is needed — the real engineering surface is (a) exposing the existing per-experiment `threshold`/`snr_floor` knobs on the `lucy jcamp` CLI as repeatable `key=value` options, (b) fixing one genuine, verified reader defect that currently blocks HMBC from being read at all, and (c) running a bounded, logged knob-matrix search against real data whose over-picking behavior at default settings is dramatically worse than any fixture previously exercised.

This session ran the real chain against the real dataset (read-only, output redirected to the scratchpad, nothing in either data directory touched) and obtained hard evidence for three previously-unproven claims from `102-VALIDATION.md`'s "NOT PROVEN — Phase 103 / JVAL" row: peak-count plausibility is **currently very wrong** at CLI defaults (HSQC picks 10,687 cross-peaks against an expected ~17–27; COSY picks 16,244), full-matrix SNR behavior is **provably different** from the 16-row fixture behavior characterized in Phase 102, and one experiment (HMBC) **fails to read at all** at the reader's current plausibility bounds. All three are now characterized with concrete numbers below, and a candidate fix for the HMBC defect was verified. A fourth, more important discovery, not on anyone's radar in CONTEXT.md: the byte-frozen `lucy-nmr-chemist.md` agent's peak-picking step is hardcoded to `lucy pick 1d/hsqc/hmbc <path>` (Bruker-only, via `BrukerReader`) and has **zero written awareness** of the `analysis/nmr_peaks/*.json` files this phase (and, unexercised, the whole v10.0 NUS path) pre-populates. This exact hand-off was never actually exercised even once in v10.0 (Phase 100's VAL-02 was never reached). JVAL-02 is the **first real test** of "does an LLM nmr-chemist notice pre-picked peaks and use them instead of trying to re-pick from a `.dx` file its own hardcoded command can't read" — this is a genuine, unmitigated risk for the D-14 handoff, independent of anything this phase's own code does.

**Primary recommendation:** Fix the one verified HMBC-blocking reader defect first (widen the `13C` upper plausibility bound in `readers/jcamp.py`), then add the `--threshold`/`--snr-floor` `key=value` CLI wiring, then run the knob-matrix search via **direct Python calls** to `bridge_peak_pick`/`bridge_peak_pick_1d` (cheap, ~1–3 s per probe) rather than repeated full `lucy jcamp` CLI invocations (~22 s each, re-reads and re-QCs every file every time), and only invoke the final `lucy jcamp` CLI once per experiment-set with the winning per-experiment knobs to produce the governed, QC-graded, committed evidence. Before starting the JVAL-02 handoff, explicitly brief the human about the nmr-chemist integration risk (Open Question #1) so a stall there is recognized immediately rather than mistaken for a CASE-solver defect.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JCAMP file reading (`.dx` → `Spectrum1D`/`Spectrum2D`) | Core library (`readers/jcamp.py`) | — | Already shipped (Phase 101); this phase only widens one plausibility bound (D-09) |
| Peak picking (2D bridge, 1D bridge) | Core library (`nus/bridge.py`, `processing/jcamp_1d_bridge.py`) | CLI (`cli/jcamp.py`) | Bridges already accept `threshold`/`snr_floor`; CLI just needs to forward per-experiment values (D-01/D-04) |
| QC grading | Core library (`nus/qc.py`, byte-frozen) | CLI write-boundary (`cli/jcamp.py`) | Gate logic frozen; only consumed here |
| Knob-matrix search (this phase's new work) | Ad-hoc script / direct Python calls | CLI (final governed run only) | Cheapest correct place to iterate; CLI is for the one artifact-producing invocation, not the search loop |
| §10 ground-truth cross-check | New: phase-local script/table in `VALIDATION.md` | — | Not owned by any existing module; a pure documentation/analysis step this phase authors |
| CASE structure elucidation | `.claude/commands/lucy-ng/case.md` + 5-agent team (byte-frozen) | — | Consumes `analysis/nmr_peaks/*.json`; **the exact consumption mechanism is the Open Question #1 risk** |
| Blind-run hygiene (memory, README move-aside, formula-leak check) | Human/executor process (shell, Claude Code session config) | — | Not code; operational discipline around the frozen orchestrator |

## User Constraints (from CONTEXT.md)

<user_constraints>

### Locked Decisions

- **D-01 — Expose `threshold`; no new picking logic.** `bridge_peak_pick` (2D) and `bridge_peak_pick_1d` already accept `threshold` **and** `snr_floor`; `cli/jcamp.py` only wires `--snr-floor` (default 5.0). Phase 103 adds the missing Click option so the tuning surface is two real knobs. **Rejected:** a post-pick ridge/artefact filter — ridge-freedom is what §8 is supposed to *measure*, so filtering it away would invalidate the check. **Also rejected:** turning `--snr-floor` alone and honest-stopping — the knob already exists in the bridges, withholding it from the CLI is an accident of Phase-102 scope, not a deliberate constraint.
- **D-02 — Per-experiment knob values, not one global set.** HSQC is clean, HMBC is ridge-prone, COSY carries the OH ridge at 5.32 ppm; a single value would either smear HMBC or thin out HSQC. The chosen `(threshold, snr_floor)` pair **per experiment** is recorded in `VALIDATION.md` so the run is reproducible by hand.
- **D-03 — Pre-defined finite knob matrix, then honest stop** (the Phase-100 D-04 pattern). The planner fixes a concrete, finite combination matrix up front (e.g. 3 `snr_floor` × 3 `threshold` values per experiment ⇒ ≤ 9 runs per experiment); **every** combination's outcome is logged, not just the winner. Once the matrix is exhausted, tuning stops. **Rejected:** a wall-clock budget (harder to document) and a baseline-run-then-decide gate (inserts an extra user interrupt mid-phase).
- **D-04 — Per-experiment knobs are wired as repeatable `key=value` options on the single `lucy jcamp` invocation.** e.g. `--threshold hsqc=1e4 --threshold hmbc=3e4 --snr-floor cosy=7`, with the bare/unkeyed value (or the existing default) applying to every experiment not named. **This is load-bearing:** the QC gate must run **exactly once** over the fully-staged set because the 1D lists are the trusted reference for grading the 2D ones (Phase-102 staged/final two-call pattern). Splitting into per-file invocations would give each run a referenceless, useless QC pass and trigger the D-07 write boundary per run. Backwards compatibility of the plain `--snr-floor 5.0` form must be preserved.
- **D-05 — JVAL-01 = QC verdict **plus** an explicit §10 cross-check table.** The QC verdict stays the formal gate, but `VALIDATION.md` additionally carries: (a) picked 1D-¹³C shifts vs. the §10 ground-truth shifts, with per-signal deviation, and (b) counted HSQC correlations vs. §8's ~17 protonated carbons. **Why:** with no DEPT file present, `QcConfig.default()`'s `known_quaternary_shifts` is applied unconditionally, so `classification_source` reads `"override"` — the quaternary check partly grades itself against pre-baked knowledge of this compound; the §10 table is the independent evidence the gate cannot supply on this dataset.
- **D-06 — Critical/soft tiers stay exactly as Phase 99/100 defined them.** Critical (⇒ FAIL, never waved through): quaternary-carbon 1-bond correlation, ppm calibration, signal-to-ridge dominance. Soft (⇒ PARTIAL possible): edited-sign self-consistency, COSY diagonal symmetry. **Explicitly rejected:** downgrading the quaternary check to informational because of the override.
- **D-07 — Soft-PARTIAL chemist confirmation is an inline gate during the phase.** The executor stops, presents the violated soft checks + the §10 cross-check table + a short summary of the COSY/HMBC connectivity, the user (the chemist) confirms or rejects, and the decision **with its reasoning** is recorded verbatim in `VALIDATION.md`. **Rejected:** rendering spectra with overlaid picks, and deferring the judgement until after the CASE run.
- **D-08 — A 1D-¹³C list that disagrees with §10 is corrected only through the D-03 knob matrix, never by hand.** Hand-editing a peak list against §10, or substituting the §10 list as the reference, is forbidden.
- **D-09 — Reader/bridge/CLI fixes allowed; gate semantics frozen.** Genuine defects in `readers/jcamp.py`, `processing/jcamp_1d_bridge.py` or `cli/jcamp.py` that block JVAL-01/02 are fixed inside Phase 103. **Byte-frozen:** `nus/qc.py`, `PeakPicker2D`, the 1D picker, `case.md`, the five `lucy-*.md` agent files — `tests/test_skill_files_unchanged.py` must stay green. Every such fix is logged as an explicit deviation.
- **D-10 — On exhausted budget: honest partial close, per Phase 100.** What was achieved is recorded as achieved; what was not is recorded as **NOT** achieved — `VALIDATION.md` + a limitation note in ROADMAP/REQUIREMENTS + a **named tracked next step**. v10.1 then closes PARTIAL if needed. No indefinite milestone block.
- **D-11 — Committed evidence (all four):** `VALIDATION.md`; the real generated `analysis/nmr_peaks/*.json`; the full `qc_report.json`; the JCAMP peaks additionally committed as a **known-good positive regression fixture**. **Hard constraint:** the existing known-bad QC-02 regression fixtures under `.../C20H32O2/analysis/nmr_peaks/` must **never** be overwritten.
- **D-12 — The run happens in the jcamp directory, cleanly separated.** `lucy jcamp` writes to `C20H32O2-jcamp/analysis/nmr_peaks/`, CASE runs there. The sibling Bruker tree `../C20H32O2/` is **not entered**.
- **D-13 — Four blind safeguards are mandatory:** (1) `autoMemoryEnabled: false` for the jcamp data directory + quarantine of any pre-existing memory files there; (2) `C20H32O2-jcamp/README.md` moved aside for the run, restored afterwards; (3) a `lucy sanitise`-style/grep check of the JCAMP headers for a compound-name leak; (4) the `case.md` model-disclosure gate runs and the model actually used is recorded in `VALIDATION.md`.
- **D-14 — A fresh interactive session, started by the user.** The executor prepares everything and stops; the user starts `/lucy-ng:case` in a fresh session in the jcamp directory and reports back. **Rejected:** headless from inside the phase, and a Sheldon run.
- **D-15 — JVAL-02 bar = Phase-100 D-03 unchanged, plus a hard cap.** Success = LSD terminates normally (no timeout, no ~10⁶ explosion) **and** `lucy lsd rank` produces a ranked list. A pre-defined wall-clock/iteration cap makes "terminates" measurable. **The correct structure appearing top-N is a bonus, not a condition.**
- **D-16 — One plan, ending in a handoff gate, `autonomous: false`.** Runs the additive CLI change → ingestion → knob matrix → QC → §10 table → chemist gate, writes `VALIDATION.md` through JVAL-01, and ends with an explicit handoff. Mirrors `100-03-PLAN.md`'s honest `autonomous: false` shape.

### Claude's Discretion

- The concrete numeric knob-matrix bounds (how many values per knob, which starting values per experiment) — see this document's concrete, real-data-grounded recommendation below.
- The concrete wall-clock/iteration cap for the CASE run.
- Exact `key=value` option syntax and parsing for the per-experiment knobs, and how the bare-value default is preserved — see Code Examples below for a concrete, verified Click pattern.
- Layout of `VALIDATION.md` and where the committed peak JSONs / positive fixture live relative to the known-bad QC-02 fixtures — see Don't-Hand-Roll / fixture-location recommendation below.
- The mechanism of the JCAMP-header leak check (D-13.3) — reuse of the existing sanitise path vs. a one-off grep — this session already ran the grep check (see Common Pitfalls, "formula leak") and its result can be reused directly.

### Deferred Ideas (OUT OF SCOPE)

- Post-pick ridge/artefact filter for the JCAMP path (rejected in D-01).
- A CLI escape hatch for `QcConfig`'s quaternary override (needs a `qc.py` edit, byte-protected).
- Webview rendering of a JCAMP ingest (rejected as the chemist-gate mechanism in D-07).
- NOESY consumption by the CASE constraint model (JC-F1).
- RECON-F1 (hmsIST/mddnmr in-lucy-ng NUS fallback).
- Milestone-close bookkeeping (`/gsd-complete-milestone`, infographic-deck refresh).
- CASE4 azulene-regiochemistry gap and ranking-tests-hardfail todo — reviewed, not folded (unrelated).

</user_constraints>

## Phase Requirements

<phase_requirements>

| ID | Description | Research Support |
|----|-------------|------------------|
| JVAL-01 | `C20H32O2-jcamp` read, peak-picked, and QC-graded to §8 quality (QC PASS or soft-only PARTIAL + chemist confirmation) | This session ran the real chain end-to-end (read-only) and obtained hard numbers for default-setting peak counts (Common Pitfalls #2), a verified fix for the one reader defect blocking HMBC entirely (Common Pitfalls #1), and a real-data-grounded knob-matrix starting range (Architecture Patterns / knob matrix). The full §10 ground-truth table is transcribed below for the D-05 cross-check. |
| JVAL-02 | Fresh `/lucy-ng:case C20H32O2` on the JCAMP-derived peak lists converges on a finite, rankable solution set | LSD/outlsd verified available on this machine (`lucy lsd check` → both available). The CASE-handoff mechanics are documented (D-13/D-14), and a previously-undocumented integration risk between the byte-frozen nmr-chemist agent and pre-picked `analysis/nmr_peaks/*.json` is flagged as Open Question #1 — this is the single highest-uncertainty item for JVAL-02 and is independent of anything this phase's own code changes. |

</phase_requirements>

## Standard Stack

No new external packages are required this phase. All work is: (a) a Click CLI option addition using the stdlib `click` already vendored as a core dependency, (b) a small, targeted constant change in `readers/jcamp.py`, (c) ad-hoc Python scripting for the knob-matrix search (using already-imported project modules), and (d) documentation (`VALIDATION.md`).

**Version verification:** `click==8.1.8` confirmed installed in this environment (`python -c "import click; print(click.__version__)"`). No `pip install` needed.

## Package Legitimacy Audit

**N/A — no new external packages are introduced by this phase.** Nothing to run through slopcheck/registry verification.

## Architecture Patterns

### System Architecture Diagram

```
 C20H32O2-jcamp/*.dx (6 files, real, external, ~55MB)
        |
        v
 [readers/jcamp.py] JcampReader.read()  --dispatch on NUM DIM--> Spectrum1D | Spectrum2D
        |                                                             |
        | (1D: 1H, 13C)                                                | (2D: HSQC, HMBC, COSY; NOESY read-but-skipped D-06)
        v                                                             v
 [processing/jcamp_1d_bridge.py]                        [nus/bridge.py::bridge_peak_pick]
   bridge_peak_pick_1d(threshold, snr_floor)               (threshold, snr_floor, per-experiment)
        |                                                             |
        +----------------------- staged (qc_report=None) -------------+
                                     |
                                     v
                    [nus/qc.py::run_qc_checks]  <-- BYTE-FROZEN
                    (6 checks: quaternary_exclusion, ppm_calibration,
                     signal_to_ridge, hsqc_coverage [critical];
                     edited_sign_consistency, cosy_diagonal_symmetry [soft])
                                     |
                    PASS/PARTIAL -----------------------> FAIL
                         |                                   |
                         v                                   v
      [cli/jcamp.py] write consumable                [cli/jcamp.py] quarantine
      analysis/nmr_peaks/*.json                       jcamp_ingest/qc_failed/*
      (+ qc_verdict embedded per payload)              + qc_report.json, exit 1
                         |
                         v
      §10 ground-truth cross-check table (NEW, this phase, in VALIDATION.md)
      + D-07 chemist gate on soft-PARTIAL
                         |
                         v
      D-14 HANDOFF: fresh /lucy-ng:case C20H32O2 in jcamp dir (interactive, human-started)
                         |
                         v
      case.md (BYTE-FROZEN) spawns lucy-nmr-chemist (BYTE-FROZEN)
        -- OPEN QUESTION #1: nmr-chemist's hardcoded "lucy pick 1d/hsqc/hmbc <path>"
           step targets BrukerReader-only input; it has NO written path for consuming
           pre-existing analysis/nmr_peaks/*.json. Untested even in v10.0.
                         |
                         v
      lsd-engineer -> LSDRunner -> solution-analyst -> analysis/final_results.md
      (JVAL-02 bar: LSD terminates, finite rankable set — D-15)
```

### Recommended Project Structure

No new modules. Touched files:
```
src/lucy_ng/
├── cli/jcamp.py              # D-01/D-04: add --threshold/--snr-floor key=value options
├── readers/jcamp.py          # D-09: widen the 13C plausibility upper bound (verified fix, see Pitfall #1)
tests/
├── fixtures/jcamp/
│   └── known_good_peaks/     # NEW (D-11.4), mirrors tests/fixtures/nus/known_bad_peaks/'s
│                              # sibling tests/fixtures/nus/clean_peaks_synthetic/ naming convention
.planning/phases/103-.../
├── VALIDATION.md              # NEW, primary evidence artifact (D-11.1)
```

### Pattern 1: Staged/Final Two-Call QC Wiring (already shipped, unchanged this phase)
**What:** Stage every file (1D and 2D) with `qc_report=None`, run `run_qc_checks()` exactly once over the fully-staged directory, then rebuild payloads with the real verdict before writing consumables.
**When to use:** Already implemented in `cli/jcamp.py`; this phase's `--threshold`/`--snr-floor` per-experiment values must flow into BOTH the staging call and the final rebuild call (see `cli/jcamp.py` lines ~265-347) — the CR-01 lesson from Phase 102 (a write boundary needs run-to-run state hygiene, not just correct per-run branching) also still applies here unmodified; do not regress it while adding the new options.
**Example:**
```python
# Source: src/lucy_ng/cli/jcamp.py (existing, Phase 102)
staged_payload = bridge_peak_pick(
    spectrum, experiment=experiment_type, qc_report=None,
    recon_meta={"backend": RECON_BACKEND, "iterations": None},
    threshold=per_experiment_threshold.get(experiment_type),   # NEW this phase
    snr_floor=per_experiment_snr_floor.get(experiment_type, 5.0),  # NEW this phase
)
```

### Pattern 2: Cheap knob-matrix search via direct bridge calls, CLI only for the final governed run

**What:** For the D-03 knob-matrix search, call `PeakPicker2D.pick_peaks(spectrum, snr_floor=..., threshold=..., detect_negative=...)` (or `bridge_peak_pick`) directly in a throwaway script against an already-loaded `Spectrum2D`, rather than invoking the full `lucy jcamp` CLI once per matrix cell.

**When to use:** Measured this session: a single full `lucy jcamp <jcamp-dir> --out <scratch>` invocation over all 6 real files took **~22 s wall-clock** (re-reads every `.dx` file, re-picks every experiment, runs the QC gate once). A single `JcampReader.read_2d()` call on the real 2048×2048 HSQC/COSY file takes **~3.1–3.2 s**; HMBC (1024×2048) **~1.6 s**; re-running `PeakPicker2D.pick_peaks()` at a new `snr_floor` on an already-loaded spectrum takes **~0.9–1.2 s** regardless of the value. So: read each 2D spectrum **once** per experiment (~3 s × 3 experiments ≈ 9 s total), then sweep `snr_floor`/`threshold` values against the in-memory array (~1 s each) — a 5-value-per-knob matrix across 3 experiments this way costs roughly `9 s + 15 × 1 s ≈ 24 s` total, versus `15 × 22 s ≈ 330 s` if driven through the CLI. Only the single final, chosen combination should go through the real `lucy jcamp` CLI invocation (to produce the actual committed, QC-graded, `--format json` evidence artifact).
**Example:**
```python
# Source: verified interactively this session (PYTHONPATH="$(pwd)/src" python3 ...)
from lucy_ng.readers.jcamp import JcampReader
from lucy_ng.processing.peak_picker_2d import PeakPicker2D

spec = JcampReader.read_2d(".../C20H32O2-jcamp/C20H32O2_HSQC.dx")  # read ONCE
for snr in (5, 50, 500, 2000, 5000):                                # sweep cheaply
    pl = PeakPicker2D.pick_peaks(spec, snr_floor=snr, detect_negative=True)
    print(snr, len(pl.peaks))   # log EVERY cell's outcome (D-03), not just the winner
```

### Pattern 3: Repeatable `key=value` Click options with a bare-value fallback (D-04)

**What:** `click.option("--threshold", multiple=True, ...)` collects a tuple of raw strings; a small parser splits `key=value` pairs from bare values and builds a `dict[str, float]` with an optional `None`-keyed (or sentinel-keyed) default applied to every experiment not explicitly named. `multiple=True` is already used elsewhere in this codebase (`cli/visualize.py:48`), confirming the pattern is idiomatic here, though nowhere yet combines it with `key=value` parsing — this is genuinely new syntax for this CLI, not a copy of an existing helper.
**When to use:** Exactly D-04's requirement — `--threshold hsqc=1e4 --threshold hmbc=3e4 --snr-floor cosy=7`, with a bare `--snr-floor 5.0` (no `=`) still meaning "apply to everything", preserving the existing test `test_help_exits_zero_and_documents_options` and every other `--snr-floor 5.0`-style call in `tests/test_cli_jcamp.py`.
**Example (verified idiom, not lifted from this codebase — Click's own documented `multiple=True` + manual parse pattern):**
```python
@click.option("--threshold", "thresholds", multiple=True, default=(),
              help="threshold value, or KEY=value to scope to one experiment "
                   "(e.g. --threshold hmbc=0.02); repeatable.")
@click.option("--snr-floor", "snr_floors", multiple=True, default=("5.0",),
              help="snr_floor value, or KEY=value; repeatable. Bare form preserves "
                   "the Phase-102 default of 5.0 for every experiment.")
def jcamp(thresholds: tuple[str, ...], snr_floors: tuple[str, ...], ...):
    def _parse_keyed(raw: tuple[str, ...], cast) -> tuple[dict[str, float], float | None]:
        by_key: dict[str, float] = {}
        bare: float | None = None
        for item in raw:
            if "=" in item:
                key, _, value = item.partition("=")
                by_key[key.strip().upper()] = cast(value)
            else:
                bare = cast(item)   # last bare value wins; keyed values always win over it
        return by_key, bare
    threshold_by_exp, threshold_bare = _parse_keyed(thresholds, float)
    snr_by_exp, snr_bare = _parse_keyed(snr_floors, float)
    snr_bare = snr_bare if snr_bare is not None else 5.0   # preserve the existing default
    # per experiment_type in the staging loop:
    #   threshold=threshold_by_exp.get(experiment_type, threshold_bare)
    #   snr_floor=snr_by_exp.get(experiment_type, snr_bare)
```
Note: `SUPPORTED_2D = ("HSQC", "HMBC", "COSY")` and `SUPPORTED_1D = ("1H", "13C")` in `cli/jcamp.py` are already upper-case-normalized experiment/nucleus names — match the parser's `.upper()` key normalization against these exact strings (`"HSQC"`, `"13C"`, not `"hsqc"`/`"13c"`) so `--threshold hsqc=...` and `--threshold 13c=...` both resolve, and add a fail-loud check for an unrecognized key (typo guard — e.g. `--threshold hqsc=...` should error, not silently apply nothing).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Re-grading a peaks directory after tuning | A custom "does this pass §8" checker | `lucy nus qc <peaks-dir>` (identical schema across NUS/JCAMP paths, Phase-102 D-01) or `run_qc_checks()` in-process | Already exists, byte-frozen, identical to what the CLI itself uses — inventing a parallel checker risks disagreeing with the actual gate |
| Peak-count / SNR sweep across knob values | A shell loop invoking `lucy jcamp` per combination | Direct `PeakPicker2D.pick_peaks()`/`bridge_peak_pick()` calls against an already-loaded `Spectrum2D` (Pattern 2 above) | ~300x cheaper per this session's measurement; the CLI's read+QC overhead is unrelated to what the sweep is testing |
| "Is the QC gate result chemically plausible" | An automated ranking of PARTIAL results | The D-07 human chemist gate (already decided) | The QC gate's own quaternary check leans on 5 compiled-in shifts of *this* compound (classification_source="override") — it cannot independently validate itself; a human with §10 is the only independent check |
| Ridge/artefact suppression on the real matrix | A new post-pick ridge filter | Tune `snr_floor`/`threshold` only (D-01); `signal_to_ridge` is a QC *check*, not a picker feature | Explicitly rejected in D-01 — filtering ridges away would invalidate the exact thing §8/QC measures |

**Key insight:** every piece of machinery this phase needs (picker, bridge, QC gate, re-grading CLI) already exists and is verified working on real data (this session proved it runs, just with wrong default knobs and one reader bug). The only genuinely new code is the CLI option-parsing glue and the one-line reader bound fix.

## Common Pitfalls

### Pitfall 1 (VERIFIED, HIGH confidence): HMBC currently fails to read at all — a genuine, fixable reader defect

**What goes wrong:** `JcampReader.read_2d()` on the real `C20H32O2_HMBC.dx` raises `ValueError: Implausible 13C ppm axis: [-4.57, 234.81] outside expected [-15.0, 230.0] -- likely wrong Hz/frequency divisor`. This is not a fixture artifact — it reproduces on the real, full-size file.

**Why it happens:** HMBC's real `##$OFFSET=` for the 13C dimension is `234.8062` ppm (vs. HSQC's `174.9902` ppm) with a wider sweep width (`FIRST=29516.31 Hz, LAST=-574.76 Hz` → SW ≈ 30091 Hz ≈ 239.4 ppm at `SF=125.705 MHz`, vs. HSQC's ≈180 ppm window). This is a **real, legitimate, wider HMBC acquisition window** (HMBC pulse programs commonly use a broader 13C sweep than HSQC to safely bracket carbonyls/heteroatom carbons even when none are present in this particular compound) — it is not a units bug. The reader's own `_ppm_scale()` formula reproduces the correct axis (verified by hand-computation and by monkeypatch below); the module-level constant `_PPM_PLAUSIBILITY_BOUNDS["13C"] = (-15.0, 230.0)` is simply too tight for this real experiment's parameter choice.

Also note (secondary, non-blocking fact worth documenting): the real HMBC file's 2D grid is **1024×2048** (`##VAR_DIM= 1024, 2048, 2048`), not 2048×2048 like HSQC/COSY — the "2D grids up to 2048×2048" phrasing in prior docs is correctly hedged ("up to"), but the planner/executor should not assume all four 2D files share identical dimensions.

**How to avoid:** Widen `_PPM_PLAUSIBILITY_BOUNDS["13C"]` in `src/lucy_ng/readers/jcamp.py` — verified this session via monkeypatch that setting the upper bound to `250.0` (instead of `230.0`) lets `read_2d()` succeed and produces a physically sensible axis: F1 (13C) range `[-4.57, 234.81]` ppm, F2 (1H) range `[-0.45, 7.05]` ppm. This is consistent with the function's own docstring, which explicitly frames this bound as "a deliberately coarse safety net... NOT the load-bearing check" (the finer JC-02 cross-check against 1D reference peaks is a separate, already-existing mechanism). Recommend `240.0`–`250.0` as the new bound (leaves margin without being so loose it stops catching a genuine SFO-vs-SF divisor bug, which would produce errors far larger than ~5 ppm). This is a D-09 in-scope fix (reader defect blocking JVAL-01) — log it as an explicit deviation per D-09's own requirement.

**Warning signs:** `ValueError: Implausible ... ppm axis` at read time, specifically for HMBC (not HSQC/COSY, which use narrower windows in this dataset).

### Pitfall 2 (VERIFIED, HIGH confidence): default knob values (`snr_floor=5.0`) massively over-pick on the real full-size matrix

**What goes wrong:** Running `lucy jcamp` on the real dataset with all-default knobs (after locally patching around Pitfall 1 to also get an HMBC count) gives:

| Experiment | Default count | §8/§10-plausible expectation | Ratio |
|---|---|---|---|
| HSQC (2048×2048) | 10,687 cross-peaks | ~17–27 (≈17 protonated C, some CH2 giving 2 correlations) | ~450x too many |
| COSY (2048×2048) | 16,244 cross-peaks | "a real aliphatic network" — dozens to low hundreds, doubled by diagonal symmetry | order(s) of magnitude too many |
| HMBC (1024×2048) | 19,015 cross-peaks (after Pitfall-1 fix, `snr_floor=5`) | 2–3 bond correlations, ridge-free | orders of magnitude too many |
| 1D 13C | 45 peaks | ~20 real carbons (§10 lists 20) | ~2.25x too many |
| 1D 1H | 265 peaks | Lower (exact count depends on multiplet splitting — less obviously wrong, but still likely inflated) | uncertain, probably inflated |

Full QC verdict at defaults: **FAIL**, critically on `quaternary_exclusion` (326 HSQC correlations land at the 5 known-quaternary shifts — a direct symptom of over-picking, not a real quaternary-leak), and also failing `edited_sign_consistency` (soft) with essentially every 0.5 ppm bucket across the whole aliphatic region showing mixed hints — another symptom of the same over-picking flooding every bucket.

**Why it happens:** `_compute_2d_noise_sigma()`'s global-MAD estimate, calibrated in Phase 99 against a synthetic/small-scale reference (documented ratio ≈3,477:1 max-to-sigma on a CASE1 mock), measures a **max/sigma ratio of ~53,615:1** on this real, CS/IRLS-reconstructed HSQC matrix — roughly 15x higher dynamic range than what the default `snr_floor=5.0` was ever tuned against. Real compressed-sensing (mddnmr/IRLS) reconstructions leave a very large number of small-amplitude ripples across the matrix (not flat Gaussian noise), which the MAD statistic under-estimates as "noise level," so a `k=5` floor clears far too much of that ripple as "signal." This is exactly the risk flagged in Phase 102's own carried-forward hazard note ("`_compute_2d_noise_sigma`'s global MAD was only ever exercised on 16-row trimmed fixtures").

Empirically measured HSQC peak count vs. `snr_floor` (`detect_negative=True`, all else default), this session, on the real file:

| `snr_floor` | HSQC peak count |
|---|---|
| 5 (current CLI default) | 10,687 |
| 10 | 3,448 |
| 20 | 828 |
| 50 | 340 |
| 100 | 219 |
| 200 | 121 |
| 300 | 98 |
| 500 | 61 |
| 800 | 57 |
| 1000–2000 | ~50–52 (plateau) |
| 3000 | 39 |
| 5000 | 11 |
| 8000 | 6 |

And the legacy fraction-of-max `threshold` mode (`use_snr=False`), same spectrum:

| `threshold` (fraction of max \|intensity\|) | HSQC peak count |
|---|---|
| 0.001 | 332 |
| 0.005 | 105 |
| 0.01 | 62 |
| 0.02 | 51 |
| 0.05 | 46 |

COSY (`detect_negative=False`) is even more resistant to thinning via `snr_floor` alone — even at `snr_floor=800` it still returns 364 peaks, well above what "a real aliphatic network" should plausibly contain; COSY may need the fraction-of-max `threshold` mode, or a combination, more than HSQC does. HMBC similarly needs `snr_floor` in the low thousands (470 at 50; 138 at 500; 59 at 2000) before approaching a plausible count.

**How to avoid:** Do not trust the CLI's `snr_floor=5.0` default on real data — it was calibrated against fixtures ~15x lower dynamic range than this real matrix. Ground the D-03 knob matrix in the numbers above (see the concrete recommendation below) rather than picking arbitrary values; re-verify with the direct-call probing pattern (Architecture Pattern 2) before spending a full CLI invocation on each candidate.

**Warning signs:** `n_cross_peaks` in the thousands to tens-of-thousands on any 2D experiment; `quaternary_exclusion` failing with a long, near-continuous list of hit shifts spanning the whole aliphatic region (a real quaternary leak looks like 1-5 discrete hits at the known shifts, not hundreds); `edited_sign_consistency` failing at essentially every 0.5-ppm bucket across the full axis.

### Pitfall 3 (VERIFIED, HIGH confidence): the byte-frozen `lucy-nmr-chemist.md` agent has no written path for pre-picked peaks — the JVAL-02 handoff's real risk

**What goes wrong:** `case.md`'s peak-picking `TaskCreate` description says only "Pick 13C, HSQC, HMBC peaks for {compound_path}..." — it does not enumerate specific file paths, delegating discovery entirely to the nmr-chemist agent. `lucy-nmr-chemist.md`'s own workflow step 4 is hardcoded: `` `lucy pick 1d <13c>`, `lucy pick 1d <dept135>`, `lucy pick hsqc <hsqc>`, `lucy pick hmbc <hmbc>` ``. `cli/pick.py`'s `pick_1d`/`pick_hsqc`/`pick_hmbc` commands are hardcoded to `BrukerReader.read_1d`/`read_2d` (verified by reading the source — `from lucy_ng.readers import BrukerReader`, called at lines 91/182/229/306) and **cannot read `.dx` JCAMP files at all**. A grep of the entire `lucy-nmr-chemist.md` file for `nmr_peaks`, `jcamp`, `nus`, "already exist", "pre-picked", or "existing peak" returns **zero matches** — there is no written instruction anywhere telling the agent to look for or trust pre-existing `analysis/nmr_peaks/*.json`.

**Why it happens:** This exact hand-off (peaks pre-computed by a bridge outside `lucy pick`, then consumed by the unmodified CASE orchestrator) was designed into v10.0's `nus/` package (Phase 99) and carried into v10.1's `lucy jcamp`, but **was never actually exercised end-to-end even once** — Phase 100's VAL-02 (the only prior attempt) never reached the CASE-handoff step because SMILE aborted before producing any peaks (documented in `ROADMAP.md`'s Phase-100 limitation note). So the "does the nmr-chemist agent gracefully consume pre-existing peaks instead of trying to re-invoke `lucy pick` on files it can't read" question has literally never been tested. `case.md` and `lucy-nmr-chemist.md` are LLM-driven instructions, not rigid scripts — the agent *may* notice `analysis/nmr_peaks/*.json` already populated (e.g. via an `ls`/`Glob` of `{compound_path}` before deciding how to proceed) and use it directly, especially once its hardcoded `lucy pick hsqc <hsqc.dx>` attempt visibly fails against a JCAMP file. But this is unverified LLM judgment, not a guaranteed code path.

**How to avoid:** This cannot be "fixed" within this phase's scope — `case.md` and `lucy-nmr-chemist.md` are byte-frozen (D-09). The mitigation is honesty and preparation, not a code change:
1. Flag this explicitly to the human before the D-14 handoff (recommend adding this as an explicit line in the handoff instructions the plan writes, so a stall here is immediately recognized as "the known nmr-chemist/pre-picked-peaks integration gap," not misdiagnosed as a JCAMP-reader or QC-gate defect).
2. If the fresh CASE run does stall at the peak-picking step because `lucy pick hsqc <path.dx>` fails, the expected/hoped-for LLM recovery is for the nmr-chemist to notice the failure, `ls analysis/nmr_peaks/`, find the already-QC-graded JSON files, and proceed using them (their schema is unchanged from what `lucy pick` itself would have produced) — but this is not guaranteed and should be recorded as an observed outcome either way in `VALIDATION.md`'s CASE Convergence section (mirroring `100-03-PLAN.md`'s "observe, do not instrument" discipline).
3. Do **not** attempt to fix this by editing `case.md`/`lucy-nmr-chemist.md` — that is explicitly out of scope (byte-frozen) and would violate JCLI-02's "case.md byte-unchanged" invariant this whole milestone depends on.

**Warning signs:** The fresh CASE run's `[SETUP-COMPLETE]` message either never arrives, arrives reporting a `lucy pick` failure it worked around, or arrives suspiciously fast without any visible `lucy pick` invocation at all (meaning the agent silently used the existing JSON, which would actually be the *good* outcome).

### Pitfall 4 (VERIFIED): the memory-quarantine mechanism named in CONTEXT.md D-13.1 has a known failure mode — use the project's actual established fix instead

**What goes wrong:** CONTEXT.md's D-13.1 describes "`autoMemoryEnabled: false` for the jcamp data directory." This is exactly the mechanism this project's own memory (`project_blind_uat_memory_contamination.md`) documents as **fragile and already known to fail**: "every CASE run WIPES the data-dir `.claude/settings.json`" — so a per-directory `autoMemoryEnabled: false` written before the run is destroyed by the very run it is meant to protect, and would not protect a *second* fresh run in the same directory.

**Why it happens:** Confirmed empirically in a prior milestone (2026-06-20): CASE2/3/4/5 lost their per-dir `settings.json` after running; un-run CASE6/7/8 kept theirs. The robust, already-adopted project fix (2026-06-20, still in `~/.zshrc`) is instead the **`case-blind` shell alias**: `alias case-blind='CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 claude --dangerously-skip-permissions'` — an env var beats any settings.json and cannot be wiped by the run itself.

**How to avoid:** For the D-14 fresh session, recommend the human launch it with `case-blind` (or manually export `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` before `claude`) rather than relying on a `.claude/settings.json` edit in the jcamp directory. Separately: **verified this session** that `~/.claude/projects/-Users-steinbeck-Dropbox-develop-data-nmrdata-active-lucy-ng-testprojects-C20H32O2-jcamp/` **does not exist yet** — there is no pre-existing memory directory for this exact path to quarantine (a Claude Code session has never been opened with this directory as cwd). No quarantine step is actually needed for D-13.1 as long as `case-blind`/the env var is used for the fresh run; this should be verified again immediately before the handoff in case anything changed between research and execution.

**Warning signs:** A fresh session in the jcamp directory immediately reciting facts about the compound (formula, shift assignments, prior CASE outcomes) before any tool call — the exact symptom that triggered the original 2026-06-17 discovery of this issue.

### Pitfall 5 (VERIFIED, benign): the "compound-name leak" (D-13.3) that actually exists is the molecular formula, not a trivial name — and CASE is given the formula anyway

**What goes wrong (or doesn't):** A grep across all six real `.dx` files for anything resembling a leaked identity (`##SAMPLE DESCRIPTION`, `structure`, `diterpen`, trivial-name strings) found **no trivial/systematic compound name anywhere**. The only identity-adjacent string present is the **molecular formula** `C20H32O2` itself, appearing in two places per file: `##$NAME= <C20H32O2>` and the `mddnmr` audit-trail path `.../nmr-data/cs/nmr/C20H32O2/3/pdata/1/auditp.txt`.

**Why this is not the same class of leak as CASE2/3/4/5/8:** Those datasets leaked a trivial/systematic *name* (letting an agent recall structural facts about a known compound from parametric memory without doing any spectral analysis — the exact "parametric naming hallucination" failure mode this project has repeatedly guarded against). Here, the leaked string is the **formula**, which `/lucy-ng:case C20H32O2` is *already explicitly given* as its second argument (D-14) — so this "leak" discloses nothing the CASE run doesn't already legitimately have as input.

**How to avoid:** Document this finding directly in `VALIDATION.md`'s D-13.3 check rather than treating it as a fail — a one-off grep (`grep -a "C20H32O2" *.dx` or similar) is sufficient to reproduce this check; no `lucy sanitise`-path work is needed to conclude "no disqualifying leak, only the already-given formula." This resolves the "reuse the sanitise path vs. a one-off grep" discretion point in CONTEXT.md in favor of the simpler one-off grep, since it already fully answers the question.

**Warning signs:** N/A — this is a documented non-issue, not a risk to watch for at execution time, but the D-13.3 check should still be explicitly re-run (not assumed from this research) and its (expected: benign) result recorded verbatim in `VALIDATION.md`.

### Pitfall 6 (inherited from Phase 102, still applies): worktree `PYTHONPATH` hazard and stale-base hazard

**What goes wrong:** Bare `python`/`pytest` inside a git worktree resolves to the **main repo checkout's** editable install, not the worktree's own source — silently verifying the wrong tree. Separately, worktree-isolated executors have repeatedly started on a stale, unrelated base commit.
**How to avoid:** Prepend `PYTHONPATH="$(pwd)/src"` to every runtime verification command inside a worktree (this session used it directly from the main checkout, so it was not itself needed here, but the executing plan will very likely run inside a worktree and must carry this forward); assert the worktree base commit via `git reset --hard` before any file is read/written, per Phase 102's established convention.

### Pitfall 7 (design note, not yet a defect): the QC gate's quaternary override is a real epistemic gap on this exact dataset

**What goes wrong:** With no DEPT `.dx` file in this dataset, `QcConfig.default()`'s five compiled-in §8 quaternary shifts (142.00, 135.86, 79.35, 36.23, 37.86) are applied unconditionally (`classification_source == "override"`), meaning the `quaternary_exclusion` check partially validates itself against pre-baked knowledge of this exact compound rather than independent DEPT evidence.
**Why it happens/how to avoid:** This is inherited, byte-frozen behavior from Phase 99/102 (`qc.py` cannot be edited). D-05 already accounts for this by requiring the independent §10 cross-check table as a supplement — this pitfall entry exists only to make sure the plan does not accidentally treat a clean `quaternary_exclusion` PASS as fully independent proof; it is proof only when read alongside the §10 table.

## Code Examples

### §10 Ground-Truth Table (verbatim transcription for the D-05 cross-check, `NUS-RECONSTRUCTION-GUIDE.md` §10)

C20H32O2, DBE 5, a tetracyclic diterpene:

- Tetrasubstituted endocyclic C=C: **142.00** / **135.86** ppm (both quaternary, no sp2-CH; the OH proton at 5.32 ppm is NOT an olefinic CH).
- **gem-Dimethyl quaternary at 36.23** ppm — hard-confirmed from two methyl singlets at 0.990/0.964 ppm (12.9 Hz apart = not J-coupling; an isopropyl would give doublets, ruled out). All 4 methyls are singlets → no secondary methyl, no isopropyl.
- Tertiary alcohol: Cq-O at **79.35** ppm (+ OH at 5.32 ppm).
- Oxygenated CH at **69.06** ppm and CH2 at **67.06** ppm.
- 4×CH3: 25.96 (allylic, near 135.86), 23.43 (angular), 21.78 + 22.63 (gem-dimethyl on 36.23).
- No aromatic ring (only 2 sp2 C), no carbonyl (nothing 160–235 ppm).
- Probable sp3 quaternaries: 79.35 (Cq-O) + 36.23 (gem-diMe) + possibly one angular C ~**37.86** (MEDIUM confidence) — i.e. the 5 quaternary shifts the QC gate's override hard-codes.
- **Full 13C shift list (20 carbons):** 142.00, 135.86, 79.35, 69.06, 67.06, 51.63, 37.86, 37.19, 36.23, 35.23, 34.21, 33.67, 30.66, 29.77, 27.93, 27.15, 25.96, 23.43, 22.63, 21.78.
- Open (needs the 2D data): exact ring connectivity and O-topology (ether vs. diol).

### §8 Verification Criteria (verbatim transcription, `NUS-RECONSTRUCTION-GUIDE.md` §8)

- **HSQC:** clean 1-bond cross-peaks; each of the ~17 protonated 13C shows exactly one correlation (two for CH2, diastereotopic); the 5 quaternaries above show **no** 1-bond correlation; edited signs (CH/CH3 vs CH2) clean and consistent.
- **HMBC:** defined 2–3 bond cross-peaks with no continuous t1-ridges; the gem-dimethyl methyls (~0.96/0.99 ppm) show sharp correlations; no artefact streaks along F1.
- **COSY:** a real aliphatic H–H coupling network (not just the OH ridge at 5.32 ppm, which was the only "signal" in the prior home-IST attempt).
- Quick-check: signal-to-ridge ratio clearly better than the existing known-bad `*_exp*.json` lists.

### Real-data-grounded knob-matrix recommendation (concrete starting values for D-03)

Based on this session's measurements (Pitfall 2), a plausible finite matrix per 2D experiment — smaller than an arbitrary 3×3 grid, chosen to bracket the empirically observed transition zones rather than guess blindly:

| Experiment | `snr_floor` candidates | Rationale |
|---|---|---|
| HSQC | 500, 1000, 2000, 3000, 5000 | Count plateaus ~50 from 800–2000, drops to 39 at 3000, 11 at 5000 — the ~17–27 target likely sits between 3000–5000; test this range specifically |
| COSY | 800, 1500, 3000, 5000, 8000 | Resists thinning much more than HSQC (364 peaks even at snr_floor=800) — needs testing further out; consider also trying `threshold` fraction-of-max mode (e.g. 0.02, 0.05) as an alternative if `snr_floor` alone cannot reach a plausible count without also cutting real cross-peaks |
| HMBC | 500, 1000, 2000, 3000, 5000 | 138 peaks at 500, 59 at 2000 — likely needs to go higher than HSQC given HMBC's inherently weaker (2-3 bond) correlations; do not assume the same values transfer directly from HSQC |
| 1D 13C | `snr_floor` 5 (default), 10, 20 | 45 peaks at default vs. ~20 real shifts — a smaller adjustment than the 2D experiments; likely resolvable within a narrow range |
| 1D 1H | `snr_floor` 5 (default), 10 | 265 peaks at default — evaluate against real multiplet structure before assuming this needs correction; 1H splitting can legitimately produce many peaks |

This gives ≤5 values × 3 2D experiments + ≤2 values × 2 1D experiments = ≤19 direct-call probes, each ~1-3s (Pattern 2) — well within a single research/tuning session, before the one final governed `lucy jcamp` CLI invocation with the chosen values. Log every cell (D-03), not just the winner — a simple CSV or table in `VALIDATION.md` (experiment, snr_floor/threshold, n_peaks, qc-relevant symptom e.g. "quaternary_exclusion hit count") is sufficient.

## State of the Art

| Old Approach (Phase 99/100 assumption) | Current Approach (this phase's finding) | When Changed | Impact |
|---|---|---|---|
| `snr_floor=5.0` default assumed roughly-transferable across NUS/JCAMP real data based on Phase-99's CASE1 mock calibration (~3,477:1 max/sigma ratio) | This real HSQC matrix measures ~53,615:1 max/sigma — ~15x higher; `snr_floor` needs to scale roughly with that ratio, not stay fixed | Discovered this session (2026-07-26), first real full-matrix run | The D-03 knob matrix must be grounded in real measurements (as done above), not the Phase-99/100 mock calibration |
| `_PPM_PLAUSIBILITY_BOUNDS["13C"] = (-15.0, 230.0)` assumed sufficient for any real 13C 2D experiment | HMBC's real, legitimate acquisition window reaches 234.8 ppm, exceeding the bound | Discovered this session | D-09 fix: widen the bound (recommend 240-250) |

**Deprecated/outdated:** None — this is the first real-data exercise of this code; nothing here is a regression, only a first real measurement.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Widening `_PPM_PLAUSIBILITY_BOUNDS["13C"]` to 240-250 is a safe, sufficient fix for the HMBC read failure, without masking a genuine future Hz/ppm divisor bug | Pitfall 1 / Don't Hand-Roll | LOW — verified this session that with the widened bound, the resulting axis is physically sensible (matches the expected 13C/1H ranges); a genuine divisor bug would produce errors far larger than 5-20 ppm, so the loosened bound should still catch it |
| A2 | The knob-matrix starting values recommended above will actually reach a QC-plausible peak count for COSY/HMBC (only HSQC was swept far enough to see a plausible-looking plateau in this session) | Code Examples / knob-matrix recommendation | MEDIUM — COSY in particular resisted thinning strongly even at snr_floor=800; the matrix may need to extend further, or combine with `threshold` fraction-of-max mode, or the D-03 budget may need to honestly conclude COSY needs a wider search than initially bounded |
| A3 | The nmr-chemist LLM agent will notice and use pre-existing `analysis/nmr_peaks/*.json` if its hardcoded `lucy pick` call fails against a `.dx` file (Pitfall 3) | Pitfall 3 / Open Questions #1 | HIGH if wrong — this is the single largest unverified assumption in the whole phase; if the agent does not recover, JVAL-02 stalls for a reason entirely outside this phase's own code, and the honest D-10 partial-close path would need to name this specific integration gap (not RECON-F1) as the tracked next step |
| A4 | No pre-existing Claude Code memory directory exists for the jcamp path (verified absent this session) will still be true at execution time | Pitfall 4 | LOW — directories don't spontaneously appear; re-verify immediately before the D-14 handoff as a cheap sanity check |

**If this table is empty:** N/A — see entries above; A3 is the one item that most needs user/planner attention.

## Open Questions (RESOLVED — operationalized in `103-01-PLAN.md`: Q1 → Task 6, Q2 → Task 3 Step B, Q3 → Task 1 + Task 3 Step E)

1. **RESOLVED (by design — only answerable by running JVAL-02 itself).** Will the byte-frozen `lucy-nmr-chemist` agent successfully consume pre-picked `analysis/nmr_peaks/*.json` instead of failing on its hardcoded `lucy pick <bruker-path>` step?
   - *Resolution:* Task 6 briefs the user on this exact risk in the D-14 handoff text, defines what "the agent recovered" vs. "the agent could not consume pre-picked peaks" looks like as an observation, and routes the second outcome into the D-10 honest-close branch with the named tracked next step **JVAL-F1** (teach the CASE path about pre-existing peak lists) — explicitly recorded as *not* a JCAMP-chain defect. No attempt is made to edit the byte-frozen agent files.
   - What we know: The agent's workflow is hardcoded to `lucy pick 1d/hsqc/hmbc <path>` (Bruker-only reader). There is zero written instruction anywhere in `case.md` or `lucy-nmr-chemist.md` about pre-existing peak lists. This exact hand-off was designed for in v10.0 but never once exercised (Phase 100 VAL-02 never reached this step).
   - What's unclear: Whether the agent, as an LLM following loose natural-language instructions, will notice the pre-existing JSON and adapt, or will stall/fail/misreport.
   - Recommendation: Flag this explicitly in the D-14 handoff instructions so a stall here is correctly attributed; record the actual observed behavior (success or failure, and how) in `VALIDATION.md` regardless of outcome — this is itself valuable evidence for the milestone even if JVAL-02 does not pass on the first attempt. Do not attempt to fix `case.md`/`lucy-nmr-chemist.md` (byte-frozen).

2. **RESOLVED — Task 3 Step B.** Exactly which knob values will drive COSY and HMBC to a §8-plausible peak count?
   - *Resolution:* the plan's 31-cell D-03 matrix carries **both** `snr_floor` and `threshold`-mode candidates for COSY and HMBC (COSY `snr_floor` 800/1500/3000/5000/8000 + `threshold` 0.02/0.05/0.10; HMBC `snr_floor` 500/1000/2000/3000/5000 + `threshold` 0.01/0.02/0.05), with per-experiment target zones and an explicit `MATRIX EXHAUSTED` outcome feeding the D-10 branch in Task 4.
   - What we know: HSQC has a clear-ish empirical target zone (snr_floor 3000-5000 range, from a measured plateau). COSY resists thinning far more strongly. HMBC was only lightly swept.
   - What's unclear: Whether `snr_floor` alone (vs. combining with the legacy `threshold` fraction-of-max mode) is sufficient for COSY without also destroying real weak long-range correlations.
   - Recommendation: Include both `snr_floor` and `threshold` mode candidates for COSY/HMBC in the D-03 matrix; if the honest D-03 budget is exhausted without reaching PASS, a soft-only PARTIAL + chemist confirmation (D-07) remains a valid, decided-in-advance outcome — do not treat "not a clean PASS" as a phase failure.

3. **RESOLVED — Task 1 + Task 3 Step E.** Does the widened `_PPM_PLAUSIBILITY_BOUNDS["13C"]` value need to also be re-verified against the 1D 13C reference for consistency, per JC-02's own stated verification discipline?
   - *Resolution:* Task 1 brackets the widened bound with negative controls that genuinely hold (a >250 ppm axis and a raw-**Hz** axis — the real HMBC `FIRST`/`LAST` 29516.31/-574.76), **not** the SFO-vs-SF control originally suggested here: `_assert_plausible_ppm_axis`'s own docstring records that error as only ~0.447 ppm, i.e. inside these bounds by design, so it remains JC-02's 1D cross-check's job. The stronger real-data evidence asked for here is Task 3 Step E's §10 cross-check table.
   - What we know: JC-02's cross-check discipline (Phase 101) says ppm-axis correctness should be checked against the trusted 1D reference, not just a coarse bound.
   - What's unclear: Whether the fix should also add/extend a test asserting the widened HMBC axis lines up with the real 1D 13C peak positions (stronger evidence than just "it no longer raises").
   - Recommendation: At minimum, cross-check a few real HMBC cross-peak 13C positions against the §10 list after the fix (this is effectively what the QC gate's `ppm_calibration` check already does for HSQC — extend the same expectation to HMBC once it can be read).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `lucy` CLI (editable install of this repo) | Everything | ✓ | 0.1.0 | — |
| LSD solver (`LSD`/`outlsd` on PATH) | JVAL-02 (`lucy lsd check`) | ✓ | — (verified `lucy lsd check` → both "available") | — |
| `click` | CLI option additions | ✓ | 8.1.8 | — |
| Reference database (`lucy database info`) | Not directly needed this phase (no dereplication/prediction path in JVAL-01/02 scope) | not checked | — | N/A — out of scope |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | D-14 fresh CASE session | ✓ (set in this shell) | — | Must be re-verified/set in whatever shell the human launches the fresh session from |
| `case-blind` alias (`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`) | D-13.1 blind-run hygiene | ✓ (present in `~/.zshrc`) | — | Manually export the env var if the alias is unavailable in the launching shell |
| Real `C20H32O2-jcamp` dataset (6 `.dx` files) | JVAL-01 | ✓ | ~55 MB total, verified present and readable | — |
| Sibling `NUS-RECONSTRUCTION-GUIDE.md` §8/§10 (read-only, for grading) | JVAL-01 D-05 cross-check | ✓ | — | — |

**Missing dependencies with no fallback:** None identified.

**Missing dependencies with fallback:** None identified — all required tooling is present on this machine.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Quick run command | `pytest tests/readers/test_jcamp.py tests/test_jcamp_1d_bridge.py tests/test_cli_jcamp.py tests/test_skill_files_unchanged.py -q` |
| Full suite command | `pytest -q` (1408 passing at Phase-102 close) |

Static gates (CLAUDE.md, run alongside the suite): `mypy src/lucy_ng` (strict), `ruff check src tests`.

Reused-module drift gate (extend Phase 102's, unchanged files list): `case.md` + 5 agent files must stay byte-identical (`tests/test_skill_files_unchanged.py`); `nus/qc.py`, `PeakPicker2D`, the 1D picker must stay byte-identical for this phase too (only `readers/jcamp.py` and `cli/jcamp.py` are the phase's own touched files, per D-09).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JVAL-01 (CLI knob wiring) | `--threshold`/`--snr-floor` accept both bare and `key=value` forms; backwards-compatible plain `--snr-floor 5.0` | unit + CLI-surface | `pytest tests/test_cli_jcamp.py -q` (extend existing `TestJcampCliSurface`) | ⚠️ extends existing file |
| JVAL-01 (D-09 reader fix) | Widened 13C plausibility bound lets HMBC read without breaking the existing plausibility guard for genuinely-wrong axes | unit | `pytest tests/readers/test_jcamp.py -q` (extend with a real-or-synthetic case near the new bound) | ⚠️ extends existing file |
| JVAL-01 (real-data run) | The real `C20H32O2-jcamp` dataset, with tuned per-experiment knobs, reaches QC PASS or soft-only PARTIAL | **MANUAL-ONLY** | N/A — real dataset (~55 MB) lives outside the repo and cannot be committed; this is the phase's own milestone-closing manual proof, mirroring Phase-100's VAL-01 | N/A |
| JVAL-01 (positive regression fixture, D-11.4) | The accepted real peak lists are committed as a new "known-good" fixture, distinct from the known-bad QC-02 floor | automated (once committed) | A new test asserting `run_qc_checks()` on the committed known-good fixture returns PASS/soft-PARTIAL (mirrors `tests/nus/test_qc_regression.py`'s known-bad-FAILs/synthetic-clean-PASSes shape) | ❌ new file, this phase |
| JVAL-02 (CASE convergence) | Fresh `/lucy-ng:case C20H32O2` observed to converge (LSD terminates, finite rankable set) | **MANUAL-ONLY** | N/A — interactive, human-started, multi-hour agentic run; not automatable (D-14) | N/A |

### Sampling Rate
- **Per task commit:** the quick command above.
- **Per wave merge:** full suite + `mypy` + the drift gate.
- **Phase gate:** full suite green before `/gsd:verify-work`; the two MANUAL-ONLY rows are satisfied by `VALIDATION.md`'s recorded evidence, exactly as Phase 100's VAL-01/02 rows were.

### Wave 0 Gaps
- [ ] A test near the widened `_PPM_PLAUSIBILITY_BOUNDS["13C"]` boundary (e.g. an axis at ~235 ppm passes, one genuinely wrong — e.g. computed from SFO instead of SF, which would be off by much more — still fails) — covers the D-09 reader fix.
- [ ] `tests/test_cli_jcamp.py` extension for the new `key=value` option parsing (both keyed and bare forms, plus an unrecognized-key error case).
- [ ] `tests/fixtures/jcamp/known_good_peaks/` (or equivalent name, planner discretion per D-11) + a small regression test mirroring `tests/nus/test_qc_regression.py`.

*Existing infrastructure otherwise covers this phase: `tests/readers/test_jcamp.py`, `tests/test_jcamp_1d_bridge.py`, `tests/test_cli_jcamp.py`, `tests/test_skill_files_unchanged.py` (all Phase 101/102, unaffected by this phase's additive changes except where explicitly extended above).*

## Proof-Level Ledger (honesty gate, extending Phase 102's)

| Level | What it covers going into Phase 103 |
|-------|--------------------------------------|
| **REAL-DATA (this research session)** | HMBC read failure at default bounds (reproduced against the real file); massive over-picking at default knobs on the real HSQC/COSY/HMBC/1D files (exact counts measured); the nmr-chemist/`lucy pick` Bruker-only hardcoding (verified by reading `cli/pick.py` source); the formula-only (not trivial-name) leak in the real `.dx` headers; the absence of a pre-existing memory directory for the jcamp path; LSD/outlsd availability on this machine |
| **FIXTURE-COVERED (Phase 102)** | Everything `tests/test_cli_jcamp.py`/`tests/readers/test_jcamp.py` already exercise on the trimmed 16-row fixtures — unaffected by this phase except where the D-09 fix requires new coverage |
| **NOT PROVEN — still open after this research** | Whether the D-03 knob matrix will actually reach a QC-PASS/soft-PARTIAL verdict on all three 2D experiments (only HSQC's approximate target zone was identified; COSY/HMBC need further sweeping in the plan's own execution); whether the nmr-chemist agent will actually recover from its hardcoded `lucy pick` failure (Open Question #1) — this can only be resolved by actually running JVAL-02, not by further research |

## Security Domain

No new external-facing surface is introduced this phase (no new endpoints, no new auth, no new untrusted network input). The relevant ASVS-adjacent concerns are file-handling only, already covered by existing patterns:

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V5 Input Validation | Yes (file paths) | `Path(...).resolve()` on every user-supplied path (already done in `cli/jcamp.py`); the new `key=value` option parser must reject an unrecognized experiment/nucleus key rather than silently ignoring it (typo guard, see Code Examples) |
| V12 File Handling | Yes | Existing CR-01-hardened write/quarantine boundary is unmodified by this phase's changes; the new knob options do not introduce any new file-write path, only new values flowing into the existing one |
| V2/V3/V4/V6 (auth, session, access control, crypto) | No | Not applicable — this is a local CLI + file-based workflow with no network/auth surface |

### Known Threat Patterns
No new threat surface. The one pre-existing consideration worth restating: the D-13 blind-run hygiene steps (README move-aside, memory quarantine) exist to prevent an *information* leak into the CASE run's context, not a security vulnerability in the traditional sense — treat them as data-integrity/scientific-validity controls, not ASVS findings.

## Sources

### Primary (HIGH confidence — verified directly in this session)
- Direct execution of `lucy jcamp` against the real `C20H32O2-jcamp` dataset (read-only, output to scratchpad) — verdict, peak counts, HMBC failure.
- Direct Python probing of `JcampReader.read_2d()`, `PeakPicker2D.pick_peaks()`, `_compute_2d_noise_sigma()` against the real files (snr_floor/threshold sweeps, timing).
- Direct grep of all six real `.dx` files' headers for compound-name/formula leak content.
- Source reads: `src/lucy_ng/cli/jcamp.py`, `src/lucy_ng/nus/bridge.py`, `src/lucy_ng/processing/jcamp_1d_bridge.py`, `src/lucy_ng/nus/qc.py`, `src/lucy_ng/readers/jcamp.py`, `src/lucy_ng/processing/peak_picker_2d.py`, `src/lucy_ng/processing/peak_picker.py`, `src/lucy_ng/cli/pick.py`, `src/lucy_ng/cli/lsd.py`, `src/lucy_ng/cli/nus.py`.
- `.claude/commands/lucy-ng/case.md` and `.claude/agents/lucy-nmr-chemist.md` (read directly, byte-frozen).
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` §8/§10 (transcribed verbatim above).
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/` directory inventory + `README.md`.
- `lucy lsd check`, `lucy --version`, `python -c "import click; print(click.__version__)"` — direct tool verification.

### Secondary (MEDIUM confidence)
- `.planning/phases/102-.../102-LEARNINGS.md`, `102-VALIDATION.md`, `102-CONTEXT.md` — prior-phase decisions and the proof-level-ledger pattern this document extends.
- `.planning/phases/100-.../100-CONTEXT.md`, `100-03-PLAN.md` — the honest-partial-close and observation-not-instrumentation precedent this phase's D-10/D-15/D-16 mirror.
- `~/.claude/projects/.../memory/project_blind_uat_memory_contamination.md` — the `case-blind`/env-var mechanism, cross-referenced against CONTEXT.md's D-13.1 wording.

### Tertiary (LOW confidence)
- None — every claim above was either verified directly this session or cited from an existing project document.

## Metadata

**Confidence breakdown:**
- Standard stack / package legitimacy: N/A — no new packages
- CLI wiring pattern (D-04): HIGH — verified `click` version, verified `multiple=True` precedent in-repo, pattern is standard Click usage
- Real-data peak-pick/QC behavior (Pitfalls 1-2): HIGH — directly measured this session against the real dataset
- CASE-handoff integration risk (Pitfall 3 / Open Question #1): MEDIUM — the *gap* is verified (source code + agent file both read directly), but the *actual runtime outcome* (does the LLM agent recover) is inherently unverifiable without running it
- Blind-run hygiene mechanism (Pitfall 4): HIGH — verified against this project's own documented incident and current `~/.zshrc`

**Research date:** 2026-07-26
**Valid until:** This is real-data-grounded empirical research tied to one specific dataset and one specific commit of the codebase — treat findings on peak counts/knob values as valid until the reader or picker code changes; the nmr-chemist integration risk (Open Question #1) is valid until `case.md`/`lucy-nmr-chemist.md` are ever intentionally revised (out of scope, not expected soon) or until JVAL-02 is actually attempted (which resolves the question empirically either way).
