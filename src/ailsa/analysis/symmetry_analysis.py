"""Combined symmetry analysis for AI-driven structure elucidation.

Combines hydrogen budget analysis and intensity reporting into a single
AI-readable summary for reasoning about molecular symmetry.
"""

from dataclasses import dataclass

from ailsa.lsd.generator import parse_molecular_formula
from ailsa.models import Spectrum2D
from ailsa.processing.dept_guided_picker import DEPTGuidedResult

from ailsa.analysis.hydrogen_budget import HydrogenBudgetAnalyzer, HydrogenBudgetResult
from ailsa.analysis.intensity_reporter import IntensityReporter, IntensityReport


@dataclass
class SymmetryAnalysisResult:
    """Combined result of symmetry analysis.

    Attributes:
        molecular_formula: The molecular formula analyzed
        hydrogen_budget: Result from hydrogen budget analysis
        intensity_report: Result from intensity analysis
        signal_count: Number of observed carbon signals
        expected_carbons: Number of carbons from molecular formula
        missing_carbons: Difference (indicates equivalent atoms)
    """

    molecular_formula: str
    hydrogen_budget: HydrogenBudgetResult
    intensity_report: IntensityReport
    signal_count: int
    expected_carbons: int
    missing_carbons: int

    @property
    def has_symmetry(self) -> bool:
        """True if analysis suggests molecular symmetry."""
        return self.missing_carbons > 0 or self.hydrogen_budget.has_equivalents

    def summary(self) -> str:
        """Generate combined AI-readable summary for symmetry reasoning."""
        lines = [
            f"Symmetry Analysis for {self.molecular_formula}",
            "=" * 50,
            "",
            "SIGNAL COUNT:",
            f"  Observed carbon signals: {self.signal_count}",
            f"  Expected from formula:   {self.expected_carbons}",
            f"  Missing carbons:         {self.missing_carbons}",
        ]

        if self.missing_carbons < 0:
            lines.append(
                f"  OVERCOUNT ALARM: {-self.missing_carbons} more signals than carbons"
                " — likely noise peaks in the spectrum. Re-pick at snr_floor >= 5 before"
                " any symmetry or DBE reasoning."
            )
        elif self.missing_carbons > 0:
            lines.append(f"  → {self.missing_carbons} carbons must be equivalent to observed signals")

        lines.append("")
        lines.append("HYDROGEN BUDGET:")
        lines.append(f"  Expected H (from MF):  {self.hydrogen_budget.expected_h}")
        lines.append(f"  Accounted H:           {self.hydrogen_budget.total_accounted}")
        lines.append(f"  Missing H:             {self.hydrogen_budget.missing_h}")

        if self.hydrogen_budget.has_equivalents:
            # Estimate number of equivalent pairs
            # Missing 6 H could be 3 pairs of CH (1H each) or 1 pair of CH3 (3H each) + other
            lines.append(f"  → {self.hydrogen_budget.missing_h} missing H indicates equivalent protonated carbons")

        lines.append("")
        lines.append("INTENSITY EVIDENCE:")

        if self.intensity_report.has_potential_equivalents:
            lines.append("  High intensity signals (potential 2× equivalents):")
            for peak in self.intensity_report.peaks:
                if peak.is_potential_equivalent:
                    region = self._classify_region(peak.carbon_shift)
                    lines.append(
                        f"    - {peak.carbon_shift:.1f} ppm "
                        f"({peak.multiplicity or '?'}, {peak.relative_intensity:.1f}×) "
                        f"- {region}"
                    )
        else:
            lines.append("  No signals with significantly elevated intensity")

        # Add interpretation hints
        lines.append("")
        lines.append("INTERPRETATION HINTS:")

        if self.missing_carbons > 0:
            lines.append(f"  - {self.missing_carbons} carbons are equivalent to observed signals")

            # Check for aromatic pattern
            aromatic_equivalents = [
                p for p in self.intensity_report.peaks
                if p.is_potential_equivalent and 100 <= p.carbon_shift <= 160
            ]
            if len(aromatic_equivalents) == 2:
                lines.append("  - 2 aromatic CH with high intensity → likely para-disubstituted benzene")

            # Check for aliphatic CH3 equivalents
            ch3_equivalents = [
                p for p in self.intensity_report.peaks
                if p.is_potential_equivalent
                and p.multiplicity in ("CH3", "CH/CH3")
                and p.carbon_shift < 40
            ]
            if ch3_equivalents:
                lines.append("  - High intensity CH3 in aliphatic region → likely equivalent methyls (isopropyl, tert-butyl)")

        if not self.has_symmetry:
            lines.append("  - No clear evidence of molecular symmetry")

        return "\n".join(lines)

    @staticmethod
    def _classify_region(shift: float) -> str:
        """Classify chemical shift region."""
        if shift > 160:
            return "carbonyl/heteroaromatic"
        elif shift >= 100:
            return "aromatic"
        elif shift >= 50:
            return "oxygenated aliphatic"
        elif shift >= 25:
            return "aliphatic CH/CH2"
        else:
            return "aliphatic CH3"


class SymmetryAnalyzer:
    """Analyze molecular symmetry from spectroscopic data.

    Combines hydrogen budget analysis and HSQC intensity analysis to
    provide a comprehensive summary for AI-driven symmetry reasoning.

    The AI uses this summary to:
    1. Determine if equivalent atoms exist
    2. Identify which signals likely represent equivalent positions
    3. Generate appropriate LSD input with correct atom counts

    Example:
        >>> from ailsa import BrukerReader
        >>> from ailsa.processing import DEPTGuidedPicker
        >>> from ailsa.analysis import SymmetryAnalyzer
        >>>
        >>> hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
        >>> dept = BrukerReader.read_1d("data/Ibuprofen/3")
        >>> dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)
        >>>
        >>> result = SymmetryAnalyzer.analyze("C13H18O2", dept_result, hsqc)
        >>> print(result.summary())
    """

    @staticmethod
    def analyze(
        molecular_formula: str,
        dept_result: DEPTGuidedResult,
        hsqc: Spectrum2D,
        equivalence_threshold: float = 1.5,
    ) -> SymmetryAnalysisResult:
        """Perform combined symmetry analysis.

        Args:
            molecular_formula: Molecular formula (e.g., "C13H18O2")
            dept_result: Result from DEPTGuidedPicker
            hsqc: HSQC 2D spectrum
            equivalence_threshold: Intensity threshold for flagging equivalents

        Returns:
            SymmetryAnalysisResult with combined analysis
        """
        # Parse formula for carbon count
        formula_counts = parse_molecular_formula(molecular_formula)
        expected_carbons = formula_counts.get("C", 0)

        # Count observed signals
        signal_count = len(dept_result.carbon_multiplicities)

        # Run hydrogen budget analysis
        hydrogen_budget = HydrogenBudgetAnalyzer.analyze(molecular_formula, dept_result)

        # Run intensity analysis
        intensity_report = IntensityReporter.report(
            hsqc, dept_result, equivalence_threshold=equivalence_threshold
        )

        return SymmetryAnalysisResult(
            molecular_formula=molecular_formula,
            hydrogen_budget=hydrogen_budget,
            intensity_report=intensity_report,
            signal_count=signal_count,
            expected_carbons=expected_carbons,
            missing_carbons=expected_carbons - signal_count,
        )
