# Merge Plan: Visualization + LSD Analyzer + Reporting Integration

## Overview

Three complementary features need to be unified for publication-quality CASE reporting:

| Feature | Location | Purpose |
|---------|----------|---------|
| **Correlation Diagrams** | `visualization/` | SVG with HMBC arrows, chemical shift labels |
| **LSD Analyzer** | `lsd/analyzer.py` | Parse .sol files, J-coupling paths, atom numbering |
| **CASE Skill** | `skill/CASE/SKILL.md` | Workflow + PDF report generation |

**Goal**: Create an integrated reporting system that produces:
- Clean 2D structures with publication-style atom numbering (red annotations)
- HMBC correlation diagrams with curved arrows and J-coupling labels
- Complete PDF reports with all NMR tables and structure images

---

## Current State

### This Session: Visualization Module (`visualization/`)
- `CorrelationDiagramGenerator.generate(smiles, correlations, shifts)` → SVG
- Bezier arrow routing with collision avoidance
- Chemical shift annotations
- CLI: `lucy visualize correlations`
- MCP: `generate_correlation_diagram`

### Parallel Session: LSD Analyzer (`lsd/analyzer.py`)
- `LSDSolutionAnalyzer.parse_sol_file()` → List[SolutionGraph]
- `SolutionGraph.to_rdkit_mol()` → Mol with AtomMapNum
- `SolutionGraph.shortest_path()` → BFS for J-coupling
- `SolutionGraph.draw_with_atom_numbers()` → PNG/SVG (embedded labels)
- CLI: `lucy lsd analyze compound.sol compound.lsd --draw`

### Parallel Session: CASE Skill Workflow
- Step 11: J-coupling analysis
- Step 12: Markdown report template
- Step 13: PDF report via ReportLab with tables and structure images

---

## Integration Tasks

### Task 1: Publication-Style Atom Numbering

**Problem**: Current `draw_with_atom_numbers()` embeds labels in atoms ("C7/H7"), cluttering the structure.

**Solution**: Add separate red text annotations positioned near atoms.

**Files to modify**: `visualization/diagram_generator.py`, `visualization/svg_builder.py`, `visualization/models.py`

```python
# In models.py - add to DiagramConfig
class DiagramConfig:
    # ... existing fields ...
    show_atom_numbers: bool = False
    atom_number_color: str = "#CC0000"  # Red like publications
    atom_number_font_size: float = 9.0
    atom_number_offset: float = 10.0

# In diagram_generator.py - new method
def _add_atom_number_annotations(
    self,
    builder: SVGBuilder,
    positions: dict[int, AtomPosition],
    atom_numbers: dict[int, str],  # 0-based RDKit idx → label
) -> None:
    """Add publication-style atom numbers as separate annotations."""
    for idx, label in atom_numbers.items():
        if idx not in positions:
            continue
        pos = positions[idx]
        # Smart positioning: offset away from molecule center
        label_x = pos.x + self.config.atom_number_offset
        label_y = pos.y - self.config.atom_number_offset / 2
        builder.add_text_label(
            label_x, label_y, label,
            font_size=self.config.atom_number_font_size,
            color=self.config.atom_number_color,
            anchor="start",
        )
```

### Task 2: Generate from .sol Files

**Purpose**: Create diagrams directly from LSD solution output (no SMILES needed).

**Files to modify**: `visualization/diagram_generator.py`

```python
def generate_from_sol_file(
    self,
    sol_path: Path | str,
    lsd_path: Path | str,
    solution_number: int = 1,
    show_j_coupling: bool = False,
) -> DiagramResult:
    """Generate diagram from LSD solution with optional J-coupling labels.

    Args:
        sol_path: Path to .sol file with molecular connectivity
        lsd_path: Path to .lsd file with correlations and shifts
        solution_number: Which solution to visualize (1-based)
        show_j_coupling: Add ²J/³J labels on arrows
    """
    from lucy_ng.lsd.analyzer import LSDSolutionAnalyzer

    # Analyze solution
    results = LSDSolutionAnalyzer.analyze(sol_path, lsd_path, solution_number)
    if not results:
        raise ValueError(f"Solution {solution_number} not found")
    result = results[0]

    # Get SMILES from solved structure
    smiles = result.graph.to_smiles()

    # Convert correlations (LSD 1-based → RDKit 0-based)
    correlations = []
    j_couplings = {}  # (source, target) → j value

    for c in result.correlations:
        corr = Correlation(
            source_atom=c.carbon_idx - 1,
            target_atom=c.proton_idx - 1,
            correlation_type=CorrelationType.HMBC,
        )
        correlations.append(corr)
        if show_j_coupling and c.j_coupling:
            j_couplings[(c.carbon_idx - 1, c.proton_idx - 1)] = c.j_coupling

    # Get shifts from analysis
    shifts = {c.carbon_idx - 1: c.carbon_shift
              for c in result.correlations if c.carbon_shift}

    # Build atom number map (LSD numbering)
    atom_numbers = {i - 1: str(i) for i in result.graph.atoms.keys()}

    return self._generate_with_annotations(
        smiles=smiles,
        correlations=correlations,
        carbon_shifts=shifts,
        atom_numbers=atom_numbers if self.config.show_atom_numbers else None,
        j_couplings=j_couplings if show_j_coupling else None,
    )
```

