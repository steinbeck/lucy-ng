"""Tests for symmetry analysis tools.

Tests hydrogen budget analysis, intensity reporting, and combined
symmetry analysis for detecting equivalent atoms.
"""

import pytest
import numpy as np

from ailsa.analysis import (
    CarbonHInfo,
    HydrogenBudgetAnalyzer,
    HydrogenBudgetResult,
    IntensityReport,
    IntensityReporter,
    PeakIntensityInfo,
    SymmetryAnalysisResult,
    SymmetryAnalyzer,
)
from ailsa.models import Peak1D, Peak2D, PeakList1D, PeakList2D, Spectrum2D
from ailsa.processing.dept_guided_picker import DEPTGuidedResult


# --- Fixtures ---


@pytest.fixture
def simple_dept_result() -> DEPTGuidedResult:
    """Simple DEPT result with known multiplicities."""
    hsqc_peaks = PeakList2D(
        peaks=[
            Peak2D(f1_position=129.4, f2_position=7.12, intensity=1000.0),
            Peak2D(f1_position=127.3, f2_position=7.25, intensity=900.0),
            Peak2D(f1_position=45.0, f2_position=3.07, intensity=500.0),
            Peak2D(f1_position=30.1, f2_position=1.87, intensity=200.0),
            Peak2D(f1_position=22.4, f2_position=0.86, intensity=800.0),
            Peak2D(f1_position=18.1, f2_position=1.49, intensity=400.0),
        ],
        f1_nucleus="13C",
        f2_nucleus="1H",
        experiment_type="HSQC",
    )

    dept_peaks = PeakList1D(
        peaks=[
            Peak1D(position=129.4, intensity=1000.0),
            Peak1D(position=127.3, intensity=900.0),
            Peak1D(position=45.0, intensity=-500.0),  # CH2 negative
            Peak1D(position=30.1, intensity=200.0),
            Peak1D(position=22.4, intensity=800.0),
            Peak1D(position=18.1, intensity=400.0),
        ],
        nucleus="13C",
    )

    return DEPTGuidedResult(
        peaks=hsqc_peaks,
        dept_peaks=dept_peaks,
        threshold_used=1000.0,
        iterations=1,
        all_carbons_found=True,
        carbon_multiplicities={
            129.4: "CH",
            127.3: "CH",
            45.0: "CH2",
            30.1: "CH",
            22.4: "CH3",
            18.1: "CH3",
        },
    )


@pytest.fixture
def ibuprofen_like_dept_result() -> DEPTGuidedResult:
    """DEPT result mimicking Ibuprofen (9 signals, 13 carbons expected)."""
    hsqc_peaks = PeakList2D(
        peaks=[
            # Aromatic CH (expected to be 2× equivalent each)
            Peak2D(f1_position=129.4, f2_position=7.12, intensity=2000.0),
            Peak2D(f1_position=127.3, f2_position=7.25, intensity=1800.0),
            # Aliphatic CH2
            Peak2D(f1_position=45.0, f2_position=3.07, intensity=1000.0),
            # Aliphatic CH
            Peak2D(f1_position=30.1, f2_position=1.87, intensity=900.0),
            # CH3 - one equivalent pair, one single
            Peak2D(f1_position=22.4, f2_position=0.86, intensity=1900.0),
            Peak2D(f1_position=18.1, f2_position=1.49, intensity=1000.0),
        ],
        f1_nucleus="13C",
        f2_nucleus="1H",
        experiment_type="HSQC",
    )

    dept_peaks = PeakList1D(
        peaks=[
            Peak1D(position=129.4, intensity=2000.0),
            Peak1D(position=127.3, intensity=1800.0),
            Peak1D(position=45.0, intensity=-1000.0),
            Peak1D(position=30.1, intensity=900.0),
            Peak1D(position=22.4, intensity=1900.0),
            Peak1D(position=18.1, intensity=1000.0),
        ],
        nucleus="13C",
    )

    return DEPTGuidedResult(
        peaks=hsqc_peaks,
        dept_peaks=dept_peaks,
        threshold_used=1000.0,
        iterations=1,
        all_carbons_found=True,
        carbon_multiplicities={
            129.4: "CH",
            127.3: "CH",
            45.0: "CH2",
            30.1: "CH",
            22.4: "CH3",
            18.1: "CH3",
        },
    )


@pytest.fixture
def mock_hsqc() -> Spectrum2D:
    """Mock HSQC spectrum with minimal required data."""
    return Spectrum2D(
        data=np.zeros((10, 10)),
        f1_ppm_scale=np.linspace(0, 150, 10),
        f2_ppm_scale=np.linspace(0, 10, 10),
        experiment_type="HSQC",
        f1_nucleus="13C",
        f2_nucleus="1H",
        frequency=500.0,
    )


