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

### Database: lucy-ng-derep.db

The SQLite compound database `lucy-ng-derep.db` contains 928K compounds:
- **COCONUT**: 895,099 natural products with predicted 13C shifts
- **NMRShiftDB**: 33,344 compounds with experimental 13C shifts
- **111,493 unique molecular formulas** indexed for fast lookup

The CLI automatically discovers the database by searching:
1. `LUCY_DATABASE` environment variable
2. `data/reference/lucy-ng-derep.db` (project location)
3. Common paths (`~/.lucy/`, `~/lucy-ng/`, `~/.local/share/lucy-ng/`)
4. macOS Spotlight (`mdfind`) for fast discovery

If not found, download with:
```bash
lucy database download
```

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

### Step 3: Run Dereplication

**From Bruker spectrum (preferred)**

```bash
lucy dereplicate c13 <bruker_13c_path> <formula> -n 10
```

The CLI automatically discovers and uses `lucy-ng-derep.db`.

**From peak list (Python API)**

```python
from lucy_ng.database import DatabaseQueryService
from lucy_ng.dereplication import DereplicationService

shifts = [187.81, 152.55, 135.73, 123.41, 120.68, 120.09, 118.99, 113.45]

# db_path auto-discovered or specify explicitly
with DatabaseQueryService(db_path) as query:
    service = DereplicationService(query)
    result = service.dereplicate_from_shifts(shifts, "C16H10N2O2", top_n=10)

    for match in result.top_matches:
        print(f"{match.entry.name}: score={match.score:.3f}")
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
**Database:** lucy-ng-derep.db (928K compounds)

### Top Matches

| Rank | Compound | Score | Avg Deviation |
|------|----------|-------|---------------|
| 1 | [Name] | 0.XX | X.X ppm |
| 2 | [Name] | 0.XX | X.X ppm |

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
**Database:** lucy-ng-derep.db (928K compounds)

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
4. **Database is ~100x faster** than SD file scanning due to formula-based indexing

---

## Quick Reference

```bash
# Quick dereplication with CLI (auto-discovers database)
lucy dereplicate c13 ./2 C16H10N2O2 -n 10

# Check database status
lucy database info lucy-ng-derep.db

# Download database if missing
lucy database download
```
