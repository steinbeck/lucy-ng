"""Tests for detect_intensity_symmetry (FIX-05).

Verifies that CASE9's two 2C aromatic CH peaks are flagged as equivalence
candidates while single-carbon peaks are not.
"""

import pytest

from ailsa.models import Peak1D
from ailsa.processing.peak_picker import detect_intensity_symmetry


# Synthetic fixtures — same style as test_symmetry_analysis.py


@pytest.fixture
def case9_like_aromatic_peaks() -> list[Peak1D]:
    """CASE9 13C peaks: two 2C arom-CH (high intensity) + two 1C arom-Cq (low)."""
    return [
        # 2C aromatic CH — ratio ~100x median of class
        Peak1D(position=129.94, intensity=1.81e7),
        Peak1D(position=125.31, intensity=1.72e7),
        # 1C aromatic Cq — below threshold
        Peak1D(position=150.80, intensity=3.1e6),
        Peak1D(position=130.16, intensity=2.9e6),
        # Non-aromatic (below 100 ppm) — must NOT be returned
        Peak1D(position=22.10, intensity=1.70e7),
    ]


@pytest.fixture
def aromatic_ch_ppms_case9() -> list[float]:
    """HSQC-confirmed aromatic CH positions for CASE9."""
    return [129.94, 125.31]  # the two 2C aromatic CH from CASE9 HSQC


class TestDetectIntensitySymmetry:
    """Unit tests for detect_intensity_symmetry."""

    def test_case9_flags_two_candidates(
        self,
        case9_like_aromatic_peaks: list[Peak1D],
        aromatic_ch_ppms_case9: list[float],
    ) -> None:
        """Both 2C aromatic CH peaks must be flagged."""
        result = detect_intensity_symmetry(
            case9_like_aromatic_peaks, aromatic_ch_ppms_case9
        )
        assert len(result) == 2
        ppms = [r[0] for r in result]
        assert any(abs(ppm - 129.94) < 1.0 for ppm in ppms)
        assert any(abs(ppm - 125.31) < 1.0 for ppm in ppms)

    def test_estimated_carbon_count_is_2(
        self,
        case9_like_aromatic_peaks: list[Peak1D],
        aromatic_ch_ppms_case9: list[float],
    ) -> None:
        """Estimated carbon count for 2C candidates must be 2."""
        result = detect_intensity_symmetry(
            case9_like_aromatic_peaks, aromatic_ch_ppms_case9
        )
        for _, ratio, count in result:
            assert count == 2, f"Expected count=2, got {count} (ratio={ratio:.1f})"

    def test_non_aromatic_peaks_excluded(
        self,
        case9_like_aromatic_peaks: list[Peak1D],
        aromatic_ch_ppms_case9: list[float],
    ) -> None:
        """Peaks outside 100-165 ppm must not appear in results."""
        result = detect_intensity_symmetry(
            case9_like_aromatic_peaks, aromatic_ch_ppms_case9
        )
        for ppm, _, _ in result:
            assert 100.0 <= ppm <= 165.0

    def test_empty_aromatic_ch_list_returns_empty(self) -> None:
        """No HSQC-confirmed aromatics -> empty result."""
        peaks = [Peak1D(position=129.0, intensity=1e7)]
        result = detect_intensity_symmetry(peaks, aromatic_ch_ppms=[])
        assert result == []

    def test_single_aromatic_ch_returns_empty(self) -> None:
        """Single aromatic CH: no class median comparison possible -> empty."""
        peaks = [Peak1D(position=129.0, intensity=1e7)]
        result = detect_intensity_symmetry(peaks, aromatic_ch_ppms=[129.0])
        assert result == []
