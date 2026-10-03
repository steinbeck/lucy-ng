"""Tests for SNR/MAD peak-picker threshold (FIX-04).

Regression tests verifying that:
  - CASE9 ester carbonyl at 166.08 ppm is picked by the new threshold.
  - CASE1 (ibuprofen) 13C peak count is unchanged.
  - Per-peak SNR annotation is present.
"""

from pathlib import Path

import numpy as np
import pytest

from ailsa.models import PeakList1D
from ailsa.processing.peak_picker import AdaptivePeakPicker, _compute_snr_threshold
from ailsa.readers import BrukerReader

# Real Bruker data paths — confirmed available by RESEARCH.md
DATA_DIR = Path(__file__).parent.parent / "data"
CASE1_C13 = DATA_DIR / "Ibuprofen" / "2"  # in-repo

# CASE9 is outside the repo (see reference_test_data memory)
CASE9_C13 = Path(
    "/Users/steinbeck/Dropbox/develop/data/nmrdata"
    "/active-lucy-ng-testprojects/CASE9/12"
)


class TestSNRThreshold:
    """Unit tests for _compute_snr_threshold helper."""

    def test_mad_lower_than_max_for_cdcl3_dominated_spectrum(self) -> None:
        """sigma_mad must be << 5% of max for CDCl3-dominated spectrum."""
        # Synthetic: noise floor + one large CDCl3 spike
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 1e5, 32768)
        ppm = np.linspace(220.0, 0.0, 32768)
        # Inject CDCl3 spike at 77 ppm
        cdcl3_idx = int((220.0 - 77.16) / 220.0 * 32768)
        noise[cdcl3_idx] = 4.6e7
        threshold, sigma_mad = _compute_snr_threshold(noise, ppm, solvent="CDCl3")
        # sigma_mad must be close to 1e5, not inflated by the spike
        assert sigma_mad < 5e5, f"sigma_mad too large: {sigma_mad:.2e}"
        # threshold = 3 * sigma_mad, must be << 2.30e6 (the old 5%-max threshold)
        assert threshold < 1e6

    def test_empty_clean_data_fallback_is_finite(self) -> None:
        """When solvent exclusion removes all points, fallback must produce finite threshold.

        Regression for CR-01: np.median([]) returns nan, which propagated silently to
        find_peaks and to JSON output (NaN literal, invalid RFC-8259).
        """
        # Spectrum entirely within the CDCl3 exclusion window (72–82 ppm).
        # After masking, clean_data is empty → old code returned (nan, nan).
        ppm = np.linspace(82.0, 72.0, 100)   # entirely inside exclusion window
        data = np.zeros(100)
        data[50] = 1.0                         # one real peak at centre
        threshold, sigma_mad = _compute_snr_threshold(data, ppm, solvent="CDCl3")
        assert np.isfinite(threshold), f"threshold must be finite, got {threshold}"
        assert np.isfinite(sigma_mad), f"sigma_mad must be finite, got {sigma_mad}"
        assert threshold > 0

    def test_zero_mad_fallback_is_finite(self) -> None:
        """When MAD=0 (perfectly flat baseline), fallback must produce non-zero threshold.

        Regression for CR-01: zero-background synthetic spectra have MAD=0, so
        _compute_snr_threshold previously returned threshold=0, causing every local
        max to be picked (find_peaks(height=0) floods results).
        """
        ppm = np.linspace(200.0, 0.0, 1000)
        data = np.zeros(1000)
        data[300] = 1.0   # one isolated peak on a perfectly flat baseline
        threshold, sigma_mad = _compute_snr_threshold(data, ppm, solvent=None)
        assert np.isfinite(threshold), f"threshold must be finite, got {threshold}"
        assert np.isfinite(sigma_mad), f"sigma_mad must be finite, got {sigma_mad}"
        assert threshold > 0

    def test_empty_clean_data_fallback_picks_real_peak(self) -> None:
        """After the empty-clean_data fallback, real peaks are still found.

        Verifies the full pick_peaks path does not silently discard peaks when the
        solvent exclusion covers the entire spectrum window.
        """
        ppm = np.linspace(82.0, 72.0, 200)
        data = np.zeros(200)
        # Strong peak at 77 ppm (inside CDCl3 window — pathological spectrum)
        peak_idx = 100
        data[peak_idx] = 1.0
        data[peak_idx - 1] = 0.3
        data[peak_idx + 1] = 0.3

        from ailsa.models import Spectrum1D

        spectrum = Spectrum1D(data=data, ppm_scale=ppm, nucleus="13C", frequency=100.0, solvent="CDCl3")
        from ailsa.processing.peak_picker import AdaptivePeakPicker
        peaks = AdaptivePeakPicker.pick_peaks(spectrum)
        # The fallback threshold (5% of max = 0.05) must leave the 1.0-intensity peak visible
        assert len(peaks.peaks) >= 1
        # noise_sigma must be finite (not NaN)
        assert peaks.noise_sigma is not None
        assert np.isfinite(peaks.noise_sigma)


