# C20H32O2: CH/CH₂/CH₃/quaternary classification read from the raw HSQC matrix

**Date:** 2026-08-02
**Input:** the six `.dx` files, read through lucy-ng's own `JcampReader` — the **raw 2D
matrix**, not the picked peak lists.
**Why:** the 2026-07-31 re-analysis used the picked lists (23 HSQC cross peaks at
`snr_floor=4000`). Those lists are under-picked, and their gaps propagated into that
document's conclusions. This one goes to the source.
**Read-only:** nothing was re-run, re-picked, or modified.

> ## ⚠ CORRECTED LATER THE SAME DAY — read this before the conclusions
>
> Two claims below are wrong, and they were wrong in a way that made each other
> look right:
>
> 1. **22.64 ppm is TWO coincident CH₂ carbons, not one.** Its 1D ¹³C integral is
>    **2.02×** the single-carbon median (every other carbon: 0.84–1.05) and its HSQC
>    volume **1.92×**. Two independent measurements, no borderline case.
> 2. **79.35 is therefore not needed, and most likely is not part of the compound.**
>    With 22.64 counted twice the formula closes at exactly 20 C and 32 C-bound H
>    *without* it. 79.35 sits in the weakest tier of every experiment (1D S/N 18 vs
>    51–102; HSQC 748σ vs median 4521σ; HMBC 842σ vs median 6650σ) and its proton
>    integrates ~0.1–0.3 H in a crowded band, not 1 H.
>
> The "balance closes exactly at 20 C / 31 H + 1 OH" argument below is void: it
> closed only because two errors cancelled — counting 22.64 once and counting
> 79.35 in. The corrected balance is **11 CH₂ + 4 CH + 2 CH₃ + 3 Cq = 20 C, 32 H,
> no OH** — both oxygens are ethers. Independently supported: the ¹H region at
> 5.32 ppm, where §10 claims an OH, holds 0.11 H.
>
> Also relevant: the total ¹H integral is ~45 H against 32 expected, so the sample
> carries roughly 40 % of a minor component. Absolute integrals are therefore
> unreliable here; the 2.02× figure is trustworthy because it compares like with
> like inside one ¹³C spectrum.
>
> Credit where due: the doubling was the user's hypothesis, not a finding of this
> analysis.

---

## Correction of my own prior analysis

`2026-07-31-PROV-01-quaternary-reanalysis.md` reported the data-derived quaternary set as
**51.63, 37.19, 36.23, 35.23, 30.66**. That was wrong. Four of those five carbons *do* carry
HSQC correlations; the picker simply had not found them at the chosen threshold.

This is the same error class the PROV-01 document was written to expose: trusting a derived
artefact instead of the source. Recorded here rather than quietly fixed.

## Method

For each ¹³C shift, take the ±2-point slice in F1, scan the ¹H range 0.4–4.6 ppm, and report the
extremum and its sign. Noise σ = 7232 (MAD over the full matrix). A carbon is called quaternary
only when nothing in its F1 slice exceeds ~150σ; empty control regions measure ±20–270σ.

## Result — every carbon accounted for

| ¹³C | S/N | ¹H | assignment |
|---:|---:|---:|---|
| 142.00 | −18 | — | **quaternary** (olefinic) |
| 135.86 | −13 | — | **quaternary** (olefinic) |
| 79.35 | **+748** | 3.805 | oxygenated CH — but ⚠ **minor component**, not the compound (see banner) |
| 69.06 | −8568 | 3.337 | CH₂, oxygenated |
| 67.06 | +9644 | 4.131 | CH, oxygenated |
| 51.63 | +53 | — | **quaternary** — the only one in the exp6 window |
| 37.86 | +5758 | 1.571 | CH |
| 37.19 | +3518 | 2.146 | CH |
| 36.23 | +3912 | 1.806 | CH |
| 35.23 | −346 | 1.480 | CH₂ (weak) |
| 34.21 | −4269 | 1.959 | CH₂ |
| 33.67 | −4521 | 1.970 | CH₂ |
| 30.66 | −3286 | 2.121 | CH₂ |
| 29.77 | −5491 | 1.612 | CH₂ |
| 27.93 | −4928 | 1.535 | CH₂ |
| 27.16 | −4672 | 1.238 | CH₂ |
| 25.96 | −4201 | 1.696 | CH₂ |
| 23.43 | **+53615** | 0.963 | **CH₃** |
| 22.64 | −8625 | 1.813 | ⚠ **TWO coincident CH₂** — 1D area 2.02×, HSQC volume 1.92× (see banner) |
| 21.78 | **+51522** | 0.989 | **CH₃** |

The two CH₃ signals are ~7× more intense than any CH — consistent with 3 H versus 1 H, and with
§10's own observation of two methyl singlets at 0.990/0.964.

## The balance — as first computed (superseded)

