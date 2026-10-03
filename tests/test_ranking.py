"""Tests for LSD solution ranking."""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from ailsa.ranking.models import ShiftAssignment, RankedSolution, RankingResult
from ailsa.ranking.ranker import SolutionRanker
from ailsa.lsd.parser import LSDSolution
from ailsa.prediction import C13Predictor
from ailsa.prediction.models import PredictionResult, PredictedShift


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


class TestTwoTierRanking:
    """Tests for two-tier ranking (match count primary, MAE secondary)."""

    @pytest.fixture
    def mock_predictor(self):
        """Create a mock predictor with configurable predictions."""
        predictor = MagicMock(spec=C13Predictor)
        return predictor

    def test_two_tier_ranking_match_count_primary(self, mock_predictor):
        """Test that solutions with more matched signals rank higher even with higher MAE.

        This tests the core two-tier ranking: match count first, MAE second.
        A solution with more matches but slightly higher MAE should rank above
        one with fewer matches but lower MAE.
        """
        # Configure predictor for two solutions
        def predict_side_effect(smiles: str):
            if smiles == "HIGH_MATCH":
                # 3 predictions close to experimental (all will match)
                return make_prediction_result(smiles, [45.0, 128.0, 180.0])
            else:  # "LOW_MATCH"
                # 3 predictions, but one far from any experimental (only 2 match)
                return make_prediction_result(smiles, [45.0, 128.0, 999.0])

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="LOW_MATCH"),   # Will have 2/3 matched
            LSDSolution(index=2, smiles="HIGH_MATCH"),  # Will have 3/3 matched
        ]
        experimental = [45.5, 128.5, 180.5]  # All within 3 ppm of HIGH_MATCH predictions

        result = ranker.rank(solutions, experimental)

        # HIGH_MATCH should rank #1 due to more matches (3/3 vs 2/3)
        assert result.solutions[0].smiles == "HIGH_MATCH"
        assert result.solutions[0].matched_count == 3
        assert result.solutions[1].smiles == "LOW_MATCH"
        assert result.solutions[1].matched_count == 2

    def test_hallucination_prevention_ibuprofen_style(self, mock_predictor):
        """Test ranking with ibuprofen-style hallucination scenario.

        Simulates the exact issue from the Sherlock analysis:
        - WRONG solution: 11/13 matched, MAE=1.93 (lower MAE!)
        - CORRECT solution: 13/13 matched, MAE=2.13 (higher MAE)

        The correct solution MUST rank #1 despite higher MAE, because it has
        more matched signals. The key is that WRONG has fewer matches but its
        unmatched predictions are close to experimental peaks (just outside
        tolerance), so its overall MAE is actually lower.
        """
        # Configure predictor to simulate the hallucination scenario
        def predict_side_effect(smiles: str):
            if smiles == "WRONG":
                # 13 predictions: 11 matched (within 3 ppm), 2 unmatched (ghost carbons >3 ppm from all experimental)
                # MAE stays low because the 11 matched have very small errors (~0.2 ppm)
                # and the 2 unmatched are only ~3.5 ppm away (not 100+ ppm)
                return make_prediction_result(
                    smiles,
                    # These 11 match experimental peaks with very small errors (0.1-0.3 ppm)
                    [180.2, 140.5, 136.9, 129.2, 126.9, 44.9, 40.2, 30.1, 50.1, 25.1, 14.9,
                     # These 2 are "ghost carbons" - hallucinated CH2 groups in wrong positions
                     # They're in gaps between real signals, >3 ppm from closest experimental
                     # 33.5 is between 30.2 and 40.4 (closest is 40.4 at 6.9 ppm away)
                     # 11.0 is below 15.0 (closest is 15.0 at 4.0 ppm away)
                     33.5, 11.0]
                )
            else:  # "CORRECT"
                # All 13 predictions match (within 3 ppm), but with larger errors (2.0-2.5 ppm each)
                # This gives higher MAE but complete signal coverage
                return make_prediction_result(
                    smiles,
                    # All 13 match experimental with 2.0-2.5 ppm errors
                    [182.5, 143.0, 139.5, 131.5, 129.0, 47.0, 42.5, 32.5, 24.5, 20.5, 52.5, 27.5, 17.5]
                )

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        # Use real parseable aromatic SMILES so the plausibility pre-filter (D-09) does not
        # reject either solution (4 shifts in 110-160 ppm → aromatic ring required).
        # The SMILES identity strings still match the mock dispatch conditions above.
        wrong_smiles = "CC(C)Cc1ccc(CC(C)C)cc1"   # bis-isobutylbenzene, aromatic, labelled WRONG
        correct_smiles = "CC(C)Cc1ccc(C(C)C(=O)O)cc1"  # ibuprofen isomer, aromatic, labelled CORRECT

        # Re-define side_effect so mock dispatches on the real SMILES strings
        def predict_side_effect_real(smiles: str):
            if smiles == wrong_smiles:
                return make_prediction_result(
                    smiles,
                    [180.2, 140.5, 136.9, 129.2, 126.9, 44.9, 40.2, 30.1, 50.1, 25.1, 14.9,
                     33.5, 11.0]
                )
            else:  # correct_smiles
                return make_prediction_result(
                    smiles,
                    [182.5, 143.0, 139.5, 131.5, 129.0, 47.0, 42.5, 32.5, 24.5, 20.5, 52.5, 27.5, 17.5]
                )

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect_real

        solutions = [
            LSDSolution(index=1, smiles=wrong_smiles),
            LSDSolution(index=2, smiles=correct_smiles),
        ]
        # 13 experimental peaks
        experimental = [180.5, 140.8, 137.2, 129.4, 127.1, 45.1, 40.4, 30.2, 22.4, 18.2, 50.2, 25.0, 15.0]

        result = ranker.rank(solutions, experimental)

        # Check that WRONG has lower MAE but fewer matches (this is the hallucination scenario)
        wrong_sol = next(s for s in result.solutions if s.smiles == wrong_smiles)
        correct_sol = next(s for s in result.solutions if s.smiles == correct_smiles)

        assert wrong_sol.matched_count == 11, f"WRONG should have 11 matches, got {wrong_sol.matched_count}"
        assert correct_sol.matched_count == 13, f"CORRECT should have 13 matches, got {correct_sol.matched_count}"
        assert wrong_sol.mae < correct_sol.mae, \
            f"WRONG should have lower MAE (hallucination scenario), got WRONG={wrong_sol.mae:.2f} vs CORRECT={correct_sol.mae:.2f}"

        # CORRECT should rank #1 despite higher MAE (more matches is primary sort key)
        assert result.solutions[0].smiles == correct_smiles, \
            f"Expected CORRECT to rank #1 (matched={correct_sol.matched_count}, MAE={correct_sol.mae:.2f}), " \
            f"but got {result.solutions[0].smiles} (matched={result.solutions[0].matched_count}, MAE={result.solutions[0].mae:.2f})"

    def test_equal_match_count_fallback_to_mae(self, mock_predictor):
        """Test that when match counts are equal, MAE acts as tiebreaker.

        Both solutions match the same number of signals, so ranking should
        fall back to MAE (lower is better).
        """
        # Configure predictor for two solutions with equal match counts
        def predict_side_effect(smiles: str):
            if smiles == "BETTER_MAE":
                # Predictions very close to experimental (low MAE)
                return make_prediction_result(smiles, [45.0, 128.0, 180.0, 30.0, 22.0])
            else:  # "WORSE_MAE"
                # Predictions within tolerance but with more error (higher MAE)
                return make_prediction_result(smiles, [46.5, 129.5, 182.0, 31.5, 23.5])

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="WORSE_MAE"),
            LSDSolution(index=2, smiles="BETTER_MAE"),
        ]
        experimental = [45.0, 128.0, 180.0, 30.0, 22.0]

        result = ranker.rank(solutions, experimental)

        # Both should have 5/5 matched (all within 3 ppm tolerance)
        assert result.solutions[0].matched_count == result.solutions[1].matched_count
        # BETTER_MAE should rank #1 (lower MAE as tiebreaker)
        assert result.solutions[0].smiles == "BETTER_MAE"
        assert result.solutions[0].mae < result.solutions[1].mae

    def test_backward_compat_all_matched(self, mock_predictor):
        """Test backward compatibility when all solutions have 100% match rate.

        When all solutions match all their signals, ranking should reduce to
        MAE-only ordering (same as old behavior).
        """
        # Configure predictor for three solutions all with 100% match
        def predict_side_effect(smiles: str):
            if smiles == "MAE_1":
                return make_prediction_result(smiles, [45.0, 128.0, 180.0])
            elif smiles == "MAE_2":
                return make_prediction_result(smiles, [46.0, 129.0, 181.0])
            else:  # "MAE_3"
                return make_prediction_result(smiles, [47.0, 130.0, 182.0])

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=3, smiles="MAE_3"),  # Worst MAE
            LSDSolution(index=1, smiles="MAE_1"),  # Best MAE
            LSDSolution(index=2, smiles="MAE_2"),  # Middle MAE
        ]
        experimental = [45.0, 128.0, 180.0]

        result = ranker.rank(solutions, experimental)

        # All should have 3/3 matched
        for sol in result.solutions:
            assert sol.matched_count == 3

        # Should be ordered by MAE (ascending)
        assert result.solutions[0].smiles == "MAE_1"
        assert result.solutions[1].smiles == "MAE_2"
        assert result.solutions[2].smiles == "MAE_3"
        assert result.solutions[0].mae < result.solutions[1].mae < result.solutions[2].mae


