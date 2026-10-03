"""Tests for NMR data models."""

import numpy as np
import pytest

from ailsa.models import Peak1D, Peak2D, PeakList1D, PeakList2D, Spectrum1D, Spectrum2D


class TestSpectrum1D:
    """Tests for Spectrum1D model."""

    def test_creation(self, sample_spectrum_1d: Spectrum1D) -> None:
        """Test Spectrum1D can be created with valid data."""
        assert sample_spectrum_1d.nucleus == "1H"
        assert sample_spectrum_1d.frequency == 600.0
        assert sample_spectrum_1d.solvent == "CDCl3"
        assert len(sample_spectrum_1d.data) == 4096
        assert len(sample_spectrum_1d.ppm_scale) == 4096

    def test_numpy_conversion(self) -> None:
        """Test that list inputs are converted to numpy arrays."""
        spectrum = Spectrum1D(
            data=[1.0, 2.0, 3.0],
            ppm_scale=[10.0, 5.0, 0.0],
            nucleus="1H",
            frequency=400.0,
        )
        assert isinstance(spectrum.data, np.ndarray)
        assert isinstance(spectrum.ppm_scale, np.ndarray)
        assert spectrum.data.dtype == np.float64

    def test_invalid_nucleus(self) -> None:
        """Test that invalid nucleus raises ValueError."""
        with pytest.raises(ValueError, match="Unknown nucleus"):
            Spectrum1D(
                data=[1.0, 2.0],
                ppm_scale=[10.0, 0.0],
                nucleus="invalid",
                frequency=400.0,
            )

    def test_json_serialization(self, sample_spectrum_1d: Spectrum1D) -> None:
        """Test JSON round-trip serialization."""
        d = sample_spectrum_1d.to_dict()
        restored = Spectrum1D.from_dict(d)

        assert restored.nucleus == sample_spectrum_1d.nucleus
        assert restored.frequency == sample_spectrum_1d.frequency
        assert np.allclose(restored.data, sample_spectrum_1d.data)
        assert np.allclose(restored.ppm_scale, sample_spectrum_1d.ppm_scale)


class TestSpectrum2D:
    """Tests for Spectrum2D model."""

    def test_creation(self, sample_spectrum_2d: Spectrum2D) -> None:
        """Test Spectrum2D can be created with valid data."""
        assert sample_spectrum_2d.f1_nucleus == "13C"
        assert sample_spectrum_2d.f2_nucleus == "1H"
        assert sample_spectrum_2d.experiment_type == "HSQC"
        assert sample_spectrum_2d.data.shape == (256, 1024)

    def test_invalid_experiment_type(self) -> None:
        """Test that invalid experiment type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown experiment type"):
            Spectrum2D(
                data=[[1.0, 2.0], [3.0, 4.0]],
                f1_ppm_scale=[200.0, 0.0],
                f2_ppm_scale=[12.0, 0.0],
                f1_nucleus="13C",
                f2_nucleus="1H",
                experiment_type="INVALID",
                frequency=600.0,
            )

    def test_json_serialization(self, sample_spectrum_2d: Spectrum2D) -> None:
        """Test JSON round-trip serialization."""
        d = sample_spectrum_2d.to_dict()
        restored = Spectrum2D.from_dict(d)

        assert restored.experiment_type == sample_spectrum_2d.experiment_type
        assert np.allclose(restored.data, sample_spectrum_2d.data)


class TestPeak1D:
    """Tests for Peak1D model."""

    def test_creation(self, sample_peak_1d: Peak1D) -> None:
        """Test Peak1D can be created."""
        assert sample_peak_1d.position == 7.26
        assert sample_peak_1d.intensity == 1000.0
        assert sample_peak_1d.multiplicity == "s"

    def test_multiplicity_normalization(self) -> None:
        """Test that multiplicity is normalized to lowercase."""
        peak = Peak1D(position=1.0, intensity=100.0, multiplicity="D")
        assert peak.multiplicity == "d"

    def test_invalid_multiplicity(self) -> None:
        """Test that invalid multiplicity raises ValueError."""
        with pytest.raises(ValueError, match="Unknown multiplicity"):
            Peak1D(position=1.0, intensity=100.0, multiplicity="invalid")


class TestPeak2D:
    """Tests for Peak2D model."""

    def test_creation(self, sample_peak_2d: Peak2D) -> None:
        """Test Peak2D can be created."""
        assert sample_peak_2d.f1_position == 125.0
        assert sample_peak_2d.f2_position == 7.26

    def test_position_property(self, sample_peak_2d: Peak2D) -> None:
        """Test position property returns tuple."""
        assert sample_peak_2d.position == (125.0, 7.26)


class TestPeakList1D:
    """Tests for PeakList1D model."""

    def test_creation(self, sample_peak_list_1d: PeakList1D) -> None:
        """Test PeakList1D can be created."""
        assert len(sample_peak_list_1d.peaks) == 3
        assert sample_peak_list_1d.nucleus == "1H"

    def test_json_serialization(self, sample_peak_list_1d: PeakList1D) -> None:
        """Test JSON round-trip serialization."""
        d = sample_peak_list_1d.to_dict()
        restored = PeakList1D.from_dict(d)

        assert len(restored.peaks) == len(sample_peak_list_1d.peaks)
        assert restored.nucleus == sample_peak_list_1d.nucleus


class TestPeakList2D:
    """Tests for PeakList2D model."""

    def test_creation(self, sample_peak_list_2d: PeakList2D) -> None:
        """Test PeakList2D can be created."""
        assert len(sample_peak_list_2d.peaks) == 3
        assert sample_peak_list_2d.experiment_type == "HSQC"

    def test_json_serialization(self, sample_peak_list_2d: PeakList2D) -> None:
        """Test JSON round-trip serialization."""
        d = sample_peak_list_2d.to_dict()
        restored = PeakList2D.from_dict(d)

        assert len(restored.peaks) == len(sample_peak_list_2d.peaks)
        assert restored.experiment_type == sample_peak_list_2d.experiment_type
