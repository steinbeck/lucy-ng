"""Tests for LSD solution ranking."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from lucy_ng.ranking.models import ShiftAssignment, RankedSolution, RankingResult
from lucy_ng.ranking.ranker import SolutionRanker
from lucy_ng.lsd.parser import LSDSolution
from lucy_ng.prediction import C13Predictor
from lucy_ng.prediction.models import PredictionResult, PredictedShift


def make_predicted_shift(atom_index: int, shift: float, confidence: float = 0.9) -> PredictedShift:
    """Helper to create a PredictedShift with all required fields."""
    return PredictedShift(
        atom_index=atom_index,
        shift=shift,
        confidence=confidence,
        hose_code=f"C({shift:.0f})",
        radius_used=6,
        match_count=100,
        std_dev=2.0,
        min_shift=shift - 5.0,
        max_shift=shift + 5.0,
    )


def make_prediction_result(smiles: str, shifts: list[float]) -> PredictionResult:
    """Helper to create a PredictionResult with all required fields."""
    predictions = [make_predicted_shift(i, s) for i, s in enumerate(shifts)]
    return PredictionResult(
        smiles=smiles,
        predictions=predictions,
        carbon_count=len(shifts),
        success_count=len(shifts),
    )


class TestShiftAssignment:
    """Tests for ShiftAssignment model."""

    def test_create_matched_assignment(self):
        """Test creating a matched shift assignment."""
        assignment = ShiftAssignment(
            atom_index=0,
            predicted_shift=45.2,
            experimental_shift=44.8,
            error=0.4,
        )
        assert assignment.atom_index == 0
        assert assignment.predicted_shift == 45.2
        assert assignment.experimental_shift == 44.8
        assert assignment.error == 0.4
        assert assignment.is_matched is True

    def test_create_unmatched_assignment(self):
        """Test creating an unmatched shift assignment."""
        assignment = ShiftAssignment(
            atom_index=1,
            predicted_shift=180.5,
            experimental_shift=None,
            error=None,
        )
        assert assignment.is_matched is False
        assert assignment.experimental_shift is None
        assert assignment.error is None

    def test_is_matched_property(self):
        """Test is_matched property logic."""
        matched = ShiftAssignment(
            atom_index=0,
            predicted_shift=45.2,
            experimental_shift=44.8,
            error=0.4,
        )
        unmatched = ShiftAssignment(
            atom_index=1,
            predicted_shift=180.5,
        )

        assert matched.is_matched is True
        assert unmatched.is_matched is False


class TestRankedSolution:
    """Tests for RankedSolution model."""

    def test_create_ranked_solution(self):
        """Test creating a ranked solution."""
        sol = RankedSolution(
            solution_index=1,
            smiles="CC(C)Cc1ccc(cc1)C(C)C(=O)O",
            mae=1.5,
            matched_count=10,
            total_carbons=13,
            prediction_rate=0.92,
            assignments=[],
        )
        assert sol.solution_index == 1
        assert sol.smiles == "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
        assert sol.mae == 1.5
        assert sol.matched_count == 10
        assert sol.total_carbons == 13
        assert sol.prediction_rate == 0.92

    def test_match_rate_property(self):
        """Test match_rate property calculation."""
        sol = RankedSolution(
            solution_index=1,
            smiles="CCC",
            mae=1.0,
            matched_count=3,
            total_carbons=5,
            prediction_rate=1.0,
        )
        assert sol.match_rate == 0.6  # 3/5

    def test_match_rate_zero_carbons(self):
        """Test match_rate with zero carbons."""
        sol = RankedSolution(
            solution_index=1,
            smiles="",
            mae=0.0,
            matched_count=0,
            total_carbons=0,
            prediction_rate=0.0,
        )
        assert sol.match_rate == 0.0

    def test_summary(self):
        """Test human-readable summary."""
        # Create assignments with deviations for proper summary output
        assignments = [
            ShiftAssignment(atom_index=0, predicted_shift=20.0, experimental_shift=21.0, error=1.0),
            ShiftAssignment(atom_index=1, predicted_shift=30.0, experimental_shift=31.5, error=1.5),
            ShiftAssignment(atom_index=2, predicted_shift=40.0, experimental_shift=42.0, error=2.0),
        ]
        sol = RankedSolution(
            solution_index=1,
            smiles="CCC",
            mae=1.5,
            matched_count=3,
            total_carbons=3,
            prediction_rate=1.0,
            assignments=assignments,
        )
        summary = sol.summary()

        assert "Solution 1" in summary
        assert "CCC" in summary
        assert "MAE: 1.50 ppm" in summary
        # Summary now shows tolerance_summary: "≤3ppm: 3/3 | ≤5ppm: 3/3"
        assert "3/3" in summary


class TestRankingResult:
    """Tests for RankingResult model."""

    def test_create_ranking_result(self):
        """Test creating a ranking result."""
        result = RankingResult(
            solutions=[],
            experimental_shifts=[45.0, 128.5, 180.3],
            total_solutions=10,
            ranked_count=8,
            skipped_count=2,
            tolerance=3.0,
        )
        assert len(result.experimental_shifts) == 3
        assert result.total_solutions == 10
        assert result.ranked_count == 8
        assert result.skipped_count == 2
        assert result.tolerance == 3.0

    def test_get_top(self):
        """Test getting top N solutions."""
        solutions = [
            RankedSolution(
                solution_index=i,
                smiles=f"C{'C' * i}",
                mae=float(i),
                matched_count=5,
                total_carbons=5,
                prediction_rate=1.0,
            )
            for i in range(1, 6)
        ]
        result = RankingResult(
            solutions=solutions,
            experimental_shifts=[],
            total_solutions=5,
            ranked_count=5,
        )

        top3 = result.get_top(3)
        assert len(top3) == 3
        assert top3[0].solution_index == 1
        assert top3[2].solution_index == 3

    def test_summary(self):
        """Test result summary."""
        sol = RankedSolution(
            solution_index=1,
            smiles="CCC",
            mae=1.5,
            matched_count=3,
            total_carbons=3,
            prediction_rate=1.0,
        )
        result = RankingResult(
            solutions=[sol],
            experimental_shifts=[20.0, 30.0, 40.0],
            total_solutions=5,
            ranked_count=3,
            skipped_count=2,
            tolerance=3.0,
        )

        summary = result.summary()
        assert "Total solutions: 5" in summary
        assert "Successfully ranked: 3" in summary
        assert "Skipped: 2" in summary
        assert "3.0 ppm" in summary


class TestSolutionRankerMatching:
    """Tests for the greedy shift matching algorithm."""

    @pytest.fixture
    def mock_predictor(self):
        """Create a mock predictor."""
        predictor = MagicMock(spec=C13Predictor)
        return predictor

    def test_perfect_match(self, mock_predictor):
        """Test matching with perfect alignment."""
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        predictions = [
            make_predicted_shift(0, 45.0),
            make_predicted_shift(1, 128.0),
        ]
        experimental = [45.0, 128.0]

        assignments, mae = ranker._match_shifts(predictions, experimental)

        assert len(assignments) == 2
        assert mae == 0.0
        assert all(a.is_matched for a in assignments)

    def test_match_within_tolerance(self, mock_predictor):
        """Test matching within tolerance."""
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        predictions = [
            make_predicted_shift(0, 45.0),
            make_predicted_shift(1, 128.0),
        ]
        experimental = [46.5, 130.0]  # 1.5 and 2.0 ppm off

        assignments, mae = ranker._match_shifts(predictions, experimental)

        assert len(assignments) == 2
        assert all(a.is_matched for a in assignments)
        assert mae == pytest.approx(1.75)  # (1.5 + 2.0) / 2

    def test_match_outside_tolerance(self, mock_predictor):
        """Test matching outside tolerance results in unmatched status but still contributes to MAE."""
        ranker = SolutionRanker(mock_predictor, tolerance=2.0)

        predictions = [
            make_predicted_shift(0, 45.0),
        ]
        experimental = [50.0]  # 5 ppm off, outside tolerance of 2.0

        assignments, mae = ranker._match_shifts(predictions, experimental)

        assert len(assignments) == 1
        assert not assignments[0].is_matched  # Outside tolerance
        # MAE is calculated from ALL shifts, not just those within tolerance
        # So MAE = 5.0 (the actual error), not infinity
        assert mae == pytest.approx(5.0)

    def test_greedy_assignment(self, mock_predictor):
        """Test greedy algorithm assigns to closest match."""
        ranker = SolutionRanker(mock_predictor, tolerance=5.0)

        # Two predictions, both could match either experimental
        predictions = [
            make_predicted_shift(0, 50.0),
            make_predicted_shift(1, 45.0),
        ]
        # Experimentals: 51 is closer to 50, 44 is closer to 45
        experimental = [51.0, 44.0]

        assignments, mae = ranker._match_shifts(predictions, experimental)

        # The greedy algorithm processes highest shifts first
        # So 50.0 should match to 51.0 (error 1.0)
        # Then 45.0 should match to 44.0 (error 1.0)
        assert all(a.is_matched for a in assignments)
        assert mae == pytest.approx(1.0)

    def test_more_predictions_than_experimental(self, mock_predictor):
        """Test when there are more predictions than experimental peaks (N:1 matching).

        With N:1 matching, multiple predictions can match the same experimental peak.
        This handles molecular symmetry where equivalent carbons predict the same shift.
        """
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        predictions = [
            make_predicted_shift(0, 50.0),
            make_predicted_shift(1, 45.0),
            make_predicted_shift(2, 40.0),
        ]
        experimental = [50.0, 45.0]  # Only 2 peaks

        assignments, mae = ranker._match_shifts(predictions, experimental)

        assert len(assignments) == 3
        # 2 matched, 1 unmatched (40.0 is outside tolerance of both peaks)
        matched = [a for a in assignments if a.is_matched]
        unmatched = [a for a in assignments if not a.is_matched]
        assert len(matched) == 2
        assert len(unmatched) == 1
        # MAE is calculated from ALL shifts:
        # - 50.0 → closest 50.0 → error 0
        # - 45.0 → closest 45.0 → error 0
        # - 40.0 → closest 45.0 → error 5
        # MAE = (0 + 0 + 5) / 3 = 1.67
        assert mae == pytest.approx(5.0 / 3.0)

    def test_empty_predictions(self, mock_predictor):
        """Test with empty predictions."""
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        assignments, mae = ranker._match_shifts([], [45.0, 50.0])

        assert len(assignments) == 0
        assert mae == float("inf")


class TestSolutionRankerRank:
    """Tests for the rank() method."""

    @pytest.fixture
    def mock_predictor(self):
        """Create a mock predictor with configurable predictions."""
        predictor = MagicMock(spec=C13Predictor)
        return predictor

    def test_rank_solutions(self, mock_predictor):
        """Test ranking multiple solutions."""
        # Configure predictor to return different predictions for different SMILES
        def predict_side_effect(smiles: str):
            if smiles == "GOOD":
                # Good match - low MAE
                return make_prediction_result(smiles, [45.0, 128.0])
            else:
                # Poor match - higher MAE
                return make_prediction_result(smiles, [60.0, 100.0])

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="BAD"),
            LSDSolution(index=2, smiles="GOOD"),
        ]
        experimental = [45.0, 128.0]

        result = ranker.rank(solutions, experimental)

        assert result.ranked_count == 2
        assert result.skipped_count == 0
        # Good solution should rank first (lower MAE)
        assert result.solutions[0].smiles == "GOOD"
        assert result.solutions[0].mae == 0.0
        assert result.solutions[1].smiles == "BAD"

    def test_skip_solutions_with_empty_smiles(self, mock_predictor):
        """Test that solutions with empty SMILES are skipped."""
        mock_predictor.predict_from_smiles.return_value = make_prediction_result("CCC", [45.0])

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="CCC"),
            LSDSolution(index=2, smiles=""),    # Empty SMILES
        ]

        result = ranker.rank(solutions, [45.0])

        assert result.total_solutions == 2
        assert result.ranked_count == 1
        assert result.skipped_count == 1

    def test_skip_failed_predictions(self, mock_predictor):
        """Test that failed predictions are skipped."""
        mock_predictor.predict_from_smiles.side_effect = Exception("Invalid SMILES")

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="INVALID"),
        ]

        result = ranker.rank(solutions, [45.0])

        assert result.ranked_count == 0
        assert result.skipped_count == 1

    def test_top_n_limit(self, mock_predictor):
        """Test top_n parameter limits results."""
        mock_predictor.predict_from_smiles.return_value = make_prediction_result("C", [45.0])

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=i, smiles=f"C{'C' * i}")
            for i in range(10)
        ]

        result = ranker.rank(solutions, [45.0], top_n=3)

        assert len(result.solutions) == 3

    def test_empty_solutions(self, mock_predictor):
        """Test with empty solutions list."""
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        result = ranker.rank([], [45.0])

        assert result.total_solutions == 0
        assert result.ranked_count == 0
        assert result.skipped_count == 0


class TestSolutionRankerFromFile:
    """Tests for from_table_file factory method."""

    def test_from_table_file_not_found(self):
        """Test error handling for missing table file."""
        with pytest.raises(FileNotFoundError):
            SolutionRanker.from_table_file("/nonexistent/table.json.gz")

    @pytest.mark.skipif(
        not Path("data/reference/hose_nmrshiftdb.json.gz").exists(),
        reason="HOSE lookup table not available",
    )
    def test_from_table_file_integration(self):
        """Integration test with real HOSE table."""
        ranker = SolutionRanker.from_table_file(
            "data/reference/hose_nmrshiftdb.json.gz",
            tolerance=3.0,
        )

        # Rank ibuprofen - should work with real predictor
        solutions = [
            LSDSolution(index=1, smiles="CC(C)Cc1ccc(cc1)C(C)C(=O)O"),  # Ibuprofen
        ]
        # Ibuprofen 13C shifts (approximate)
        experimental = [180.5, 140.8, 137.0, 129.4, 127.1, 45.1, 40.4, 30.2, 22.4, 18.2]

        result = ranker.rank(solutions, experimental)

        assert result.ranked_count == 1
        assert result.solutions[0].mae < 5.0  # Should have reasonably good match


class TestRankingCLI:
    """Tests for CLI integration (basic structure)."""

    def test_cli_imports(self):
        """Test that CLI imports work correctly."""
        from lucy_ng.cli.lsd import lsd_rank, _get_default_table_path
        assert callable(lsd_rank)
        assert callable(_get_default_table_path)


class TestRankingMCP:
    """Tests for MCP tool integration (basic structure)."""

    def test_mcp_imports(self):
        """Test that MCP tool imports work correctly."""
        mcp = pytest.importorskip("mcp")
        from lucy_ng.mcp.server import rank_lsd_solutions
        assert callable(rank_lsd_solutions)
