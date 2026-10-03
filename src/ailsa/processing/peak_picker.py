"""Peak picking for 1D NMR spectra."""

import numpy as np
from scipy.signal import find_peaks, peak_widths

from ailsa.models import Peak1D, PeakList1D, Spectrum1D

# Solvent residual 13C shifts: exclusion windows (low_ppm, high_ppm).
# Each window is centred on the residual shift with ±5 ppm margin for multiplets.
# Values are lists of (lo, hi) tuples to support solvents with multiple signals.
_SOLVENT_EXCLUSION_13C: dict[str, list[tuple[float, float]]] = {
    "CDCl3":   [(72.0, 82.0)],                       # 77.16 ppm triplet
    "DMSO":    [(37.0, 42.0)],                        # 39.52 ppm septet
    "DMSO-d6": [(37.0, 42.0)],
    "CD3OD":   [(46.0, 52.0)],                        # 49.0 ppm septet
    "MeOD":    [(46.0, 52.0)],
    "CD3CN":   [(1.0, 5.0), (114.0, 120.0)],          # 1.32 ppm CD3 septet + 117.1 ppm CN singlet
    "acetone": [(27.0, 33.0)],                        # 29.84 ppm
    "C6D6":    [(125.0, 131.0)],                      # 128.06 ppm triplet
}


def _compute_snr_threshold(
    data: np.ndarray,
    ppm_scale: np.ndarray,
    solvent: str | None = None,
    k: float = 3.0,
) -> tuple[float, float]:
    """Compute SNR-based absolute threshold using MAD noise estimate.

    Args:
        data: Spectrum intensity array.
        ppm_scale: Corresponding ppm axis.
        solvent: Bruker SOLVENT string (e.g. "CDCl3"). If None or not in table,
                 MAD is computed over the full array (still robust for 13C).
        k: SNR floor multiplier. IUPAC LoD convention: k=3.

    Returns:
        (abs_threshold, sigma_mad) — threshold = k * sigma_mad.
        Both values are always finite (fallback to 5%-of-max if MAD is zero or
        solvent exclusion empties the noise region).
    """
    windows = _SOLVENT_EXCLUSION_13C.get(solvent or "", None)
    if windows is not None:
        # Build a combined exclusion mask across all solvent windows.
        mask = np.zeros(len(ppm_scale), dtype=bool)
        for lo, hi in windows:
            mask |= (ppm_scale >= lo) & (ppm_scale <= hi)
        clean_data = data[~mask]
        # Fall back to full spectrum if exclusion removed all points.
        if len(clean_data) == 0:
            clean_data = data
    else:
        clean_data = data

    mad = float(np.median(np.abs(clean_data - np.median(clean_data))))
    sigma_mad = 1.4826 * mad

    # Guard against zero/NaN sigma (constant or empty baseline).
    # Fall back to 5% of max so the function always returns a usable threshold.
    if not np.isfinite(sigma_mad) or sigma_mad == 0.0:
        fallback = 0.05 * float(np.max(np.abs(data))) if data.size > 0 else 1.0
        return fallback, fallback / k

    return k * sigma_mad, sigma_mad


def detect_intensity_symmetry(
    peaks: list[Peak1D],
    aromatic_ch_ppms: list[float],
    tolerance_ppm: float = 1.0,
    min_ratio: float = 1.6,
) -> list[tuple[float, float, int]]:
    """Detect intensity-doubled aromatic CH peaks as 2C-equivalence candidates.

    Compares each HSQC-confirmed aromatic CH peak against the median intensity
    of ALL peaks in the aromatic region (100-165 ppm). A 2C-equivalent peak
    (two equivalent carbons contributing to one signal) will have ~2× the
    intensity of a 1C aromatic signal, and thus will exceed the min_ratio
    threshold when the class median is dominated by 1C signals (Cq, mono-CH).

    Scope restriction (D-06): results are restricted to HSQC-confirmed aromatic
    CH carbons; the comparison median uses all 100-165 ppm peaks.

    Args:
        peaks: List of 1D peaks (from 13C spectrum).
        aromatic_ch_ppms: HSQC-confirmed aromatic CH ppm positions.
        tolerance_ppm: Match window for pairing 13C peaks to HSQC references.
        min_ratio: Minimum intensity ratio vs class median to flag as 2C candidate.

    Returns:
        List of (ppm, intensity_ratio_to_class_median, estimated_carbon_count).
    """
    if not aromatic_ch_ppms:
        return []

    # Median is computed over ALL peaks in the aromatic region (100-165 ppm).
    # This includes Cq signals which serve as the 1C baseline for comparison.
    all_aromatic = [p for p in peaks if 100.0 <= p.position <= 165.0]
    if len(all_aromatic) < 2:
        return []

    median_intensity = float(np.median([p.intensity for p in all_aromatic]))
    if median_intensity <= 0:
        return []

    # Flag HSQC-confirmed CH peaks that exceed the ratio threshold.
    # Use reference-driven matching: for each reference, find the closest peak.
    results: list[tuple[float, float, int]] = []
    seen_peaks: set[int] = set()
    for ref in aromatic_ch_ppms:
        candidates = [
            p for p in all_aromatic
            if abs(p.position - ref) < tolerance_ppm
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda p: abs(p.position - ref))
        if id(best) in seen_peaks:
            continue
        seen_peaks.add(id(best))
        ratio = best.intensity / median_intensity
        if ratio >= min_ratio:
            results.append((best.position, ratio, round(ratio)))

    return results


