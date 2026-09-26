# Phase 103: End-to-End Validation (C20H32O2-jcamp) - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning

<domain>
## Phase Boundary

The milestone-closing **proof phase** of v10.1. The `C20H32O2-jcamp` dataset —
six real `.dx` files (1H, 13C, HSQC, HMBC, COSY, NOESY; 2D grids up to
2048×2048), reconstructed externally in TopSpin via `mddnmr` CS/IRLS — is run
through the shipped `lucy jcamp` chain for the first time on **non-fixture**
data, graded against §8 quality, and then handed to a fresh `/lucy-ng:case`
run. Delivers requirements **JVAL-01, JVAL-02**.

**In scope:**
- **JVAL-01:** all six `.dx` read + peak-picked via `lucy jcamp` (NOESY skipped
  per D-06), driven to §8 quality within a pre-defined tuning budget, QC verdict
  PASS or soft-only PARTIAL + chemist confirmation, plus an explicit §10
  ground-truth cross-check table.
- **JVAL-02:** a fresh `/lucy-ng:case C20H32O2` on the JCAMP-derived peak lists
  converging on a finite, rankable solution set.
- One **additive** CLI change: expose the already-existing `threshold`
  parameter of both bridges as a per-experiment `lucy jcamp` option (D-01/D-04).
- Durable evidence: `VALIDATION.md`, the real peak JSONs, `qc_report.json`, and
  a new positive regression fixture.

**Out of scope (later / other milestones):**
- Any change to the **QC gate semantics** (`nus/qc.py`), `PeakPicker2D`, the 1D
  picker, `case.md` or the 5 agent files — the SHA-256 byte-freeze guard from
  Phase 102 stays green (D-09).
- New peak-picking algorithms, ridge post-filters, or a re-tuned noise
  estimator (rejected in D-01).
- NUS self-reconstruction inside lucy-ng (v10.0 PARTIAL / RECON-F1).
- NOESY consumption by the CASE constraint model (JC-F1).
- Milestone-close bookkeeping (`/gsd-complete-milestone`, infographic-deck
  refresh) — a separate command, not this phase.

**Invariant carried forward (Phases 98/99/102):** `case.md` and the 5-agent team
stay **byte-unchanged**; JVAL-02 runs the real orchestrator unmodified.
</domain>

<decisions>
## Implementation Decisions

### Peak-pick tuning surface & budget (JVAL-01)

- **D-01 — Expose `threshold`; no new picking logic.** `bridge_peak_pick`
  (2D) and `bridge_peak_pick_1d` already accept `threshold` **and**
  `snr_floor`; `cli/jcamp.py` only wires `--snr-floor` (default 5.0). Phase 103
  adds the missing Click option so the tuning surface is two real knobs.
  **Rejected:** a post-pick ridge/artefact filter — ridge-freedom is what §8 is
  supposed to *measure*, so filtering it away would invalidate the check.
  **Also rejected:** turning `--snr-floor` alone and honest-stopping — the knob
  already exists in the bridges, withholding it from the CLI is an accident of
  Phase-102 scope, not a deliberate constraint.

- **D-02 — Per-experiment knob values, not one global set.** HSQC is clean,
  HMBC is ridge-prone, COSY carries the OH ridge at 5.32 ppm; a single value
  would either smear HMBC or thin out HSQC. The chosen `(threshold, snr_floor)`
  pair **per experiment** is recorded in `VALIDATION.md` so the run is
  reproducible by hand.

- **D-03 — Pre-defined finite knob matrix, then honest stop** (the Phase-100
  D-04 pattern). The planner fixes a concrete, finite combination matrix up
  front (e.g. 3 `snr_floor` × 3 `threshold` values per experiment ⇒ ≤ 9 runs per
  experiment); **every** combination's outcome is logged, not just the winner.
  Once the matrix is exhausted, tuning stops — this keeps the phase at "did we
  drive it correctly", not open-ended drift.
  **Rejected:** a wall-clock budget (harder to document) and a
  baseline-run-then-decide gate (inserts an extra user interrupt mid-phase).

