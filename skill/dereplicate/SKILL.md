---
name: lucy-ng:dereplicate
description: Dereplication only - match observed 13C shifts against reference databases to identify known compounds. Use for quick checks if a compound is already known before deciding whether full CASE is needed.
---

# lucy-ng:dereplicate

Dereplication only - match observed 13C shifts against reference databases to identify known compounds.

---

## Purpose

This skill performs ONLY dereplication (database matching). It does NOT proceed to full structure elucidation. Use this when you want to:

- Quickly check if a compound is already known
- Identify a natural product from a database
- Get candidate matches before deciding whether full CASE is needed

---

## Prerequisites

```bash
lucy --version || pip install lucy-ng
```

Reference databases should be in `data/reference/` or specified by path:
- `nmrshiftdb2withsignals.sd` - NMRShiftDB (~33,000 compounds)
- `coconut_predicted.sd` - COCONUT natural products (optional, ~895,000 compounds)

---

## Workflow

### Step 1: Identify Available Data

Check what NMR experiments are available:

```bash
# List experiments and identify 13C spectrum
for dir in */; do
    if [ -f "$dir/acqus" ]; then
        nuc=$(grep "##\$NUC1=" "$dir/acqus" | head -1)
        echo "Experiment $dir: $nuc"
    fi
done
```

Dereplication requires:
- **13C spectrum** (essential) - either binary data or peak list
- **Molecular formula** (essential) - from user (simulating HRMS)

### Step 2: Request Molecular Formula

**Always ask the user for the molecular formula.** Do not extract from metadata.

```
"Please provide the molecular formula for this compound (typically from HRMS)."
```

### Step 3: Extract 13C Shifts

**Option A: From Bruker spectrum (if binary data exists)**

```bash
lucy dereplicate c13 <bruker_13c_path> <formula> -n 10
```

**Option B: From peak list (if only peaklist.xml available)**

Extract shifts from peaklist.xml and use Python API:

```python
from lucy_ng.dereplication import NMRShiftDBLoader, DereplicationService

# Extract shifts from peaklist.xml (parse the F1 values)
shifts = [187.81, 152.55, 135.73, 123.41, 120.68, 120.09, 118.99, 113.45]

# Load database
loader = NMRShiftDBLoader("data/reference/nmrshiftdb2withsignals.sd")
loader.load()

# Run dereplication
service = DereplicationService(loader)
result = service.dereplicate_from_shifts(shifts, "C16H10N2O2", top_n=10)

for match in result.top_matches:
    print(f"{match.entry.name}: score={match.score:.3f}, avg_dev={match.average_deviation:.2f} ppm")
```

### Step 4: Interpret Results

| Score | Interpretation | Recommendation |
|-------|---------------|----------------|
| > 0.85 | **Strong match** | Likely identified. Verify with literature. |
| 0.65 - 0.85 | **Possible match** | Top candidate often correct. Verify carefully. |
| 0.50 - 0.65 | **Weak match** | Starting hypothesis only. Consider full CASE. |
| < 0.50 | **No match** | Likely novel compound. Proceed to full CASE. |

### Step 5: Report Results

**For strong/possible matches:**

```markdown
## Dereplication Results

**Molecular Formula:** C16H10N2O2
**Database:** NMRShiftDB

### Top Matches

| Rank | Compound | Score | Avg Deviation |
|------|----------|-------|---------------|
| 1 | [Name] | 0.XX | X.X ppm |
| 2 | [Name] | 0.XX | X.X ppm |
| ... | ... | ... | ... |

### Assessment

[Strong/Possible/Weak/No] match found.

**Top candidate:** [Name]
**Confidence:** [High/Medium/Low]
**SMILES:** [if available]

### Recommendation

[Either "Compound likely identified as X" or "Consider full CASE for confirmation"]
```

**For no matches:**

```markdown
## Dereplication Results

**Molecular Formula:** C16H10N2O2
**Database:** NMRShiftDB

No strong matches found (best score: 0.XX)

This suggests:
1. Novel compound not in database
2. Known compound with different stereochemistry
3. Compound not yet added to reference database

### Recommendation

Proceed to full CASE: `/lucy-ng:CASE`
```

---

## Important Notes

1. **This skill does NOT perform full structure elucidation**
2. **Molecular formula must come from user**, not metadata
3. **Symmetry affects matching** - if formula has 16 carbons but only 8 signals, the compound has symmetry
4. **Database coverage varies** - NMRShiftDB is smaller but has experimental shifts; COCONUT is larger but has predicted shifts

---

## Quick Reference

```bash
# Quick dereplication with CLI
lucy dereplicate c13 ./2 C16H10N2O2 -n 10

# Check available databases
ls data/reference/*.sd

# With COCONUT (if available)
lucy dereplicate c13 ./2 C16H10N2O2 -n 10 --db data/reference/coconut_predicted.sd
```
