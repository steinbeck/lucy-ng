# lucy-ng

AI-agent powered Computer-Assisted Structure Elucidation for organic natural products.

---

## End-User Setup (First-Time Installation)

When a user asks to set up structure elucidation or perform CASE, run these checks:

### 1. Install lucy-ng
```bash
lucy --version || pip install lucy-ng
```

### 2. Check LSD Solver (REQUIRED)
```bash
lucy lsd check
```

If LSD is not found:
- Download from: http://eos.univ-reims.fr/LSD/
- Extract the archive
- Add the `bin/` directory to PATH (contains `LSD` and `outlsd`)
- Both `LSD` and `outlsd` are required for full functionality

### 3. Verify Setup
```bash
lucy lsd check
```
Should report both LSD and outlsd as available.

### 4. Create Permissions File
Create `.claude/settings.json` in the working directory:
```json
{
  "permissions": {
    "allow": ["Bash(lucy:*)", "Bash(python3:*)", "Bash(ls:*)", "Bash(mkdir:*)"]
  }
}
```

### 5. Learn the Workflow
Read the AI Guide for structure elucidation workflow:
https://raw.githubusercontent.com/steinbeck/lucy-ng/master/docs/AI_GUIDE.md

## Performing Structure Elucidation

Once setup is complete, follow this workflow. The best possible outcome is between one and ten solutions. In case of another outcome, the workflow needs to be repeated and adjusted automatically until a satifactory outcome is reached. In case of no solution structure, constraints and assumptions need to be checked and adjusted. In case of too many solutions, constraints like more HMBC signals or hetero-attachments for specific carbons in the correct shift range need to be added. 

0. **Documentation** - Create an `analysis/` folder to document all steps and results. Document immediately after each step below, so that the user can follow while you work.
1. **Dereplication** - `lucy dereplicate c13 <spectrum> <formula>` - check known compounds first
2. **Symmetry** - `lucy analyze symmetry <data_dir> <formula>` - detect equivalent atoms
3. **Peak Picking**:
   - `lucy pick 1d <c13>` - carbon peaks
   - `lucy pick hsqc <hsqc> --dept135 <dept135>` - direct C-H correlations
   - `lucy pick hmbc <hmbc> --c13 <c13> --hsqc <hsqc>` - long-range correlations
4. **LSD Generation** - `lucy lsd generate <data_dir> <formula> -o output.lsd`
5. **Solve** - `lucy lsd run output.lsd`
6. **Rank** - `lucy lsd rank <smiles_file> --spectrum <c13>` or `--shifts "..."`

---

## Developer Reference

## Quick Reference

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=lucy_ng

# Type checking
mypy src/lucy_ng

# Linting
ruff check src tests

# Build package
hatch build
```

## Project Structure

```
src/lucy_ng/
├── models/          # Pydantic v2 data models (Spectrum1D, Spectrum2D, Peak1D, etc.)
├── readers/         # NMR file readers (BrukerReader)
├── processing/      # Peak picking, signal processing
├── dereplication/   # Database matching (NMRShiftDBLoader, SpectrumMatcher)
├── solvers/         # LSD/pyLSD integration (future)
└── __init__.py      # Public API exports