- **D-04 — Per-experiment knobs are wired as repeatable `key=value` options on
  the single `lucy jcamp` invocation.** e.g.
  `--threshold hsqc=1e4 --threshold hmbc=3e4 --snr-floor cosy=7`, with the
  bare/unkeyed value (or the existing default) applying to every experiment not
  named. **This is load-bearing:** the QC gate must run **exactly once** over
  the fully-staged set because the 1D lists are the trusted reference for
  grading the 2D ones (Phase-102 staged/final two-call pattern). Splitting into
  per-file invocations would give each run a referenceless, useless QC pass and
  trigger the D-07 write boundary per run. Backwards compatibility of the plain
  `--snr-floor 5.0` form must be preserved.

### QC grading & the chemist gate (JVAL-01)

- **D-05 — JVAL-01 = QC verdict **plus** an explicit §10 cross-check table.**
  The QC verdict stays the formal gate (Phase-100 D-02 semantics carried
  forward unchanged), but `VALIDATION.md` additionally carries:
  (a) picked 1D-¹³C shifts vs. the §10 ground-truth shifts, with per-signal
  deviation, and (b) counted HSQC correlations vs. §8's ~17 protonated carbons.
  **Why:** with no DEPT file present, `QcConfig.default()`'s
  `known_quaternary_shifts` — the five compiled-in §8 shifts (142.00, 135.86,
  79.35, 36.23, 37.86) — is applied unconditionally, so
  `classification_source` reads `"override"` (Phase-102 surprise, inherited
  byte-protected behaviour). The quaternary check therefore partly grades
  itself against pre-baked knowledge of this compound; the §10 table is the
  independent evidence the gate cannot supply on this dataset.

- **D-06 — Critical/soft tiers stay exactly as Phase 99/100 defined them.**
  Critical (⇒ FAIL, never waved through): quaternary-carbon 1-bond correlation,
  ppm calibration, signal-to-ridge dominance. Soft (⇒ PARTIAL possible):
  edited-sign self-consistency, COSY diagonal symmetry. **Explicitly rejected:**
  downgrading the quaternary check to informational because of the override —
  that check is precisely the fabricated-cross-peak guard this whole milestone
  exists for, and `qc.py` is byte-frozen anyway.

- **D-07 — Soft-PARTIAL chemist confirmation is an inline gate during the
  phase.** The executor stops, presents the violated soft checks + the §10
  cross-check table + a short summary of the COSY/HMBC connectivity, the user
  (the chemist) confirms or rejects, and the decision **with its reasoning** is
  recorded verbatim in `VALIDATION.md`. One-off, no CI burden — the Phase-100
  D-02 pattern. **Rejected:** rendering spectra with overlaid picks for visual
  judgement (the v9.3 webview hangs off a CASE run manifest, not a JCAMP
  ingest — wiring cost not justified here), and deferring the judgement until
  after the CASE run (would burn a long run on visibly bad peaks).

- **D-08 — A 1D-¹³C list that disagrees with §10 is corrected only through the
  D-03 knob matrix, never by hand.** The picked 1D lists are simultaneously the
  QC gate's trusted reference **and** CASE's input, so a mis-pick poisons both.
  Disagreement is a signal to vary the 1D knob values inside the matrix.
  **Hand-editing a peak list against §10, or substituting the §10 list as the
  reference, is forbidden** — it would build the answer into the input and make
  JVAL-02 worthless. Residual deviations are documented in `VALIDATION.md`, not
  retouched away.

### Fix boundary & failure contingency