### Task 3: J-Coupling Arrow Annotations

**Purpose**: Show ²J, ³J labels on HMBC arrows.

**Files to modify**: `visualization/svg_builder.py`, `visualization/diagram_generator.py`

```python
# In svg_builder.py
def add_j_coupling_label(
    self,
    x: float,
    y: float,
    j_value: int,
    font_size: float = 8.0,
    color: str = "#666666",
) -> None:
    """Add J-coupling notation near an arrow."""
    superscripts = {2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶"}
    label = f"{superscripts.get(j_value, str(j_value))}J"
    self.add_text_label(x, y, label, font_size=font_size, color=color)
```

### Task 4: Deprecate Embedded Atom Labels

**Purpose**: Remove the cluttered "C7/H7" style from `SolutionGraph.draw_with_atom_numbers()`.

**Files to modify**: `lsd/analyzer.py`

Option A: Deprecate and redirect to visualization module
```python
def draw_with_atom_numbers(self, output_path, ...):
    """DEPRECATED: Use CorrelationDiagramGenerator for publication-quality output."""
    import warnings
    warnings.warn(
        "draw_with_atom_numbers is deprecated. Use "
        "CorrelationDiagramGenerator.generate_from_sol_file() for "
        "publication-quality diagrams with clean atom numbering.",
        DeprecationWarning
    )
    # Keep existing implementation for backwards compatibility
    ...
```

Option B: Update to use visualization module internally
```python
def draw_with_atom_numbers(self, output_path, show_correlations=False, ...):
    """Draw structure with publication-style atom numbering."""
    from lucy_ng.visualization import CorrelationDiagramGenerator, DiagramConfig

    config = DiagramConfig(
        show_atom_numbers=True,
        show_chemical_shifts=False,
        show_legend=False,
    )
    gen = CorrelationDiagramGenerator(config)
    # ... delegate to visualization module
```

### Task 5: CLI Updates

**Files to modify**: `cli/visualize.py`, `cli/lsd.py`

```bash
# New options for lucy visualize correlations
lucy visualize correlations --sol compound.sol --lsd compound.lsd \
    --show-atom-numbers \
    --show-j-coupling \
    --solution 1 \
    -o diagram.svg

# Update lucy lsd analyze --draw to use new style
lucy lsd analyze compound.sol compound.lsd \
    --draw-style publication \  # New: clean atom annotations
    --draw solution_{n}.svg
```

### Task 6: PDF Report Integration

**Purpose**: Generate publication-quality correlation diagrams in PDF reports.

**Files to modify**: `skill/CASE/SKILL.md` (update Step 13 template)

The PDF report should include:

1. **Structure with Atom Numbers** (before HMBC table)
   - Use `CorrelationDiagramGenerator` with `show_atom_numbers=True`
   - Clean structure with red atom number annotations
   - No correlation arrows (just numbered structure)

2. **HMBC Correlation Diagram** (optional, after HMBC table)
   - Full diagram with arrows and J-coupling labels
   - Shows how correlations connect atoms

**Updated PDF template section:**
```python
# In SKILL.md Step 13 - replace RDKit direct drawing with:

from lucy_ng.visualization import CorrelationDiagramGenerator, DiagramConfig
from lucy_ng.lsd.analyzer import LSDSolutionAnalyzer
import cairosvg  # For SVG→PNG conversion

def generate_structure_image(sol_path, lsd_path, solution_num, output_png):
    """Generate numbered structure for PDF report."""
    config = DiagramConfig(
        width=500,
        height=400,
        show_atom_numbers=True,
        show_chemical_shifts=False,
        show_legend=False,
        show_hydrogens=False,  # Cleaner for reports
    )
    gen = CorrelationDiagramGenerator(config)
    result = gen.generate_from_sol_file(sol_path, lsd_path, solution_num)

    # Convert SVG to PNG for ReportLab
    cairosvg.svg2png(bytestring=result.svg_content.encode(), write_to=output_png)
    return output_png

def generate_correlation_diagram(sol_path, lsd_path, solution_num, output_png):
    """Generate HMBC correlation diagram for PDF report."""
    config = DiagramConfig(
        width=600,
        height=450,
        show_atom_numbers=True,
        show_chemical_shifts=True,
        show_legend=True,
    )
    gen = CorrelationDiagramGenerator(config)
    result = gen.generate_from_sol_file(
        sol_path, lsd_path, solution_num,
        show_j_coupling=True,  # Add ²J/³J labels
    )
    cairosvg.svg2png(bytestring=result.svg_content.encode(), write_to=output_png)
    return output_png
```