class AdaptivePeakPicker:
    """Adaptive peak picker that adjusts minimum distance based on line width.

    Uses a two-pass approach:
    1. First pass: Find prominent peaks with loose criteria
    2. Measure FWHM (Full Width at Half Maximum) for each peak
    3. Calculate adaptive min_distance based on median FWHM
    4. Second pass: Re-pick with adaptive distance

    This allows detecting closely-spaced peaks in high-resolution spectra
    while avoiding noise in broader regions.
    """

    # Default instance for static method
    _default_instance: "AdaptivePeakPicker | None" = None

    def __init__(self, fwhm_factor: float = 1.5, fallback_min_distance_ppm: float = 0.1):
        """Initialize adaptive peak picker.

        Args:
            fwhm_factor: Multiplier for median FWHM to get min_distance.
                        Default 1.5 means peaks must be ~1.5 line widths apart.
            fallback_min_distance_ppm: Minimum distance to use if FWHM
                        estimation fails. Default 0.1 ppm.
        """
        self.fwhm_factor = fwhm_factor
        self.fallback_min_distance_ppm = fallback_min_distance_ppm

    @staticmethod
    def pick_peaks(
        spectrum: Spectrum1D,
        threshold: float = 0.05,
        detect_negative: bool = False,
        snr_floor: float = 5.0,
        use_snr: bool = True,
    ) -> PeakList1D:
        """Pick peaks with adaptive minimum distance based on line width.

        Static convenience method that uses default parameters.
        For custom fwhm_factor or fallback_min_distance_ppm, create an
        instance and call pick_peaks_instance() instead.

        Args:
            spectrum: 1D NMR spectrum with data and ppm_scale
            threshold: Minimum intensity as fraction of max (0-1); used only
                       when use_snr=False (backwards-compat mode)
            detect_negative: If True, also detect negative peaks (for DEPT)
            snr_floor: SNR floor multiplier k (k=5 signal/noise separation;
                       use k=3 for exploratory re-pick). Used when
                       use_snr=True (default).
            use_snr: If True (default), use MAD/SNR absolute threshold.
                     If False, fall back to threshold * max behaviour.

        Returns:
            PeakList1D containing detected peaks (with snr annotation when
            use_snr=True)
        """
        # Lazily create default instance
        if AdaptivePeakPicker._default_instance is None:
            AdaptivePeakPicker._default_instance = AdaptivePeakPicker()

        return AdaptivePeakPicker._default_instance.pick_peaks_instance(
            spectrum, threshold, detect_negative, snr_floor, use_snr
        )

    def pick_peaks_instance(
        self,
        spectrum: Spectrum1D,
        threshold: float = 0.05,
        detect_negative: bool = False,
        snr_floor: float = 5.0,
        use_snr: bool = True,
    ) -> PeakList1D:
        """Pick peaks with adaptive minimum distance based on line width.

        Instance method that uses instance's fwhm_factor and fallback settings.

        Args:
            spectrum: 1D NMR spectrum with data and ppm_scale
            threshold: Minimum intensity as fraction of max (0-1); used only
                       when use_snr=False (backwards-compat mode)
            detect_negative: If True, also detect negative peaks (for DEPT)
            snr_floor: SNR floor multiplier k (k=5 signal/noise separation;
                       use k=3 for exploratory re-pick). Used when
                       use_snr=True (default).
            use_snr: If True (default), use MAD/SNR absolute threshold.
                     If False, fall back to threshold * max behaviour.

        Returns:
            PeakList1D containing detected peaks (with snr annotation when
            use_snr=True)
        """
        data = spectrum.data
        ppm_scale = spectrum.ppm_scale
        ppm_per_point = abs(ppm_scale[1] - ppm_scale[0]) if len(ppm_scale) > 1 else 1.0

        # Compute threshold in absolute units
        if use_snr:
            abs_threshold, sigma_mad = _compute_snr_threshold(
                data, ppm_scale, solvent=spectrum.solvent, k=snr_floor
            )
        else:
            abs_threshold = threshold * np.max(np.abs(data))
            sigma_mad = None

        # Estimate adaptive minimum distance from line widths
        min_distance_ppm = self._estimate_min_distance(
            data, ppm_per_point, abs_threshold
        )
        min_distance_points = max(1, int(min_distance_ppm / ppm_per_point))

        # Find positive peaks
        peak_indices, _ = find_peaks(
            data,
            height=abs_threshold,
            distance=min_distance_points,
        )

        peaks = []
        for idx in peak_indices:
            snr = float(abs(data[idx]) / sigma_mad) if sigma_mad is not None else None
            peaks.append(Peak1D(
                position=float(ppm_scale[idx]),
                intensity=float(data[idx]),
                snr=snr,
            ))

        # Find negative peaks if requested (for DEPT spectra)
        if detect_negative:
            neg_indices, _ = find_peaks(
                -data,
                height=abs_threshold,
                distance=min_distance_points,
            )
            for idx in neg_indices:
                # SNR uses abs value so it is always positive even for negative DEPT peaks
                snr = float(abs(data[idx]) / sigma_mad) if sigma_mad is not None else None
                peaks.append(Peak1D(
                    position=float(ppm_scale[idx]),
                    intensity=float(data[idx]),  # Keep negative value
                    snr=snr,
                ))

        # Sort by ppm (descending)
        peaks.sort(key=lambda p: p.position, reverse=True)

        return PeakList1D(
            peaks=peaks,
            nucleus=spectrum.nucleus,
            noise_sigma=sigma_mad,
        )

    def estimate_line_widths(
        self,
        spectrum: Spectrum1D,
        threshold: float = 0.05,
    ) -> dict[str, float]:
        """Estimate line widths from the spectrum.

        Args:
            spectrum: 1D NMR spectrum
            threshold: Minimum intensity as fraction of max (0-1)

        Returns:
            Dictionary with 'median_fwhm_ppm', 'median_fwhm_hz',
            'min_fwhm_ppm', 'max_fwhm_ppm', 'adaptive_min_distance_ppm'
        """
        data = spectrum.data
        ppm_scale = spectrum.ppm_scale
        ppm_per_point = abs(ppm_scale[1] - ppm_scale[0]) if len(ppm_scale) > 1 else 1.0

        max_intensity = np.max(np.abs(data))
        abs_threshold = threshold * max_intensity

        # First pass with loose distance
        initial_distance = max(1, int(0.01 / ppm_per_point))  # ~0.01 ppm
        peak_indices, _ = find_peaks(
            data,
            height=abs_threshold,
            distance=initial_distance,
        )

        if len(peak_indices) == 0:
            return {
                "median_fwhm_ppm": self.fallback_min_distance_ppm,
                "median_fwhm_hz": self.fallback_min_distance_ppm * spectrum.frequency,
                "min_fwhm_ppm": self.fallback_min_distance_ppm,
                "max_fwhm_ppm": self.fallback_min_distance_ppm,
                "adaptive_min_distance_ppm": self.fallback_min_distance_ppm,
                "num_peaks_analyzed": 0,
            }

        # Measure FWHM
        try:
            widths_points, _, _, _ = peak_widths(data, peak_indices, rel_height=0.5)
            widths_ppm = widths_points * ppm_per_point

            # Filter out unreasonably wide peaks (likely baseline issues)
            reasonable_widths = widths_ppm[widths_ppm < 1.0]  # Max 1 ppm
            if len(reasonable_widths) == 0:
                reasonable_widths = widths_ppm

            median_fwhm = float(np.median(reasonable_widths))
            min_fwhm = float(np.min(reasonable_widths))
            max_fwhm = float(np.max(reasonable_widths))

        except Exception:
            median_fwhm = self.fallback_min_distance_ppm
            min_fwhm = self.fallback_min_distance_ppm
            max_fwhm = self.fallback_min_distance_ppm

        return {
            "median_fwhm_ppm": median_fwhm,
            "median_fwhm_hz": median_fwhm * spectrum.frequency,
            "min_fwhm_ppm": min_fwhm,
            "max_fwhm_ppm": max_fwhm,
            "adaptive_min_distance_ppm": median_fwhm * self.fwhm_factor,
            "num_peaks_analyzed": len(peak_indices),
        }

    def _estimate_min_distance(
        self,
        data: np.ndarray,
        ppm_per_point: float,
        abs_threshold: float,
    ) -> float:
        """Estimate minimum distance from line widths.

        Args:
            data: Spectrum intensity data
            ppm_per_point: PPM per data point
            abs_threshold: Absolute intensity threshold

        Returns:
            Adaptive minimum distance in ppm
        """
        # First pass: find peaks with very loose distance criterion
        initial_distance = max(1, int(0.01 / ppm_per_point))  # ~0.01 ppm minimum

        peak_indices, _ = find_peaks(
            data,
            height=abs_threshold,
            distance=initial_distance,
        )

        if len(peak_indices) < 2:
            return self.fallback_min_distance_ppm

        # Measure FWHM for detected peaks
        try:
            widths_points, _, _, _ = peak_widths(data, peak_indices, rel_height=0.5)
            widths_ppm = widths_points * ppm_per_point

            # Filter unreasonably wide peaks
            reasonable_widths = widths_ppm[widths_ppm < 1.0]
            if len(reasonable_widths) == 0:
                return self.fallback_min_distance_ppm

            median_fwhm = np.median(reasonable_widths)
            return float(median_fwhm * self.fwhm_factor)

        except Exception:
            return self.fallback_min_distance_ppm