class TestAromaticSanityCheck:
    """Tests for aromatic ring sanity check on ranking results."""

    @pytest.fixture
    def mock_predictor(self):
        """Create a mock predictor."""
        predictor = MagicMock(spec=C13Predictor)
        return predictor

    def test_has_aromatic_ring_true_for_aromatic_smiles(self, mock_predictor):
        """Test has_aromatic_ring is True for structures with aromatic rings."""
        mock_predictor.predict_from_smiles.return_value = make_prediction_result(
            "c1ccccc1", [128.0, 128.0, 128.0, 128.0, 128.0, 128.0]
        )
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)
        solutions = [LSDSolution(index=1, smiles="c1ccccc1")]
        result = ranker.rank(solutions, [128.0])

        assert result.solutions[0].has_aromatic_ring is True

    def test_has_aromatic_ring_false_for_non_aromatic_smiles(self, mock_predictor):
        """Test has_aromatic_ring is False for non-aromatic structures."""
        mock_predictor.predict_from_smiles.return_value = make_prediction_result(
            "C1CCCCC1", [27.0, 27.0, 27.0, 27.0, 27.0, 27.0]
        )
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)
        solutions = [LSDSolution(index=1, smiles="C1CCCCC1")]
        result = ranker.rank(solutions, [27.0])

        assert result.solutions[0].has_aromatic_ring is False

    def test_warning_when_aromatic_expected_but_no_solutions_aromatic(self, mock_predictor):
        """Test warning generated when 4+ shifts in 110-160 ppm but all solutions non-aromatic."""
        mock_predictor.predict_from_smiles.return_value = make_prediction_result(
            "C1CCCCC1", [130.0, 128.0, 125.0, 140.0, 27.0, 27.0]
        )
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)
        solutions = [LSDSolution(index=1, smiles="C1CCCCC1")]  # Non-aromatic
        # 5 experimental shifts in 110-160 ppm range (aromatic region)
        experimental = [129.4, 127.3, 137.0, 140.8, 141.0, 45.0, 30.0]

        result = ranker.rank(solutions, experimental)

        assert len(result.warnings) == 1
        assert "Aromatic ring expected" in result.warnings[0]
        assert "5 shifts in 110-160 ppm" in result.warnings[0]
        # D-04: warning now references ELIM escalation instead of 4J HMBC artifact (Phase 80)
        assert "ELIM" in result.warnings[0]

    def test_no_warning_when_solutions_contain_aromatic_rings(self, mock_predictor):
        """Test no warning when at least one solution has an aromatic ring."""
        mock_predictor.predict_from_smiles.return_value = make_prediction_result(
            "c1ccccc1", [128.0, 128.0, 128.0, 128.0, 128.0, 128.0]
        )
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)
        solutions = [LSDSolution(index=1, smiles="c1ccccc1")]  # Aromatic
        experimental = [128.0, 129.0, 130.0, 131.0, 45.0]

        result = ranker.rank(solutions, experimental)

        assert len(result.warnings) == 0

    def test_no_warning_when_fewer_than_4_aromatic_shifts(self, mock_predictor):
        """Test no warning when fewer than 4 experimental shifts are in the aromatic range."""
        mock_predictor.predict_from_smiles.return_value = make_prediction_result(
            "C1CCCCC1", [27.0, 27.0, 27.0, 27.0, 27.0, 27.0]
        )
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)
        solutions = [LSDSolution(index=1, smiles="C1CCCCC1")]  # Non-aromatic
        # Only 2 shifts in aromatic range (below threshold of 4)
        experimental = [130.0, 128.0, 45.0, 30.0, 22.0]

        result = ranker.rank(solutions, experimental)

        assert len(result.warnings) == 0

    def test_no_warning_when_no_ranked_solutions(self, mock_predictor):
        """Test no warning when all solutions were skipped (no ranked solutions)."""
        mock_predictor.predict_from_smiles.side_effect = Exception("bad SMILES")
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)
        solutions = [LSDSolution(index=1, smiles="INVALID")]
        experimental = [128.0, 129.0, 130.0, 131.0, 132.0]

        result = ranker.rank(solutions, experimental)

        assert len(result.warnings) == 0


