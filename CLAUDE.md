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

### 4. Download Compound Database (REQUIRED for dereplication)
```bash
lucy database download
```

This downloads the pre-built compound database (~343 MB compressed) from Figshare:
- DOI: 10.6084/m9.figshare.31073554
- Contains 928K compounds (COCONUT + NMRShiftDB) with 13C NMR shifts
- Auto-decompresses to `data/reference/compounds.db` (~1.0 GB)

Verify installation:
```bash
lucy database info data/reference/compounds.db
```

### 5. Create Permissions File
Create `.claude/settings.json` in the working directory:
```json
{
  "permissions": {
    "allow": ["Bash(lucy:*)", "Bash(python3:*)", "Bash(ls:*)", "Bash(mkdir:*)"]
  }
}
```

---

## Blind CASE Protocol (For Research Evaluation)

**CRITICAL**: When evaluating AI-based CASE on datasets from public sources (nmrXiv, metabolomics repositories), compound identity may be present in metadata files.

### If You Discover Compound Identity in Metadata

If you find compound names in title files, peaklist.xml, audit logs, or any other files:

1. **STOP** - Do not use this information for structure determination
2. **Do not** look up the compound structure or properties
3. **Do not** infer molecular formula from the name
4. **Treat** the compound as completely unknown
5. **Ask** the user to provide the molecular formula (simulating HRMS)

### Data Sanitization

For valid CASE evaluation, use the `/lucy-ng:sanitize` subskill to remove compound identity before analysis. This requires:

1. Run `/lucy-ng:sanitize` on the dataset
2. Start a **fresh AI session** (to clear memory of compound identity)
3. Perform CASE in the new session with user-provided molecular formula

### Why This Matters

For AI-based CASE research, the AI must demonstrate it can:
- Determine structure from NMR correlations alone
- Handle symmetry and equivalence without prior knowledge
- Generate and rank candidate structures objectively

Using compound identity from metadata invalidates the evaluation.

---

## Available Subskills

| Subskill | Purpose | When to Use |
|----------|---------|-------------|
| `/lucy-ng:sanitize` | Remove compound identity from dataset | Before blind CASE evaluation on public data |
| `/lucy-ng:dereplicate` | Database matching only | Quick check if compound is known |
| `/lucy-ng:CASE` | Full structure elucidation (skip dereplication) | Novel compounds, research evaluation |

### Workflow Selection

```
Is this for blind CASE evaluation on public data?
    ├─ YES → /lucy-ng:sanitize (then fresh session)
    └─ NO → Continue

Do you want to check databases first?
    ├─ YES → /lucy-ng:dereplicate
    │         └─ Match found? → Done
    │         └─ No match? → /lucy-ng:CASE
    └─ NO (skip to full CASE) → /lucy-ng:CASE
```

### Default Behavior

The base `/lucy-ng` skill follows the full workflow: dereplication first, then CASE if needed. Use subskills for specific tasks.

---

## Structure Elucidation Workflow

Once setup is complete, follow this workflow. The best possible outcome is between one and ten solutions. In case of another outcome, the workflow needs to be repeated and adjusted automatically until a satisfactory outcome is reached. In case of no solution structure, constraints and assumptions need to be checked and adjusted. In case of too many solutions, constraints like more HMBC signals or hetero-attachments for specific carbons in the correct shift range need to be added.

**Key Principle: Be Conservative** - Always prefer known compounds over de novo structure determination. Dereplication (database matching) is faster, more reliable, and avoids the combinatorial explosion of possible structures. Only proceed to full structure elucidation if dereplication fails.

### Workflow Steps

0. **Documentation** - Create an `analysis/` folder to document all steps and results. Document immediately after each step below, so that the user can follow while you work.
1. **Dereplication** - Check known compounds first (see Dereplication section below for details)
2. **Symmetry** - `lucy analyze symmetry <data_dir> <formula>` - detect equivalent atoms
3. **Peak Picking**:
   - `lucy pick 1d <c13>` - carbon peaks
   - `lucy pick hsqc <hsqc> --dept135 <dept135>` - direct C-H correlations
   - `lucy pick hmbc <hmbc> --c13 <c13> --hsqc <hsqc>` - long-range correlations
