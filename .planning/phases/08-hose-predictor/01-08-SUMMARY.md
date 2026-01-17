# Phase 8 Summary: HOSE-Based 13C Spectrum Predictor

## Outcome

**Successfully implemented** a pure Python 13C NMR chemical shift predictor using HOSE codes. The system can predict shifts from molecular structure (SMILES) by looking up HOSE codes in a reference database built from COCONUT.

## What Was Built

### Core Module: `lucy_ng.prediction`

| Component | Description |
|-----------|-------------|
| `HOSECodeGenerator` | Wrapper around hosegen library for generating HOSE codes |
| `HOSELookupTable` | Build, save, load HOSE→shift lookup tables from COCONUT SD |
| `C13Predictor` | Main predictor with 6→1 radius fallback strategy |
| `PredictedShift` | Pydantic model for individual predictions |
| `PredictionResult` | Pydantic model for full molecule prediction |

### CLI Commands

```bash
# Predict shifts from SMILES
lucy predict c13 "CC(C)Cc1ccc(cc1)C(C)C(=O)O"

# Build lookup table from COCONUT (one-time)
lucy predict build-table data/reference/coconut_predicted.sd

# Show table info
lucy predict table-info
```

### MCP Tool

- `predict_c13_shifts(smiles, table_path?, max_radius?)` - Predict shifts for AI agents
- Caches lookup table for efficient repeated calls
- Auto-discovers table in default locations

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| HOSE codes over GNN | nmrgnn, CASCADE, nmr_mpnn all had TensorFlow compatibility issues |
| 6-sphere default radius | Higher specificity; fallback to shorter radii when no match |
| COCONUT as data source | ~895K molecules vs 33K in nmrshiftdb2 (27x more data) |
| Gzip-compressed JSON | Balance between size (~1-2GB) and load speed |
| Confidence scoring | Based on radius, match count, and std deviation |
| **No explicit hydrogens** | HOSE codes must be generated from molecules WITHOUT explicit H atoms (see below) |

### CRITICAL: Hydrogen Handling Convention

**All HOSE code operations MUST use molecules WITHOUT explicit hydrogens.**

This affects:
1. **Database generation**: Read SDF/SMILES → do NOT call `AddHs()` → generate HOSE codes
2. **Prediction**: Parse SMILES with `MolFromSmiles()` (implicit H) → generate HOSE codes
3. **Ranking**: Same as prediction

**Why this matters:**
- With explicit H: `C-4;HHHC(//)` (ethanol CH3)
- Without explicit H: `C-4;C(//)` (ethanol CH3)

These are **different HOSE codes** and will NOT match! Using inconsistent hydrogen handling between database generation and prediction causes 100% prediction failures.

**Code verification:**
```python
# CORRECT - no explicit H
mol = Chem.MolFromSmiles("CCO")  # 3 atoms
hose = generate_for_atom(mol, 0, radius=1)  # "C-4;C(//)"

# WRONG - explicit H causes mismatch
mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))  # 9 atoms
hose = generate_for_atom(mol, 0, radius=1)  # "C-4;HHHC(//)" - WON'T MATCH!
```

## Architecture

```
src/lucy_ng/prediction/
├── __init__.py       # Public API: C13Predictor, HOSECodeGenerator, HOSELookupTable
├── hose.py           # HOSE code generation wrapper
├── lookup.py         # Lookup table with build/save/load
├── models.py         # PredictedShift, PredictionResult
└── predictor.py      # C13Predictor with fallback strategy
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 4fd64f7 | feat | Add HOSE-based 13C shift prediction module |
| 16307b5 | feat | Add predict CLI commands |
| 3d175ef | feat | Add predict_c13_shifts MCP tool |
| 72b669e | test | Add tests for prediction module (28 tests) |
| 0413341 | chore | Export prediction module from main package |

## Test Coverage

- **28 new tests** covering:
  - HOSE code generation (6 tests)
  - Lookup table operations (9 tests)
  - Predictor behavior and fallback (6 tests)
  - Data models (3 tests)
  - CLI commands (4 tests)

## Dependencies Added

- `tqdm>=4.0` - Progress bars for table building
- `hose-code-generator` - HOSE code generation (hosegen)

## Usage Example

```python
from lucy_ng import C13Predictor, HOSELookupTable

# Build table once (takes 1-2 hours for full COCONUT)
table = HOSELookupTable.build_from_coconut("coconut_predicted.sd")
table.save("hose_lookup.json.gz")

# Predict shifts
predictor = C13Predictor.from_table_file("hose_lookup.json.gz")
result = predictor.predict_from_smiles("CC(C)Cc1ccc(cc1)C(C)C(=O)O")

print(result.summary())
# 13C Shift Predictions for: CC(C)Cc1ccc(cc1)C(C)C(=O)O
# Carbons: 13, Predicted: 13 (100%)
# ...
```

## Next Steps

1. **Build lookup table** from full COCONUT database (user needs to run `lucy predict build-table`)
2. **Phase 9**: Use predictor for LSD solution ranking by comparing predicted vs experimental shifts

## Notes

- Table building is a one-time operation (~1-2 hours for ~895K molecules)
- Prediction latency is very fast (<100ms per molecule) once table is loaded
- Fallback from radius 6→5→4→3→2→1 ensures most carbons get predictions
- Confidence decreases as fallback radius decreases (less structural specificity)

---
*Completed: 2026-01-11*