tests/               # pytest tests
data/                # Test NMR datasets (Bruker format)
.planning/           # GSD planning files (PROJECT.md, ROADMAP.md, STATE.md)
```

## Technology Stack

- **Python 3.10+** - minimum version
- **Pydantic v2** - data models with validation
- **nmrglue** - Bruker NMR file parsing
- **NumPy/SciPy** - numerical processing
- **RDKit** - SD file parsing for reference databases
- **hatch** - build system
- **pytest** - testing
- **ruff** - linting
- **mypy** - type checking (strict mode)

## Code Conventions

- Type hints on all functions
- Docstrings with Args/Returns/Raises sections
- Static methods for readers (e.g., `BrukerReader.read_1d()`)
- Helper functions prefixed with `_` for private use
- Line length: 100 characters
- Imports: standard library, third-party, local (isort order)

## NMR Data

Test data is Bruker format in `data/` directory:
- `data/Ibuprofen/` - 1D (1H, 13C) and 2D (COSY, HSQC, HMBC)
- `data/4-Hydroxy-3-Iodo-biphenyl/` - includes NOESY
- Processed data read from `pdata/1/` subdirectory

## Reference Data

Reference databases for dereplication are stored in `data/reference/`:

| File | Description | Entries | Size | Included |
|------|-------------|---------|------|----------|
| `nmrshiftdb2withsignals.sd.gz` | NMRShiftDB SD file with 13C chemical shifts | ~33,000 | ~20 MB | **Yes** |
| `coconut_predicted.sd` | COCONUT natural products (predicted shifts) | ~895,000 | ~4.8 GB | No |
| `sherlock_13c.json` | Pre-processed 13C reference data | - | ~350 MB | No |

**Usage**: The CLI `lucy dereplicate c13` command auto-discovers databases in `data/reference/`. The included NMRShiftDB database is auto-decompressed on first use.

**Auto-decompression**: When running from the lucy-ng directory, the CLI will:
1. Find `nmrshiftdb2withsignals.sd.gz` in `data/reference/`
2. Automatically decompress it to `nmrshiftdb2withsignals.sd` on first use
3. Use the decompressed file for subsequent runs

**Loaders**:
- `CoconutLoader` - For COCONUT SD files (parses `<CNMR_SHIFTS>`, `<Quaternaries>`, etc.)
- `NMRShiftDBLoader` - For nmrshiftdb SD files (parses `<Spectrum 13C 0>` field)

**Optional**: For larger database coverage, obtain COCONUT separately:
- COCONUT: https://coconut.naturalproducts.net/

## Key Patterns

### Reading NMR data
```python
from lucy_ng import BrukerReader, Spectrum1D

spectrum: Spectrum1D = BrukerReader.read_1d("data/Ibuprofen/10")
```

### Models are Pydantic
```python
from lucy_ng.models import Peak1D

peak = Peak1D(ppm=45.2, intensity=1.0e6, assignment="C-1")
```

## Peak Picking

### Scientific Rationale: Guided Peak Picking

Raw 2D peak picking produces many noise peaks and artifacts. For reliable structure elucidation, we use **guided peak picking** that cross-validates peaks against reference spectra:

**The Problem**: Unfiltered 2D peak picking leads to:
- Noise peaks that don't correspond to real correlations
- Artifacts (e.g., 1J bleeding in HMBC, t1 noise)
- Too many false correlations → LSD produces thousands of solutions instead of a manageable set

**The Solution**: Use 1D spectra as ground truth to filter 2D peaks:
- DEPT provides ground truth for protonated carbons (CH, CH2, CH3)
- 13C provides all carbon positions including quaternary
- HSQC provides valid proton chemical shifts. We only use picked HSQC shifts where the C-axis matches a DEPT peak.
- HMBC provied long-range correlations between carbons and hydrogens. Only peaks where the carbon shift matches a picked peak from the 1D carbon spectrum and the proton shift matches a proton shift from the HSQC signals are kept as being valid. 

### Molecular Symmetry

**Important**: Equivalent carbons appear as single NMR signals due to molecular symmetry.

Example - Ibuprofen (para-disubstituted benzene):
- Molecular formula: C13H18O2 (13 carbons)
- Observed 13C signals: ~10-11 (due to symmetry)
- Two ortho CH carbons are equivalent → 1 signal
- Two meta CH carbons are equivalent → 1 signal

The AI agent must detect this discrepancy between molecular formula and observed signals to properly constrain structure elucidation. Symmetry affects both carbon and proton counts.

### HSQC: Use DEPT-Guided Picker (Preferred)

For HSQC peak picking, **always use `DEPTGuidedPicker`** instead of raw `PeakPicker2D`.

**Why DEPT-guided?**
- DEPT-135 shows ALL protonated carbons (ground truth)
- Algorithm lowers HSQC threshold iteratively until all DEPT carbons are matched
- Only HSQC peaks at valid DEPT positions are retained
- Multiplicity (CH, CH2, CH3) extracted from DEPT-135 peak signs:
  - Positive peaks: CH or CH3
  - Negative peaks: CH2
- DEPT-90 (optional) distinguishes CH from CH3 (only CH visible in DEPT-90)

```python
from lucy_ng import BrukerReader
from lucy_ng.processing import DEPTGuidedPicker

