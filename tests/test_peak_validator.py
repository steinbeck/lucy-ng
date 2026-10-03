"""Tests for peak validation."""

from pathlib import Path

import pytest

from ailsa.models import Peak1D, Peak2D, PeakList1D, PeakList2D
from ailsa.processing.peak_validator import PeakValidator, ValidationResult
from ailsa.processing import PeakPicker2D, AdaptivePeakPicker
from ailsa.readers import BrukerReader

# Test data paths
DATA_DIR = Path(__file__).parent.parent / "data"
IBUPROFEN_13C = DATA_DIR / "Ibuprofen" / "2"
IBUPROFEN_1H = DATA_DIR / "Ibuprofen" / "1"
IBUPROFEN_HSQC = DATA_DIR / "Ibuprofen" / "6"
IBUPROFEN_COSY = DATA_DIR / "Ibuprofen" / "5"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_summary_output(self) -> None:
        """Test that summary produces readable output."""
        result = ValidationResult(
            matched_peaks=[],
            unmatched_2d_peaks=[],
            unmatched_1d_peaks=[],
            match_rate=0.75,
            tolerance_used=0.5,
        )
        summary = result.summary()
        assert "75.0%" in summary
        assert "0.5 ppm" in summary


class TestPeakValidatorHSQC:
    """Tests for HSQC validation."""

    def test_validate_hsqc_perfect_match(self) -> None:
        """Test validation where all peaks match."""
        # Create mock data with matching peaks
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0),
                Peak2D(f1_position=30.0, f2_position=1.2, intensity=800.0),
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[
                Peak1D(position=45.0, intensity=5000.0),
                Peak1D(position=30.0, intensity=4000.0),
            ],
            nucleus="13C",
        )

        result = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        assert result.match_rate == 1.0
        assert len(result.matched_peaks) == 2
        assert len(result.unmatched_2d_peaks) == 0

    def test_validate_hsqc_partial_match(self) -> None:
        """Test validation where some peaks match."""
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0),
                Peak2D(f1_position=100.0, f2_position=7.0, intensity=500.0),  # No match
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[Peak1D(position=45.0, intensity=5000.0)],
            nucleus="13C",
        )

        result = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        assert result.match_rate == 0.5
        assert len(result.matched_peaks) == 1
        assert len(result.unmatched_2d_peaks) == 1
        assert result.unmatched_2d_peaks[0].f1_position == 100.0

    def test_validate_hsqc_no_match(self) -> None:
        """Test validation where no peaks match."""
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0),
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[Peak1D(position=100.0, intensity=5000.0)],
            nucleus="13C",
        )

        result = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        assert result.match_rate == 0.0
        assert len(result.matched_peaks) == 0
        assert len(result.unmatched_2d_peaks) == 1

    def test_validate_hsqc_tolerance(self) -> None:
        """Test that tolerance affects matching."""
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0),
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[Peak1D(position=45.3, intensity=5000.0)],  # 0.3 ppm away
            nucleus="13C",
        )

        # With tight tolerance, no match
        result_tight = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.2
        )
        assert result_tight.match_rate == 0.0

        # With loose tolerance, match
        result_loose = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )
        assert result_loose.match_rate == 1.0

    def test_validate_hsqc_wrong_experiment_type(self) -> None:
        """Test that wrong experiment type raises error."""
        cosy_peaks = PeakList2D(
            peaks=[],
            f1_nucleus="1H",
            f2_nucleus="1H",
            experiment_type="COSY",
        )
        carbon_peaks = PeakList1D(peaks=[], nucleus="13C")

        with pytest.raises(ValueError, match="Expected HSQC"):
            PeakValidator.validate_hsqc_against_1d(cosy_peaks, carbon_peaks)

    def test_validate_hsqc_wrong_nucleus(self) -> None:
        """Test that wrong nucleus raises error."""
        hsqc_peaks = PeakList2D(
            peaks=[],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        proton_peaks = PeakList1D(peaks=[], nucleus="1H")

        with pytest.raises(ValueError, match="Expected 13C"):
            PeakValidator.validate_hsqc_against_1d(hsqc_peaks, proton_peaks)

    def test_unmatched_1d_peaks(self) -> None:
        """Test that unmatched 1D peaks are tracked."""
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0),
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[
                Peak1D(position=45.0, intensity=5000.0),  # Matched
                Peak1D(position=180.0, intensity=3000.0),  # Unmatched (quaternary)
            ],
            nucleus="13C",
        )

        result = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        assert len(result.unmatched_1d_peaks) == 1
        assert result.unmatched_1d_peaks[0].position == 180.0


class TestPeakValidatorCOSY:
    """Tests for COSY validation."""

    def test_validate_cosy_both_dimensions(self) -> None:
        """Test COSY requires both F1 and F2 to match."""
        cosy_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=3.5, f2_position=1.2, intensity=1000.0),
            ],
            f1_nucleus="1H",
            f2_nucleus="1H",
            experiment_type="COSY",
        )
        proton_peaks = PeakList1D(
            peaks=[
                Peak1D(position=3.5, intensity=5000.0),
                Peak1D(position=1.2, intensity=4000.0),
            ],
            nucleus="1H",
        )

        result = PeakValidator.validate_cosy_against_1d(
            cosy_peaks, proton_peaks, tolerance=0.05
        )

        assert result.match_rate == 1.0
        assert len(result.matched_peaks) == 1

    def test_validate_cosy_one_dimension_fails(self) -> None:
        """Test COSY fails if only one dimension matches."""
        cosy_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=3.5, f2_position=1.2, intensity=1000.0),
            ],
            f1_nucleus="1H",
            f2_nucleus="1H",
            experiment_type="COSY",
        )
        proton_peaks = PeakList1D(
            peaks=[
                Peak1D(position=3.5, intensity=5000.0),
                # No peak at 1.2 ppm
            ],
            nucleus="1H",
        )

        result = PeakValidator.validate_cosy_against_1d(
            cosy_peaks, proton_peaks, tolerance=0.05
        )

        assert result.match_rate == 0.0
        assert len(result.unmatched_2d_peaks) == 1