### Task 7: MCP Tool Update

**Files to modify**: `mcp/server.py`

```python
@mcp.tool()
def generate_correlation_diagram(
    smiles: str | None = None,
    sol_content: str | None = None,      # NEW
    lsd_content: str | None = None,
    solution_number: int = 1,            # NEW
    correlations: list[dict] | None = None,
    carbon_shifts: dict | None = None,
    show_atom_numbers: bool = False,     # NEW
    show_j_coupling: bool = False,       # NEW
    width: int = 800,
    height: int = 600,
    # ... existing params ...
) -> dict:
    """Generate NMR correlation diagram with publication-quality features.

    New features:
    - show_atom_numbers: Add red atom number annotations
    - show_j_coupling: Add ²J/³J labels on HMBC arrows
    - sol_content: Generate from LSD solution file content
    """
```

---

## Data Flow After Integration

```
┌──────────────┐     ┌──────────────┐
│  .sol file   │     │  .lsd file   │
│ (solved)     │     │ (input)      │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │  LSDSolutionAnalyzer  │
    │  - Molecular graph    │
    │  - J-coupling (BFS)   │
    │  - SMILES generation  │
    └───────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │ CorrelationDiagram    │
    │ Generator             │
    │  - Clean structure    │
    │  - Red atom numbers   │
    │  - HMBC arrows        │
    │  - J-coupling labels  │
    │  - Shift annotations  │
    └───────────┬───────────┘
                ▼
         ┌─────────────┐
         │   SVG       │
         └──────┬──────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
┌─────────────┐   ┌─────────────┐
│  PDF Report │   │ Direct SVG  │
│ (ReportLab) │   │   Output    │
└─────────────┘   └─────────────┘
```

---

## Implementation Order

| Phase | Task | Effort | Files |
|-------|------|--------|-------|
| 1 | Task 1: Publication-style atom numbers | Medium | models.py, diagram_generator.py, svg_builder.py |
| 2 | Task 2: Generate from .sol files | Medium | diagram_generator.py |
| 3 | Task 3: J-coupling arrow labels | Small | svg_builder.py, diagram_generator.py |
| 4 | Task 5: CLI updates | Small | cli/visualize.py |
| 5 | Task 7: MCP updates | Small | mcp/server.py |
| 6 | Task 4: Deprecate old method | Small | lsd/analyzer.py |
| 7 | Task 6: PDF report integration | Medium | skill/CASE/SKILL.md |

---

## Testing Requirements

### Unit Tests
- `test_atom_number_annotations()` - verify red labels positioned correctly
- `test_generate_from_sol_file()` - parse .sol and generate diagram
- `test_j_coupling_labels()` - verify ²J/³J annotations on arrows
- `test_smart_label_positioning()` - labels avoid bond overlap

### Integration Tests
- End-to-end: .sol + .lsd → SVG with all annotations
- PDF generation with embedded diagrams
- CLI `--sol` option

### Visual Verification
- Compare output to publication screenshot style
- Verify atom numbers are readable and well-positioned

---

## Example Output

After integration, a correlation diagram from `lucy lsd analyze --draw` would show:

```
                    ²J
            ┌───────────────────┐
            │                   │
            ▼      11           │
        ┌───O─────────┐    1    │
        │             │    ↗    │
    10──┤             ├───CH────┘
        │    ³J       │    │
        │    ↓        │   2│
     9──┤    CH───────┤    │
        │    │        │    CH──3
        └────┴────────┘    │
             8        7   ³J
                      │    │
                      └────┘
```

**Visual features**:
- Clean molecular structure (standard chemical drawing)
- Red atom numbers (1, 2, 3, 7, 8, 9, 10, 11) as separate annotations
- Curved HMBC arrows with ²J/³J labels
- Gray chemical shift values (optional)
- Legend showing correlation types

---

## Dependencies

**Existing**:
- RDKit (molecule rendering)
- ReportLab (PDF generation)

**Optional** (for PNG export from SVG):
- cairosvg: `pip install cairosvg`

---

## Migration Notes

1. Existing `lucy lsd analyze --draw` will continue to work
2. Add deprecation warning pointing to new visualization module
3. Update SKILL.md with new image generation code
4. PDF reports automatically use improved diagrams

---

*Created: 2026-01-16*
*Updated: 2026-01-16 - Added full reporting workflow integration*
