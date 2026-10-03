"""Hydrogen budget analysis for symmetry detection.

Compares molecular formula hydrogen count with observed carbon-assigned hydrogens
to detect equivalent atoms.
"""

from dataclasses import dataclass, field

from ailsa.lsd.generator import parse_molecular_formula
from ailsa.processing.dept_guided_picker import DEPTGuidedResult


@dataclass
class CarbonHInfo:
    """Information about hydrogen assignment for a single carbon signal."""

    carbon_shift: float
    multiplicity: str  # "CH", "CH2", "CH3", "C" (quaternary)
    hydrogen_count: int

    def __str__(self) -> str:
        return f"{self.carbon_shift:>7.1f} ppm: {self.multiplicity:<5} → {self.hydrogen_count:2d} H"


@dataclass
class HydrogenBudgetResult:
    """Result of hydrogen budget analysis.

    Attributes:
        molecular_formula: The molecular formula analyzed
        expected_h: Total hydrogen count from molecular formula
        carbon_assigned_h: Sum of hydrogens on observed carbon signals
        heteroatom_h: Estimated hydrogens on heteroatoms (O, N, etc.)
        total_accounted: carbon_assigned_h + heteroatom_h
        missing_h: expected_h - total_accounted (indicates equivalent atoms)
        carbon_details: Per-carbon breakdown of hydrogen assignments
        heteroatom_details: Breakdown of heteroatom hydrogen estimates
    """

    molecular_formula: str
    expected_h: int
    carbon_assigned_h: int
    heteroatom_h: int
    total_accounted: int
    missing_h: int
    carbon_details: list[CarbonHInfo] = field(default_factory=list)
    heteroatom_details: dict[str, int] = field(default_factory=dict)

    @property
    def has_equivalents(self) -> bool:
        """True if missing hydrogens suggest equivalent atoms."""
        return self.missing_h > 0

    def summary(self) -> str:
        """Generate AI-readable text summary."""
        lines = [
            "Hydrogen Budget Analysis:",
            f"  Molecular formula: {self.molecular_formula}",
            f"  Expected H (from MF): {self.expected_h}",
            "",
            "  Observed carbons with H:",
        ]

        for info in sorted(self.carbon_details, key=lambda x: -x.carbon_shift):
            lines.append(f"    {info}")

        lines.append("  " + "─" * 30)
        lines.append(f"  Carbon-assigned H:    {self.carbon_assigned_h:2d} H")

        if self.heteroatom_details:
            details = ", ".join(
                f"{count} {elem}" for elem, count in self.heteroatom_details.items()
            )
            lines.append(f"  Heteroatom H (est):   {self.heteroatom_h:2d} H  ({details})")
        else:
            lines.append(f"  Heteroatom H (est):   {self.heteroatom_h:2d} H")

        lines.append("  " + "─" * 30)
        lines.append(f"  Total accounted:      {self.total_accounted:2d} H")
        lines.append(f"  Missing H:            {self.missing_h:2d} H")

        if self.has_equivalents:
            lines.append("")
            lines.append(f"  ⚠ {self.missing_h} missing H indicates equivalent atoms")

        return "\n".join(lines)


class HydrogenBudgetAnalyzer:
    """Analyze hydrogen budget to detect molecular symmetry.

    Compares the hydrogen count from molecular formula with the sum of
    hydrogens assigned to observed carbon signals. A discrepancy indicates
    equivalent atoms (carbons that give a single NMR signal but represent
    multiple atoms in the structure).

    Example:
        >>> from ailsa import BrukerReader
        >>> from ailsa.processing import DEPTGuidedPicker
        >>> from ailsa.analysis import HydrogenBudgetAnalyzer
        >>>
        >>> hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
        >>> dept = BrukerReader.read_1d("data/Ibuprofen/3")
        >>> dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)
        >>>
        >>> result = HydrogenBudgetAnalyzer.analyze("C13H18O2", dept_result)
        >>> print(result.summary())
    """

    # Multiplicity to hydrogen count mapping
    MULT_TO_H = {
        "CH": 1,
        "CH2": 2,
        "CH3": 3,
        "CH/CH3": 2,  # Ambiguous - use average or heuristic
        "C": 0,  # Quaternary
    }

    @staticmethod
    def analyze(
        molecular_formula: str,
        dept_result: DEPTGuidedResult,
        ch_ch3_default: int = 2,
    ) -> HydrogenBudgetResult:
        """Analyze hydrogen budget from molecular formula and DEPT data.

        Args:
            molecular_formula: Molecular formula (e.g., "C13H18O2")
            dept_result: Result from DEPTGuidedPicker with carbon multiplicities
            ch_ch3_default: H count to use for ambiguous CH/CH3 (default 2)

        Returns:
            HydrogenBudgetResult with analysis details
        """
        # Parse molecular formula
        formula_counts = parse_molecular_formula(molecular_formula)
        expected_h = formula_counts.get("H", 0)

        # Count hydrogens from observed carbons
        carbon_details: list[CarbonHInfo] = []
        carbon_assigned_h = 0

        for c_shift, mult in dept_result.carbon_multiplicities.items():
            if mult == "CH/CH3":
                # Use heuristic based on chemical shift
                # < 30 ppm: likely CH3, 30-60 ppm: likely CH, > 100 ppm: aromatic CH
                if c_shift < 30:
                    h_count = 3  # Likely CH3
                elif c_shift > 100:
                    h_count = 1  # Aromatic CH
                else:
                    h_count = ch_ch3_default  # Use default
            else:
                h_count = HydrogenBudgetAnalyzer.MULT_TO_H.get(mult, 0)

            carbon_details.append(CarbonHInfo(
                carbon_shift=c_shift,
                multiplicity=mult,
                hydrogen_count=h_count,
            ))
            carbon_assigned_h += h_count

        # Estimate heteroatom hydrogens
        heteroatom_h = 0
        heteroatom_details: dict[str, int] = {}

        # Oxygen: assume each odd oxygen after first gets 1 H (hydroxyl/carboxylic)
        # This is a rough estimate - carboxylic acid has 2 O but only 1 H
        oxygen_count = formula_counts.get("O", 0)
        if oxygen_count > 0:
            # For carboxylic acid pattern (2 O), assume 1 H
            # For single O, assume 1 H (hydroxyl)
            # For more O, be conservative
            if oxygen_count <= 2:
                o_h = 1
            else:
                o_h = (oxygen_count + 1) // 2  # Rough estimate
            heteroatom_h += o_h
            heteroatom_details["O"] = o_h

        # Nitrogen: assume 1-2 H depending on count
        nitrogen_count = formula_counts.get("N", 0)
        if nitrogen_count > 0:
            n_h = nitrogen_count  # Primary amine has 2H, but varies
            heteroatom_h += n_h
            heteroatom_details["N"] = n_h

        total_accounted = carbon_assigned_h + heteroatom_h
        missing_h = expected_h - total_accounted

        return HydrogenBudgetResult(
            molecular_formula=molecular_formula,
            expected_h=expected_h,
            carbon_assigned_h=carbon_assigned_h,
            heteroatom_h=heteroatom_h,
            total_accounted=total_accounted,
            missing_h=missing_h,
            carbon_details=carbon_details,
            heteroatom_details=heteroatom_details,
        )
