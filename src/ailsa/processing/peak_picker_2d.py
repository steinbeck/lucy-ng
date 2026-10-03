"""2D NMR peak picking."""

from typing import Any

import nmrglue as ng
import numpy as np

from ailsa.models import Peak2D, PeakList2D, Spectrum2D


def _compute_2d_noise_sigma(data: "np.ndarray[Any, Any]") -> float:
    """Compute a robust MAD-based noise sigma for a 2D NMR spectrum.

    This is the 2D analog of the 1D FIX-08 ``_compute_snr_threshold`` MAD
    estimate. A median-absolute-deviation statistic is computed over the
    *entire* 2D array (sigma = 1.4826 * median(|data - median(data)|)).

    The MAD is used in preference to the corner-std estimate (the existing
    ``estimate_noise``) because it is robust against the intense aliphatic/2J
    cross-peaks that dominate an HMBC plane and would inflate a plain std/mean.
    Empirically (CASE1 expno 7), the global MAD gives sigma ~= 2.15e4 against a
    global max of ~7.48e7, so the diagnostic 3J-meta cross-peak at 0.64 % of max
    (intensity ~4.8e5) sits at SNR ~= 22 — comfortably above a k=5 floor — while
    the corner-std estimate is ~2.4x larger (driven by tail signal leaking into
    the corners) and depresses that same peak toward the floor.

    Args:
        data: 2D intensity array.

    Returns:
        A finite, strictly-positive noise sigma. Falls back to a small fraction
        of the global max (mirroring the 1D zero/NaN guard) when the MAD is zero
        or non-finite (constant / empty plane), so the picker never produces NaN.
    """
    if data.size == 0:
        return 1.0
    med = float(np.median(data))
    mad = float(np.median(np.abs(data - med)))
    sigma_mad = 1.4826 * mad

    # Guard against zero/NaN sigma (constant baseline) — mirror the 1D fallback.
    if not np.isfinite(sigma_mad) or sigma_mad == 0.0:
        max_abs = float(np.max(np.abs(data)))
        # 0.05 * max / 5 keeps a k=5 floor at 5 % of max, matching the legacy
        # fraction-of-max default when robust noise cannot be estimated.
        return (0.05 * max_abs / 5.0) if max_abs > 0 else 1.0

    return sigma_mad