class TestRankingCLI:
    """Tests for CLI integration (basic structure)."""

    def test_cli_imports(self):
        """Test that CLI imports work correctly."""
        from ailsa.cli.lsd import lsd_rank, _get_default_table_path
        assert callable(lsd_rank)
        assert callable(_get_default_table_path)


class TestPlausibilityFilter:
    """Tests for _is_chemically_plausible() pre-filter (Phase 80 D-09)."""

    @pytest.fixture
    def mock_predictor(self):
        """Create a mock predictor."""
        predictor = MagicMock(spec=C13Predictor)
        return predictor

    def test_non_aromatic_rejected_when_aromatic_expected(self, mock_predictor):
        """Non-aromatic solution is IMPLAUSIBLE when >= 4 shifts are in 110-160 ppm."""
        # Ibuprofen-like aromatic shifts (5 shifts in 110-160 ppm)
        experimental = [180.0, 141.0, 137.0, 129.4, 127.1, 45.0, 30.0]

        def predict(smiles: str):
            return make_prediction_result(smiles, [180.0, 141.0, 137.0, 129.4, 127.1, 45.0, 30.0])

        mock_predictor.predict_from_smiles.side_effect = predict
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="C1CCCCC1C(=O)O"),  # cyclohexane acid, no aromatic ring
        ]
        result = ranker.rank(solutions, experimental)

        # The non-aromatic solution should appear but be marked implausible
        assert len(result.solutions) == 1
        assert result.solutions[0].is_plausible is False

    def test_aromatic_retained_when_aromatic_expected(self, mock_predictor):
        """Aromatic solution is PLAUSIBLE when shifts suggest aromaticity."""
        experimental = [180.0, 141.0, 137.0, 129.4, 127.1, 45.0, 30.0]

        def predict(smiles: str):
            return make_prediction_result(smiles, [180.0, 141.0, 137.0, 129.4, 127.1, 45.0, 30.0])

        mock_predictor.predict_from_smiles.side_effect = predict
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="CC(C)Cc1ccc(cc1)C(C)C(=O)O"),  # ibuprofen, has aromatic ring
        ]
        result = ranker.rank(solutions, experimental)

        assert result.solutions[0].is_plausible is True

    def test_non_aromatic_ok_when_no_aromatic_shifts(self, mock_predictor):
        """Non-aromatic solution is PLAUSIBLE when < 4 shifts in 110-160 ppm."""
        experimental = [45.0, 30.0, 22.0]  # Only aliphatic shifts

        def predict(smiles: str):
            return make_prediction_result(smiles, [45.0, 30.0, 22.0])

        mock_predictor.predict_from_smiles.side_effect = predict
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="CCC"),  # no aromatic ring
        ]
        result = ranker.rank(solutions, experimental)

        assert result.solutions[0].is_plausible is True


