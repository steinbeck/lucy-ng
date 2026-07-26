# Phase 103: End-to-End Validation (C20H32O2-jcamp) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-26
**Phase:** 103-end-to-end-validation-c20h32o2-jcamp
**Areas discussed:** Peak-pick tuning budget, QC verdict & chemist gate, CASE run setup (JVAL-02), Failure contingency & fix boundary

---

## Peak-Pick Tuning Budget

### Q1 — How far may Phase 103 extend the tuning surface to reach §8 quality?

| Option | Description | Selected |
|--------|-------------|----------|
| Wire `--threshold` through | Both bridges already accept `threshold`; only the Click option is missing. No new algorithm, no `PeakPicker2D` edit. | ✓ |
| Turn `--snr-floor` only | Pure proof phase, no code. A miss becomes a documented honest stop. | |
| Knobs + ridge post-filter | Additional post-pick ridge/artefact filter for HMBC. | |

**User's choice:** Wire `--threshold` through.
**Notes:** Ridge filtering was rejected on the grounds that ridge-freedom is what §8 is meant to measure.

### Q2 — How tightly bounded is the tuning budget before an honest stop?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-defined fixed knob matrix | Finite combination matrix set up front (e.g. 3 × 3 per experiment), all results logged, then stop. | ✓ |
| Wall-clock budget | Time cap instead of a combination count. | |
| Baseline run, then decide | Run defaults first, review together, then set the budget. | |

**User's choice:** Pre-defined fixed knob matrix.
**Notes:** Follows the Phase-100 D-04 pattern — keeps it at "did we drive it correctly" instead of open-ended drift.

### Q3 — Are knob values chosen globally or per experiment?

| Option | Description | Selected |
|--------|-------------|----------|
| Per experiment | HSQC clean, HMBC ridge-prone, COSY carries the OH ridge at 5.32; chosen set recorded per experiment in VALIDATION.md. | ✓ |
| One global set | Single pair for the whole run. | |
| Global by default, per-experiment on demand | Deviate only where §8 tears. | |

**User's choice:** Per experiment.

### Q4 — How are per-experiment values wired without breaking the single QC call?

| Option | Description | Selected |
|--------|-------------|----------|
| Repeatable `key=value` options | `--threshold hsqc=… --threshold hmbc=…`; one `lucy jcamp` invocation stays, QC gate still runs exactly once. Purely additive CLI change. | ✓ |
| Tune offline, final run with one set | Knob search in a throwaway script against `bridge_peak_pick`; final run carries one global set. | |
| Separate runs per experiment, QC afterwards | One invocation per file into a shared dir, then `lucy nus qc`. | |

**User's choice:** Repeatable `key=value` options.
**Notes:** Load-bearing — the 1D lists are the trusted reference for grading the 2D ones, so the gate must see the full staged set at once.

---

## QC Verdict & Chemist Gate

### Q1 — What does the JVAL-01 verdict rest on?

| Option | Description | Selected |
|--------|-------------|----------|
| QC verdict + explicit §10 cross-check | Verdict stays the formal gate; VALIDATION.md additionally carries picked-vs-§10 1D-¹³C shifts and counted HSQC correlations vs §8's ~17 protonated carbons. | ✓ |
| QC verdict only | Purely machine acceptance per Phase-100 D-02. | |
| Verdict + §10 + second independent quaternary derivation | Derive prot/quaternary from HSQC coverage itself. | |

**User's choice:** QC verdict + explicit §10 cross-check.
**Notes:** Motivated by the inherited `classification_source == "override"` behaviour — the quaternary check partly grades itself against pre-baked knowledge of this compound. The third option was flagged as circular by Phase-99 D-03 (HSQC is the thing under test).

### Q2 — How does the chemist confirmation on a soft-PARTIAL actually work?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline gate during the phase | Executor stops, presents violated soft checks + §10 table + connectivity summary; decision recorded verbatim in VALIDATION.md. | ✓ |
| Spectra images as the basis | Render 2D spectra with overlaid picks (v9.3 webview) for visual judgement. | |
| No gate — judge after the CASE run | Wave PARTIAL through, let the CASE result decide retroactively. | |