4. **LSD Generation** - `lucy lsd generate <data_dir> <formula> -o output.lsd`
5. **Solve** - `lucy lsd run output.lsd`
6. **Rank** - `lucy lsd rank <smiles_file> --spectrum <c13>` or `--shifts "..."`

---

## NMR Quick Reference

### Experiment Types

| Experiment | Information Provided | Key Insight |
|------------|---------------------|-------------|
| **1H** | Proton chemical shifts | Hydrogen environment |
| **13C** | Carbon chemical shifts | All carbons including quaternary |
| **DEPT-135** | Protonated carbons only | CH/CH3 positive, CH2 negative |
| **DEPT-90** | CH only | Distinguishes CH from CH3 |
| **HSQC** | Direct C-H connections | Which H is attached to which C |
| **HMBC** | 2-3 bond C-H correlations | Connectivity through bonds |
| **COSY** | H-H correlations | Adjacent protons |

### 13C Chemical Shift Regions

| Region (ppm) | Typical Assignment |
|--------------|-------------------|
| 0-50 | Aliphatic carbons (CH3, CH2, CH) |
| 50-90 | Carbons attached to oxygen (C-O) |
| 90-120 | Anomeric carbons, alkenes |
| 120-160 | Aromatic carbons, alkenes |
| 160-180 | Carboxylic acids, esters, amides |
| 180-220 | Aldehydes, ketones |

### Lucy-ng Tool Output Reference

| Tool | Key Output Fields |
|------|------------------|
| `read_spectrum_1d` | nucleus, frequency, ppm_range, data_points |
| `pick_peaks_1d` | peaks (ppm, intensity), count |
| `pick_hsqc_peaks` | peaks (carbon_ppm, proton_ppm), multiplicities |
| `pick_hmbc_peaks` | peaks (carbon_ppm, proton_ppm), validated_count |
| `analyze_symmetry` | expected_carbons, observed_carbons, symmetry_detected |
| `dereplicate_c13` | is_match, top_matches (name, smiles, score) |
| `predict_c13_shifts` | predictions (atom_index, shift, confidence), success |
| `rank_lsd_solutions` | ranked_solutions (smiles, mae, quality, deviations, within_3ppm, within_5ppm) |

---

## Common Pitfalls and Solutions

### Pitfall 1: Signal Count ≠ Atom Count (Symmetry)

**The Problem**: The molecular formula says C13H18O2 (13 carbons), but you only see 10-11 peaks in the 13C spectrum.

**Why This Happens**: Molecular symmetry causes equivalent atoms to produce identical signals that overlap.

**What To Do**:
1. Use `lucy analyze symmetry` to detect discrepancies
2. Look at HSQC intensities - doubled signals have ~2x intensity
3. Consider common symmetric motifs:
   - Para-substituted benzene (2 pairs of equivalent CH)
   - Isopropyl groups (2 equivalent CH3)
   - Gem-dimethyl groups (2 equivalent CH3)
   - Symmetric ethers/esters

**Key Insight**: If formula hydrogens > sum of (multiplicity × count) from HSQC, you have equivalent positions.

### Pitfall 2: Quaternary Carbons Are Invisible in DEPT/HSQC

**The Problem**: Some carbons appear in the 13C spectrum but have no HSQC correlation.

**Why This Happens**: Quaternary carbons (C with no attached H) don't appear in DEPT or HSQC experiments.

**What To Do**:
1. Compare 13C peak count with DEPT-135 peak count
2. The difference = quaternary carbons
3. Quaternary carbons are only connected to the structure through HMBC correlations
4. Common quaternary carbons:
   - Carbonyl carbons (C=O) at 160-220 ppm
   - Aromatic junction carbons at 120-160 ppm
   - Bridgehead carbons

### Pitfall 3: HMBC Noise Creates False Correlations

**The Problem**: Raw HMBC peak picking finds hundreds of peaks, most of which are noise.

**Why This Happens**: HMBC is an insensitive experiment with many artifacts (t1 noise, 1J bleeding).

**What To Do**:
1. **Always use guided HMBC picking** (`lucy pick hmbc`)
2. The guided picker validates that:
   - The carbon position exists in 13C/DEPT
   - The proton position exists in HSQC
3. This typically reduces peak count from hundreds to tens

**Key Insight**: More HMBC correlations = better LSD results, but only if they're real correlations.

### Pitfall 4: Too Many LSD Solutions

