# lucy-ng

**AI-Agent Powered Computer-Assisted Structure Elucidation for Organic Natural Products**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

lucy-ng determines the structure of an unknown organic natural product from its NMR
spectra. Its centrepiece is a **team of cooperating AI agents** that runs the full
Computer-Assisted Structure Elucidation (CASE) workflow autonomously — picking peaks,
extracting constraints, driving the LSD solver, ranking candidates, and critiquing its
own work — the way a group of human spectroscopists would, but unattended.

Underneath the team sits the `lucy` command-line toolkit. That toolkit does not reinvent
the science: it is largely an **integration layer around established software written by
others**, with **[LSD](https://nuzillard.github.io/LSD/) — Jean-Marc Nuzillard's structure
generator — at its core** (see [Built on LSD](#built-on-lsd-and-established-tools) below).
The genuinely novel part, and our own contribution, is the cooperative **agent team** that
drives all of it unattended.

> lucy-ng is a reference to the original *Lucy* CASE program written by the project author.
> The existence of LSD made Lucy obsolete.

---

## Table of Contents

- [Built on LSD and Established Tools](#built-on-lsd-and-established-tools)
- [The CASE Agent Team](#the-case-agent-team)
- [Running a CASE Elucidation](#running-a-case-elucidation)
- [The `lucy` CLI](#the-lucy-cli)
- [Installation](#installation)
- [Scientific Background](#scientific-background)
- [Architecture](#architecture)
- [Supported Data](#supported-data)
- [Development](#development)
- [License & Citation](#license--citation)

---

## Built on LSD and Established Tools

The hard combinatorial heart of structure elucidation — enumerating every molecular graph
consistent with the spectroscopic constraints — is done by **[LSD (Logic for Structure
Determination)](https://nuzillard.github.io/LSD/), created and maintained by Jean-Marc
Nuzillard** (Université de Reims Champagne-Ardenne, CNRS). LSD is the product of decades of
rigorous work, it builds structures purely from 2D-NMR connectivity without leaning on a
chemical-shift database, and it is the foundation without which lucy-ng simply would not
exist. **If you use lucy-ng in research, cite LSD** — see [Citation](#license--citation).

lucy-ng does not replace LSD or the other packages it relies on. It wraps and coordinates
them:

| Foundation | By | Its role in lucy-ng |
|------------|-----|---------------------|
| **LSD** | Jean-Marc Nuzillard | The structure generator — the core solver |
| **RDKit** | RDKit contributors | Cheminformatics: molecules, SMILES/InChI, substructure search |
| **nmrglue** | J. J. Helmus et al. | Reading Bruker NMR data |
| **HOSE codes** | W. Bremser (1978) | 13C shift-prediction descriptors |
| **COCONUT**, **NMRShiftDB** | their respective communities | Reference data for dereplication and prediction |

The `lucy` command-line tools are the wrappers through which these packages are driven.
**What is genuinely new here — our own contribution — is the [CASE agent team](#the-case-agent-team)**
that operates all of them end to end, unattended.

---

## The CASE Agent Team

Structure elucidation is not a single algorithm — it is an iterative, judgement-heavy
process where evidence from several spectra has to be weighed, constraints have to be
built carefully, and wrong turns have to be caught before they waste a solver run.
lucy-ng models this as a **specialist team led by an orchestrator**, rather than as one
monolithic prompt.

When you start a run, the orchestrator (`/lucy-ng:case`) spawns four specialists and
supervises them as team lead. Each owns a part of the workflow:

| Agent | Role |
|-------|------|
| 🧪 **NMR Chemist** (`lucy-nmr-chemist`) | Peak picking, multiplicity assignment, statistical detection (hybridisation, neighbours), spectral-quality assessment. Establishes the chemistry-first evidence hierarchy. |
| 🔧 **LSD Engineer** (`lucy-lsd-engineer`) | Builds LSD constraint files, runs the solver, manages the constraint inventory across iterations, adds HMBC correlations incrementally, converts solutions to structures. |
| 📊 **Solution Analyst** (`lucy-solution-analyst`) | Ranks candidate structures by 13C-shift prediction, derives and verifies identity, assesses chemical plausibility, and reports the final result. |
| 😈 **Devil's Advocate** (`lucy-devils-advocate`) | Quality gate. Validates **every** LSD file before the solver runs, checks that constraints persist across iterations, and flags loss or over-constraint — the primary defence against silent failure modes. |

A fifth agent, the **Diagnostic specialist** (`lucy-diagnostic`), is held in reserve and
called only when a run gets stuck (zero solutions or a solution explosion) and basic
intervention has failed.

### How a run unfolds

```
                       ┌─────────────────────────────┐
                       │   Orchestrator  /lucy-ng:case │
                       │   (team lead + supervision)   │
                       └──────────────┬────────────────┘
            spawns + supervises ──────┼──────────────────────────
                  │                   │                   │
        ┌─────────▼──────┐  ┌─────────▼────────┐  ┌───────▼────────┐
        │  NMR Chemist   │  │  LSD Engineer    │  │ Solution Analyst│
        │  peaks/multipl.│→ │  constraints/LSD │→ │  rank + identify │
        └────────────────┘  └─────────┬────────┘  └────────────────┘
                                       │ every LSD file
                              ┌────────▼─────────┐
                              │ Devil's Advocate  │  ← validate before each solver run
                              │  (quality gate)   │
                              └───────────────────┘
```

The orchestrator monitors progress, detects unproductive loops, intervenes with
**advisory** constraints (telling the team *what* is wrong, not *how* to fix it, so the
specialists keep their autonomy), and escalates to you only after repeated intervention
cycles fail. It never does dereplication and never short-cuts the elucidation — a CASE
run always starts from the raw spectra.

The agents live in [`.claude/`](.claude/) (`agents/lucy-*.md` and
`commands/lucy-ng/`) and are loaded as Claude Code skills.

---

## Running a CASE Elucidation

The team runs inside [Claude Code](https://claude.com/claude-code). The fastest path on a
fresh machine is the CASE-host bootstrap, which provisions Python + dependencies, the LSD
solver, the reference database, **and** the CASE commands and team agents:

```bash
git clone https://github.com/steinbeck/lucy-ng.git
cd lucy-ng
./scripts/bootstrap_case_host.sh
```

See **[docs/SERVER_BOOTSTRAP.md](docs/SERVER_BOOTSTRAP.md)** for a headless/compute-host
walkthrough.

Then, from a directory holding your Bruker NMR data, start Claude Code and run:

```
/lucy-ng:case
```

The orchestrator picks up the spectra in the current directory, asks for the molecular
formula if it cannot infer one, assembles the team, and runs to completion. Other
commands in the same family:

| Command | Purpose |
|---------|---------|
| `/lucy-ng:case` | Full autonomous CASE elucidation (the agent team) |
| `/lucy-ng:dereplicate` | Match a 13C spectrum against the reference database |
| `/lucy-ng:predict` | Predict 13C shifts for a candidate SMILES |
| `/lucy-ng:sanitise` | Strip identifiers from a dataset for blind evaluation |
| `/lucy-ng:status` | Check environment readiness (LSD, database, install) |

---

## The `lucy` CLI

Everything the agents do is available directly through the `lucy` command. These commands
are thin wrappers that orchestrate the [foundational packages above](#built-on-lsd-and-established-tools)
— LSD, RDKit, nmrglue and the rest — behind one consistent interface; the science lives in
those packages, not here. Every subcommand supports `--format json` for scripting. The
command groups:

| Group | What it does |
|-------|--------------|
| `lucy read` | Read 1D / 2D Bruker spectra |
| `lucy pick` | Peak picking (1D, DEPT-guided HSQC, guided HMBC) |
| `lucy analyze` | Symmetry detection and structural analysis |
| `lucy detect` | Statistical detection (hybridisation, neighbours) |
| `lucy dereplicate` | Match a spectrum against the reference database |
| `lucy identify` | Derive a deterministic identity (SMILES → InChIKey + DB name) |
| `lucy predict` | Predict 13C shifts from structure (HOSE codes) |
| `lucy lsd` | Generate LSD input, run the solver, rank solutions |
| `lucy pylsd` | Multi-run LSD orchestration for 4J-HMBC handling |
| `lucy fragment` | Fragment-library build / search |
| `lucy visualize` | NMR correlation diagrams |
| `lucy fetch` | Fetch datasets from external repositories |
| `lucy database` | Download and inspect the reference database |

A few representative invocations:

```bash
# Inspect a carbon spectrum
lucy read 1d data/Ibuprofen/2

# DEPT-guided HSQC picking (DEPT-135 as ground truth)
lucy pick hsqc data/Ibuprofen/6 --dept135 data/Ibuprofen/3

# Guided HMBC picking (cross-validated against 13C and HSQC)
lucy pick hmbc data/Ibuprofen/7 --c13 data/Ibuprofen/2 --hsqc data/Ibuprofen/6

# Dereplicate against the reference database
lucy dereplicate c13 data/Ibuprofen/2 C13H18O2

# Generate constraints, solve, and rank
lucy lsd generate data/Ibuprofen C13H18O2 -o ibuprofen.lsd
lucy lsd run ibuprofen.lsd
lucy lsd rank output/ data/Ibuprofen/2 --top 10

# Predict 13C shifts for a candidate
lucy predict c13 "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
```

A Python API mirrors the CLI for custom workflows — see
[docs/USER_GUIDE.md](docs/USER_GUIDE.md).

---

## Installation

To install lucy-ng, simply ask your AI to look at this repo and do the installation for you. Alternatively, you can follow the instructions below.

### CLI only

```bash
pip install "lucy-ng @ git+https://github.com/steinbeck/lucy-ng.git"
```

> **macOS / zsh:** the quotes are required because zsh expands square brackets.

### Development

```bash
git clone https://github.com/steinbeck/lucy-ng.git
cd lucy-ng
pip install -e ".[dev]"
```

### 13C prediction support

13C prediction needs the `hose-code-generator` package, which has a broken test
dependency on modern Python. Install it without that dependency:

```bash
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
pip install rdkit
```

### LSD solver

The [LSD solver](https://nuzillard.github.io/LSD/) by Jean-Marc Nuzillard does the actual
structure generation. Download it, extract it, and add its `bin/` directory to `PATH`.
Verify with:

```bash
lucy lsd check     # must report both LSD and outlsd on PATH
```

### Reference database

Dereplication, 13C prediction, and CASE ranking all share one pre-built SQLite database:
**928,443 compounds** (COCONUT + NMRShiftDB) and **7.9 M HOSE-code statistics**
(~830 MB download → ~2.8 GB uncompressed).

```bash
lucy database download -o data/reference/lucy-ng-derep.db
lucy database info data/reference/lucy-ng-derep.db
```

It is auto-discovered at `data/reference/lucy-ng-derep.db`. DOI:
[10.6084/m9.figshare.31073554](https://doi.org/10.6084/m9.figshare.31073554). See
[docs/INSTALLATION.md](docs/INSTALLATION.md#reference-database) for detail.

### NMRPipe + SMILE (NUS reconstruction)

Automatic reconstruction of non-uniformly-sampled (NUS) 2D spectra (`lucy nus reconstruct`
/ `pipeline`) uses NMRPipe with the SMILE plugin as its backend. Install NMRPipe (native
`mac11_arm64`/Linux build) **and** the separate SMILE companion plugin
(`plugin.smile.tZ`) from https://www.ibbr.umd.edu/nmrpipe/install, source its environment
script, and add its `bin/` directory to `PATH`. Verify with:

```bash
lucy nus check     # must report the backend "available"
```

See [docs/NUS-PORTABILITY.md](docs/NUS-PORTABILITY.md) for the full per-platform matrix
(macOS Apple Silicon native / Linux native / Windows WSL2 gap).

---

## Scientific Background

CASE follows a systematic pipeline:

```
NMR Spectra → Peak Picking → Constraint Extraction → Solver → Candidate Structures → Ranking
```

Two design choices matter most for getting correct answers:

### Guided peak picking

Raw 2D peak picking produces many noise peaks and artefacts. lucy-ng uses DEPT-135 as
ground truth (it definitively shows all protonated carbons), lowers the HSQC threshold
until every DEPT carbon is matched, and filters HMBC peaks to require a matching carbon
(from 13C) **and** proton (from HSQC). This removes the false correlations that would
otherwise generate thousands of incorrect structures.

| Constraint source | Typical LSD solutions |
|-------------------|-----------------------|
| Manual HMBC (~16 correlations) | 900+ structures |
| Guided HMBC (28–30 correlations) | 1–10 structures |

### Molecular symmetry

Equivalent carbons appear as single signals, so the observed carbon count is often below
the formula count (e.g. a para-disubstituted benzene shows two pairs of equivalent
carbons). lucy-ng detects this by comparing the formula's hydrogen budget with the
observed C–H count and by analysing relative peak intensities, then encodes it as solver
constraints rather than guessing.

---

## Architecture

```
lucy-ng/
├── src/lucy_ng/
│   ├── models/          # Pydantic v2 data models (Spectrum1D/2D, Peak1D, …)
│   ├── readers/         # NMR file readers (BrukerReader)
│   ├── processing/      # peak picking, signal processing
│   ├── detection/       # statistical detection (hybridisation, neighbours)
│   ├── analysis/        # symmetry / signal-grouping analysis
│   ├── dereplication/   # formula-indexed compound DB matching
│   ├── prediction/      # HOSE-code 13C shift prediction
│   ├── ranking/         # candidate solution ranking
│   ├── lsd/             # LSD solver integration + bundled fragment filters
│   ├── identity.py      # deterministic identity derivation (lucy identify)
│   └── cli/             # the `lucy` Click CLI
├── .claude/             # CASE orchestrator command + team agents (skills)
├── tests/               # pytest suite
├── data/                # local test NMR datasets (Bruker format)
└── docs/                # documentation
```

### Design principles

1. **Structured results** — every operation returns a result object with a success flag
   and detailed data, rather than raising on the common error paths.
2. **Pydantic models** — all data structures use Pydantic v2 for validation and
   serialisation.
3. **HOSE codes use molecules without explicit hydrogens** — a hard invariant shared
   between database generation and prediction; mixing the two causes prediction
   mismatches (see [CLAUDE.md](CLAUDE.md)).

For the AI-agent workflow, pitfalls, and best practices, see [CLAUDE.md](CLAUDE.md).

---

## Supported Data

**Input:** Bruker TopSpin 1D and 2D spectra (processed data from `pdata/1/`); SD files
for reference databases.

| Experiment | Detection | Notes |
|------------|-----------|-------|
| 1H | Nucleus | Proton spectrum |
| 13C | Nucleus | Carbon spectrum |
| DEPT-135 | Pulse program | CH/CH3 up, CH2 down |
| DEPT-90 | Pulse program | CH only |
| COSY | Pulse program | H–H correlations |
| HSQC | Pulse program (inv4) | Direct C–H |
| HMBC | Pulse program (inv4·lr) | Long-range C–H |

---

## Development

```bash
pytest                    # run tests
pytest --cov=lucy_ng      # with coverage
mypy src/lucy_ng          # type checking (strict)
ruff check src tests      # linting
hatch build               # build the package
```

---

## License & Citation

MIT License — see [LICENSE](LICENSE).

### Cite LSD first

lucy-ng is worthless without the LSD structure generator. **Any work using lucy-ng must
cite LSD.** See the [LSD website](https://nuzillard.github.io/LSD/) for the author's
current preferred citation; a key reference is:

> B. Plainchont, V. P. Emerenciano, J.-M. Nuzillard. *Recent advances in the structure
> elucidation of small organic molecules by the LSD software.* Magn. Reson. Chem. **2013**,
> 51, 447–453. See also J.-M. Nuzillard, *Tutorial for the structure elucidation of small
> molecules by means of the LSD software*, Magn. Reson. Chem. **2018**
> ([doi:10.1002/mrc.4612](https://doi.org/10.1002/mrc.4612)).

**Acknowledgments:** LSD by Jean-Marc Nuzillard (Université de Reims Champagne-Ardenne) ·
original Lucy concept by Christoph Steinbeck · RDKit · nmrglue for NMR file parsing ·
HOSE codes (W. Bremser, *Anal. Chim. Acta* **1978**, 103, 355–365) · COCONUT and
NMRShiftDB for reference data.

If you use lucy-ng itself, please also cite it (alongside LSD):

```bibtex
@software{lucy-ng,
  author = {Steinbeck, Christoph},
  title  = {lucy-ng: AI-Agent Powered Computer-Assisted Structure Elucidation},
  url    = {https://github.com/steinbeck/lucy-ng},
  year   = {2026}
}
```
