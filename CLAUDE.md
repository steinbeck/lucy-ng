# lucy-ng

AI-agent powered Computer-Assisted Structure Elucidation (CASE) for organic natural products from NMR. This repository is the Python package.

> **Scope of this file:** developer/maintainer context for working **inside this repo** — it is the project memory loaded when you open Claude Code in the lucy-ng repo. It is **not** loaded during a CASE run (those run from NMR data directories outside this repo, so only `~/.claude/CLAUDE.md` and any CLAUDE.md in the data tree apply there). The CASE workflow itself — orchestrator, team agents, references — lives under `.claude/` (see *CASE skill location* below). Do **not** put operational/skill instructions here; they belong with the skill.

---

## Developer Reference

### Commands

```bash
pytest                    # run tests
pytest --cov=lucy_ng      # with coverage
mypy src/lucy_ng          # type checking (strict mode)
ruff check src tests      # linting
hatch build               # build package
```

### Local prerequisites

Needed to run the full test suite and the dereplication/prediction paths locally:

- **LSD solver** — `lucy lsd check` must report both `LSD` and `outlsd` on PATH. Download from http://eos.univ-reims.fr/LSD/, extract, add the `bin/` directory to PATH.
- **Reference database** — `lucy database download` fetches the pre-built SQLite DB (~830 MB compressed → ~2.8 GB) to `data/reference/lucy-ng-derep.db`. Verify with `lucy database info data/reference/lucy-ng-derep.db`. See *Database Reference* below.
- **NMRPipe + SMILE** — `lucy nus check` must report the backend `available` (and the new platform section clear of critical issues). Install NMRPipe (native `mac11_arm64`/Linux build) **and** the separate SMILE companion plugin (`plugin.smile.tZ`) from https://www.ibbr.umd.edu/nmrpipe/install, source its environment script, add `bin/` to PATH. See `docs/NUS-PORTABILITY.md` for the full per-platform matrix (macOS-arm64-native / Linux-native / Windows-WSL2-gap).

### Project structure

```
src/lucy_ng/
├── models/          # Pydantic v2 data models (Spectrum1D/2D, Peak1D, …)
├── readers/         # NMR file readers (BrukerReader)
├── processing/      # peak picking, signal processing
├── detection/       # statistical detection (hybridisation, neighbours, HHB)
├── analysis/        # symmetry / signal-grouping analysis
├── dereplication/   # formula-indexed compound DB matching
├── prediction/      # HOSE-code 13C shift prediction
├── ranking/         # candidate solution ranking
├── lsd/             # LSD solver integration
├── fragments/       # bundled LSD fragment / ring-exclusion filter files
├── cli/             # `lucy` Click CLI (all subcommands; every one supports --format json)
└── …                # database, visualization, nmrxiv, solvers, data
tests/               # pytest suite
data/                # local test NMR datasets (Bruker format)
.claude/             # CASE skill + team agents (symlinked into ~/.claude) — see below
.planning/           # GSD planning files (PROJECT.md, ROADMAP.md, STATE.md, phases/)
docs/                # human docs (ARCHITECTURE, USER_GUIDE, …); docs/infographics/ = editable project slide deck (regenerate via build.py — see its README)
```

The package exposes a `lucy` CLI; every subcommand supports `--format json`. Command and flag definitions live in `src/lucy_ng/cli/` — use `lucy --help` rather than duplicating a command catalogue here.

### Critical Architecture Decisions

#### HOSE Codes: NO Explicit Hydrogens

**All HOSE code operations MUST use molecules WITHOUT explicit hydrogens.**

This is critical for consistency between database generation and prediction. Using inconsistent hydrogen handling causes 100% prediction failures.

| Operation | Correct Approach |
|-----------|------------------|
| Database generation | Read SDF → do NOT call `AddHs()` → generate HOSE |
| Prediction from SMILES | `MolFromSmiles()` (implicit H) → generate HOSE |
| Prediction from MOL | `MolFromMolBlock(removeHs=True)` → generate HOSE |

```python
# CORRECT - no explicit H
mol = Chem.MolFromSmiles("CCO")  # 3 atoms
hose = generate_for_atom(mol, 0, radius=1)  # "C-4;C(//)"

# WRONG - causes mismatch
mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))  # 9 atoms
hose = generate_for_atom(mol, 0, radius=1)  # "C-4;HHHC(//)" - WON'T MATCH!
```

#### COCONUT Atom Indices: 1-Based

COCONUT SDF files use **1-based** atom indices in the `CNMR_SHIFTS` field. When parsing, convert to 0-based for RDKit:

```python
atom_idx_0based = int(atom_idx_from_coconut) - 1
```

---

## Database Reference

The pre-built SQLite database powers **both** dereplication (formula-indexed compound lookup) and 13C prediction (HOSE-based shift calculation):

| Property | Value |
|----------|-------|
| **DOI** | [10.6084/m9.figshare.31073554](https://doi.org/10.6084/m9.figshare.31073554) |
| **Compounds** | 928,443 (COCONUT + NMRShiftDB) |
| **HOSE Statistics** | 7.9M entries for 13C prediction |
| **Formulas** | 111,493 unique |
| **Size** | ~830 MB download, ~2.8 GB uncompressed |

---

## CASE skill location (maintenance pointer — not documented here)

The autonomous CASE workflow lives under `.claude/` in this repo and is symlinked into `~/.claude` (so it loads as a Claude Code skill globally):

- `.claude/commands/lucy-ng/` — the `/lucy-ng:*` commands: orchestrator `case.md` + `references/`, plus `dereplicate`/`predict`/`sanitise`/`status`/routing.
- `.claude/agents/lucy-*.md` — the specialist team spawned by `case.md` (`lucy-nmr-chemist`, `lucy-lsd-engineer`, `lucy-solution-analyst`, `lucy-devils-advocate`) and `lucy-diagnostic` (escalation only).

Edit those files to change CASE behaviour. A **fresh Claude Code session** is required to reload edited agents/commands. All operational and domain-strategy knowledge belongs there — keep this CLAUDE.md free of it.

---

## Infographic deck (keep in sync at milestone close)

`docs/infographics/` holds the project slide deck (7× 16:9, for talking to colleagues). It bakes in **project facts** — the CASE1–9 test-set structures + solved status, the agent-team roster, and the headline numbers (DB size, HOSE/fragment counts, test count, milestones shipped).

**Recurring maintenance:** when those facts change — most commonly at **milestone close** (`/gsd-complete-milestone`), or when a CASE test result flips solved↔partial — refresh the deck so it does not go stale:

1. Update the ground truth first in its source (`.planning/CASE-DATASET-IDENTITIES.md`, `PROJECT.md`, `STATE.md`).
2. Mirror the changed values into `docs/infographics/build.py` (and `gen_structures.py` if a molecule changed).
3. Rebuild: `cd docs/infographics && python build.py` (+ optional PDF export — see its `README.md`).

The deck is generated: **edit `build.py`, never `deck.html`.** Full build/edit instructions live in `docs/infographics/README.md`.
