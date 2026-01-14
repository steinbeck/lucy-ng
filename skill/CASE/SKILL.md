---
name: CASE
description: Full de novo structure elucidation - skip dereplication and solve the structure from NMR correlations. Use when dereplication returned no matches, the compound is known to be novel, or you want to solve the structure from first principles.
---

# lucy-ng:CASE

Full de novo structure elucidation - skip dereplication and solve the structure from NMR correlations.

---

## Purpose

This skill performs FULL Computer-Assisted Structure Elucidation (CASE) without dereplication. Use this when:

- Dereplication already returned no matches
- You know the compound is novel/not in databases
- You want to solve the structure from first principles
- You're evaluating AI-based CASE methodology

---

## Blind CASE Protocol (CRITICAL)

**If you discover compound identity in ANY metadata file:**

1. ❌ **STOP** - Do not use this information
2. ❌ Do not look up the compound or its properties
3. ❌ Do not infer molecular formula from the name
4. ✅ Treat the compound as **completely unknown**
5. ✅ Ask user for molecular formula (simulating HRMS)
6. ✅ Derive ALL structural information from spectra only

**If data needs sanitization, use `/lucy-ng:sanitize` first, then start a fresh session.**

---

## Prerequisites

```bash
lucy --version || pip install lucy-ng
lucy lsd check  # Must show LSD and outlsd available
```

---

## Required Data

| Data | Essential? | Purpose |
|------|-----------|---------|
| **Molecular formula** | YES | From user (HRMS) |
| **13C spectrum** | YES | All carbon positions |
| **HSQC** | YES | Direct C-H correlations |
| **HMBC** | YES | Long-range correlations |
| **DEPT-135** | Recommended | Multiplicities (CH, CH2, CH3) |
| **COSY** | Optional | H-H correlations |

---

## Workflow

### Step 0: Setup Documentation

```bash
mkdir -p analysis
```

Document all steps in `analysis/` as you proceed.

### Step 1: Request Molecular Formula

**Always ask the user:**

```
"Please provide the molecular formula for this unknown compound (typically from HRMS)."
```

**Calculate key values from formula:**
- Total carbons
- Total hydrogens
- Heteroatoms (N, O, S, etc.)
- Degree of unsaturation: DBE = (2C + 2 + N - H) / 2

### Step 2: Identify Available Experiments

```bash
for dir in */; do
    if [ -f "$dir/acqus" ]; then
        nuc=$(grep "##\$NUC1=" "$dir/acqus" | head -1)
        pp=$(grep "##\$PULPROG=" "$dir/acqus" | head -1)
        echo "Exp $dir: $nuc | $pp"
    fi
done
```

Map experiments:
- 1H: `zg*`
- 13C: `zgdc*`, `zgpg*`
- DEPT: `dept*`
- HSQC: `hsqc*`
- HMBC: `hmbc*`
- COSY: `cosy*`

### Step 3: Analyze Symmetry

Compare expected vs observed signals:

```bash
lucy analyze symmetry <data_dir> <formula>
```

Or manually:
1. Count peaks in 13C spectrum
2. Compare to carbons in formula
3. If observed < expected → molecule has symmetry

**Document:**
```markdown
## Symmetry Analysis
- Expected carbons (from formula): X
- Observed 13C signals: Y
- Interpretation: [No symmetry / C2 symmetry / etc.]
```

### Step 4: Pick 13C Peaks

```bash
lucy pick 1d <13c_experiment>
```

Or from peaklist.xml if binary data is poor:
- Extract F1 values from `<Peak1D F1="..."/>` tags
- List all carbon shifts

**Document all peaks with proposed assignments:**

| # | Shift (ppm) | Type (if known) |
|---|-------------|-----------------|
| 1 | 187.8 | Carbonyl? |
| 2 | 152.5 | C-N? |
| ... | ... | ... |

### Step 5: Pick HSQC Peaks

**With DEPT (preferred):**
```bash
lucy pick hsqc <hsqc_exp> --dept135 <dept_exp>
```

**Without DEPT:**
```python
from lucy_ng import BrukerReader
from lucy_ng.processing import PeakPicker2D

hsqc = BrukerReader.read_2d("<hsqc_path>")
result = PeakPicker2D.pick_peaks(hsqc, threshold=0.1)

for p in result.peaks:
    print(f"C: {p.f1_position:.2f}, H: {p.f2_position:.2f}")
```

**Document:**
- Which carbons are protonated (have HSQC signals)
- Which are quaternary (no HSQC signal)
- Multiplicities if DEPT available (CH, CH2, CH3)

### Step 6: Pick HMBC Peaks

**Use guided picking** to filter noise:

```bash
lucy pick hmbc <hmbc_exp> --c13 <13c_exp> --hsqc <hsqc_exp>
```

Or manually with validation:
- Carbon position must match a 13C peak (±1.5 ppm)
- Proton position must match an HSQC proton (±0.1 ppm)

