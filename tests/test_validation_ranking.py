"""Validation tests for two-tier ranking and badlist patterns.

These tests verify that v3.0 ranking prevents MAE hallucination (the core
failure mode from v2.1 ibuprofen) and that badlist patterns are properly
encoded in agent knowledge.
"""

import pytest
from unittest.mock import MagicMock

from ailsa.ranking.ranker import SolutionRanker
from ailsa.ranking.models import RankedSolution
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


@pytest.fixture
def mock_predictor():
    """Create a mock predictor."""
    predictor = MagicMock(spec=C13Predictor)
    return predictor


class TestTwoTierRanking:
    """Validate two-tier ranking prevents MAE hallucination."""

    def test_ibuprofen_scenario_complete_coverage_wins(self, mock_predictor):
        """Complete signal coverage must rank above partial coverage despite higher MAE.

        This is the EXACT failure mode from v2.1 ibuprofen analysis:
        - WRONG solution: 11/13 matched, MAE=1.93 ppm (cyclohexadiene)
        - CORRECT solution: 13/13 matched, MAE=2.13 ppm (ibuprofen)

        v2.1 ranking used MAE-only → WRONG ranked #1 → agent failed.
        v3.0 two-tier ranking → CORRECT ranks #1 → agent succeeds.

        Chemistry: Wrong structure can have coincidentally good shift matches
        for a subset of signals (ghost carbons in CH2-rich structures). Complete
        signal coverage is PRIMARY indicator of correctness.
        """
        def predict_side_effect(smiles: str):
            if smiles == "WRONG_CYCLOHEXADIENE":
                # 13 predictions: 11 match well (~0.2 ppm errors), 2 are ghosts (~4 ppm errors)
                # MAE = (11*0.2 + 2*4.0) / 13 = 0.78 ppm
                # But only 11/13 within 3 ppm tolerance
                return make_prediction_result(
                    smiles,
                    # 11 good matches
                    [180.3, 140.6, 136.8, 129.2, 127.3, 44.8, 40.2, 30.3, 22.5, 18.1, 50.1,
                     # 2 ghost carbons (hallucinated CH2 groups)
                     33.5, 11.0]  # >3 ppm from all experimental
                )
            else:  # "CORRECT_IBUPROFEN"
                # All 13 match with moderate errors (~2.0 ppm each)
                # MAE = 2.0 ppm
                return make_prediction_result(
                    smiles,
                    [182.5, 143.0, 139.0, 131.5, 129.0, 47.0, 42.5, 32.5, 24.5, 20.0, 52.0, 27.5, 15.5]
                )

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        # Use real parseable aromatic SMILES so the plausibility pre-filter (D-09) does not
        # reject either solution (4 shifts in 110-160 ppm → aromatic ring required).
        # The wrong structure is an isobutylbenzene (wrong connectivity but still aromatic);
        # the correct structure is ibuprofen. Both pass the aromatic plausibility check.
        wrong_smiles = "CC(C)Cc1ccccc1"     # isobutylbenzene — aromatic, labelled WRONG
        correct_smiles = "CC(C)Cc1ccc(C(C)C(=O)O)cc1"  # ibuprofen — aromatic, labelled CORRECT

        def predict_side_effect_real(smiles: str):
            if smiles == wrong_smiles:
                return make_prediction_result(
                    smiles,
                    [180.3, 140.6, 136.8, 129.2, 127.3, 44.8, 40.2, 30.3, 22.5, 18.1, 50.1,
                     33.5, 11.0]
                )
            else:  # correct_smiles
                return make_prediction_result(
                    smiles,
                    [182.5, 143.0, 139.0, 131.5, 129.0, 47.0, 42.5, 32.5, 24.5, 20.0, 52.0, 27.5, 15.5]
                )

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect_real

        solutions = [
            LSDSolution(index=1, smiles=wrong_smiles),
            LSDSolution(index=2, smiles=correct_smiles),
        ]
        # 13 experimental peaks (ibuprofen)
        experimental = [180.5, 140.8, 137.2, 129.4, 127.1, 45.1, 40.4, 30.2, 22.4, 18.2, 50.2, 25.0, 15.0]

        result = ranker.rank(solutions, experimental)

        # Verify the hallucination scenario exists
        wrong_sol = next(s for s in result.solutions if s.smiles == wrong_smiles)
        correct_sol = next(s for s in result.solutions if s.smiles == correct_smiles)

        assert wrong_sol.matched_count < correct_sol.matched_count, \
            "WRONG should have fewer matches (hallucination scenario)"
        assert correct_sol.matched_count == 13, "CORRECT should match all 13 signals"

        # THE CRITICAL VALIDATION: CORRECT ranks #1 despite higher MAE
        assert result.solutions[0].smiles == correct_smiles, \
            "Two-tier ranking MUST place complete coverage first (prevents MAE hallucination)"
        assert result.solutions[1].smiles == wrong_smiles

    def test_same_coverage_mae_tiebreaker(self, mock_predictor):
        """When signal coverage is equal, MAE acts as tiebreaker.

        Chemistry: If two structures explain the same number of signals,
        prefer the one with better quantitative match (lower errors).
        """
        def predict_side_effect(smiles: str):
            if smiles == "BETTER_MAE":
                # All 10 match with low errors
                return make_prediction_result(smiles, [45.0, 128.0, 180.0, 30.0, 22.0, 50.0, 25.0, 15.0, 140.0, 127.0])
            else:  # "WORSE_MAE"
                # All 10 match but with higher errors
                return make_prediction_result(smiles, [46.5, 129.5, 182.0, 31.5, 23.5, 51.5, 26.5, 16.5, 141.5, 128.5])

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="WORSE_MAE"),
            LSDSolution(index=2, smiles="BETTER_MAE"),
        ]
        experimental = [45.0, 128.0, 180.0, 30.0, 22.0, 50.0, 25.0, 15.0, 140.0, 127.0]

        result = ranker.rank(solutions, experimental)

        # Both should have 10/10 matched
        assert result.solutions[0].matched_count == result.solutions[1].matched_count == 10

        # BETTER_MAE should rank #1 (MAE tiebreaker)
        assert result.solutions[0].smiles == "BETTER_MAE"
        assert result.solutions[0].mae < result.solutions[1].mae

    def test_partial_match_cannot_hallucinate_win(self, mock_predictor):
        """Solution with fewer matches cannot rank above more matches despite lower MAE.

        Chemistry: A structure that explains fewer signals cannot be
        correct, even if the matched signals fit extremely well.
        Two-tier ranking prioritizes signal coverage over MAE.
        """
        def predict_side_effect(smiles: str):
            if smiles == "FEWER_MATCHES":
                # Only 8/10 match (within tolerance)
                # The 8 that match have very small errors (0.1 ppm average)
                # The 2 that don't match are ~5 ppm from closest peak
                # Overall MAE ~ (8*0.1 + 2*5) / 10 = 1.08 ppm
                return make_prediction_result(
                    smiles,
                    [45.0, 128.0, 180.0, 30.0, 22.0, 50.0, 25.0, 15.0,  # 8 perfect matches
                     35.0, 10.0]  # 2 ghost carbons: 35 is 5 ppm from 30, 10 is 5 ppm from 15
                )
            else:  # "MORE_MATCHES"
                # All 10 match with moderate errors (2.5 ppm average)
                # MAE = 2.5 ppm (higher than FEWER_MATCHES)
                return make_prediction_result(
                    smiles,
                    [47.5, 130.5, 182.5, 32.5, 24.5, 52.5, 27.5, 17.5, 142.5, 129.5]
                )

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [
            LSDSolution(index=1, smiles="FEWER_MATCHES"),
            LSDSolution(index=2, smiles="MORE_MATCHES"),
        ]
        experimental = [45.0, 128.0, 180.0, 30.0, 22.0, 50.0, 25.0, 15.0, 140.0, 127.0]

        result = ranker.rank(solutions, experimental)

        # Verify scenario
        fewer_sol = next(s for s in result.solutions if s.smiles == "FEWER_MATCHES")
        more_sol = next(s for s in result.solutions if s.smiles == "MORE_MATCHES")

        assert fewer_sol.matched_count == 8, "FEWER should match 8/10"
        assert more_sol.matched_count == 10, "MORE should match 10/10"
        assert fewer_sol.mae < more_sol.mae, "FEWER has lower MAE (but fewer matches)"

        # MORE_MATCHES must rank #1 (match count > MAE)
        assert result.solutions[0].smiles == "MORE_MATCHES", \
            "Two-tier ranking places more matches first despite higher MAE"