**The Problem**: LSD generates hundreds or thousands of candidate structures.

**Why This Happens**: Insufficient or incorrect constraints.

**Common Causes**:
1. Missing HMBC correlations (manually constructed vs. real data)
2. Incorrect atom multiplicities
3. Symmetry not accounted for
4. Quaternary carbons with no HMBC connections

**What To Do**:
1. Verify all HMBC correlations from experimental data
2. Check that all protonated carbons have HSQC correlations
3. Ensure molecular formula is correct
4. Consider if the compound has unusual features (macrocycles, etc.)

**Expected Results**:
- 1-10 solutions: Good constraint quality
- 10-100 solutions: May need more data or review
- 100+ solutions: Likely missing critical constraints

### Pitfall 5: Heteroatom Positions

**The Problem**: Oxygen and nitrogen atoms don't appear directly in standard NMR experiments.

**Why This Happens**: Most heteroatoms have no attached protons (carbonyl O, ether O) or exchange rapidly (OH, NH).

**What To Do**:
1. Infer heteroatom positions from:
   - Molecular formula (tells you how many O, N, etc.)
   - Chemical shifts (C-O carbons appear 50-90 ppm)
   - Carbonyl carbons (160-220 ppm)
2. LSD uses the molecular formula to place heteroatoms
3. Use BOND or LIST/PROP constraints to guide heteroatom attachment

---

## Reference Data

### Pre-built Compound Database (Recommended)

A pre-built SQLite database with 928K compounds is available for download:

```bash
lucy database download
```