class PeakPicker2D:
    """2D NMR peak picker using nmrglue.

    Uses nmrglue's peak picking algorithm which finds local maxima
    and clusters connected regions above threshold.
    """

    @staticmethod
    def pick_peaks(
        spectrum: Spectrum2D,
        threshold: float | None = None,
        min_separation: tuple[int, int] = (3, 3),
        detect_negative: bool = False,
        snr_floor: float = 5.0,
        use_snr: bool = True,
    ) -> PeakList2D:
        """Pick peaks from a 2D spectrum.

        Two thresholding modes (the 2D analog of the 1D FIX-08 picker):

        * **SNR mode (default).** When ``use_snr`` is True and no explicit
          ``threshold`` is given, the absolute pick threshold is
          ``snr_floor * sigma`` where sigma is a robust MAD-based 2D noise
          estimate (see :func:`_compute_2d_noise_sigma`). This keeps weak but
          real long-range cross-peaks (e.g. ring-diagnostic 3J-meta aromatic
          correlations at ~0.6 % of the global max, which are SNR>=floor over
          local noise) that the fraction-of-max threshold systematically drops,
          while still rejecting the ~0.5-2 %-of-max noise that floods a naive
          low-threshold pick. Each picked peak is annotated with
          ``snr = abs(intensity) / sigma``.
        * **Legacy fraction-of-max mode.** When an explicit ``threshold`` is
          passed (a float), the absolute threshold is ``threshold * max(|data|)``
          exactly as before; ``snr`` is left ``None``. Passing ``use_snr=False``
          (with the default ``threshold`` then treated as 0.05) also forces this
          path for callers that want fraction-of-max without specifying a value.

        Args:
            spectrum: 2D NMR spectrum with data and ppm scales.
            threshold: Minimum intensity as fraction of max (0-1). When given
                (non-None), the legacy fraction-of-max path is used and SNR mode
                is disabled. When None (default), SNR mode is used.
            min_separation: Minimum separation in points (F1, F2).
            detect_negative: Also detect negative peaks (for HMBC artifacts).
            snr_floor: SNR floor multiplier k for SNR mode (default 5.0, matching
                the 1D FIX-08 signal/noise separation default).
            use_snr: If True (default) and no explicit threshold is given, use the
                MAD/SNR absolute threshold. If False, use fraction-of-max.

        Returns:
            PeakList2D containing detected peaks (with per-peak snr in SNR mode).
        """
        data = spectrum.data
        f1_ppm_scale = spectrum.f1_ppm_scale
        f2_ppm_scale = spectrum.f2_ppm_scale

        # Resolve mode: an explicit threshold always means legacy fraction-of-max
        # (this preserves every existing direct-call test). SNR mode applies only
        # when use_snr is True AND no explicit threshold was provided.
        snr_mode = use_snr and threshold is None

        sigma: float | None
        if snr_mode:
            sigma_value = _compute_2d_noise_sigma(data)
            sigma = sigma_value
            abs_threshold = snr_floor * sigma_value
        else:
            sigma = None
            frac = threshold if threshold is not None else 0.05
            abs_threshold = frac * float(np.max(np.abs(data)))

        peaks: list[Peak2D] = []

        def _snr_for(intensity: float) -> float | None:
            return float(abs(intensity) / sigma) if sigma is not None else None

        # Pick positive peaks
        pos_result = ng.peakpick.pick(
            data,
            pthres=abs_threshold,
            nthres=None,
            msep=min_separation,
            algorithm="connected",
            est_params=True,
            cluster=True,
            table=True,
        )

        # Convert to Peak2D objects
        for row in pos_result:
            y_idx = int(row["Y_AXIS"])
            x_idx = int(row["X_AXIS"])

            # Convert indices to ppm
            f1_ppm = float(f1_ppm_scale[y_idx]) if y_idx < len(f1_ppm_scale) else 0.0
            f2_ppm = float(f2_ppm_scale[x_idx]) if x_idx < len(f2_ppm_scale) else 0.0

            # Get intensity at peak location
            intensity = float(data[y_idx, x_idx])

            peaks.append(
                Peak2D(
                    f1_position=f1_ppm,
                    f2_position=f2_ppm,
                    intensity=intensity,
                    snr=_snr_for(intensity),
                )
            )

        # Pick negative peaks if requested
        if detect_negative:
            neg_result = ng.peakpick.pick(
                data,
                pthres=None,
                nthres=-abs_threshold,
                msep=min_separation,
                algorithm="connected",
                est_params=True,
                cluster=True,
                table=True,
            )

            for row in neg_result:
                y_idx = int(row["Y_AXIS"])
                x_idx = int(row["X_AXIS"])

                f1_ppm = float(f1_ppm_scale[y_idx]) if y_idx < len(f1_ppm_scale) else 0.0
                f2_ppm = float(f2_ppm_scale[x_idx]) if x_idx < len(f2_ppm_scale) else 0.0
                intensity = float(data[y_idx, x_idx])

                peaks.append(
                    Peak2D(
                        f1_position=f1_ppm,
                        f2_position=f2_ppm,
                        intensity=intensity,
                        snr=_snr_for(intensity),
                    )
                )

        # Sort by F1 ppm (descending), then F2 ppm (descending)
        peaks.sort(key=lambda p: (-p.f1_position, -p.f2_position))

        return PeakList2D(
            peaks=peaks,
            f1_nucleus=spectrum.f1_nucleus,
            f2_nucleus=spectrum.f2_nucleus,
            experiment_type=spectrum.experiment_type,
        )

    @staticmethod
    def pick_peaks_snr(
        spectrum: Spectrum2D,
        snr_threshold: float = 5.0,
        min_separation: tuple[int, int] = (3, 3),
        detect_negative: bool = False,
    ) -> PeakList2D:
        """Pick peaks using signal-to-noise ratio threshold.

        Args:
            spectrum: 2D NMR spectrum
            snr_threshold: Minimum signal-to-noise ratio
            min_separation: Minimum separation in points (F1, F2)
            detect_negative: Also detect negative peaks

        Returns:
            PeakList2D containing detected peaks
        """
        noise = PeakPicker2D.estimate_noise(spectrum)
        abs_threshold = snr_threshold * noise

        # Use absolute threshold with pick_peaks logic
        max_intensity = np.max(np.abs(spectrum.data))
        relative_threshold = abs_threshold / max_intensity

        return PeakPicker2D.pick_peaks(
            spectrum,
            threshold=relative_threshold,
            min_separation=min_separation,
            detect_negative=detect_negative,
        )

    @staticmethod
    def estimate_noise(spectrum: Spectrum2D, corner_fraction: float = 0.1) -> float:
        """Estimate noise level from spectrum corners.

        Uses the corners of the 2D spectrum where real peaks are
        unlikely to be found.

        Args:
            spectrum: 2D NMR spectrum
            corner_fraction: Fraction of each dimension to use (0-0.5)

        Returns:
            Estimated noise level (standard deviation)
        """
        data = spectrum.data
        f1_size, f2_size = data.shape

        # Calculate corner sizes
        f1_corner = max(1, int(f1_size * corner_fraction))
        f2_corner = max(1, int(f2_size * corner_fraction))

        # Extract corners (top-left, top-right, bottom-left, bottom-right)
        corners = [
            data[:f1_corner, :f2_corner],  # Top-left
            data[:f1_corner, -f2_corner:],  # Top-right
            data[-f1_corner:, :f2_corner],  # Bottom-left
            data[-f1_corner:, -f2_corner:],  # Bottom-right
        ]

        # Combine all corner data
        corner_data = np.concatenate([c.flatten() for c in corners])

        # Return standard deviation as noise estimate
        return float(np.std(corner_data))

    @staticmethod
    def get_peak_info(spectrum: Spectrum2D, peak: Peak2D) -> dict[str, Any]:
        """Get detailed information about a peak.

        Args:
            spectrum: 2D NMR spectrum
            peak: Peak to analyze

        Returns:
            Dictionary with peak details including linewidths
        """
        # Find index of peak
        f1_idx = int(np.argmin(np.abs(spectrum.f1_ppm_scale - peak.f1_position)))
        f2_idx = int(np.argmin(np.abs(spectrum.f2_ppm_scale - peak.f2_position)))

        return {
            "f1_ppm": peak.f1_position,
            "f2_ppm": peak.f2_position,
            "f1_index": f1_idx,
            "f2_index": f2_idx,
            "intensity": peak.intensity,
            "f1_nucleus": spectrum.f1_nucleus,
            "f2_nucleus": spectrum.f2_nucleus,
        }
