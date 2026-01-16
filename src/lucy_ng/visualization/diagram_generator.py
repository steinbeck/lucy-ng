"""Main diagram generator for NMR correlation visualization."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rdkit import Chem
from rdkit.Chem import AllChem, Draw
from rdkit.Chem.Draw import rdMolDraw2D

from .arrow_router import ArrowRouter, fan_out_arrows
from .models import (
    AtomPosition,
    Correlation,
    CorrelationType,
    DiagramConfig,
    DiagramResult,
    RoutedArrow,
)
from .svg_builder import SVGBuilder

if TYPE_CHECKING:
    from lucy_ng.lsd.models import LSDProblem


class CorrelationDiagramGenerator:
    """Generate publication-quality NMR correlation diagrams.

    Creates SVG images showing molecular structure with chemical shift
    annotations and curved arrows for NMR correlations (HMBC, COSY, etc.).

    Example:
        >>> from lucy_ng.visualization import CorrelationDiagramGenerator
        >>> gen = CorrelationDiagramGenerator()
        >>> result = gen.generate(
        ...     smiles="CC(C)Cc1ccc(cc1)C(C)C(=O)O",
        ...     correlations=[
        ...         Correlation(source_atom=0, target_atom=3, correlation_type=CorrelationType.HMBC),
        ...     ],
        ...     carbon_shifts={0: 180.5, 1: 45.1},
        ... )
        >>> Path("diagram.svg").write_text(result.svg_content)
    """

    def __init__(self, config: DiagramConfig | None = None) -> None:
        """Initialize generator with optional configuration.

        Args:
            config: Diagram configuration (uses defaults if not provided)
        """
        self.config = config or DiagramConfig()
        self._router = ArrowRouter()

    def generate(
        self,
        smiles: str,
        correlations: list[Correlation],
        carbon_shifts: dict[int, float] | None = None,
        proton_shifts: dict[int, float] | None = None,
        atom_numbers: dict[int, str] | None = None,
        j_couplings: dict[tuple[int, int], int] | None = None,
    ) -> DiagramResult:
        """Generate correlation diagram from SMILES and correlation data.

        Args:
            smiles: Molecular structure in SMILES format
            correlations: List of NMR correlations to visualize
            carbon_shifts: Optional dict of atom_index -> 13C shift (ppm)
            proton_shifts: Optional dict of atom_index -> 1H shift (ppm)
            atom_numbers: Optional dict of atom_index -> label string for
                publication-style numbering (e.g., {0: "1", 1: "2"})
            j_couplings: Optional dict of (source, target) -> J value for
                labeling arrows with ²J/³J annotations

        Returns:
            DiagramResult with SVG content and metadata

        Raises:
            ValueError: If SMILES is invalid
        """
        # 1. Parse molecule and compute 2D layout
        mol = self._prepare_molecule(smiles)

        # 2. Extract atom positions
        atom_positions = self._extract_atom_positions(mol)

        # 3. Add chemical shift data
        if carbon_shifts:
            self._annotate_shifts(atom_positions, carbon_shifts, "carbon")
        if proton_shifts:
            self._annotate_shifts(atom_positions, proton_shifts, "proton")

        # 4. Route arrows to minimize overlaps
        routed_arrows = self._router.route_arrows(
            correlations, atom_positions, self.config, mol
        )

        # 5. Fan out arrows sharing endpoints
        routed_arrows = fan_out_arrows(routed_arrows)

        # 6. Build SVG
        svg_content = self._build_svg(
            mol, atom_positions, routed_arrows, atom_numbers, j_couplings
        )

        return DiagramResult(
            svg_content=svg_content,
            width=self.config.width,
            height=self.config.height,
            atom_count=mol.GetNumAtoms(),
            correlation_count=len(correlations),
            arrows_routed=len(routed_arrows),
        )

    def _generate_from_mol(
        self,
        mol: Chem.Mol,
        correlations: list[Correlation],
        carbon_shifts: dict[int, float] | None = None,
        proton_shifts: dict[int, float] | None = None,
        atom_numbers: dict[int, str] | None = None,
        j_couplings: dict[tuple[int, int], int] | None = None,
    ) -> DiagramResult:
        """Generate correlation diagram from pre-built RDKit molecule.

        This method is used when atom ordering must be preserved (e.g., from LSD).
        The molecule should already have 2D coordinates computed.

        Args:
            mol: RDKit molecule with 2D coordinates
            correlations: List of NMR correlations to visualize
            carbon_shifts: Optional dict of atom_index -> 13C shift (ppm)
            proton_shifts: Optional dict of atom_index -> 1H shift (ppm)
            atom_numbers: Optional dict of atom_index -> label string
            j_couplings: Optional dict of (source, target) -> J value

        Returns:
            DiagramResult with SVG content and metadata
        """
        # Optionally add explicit hydrogens
        if self.config.show_hydrogens:
            mol = Chem.AddHs(mol)
            AllChem.Compute2DCoords(mol)

        # Extract atom positions
        atom_positions = self._extract_atom_positions(mol)

        # Add chemical shift data
        if carbon_shifts:
            self._annotate_shifts(atom_positions, carbon_shifts, "carbon")
        if proton_shifts:
            self._annotate_shifts(atom_positions, proton_shifts, "proton")

        # Route arrows to minimize overlaps
        routed_arrows = self._router.route_arrows(
            correlations, atom_positions, self.config, mol
        )

        # Fan out arrows sharing endpoints
        routed_arrows = fan_out_arrows(routed_arrows)

        # Build SVG
        svg_content = self._build_svg(
            mol, atom_positions, routed_arrows, atom_numbers, j_couplings
        )

        return DiagramResult(
            svg_content=svg_content,
            width=self.config.width,
            height=self.config.height,
            atom_count=mol.GetNumAtoms(),
            correlation_count=len(correlations),
            arrows_routed=len(routed_arrows),
        )

    def generate_from_lsd_problem(
        self,
        smiles: str,
        problem: LSDProblem,
    ) -> DiagramResult:
        """Generate diagram from an LSD problem definition.

        Extracts HMBC correlations and chemical shifts from the LSDProblem.
        Note: LSD uses 1-based atom indices, which are converted to 0-based.

        Args:
            smiles: Molecular structure in SMILES format
            problem: LSD problem with atoms and correlations

        Returns:
            DiagramResult with SVG content and metadata
        """
        # Convert LSD correlations to visualization correlations
        correlations = self._convert_lsd_correlations(problem)

        # Extract chemical shifts (convert 1-based to 0-based indices)
        carbon_shifts: dict[int, float] = {}
        proton_shifts: dict[int, float] = {}

        for atom in problem.atoms:
            idx = atom.index - 1  # Convert to 0-based
            if atom.carbon_shift is not None:
                carbon_shifts[idx] = atom.carbon_shift
            if atom.proton_shift is not None:
                proton_shifts[idx] = atom.proton_shift

        return self.generate(
            smiles,
            correlations,
            carbon_shifts if carbon_shifts else None,
            proton_shifts if proton_shifts else None,
        )

    def generate_from_sol_file(
        self,
        sol_path: str | Path,
        lsd_path: str | Path,
        solution_number: int = 1,
        show_j_coupling: bool = False,
    ) -> DiagramResult:
        """Generate diagram from LSD solution with optional J-coupling labels.

        Parses the .sol file to extract molecular connectivity and creates
        a correlation diagram with the solved structure. Optionally includes
        J-coupling annotations (²J, ³J, etc.) on HMBC arrows.

        IMPORTANT: Uses to_rdkit_mol() directly to preserve LSD atom ordering.
        This ensures LSD index N corresponds to RDKit index N-1.

        Args:
            sol_path: Path to .sol file with molecular connectivity
            lsd_path: Path to .lsd file with correlations and shifts
            solution_number: Which solution to visualize (1-based)
            show_j_coupling: Add ²J/³J labels on arrows

        Returns:
            DiagramResult with SVG content and metadata

        Raises:
            ValueError: If solution not found or files invalid
        """
        from lucy_ng.lsd.analyzer import LSDSolutionAnalyzer

        # Analyze solution
        results = LSDSolutionAnalyzer.analyze(
            Path(sol_path), Path(lsd_path), solution_number
        )
        if not results:
            raise ValueError(f"Solution {solution_number} not found in {sol_path}")

        result = results[0]

        # Get RDKit mol directly to preserve LSD atom ordering
        # CRITICAL: Don't use to_smiles() as it canonicalizes and breaks index mapping!
        mol = result.graph.to_rdkit_mol()
        if mol is None:
            raise ValueError("Could not generate RDKit molecule from solution")

        # Convert correlations (LSD 1-based → RDKit 0-based)
        # Since to_rdkit_mol() preserves order: LSD index N → RDKit index N-1
        correlations: list[Correlation] = []
        j_couplings: dict[tuple[int, int], int] = {}

        for c in result.correlations:
            corr = Correlation(
                source_atom=c.carbon_idx - 1,
                target_atom=c.proton_idx - 1,
                correlation_type=CorrelationType.HMBC,
            )
            correlations.append(corr)

            if show_j_coupling and c.j_coupling is not None:
                j_couplings[(c.carbon_idx - 1, c.proton_idx - 1)] = c.j_coupling

        # Get shifts from analysis
        shifts: dict[int, float] = {}
        for c in result.correlations:
            if c.carbon_shift is not None:
                shifts[c.carbon_idx - 1] = c.carbon_shift

        # Build atom number map (LSD numbering, 1-based labels)
        atom_numbers: dict[int, str] | None = None
        if self.config.show_atom_numbers:
            atom_numbers = {i - 1: str(i) for i in result.graph.atoms.keys()}

        return self._generate_from_mol(
            mol=mol,
            correlations=correlations,
            carbon_shifts=shifts if shifts else None,
            atom_numbers=atom_numbers,
            j_couplings=j_couplings if show_j_coupling and j_couplings else None,
        )

    def _convert_lsd_correlations(self, problem: LSDProblem) -> list[Correlation]:
        """Convert LSD correlations to visualization correlations.

        Filters for HMBC correlations and converts 1-based to 0-based indices.
        """
        correlations = []
        for lsd_corr in problem.correlations:
            # Map LSD correlation types
            corr_type_map = {
                "HMBC": CorrelationType.HMBC,
                "HSQC": CorrelationType.HSQC,
                "HMQC": CorrelationType.HSQC,  # Treat HMQC as HSQC
                "COSY": CorrelationType.COSY,
            }

            if lsd_corr.correlation_type not in corr_type_map:
                continue

            correlations.append(
                Correlation(
                    source_atom=lsd_corr.atom1_index - 1,  # Convert to 0-based
                    target_atom=lsd_corr.atom2_index - 1,
                    correlation_type=corr_type_map[lsd_corr.correlation_type],
                )
            )

        return correlations

    def _prepare_molecule(self, smiles: str) -> Chem.Mol:
        """Parse SMILES and compute 2D coordinates.

        Args:
            smiles: SMILES string

        Returns:
            RDKit molecule with 2D coordinates

        Raises:
            ValueError: If SMILES is invalid
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")

        # Add explicit hydrogens if configured
        if self.config.show_hydrogens:
            mol = Chem.AddHs(mol)

        # Compute 2D layout
        AllChem.Compute2DCoords(mol)

        return mol

    def _extract_atom_positions(self, mol: Chem.Mol) -> dict[int, AtomPosition]:
        """Extract 2D coordinates for all atoms.

        Args:
            mol: RDKit molecule with conformer

        Returns:
            Dict mapping atom index to AtomPosition
        """
        conf = mol.GetConformer()
        positions: dict[int, AtomPosition] = {}

        for atom in mol.GetAtoms():
            idx = atom.GetIdx()
            pos = conf.GetAtomPosition(idx)
            positions[idx] = AtomPosition(
                atom_index=idx,
                x=pos.x,
                y=pos.y,
                element=atom.GetSymbol(),
                hydrogen_count=atom.GetTotalNumHs(),
            )

        return positions

    def _annotate_shifts(
        self,
        positions: dict[int, AtomPosition],
        shifts: dict[int, float],
        shift_type: str,
    ) -> None:
        """Add chemical shift annotations to atom positions.

        Args:
            positions: Dict of atom positions to annotate
            shifts: Dict of atom_index -> shift (ppm)
            shift_type: "carbon" or "proton"
        """
        for idx, shift in shifts.items():
            if idx in positions:
                if shift_type == "carbon":
                    positions[idx].carbon_shift = shift
                else:
                    positions[idx].proton_shift = shift

    def _build_svg(
        self,
        mol: Chem.Mol,
        atom_positions: dict[int, AtomPosition],
        routed_arrows: list[RoutedArrow],
        atom_numbers: dict[int, str] | None = None,
        j_couplings: dict[tuple[int, int], int] | None = None,
    ) -> str:
        """Build complete SVG with structure, arrows, and labels.

        Args:
            mol: RDKit molecule
            atom_positions: Dict of atom positions
            routed_arrows: List of routed arrows to draw
            atom_numbers: Optional dict of atom_index -> label for numbering
            j_couplings: Optional dict of (source, target) -> J value

        Returns:
            Complete SVG document as string
        """
        # Create SVG builder
        builder = SVGBuilder(self.config.width, self.config.height)

        # Add background
        builder.add_raw_svg(
            f'<rect width="{self.config.width}" height="{self.config.height}" fill="white" />'
        )

        # Render molecule using RDKit and get actual drawing coordinates
        mol_svg, drawing_coords = self._render_molecule_svg_with_coords(mol)
        builder.add_raw_svg(mol_svg)

        # Update atom positions with actual drawing coordinates
        transformed_positions: dict[int, AtomPosition] = {}
        for idx, pos in atom_positions.items():
            if idx in drawing_coords:
                draw_x, draw_y = drawing_coords[idx]
                transformed_positions[idx] = AtomPosition(
                    atom_index=pos.atom_index,
                    x=draw_x,
                    y=draw_y,
                    element=pos.element,
                    hydrogen_count=pos.hydrogen_count,
                    carbon_shift=pos.carbon_shift,
                    proton_shift=pos.proton_shift,
                )

        # Add start markers (circles) for clear correlation origin indication
        # No arrowheads - just circles at start and end points for cleaner look
        builder.add_start_marker("hmbc-start", self.config.hmbc_style.color, self.config.hmbc_style.start_marker_size)
        builder.add_start_marker("hsqc-start", self.config.hsqc_style.color, self.config.hsqc_style.start_marker_size)
        builder.add_start_marker("cosy-start", self.config.cosy_style.color, self.config.cosy_style.start_marker_size)
        builder.add_start_marker("noesy-start", self.config.noesy_style.color, self.config.noesy_style.start_marker_size)

        # Add end markers (smaller circles) for correlation target indication
        builder.add_start_marker("hmbc-end", self.config.hmbc_style.color, self.config.hmbc_style.start_marker_size * 0.8)
        builder.add_start_marker("hsqc-end", self.config.hsqc_style.color, self.config.hsqc_style.start_marker_size * 0.8)
        builder.add_start_marker("cosy-end", self.config.cosy_style.color, self.config.cosy_style.start_marker_size * 0.8)
        builder.add_start_marker("noesy-end", self.config.noesy_style.color, self.config.noesy_style.start_marker_size * 0.8)

        # Route arrows using actual drawing coordinates
        # Re-route arrows with the correct screen coordinates
        routed_arrows = self._router.route_arrows(
            [a.correlation for a in routed_arrows],
            transformed_positions,
            self.config,
            mol,
        )

        # Add arrows (already in screen coordinates now)
        for arrow in routed_arrows:
            # Get marker ids based on correlation type (circles at both ends, no arrowheads)
            marker_ids = {
                CorrelationType.HMBC: ("hmbc-end", "hmbc-start"),
                CorrelationType.HSQC: ("hsqc-end", "hsqc-start"),
                CorrelationType.COSY: ("cosy-end", "cosy-start"),
                CorrelationType.NOESY: ("noesy-end", "noesy-start"),
                CorrelationType.ROESY: ("noesy-end", "noesy-start"),
            }
            end_marker_id, start_marker_id = marker_ids.get(
                arrow.correlation.correlation_type, ("hmbc-end", "hmbc-start")
            )

            builder.add_bezier_arrow(arrow, end_marker_id, start_marker_id)

        # Add chemical shift labels
        if self.config.show_chemical_shifts:
            self._add_shift_labels(builder, transformed_positions)

        # Add publication-style atom number annotations
        if self.config.show_atom_numbers or atom_numbers:
            self._add_atom_number_annotations(
                builder, transformed_positions, atom_numbers
            )

        # Add J-coupling labels on arrows (arrows are already in screen coordinates)
        if j_couplings:
            self._add_j_coupling_labels_direct(builder, routed_arrows, j_couplings)

        # Add legend
        if self.config.show_legend:
            legend_x = self.config.width - self.config.padding - 100
            legend_y = self.config.padding + 20

            # Only show correlation types that are present
            legend_items = []
            corr_types_present = {a.correlation.correlation_type for a in routed_arrows}

            if CorrelationType.HMBC in corr_types_present:
                legend_items.append(("HMBC", self.config.hmbc_style))
            if CorrelationType.HSQC in corr_types_present:
                legend_items.append(("HSQC", self.config.hsqc_style))
            if CorrelationType.COSY in corr_types_present:
                legend_items.append(("COSY", self.config.cosy_style))
            if CorrelationType.NOESY in corr_types_present or CorrelationType.ROESY in corr_types_present:
                legend_items.append(("NOESY", self.config.noesy_style))

            if legend_items:
                builder.add_legend(
                    legend_x,
                    legend_y,
                    legend_items,
                    font_size=self.config.legend_font_size,
                    arrow_length=self.config.legend_arrow_length,
                    arrow_head_size=self.config.legend_arrow_head_size,
                )

        return builder.build()

    def _render_molecule_svg_with_coords(
        self,
        mol: Chem.Mol,
    ) -> tuple[str, dict[int, tuple[float, float]]]:
        """Render molecule structure using RDKit and return drawing coordinates.

        Returns:
            Tuple of (svg_content, drawing_coords) where drawing_coords maps
            atom index to (x, y) pixel coordinates as drawn by RDKit.
        """
        import re

        # Clear atom map numbers to avoid double-labeling (we add our own labels)
        for atom in mol.GetAtoms():
            atom.SetAtomMapNum(0)

        # Use RDKit's drawer
        drawer = rdMolDraw2D.MolDraw2DSVG(self.config.width, self.config.height)

        # Configure drawing options
        opts = drawer.drawOptions()
        opts.addAtomIndices = self.config.show_atom_indices
        opts.addStereoAnnotation = False

        # Draw the molecule
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()

        # Get the actual drawing coordinates for each atom
        drawing_coords: dict[int, tuple[float, float]] = {}
        for atom in mol.GetAtoms():
            idx = atom.GetIdx()
            point = drawer.GetDrawCoords(idx)
            drawing_coords[idx] = (point.x, point.y)

        # Get SVG and extract just the drawing elements
        svg_text = drawer.GetDrawingText()

        # Find content between <svg...> and </svg>
        match = re.search(r'<svg[^>]*>(.*)</svg>', svg_text, re.DOTALL)
        if match:
            inner_content = match.group(1)
            # Remove any rect background that RDKit adds
            inner_content = re.sub(r'<rect[^>]*fill=["\']#FFFFFF["\'][^>]*/>', '', inner_content)
            return inner_content, drawing_coords

        return "", drawing_coords

    def _transform_arrow(
        self,
        arrow: RoutedArrow,
        scale: float,
        offset_x: float,
        offset_y: float,
        min_x: float,
        min_y: float,
    ) -> RoutedArrow:
        """Transform arrow coordinates to canvas space."""

        def transform_point(x: float, y: float) -> tuple[float, float]:
            return (x * scale + offset_x, y * scale + offset_y)

        start = transform_point(arrow.start_x, arrow.start_y)
        end = transform_point(arrow.end_x, arrow.end_y)
        ctrl_points = [transform_point(cx, cy) for cx, cy in arrow.control_points]

        return RoutedArrow(
            correlation=arrow.correlation,
            start_x=start[0],
            start_y=start[1],
            end_x=end[0],
            end_y=end[1],
            control_points=ctrl_points,
            style=arrow.style,
        )

    def _add_shift_labels(
        self,
        builder: SVGBuilder,
        positions: dict[int, AtomPosition],
    ) -> None:
        """Add chemical shift labels near atoms."""
        for pos in positions.values():
            if pos.carbon_shift is not None and pos.element == "C":
                # Format shift to 1 decimal place
                label = f"{pos.carbon_shift:.1f}"
                # Position label slightly offset from atom
                label_x = pos.x + self.config.shift_label_offset
                label_y = pos.y - self.config.shift_label_offset / 2

                builder.add_text_label(
                    label_x,
                    label_y,
                    label,
                    font_size=self.config.font_size * 0.8,
                    color="#666666",
                    anchor="start",
                    font_family=self.config.font_family,
                )

    def _add_atom_number_annotations(
        self,
        builder: SVGBuilder,
        positions: dict[int, AtomPosition],
        atom_numbers: dict[int, str] | None,
    ) -> None:
        """Add publication-style atom number annotations.

        Places red number labels near atoms, positioned to minimize overlap
        with the molecular structure. If atom_numbers is not provided but
        show_atom_numbers is True, generates sequential numbers.

        Args:
            builder: SVG builder to add annotations to
            positions: Dict of atom positions (transformed to canvas space)
            atom_numbers: Optional dict of atom_index -> label string
        """
        # If no explicit numbers provided, generate from indices
        # Only number heavy atoms (non-hydrogen)
        if atom_numbers is None:
            atom_numbers = {
                idx: str(idx + 1)  # 1-based numbering
                for idx, pos in positions.items()
                if pos.element != "H"
            }

        # Calculate molecule center for positioning
        heavy_positions = [p for p in positions.values() if p.element != "H"]
        if not heavy_positions:
            return

        center_x = sum(p.x for p in heavy_positions) / len(heavy_positions)
        center_y = sum(p.y for p in heavy_positions) / len(heavy_positions)

        for idx, label in atom_numbers.items():
            if idx not in positions:
                continue

            pos = positions[idx]

            # Smart positioning: offset away from molecule center
            dx = pos.x - center_x
            dy = pos.y - center_y
            dist = (dx**2 + dy**2) ** 0.5

            if dist > 0.001:
                # Normalize and scale
                offset_x = (dx / dist) * self.config.atom_number_offset
                offset_y = (dy / dist) * self.config.atom_number_offset
            else:
                # Default offset if at center
                offset_x = self.config.atom_number_offset
                offset_y = -self.config.atom_number_offset / 2

            label_x = pos.x + offset_x
            label_y = pos.y + offset_y + self.config.atom_number_font_size / 3

            builder.add_atom_number(
                label_x,
                label_y,
                label,
                font_size=self.config.atom_number_font_size,
                color=self.config.atom_number_color,
            )

    def _add_j_coupling_labels(
        self,
        builder: SVGBuilder,
        routed_arrows: list[RoutedArrow],
        j_couplings: dict[tuple[int, int], int],
        scale: float,
        offset_x: float,
        offset_y: float,
    ) -> None:
        """Add J-coupling labels (²J, ³J, etc.) on HMBC arrows.

        Places the J-coupling notation near the midpoint of each arrow.

        Args:
            builder: SVG builder to add labels to
            routed_arrows: List of routed arrows
            j_couplings: Dict mapping (source, target) to J value
            scale: Coordinate scale factor
            offset_x: X offset for transformation
            offset_y: Y offset for transformation
        """
        for arrow in routed_arrows:
            # Check if this correlation has a J-coupling value
            key = (arrow.correlation.source_atom, arrow.correlation.target_atom)
            key_rev = (arrow.correlation.target_atom, arrow.correlation.source_atom)

            j_value = j_couplings.get(key) or j_couplings.get(key_rev)
            if j_value is None:
                continue

            # Calculate position at the arrow's control point (curve apex)
            if arrow.control_points:
                # Transform control point to canvas space
                ctrl_x, ctrl_y = arrow.control_points[0]
                label_x = ctrl_x * scale + offset_x
                label_y = ctrl_y * scale + offset_y - 5  # Slight offset above
            else:
                # Midpoint for straight arrows
                label_x = (arrow.start_x + arrow.end_x) / 2 * scale + offset_x
                label_y = (arrow.start_y + arrow.end_y) / 2 * scale + offset_y - 5

            builder.add_j_coupling_label(
                label_x,
                label_y,
                j_value,
                font_size=self.config.j_coupling_font_size,
                color="#444444",
            )

    def _add_j_coupling_labels_direct(
        self,
        builder: SVGBuilder,
        routed_arrows: list[RoutedArrow],
        j_couplings: dict[tuple[int, int], int],
    ) -> None:
        """Add J-coupling labels for arrows already in screen coordinates.

        Args:
            builder: SVG builder to add labels to
            routed_arrows: List of routed arrows (in screen coordinates)
            j_couplings: Dict mapping (source, target) to J value
        """
        for arrow in routed_arrows:
            # Check if this correlation has a J-coupling value
            key = (arrow.correlation.source_atom, arrow.correlation.target_atom)
            key_rev = (arrow.correlation.target_atom, arrow.correlation.source_atom)

            j_value = j_couplings.get(key) or j_couplings.get(key_rev)
            if j_value is None:
                continue

            # Calculate position at the arrow's control point (curve apex)
            if arrow.control_points:
                ctrl_x, ctrl_y = arrow.control_points[0]
                label_x = ctrl_x
                label_y = ctrl_y - 5  # Slight offset above
            else:
                # Midpoint for straight arrows
                label_x = (arrow.start_x + arrow.end_x) / 2
                label_y = (arrow.start_y + arrow.end_y) / 2 - 5

            builder.add_j_coupling_label(
                label_x,
                label_y,
                j_value,
                font_size=self.config.j_coupling_font_size,
                color="#444444",
            )