hsqc = BrukerReader.read_2d("data/Ibuprofen/6")      # HSQC
dept135 = BrukerReader.read_1d("data/Ibuprofen/3")   # DEPT-135
dept90 = BrukerReader.read_1d("data/Ibuprofen/4")    # DEPT-90 (optional)

# With DEPT-90 for full CH/CH3 disambiguation
result = DEPTGuidedPicker.pick_hsqc_peaks_with_dept90(hsqc, dept135, dept90)

# Or with DEPT-135 only (CH and CH3 remain ambiguous as "CH/CH3")
result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

print(result.summary())
# Access: result.peaks, result.carbon_multiplicities, result.all_carbons_found
```

### HMBC: Use Guided Picker (Preferred)

For HMBC peak picking, **use `HMBCGuidedPicker`** to filter noise.

**Why guided HMBC picking?**
- HMBC spectra are noisy with many artifacts
- A real HMBC correlation requires:
  1. The carbon exists (visible in 13C or DEPT)
  2. The proton exists and is attached to a carbon (visible in HSQC)
- Filtering by these criteria removes noise peaks that would create false constraints for LSD

**Filtering criteria:**
1. Carbon (F1) must match a known carbon from 13C or DEPT spectrum (±1.5 ppm). Also look for HMBC signals for the quarternary carbons. 
2. Proton (F2) must match a known proton from HSQC (±0.1 ppm)

```python
from lucy_ng import BrukerReader
from lucy_ng.processing import HMBCGuidedPicker

hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
c13 = BrukerReader.read_1d("data/Ibuprofen/2")
hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
dept135 = BrukerReader.read_1d("data/Ibuprofen/3")  # optional

result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
    hmbc=hmbc,
    carbon_spectrum=c13,
    hsqc=hsqc,
    dept135=dept135,  # optional, adds extra carbon positions
)

print(result.summary())
# Access: result.peaks, result.validated_count, result.rejected_count
```

### Other 2D Spectra (COSY, etc.)

For COSY and other 2D spectra, use `PeakPicker2D`:
```python
from lucy_ng.processing import PeakPicker2D

cosy = BrukerReader.read_2d("data/Ibuprofen/5")
peaks = PeakPicker2D.pick_peaks(cosy, threshold=0.05)
```

## LSD Integration

### LSD Input Quality

**Critical insight**: The number of LSD solutions depends heavily on the quality and completeness of input constraints.

**Problem observed**: Manually constructed test correlations (16 HMBC) produced 900+ solutions for Ibuprofen. Real experimental data (28-30 HMBC correlations) provides much stronger constraints.

**Best practices for LSD input:**
1. Use real experimental HMBC data, not manually constructed correlations
2. Include ALL HMBC correlations from guided peak picking but adjust as needed in case of no or too many solutions. 
3. Quaternary carbons (visible in 13C but not DEPT) need HMBC correlations to be connected
4. Heteroatoms (O, N, etc.) without direct NMR visibility are constrained only by molecular formula. Use LSD's list feature to indicate that a carbon with a shift indicative of a hetero attachment shoud be directly bonded there. 

### LSD Command Format
The LSD user guide for full reference is at https://nuzillard.github.io/LSD/MANUAL_ENG.html.

**HMBC correlations**: Use 2 parameters (LSD defaults to 2-3 bond distance)
```
HMBC 1 2    ; carbon 1 correlates to proton attached to carbon 2
```

**HSQC correlations**: Direct C-H attachment
```
HSQC 1 1    ; carbon 1 has directly attached proton(s)
```

**Atom definitions**: MULT command with hybridization and H-count
```
MULT 1 C 2 1    ; atom 1, carbon, sp2 hybridization, 1 hydrogen
MULT 2 C 3 3    ; atom 2, carbon, sp3 hybridization, 3 hydrogens (CH3)
```

### LSD Runner Notes

- LSD writes solution count to **stderr**, not stdout
- Success is determined by finding solutions, not just return code
- Solution files are written as `.sol` files in the working directory

## Planning

This project uses GSD (Get Shit Done) workflow. Planning files in `.planning/`:
- `STATE.md` - current position and session context
- `ROADMAP.md` - milestone and phase overview
- `PROJECT.md` - vision, requirements, constraints
- `phases/` - detailed phase plans and summaries

Use `/gsd:resume-work` to restore context at session start.
