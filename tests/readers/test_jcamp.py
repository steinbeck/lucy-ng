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
COSY_TRIMMED = FIXTURE_DIR / "C20H32O2_COSY_trimmed.dx"
HMBC_TRIMMED = FIXTURE_DIR / "C20H32O2_HMBC_trimmed.dx"
NOESY_TRIMMED = FIXTURE_DIR / "C20H32O2_NOESY_trimmed.dx"
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
        """Reader's fail-loud ppm-axis assertion rejects implausible/non-reversed axes (D-04).

        Phase 103 (D-09) widened the 13C upper bound 230.0 -> 250.0 so the
        real HMBC file's legitimate ~234.81 ppm acquisition window can be
        read. The negative controls that genuinely hold post-widening are
        a >250 ppm axis and a raw-**Hz** axis (the real HMBC ``FIRST``/
        ``LAST`` values 29516.31/-574.76 -- the "forgot to divide by SF"
        bug class this guard exists to catch). This coarse net does NOT
        and never did catch the ~0.447 ppm SFO-vs-SF divisor bug (per
        ``_assert_plausible_ppm_axis``'s own docstring) -- that remains
        the JC-02 1D cross-check's job, not this test's.
        """
        from lucy_ng.readers.jcamp import _assert_plausible_ppm_axis

        # Plausible, correctly-reversed 13C axis: no error.
        _assert_plausible_ppm_axis(np.array([175.0, 100.0, 0.0]), "13C")

        # Non-reversed (ascending) axis must raise.
        with pytest.raises(ValueError):
            _assert_plausible_ppm_axis(np.array([0.0, 100.0, 175.0]), "13C")

        # Implausible out-of-range axis must raise.
        with pytest.raises(ValueError):
            _assert_plausible_ppm_axis(np.array([5000.0, 0.0]), "13C")

        # The real HMBC window (verified [-4.57, 234.81] ppm) is accepted.
        _assert_plausible_ppm_axis(np.array([234.81, 100.0, -4.57]), "13C")

        # The widened bound is inclusive at both ends.
        _assert_plausible_ppm_axis(np.array([250.0, 0.0, -15.0]), "13C")

        # The widened bound is still a bound -- not "raise the ceiling
        # until it stops complaining".
        with pytest.raises(ValueError):
            _assert_plausible_ppm_axis(np.array([260.0, 0.0]), "13C")

        # A raw-Hz axis (real HMBC FIRST/LAST left undivided by SF) is
        # still rejected -- the guard still catches the divisor-bug class.
        with pytest.raises(ValueError):
            _assert_plausible_ppm_axis(np.array([29516.31, -574.76]), "13C")

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


