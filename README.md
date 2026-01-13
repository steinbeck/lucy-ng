# lucy-ng

**AI-Agent Powered Computer-Assisted Structure Elucidation for Organic Natural Products**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

lucy-ng is a next-generation structure elucidation system designed for AI-agent driven workflows. Unlike traditional GUI-focused NMR processing tools, lucy-ng is built for programmatic, unattended operation where an AI agent (such as Claude) can iterate through the elucidation process until a structure is determined.

## Table of Contents

- [Vision](#vision)
- [Key Features](#key-features)
- [Scientific Background](#scientific-background)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Command-Line Interface](#command-line-interface)
  - [Python API](#python-api)
  - [MCP Server (AI Integration)](#mcp-server-ai-integration)
- [Architecture](#architecture)
- [Supported Data](#supported-data)
- [Development](#development)
- [License](#license)

## Vision

Lucy-ng represents a complete reimagining of Computer-Assisted Structure Elucidation (CASE) for the AI era. The original Lucy software was created by the project author and sold to Bruker. Lucy-ng builds on decades of CASE experience but prioritizes:

1. **AI-First Design**: Every feature is accessible via structured APIs suitable for LLM agents
2. **Unattended Operation**: No human intervention required during the elucidation process
3. **Iterative Refinement**: AI agents can run multiple cycles of hypothesis generation and testing
4. **Transparent Reasoning**: All processing steps are logged and explainable

### The Problem We Solve

Existing NMR processing tools like NMRium are GUI-focused, making it difficult for AI agents to interact with them programmatically. Structure elucidation typically requires:

- Loading multiple NMR spectra (1D and 2D)
- Peak picking with appropriate thresholds
- Cross-validation between experiments
- Generation of structural constraints
- Execution of constraint-based solvers
- Validation of proposed structures

Lucy-ng automates this entire pipeline while exposing each step as a programmable tool.

## Key Features

### NMR Data Processing
- **Bruker Format Support**: Read 1D and 2D NMR spectra from Bruker TopSpin format
- **Automatic Experiment Detection**: Identifies 1H, 13C, DEPT, COSY, HSQC, HMBC from pulse programs
- **Processed Data Reading**: Works with processed spectra (pdata/1/) for immediate use

### Intelligent Peak Picking
- **Adaptive Peak Picker**: Automatically adjusts minimum distance based on line width (FWHM)
- **DEPT-Guided HSQC Picking**: Uses DEPT-135 as ground truth to ensure all protonated carbons are found
- **HMBC-Guided Filtering**: Removes noise peaks by validating against known carbon and proton positions
- **Multiplicity Assignment**: Automatically determines CH, CH2, CH3 from DEPT-135/90

### Dereplication
- **COCONUT Database**: Match against ~895,000 natural products with predicted 13C shifts
- **NMRShiftDB**: Fallback database with ~33,000 experimental spectra
- **Streaming Mode**: Efficiently handles multi-GB databases without loading into memory
- **Formula-Based Filtering**: Only processes compounds matching the target molecular formula

### Structure Elucidation
- **LSD Integration**: Generate input files and execute the LSD solver
- **Symmetry Detection**: Identifies equivalent atoms from hydrogen budget and intensity analysis
- **Constraint Generation**: Automatic MULT, HSQC, HMBC, BOND constraints from spectroscopic data
- **Solution Ranking**: Rank LSD solutions by comparing predicted vs experimental 13C spectra

### 13C Shift Prediction
- **HOSE Code Prediction**: Predict 13C shifts from molecular structure using HOSE codes
- **Fallback Strategy**: Automatic radius reduction (6→1) for maximum coverage
- **Pre-built Lookup Table**: Fast predictions using nmrshiftdb2 reference data

### AI Integration
- **MCP Server**: Model Context Protocol tools for Claude Desktop and other AI agents
- **CLI Interface**: Full command-line interface for scripting and testing
- **Python API**: Direct library access for custom workflows

## Scientific Background

### The CASE Workflow

Computer-Assisted Structure Elucidation follows a systematic approach:

```
NMR Spectra → Peak Picking → Constraint Extraction → Solver → Candidate Structures → Validation
```

Lucy-ng implements each step with careful attention to scientific accuracy:

#### 1. Peak Picking Strategy

Raw 2D peak picking produces many noise peaks and artifacts. Lucy-ng uses a **guided peak picking** strategy:

- **DEPT as Ground Truth**: DEPT-135 definitively shows all protonated carbons
- **Adaptive Thresholding**: HSQC threshold is lowered iteratively until all DEPT carbons are matched
- **Cross-Validation**: HMBC peaks are filtered to require matching carbon (from 13C) AND proton (from HSQC)

This dramatically reduces false correlations that would otherwise produce thousands of incorrect structures.

#### 2. Handling Molecular Symmetry

Equivalent carbons due to molecular symmetry appear as single NMR signals:

```
Ibuprofen (C13H18O2):
- Expected carbons from formula: 13
- Observed 13C signals: 10-11
- Reason: Para-disubstituted benzene has 2 pairs of equivalent carbons
```

Lucy-ng detects symmetry by:
- Comparing molecular formula H count with observed C-H count
- Analyzing relative peak intensities (doubled signals have ~2x intensity)
- Recognizing common symmetric motifs

#### 3. Constraint Quality

The number of LSD solutions depends heavily on constraint quality:

| Constraint Source | Typical Solutions |
|-------------------|-------------------|
| Manual HMBC (16 correlations) | 900+ structures |
| Guided HMBC (28-30 correlations) | 1-10 structures |

Real experimental data with proper filtering provides much stronger constraints than manually constructed correlations.

## Installation

### From GitHub

```bash
# Basic installation
pip install "lucy-ng @ git+https://github.com/steinbeck/lucy-ng.git"

# With MCP server support (recommended)
pip install "lucy-ng[mcp] @ git+https://github.com/steinbeck/lucy-ng.git"
```

> **Note for macOS/zsh users**: The quotes are required because zsh interprets square brackets as glob patterns.

### Development Installation

```bash
git clone https://github.com/steinbeck/lucy-ng.git
cd lucy-ng
pip install -e ".[dev,mcp]"
```

### 13C Prediction Support (Python 3.12)

The 13C shift prediction feature requires the `hose-code-generator` package. On Python 3.12, install it separately:

```bash
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
```

> **Note**: The `--no-deps` flag skips a broken test dependency (`xmlrunner`) that doesn't work with Python 3.12. The prediction feature works fine without it.

### External Dependencies

**LSD Solver** (optional, for structure generation):
```bash
# Download from http://eos.univ-reims.fr/LSD/
# Extract and add to PATH, or specify location when running
```

### Reference Databases

For dereplication, download one or both databases:

| Database | Size | Entries | Download |
|----------|------|---------|----------|
| COCONUT | ~4.8 GB | ~895,000 | [coconut.naturalproducts.net](https://coconut.naturalproducts.net/) |
| NMRShiftDB | ~100 MB | ~33,000 | [nmrshiftdb.nmr.uni-koeln.de](https://nmrshiftdb.nmr.uni-koeln.de/) |

Place in `data/reference/` or `~/.lucy/` for auto-discovery.

## Quick Start

### Read a Spectrum

```python
from lucy_ng import BrukerReader

# Read 1D carbon spectrum
spectrum = BrukerReader.read_1d("data/Ibuprofen/2")
print(f"Nucleus: {spectrum.nucleus}")
print(f"Points: {len(spectrum.data)}")
print(f"PPM range: {spectrum.ppm_scale.min():.1f} - {spectrum.ppm_scale.max():.1f}")
```

### Pick Peaks

```python
from lucy_ng import BrukerReader, AdaptivePeakPicker

spectrum = BrukerReader.read_1d("data/Ibuprofen/2")
peaks = AdaptivePeakPicker.pick_peaks(spectrum, threshold=0.05)

for peak in peaks.peaks[:5]:
    print(f"{peak.position:.2f} ppm, intensity: {peak.intensity:.2e}")
```

### DEPT-Guided HSQC Picking

```python
from lucy_ng import BrukerReader
from lucy_ng.processing import DEPTGuidedPicker

hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
dept135 = BrukerReader.read_1d("data/Ibuprofen/3")

result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)
print(result.summary())
# Access: result.peaks, result.carbon_multiplicities
```

### Dereplication

```bash
lucy dereplicate c13 data/Ibuprofen/2 C13H18O2
```

```python
from lucy_ng.dereplication import DereplicationService, NMRShiftDBLoader
from lucy_ng import BrukerReader

spectrum = BrukerReader.read_1d("data/Ibuprofen/2")
loader = NMRShiftDBLoader("data/reference/nmrshiftdb2withsignals.sd")
loader.load()

service = DereplicationService(loader)
result = service.dereplicate_from_spectrum(spectrum, "C13H18O2")

if result.is_match:
    print(f"Match found: {result.top_matches[0].entry.name}")
```

## Usage

### Command-Line Interface

Lucy-ng provides a comprehensive CLI with five command groups:

#### Read Spectra
```bash
# Read 1D spectrum
lucy read 1d data/Ibuprofen/2

# Read 2D spectrum
lucy read 2d data/Ibuprofen/6

# Output as JSON
lucy read 1d data/Ibuprofen/2 --format json
```

#### Pick Peaks
```bash
# 1D peak picking
lucy pick 1d data/Ibuprofen/2

# DEPT-guided HSQC picking
lucy pick hsqc data/Ibuprofen/6 --dept135 data/Ibuprofen/3

# With DEPT-90 for CH/CH3 disambiguation
lucy pick hsqc data/Ibuprofen/6 --dept135 data/Ibuprofen/3 --dept90 data/Ibuprofen/4

# Guided HMBC picking
lucy pick hmbc data/Ibuprofen/7 --c13 data/Ibuprofen/2 --hsqc data/Ibuprofen/6
```

#### Analyze Symmetry
```bash
lucy analyze symmetry data/Ibuprofen C13H18O2
```

#### Dereplication
```bash
# Default uses COCONUT database
lucy dereplicate c13 data/Ibuprofen/2 C13H18O2

# Specify database
lucy dereplicate c13 data/Ibuprofen/2 C13H18O2 --database data/reference/nmrshiftdb2withsignals.sd
```

#### LSD Integration
```bash
# Generate LSD input file
lucy lsd generate data/Ibuprofen C13H18O2 -o ibuprofen.lsd

# Run LSD solver
lucy lsd run ibuprofen.lsd

# Rank solutions by 13C prediction
lucy lsd rank output/ data/Ibuprofen/2 --top 10

# Check LSD availability
lucy lsd check
```

#### 13C Shift Prediction
```bash
# Predict shifts from SMILES
lucy predict c13 "CC(C)Cc1ccc(cc1)C(C)C(=O)O"

# Build lookup table (one-time setup)
lucy predict build-table data/reference/nmrshiftdb2withsignals.sd

# Show table info
lucy predict table-info
```

### Python API

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for comprehensive Python API documentation.

### Claude Code Integration

Lucy-ng works seamlessly with [Claude Code](https://claude.ai/claude-code) for interactive structure elucidation. Copy this prompt to set up a new machine:

```
Set up this machine for NMR structure elucidation with lucy-ng:

1. Check/install lucy-ng: `lucy --version || pip install lucy-ng`
2. Check LSD solver: `lucy lsd check` - if missing, install from http://eos.univ-reims.fr/LSD/
3. Download CLAUDE.md to .claude/CLAUDE.md: https://raw.githubusercontent.com/steinbeck/lucy-ng/master/CLAUDE.md
4. Create .claude/settings.json with: {"permissions":{"allow":["Bash(lucy:*)","Bash(python3:*)"]}}

Once ready, place Bruker NMR data in a folder and I'll perform complete structure elucidation.
```

After setup, simply ask:
```
Perform structure elucidation on the NMR data in this folder. Molecular formula: C13H18O2
```

Claude will automatically run dereplication, pick peaks, analyze symmetry, generate LSD constraints, solve structures, and rank solutions by 13C shift prediction.

### MCP Server (AI Integration)

Lucy-ng includes an MCP (Model Context Protocol) server for AI agent integration.

#### Available Tools

| Tool | Description |
|------|-------------|
| `read_spectrum_1d` | Read 1D NMR spectrum metadata |
| `read_spectrum_2d` | Read 2D NMR spectrum metadata |
| `pick_peaks_1d` | Pick peaks from 1D spectrum |
| `pick_hsqc_peaks` | DEPT-guided HSQC peak picking |
| `pick_hmbc_peaks` | Guided HMBC peak picking |
| `analyze_symmetry` | Detect molecular symmetry |
| `dereplicate_c13` | Match against reference database |
| `generate_lsd_input` | Generate LSD input from NMR data |
| `run_lsd` | Execute LSD solver |
| `check_lsd_availability` | Check if LSD is installed |
| `rank_lsd_solutions` | Rank solutions by 13C prediction similarity |
| `predict_c13_shifts` | Predict 13C shifts from SMILES |

#### Claude Desktop Integration

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lucy-ng": {
      "command": "lucy-mcp"
    }
  }
}
```

Then ask Claude: *"Use lucy-ng to analyze the NMR data in data/Ibuprofen and identify the compound"*

See [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) for detailed setup instructions.

**AI Agent Guide**: For comprehensive guidance on structure elucidation workflow, pitfalls, and best practices, see [CLAUDE.md](CLAUDE.md).

## Architecture

```
lucy-ng/
├── src/lucy_ng/
│   ├── models/          # Pydantic data models (Spectrum1D, Peak1D, etc.)
│   ├── readers/         # NMR file readers (BrukerReader)
│   ├── processing/      # Peak picking and signal processing
│   │   ├── peak_picker.py       # AdaptivePeakPicker
│   │   ├── peak_picker_2d.py    # PeakPicker2D
│   │   ├── dept_guided_picker.py # DEPTGuidedPicker
│   │   └── hmbc_guided_picker.py # HMBCGuidedPicker
│   ├── analysis/        # Symmetry analysis tools
│   ├── dereplication/   # Database matching
│   │   ├── coconut.py   # COCONUT loader (streaming)
│   │   ├── nmrshiftdb.py # NMRShiftDB loader
│   │   └── service.py   # DereplicationService
│   ├── lsd/             # LSD solver integration
│   │   ├── generator.py # LSD input file generation
│   │   └── runner.py    # LSD execution
│   ├── prediction/      # 13C shift prediction
│   │   ├── hose.py      # HOSE code generation
│   │   ├── lookup.py    # Lookup table management
│   │   └── predictor.py # C13Predictor
│   ├── ranking/         # Solution ranking
│   │   └── ranker.py    # SolutionRanker
│   ├── cli/             # Click-based CLI
│   └── mcp/             # MCP server
│       └── server.py    # FastMCP tools (12 tools)
├── tests/               # pytest test suite
├── data/                # Test NMR datasets
└── docs/                # Documentation
```

### Design Principles

1. **Static Methods for Convenience**: Core operations like `AdaptivePeakPicker.pick_peaks()` are static for easy use
2. **Pydantic Models**: All data structures use Pydantic v2 for validation and serialization
3. **Structured Results**: Every operation returns a result object with success status and detailed data
4. **Error Tolerance**: Operations return error information rather than raising exceptions

## Supported Data

### Input Formats
- Bruker TopSpin 1D and 2D spectra (processed data from pdata/1/)
- SD files for reference databases

### Experiment Types
| Type | Detection | Notes |
|------|-----------|-------|
| 1H | Nucleus | Proton spectrum |
| 13C | Nucleus | Carbon spectrum |
| DEPT-135 | Pulse program | CH/CH3 up, CH2 down |
| DEPT-90 | Pulse program | CH only |
| COSY | Pulse program | H-H correlations |
| HSQC | Pulse program (inv4) | Direct C-H |
| HMBC | Pulse program (inv4*lr*) | Long-range C-H |

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=lucy_ng

# Excluding slow dereplication tests
pytest --ignore=tests/test_dereplication.py
```

### Code Quality

```bash
# Type checking
mypy src/lucy_ng

# Linting
ruff check src tests

# Format checking
ruff format --check src tests
```

### Building

```bash
hatch build
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Original Lucy concept by Christoph Steinbeck
- LSD solver by Jean-Marc Nuzillard
- nmrglue library for NMR file parsing
- COCONUT and NMRShiftDB for reference data

## Citation

If you use lucy-ng in your research, please cite:

```bibtex
@software{lucy-ng,
  author = {Steinbeck, Christoph},
  title = {lucy-ng: AI-Agent Powered Computer-Assisted Structure Elucidation},
  url = {https://github.com/steinbeck/lucy-ng},
  year = {2026}
}
```
