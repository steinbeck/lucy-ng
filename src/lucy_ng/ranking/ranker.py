"""Solution ranking by 13C spectrum prediction."""

from lucy_ng.lsd.parser import LSDSolution
from lucy_ng.prediction import C13Predictor, PredictedShift

from .models import RankedSolution, RankingResult, ShiftAssignment


class SolutionRanker:
    """Rank LSD solutions by comparing predicted vs experimental 13C shifts.

    Uses the local HOSE-based C13Predictor to predict shifts for each
    candidate structure, then ranks by Mean Absolute Error (MAE) between
    predicted and experimental shifts.

    Example:
        >>> from lucy_ng import C13Predictor, SolutionRanker
        >>> predictor = C13Predictor.from_table_file("hose_lookup.json.gz")
        >>> ranker = SolutionRanker(predictor, tolerance=3.0)
        >>> result = ranker.rank(solutions, experimental_shifts=[180.5, 140.8, 129.4])
        >>> print(result.solutions[0].smiles)  # Best match
    """

    def __init__(
        self,
        predictor: C13Predictor,
        tolerance: float = 3.0,
    ) -> None:
        """Initialize the solution ranker.

        Args:
            predictor: C13Predictor instance for shift prediction
            tolerance: Maximum ppm difference for matching peaks (default: 3.0)
        """
        self.predictor = predictor
        self.tolerance = tolerance

    def rank(
        self,
        solutions: list[LSDSolution],
        experimental_shifts: list[float],
        top_n: int | None = None,
    ) -> RankingResult:
        """Rank LSD solutions by 13C spectrum similarity.

        Args:
            solutions: List of LSD solutions (must have SMILES for ranking)
            experimental_shifts: List of experimental 13C peak positions in ppm
            top_n: If specified, only return top N results

        Returns:
            RankingResult with solutions sorted by MAE (best first)
        """
        ranked: list[RankedSolution] = []
        skipped = 0

        for solution in solutions:
            # Skip solutions without SMILES
            if not solution.smiles:
                skipped += 1
                continue

            # Predict shifts for this structure
            try:
                prediction = self.predictor.predict_from_smiles(solution.smiles)
            except Exception:
                skipped += 1
                continue

            if not prediction.predictions:
                skipped += 1
                continue

            # Match predicted to experimental shifts
            assignments, mae = self._match_shifts(
                prediction.predictions,
                experimental_shifts,
            )

            # Count successful matches
            matched_count = sum(1 for a in assignments if a.is_matched)

            ranked_solution = RankedSolution(
                solution_index=solution.index,
                smiles=solution.smiles,
                mae=mae,
                matched_count=matched_count,
                total_carbons=prediction.carbon_count,
                prediction_rate=prediction.success_rate,
                assignments=assignments,
            )
            ranked.append(ranked_solution)

        # Sort by MAE (lower is better), then by match count (higher is better)
        ranked.sort(key=lambda r: (r.mae, -r.matched_count))

        # Store count before limiting
        total_ranked = len(ranked)

        # Limit results if requested
        if top_n is not None:
            ranked = ranked[:top_n]

        return RankingResult(
            solutions=ranked,
            experimental_shifts=experimental_shifts,
            total_solutions=len(solutions),
            ranked_count=total_ranked,
            skipped_count=skipped,
            tolerance=self.tolerance,
        )

    def _match_shifts(
        self,
        predictions: list[PredictedShift],
        experimental: list[float],
    ) -> tuple[list[ShiftAssignment], float]:
        """Match predicted shifts to experimental peaks allowing N:1 matching.

        Each predicted shift independently finds its closest experimental peak.
        Multiple predictions CAN match the same experimental peak - this handles
        molecular symmetry where equivalent carbons produce one signal.

        For example, para-disubstituted benzene has 2 equivalent ortho carbons
        that both predict ~129 ppm and should both match the single experimental
        peak at that position.

        **MAE Calculation**: Uses ALL shifts, not just those within tolerance.
        This provides a more accurate measure of fit quality. The tolerance is
        only used to determine "matched" status for reporting purposes.

        Args:
            predictions: List of predicted shifts from C13Predictor
            experimental: List of experimental 13C peaks in ppm

        Returns:
            Tuple of (list of ShiftAssignments, MAE across all predictions)
        """
        assignments: list[ShiftAssignment] = []
        all_errors: list[float] = []

        for pred in predictions:
            # Find closest experimental peak (regardless of tolerance)
            closest_shift: float | None = None
            closest_error: float | None = None

            for exp_shift in experimental:
                error = abs(pred.shift - exp_shift)
                if closest_error is None or error < closest_error:
                    closest_shift = exp_shift
                    closest_error = error

            # Determine if it's "matched" (within tolerance) for reporting
            is_within_tolerance = (
                closest_error is not None and closest_error <= self.tolerance
            )

            # Record assignment - always store error for MAE calculation
            if closest_error is not None:
                all_errors.append(closest_error)

            assignment = ShiftAssignment(
                atom_index=pred.atom_index,
                predicted_shift=pred.shift,
                # experimental_shift is set only if within tolerance (for backward compat)
                experimental_shift=closest_shift if is_within_tolerance else None,
                # error is always set (for MAE and deviation analysis)
                error=closest_error,
                closest_experimental=closest_shift,
            )

            assignments.append(assignment)

        # Calculate MAE using ALL shifts (no cutoff)
        # This provides a true measure of prediction quality
        if all_errors:
            mae = sum(all_errors) / len(all_errors)
        else:
            mae = float("inf")

        return assignments, mae

    @classmethod
    def from_table_file(
        cls,
        table_path: str,
        tolerance: float = 3.0,
        max_radius: int = 6,
    ) -> "SolutionRanker":
        """Create a SolutionRanker from a HOSE lookup table file.

        Convenience method that creates the C13Predictor from a table file.

        Args:
            table_path: Path to HOSE lookup table (JSON or compressed)
            tolerance: Maximum ppm difference for matching (default: 3.0)
            max_radius: Maximum HOSE radius for prediction (default: 6)

        Returns:
            Configured SolutionRanker instance
        """
        from pathlib import Path

        predictor = C13Predictor.from_table_file(Path(table_path), max_radius=max_radius)
        return cls(predictor, tolerance=tolerance)
