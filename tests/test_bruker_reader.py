"""Tests for Bruker NMR file reader."""

from pathlib import Path

import numpy as np
import pytest

from ailsa.readers.bruker import BrukerReader

# Test data paths
DATA_DIR = Path(__file__).parent.parent / "data"
IBUPROFEN_1H = DATA_DIR / "Ibuprofen" / "1"
IBUPROFEN_13C = DATA_DIR / "Ibuprofen" / "2"


class TestBrukerReader1H:
    """Tests for reading 1H NMR spectra."""

    def test_read_1h_spectrum_nucleus(self) -> None:
        """Test that 1H spectrum has correct nucleus."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert spectrum.nucleus == "1H"

    def test_read_1h_spectrum_frequency(self) -> None:
        """Test that 1H spectrum has correct frequency (~500 MHz)."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert 499.0 < spectrum.frequency < 500.0

    def test_read_1h_spectrum_solvent(self) -> None:
        """Test that 1H spectrum has correct solvent."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert spectrum.solvent == "CDCl3"

    def test_read_1h_spectrum_data_not_empty(self) -> None:
        """Test that 1H spectrum data is not empty."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert len(spectrum.data) > 0
        assert not np.all(spectrum.data == 0)

    def test_read_1h_spectrum_ppm_scale_length(self) -> None:
        """Test that ppm scale has same length as data."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert len(spectrum.ppm_scale) == len(spectrum.data)

    def test_read_1h_ppm_scale_range(self) -> None:
        """Test that 1H ppm range is reasonable (roughly -1 to 14 ppm)."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        ppm_min = spectrum.ppm_scale.min()
        ppm_max = spectrum.ppm_scale.max()
        # 1H spectra typically run from -1 to 14 ppm
        assert ppm_min > -5
        assert ppm_max < 20


class TestBrukerReader13C:
    """Tests for reading 13C NMR spectra."""

    def test_read_13c_spectrum_nucleus(self) -> None:
        """Test that 13C spectrum has correct nucleus."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_13C)
        assert spectrum.nucleus == "13C"

    def test_read_13c_spectrum_frequency(self) -> None:
        """Test that 13C spectrum has correct frequency (~125 MHz)."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_13C)
        assert 125.0 < spectrum.frequency < 126.0

    def test_read_13c_spectrum_data_populated(self) -> None:
        """Test that 13C spectrum has data and ppm scale."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_13C)
        assert len(spectrum.data) > 0
        assert len(spectrum.ppm_scale) == len(spectrum.data)


class TestBrukerReaderMetadata:
    """Tests for metadata extraction."""

    def test_metadata_pulse_program(self) -> None:
        """Test that pulse program is extracted."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert "pulse_program" in spectrum.metadata
        assert spectrum.metadata["pulse_program"] == "zg30"

    def test_metadata_num_scans(self) -> None:
        """Test that number of scans is extracted."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert "num_scans" in spectrum.metadata
        assert spectrum.metadata["num_scans"] == 64

    def test_metadata_temperature(self) -> None:
        """Test that temperature is extracted."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert "temperature" in spectrum.metadata
        assert spectrum.metadata["temperature"] == 298


class TestBrukerReaderErrors:
    """Tests for error handling."""

    def test_invalid_directory(self) -> None:
        """Test that FileNotFoundError is raised for non-existent path."""
        with pytest.raises(FileNotFoundError):
            BrukerReader.read_1d("/nonexistent/path")

    def test_invalid_directory_message(self) -> None:
        """Test that error message includes the path."""
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            BrukerReader.read_1d("/nonexistent/path")


# 2D test data paths
IBUPROFEN_COSY = DATA_DIR / "Ibuprofen" / "5"
IBUPROFEN_HSQC = DATA_DIR / "Ibuprofen" / "6"
IBUPROFEN_HMBC = DATA_DIR / "Ibuprofen" / "7"
HYDROXY_NOESY = DATA_DIR / "4-Hydroxy-3-Iodo-biphenyl" / "8"


class TestBrukerReader2D:
    """Tests for reading 2D NMR spectra."""

    def test_read_hsqc_shape(self) -> None:
        """Test that HSQC data is a 2D array."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        assert len(spectrum.data.shape) == 2
        assert spectrum.data.shape[0] > 0
        assert spectrum.data.shape[1] > 0

    def test_read_hsqc_nuclei(self) -> None:
        """Test that HSQC has correct nuclei (13C in F1, 1H in F2)."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        assert spectrum.f1_nucleus == "13C"
        assert spectrum.f2_nucleus == "1H"

    def test_read_hsqc_experiment_type(self) -> None:
        """Test that HSQC experiment type is detected."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        assert spectrum.experiment_type == "HSQC"

    def test_read_hsqc_ppm_scales(self) -> None:
        """Test that F1/F2 ppm scales match data dimensions."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        f1_size, f2_size = spectrum.data.shape
        assert len(spectrum.f1_ppm_scale) == f1_size
        assert len(spectrum.f2_ppm_scale) == f2_size

    def test_read_hmbc_experiment_type(self) -> None:
        """Test that HMBC experiment type is detected."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HMBC)
        assert spectrum.experiment_type == "HMBC"

    def test_read_hmbc_nuclei(self) -> None:
        """Test that HMBC has correct nuclei."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HMBC)
        assert spectrum.f1_nucleus == "13C"
        assert spectrum.f2_nucleus == "1H"

    def test_read_cosy_nuclei(self) -> None:
        """Test that COSY has homonuclear 1H-1H."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_COSY)
        assert spectrum.f1_nucleus == "1H"
        assert spectrum.f2_nucleus == "1H"

    def test_read_cosy_experiment_type(self) -> None:
        """Test that COSY experiment type is detected."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_COSY)
        assert spectrum.experiment_type == "COSY"

    def test_read_noesy(self) -> None:
        """Test that NOESY experiment is detected correctly."""
        spectrum = BrukerReader.read_2d(HYDROXY_NOESY)
        assert spectrum.experiment_type == "NOESY"
        assert spectrum.f1_nucleus == "1H"
        assert spectrum.f2_nucleus == "1H"

    def test_read_2d_invalid_directory(self) -> None:
        """Test that FileNotFoundError is raised for non-existent path."""
        with pytest.raises(FileNotFoundError):
            BrukerReader.read_2d("/nonexistent/path")

    def test_read_2d_frequency(self) -> None:
        """Test that 2D spectrum has correct frequency."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        # F2 frequency should be 1H (~500 MHz)
        assert 499.0 < spectrum.frequency < 500.0

    def test_read_2d_metadata(self) -> None:
        """Test that 2D spectrum has metadata."""
        spectrum = BrukerReader.read_2d(IBUPROFEN_HSQC)
        assert "pulse_program" in spectrum.metadata
        assert "num_scans" in spectrum.metadata