class TestPlausibilityFilterOrdering:
    """Tests that plausible solutions rank ABOVE implausible ones (Phase 80 D-09)."""

    @pytest.fixture
    def mock_predictor(self):
        predictor = MagicMock(spec=C13Predictor)
        return predictor

    def test_plausible_ranks_above_implausible(self, mock_predictor):
        """Plausible solution (aromatic) must appear before implausible (non-aromatic)
        even when the implausible solution has a lower MAE."""
        # Use real parseable SMILES so RDKit can evaluate aromaticity:
        # c1ccccc1C = toluene (has aromatic ring); C1CCCCC1C = methylcyclohexane (no ring)
        aromatic_smiles = "c1ccccc1C"
        non_aromatic_smiles = "C1CCCCC1C"

        def predict(smiles: str):
            if smiles == aromatic_smiles:
                # Slightly higher MAE than the non-aromatic
                return make_prediction_result(smiles, [180.0, 141.0, 137.0, 129.4, 127.1, 48.0, 30.0])
            else:  # non_aromatic_smiles
                # Perfect MAE but no aromatic ring
                return make_prediction_result(smiles, [180.0, 141.0, 137.0, 129.4, 127.1, 45.0, 30.0])

        mock_predictor.predict_from_smiles.side_effect = predict
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        # Experimental shifts: 5 in 110-160 ppm range → aromatic required
        experimental = [180.0, 141.0, 137.0, 129.4, 127.1, 45.0, 30.0]
        solutions = [
            LSDSolution(index=1, smiles=non_aromatic_smiles),  # non-aromatic, low MAE
            LSDSolution(index=2, smiles=aromatic_smiles),       # aromatic, higher MAE
        ]

        result = ranker.rank(solutions, experimental)

        assert len(result.solutions) == 2
        # Aromatic solution must be first (plausible before implausible)
        assert result.solutions[0].smiles == aromatic_smiles
        assert result.solutions[0].is_plausible is True
        assert result.solutions[1].smiles == non_aromatic_smiles
        assert result.solutions[1].is_plausible is False

    def test_survivor_ordering_preserved(self, mock_predictor):
        """Among plausible solutions, original matched_count-desc / MAE-asc order is preserved."""
        # Use real parseable aromatic SMILES so both solutions pass the aromatic check
        high_match_smiles = "c1ccccc1"       # benzene — aromatic, high match
        low_match_smiles = "c1ccc(C)cc1"     # toluene — aromatic, low match

        def predict(smiles: str):
            if smiles == high_match_smiles:
                return make_prediction_result(smiles, [141.0, 137.0, 129.4, 127.1, 45.0, 30.0, 22.0])
            else:  # low_match_smiles
                return make_prediction_result(smiles, [141.0, 137.0, 999.0, 888.0, 45.0, 30.0, 22.0])

        mock_predictor.predict_from_smiles.side_effect = predict
        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        # 4 shifts in 110-160 range: both solutions need aromatic ring to be plausible
        experimental = [141.0, 137.0, 129.4, 127.1, 45.0, 30.0, 22.0]
        solutions = [
            LSDSolution(index=1, smiles=low_match_smiles),
            LSDSolution(index=2, smiles=high_match_smiles),
        ]

        result = ranker.rank(solutions, experimental)

        assert result.solutions[0].smiles == high_match_smiles
        assert result.solutions[1].smiles == low_match_smiles


@pytest.fixture
def temp_db(tmp_path):
    """Create a small deterministic SQLite DB with HOSE statistics.

    Mirrors the temp_db_with_ethanol pattern in tests/test_prediction.py:622-644
    so SolutionRanker.from_database / resolve_c13_predictor can be exercised
    without the 3.97 GB production database.
    """
    from ailsa.database import DatabaseManager
    from ailsa.database.models import HOSEStatsRecord

    db_path = tmp_path / "test_rank.db"
    db = DatabaseManager(db_path)
    db.create_tables()
    test_stats = [
        HOSEStatsRecord(hose_code="C-4;HHHC(//", radius=1, mean=15.0, std=2.0, count=100),
        HOSEStatsRecord(hose_code="C-4;C(O//)//", radius=2, mean=14.5, std=1.5, count=50),
        HOSEStatsRecord(hose_code="C-4;HHOC(//", radius=1, mean=60.0, std=3.0, count=80),
        HOSEStatsRecord(hose_code="C-4;O(//C(//))", radius=2, mean=58.0, std=2.5, count=40),
    ]
    db.insert_hose_stats_batch(test_stats)
    db.close()
    return db_path


class TestSolutionRankerFromDatabase:
    """Tests for SolutionRanker.from_database factory method (RANK-01)."""

    def test_from_database_returns_db_backed_ranker(self, temp_db):
        """from_database returns a ranker whose predictor uses a DatabaseHOSELookup."""
        from ailsa.prediction.db_lookup import DatabaseHOSELookup

        ranker = SolutionRanker.from_database(temp_db)

        assert isinstance(ranker, SolutionRanker)
        assert isinstance(ranker.predictor.lookup, DatabaseHOSELookup)

    def test_from_database_propagates_tolerance_and_max_radius(self, temp_db):
        """tolerance reaches the ranker; max_radius reaches the predictor."""
        ranker = SolutionRanker.from_database(temp_db, tolerance=2.0, max_radius=4)

        assert ranker.tolerance == 2.0
        assert ranker.predictor._max_radius == 4

    def test_from_database_can_rank_smiles(self, temp_db):
        """A DB-backed ranker can rank a trivial SMILES list without raising (smoke)."""
        ranker = SolutionRanker.from_database(temp_db)
        solutions = [LSDSolution(index=1, smiles="CCO")]
        experimental = [60.0, 15.0]

        # Smoke test: ranking completes and returns a populated result object.
        # (Whether the trivial SMILES is ranked or skipped depends on HOSE-code
        # coverage in the tiny temp_db; the contract under test is "does not raise".)
        result = ranker.rank(solutions, experimental)

        assert isinstance(result, RankingResult)
        assert result.total_solutions == 1