```
  10 × CH2  (negative)   ->  20 H
   5 × CH   (positive)   ->   5 H
   2 × CH3  (positive)   ->   6 H
   3 × Cq                ->   0 H
  ----------------------------------
  20 carbons                 31 H on carbon
```

**⚠ SUPERSEDED — see the correction banner at the top.** This balance closed only because
22.64 was counted as one carbon (it is two) *and* 79.35 was counted in (it most likely does
not belong). The corrected balance is 11 CH₂ + 4 CH + 2 CH₃ + 3 Cq = 20 C and 32 C-bound H,
with no OH. The ¹H spectrum shows 0.11 H at 5.32 ppm, so §10's OH claim is not supported
either.

DBE = 5 = one C=C (142.00/135.86) + **4 rings** — this part is unaffected. The oxygen reading
is not: with 79.35 excluded only two oxygenated carbons remain (69.06 CH₂, 67.06 CH), and with
all 32 H on carbon there is no OH, so **both oxygens are ethers**.

## Validation of the two contested signals

**79.35 is a real signal — but ⚠ most likely NOT part of the main compound** (see the
correction banner). The observations below stand as measurements; the attribution does not.

- 1D ¹³C: sharp isolated line at 79.345 ppm, S/N 18. Neighbouring 0.1-ppm bins are at S/N
  1.0–2.3; the CDCl₃ foot at 78.58 is S/N 2.0. It is not solvent tailing.
- HSQC: a cross peak at 79.35/3.805 at 748σ. Eight F1 points away it drops to ±27σ, and the
  ¹H = 3.805 column has median 0.8σ along F1 — so it is a genuine cross peak, not a t₁ ridge.
- The picker missed it because the ¹³C `snr_floor` was set to 40, above its S/N of 18.

**There are two methyls, not four.** §10 proposes four CH₃ singlets (25.96 allylic, 23.43
angular, 21.78 + 22.63 gem-dimethyl). The raw matrix shows 25.96 and 22.64 as clearly negative
(CH₂, −4201σ and −8625σ). Only 23.43 and 21.78 are positive with methyl-region ¹H shifts. Four
methyls would also break the H balance, which two methyls close exactly (and still do under
the corrected 11 CH₂ / 4 CH / 2 CH₃ / 3 Cq reading).

## Consequences

1. **§8/§10 is wrong on more than the one hedged shift.** Of five proposed quaternaries only
   142.00 and 135.86 survive; 79.35, 36.23 and 37.86 are all protonated. The real quaternary
   set in the exported window is a single carbon, 51.63.
2. **The `quaternary_exclusion` FAIL was fully explained by the false reference.** Two of the
   three shifts it fired on (36.23, 37.86) are protonated carbons; the check was doing its job.
3. **Both of Phase 103's failing checks trace back to the reference, not the spectra.** The
   spectra support a complete, formula-consistent assignment of all 20 carbons.
4. **The ¹³C `snr_floor=40` was also chosen against the false expectation** — it produced "20
   peaks, an exact match to §10's count", but only because three CDCl₃ lines filled in for three
   real carbons the window or the threshold excluded.
5. **The `lucy jcamp` chain delivered usable data.** Reading, ppm axes, edited signs and
   *quantitative* intensities are all sound enough to classify every carbon, detect a 2×
   coincidence at 22.64, and integrate protons correctly (methyls 2.98/3.02 H, methines
   1.02/1.03 H). What failed was the grading, not the reader.
6. **The peak picker, not the reader, is the weak link.** Every wrong conclusion in this
   episode — Phase 103's, the 2026-07-09 agent's, and both of mine — came from working with
   picked lists instead of the raw matrix.
7. **Peak lists discard the information that actually decided this.** Signal area and relative
   intensity are what revealed the 22.64 coincidence and the minor component; `lucy jcamp`
   writes neither. A CASE agent would be stuck at 19 carbons.

## Open

- The 1D ¹³C list still lacks 142.00 and 135.86 because `exp6` (narrow) was exported instead of
  `exp7` (wide) — JVAL-F3 stands, and is now clearly worth doing.
- A DEPT/APT would confirm the CH₃ count independently and, more usefully, help resolve the
  crowded 27.5–25.5 ppm region where a further coincidence could hide. The HMBC cannot: its F1
  digital resolution is 0.234 ppm/point (1024 points over 239 ppm), which leaves 37.86/37.19,
  34.21/33.67 and 27.16/25.96 unresolved — so only 17 distinct F1 positions for 20 carbons.
- Whether 79.35 belongs to the compound is **not settled** by these data, only made unlikely.
  The sample carries ~40 % of a minor component; a cleaner sample would decide it.
- Whether the JCAMP path can reach a QC PASS is untested under a corrected reference; the
  underlying data now look capable of it.

---

*Read-only analysis via `JcampReader`. Figures: `~/Downloads/C20H32O2-jcamp-spektren/`.*