| Property | Value |
|----------|-------|
| **DOI** | [10.6084/m9.figshare.31073554](https://doi.org/10.6084/m9.figshare.31073554) |
| **Compounds** | 928,443 total |
| **Sources** | COCONUT (895K) + NMRShiftDB (33K) |
| **Formulas** | 111,493 unique |
| **Size** | ~343 MB download, ~1 GB uncompressed |

The database is indexed by molecular formula for fast O(1) lookup during dereplication.

### Alternative: Raw SD Files

Reference databases in SD format are stored in `data/reference/`:

| File | Description | Entries | Size | Included |
|------|-------------|---------|------|----------|
| `nmrshiftdb2withsignals.sd.gz` | NMRShiftDB SD file with 13C chemical shifts | ~33,000 | ~20 MB | **Yes** |
| `coconut_predicted.sdf` | COCONUT natural products (predicted shifts) | ~895,000 | ~4.8 GB | No |

**Building from SD files**: If you have the raw SD files, you can build a database manually:
```bash
lucy database build --nmrshiftdb data/reference/nmrshiftdb2withsignals.sd \
                    --coconut data/reference/predicted_coconut.sdf \
                    -o data/reference/compounds.db
```

**Legacy SD file usage**: The CLI `lucy dereplicate c13` command can also use SD files directly, but the database is ~100x faster for lookups

---

## Dereplication

Dereplication matches observed 13C shifts against reference databases to identify known compounds before attempting de novo structure elucidation.

### Two Approaches

**Approach A: From Bruker Spectrum (preferred when binary data exists)**
```bash
lucy dereplicate c13 <bruker_experiment_path> <formula>
```
Example:
```bash
lucy dereplicate c13 data/compound/2 C14H16 -n 10
```
This requires the binary spectrum files (1r in pdata/1/).

**Approach B: From Shift List (when binary data is missing)**

When Bruker binary spectrum files are missing but peak lists are available (e.g., from peaklist.xml or manual extraction), use the Python API directly:

```python
from lucy_ng.dereplication import NMRShiftDBLoader, DereplicationService

# Extract shifts from peaklist.xml or other source
shifts = [139.94, 138.51, 137.16, 136.53, 133.17, ...]

# Load database (from lucy-ng directory)
loader = NMRShiftDBLoader("data/reference/nmrshiftdb2withsignals.sd")
loader.load()

# Run dereplication
service = DereplicationService(loader)
result = service.dereplicate_from_shifts(shifts, "C14H16", top_n=10)

# Check results
for match in result.top_matches:
    print(f"{match.entry.name}: score={match.score:.3f}")
```

### When to Use Each Approach

| Situation | Approach |
|-----------|----------|
| Full Bruker data with binary files | Use CLI: `lucy dereplicate c13` |
| Only peaklist.xml available | Use Python API: `dereplicate_from_shifts()` |
| Peaks extracted from TopSpin | Use Python API: `dereplicate_from_shifts()` |
| Manual peak list from literature | Use Python API: `dereplicate_from_shifts()` |

### Interpreting Results

Results are ranked by:
1. **Score** (higher is better): fraction of peaks matched
2. **Average deviation** (lower is better): used as tiebreaker when scores are equal

The compound with the highest score AND lowest average deviation ranks #1.

---

## LSD Integration

### LSD File Structure

**Important:** LSD does NOT have a molecular formula command. The formula is defined implicitly by the sum of all MULT atom definitions.

**File structure:**
```
; Comments start with semicolon
MULT 1 C 2 0    ; Define atoms with MULT
MULT 2 C 2 0
...
HSQC 4 4        ; Define correlations (HSQC FIRST!)
HMBC 2 8        ; Then HMBC
...
; NO ELIM command on first run - only add if needed
```

**Note:** Do NOT use `FORM`, `FORMULA`, or similar commands - these are invalid in LSD.

### Correlation Order (CRITICAL)

HSQC/HMQC commands MUST appear BEFORE any HMBC commands that reference those proton positions. LSD defines proton positions through HSQC correlations.

**Correct order:**
```
; 1. Atom definitions (MULT)
MULT 1 C 2 0
...

; 2. HSQC correlations - defines proton positions
HSQC 4 4    ; H4 is now defined
HSQC 6 6    ; H6 is now defined

; 3. HMBC correlations - can now reference H4, H6
HMBC 2 4    ; C2 correlates to H4
HMBC 3 6    ; C3 correlates to H6
```

**Error if wrong order:** "Cannot set an HMBC correlation between X and H-Y because H-Y is not defined by an HMQC command."

### Hybridization Rules

**CRITICAL:** LSD requires an EVEN number of sp2 atoms.

Each double bond connects two sp2 atoms, so an odd count is invalid.

**Common sp2 atoms:**
- Carbonyl carbons (C=O): sp2
- Carbonyl oxygens (C=O): sp2
- Aromatic carbons: sp2
- Aromatic nitrogens (pyridine-type): sp2

**Common sp3 atoms:**
- Saturated carbons (CH3, CH2, CH): sp3
- Ether/hydroxyl oxygens: sp3
- Amine nitrogens (NR3): sp3
- N-methyl nitrogens: sp3

**Validation:** Count sp2 atoms before running LSD. If odd, adjust one atom's hybridization.

**Example - Caffeine (C8H10N4O2):**
- 5 sp2 carbons (2 carbonyl + 3 aromatic)
- 2 sp2 oxygens (2 carbonyl)
- 1 sp2 nitrogen (imidazole ring)
- 3 sp3 nitrogens (N-methyl positions)
- Total: 8 sp2 atoms (even) ✓

### Heteroatom Attachment Constraints

There are TWO approaches to constrain heteroatom attachment:

#### Approach A: Direct BOND (Simple cases)

Use when you know the exact atoms that should be bonded:

```
; C1 (carbonyl at 155 ppm) bonded to O13
BOND 1 13

; N-CH3 carbon bonded to nitrogen
BOND 6 9
```

**Pros:** Simple, explicit
**Cons:** Less flexible, may over-constrain

#### Approach B: LIST + ELEM + PROP (Flexible)

Use when you want to constrain by element type without specifying exact atoms:

```
; Create list of carbonyl carbons (atoms 1 and 2)
LIST L1 1 2

; Create list of all oxygens
ELEM L2 O

; Each carbonyl must have exactly 1 oxygen neighbor
PROP L1 1 L2

; Create list of N-CH3 carbons
LIST L3 6 7 8

; Create list of all nitrogens
ELEM L4 N

; Each N-CH3 carbon must have exactly 1 nitrogen neighbor
PROP L3 1 L4
```

**Pros:** More flexible, lets LSD find optimal assignment
**Cons:** More verbose

#### When to use each:

| Scenario | Recommended |
|----------|-------------|
| Carbonyl C=O | BOND (usually clear which O) |
| N-CH3 attachment | LIST/PROP (N assignment flexible) |
| Ether oxygen | LIST/PROP (attachment flexible) |

### LSD Command Format

The LSD user guide for full reference is at https://nuzillard.github.io/LSD/MANUAL_ENG.html.

**Atom definitions**: MULT command with hybridization and H-count
```
MULT 1 C 2 0    ; atom 1, carbon, sp2 hybridization, 0 hydrogens (quaternary)
MULT 2 C 2 1    ; atom 2, carbon, sp2 hybridization, 1 hydrogen (CH)
MULT 3 C 3 3    ; atom 3, carbon, sp3 hybridization, 3 hydrogens (CH3)
MULT 4 N 3 0    ; atom 4, nitrogen, sp3, 0 hydrogens
MULT 5 O 2 0    ; atom 5, oxygen, sp2, 0 hydrogens (carbonyl)
```

**HSQC correlations**: Direct C-H attachment
```
HSQC 2 2    ; carbon 2 has directly attached proton (defines H2)
HSQC 3 3    ; carbon 3 has directly attached protons (defines H3)
```

**HMBC correlations**: 2-3 bond C-H correlations
```
HMBC 1 2    ; carbon 1 correlates to proton attached to carbon 2
HMBC 1 3    ; carbon 1 correlates to protons attached to carbon 3
```

**ELIM command**: Allows elimination of invalid HMBC/COSY correlations (USE ONLY AS LAST RESORT)
```
ELIM P1 P2
; P1 = maximum number of correlations that can be eliminated
; P2 = maximum bond distance limit for eliminated correlations (0 = no limit)
```
**IMPORTANT:** Do NOT include ELIM in the first LSD run. Only add ELIM if LSD returns 0 solutions and you have verified all other constraints are correct. ELIM allows LSD to ignore correlations that may be artifacts or errors, but using it prematurely can lead to thousands of incorrect solutions instead of a unique correct one.

### Converting LSD Solutions to SMILES

After running LSD, convert solutions using `outlsd`:

```bash
outlsd 5 < compound.sol > solutions.smi
```

**Format options:**
| Code | Format |
|------|--------|
| 1 | Bond lists |
| 5 | SMILES |
| 6 | 2D coordinates (.coo) |
| 7 | SDF 2D (.mol) |
| 8 | SDF 3D without H (.mol) |
| 9 | SDF 3D with H (.mol) |

**Complete workflow:**
```bash
# Run LSD
LSD compound.lsd

# Convert to SMILES
outlsd 5 < compound.sol > solutions.smi

# Rank solutions
lucy lsd rank solutions.smi --shifts "155.08,151.58,..."
```

### Solution Ranking and MAE Interpretation

When LSD produces multiple solutions, rank them using `lucy lsd rank`:

**How it works:**
1. For each solution SMILES, predict 13C shifts using HOSE codes
2. For each prediction, find the closest experimental peak
3. Calculate MAE (Mean Absolute Error) using **all** shifts
4. Sort solutions by MAE (lower = better match)

**New output format (v0.1.1+):**
```
  1. Solution 188: MAE=3.26 ppm (Good)
     CC1CC(C)=C(C1)CC(=O)C
     ≤3ppm: 6/10 | ≤5ppm: 9/10
```

The output shows:
- **MAE with quality label**: "Excellent", "Good", "Moderate", or "Poor"
- **Multi-level tolerance**: How many shifts fall within 3 ppm and 5 ppm

**Interpreting MAE scores:**

| MAE (ppm) | Quality Label | Interpretation |
|-----------|---------------|----------------|
| < 2.0 | Excellent | High confidence in structure |
| 2.0 - 3.5 | Good | Reasonable confidence |
| 3.5 - 5.0 | Moderate | Review carefully, check alternatives |
| > 5.0 | Poor | Likely incorrect or unusual structure |

**Understanding the tolerance summary:**
- `≤3ppm: 6/10` means 6 of 10 predicted shifts are within 3 ppm of an experimental peak
- `≤5ppm: 9/10` means 9 of 10 are within 5 ppm
- This multi-level view is more informative than a single hard cutoff

**Why correct structures may not rank #1:**
1. **HOSE prediction errors**: Carbonyl carbons can vary ±5-10 ppm; conjugated systems are harder to predict
2. **Symmetry effects**: Equivalent carbons produce one signal but multiple predictions
3. **Unusual environments**: Strained rings, unusual substituents reduce prediction accuracy

**Best practices:**
- Always examine the **top 10-20 candidates** for chemical reasonableness
- A structure with MAE=3.5 (Good) and sensible chemistry may be correct over one with MAE=3.2 but unusual features
- Use the tolerance summary to understand where predictions differ
- Cross-reference with dereplication hits if available

### LSD Runner Notes

- LSD writes solution count to **stderr**, not stdout
- Success is determined by finding solutions, not just return code
- Solution files are written as `.sol` files in the working directory

---

## Manual LSD File Construction

When `lucy lsd generate` fails (e.g., missing DEPT), construct the LSD file manually:

### Template
```
; LSD input file for [FORMULA]
; Atom definitions (MULT)
MULT 1 C 2 0    ; sp2 quaternary carbon (e.g., carbonyl)
MULT 2 C 2 1    ; sp2 CH (aromatic)
MULT 3 C 3 3    ; sp3 CH3
MULT 4 N 3 0    ; sp3 nitrogen (N-methyl)
MULT 5 O 2 0    ; sp2 oxygen (carbonyl)
...

; HSQC correlations (define H positions FIRST)
HSQC 2 2        ; H2 on C2
HSQC 3 3        ; H3 on C3

; HMBC correlations (AFTER HSQC)
HMBC 1 2        ; C1 correlates to H2
HMBC 1 3        ; C1 correlates to H3

; Heteroatom constraints (BOND or LIST/PROP)
BOND 1 5        ; C1 bonded to O5 (carbonyl)

; NO ELIM on first run!
```

### Checklist
1. All carbons from 13C defined with MULT
2. Heteroatoms from formula added (N, O, S, etc.)
3. sp2 count is EVEN
4. HSQC correlations defined for protonated carbons
5. HMBC correlations reference only defined H positions
6. Heteroatom constraints added (BOND or LIST/PROP)
7. **NO ELIM command** on first run (add only if 0 solutions found)

### LSD Troubleshooting

**Common errors and solutions:**

| Error | Cause | Solution |
|-------|-------|----------|
| "Odd total sum of valences" | Hydrogen count wrong | Verify: sum of (multiplicity × count) = formula H |
| "Cannot set HMBC correlation" | HSQC not defined first | Move all HSQC commands before HMBC |
| "No solution found" | Over-constrained | 1) Check sp2 count is even, 2) verify HMBC correlations, 3) only then try `ELIM 1 0` |
| Too many solutions (>100) | Under-constrained | Add more HMBC correlations, verify existing ones are correct |

