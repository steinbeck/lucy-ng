# Feature Research

**Domain:** Automated NUS (non-uniform-sampling) 2D NMR reconstruction pipeline, embedded in an AI-agent CASE toolchain (lucy-ng v10.0)
**Researched:** 2026-07-12
**Confidence:** MEDIUM-HIGH (pipeline architecture and FnMODE/schedule mechanics are well-established NMR methodology, HIGH confidence via multiple independent official sources; specific backend behaviour for lucy-ng's exact experiments is MEDIUM — verified via official docs/search, not hands-on tested in this research pass)

## Pipeline Chain Reference (backbone for the feature tables below)

This is the concrete, ordered chain every NUS 2D experiment must pass through. Each step is tagged **[US]** (backend-agnostic, our Python code) or **[BE]** (delegated to whichever reconstruction backend is chosen — NMRPipe+SMILE, NMRFx (IST/NESTA), or hmsIST/mddnmr are the three real options identified; final backend selection is a STACK.md decision, not decided here).

1. **[US] Read Bruker raw data** — `ser`, `nuslist`, `acqus`/`acqu2s` via nmrglue (`nmrglue.bruker.read`). lucy-ng already has a `BrukerReader`; this step extends it to NUS metadata (NusSEED, nuslist path, sampled-point count) rather than replacing it.
2. **[US] Parse acquisition parameters needed for conversion** — SFO1, SW_h, TD (per dim), FnMODE (numeric code, e.g. 1=QF, 6=echo-antiecho), DECIM/GRPDLY (digital-filter group delay), byte order, carrier (O1/OBS), number of hypercomplex components per t1 point. These map directly onto what `bruk2pipe`/`fid.com` (NMRPipe path) or NMRFx's Bruker importer need — **[US]** because lucy-ng must derive them itself to drive any backend headlessly (no GUI wizard to read `acqus` for you).
3. **[BE] Bruker → backend format conversion** — `bruk2pipe` (NMRPipe) or NMRFx's native Bruker reader. Produces a converted, still-sparse FID matrix.
4. **[BE or US] NUS expansion** — zero-fill the sparse FID onto the full nominal t1 grid at the schedule's recorded indices (`nusExpand.tcl` in the NMRPipe path; built into NMRFx's IST/NESTA operators). Conceptually simple (scatter sampled rows into a zero matrix) — could be reimplemented in **[US]** Python/numpy if backend interop becomes a friction point, but there is no value in reinventing it if the backend already does it correctly.
5. **[BE] Indirect-dimension reconstruction** — SMILE / IST / NESTA / MDD, operating on the full (expanded) t1 grid, informed by the sampling mask. This is the algorithmic core and the piece we are explicitly NOT reimplementing (see Anti-Features).
6. **[BE] Direct-dimension (F2) processing first** — apodization, zero-fill, FT, phase correction on F2 *before* indirect reconstruction — SMILE's own docs state the input must already have the direct dimension processed. This ordering constraint is backend-mandated but must be enforced by **[US]** pipeline orchestration code (get the sequencing right, don't let a script silently skip it).
7. **[BE] Indirect-dimension processing** — apodization, ZF, FT, phase correction (F1), applied after reconstruction.
8. **[US or BE] Baseline correction** — either backend-native (NMRPipe `POLY`/`BASE`) or done afterward in nmrglue/numpy on the read-back spectrum; not reconstruction-critical, can be **[US]**.
9. **[US] Peak picking → JSON** — **do not** use the backend's native peak picker. lucy-ng already has a proven nmrglue-based 2D peak-picking stack (DEPT-guided HSQC, HMBC-guided, COSY) that reads processed spectra directly. NMRPipe-format 2D files are natively readable by `nmrglue.fileio.pipe` (well-established, textbook interop) — this makes the peak-picking stage genuinely backend-agnostic regardless of which reconstruction tool produced the frequency-domain data, and preserves the existing JSON schema (see below) instead of forcing a rewrite around a new tool's output format.
10. **[US] Reconstruction quality auto-assessment** — no human in the loop; see Differentiators.

## Feature Landscape

### Table Stakes (Users Expect These)

