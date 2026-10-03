"""FIX-08 regression tests: peak-picking integrity (Phase 81).

Three test classes:
  TestFIX08CASE9Integration  — CASE9/12 at snr_floor=5 (skipif external data missing)
  TestFIX08OvercountGuard    — synthetic overcount scenarios (always runs)
  TestFIX08CASE1Regression   — ibuprofen non-regression at snr_floor=5 (in-repo data)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.analysis.hydrogen_budget import HydrogenBudgetResult
from ailsa.analysis.intensity_reporter import IntensityReport
from ailsa.analysis.symmetry_analysis import SymmetryAnalysisResult
from ailsa.cli.analyze import analyze
from ailsa.processing.peak_picker import AdaptivePeakPicker
from ailsa.readers import BrukerReader

# In-repo CASE1 path (always available)
DATA_DIR = Path(__file__).parent.parent / "data"
CASE1_C13 = DATA_DIR / "Ibuprofen" / "2"

# CASE9 is outside the repo (see reference_test_data memory)
CASE9_C13 = Path(
    "/Users/steinbeck/Dropbox/develop/data/nmrdata"
    "/active-lucy-ng-testprojects/CASE9/12"
)


class TestFIX08CASE9Integration:
    """Integration regression: CASE9/12 re-picked at snr_floor=5 (FIX-08)."""

    @pytest.mark.skipif(
        not CASE9_C13.exists(),
        reason="CASE9 dataset not available on this machine",
    )
    def test_case9_snr5_peak_count(self) -> None:
        """Re-picking CASE9/12 at snr_floor=5 must return ≤30 peaks."""
        spectrum = BrukerReader.read_1d(str(CASE9_C13))
        peaks = AdaptivePeakPicker.pick_peaks(spectrum, snr_floor=5.0)
        assert len(peaks.peaks) <= 30, (
            f"Expected ≤30 peaks at snr_floor=5, got {len(peaks.peaks)}"
        )

    @pytest.mark.skipif(
        not CASE9_C13.exists(),
        reason="CASE9 dataset not available on this machine",
    )
    def test_case9_snr5_no_impossible_peaks(self) -> None:
        """No peak may be >230 ppm at snr_floor=5 (physically impossible for organic C)."""
        spectrum = BrukerReader.read_1d(str(CASE9_C13))
        peaks = AdaptivePeakPicker.pick_peaks(spectrum, snr_floor=5.0)
        impossible = [p.position for p in peaks.peaks if p.position > 230.0]
        assert impossible == [], (
            f"Impossible peaks >230 ppm at snr_floor=5: {sorted(impossible, reverse=True)}"
        )

    @pytest.mark.skipif(
        not CASE9_C13.exists(),
        reason="CASE9 dataset not available on this machine",
    )
    def test_case9_snr5_carbonyl_present(self) -> None:
        """Ester carbonyl at ~166.08 ppm (SNR≈17) must be present at snr_floor=5."""
        spectrum = BrukerReader.read_1d(str(CASE9_C13))
        peaks = AdaptivePeakPicker.pick_peaks(spectrum, snr_floor=5.0)
        ppms = [p.position for p in peaks.peaks]
        assert any(164.0 <= ppm <= 168.0 for ppm in ppms), (
            f"Carbonyl not found near 166 ppm. Top peaks: {sorted(ppms, reverse=True)[:10]}"
        )

    @pytest.mark.skipif(
        not CASE9_C13.exists(),
        reason="CASE9 dataset not available on this machine",
    )
    def test_case9_default_snr_is_5(self) -> None:
        """Default pick == explicit snr_floor=5.0 pick — confirms new default is in effect."""
        spectrum = BrukerReader.read_1d(str(CASE9_C13))
        peaks_default = AdaptivePeakPicker.pick_peaks(spectrum)
        peaks_explicit = AdaptivePeakPicker.pick_peaks(spectrum, snr_floor=5.0)
        assert len(peaks_default.peaks) == len(peaks_explicit.peaks), (
            f"Default ({len(peaks_default.peaks)}) != explicit snr_floor=5.0 "
            f"({len(peaks_explicit.peaks)}) — default may not be 5.0"
        )


class TestFIX08OvercountGuard:
    """Overcount guard fires on synthetic 76-vs-12 scenario (no external data needed)."""

    def _make_result(self, signal_count: int, expected_carbons: int) -> SymmetryAnalysisResult:
        hb = HydrogenBudgetResult(
            molecular_formula="C12H16O3",
            expected_h=16,
            carbon_assigned_h=16,
            heteroatom_h=0,
            total_accounted=16,
            missing_h=0,
        )
        ir = IntensityReport()
        missing = expected_carbons - signal_count
        return SymmetryAnalysisResult(
            molecular_formula="C12H16O3",
            hydrogen_budget=hb,
            intensity_report=ir,
            signal_count=signal_count,
            expected_carbons=expected_carbons,
            missing_carbons=missing,
        )

    def test_overcount_symmetry_analysis_summary(self) -> None:
        """summary() contains 'OVERCOUNT ALARM' when observed signal_count > expected_carbons."""
        result = self._make_result(signal_count=76, expected_carbons=12)
        assert result.missing_carbons == -64
        assert "OVERCOUNT ALARM" in result.summary()

    def test_overcount_cli_json(self) -> None:
        """CLI analyze symmetry with C4H8/Ibuprofen/2 must return overcount_alarm=True in JSON."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            ["symmetry", "C4H8", str(CASE1_C13), "--format", "json"],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        data = json.loads(result.output)
        assert data["overcount_alarm"] is True, (
            f"Expected overcount_alarm=True; got {data}"
        )

    def test_overcount_cli_text(self) -> None:
        """CLI analyze symmetry with C4H8/Ibuprofen/2 must contain 'more signals than carbons'."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            ["symmetry", "C4H8", str(CASE1_C13)],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "more signals than carbons" in result.output, (
            f"Expected 'more signals than carbons' in output; got:\n{result.output}"
        )


class TestFIX08CASE1Regression:
    """Non-regression: ibuprofen at snr_floor=5.0 must still yield >=9 peaks."""

    def test_case1_snr5_count_floor(self) -> None:
        """Ibuprofen 13C at snr_floor=5.0 must yield >=9 peaks (unchanged from prior)."""
        spectrum = BrukerReader.read_1d(str(CASE1_C13))
        peaks = AdaptivePeakPicker.pick_peaks(spectrum, snr_floor=5.0)
        assert len(peaks.peaks) >= 9, (
            f"Ibuprofen peak count dropped below 9 at snr_floor=5.0: {len(peaks.peaks)}"
        )