**User's choice:** Inline gate during the phase.
**Notes:** Webview rejected on wiring cost (it hangs off a CASE run manifest, not a JCAMP ingest).

### Q3 — What if the picked 1D-¹³C list disagrees with §10?

| Option | Description | Selected |
|--------|-------------|----------|
| Correct only via the knob matrix, never by hand | Disagreement drives knob variation inside the matrix; manual editing forbidden; residual deviation documented. | ✓ |
| Allow feeding the §10 list as reference | Decouples JVAL-02 from 1D pick quality but makes the run partly non-blind. | |
| Separate roles: picked for CASE, §10 for comparison only | Strict, but without the knob-matrix headroom. | |

**User's choice:** Correct only via the knob matrix, never by hand.
**Notes:** Hand-editing would build the answer into the input and make JVAL-02 worthless.

### Q4 — How do the critical/soft tiers apply to this run?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase-99/100 tiers unchanged | Critical: quaternary 1-bond correlation, ppm calibration, signal-to-ridge. Soft: edited-sign consistency, COSY diagonal symmetry. | ✓ |
| Treat the quaternary check as soft (because of the override) | Resolves the circularity but removes the fabricated-cross-peak guard. | |

**User's choice:** Phase-99/100 tiers unchanged.

---

## CASE Run Setup (JVAL-02)

### Q1 — Which directory does the fresh `/lucy-ng:case` run in?

| Option | Description | Selected |
|--------|-------------|----------|
| The jcamp directory, cleanly separated | CASE runs on `C20H32O2-jcamp/analysis/nmr_peaks/`; sibling Bruker tree not entered; README moved aside. | ✓ |
| Fresh working directory, only peaks + formula copied | Maximally blind, but decoupled from data provenance. | |
| jcamp directory, README left in place | Zero effort, but the README names the compound class and links the ground-truth guide. | |

**User's choice:** The jcamp directory, cleanly separated.
**Notes:** The sibling tree holds NUS-RECONSTRUCTION-GUIDE.md (§8/§10), DIAGNOSTIC-REPORT.md and 17 `iteration_*` directories from the failed 2026-07-09 run.

### Q2 — Who executes the CASE run, and how?

| Option | Description | Selected |
|--------|-------------|----------|
| Fresh interactive session, started by the user | Executor prepares and stops; user runs `/lucy-ng:case` in a fresh session and reports back. | ✓ |
| Headless from inside the phase | Fully automatic, but the executor is not blind and the headless path requires inline stage driving. | |
| On Sheldon | More LSD compute, but 55 MB transfer + setup for no gain. | |

**User's choice:** Fresh interactive session, started by the user.

### Q3 — What counts as "converged on a finite, rankable solution set"?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase-100 D-03 unchanged + hard cap | LSD terminates normally + `lucy lsd rank` produces a ranked list; pre-defined wall-clock/iteration cap; correct structure in top-N = bonus. | ✓ |
| Plus a candidate-count ceiling | Concrete number (e.g. ≤ 10,000) so "finite" cannot mean 500,000. | |
| Correct structure in top-N required | Strongest proof, but depends on ranking quality and regiochemistry. | |

**User's choice:** Phase-100 D-03 unchanged + hard cap.

### Q4 — Which blind safeguards are mandatory? *(multi-select)*

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-memory off in the data directory | `autoMemoryEnabled: false` + quarantine of pre-existing memory files. | ✓ |
| Move README/guide references aside | README relocated for the run, restored afterwards. | ✓ |
| Metadata leak check on the `.dx` files | Check `##TITLE`, `##SAMPLE DESCRIPTION`, `mddnmr` audit trail for a compound name. | ✓ |
| Log model disclosure | `case.md` disclosure gate runs; model used recorded in VALIDATION.md. | ✓ |

**User's choice:** All four.

---

## Failure Contingency & Fix Boundary

### Q1 — Which code fixes may Phase 103 pull in?

