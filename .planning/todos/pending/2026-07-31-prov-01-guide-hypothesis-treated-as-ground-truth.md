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