class TestJcampReaderHomonuclear:
    """Tests for the _resolve_dim homonuclear positional fallback (102-01 Task 2).

    _resolve_dim's ambiguous-nucleus branch previously raised unconditionally
    for any homonuclear 2D file (both dims sharing one nucleus, e.g. COSY/
    NOESY). This class proves the positional fallback (procs_index=0=F2/
    direct, procs_index=1=F1/indirect) against committed ground truth: the
    convention itself is proven on the HETERONUCLEAR HSQC fixture (where
    nucleus matching independently disambiguates), then the resulting COSY
    axes are cross-checked twice against committed ground truth (diagonal
    self-consistency and the 1H 1D reference) -- not just "doesn't raise".
    """

    def test_heteronuclear_positional_convention_holds(self) -> None:
        """procs_index=0/1 reproduce the HSQC fixture's unique nucleus-match values.

        This is the load-bearing convention proof: on a heteronuclear file,
        nucleus matching independently resolves each dimension, so we can
        assert the positional hint agrees with it exactly -- proving
        "index 0 = F2/direct, index 1 = F1/indirect" on data where the
        answer is independently knowable, not merely assumed.
        """
        from lucy_ng.readers.jcamp import _read_metadata, _resolve_dim

        inner = _read_metadata(HSQC_TRIMMED)

        unique_1h = _resolve_dim(inner, "1H")
        positional_1h = _resolve_dim(inner, "1H", procs_index=0)
        assert unique_1h == positional_1h
        assert unique_1h == (7.050608, 499.92)

        unique_13c = _resolve_dim(inner, "13C")
        positional_13c = _resolve_dim(inner, "13C", procs_index=1)
        assert unique_13c == positional_13c
        assert unique_13c == (174.9902, 125.704983984)

    def test_read_2d_homonuclear_cosy(self) -> None:
        """JcampReader.read_2d() on the COSY fixture does not raise."""
        from lucy_ng.readers.jcamp import JcampReader

        spectrum = JcampReader.read_2d(COSY_TRIMMED)
        assert spectrum.data.shape == (16, 2048)
        assert spectrum.f1_nucleus == "1H"
        assert spectrum.f2_nucleus == "1H"
        assert spectrum.experiment_type == "COSY"
        assert spectrum.f1_ppm_scale[0] > spectrum.f1_ppm_scale[-1]
        assert spectrum.f2_ppm_scale[0] > spectrum.f2_ppm_scale[-1]

    def test_cosy_diagonal_self_consistency(self) -> None:
        """The COSY window's strongest peak sits on the diagonal (F1 ppm ~= F2 ppm).

        Measured actual values (102-01-PLAN.md <interfaces>): F1=1.4792,
        F2=1.4796 -- a real COSY diagonal peak. A wrong-by-orders axis on
        either dimension breaks this self-consistency check.
        """
        from lucy_ng.readers.jcamp import JcampReader

        spectrum = JcampReader.read_2d(COSY_TRIMMED)
        row, col = np.unravel_index(
            np.argmax(np.abs(spectrum.data)), spectrum.data.shape
        )
        f1_ppm = float(spectrum.f1_ppm_scale[row])
        f2_ppm = float(spectrum.f2_ppm_scale[col])
        assert abs(f1_ppm - f2_ppm) < PPM_CROSS_CHECK_TOLERANCE_1H

    def test_cosy_axes_match_1d_reference(self) -> None:
        """Both COSY axes (F1 and F2, both 1H) cross-check against the 1D 1H reference.

        Mirrors TestJcampReaderPpmCrossCheck.test_read_2d_ppm_axes_match_1d_reference
        exactly -- absolute-truth cross-check, not just internal
        self-consistency.
        """
        from lucy_ng.readers.jcamp import JcampReader

        spectrum = JcampReader.read_2d(COSY_TRIMMED)
        ref_1h = JcampReader.read_1d(REF_1H)

        f1_peak_idx = int(np.argmax(spectrum.data.max(axis=1)))
        f2_peak_idx = int(np.argmax(spectrum.data.max(axis=0)))
        f1_peak_ppm = float(spectrum.f1_ppm_scale[f1_peak_idx])
        f2_peak_ppm = float(spectrum.f2_ppm_scale[f2_peak_idx])

        f1_ref_idx = int(np.argmin(np.abs(ref_1h.ppm_scale - f1_peak_ppm)))
        f2_ref_idx = int(np.argmin(np.abs(ref_1h.ppm_scale - f2_peak_ppm)))

        assert (
            abs(float(ref_1h.ppm_scale[f1_ref_idx]) - f1_peak_ppm)
            < PPM_CROSS_CHECK_TOLERANCE_1H
        )
        assert (
            abs(float(ref_1h.ppm_scale[f2_ref_idx]) - f2_peak_ppm)
            < PPM_CROSS_CHECK_TOLERANCE_1H
        )

    def test_read_2d_homonuclear_noesy(self) -> None:
        """Phase 102 must READ NOESY fine even though D-06 skips picking it."""
        from lucy_ng.readers.jcamp import JcampReader

        spectrum = JcampReader.read_2d(NOESY_TRIMMED)
        assert spectrum.experiment_type == "NOESY"
        assert spectrum.data.shape == (16, 2048)

    def test_ambiguous_without_hint_still_raises(self) -> None:
        """The fail-loud default is preserved when no procs_index hint is supplied (T-102-02)."""
        from lucy_ng.readers.jcamp import _read_metadata, _resolve_dim

        inner = _read_metadata(COSY_TRIMMED)
        with pytest.raises(ValueError, match="Ambiguous nucleus"):
            _resolve_dim(inner, "1H")


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
