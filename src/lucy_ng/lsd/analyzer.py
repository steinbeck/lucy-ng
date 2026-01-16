"""Analyzer for LSD solution files.

Parses .sol files to extract molecular connectivity and computes
J-coupling path lengths for HMBC correlations.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SolutionAtom:
    """Atom in a solved structure."""

    index: int
    element: str
    h_count: int
    neighbors: list[int] = field(default_factory=list)
    bond_orders: list[int] = field(default_factory=list)  # Bond order for each neighbor


@dataclass
class SolutionGraph:
    """Molecular graph extracted from LSD solution."""

    solution_number: int
    atoms: dict[int, SolutionAtom] = field(default_factory=dict)
    _adjacency: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))

    def __post_init__(self) -> None:
        """Build adjacency list from atoms."""
        self._rebuild_adjacency()

    def _rebuild_adjacency(self) -> None:
        """Rebuild adjacency list from atom neighbors."""
        self._adjacency = defaultdict(set)
        for atom_idx, atom in self.atoms.items():
            for neighbor in atom.neighbors:
                self._adjacency[atom_idx].add(neighbor)
                self._adjacency[neighbor].add(atom_idx)

    def shortest_path(self, start: int, end: int) -> int:
        """Find shortest path (number of bonds) between two atoms using BFS.

        Args:
            start: Starting atom index
            end: Target atom index

        Returns:
            Number of bonds in shortest path, or -1 if no path exists
        """
        if start == end:
            return 0
        if start not in self._adjacency or end not in self._adjacency:
            return -1

        visited = {start}
        queue = [(start, 0)]

        while queue:
            node, dist = queue.pop(0)
            for neighbor in self._adjacency[node]:
                if neighbor == end:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return -1  # No path found

    def to_rdkit_mol(self) -> "Chem.Mol | None":
        """Convert solution graph to RDKit molecule with LSD atom numbering.

        Creates an RDKit molecule from the molecular connectivity stored in
        this solution graph. Each atom's AtomMapNum is set to its LSD index
        (1-based), enabling labeled structure rendering.

        Returns:
            RDKit Mol object with atom map numbers set to LSD indices,
            or None if RDKit is not available.

        Example:
            >>> graph = LSDSolutionAnalyzer.parse_sol_file("compound.sol")[0]
            >>> mol = graph.to_rdkit_mol()
            >>> # Render with atom labels
            >>> from rdkit.Chem import Draw
            >>> Draw.MolToFile(mol, "structure.png")
        """
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem
        except ImportError:
            return None

        mol = Chem.RWMol()
        atom_map: dict[int, int] = {}  # LSD index -> RDKit index

        # Add atoms in LSD index order
        for lsd_idx in sorted(self.atoms.keys()):
            atom = self.atoms[lsd_idx]
            rdkit_atom = Chem.Atom(atom.element)
            rdkit_atom.SetNumExplicitHs(atom.h_count)
            rdkit_atom.SetAtomMapNum(lsd_idx)  # Store LSD index for labeling
            rdkit_idx = mol.AddAtom(rdkit_atom)
            atom_map[lsd_idx] = rdkit_idx

        # Add bonds (only once per pair, using bond orders)
        bond_type_map = {
            1: Chem.BondType.SINGLE,
            2: Chem.BondType.DOUBLE,
            3: Chem.BondType.TRIPLE,
        }
        added_bonds: set[tuple[int, int]] = set()

        for lsd_idx, atom in self.atoms.items():
            for i, neighbor in enumerate(atom.neighbors):
                bond_key = tuple(sorted([lsd_idx, neighbor]))
                if bond_key not in added_bonds:
                    # Get bond order (default to single if not available)
                    bond_order = atom.bond_orders[i] if i < len(atom.bond_orders) else 1
                    bond_type = bond_type_map.get(bond_order, Chem.BondType.SINGLE)
                    mol.AddBond(atom_map[lsd_idx], atom_map[neighbor], bond_type)
                    added_bonds.add(bond_key)

        mol = mol.GetMol()
        AllChem.Compute2DCoords(mol)
        return mol

    def to_smiles(self) -> str | None:
        """Generate SMILES string from solution graph.

        Returns:
            SMILES string, or None if RDKit is not available.
        """
        mol = self.to_rdkit_mol()
        if mol is None:
            return None

        from rdkit import Chem

        # Remove atom map numbers for clean SMILES
        mol_clean = Chem.RWMol(mol)
        for atom in mol_clean.GetAtoms():
            atom.SetAtomMapNum(0)
        return Chem.MolToSmiles(mol_clean.GetMol())

    def draw_with_atom_numbers(
        self,
        output_path: str | Path,
        size: tuple[int, int] = (600, 450),
        font_size: int = 20,
        show_h_labels: bool = True,
    ) -> bool:
        """Draw structure with LSD atom numbers as labels.

        Args:
            output_path: Path to save image (PNG or SVG based on extension)
            size: Image dimensions (width, height)
            font_size: Font size for atom labels
            show_h_labels: If True, show H indices for protonated carbons (e.g., "C7/H7")

        Returns:
            True if successful, False if RDKit not available
        """
        mol = self.to_rdkit_mol()
        if mol is None:
            return False

        try:
            from rdkit.Chem.Draw import rdMolDraw2D
        except ImportError:
            return False

        output_path = Path(output_path)
        suffix = output_path.suffix.lower()

        if suffix == ".svg":
            drawer = rdMolDraw2D.MolDraw2DSVG(*size)
        else:
            drawer = rdMolDraw2D.MolDraw2DCairo(*size)

        opts = drawer.drawOptions()
        opts.bondLineWidth = 2
        opts.atomLabelFontSize = font_size

        # Set atom labels to element + LSD number
        # For protonated carbons, also show H index (e.g., "C7/H7")
        for atom in mol.GetAtoms():
            lsd_num = atom.GetAtomMapNum()
            sym = atom.GetSymbol()
            h_count = atom.GetNumExplicitHs()

            if show_h_labels and sym == "C" and h_count > 0:
                # Show both C and H labels for protonated carbons
                opts.atomLabels[atom.GetIdx()] = f"C{lsd_num}/H{lsd_num}"
            else:
                opts.atomLabels[atom.GetIdx()] = f"{sym}{lsd_num}"

        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()

        with open(output_path, "wb" if suffix != ".svg" else "w") as f:
            f.write(drawer.GetDrawingText())

        return True


@dataclass
class HMBCCorrelation:
    """HMBC correlation with computed J-coupling."""

    carbon_idx: int
    proton_idx: int  # This is the index of the carbon bearing the proton
    carbon_shift: float | None = None
    path_length: int | None = None  # Number of bonds

    @property
    def j_coupling(self) -> int | None:
        """Return n for nJ_CH (path_length + 1)."""
        if self.path_length is None:
            return None
        return self.path_length + 1

    @property
    def j_notation(self) -> str:
        """Return spectroscopist notation like ²J_CH, ³J_CH."""
        if self.j_coupling is None:
            return "?J_CH"
        superscripts = {2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶"}
        sup = superscripts.get(self.j_coupling, str(self.j_coupling))
        return f"{sup}J_CH"


@dataclass
class AnalysisResult:
    """Result of analyzing HMBC correlations against a solution."""

    solution_number: int
    correlations: list[HMBCCorrelation]
    graph: SolutionGraph

    @property
    def all_2j_3j(self) -> bool:
        """Check if all correlations are ²J or ³J."""
        for corr in self.correlations:
            if corr.j_coupling is not None and corr.j_coupling > 3:
                return False
        return True

    @property
    def max_j(self) -> int | None:
        """Return the maximum J coupling found."""
        j_values = [c.j_coupling for c in self.correlations if c.j_coupling is not None]
        return max(j_values) if j_values else None

    def summary(self) -> str:
        """Return a summary of the analysis."""
        j_counts: dict[int, int] = defaultdict(int)
        for corr in self.correlations:
            if corr.j_coupling is not None:
                j_counts[corr.j_coupling] += 1

        parts = [f"Solution {self.solution_number}:"]
        for j in sorted(j_counts.keys()):
            sup = {2: "²", 3: "³", 4: "⁴", 5: "⁵"}.get(j, str(j))
            parts.append(f"{j_counts[j]}× {sup}J")

        if self.all_2j_3j:
            parts.append("(all ²J/³J, no ELIM needed)")
        else:
            parts.append(f"(max {self.max_j}J, may need ELIM)")

        return " ".join(parts)


class LSDSolutionAnalyzer:
    """Analyze LSD solutions for HMBC J-coupling paths."""

    @staticmethod
    def parse_sol_file(sol_path: Path | str) -> list[SolutionGraph]:
        """Parse a .sol file to extract molecular graphs for all solutions.

        The .sol file contains an OUTLSD section with connectivity data:
        ```
        11 1                           # Solution 1 with 11 atoms
         1  C 4 0 3 3  0   2 2   7 1  10 1   0 0
         1  C 4 1 2 2  0   8 1   1 2   0 0   0 0
        ...
        11 2                           # Solution 2
        ...
        0                              # End marker
        ```

        Args:
            sol_path: Path to .sol file

        Returns:
            List of SolutionGraph objects
        """
        sol_path = Path(sol_path)
        content = sol_path.read_text()
        lines = content.split("\n")

        solutions: list[SolutionGraph] = []
        current_solution: SolutionGraph | None = None
        atom_idx = 0
        in_outlsd = False

        for line in lines:
            line = line.strip()

            # Look for OUTLSD section
            if line == "OUTLSD":
                in_outlsd = True
                continue

            if not in_outlsd:
                continue

            # End of solutions
            if line == "0":
                if current_solution:
                    current_solution._rebuild_adjacency()
                    solutions.append(current_solution)
                break

            # Solution header: "11 1" = 11 atoms, solution 1
            if re.match(r"^\d+\s+\d+$", line):
                if current_solution:
                    current_solution._rebuild_adjacency()
                    solutions.append(current_solution)

                parts = line.split()
                sol_num = int(parts[1])
                current_solution = SolutionGraph(solution_number=sol_num)
                atom_idx = 0
                continue

            # Atom line: starts with "1" (status), then element (C, O, N, etc.)
            # Format: "1  C 4 0 3 3  0   2 2   7 1  10 1   0 0"
            # Fields: status element ? h_count ? ? ? (neighbor bond_order)...
            if current_solution and re.match(r"^1\s+[A-Z]", line):
                atom_idx += 1
                parts = line.split()

                if len(parts) >= 8:
                    element = parts[1]
                    h_count = int(parts[3])

                    # Parse neighbors: pairs of (atom_num, bond_order) starting at index 7
                    neighbors = []
                    bond_orders = []
                    for i in range(7, len(parts), 2):
                        neighbor_atom = int(parts[i])
                        if neighbor_atom > 0 and i + 1 < len(parts):
                            neighbors.append(neighbor_atom)
                            bond_orders.append(int(parts[i + 1]))

                    current_solution.atoms[atom_idx] = SolutionAtom(
                        index=atom_idx,
                        element=element,
                        h_count=h_count,
                        neighbors=neighbors,
                        bond_orders=bond_orders,
                    )

        return solutions

    @staticmethod
    def parse_lsd_file(lsd_path: Path | str) -> tuple[list[tuple[int, int]], dict[int, float]]:
        """Parse .lsd file to extract HMBC correlations and chemical shifts.

        Args:
            lsd_path: Path to .lsd file

        Returns:
            Tuple of (hmbc_correlations, shifts_dict)
            - hmbc_correlations: List of (carbon_idx, proton_idx) tuples
            - shifts_dict: Dict mapping atom index to chemical shift
        """
        lsd_path = Path(lsd_path)
        content = lsd_path.read_text()

        hmbc_correlations: list[tuple[int, int]] = []
        shifts: dict[int, float] = {}

        for line in content.split("\n"):
            line = line.strip()

            # Skip comments
            if line.startswith(";") or not line:
                continue

            # Parse HMBC correlations
            match = re.match(r"HMBC\s+(\d+)\s+(\d+)", line)
            if match:
                c_idx = int(match.group(1))
                h_idx = int(match.group(2))
                hmbc_correlations.append((c_idx, h_idx))
                continue

            # Parse chemical shifts
            match = re.match(r"SHIX\s+(\d+)\s+([\d.]+)", line)
            if match:
                atom_idx = int(match.group(1))
                shift = float(match.group(2))
                shifts[atom_idx] = shift

        return hmbc_correlations, shifts

    @classmethod
    def analyze(
        cls,
        sol_path: Path | str,
        lsd_path: Path | str,
        solution_number: int | None = None,
    ) -> list[AnalysisResult]:
        """Analyze HMBC correlations for one or all solutions.

        Args:
            sol_path: Path to .sol file with molecular connectivity
            lsd_path: Path to .lsd file with HMBC correlations
            solution_number: Specific solution to analyze (1-based), or None for all

        Returns:
            List of AnalysisResult objects
        """
        # Parse files
        solutions = cls.parse_sol_file(sol_path)
        hmbc_correlations, shifts = cls.parse_lsd_file(lsd_path)

        results: list[AnalysisResult] = []

        for graph in solutions:
            if solution_number is not None and graph.solution_number != solution_number:
                continue

            correlations: list[HMBCCorrelation] = []

            for c_idx, h_idx in hmbc_correlations:
                # h_idx is the atom index of the carbon bearing the proton
                # (from HSQC, where HSQC n n means carbon n has proton n)
                path_length = graph.shortest_path(c_idx, h_idx)

                corr = HMBCCorrelation(
                    carbon_idx=c_idx,
                    proton_idx=h_idx,
                    carbon_shift=shifts.get(c_idx),
                    path_length=path_length if path_length >= 0 else None,
                )
                correlations.append(corr)

            results.append(
                AnalysisResult(
                    solution_number=graph.solution_number,
                    correlations=correlations,
                    graph=graph,
                )
            )

        return results