**Before running LSD, verify:**

- [ ] **Hydrogen count**: Sum of (CH3 × 3 + CH2 × 2 + CH × 1) = formula H count
- [ ] **sp2 count is EVEN**: Count all sp2 atoms (carbonyl C+O, aromatic, C=C)
- [ ] **NO ELIM on first run**: Only add ELIM if you get 0 solutions after verifying constraints
- [ ] **Correlation order**: All HSQC commands must come before any HMBC commands

**If 0 solutions found**, troubleshoot in this order:
1. Verify sp2 count is even
2. Check hydrogen count matches formula
3. Review HMBC correlations for errors or artifacts
4. Only then try `ELIM 1 0` to allow eliminating 1 correlation
5. If still no solution, try `ELIM 2 0`, etc. incrementally

---

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
- HMBC provides long-range correlations between carbons and hydrogens. Only peaks where the carbon shift matches a picked peak from the 1D carbon spectrum and the proton shift matches a proton shift from the HSQC signals are kept as being valid.

### Molecular Symmetry

**Important**: Equivalent carbons appear as single NMR signals due to molecular symmetry.

Example - Ibuprofen (para-disubstituted benzene):
- Molecular formula: C13H18O2 (13 carbons)
- Observed 13C signals: ~10-11 (due to symmetry)
- Two ortho CH carbons are equivalent → 1 signal
- Two meta CH carbons are equivalent → 1 signal

