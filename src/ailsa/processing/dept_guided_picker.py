"""DEPT-guided adaptive HSQC peak picker."""

from dataclasses import dataclass, field

from ailsa.models import Peak1D, PeakList1D, PeakList2D, Spectrum1D, Spectrum2D
from ailsa.processing.peak_picker import AdaptivePeakPicker
from ailsa.processing.peak_picker_2d import PeakPicker2D
from ailsa.processing.peak_validator import PeakValidator


@dataclass
class DEPTGuidedResult:
    """Result of DEPT-guided HSQC peak picking.

    Attributes:
        peaks: Validated HSQC peaks (filtered to match DEPT carbons)
        dept_peaks: DEPT-135 reference peaks used as ground truth
        threshold_used: Final HSQC threshold that found all carbons
        iterations: Number of threshold adjustments made
        all_carbons_found: Whether all DEPT carbons were matched in HSQC
        unmatched_dept_peaks: DEPT peaks not found in HSQC (if any)
        carbon_multiplicities: Map of ppm -> multiplicity ("CH", "CH2", "CH3", or "CH/CH3")
    """

    peaks: PeakList2D
    dept_peaks: PeakList1D
    threshold_used: float
    iterations: int
    all_carbons_found: bool
    unmatched_dept_peaks: list[Peak1D] = field(default_factory=list)
    carbon_multiplicities: dict[float, str] = field(default_factory=dict)

    def summary(self) -> str:
        """Return a human-readable summary of the result."""
        lines = [
            "DEPT-Guided HSQC Peak Picking Result",
            f"  DEPT peaks (ground truth): {len(self.dept_peaks.peaks)}",
            f"  Validated HSQC peaks: {len(self.peaks.peaks)}",
            f"  Threshold used: {self.threshold_used:.4f}",
            f"  Iterations: {self.iterations}",
            f"  All carbons found: {self.all_carbons_found}",
        ]
        if self.unmatched_dept_peaks:
            lines.append(f"  Unmatched DEPT peaks: {len(self.unmatched_dept_peaks)}")
            for p in self.unmatched_dept_peaks:
                lines.append(f"    - {p.position:.2f} ppm")
        if self.carbon_multiplicities:
            lines.append("  Carbon multiplicities:")
            for ppm in sorted(self.carbon_multiplicities.keys(), reverse=True):
                mult = self.carbon_multiplicities[ppm]
                lines.append(f"    {ppm:7.2f} ppm: {mult}")
        return "\n".join(lines)