class TestFilterValidatedPeaks:
    """Tests for peak filtering."""

    def test_filter_validated_peaks(self) -> None:
        """Test that filtering removes unvalidated peaks."""
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0),
                Peak2D(f1_position=100.0, f2_position=7.0, intensity=500.0),  # Artifact
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[Peak1D(position=45.0, intensity=5000.0)],
            nucleus="13C",
        )

        filtered = PeakValidator.filter_validated_peaks(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        assert len(filtered.peaks) == 1
        assert filtered.peaks[0].f1_position == 45.0
        assert filtered.experiment_type == "HSQC"

    def test_filter_preserves_metadata(self) -> None:
        """Test that filtering preserves peak list metadata."""
        hsqc_peaks = PeakList2D(
            peaks=[Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0)],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            spectrum_id="test-spectrum",
        )
        carbon_peaks = PeakList1D(
            peaks=[Peak1D(position=45.0, intensity=5000.0)],
            nucleus="13C",
        )

        filtered = PeakValidator.filter_validated_peaks(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        assert filtered.f1_nucleus == "13C"
        assert filtered.f2_nucleus == "1H"
        assert filtered.experiment_type == "HSQC"
        assert filtered.spectrum_id == "test-spectrum"


class TestMatchRateCalculation:
    """Tests for match rate calculation."""

    def test_match_rate_empty_list(self) -> None:
        """Test match rate with empty peak list."""
        hsqc_peaks = PeakList2D(
            peaks=[],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[Peak1D(position=45.0, intensity=5000.0)],
            nucleus="13C",
        )

        result = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        assert result.match_rate == 0.0

    def test_match_rate_calculation(self) -> None:
        """Test that match rate is calculated correctly."""
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.5, intensity=1000.0),
                Peak2D(f1_position=30.0, f2_position=1.5, intensity=800.0),
                Peak2D(f1_position=100.0, f2_position=7.0, intensity=500.0),
                Peak2D(f1_position=120.0, f2_position=7.5, intensity=400.0),
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        carbon_peaks = PeakList1D(
            peaks=[
                Peak1D(position=45.0, intensity=5000.0),
                Peak1D(position=30.0, intensity=4000.0),
            ],
            nucleus="13C",
        )

        result = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=0.5
        )

        # 2 out of 4 peaks match
        assert result.match_rate == 0.5


class TestIbuprofenIntegration:
    """Integration tests with real Ibuprofen NMR data."""

    def test_validate_hsqc_ibuprofen(self) -> None:
        """Test HSQC validation with real Ibuprofen data."""
        # Load spectra
        carbon_spectrum = BrukerReader.read_1d(IBUPROFEN_13C)
        hsqc_spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        # Pick peaks
        carbon_peaks = AdaptivePeakPicker.pick_peaks(carbon_spectrum, threshold=0.02)
        hsqc_peaks = PeakPicker2D.pick_peaks(hsqc_spectrum, threshold=0.05)

        # Validate
        result = PeakValidator.validate_hsqc_against_1d(
            hsqc_peaks, carbon_peaks, tolerance=1.0
        )

        # Ibuprofen should have reasonable match rate
        # Some HSQC peaks may be artifacts, so we don't expect 100%
        assert result.match_rate >= 0.3  # At least 30% should match
        assert len(result.matched_peaks) >= 5  # At least 5 valid peaks

        # Print validation report for debugging
        print(f"\n{result.summary()}")
        print(f"\nMatched peaks:")
        for peak_2d, peak_1d in result.matched_peaks[:5]:
            delta = abs(peak_2d.f1_position - peak_1d.position)
            print(f"  HSQC {peak_2d.f1_position:.1f} ppm → 1D {peak_1d.position:.2f} ppm (Δ={delta:.2f})")

    def test_filter_ibuprofen_hsqc(self) -> None:
        """Test filtering Ibuprofen HSQC peaks."""
        carbon_spectrum = BrukerReader.read_1d(IBUPROFEN_13C)
        hsqc_spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)

        carbon_peaks = AdaptivePeakPicker.pick_peaks(carbon_spectrum, threshold=0.02)
        hsqc_peaks = PeakPicker2D.pick_peaks(hsqc_spectrum, threshold=0.05)

        # Filter to remove artifacts
        filtered_hsqc = PeakValidator.filter_validated_peaks(
            hsqc_peaks, carbon_peaks, tolerance=1.0
        )

        # Filtered list should have fewer peaks
        assert len(filtered_hsqc.peaks) <= len(hsqc_peaks.peaks)
        # But should still have some peaks
        assert len(filtered_hsqc.peaks) >= 5

        print(f"\nOriginal: {len(hsqc_peaks.peaks)} peaks")
        print(f"Filtered: {len(filtered_hsqc.peaks)} peaks")
        print(f"Removed: {len(hsqc_peaks.peaks) - len(filtered_hsqc.peaks)} likely artifacts")
