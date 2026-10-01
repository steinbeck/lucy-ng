# Benchmark: blind evaluation on 258 NMR datasets

lucy-ng is evaluated **blind**. The agent team is handed nothing but a directory of
Bruker spectra and a molecular formula; it never sees the compound's name, structure or
database entry, and dereplication is forbidden. Everything below is measured that way.

> **Status: complete (2026-09-29).** Every runnable dataset has been run on the current
> model, and the 102 datasets of the earlier model's arm have been run on both. Figures
> here are regenerated from the run artefacts with the grader in this repository, not
> transcribed.

---

## What counts as success

Two thresholds are reported, because they answer different questions.

**Rank 1** — the correct constitution is the top-ranked candidate. This is the strict
reading: the system got it right without a human choosing among alternatives.

**Top 10** — the correct constitution is somewhere in the first ten candidates. This is
the *useful* reading, and it is the more honest one for how CASE output is actually
consumed: a shortlist of ten is exactly the size that DP4/GIAO chemical-shift
calculations are run on to pick the winner. A result that puts the truth in the top ten
is one a spectroscopist can finish.

In practice the two are close to each other but far from a third number — "found
anywhere in the solution set". Across every arm, when the true structure appears at all,
it is almost always already within the top ten. The ranking is not the bottleneck; the
generation is.

**Matching is on the first InChIKey block** — constitution only. Stereochemistry is
**not** tested: a candidate without E/Z or R/S assignment counts as correct if the
skeleton and connectivity match. Read every figure below with that in mind.

---

## How blindness is enforced

Four mechanisms, because a prompt instruction alone is not evidence of anything:

1. **The datasets are sanitised.** Compound names are stripped from Bruker metadata —
   `pdata/*/title`, the free-text `$TI` parameter, experiment directory names and
   embedded sample codes.
2. **A fence in the system prompt** forbids reading any ground-truth, answer-key or
   benchmark-results location, and forbids dereplication and lookup by name.
3. **A physical lockout.** Every file that maps a dataset to its answer is *moved* out
   of the filesystem for the duration of a batch and restored afterwards. Runs execute
   with `--dangerously-skip-permissions`, so the fence is advice; the move is the
   barrier.
4. **Grading is external and independent.** `tests/case-benchmark/grade_blind.py` parses
   each run's `final_results.md`, validates every candidate with RDKit, and compares
   InChIKeys against the answer key. The run's own claim about its result is never used.

An audit of the finished campaign read all 138 protocol/report pairs against a rubric
taken from the orchestrator's own rules, looking for short cuts to the answer. It raised
93 findings; 92 were refuted on inspection and **one stood** — a case where the solution
analyst swept the reference database for a replacement structure, which the coordinator
caught, demoted, and re-ran. A separate mechanical scan of all 258 datasets found **6
that still leaked a compound name** (3 through experiment directory names, 3 through
title text), worth about 0.3 points on the headline; three of those were re-sanitised
before the current re-run.

---

## Results

### The whole benchmark on the current model

256 datasets were run on Opus 5 (all 258 minus the two excluded below). Median size 24
heavy atoms, range 2–39.

| | Of all 256 datasets | Of the 231 runs that produced a report |
|---|---:|---:|
| Correct structure ranked **first** | **177 — 69.1 %** | **76.6 %** |
| Correct structure **within the top 10** | **189 — 73.8 %** | **81.8 %** |

The 25 runs without a report all ended at the three-hour wall-clock limit per dataset;
none failed for an infrastructure reason. The left column counts them as failures,
which is the strict reading and the one to cite.

Four datasets are **not blind** any more: their identities were in this public
repository before they were run (CASE86, CASE87, CASE93, CASE265). Without them the
figures are 175 / 253 = 69.2 % at rank 1 — they do not move the result.

### By molecule size

Rank 1 of all runs, timeouts counted as failures:

| Heavy atoms | Datasets | Rank 1 | No report |
|---|---:|---:|---:|
| ≤ 15 | 40 | **40 — 100 %** | 0 |
| 16–20 | 32 | **28 — 88 %** | 0 |
| 21–25 | 70 | **49 — 70 %** | 5 |
| ≥ 26 | 114 | **60 — 53 %** | 20 |

The decline above 25 heavy atoms is not uniform. The large molecules of the main
campaign were solved at rank 1 in 77 % of the runs with a report; those of the
re-run set in 37 %. On the 34 large datasets run on both models, 21 are solved by
neither. And a failed run almost never had the truth further down its list: 190
datasets have the true structure somewhere in the report, 189 of them in the top ten.
When the system fails, the right structure is not among the candidates it reports at
all; ranking is not what limits it.

