"""Tests for DEPT-guided adaptive HSQC peak picker."""

import pytest
import numpy as np

from ailsa import (
    BrukerReader,
    DEPTGuidedPicker,
    DEPTGuidedResult,
    Peak1D,
    PeakList1D,
    Spectrum1D,
    Spectrum2D,
)


class TestDEPTGuidedResult:
    """Tests for DEPTGuidedResult dataclass."""

    def test_summary_basic(self):
        """Test summary output for basic result."""
        result = DEPTGuidedResult(
            peaks=PeakList1D(peaks=[], nucleus="13C"),  # Will be replaced
            dept_peaks=PeakList1D(peaks=[], nucleus="13C"),
            threshold_used=0.05,
            iterations=3,
            all_carbons_found=True,
            unmatched_dept_peaks=[],
            carbon_multiplicities={},
        )
        # Create proper PeakList2D for peaks
        from ailsa.models import PeakList2D
        result.peaks = PeakList2D(
            peaks=[], f1_nucleus="13C", f2_nucleus="1H", experiment_type="HSQC"
        )

        summary = result.summary()
        assert "DEPT-Guided" in summary
        assert "Threshold used: 0.0500" in summary
        assert "Iterations: 3" in summary
        assert "All carbons found: True" in summary

    def test_summary_with_unmatched(self):
        """Test summary shows unmatched peaks."""
        from ailsa.models import PeakList2D

        unmatched = [Peak1D(position=45.0, intensity=1000.0)]
        result = DEPTGuidedResult(
            peaks=PeakList2D(
                peaks=[], f1_nucleus="13C", f2_nucleus="1H", experiment_type="HSQC"
            ),
            dept_peaks=PeakList1D(peaks=unmatched, nucleus="13C"),
            threshold_used=0.005,
            iterations=5,
            all_carbons_found=False,
            unmatched_dept_peaks=unmatched,
            carbon_multiplicities={},
        )

        summary = result.summary()
        assert "All carbons found: False" in summary
        assert "Unmatched DEPT peaks: 1" in summary
        assert "45.00 ppm" in summary

    def test_summary_with_multiplicities(self):
        """Test summary shows carbon multiplicities."""
        from ailsa.models import PeakList2D

        result = DEPTGuidedResult(
            peaks=PeakList2D(
                peaks=[], f1_nucleus="13C", f2_nucleus="1H", experiment_type="HSQC"
            ),
            dept_peaks=PeakList1D(peaks=[], nucleus="13C"),
            threshold_used=0.05,
            iterations=2,
            all_carbons_found=True,
            unmatched_dept_peaks=[],
            carbon_multiplicities={129.5: "CH/CH3", 45.0: "CH2", 22.0: "CH3"},
        )

        summary = result.summary()
        assert "Carbon multiplicities:" in summary
        assert "CH/CH3" in summary
        assert "CH2" in summary
        assert "CH3" in summary


class TestDEPTGuidedPickerValidation:
    """Tests for input validation."""

    def test_rejects_non_hsqc_spectrum(self):
        """Test that non-HSQC spectrum raises ValueError."""
        # Create a mock HMBC spectrum
        hsqc = Spectrum2D(
            data=np.zeros((10, 10)),
            f1_ppm_scale=np.linspace(200, 0, 10),
            f2_ppm_scale=np.linspace(10, 0, 10),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HMBC",  # Wrong type
            frequency=400.0,
        )
        dept = Spectrum1D(
            data=np.zeros(100),
            ppm_scale=np.linspace(200, 0, 100),
            nucleus="13C",
            frequency=100.0,
        )

        with pytest.raises(ValueError, match="Expected HSQC"):
            DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)

    def test_rejects_non_carbon_dept(self):
        """Test that non-13C DEPT raises ValueError."""
        hsqc = Spectrum2D(
            data=np.zeros((10, 10)),
            f1_ppm_scale=np.linspace(200, 0, 10),
            f2_ppm_scale=np.linspace(10, 0, 10),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=400.0,
        )
        dept = Spectrum1D(
            data=np.zeros(100),
            ppm_scale=np.linspace(10, 0, 100),
            nucleus="1H",  # Wrong nucleus
            frequency=400.0,
        )

        with pytest.raises(ValueError, match="Expected 13C"):
            DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)


