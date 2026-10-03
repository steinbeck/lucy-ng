"""Solution ranking by 13C spectrum prediction."""

from typing import TYPE_CHECKING

from rdkit import Chem

if TYPE_CHECKING:
    from pathlib import Path

from ailsa.lsd.parser import LSDSolution
from ailsa.prediction import C13Predictor, PredictedShift

from .models import RankedSolution, RankingResult, ShiftAssignment


def _calc_dbe_from_formula(formula: str) -> float:
    """Compute Degree of Unsaturation (DBE) from a molecular formula string.

    DBE = (2C + 2 + N - H - X) / 2  where X = halogens (F, Cl, Br, I).
    Uses parse_molecular_formula() from ailsa.lsd.generator.
    """
    from ailsa.lsd.generator import parse_molecular_formula

    counts = parse_molecular_formula(formula)
    c = counts.get("C", 0)
    h = counts.get("H", 0)
    n = counts.get("N", 0)
    x = (
        counts.get("F", 0)
        + counts.get("Cl", 0)
        + counts.get("Br", 0)
        + counts.get("I", 0)
    )
    return (2 * c + 2 + n - h - x) / 2


def _calc_dbe_from_mol(mol: "Chem.Mol") -> float:
    """Compute DBE from an RDKit mol object via CalcMolFormula."""
    from rdkit.Chem import rdMolDescriptors

    formula = rdMolDescriptors.CalcMolFormula(mol)
    return _calc_dbe_from_formula(formula)


def _is_chemically_plausible(
    solution: "RankedSolution",
    experimental_shifts: list[float],
    formula: str | None = None,
) -> bool:
    """Return False if the solution is chemically implausible.

    Check 1: Aromatic ring required when >= 4 shifts are in 110-160 ppm.
    Check 2: DBE consistency when formula is provided (tolerance ±1).

    Args:
        solution: Ranked solution to evaluate
        experimental_shifts: List of experimental 13C shifts in ppm
        formula: Optional molecular formula string for DBE check (e.g. "C12H16O3")

    Returns:
        False if the solution fails a plausibility check, True otherwise
    """
    # Check 1: aromatic ring required when shifts strongly suggest aromaticity
    aromatic_shift_count = sum(1 for s in experimental_shifts if 110.0 <= s <= 160.0)
    if aromatic_shift_count >= 4 and not solution.has_aromatic_ring:
        return False

    # Check 2: DBE consistency (optional — requires formula)
    if formula is not None:
        expected_dbe = _calc_dbe_from_formula(formula)
        # Relies on RDKit default sanitization for aromaticity perception;
        # intentionally outside FIX-11 scope (the explicit aromatization
        # hardening lives in HOSECodeGenerator.prepare_mol on the prediction path).
        mol = Chem.MolFromSmiles(solution.smiles)
        if mol is not None:
            actual_dbe = _calc_dbe_from_mol(mol)
            if abs(actual_dbe - expected_dbe) > 1:
                return False

    return True


class SolutionRanker:
    """Rank LSD solutions by comparing predicted vs experimental 13C shifts.

    Uses the local HOSE-based C13Predictor to predict shifts for each
    candidate structure, then ranks by signal match count (most matches first),
    with MAE as tiebreaker.

    Example:
        >>> from ailsa import C13Predictor, SolutionRanker
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
        formula: str | None = None,
    ) -> RankingResult:
        """Rank LSD solutions by 13C spectrum similarity.

        Args:
            solutions: List of LSD solutions (must have SMILES for ranking)
            experimental_shifts: List of experimental 13C peak positions in ppm
            top_n: If specified, only return top N results
            formula: Optional molecular formula (e.g. "C12H16O3") for DBE
                plausibility check (D-09). When provided, solutions with DBE
                deviating >1 from expected are marked implausible.

        Returns:
            RankingResult with solutions sorted by match count (best first), then MAE.
            Plausible solutions appear before implausible ones; implausible solutions
            have is_plausible=False set on their RankedSolution entry.
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

            # Check for aromatic ring
            has_aromatic = False
            # Relies on RDKit default sanitization for aromaticity perception;
            # intentionally outside FIX-11 scope (the explicit aromatization
            # hardening lives in HOSECodeGenerator.prepare_mol on the prediction path).
            mol = Chem.MolFromSmiles(solution.smiles)
            if mol is not None:
                has_aromatic = any(atom.GetIsAromatic() for atom in mol.GetAtoms())

            ranked_solution = RankedSolution(
                solution_index=solution.index,
                smiles=solution.smiles,
                mae=mae,
                matched_count=matched_count,
                total_carbons=prediction.carbon_count,
                prediction_rate=prediction.success_rate,
                assignments=assignments,
                has_aromatic_ring=has_aromatic,
            )
            ranked.append(ranked_solution)

        # Chemical plausibility pre-filter (D-09): partition before MAE sort.
        # Plausible solutions are sorted by the ranking contract (matched_count desc,
        # MAE asc); implausible solutions are appended after with is_plausible=False.
        plausible = [
            r for r in ranked if _is_chemically_plausible(r, experimental_shifts, formula)
        ]
        implausible = [
            r for r in ranked if not _is_chemically_plausible(r, experimental_shifts, formula)
        ]
        plausible.sort(key=lambda r: (-r.matched_count, r.mae))
        ranked = plausible + [
            r.model_copy(update={"is_plausible": False}) for r in implausible
        ]

        # Store count before limiting
        total_ranked = len(ranked)

        # Sanity checks
        warnings: list[str] = []

        # Aromatic ring sanity check: if experimental shifts strongly suggest
        # aromaticity (>= 4 shifts in 110-160 ppm) but no plausible solutions
        # have aromatic rings, note that the pre-filter has acted.
        aromatic_shift_count = sum(
            1 for s in experimental_shifts if 110.0 <= s <= 160.0
        )
        any_aromatic = any(r.has_aromatic_ring for r in ranked)
        if aromatic_shift_count >= 4 and ranked and not any_aromatic:
            warnings.append(
                f"Aromatic ring expected ({aromatic_shift_count} shifts in "
                f"110-160 ppm) but no solutions contain aromatic rings. "
                f"Implausible solutions (no aromatic ring) are appended after "
                f"plausible ones. Consider ELIM escalation (D-02) if no plausible "
                f"solutions emerge."
            )

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
            warnings=warnings,
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
                radius_used=pred.radius_used,
                confidence=pred.confidence,
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

    @classmethod
    def from_database(
        cls,
        db_path: "str | Path",
        tolerance: float = 3.0,
        max_radius: int = 6,
    ) -> "SolutionRanker":
        """Create a SolutionRanker from a SQLite database with HOSE statistics.

        Convenience method that creates the C13Predictor from the SQLite
        database backend (the same 7.9M-entry DB used by ``ailsa predict c13``),
        mirroring ``from_table_file`` but using the richer DB lookup.

        Args:
            db_path: Path to SQLite database with HOSE statistics
            tolerance: Maximum ppm difference for matching (default: 3.0)
            max_radius: Maximum HOSE radius for prediction (default: 6)

        Returns:
            Configured SolutionRanker instance
        """
        from pathlib import Path

        predictor = C13Predictor.from_database(Path(db_path), max_radius=max_radius)
        return cls(predictor, tolerance=tolerance)
