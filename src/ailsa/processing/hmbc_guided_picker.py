"""HMBC peak picker guided by 13C and HSQC data."""

from dataclasses import dataclass, field

from ailsa.models import Peak2D, PeakList1D, PeakList2D, Spectrum1D, Spectrum2D
from ailsa.processing.peak_picker import AdaptivePeakPicker
from ailsa.processing.peak_picker_2d import PeakPicker2D


@dataclass
class HMBCGuidedResult:
    """Result of guided HMBC peak picking.

    Attributes:
        peaks: Validated HMBC peaks (filtered to match known C and H positions)
        carbon_positions: Reference carbon positions used for filtering
        proton_positions: Reference proton positions used for filtering
        raw_peak_count: Number of peaks before filtering
        rejected_no_carbon: Peaks rejected due to no matching carbon
        rejected_no_proton: Peaks rejected due to no matching proton
        rejected_both: Peaks rejected due to neither matching
    """

    peaks: PeakList2D
    carbon_positions: list[float]
    proton_positions: list[float]
    raw_peak_count: int
    rejected_no_carbon: list[Peak2D] = field(default_factory=list)
    rejected_no_proton: list[Peak2D] = field(default_factory=list)
    rejected_both: list[Peak2D] = field(default_factory=list)

    @property
    def validated_count(self) -> int:
        """Number of validated peaks."""
        return len(self.peaks.peaks)

    @property
    def rejected_count(self) -> int:
        """Total number of rejected peaks."""
        return (
            len(self.rejected_no_carbon)
            + len(self.rejected_no_proton)
            + len(self.rejected_both)
        )

    def summary(self) -> str:
        """Return a human-readable summary of the result."""
        lines = [
            "HMBC Guided Peak Picking Result",
            f"  Reference carbons: {len(self.carbon_positions)}",
            f"  Reference protons: {len(self.proton_positions)}",
            f"  Raw HMBC peaks: {self.raw_peak_count}",
            f"  Validated peaks: {self.validated_count}",
            f"  Rejected (no C match): {len(self.rejected_no_carbon)}",
            f"  Rejected (no H match): {len(self.rejected_no_proton)}",
            f"  Rejected (no C or H): {len(self.rejected_both)}",
        ]
        return "\n".join(lines)