The AI agent must detect this discrepancy between molecular formula and observed signals to properly constrain structure elucidation. Symmetry affects both carbon and proton counts.

### Working with APT Instead of DEPT-135

APT (Attached Proton Test) provides similar multiplicity information to DEPT:
- **Positive peaks**: CH and CH3 (odd number of attached protons)
- **Negative peaks**: CH2 and quaternary C (even number of attached protons)

When DEPT-135 is unavailable but APT is present:
1. Use `lucy pick 1d` on APT spectrum for carbon positions
2. Pick HSQC peaks manually with `PeakPicker2D` at threshold 0.05
3. Cross-reference APT phase with HSQC intensities for multiplicity:
   - High-intensity HSQC peak + positive APT = likely CH3
   - Medium-intensity HSQC + positive APT = likely CH
   - HSQC present + negative APT = CH2
   - No HSQC + negative APT = quaternary C

**Note**: APT cannot distinguish CH from CH3 without additional information (HSQC intensity, chemical shift patterns).

### HSQC: Use DEPT-Guided Picker (Preferred)

For HSQC peak picking, **always use `DEPTGuidedPicker`** instead of raw `PeakPicker2D` when DEPT-135 is available.

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
1. Carbon (F1) must match a known carbon from 13C or DEPT spectrum (±1.5 ppm). Also look for HMBC signals for the quaternary carbons.
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

