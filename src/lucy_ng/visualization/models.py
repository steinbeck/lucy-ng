"""Data models for NMR correlation diagram visualization."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CorrelationType(str, Enum):
    """Types of NMR correlations that can be visualized."""

    HMBC = "HMBC"  # C to H long-range (2-3 bonds)
    HSQC = "HSQC"  # C to H direct (1 bond)
    COSY = "COSY"  # H to H vicinal
    NOESY = "NOESY"  # H to H through space
    ROESY = "ROESY"  # H to H through space (rotating frame)


class ArrowStyle(BaseModel):
    """Visual style for correlation arrows."""

    color: str = "#E41A1C"  # Default red for HMBC
    stroke_width: float = 2.0  # Increased from 1.5 for better visibility
    dash_pattern: str | None = None  # None = solid, "5,3" = dashed
    head_size: float = 10.0  # Increased from 6.0 for clearer arrow heads
    start_marker_size: float = 5.0  # Size of circle at arrow start point
    curvature: float = 0.8  # Bezier control point offset factor (0.8 for publication-style wide arcs)


class AtomPosition(BaseModel):
    """2D position of an atom in the diagram."""

    atom_index: int
    x: float
    y: float
    element: str
    hydrogen_count: int = 0
    carbon_shift: float | None = None
    proton_shift: float | None = None


class Correlation(BaseModel):
    """A single NMR correlation to visualize."""

    source_atom: int  # Atom index (0-based for RDKit, convert from 1-based LSD)
    target_atom: int  # Atom index for target
    correlation_type: CorrelationType = CorrelationType.HMBC


class RoutedArrow(BaseModel):
    """Arrow with computed path for rendering."""

    correlation: Correlation
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    control_points: list[tuple[float, float]]  # Bezier control points
    style: ArrowStyle = Field(default_factory=ArrowStyle)


class DiagramConfig(BaseModel):
    """Configuration for diagram generation."""

    width: int = 800
    height: int = 600
    padding: int = 50
    show_chemical_shifts: bool = True
    show_atom_indices: bool = False
    show_hydrogens: bool = False  # Publication style: no explicit H atoms (cleaner)
    show_all_atom_labels: bool = False  # Show element symbols for all atoms (C, H, etc.)
    show_legend: bool = True
    hmbc_style: ArrowStyle = Field(
        default_factory=lambda: ArrowStyle(color="#E41A1C")  # Red
    )
    hsqc_style: ArrowStyle = Field(
        default_factory=lambda: ArrowStyle(color="#4DAF4A", dash_pattern="3,2")  # Green
    )
    cosy_style: ArrowStyle = Field(
        default_factory=lambda: ArrowStyle(color="#377EB8")  # Blue
    )
    noesy_style: ArrowStyle = Field(
        default_factory=lambda: ArrowStyle(color="#984EA3", dash_pattern="5,3")  # Purple
    )
    font_family: str = "Arial, sans-serif"
    font_size: float = 12.0  # Increased from 10.0 for better readability
    shift_label_offset: float = 14.0  # Increased from 12.0
    arrow_offset_from_atom: float = 15.0  # Offset from atom center for clearer separation

    # Publication-style atom numbering (red annotations near atoms)
    show_atom_numbers: bool = False
    atom_number_color: str = "#CC0000"  # Red like publications
    atom_number_font_size: float = 9.0  # Smaller to fit as subscript-style
    atom_number_offset: float = 12.0  # Base offset, used for subscript positioning

    # Legend settings
    legend_font_size: float = 12.0  # Font size for legend labels
    legend_arrow_length: float = 35.0  # Length of sample arrow in legend
    legend_arrow_head_size: float = 8.0  # Arrow head size in legend

    # J-coupling label settings
    j_coupling_font_size: float = 11.0  # Font size for ²J/³J labels

    def get_style_for_type(self, correlation_type: CorrelationType) -> ArrowStyle:
        """Get arrow style for a correlation type."""
        styles = {
            CorrelationType.HMBC: self.hmbc_style,
            CorrelationType.HSQC: self.hsqc_style,
            CorrelationType.COSY: self.cosy_style,
            CorrelationType.NOESY: self.noesy_style,
            CorrelationType.ROESY: self.noesy_style,  # Same as NOESY
        }
        return styles.get(correlation_type, self.hmbc_style)


class DiagramResult(BaseModel):
    """Result of diagram generation."""

    svg_content: str
    width: int
    height: int
    atom_count: int
    correlation_count: int
    arrows_routed: int