### The same molecules, both models

102 datasets have been run on both Opus 4.8 and Opus 5. Each dataset is its own
control, so this comparison is not confounded by which molecules happened to land in
which arm:

| | Opus 4.8 | Opus 5 |
|---|---:|---:|
| Rank 1 | 40 / 102 (39.2 %) | **67 / 102 (65.7 %)** |
| Won only by this model | 3 | **30** |

Exact two-sided McNemar over the 33 discordant pairs: **p = 1.4 · 10⁻⁶**. Runs without
a report count as failures; restricted to the 93 datasets where both runs produced a
report, it is 30 : 1, p = 3 · 10⁻⁸.

### The arms

The figures above combine two Opus-5 arms that do not overlap. For reference, every
arm separately (rank 1 and top 10 relative to the runs that produced a report):

| Arm | Datasets | With report | Rank 1 | Top 10 |
|---|---:|---:|---:|---:|
| Opus 5 — main campaign | 154 | 138 | 110 (79.7 %) | 119 (86.2 %) |
| Opus 5 — re-run of the 4.8 datasets | 102 | 93 | 67 (72.0 %) | 70 (75.3 %) |
| Opus 5 — earlier repeat sample | 15 | 12 | 8 (66.7 %) | 10 (83.3 %) |
| Opus 4.8 — historical arm | 102 | 102 | 40 (39.2 %) | 44 (43.1 %) |

The 15-dataset repeat sample was run on 8–9 August, a month before the re-run and on an
earlier revision of the skill; its datasets are part of the re-run. The two agree on 11
of 15; in the four where they differ the later run is the one at rank 1. That is the closest thing
here to a measure of run-to-run variation, and it is confounded with the skill change.

### What changed between the arms — and what that costs the comparison

The arms differ in **two** ways, not one: the model changed from Opus 4.8 to Opus 5,
**and** the orchestrator skill was revised in between. Nothing here separates the two.
The honest claim is "lucy-ng as it was then versus lucy-ng as it is now", and that is how
it should be cited.

The main campaign set is significantly *larger* and *more flexible* than the 4.8 set
(median 26 vs 22 heavy atoms, p = 0.014; 3 vs 1 rotatable bonds, p = 0.0003), with
rings, aromaticity and sp³ fraction indistinguishable. Yet the main campaign scores
higher than the re-run of the 4.8 set on the same model. Which molecules are hard is a
property of the individual datasets, not of size alone.

### A measurement error, and its correction

Until 2026-09-14 this project recorded the Opus-4.8 baseline as **21.8 %** at rank 1.
That figure was an artefact. The grader used at the time prepended `meta.json`'s
`top_smiles` field as candidate #1, and that field is produced by a shell regexp that
truncates any SMILES at its first closing parenthesis — so for most molecules candidate
#1 was unparseable and the real top candidate was scored as rank 2. Exactly 18 datasets
were displaced that way. Re-grading the identical run artefacts with the current grader
gives **39.2 %**; the count of wrong and no-result runs is unchanged, and the
"found anywhere" figure was never affected (43.1 % then and now). Every figure on this
page was graded with the corrected code.

---

## The datasets

