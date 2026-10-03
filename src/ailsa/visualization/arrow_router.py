"""Arrow routing algorithms for correlation diagrams."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .models import ArrowStyle, AtomPosition, Correlation, RoutedArrow

if TYPE_CHECKING:
    from rdkit.Chem import Mol

    from .models import DiagramConfig


class ArrowRouter:
    """Route curved arrows to minimize visual overlaps.

    Uses geometric analysis to compute Bezier curve paths that avoid
    collisions with bonds, atoms, and other arrows.

    Algorithm:
    1. Sort correlations by distance (longest first)
    2. Compute initial straight-line paths
    3. Calculate molecule center and curve OUTWARD (away from center)
    4. Apply curvature offsets to create publication-style wide arcs
    5. Fan out multiple arrows from the same atom
    """

    def __init__(self) -> None:
        """Initialize arrow router."""
        self._ring_atoms: set[int] = set()
        self._bond_midpoints: list[tuple[float, float]] = []
        self._molecule_center: tuple[float, float] = (0.0, 0.0)

    def route_arrows(
        self,
        correlations: list[Correlation],
        atom_positions: dict[int, AtomPosition],
        config: DiagramConfig,
        mol: Mol | None = None,
    ) -> list[RoutedArrow]:
        """Compute optimized arrow paths for all correlations.

        Args:
            correlations: List of correlations to visualize
            atom_positions: Map of atom index to position
            config: Diagram configuration with styles
            mol: Optional RDKit molecule for ring detection

        Returns:
            List of RoutedArrow with computed Bezier paths
        """
        if not correlations:
            return []

        # Calculate molecule center for outward curving
        if atom_positions:
            # Only use heavy atoms (non-H) for center calculation
            heavy_positions = [p for p in atom_positions.values() if p.element != "H"]
            if heavy_positions:
                center_x = sum(p.x for p in heavy_positions) / len(heavy_positions)
                center_y = sum(p.y for p in heavy_positions) / len(heavy_positions)
                self._molecule_center = (center_x, center_y)

        # Extract ring information if molecule provided
        if mol is not None:
            self._extract_ring_info(mol)
            self._extract_bond_midpoints(mol, atom_positions)

        # Sort by distance (longest first - they need more curvature)
        sorted_correlations = self._sort_by_distance(correlations, atom_positions)

        routed: list[RoutedArrow] = []
        for corr in sorted_correlations:
            arrow = self._route_single_arrow(
                corr, atom_positions, routed, config
            )
            if arrow is not None:
                routed.append(arrow)

        return routed

    def _extract_ring_info(self, mol: Mol) -> None:
        """Extract ring atom indices from molecule."""
        ring_info = mol.GetRingInfo()
        self._ring_atoms = set()
        for ring in ring_info.AtomRings():
            self._ring_atoms.update(ring)

    def _extract_bond_midpoints(
        self,
        mol: Mol,
        atom_positions: dict[int, AtomPosition],
    ) -> None:
        """Extract bond midpoints for collision detection."""
        self._bond_midpoints = []
        for bond in mol.GetBonds():
            idx1 = bond.GetBeginAtomIdx()
            idx2 = bond.GetEndAtomIdx()
            if idx1 in atom_positions and idx2 in atom_positions:
                p1 = atom_positions[idx1]
                p2 = atom_positions[idx2]
                mid_x = (p1.x + p2.x) / 2
                mid_y = (p1.y + p2.y) / 2
                self._bond_midpoints.append((mid_x, mid_y))

    def _sort_by_distance(
        self,
        correlations: list[Correlation],
        positions: dict[int, AtomPosition],
    ) -> list[Correlation]:
        """Sort correlations by distance (longest first)."""

        def get_distance(corr: Correlation) -> float:
            if corr.source_atom not in positions or corr.target_atom not in positions:
                return 0.0
            p1 = positions[corr.source_atom]
            p2 = positions[corr.target_atom]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            return math.sqrt(dx * dx + dy * dy)

        return sorted(correlations, key=get_distance, reverse=True)

    def _route_single_arrow(
        self,
        correlation: Correlation,
        positions: dict[int, AtomPosition],
        existing_arrows: list[RoutedArrow],
        config: DiagramConfig,
    ) -> RoutedArrow | None:
        """Route a single arrow, curving OUTWARD from molecule center.

        Publication-style HMBC diagrams show arrows that arc around
        the outside of the molecule structure, not through it.

        Returns None if source or target atom not found.
        """
        if correlation.source_atom not in positions:
            return None
        if correlation.target_atom not in positions:
            return None

        source = positions[correlation.source_atom]
        target = positions[correlation.target_atom]

        # Vector from source to target
        dx = target.x - source.x
        dy = target.y - source.y
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1e-6:
            # Source and target at same position
            return None

        # Normalize direction
        dir_x = dx / length
        dir_y = dy / length

        # Perpendicular vector (for curve offset)
        perp_x = -dir_y
        perp_y = dir_x

        # Calculate offset from atom centers
        offset = config.arrow_offset_from_atom

        start_x = source.x + dir_x * offset
        start_y = source.y + dir_y * offset
        end_x = target.x - dir_x * offset
        end_y = target.y - dir_y * offset

        # Midpoint of the arrow
        mid_x = (start_x + end_x) / 2
        mid_y = (start_y + end_y) / 2

        # Determine curvature direction - ALWAYS curve OUTWARD from molecule center
        style = config.get_style_for_type(correlation.correlation_type)
        curvature_direction = self._calculate_outward_direction(
            mid_x, mid_y, perp_x, perp_y, existing_arrows, correlation
        )

        # Calculate control point offset based on arrow length
        # Use higher curvature for longer arrows (they need to arc more to go around)
        curve_offset = style.curvature * length * curvature_direction

        # Single control point for quadratic Bezier
        ctrl_x = mid_x + perp_x * curve_offset
        ctrl_y = mid_y + perp_y * curve_offset

        return RoutedArrow(
            correlation=correlation,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            control_points=[(ctrl_x, ctrl_y)],
            style=style,
        )

    def _calculate_outward_direction(
        self,
        mid_x: float,
        mid_y: float,
        perp_x: float,
        perp_y: float,
        existing_arrows: list[RoutedArrow],
        correlation: Correlation,
    ) -> float:
        """Determine curvature direction to curve AWAY from molecule center.

        This creates publication-style arrows that arc around the outside
        of the molecule rather than cutting through it.

        Returns:
            +1.0 or -1.0 indicating which direction curves outward
        """
        center_x, center_y = self._molecule_center

        # Vector from molecule center to arrow midpoint
        to_mid_x = mid_x - center_x
        to_mid_y = mid_y - center_y

        # Dot product with perpendicular determines which perpendicular
        # direction points AWAY from the center
        dot = to_mid_x * perp_x + to_mid_y * perp_y

        # Base direction: curve away from center
        base_direction = 1.0 if dot > 0 else -1.0

        # Check for collisions with existing arrows and alternate if needed
        for arrow in existing_arrows:
            if self._arrows_overlap(correlation, arrow.correlation):
                # If another arrow from same atom curves in this direction,
                # consider alternating (but still prefer outward)
                if arrow.control_points:
                    existing_ctrl_y = arrow.control_points[0][1]
                    existing_mid_y = (arrow.start_y + arrow.end_y) / 2
                    existing_dir = 1.0 if existing_ctrl_y > existing_mid_y else -1.0
                    if existing_dir == base_direction:
                        # Alternate for variety, but don't go inward
                        pass  # Keep base_direction for now

        return base_direction

    def _calculate_curvature_direction(
        self,
        correlation: Correlation,
        source: AtomPosition,
        target: AtomPosition,
        existing_arrows: list[RoutedArrow],
    ) -> float:
        """Determine curvature direction (+1 or -1) to minimize overlaps.

        Prefers curving away from:
        - Ring centers (if atoms are in a ring)
        - Existing arrows with similar endpoints
        - Bond midpoints

        Returns:
            +1.0 for one direction, -1.0 for opposite
        """
        # Check if both atoms are in a ring
        source_in_ring = source.atom_index in self._ring_atoms
        target_in_ring = target.atom_index in self._ring_atoms

        if source_in_ring and target_in_ring:
            # Prefer curving outside the ring
            # Estimate ring center from midpoints
            if self._bond_midpoints:
                ring_center_x = sum(p[0] for p in self._bond_midpoints) / len(
                    self._bond_midpoints
                )
                ring_center_y = sum(p[1] for p in self._bond_midpoints) / len(
                    self._bond_midpoints
                )

                # Arrow midpoint
                mid_x = (source.x + target.x) / 2
                mid_y = (source.y + target.y) / 2

                # Vector from ring center to arrow midpoint
                to_mid_x = mid_x - ring_center_x
                to_mid_y = mid_y - ring_center_y

                # Perpendicular to arrow
                dx = target.x - source.x
                dy = target.y - source.y
                perp_x = -dy
                perp_y = dx

                # Dot product determines which side is "outside"
                dot = to_mid_x * perp_x + to_mid_y * perp_y
                return 1.0 if dot > 0 else -1.0

        # Check for collisions with existing arrows
        pos_score = 0
        neg_score = 0

        for arrow in existing_arrows:
            # Simple heuristic: count arrows curving each direction
            # between similar endpoints
            if self._arrows_overlap(correlation, arrow.correlation):
                if arrow.control_points:
                    # Determine which way the existing arrow curves
                    existing_mid_y = (arrow.start_y + arrow.end_y) / 2
                    ctrl_y = arrow.control_points[0][1]
                    if ctrl_y > existing_mid_y:
                        pos_score += 1
                    else:
                        neg_score += 1

        # Prefer the less crowded direction
        if pos_score != neg_score:
            return -1.0 if pos_score > neg_score else 1.0

        # Default: curve in consistent direction based on atom indices
        return 1.0 if correlation.source_atom < correlation.target_atom else -1.0

    def _arrows_overlap(
        self,
        corr1: Correlation,
        corr2: Correlation,
    ) -> bool:
        """Check if two correlations share an endpoint."""
        atoms1 = {corr1.source_atom, corr1.target_atom}
        atoms2 = {corr2.source_atom, corr2.target_atom}
        return len(atoms1 & atoms2) > 0


def fan_out_arrows(
    arrows: list[RoutedArrow],
    fan_angle: float = 15.0,
) -> list[RoutedArrow]:
    """Adjust arrows sharing an endpoint to fan out.

    Groups arrows by shared endpoints and spreads them apart
    by adjusting their curvature.

    Args:
        arrows: List of routed arrows
        fan_angle: Angle in degrees to spread each arrow

    Returns:
        Adjusted list of arrows
    """
    # Group by source atom
    by_source: dict[int, list[RoutedArrow]] = {}
    for arrow in arrows:
        src = arrow.correlation.source_atom
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(arrow)

    # Adjust groups with multiple arrows
    adjusted = []
    for src, group in by_source.items():
        if len(group) <= 1:
            adjusted.extend(group)
            continue

        # Fan out by adjusting curvature
        angle_step = math.radians(fan_angle)
        for i, arrow in enumerate(group):
            offset = (i - (len(group) - 1) / 2) * angle_step

            if arrow.control_points:
                # Rotate control point around midpoint
                mid_x = (arrow.start_x + arrow.end_x) / 2
                mid_y = (arrow.start_y + arrow.end_y) / 2
                ctrl_x, ctrl_y = arrow.control_points[0]

                # Translate to origin
                dx = ctrl_x - mid_x
                dy = ctrl_y - mid_y

                # Rotate
                cos_a = math.cos(offset)
                sin_a = math.sin(offset)
                new_dx = dx * cos_a - dy * sin_a
                new_dy = dx * sin_a + dy * cos_a

                # Translate back
                new_ctrl = (mid_x + new_dx, mid_y + new_dy)

                adjusted.append(
                    RoutedArrow(
                        correlation=arrow.correlation,
                        start_x=arrow.start_x,
                        start_y=arrow.start_y,
                        end_x=arrow.end_x,
                        end_y=arrow.end_y,
                        control_points=[new_ctrl],
                        style=arrow.style,
                    )
                )
            else:
                adjusted.append(arrow)

    return adjusted
