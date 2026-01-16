---
name: lucy-ng:CASE
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

### Step 12: Generate PDF Report

**Always generate a PDF report** with rendered structures and formatted tables at the end of every CASE analysis.

```python
# Generate PDF report with structures and tables
python3 << 'EOF'
from rdkit import Chem
from rdkit.Chem import Draw, AllChem
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
import io

# Create the PDF document
doc = SimpleDocTemplate(
    "analysis/CASE_Report.pdf",
    pagesize=A4,
    rightMargin=0.75*inch,
    leftMargin=0.75*inch,
    topMargin=0.75*inch,
    bottomMargin=0.75*inch
)

# Styles
styles = getSampleStyleSheet()
title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
    fontSize=20, spaceAfter=30, alignment=TA_CENTER)
heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
    fontSize=14, spaceBefore=20, spaceAfter=10)
normal_style = styles['Normal']

story = []

# Title
story.append(Paragraph("CASE Structure Elucidation Report", title_style))
story.append(Spacer(1, 0.25*inch))

# Summary table
story.append(Paragraph("Summary", heading_style))
summary_data = [
    ["Molecular Formula", "<FORMULA>"],
    ["Molecular Weight", "<MW> Da"],
    ["Degree of Unsaturation (DBE)", "<DBE>"],
    ["LSD Solutions Found", "<COUNT>"],
]
summary_table = Table(summary_data, colWidths=[2.5*inch, 3*inch])
summary_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('PADDING', (0, 0), (-1, -1), 8),
]))
story.append(summary_table)
story.append(Spacer(1, 0.3*inch))

# 13C NMR Data Table
story.append(Paragraph("13C NMR Data", heading_style))
c13_data = [
    ["#", "Shift (ppm)", "Multiplicity", "Assignment"],
    # Add rows for each carbon signal:
    # ["1", "131.29", "C (quat)", "=C< olefinic"],
]
c13_table = Table(c13_data, colWidths=[0.4*inch, 1.2*inch, 1.2*inch, 2.5*inch])
c13_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('PADDING', (0, 0), (-1, -1), 6),
]))
story.append(c13_table)
story.append(Spacer(1, 0.3*inch))

# Structure rendering function
def smiles_to_image(smiles, size=(400, 300)):
    mol = Chem.MolFromSmiles(smiles)
    AllChem.Compute2DCoords(mol)
    img = Draw.MolToImage(mol, size=size)
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

# For each candidate structure:
story.append(Paragraph("Structure Candidates", heading_style))
# candidate_smiles = ["SMILES1", "SMILES2", ...]
# for i, smi in enumerate(candidate_smiles, 1):
#     story.append(Paragraph(f"<b>Rank {i}:</b> {name}", normal_style))
#     story.append(Paragraph(f"MAE: {mae} ppm | SMILES: {smi}", normal_style))
#     img = smiles_to_image(smi)
#     story.append(Image(img, width=3*inch, height=2.25*inch))
#     story.append(Spacer(1, 0.2*inch))

# Ranking comparison table
story.append(Paragraph("Ranking Comparison", heading_style))
rank_data = [
    ["Rank", "Structure", "MAE (ppm)", "Quality", "Within 3ppm"],
    # ["1", "Name", "2.69", "Good", "6/10"],
]
rank_table = Table(rank_data, colWidths=[0.5*inch, 2.5*inch, 1*inch, 0.8*inch, 1*inch])
rank_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('PADDING', (0, 0), (-1, -1), 6),
]))
story.append(rank_table)

# Build PDF
doc.build(story)
print("PDF report generated: analysis/CASE_Report.pdf")
EOF
```

**The PDF report must include:**
1. Summary table (formula, MW, DBE, solution count)
2. 13C NMR data table with shifts, multiplicities, and assignments
3. Key HMBC correlations table
4. Rendered 2D structure images for all candidate structures (using RDKit)
5. Ranking comparison table with MAE scores
6. Recommended structure with larger image

**Required dependencies:**
```bash
pip install reportlab  # For PDF generation (RDKit should already be installed)
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
lucy pick hsqc ./5 ./3 --dept90 ./4                # HSQC + multiplicities
lucy pick hmbc ./6 ./2 ./5 --dept135 ./3           # HMBC correlations
lucy lsd generate . C16H10N2O2 -o analysis/compound.lsd  # Generate LSD input
cd analysis && LSD compound.lsd                     # Solve
lucy lsd rank solutions.smi --spectrum ../2        # Rank by 13C prediction
# Generate PDF report (see Step 12 for full template)
```

**IMPORTANT:** Always generate a PDF report at the end of every CASE analysis (Step 12).