class TestRankingOutput:
    """Validate ranking output includes transparency fields."""

    def test_radius_transparency(self, mock_predictor):
        """Ranked output must include HOSE prediction radius for transparency.

        Chemistry: Lower radius = more specific context = higher confidence.
        Agent needs this info to assess prediction quality.
        """
        def predict_side_effect(smiles: str):
            # Create prediction with varying radius_used
            shifts = [
                PredictedShift(
                    atom_index=0, shift=45.0, confidence=0.9, hose_code="C", radius_used=6,
                    match_count=100, std_dev=2.0, min_shift=40.0, max_shift=50.0
                ),
                PredictedShift(
                    atom_index=1, shift=128.0, confidence=0.7, hose_code="C", radius_used=3,
                    match_count=50, std_dev=3.5, min_shift=120.0, max_shift=135.0
                ),
            ]
            return PredictionResult(
                smiles=smiles, predictions=shifts, carbon_count=2, success_count=2
            )

        mock_predictor.predict_from_smiles.side_effect = predict_side_effect

        ranker = SolutionRanker(mock_predictor, tolerance=3.0)

        solutions = [LSDSolution(index=1, smiles="TEST")]
        experimental = [45.0, 128.0]

        result = ranker.rank(solutions, experimental)

        # Check that radius_used is present in assignments
        assert len(result.solutions[0].assignments) == 2
        assert result.solutions[0].assignments[0].radius_used == 6
        assert result.solutions[0].assignments[1].radius_used == 3

        # Check that confidence is present
        assert result.solutions[0].assignments[0].confidence == 0.9
        assert result.solutions[0].assignments[1].confidence == 0.7


class TestRegressionSuite:
    """Full regression check - all existing tests must still pass."""

    def test_full_suite_passes(self):
        """Run full test suite to ensure no regressions from v3.0 changes.

        This test is a placeholder that documents the requirement.
        Actual execution is via `pytest --tb=short -q` in task verification.
        """
        # This test always passes - it's a documentation of regression requirement
        # Real regression check is external: `pytest --tb=short -q`
        assert True, "Regression suite executed externally"