class HMBCGuidedPicker:
    """HMBC peak picker guided by 13C spectrum and HSQC data.

    Filters HMBC peaks to only include correlations where:
    1. The carbon (F1) position matches a known carbon from 13C or DEPT spectra
    2. The proton (F2) position matches a known proton from HSQC

    This removes noise peaks and artifacts that don't correspond to
    real carbon-proton correlations in the molecule.
    """

    @staticmethod
    def pick_hmbc_peaks(
        hmbc: Spectrum2D,
        carbon_spectrum: Spectrum1D | None = None,
        dept_peaks: PeakList1D | None = None,
        hsqc_peaks: PeakList2D | None = None,
        carbon_tolerance: float = 1.5,
        proton_tolerance: float = 0.1,
        hmbc_threshold: float = 0.05,
        carbon_threshold: float = 0.02,
        hmbc_snr_floor: float = 5.0,
        hmbc_use_snr: bool = True,
    ) -> HMBCGuidedResult:
        """Pick HMBC peaks guided by 13C and HSQC reference data.

        Args:
            hmbc: HMBC 2D spectrum
            carbon_spectrum: 13C 1D spectrum (for all carbons including quaternary)
            dept_peaks: DEPT peak list (alternative/additional carbon source)
            hsqc_peaks: HSQC 2D peak list (for valid proton positions)
            carbon_tolerance: Maximum ppm difference for carbon matching
            proton_tolerance: Maximum ppm difference for proton matching
            hmbc_threshold: Threshold for HMBC peak picking (fraction of max),
                used only when hmbc_use_snr is False (legacy path)
            carbon_threshold: Threshold for 13C peak picking if spectrum provided
            hmbc_snr_floor: SNR floor multiplier k for the SNR raw-pick path
                (default 5.0, FIX-12). Recovers weak long-range cross-peaks
                (e.g. ring-diagnostic 3J-meta correlations at ~0.6 % of max)
                that the fraction-of-max threshold drops before cross-validation.
            hmbc_use_snr: If True (default), the raw HMBC pick uses the MAD-based
                SNR floor (ignoring hmbc_threshold); if False, the legacy
                fraction-of-max threshold is used.

        Returns:
            HMBCGuidedResult with validated peaks and rejection statistics

        Raises:
            ValueError: If neither carbon_spectrum nor dept_peaks provided
            ValueError: If hsqc_peaks not provided
            ValueError: If hmbc is not an HMBC spectrum
        """
        # Validate inputs
        if hmbc.experiment_type != "HMBC":
            raise ValueError(f"Expected HMBC spectrum, got {hmbc.experiment_type}")

        if carbon_spectrum is None and dept_peaks is None:
            raise ValueError("Must provide either carbon_spectrum or dept_peaks")

        if hsqc_peaks is None:
            raise ValueError("Must provide hsqc_peaks for proton reference")

        # Collect reference carbon positions
        carbon_positions: list[float] = []

        if carbon_spectrum is not None:
            c13_peaks = AdaptivePeakPicker.pick_peaks(carbon_spectrum, threshold=carbon_threshold)
            carbon_positions.extend(p.position for p in c13_peaks.peaks)

        if dept_peaks is not None:
            # Add DEPT positions, avoiding near-duplicates
            for dept_p in dept_peaks.peaks:
                if not any(
                    abs(dept_p.position - c) <= carbon_tolerance for c in carbon_positions
                ):
                    carbon_positions.append(dept_p.position)

        # Collect reference proton positions from HSQC
        proton_positions = [p.f2_position for p in hsqc_peaks.peaks]

        # Pick raw HMBC peaks. By default (FIX-12) the raw pick routes through
        # the MAD-based SNR floor so weak long-range cross-peaks survive to the
        # cross-validation stage; the legacy fraction-of-max path is used only
        # when hmbc_use_snr is False.
        if hmbc_use_snr:
            raw_peaks = PeakPicker2D.pick_peaks(
                hmbc, snr_floor=hmbc_snr_floor, use_snr=True
            )
        else:
            raw_peaks = PeakPicker2D.pick_peaks(
                hmbc, threshold=hmbc_threshold, use_snr=False
            )

        # Filter peaks
        validated: list[Peak2D] = []
        rejected_no_carbon: list[Peak2D] = []
        rejected_no_proton: list[Peak2D] = []
        rejected_both: list[Peak2D] = []

        for peak in raw_peaks.peaks:
            c_match = any(
                abs(peak.f1_position - c) <= carbon_tolerance for c in carbon_positions
            )
            h_match = any(
                abs(peak.f2_position - h) <= proton_tolerance for h in proton_positions
            )

            if c_match and h_match:
                validated.append(peak)
            elif not c_match and not h_match:
                rejected_both.append(peak)
            elif not c_match:
                rejected_no_carbon.append(peak)
            else:
                rejected_no_proton.append(peak)

        # Create validated peak list
        validated_peaks = PeakList2D(
            peaks=validated,
            f1_nucleus=hmbc.f1_nucleus,
            f2_nucleus=hmbc.f2_nucleus,
            experiment_type=hmbc.experiment_type,
        )

        return HMBCGuidedResult(
            peaks=validated_peaks,
            carbon_positions=sorted(carbon_positions, reverse=True),
            proton_positions=sorted(set(round(p, 2) for p in proton_positions), reverse=True),
            raw_peak_count=len(raw_peaks.peaks),
            rejected_no_carbon=rejected_no_carbon,
            rejected_no_proton=rejected_no_proton,
            rejected_both=rejected_both,
        )

    @staticmethod
    def pick_hmbc_peaks_from_spectra(
        hmbc: Spectrum2D,
        carbon_spectrum: Spectrum1D,
        hsqc: Spectrum2D,
        dept135: Spectrum1D | None = None,
        carbon_tolerance: float = 1.5,
        proton_tolerance: float = 0.1,
        hmbc_threshold: float = 0.05,
        carbon_threshold: float = 0.02,
        hsqc_threshold: float = 0.05,
        hmbc_snr_floor: float = 5.0,
        hmbc_use_snr: bool = True,
    ) -> HMBCGuidedResult:
        """Convenience method that picks peaks from all input spectra.

        This is a higher-level method that handles peak picking from
        the raw spectra rather than requiring pre-picked peak lists.

        Args:
            hmbc: HMBC 2D spectrum
            carbon_spectrum: 13C 1D spectrum
            hsqc: HSQC 2D spectrum
            dept135: Optional DEPT-135 spectrum for additional carbon positions
            carbon_tolerance: Maximum ppm difference for carbon matching
            proton_tolerance: Maximum ppm difference for proton matching
            hmbc_threshold: Threshold for HMBC peak picking (legacy path only)
            carbon_threshold: Threshold for 13C peak picking
            hsqc_threshold: Threshold for HSQC peak picking
            hmbc_snr_floor: SNR floor multiplier k for the raw HMBC pick (FIX-12)
            hmbc_use_snr: If True (default), route the raw HMBC pick through the
                MAD-based SNR floor; if False, use fraction-of-max

        Returns:
            HMBCGuidedResult with validated peaks
        """
        # Pick HSQC peaks
        hsqc_peaks = PeakPicker2D.pick_peaks(hsqc, threshold=hsqc_threshold)

        # Pick DEPT peaks if provided
        dept_peaks = None
        if dept135 is not None:
            from ailsa.processing.peak_picker import AdaptivePeakPicker

            picker = AdaptivePeakPicker()
            dept_peaks = picker.pick_peaks(dept135, threshold=carbon_threshold, detect_negative=True)

        return HMBCGuidedPicker.pick_hmbc_peaks(
            hmbc=hmbc,
            carbon_spectrum=carbon_spectrum,
            dept_peaks=dept_peaks,
            hsqc_peaks=hsqc_peaks,
            carbon_tolerance=carbon_tolerance,
            proton_tolerance=proton_tolerance,
            hmbc_threshold=hmbc_threshold,
            carbon_threshold=carbon_threshold,
            hmbc_snr_floor=hmbc_snr_floor,
            hmbc_use_snr=hmbc_use_snr,
        )