Non-negotiable for a v10.0 that actually replaces the ad-hoc per-column IST. Missing any of these reproduces the exact failure the milestone exists to fix.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Real CS/IST/SMILE reconstruction of the indirect (t1) dimension | The whole milestone exists because the home-grown per-column IST leaves t1 ridges that defeat LSD constraint pruning — this is the core deliverable, not optional | HIGH | Delegate to an established backend (SMILE/hmsIST/NESTA); do not write a new solver |
| Correct Bruker→backend schedule conversion (nuslist indexing) | Wrong schedule alignment silently produces a plausible-looking but wrong reconstruction — worse than no reconstruction because it looks confident | MEDIUM | `nuslist` is 0-based indices into the full t1 grid; NMRPipe processing files are conventionally 1-based — conversion tooling (`nusExpand.tcl`/NMRFx importer) handles this, but lucy-ng's own schedule-derivation code must not double-convert or off-by-one it |
| FnMODE-aware processing: echo-antiecho (HSQC/HMBC) vs QF (COSY) | These are fundamentally different quadrature-detection schemes; treating them identically produces either lost phase information (EA data run as QF) or garbage frequency discrimination (QF data run as EA) | HIGH | See dedicated FnMODE section below — this is the single most likely place to introduce a silent correctness bug |
| Direct-dimension-first processing order enforced | SMILE (and IST generally) requires F2 already apodized/ZF'd/FT'd/phased before indirect reconstruction runs; get the order wrong and reconstruction runs on the wrong domain | LOW (once known) | Purely an orchestration/sequencing bug risk — encode as a hard pipeline gate, not a convention to remember |
| Apodization + zero-fill + FT + phase correction + baseline for both dimensions | Standard 2D processing; without it the reconstructed FID never becomes a usable frequency-domain spectrum | LOW | Well-trodden ground — nmrglue/NMRPipe both provide this natively |
| Peak picking → JSON preserving the existing schema | CASE (`/lucy-ng:case`) and the webview already consume `analysis/nmr_peaks/{HSQC,HMBC,COSY}_exp*.json`; a schema break cascades into every downstream consumer | LOW-MEDIUM | Reuse existing lucy-ng picker code paths (`lucy pick hsqc` etc.) against the newly reconstructed spectra rather than inventing new output |
| Edited-sign / multiplicity for HSQC (CH/CH3 positive vs CH2 negative) | v9.1 MULT work (`multiplicity_edited`) already depends on this; a NUS-reconstructed HSQC that loses edited-sign fidelity regresses a shipped feature | MEDIUM | Edited HSQC sign comes from the F2 (direct ¹H) processing pathway, largely orthogonal to the NUS reconstruction of F1 — but must be verified post-reconstruction, not assumed preserved |
| Handle both 25% (HSQC/COSY) and 33% (HMBC) sampling densities from the same pipeline | The three real experiments span two densities; a pipeline hard-coded to one density is not reusable | LOW | Density only affects the schedule/mask size and reconstruction iteration budget, not the algorithm |
| Reusable `lucy` CLI step, not a one-off script for C20H32O2 | PROJECT.md explicitly requires "usable by any NUS CASE run, not just C20H32O2" | MEDIUM | Needs a general Bruker-metadata-driven schedule/FnMODE dispatcher, not per-experiment hard-coded parameters |
| Documented cross-platform behaviour (macOS/Linux/Windows) | Explicit milestone constraint; PROJECT.md accepts documented gaps but not silent ones | MEDIUM-HIGH | NMRPipe has no native Windows support (VM or unofficial WSL only, confirmed via official install docs); this alone may decide the backend — see Differentiators |

### Differentiators (Competitive Advantage)

