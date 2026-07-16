# Phase 99: Peak-Pick Bridge + QC Gate + CLI - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning

<domain>
## Phase Boundary

lucy-ng automatically peak-picks reconstructed 2D spectra into the **existing** `analysis/nmr_peaks/*.json` schema (via a direct in-memory `Spectrum2D` → existing `PeakPicker2D` call, mirroring `_perform_ranking()` — **not** a new picker), and **every** reconstruction passes a mandatory, headless, machine-readable **QC gate (PASS/PARTIAL/FAIL)** before the CASE pipeline is allowed to consume it. Delivers `nus/bridge.py` (peak-pick bridge), the QC gate module + its six checks, `lucy nus qc`, `lucy nus pipeline`, and the reconstruction-quality metadata embedding.

**In scope (PICK-01..03, QC-01..03):**
- Peak-pick bridge: `Spectrum2D` (from Phase 98 processed spectrum) → `PeakPicker2D.pick_peaks()` → `analysis/nmr_peaks/*.json` in the existing per-peak schema (HSQC edited-sign, HMBC, COSY).
- QC gate cross-checking every reconstructed correlation against the **trusted 1D shift data**: protonated-C HSQC coverage, quaternary-C exclusion, edited-sign self-consistency, COSY diagonal symmetry, ppm calibration, signal-to-ridge ratio → machine-readable PASS/PARTIAL/FAIL, no human in the loop.
- QC-02 discrimination: FAIL on the existing known-bad home-IST/t1-ridge peak lists, PASS on a clean reconstruction.
- QC-03 enforcement: on FAIL, no consumable peaks reach CASE (extends the v9.0 FIX-10 constraint-hardness guard to reconstruction-derived peaks).
- `lucy nus qc` (standalone) + `lucy nus pipeline` (full chain params→schedule→reconstruct→process→peak-pick→QC); all `lucy nus` subcommands support `--format json`.
- Reconstruction-quality metadata (backend, iterations, QC verdict) embedded in the peak JSON, replacing the blanket `"confidence": "low"`.

**Out of scope (later phases):** platform preflight matrix / Apple-Silicon `arch`/Rosetta / `csh` availability probe → **Phase 100 / PORT**; end-to-end §8-gate validation on C20H32O2 exp2/3/4 and `/lucy-ng:case C20H32O2` convergence → **Phase 100 / VAL**; hmsIST/mddnmr fallback backends → deferred. The Phase-97/98 reconstruction internals are **not** re-litigated here — this phase consumes the processed `Spectrum2D` they produce.

**Invariant carried forward from Phase 98:** `case.md` stays **untouched** (the "CASE pipeline unchanged" invariant). All enforcement lives at the pipeline/write boundary, not in the orchestrator. `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` are read/reused, not modified (except any additive metadata the bridge itself emits).
</domain>

<decisions>
## Implementation Decisions

### QC verdict semantics & PARTIAL handling (D-01, D-02)
- **D-01 — PARTIAL passes with a warning; only FAIL blocks.** Literal-to-QC-03: FAIL refuses CASE handoff. PARTIAL writes peaks and proceeds into CASE, but the `partial` verdict + the list of violated checks is surfaced in the peak-JSON metadata block so the CASE agents (nmr-chemist reading the peaks) can see it — **no `case.md` change required**. Rationale: the whole milestone exists to get CASE to convergence; a hard block on PARTIAL risks stopping every real-world reconstruction. A too-lax gate is guarded against by the critical-check FAIL tier (D-02) and the QC-02 discrimination floor.
- **D-02 — Verdict aggregation = critical vs. soft checks** (not a flat count, not per-check worst-of). Not all §8 criteria weigh equally.
  - **Critical checks (any violation ⇒ FAIL):** (1) quaternary-carbon exclusion — a known quaternary showing a 1-bond HSQC correlation is direct evidence of fabricated/ridge peaks (the worst failure mode); (2) ppm calibration — grossly off axes mis-place every correlation and mislead CASE; (3) signal-to-ridge ratio — dominant continuous t1-ridges are exactly the home-IST failure mode QC-02 must catch as FAIL; (4) HSQC coverage — user chose this critical too (see threshold note in D-04).
  - **Soft checks (violation ⇒ PARTIAL, clean ⇒ contributes to PASS):** edited-sign self-consistency; COSY diagonal symmetry.
  - **PASS** = no violations; **PARTIAL** = only soft violations; **FAIL** = any critical violation.

