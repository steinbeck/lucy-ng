# CASE budget-forced ranking — design

**Date:** 2026-08-10
**Status:** design approved, **expected benefit downgraded** — see *Verification result*
before implementing. This mechanism does not improve the hit rate; it converts
empty runs into reported ones and saves wall-clock.
**Scope:** `.claude/commands/lucy-ng/case.md`, `.claude/agents/lucy-lsd-engineer.md`, `.claude/agents/lucy-solution-analyst.md`

## Problem

A CASE run can burn its entire wall-clock budget and produce nothing. In the paired
Opus-5 benchmark (2026-08-08/09) three of fifteen runs ended with
`final_results: false` after the full 10801 s deadline: CASE48 (C29H46O4),
CASE80 (C21H20O10), CASE98 (C15H10O8). Claude 4.8 finished the same three cases
in 3778–5874 s, two of them *correctly* (CASE80 rank 2, CASE98 top-1).

This is not a chemistry defect. It is a stopping defect: the workflow keeps
refining where it should cut off and rank what it has.

### Why the existing stopping conditions do not fire

`lucy-lsd-engineer.md` already has stopping conditions, but all of them count
iterations:

```
5. Repeat until: >= 1 plausible solution, all HMBC added + ELIM escalated to N=3, or 10 iterations (cap)

### Convergence Stall
3 consecutive iterations with <10% reduction AND >50 solutions: stop adding correlations. Rank current solutions with caveat.
```

| case | iterations in 180 min | why no brake fired |
|---|---|---|
| CASE80 | 2 | the 10-iteration cap is unreachable; Convergence Stall needs 3 iterations |
| CASE98 | 4 | counts jumped (664 → 0 → 0 → 3687 → 9806), never "<10 % reduction" |
| CASE48 | 8 family runs | same: 24564 → 39292 → 18140 |
| CASE85 (success) | 6 in 56 min | converged on its own |

When a single iteration takes hours, iteration counting is the wrong unit, and
"<10 % reduction" never triggers on counts that jump rather than stagnate.

### What was already on disk

CASE80's `analysis/iteration_02/probes/probe_C.smi` holds **283 converted,
rankable solutions**, written at 20:27 and never used, while the agent kept
working on a 473894-solution set. That set has no `solutions.smi` at all — only
a 607 MB `compound.sol`. At half a million solutions the SMILES conversion never
ran.

Two consequences for the design: a fallback set must be **converted**, not merely
solved; and it must be captured from **any** solver run in the case — main
iteration, per-family run, or probe — because CASE80's only rankable set came
from a probe.

## Design

Split along what each participant already knows: the engineer knows its solution
sets, the coordinator owns the clock.

### 1. Budget

`CASE_TIME_BUDGET_MIN` (integer, minutes). Default **120** when unset.

The coordinator reads it once at `run_start` and records it as the first
`timing.jsonl` entry, alongside the `run_start` stamp it already writes
(`case.md:355`). Elapsed time is `now - run_start`, both from `date -u +%s` —
the same clock source already in use, so no new mechanism.

The benchmark harness sets it from `CASE_RUN_DEADLINE_S` so skill and harness can
never disagree. That disagreement is the present failure: the deadline lives only
in `blind_case_run.sh` and the agent knows nothing about it.

### 2. Fallback set (engineer)

After every solver run that yields solutions — main iteration, per-family run, or
probe — the engineer:

1. reads the count from the run's `solncounter` file and skips the step entirely
   if it exceeds **2000** (no conversion attempt, no write). `solncounter` is
   written by LSD before any SMILES conversion — CASE80's `iteration_02` has
   `solncounter` = 473894 next to a `compound.sol` and no `solutions.smi`, which
   is exactly the case this check must catch cheaply;
2. otherwise converts to SMILES as it already does;
3. writes the result to `analysis/best_so_far.smi` **only if** its count is lower
   than the count recorded in `analysis/best_so_far.json`, or that file is absent;
4. writes `analysis/best_so_far.json` alongside it:

```json
{
  "count": 283,
  "source": "iteration_02/probes/probe_C_oxygenation",
  "constraints": "5/26 HMBC, ELIM 0, ring3+ring4 excluded",
  "stamped_utc": "2026-08-08T18:27:11Z"
}
```

The 2000 threshold is measured, not guessed. `lucy lsd rank` processes 20–24
solutions/s (70 → 4 s, 213 → 9 s, 17698 → timeout > 420 s), so 2000 costs about
85 s. Every real successful ranking in the benchmark was below 1000 (CASE13: 102,
CASE175: 177, CASE96: 839).