Features that make this pipeline meaningfully better than "get SMILE running once" — align with lucy-ng's Core Value (autonomous, no-human CASE).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Fully automatic, no-GUI quality auto-assessment of the reconstruction | This milestone's entire premise is a human ("Chris") no longer manually judging spectra in TopSpin; an agent needs a numeric/structural verdict it can act on | MEDIUM-HIGH | Concrete, implementable metrics (see below) rather than "looks clean" — this is the piece most likely to need dedicated phase-level research |
| Backend chosen for headless + cross-platform scriptability over raw reconstruction fidelity | A backend that reconstructs beautifully but only runs inside a GUI or a Linux VM fails the "fully automatic, no GUI" hard constraint regardless of spectral quality | MEDIUM | NMRFx (pure Java, Linux/macOS/Windows native, Python-scripted, headless-executable, built-in IST/NESTA) is architecturally the strongest fit for the portability constraint; NMRPipe+SMILE is the most literature-validated algorithm but Linux/macOS-only without VM/WSL — this tradeoff belongs in STACK.md but directly shapes which pipeline features are even reachable |
| Backend-agnostic peak picking via nmrglue interop | Decouples "which reconstruction tool won" from "how do we get peaks" — NMRPipe's `.ft2` output format is natively readable by `nmrglue.fileio.pipe`, so lucy-ng's existing, already-validated peak pickers (DEPT-guided HSQC, HMBC-guided, edited-sign detection) work unmodified against reconstructed spectra from any backend that can emit NMRPipe-compatible frequency-domain data | LOW-MEDIUM (given the picker code already exists) | Avoids a second, backend-specific peak-picking implementation and a second output schema to maintain |
| Reconstruction-quality metadata embedded in the peak JSON (replacing the current blanket "low confidence" caveat) | Current files carry a hard-coded `"confidence": "low"` on every single peak because the home-IST approximation offers no better granularity; a real reconstruction can report per-peak or per-spectrum confidence grounded in an actual metric | LOW | Direct schema evolution of the existing `caveat`/`confidence`/`note` fields — cheap, high signal value for the CASE agent team's devils-advocate gate |
| Magnitude-mode-aware COSY handling (QF ≠ phase-sensitive) | `cosygpmfppqf` is a magnitude-mode pulse sequence; naively phase-correcting F1 as if it were echo-antiecho/States data produces meaningless phase artifacts. Recognizing QF and routing through magnitude-mode reconstruction/display (or the "virtual echo" trick where applicable) is a genuine correctness differentiator over a one-size-fits-all pipeline | MEDIUM | See FnMODE section — this is domain expertise, not a library feature |
| Configurable reconstruction knobs exposed through `lucy`, not buried in a hand-edited backend script | Iteration count, threshold, and virtual-echo toggles materially change artifact levels at 25-33% sampling; exposing them as CLI flags (with sane experiment-type defaults) lets a future CASE run retry with different settings without hand-editing tcsh/Java scripts | LOW-MEDIUM | Table-stakes-adjacent; promoted to differentiator because "backend script buried in a data directory" is exactly the failure mode the milestone is escaping |
| Portability matrix documentation (what runs where, why not, workaround) | Explicit PROJECT.md ask; turns "silently doesn't work on Windows" into an auditable, plannable gap | LOW | Documentation feature, not code — cheap, high value for future contributors/users |

### Anti-Features (Commonly Requested, Often Problematic)

Features that look reasonable for this milestone but would blow the scope, the "no GUI" constraint, or duplicate mature prior art.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Writing a new from-scratch CS/IST/MDD solver in Python | "Keep it pure-Python, no external NMR tooling dependency" | Reconstruction quality (artifact suppression at 25-33% sparse sampling) is the entire point of this milestone; SMILE/hmsIST/NESTA/MDD represent years of published, peer-reviewed algorithm tuning (lineshape enhancement, virtual-echo tricks, Poisson-gap-aware thresholding) that a first Python implementation will not match, and a subtly-wrong home-grown solver is exactly the failure this milestone exists to fix | Delegate reconstruction to an established backend; keep only conversion/orchestration/QA in-house |
| TopSpin GUI-driven reconstruction (Alternative A in the GUIDE) | Simplest path for a human, native Bruker support, CS/MDD built in, zero conversion friction | Explicitly GUI-driven; "fully automatic, no GUI" is a hard project constraint, and TopSpin AU/Python macro automation is undocumented/unreliable for unattended headless CI-style runs | Use it only as a manual cross-check/validation tool during development, never as the production pipeline path |
| Deep-learning-based NUS reconstruction (recent literature trend) | Papers show DNN reconstruction competitive with IST/SMILE in reconstruction time | Adds a large, potentially GPU-dependent, poorly cross-platform-portable dependency (model weights, framework version pinning) for a milestone whose primary constraint is broad, documented cross-platform portability on modest hardware; also far less mature/battle-tested for small-molecule 2D natural-product spectra specifically (most validation is biomolecular NMR) | Stick with IST/SMILE/NESTA; revisit DNN reconstruction only if a future milestone specifically needs it and portability constraints relax |
| 3D/4D NUS support | "While we're building this, generalize to 3D/4D too" | No 3D/4D experiments exist or are planned for lucy-ng's small-molecule CASE workflow (2D HSQC/HMBC/COSY is the full target set per PROJECT.md); 3D adds real complexity (schedule geometry, memory, processing time) with zero current consumer | Design the schedule/FnMODE abstraction cleanly enough that 3D could be added later, but do not implement or test it now |
| Non-Bruker vendor NUS support (Varian/Agilent, JEOL) | "Other users have other vendors' NUS data" | Already explicitly out of scope for lucy-ng generally ("Bruker only for v1", still true at v9.x); NUS schedule/metadata formats differ meaningfully across vendors | Keep Bruker-only; document the vendor assumption clearly in the new pipeline code |
| Maximum-entropy (MaxEnt) reconstruction as a fourth backend option | MaxEnt is a legitimate, well-published alternative (e.g., Rowland NMR Toolkit) | Adds a fourth reconstruction paradigm to evaluate/maintain when IST/SMILE/NESTA already cover the accuracy/portability tradeoff space needed here; MaxEnt has its own convergence/parameter-tuning idiosyncrasies that would need separate research | Evaluate only if the chosen IST/SMILE/NESTA backend demonstrably fails the §8 verification criteria on all three real experiments |
| A generic "any NUS pattern, any nucleus pair" abstraction layer up front | Engineering instinct to generalize before the three concrete experiments are solved | Speculative generality before the concrete COSY/HSQC/HMBC cases are proven adds design risk and delays validation against the one dataset (C20H32O2) that actually gates milestone completion | Build concretely for COSY (QF)/HSQC+HMBC (echo-antiecho) first; generalize in a later milestone once a second real NUS dataset exists |

