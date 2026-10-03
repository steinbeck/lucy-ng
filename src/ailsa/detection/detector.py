"""Statistical detector for structural constraints from NMR shifts."""

from __future__ import annotations

from pathlib import Path

from ailsa.database import DatabaseManager
from ailsa.detection.models import (
    BondPairInfo,
    HHBResult,
    HybridisationDistribution,
    HybridisationResult,
    NeighbourDistribution,
    NeighbourResult,
)


class StatisticalDetector:
    """Detector for statistical analysis of NMR shifts.

    Queries the HOSE statistics database to determine structural
    constraints like hybridisation state based on chemical shift ranges.

    Usage:
        with StatisticalDetector("database.db") as detector:
            result = detector.detect_hybridisation(130.5)
            print(result.summary())
    """

    def __init__(self, db_path: Path | str):
        """Initialize detector with database path.

        Args:
            db_path: Path to SQLite database with HOSE statistics
        """
        self.db_path = Path(db_path)
        self._db = DatabaseManager(self.db_path)
        self._db._connect()

    def __enter__(self) -> StatisticalDetector:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close database connection."""
        if self._db:
            self._db.close()

    def detect_hybridisation(
        self,
        shift_ppm: float,
        radius: int = 3,
        window_ppm: float = 2.0,
        threshold: float = 0.01,
    ) -> HybridisationResult:
        """Detect hybridisation state from chemical shift.

        Queries all HOSE codes at the given radius whose mean shift falls
        within [shift_ppm - window_ppm, shift_ppm + window_ppm], aggregates
        their hybridisation counts, and computes frequency distributions.

        States below the threshold are filtered out (set to 0.0).

        Args:
            shift_ppm: Target chemical shift in ppm
            radius: HOSE code radius (1-6, default: 3)
            window_ppm: Window size in ppm (default: 2.0)
            threshold: Minimum frequency to include (default: 0.01 = 1%)

        Returns:
            HybridisationResult with distribution and metadata
        """
        # Query database for matching HOSE stats
        records = self._db.get_hose_stats_by_shift_window(
            shift_ppm, radius, window_ppm
        )

        # Aggregate hybridisation counts
        sp3_total = sum(r.sp3_count for r in records)
        sp2_total = sum(r.sp2_count for r in records)
        sp1_total = sum(r.sp1_count for r in records)
        total_observations = sp3_total + sp2_total + sp1_total
        unique_hose_codes = len(records)

        # Check if we have data
        if total_observations == 0:
            return HybridisationResult(
                shift_ppm=shift_ppm,
                window_ppm=window_ppm,
                radius=radius,
                threshold=threshold,
                distribution=HybridisationDistribution(),
                total_observations=0,
                unique_hose_codes=unique_hose_codes,
                has_data=False,
                warning=(
                    "No hybridisation data found. "
                    "Database may need regeneration with v4 schema."
                ),
            )

        # Compute raw frequencies
        sp3_freq = sp3_total / total_observations
        sp2_freq = sp2_total / total_observations
        sp1_freq = sp1_total / total_observations

        # Apply threshold filter
        if sp3_freq < threshold:
            sp3_freq = 0.0
        if sp2_freq < threshold:
            sp2_freq = 0.0
        if sp1_freq < threshold:
            sp1_freq = 0.0

        # Normalize remaining frequencies to sum to 1.0
        remaining_total = sp3_freq + sp2_freq + sp1_freq
        if remaining_total > 0:
            sp3_freq /= remaining_total
            sp2_freq /= remaining_total
            sp1_freq /= remaining_total

        distribution = HybridisationDistribution(
            sp3=sp3_freq,
            sp2=sp2_freq,
            sp1=sp1_freq,
        )

        return HybridisationResult(
            shift_ppm=shift_ppm,
            window_ppm=window_ppm,
            radius=radius,
            threshold=threshold,
            distribution=distribution,
            total_observations=total_observations,
            unique_hose_codes=unique_hose_codes,
            has_data=True,
        )

    def detect_neighbours(
        self,
        shift_ppm: float,
        radius: int = 3,
        window_ppm: float = 2.0,
        forbidden_threshold: float = 0.01,
        mandatory_threshold: float = 0.95,
    ) -> NeighbourResult:
        """Detect bond partner element constraints from chemical shift.

        Queries all HOSE codes at the given radius whose mean shift falls
        within [shift_ppm - window_ppm, shift_ppm + window_ppm], aggregates
        their neighbour element counts, and computes frequency distributions.

        Elements are classified as forbidden (< forbidden_threshold),
        typical (between thresholds), or mandatory (> mandatory_threshold).

        Args:
            shift_ppm: Target chemical shift in ppm
            radius: HOSE code radius (1-6, default: 3)
            window_ppm: Window size in ppm (default: 2.0)
            forbidden_threshold: Minimum frequency to not be forbidden (default: 0.01 = 1%)
            mandatory_threshold: Minimum frequency to be mandatory (default: 0.95 = 95%)

        Returns:
            NeighbourResult with distribution, constraints, and metadata
        """
        # Query database for matching HOSE stats
        records = self._db.get_hose_stats_by_shift_window(
            shift_ppm, radius, window_ppm
        )

        unique_hose_codes = len(records)
        total_observations = sum(r.count for r in records)

        # Check if we have any records
        if total_observations == 0:
            return NeighbourResult(
                shift_ppm=shift_ppm,
                window_ppm=window_ppm,
                radius=radius,
                forbidden_threshold=forbidden_threshold,
                mandatory_threshold=mandatory_threshold,
                distribution=NeighbourDistribution(),
                constraints=[],
                total_observations=0,
                unique_hose_codes=0,
                has_data=False,
                warning="No data found for this shift range.",
            )

        # Aggregate neighbour counts
        has_carbon = sum(r.has_carbon_neighbor for r in records)
        has_oxygen = sum(r.has_oxygen_neighbor for r in records)
        has_nitrogen = sum(r.has_nitrogen_neighbor for r in records)
        has_sulfur = sum(r.has_sulfur_neighbor for r in records)
        has_halogen = sum(r.has_halogen_neighbor for r in records)

        # Check if all neighbour columns are zero (database has data but no neighbour info)
        if (
            has_carbon == 0
            and has_oxygen == 0
            and has_nitrogen == 0
            and has_sulfur == 0
            and has_halogen == 0
        ):
            return NeighbourResult(
                shift_ppm=shift_ppm,
                window_ppm=window_ppm,
                radius=radius,
                forbidden_threshold=forbidden_threshold,
                mandatory_threshold=mandatory_threshold,
                distribution=NeighbourDistribution(),
                constraints=[],
                total_observations=total_observations,
                unique_hose_codes=unique_hose_codes,
                has_data=False,
                warning=(
                    "Neighbour columns are unpopulated. "
                    "Database needs regeneration with v5 schema."
                ),
            )

        # Compute frequencies
        carbon_freq = has_carbon / total_observations
        oxygen_freq = has_oxygen / total_observations
        nitrogen_freq = has_nitrogen / total_observations
        sulfur_freq = has_sulfur / total_observations
        halogen_freq = has_halogen / total_observations

        # Create distribution
        distribution = NeighbourDistribution(
            carbon=carbon_freq,
            oxygen=oxygen_freq,
            nitrogen=nitrogen_freq,
            sulfur=sulfur_freq,
            halogen=halogen_freq,
        )

        # Get constraints
        constraints = distribution.get_constraints(
            forbidden_threshold=forbidden_threshold,
            mandatory_threshold=mandatory_threshold,
        )

        return NeighbourResult(
            shift_ppm=shift_ppm,
            window_ppm=window_ppm,
            radius=radius,
            forbidden_threshold=forbidden_threshold,
            mandatory_threshold=mandatory_threshold,
            distribution=distribution,
            constraints=constraints,
            total_observations=total_observations,
            unique_hose_codes=unique_hose_codes,
            has_data=True,
        )

    def detect_hhb(
        self,
        formula: str,
        threshold: float = 0.01,
    ) -> HHBResult:
        """Detect allowed hetero-hetero bonds for a molecular formula.

        Queries the bond_pair_stats table for which heteroatom-heteroatom
        bonds (O-O, O-N, N-N, N-S, etc.) occur in compounds with the
        given formula. Bonds below the threshold are classified as forbidden.

        Args:
            formula: Molecular formula (e.g., "C10H14O2")
            threshold: Minimum frequency for allowed bond (default: 0.01 = 1%)

        Returns:
            HHBResult with allowed and forbidden bond pairs
        """
        import re

        # Check if formula has heteroatoms (elements other than C and H)
        # Simple check: look for N, O, S, F, Cl, Br, I, P, Si
        heteroatom_pattern = r"(N|O|S|F|Cl|Br|I|P|Si)"
        has_heteroatoms = bool(re.search(heteroatom_pattern, formula))

        if not has_heteroatoms:
            return HHBResult(
                formula=formula,
                threshold=threshold,
                has_heteroatoms=False,
            )

        # Query bond pair stats by formula
        records = self._db.get_bond_pair_stats_by_formula(formula)

        # If no records found, check if formula exists in compounds table
        if not records:
            # Get total compound count for this formula
            cursor = self._db.connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM compounds WHERE formula_normalized = ?",
                (formula,),
            )
            result = cursor.fetchone()
            total_compounds = result[0] if result else 0

            if total_compounds == 0:
                return HHBResult(
                    formula=formula,
                    threshold=threshold,
                    has_data=False,
                    warning=f"Formula '{formula}' not found in database",
                )
            else:
                # Formula exists but no HHB bonds found (valid - many compounds have only C-X bonds)
                return HHBResult(
                    formula=formula,
                    threshold=threshold,
                    has_data=True,
                    total_compounds=total_compounds,
                    allowed_pairs=[],
                    forbidden_pairs=[],
                )

        # Get total compounds for this formula from first record
        total_compounds = records[0].total_compounds if records else 0

        # Classify each bond pair
        allowed_pairs = []
        forbidden_pairs = []

        for record in records:
            pair_info = BondPairInfo(
                element1=record.element1,
                element2=record.element2,
                frequency=record.frequency,
                compound_count=record.compound_count,
            )

            if record.frequency >= threshold:
                allowed_pairs.append(pair_info)
            else:
                forbidden_pairs.append(pair_info)

        return HHBResult(
            formula=formula,
            threshold=threshold,
            allowed_pairs=allowed_pairs,
            forbidden_pairs=forbidden_pairs,
            total_compounds=total_compounds,
            has_data=True,
        )

