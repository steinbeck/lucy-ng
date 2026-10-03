"""Validation of 2D NMR peaks against 1D reference peaks."""

from dataclasses import dataclass

from ailsa.models import Peak1D, Peak2D, PeakList1D, PeakList2D


@dataclass
class ValidationResult:
    """Result of peak list validation.

    Attributes:
        matched_peaks: List of (2D peak, matched 1D peak) tuples
        unmatched_2d_peaks: 2D peaks with no corresponding 1D peak
        unmatched_1d_peaks: 1D peaks with no corresponding 2D peak
        match_rate: Fraction of 2D peaks that matched (0.0 to 1.0)
        tolerance_used: Tolerance in ppm used for matching
    """

    matched_peaks: list[tuple[Peak2D, Peak1D]]
    unmatched_2d_peaks: list[Peak2D]
    unmatched_1d_peaks: list[Peak1D]
    match_rate: float
    tolerance_used: float

    def summary(self) -> str:
        """Return a human-readable summary of the validation."""
        total_2d = len(self.matched_peaks) + len(self.unmatched_2d_peaks)
        lines = [
            f"Validation Summary (tolerance: {self.tolerance_used} ppm)",
            f"  Total 2D peaks: {total_2d}",
            f"  Matched: {len(self.matched_peaks)} ({self.match_rate:.1%})",
            f"  Unmatched 2D: {len(self.unmatched_2d_peaks)}",
            f"  Unmatched 1D: {len(self.unmatched_1d_peaks)}",
        ]
        return "\n".join(lines)


