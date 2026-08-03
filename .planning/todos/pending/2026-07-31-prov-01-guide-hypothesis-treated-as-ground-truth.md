---
created: 2026-07-31
title: "PROV-01: an unsolved sample's agent-authored hypothesis is compiled into the QC gate as ground truth"
area: qc
priority: high
files:
  - src/lucy_ng/nus/postprocess.py
  - src/lucy_ng/nus/qc.py
  - src/lucy_ng/cli/jcamp.py
  - .planning/research/PITFALLS.md
---

## Problem

`nus/qc.py` and `nus/postprocess.py` compile in two constants that the codebase and
three phases of planning documents describe as **ground truth**:

```python
# nus/postprocess.py
GUIDE_S10_C13 = [142.00, 135.86, 79.35, 69.06, 67.06, 51.63, 37.86, ...]   # 20 shifts
# nus/qc.py
DEFAULT_QUATERNARY_SHIFTS = (142.00, 135.86, 79.35, 36.23, 37.86)
```

They are not ground truth. Their source is
`<data>/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` §8/§10 —
a file written **by a Claude instance into the output directory of the failed 2026-07-09
CASE run**, as a handover note for its successor. §10's own heading reads:

> "Gesicherte Fakten aus dem ersten Lauf (aus den verlässlichen 1D-Daten — als Startpunkt)"

i.e. facts that agent inferred from *this very sample's own 1D spectra*. C20H32O2 is an
**unsolved** test dataset from Nils Schlörer (Jena); the user confirmed on 2026-07-31 that
no human reference assignment exists for it. The guide hedges two of the five "quaternary"
shifts in its own words:

- `37.86` — "evtl. ein angularer C10 (~37.86, **MEDIUM**)"; §8 calls it "37.86-**Kandidat**"
- `79.35` — "...ODER 4 Carbon-Ringe + Diol (**falls 79.35 doch Rauschen**)"

Despite this, `qc.py`'s comment called them "The 5 **confirmed**-quaternary 13C shifts" and
`postprocess.py` called its list "**Ground-truth** 1D 13C shifts ... the calibration
cross-check's **source of truth**".

## Why it matters

1. **Circular validation.** Phase 103's headline "§10 cross-check: 17/20 matched within
   ±0.5 ppm" compares peaks we picked from the 1D ¹³C spectrum against peaks an earlier
   agent picked from the same spectrum. It measures reproducibility, not correctness.
   (It does retain narrower value: the earlier list came via the **Bruker** reader and the
   new one via the **JCAMP** reader, so agreement genuinely cross-checks the new ppm axis —
   the JC-02/WR-04 risk. That is the claim it can support, and only that one.)
2. **The `quaternary_exclusion` FAIL is ambiguous, not diagnostic.** It fires when the
   hypothesis and the data disagree. "37.86 is simply not quaternary" produces exactly the
   same FAIL as "the picker found an artifact". Phase 103 recorded it as the former being
   *knob-independent* — correct — but framed it as a reconstruction/threshold problem.
3. **`hsqc_coverage`'s denominator** (~17 protonated carbons) comes from the same hypothesis.
4. **Cross-contamination beyond this sample.** `cli/jcamp.py` reaches
   `QcConfig.default()` unconditionally when no DEPT file is present. Any other compound run
   through `lucy jcamp` (or `lucy nus qc`) without DEPT is graded against C20H32O2's guesses.
   This is the part that is a defect rather than a labelling error.

## Done so far (2026-07-31) — labelling only, no behaviour change

- Provenance notes added to `GUIDE_S10_C13`, `DEFAULT_QUATERNARY_SHIFTS`,
  `PROTONATED_REFERENCE`, `qc_check_ppm_calibration()`, `cli/jcamp.py`'s docstring and
  `tests/nus/conftest.py`. "Ground truth" / "confirmed" removed wherever it was claimed.
- Planning documents corrected so the term stops propagating.

## Re-analysis result (2026-07-31, same day) — decision 2 and 3 now have evidence

Full write-up: `.planning/analysis/2026-07-31-PROV-01-quaternary-reanalysis.md`.
Read-only re-reading of the quarantined Phase-103 peak lists, deriving the quaternary set
from the edited HSQC instead of from the hypothesis:

- **37.86 ppm is a CH** (positive HSQC correlation at 1H 1.571), not a quaternary carbon. The
  `quaternary_exclusion` FAIL was the gate correctly reporting that its input assumption is
  wrong — not a reconstruction or threshold problem.
- Data-derived quaternaries are **51.63, 37.19, 36.23, 35.23, 30.66** (+ 142/135.86, confirmed
  independently by HMBC with 3 and 8 correlations). Only 36.23 and the olefinics agree with the
  hypothesis; **3 of 5 assumed quaternaries are wrong**.