### QC 1D reference source & prot/quaternary classification (D-03)
- **D-03 — Trusted 1D reference comes from the existing 1D peak lists.** Read `analysis/nmr_peaks/13C_exp*.json` + `1H_exp1.json` (the project-wide "trusted 1D data", in contrast to the NUS 2D). No re-pick, no second parse pass, no second source of truth. In a NUS CASE run the 1D lists are picked first (1D is not NUS), so they exist by the time reconstruction + QC runs.
- **Protonated-vs-quaternary classification** (needed by both the HSQC-coverage AND quaternary-exclusion critical checks, and must **not** use the HSQC under test — that would be circular): prefer a picked **DEPT/edited** experiment if present; otherwise fall back to the existing `detection/` multiplicity/hybridisation statistics (which already run in CASE setup). This keeps the reference independent of the spectrum being graded.

### QC thresholds (D-04)
- **D-04 — Sensible defaults derived from §8 + the existing peak-list tolerances, centralised in a QC-config/constants object, overridable via CLI flags/config** for special cases (headless by default per QC-01, but adjustable). Seed tolerances: **13C ±0.5 ppm, 1H ±0.05 ppm** (the tolerances already documented in the current peak-list caveats).
- **Research/calibration assignment:** the exact numeric values for the **signal-to-ridge FAIL threshold** and the **HSQC-coverage FAIL floor** are NOT seriously fixable without data calibration. They are calibrated against the QC-02 discrimination anchor: the known-bad home-IST lists **must** land FAIL and a clean reconstruction **must** land PASS. HSQC-coverage-as-critical means the coverage check needs a FAIL floor low enough that a mostly-complete-but-clean reconstruction is not hard-blocked (a grossly-incomplete one is).

### Schema & metadata (D-05, D-06)
- **D-05 — Reconstruction metadata lives in a new top-level additive block** (e.g. `"reconstruction"` / `"nus_metadata"`) alongside `experiment`/`cross_peaks`, bundling backend, iterations, QC verdict, violated checks, thresholds used. The **existing per-peak keys stay structurally unchanged**; the CASE consumer ignores unknown top-level keys. This reconciles PICK-01 (per-peak schema stable) with PICK-03 (metadata embedded) without conflict. *(User delegated the exact placement — "Du entscheidest" — Claude chose top-level block.)*
- **D-06 — Per-peak `confidence` is derived from the QC verdict**: PASS → high/medium, PARTIAL → low; FAIL peaks never reach the consumable location at all (D-07), so no FAIL confidence is emitted to CASE. Honest — reflects the now-validated reconstruction quality — and uses exactly the new QC information. Replaces the blanket `"confidence": "low"`.
- **"byte-for-byte" clarification (for planner + verifier):** PICK-01's "byte-for-byte" is to be read as **structurally schema-identical for the per-peak keys the CASE pipeline parses**, NOT a literal byte-diff against the current files. The top-level `caveat` and per-peak `confidence` values necessarily change (the current `caveat` documents home-IST; the new one reflects the real backend/QC state, or is dropped — planner discretion). A verifier must NOT fail this phase on a literal byte comparison.

### QC wiring & CLI surface (D-07, D-08)
- **D-07 — Enforcement sits at the pipeline/write boundary: `lucy nus pipeline` writes productive `nmr_peaks/*.json` only when QC ∈ {PASS, PARTIAL}.** On FAIL: productive peaks are **not** written to the consumable location — instead written to a quarantine/diagnostic path (forensics, consistent with Phase-98 D-03 "keep intermediates") — and the command exits non-zero with a clear error. CASE then simply finds no consumable peaks. Primary barrier is fail-loud at the point of creation, so a fabricated cross-peak is never written where it could become a hard LSD constraint (FIX-10 spirit). **`case.md` is NOT touched** — no second orchestrator-side gate (rejected the defense-in-depth option specifically to preserve the untouched-`case.md` invariant).
- **D-08 — CLI: standalone `lucy nus qc <peaks-dir>` + `lucy nus pipeline <expdir>`.** `qc` must be independently runnable against arbitrary peak lists — that is exactly what QC-02 needs to assert FAIL on the known-bad lists and PASS on a clean one. `pipeline` orchestrates the full chain (params→schedule→reconstruct→process→peak-pick→QC) and calls the **same** qc code internally. A thin `lucy nus peak-pick` bridge stage may be exposed too (planner discretion). Every `lucy nus` subcommand supports `--format json`.

