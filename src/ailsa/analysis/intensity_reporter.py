"""HSQC peak intensity analysis for symmetry detection.

Reports relative peak intensities to help identify equivalent atoms
(which show ~2× intensity compared to non-equivalent signals).
"""

from dataclasses import dataclass, field

from ailsa.models import Spectrum2D
from ailsa.processing.dept_guided_picker import DEPTGuidedResult


@dataclass
class PeakIntensityInfo:
    """Intensity information for a single HSQC peak."""

    carbon_shift: float
    proton_shift: float
    absolute_intensity: float
    relative_intensity: float  # Normalized to reference
    multiplicity: str | None = None
    is_potential_equivalent: bool = False

    def __str__(self) -> str:
        mult = self.multiplicity or "?"
        flag = " [POTENTIAL 2× EQUIVALENT]" if self.is_potential_equivalent else ""
        return (
            f"{self.carbon_shift:>7.1f}  {self.proton_shift:>6.2f}  "
            f"{self.relative_intensity:>5.1f}×  {mult:<5}{flag}"
        )


@dataclass
class IntensityReport:
    """Result of HSQC intensity analysis.

    Attributes:
        peaks: List of peaks with intensity information
        reference_peak: The peak used as 1.0× reference (typically weakest)
        potential_equivalents: Carbon shifts of peaks flagged as potential equivalents
        equivalence_threshold: The threshold used for flagging
    """

    peaks: list[PeakIntensityInfo] = field(default_factory=list)
    reference_peak: PeakIntensityInfo | None = None
    potential_equivalents: list[float] = field(default_factory=list)
    equivalence_threshold: float = 1.5

    @property
    def has_potential_equivalents(self) -> bool:
        """True if any peaks are flagged as potential equivalents."""
        return len(self.potential_equivalents) > 0

    def summary(self) -> str:
        """Generate AI-readable text summary."""
        lines = [
            "HSQC Relative Intensities:",
            f"  (Normalized to weakest signal, threshold for equivalence: >{self.equivalence_threshold:.1f}×)",
            "",
            "  C shift   H shift  Rel.Int  Mult",
            "  " + "─" * 45,
        ]

        for peak in sorted(self.peaks, key=lambda x: -x.carbon_shift):
            lines.append(f"  {peak}")

        if self.potential_equivalents:
            lines.append("")
            lines.append(f"  Potential equivalents (intensity > {self.equivalence_threshold:.1f}×):")
            for c_shift in sorted(self.potential_equivalents, reverse=True):
                lines.append(f"    {c_shift:.1f} ppm")

        return "\n".join(lines)


class IntensityReporter:
    """Analyze HSQC peak intensities to identify potential equivalent atoms.

    Equivalent atoms (e.g., two equivalent aromatic CH carbons) produce
    signals with approximately twice the intensity of non-equivalent atoms.
    This class reports relative intensities and flags peaks that may
    represent equivalent positions.

    Example:
        >>> from ailsa import BrukerReader
        >>> from ailsa.processing import DEPTGuidedPicker
        >>> from ailsa.analysis import IntensityReporter
        >>>
        >>> hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
        >>> dept = BrukerReader.read_1d("data/Ibuprofen/3")
        >>> dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)
        >>>
        >>> report = IntensityReporter.report(hsqc, dept_result)
        >>> print(report.summary())
    """

    @staticmethod
    def report(
        hsqc: Spectrum2D,
        dept_result: DEPTGuidedResult,
        equivalence_threshold: float = 1.5,
        tolerance: float = 1.0,
    ) -> IntensityReport:
        """Analyze HSQC peak intensities relative to DEPT positions.

        Args:
            hsqc: HSQC 2D spectrum
            dept_result: Result from DEPTGuidedPicker with validated peaks
            equivalence_threshold: Relative intensity above which to flag
                as potential equivalent (default 1.5 = 50% stronger)
            tolerance: ppm tolerance for matching carbon positions

        Returns:
            IntensityReport with intensity analysis
        """
        # Group HSQC peaks by carbon position and sum intensities
        carbon_intensities: dict[float, dict] = {}

        for peak in dept_result.peaks.peaks:
            # Round carbon shift for grouping
            c_shift = round(peak.f1_position, 1)

            if c_shift not in carbon_intensities:
                carbon_intensities[c_shift] = {
                    "total_intensity": 0.0,
                    "h_shifts": [],
                    "count": 0,
                }

            carbon_intensities[c_shift]["total_intensity"] += peak.intensity
            carbon_intensities[c_shift]["h_shifts"].append(peak.f2_position)
            carbon_intensities[c_shift]["count"] += 1

        if not carbon_intensities:
            return IntensityReport(equivalence_threshold=equivalence_threshold)

        # Find minimum intensity for normalization
        min_intensity = min(v["total_intensity"] for v in carbon_intensities.values())
        if min_intensity <= 0:
            min_intensity = 1.0  # Avoid division by zero

        # Build peak info list
        peaks: list[PeakIntensityInfo] = []
        potential_equivalents: list[float] = []
        reference_peak: PeakIntensityInfo | None = None

        for c_shift, info in carbon_intensities.items():
            avg_h_shift = sum(info["h_shifts"]) / len(info["h_shifts"])
            rel_intensity = info["total_intensity"] / min_intensity

            # Find multiplicity from DEPT result
            mult = None
            for dept_shift, dept_mult in dept_result.carbon_multiplicities.items():
                if abs(dept_shift - c_shift) <= tolerance:
                    mult = dept_mult
                    break

            is_potential = rel_intensity > equivalence_threshold

            peak_info = PeakIntensityInfo(
                carbon_shift=c_shift,
                proton_shift=avg_h_shift,
                absolute_intensity=info["total_intensity"],
                relative_intensity=rel_intensity,
                multiplicity=mult,
                is_potential_equivalent=is_potential,
            )

            peaks.append(peak_info)

            if is_potential:
                potential_equivalents.append(c_shift)

            # Track reference (minimum intensity)
            if info["total_intensity"] == min_intensity:
                reference_peak = peak_info

        return IntensityReport(
            peaks=peaks,
            reference_peak=reference_peak,
            potential_equivalents=potential_equivalents,
            equivalence_threshold=equivalence_threshold,
        )