class TestResolveC13Predictor:
    """Tests for the shared resolve_c13_predictor backend ladder (RANK-01)."""

    def _make_json_table(self, tmp_path):
        """Build a minimal on-disk JSON HOSE lookup table the loader accepts."""
        from ailsa.prediction.lookup import HOSELookupTable

        table = HOSELookupTable()
        table.add_entry("C-4;HHHC(//", 15.0)
        table.add_entry("C-4;HHOC(//", 60.0)
        table_path = tmp_path / "hose_table.json.gz"
        table.save(table_path, compress=True)
        return table_path

    def test_resolve_explicit_db(self, temp_db):
        """Explicit db= yields a DB-backed predictor (priority 1)."""
        from ailsa.prediction.db_lookup import DatabaseHOSELookup
        from ailsa.prediction.resolver import resolve_c13_predictor

        predictor = resolve_c13_predictor(db=temp_db)

        assert isinstance(predictor.lookup, DatabaseHOSELookup)

    def test_resolve_explicit_table(self, tmp_path):
        """Explicit table= yields a table-backed predictor (priority 2)."""
        from ailsa.prediction.lookup import HOSELookupTable
        from ailsa.prediction.resolver import resolve_c13_predictor

        table_path = self._make_json_table(tmp_path)
        predictor = resolve_c13_predictor(table=table_path)

        assert isinstance(predictor.lookup, HOSELookupTable)

    def test_resolve_autodetect_prefers_database(self, temp_db, monkeypatch):
        """With no explicit args, an auto-detected DB wins over any table (priority 3)."""
        from ailsa.database.finder import DatabaseFinder
        from ailsa.prediction.db_lookup import DatabaseHOSELookup
        from ailsa.prediction.resolver import resolve_c13_predictor

        monkeypatch.setattr(
            DatabaseFinder, "find_hose_database", staticmethod(lambda: temp_db)
        )
        predictor = resolve_c13_predictor()

        assert isinstance(predictor.lookup, DatabaseHOSELookup)

    def test_resolve_no_backend_raises(self, monkeypatch, tmp_path):
        """No db/table and no auto-detected backend raises a clear error."""
        from ailsa.database.finder import DatabaseFinder
        from ailsa.prediction import resolver
        from ailsa.prediction.resolver import resolve_c13_predictor

        monkeypatch.setattr(
            DatabaseFinder, "find_hose_database", staticmethod(lambda: None)
        )
        monkeypatch.setattr(
            DatabaseFinder, "find_hose_table", staticmethod(lambda: None)
        )
        # Force the replicated shipped-table candidate paths to a location with no table
        monkeypatch.setattr(
            resolver, "_shipped_table_candidates", lambda: [tmp_path / "nope.json.gz"]
        )

        with pytest.raises(Exception, match="ailsa database download"):
            resolve_c13_predictor()

    def test_resolve_propagates_max_radius(self, temp_db):
        """max_radius is propagated to the constructed predictor."""
        from ailsa.prediction.resolver import resolve_c13_predictor

        predictor = resolve_c13_predictor(db=temp_db, max_radius=3)

        assert predictor._max_radius == 3

    def test_resolver_no_cli_layering_inversion(self):
        """The resolver module must not import from ailsa.cli (layering guard)."""
        import ailsa.prediction.resolver as resolver_mod

        source = Path(resolver_mod.__file__).read_text()
        import_lines = [
            line for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        assert not any("ailsa.cli" in line for line in import_lines)


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner (mirrors tests/test_prediction.py:456)."""
    from click.testing import CliRunner

    return CliRunner()


@pytest.fixture
def smiles_file(tmp_path):
    """Write a one-SMILES-per-line file (the lsd_rank SMILES_FILE argument)."""
    path = tmp_path / "solutions.smi"
    path.write_text("CCO\n")
    return path


class TestRankCLIBackendWiring:
    """RANK-01: `ailsa lsd rank` resolves its predictor through resolve_c13_predictor.

    These CLI-level tests pin that the ranker command honours --db / --table /
    --max-radius and auto-detects the SQLite DB first, exactly like predict c13.
    """

    def test_cli_db_uses_database_backend(self, cli_runner, temp_db, smiles_file):
        """`ailsa lsd rank --db <temp_db>` ranks via the DB backend (JSON output parses)."""
        from ailsa.cli import cli

        result = cli_runner.invoke(
            cli,
            [
                "lsd", "rank", str(smiles_file),
                "--shifts", "60.0,15.0",
                "--db", str(temp_db),
                "--format", "json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["total_solutions"] == 1
        assert "solutions" in data

    def test_cli_table_uses_table_backend(self, cli_runner, tmp_path, smiles_file):
        """`ailsa lsd rank --table <json>` ranks via the JSON table backend."""
        from ailsa.cli import cli
        from ailsa.prediction.lookup import HOSELookupTable

        table = HOSELookupTable()
        table.add_entry("C-4;HHHC(//", 15.0)
        table.add_entry("C-4;HHOC(//", 60.0)
        table_path = tmp_path / "hose_table.json.gz"
        table.save(table_path, compress=True)

        result = cli_runner.invoke(
            cli,
            [
                "lsd", "rank", str(smiles_file),
                "--shifts", "60.0,15.0",
                "--table", str(table_path),
                "--format", "json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["total_solutions"] == 1

    def test_cli_autodetect_prefers_database(
        self, cli_runner, temp_db, smiles_file, monkeypatch
    ):
        """With no --db/--table, the rank command auto-detects the DB first (priority 3)."""
        from ailsa.cli import cli
        from ailsa.database.finder import DatabaseFinder

        monkeypatch.setattr(
            DatabaseFinder, "find_hose_database", staticmethod(lambda: temp_db)
        )
        result = cli_runner.invoke(
            cli,
            [
                "lsd", "rank", str(smiles_file),
                "--shifts", "60.0,15.0",
                "--format", "json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["total_solutions"] == 1

    def test_cli_max_radius_option_accepted(self, cli_runner, temp_db, smiles_file):
        """`ailsa lsd rank --max-radius 4` is accepted and propagated without error."""
        from ailsa.cli import cli

        result = cli_runner.invoke(
            cli,
            [
                "lsd", "rank", str(smiles_file),
                "--shifts", "60.0,15.0",
                "--db", str(temp_db),
                "--max-radius", "4",
                "--format", "json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["total_solutions"] == 1

    def test_cli_help_lists_db_and_max_radius(self, cli_runner):
        """`ailsa lsd rank --help` advertises both --db and --max-radius (parity surface)."""
        from ailsa.cli import cli

        result = cli_runner.invoke(cli, ["lsd", "rank", "--help"])
        assert result.exit_code == 0
        assert "--db" in result.output
        assert "--max-radius" in result.output

    def test_cli_predict_c13_db_path_still_works(self, cli_runner, temp_db):
        """RANK-01 parity: predict c13 --db still works after the shared-helper refactor."""
        from ailsa.cli import cli

        result = cli_runner.invoke(
            cli,
            ["predict", "c13", "CCO", "--db", str(temp_db), "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["smiles"] == "CCO"


# ============================================================================
# RANK-01 / RANK-02 / RANK-03 regression — CASE1 (ibuprofen) + CASE3 (pulegone)
#
# Responsibility split (anti-circularity, per plan 86-02):
#   * The DETERMINISTIC temp_db tests below pin RANK-01 (per-shift parity: the
#     ranker's predictor and predict c13's predictor give bit-identical
#     PredictedShift lists) and RANK-02 (ranker MAE/match-count agree with a
#     directly-recomputed MAE). The deterministic RANK-03 ordering test is a
#     PARITY / no-ordering-regression guard: it asserts the wrong isomer's HOSE
#     codes GENUINELY DIFFER from the correct structure's BEFORE asserting the
#     correct structure outranks it, so a passing test cannot be a seeding
#     artifact ("whatever I seeded wins").
#   * The skipif-guarded REAL-DB integration test is the TRUE carrier of the
#     RANK-03 ordering-fix intent: against the production 7.9M-entry DB it
#     asserts BOTH (a) correct-structure MAE <= ~0.5 AND matched_count ==
#     total_carbons (reproducing 0.24 / 13/13 vs the old 2.23 / 8/13), AND
#     (b) the correct isomer ranks strictly ahead of the prior wrong isomer.
#
# HOSE invariant (CLAUDE.md): HOSE codes are generated on the no-AddHs prepared
# mol — _carbon_hose_codes() below uses HOSECodeGenerator.prepare_mol +
# Chem.RemoveHs and never calls AddHs.
#
# matched_count is over PREDICTIONS, not experimental peaks (research Pitfall 4):
# assertions use sol.matched_count and sol.mae directly — never a hand-derived
# "/10" denominator.
# ============================================================================

# Verified molecule identities (orchestrator answer-key context):
IBUPROFEN_SMILES = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"  # CASE1, para-substituted
IBUPROFEN_WRONG_SMILES = "CC(C)Cc1cccc(c1)C(C)C(=O)O"  # meta isomer (wrong constitution)
PULEGONE_SMILES = "CC(C)=C1CCC(C)CC1=O"  # CASE3, conjugated cyclic enone
PULEGONE_WRONG_SMILES = "CC(C)=C1CCCC(C)C1=O"  # ring-methyl shifted (wrong constitution)


def _carbon_hose_codes(smiles, max_radius=6):
    """Generate per-carbon HOSE codes at all radii on the no-AddHs prepared mol.

    Returns dict[atom_index -> dict[radius -> hose_code]]. Honours the CLAUDE.md
    "HOSE Codes: NO Explicit Hydrogens" invariant (prepare_mol does not AddHs;
    predict_from_mol's RemoveHs is mirrored here).
    """
    from rdkit import Chem

    from ailsa.prediction.hose import HOSECodeGenerator

    gen = HOSECodeGenerator()
    mol = HOSECodeGenerator.prepare_mol(smiles)
    assert mol is not None
    mol = Chem.RemoveHs(mol)  # mirror predict_from_mol; NO AddHs

    codes: dict[int, dict[int, str]] = {}
    for atom in mol.GetAtoms():
        if atom.GetSymbol() != "C":
            continue
        idx = atom.GetIdx()
        codes[idx] = {}
        for radius in range(1, max_radius + 1):
            try:
                codes[idx][radius] = gen.generate_for_atom(mol, idx, radius=radius)
            except Exception:
                pass
    return codes


def _seed_db_for_smiles(db_path, smiles, shifts, seed_radius=6):
    """Seed a SQLite DB so `smiles` predicts exactly the given per-carbon `shifts`.

    `shifts` maps atom_index -> expected 13C shift. Only the FULL-radius
    (``seed_radius``, default 6) HOSE code of each carbon is inserted with
    mean == the expected shift, so:
      * the correct structure matches every carbon at r6 -> MAE ~0;
      * a constitutional isomer whose r6 HOSE codes differ (verified zero
        overlap in the ordering test) finds NO r6 match, falls back through
        r5..r1 (none seeded) and is left unranked / poorly ranked.
    Seeding only the full-radius code is what makes the ordering test
    non-circular: low-radius collisions between isomers cannot give the wrong
    isomer a spurious perfect score.
    """
    from ailsa.database import DatabaseManager
    from ailsa.database.models import HOSEStatsRecord

    db = DatabaseManager(db_path)
    db.create_tables()

    records: list = []
    codes = _carbon_hose_codes(smiles, max_radius=seed_radius)
    for atom_idx, radius_codes in codes.items():
        hose_code = radius_codes.get(seed_radius)
        if hose_code is None:
            continue
        records.append(
            HOSEStatsRecord(
                hose_code=hose_code,
                radius=seed_radius,
                mean=shifts[atom_idx],
                std=0.5,
                count=100,
            )
        )
    db.insert_hose_stats_batch(records)
    db.close()


# Synthetic-but-distinct per-carbon shifts (atom_index -> ppm) used to seed the
# deterministic DB. Values need not be the real assignment — only that each
# carbon gets a stable shift so MAE is well-defined and reproducible.
_IBUPROFEN_SHIFTS = {
    0: 22.4, 1: 30.2, 2: 22.4, 3: 45.0, 4: 137.0, 5: 129.4, 6: 127.1,
    7: 129.4, 8: 127.1, 9: 129.4, 10: 45.6, 11: 18.1, 12: 180.5,
}
_PULEGONE_SHIFTS = {
    0: 23.0, 1: 147.5, 2: 22.5, 3: 35.0, 4: 33.5, 5: 50.5,
    6: 25.5, 7: 33.5, 8: 21.5, 9: 199.0,
}


@pytest.fixture
def ibuprofen_db(tmp_path):
    """Deterministic DB that makes ibuprofen predict its seeded shifts exactly."""
    db_path = tmp_path / "ibuprofen.db"
    _seed_db_for_smiles(db_path, IBUPROFEN_SMILES, _IBUPROFEN_SHIFTS)
    return db_path


@pytest.fixture
def pulegone_db(tmp_path):
    """Deterministic DB that makes pulegone predict its seeded shifts exactly."""
    db_path = tmp_path / "pulegone.db"
    _seed_db_for_smiles(db_path, PULEGONE_SMILES, _PULEGONE_SHIFTS)
    return db_path


def _predicted_shifts_sorted(predictor, smiles):
    """Return the molecule's PredictedShift list sorted by atom_index."""
    result = predictor.predict_from_smiles(smiles)
    return sorted(result.predictions, key=lambda p: p.atom_index)


class TestRankPredictParity:
    """RANK-01: the ranker's predictor and predict c13's predictor are identical."""

    @pytest.mark.parametrize(
        "fixture_name,smiles",
        [
            ("ibuprofen_db", IBUPROFEN_SMILES),
            ("pulegone_db", PULEGONE_SMILES),
        ],
    )
    def test_rank01_path_parity_per_shift(self, request, fixture_name, smiles):
        """Both paths (ranker predictor vs C13Predictor.from_database) give
        bit-identical per-carbon PredictedShift lists (RANK-01)."""
        from ailsa.prediction.predictor import C13Predictor
        from ailsa.prediction.resolver import resolve_c13_predictor

        db_path = request.getfixturevalue(fixture_name)

        # Path A: the SHARED resolver (what `ailsa lsd rank` + `predict c13` use)
        resolver_pred = resolve_c13_predictor(db=db_path)
        # Path B: the direct factory (what predict c13 used before unification)
        direct_pred = C13Predictor.from_database(db_path)

        a = _predicted_shifts_sorted(resolver_pred, smiles)
        b = _predicted_shifts_sorted(direct_pred, smiles)

        assert len(a) == len(b)
        assert len(a) > 0
        for pa, pb in zip(a, b, strict=True):
            assert pa.atom_index == pb.atom_index
            assert abs(pa.shift - pb.shift) < 1e-6
            assert pa.radius_used == pb.radius_used


class TestRankMAEAgreement:
    """RANK-02: ranker MAE/match-count agrees with a directly-recomputed MAE."""

    @pytest.mark.parametrize(
        "fixture_name,smiles,shift_map",
        [
            ("ibuprofen_db", IBUPROFEN_SMILES, _IBUPROFEN_SHIFTS),
            ("pulegone_db", PULEGONE_SMILES, _PULEGONE_SHIFTS),
        ],
    )
    def test_rank02_agreement(self, request, fixture_name, smiles, shift_map):
        """Ranker sol.mae equals a hand-recomputed MAE within 0.05 ppm and
        matched_count agrees exactly (RANK-02)."""
        from ailsa.prediction.resolver import resolve_c13_predictor

        db_path = request.getfixturevalue(fixture_name)
        experimental = sorted(set(shift_map.values()))

        ranker = SolutionRanker.from_database(db_path, tolerance=3.0)
        solutions = [LSDSolution(index=1, smiles=smiles)]
        result = ranker.rank(solutions, experimental)
        assert result.ranked_count == 1
        sol = result.solutions[0]

        # Recompute MAE directly from the predictor's predictions vs experimental:
        # mean over ALL predictions of |pred - closest experimental| (no cutoff),
        # exactly mirroring SolutionRanker._match_shifts (which is NOT modified).
        predictor = resolve_c13_predictor(db=db_path)
        preds = _predicted_shifts_sorted(predictor, smiles)
        errors = [min(abs(p.shift - e) for e in experimental) for p in preds]
        recomputed_mae = sum(errors) / len(errors)
        recomputed_matched = sum(1 for err in errors if err <= 3.0)

        assert abs(sol.mae - recomputed_mae) <= 0.05
        assert sol.matched_count == recomputed_matched
        # matched_count is over PREDICTIONS (Pitfall 4), so it equals the carbon count here
        assert sol.total_carbons == len(preds)


class TestRankOrderingNonCircular:
    """RANK-03 deterministic guard: correct outranks a genuinely-different wrong
    isomer (parity / no ordering regression — NOT a seeding artifact)."""

    @pytest.mark.parametrize(
        "fixture_name,correct,wrong,shift_map",
        [
            ("ibuprofen_db", IBUPROFEN_SMILES, IBUPROFEN_WRONG_SMILES, _IBUPROFEN_SHIFTS),
            ("pulegone_db", PULEGONE_SMILES, PULEGONE_WRONG_SMILES, _PULEGONE_SHIFTS),
        ],
    )
    def test_rank03_deterministic_ordering(
        self, request, fixture_name, correct, wrong, shift_map
    ):
        """Correct isomer ranks #1 over a wrong isomer whose HOSE codes DIFFER.

        Anti-circularity: assert the wrong-isomer HOSE codes are genuinely
        different from the correct structure's at the seeded carbons BEFORE the
        ordering assertion, so the result proves ordering rather than a seeding
        artifact. The deterministic DB carries RANK-01/02 parity; the real-DB
        test below carries the RANK-03 ordering-FIX validation.
        """
        # Anti-circularity pre-condition: HOSE environments must genuinely differ.
        correct_hoses = {
            r6 for codes in _carbon_hose_codes(correct).values()
            if (r6 := codes.get(6)) is not None
        }
        wrong_hoses = {
            r6 for codes in _carbon_hose_codes(wrong).values()
            if (r6 := codes.get(6)) is not None
        }
        assert correct_hoses != wrong_hoses
        # Stronger: zero overlap at r6 for these constitutional isomers.
        assert not (correct_hoses & wrong_hoses)

        db_path = request.getfixturevalue(fixture_name)
        experimental = sorted(set(shift_map.values()))

        ranker = SolutionRanker.from_database(db_path, tolerance=3.0)
        solutions = [
            LSDSolution(index=1, smiles=wrong),
            LSDSolution(index=2, smiles=correct),
        ]
        result = ranker.rank(solutions, experimental)

        # The correct structure (seeded from its own HOSE codes) must rank first.
        # This is a PARITY / no-ordering-regression guard, so the assertion is on
        # ORDERING, not an absolute MAE (low-radius HOSE-code collisions between
        # symmetry-equivalent carbons in the tiny DB can perturb the absolute MAE;
        # the real-DB test below carries the absolute MAE-reproduction intent).
        assert result.solutions[0].smiles == correct
        correct_sol = next(s for s in result.solutions if s.smiles == correct)
        wrong_sol = next((s for s in result.solutions if s.smiles == wrong), None)
        # Either the wrong isomer is ranked strictly worse, or it is unrankable
        # (no HOSE matches in this tiny DB) — both prove correct outranks wrong.
        if wrong_sol is not None:
            assert correct_sol.mae < wrong_sol.mae


@pytest.mark.skipif(
    __import__("ailsa.database.finder", fromlist=["DatabaseFinder"])
    .DatabaseFinder.find_hose_database() is None,
    reason="real HOSE DB not present (run: ailsa database download)",
)
class TestRankRealDBOrderingFix:
    """RANK-03 ordering-fix validation against the production HOSE DB.

    True carrier of the ordering-fix intent: reproduces 0.24 / 13-13 for the
    correct structure (vs the old 2.23 / 8-13 from the sparse JSON table) and
    proves the correct isomer outranks the prior wrong isomer.
    """

    @pytest.mark.parametrize(
        "correct,wrong,experimental,total_carbons,mae_max,assert_full_match",
        [
            (
                IBUPROFEN_SMILES,
                IBUPROFEN_WRONG_SMILES,
                # Ibuprofen experimental 13C shifts (the bug-report set).
                [180.5, 140.8, 137.0, 129.4, 127.1, 45.1, 40.4, 30.2, 22.4, 18.2],
                13,
                0.5,  # reproduces the empirical 0.244 (vs old 2.230) — tight bound
                True,  # 13/13 matched (vs old 8/13)
            ),
            (
                PULEGONE_SMILES,
                PULEGONE_WRONG_SMILES,
                # Pulegone (CASE3) experimental 13C shifts (literature).
                # The conjugated-enone carbons predict less tightly than ibuprofen;
                # the empirically-verified MAE<=0.5/full-match reproduction is
                # ibuprofen-specific (plan 86-02: pulegone tight assertion only
                # "where available"). For pulegone the real-DB test asserts the
                # ORDERING FIX + a plausible MAE bound, not the 0.5/full-match pin.
                [199.0, 147.5, 127.0, 50.5, 35.0, 33.5, 25.5, 22.5, 23.0, 21.5],
                10,
                3.0,  # loose, conjugated-enone bound (correct still clearly fits)
                False,  # full-match not asserted for the harder conjugated case
            ),
        ],
    )
    def test_rank03_real_db_ordering_fix(
        self, correct, wrong, experimental, total_carbons, mae_max, assert_full_match
    ):
        from ailsa.database.finder import DatabaseFinder

        db_path = DatabaseFinder.find_hose_database()
        ranker = SolutionRanker.from_database(db_path, tolerance=3.0)
        solutions = [
            LSDSolution(index=1, smiles=wrong),
            LSDSolution(index=2, smiles=correct),
        ]
        result = ranker.rank(solutions, experimental)

        correct_sol = next(s for s in result.solutions if s.smiles == correct)
        # (a) correct-structure MAE within the molecule's reproduced bound.
        #     (ibuprofen: <=0.5 reproducing 0.244 vs old 2.230; matched_count over
        #     PREDICTIONS == total_carbons, reproducing 13/13 vs old 8/13.)
        assert correct_sol.mae <= mae_max
        assert correct_sol.total_carbons == total_carbons
        if assert_full_match:
            assert correct_sol.matched_count == total_carbons
        # (b) correct isomer outranks the prior wrong isomer (the ordering FIX).
        assert result.solutions[0].smiles == correct
        wrong_sol = next((s for s in result.solutions if s.smiles == wrong), None)
        if wrong_sol is not None:
            assert correct_sol.mae < wrong_sol.mae