- **But the peak lists are genuinely incomplete:** 19 of 20 carbons, and only ~24 of the
  expected ~30-31 C-bound hydrogens. So the FAIL is not purely an artifact of the wrong ruler.
- **The knob matrix was decided against the false hypothesis.** The winning cell (23 peaks) was
  chosen because it matched §10's expected count; richer cells (39/50/51/62) were rejected as
  "above zone". The H balance says 23 is too *few*. The 62-peak cell was partly rejected over a
  "quaternary hit at 79.29" — the very carbon the C20 count requires as the missing twentieth.

**Consequence for decision 2:** Phase 103's PARTIAL stands, but its stated cause does not.
**Consequence for decision 3 (JVAL-F2):** mis-scoped. Not "recalibrate the noise model" but
(a) `quaternary_exclusion` is conceptually inverted — the edited HSQC is what *determines* the
quaternary set, so grading it against a supplied list can only measure agreement with an
assumption; a sound check derives the set and tests it against hard facts (formula carbon
count, H balance); and (b) HSQC completeness, re-judged against formula-derived criteria.

## Final state of the C20H32O2 analysis (2026-08-02)

Full write-up: `.planning/analysis/2026-08-02-PROV-01-raw-matrix-classification.md`
(carries its own correction banner — two of its claims were wrong and cancelled each other).

Settled:
- **22.64 ppm is two coincident CH₂ carbons** — 1D ¹³C integral 2.02× the single-carbon
  median, HSQC volume 1.92×. The user's hypothesis, confirmed by two independent measures.
- Corrected assignment: **11 CH₂ + 4 CH + 2 CH₃ + 3 Cq = 20 C, 32 C-bound H, no OH**
  (both oxygens ethers). DBE 5 = one C=C + 4 rings. §10's claimed OH at 5.32 ppm: 0.11 H.
- **Of §8/§10's five proposed quaternaries only the two olefinics survive.** The single
  quaternary inside the exported window is 51.63.
- **79.35 is a real signal but most likely the minor component**, not the compound: weakest
  tier in all three experiments, proton integrates ~0.1–0.3 H. Not needed for the formula.
- The sample carries **~40 % of a minor component** (total ¹H integral 45 H vs 32).

Not settled, and not worth more effort here: whether 79.35 belongs, and whether a further
coincidence hides in the crowded 27.5–25.5 ppm region. Both need a cleaner sample. Solving
this structure is not a lucy-ng deliverable — the analysis was a means of validating the
reader, and that goal is met.

## Development findings this produced (the actual value)

1. **The JCAMP reader is validated by real use.** Both ppm axes, edited signs and
   *quantitative* intensities held up through a full manual assignment: methyls integrate
   2.98/3.02 H, methines 1.02/1.03 H, and a 2× coincidence was detectable. Far stronger
   evidence than Phase 103's circular "17/20 vs §10". Untested: COSY, NOESY, other datasets.
2. **The peak picker is the weak link, not the reader.** Every wrong conclusion in this
   episode came from picked lists rather than the raw matrix.
3. **Peak lists discard signal area and relative intensity** — exactly the information that
   revealed the 22.64 coincidence and the minor component. A CASE agent gets 19 carbons.
4. **The HMBC F1 resolution (0.234 ppm/point) is a real ceiling** on this dataset: 17
   distinct F1 positions for 20 carbons.
5. **A formula-balance check (carbon count, H count) is the non-circular replacement for
   `quaternary_exclusion`** — it grades against the molecular formula, a hard fact, instead
   of against an assumed shift list. This resolves PROV-01's decision 1 in principle.

## Open — needs a decision, deliberately not taken unilaterally

1. **Should `DEFAULT_QUATERNARY_SHIFTS` remain a library default at all?** Options: drop the
   default and require an explicit per-sample override; keep it but refuse to apply it unless
   the caller names the sample; or emit a loud warning in the QC report when it is used.
   Any of these changes gate behaviour, so it is a user call.
2. **Re-read Phase 103's verdict under the corrected framing.** JVAL-01's FAIL may be
   substantially "the hypothesis is wrong", which is a different problem from JVAL-F2's
   "recalibrate the noise model". JVAL-F2's description should be re-scoped accordingly.
3. **Is 37.86 quaternary?** A DEPT or an APT on this sample would settle it directly and
   would remove the need for the compiled-in override entirely for this dataset.

## Meta-lesson

The word "ground truth" entered the code and the roadmap from an agent-authored handover
note and survived three phases of planning, research, verification and code review without
anyone opening the source file. Provenance of a reference dataset must be checked at the
point it is first cited, not assumed from its label.