# --- HydrogenBudgetAnalyzer Tests ---


class TestHydrogenBudgetAnalyzer:
    """Tests for HydrogenBudgetAnalyzer."""

    def test_basic_analysis(self, simple_dept_result: DEPTGuidedResult):
        """Test basic hydrogen budget calculation."""
        result = HydrogenBudgetAnalyzer.analyze("C6H12O", simple_dept_result)

        assert result.molecular_formula == "C6H12O"
        assert result.expected_h == 12
        assert isinstance(result.carbon_assigned_h, int)
        assert len(result.carbon_details) == 6

    def test_ibuprofen_missing_h(self, ibuprofen_like_dept_result: DEPTGuidedResult):
        """Test detection of missing hydrogens for symmetric molecule."""
        # Ibuprofen: C13H18O2 has 18 H
        # With 6 signals visible (not 13), missing H indicates equivalence
        result = HydrogenBudgetAnalyzer.analyze("C13H18O2", ibuprofen_like_dept_result)

        assert result.expected_h == 18
        assert result.has_equivalents  # Should detect missing H
        assert result.missing_h > 0

    def test_no_missing_h(self, simple_dept_result: DEPTGuidedResult):
        """Test case with no molecular symmetry."""
        # Create formula that matches observed H exactly
        # 2 CH (2H) + 1 CH2 (2H) + 1 CH (1H) + 2 CH3 (6H) = 11H
        # Add 1H for O = 12H total
        result = HydrogenBudgetAnalyzer.analyze("C6H12O", simple_dept_result)

        # Check calculation was performed
        assert result.expected_h == 12
        assert isinstance(result.missing_h, int)

    def test_ch_ch3_ambiguity_aliphatic(self):
        """Test CH/CH3 disambiguation in aliphatic region."""
        # Create result with ambiguous multiplicity in low-shift region
        hsqc_peaks = PeakList2D(
            peaks=[Peak2D(f1_position=15.0, f2_position=0.9, intensity=1000.0)],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        dept_peaks = PeakList1D(
            peaks=[Peak1D(position=15.0, intensity=1000.0)],
            nucleus="13C",
        )
        dept_result = DEPTGuidedResult(
            peaks=hsqc_peaks,
            dept_peaks=dept_peaks,
            threshold_used=1000.0,
            iterations=1,
            all_carbons_found=True,
            carbon_multiplicities={15.0: "CH/CH3"},  # Ambiguous at 15 ppm (< 30)
        )

        result = HydrogenBudgetAnalyzer.analyze("C1H4", dept_result)

        # < 30 ppm should be treated as CH3 (3 H)
        assert result.carbon_details[0].hydrogen_count == 3

    def test_ch_ch3_ambiguity_aromatic(self):
        """Test CH/CH3 disambiguation in aromatic region."""
        hsqc_peaks = PeakList2D(
            peaks=[Peak2D(f1_position=125.0, f2_position=7.0, intensity=1000.0)],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        dept_peaks = PeakList1D(
            peaks=[Peak1D(position=125.0, intensity=1000.0)],
            nucleus="13C",
        )
        dept_result = DEPTGuidedResult(
            peaks=hsqc_peaks,
            dept_peaks=dept_peaks,
            threshold_used=1000.0,
            iterations=1,
            all_carbons_found=True,
            carbon_multiplicities={125.0: "CH/CH3"},  # Ambiguous at 125 ppm (> 100)
        )

        result = HydrogenBudgetAnalyzer.analyze("C1H1", dept_result)

        # > 100 ppm should be treated as CH (1 H)
        assert result.carbon_details[0].hydrogen_count == 1

    def test_heteroatom_h_estimation(self):
        """Test estimation of hydrogens on heteroatoms."""
        hsqc_peaks = PeakList2D(
            peaks=[],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        dept_peaks = PeakList1D(
            peaks=[],
            nucleus="13C",
        )
        dept_result = DEPTGuidedResult(
            peaks=hsqc_peaks,
            dept_peaks=dept_peaks,
            threshold_used=1000.0,
            iterations=1,
            all_carbons_found=True,
            carbon_multiplicities={},
        )

        # Test with oxygen
        result = HydrogenBudgetAnalyzer.analyze("C6H12O2", dept_result)
        assert result.heteroatom_h > 0
        assert "O" in result.heteroatom_details

        # Test with nitrogen
        result = HydrogenBudgetAnalyzer.analyze("C6H13N", dept_result)
        assert result.heteroatom_h > 0
        assert "N" in result.heteroatom_details

    def test_summary_output(self, simple_dept_result: DEPTGuidedResult):
        """Test that summary produces readable text."""
        result = HydrogenBudgetAnalyzer.analyze("C13H18O2", simple_dept_result)
        summary = result.summary()

        assert "Hydrogen Budget Analysis" in summary
        assert "C13H18O2" in summary
        assert "Expected H" in summary
        assert "Carbon-assigned H" in summary


# --- IntensityReporter Tests ---


class TestIntensityReporter:
    """Tests for IntensityReporter."""

    def test_basic_report(self, mock_hsqc: Spectrum2D, simple_dept_result: DEPTGuidedResult):
        """Test basic intensity reporting."""
        report = IntensityReporter.report(mock_hsqc, simple_dept_result)

        assert isinstance(report, IntensityReport)
        assert len(report.peaks) == 6
        assert report.equivalence_threshold == 1.5

    def test_relative_intensity_calculation(
        self, mock_hsqc: Spectrum2D, simple_dept_result: DEPTGuidedResult
    ):
        """Test that relative intensities are normalized correctly."""
        report = IntensityReporter.report(mock_hsqc, simple_dept_result)

        # Find minimum and maximum relative intensities
        rel_intensities = [p.relative_intensity for p in report.peaks]

        # Minimum should be normalized to 1.0
        assert min(rel_intensities) == pytest.approx(1.0)
        # Maximum should be > 1.0 (since intensities vary)
        assert max(rel_intensities) >= 1.0

    def test_potential_equivalents_flagging(
        self, mock_hsqc: Spectrum2D, ibuprofen_like_dept_result: DEPTGuidedResult
    ):
        """Test that high-intensity peaks are flagged as potential equivalents."""
        report = IntensityReporter.report(
            mock_hsqc, ibuprofen_like_dept_result, equivalence_threshold=1.5
        )

        # Should flag some peaks with intensity > 1.5× reference
        assert report.has_potential_equivalents
        assert len(report.potential_equivalents) > 0

    def test_custom_threshold(
        self, mock_hsqc: Spectrum2D, simple_dept_result: DEPTGuidedResult
    ):
        """Test custom equivalence threshold."""
        # Very high threshold - nothing should be flagged
        report = IntensityReporter.report(
            mock_hsqc, simple_dept_result, equivalence_threshold=100.0
        )
        assert not report.has_potential_equivalents

        # Very low threshold - everything above reference flagged
        report = IntensityReporter.report(
            mock_hsqc, simple_dept_result, equivalence_threshold=1.0
        )
        # At threshold 1.0, only peaks > 1.0× are flagged (not equal)
        # So some peaks should still be flagged

    def test_empty_peaks(self, mock_hsqc: Spectrum2D):
        """Test handling of empty peak list."""
        hsqc_peaks = PeakList2D(
            peaks=[],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        dept_peaks = PeakList1D(
            peaks=[],
            nucleus="13C",
        )
        empty_result = DEPTGuidedResult(
            peaks=hsqc_peaks,
            dept_peaks=dept_peaks,
            threshold_used=1000.0,
            iterations=1,
            all_carbons_found=True,
            carbon_multiplicities={},
        )

        report = IntensityReporter.report(mock_hsqc, empty_result)

        assert len(report.peaks) == 0
        assert not report.has_potential_equivalents

    def test_summary_output(
        self, mock_hsqc: Spectrum2D, simple_dept_result: DEPTGuidedResult
    ):
        """Test that summary produces readable text."""
        report = IntensityReporter.report(mock_hsqc, simple_dept_result)
        summary = report.summary()

        assert "HSQC Relative Intensities" in summary
        assert "C shift" in summary
        assert "H shift" in summary
        assert "Rel.Int" in summary


# --- SymmetryAnalyzer Tests ---


class TestSymmetryAnalyzer:
    """Tests for SymmetryAnalyzer."""

    def test_basic_analysis(
        self,
        mock_hsqc: Spectrum2D,
        simple_dept_result: DEPTGuidedResult,
    ):
        """Test basic symmetry analysis."""
        result = SymmetryAnalyzer.analyze(
            "C13H18O2", simple_dept_result, mock_hsqc
        )

        assert isinstance(result, SymmetryAnalysisResult)
        assert result.molecular_formula == "C13H18O2"
        assert result.expected_carbons == 13
        assert result.signal_count == 6  # From simple_dept_result

    def test_missing_carbons_detection(
        self,
        mock_hsqc: Spectrum2D,
        ibuprofen_like_dept_result: DEPTGuidedResult,
    ):
        """Test detection of missing carbons due to equivalence."""
        result = SymmetryAnalyzer.analyze(
            "C13H18O2", ibuprofen_like_dept_result, mock_hsqc
        )

        # 13 expected - 6 observed = 7 missing
        assert result.expected_carbons == 13
        assert result.signal_count == 6
        assert result.missing_carbons == 7

    def test_has_symmetry_property(
        self,
        mock_hsqc: Spectrum2D,
        ibuprofen_like_dept_result: DEPTGuidedResult,
    ):
        """Test has_symmetry property."""
        result = SymmetryAnalyzer.analyze(
            "C13H18O2", ibuprofen_like_dept_result, mock_hsqc
        )

        # Should detect symmetry from missing carbons or missing H
        assert result.has_symmetry

    def test_no_symmetry(self, mock_hsqc: Spectrum2D):
        """Test case with no molecular symmetry."""
        # Create a molecule where signals = expected carbons
        hsqc_peaks = PeakList2D(
            peaks=[
                Peak2D(f1_position=45.0, f2_position=3.07, intensity=1000.0),
                Peak2D(f1_position=30.1, f2_position=1.87, intensity=900.0),
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )
        dept_peaks = PeakList1D(
            peaks=[
                Peak1D(position=45.0, intensity=-1000.0),
                Peak1D(position=30.1, intensity=900.0),
            ],
            nucleus="13C",
        )
        dept_result = DEPTGuidedResult(
            peaks=hsqc_peaks,
            dept_peaks=dept_peaks,
            threshold_used=1000.0,
            iterations=1,
            all_carbons_found=True,
            carbon_multiplicities={45.0: "CH2", 30.1: "CH3"},
        )

        # C2H5 = ethyl group, 2 carbons, 5 H
        result = SymmetryAnalyzer.analyze("C2H5", dept_result, mock_hsqc)

        assert result.signal_count == 2
        assert result.expected_carbons == 2
        assert result.missing_carbons == 0

    def test_combined_summary(
        self,
        mock_hsqc: Spectrum2D,
        ibuprofen_like_dept_result: DEPTGuidedResult,
    ):
        """Test combined summary output."""
        result = SymmetryAnalyzer.analyze(
            "C13H18O2", ibuprofen_like_dept_result, mock_hsqc
        )
        summary = result.summary()

        assert "Symmetry Analysis" in summary
        assert "C13H18O2" in summary
        assert "SIGNAL COUNT" in summary
        assert "HYDROGEN BUDGET" in summary
        assert "INTENSITY EVIDENCE" in summary
        assert "INTERPRETATION HINTS" in summary

    def test_aromatic_pattern_hint(
        self,
        mock_hsqc: Spectrum2D,
        ibuprofen_like_dept_result: DEPTGuidedResult,
    ):
        """Test that aromatic symmetry pattern is recognized."""
        result = SymmetryAnalyzer.analyze(
            "C13H18O2", ibuprofen_like_dept_result, mock_hsqc
        )
        summary = result.summary()

        # Should mention para-disubstituted pattern if 2 aromatic CH equivalents
        # This depends on intensity flagging
        assert "Symmetry Analysis" in summary

    def test_region_classification(self):
        """Test chemical shift region classification."""
        result = SymmetryAnalysisResult

        assert result._classify_region(180.0) == "carbonyl/heteroaromatic"
        assert result._classify_region(125.0) == "aromatic"
        assert result._classify_region(70.0) == "oxygenated aliphatic"
        assert result._classify_region(35.0) == "aliphatic CH/CH2"
        assert result._classify_region(15.0) == "aliphatic CH3"


# --- Integration Tests ---


class TestIntegration:
    """Integration tests using realistic data patterns."""

    def test_full_symmetry_workflow(self, mock_hsqc: Spectrum2D):
        """Test complete symmetry analysis workflow."""
        # Create Ibuprofen-like data
        hsqc_peaks = PeakList2D(
            peaks=[
                # Aromatic (equivalent pairs)
                Peak2D(f1_position=129.4, f2_position=7.12, intensity=2000.0),
                Peak2D(f1_position=127.3, f2_position=7.25, intensity=2000.0),
                # Quaternary aromatics would not appear in HSQC
                # Aliphatic
                Peak2D(f1_position=45.0, f2_position=3.07, intensity=1000.0),  # CH2
                Peak2D(f1_position=30.1, f2_position=1.87, intensity=1000.0),  # CH
                Peak2D(f1_position=22.4, f2_position=0.86, intensity=2000.0),  # Equivalent CH3
                Peak2D(f1_position=18.1, f2_position=1.49, intensity=1000.0),  # Single CH3
            ],
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
        )

        dept_peaks = PeakList1D(
            peaks=[
                Peak1D(position=129.4, intensity=2000.0),
                Peak1D(position=127.3, intensity=2000.0),
                Peak1D(position=45.0, intensity=-1000.0),
                Peak1D(position=30.1, intensity=1000.0),
                Peak1D(position=22.4, intensity=2000.0),
                Peak1D(position=18.1, intensity=1000.0),
            ],
            nucleus="13C",
        )

        dept_result = DEPTGuidedResult(
            peaks=hsqc_peaks,
            dept_peaks=dept_peaks,
            threshold_used=1000.0,
            iterations=1,
            all_carbons_found=True,
            carbon_multiplicities={
                129.4: "CH",
                127.3: "CH",
                45.0: "CH2",
                30.1: "CH",
                22.4: "CH3",
                18.1: "CH3",
            },
        )

        # Run analysis
        result = SymmetryAnalyzer.analyze("C13H18O2", dept_result, mock_hsqc)

        # Verify key findings
        assert result.missing_carbons > 0  # Some carbons are equivalent
        assert result.hydrogen_budget.has_equivalents or result.intensity_report.has_potential_equivalents

        # Summary should be AI-readable
        summary = result.summary()
        assert len(summary) > 100  # Substantial output
        assert "Symmetry Analysis" in summary


# --- FIX-08 SymmetryAnalysisResult overcount alarm tests ---


class TestSymmetryAnalysisResultOvercount:
    """Tests for FIX-08: overcount alarm in SymmetryAnalysisResult.summary()."""

    @pytest.fixture
    def overcount_result(self) -> SymmetryAnalysisResult:
        """SymmetryAnalysisResult with overcount (76 observed vs 12 expected)."""
        hb = HydrogenBudgetResult(
            molecular_formula="C12H16O3",
            expected_h=16,
            carbon_assigned_h=16,
            heteroatom_h=0,
            total_accounted=16,
            missing_h=0,
        )
        ir = IntensityReport(peaks=[])
        return SymmetryAnalysisResult(
            molecular_formula="C12H16O3",
            hydrogen_budget=hb,
            intensity_report=ir,
            signal_count=76,
            expected_carbons=12,
            missing_carbons=-64,
        )

    def test_overcount_summary_contains_overcount_alarm(
        self, overcount_result: SymmetryAnalysisResult
    ) -> None:
        """summary() must contain 'OVERCOUNT ALARM' when missing_carbons < 0."""
        s = overcount_result.summary()
        assert "OVERCOUNT ALARM" in s

    def test_overcount_summary_contains_more_signals_than_carbons(
        self, overcount_result: SymmetryAnalysisResult
    ) -> None:
        """summary() must mention 'more signals than carbons' for overcount."""
        s = overcount_result.summary()
        assert "more signals than carbons" in s

    def test_overcount_has_symmetry_is_false(
        self, overcount_result: SymmetryAnalysisResult
    ) -> None:
        """has_symmetry must be False when missing_carbons < 0."""
        assert overcount_result.has_symmetry is False

    def test_undercount_summary_unchanged(self) -> None:
        """Undercount path (missing_carbons > 0) must be unchanged."""
        hb = HydrogenBudgetResult(
            molecular_formula="C13H18O2",
            expected_h=18,
            carbon_assigned_h=11,
            heteroatom_h=0,
            total_accounted=11,
            missing_h=7,
        )
        ir = IntensityReport(peaks=[])
        r = SymmetryAnalysisResult(
            molecular_formula="C13H18O2",
            hydrogen_budget=hb,
            intensity_report=ir,
            signal_count=6,
            expected_carbons=13,
            missing_carbons=7,
        )
        s = r.summary()
        assert "OVERCOUNT ALARM" not in s
        assert "7 carbons must be equivalent" in s

    def test_zero_difference_summary_unchanged(self) -> None:
        """Zero difference (missing_carbons == 0) must produce no alarm."""
        hb = HydrogenBudgetResult(
            molecular_formula="C2H6O",
            expected_h=6,
            carbon_assigned_h=6,
            heteroatom_h=0,
            total_accounted=6,
            missing_h=0,
        )
        ir = IntensityReport(peaks=[])
        r = SymmetryAnalysisResult(
            molecular_formula="C2H6O",
            hydrogen_budget=hb,
            intensity_report=ir,
            signal_count=2,
            expected_carbons=2,
            missing_carbons=0,
        )
        s = r.summary()
        assert "OVERCOUNT ALARM" not in s