---

## Decision Trees

### When to Proceed with Full Elucidation

```
Start
  │
  ├─ Dereplication found match?
  │    ├─ YES → Report match, confidence level, DONE
  │    └─ NO → Continue
  │
  ├─ All necessary spectra available?
  │    ├─ YES → Continue
  │    └─ NO → Request missing data:
  │           - Need at minimum: 13C, HSQC, HMBC
  │           - DEPT highly recommended
  │
  ├─ Molecular formula provided?
  │    ├─ YES → Continue
  │    └─ NO → Request from user (essential!)
  │
  └─ Proceed with peak picking and LSD
```

### Handling Symmetry

```
Symmetry Analysis Result
  │
  ├─ observed_carbons == expected_carbons?
  │    └─ No symmetry → Proceed normally
  │
  ├─ observed_carbons < expected_carbons?
  │    │
  │    ├─ Difference = 2?
  │    │    └─ Likely: one pair of equivalent carbons
  │    │       (e.g., para-benzene CH, isopropyl CH3)
  │    │
  │    ├─ Difference = 4?
  │    │    └─ Likely: two pairs of equivalent carbons
  │    │       (e.g., para-benzene ring)
  │    │
  │    └─ Larger difference?
  │         └─ Highly symmetric molecule
  │            (e.g., C2 or higher symmetry)
  │
  └─ Check HSQC intensities for confirmation
       - Doubled signals have ~2x intensity
```

### LSD Result Interpretation

```
LSD Solution Count
  │
  ├─ 0 solutions
  │    └─ Over-constrained. Check IN ORDER:
  │       1. sp2 count is even?
  │       2. Hydrogen count matches formula?
  │       3. HMBC correlations correct?
  │       4. Wrong molecular formula?
  │       5. Only after all above: try ELIM 1 0
  │
  ├─ 1 solution
  │    └─ IDEAL RESULT - High confidence
  │       - Verify solution makes chemical sense
  │       - Check for unusual features
  │       - Verify with lucy lsd rank (MAE score)
  │
  ├─ 2-10 solutions
  │    └─ Good result → USE RANKING
  │       - lucy lsd rank to identify best match
  │       - Examine differences between top candidates
  │       - Often differ in stereochemistry or regiochemistry
  │
  ├─ 10-100 solutions
  │    └─ Under-constrained → ADD MORE CONSTRAINTS
  │       - Add missing HMBC correlations
  │       - Check if ELIM was used (remove it!)
  │       - Use ranking to narrow candidates
  │
  └─ >100 solutions
       └─ Severely under-constrained
          - Was ELIM used? Remove it first!
          - Request additional NMR data
          - Add more HMBC correlations
          - Add heteroatom constraints (BOND or LIST/PROP)
```

---

## Result Reporting Templates

### Dereplication Results

**Interpreting dereplication scores:**

| Score | Interpretation | Recommended Action |
|-------|---------------|-------------------|
| > 0.85 | Strong match | Likely identified; verify with literature |
| 0.65 - 0.85 | Possible match | Top candidate often correct; verify carefully |
| 0.50 - 0.65 | Weak match | Use as starting hypothesis; full elucidation recommended |
| < 0.50 | No match | Likely novel compound; proceed with full elucidation |

**Note**: A score of 0.65-0.85 often indicates the correct compound, especially when the molecular formula matches exactly. The score reflects peak overlap, which can be affected by reference data quality and experimental conditions.