**Document all HMBC correlations:**

| Carbon (ppm) | Proton (ppm) | Notes |
|--------------|--------------|-------|
| 187.8 | 7.5 | Carbonyl to aromatic H |
| ... | ... | ... |

### Step 7: Generate LSD Input

**Option A: Automatic generation**
```bash
lucy lsd generate <data_dir> <formula> -o compound.lsd
```

**Option B: Manual construction (if auto fails)**

Build the LSD file manually:

```
; LSD input for <FORMULA>

; Atom definitions (MULT atom# element hybridization H-count)
MULT 1 C 2 0    ; Carbonyl carbon, sp2, 0H (quaternary)
MULT 2 C 2 1    ; Aromatic CH, sp2, 1H
MULT 3 N 3 1    ; Amine nitrogen, sp3, 1H (NH)
MULT 4 O 2 0    ; Carbonyl oxygen, sp2, 0H
...

; HSQC correlations (MUST come before HMBC)
HSQC 2 2        ; C2 has H2 attached
HSQC 5 5        ; C5 has H5 attached
...

; HMBC correlations
HMBC 1 2        ; C1 correlates to H2
HMBC 1 5        ; C1 correlates to H5
...

; Heteroatom constraints (optional but helpful)
BOND 1 4        ; C1 bonded to O4 (carbonyl)
```

**Critical checks before running:**
- [ ] sp2 count is EVEN
- [ ] Hydrogen count matches formula
- [ ] All HSQC commands before HMBC commands
- [ ] NO `ELIM` command on first run

### Step 8: Run LSD Solver

```bash
lucy lsd run compound.lsd
```

Or directly:
```bash
LSD compound.lsd
```

**Interpret results:**

| Solutions | Meaning | Action |
|-----------|---------|--------|
| 0 | Over-constrained | Check sp2 count, H count, correlations |
| 1 | Ideal | Verify and report |
| 2-10 | Good | Rank and report top candidates |
| 10-100 | Under-constrained | Add more HMBC, check ELIM usage |
| >100 | Severely under-constrained | Review all constraints |

### Step 9: Convert to SMILES

```bash
outlsd 5 < compound.sol > solutions.smi
```

### Step 10: Rank Solutions

```bash
lucy lsd rank solutions.smi --spectrum <13c_exp>
# Or with shift list:
lucy lsd rank solutions.smi --shifts "187.8,152.5,135.7,..."
```

**Interpret MAE scores:**

| MAE (ppm) | Quality | Interpretation |
|-----------|---------|----------------|
| < 2.0 | Excellent | High confidence |
| 2.0 - 3.5 | Good | Reasonable confidence |
| 3.5 - 5.0 | Moderate | Review carefully |
| > 5.0 | Poor | Likely incorrect |

### Step 11: Report Results

```markdown
## CASE Results

**Molecular Formula:** [formula]
**Degree of Unsaturation:** [DBE]

### Data Used
- 13C: [X] signals
- HSQC: [Y] correlations (Z protonated carbons)
- HMBC: [N] correlations
- Symmetry: [description]

### LSD Results
- Solutions found: [count]
- ELIM used: [Yes/No]

### Top Candidates

**Rank 1:** MAE = X.XX ppm ([Quality])
```
[SMILES]
```
- Key features: [description]

**Rank 2:** MAE = X.XX ppm ([Quality])
```
[SMILES]
```
- Differs from #1 in: [description]

### Confidence Assessment
[High/Medium/Low] - [reasoning]

### Recommendation
[Final structure proposal or need for additional data]
```

---

## Troubleshooting

### 0 Solutions

1. **Check sp2 count is EVEN** - count all sp2 atoms
2. **Check hydrogen count** - sum of (mult × count) = formula H
3. **Review HMBC correlations** - any errors or artifacts?
4. **Only then try ELIM** - start with `ELIM 1 0`, increment if needed

### Too Many Solutions (>100)

1. **Remove ELIM** if present
2. **Add more HMBC correlations**
3. **Add heteroatom constraints** (BOND or LIST/PROP)
4. **Verify HSQC correlations** are complete

### Ranking Doesn't Match Expected

1. **HOSE prediction limitations** - carbonyl carbons can vary ±5-10 ppm
2. **Check top 10-20 candidates** - not just #1
3. **Consider chemical reasonableness**

---

## Quick Reference

```bash
# Full workflow
mkdir -p analysis
lucy pick 1d ./2                                    # 13C peaks
lucy pick hsqc ./5 --dept135 ./3                   # HSQC + multiplicities
lucy pick hmbc ./6 --c13 ./2 --hsqc ./5            # HMBC correlations
lucy lsd generate . C16H10N2O2 -o compound.lsd     # Generate LSD input
lucy lsd run compound.lsd                           # Solve
outlsd 5 < compound.sol > solutions.smi            # Convert to SMILES
lucy lsd rank solutions.smi --spectrum ./2         # Rank by 13C prediction
```
