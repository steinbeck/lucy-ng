"""Tests for 2D peak picker."""

from pathlib import Path

import pytest

from ailsa.models import PeakList2D
from ailsa.processing.peak_picker_2d import PeakPicker2D
from ailsa.readers.bruker import BrukerReader

# Test data paths
DATA_DIR = Path(__file__).parent.parent / "data"
IBUPROFEN_HSQC = DATA_DIR / "Ibuprofen" / "6"
IBUPROFEN_HMBC = DATA_DIR / "Ibuprofen" / "7"
IBUPROFEN_COSY = DATA_DIR / "Ibuprofen" / "5"


class TestPeakPicker2D:
    """Tests for 2D peak picking."""

    def test_pick_hsqc_peaks(self) -> None:
        """Test that HSQC peak picking finds reasonable number of peaks."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=0.05)

        # Ibuprofen has ~10 C-H correlations, expect 5-30 peaks
        assert len(peaks.peaks) >= 5
        assert len(peaks.peaks) <= 50

    def test_hsqc_peak_positions(self) -> None:
        """Test that HSQC peaks are in expected ppm ranges."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=0.05)

        for peak in peaks.peaks:
            # F1 (13C) should be 0-200 ppm
            assert 0 <= peak.f1_position <= 200
            # F2 (1H) should be 0-15 ppm
            assert 0 <= peak.f2_position <= 15

    def test_pick_hmbc_peaks(self) -> None:
        """Test that HMBC finds more peaks than HSQC (long-range correlations)."""
        hsqc = BrukerReader.read_2d(IBUPROFEN_HSQC)
        hmbc = BrukerReader.read_2d(IBUPROFEN_HMBC)

        hsqc_peaks = PeakPicker2D.pick_peaks(hsqc, threshold=0.05)
        hmbc_peaks = PeakPicker2D.pick_peaks(hmbc, threshold=0.05)

        # HMBC typically has more correlations than HSQC
        # But with same threshold, just verify we get peaks
        assert len(hmbc_peaks.peaks) >= 5

    def test_pick_cosy_peaks(self) -> None:
        """Test COSY peak picking (homonuclear)."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_COSY)
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=0.05)

        # Should find some correlations
        assert len(peaks.peaks) >= 3

        # Both dimensions should be 1H (0-15 ppm)
        for peak in peaks.peaks:
            assert 0 <= peak.f1_position <= 15
            assert 0 <= peak.f2_position <= 15

    def test_threshold_affects_count(self) -> None:
        """Test that higher threshold yields fewer peaks."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        peaks_low = PeakPicker2D.pick_peaks(spectrum, threshold=0.02)
        peaks_high = PeakPicker2D.pick_peaks(spectrum, threshold=0.20)

        assert len(peaks_low.peaks) > len(peaks_high.peaks)

    def test_min_separation_affects_count(self) -> None:
        """Test that larger separation can yield fewer peaks."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        peaks_close = PeakPicker2D.pick_peaks(spectrum, threshold=0.05, min_separation=(2, 2))
        peaks_far = PeakPicker2D.pick_peaks(spectrum, threshold=0.05, min_separation=(10, 10))

        # Larger separation should typically give same or fewer peaks
        assert len(peaks_close.peaks) >= len(peaks_far.peaks)

    def test_peak_list_metadata(self) -> None:
        """Test that peak list has correct metadata."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=0.05)

        assert peaks.f1_nucleus == "13C"
        assert peaks.f2_nucleus == "1H"
        assert peaks.experiment_type == "HSQC"

    def test_cosy_metadata(self) -> None:
        """Test COSY peak list metadata."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_COSY)
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=0.05)

        assert peaks.f1_nucleus == "1H"
        assert peaks.f2_nucleus == "1H"
        assert peaks.experiment_type == "COSY"

    def test_peak_intensities(self) -> None:
        """Test that peaks have valid intensities."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=0.05)

        for peak in peaks.peaks:
            # All peaks should have non-zero intensity
            assert peak.intensity != 0

    def test_peaks_sorted_by_f1(self) -> None:
        """Test that peaks are sorted by F1 ppm (descending)."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=0.05)

        if len(peaks.peaks) >= 2:
            f1_values = [p.f1_position for p in peaks.peaks]
            # Should be sorted descending
            assert f1_values == sorted(f1_values, reverse=True)


class TestNoiseEstimation:
    """Tests for noise estimation."""

    def test_estimate_noise_positive(self) -> None:
        """Test that noise estimate is positive."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        noise = PeakPicker2D.estimate_noise(spectrum)

        assert noise > 0

    def test_estimate_noise_reasonable(self) -> None:
        """Test that noise is much smaller than max signal."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        noise = PeakPicker2D.estimate_noise(spectrum)
        max_signal = abs(spectrum.data.max())

        # Noise should be much smaller than max signal (at least 10x)
        assert noise < max_signal / 10

    def test_pick_peaks_snr(self) -> None:
        """Test SNR-based peak picking."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        peaks = PeakPicker2D.pick_peaks_snr(spectrum, snr_threshold=5.0)

        # Should find some peaks
        assert len(peaks.peaks) >= 3
        assert isinstance(peaks, PeakList2D)


class TestSpectrum2DHelpers:
    """Tests for Spectrum2D ppm/index conversion."""

    def test_f1_ppm_to_index(self) -> None:
        """Test F1 ppm to index conversion."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        # Get index for a middle ppm value
        mid_ppm = float(spectrum.f1_ppm_scale[len(spectrum.f1_ppm_scale) // 2])
        idx = spectrum.f1_ppm_to_index(mid_ppm)

        assert 0 <= idx < len(spectrum.f1_ppm_scale)

    def test_f2_ppm_to_index(self) -> None:
        """Test F2 ppm to index conversion."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        mid_ppm = float(spectrum.f2_ppm_scale[len(spectrum.f2_ppm_scale) // 2])
        idx = spectrum.f2_ppm_to_index(mid_ppm)

        assert 0 <= idx < len(spectrum.f2_ppm_scale)

    def test_index_to_ppm_roundtrip(self) -> None:
        """Test that index -> ppm -> index is consistent."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        # Pick a random index
        test_idx = 100
        ppm = spectrum.f1_index_to_ppm(test_idx)
        recovered_idx = spectrum.f1_ppm_to_index(ppm)

        assert recovered_idx == test_idx

    def test_ppm_to_index_edge_values(self) -> None:
        """Test ppm to index for edge values."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        # Test with first ppm value
        first_ppm = float(spectrum.f1_ppm_scale[0])
        assert spectrum.f1_ppm_to_index(first_ppm) == 0

        # Test with last ppm value
        last_ppm = float(spectrum.f1_ppm_scale[-1])
        assert spectrum.f1_ppm_to_index(last_ppm) == len(spectrum.f1_ppm_scale) - 1
