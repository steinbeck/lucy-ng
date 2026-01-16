"""Generate HOSE statistics from database compounds."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import TYPE_CHECKING

from tqdm import tqdm

from lucy_ng.database.models import HOSEStatsRecord

from .hose import HOSECodeGenerator

if TYPE_CHECKING:
    from lucy_ng.database import DatabaseManager


class HOSEStatsGenerator:
    """Generate HOSE code statistics from database compounds.

    Processes all compounds in the database, generates HOSE codes for each
    carbon with a known shift, and computes aggregated statistics (mean, std, count)
    per HOSE code at each radius.

    Usage:
        with DatabaseManager("compounds.db") as db:
            generator = HOSEStatsGenerator(db, max_radius=6)
            count = generator.populate_database(progress=True)
            print(f"Generated {count} statistics")
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        max_radius: int = 6,
    ) -> None:
        """Initialize the generator.

        Args:
            db_manager: Database manager for compound iteration and stats insertion
            max_radius: Maximum HOSE code radius (1-6)
        """
        self.db_manager = db_manager
        self.max_radius = max_radius
        self._hose_gen = HOSECodeGenerator()

        # Statistics tracking
        self._compounds_processed = 0
        self._compounds_failed = 0
        self._shifts_processed = 0

    def generate_all(
        self,
        progress: bool = True,
    ) -> dict[tuple[str, int], list[float]]:
        """Generate HOSE code shift aggregates from all compounds.

        Iterates through all compounds in the database, generates HOSE codes
        for each carbon with a known shift, and aggregates shifts by
        (hose_code, radius) key.

        Args:
            progress: Show progress bar

        Returns:
            Dict mapping (hose_code, radius) to list of observed shifts
        """
        # Reset statistics
        self._compounds_processed = 0
        self._compounds_failed = 0
        self._shifts_processed = 0

        # Aggregation: {(hose_code, radius): [shift1, shift2, ...]}
        aggregates: dict[tuple[str, int], list[float]] = defaultdict(list)

        # Get total count for progress bar
        total = self.db_manager.get_compound_count()

        # Iterate through compounds
        compound_iter = self.db_manager.iter_compounds_with_shifts()
        if progress:
            compound_iter = tqdm(
                compound_iter,
                total=total,
                desc="Generating HOSE stats",
                unit=" compounds",
            )

        for _compound_id, smiles, shifts in compound_iter:
            self._compounds_processed += 1

            # Parse SMILES to RDKit mol
            mol = HOSECodeGenerator.prepare_mol(smiles)
            if mol is None:
                self._compounds_failed += 1
                continue

            # Process each carbon with a known shift
            for atom_idx, shift_ppm in shifts:
                if atom_idx is None:
                    continue

                # Verify it's a carbon
                try:
                    atom = mol.GetAtomWithIdx(atom_idx)
                    if atom.GetSymbol() != "C":
                        continue
                except Exception:
                    continue

                # Generate HOSE codes at all radii
                for radius in range(1, self.max_radius + 1):
                    try:
                        hose_code = self._hose_gen.generate_for_atom(mol, atom_idx, radius)
                        if hose_code:
                            aggregates[(hose_code, radius)].append(shift_ppm)
                            self._shifts_processed += 1
                    except Exception:
                        # Skip atoms that fail HOSE generation
                        continue

        return dict(aggregates)

    def compute_stats(
        self,
        aggregates: dict[tuple[str, int], list[float]],
    ) -> list[HOSEStatsRecord]:
        """Compute statistics from aggregated shifts.

        Args:
            aggregates: Dict mapping (hose_code, radius) to list of shifts

        Returns:
            List of HOSEStatsRecord with mean, std, count
        """
        stats: list[HOSEStatsRecord] = []

        for (hose_code, radius), shifts in aggregates.items():
            if not shifts:
                continue

            mean = statistics.mean(shifts)
            std = statistics.stdev(shifts) if len(shifts) > 1 else 0.0
            count = len(shifts)

            stats.append(
                HOSEStatsRecord(
                    hose_code=hose_code,
                    radius=radius,
                    mean=mean,
                    std=std,
                    count=count,
                )
            )

        return stats

    def populate_database(
        self,
        progress: bool = True,
        batch_size: int = 10000,
    ) -> int:
        """Generate HOSE statistics and insert into database.

        This is the main entry point for batch HOSE generation.
        Processes all compounds, computes statistics, and inserts into
        the hose_stats table.

        Args:
            progress: Show progress bar during generation
            batch_size: Batch size for database insertion

        Returns:
            Number of statistics entries inserted
        """
        # Generate aggregates
        aggregates = self.generate_all(progress=progress)

        # Compute statistics
        stats = self.compute_stats(aggregates)

        # Insert into database
        count = self.db_manager.insert_hose_stats_batch(stats, batch_size=batch_size)

        return count

    @property
    def compounds_processed(self) -> int:
        """Number of compounds processed in last run."""
        return self._compounds_processed

    @property
    def compounds_failed(self) -> int:
        """Number of compounds that failed parsing in last run."""
        return self._compounds_failed

    @property
    def shifts_processed(self) -> int:
        """Number of shift observations processed in last run."""
        return self._shifts_processed
