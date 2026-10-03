"""Tests for HMBC-guided peak picker."""

import pytest

from ailsa import BrukerReader
from ailsa.models import Peak1D, Peak2D, PeakList1D, PeakList2D
from ailsa.processing import HMBCGuidedPicker, HMBCGuidedResult


class TestHMBCGuidedResult:
    """Tests for HMBCGuidedResult dataclass."""

    def test_summary_basic(self):
        """Test summary output format."""
        result = HMBCGuidedResult(
            peaks=PeakList2D(peaks=[], f1_nucleus="13C", f2_nucleus="1H", experiment_type="HMBC"),
            carbon_positions=[180.0, 130.0, 45.0],
            proton_positions=[7.2, 3.5, 1.5],
            raw_peak_count=10,
            rejected_no_carbon=[],
            rejected_no_proton=[],
            rejected_both=[],
        )
        summary = result.summary()
        assert "Reference carbons: 3" in summary
        assert "Reference protons: 3" in summary
        assert "Raw HMBC peaks: 10" in summary

    def test_validated_count(self):
        """Test validated_count property."""
        peaks = [
            Peak2D(f1_position=180.0, f2_position=3.5, intensity=1e6),
            Peak2D(f1_position=130.0, f2_position=7.2, intensity=1e6),
        ]
        result = HMBCGuidedResult(
            peaks=PeakList2D(peaks=peaks, f1_nucleus="13C", f2_nucleus="1H", experiment_type="HMBC"),
            carbon_positions=[180.0, 130.0],
            proton_positions=[7.2, 3.5],
            raw_peak_count=5,
        )
        assert result.validated_count == 2

    def test_rejected_count(self):
        """Test rejected_count property."""
        result = HMBCGuidedResult(
            peaks=PeakList2D(peaks=[], f1_nucleus="13C", f2_nucleus="1H", experiment_type="HMBC"),
            carbon_positions=[],
            proton_positions=[],
            raw_peak_count=10,
            rejected_no_carbon=[Peak2D(f1_position=50.0, f2_position=1.0, intensity=1e5)],
            rejected_no_proton=[Peak2D(f1_position=100.0, f2_position=5.0, intensity=1e5)],
            rejected_both=[Peak2D(f1_position=200.0, f2_position=9.0, intensity=1e5)],
        )
        assert result.rejected_count == 3


class TestHMBCGuidedPickerValidation:
    """Tests for input validation."""

    def test_rejects_non_hmbc_spectrum(self):
        """Test that non-HMBC spectrum is rejected."""
        # Create a mock HSQC spectrum
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")  # HSQC
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc_peaks = PeakList2D(
            peaks=[Peak2D(f1_position=45.0, f2_position=3.7, intensity=1e6)],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )

        with pytest.raises(ValueError, match="Expected HMBC"):
            HMBCGuidedPicker.pick_hmbc_peaks(
                hmbc=hsqc,  # Wrong type!
                carbon_spectrum=c13,
                hsqc_peaks=hsqc_peaks,
            )

    def test_requires_carbon_source(self):
        """Test that carbon source is required."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        hsqc_peaks = PeakList2D(
            peaks=[Peak2D(f1_position=45.0, f2_position=3.7, intensity=1e6)],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )

        with pytest.raises(ValueError, match="carbon_spectrum or dept_peaks"):
            HMBCGuidedPicker.pick_hmbc_peaks(
                hmbc=hmbc,
                carbon_spectrum=None,
                dept_peaks=None,
                hsqc_peaks=hsqc_peaks,
            )

    def test_requires_hsqc_peaks(self):
        """Test that HSQC peaks are required."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")

        with pytest.raises(ValueError, match="hsqc_peaks"):
            HMBCGuidedPicker.pick_hmbc_peaks(
                hmbc=hmbc,
                carbon_spectrum=c13,
                hsqc_peaks=None,
            )


class TestHMBCGuidedPickerFiltering:
    """Tests for peak filtering logic."""

    def test_filters_peaks_without_carbon_match(self):
        """Test that peaks without carbon match are rejected."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")

        result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
        )

        # Should have some rejected peaks
        assert result.raw_peak_count >= result.validated_count

    def test_carbon_tolerance_affects_filtering(self):
        """Test that carbon tolerance affects which peaks are accepted."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")

        # Tight tolerance
        result_tight = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            carbon_tolerance=0.5,
        )

        # Loose tolerance
        result_loose = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            carbon_tolerance=3.0,
        )

        # Looser tolerance should accept more or equal peaks
        assert result_loose.validated_count >= result_tight.validated_count

    def test_proton_tolerance_affects_filtering(self):
        """Test that proton tolerance affects which peaks are accepted."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")

        # Tight tolerance
        result_tight = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            proton_tolerance=0.02,
        )

        # Loose tolerance
        result_loose = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            proton_tolerance=0.2,
        )

        # Looser tolerance should accept more or equal peaks
        assert result_loose.validated_count >= result_tight.validated_count


class TestIbuprofenIntegration:
    """Integration tests using Ibuprofen data."""

    def test_picks_reasonable_number_of_peaks(self):
        """Test that HMBC picking returns reasonable number of correlations."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")

        # Pin to the legacy fraction-of-max path: this 15-50 envelope was
        # written for the fraction-of-max picker. FIX-12 changed the default to
        # the noise-relative SNR floor, which intentionally surfaces many more
        # weak long-range cross-peaks for downstream curation; the SNR-mode
        # behaviour (incl. recovery of the ring-diagnostic 3J-meta correlations)
        # is pinned by the dedicated regression test in plan 85-02.
        result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            hmbc_use_snr=False,
        )

        # Ibuprofen should have 20-40 HMBC correlations (fraction-of-max path)
        assert 15 <= result.validated_count <= 50
        assert result.validated_count <= result.raw_peak_count

    def test_includes_carbonyl_correlations(self):
        """Test that carbonyl carbon (180 ppm) has HMBC correlations."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")

        result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
        )

        # Check for carbonyl correlations (around 180 ppm)
        carbonyl_peaks = [p for p in result.peaks.peaks if 175 <= p.f1_position <= 185]
        assert len(carbonyl_peaks) >= 1, "Should find carbonyl HMBC correlations"

    def test_includes_aromatic_correlations(self):
        """Test that aromatic carbons have HMBC correlations."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")

        result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
        )

        # Check for aromatic correlations (120-145 ppm)
        aromatic_peaks = [p for p in result.peaks.peaks if 120 <= p.f1_position <= 145]
        assert len(aromatic_peaks) >= 2, "Should find aromatic HMBC correlations"

    def test_summary_output(self):
        """Test that summary is well-formatted."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")

        result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
        )

        summary = result.summary()
        assert "HMBC Guided Peak Picking Result" in summary
        assert "Reference carbons:" in summary
        assert "Reference protons:" in summary
        assert "Validated peaks:" in summary

    def test_with_dept_adds_carbons(self):
        """Test that DEPT adds additional carbon positions."""
        hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
        c13 = BrukerReader.read_1d("data/Ibuprofen/2")
        hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
        dept135 = BrukerReader.read_1d("data/Ibuprofen/3")

        result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            dept135=dept135,
        )

        # Should have reference carbons from both sources
        assert len(result.carbon_positions) >= 8


class TestModuleExports:
    """Tests for module exports."""

    def test_import_from_processing(self):
        """Test importing from processing module."""
        from ailsa.processing import HMBCGuidedPicker, HMBCGuidedResult

        assert HMBCGuidedPicker is not None
        assert HMBCGuidedResult is not None