- **D-09 — Reader/bridge/CLI fixes allowed; gate semantics frozen.** Genuine
  defects in `readers/jcamp.py`, `processing/jcamp_1d_bridge.py` or
  `cli/jcamp.py` that block JVAL-01/02 are fixed inside Phase 103 — the
  Phase-102 precedent (the COSY-blocking `_resolve_dim` defect was pulled into
  the next phase because it blocked that phase's own success criteria).
  **Byte-frozen:** `nus/qc.py`, `PeakPicker2D`, the 1D picker, `case.md`, the
  five `lucy-*.md` agent files — `tests/test_skill_files_unchanged.py` must stay
  green. Every such fix is logged as an explicit deviation so a proof phase does
  not silently become a development phase.
  **Rejected:** strict no-code (risks losing the milestone to a one-line fix)
  and anything-goes-except-case.md (would destroy the "unchanged Phase-99
  reuse" claim that *is* JCLI-02).

- **D-10 — On exhausted budget: honest partial close, per Phase 100.** What was
  achieved is recorded as achieved; what was not is recorded as **NOT**
  achieved — `VALIDATION.md` + a limitation note in ROADMAP/REQUIREMENTS + a
  **named tracked next step** (the RECON-F1 analogue). v10.1 then closes
  PARTIAL. No indefinite milestone block: CASE convergence also depends on
  LSD's solvability for this compound, not only on the JCAMP chain.

- **D-11 — Committed evidence (all four).**
  1. `VALIDATION.md` as the primary artefact: per experiment the chosen knob
     values, peak counts, QC verdict + violated checks, the §10 cross-check
     table, the chemist's verdict verbatim, the CASE outcome, and the model
     actually used.
  2. The real generated `analysis/nmr_peaks/*.json`.
  3. The full `qc_report.json` (all six checks, thresholds, violations).
  4. The JCAMP peaks additionally committed as a **known-good positive
     regression fixture** — the counterpart to the known-bad home-IST set.
  **Hard constraint:** the existing known-bad QC-02 regression fixtures under
  `.../C20H32O2/analysis/nmr_peaks/` must **never** be overwritten — they are
  the floor proving the gate discriminates. The positive fixture must be
  regenerable and must record the knob values it depends on.

### CASE run setup (JVAL-02)

- **D-12 — The run happens in the jcamp directory, cleanly separated.**
  `lucy jcamp` writes to `C20H32O2-jcamp/analysis/nmr_peaks/`, CASE runs there.
  The sibling Bruker tree `../C20H32O2/` is **not entered**: it holds
  `NUS-RECONSTRUCTION-GUIDE.md` (§8/§10 ground truth), `DIAGNOSTIC-REPORT.md`
  and 17 `iteration_*` directories from the failed 2026-07-09 run — an agent
  working there reads the answer.

- **D-13 — Four blind safeguards are mandatory** (all selected):
  1. `autoMemoryEnabled: false` for the jcamp data directory + quarantine of any
     pre-existing memory files there (the known per-data-dir contamination
     vector).
  2. `C20H32O2-jcamp/README.md` moved aside for the duration of the run (it
     names the compound class and links the ground-truth guide), restored
     afterwards.
  3. A `lucy sanitise`-style check of the JCAMP headers (`##TITLE`,
     `##SAMPLE DESCRIPTION`, the `mddnmr` audit trail) for a compound name —
     the exact leak found in the Bruker datasets CASE2/3/4/5/8.
  4. The `case.md` model-disclosure gate runs and the model actually used is
     recorded in `VALIDATION.md`.

- **D-14 — A fresh interactive session, started by the user.** The executor
  prepares everything (peaks written, QC green, directory clean) and stops; the
  user starts `/lucy-ng:case` in a fresh session in the jcamp directory and
  reports the result back. Rationale: skill edits only load in a fresh session,
  the push-based coordination pattern works as designed interactively, and the
  blind-UAT convention (a fresh, uncontaminated instance) is preserved — the
  executor itself carries the whole milestone context including §8/§10 and is
  therefore *not* blind. **Rejected:** headless from inside the phase, and a
  Sheldon run (55 MB transfer + setup for no gain here).

- **D-15 — JVAL-02 bar = Phase-100 D-03 unchanged, plus a hard cap.** Success =
  LSD terminates normally (no timeout, no ~10⁶ explosion — the 2026-07-09
  failure mode) **and** `lucy lsd rank` produces a ranked list. A pre-defined
  wall-clock / iteration cap makes "terminates" measurable. **The correct
  C20H32O2 structure appearing in the top-N is explicitly a bonus, not a
  condition** — that depends on ranking quality and regiochemistry resolution,
  well beyond "the JCAMP connectivity is usable".

### Phase structure

- **D-16 — One plan, ending in a handoff gate, `autonomous: false`.** The plan
  runs the additive CLI change → ingestion → knob matrix → QC → §10 table →
  chemist gate, writes `VALIDATION.md` through JVAL-01, and ends with an
  explicit handoff ("start `/lucy-ng:case` in a fresh session now, report
  back"). `VALIDATION.md` is then extended with the JVAL-02 part before phase
  verification. Mirrors `100-03-PLAN.md`'s honest `autonomous: false` shape.

### Claude's Discretion
- The concrete numeric knob-matrix bounds (how many values per knob, which
  starting values per experiment) — the planner sets a finite, explicit matrix
  (D-03).
- The concrete wall-clock/iteration cap for the CASE run (D-15).
- Exact `key=value` option syntax and parsing for the per-experiment knobs, and
  how the bare-value default is preserved (D-04) — planner discretion, additive
  and backwards-compatible.
- Layout of `VALIDATION.md` and where the committed peak JSONs / positive
  fixture live relative to the known-bad QC-02 fixtures (D-11).
- The mechanism of the JCAMP-header leak check (D-13.3) — reuse of the existing
  sanitise path vs. a one-off grep — planner picks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone planning
- `.planning/REQUIREMENTS.md` — JVAL-01, JVAL-02 (the two requirements this
  phase closes); the Out-of-Scope table (no changes to `PeakPicker2D`, the QC
  gate, or `case.md`); JC-F1 (NOESY) and RECON-F1 deferred.
- `.planning/ROADMAP.md` § "Phase 103: End-to-End Validation (C20H32O2-jcamp)"
  — goal + the 3 success criteria; § "Phase 100" limitation note for the
  honest-partial-close precedent (D-10).

### Prior-phase context (decisions this phase inherits)
- `.planning/phases/102-cli-peak-pick-bridge-qc-reuse/102-CONTEXT.md` — D-01
  single full-chain command, D-02 output location, D-03 1D bridge, D-04 QC
  reuse + quaternary override, **D-05 (the JVAL boundary this phase is on the
  other side of)**, D-06 NOESY skip.
- `.planning/phases/102-cli-peak-pick-bridge-qc-reuse/102-LEARNINGS.md` —
  **read before planning.** The staged/final two-call QC wiring (why D-04
  matters), the `RECON_BACKEND="jcamp"` provenance split, the CR-01
  run-to-run state-hygiene defect, the `PYTHONPATH="$(pwd)/src"` worktree
  hazard, the `CliRunner(mix_stderr=False)` JSON-assertion hazard, and the
  proof-level-ledger pattern.
- `.planning/phases/102-cli-peak-pick-bridge-qc-reuse/102-VALIDATION.md` §
  "Manual-Only Verifications" + § "Proof-Level Ledger" — the four items filed
  **NOT PROVEN — Phase 103 / JVAL** are exactly this phase's work list:
  peak-count plausibility, full-matrix SNR behaviour, the §8-quality green
  verdict, CASE convergence, and any claim that a verdict is chemically correct.
- `.planning/phases/100-cross-platform-hardening-end-to-end-validation/100-CONTEXT.md`
  — D-02 (QC PASS / soft-PARTIAL + chemist confirm), D-03 (the CASE bar), D-04
  (bounded budget → honest stop) — all carried forward here.
- `.planning/phases/99-peak-pick-bridge-qc-gate-cli/99-CONTEXT.md` — D-01/D-02
  verdict semantics and critical-vs-soft tiers (D-06), **D-03 non-circular
  prot/quaternary classification** (why D-05's third option was rejected), D-05
  additive metadata block, D-07 write boundary.

### Ground truth & the dataset (real, external — not committed)
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/`
  — the six `.dx` files + `Molecular-Formula.txt` (`C20H32O2`) + `README.md`
  (moved aside during the CASE run per D-13.2).
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md`
  **§8** — the authoritative quality definitions JVAL-01 grades against (~17
  protonated carbons each with one/CH₂-two HSQC correlations; the five
  quaternaries 142.00/135.86/79.35/36.23/37.86 with NO 1-bond correlation;
  clean edited signs; ridge-free HMBC; a real aliphatic COSY network, not just
  the OH ridge at 5.32) — and **§10**, the ground-truth 1D shifts for the D-05
  cross-check table. **Read by the executor for grading only — never inside the
  CASE run's working tree (D-12).**
- `.../C20H32O2/analysis/nmr_peaks/*.json` — the known-bad home-IST lists
  (QC-02 FAIL regression floor). **Must NOT be overwritten** (D-11).

### Existing code this phase runs and may fix (D-09)
- `src/lucy_ng/cli/jcamp.py` — the full-chain command; currently `--out`,
  `--snr-floor` (default 5.0), `--format`. D-01/D-04 add the per-experiment
  `--threshold`/`--snr-floor` wiring here. Carries the staged/final QC call,
  the D-06 skip path, the D-07 write boundary and the CR-01 state-hygiene
  clearing.
- `src/lucy_ng/nus/bridge.py::bridge_peak_pick(spectrum, *, experiment,
  qc_report, recon_meta, threshold=None, snr_floor=5.0)` — **already accepts
  `threshold`**; byte-unchanged reuse.
- `src/lucy_ng/processing/jcamp_1d_bridge.py::bridge_peak_pick_1d(spectrum, *,
  threshold=None, snr_floor=None)` — same, for the 1D lists.
- `src/lucy_ng/readers/jcamp.py` — `JcampReader.read/read_1d/read_2d`,
  `_resolve_dim` with the `procs_index` hint; fixable under D-09.
- `src/lucy_ng/nus/qc.py` — **byte-frozen.** `run_qc_checks`, the keyword-glob
  1D reference discovery, `QcConfig.default()`'s `known_quaternary_shifts`
  (the D-05 override caveat).
- `tests/test_skill_files_unchanged.py` — the SHA-256 + roster guard that must
  stay green (D-09).
- `.claude/commands/lucy-ng/case.md` — the unmodified orchestrator JVAL-02
  invokes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`lucy jcamp` (Phase 102, shipped)** — the entire chain already exists:
  discovery → read → 1D/2D routing → picking → single staged QC call →
  verdict-annotated write or quarantine + non-zero exit. Phase 103 *runs* it;
  the only planned code change is exposing `threshold`.
- **`threshold` in both bridges** — present and typed, just unreachable from
  the CLI. D-01 is genuinely a wiring change, not new logic.
- **`lucy nus qc <peaks-dir>`** — standalone re-grading with custom thresholds,
  identical schema across the NUS and JCAMP paths (Phase-102 D-01). Useful for
  re-scoring a knob-matrix run without re-picking.
- **Phase-102 committed fixtures + `tests/test_cli_jcamp.py`** — the regression
  floor that must stay green while D-01/D-09 changes land.

### Established Patterns
- **Staged/final two-call QC wiring** — stage every file with
  `qc_report=None`, run the gate **once** over the complete staged set, rebuild
  payloads with the real verdict. This is why D-04 keeps a single invocation.
- **D-07 write boundary + CR-01 state hygiene** — a FAIL writes nothing
  consumable and the previous run's output is cleared first; the guarantee is
  about the *state of the directory*, not the behaviour of one invocation.
- **Bounded budget → honest stop → named next step** (Phase-100 D-04) — the
  shape D-03/D-10 reuse.
- **Proof-level ledger** (Phase-102 `VALIDATION.md`) — every claim filed as
  FIXTURE-COVERED / SYNTHETIC / MOCK-COVERED / NOT-PROVEN. Phase 103's job is
  to move the four NOT-PROVEN rows into a real-data level.

### Integration Points
- `lucy jcamp <jcamp-dir>` → `C20H32O2-jcamp/analysis/nmr_peaks/{HSQC,HMBC,COSY}.json`
  + `13C.json`/`1H.json` → QC gate (unchanged) → verdict embedded per payload.
- Those same 1D lists serve double duty: QC trusted reference **and** CASE 1D
  input (the D-08 constraint follows from this).
- `/lucy-ng:case` in a fresh session, working in the jcamp directory, reading
  those peak lists — orchestrator byte-unchanged.

### Known hazards to carry into the plan
- `PYTHONPATH="$(pwd)/src"` is required for any runtime verification inside a
  git worktree — the editable install otherwise resolves to the main checkout.
- Worktree executors have repeatedly started on a stale base commit; the
  `git reset --hard` base assertion is load-bearing.
- `_compute_2d_noise_sigma`'s global MAD was only ever exercised on 16-row
  trimmed fixtures — its behaviour on a full 2048×2048 matrix is unproven and
  is a prime suspect if the first real run's peak counts look wrong.

</code_context>

<specifics>
## Specific Ideas

- **This is a proof phase, and the proof must stay clean.** Every deviation
  from "run the shipped chain and report" — the CLI knob (D-01), any reader fix
  (D-09) — is deliberate, bounded, and logged. The failure mode to avoid is a
  phase that quietly turns into development and then claims the pipeline
  "worked".
- **The §10 table exists because the QC gate cannot be fully independent
  here.** With `classification_source == "override"` the quaternary check leans
  on five compiled-in shifts of this very compound. That is inherited,
  byte-protected behaviour — so the honest response is extra independent
  evidence (D-05), not a re-tuned gate.
- **Never hand-edit a peak list toward §10** (D-08). The whole point of JVAL-02
  is that CASE receives what the pipeline actually produced.
- **The sibling Bruker tree is radioactive for the CASE run** — guide,
  diagnostic report and 17 iteration directories from the failed run all sit
  there (D-12).
- **JVAL-01 is the gate; JVAL-02 is the bar.** A soft-PARTIAL ingestion that
  still lets CASE converge on a rankable set is a genuine milestone pass.
- The four rows filed **NOT PROVEN — Phase 103 / JVAL** in
  `102-VALIDATION.md` are the literal acceptance list for this phase.

</specifics>

<deferred>
## Deferred Ideas

- **Post-pick ridge/artefact filter for the JCAMP path** — rejected in D-01
  (would filter away exactly what §8 measures). If real HMBC data proves
  unusable without it, that is a new requirement, not a Phase-103 fix.
- **A CLI escape hatch for `QcConfig`'s quaternary override** — needs an edit
  to the byte-frozen `qc.py`; documented as inherited behaviour instead
  (Phase-102 decision, unchanged here).
- **Webview rendering of a JCAMP ingest** (spectra + overlaid picks for visual
  QC) — rejected as the chemist-gate mechanism in D-07; the webview currently
  hangs off a CASE run manifest. Natural candidate for a later UX requirement.
- **NOESY consumption by the CASE constraint model** (JC-F1) — still deferred.
- **RECON-F1** (hmsIST/mddnmr in-lucy-ng NUS fallback) — carried from v10.0;
  note this dataset was itself produced by `mddnmr`.
- **Milestone-close bookkeeping** (`/gsd-complete-milestone`, infographic-deck
  refresh per CLAUDE.md) — follows the phase, is not part of it.

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` (score 0.6, generic
  keyword match) — CASE-solver / azulene regiochemistry defect, unrelated to
  JCAMP validation. **Not folded** (same determination as Phases 97–102).
- `2026-06-30-ranking-tests-hardfail-without-hosegen` (keyword match) —
  ranking-test-infra todo. **Not folded.**

</deferred>

---

*Phase: 103-end-to-end-validation-c20h32o2-jcamp*
*Context gathered: 2026-07-26*
