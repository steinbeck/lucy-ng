"""Data models for LSD (Logic for Structure Determination) integration."""

from dataclasses import dataclass, field
from enum import Enum


class Hybridization(Enum):
    """Atom hybridization state for LSD."""

    SP = 1  # Triple bond or allene
    SP2 = 2  # Double bond, aromatic
    SP3 = 3  # Single bonds only


@dataclass
class LSDAtom:
    """Atom definition for LSD input.

    Corresponds to the MULT command in LSD:
    MULT atom_num element hybridization h_count [charge]

    Attributes:
        index: Atom number (1-based, as used in LSD)
        element: Chemical element symbol (C, N, O, S, etc.)
        hybridization: sp, sp2, or sp3
        hydrogen_count: Number of directly bonded hydrogens
        charge: Formal charge (-1, 0, 1, 2)
        carbon_shift: 13C chemical shift in ppm (optional)
        proton_shift: 1H chemical shift in ppm (optional, for attached H)
    """

    index: int
    element: str
    hybridization: Hybridization
    hydrogen_count: int
    charge: int = 0
    carbon_shift: float | None = None
    proton_shift: float | None = None

    def __post_init__(self) -> None:
        """Validate atom parameters."""
        valid_elements = {"C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "Si", "B"}
        if self.element not in valid_elements:
            raise ValueError(f"Invalid element: {self.element}. Valid: {valid_elements}")
        if self.index < 1:
            raise ValueError(f"Atom index must be >= 1, got {self.index}")
        if self.hydrogen_count < 0:
            raise ValueError(f"Hydrogen count must be >= 0, got {self.hydrogen_count}")
        if self.charge not in (-1, 0, 1, 2):
            raise ValueError(f"Charge must be -1, 0, 1, or 2, got {self.charge}")

    def to_mult_line(self) -> str:
        """Generate LSD MULT command line.

        Returns:
            String like "MULT 1 C 2 0" or "MULT 1 N 3 1 1" (with charge)
        """
        parts = [
            "MULT",
            str(self.index),
            self.element,
            str(self.hybridization.value),
            str(self.hydrogen_count),
        ]
        if self.charge != 0:
            parts.append(str(self.charge))
        return " ".join(parts)


@dataclass
class LSDConstraint:
    """Structural constraint for LSD input.

    Represents BOND (required bond) or FBND (forbidden bond) constraints.
    These encode prior chemical knowledge derived from spectroscopic data.

    Attributes:
        atom1_index: First atom index
        atom2_index: Second atom index
        constraint_type: "BOND" (required) or "FBND" (forbidden)
        reason: Optional reason/source for this constraint
    """

    atom1_index: int
    atom2_index: int
    constraint_type: str = "BOND"
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate constraint parameters."""
        valid_types = {"BOND", "FBND"}
        if self.constraint_type not in valid_types:
            raise ValueError(
                f"Invalid constraint type: {self.constraint_type}. Valid: {valid_types}"
            )
        if self.atom1_index < 1 or self.atom2_index < 1:
            raise ValueError("Atom indices must be >= 1")

    def to_lsd_line(self) -> str:
        """Generate LSD constraint command line.

        Returns:
            String like "BOND 1 2" or "FBND 3 4"
        """
        return f"{self.constraint_type} {self.atom1_index} {self.atom2_index}"


@dataclass
class LSDCorrelation:
    """NMR correlation for LSD input.

    Represents HSQC (direct), HMBC (long-range), or COSY (H-H) correlations.

    Attributes:
        atom1_index: First atom index (carbon for HSQC/HMBC, H for COSY)
        atom2_index: Second atom index (H position for HSQC/HMBC, H for COSY)
        correlation_type: "HSQC", "HMBC", or "COSY"
        min_bonds: Minimum bond distance (for HMBC, default 2)
        max_bonds: Maximum bond distance (for HMBC, default 3)
    """

    atom1_index: int
    atom2_index: int
    correlation_type: str
    min_bonds: int = 2
    max_bonds: int = 3

    def __post_init__(self) -> None:
        """Validate correlation parameters."""
        valid_types = {"HSQC", "HMBC", "COSY", "HMQC"}
        if self.correlation_type not in valid_types:
            raise ValueError(
                f"Invalid correlation type: {self.correlation_type}. Valid: {valid_types}"
            )
        if self.atom1_index < 1 or self.atom2_index < 1:
            raise ValueError("Atom indices must be >= 1")

    def to_lsd_line(self) -> str:
        """Generate LSD correlation command line.

        Returns:
            String like "HSQC 1 1" or "HMBC 1 2"

        Note:
            HMBC uses 2 parameters (carbon index, proton-source atom index).
            LSD defaults to 2-3 bond distance for HMBC.
        """
        if self.correlation_type in ("HSQC", "HMQC"):
            return f"HSQC {self.atom1_index} {self.atom2_index}"
        elif self.correlation_type == "HMBC":
            # Emit extended bond range syntax when non-default range is specified
            if self.min_bonds != 2 or self.max_bonds != 3:
                return f"HMBC {self.atom1_index} {self.atom2_index} {self.min_bonds} {self.max_bonds}"
            # LSD HMBC format: just the two atom indices
            # Bond distance defaults to 2-3 in LSD
            return f"HMBC {self.atom1_index} {self.atom2_index}"
        elif self.correlation_type == "COSY":
            return f"COSY {self.atom1_index} {self.atom2_index}"
        else:
            raise ValueError(f"Unknown correlation type: {self.correlation_type}")


@dataclass
class LSDProblem:
    """Complete LSD problem definition.

    Contains all atoms, correlations, and constraints needed to generate an LSD input file.

    Attributes:
        atoms: List of atom definitions
        correlations: List of NMR correlations
        constraints: List of structural constraints (BOND/FBND)
        molecular_formula: Molecular formula string (e.g., "C13H18O2")
        name: Problem name for identification
        comments: Optional comments for the input file
    """

    atoms: list[LSDAtom] = field(default_factory=list)
    correlations: list[LSDCorrelation] = field(default_factory=list)
    constraints: list[LSDConstraint] = field(default_factory=list)
    molecular_formula: str | None = None
    name: str = "problem"
    comments: list[str] = field(default_factory=list)
    pylsd_mode: bool = False
    elim_commands: list[tuple[int, int]] = field(default_factory=list)
    elim_budget: int = 0  # Global ELIM N value (Phase 80 D-01/D-02). 0 = no ELIM. Ceiling: 3.
    ring_exclusion_enabled: bool = False

    def add_atom(self, atom: LSDAtom) -> None:
        """Add an atom to the problem."""
        self.atoms.append(atom)

    def add_correlation(self, correlation: LSDCorrelation) -> None:
        """Add a correlation to the problem."""
        self.correlations.append(correlation)

    def add_constraint(self, constraint: LSDConstraint) -> None:
        """Add a structural constraint to the problem."""
        self.constraints.append(constraint)

    def add_equivalence_pair(
        self,
        parent_index: int,
        child1_index: int,
        child2_index: int,
    ) -> None:
        """Add gem-dimethyl (or isopropyl) equivalence as BOND constraints.

        Injects two BOND entries into self.constraints so the existing BOND
        section in generate() renders them natively (D-03, Option A).

        Args:
            parent_index: Atom index of the common parent (e.g., isobutyl CH).
            child1_index: Atom index of first equivalent child (e.g., CH3 #1).
            child2_index: Atom index of second equivalent child (e.g., CH3 #2).
        """
        self.constraints.append(LSDConstraint(
            atom1_index=parent_index,
            atom2_index=child1_index,
            constraint_type="BOND",
            reason="gem_dimethyl equivalence",
        ))
        self.constraints.append(LSDConstraint(
            atom1_index=parent_index,
            atom2_index=child2_index,
            constraint_type="BOND",
            reason="gem_dimethyl equivalence",
        ))

    def add_aromatic_equivalence_pair(self, atom1_index: int, atom2_index: int) -> None:
        """Add an aromatic CH-pair equivalence as a COSY correlation.

        Injects one COSY entry into self.correlations so the existing COSY
        section in generate() renders it natively (D-03, Option A).

        Deduplicates: if a COSY for the sorted (atom1, atom2) pair already
        exists it is not added again, preventing duplicate COSY lines when
        peak-data COSY and equivalence COSY overlap.

        Args:
            atom1_index: Atom index of first aromatic CH.
            atom2_index: Atom index of second aromatic CH.
        """
        key = tuple(sorted([atom1_index, atom2_index]))
        for corr in self.correlations:
            if corr.correlation_type == "COSY":
                existing_key = tuple(sorted([corr.atom1_index, corr.atom2_index]))
                if existing_key == key:
                    return  # Already present — skip
        self.correlations.append(LSDCorrelation(
            atom1_index=atom1_index,
            atom2_index=atom2_index,
            correlation_type="COSY",
        ))

    def get_atom_by_index(self, index: int) -> LSDAtom | None:
        """Get atom by index."""
        for atom in self.atoms:
            if atom.index == index:
                return atom
        return None

    def get_correlations_for_atom(self, index: int) -> list[LSDCorrelation]:
        """Get all correlations involving an atom."""
        return [
            c for c in self.correlations
            if c.atom1_index == index or c.atom2_index == index
        ]

    def validate(self) -> list[str]:
        """Validate the problem for common issues.

        Returns:
            List of warning/error messages (empty if valid)
        """
        issues = []

        # Check for duplicate atom indices
        indices = [a.index for a in self.atoms]
        if len(indices) != len(set(indices)):
            issues.append("Duplicate atom indices found")

        # Check that correlation atoms exist
        atom_indices = set(indices)
        for corr in self.correlations:
            if corr.atom1_index not in atom_indices:
                issues.append(f"Correlation references non-existent atom {corr.atom1_index}")
            # Note: atom2 in HSQC/HMBC refers to H position, which may equal atom1

        # Check that constraint atoms exist
        for constraint in self.constraints:
            if constraint.atom1_index not in atom_indices:
                issues.append(f"Constraint references non-existent atom {constraint.atom1_index}")
            if constraint.atom2_index not in atom_indices:
                issues.append(f"Constraint references non-existent atom {constraint.atom2_index}")

        # Check for atoms without correlations
        corr_atoms = set()
        for corr in self.correlations:
            corr_atoms.add(corr.atom1_index)
        uncorrelated = atom_indices - corr_atoms
        if uncorrelated:
            issues.append(f"Atoms without correlations: {sorted(uncorrelated)}")

        return issues

    @property
    def carbon_count(self) -> int:
        """Count of carbon atoms."""
        return sum(1 for a in self.atoms if a.element == "C")

    @property
    def heteroatom_count(self) -> int:
        """Count of non-carbon heavy atoms."""
        return sum(1 for a in self.atoms if a.element != "C")

    def summary(self) -> str:
        """Return a summary of the problem."""
        lines = [
            f"LSD Problem: {self.name}",
            f"  Molecular formula: {self.molecular_formula or 'not specified'}",
            f"  Atoms: {len(self.atoms)} ({self.carbon_count} C, {self.heteroatom_count} hetero)",
            f"  Correlations: {len(self.correlations)}",
        ]

        # Count correlation types
        type_counts: dict[str, int] = {}
        for corr in self.correlations:
            type_counts[corr.correlation_type] = type_counts.get(corr.correlation_type, 0) + 1
        for ctype, count in sorted(type_counts.items()):
            lines.append(f"    {ctype}: {count}")

        # Add constraint summary
        if self.constraints:
            lines.append(f"  Constraints: {len(self.constraints)}")
            constraint_counts: dict[str, int] = {}
            for c in self.constraints:
                constraint_counts[c.constraint_type] = constraint_counts.get(c.constraint_type, 0) + 1
            for ctype, count in sorted(constraint_counts.items()):
                lines.append(f"    {ctype}: {count}")

        return "\n".join(lines)
