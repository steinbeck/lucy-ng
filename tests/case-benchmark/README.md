# CASE blind-UAT harness

Runs `/lucy-ng:case` **blind** on sanitised NMR datasets at scale, in isolated
**headless** `claude` processes, and grades each run's structure against a
ground-truth table with RDKit — so a run's correctness is verified automatically,
not by eye.

It replaces the previous semi-manual harness (`prepare-run.sh` → *"open a Claude
Code session and run…"* → `archive-run.sh`), which could not be driven
unattended and graded only by a crude SMILES grep with no ground-truth check.

## Why "blind"

The whole point of CASE UAT is that the solver must derive the structure from
NMR + molecular formula alone. Any leak of the answer invalidates the result, so:

- Each dataset is solved in a **fresh `claude` process** (empty conversation
  context) whose prompt contains **only** the dataset path + the molecular
  formula (read from the dataset's own `molecular-formula.txt` /
  `molecularformula.txt`).
- The process runs in a **neutral scratch cwd** (no project memory) and a
  system-prompt fence forbids reading any ground-truth / answer-key location.
- Optional **hard lockout**: the batch driver can physically move the
  ground-truth files out of reach for the whole run (`CASE_ANSWERKEY_PATHS`),
  restoring them afterward — belt-and-suspenders on top of the fence.
- **Grading is a separate step** (`grade_blind.py`), run *after* the batch with
  the ground truth restored. Solving and grading never share a process.

## Scripts

| Script | Role |
|--------|------|
| `blind_case_run.sh <CASE_DIR> <RESULTS_DIR> [full\|smoke]` | One blind run. Fresh headless `claude -p "/lucy-ng:case …"`, resume-on-stall backstop, relocates `analysis/` into the results dir, writes `meta.json`. `smoke` = 1-iteration pipeline check. |
| `blind_case_batch.py [--all \| CASE… ] -k N --mode full` | Drives many datasets with concurrency `N`, resumable (skips done), optional answer-key lockout, writes `summary.tsv`. |
| `grade_blind.py [--results DIR]` | Extracts each run's top structure, computes InChIKey (RDKit), compares to ground truth → `SOLVED_TOP1` / `CORRECT_RANK_n` / `WRONG` / `NO_RESULT`. Writes `scorecard.tsv`. |

## Requirements

- `claude` CLI (headless `-p`, agent-teams). The batch sets
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
- `lucy` on `PATH` (or a `.venv/bin` in the repo root — auto-added).
- `grade_blind.py` needs **RDKit**: `pip install rdkit`.

## Configuration (env vars)

| Var | Used by | Meaning |
|-----|---------|---------|
| `CASE_DATA_DIR` | batch | **required** — dir holding the `CASE<name>/` dataset folders |
| `CASE_RESULTS_DIR` | all | results root (default: `./results`, gitignored) |
| `CASE_PROJECT_DIR` | run | lucy-ng repo root for `.venv/bin` (default: this repo) |
| `CLAUDE_MODEL` | run | model id (default `claude-opus-4-8`) |
| `CASE_GROUNDTRUTH` | grade | **required for grading** — TSV path (see below); never committed |
| `CASE_ANSWERKEY_PATHS` | batch | optional `:`-separated files/dirs to hard-lock during the batch |
| `CASE_STASH_DIR` | batch | where locked-out paths are stashed (default `~/.case-uat-stash`) |
| `CASE_RUN_MAX_ATTEMPTS` / `CASE_RUN_CALL_TIMEOUT` / `CASE_RUN_DEADLINE_S` | run | resume-loop bounds (defaults 8 / 3600 / 9000) |

### Ground-truth TSV (`CASE_GROUNDTRUTH`)

Tab-separated, header row; needs at least a case column (`case` or
`case_folder`) and an `inchikey` column; optional `name`:

```
case	inchikey	name
CASE1	AAAAAAAAAAAAAA-BBBBBBBBBB-C	<trivial name>
```

(The row above is a format placeholder, not a real mapping.) Keep this file
**outside the repo** — it is the answer key.

## Typical run

```bash
export CASE_DATA_DIR=/path/to/datasets
export CASE_GROUNDTRUTH=/path/to/truth.tsv          # for grading, kept private
export CASE_ANSWERKEY_PATHS=$CASE_GROUNDTRUTH       # optional hard lockout

python tests/case-benchmark/blind_case_batch.py --all -k 3 --mode full
python tests/case-benchmark/grade_blind.py         # after the batch restores truth
```

`results/` is gitignored — run outputs, `timing.json`, `CASE-PROGRESS.md`,
`scorecard.tsv` (blind-sensitive) stay local and are never committed.