| Option | Description | Selected |
|--------|-------------|----------|
| Reader/bridge/CLI yes, gate semantics no | Fixes in `readers/jcamp.py`, the 1D bridge, `cli/jcamp.py`; `nus/qc.py`, the pickers, `case.md` and the 5 agent files stay byte-frozen; every fix logged as a deviation. | ✓ |
| Strictly no code — run and record only | Maximal proof separation, risks losing the milestone to a one-liner. | |
| Anything except `case.md`/agent files | Maximal freedom, destroys the "unchanged Phase-99 reuse" claim (JCLI-02). | |

**User's choice:** Reader/bridge/CLI yes, gate semantics no.
**Notes:** Follows the Phase-102 precedent, where the COSY-blocking `_resolve_dim` defect was pulled into the next phase because it blocked that phase's own success criteria.

### Q2 — What happens if the budget is exhausted and QC critically FAILs or CASE does not converge?

| Option | Description | Selected |
|--------|-------------|----------|
| Honest partial close, per Phase 100 | Achieved recorded as achieved, not-achieved as NOT achieved; VALIDATION.md + limitation note + named tracked next step; v10.1 closes PARTIAL. | ✓ |
| JVAL-01 and JVAL-02 separately closable | Finer resolution of the partial close. | |
| Block the milestone until solved | Risks blocking indefinitely on LSD solvability. | |

**User's choice:** Honest partial close, per Phase 100.

### Q3 — Which evidence is committed? *(multi-select)*

| Option | Description | Selected |
|--------|-------------|----------|
| VALIDATION.md as primary artefact | Knob values, peak counts, verdict + violations, §10 table, chemist verdict verbatim, CASE result, model used. | ✓ |
| The real peak JSONs | Generated `analysis/nmr_peaks/*.json` as durable evidence. | ✓ |
| The QC report JSON | Full `qc_report.json` with all six checks, thresholds, violations. | ✓ |
| Peaks as a new positive regression fixture | Known-good counterpart to the known-bad home-IST set. | ✓ |

**User's choice:** All four.
**Notes:** The known-bad QC-02 fixtures must never be overwritten; the positive fixture must be regenerable and must record the knob values it depends on.

### Q4 — How is the phase structured, given the CASE run comes from a foreign fresh session?

| Option | Description | Selected |
|--------|-------------|----------|
| One plan with a handoff gate at the end | Ingestion + tuning + QC + chemist gate + VALIDATION.md through JVAL-01, then explicit handoff; `autonomous: false` like 100-03. | ✓ |
| Two separate plans | Plan 1 autonomous (JVAL-01), plan 2 non-autonomous (JVAL-02). | |
| Three plans incl. an upfront CLI-extension plan | Cleanest code/proof separation, more planning overhead. | |

**User's choice:** One plan with a handoff gate at the end.

---

## Claude's Discretion

- Concrete numeric bounds of the knob matrix (values per knob, starting values per experiment).
- The concrete wall-clock/iteration cap for the CASE run.
- Exact `key=value` option syntax and parsing, and how the bare-value default is preserved.
- Layout of VALIDATION.md and placement of the committed peak JSONs / positive fixture relative to the known-bad QC-02 fixtures.
- Mechanism of the JCAMP-header leak check (reuse of the sanitise path vs. a one-off grep).

## Deferred Ideas

- Post-pick ridge/artefact filter for the JCAMP path (rejected in D-01; a new requirement if real HMBC data proves unusable without it).
- CLI escape hatch for `QcConfig`'s quaternary override (needs an edit to the byte-frozen `qc.py`).
- Webview rendering of a JCAMP ingest (spectra + overlaid picks) — rejected as the chemist-gate mechanism, natural later UX requirement.
- NOESY consumption by the CASE constraint model (JC-F1).
- RECON-F1 (hmsIST/mddnmr in-lucy-ng NUS fallback), carried from v10.0.
- Milestone-close bookkeeping (`/gsd-complete-milestone`, infographic-deck refresh).

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` (score 0.6) — unrelated to JCAMP validation.
- `2026-06-30-ranking-tests-hardfail-without-hosegen` — ranking-test-infra todo, unrelated.