**Strong match** (score > 0.85):
```
"The compound matches [NAME] in the database with a score of [X].
This is a known compound: [SMILES/structure description].
The match is based on [N] carbon shifts with an average deviation of [Y] ppm."
```

**Possible match** (score 0.50-0.85):
```
"There is a potential match to [NAME] with a score of [X].
This should be verified by comparing predicted vs. observed shifts.
Consider proceeding with structure elucidation to confirm.
Key differences are at positions: [list any outliers]."
```

**No match** (score < 0.50 or no candidates):
```
"No database match found. This may be:
1. A novel compound not in the database
2. A known compound with different stereochemistry
3. A compound not yet added to the reference database

Proceeding with de novo structure elucidation..."
```

### LSD Results

**Report solutions like this**:
```
"LSD found [N] candidate structure(s).

Solution 1: [Description]
- Core scaffold: [aromatic/aliphatic/mixed]
- Key features: [functional groups, ring systems]
- Consistent with: [which spectroscopic features]

[If multiple solutions, describe key differences]

The solutions differ in:
- Position of [functional group]
- Ring fusion pattern
- Stereochemistry at [position]
"
```

### Reporting Uncertainty

**Always be transparent about**:
- Missing data that would improve confidence
- Assumptions made during analysis
- Alternative interpretations
- Recommended additional experiments

---

## Quick Reference Card

### Essential Workflow
1. **Dereplication FIRST** - Always check databases before full analysis
2. **Check symmetry** - Explains "missing" signals
3. **Use guided peak picking** - Reduces noise dramatically
4. **Validate data** - Cross-check between experiments
5. **Run LSD** - Generate candidate structures
6. **Rank solutions** - Use `lucy lsd rank` if multiple candidates
7. **Interpret results conservatively** - Report uncertainty

### Red Flags to Watch For
- Fewer signals than expected atoms → Symmetry
- More signals than expected → Impurity or wrong formula
- Zero LSD solutions → Over-constrained (check sp2 count, HMBC correlations)
- Thousands of LSD solutions → Under-constrained OR using ELIM when not needed

### Key Tolerances
- 13C chemical shift matching: ±1.5 ppm (carbonyl), ±0.8 ppm (aliphatic)
- HSQC validation: ±1.0 ppm (13C dimension)
- HMBC validation: ±1.5 ppm (13C), ±0.1 ppm (1H)
- Dereplication: score > 0.85 strong, 0.65-0.85 possible, < 0.50 no match
- Solution ranking: MAE < 2.0 = Excellent, 2-3.5 = Good, 3.5-5 = Moderate, > 5 = Poor

### Ranking Output Interpretation
The ranking now shows quality labels and multi-level tolerance:
```
  1. Solution 188: MAE=3.26 ppm (Good)
     CC1CC(C)=C(C1)CC(=O)C
     ≤3ppm: 6/10 | ≤5ppm: 9/10
```
- **MAE** is the primary quality metric (lower is better)
- **Quality label** provides quick assessment
- **Tolerance summary** shows how many predictions are close vs. outliers
- Always review top 10-20 candidates, not just #1

### When to Ask for Help
- Conflicting data between experiments
- Unusual chemical shifts outside normal ranges
- Molecular formula doesn't match observed data
- User requests interpretation beyond available data

---

## Developer Reference

### Quick Reference

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

### Project Structure

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

### Technology Stack

- **Python 3.10+** - minimum version
- **Pydantic v2** - data models with validation
- **nmrglue** - Bruker NMR file parsing
- **NumPy/SciPy** - numerical processing
- **RDKit** - SD file parsing for reference databases
- **hatch** - build system
- **pytest** - testing
- **ruff** - linting

### Critical Architecture Decisions

#### HOSE Codes: NO Explicit Hydrogens

**All HOSE code operations MUST use molecules WITHOUT explicit hydrogens.**

This is critical for consistency between database generation and prediction. Using inconsistent hydrogen handling causes 100% prediction failures.

| Operation | Correct Approach |
|-----------|------------------|
| Database generation | Read SDF → do NOT call `AddHs()` → generate HOSE |
| Prediction from SMILES | `MolFromSmiles()` (implicit H) → generate HOSE |
| Prediction from MOL | `MolFromMolBlock(removeHs=True)` → generate HOSE |

**Example:**
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
- **mypy** - type checking (strict mode)
