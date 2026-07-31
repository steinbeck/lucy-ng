# PROV-01 follow-up: re-analysing Phase 103's data without the assumed quaternary list

**Date:** 2026-07-31
**Input:** the quarantined Phase-103 peak lists, unchanged, at
`<data>/active-lucy-ng-testprojects/C20H32O2-jcamp/analysis/jcamp_ingest/qc_failed/`
**Method:** derive the quaternary set from the edited HSQC itself (a carbon with no HSQC
correlation is quaternary) instead of comparing against `DEFAULT_QUATERNARY_SHIFTS`.
**Nothing was re-run, re-picked or modified** — this is a read-only re-reading of existing output.

---

## Question

Phase 103 failed `quaternary_exclusion` and `hsqc_coverage`, and JVAL-F2 was filed as
"recalibrate the noise/threshold model". PROV-01 then established that the grading reference
was a prior agent's hypothesis about an unsolved sample. So: **did the JCAMP path actually
fail, or was it graded with the wrong ruler?**

Answer: **both, but not as diagnosed.** The ruler was wrong *and* the peak lists are genuinely
incomplete — however the incompleteness is the opposite of what the matrix concluded.

---

## Finding 1 — 37.86 ppm is a CH, not a quaternary carbon

```
37.90 ppm  ←  1H 1.571   edited_sign = positive(CH_or_CH3)
```

`NUS-RECONSTRUCTION-GUIDE.md` §10 proposed 37.86 as "evtl. ein angularer C10 (~37.86, MEDIUM)"
and §8 listed it as "37.86-Kandidat". The edited HSQC contradicts it directly.

**Therefore Phase 103's `quaternary_exclusion` critical FAIL was the gate correctly reporting
that its own input assumption is wrong.** It was recorded as evidence of a reconstruction or
threshold problem. It is neither.

## Finding 2 — the data-derived quaternary set differs substantially

| Source | Quaternary carbons |
|---|---|
| §8/§10 hypothesis | 142.00, 135.86, 79.35, 36.23, **37.86** |
| Derived from the edited HSQC | 142, 135.86, **51.63, 37.19, 36.23, 35.23, 30.66** |

Only 36.23 and the two olefinic carbons agree. Three of the five assumed quaternaries are
wrong or unsupported, and four carbons that genuinely show no HSQC correlation (51.63, 37.19,
35.23, 30.66) were absent from the hypothesis entirely.

Full classification (17 carbons in the 1D list; the 3 CDCl₃ lines at 77.28/77.03/76.78 excluded):

| ¹³C | HSQC | sign | ¹H | reading |
|---|---|---|---|---|
| 69.06 | yes | negative | 3.318 / 3.337 / 3.428 / 3.447 | CH₂ (O-CH₂, diastereotopic) |
| 67.06 | yes | positive | 4.131 | CH (oxygenated) |
| **51.63** | **no** | — | — | **quaternary** |
| 37.86 | yes | positive | 1.571 | **CH** — contradicts §10 |
| **37.19** | **no** | — | — | **quaternary** |
| 36.23 | no | — | — | quaternary (agrees with §10) |
| **35.23** | **no** | — | — | **quaternary** |
| 34.21 | yes | negative | 1.959 | CH₂ |
| 33.67 | yes | negative | 1.355 / 1.970 | CH₂ |
| **30.66** | **no** | — | — | **quaternary** |
| 29.77 | yes | negative | 1.480 / 1.612 | CH₂ |
| 27.93 | yes | negative | 1.535 / 1.619 | CH₂ |
| 27.16 | yes | negative | 1.238 / 1.267 / 1.970 | CH₂ |
| 25.96 | yes | negative | 1.696 / 1.721 | CH₂ — §10 called this an allylic CH₃ |
| 23.43 | yes | positive | 0.963 | CH₃ |
| 22.64 | yes | negative | 1.791 / 1.813 | CH₂ — §10 called this a gem-dimethyl CH₃ |
| 21.78 | yes | positive | 0.989 | CH₃ |

## Finding 3 — HMBC independently confirms the two olefinic carbons

HMBC F1 values not present in the 1D ¹³C pick list:

| ¹³C | correlations |
|---|---|
| 141.9 | 3 |
| 135.8 | 8 |
| 26.5 | 1 |
| 0.1 | 1 (artifact) |

141.9 and 135.8 are real and well-correlated; they are missing from the 1D list only because
the narrow `exp6` was exported instead of `exp7`. This is a second, independent confirmation of
the exp6/exp7 diagnosis — reached without touching the raw Bruker tree.

## Finding 4 — the peak lists ARE genuinely incomplete

This is the half that survives the correction.

```
carbons:  17 picked (+2 visible in HMBC) = 19        C20H32O2 needs 20
H count:  8 × CH2                        = 16 H
          2 × CH  (67.06@4.13, 37.86@1.57) =  2 H
          2 × CH3 (23.43@0.96, 21.78@0.99) =  6 H
          ------------------------------------
                                           24 H      expected ~30-31 C-bound H
```

~6–7 C-bound hydrogens and at least one carbon are missing. §10 also claims four methyl
singlets while the data show only two unambiguous methyls. Plus one artifact cross peak at the
origin (0.02 / 0.018) in HSQC and one at 0.1 ppm in HMBC.

Caveat, stated rather than glossed: an overlapping CH₃/CH₂ pair at the same ¹³C shift can
present as negative in an edited HSQC if the CH₂ dominates, so 25.96 and 22.64 are not proof
that §10's methyl assignment is wrong — only that the picked data do not support it.

## Finding 5 — the knob matrix was decided against the false hypothesis

From `103-VALIDATION.md`:

```
snr_floor 1000 -> 51 peaks   "above 17-40 zone"                        rejected
snr_floor 2000 -> 50 peaks   "above 17-40 zone"                        rejected
snr_floor 3000 -> 39 peaks   "in zone ... quaternary hit at 36.23 AND 37.9"
snr_floor 4000 -> 23 peaks   "closest to Sec.8's ~17-27 expectation"   CHOSEN
snr_floor 5000 -> 11 peaks   "coverage collapses (6/16)"
threshold 0.01 -> 62 peaks   "quaternary hits at 36.23, 37.9, AND 79.29"
```

The winning cell was chosen **because its peak count matched the expectation derived from
§10**, and richer cells were rejected for producing "too many" peaks against that same
expectation. The H balance says 23 is too *few*. The threshold selection is therefore
contaminated by the same false premise as the verdict.

Note also that the 62-peak cell was partly rejected over a "quaternary hit at 79.29" — at
precisely the carbon the C20 count requires as the missing twentieth (a tert-alcohol Cq-O is
§10's own reading of 79.35, which it then doubted).

---

## What this changes

1. **JVAL-F2 is mis-scoped.** It is not "recalibrate the noise model for CS-reconstructed
   matrices". The real issues are (a) `quaternary_exclusion` compares against an assumed set
   instead of deriving it, and (b) HSQC sensitivity/completeness, judged against a contaminated
   criterion.
2. **`quaternary_exclusion` is conceptually inverted.** The edited HSQC is the experiment that
   *determines* which carbons are quaternary. A check that grades the HSQC against a
   pre-supplied quaternary list can only ever measure agreement with an assumption. A sound
   check would derive the set from the data and then test it for internal consistency — e.g.
   against the molecular formula's carbon count and H balance, which are hard facts.
3. **`hsqc_coverage` is the right idea with the wrong denominator.** Sourced from the ¹³C pick
   list rather than the hypothesis, it would have flagged the real problem here: the H balance
   is short by ~6–7 H.
4. **Phase 103's PARTIAL outcome stands**, but its stated cause does not. The reader work is
   unaffected.

## Recommended next step

Re-judge the knob matrix against **formula-derived** criteria instead of §10: does the picked
set account for 20 carbons and ~30–31 C-bound hydrogens, and is the CH/CH₂/CH₃ pattern
self-consistent? The matrix cells are already recorded, so this is re-reading, not re-running —
though confirming a richer cell would mean one more `lucy jcamp` invocation.

Open and unanswerable from this dataset alone: whether 79.35 is a real carbon (a DEPT/APT would
settle both that and the methyl count directly, and would remove the need for any compiled-in
override on this sample).

---

*Read-only analysis. No peak list, fixture or source file was modified in producing it.*
