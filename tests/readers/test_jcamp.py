"""Tests for the JCAMP-DX reader (D-08 layer 2: integration on the trimmed real fixture).

Imports of `lucy_ng.readers.jcamp` / `lucy_ng.readers._jcampdx_decode` go
INSIDE test function bodies (WV-08 convention) so collection succeeds while
the target modules are still absent (Wave 0, RED per-test).
"""

from pathlib import Path

import numpy as np
import pytest

# Fixture paths (committed real data, see tests/fixtures/jcamp/_generate_fixture.py)
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "jcamp"
HSQC_TRIMMED = FIXTURE_DIR / "C20H32O2_HSQC_trimmed.dx"
REF_1H = FIXTURE_DIR / "C20H32O2_1H.dx"
REF_13C = FIXTURE_DIR / "C20H32O2_13C.dx"

# JC-02 cross-check tolerances (101-RESEARCH.md): tight enough to catch the
# naive Hz/frequency-divisor bug class (measured 0.447 ppm real error) with
# a wide safety margin, generous enough for real linewidths.
PPM_CROSS_CHECK_TOLERANCE_1H = 0.05  # ppm
PPM_CROSS_CHECK_TOLERANCE_13C = 0.10  # ppm


class TestJcampReader2D:
    """Tests for reading 2D JCAMP-DX NTUPLES spectra (JC-01, JC-02, JC-04)."""

    def test_read_2d_shape(self) -> None:
        """Trimmed HSQC fixture (16 real F1 pages, 2048 F2 points) decodes to (16, 2048)."""
        from lucy_ng.readers.jcamp import JcampReader

        spectrum = JcampReader.read_2d(HSQC_TRIMMED)
        assert spectrum.data.shape == (16, 2048)

    def test_read_2d_ppm_axis_assertion(self) -> None:
        """Reader's fail-loud ppm-axis assertion rejects implausible/non-reversed axes (D-04)."""
        from lucy_ng.readers.jcamp import _assert_plausible_ppm_axis

        # Plausible, correctly-reversed 13C axis: no error.
        _assert_plausible_ppm_axis(np.array([175.0, 100.0, 0.0]), "13C")

        # Non-reversed (ascending) axis must raise.
        with pytest.raises(ValueError):
            _assert_plausible_ppm_axis(np.array([0.0, 100.0, 175.0]), "13C")

        # Implausible out-of-range axis must raise.
        with pytest.raises(ValueError):
            _assert_plausible_ppm_axis(np.array([5000.0, 0.0]), "13C")

    def test_read_2d_yfactor_scaling(self) -> None:
        """A Y_FACTOR != 1 must be multiplied through decoded row intensities (Pitfall 2).

        The real HSQC fixture's own Y_FACTOR happens to be 1, so this scaling
        step must be exercised directly rather than via the fixture (a
        fixture whose Y_FACTOR is 1 would not catch a missing multiplication).
        """
        from lucy_ng.readers.jcamp import _apply_yfactor

        raw = [100.0, 105.0, 105.0, 102.0]
        scaled = _apply_yfactor(raw, 2.5)
        assert list(scaled) == [250.0, 262.5, 262.5, 255.0]


class TestJcampReaderPpmCrossCheck:
    """JC-02 load-bearing cross-check: 2D axes vs 1D reference peaks (D-03)."""

    def test_read_2d_ppm_axes_match_1d_reference(self) -> None:
        """Project the 2D onto each axis and match against verified 1D reference peaks.

        Verified real cross-peak (101-RESEARCH.md): 13C ~21.7-23.5 ppm,
        1H ~0.96-0.99 ppm -- genuine signal in the trimmed fixture's page window.
        """
        from lucy_ng.readers.jcamp import JcampReader

        spectrum_2d = JcampReader.read_2d(HSQC_TRIMMED)
        ref_1h = JcampReader.read_1d(REF_1H)
        ref_13c = JcampReader.read_1d(REF_13C)

        f1_peak_idx = int(np.argmax(spectrum_2d.data.max(axis=1)))
        f2_peak_idx = int(np.argmax(spectrum_2d.data.max(axis=0)))
        f1_peak_ppm = float(spectrum_2d.f1_ppm_scale[f1_peak_idx])
        f2_peak_ppm = float(spectrum_2d.f2_ppm_scale[f2_peak_idx])

        f1_ref_idx = int(np.argmin(np.abs(ref_13c.ppm_scale - f1_peak_ppm)))
        f2_ref_idx = int(np.argmin(np.abs(ref_1h.ppm_scale - f2_peak_ppm)))

        assert (
            abs(float(ref_13c.ppm_scale[f1_ref_idx]) - f1_peak_ppm)
            < PPM_CROSS_CHECK_TOLERANCE_13C
        )
        assert (
            abs(float(ref_1h.ppm_scale[f2_ref_idx]) - f2_peak_ppm)
            < PPM_CROSS_CHECK_TOLERANCE_1H
        )


class TestJcampReader1D:
    """Tests for reading 1D JCAMP-DX spectra (JC-03)."""

    def test_read_1d(self) -> None:
        """1H and 13C references decode to Spectrum1D with the correct nucleus."""
        from lucy_ng.readers.jcamp import JcampReader

        spectrum_1h = JcampReader.read_1d(REF_1H)
        assert spectrum_1h.nucleus == "1H"

        spectrum_13c = JcampReader.read_1d(REF_13C)
        assert spectrum_13c.nucleus == "13C"


class TestJcampReaderErrors:
    """Tests for error handling."""

    def test_invalid_path(self) -> None:
        """Test that FileNotFoundError is raised for a non-existent path."""
        from lucy_ng.readers.jcamp import JcampReader

        with pytest.raises(FileNotFoundError):
            JcampReader.read_1d("/nonexistent/path.dx")

    def test_invalid_path_message(self) -> None:
        """Test that the error message includes the path."""
        from lucy_ng.readers.jcamp import JcampReader

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            JcampReader.read_1d("/nonexistent/path.dx")
