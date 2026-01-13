# Installation Guide

This guide covers all installation options for lucy-ng.

## Table of Contents

- [Requirements](#requirements)
- [Quick Installation](#quick-installation)
- [Installation Options](#installation-options)
- [External Dependencies](#external-dependencies)
- [Reference Databases](#reference-databases)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Requirements

### Python Version

Lucy-ng requires **Python 3.10 or higher**.

Check your Python version:
```bash
python3 --version
```

### System Dependencies

Lucy-ng's Python dependencies will be installed automatically. The core dependencies are:

| Package | Version | Purpose |
|---------|---------|---------|
| nmrglue | >=0.9 | Bruker NMR file parsing |
| numpy | >=1.24 | Numerical operations |
| scipy | >=1.10 | Peak picking algorithms |
| pydantic | >=2.0 | Data model validation |
| rdkit | >=2023.0 | SD file parsing for databases |
| click | >=8.0 | CLI framework |
| tqdm | >=4.0 | Progress bars |

**Optional dependencies:**

| Package | Purpose | Notes |
|---------|---------|-------|
| hose-code-generator | 13C shift prediction | See [Python 3.12 note](#13c-prediction-python-312) |
| mcp[cli] | MCP server for AI agents | Installed with `[mcp]` extra |

## Quick Installation

### From GitHub (Recommended)

Lucy-ng is currently installed directly from GitHub:

```bash
# Basic installation
pip install "lucy-ng @ git+https://github.com/steinbeck/lucy-ng.git"

# With MCP server support (recommended for AI integration)
pip install "lucy-ng[mcp] @ git+https://github.com/steinbeck/lucy-ng.git"
```

This adds the `mcp[cli]>=1.2.0` dependency for AI agent integration.

> **Note for macOS/zsh users**: The quotes are required because zsh interprets square brackets as glob patterns. Without quotes, you'll get "no matches found" error.

### Full Installation (All Features)

```bash
pip install "lucy-ng[mcp,dev] @ git+https://github.com/steinbeck/lucy-ng.git"
```

## Installation Options

### Option 1: User Installation

Install for the current user only (no root required):

```bash
pip install --user "lucy-ng[mcp] @ git+https://github.com/steinbeck/lucy-ng.git"
```

### Option 2: Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv lucy-env
source lucy-env/bin/activate  # Linux/macOS
# or: lucy-env\Scripts\activate  # Windows

# Install lucy-ng
pip install "lucy-ng[mcp] @ git+https://github.com/steinbeck/lucy-ng.git"
```

### Option 3: Development Installation (For Contributors)

For contributing or modifying lucy-ng:

```bash
# Clone repository
git clone https://github.com/steinbeck/lucy-ng.git
cd lucy-ng

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev,mcp]"

# Verify installation
pytest
```

### Option 4: System-Wide Installation

```bash
sudo pip install "lucy-ng[mcp] @ git+https://github.com/steinbeck/lucy-ng.git"
```

## 13C Prediction (Python 3.12)

The 13C shift prediction feature (`lucy predict c13`, `predict_c13_shifts` MCP tool, solution ranking) requires the `hose-code-generator` package for HOSE code generation.

### Python 3.10/3.11

On Python 3.10 or 3.11, hosegen installs automatically with all its dependencies.

### Python 3.12+

On Python 3.12, the `hose-code-generator` package has a broken test dependency (`xmlrunner`) that fails to install. Install it manually without dependencies:

```bash
# After installing lucy-ng
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
```

The `--no-deps` flag skips the broken `xmlrunner` dependency, which is only needed for running hosegen's own tests, not for HOSE code generation. The prediction features work correctly without it.

### Checking Availability

You can check if HOSE code prediction is available:

```python
from lucy_ng.prediction import HOSEGEN_AVAILABLE
print(f"HOSE prediction available: {HOSEGEN_AVAILABLE}")
```

Or via CLI:
```bash
lucy predict c13 "CCO"  # Will show error if hosegen not installed
```

## External Dependencies

### LSD Solver (Optional)

LSD (Logic for Structure Determination) is required for structure generation. It's optional for dereplication and analysis.

#### Download and Install

1. Download LSD from: http://eos.univ-reims.fr/LSD/
2. Extract the archive:
   ```bash
   tar -xzf LSD-3.5.3.tar.gz
   cd LSD-3.5.3
   ```
3. Compile (if needed):
   ```bash
   make
   ```
4. Add to PATH or copy to standard location:
   ```bash
   # Option A: Add to PATH
   export PATH="$PATH:$HOME/LSD-3.5.3"

   # Option B: Copy to ~/bin
   mkdir -p ~/bin
   cp lsd ~/bin/
   export PATH="$PATH:$HOME/bin"

   # Option C: Copy to system location
   sudo cp lsd /usr/local/bin/
   ```

#### Install outlsd (Recommended)

The `outlsd` program converts LSD solutions to SMILES format, which is required for solution ranking. It is distributed with LSD.

```bash
# Copy outlsd alongside lsd
cp outlsd ~/bin/
# or
sudo cp outlsd /usr/local/bin/
```

Without `outlsd`:
- LSD will still generate solutions
- But `lucy lsd rank` cannot rank them (no SMILES available)
- The `rank_lsd_solutions` MCP tool will skip all solutions

#### Verify LSD Installation

```bash
# Using CLI - shows both lsd and outlsd status
lucy lsd check

# Or directly
which lsd
which outlsd
```

Expected output:
```
LSD: available
outlsd: available (SMILES conversion enabled)
```

### pyLSD (Alternative Solver)

pyLSD is a Python wrapper around LSD with additional features. Install separately if needed:

```bash
pip install pylsd
```

## Reference Databases

Lucy-ng supports two reference databases for dereplication. At least one is required for the `dereplicate` command.

### COCONUT Database (Recommended)

The COCONUT database contains ~895,000 natural products with predicted 13C NMR shifts.

1. Download from: https://coconut.naturalproducts.net/
2. Look for the SD file with predicted NMR data (typically `coconut_predicted.sd`)
3. Place in one of these locations:
   - `data/reference/coconut_predicted.sd` (project directory)
   - `~/.lucy/coconut_predicted.sd` (user directory)

**Note**: The COCONUT file is ~4.8 GB. Lucy-ng uses streaming mode to handle it efficiently.

### NMRShiftDB (Smaller Alternative)

NMRShiftDB contains ~33,000 compounds with experimental 13C shifts.

1. Download from: https://nmrshiftdb.nmr.uni-koeln.de/
2. Look for `nmrshiftdb2withsignals.sd`
3. Place in:
   - `data/reference/nmrshiftdb2withsignals.sd`
   - `~/.lucy/nmrshiftdb.sd`

### Auto-Discovery

Lucy-ng automatically discovers databases in this order:
1. `data/reference/coconut_predicted.sd`
2. `data/reference/nmrshiftdb2withsignals.sd`
3. `~/.lucy/coconut_predicted.sd`
4. `~/.lucy/nmrshiftdb.sd`

You can also specify the database explicitly:
```bash
lucy dereplicate c13 spectrum_path formula --database /path/to/database.sd
```

## Verification

After installation, verify everything works:

### Check CLI Installation

```bash
# Should show help message
lucy --help

# Check version
lucy --version
```

### Check MCP Server

```bash
# Should show help for MCP server
lucy-mcp --help

# Or run directly
python -m lucy_ng.mcp --help
```

### Run Tests

```bash
# Quick test (if dev dependencies installed)
pytest tests/test_mcp_server.py -v

# Full test suite
pytest
```

### Test with Sample Data

```bash
# Read a spectrum (if test data available)
lucy read 1d data/Ibuprofen/2

# Pick peaks
lucy pick 1d data/Ibuprofen/2
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'lucy_ng'`

**Solution**:
```bash
# Ensure you're in the right environment
which python3
pip list | grep lucy

# Reinstall if needed
pip install --force-reinstall lucy-ng
```

### RDKit Installation Issues

**Problem**: RDKit fails to install

**Solution**:
```bash
# Try conda instead
conda install -c conda-forge rdkit

# Or use mamba
mamba install rdkit
```

### MCP Server Not Found

**Problem**: `lucy-mcp: command not found`

**Solution**:
```bash
# Ensure MCP extras were installed
pip install lucy-ng[mcp]

# Check if entry point exists
pip show lucy-ng | grep -A 10 "Entry-points"

# Run directly as module
python -m lucy_ng.mcp
```

### LSD Not Found

**Problem**: `lucy lsd check` says LSD is not available

**Solution**:
```bash
# Find LSD binary
find ~ -name "lsd" -type f 2>/dev/null

# Add to PATH
export PATH="$PATH:/path/to/lsd/directory"

# Verify
which lsd
```

### Database Loading Slow

**Problem**: Dereplication takes very long with COCONUT

**Solution**: This is normal for the first query. Lucy-ng uses streaming mode so it doesn't load the entire 4.8 GB file into memory. Typical query time is 1-2 minutes for formula-based filtering.

### Memory Issues

**Problem**: Out of memory errors with large databases

**Solution**: Lucy-ng's COCONUT loader uses streaming mode by default. If you're still seeing issues:
```bash
# Increase available memory
ulimit -v unlimited

# Or use NMRShiftDB instead
lucy dereplicate c13 spectrum formula --database data/reference/nmrshiftdb2withsignals.sd
```

### HOSE Code Generator Issues (Python 3.12)

**Problem**: Installation fails with `xmlrunner` or `_TextTestResult` errors

```
ImportError: cannot import name '_TextTestResult' from 'unittest'
```

**Solution**: This is a known issue with Python 3.12. Install hosegen without its broken test dependency:

```bash
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
```

**Problem**: `hosegen package not installed` error when using prediction

**Solution**: Install hosegen as shown above. The prediction features require this package for HOSE code generation.

## Next Steps

After installation:

1. **Read the User Guide**: See [USER_GUIDE.md](USER_GUIDE.md) for detailed usage
2. **Set up MCP**: See [MCP_INTEGRATION.md](MCP_INTEGRATION.md) for Claude Desktop integration
3. **AI Agent Guide**: See [../CLAUDE.md](../CLAUDE.md) for comprehensive structure elucidation workflow and pitfalls
4. **Explore the CLI**: Run `lucy --help` to see all commands
5. **Try the examples**: See the Quick Start section in the main README