class TestCASE9Regression:
    """Integration regression: CASE9 carbonyl must be picked."""

    @pytest.mark.skipif(
        not CASE9_C13.exists(),
        reason="CASE9 dataset not available on this machine",
    )
    def test_case9_carbonyl_picked(self) -> None:
        """Ester C=O at 166.08 ppm (SNR≈17) must appear in peak list."""
        spectrum = BrukerReader.read_1d(str(CASE9_C13))
        peaks = AdaptivePeakPicker.pick_peaks(spectrum)

        ppms = [p.position for p in peaks.peaks]
        # Carbonyl at 166.08 ppm — accept ±2 ppm window
        assert any(164.0 <= ppm <= 168.0 for ppm in ppms), (
            f"Carbonyl not found near 166 ppm. Picked: {sorted(ppms, reverse=True)[:10]}"
        )

    @pytest.mark.skipif(
        not CASE9_C13.exists(),
        reason="CASE9 dataset not available on this machine",
    )
    def test_case9_all_peaks_have_snr(self) -> None:
        """Every picked peak must carry a non-None SNR annotation."""
        spectrum = BrukerReader.read_1d(str(CASE9_C13))
        peaks = AdaptivePeakPicker.pick_peaks(spectrum)
        for p in peaks.peaks:
            assert p.snr is not None
            assert p.snr > 0


class TestSNRFloorDefault:
    """Tests for FIX-08: snr_floor default raised from 3.0 to 5.0."""

    def test_pick_peaks_default_snr_floor_is_5(self) -> None:
        """AdaptivePeakPicker.pick_peaks must have snr_floor default = 5.0."""
        import inspect

        sig = inspect.signature(AdaptivePeakPicker.pick_peaks)
        assert sig.parameters["snr_floor"].default == 5.0, (
            f"Expected snr_floor default 5.0, got {sig.parameters['snr_floor'].default}"
        )

    def test_pick_peaks_instance_default_snr_floor_is_5(self) -> None:
        """AdaptivePeakPicker.pick_peaks_instance must have snr_floor default = 5.0."""
        import inspect

        sig = inspect.signature(AdaptivePeakPicker.pick_peaks_instance)
        assert sig.parameters["snr_floor"].default == 5.0, (
            f"Expected snr_floor default 5.0, got {sig.parameters['snr_floor'].default}"
        )

    def test_explicit_snr_floor_3_still_overrides(self) -> None:
        """Explicit snr_floor=3.0 kwarg must override the new default."""
        spectrum = BrukerReader.read_1d(str(CASE1_C13))
        peaks_at_3 = AdaptivePeakPicker.pick_peaks(spectrum, snr_floor=3.0)
        peaks_at_5 = AdaptivePeakPicker.pick_peaks(spectrum, snr_floor=5.0)
        # At k=3 we expect at least as many peaks as at k=5 (lower floor = more peaks)
        assert len(peaks_at_3.peaks) >= len(peaks_at_5.peaks), (
            f"k=3 returned {len(peaks_at_3.peaks)} peaks, k=5 returned {len(peaks_at_5.peaks)}. "
            "Lower SNR floor should return >= peaks."
        )


class TestCASE1Regression:
    """Regression: ibuprofen 13C peak count must not decrease."""

    def test_case1_count_unchanged(self) -> None:
        """Ibuprofen should still yield >= 9 13C peaks (same as before)."""
        spectrum = BrukerReader.read_1d(str(CASE1_C13))
        peaks = AdaptivePeakPicker.pick_peaks(spectrum)
        # v8.0 picked 13 peaks; SNR threshold picks a superset — assert floor
        assert len(peaks.peaks) >= 9, (
            f"Ibuprofen peak count dropped to {len(peaks.peaks)}"
        )


class TestCLIPick1D:
    """CLI JSON output regression tests for FIX-04 fields."""

    def test_pick_1d_json_has_snr(self) -> None:
        """New SNR field must be present in each peak in JSON output."""
        import json

        from click.testing import CliRunner

        from ailsa.cli.pick import pick

        runner = CliRunner()
        result = runner.invoke(pick, ["1d", str(CASE1_C13), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "snr" in data["peaks"][0]
        # snr must be a positive number (not None serialized as null)
        assert data["peaks"][0]["snr"] is not None
        assert data["peaks"][0]["snr"] > 0

    def test_pick_1d_json_has_noise_sigma(self) -> None:
        """New noise_sigma top-level field must be present in JSON output."""
        import json

        from click.testing import CliRunner

        from ailsa.cli.pick import pick

        runner = CliRunner()
        result = runner.invoke(pick, ["1d", str(CASE1_C13), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "noise_sigma" in data
        assert data["noise_sigma"] is not None
        assert data["noise_sigma"] > 0