This reuses the existing union pattern (`lucy-lsd-engineer.md:263`,
`analysis/union_solutions.smi`) — same idea across iterations instead of across
multiplicity families.

### 3. Trigger (coordinator)

At each phase boundary — where it already stamps `timing.jsonl` — the coordinator
computes `elapsed / budget`. At **≥ 70 %** it enters a consolidation stage:

- no *new* LSD runs are dispatched. An LSD run already in flight is left to
  finish — killing it would waste the work and, if it converges, its set is the
  best available. Its result still goes through the step-2 capture, so a late
  small set can replace the fallback before ranking;
- the solution analyst ranks `analysis/best_so_far.smi`;
- the report is written and the run ends normally.

The remaining 30 % is the reserve for ranking, gates and reporting. On the
benchmark's 180 min that is 54 minutes for roughly 85 s of ranking plus checks.

Phase boundaries are the coordinator's existing checkpoints — the points where it
already stamps `timing.jsonl` between workflow stages, not a new polling loop. A
long single LSD run can therefore overshoot 70 % before the next check. The
reserve absorbs this: even a full extra hour of overshoot leaves time to rank and
report.

### 4. Labelling

`final_results.md` carries a visible `budget-forced ranking` marker stating which
iteration the set came from and which constraints were in force, and confidence
is capped — a forced ranking is a different epistemic state from real
convergence. The grading harness must be able to tell them apart; without the
marker a forced result would be scored as if the run had converged.

### 5. No fallback available

If no `best_so_far.smi` exists at 70 %, nothing is forced. The coordinator writes
an honest report without a structure: what was attempted, what failed, which sets
stayed too large. That is still more than today's empty result, and it keeps the
run from inventing a ranking over a set it never had.

## Verification result (run 2026-08-10)

The retrospective check was run before implementing. It came out **negative**, and
the expected benefit must be restated accordingly.

Method: for each case, compute the first InChIKey block of every converted SMILES
on disk and compare against the ground truth in `downloaded_datasets.tsv` — the
same comparison `grade_blind.py` makes. Positive control on three solved cases
(CASE85, CASE13, CASE69) finds the truth every time, so the method is sound.

Fallback sets existed everywhere — CASE48 `top_candidates.smi` (500), CASE98
`ranking/survivors_final.smi` (215), CASE46 `shortlist.smi` (460), CASE80
`probe_C.smi` (283). None contains the truth. Widening the search to *every*
converted solution in the case directory:

| case | SMILES checked | truth in search space |
|---|---|---|
| CASE175 | 600707 | no |
| CASE48 | 192125 | no |
| CASE98 | 30824 | no |
| CASE80 | 283 only¹ | undetermined |

¹ The 473894-solution main set was never converted (607 MB `.sol`), so it cannot
be checked.

**LSD never generated the correct structure** — not even among 600000 candidates
for CASE175. The failure is not *when* the run stops but that the constraint set
excludes the answer. This is the CASE4 defect class (a hard-coded multiplicity
model excluded the truth; fixed in Phase 88), not a stopping defect.

### What this mechanism is still worth

- Three `NO_RESULT` become three `WRONG`: a reported, ranked, caveated answer
  with its constraint provenance instead of an empty directory. Better input for
  diagnosis, and honest either way.
- Wall-clock per hard case drops from 180 to about 126 minutes — roughly 30 %
  quota saved on exactly the cases that cost the most.
- For interactive users the difference between "here is my best set, forced at
  budget, low confidence" and three hours of silence is the whole product.

### What it is NOT worth

It will not move the hit rate. Anyone reading this spec expecting the paired
benchmark's 10/15 to improve will be disappointed; the three rescued runs would
all be scored `WRONG`.

There are no unit tests here — these files are prompt text, not code. Once
implemented, verify by re-running the three failures and confirming they now
produce a labelled forced ranking within budget.

## Follow-up this verification opened

The real lever on the hit rate is upstream: **why is the truth absent from the
search space?** That is diagnosable without new runs — take the known structure,
check it against the constraint file that was actually solved, and identify which
constraint it violates. Worth its own investigation; it is not in this spec's
scope.

## Out of scope

- Harness-side nudges before the timeout. The skill change is the fix; the
  existing resume-backstop stays as it is.
- Any change to the ranking algorithm, the QC gate, or the LSD constraint logic.
- Re-running the 155 outstanding benchmark datasets. That decision waits until
  this mechanism is measured (see `CASE-UAT-LOG.md`, 2026-08-09 entry).
