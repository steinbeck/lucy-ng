# CASE budget-forced ranking — design

**Date:** 2026-08-10
**Status:** approved, not yet implemented
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

## Verification

Retrospective, without launching a single CASE run: rank CASE80's
`probe_C.smi` (283 solutions) with the shifts from its own
`analysis/peaks/` pick and check whether the ground-truth InChIKey — from
`downloaded_datasets.tsv`, as `grade_blind.py` uses it — appears in the set.

- Truth present → the mechanism would have rescued this case; proceed.
- Truth absent → it saves the wall-clock but not the result. Still worth having,
  but the expected benefit is smaller and should be stated plainly rather than
  assumed.

Run the same check for CASE48 and CASE98 where a converted set under 2000 exists.

There are no unit tests here — these files are prompt text, not code. The
mechanism is verified by the retrospective check above and, once implemented, by
re-running the three failures under the new skill.

## Out of scope

- Harness-side nudges before the timeout. The skill change is the fix; the
  existing resume-backstop stays as it is.
- Any change to the ranking algorithm, the QC gate, or the LSD constraint logic.
- Re-running the 155 outstanding benchmark datasets. That decision waits until
  this mechanism is measured (see `CASE-UAT-LOG.md`, 2026-08-09 entry).