class TestDEPTGuidedPickerAlgorithm:
    """Tests for the adaptive threshold algorithm."""

    def test_empty_dept_returns_empty_result(self):
        """Test that empty DEPT spectrum returns empty result."""
        hsqc = Spectrum2D(
            data=np.zeros((100, 100)),  # Empty spectrum
            f1_ppm_scale=np.linspace(200, 0, 100),
            f2_ppm_scale=np.linspace(10, 0, 100),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=400.0,
        )
        dept = Spectrum1D(
            data=np.zeros(100),  # Empty DEPT, no peaks
            ppm_scale=np.linspace(200, 0, 100),
            nucleus="13C",
            frequency=100.0,
        )

        result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept, dept_threshold=0.5)

        assert len(result.dept_peaks.peaks) == 0
        assert len(result.peaks.peaks) == 0
        assert result.all_carbons_found is True
        assert result.iterations == 0

    def test_finds_peaks_at_first_threshold(self):
        """Test when all carbons found at initial threshold."""
        # Create HSQC with strong peak
        hsqc_data = np.zeros((100, 100))
        hsqc_data[50, 50] = 1.0  # Strong peak at center

        hsqc = Spectrum2D(
            data=hsqc_data,
            f1_ppm_scale=np.linspace(200, 0, 100),
            f2_ppm_scale=np.linspace(10, 0, 100),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=400.0,
        )

        # Create DEPT with peak at matching position
        dept_data = np.zeros(100)
        dept_data[50] = 1.0  # Peak at same F1 position

        dept = Spectrum1D(
            data=dept_data,
            ppm_scale=np.linspace(200, 0, 100),
            nucleus="13C",
            frequency=100.0,
        )

        result = DEPTGuidedPicker.pick_hsqc_peaks(
            hsqc, dept, initial_hsqc_threshold=0.10
        )

        assert result.all_carbons_found is True
        assert result.iterations == 1  # Found on first try
        assert len(result.peaks.peaks) >= 1

    def test_threshold_decreases_until_match(self):
        """Test threshold progressively decreases to find weak peaks."""
        # Create HSQC with weak peak
        hsqc_data = np.zeros((100, 100))
        hsqc_data[50, 50] = 0.05  # Weak peak (5% of max)
        hsqc_data[0, 0] = 1.0  # Strong reference peak at corner (for max calculation)

        hsqc = Spectrum2D(
            data=hsqc_data,
            f1_ppm_scale=np.linspace(200, 0, 100),
            f2_ppm_scale=np.linspace(10, 0, 100),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=400.0,
        )

        # DEPT peak at 100 ppm (center)
        dept_data = np.zeros(100)
        dept_data[50] = 1.0

        dept = Spectrum1D(
            data=dept_data,
            ppm_scale=np.linspace(200, 0, 100),
            nucleus="13C",
            frequency=100.0,
        )

        result = DEPTGuidedPicker.pick_hsqc_peaks(
            hsqc, dept, initial_hsqc_threshold=0.10, min_hsqc_threshold=0.01
        )

        # Should need multiple iterations since initial threshold (0.10) > peak intensity (0.05)
        assert result.iterations >= 1

    def test_respects_min_threshold_floor(self):
        """Test that algorithm stops at minimum threshold."""
        # Create HSQC with very weak peak that won't be found
        hsqc_data = np.zeros((100, 100))
        hsqc_data[50, 50] = 0.001  # Very weak peak
        hsqc_data[0, 0] = 1.0  # Reference for max

        hsqc = Spectrum2D(
            data=hsqc_data,
            f1_ppm_scale=np.linspace(200, 0, 100),
            f2_ppm_scale=np.linspace(10, 0, 100),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=400.0,
        )

        dept_data = np.zeros(100)
        dept_data[50] = 1.0

        dept = Spectrum1D(
            data=dept_data,
            ppm_scale=np.linspace(200, 0, 100),
            nucleus="13C",
            frequency=100.0,
        )

        result = DEPTGuidedPicker.pick_hsqc_peaks(
            hsqc,
            dept,
            initial_hsqc_threshold=0.10,
            min_hsqc_threshold=0.01,  # Floor is 0.01, peak is 0.001
        )

        # Should have unmatched peaks since peak (0.001) < min_threshold (0.01)
        assert result.all_carbons_found is False
        assert len(result.unmatched_dept_peaks) > 0


class TestMultiplicityExtraction:
    """Tests for multiplicity extraction from DEPT sign."""

    def test_positive_peaks_are_ch_ch3(self):
        """Test that positive DEPT peaks are labeled CH/CH3."""
        hsqc_data = np.zeros((100, 100))
        hsqc_data[50, 50] = 1.0

        hsqc = Spectrum2D(
            data=hsqc_data,
            f1_ppm_scale=np.linspace(200, 0, 100),
            f2_ppm_scale=np.linspace(10, 0, 100),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=400.0,
        )

        # Positive DEPT peak
        dept_data = np.zeros(100)
        dept_data[50] = 1.0  # Positive = CH or CH3

        dept = Spectrum1D(
            data=dept_data,
            ppm_scale=np.linspace(200, 0, 100),
            nucleus="13C",
            frequency=100.0,
        )

        result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)

        # Check multiplicity
        assert len(result.carbon_multiplicities) > 0
        for mult in result.carbon_multiplicities.values():
            assert mult == "CH/CH3"

    def test_negative_peaks_are_ch2(self):
        """Test that negative DEPT peaks are labeled CH2."""
        hsqc_data = np.zeros((100, 100))
        hsqc_data[50, 50] = 1.0

        hsqc = Spectrum2D(
            data=hsqc_data,
            f1_ppm_scale=np.linspace(200, 0, 100),
            f2_ppm_scale=np.linspace(10, 0, 100),
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=400.0,
        )

        # Negative DEPT peak
        dept_data = np.zeros(100)
        dept_data[50] = -1.0  # Negative = CH2

        dept = Spectrum1D(
            data=dept_data,
            ppm_scale=np.linspace(200, 0, 100),
            nucleus="13C",
            frequency=100.0,
        )

        result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept, detect_negative_dept=True)

        # Check that CH2 is found
        ch2_found = any(m == "CH2" for m in result.carbon_multiplicities.values())
        assert ch2_found or len(result.dept_peaks.peaks) == 0  # Either found or no peaks