### Claude's Discretion
- Exact top-level metadata block name/shape (`reconstruction` vs `nus_metadata`), and the exact `caveat` regeneration/removal (D-05/D-06) — planner discretion within the stable-per-peak-schema constraint.
- Whether `lucy nus peak-pick` is a separately exposed subcommand or only an internal stage (D-08).
- The precise confidence mapping (PASS→high vs medium) and quarantine directory path/name (D-07) — planner discretion.
- The exact numeric signal-to-ridge and HSQC-coverage-floor defaults — data-calibrated by research against the QC-02 anchor (D-04).
- `nus/bridge.py` API surface and its split from the QC module — planner discretion within the `_perform_ranking()`-mirroring pattern.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone planning
- `.planning/REQUIREMENTS.md` — PICK-01..03, QC-01..03 (the six requirements this phase closes); FIX-10 lineage (constraint-hardness guard being extended).
- `.planning/ROADMAP.md` § Phase 99 — goal + 5 success criteria; § Phase 100 for the scope boundary (platform preflight + end-to-end validation are NOT this phase).
- `.planning/research/SUMMARY.md` — the crux **fabricated-cross-peak** risk this QC gate is the last line of defense against; four-phase shape (Phase 3 = this phase).

### Architecture & pitfalls
- `.planning/research/ARCHITECTURE.md` — `nus/bridge.py` (peak-pick bridge), the "CASE pipeline unchanged" invariant (empty diff to `detection/`/`fragments/`/`lsd/`/`ranking/`/`cli/pick.py`/`case.md`), `_perform_ranking()` mirroring pattern.
- `.planning/research/PITFALLS.md` — fabricated/over-under-converged peaks (the exact thing QC-01 checks); ppm-axis-vs-1D-reference; silent auto-phase failure (only the QC gate might catch it).
- `.planning/phases/98-reconstruction-processing/98-CONTEXT.md` — upstream decisions (D-01 per-stage subprocess, D-02 deterministic phase, D-03 `analysis/nus_recon/<expN>/` intermediates, D-04 test strategy); the processed `Spectrum2D` this phase peak-picks is its output.

### Task brief + data (QC gate criteria live here)
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` **§8** (verification / what a good reconstruction looks like — the literal QC-01 check definitions: HSQC ~17 protonated C each with exactly one (CH2: two) correlation, the 5 quaternaries 142.0/135.86/79.35/36.23/37.86 with NO 1-bond correlation, clean edited signs; HMBC no t1-ridges, gem-dimethyl sharp; COSY a real aliphatic network not just the OH-ridge at 5.32; signal-to-ridge better than the current home-IST lists) and **§10** (ground-truth 1D shifts).
- **The known-bad QC-02 FAIL reference already exists:** `.../C20H32O2/analysis/nmr_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2}.json` — their own `caveat` field documents "reconstructed by home-grown per-column IST. Residual t1 ridges present ... BEST-EFFORT / LOW confidence" and the 13C ±0.5 / 1H ±0.05 tolerances. These are the regression-floor FAIL case.
- The trusted **1D reference lists** (D-03 source): `.../C20H32O2/analysis/nmr_peaks/13C_exp7_wide.json`, `13C_exp6_narrow.json`, `1H_exp1.json`.

### Existing code precedents to follow
- `src/lucy_ng/processing/peak_picker_2d.py` — `PeakPicker2D.pick_peaks(spectrum, threshold=…, use_snr=…, snr_floor=…)`; `estimate_noise`, `get_peak_info` — the bridge calls this directly, no new picker.
- `src/lucy_ng/cli/pick.py` — how HSQC/HMBC/COSY are currently picked and serialized (`pick_hsqc`/`pick_hmbc`/`pick_2d`, edited-sign detection `_detect_multiplicity_edited`, the exact JSON dict shape). The bridge must emit the same per-peak keys.
- `src/lucy_ng/cli/lsd.py` / `cli/pylsd.py` — `_perform_ranking()` (the "build model in memory → direct Python call to existing subsystem" pattern PICK-01 mirrors).
- `src/lucy_ng/models/spectrum.py::Spectrum2D` — the in-memory model the bridge constructs from the Phase-98 processed spectrum.
- `src/lucy_ng/nus/runner.py` + `nus/postprocess.py` — Phase-98 `NusRunner.reconstruct()` produces the processed spectrum this phase consumes; `pipeline` extends the runner.
- `src/lucy_ng/cli/nus.py` — the import-safe `lucy nus` group; add `qc`, `pipeline` (and optionally `peak-pick`) commands here.
- `src/lucy_ng/detection/models.py` + `cli/detect.py` — FIX-10 references (constraint-hardness guard being extended) and the multiplicity/hybridisation classification reused for prot/quaternary fallback (D-03).
- `src/lucy_ng/cli/webview.py` — import-safe CLI + `_require_*_extra()` pattern if any new optional dep appears.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PeakPicker2D.pick_peaks()` — full 2D picker with SNR/threshold/edited-sign support; the bridge calls it directly (PICK-01), no reimplementation.
- `Spectrum2D` (`models/spectrum.py`) — built in memory from the Phase-98 processed spectrum; the bridge's input.
- `cli/pick.py` — canonical per-peak JSON shape (`c13_ppm, h1_ppm, edited_sign, multiplicity_hint, confidence, note`) + top-level (`experiment, caveat, n_cross_peaks, cross_peaks[]`); reuse the shape, change only `caveat`/`confidence` + add the top-level metadata block.
- `detection/` multiplicity/hybridisation stats — prot/quaternary fallback classification (D-03).
- `nus/runner.py` — orchestration the `pipeline` command extends.

