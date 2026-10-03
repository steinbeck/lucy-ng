"""Data models for NMR correlation diagram visualization."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Layout Optimization Models
# =============================================================================


@dataclass
class BoundingBox:
    """Axis-aligned bounding box for collision detection."""

    x: float
    y: float
    width: float
    height: float

    @property
    def x_min(self) -> float:
        return self.x

    @property
    def y_min(self) -> float:
        return self.y

    @property
    def x_max(self) -> float:
        return self.x + self.width

    @property
    def y_max(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def intersects(self, other: BoundingBox) -> bool:
        """Check if this bounding box overlaps with another."""
        return not (
            self.x_max < other.x_min
            or other.x_max < self.x_min
            or self.y_max < other.y_min
            or other.y_max < self.y_min
        )

    def intersection_area(self, other: BoundingBox) -> float:
        """Compute area of intersection with another bounding box."""
        x_overlap = max(0, min(self.x_max, other.x_max) - max(self.x_min, other.x_min))
        y_overlap = max(0, min(self.y_max, other.y_max) - max(self.y_min, other.y_min))
        return x_overlap * y_overlap

    def expanded(self, margin: float) -> BoundingBox:
        """Return a new bounding box expanded by margin on all sides."""
        return BoundingBox(
            x=self.x - margin,
            y=self.y - margin,
            width=self.width + 2 * margin,
            height=self.height + 2 * margin,
        )

    @staticmethod
    def from_points(points: list[tuple[float, float]], padding: float = 2.0) -> BoundingBox:
        """Create bounding box from a list of points with optional padding."""
        if not points:
            return BoundingBox(0, 0, 0, 0)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return BoundingBox(
            x=min(xs) - padding,
            y=min(ys) - padding,
            width=max(xs) - min(xs) + 2 * padding,
            height=max(ys) - min(ys) + 2 * padding,
        )

    @staticmethod
    def from_line_segment(
        p1: tuple[float, float], p2: tuple[float, float], stroke_width: float = 2.0
    ) -> BoundingBox:
        """Create bounding box from a line segment with stroke width."""
        padding = stroke_width / 2
        return BoundingBox(
            x=min(p1[0], p2[0]) - padding,
            y=min(p1[1], p2[1]) - padding,
            width=abs(p2[0] - p1[0]) + 2 * padding,
            height=abs(p2[1] - p1[1]) + 2 * padding,
        )

    @staticmethod
    def from_text(
        x: float,
        y: float,
        text: str,
        font_size: float,
        anchor: str = "start",
    ) -> BoundingBox:
        """Estimate bounding box for text label.

        Conservative estimate: width = 0.7 * font_size * len(text)
        """
        char_width = 0.7 * font_size
        text_width = char_width * len(text)
        text_height = font_size

        # Adjust x based on text anchor
        if anchor == "middle":
            x = x - text_width / 2
        elif anchor == "end":
            x = x - text_width

        # Text baseline is at y, so bbox starts above
        return BoundingBox(
            x=x,
            y=y - text_height * 0.8,
            width=text_width,
            height=text_height,
        )


class ElementType(str, Enum):
    """Types of layout elements."""

    BOND = "bond"
    ATOM_LABEL = "atom_label"
    ATOM_NUMBER = "atom_number"
    ARROW = "arrow"


@dataclass
class LayoutElement:
    """Base class for layout elements with bounding boxes."""

    element_type: ElementType
    bbox: BoundingBox
    is_movable: bool = False


@dataclass
class AtomNumberElement(LayoutElement):
    """Movable atom number label positioned relative to an atom."""

    atom_idx: int = 0
    label_text: str = ""
    anchor_x: float = 0.0  # Atom center X
    anchor_y: float = 0.0  # Atom center Y
    font_size: float = 10.5  # ~85% of main font for aesthetic proportion
    offset_angle: float = 0.0  # Radians, 0 = right, pi/2 = down
    offset_distance: float = 16.0  # Pixels from atom center

    def __post_init__(self) -> None:
        self.element_type = ElementType.ATOM_NUMBER
        self.is_movable = True
        self._update_bbox()

    def _update_bbox(self) -> None:
        """Update bounding box based on current position."""
        x, y = self.get_label_position()
        self.bbox = BoundingBox.from_text(
            x, y, self.label_text, self.font_size, anchor="start"
        )

    def get_label_position(self) -> tuple[float, float]:
        """Get current label position based on angle and distance."""
        x = self.anchor_x + math.cos(self.offset_angle) * self.offset_distance
        y = self.anchor_y + math.sin(self.offset_angle) * self.offset_distance
        # Adjust for text baseline
        y += self.font_size / 3
        return (x, y)

    def update_position(self, angle: float, distance: float) -> None:
        """Update offset angle and distance, then recompute bbox."""
        self.offset_angle = angle
        self.offset_distance = distance
        self._update_bbox()


@dataclass
class ArrowElement(LayoutElement):
    """Movable arrow with adjustable curvature and direction."""

    source_atom: int = 0
    target_atom: int = 0
    start_pos: tuple[float, float] = (0.0, 0.0)
    end_pos: tuple[float, float] = (0.0, 0.0)
    curvature: float = 1.8  # Magnitude of curve - high for sweeping publication-style arcs
    direction: float = 1.0  # Sign: +1 or -1 (which way belly points)
    stroke_width: float = 2.0
    sampled_points: list[tuple[float, float]] = field(default_factory=list)
    control_point: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        self.element_type = ElementType.ARROW
        self.is_movable = True
        self._recompute_control_point_and_samples()

    def _recompute_control_point_and_samples(self) -> None:
        """Recompute Bezier control point based on curvature and direction."""
        # Midpoint
        mid_x = (self.start_pos[0] + self.end_pos[0]) / 2
        mid_y = (self.start_pos[1] + self.end_pos[1]) / 2

        # Arrow direction vector
        dx = self.end_pos[0] - self.start_pos[0]
        dy = self.end_pos[1] - self.start_pos[1]
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1e-6:
            self.control_point = (mid_x, mid_y)
            self.sampled_points = [self.start_pos, self.end_pos]
            self.bbox = BoundingBox.from_points(self.sampled_points, self.stroke_width)
            return

        # Perpendicular vector (normalized)
        perp_x = -dy / length
        perp_y = dx / length

        # Control point offset (curvature * length * direction)
        actual_direction = 1.0 if self.direction >= 0 else -1.0
        offset = self.curvature * length * actual_direction
        ctrl_x = mid_x + perp_x * offset
        ctrl_y = mid_y + perp_y * offset
        self.control_point = (ctrl_x, ctrl_y)

        # Sample points along curve
        self.sampled_points = self._sample_quadratic_bezier(15)

        # Update bounding box from sampled points
        self.bbox = BoundingBox.from_points(self.sampled_points, self.stroke_width)

    def _sample_quadratic_bezier(self, num_samples: int = 15) -> list[tuple[float, float]]:
        """Sample points along a quadratic Bezier curve.

        B(t) = (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
        """
        points = []
        start = self.start_pos
        control = self.control_point
        end = self.end_pos

        for i in range(num_samples + 1):
            t = i / num_samples
            mt = 1 - t

            x = mt * mt * start[0] + 2 * mt * t * control[0] + t * t * end[0]
            y = mt * mt * start[1] + 2 * mt * t * control[1] + t * t * end[1]
            points.append((x, y))

        return points

    def update_curve(self, curvature: float, direction: float) -> None:
        """Update curve parameters and recompute sampled points."""
        self.curvature = curvature
        self.direction = direction
        self._recompute_control_point_and_samples()


@dataclass
class LayoutProblem:
    """Complete layout optimization problem."""

    fixed_elements: list[LayoutElement]
    atom_numbers: list[AtomNumberElement]
    arrows: list[ArrowElement]
    canvas_width: int
    canvas_height: int
    max_label_distance: float = 25.0
    min_label_distance: float = 10.0
    min_curvature: float = 1.2
    max_curvature: float = 2.5


@dataclass
class LayoutSolution:
    """Result of layout optimization."""

    atom_numbers: list[AtomNumberElement]
    arrows: list[ArrowElement]
    total_cost: float
    overlap_area: float
    overlap_count: int
    warnings: list[str]
    optimization_time_ms: float


# =============================================================================
# Correlation Diagram Models
# =============================================================================


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
    curvature: float = 1.8  # Bezier control point offset factor - high for sweeping publication-style arcs


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
    # Typography convention: subscripts are ~60-70% of main text, but atom
    # numbers need readability as standalone labels. Using ~85% (10.5/12.0)
    # provides good balance between aesthetics and legibility.
    show_atom_numbers: bool = False
    atom_number_color: str = "#CC0000"  # Red like publications
    atom_number_font_size: float = 10.5  # ~85% of main font (12.0) for aesthetic proportion
    atom_number_offset: float = 16.0  # Offset distance, placed in largest gap between bonds

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