class DEPTGuidedPicker:
    """DEPT-guided adaptive HSQC peak picker.

    Uses DEPT-135 peaks as ground truth to adaptively tune HSQC
    peak picking threshold until all protonated carbons are found.

    This ensures that:
    1. All protonated carbons (visible in DEPT) are found in HSQC
    2. Noise peaks are filtered out by requiring DEPT correspondence
    3. Multiplicity information is extracted from DEPT signal sign
    """

    @staticmethod
    def pick_hsqc_peaks(
        hsqc: Spectrum2D,
        dept135: Spectrum1D,
        dept_threshold: float = 0.02,
        initial_hsqc_threshold: float = 0.10,
        min_hsqc_threshold: float = 0.005,
        tolerance: float = 1.0,
        threshold_step: float = 0.5,
        detect_negative_dept: bool = True,
    ) -> DEPTGuidedResult:
        """Pick HSQC peaks guided by DEPT-135 ground truth.

        Algorithm:
        1. Pick DEPT-135 peaks to get ground truth protonated carbons
        2. Start with high HSQC threshold
        3. Lower threshold iteratively until all DEPT carbons matched
        4. Filter HSQC peaks to only those matching DEPT positions
        5. Extract multiplicity from DEPT peak signs
        6. Return validated, noise-free peak list

        Args:
            hsqc: HSQC 2D spectrum
            dept135: DEPT-135 1D spectrum (ground truth for protonated carbons)
            dept_threshold: Threshold for DEPT peak picking (fraction of max)
            initial_hsqc_threshold: Starting HSQC threshold (fraction of max)
            min_hsqc_threshold: Minimum HSQC threshold to try
            tolerance: Maximum ppm difference for carbon matching
            threshold_step: Multiplicative factor for threshold reduction
            detect_negative_dept: If True, detect negative CH2 peaks in DEPT

        Returns:
            DEPTGuidedResult with validated peaks and metadata
        """
        # Validate input
        if hsqc.experiment_type != "HSQC":
            raise ValueError(f"Expected HSQC spectrum, got {hsqc.experiment_type}")
        if dept135.nucleus != "13C":
            raise ValueError(f"Expected 13C DEPT spectrum, got {dept135.nucleus}")

        # Step 1: Pick DEPT-135 peaks (ground truth)
        dept_peaks = DEPTGuidedPicker._pick_dept_peaks(
            dept135, dept_threshold, detect_negative_dept
        )

        # Handle empty DEPT case
        if len(dept_peaks.peaks) == 0:
            return DEPTGuidedResult(
                peaks=PeakList2D(
                    peaks=[],
                    f1_nucleus=hsqc.f1_nucleus,
                    f2_nucleus=hsqc.f2_nucleus,
                    experiment_type=hsqc.experiment_type,
                ),
                dept_peaks=dept_peaks,
                threshold_used=initial_hsqc_threshold,
                iterations=0,
                all_carbons_found=True,
                unmatched_dept_peaks=[],
                carbon_multiplicities={},
            )

        dept_positions = [p.position for p in dept_peaks.peaks]

        # Step 2: Iteratively lower HSQC threshold until all DEPT carbons matched
        threshold = initial_hsqc_threshold
        iterations = 0
        hsqc_peaks = None
        unmatched_positions: list[float] = dept_positions.copy()

        while threshold >= min_hsqc_threshold:
            iterations += 1

            # Pick HSQC peaks at current threshold
            hsqc_peaks = PeakPicker2D.pick_peaks(hsqc, threshold=threshold)
            hsqc_carbons = set(p.f1_position for p in hsqc_peaks.peaks)

            # Check which DEPT carbons are matched
            unmatched_positions = []
            for dept_ppm in dept_positions:
                if not any(abs(c - dept_ppm) <= tolerance for c in hsqc_carbons):
                    unmatched_positions.append(dept_ppm)

            if len(unmatched_positions) == 0:
                break  # All carbons found

            threshold *= threshold_step  # Lower threshold

        # Ensure we have hsqc_peaks (in case loop didn't execute)
        if hsqc_peaks is None:
            hsqc_peaks = PeakPicker2D.pick_peaks(hsqc, threshold=initial_hsqc_threshold)

        # Step 3: Filter HSQC peaks to only validated ones
        validated_peaks = PeakValidator.filter_validated_peaks(
            hsqc_peaks, dept_peaks, tolerance=tolerance
        )

        # Step 4: Extract multiplicity from DEPT peak signs
        carbon_multiplicities = DEPTGuidedPicker._extract_multiplicities(dept_peaks)

        # Find unmatched DEPT peaks
        unmatched_dept = [
            p for p in dept_peaks.peaks if p.position in unmatched_positions
        ]

        return DEPTGuidedResult(
            peaks=validated_peaks,
            dept_peaks=dept_peaks,
            threshold_used=threshold if iterations > 0 else initial_hsqc_threshold,
            iterations=iterations,
            all_carbons_found=len(unmatched_positions) == 0,
            unmatched_dept_peaks=unmatched_dept,
            carbon_multiplicities=carbon_multiplicities,
        )

    @staticmethod
    def pick_hsqc_peaks_with_dept90(
        hsqc: Spectrum2D,
        dept135: Spectrum1D,
        dept90: Spectrum1D,
        dept_threshold: float = 0.02,
        initial_hsqc_threshold: float = 0.10,
        min_hsqc_threshold: float = 0.005,
        tolerance: float = 1.0,
        threshold_step: float = 0.5,
    ) -> DEPTGuidedResult:
        """Pick HSQC peaks with DEPT-90 for CH/CH3 distinction.

        Uses both DEPT-135 and DEPT-90 to distinguish:
        - CH: positive in both DEPT-135 and DEPT-90
        - CH2: negative in DEPT-135, absent in DEPT-90
        - CH3: positive in DEPT-135, absent in DEPT-90

        Args:
            hsqc: HSQC 2D spectrum
            dept135: DEPT-135 1D spectrum
            dept90: DEPT-90 1D spectrum
            dept_threshold: Threshold for DEPT peak picking
            initial_hsqc_threshold: Starting HSQC threshold
            min_hsqc_threshold: Minimum HSQC threshold
            tolerance: Maximum ppm difference for matching
            threshold_step: Threshold reduction factor

        Returns:
            DEPTGuidedResult with refined multiplicity information
        """
        # First, get basic result using DEPT-135
        result = DEPTGuidedPicker.pick_hsqc_peaks(
            hsqc=hsqc,
            dept135=dept135,
            dept_threshold=dept_threshold,
            initial_hsqc_threshold=initial_hsqc_threshold,
            min_hsqc_threshold=min_hsqc_threshold,
            tolerance=tolerance,
            threshold_step=threshold_step,
        )

        # Pick DEPT-90 peaks (only CH visible) — use explicit threshold, not SNR mode
        dept90_peaks = AdaptivePeakPicker.pick_peaks(dept90, threshold=dept_threshold, use_snr=False)
        dept90_positions = set(p.position for p in dept90_peaks.peaks)

        # Refine multiplicities using DEPT-90
        refined_multiplicities = {}
        for ppm, mult in result.carbon_multiplicities.items():
            if mult == "CH/CH3":
                # Check if present in DEPT-90
                if any(abs(ppm - d90) <= tolerance for d90 in dept90_positions):
                    refined_multiplicities[ppm] = "CH"
                else:
                    refined_multiplicities[ppm] = "CH3"
            else:
                refined_multiplicities[ppm] = mult

        # Return updated result
        return DEPTGuidedResult(
            peaks=result.peaks,
            dept_peaks=result.dept_peaks,
            threshold_used=result.threshold_used,
            iterations=result.iterations,
            all_carbons_found=result.all_carbons_found,
            unmatched_dept_peaks=result.unmatched_dept_peaks,
            carbon_multiplicities=refined_multiplicities,
        )

    @staticmethod
    def _pick_dept_peaks(
        dept: Spectrum1D,
        threshold: float,
        detect_negative: bool,
    ) -> PeakList1D:
        """Pick peaks from DEPT spectrum including negative peaks.

        Args:
            dept: DEPT-135 spectrum
            threshold: Intensity threshold as fraction of max
            detect_negative: If True, also detect negative (CH2) peaks

        Returns:
            PeakList1D with both positive and negative peaks
        """
        from ailsa.processing.peak_picker import AdaptivePeakPicker

        # Use AdaptivePeakPicker which supports negative peak detection.
        # use_snr=False: DEPT picking uses explicit fraction-of-max threshold, not SNR mode.
        picker = AdaptivePeakPicker()
        return picker.pick_peaks(dept, threshold=threshold, detect_negative=detect_negative, use_snr=False)

    @staticmethod
    def _extract_multiplicities(dept_peaks: PeakList1D) -> dict[float, str]:
        """Extract carbon multiplicities from DEPT-135 peak signs.

        Args:
            dept_peaks: DEPT-135 peak list

        Returns:
            Dictionary mapping ppm -> multiplicity string
        """
        multiplicities = {}
        for peak in dept_peaks.peaks:
            if peak.intensity > 0:
                multiplicities[peak.position] = "CH/CH3"  # Positive = CH or CH3
            else:
                multiplicities[peak.position] = "CH2"  # Negative = CH2
        return multiplicities