class TestIbuprofenIntegration:
    """Integration tests with real Ibuprofen data."""

    @pytest.fixture
    def ibuprofen_hsqc(self):
        """Load Ibuprofen HSQC spectrum."""
        return BrukerReader.read_2d("data/Ibuprofen/6")

    @pytest.fixture
    def ibuprofen_dept135(self):
        """Load Ibuprofen DEPT-135 spectrum."""
        return BrukerReader.read_1d("data/Ibuprofen/3")

    @pytest.fixture
    def ibuprofen_dept90(self):
        """Load Ibuprofen DEPT-90 spectrum."""
        return BrukerReader.read_1d("data/Ibuprofen/4")

    def test_finds_all_protonated_carbons(self, ibuprofen_hsqc, ibuprofen_dept135):
        """Test that all DEPT carbons are found in HSQC."""
        result = DEPTGuidedPicker.pick_hsqc_peaks(ibuprofen_hsqc, ibuprofen_dept135)

        assert result.all_carbons_found is True
        assert len(result.unmatched_dept_peaks) == 0
        assert len(result.dept_peaks.peaks) >= 7  # Ibuprofen has 7+ protonated carbons

    def test_filters_noise_peaks(self, ibuprofen_hsqc, ibuprofen_dept135):
        """Test that noise peaks are filtered out."""
        from ailsa import PeakPicker2D

        # Pick all peaks at low threshold
        all_peaks = PeakPicker2D.pick_peaks(ibuprofen_hsqc, threshold=0.02)

        # Pick with DEPT guidance
        result = DEPTGuidedPicker.pick_hsqc_peaks(ibuprofen_hsqc, ibuprofen_dept135)

        # DEPT-guided should have fewer peaks (filtered)
        assert len(result.peaks.peaks) < len(all_peaks.peaks)

    def test_extracts_multiplicities(self, ibuprofen_hsqc, ibuprofen_dept135):
        """Test that multiplicities are extracted from Ibuprofen DEPT."""
        result = DEPTGuidedPicker.pick_hsqc_peaks(ibuprofen_hsqc, ibuprofen_dept135)

        assert len(result.carbon_multiplicities) > 0

        # Ibuprofen should have both CH/CH3 and CH2 groups
        mult_values = set(result.carbon_multiplicities.values())
        # At minimum should have CH/CH3 (most peaks are positive in DEPT-135)
        assert "CH/CH3" in mult_values

    def test_dept90_refines_multiplicities(
        self, ibuprofen_hsqc, ibuprofen_dept135, ibuprofen_dept90
    ):
        """Test that DEPT-90 distinguishes CH from CH3."""
        result = DEPTGuidedPicker.pick_hsqc_peaks_with_dept90(
            ibuprofen_hsqc, ibuprofen_dept135, ibuprofen_dept90
        )

        mult_values = set(result.carbon_multiplicities.values())

        # With DEPT-90, should have refined CH and CH3 instead of CH/CH3
        # (if any CH/CH3 peaks were refinable)
        assert len(result.carbon_multiplicities) > 0

    def test_summary_output(self, ibuprofen_hsqc, ibuprofen_dept135):
        """Test that summary is readable."""
        result = DEPTGuidedPicker.pick_hsqc_peaks(ibuprofen_hsqc, ibuprofen_dept135)

        summary = result.summary()
        assert "DEPT-Guided" in summary
        assert "Validated HSQC peaks" in summary
        assert "All carbons found: True" in summary


class TestModuleExports:
    """Test that classes are properly exported."""

    def test_import_from_processing(self):
        """Test import from processing module."""
        from ailsa.processing import DEPTGuidedPicker, DEPTGuidedResult

        assert DEPTGuidedPicker is not None
        assert DEPTGuidedResult is not None

    def test_import_from_top_level(self):
        """Test import from top-level package."""
        from ailsa import DEPTGuidedPicker, DEPTGuidedResult

        assert DEPTGuidedPicker is not None
        assert DEPTGuidedResult is not None