### Established Patterns
- CLI groups in `cli/main.py` via `add_command`; each subcommand `--format json`. `qc`/`pipeline` join the existing import-safe `lucy nus` group.
- Pydantic v2 models in `models/`; a QC-report / verdict model joins `models/nus.py`.
- Optional heavy deps behind `[nus]` extra + `_require_*` guard (webview precedent) if any new pip dep appears.

### Integration Points
- Bridge: processed `Spectrum2D` → `PeakPicker2D.pick_peaks()` → `analysis/nmr_peaks/*.json`.
- QC gate: reads reconstructed peak lists + the trusted 1D lists (D-03) → PASS/PARTIAL/FAIL report + verdict.
- `pipeline`: `NusRunner` chain → bridge → QC → conditional write (D-07).
- Enforcement boundary: pipeline write step (D-07). **No touch** to `case.md` — the invariant.
</code_context>

<specifics>
## Specific Ideas

- **The QC gate is the milestone's last line of defense against fabricated cross-peaks** becoming hard LSD constraints (research crux + FIX-10). The critical-check FAIL tier (D-02) is what makes PARTIAL-passes safe.
- **QC-02 is the calibration anchor, not just a test:** the exact signal-to-ridge and coverage-floor defaults (D-04) are tuned so the existing home-IST lists FAIL and a clean reconstruction PASSes. The known-bad lists are already on disk (see canonical_refs) — no fixture fabrication needed.
- **The §8 guide is the authoritative source for the six check definitions** — the 5 named quaternaries, the ~17 protonated carbons, the OH-ridge-at-5.32 COSY smell test, "signal-to-ridge better than the current home-IST lists". Implement the checks against §8, not against invented criteria.
- **prot/quaternary classification must be independent of the HSQC under test** (D-03) — otherwise the coverage and quaternary-exclusion checks are circular and self-confirming.
</specifics>

<deferred>
## Deferred Ideas

- Platform preflight matrix (Apple-Silicon `arch`/Rosetta, `csh`/`tcsh`), portability doc → **Phase 100 / PORT**.
- End-to-end §8-gate validation on C20H32O2 exp2/3/4 and `/lucy-ng:case C20H32O2` convergence → **Phase 100 / VAL**.
- Per-peak reconstruction-confidence scoring feeding LSD constraint weighting directly (RECONUX-F1); webview rendering of reconstructed 2D + QC report (RECONUX-F2) → deferred (v1.x).
- Defense-in-depth second QC gate inside `case.md`/DA — **explicitly rejected** for this phase to preserve the untouched-`case.md` invariant; single pipeline-boundary barrier (D-07) instead.
- Combined QC+SNR per-peak confidence — deferred; per-peak confidence is QC-verdict-derived only (D-06).

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` (score 0.6, generic keyword match) — CASE-solver / azulene regiochemistry defect, unrelated to peak-pick/QC. **Not folded** (same call as Phases 97/98).
- `2026-06-30-ranking-tests-hardfail-without-hosegen` (score 0.4, keyword match) — hosegen ranking-test-infra todo, unrelated to this phase. **Not folded.**

</deferred>

---

*Phase: 99-peak-pick-bridge-qc-gate-cli*
*Context gathered: 2026-07-14*
