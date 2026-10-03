"""SVG construction utilities for correlation diagrams."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ArrowStyle, CorrelationType, RoutedArrow


class SVGBuilder:
    """Build SVG documents with molecular structures and correlation arrows.

    Constructs SVG incrementally by adding elements, then generates
    the complete document with build().

    Example:
        >>> builder = SVGBuilder(800, 600)
        >>> builder.add_arrow_marker("hmbc-arrow", "#E41A1C")
        >>> builder.add_bezier_arrow(arrow, "hmbc-arrow")
        >>> svg_content = builder.build()
    """

    def __init__(self, width: int, height: int) -> None:
        """Initialize SVG builder with canvas dimensions.

        Args:
            width: Canvas width in pixels
            height: Canvas height in pixels
        """
        self.width = width
        self.height = height
        self._defs: list[str] = []
        self._elements: list[str] = []

    def add_arrow_marker(
        self,
        marker_id: str,
        color: str,
        size: float = 10.0,
    ) -> None:
        """Add arrowhead marker definition.

        Creates a triangular arrowhead marker that can be referenced
        by path elements using marker-end="url(#marker_id)".

        Args:
            marker_id: Unique identifier for the marker
            color: Fill color (hex or named)
            size: Size of the arrowhead (default increased to 10.0 for visibility)
        """
        # Triangle pointing right, refX at tip for proper positioning
        self._defs.append(
            f'<marker id="{marker_id}" markerWidth="{size}" markerHeight="{size}" '
            f'refX="{size - 1}" refY="{size / 2}" orient="auto" markerUnits="strokeWidth">'
            f'<path d="M 0 0 L {size} {size / 2} L 0 {size} z" fill="{color}" />'
            f"</marker>"
        )

    def add_start_marker(
        self,
        marker_id: str,
        color: str,
        size: float = 5.0,
    ) -> None:
        """Add circle marker for arrow start point.

        Creates a filled circle marker to clearly indicate where an arrow begins.

        Args:
            marker_id: Unique identifier for the marker
            color: Fill color (hex or named)
            size: Diameter of the circle
        """
        radius = size / 2
        self._defs.append(
            f'<marker id="{marker_id}" markerWidth="{size}" markerHeight="{size}" '
            f'refX="{radius}" refY="{radius}" markerUnits="strokeWidth">'
            f'<circle cx="{radius}" cy="{radius}" r="{radius}" fill="{color}" />'
            f"</marker>"
        )

    def add_bezier_arrow(
        self,
        arrow: RoutedArrow,
        marker_id: str,
        start_marker_id: str | None = None,
    ) -> None:
        """Add curved arrow with quadratic or cubic Bezier path.

        Args:
            arrow: RoutedArrow with start, end, and control points
            marker_id: Reference to marker definition for arrowhead
            start_marker_id: Optional marker for arrow start point (circle)
        """
        style = arrow.style

        # Build path based on number of control points
        if len(arrow.control_points) == 1:
            # Quadratic Bezier (Q command)
            cx, cy = arrow.control_points[0]
            path_d = (
                f"M {arrow.start_x:.2f} {arrow.start_y:.2f} "
                f"Q {cx:.2f} {cy:.2f} {arrow.end_x:.2f} {arrow.end_y:.2f}"
            )
        elif len(arrow.control_points) >= 2:
            # Cubic Bezier (C command)
            c1x, c1y = arrow.control_points[0]
            c2x, c2y = arrow.control_points[1]
            path_d = (
                f"M {arrow.start_x:.2f} {arrow.start_y:.2f} "
                f"C {c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} "
                f"{arrow.end_x:.2f} {arrow.end_y:.2f}"
            )
        else:
            # Straight line fallback
            path_d = (
                f"M {arrow.start_x:.2f} {arrow.start_y:.2f} "
                f"L {arrow.end_x:.2f} {arrow.end_y:.2f}"
            )

        # Build stroke attributes
        stroke_attrs = f'stroke="{style.color}" stroke-width="{style.stroke_width}"'
        if style.dash_pattern:
            stroke_attrs += f' stroke-dasharray="{style.dash_pattern}"'

        # Build marker attributes
        marker_attrs = f'marker-end="url(#{marker_id})"'
        if start_marker_id:
            marker_attrs += f' marker-start="url(#{start_marker_id})"'

        self._elements.append(
            f'<path d="{path_d}" fill="none" {stroke_attrs} {marker_attrs} />'
        )

    def add_text_label(
        self,
        x: float,
        y: float,
        text: str,
        font_size: float = 10.0,
        color: str = "#000000",
        anchor: str = "middle",
        font_family: str = "Arial, sans-serif",
    ) -> None:
        """Add text label for chemical shifts or atom indices.

        Args:
            x: X position
            y: Y position
            text: Label text
            font_size: Font size in pixels
            color: Text color
            anchor: Text anchor (start, middle, end)
            font_family: Font family
        """
        self._elements.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{font_size}" '
            f'fill="{color}" text-anchor="{anchor}" font-family="{font_family}">'
            f"{text}</text>"
        )

    def add_raw_svg(self, svg_content: str) -> None:
        """Add raw SVG content (e.g., molecule rendering from RDKit).

        The content is added as-is to the elements list.
        Use this to embed RDKit-generated molecule SVG.

        Args:
            svg_content: Raw SVG element(s) to include
        """
        self._elements.append(svg_content)

    def add_group(
        self,
        content: str,
        transform: str | None = None,
        group_id: str | None = None,
    ) -> None:
        """Add a group element with optional transform.

        Args:
            content: SVG content to wrap in group
            transform: Optional transform attribute (e.g., "translate(100, 50)")
            group_id: Optional id attribute for the group
        """
        attrs = ""
        if group_id:
            attrs += f' id="{group_id}"'
        if transform:
            attrs += f' transform="{transform}"'

        self._elements.append(f"<g{attrs}>{content}</g>")

    def add_j_coupling_label(
        self,
        x: float,
        y: float,
        j_value: int,
        font_size: float = 11.0,
        color: str = "#444444",
        font_weight: str = "bold",
    ) -> None:
        """Add J-coupling notation near an arrow.

        Args:
            x: X position for label
            y: Y position for label
            j_value: J-coupling value (2 for ²J, 3 for ³J, etc.)
            font_size: Font size in pixels (default increased to 11.0)
            color: Text color (darker for better visibility)
            font_weight: Font weight (bold for better visibility)
        """
        superscripts = {2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶"}
        label = f"{superscripts.get(j_value, str(j_value))}J"
        self._elements.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{font_size}" '
            f'fill="{color}" text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-weight="{font_weight}">{label}</text>'
        )

    def add_atom_number(
        self,
        x: float,
        y: float,
        number: str,
        font_size: float = 12.0,
        color: str = "#CC0000",
    ) -> None:
        """Add publication-style atom number annotation.

        Places a red number near the atom position, as commonly
        seen in NMR structure figures.

        Args:
            x: X position for label
            y: Y position for label
            number: Atom number as string (e.g., "1", "2", "C7")
            font_size: Font size in pixels (default increased to 12.0)
            color: Text color (default red like publications)
        """
        self._elements.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{font_size}" '
            f'fill="{color}" text-anchor="start" font-family="Arial, sans-serif" '
            f'font-weight="bold">{number}</text>'
        )

    def add_legend(
        self,
        x: float,
        y: float,
        items: list[tuple[str, ArrowStyle]],
        font_size: float = 12.0,
        arrow_length: float = 35.0,
        arrow_head_size: float = 8.0,
        start_marker_size: float = 4.0,
    ) -> None:
        """Add legend showing correlation types.

        Args:
            x: X position for legend
            y: Y position for legend
            items: List of (label, style) tuples
            font_size: Font size for labels (default increased to 12.0)
            arrow_length: Length of sample arrow (default increased to 35.0)
            arrow_head_size: Size of arrow head in legend (default 8.0)
            start_marker_size: Size of start circle marker (default 4.0)
        """
        line_height = font_size + 12  # Increased spacing
        legend_width = 100

        for i, (label, style) in enumerate(items):
            item_y = y + i * line_height

            # Sample arrow line
            line_x1 = x
            line_x2 = x + arrow_length
            line_y = item_y - font_size / 3

            stroke_attrs = f'stroke="{style.color}" stroke-width="{style.stroke_width}"'
            if style.dash_pattern:
                stroke_attrs += f' stroke-dasharray="{style.dash_pattern}"'

            # Draw sample line
            self._elements.append(
                f'<line x1="{line_x1}" y1="{line_y}" x2="{line_x2}" y2="{line_y}" '
                f'{stroke_attrs} />'
            )

            # Add start point circle
            self._elements.append(
                f'<circle cx="{line_x1}" cy="{line_y}" r="{start_marker_size / 2}" '
                f'fill="{style.color}" />'
            )

            # Add end point circle (slightly smaller than start)
            self._elements.append(
                f'<circle cx="{line_x2}" cy="{line_y}" r="{start_marker_size / 2 * 0.8}" '
                f'fill="{style.color}" />'
            )

            # Label text (larger font)
            self._elements.append(
                f'<text x="{line_x2 + 10}" y="{item_y}" font-size="{font_size}" '
                f'fill="#000000" font-family="Arial, sans-serif" font-weight="bold">{label}</text>'
            )

    def build(self) -> str:
        """Generate complete SVG document.

        Returns:
            Complete SVG document as string
        """
        defs_content = "\n    ".join(self._defs) if self._defs else ""
        elements_content = "\n  ".join(self._elements)

        defs_section = ""
        if defs_content:
            defs_section = f"\n  <defs>\n    {defs_content}\n  </defs>"

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{self.width}" height="{self.height}"
     viewBox="0 0 {self.width} {self.height}">{defs_section}
  {elements_content}
</svg>"""