class PeakValidator:
    """Validates 2D peaks against 1D reference peaks.

    Used to ensure 2D peak picking produces scientifically plausible results.
    For example, every HSQC peak (C-H correlation) should have a corresponding
    peak in the 1D 13C spectrum.
    """

    @staticmethod
    def validate_hsqc_against_1d(
        hsqc_peaks: PeakList2D,
        carbon_peaks: PeakList1D,
        tolerance: float = 0.5,
    ) -> ValidationResult:
        """Validate HSQC peaks against 1D 13C peaks.

        Every HSQC peak represents a direct C-H correlation. Therefore,
        the F1 (13C) position of each HSQC peak should correspond to a
        peak in the 1D 13C spectrum.

        Args:
            hsqc_peaks: HSQC peak list (experiment_type should be "HSQC")
            carbon_peaks: 1D 13C peak list (nucleus should be "13C")
            tolerance: Maximum ppm difference for a match

        Returns:
            ValidationResult with matched/unmatched peaks and statistics

        Raises:
            ValueError: If peak lists have wrong nuclei/experiment type
        """
        # Validate input types
        if hsqc_peaks.experiment_type != "HSQC":
            raise ValueError(
                f"Expected HSQC peaks, got {hsqc_peaks.experiment_type}"
            )
        if carbon_peaks.nucleus != "13C":
            raise ValueError(
                f"Expected 13C peaks, got {carbon_peaks.nucleus}"
            )

        return PeakValidator._validate_f1_against_1d(
            hsqc_peaks, carbon_peaks, tolerance
        )

    @staticmethod
    def validate_cosy_against_1d(
        cosy_peaks: PeakList2D,
        proton_peaks: PeakList1D,
        tolerance: float = 0.05,
    ) -> ValidationResult:
        """Validate COSY peaks against 1D 1H peaks.

        COSY is a homonuclear experiment (1H-1H). Both F1 and F2
        positions should correspond to peaks in the 1D 1H spectrum.

        A COSY peak is considered valid only if BOTH dimensions match.

        Args:
            cosy_peaks: COSY peak list
            proton_peaks: 1D 1H peak list
            tolerance: Maximum ppm difference for a match

        Returns:
            ValidationResult with matched/unmatched peaks

        Raises:
            ValueError: If peak lists have wrong nuclei/experiment type
        """
        if cosy_peaks.experiment_type != "COSY":
            raise ValueError(
                f"Expected COSY peaks, got {cosy_peaks.experiment_type}"
            )
        if proton_peaks.nucleus != "1H":
            raise ValueError(
                f"Expected 1H peaks, got {proton_peaks.nucleus}"
            )

        proton_positions = [p.position for p in proton_peaks.peaks]
        matched: list[tuple[Peak2D, Peak1D]] = []
        unmatched_2d: list[Peak2D] = []
        used_1d_indices: set[int] = set()

        for peak_2d in cosy_peaks.peaks:
            # Find match for F1
            f1_match_idx = PeakValidator._find_nearest_within_tolerance(
                peak_2d.f1_position, proton_positions, tolerance
            )
            # Find match for F2
            f2_match_idx = PeakValidator._find_nearest_within_tolerance(
                peak_2d.f2_position, proton_positions, tolerance
            )

            # Both dimensions must match for COSY
            if f1_match_idx is not None and f2_match_idx is not None:
                # Use the F1 match as the "reference" peak for the tuple
                matched.append((peak_2d, proton_peaks.peaks[f1_match_idx]))
                used_1d_indices.add(f1_match_idx)
                used_1d_indices.add(f2_match_idx)
            else:
                unmatched_2d.append(peak_2d)

        # Find unmatched 1D peaks
        unmatched_1d = [
            p for i, p in enumerate(proton_peaks.peaks)
            if i not in used_1d_indices
        ]

        total_2d = len(cosy_peaks.peaks)
        match_rate = len(matched) / total_2d if total_2d > 0 else 0.0

        return ValidationResult(
            matched_peaks=matched,
            unmatched_2d_peaks=unmatched_2d,
            unmatched_1d_peaks=unmatched_1d,
            match_rate=match_rate,
            tolerance_used=tolerance,
        )

    @staticmethod
    def validate_generic_f1(
        peaks_2d: PeakList2D,
        peaks_1d: PeakList1D,
        tolerance: float = 0.5,
    ) -> ValidationResult:
        """Validate 2D peaks F1 dimension against 1D peaks.

        Generic validation that checks if F1 positions of 2D peaks
        correspond to 1D peak positions. Works for any heteronuclear
        experiment (HSQC, HMBC, etc.).

        Args:
            peaks_2d: 2D peak list
            peaks_1d: 1D peak list for F1 nucleus
            tolerance: Maximum ppm difference for a match

        Returns:
            ValidationResult with matched/unmatched peaks
        """
        return PeakValidator._validate_f1_against_1d(
            peaks_2d, peaks_1d, tolerance
        )

    @staticmethod
    def filter_validated_peaks(
        peaks_2d: PeakList2D,
        peaks_1d: PeakList1D,
        tolerance: float = 0.5,
    ) -> PeakList2D:
        """Return only 2D peaks that have corresponding 1D peaks.

        Useful for removing likely artifacts from a peak list.

        Args:
            peaks_2d: 2D peak list to filter
            peaks_1d: 1D reference peak list
            tolerance: Maximum ppm difference for a match

        Returns:
            New PeakList2D containing only validated peaks
        """
        result = PeakValidator._validate_f1_against_1d(
            peaks_2d, peaks_1d, tolerance
        )

        validated_peaks = [peak_2d for peak_2d, _ in result.matched_peaks]

        return PeakList2D(
            peaks=validated_peaks,
            f1_nucleus=peaks_2d.f1_nucleus,
            f2_nucleus=peaks_2d.f2_nucleus,
            experiment_type=peaks_2d.experiment_type,
            spectrum_id=peaks_2d.spectrum_id,
        )

    @staticmethod
    def _validate_f1_against_1d(
        peaks_2d: PeakList2D,
        peaks_1d: PeakList1D,
        tolerance: float,
    ) -> ValidationResult:
        """Internal method to validate F1 positions against 1D peaks."""
        positions_1d = [p.position for p in peaks_1d.peaks]
        matched: list[tuple[Peak2D, Peak1D]] = []
        unmatched_2d: list[Peak2D] = []
        used_1d_indices: set[int] = set()

        for peak_2d in peaks_2d.peaks:
            match_idx = PeakValidator._find_nearest_within_tolerance(
                peak_2d.f1_position, positions_1d, tolerance
            )

            if match_idx is not None:
                matched.append((peak_2d, peaks_1d.peaks[match_idx]))
                used_1d_indices.add(match_idx)
            else:
                unmatched_2d.append(peak_2d)

        # Find unmatched 1D peaks
        unmatched_1d = [
            p for i, p in enumerate(peaks_1d.peaks)
            if i not in used_1d_indices
        ]

        total_2d = len(peaks_2d.peaks)
        match_rate = len(matched) / total_2d if total_2d > 0 else 0.0

        return ValidationResult(
            matched_peaks=matched,
            unmatched_2d_peaks=unmatched_2d,
            unmatched_1d_peaks=unmatched_1d,
            match_rate=match_rate,
            tolerance_used=tolerance,
        )

    @staticmethod
    def _find_nearest_within_tolerance(
        target: float,
        positions: list[float],
        tolerance: float,
    ) -> int | None:
        """Find index of nearest position within tolerance.

        Args:
            target: Target ppm value
            positions: List of ppm positions to search
            tolerance: Maximum allowed difference

        Returns:
            Index of nearest position within tolerance, or None if no match
        """
        if not positions:
            return None

        best_idx = None
        best_delta = float("inf")

        for i, pos in enumerate(positions):
            delta = abs(target - pos)
            if delta <= tolerance and delta < best_delta:
                best_idx = i
                best_delta = delta

        return best_idx