258 Bruker datasets drawn from [nmrXiv](https://nmrxiv.org), spanning 2–39 heavy atoms
(median 24).
The table below carries **no identity columns** — no compound name, SMILES, InChIKey or
nmrXiv accession. The runs are finished, but the dataset→compound mapping stays
unpublished until the paper is out: once it is public, none of these datasets can be
used for a blind test of any later system. Molecular formula and heavy-atom count are
safe, because the solver is handed the formula anyway.

Two datasets are excluded: **CASE7** carries a previous run's `final_results.md` inside
its own dataset directory and can no longer be run blind, and **CASE217** is ethane —
degenerate, and mislabelled in the source. (Naming that one compound is a deliberate
exception to the no-identities rule above: CASE217 is retired and will never be run
again, so saying what it is costs nothing and explains why. The Opus-4.8 arm did run
it, which is why its column counts 103 datasets where the prose counts 102.)

Each model has its own column; a dash means the dataset was not run on that model.
Regenerate this table with:

```bash
python scripts/build_benchmark_table.py \
  --truth  /path/to/answer-key.tsv \
  --index  /path/to/case-index.tsv \
  --results "Opus 5=/path/to/case-uat-results-opus5-rest" \
  --results "Opus 5=/path/to/case-uat-results-opus5-baseline" \
  --results "Opus 4.8=/path/to/case-uat-results" \
  --out /dev/stdout --fragment
```

_Opus 5: 256 datasets run · 177 at rank 1 · 12 elsewhere in the top 10 · 1 found below rank 10 · 41 missed · 25 no report._

_Opus 4.8: 103 datasets run · 40 at rank 1 · 4 elsewhere in the top 10 · 0 found below rank 10 · 58 missed · 1 no report._

| Dataset | Formula | Heavy atoms | Experiments | Opus 5 | Opus 4.8 |
|---|---|---:|---|---|---|
| CASE7 | C15H24N2O2 | — | — | — | — |
| CASE8 | C19H24N4O7 | 30 | 1H, 13C, COSY, TOCSY, HSQC(ED), HMBC | missed | missed |
| CASE9 | C19H24N4O6 | 29 | 1H, 13C, COSY, TOCSY, HSQC(ED), HMBC | **rank 1** | missed |
| CASE10 | C20H26N4O7 | 31 | 1H, 13C, COSY, TOCSY, HSQC(ED), HMBC | no result | missed |
| CASE11 | C20H26N4O6 | 30 | 1H, 13C, COSY, TOCSY, HSQC(ED), HMBC | missed | missed |
| CASE12 | C6H5NO2 | 9 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE13 | C12H12N2O3 | 17 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE14 | C11H12O2 | 13 | 1H, 13C, COSY, HMQC, HMBC, DEPT | **rank 1** | **rank 1** |
| CASE15 | C6H8O7 | 13 | 1H, COSY, 13C, APT/JMOD, DEPT, HMQC, HMBC | **rank 1** | **rank 1** |
| CASE16 | C16H21NO4 | 21 | 1H, 13C, APT/JMOD, HMQC, HMBC, HSQC(ED), COSY | **rank 1** | **rank 1** |
| CASE17 | C15H18N2O3 | 20 | 1H, 13C, DEPT, COSY, HMQC, HMBC, NOESY | **rank 1** | **rank 1** |
| CASE18 | C9H11BrN2O | 13 | 1H, COSY, HSQC(ED), HMBC, 13C | **rank 1** | missed |
| CASE19 | C9H11BrN2O | 13 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | missed |
| CASE20 | C16H26N2O2 | 20 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD, NOESY | **rank 1** | missed |
| CASE21 | C15H24N2O2 | 19 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD, NOESY | missed | missed |
| CASE22 | C15H24N2O | 18 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD | **rank 1** | missed |
| CASE23 | C17H28N2O3 | 22 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD, NOESY | no result | missed |
| CASE24 | C16H28N2O2 | 20 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD | **rank 1** | missed |
| CASE25 | C15H22N2O | 18 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD | **rank 1** | missed |
| CASE26 | C15H22N2O2 | 19 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD | **rank 1** | missed |
| CASE27 | C17H28N2O2 | 21 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD, NOESY | **rank 1** | missed |
| CASE28 | C16H26N2O3 | 21 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD | **rank 1** | missed |
| CASE29 | C15H24N2O2 | 19 | 1H, 13C, COSY, HMBC, HSQC(ED), APT/JMOD, NOESY | **rank 1** | missed |
| CASE30 | C17H25NO4 | 22 | 13C, 1H, COSY, HMBC, HSQC(ED), 2D-OTHER | **rank 1** | missed |
| CASE31 | C17H25NO4 | 22 | 13C, 1H, COSY, HMBC, HSQC(ED), 2D-OTHER | **rank 1** | missed |
| CASE32 | C16H23NO3 | 20 | 13C, 1H, COSY, HMBC, 2D-OTHER, HSQC(ED) | missed | missed |
| CASE33 | C17H25NO3 | 21 | 13C, 1H, COSY, HMBC, HSQC(ED), 2D-OTHER | **rank 1** | missed |
| CASE34 | C10H14O | 11 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE35 | C11H14N2O | 14 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | **rank 1** |
| CASE36 | C28H35NO6 | 35 | 13C, 1H, COSY, DEPT, HMBC, HSQC | missed | missed |
| CASE37 | C10H20O | 11 | 1H, 13C, HSQC(ED), COSY, HMBC, NOESY, APT/JMOD | **rank 1** | missed |
| CASE38 | C11H22O6 | 17 | 1H, HSQC(ED), COSY, HMQC, HSQC, DEPTQ, HMBC | **rank 1** | **rank 1** |
| CASE39 | C20H18ClNO4 | 26 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | top 10 (rank 2) | missed |
| CASE40 | C10H11NO3 | 14 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | **rank 1** | **rank 1** |
| CASE41 | C6H10O2 | 8 | 1H, HSQC(ED), HMBC, NOESY, COSY, DEPTQ | **rank 1** | **rank 1** |
| CASE42 | C29H46O5 | 34 | 1H, 13C, COSY, DEPT, HMBC, HSQC(ED), NOESY | missed | missed |
| CASE43 | C29H44O5 | 34 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | missed | missed |
| CASE44 | C29H44O3 | 32 | COSY, NOESY, 13C, 1H, HSQC(ED), HMBC, DEPT | missed | missed |
| CASE45 | C29H46O5 | 34 | 1H, 13C, HSQC(ED), COSY, DEPT, HMBC, NOESY | missed | missed |
| CASE46 | C30H48O3 | 33 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE47 | C29H46O4 | 33 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | missed | missed |
| CASE48 | C29H46O4 | 33 | 1H, NOESY, 13C, COSY, HSQC(ED), HMBC | missed | missed |
| CASE49 | C29H46O4 | 33 | 1H, DEPT, HSQC(ED), HMBC, NOESY, 13C, COSY | missed | missed |
| CASE50 | C26H40O3 | 29 | 1H, 13C, COSY, HSQC(ED), HMBC, NOESY | missed | missed |
| CASE51 | C21H34O3 | 24 | 1H, 13C, DEPT, COSY, HMQC, HMBC, NOESY | **rank 1** | missed |
| CASE52 | C26H28O7 | 33 | 1H, 13C, DEPT, COSY, HMQC, HMBC, NOESY | missed | missed |
| CASE53 | C26H30O7 | 33 | 1H, 13C, DEPT, COSY, HMQC, HMBC, NOESY | missed | missed |
| CASE54 | C26H30O7 | 33 | 1H, 13C, DEPT, COSY, HMQC, HMBC, NOESY | missed | missed |
| CASE55 | C26H32O8 | 34 | 1H, 13C, DEPT, COSY, HMQC, HMBC, 2D-OTHER | missed | missed |
| CASE56 | C16H16O2 | 18 | 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, 1H | **rank 1** | missed |
| CASE57 | C10H16 | 10 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | **rank 1** | top 10 (rank 4) |
| CASE58 | C10H17Br | 11 | 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, 1H | **rank 1** | missed |
| CASE59 | C16H23BrO2 | 19 | 1H, TOCSY, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | **rank 1** | missed |
| CASE60 | C10H18O | 11 | DEPT, HSQC(ED), HMBC, COSY, NOESY, 1H, 13C | **rank 1** | **rank 1** |
| CASE61 | C16H20O2 | 18 | 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, 1H | missed | missed |
| CASE62 | C22H29NO2 | 25 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | **rank 1** | missed |
| CASE63 | C24H29NO3 | 28 | 1H, 13C, HSQC(ED), HMBC, COSY, NOESY, DEPT | missed | missed |
| CASE64 | C22H27NO2 | 25 | 1H, 13C, HSQC(ED), HMBC, COSY, NOESY, DEPT | no result | missed |
| CASE65 | C24H31NO3 | 28 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | missed | missed |
| CASE66 | C22H25NO2 | 25 | 1H, 13C, HSQC(ED), HMBC, COSY, NOESY, DEPT | no result | missed |
| CASE67 | C22H27NO2 | 25 | 1H, 13C, HSQC(ED), HMBC, COSY, NOESY | no result | missed |
| CASE68 | C18H24O3 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | missed | missed |
| CASE69 | C9H12O2 | 11 | 13C, 1H, COSY, HMBC, HSQC(ED) | **rank 1** | missed |
| CASE70 | C22H34O4 | 26 | 13C, 1H, DEPT, COSY, HMBC, HSQC(ED), NOESY | **rank 1** | missed |
| CASE71 | C10H14O | 11 | 13C, 1H, COSY, HMBC, HSQC(ED) | **rank 1** | **rank 1** |
| CASE72 | C10H16O2 | 12 | 13C, 1H, COSY, HMBC, HSQC(ED) | **rank 1** | missed |
| CASE73 | C19H24O6 | 25 | 13C, 1H, COSY, HMBC, HSQC(ED) | **rank 1** | missed |
| CASE74 | C21H23F3O7 | 31 | 13C, 1H, COSY, HMBC, HSQC(ED) | **rank 1** | missed |
| CASE75 | C25H32O7 | 32 | 13C, 1H, TOCSY, HSQC(ED), HMBC | **rank 1** | top 10 (rank 5) |
| CASE76 | C12H16O4 | 16 | 13C, DEPT, 1H, TOCSY, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE77 | C17H14O7 | 24 | 13C, 1H, HSQC(ED), HMBC | missed | missed |
| CASE78 | C13H18O4 | 17 | 13C, 1H, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE79 | C22H20O13 | 35 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | top 10 (rank 3) | missed |
| CASE80 | C21H20O10 | 31 | 1H, HMBC, 13C, HSQC(ED) | **rank 1** | **rank 1** |
| CASE81 | C15H10O7 | 22 | 1H, 13C, HSQC(ED), HMBC, COSY | **rank 1** | **rank 1** |
| CASE82 | C21H20O10 | 31 | 1H, HMBC, 13C, HSQC(ED) | **rank 1** | **rank 1** |
| CASE83 | C15H14O7 | 22 | 1H, 13C, DEPT, NOESY, HSQC(ED), HMBC, COSY | **rank 1** | **rank 1** |
| CASE84 | C15H12O7 | 22 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE85 | C15H12O5 | 20 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE86 | C21H20O12 | 33 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | missed |
| CASE87 | C21H20O10 | 31 | 1H, 13C, HSQC(ED), HMBC, COSY | **rank 1** | **rank 1** |
| CASE88 | C15H10O4 | 19 | 1H, HMBC, 13C, HSQC(ED) | **rank 1** | **rank 1** |
| CASE89 | C21H20O12 | 33 | 1H, 13C, HSQC(ED), HMBC, COSY | **rank 1** | **rank 1** |
| CASE90 | C15H10O5 | 20 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE91 | C15H10O6 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE92 | C15H10O6 | 21 | 1H, 13C, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE93 | C21H20O12 | 33 | 1H, HMBC, 13C, DEPT, HSQC(ED) | no result | **rank 1** |
| CASE94 | C15H10O7 | 22 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE95 | C21H20O11 | 32 | 1H, 13C, DEPT, HSQC(ED), HMBC | no result | **rank 1** |
| CASE96 | C16H12O7 | 23 | 1H, 13C, DEPT, HSQC(ED), HMBC | no result | missed |
| CASE97 | C15H12O6 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE98 | C15H10O8 | 23 | 1H, 13C, DEPT, NOESY, HSQC(ED), HMBC, COSY | **rank 1** | **rank 1** |
| CASE99 | C15H10O5 | 20 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE100 | C15H14O6 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE101 | C15H12O6 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC | top 10 (rank 3) | **rank 1** |
| CASE102 | C15H10O5 | 20 | 1H, 13C, DEPT, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE103 | C21H20O11 | 32 | 1H, 13C, DEPT, HSQC(ED), HMBC | no result | top 10 (rank 2) |
| CASE104 | C15H10O6 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC | top 10 (rank 3) | — |
| CASE105 | C26H32N6O7 | 39 | 1H, 13C, HSQC(ED), HMBC | **rank 1** | **rank 1** |
| CASE106 | C15H14O | 16 | NOESY, APT/JMOD, COSY, HSQC(ED), HMBC, 1H, 13C | **rank 1** | — |
| CASE107 | C15H24O2 | 17 | 13C, 1H, COSY, DEPT, HMBC, HSQC | top 10 (rank 7) | — |
| CASE108 | C20H30O2 | 22 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE109 | C10H12O | 11 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE110 | C10H16O | 11 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE111 | C10H18O | 11 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE112 | C8H9IO2 | 11 | 1H, APT/JMOD, HMQC, HMBC | **rank 1** | — |
| CASE113 | C22H25NO6 | 29 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE114 | C15H22O5 | 20 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE115 | C20H20O7 | 27 | 1H, APT/JMOD, NOESY, HSQC(ED), HMBC | top 10 (rank 2) | — |
| CASE116 | C17H21NO4 | 22 | 1H, COSY, NOESY, HSQC(ED), HMBC, APT/JMOD | **rank 1** | — |
| CASE117 | C20H24N2O2 | 24 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE118 | C10H16O | 11 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE119 | C30H50O | 31 | 1H, COSY, DEPTQ, HSQC, HMBC | **rank 1** | — |
| CASE120 | C29H48O | 30 | 1H, COSY, DEPTQ, HSQC, HMBC | no result | — |
| CASE121 | C30H30O8 | 38 | 13C, 1H, COSY, HMBC, HSQC(ED) | **rank 1** | — |
| CASE122 | C18H32O16 | 34 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE123 | C8H15N | 9 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE124 | C10H12O2 | 12 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE125 | C18H16O8 | 26 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE126 | C10H18O | 11 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE127 | C16H18O10 | 26 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE128 | C6H13NO5 | 12 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE129 | C21H22N2O2 | 25 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC, 13C | **rank 1** | — |
| CASE130 | C10H16 | 10 | 1H, APT/JMOD, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE131 | C10H14N2 | 12 | 1H, APT/JMOD, 13C, COSY, NOESY, HMBC, HSQC | **rank 1** | — |
| CASE132 | C17H21NO3 | 21 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE133 | C14H16 | 14 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE134 | C16H12O5 | 21 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE135 | C15H26O | 16 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE136 | C10H6O3 | 13 | 1H, APT/JMOD, COSY, NOESY, HSQC, HMBC | **rank 1** | — |
| CASE137 | C12H22O11 | 23 | 1H, 13C, NOESY, HSQC(ED), HMBC | top 10 (rank 6) | — |
| CASE138 | C30H50O2 | 32 | APT/JMOD, COSY, NOESY, HSQC, HMBC, 2D-OTHER | **rank 1** | — |
| CASE139 | C20H26O7 | 27 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE140 | C21H20O6 | 27 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE141 | C21H30O2 | 23 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE142 | C7H10O5 | 12 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE143 | C6H8O2 | 8 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE144 | C12H20O8 | 20 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE145 | C6H8O2 | 8 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE146 | C12H16O7 | 19 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE147 | C32H48O5 | 37 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE148 | C18H21NO5 | 24 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE149 | C27H39NO8 | 36 | 1H, 13C, DEPT, COSY, HSQC, HMBC, NOESY | no result | — |
| CASE150 | C27H42O3 | 30 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE151 | C10H12O4 | 14 | 1H, APT/JMOD, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE152 | C21H22O7 | 28 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE153 | C21H20O7 | 28 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE154 | C20H18O6 | 26 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE155 | C21H20O6 | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE156 | C21H20O6 | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE157 | C20H20O6 | 26 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE158 | C20H20O7 | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE159 | C20H18O5 | 25 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE160 | C21H22O7 | 28 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE161 | C20H28O3 | 23 | 1H, COSY, HSQC(ED), HMBC, 13C, DEPT | **rank 1** | missed |
| CASE162 | C20H32O4 | 24 | 1H, COSY, HSQC(ED), HMBC, 13C, DEPT | **rank 1** | — |
| CASE163 | C20H28O | 21 | 1H, COSY, HSQC(ED), HMBC, 13C | **rank 1** | — |
| CASE164 | C20H30O | 21 | 1H, COSY, HSQC(ED), HMBC, 13C, 2D-OTHER, NOESY | **rank 1** | — |
| CASE165 | C20H30O3 | 23 | 1H, COSY, HSQC(ED), HMBC, 13C, DEPT | **rank 1** | — |
| CASE166 | C20H30O3 | 23 | 1H, COSY, HSQC(ED), HMBC, 13C, 2D-OTHER, NOESY | **rank 1** | — |
| CASE167 | C20H30O4 | 24 | 1H, COSY, HSQC(ED), HMBC, 13C, DEPT, NOESY | **rank 1** | — |
| CASE168 | C20H30O3 | 23 | 1H, COSY, HSQC(ED), HMBC, 13C, 2D-OTHER | missed | — |
| CASE169 | C30H50O5 | 35 | 1H, HSQC(ED), HMBC, COSY, 13C, 2D-OTHER | no result | — |
| CASE170 | C31H52O3 | 34 | 1H, HSQC(ED), HMBC, COSY, 13C, 2D-OTHER | no result | — |
| CASE171 | C31H52O4 | 35 | 1H, HSQC(ED), HMBC, 13C, COSY, 2D-OTHER | no result | — |
| CASE172 | C30H50O3 | 33 | 1H, HSQC(ED), HMBC, COSY, 13C, 2D-OTHER | **rank 1** | — |
| CASE173 | C31H52O5 | 36 | 1H, HSQC(ED), HMBC, COSY, 13C, 2D-OTHER | no result | — |
| CASE174 | C21H19NO8 | 30 | 1H, 2D-OTHER, COSY, HSQC, HMBC, DEPT, 13C | missed | — |
| CASE175 | C17H9ClO7 | 25 | 1H, 13C, DEPT, COSY, HSQC, HMBC | missed | missed |
| CASE176 | C30H39NO5 | 36 | 13C, 1H, COSY, DEPT, HMBC, HSQC | missed | — |
| CASE177 | C23H28O4 | 27 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE178 | C17H14O7 | 24 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE179 | C23H22O7 | 30 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE180 | C17H12O6 | 23 | 1H, 13C, HSQC(ED), HMBC, NOESY, COSY | missed | — |
| CASE181 | C21H20O6 | 27 | 1H, 13C, COSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE182 | C24H28O4 | 28 | 1H, 13C, COSY, NOESY, HSQC(ED), HMBC | top 10 (rank 2) | — |
| CASE183 | C7H14O6 | 13 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE184 | C21H22O4 | 25 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE185 | C23H22O7 | 30 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE186 | C23H22O6 | 29 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE187 | C23H22O7 | 30 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE188 | C22H24O3 | 25 | 1H, 13C, HSQC(ED), HMBC, NOESY, COSY | **rank 1** | — |
| CASE189 | C22H26O4 | 26 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE190 | C15H12O4 | 19 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE191 | C31H40O5 | 36 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | missed | — |
| CASE192 | C20H20O4 | 24 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE193 | C17H14O6 | 23 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE194 | C16H12O6 | 22 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE195 | C16H12O5 | 21 | 1H, 13C, COSY, TOCSY, NOESY, HSQC(ED), HMBC | **rank 1** | — |
| CASE196 | C20H32O3 | 23 | 1H, 13C, DEPT, COSY, HMBC, NOESY, HSQC(ED) | **rank 1** | — |
| CASE197 | C20H32O3 | 23 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC | missed | — |
| CASE198 | C25H40O4 | 29 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC | missed | — |
| CASE199 | C23H34O4 | 27 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE200 | C23H34O5 | 28 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | no result | — |
| CASE201 | C23H36O5 | 28 | 1H, 13C, DEPT, COSY, HMBC, HSQC(ED), NOESY | **rank 1** | — |
| CASE202 | C29H40N2O6 | 37 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | missed | — |
| CASE203 | C28H38N2O4 | 34 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | missed | — |
| CASE204 | C23H34O5 | 28 | 1H, 13C, DEPT, COSY, HMBC, NOESY, HSQC(ED) | no result | — |
| CASE205 | C22H32O5 | 27 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | no result | — |
| CASE206 | C23H33BrO5 | 29 | 1H, 13C, DEPT, COSY, HMBC, HSQC(ED) | **rank 1** | — |
| CASE207 | C29H38N2O6 | 37 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | no result | — |
| CASE208 | C28H37N3O8 | 39 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | no result | — |
| CASE209 | C23H34O3 | 26 | 1H, 13C, DEPT, COSY, HMBC, HSQC(ED), NOESY | no result | — |
| CASE210 | C23H35BrO5 | 29 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | missed | — |
| CASE211 | C28H36N2O4 | 34 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC | no result | — |
| CASE212 | C23H33NO9 | 33 | 1H, 13C, DEPT, COSY, HMBC, HSQC(ED), NOESY | missed | — |
| CASE213 | C23H32O5 | 28 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC, NOESY | no result | — |
| CASE214 | C23H34O8 | 31 | 1H, HMBC, HSQC(ED), 13C, DEPT, COSY, NOESY | missed | — |
| CASE215 | C20H24O4 | 24 | 1H, 13C, HSQC(ED), HMBC, COSY, NOESY | missed | — |
| CASE216 | C21H22O4 | 25 | 1H, 13C, COSY, HSQC(ED), HMBC, NOESY | **rank 1** | — |
| CASE217 | C2H6 | 2 | 1H, 13C, HSQC(ED), HMBC, COSY, TOCSY, NOESY | — | no result |
| CASE218 | C8H10N4O2 | 14 | 13C, HSQC(ED), HMBC, COSY, NOESY, 1H | **rank 1** | — |
| CASE219 | C15H21N3O2 | 20 | 1H, 13C, DEPT, COSY, HSQC, HMBC, 2D-OTHER, TOCSY, NOESY, DEPTQ | **rank 1** | — |
| CASE220 | C20H27FN2O3 | 26 | 1H, 13C, COSY, HSQC(ED), HMBC | top 10 (rank 8) | — |
| CASE221 | C25H24N2O2 | 29 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE222 | C21H30N2O | 24 | 1H, HMBC, 13C, COSY, HSQC(ED) | **rank 1** | — |
| CASE223 | C22H24N4O | 27 | 13C, COSY, HSQC(ED), 1H, HMBC | **rank 1** | — |
| CASE224 | C21H29FN2O3 | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE225 | C20H28FN3O3 | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE226 | C22H31FN2O3 | 28 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE227 | C24H23FN2O | 28 | 1H, 13C, COSY, HSQC(ED), HMBC | no result | — |
| CASE228 | C21H24N4O2 | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE229 | C21H31N3O3 | 27 | 1H, HSQC(ED), HMBC, COSY, 13C | **rank 1** | — |
| CASE230 | C25H24FNO | 28 | 1H, COSY, HSQC(ED), HMBC, 13C, HSQC | **rank 1** | — |
| CASE231 | C22H30N2O3 | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE232 | C22H24FN3O3 | 29 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE233 | C24H22FNO2 | 28 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE234 | C22H23FN2O3 | 28 | 1H, COSY, HMBC, HSQC(ED), 13C | **rank 1** | — |
| CASE235 | C23H27FN2O | 27 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE236 | C20H27N3O3 | 26 | 1H, COSY, HSQC(ED), HMBC, 13C | **rank 1** | — |
| CASE237 | C23H30ClN3O | 28 | HSQC(ED), 1H, 13C, COSY, HMBC | **rank 1** | — |
| CASE238 | C20H19FINO | 24 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE239 | C21H22FN3O3 | 28 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE240 | C18H26N4O2 | 24 | 1H, HMBC, HSQC(ED), COSY, 13C | **rank 1** | — |
| CASE241 | C17H19N3O4 | 24 | 1H, 13C, COSY, HSQC(ED), HMBC, HSQC, 2D-OTHER | **rank 1** | — |
| CASE242 | C16H25N3O4 | 23 | 1H, 13C, COSY, HSQC(ED), HMBC, NOESY | missed | — |
| CASE243 | C19H23N3O4 | 26 | 1H, 13C, COSY, HSQC(ED), HMBC, NOESY, HSQC | top 10 (rank 2) | — |
| CASE244 | C12H17N3O4 | 19 | 1H, COSY, HSQC(ED), HMBC, HSQC, 2D-OTHER, 13C, NOESY | **rank 1** | — |
| CASE245 | C30H26O6 | 36 | 13C, 1H, COSY, HMBC, HSQC(ED), NOESY | no result | — |
| CASE246 | C31H30O7 | 38 | 13C, 1H, COSY, HMBC, HSQC(ED), NOESY | **rank 1** | — |
| CASE247 | C31H30O6 | 37 | 13C, 1H, COSY, HMBC, HSQC(ED), NOESY | **rank 1** | — |
| CASE248 | C10H14O2 | 12 | 1H, 13C, DEPT, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE249 | C18H20N2 | 20 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE250 | C12H9IO | 14 | 1H, 13C, COSY, HSQC(ED), HMBC, NOESY | **rank 1** | **rank 1** |
| CASE251 | C12H16O3 | 15 | 1H, 13C, DEPT, HMBC, HSQC(ED), NOESY, COSY | **rank 1** | **rank 1** |
| CASE252 | C12H12O5 | 17 | 1H, 13C, COSY, HSQC(ED), HMBC | **rank 1** | — |
| CASE253 | C10H20O | 11 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | **rank 1** | — |
| CASE254 | C12H22O2 | 14 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, TOCSY | **rank 1** | top 10 (rank 2) |
| CASE255 | C24H38O4 | 28 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, TOCSY | **rank 1** | — |
| CASE256 | C19H28O3 | 22 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, TOCSY | **rank 1** | — |
| CASE257 | C24H36O4 | 28 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | missed | — |
| CASE258 | C19H30O3 | 22 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, TOCSY | top 10 (rank 2) | — |
| CASE259 | C19H30O3 | 22 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, TOCSY | missed | — |
| CASE260 | C19H26O2 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, TOCSY | **rank 1** | — |
| CASE261 | C19H26O3 | 22 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY, TOCSY | top 10 (rank 3) | — |
| CASE262 | C19H26O2 | 21 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | missed | — |
| CASE263 | C24H34O4 | 28 | 1H, 13C, DEPT, HSQC(ED), HMBC, COSY, NOESY | missed | — |
| CASE264 | C19H26O3 | 22 | 1H, 13C, COSY, NOESY, HSQC(ED), HMBC, TOCSY | found (rank 12) | — |