## FnMODE / Quadrature Handling (echo-antiecho vs QF) — Detail

This is the section most likely to hide a silent correctness bug, so it is expanded beyond the table.

**QF (FnMODE=1) — COSY (`cosygpmfppqf`):**
- Single quadrature detection per t1 increment: only one (real) data point type is collected per sampled t1 index, not a hypercomplex pair.
- `cosygpmfppqf` is a magnitude-mode COSY pulse sequence — phase-sensitive frequency discrimination in F1 is not attempted; the spectrum is typically displayed/processed in magnitude mode after F1 FT.
- NUS + magnitude-mode QF COSY is an established combination in the literature (CS-IST applied to magnitude-mode COSY45 is explicitly reported as working, per Systematic Evaluation of NUS Parameters in 2D NMR, PMC5844889). Do **not** attempt echo-antiecho-style phase reconstruction on this data — it has no antiecho component to reconstruct.
- Practical implication for the sampling schedule: each `nuslist` entry maps to exactly one recorded FID row for COSY, unlike echo-antiecho experiments (see below).

**Echo-Antiecho (FnMODE=6) — HSQC (`hsqcedetgpsp.3`), HMBC (`hmbcetgpl3nd`):**
- Gradient-selected hypercomplex quadrature detection: for each sampled t1 index, both the "echo" (P-type coherence) and "antiecho" (N-type coherence) pathways are separately acquired and stored. These two FIDs per t1 point are combined (add/subtract) during processing to synthesize the two orthogonal (cosine/sine-like) components needed for phase-sensitive F1 FT — functionally analogous to States quadrature detection but achieved via gradient selection instead of receiver-phase cycling.
- Consequence for schedule bookkeeping: a `nuslist` with N sampled indices does **not** mean N raw FID rows in `ser` for echo-antiecho experiments — each sampled index typically corresponds to 2 (echo+antiecho) recorded blocks. Conversion tooling (`bruk2pipe`/NMRFx's Bruker importer) must be told the correct number of hypercomplex components per point; getting this wrong desynchronizes the schedule from the data without raising an obvious error (silent misalignment, not a crash) — this is exactly the kind of bug a human GUI operator would catch visually (garbled spectrum) but an unattended pipeline needs an explicit check for.
- Reconstruction (SMILE/IST/NESTA) operates on the recombined complex time series per sampled t1 index, using the schedule mask to identify which indices in the full grid have real data vs need reconstruction — the echo/antiecho recombination must happen *before* the sparse-to-full expansion, not after.
- Phasing in F1 for echo-antiecho data uses the standard phase-sensitive 2D phasing (zero/first-order) once reconstruction has produced a complete, gridded F1 dimension — no phase-sensitive information is available point-by-point during the sparse-acquisition stage itself.

**Cross-cutting note:** the `nuslist` 0-based index always refers to the t1 *increment number*, never a raw byte or FID-row offset — the mapping from index to actual `ser` byte offset depends on the number of hypercomplex components (1 for QF, 2 for echo-antiecho, up to 4 for States-TPPI) and the number of dummy/interleaved scans, and this mapping is exactly what `bruk2pipe`/NMRFx's importer is responsible for getting right. lucy-ng's own metadata-parsing code (step 2 in the Pipeline Chain Reference) needs to derive/verify this component count from `FnMODE` + pulse-program name rather than hard-coding it per experiment, to stay reusable across future NUS datasets.

## Reconstruction Quality Knobs

| Knob | What it controls | 25% (HSQC/COSY) vs 33% (HMBC) implication |
|------|-------------------|--------------------------------------------|
| Iteration count | How many IST/SMILE threshold-subtract-reconstruct cycles run; too few leaves residual ridges, too many risks over-fitting noise into false peaks | Sparser data (25%) generally needs more iterations / more conservative thresholding to converge cleanly than 33% |
| Threshold (soft-threshold level, often adaptive per iteration) | Determines what counts as "signal" to extract at each IST iteration vs what's left for the next pass | Lower initial threshold appropriate for lower sampling density to avoid discarding real signal already weakened by sparse sampling |
| Virtual-echo construction | Doubles the effective time-domain signal via time-reversal/conjugate-symmetry tricks for hypercomplex (States-type) data, improving SNR and line shape in reconstruction — applicable to echo-antiecho HSQC/HMBC, not to magnitude-mode QF COSY | Most beneficial exactly where it's algorithmically valid: HSQC/HMBC (echo-antiecho); not applicable/needed for the QF COSY path |
| Direct-dimension-processed-first requirement | SMILE (and IST generally) explicitly requires F2 apodized/ZF'd/FT'd/phased before F1 reconstruction runs | Same requirement regardless of sampling density — a pipeline-ordering constraint, not a density-tuned knob |
| Sampling density itself (25% vs 33%) | Not a "knob" to tune but a fixed acquisition fact per experiment that reconstruction parameters must adapt to | HMBC's 33% (116/~350 points) is comparatively less sparse than HSQC/COSY's 25% (50/~200, 188/~752) — expect HMBC to reconstruct with fewer artifacts at equal iteration/threshold settings, all else equal |

## Peak-Picking JSON Schema (from the real, currently-shipped files — preserve this contract)

Read directly from `analysis/nmr_peaks/*.json` (home-IST-generated, to be replaced by real-reconstruction output using the **same schema**):

**Common structure:** top-level `experiment` (string, pulse-program-identified), `caveat` (string — currently states the home-IST provenance; must be rewritten to describe the real reconstruction backend/settings instead of removed), `n_cross_peaks` (int), `cross_peaks` (array).

**HSQC (`HSQC_exp3.json`):** each cross-peak has `c13_ppm`, `h1_ppm`, `edited_sign` (`"positive(CH_or_CH3)"` / `"negative(CH2)"`), `multiplicity_hint`, `confidence`, `note`. This directly feeds v9.1's `multiplicity_edited` machinery — edited-sign fidelity through reconstruction is a hard requirement, not cosmetic.

**HMBC (`HMBC_exp4.json`):** each cross-peak has `c13_ppm`, `h1_ppm`, `rel_intensity`, `rank_in_carbon` (intensity rank among cross-peaks sharing that carbon — used to prioritize likely 2J/3J assignments), `suspected_1J_artifact` (bool — flags HSQC-leakage into HMBC), `confidence`, `note`.

**COSY (`COSY_exp2.json`):** each cross-peak has `h1a_ppm`, `h1b_ppm`, `rel_intensity`, `confidence`, `note`.

**1D reference (`13C_exp6_narrow.json` etc., for comparison/consistency-checking):** `count`, `noise_sigma`, `negative_detected`, `snr_floor_used`, `peaks: [{ppm, intensity, snr}]` — this SNR-floor design (already validated, v9.0 FIX-08/FIX-12) is a good template for what "confidence" should mean once real reconstruction quality metrics exist for the 2D peaks, replacing the current blanket `"confidence": "low"`.

**Roadmap implication:** the JSON *shape* should not change — only the *provenance* of `caveat`/`confidence`/`note`, and ideally the addition of a real per-spectrum (or per-peak) quality score once auto-assessment (next section) exists. This keeps CASE, the webview tables/spectra routers, and the devils-advocate agent's existing consumers of these files unaffected.

## Automatic Quality Assessment ("good" reconstruction, no human) — §8 GUIDE Criteria Operationalized

The GUIDE's §8 verification criteria are currently written for a human eyeballing spectra in TopSpin. For a no-GUI milestone these need concrete, computable analogues:

| GUIDE §8 criterion (human) | Computable analogue (agent-checkable) | Complexity |
|---|---|---|
| HSQC: exactly one (or two diastereotopic) cross-peak per protonated ¹³C from the 1D reference; 5 known quaternaries show none | Cross-reference reconstructed HSQC cross-peak carbon shifts against the already-picked, high-confidence 1D `13C_exp6_narrow.json`/`13C_exp7_wide.json` peak list (±0.5 ppm tolerance, per existing convention); count matches vs the known ~17 protonated / 5 quaternary split; flag as PASS/FAIL/PARTIAL | LOW-MEDIUM — pure comparison logic against data lucy-ng already has |
| HSQC: edited-sign clean and consistent | Per-carbon, check all cross-peaks sharing that `c13_ppm` report the same `edited_sign`; flag inconsistency (a genuine reconstruction-artifact signature, not chemistry) | LOW |
| HMBC: defined 2-3J cross-peaks, no continuous t1 ridges | Ridge detection: in the reconstructed 2D matrix (not just the picked peak list), scan F1 (indirect) columns for anomalously high peak density / near-constant intensity across the full F2 range at a fixed F1 shift — a hallmark IST/SMILE artifact signature distinct from real, spectrally localized cross-peaks | MEDIUM — needs access to the processed 2D matrix, not just picked peaks; genuinely new code |
| HMBC: gem-dimethyl methyls (~0.96/0.99 ppm) show sharp correlations | Targeted spot-check against known-good 1H shifts from the 1D reference — same comparison-logic pattern as the HSQC check | LOW |
| COSY: a real aliphatic H-H coupling network, not just the OH ridge at 5.32 | Count distinct `h1b_ppm` partners across the full aliphatic 1H range (not clustered near the OH peak); a pipeline that reproduces the current 7-cross-peaks-all-off-one-proton pattern should self-flag as still-failing | LOW — directly diagnostic of the exact failure mode this milestone fixes |
| "Signal-to-ridge ratio markedly better than the existing home-IST files" | Direct, computable regression-test comparison: for each spectrum, define a numeric artifact/ridge score (e.g., ratio of picked genuine-peak count to total ridge-like high-density F1 rows) against the current shipped `analysis/nmr_peaks/*.json` as a documented floor to beat | LOW — cheap to implement, high value as an objective go/no-go gate before handing control back to CASE |

**Backend-provided vs our-code split for quality assessment:** none of the above should depend on backend-specific diagnostics (NMRPipe and NMRFx do not expose a shared "artifact score" concept) — this entire layer is **[US]**, operating purely on the reconstructed frequency-domain matrix and picked-peak JSON, keeping it backend-agnostic and reusable if the backend choice changes later.

## Feature Dependencies

```
Bruker ser+nuslist+acqus/acqu2s reading [US]
    └──requires──> Schedule/FnMODE metadata derivation [US]
                       └──requires──> Bruker→backend conversion [BE]
                                          └──requires──> NUS expansion (zero-fill onto full grid) [BE]
                                                             └──requires──> Direct-dimension (F2) processed first [BE, ordering enforced US]
                                                                                └──requires──> Indirect-dimension reconstruction (IST/SMILE/NESTA) [BE]
                                                                                                   └──requires──> Indirect-dim processing (apod/ZF/FT/phase) [BE]
                                                                                                                      └──requires──> Baseline correction [US or BE]
                                                                                                                                         └──requires──> Peak picking → JSON (existing schema) [US]
                                                                                                                                                            └──requires──> Auto quality assessment [US]
                                                                                                                                                                               └──enables──> CASE run resumption (/lucy-ng:case)

FnMODE-correct handling (echo-antiecho vs QF) ──enhances──> every stage from conversion through phasing
Cross-platform backend choice ──conflicts──> maximal reconstruction fidelity (NMRPipe+SMILE is best-validated but Linux/macOS-only without VM/WSL)
Reusable `lucy` CLI step ──requires──> metadata-driven (not hard-coded) FnMODE/schedule dispatch
```

### Dependency Notes

- **Auto quality assessment requires peak picking (JSON) AND the raw reconstructed matrix**, not peak picking alone — the ridge-detection check specifically needs the 2D frequency-domain data, so the pipeline must retain/expose the processed spectrum, not discard it once peaks are picked.
- **FnMODE-correct handling enhances every downstream stage**, not just conversion — a QF/echo-antiecho mix-up at the schedule-derivation stage propagates silently through expansion, reconstruction, and phasing, producing plausible-looking but chemically wrong cross-peaks that a naive quality check (peak *count* only) would not catch. This is why the auto-assessment layer needs shift-based cross-referencing against the trusted 1D data, not just internal self-consistency.
- **Cross-platform portability conflicts with reconstruction fidelity** in the specific sense that the most literature-validated, artifact-suppressing backend (NMRPipe+SMILE) is the least portable (no native Windows). This tradeoff should be resolved explicitly in STACK.md/roadmap phase 1, not discovered mid-implementation.

## MVP Definition

### Launch With (v1 / this milestone)

- [ ] Bruker metadata + nuslist + FnMODE parsing, reusable across experiments — foundation everything else depends on
- [ ] One reconstruction backend wired end-to-end (not three) — get COSY (QF) + HSQC/HMBC (echo-antiecho) working correctly on one backend before evaluating alternatives
- [ ] Correct schedule conversion with explicit hypercomplex-component-count handling (the QF-vs-echo-antiecho silent-desync risk called out above)
- [ ] Full processing chain (apod/ZF/FT/phase/baseline) for both dimensions
- [ ] Peak picking into the existing JSON schema, reusing current lucy-ng picker code against reconstructed spectra
- [ ] The five §8-derived auto-assessment checks (table above) as an explicit PASS/FAIL/PARTIAL gate before CASE resumption
- [ ] Documented portability matrix (even if v1 only fully validates macOS)

### Add After Validation (v1.x)

- [ ] Second backend as a documented fallback/comparison path if the primary backend fails the §8-derived gate on any of the three real experiments (GUIDE explicitly names hmsIST/mddnmr as fallbacks)
- [ ] Configurable reconstruction knobs (iteration count, threshold, virtual-echo toggle) exposed as `lucy` CLI flags rather than fixed defaults
- [ ] Linux/Windows portability validation beyond the primary macOS dev platform

### Future Consideration (v2+)

- [ ] Generalized schedule/FnMODE abstraction for experiment types beyond COSY/HSQC/HMBC (e.g. TOCSY, NOESY-NUS, 1,1-ADEQUATE) — defer until a second real NUS dataset exists to design against
- [ ] 3D/4D NUS support — no current consumer
- [ ] Per-peak (not just per-spectrum) reconstruction confidence scoring feeding directly into LSD constraint weighting — valuable but depends on the simpler per-spectrum gate proving out first

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Real backend reconstruction (replace home-IST) | HIGH | HIGH | P1 |
| Correct FnMODE (echo-antiecho vs QF) handling | HIGH | MEDIUM | P1 |
| Schedule conversion correctness (0-based, hypercomplex-aware) | HIGH | MEDIUM | P1 |
| Peak picking into existing JSON schema | HIGH | LOW-MEDIUM | P1 |
| Auto quality assessment (§8 operationalized) | HIGH | MEDIUM-HIGH | P1 |
| Reusable metadata-driven `lucy` CLI step | HIGH | MEDIUM | P1 |
| Cross-platform portability matrix (documented gaps) | MEDIUM | LOW | P1 (docs) / P2 (full Windows validation) |
| Configurable reconstruction knobs via CLI | MEDIUM | LOW-MEDIUM | P2 |
| Second backend as fallback | MEDIUM | HIGH | P2 |
| Per-peak confidence scoring feeding LSD | MEDIUM | HIGH | P3 |
| 3D/4D / other experiment types | LOW (no current consumer) | HIGH | P3 |

## Competitor / Prior-Art Feature Analysis

| Feature | NMRPipe + SMILE | NMRFx (IST/NESTA) | hmsIST / mddnmr | Our Approach |
|---------|------------------|--------------------|-------------------|--------------|
| Reconstruction algorithm maturity | Most literature-validated (SMILE = de facto standard, NIH/Bax lab) | In-house IST/NESTA, less independently published than SMILE but actively maintained (2025 paper) | hmsIST = well-published Poisson-gap IST; mddnmr = Python2, less actively maintained | Delegate to whichever backend passes the §8-derived gate on the real dataset; do not assume literature reputation alone is sufficient |
| Cross-platform (macOS/Linux/Windows) | Linux/macOS native; Windows needs VM or unofficial WSL — no native Windows binary per official install docs | Pure Java — genuinely native on macOS/Linux/Windows | Same tcsh/NMRPipe-dependent constraints as NMRPipe path | Portability is a hard project constraint — weigh heavily against SMILE's superior published fidelity |
| Headless/scriptable | tcsh scripts (`fid.com`), scriptable but not Python-native; registration-gated download | Python-scripted processing (`process.py`), explicitly designed for headless/batch execution | tcsh/NMRPipe-pipeline scriptable, similar friction to SMILE path | Prefer a backend whose scripting surface is closest to Python to minimize orchestration glue code |
| Peak picking | Built-in (`autoPick`/`Pipe2Txt.tcl`) but format-specific | Built-in, Java-object-model-specific | Delegates to NMRPipe's peak picking | **Do not use any of these** — reuse lucy-ng's own nmrglue-based picker against the reconstructed spectrum (NMRPipe-format output is nmrglue-readable regardless of which backend produced it), preserving the existing JSON schema |
| Schedule/NUS metadata auto-detection | Manual (`fid.com` built from `bruker` GUI template, adapted by hand) | Automatic — recognizes `nuslist` presence and FnMODE from Bruker metadata when generating a processing script | Manual, similar to NMRPipe path | Regardless of backend, lucy-ng's own metadata-parsing code (Pipeline Chain step 2) must not rely on backend auto-detection alone — needs independent verification for the "fully automatic, no manual step" constraint |

## Sources

- SMILE: [PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/27866371/), [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC5438302/), [official SMILE page (NIH/Bax lab)](https://spin.niddk.nih.gov/bax/software/SMILE/), [SMILE User's Manual](https://spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf) — MEDIUM-HIGH confidence (official source, WebSearch-mediated, direct fetch blocked by 404/redirect)
- NMRPipe NUS overview: [ibbr.umd.edu/nmrpipe/nus.html](https://www.ibbr.umd.edu/nmrpipe/nus.html) — MEDIUM confidence (official source, content via WebSearch synthesis; direct WebFetch returned 404)
- hmsIST: [nus@HMS docs](http://gwagner.med.harvard.edu/intranet/hmsIST/docs_pubs.html), [PMC on interpolating/extrapolating with hmsIST](https://pmc.ncbi.nlm.nih.gov/articles/PMC5614452/) — MEDIUM confidence
- mddnmr/qMDD: [mddNMR manual v2.7](http://mddnmr.spektrino.com/man), [mddnmr Google Group — QF processing thread](https://groups.google.com/g/mddnmr/c/qbeyDhqa9ns) — MEDIUM confidence
- NMRFx Processor: [Journal of Biomolecular NMR paper (2016)](https://link.springer.com/article/10.1007/s10858-016-0049-6), [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4983292/), [2025 NMRFx integrated-software preprint](https://www.biorxiv.org/content/10.1101/2025.08.26.672401v1.full), [NUS docs (docs.nmrfx.org — WebFetch cert error, content via WebSearch snippet)](http://docs.nmrfx.org/processor/howto/nus) — MEDIUM confidence (official source, not directly fetched due to TLS cert mismatch on the docs subdomain)
- NMRPipe Windows support: [official install page](https://www.ibbr.umd.edu/nmrpipe/install) — MEDIUM confidence (states VM-based Windows use; no native Windows binary; legacy WinXP/SFU version deprecated as of v8.9)
- QF/echo-antiecho quadrature mechanics: general established NMR pulse-sequence theory (States/TPPI/echo-antiecho hypercomplex detection) — HIGH confidence as domain knowledge, cross-checked against [Bruker pulse-programming training course](https://www.pascal-man.com/pulseprogram/avance3/topspin_2_1/TrainingCourse_PulseProgramming.pdf) and [hmsIST pulse-program coding notes](http://gwagner.med.harvard.edu/intranet/hmsIST/pulseprog.html)
- Magnitude-mode NUS COSY: [PMC5844889 — Systematic Evaluation of NUS Parameters in 2D NMR](https://pmc.ncbi.nlm.nih.gov/articles/PMC5844889/) — MEDIUM confidence
- nuslist 0-based / NMRPipe 1-based indexing convention: [Powers Wiki — Non-Uniform Sampling](https://bionmr.unl.edu/mediawiki/index.php/Non-Uniform_Sampling), [Powers Wiki — NUS](http://bionmr.unl.edu/mediawiki/index.php/NUS) — MEDIUM confidence
- Virtual echo: [arXiv:1401.6309 — Causality principle in reconstruction of sparse NMR spectra](https://arxiv.org/pdf/1401.6309) — MEDIUM confidence
- Existing JSON peaklist schema: direct read of `analysis/nmr_peaks/{13C_exp6_narrow,13C_exp7_wide,1H_exp1,COSY_exp2,HMBC_exp4,HSQC_exp3,NOESY_exp5}.json` — HIGH confidence (primary source, ground truth)
- Task brief: `analysis/NUS-RECONSTRUCTION-GUIDE.md` (this repo's authoritative research brief) — HIGH confidence (primary source)
- lucy-ng existing peak-picking / prediction architecture: `.planning/PROJECT.md` — HIGH confidence (primary source)
- nmrglue reading NMRPipe-format files (`nmrglue.fileio.pipe`): established, widely documented nmrglue capability — HIGH confidence (well-known library feature, consistent with lucy-ng's existing "nmrglue for NMR parsing" stack decision)

---
*Feature research for: lucy-ng v10.0 Automatic NUS 2D Reconstruction*
*Researched: 2026-07-12*
