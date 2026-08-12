# lucy-ng → faulon-ng bridge (feasibility spike, 2026-08-11)

[faulon-ng](../../../faulon-ng) is a simulated-annealing CASE engine intended as an
eventual alternative to LSD. This directory holds what was needed to feed it real
lucy-ng data and measure the result. **Spike quality, not production** — nothing here
is wired into the CASE workflow.

## Files

| | |
|---|---|
| `lsd2sml.py` | converts a `compound.lsd` into a SENECA `.sml` |
| `score_truth.py` | scores known structures with faulon-ng's own ChiefJustice, to separate a sampling failure from a scoring failure |
| `examples/CASE13.{lsd,sml}` | a solved benchmark case, input and converted output |

```bash
./lsd2sml.py examples/CASE13.lsd C12H12N2O3 out.sml --title CASE13
cd ../../../faulon-ng && .venv/bin/faulon-ng run out.sml --steps 100000 --top-n 10 --json
```

## Why convert from the .lsd and not from the raw peak lists

The value lucy-ng adds sits between them. CASE13's `hmbc_raw.json` holds **4402** peaks,
mostly noise, and its `hsqc_raw.json` holds **2**. The `compound.lsd` holds the **15**
HMBC and **6** HSQC the nmr-chemist kept and the devil's advocate cleared, plus the
DEPT-derived multiplicities. faulon-ng runs no DEPT analysis of its own and says so at
startup:

```
Using STATED per-atom hydrogenCount from .sml (bypassing DEPT).
```

So the natural division of labour is: lucy-ng's specialists interpret the spectra,
faulon-ng searches the structure space.

## Format mapping

| SENECA `.sml` | source |
|---|---|
| `<atom>` (elementType, hydrogenCount, assignedCarbonShift) | `MULT` lines |
| `carbon1d` | `MULT` carbon shifts |
| `dept135` | `MULT`, CH₂ negative |
| `hetcor` | `HSQC` |
| `hetcorlr` | `HMBC` |
| `hhcosy` | `COSY` |

## Two traps, both cost a run

**Exact ppm matching.** faulon-ng binds peaks to atoms at `eps = 1e-06`, i.e. equality.
Writing atom shifts at one decimal and signal locations at four makes *every* peak
unassignable — the run completes and returns pure noise. Both are written at four
decimals now.

**Grouped correlations.** A line like `HMBC (4 5) 10` is one observed peak whose F1
could not be resolved between two carbons. The midpoint is tidier but matches no atom
under that tolerance, so the peak vanishes. One signal per candidate is emitted instead;
grading them is exactly what a scoring engine is for. The branch where the proton sits
on the candidate carbon itself is skipped — that would be a 1J.

## Result of the spike

CASE13 (C12H12N2O3, 17 heavy atoms, solved by LSD at rank 1 under both models) was run
at 100k×3 and at 1M×5 steps. The correct structure appeared in neither top-10 nor
top-20. The search converges — best score rose 0.8074 → 0.8240 — but onto **highly
bridged, fully saturated polycycles**: 5 rings and 0 aromatic atoms, against the truth's
2 rings and 10 aromatic atoms; the 1M winner even contains a cumulene.

A plausible mechanism, measured on the two structures:

| | mean path length | atom pairs 2–3 bonds apart |
|---|---|---|
| SA winner | 3.01 | **53 %** |
| truth | 3.46 | 40 % |

A bridged skeleton has 13 percentage points more atom pairs at exactly the separation an
HMBC correlation asks for. It satisfies the constraints by being compact, not by being
right. Whether the `PlausibilityJudge` (weight 1.0, same as HMBC) is meant to offset that
is a question for the faulon-ng side.

**Caveat on `score_truth.py`:** its rebuilt judge stack does not reproduce the engine's
own numbers — it returns 0.3500 for a structure the run scored 0.8074. Comparisons
*within* one of its runs are valid (all candidates share the stack); comparisons against
the engine's output are not. The gap is unexplained; the post-anneal `HOSE13CReRanker`
is one suspect.

## Status

The bridge works and loses no correlations. A solver swap is not on the table yet — the
open question is the engine's scoring landscape, not the interface. Ground truth for the
example case is deliberately absent from this directory; see the case write-up delivered
separately.
