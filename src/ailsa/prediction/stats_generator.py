"""Generate HOSE statistics from database compounds."""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rdkit.Chem import HybridizationType
from tqdm import tqdm

from ailsa.database.models import HOSEStatsRecord
from ailsa.prediction.hose_parser import parse_sphere_1

from .hose import HOSECodeGenerator

if TYPE_CHECKING:
    from ailsa.database import DatabaseManager


def extract_hybridisation(atom) -> str:
    """Extract hybridisation state from RDKit atom.

    Returns "sp3", "sp2", or "sp1". Treats S and UNSPECIFIED as sp3.
    Works on molecules with implicit hydrogens (ailsa standard).

    CRITICAL: Never call AddHs() on molecules before this function.
    """
    hyb = atom.GetHybridization()
    mapping = {
        HybridizationType.SP3: "sp3",
        HybridizationType.SP2: "sp2",
        HybridizationType.SP: "sp1",
        HybridizationType.S: "sp3",
        HybridizationType.UNSPECIFIED: "sp3",
    }
    return mapping.get(hyb, "sp3")


# Checkpoint keys for resumable generation
CHECKPOINT_KEY_LAST_COMPOUND_ID = "hose_stats_last_compound_id"
CHECKPOINT_KEY_COMPOUNDS_PROCESSED = "hose_stats_compounds_processed"
CHECKPOINT_KEY_COMPOUNDS_FAILED = "hose_stats_compounds_failed"
CHECKPOINT_KEY_SHIFTS_PROCESSED = "hose_stats_shifts_processed"


@dataclass
class WelfordAccumulator:
    """Online algorithm for computing mean and variance in a single pass.

    Implements Welford's online algorithm which is numerically stable and
    requires O(1) memory per accumulator. Also supports parallel merging
    of multiple accumulators.

    Usage:
        acc = WelfordAccumulator()
        for value in data:
            acc.update(value)
        print(f"Mean: {acc.mean}, Std: {acc.std}")

    Reference:
        Welford, B. P. (1962). "Note on a method for calculating corrected
        sums of squares and products". Technometrics.
    """

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0  # Sum of squared differences from mean
    sp3_count: int = 0
    sp2_count: int = 0
    sp1_count: int = 0
    has_carbon_neighbor: int = 0
    has_oxygen_neighbor: int = 0
    has_nitrogen_neighbor: int = 0
    has_sulfur_neighbor: int = 0
    has_halogen_neighbor: int = 0
    # Ring membership counts (Phase 36)
    in_3ring: int = 0  # Observations where atom is in 3-membered ring
    in_4ring: int = 0  # Observations where atom is in 4-membered ring
    in_aromatic: int = 0  # Observations where atom is aromatic

    def update(self, value: float) -> None:
        """Add a single observation using Welford's algorithm.

        Args:
            value: New observation to incorporate
        """
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def update_with_hybridisation(self, value: float, hybridisation: str) -> None:
        """Add a single observation with hybridisation state tracking.

        Args:
            value: New shift observation to incorporate
            hybridisation: Hybridisation state ("sp3", "sp2", or "sp1")
        """
        self.update(value)
        if hybridisation == "sp3":
            self.sp3_count += 1
        elif hybridisation == "sp2":
            self.sp2_count += 1
        elif hybridisation == "sp1":
            self.sp1_count += 1

    def update_with_neighbors(
        self, value: float, hybridisation: str, neighbors: dict[str, int]
    ) -> None:
        """Add a single observation with hybridisation and neighbour element tracking.

        Args:
            value: New shift observation to incorporate
            hybridisation: Hybridisation state ("sp3", "sp2", or "sp1")
            neighbors: Dict mapping element symbol to count (from parse_sphere_1)
        """
        # Handle shift and hybridisation
        self.update_with_hybridisation(value, hybridisation)

        # Track neighbour presence
        if neighbors.get("C", 0) > 0:
            self.has_carbon_neighbor += 1
        if neighbors.get("O", 0) > 0:
            self.has_oxygen_neighbor += 1
        if neighbors.get("N", 0) > 0:
            self.has_nitrogen_neighbor += 1
        if neighbors.get("S", 0) > 0:
            self.has_sulfur_neighbor += 1

        # Halogen aggregation (F, Cl, Br, I)
        if any(neighbors.get(hal, 0) > 0 for hal in ("F", "Cl", "Br", "I")):
            self.has_halogen_neighbor += 1

    def update_with_rings(
        self,
        value: float,
        hybridisation: str,
        neighbors: dict[str, int],
        atom_idx: int,
        mol,  # rdkit.Chem.Mol
    ) -> None:
        """Add observation with ring membership data.

        Calls update_with_neighbors() internally for hybridisation and
        neighbour tracking, then checks ring membership.

        Args:
            value: Chemical shift in ppm
            hybridisation: "sp3", "sp2", or "sp1"
            neighbors: Dict from parse_sphere_1()
            atom_idx: Atom index in RDKit molecule
            mol: RDKit molecule object
        """
        self.update_with_neighbors(value, hybridisation, neighbors)

        ring_info = mol.GetRingInfo()
        atom = mol.GetAtomWithIdx(atom_idx)

        if ring_info.IsAtomInRingOfSize(atom_idx, 3):
            self.in_3ring += 1
        if ring_info.IsAtomInRingOfSize(atom_idx, 4):
            self.in_4ring += 1
        if atom.GetIsAromatic():
            self.in_aromatic += 1

    @property
    def variance(self) -> float:
        """Population variance of observations."""
        if self.count < 2:
            return 0.0
        return self.m2 / self.count

    @property
    def std(self) -> float:
        """Population standard deviation of observations."""
        return math.sqrt(self.variance)

    def merge(self, other: WelfordAccumulator) -> WelfordAccumulator:
        """Merge another accumulator using parallel Welford algorithm.

        This allows combining statistics from multiple chunks without
        needing to store all original observations.

        Args:
            other: Another accumulator to merge with this one

        Returns:
            New accumulator with combined statistics
        """
        if other.count == 0:
            return WelfordAccumulator(
                count=self.count,
                mean=self.mean,
                m2=self.m2,
                sp3_count=self.sp3_count,
                sp2_count=self.sp2_count,
                sp1_count=self.sp1_count,
                has_carbon_neighbor=self.has_carbon_neighbor,
                has_oxygen_neighbor=self.has_oxygen_neighbor,
                has_nitrogen_neighbor=self.has_nitrogen_neighbor,
                has_sulfur_neighbor=self.has_sulfur_neighbor,
                has_halogen_neighbor=self.has_halogen_neighbor,
                in_3ring=self.in_3ring,
                in_4ring=self.in_4ring,
                in_aromatic=self.in_aromatic,
            )
        if self.count == 0:
            return WelfordAccumulator(
                count=other.count,
                mean=other.mean,
                m2=other.m2,
                sp3_count=other.sp3_count,
                sp2_count=other.sp2_count,
                sp1_count=other.sp1_count,
                has_carbon_neighbor=other.has_carbon_neighbor,
                has_oxygen_neighbor=other.has_oxygen_neighbor,
                has_nitrogen_neighbor=other.has_nitrogen_neighbor,
                has_sulfur_neighbor=other.has_sulfur_neighbor,
                has_halogen_neighbor=other.has_halogen_neighbor,
                in_3ring=other.in_3ring,
                in_4ring=other.in_4ring,
                in_aromatic=other.in_aromatic,
            )

        combined_count = self.count + other.count
        delta = other.mean - self.mean
        combined_mean = self.mean + delta * (other.count / combined_count)
        combined_m2 = (
            self.m2
            + other.m2
            + delta * delta * (self.count * other.count / combined_count)
        )

        merged = WelfordAccumulator(
            count=combined_count,
            mean=combined_mean,
            m2=combined_m2,
        )
        merged.sp3_count = self.sp3_count + other.sp3_count
        merged.sp2_count = self.sp2_count + other.sp2_count
        merged.sp1_count = self.sp1_count + other.sp1_count
        merged.has_carbon_neighbor = self.has_carbon_neighbor + other.has_carbon_neighbor
        merged.has_oxygen_neighbor = self.has_oxygen_neighbor + other.has_oxygen_neighbor
        merged.has_nitrogen_neighbor = self.has_nitrogen_neighbor + other.has_nitrogen_neighbor
        merged.has_sulfur_neighbor = self.has_sulfur_neighbor + other.has_sulfur_neighbor
        merged.has_halogen_neighbor = self.has_halogen_neighbor + other.has_halogen_neighbor
        merged.in_3ring = self.in_3ring + other.in_3ring
        merged.in_4ring = self.in_4ring + other.in_4ring
        merged.in_aromatic = self.in_aromatic + other.in_aromatic

        return merged

    def to_tuple(
        self,
    ) -> tuple[int, float, float, int, int, int, int, int, int, int, int, int, int, int]:
        """Export as 14-element tuple for database storage.

        Returns:
            Tuple of (count, mean, m2, sp3_count, sp2_count, sp1_count,
                      has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                      has_sulfur_neighbor, has_halogen_neighbor,
                      in_3ring, in_4ring, in_aromatic)
        """
        return (
            self.count,
            self.mean,
            self.m2,
            self.sp3_count,
            self.sp2_count,
            self.sp1_count,
            self.has_carbon_neighbor,
            self.has_oxygen_neighbor,
            self.has_nitrogen_neighbor,
            self.has_sulfur_neighbor,
            self.has_halogen_neighbor,
            self.in_3ring,
            self.in_4ring,
            self.in_aromatic,
        )


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
    ) -> tuple[
        dict[tuple[str, int], list[float]],
        dict[tuple[str, int], dict[str, int]],
        dict[tuple[str, int], dict[str, int]],
        dict[tuple[str, int], dict[str, int]],
    ]:
        """Generate HOSE code shift aggregates from all compounds.

        Iterates through all compounds in the database, generates HOSE codes
        for each carbon with a known shift, and aggregates shifts by
        (hose_code, radius) key.

        Args:
            progress: Show progress bar

        Returns:
            Tuple of:
            - Dict mapping (hose_code, radius) to list of observed shifts
            - Dict mapping (hose_code, radius) to hybridisation counts
            - Dict mapping (hose_code, radius) to neighbour element counts
            - Dict mapping (hose_code, radius) to ring membership counts
        """
        # Reset statistics
        self._compounds_processed = 0
        self._compounds_failed = 0
        self._shifts_processed = 0

        # Aggregation: {(hose_code, radius): [shift1, shift2, ...]}
        aggregates: dict[tuple[str, int], list[float]] = defaultdict(list)

        # Hybridisation counts: {(hose_code, radius): {"sp3": N, "sp2": M, "sp1": K}}
        hybridisations: dict[tuple[str, int], dict[str, int]] = defaultdict(
            lambda: {"sp3": 0, "sp2": 0, "sp1": 0}
        )

        # Neighbour element counts: {(hose_code, radius): {"C": N, "O": M, ...}}
        neighbour_counts: dict[tuple[str, int], dict[str, int]] = defaultdict(
            lambda: {"C": 0, "O": 0, "N": 0, "S": 0, "halogen": 0}
        )

        # Ring membership counts: {(hose_code, radius): {"3ring": N, "4ring": M, "aromatic": K}}
        ring_counts: dict[tuple[str, int], dict[str, int]] = defaultdict(
            lambda: {"3ring": 0, "4ring": 0, "aromatic": 0}
        )

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

                # Extract hybridisation once per atom
                hybridisation = extract_hybridisation(atom)

                # Generate HOSE codes at all radii
                for radius in range(1, self.max_radius + 1):
                    try:
                        hose_code = self._hose_gen.generate_for_atom(mol, atom_idx, radius)
                        if hose_code:
                            aggregates[(hose_code, radius)].append(shift_ppm)
                            hybridisations[(hose_code, radius)][hybridisation] += 1

                            # Parse sphere 1 and track neighbour presence
                            neighbors = parse_sphere_1(hose_code)
                            if neighbors.get("C", 0) > 0:
                                neighbour_counts[(hose_code, radius)]["C"] += 1
                            if neighbors.get("O", 0) > 0:
                                neighbour_counts[(hose_code, radius)]["O"] += 1
                            if neighbors.get("N", 0) > 0:
                                neighbour_counts[(hose_code, radius)]["N"] += 1
                            if neighbors.get("S", 0) > 0:
                                neighbour_counts[(hose_code, radius)]["S"] += 1
                            if any(neighbors.get(hal, 0) > 0 for hal in ("F", "Cl", "Br", "I")):
                                neighbour_counts[(hose_code, radius)]["halogen"] += 1

                            # Ring membership detection (requires mol and atom_idx)
                            ring_info = mol.GetRingInfo()
                            if ring_info.IsAtomInRingOfSize(atom_idx, 3):
                                ring_counts[(hose_code, radius)]["3ring"] += 1
                            if ring_info.IsAtomInRingOfSize(atom_idx, 4):
                                ring_counts[(hose_code, radius)]["4ring"] += 1
                            if atom.GetIsAromatic():
                                ring_counts[(hose_code, radius)]["aromatic"] += 1

                            self._shifts_processed += 1
                    except Exception:
                        # Skip atoms that fail HOSE generation
                        continue

        return dict(aggregates), dict(hybridisations), dict(neighbour_counts), dict(ring_counts)

    def compute_stats(
        self,
        aggregates: dict[tuple[str, int], list[float]],
        hybridisations: dict[tuple[str, int], dict[str, int]] | None = None,
        neighbour_counts: dict[tuple[str, int], dict[str, int]] | None = None,
        ring_counts: dict[tuple[str, int], dict[str, int]] | None = None,
    ) -> list[HOSEStatsRecord]:
        """Compute statistics from aggregated shifts.

        Args:
            aggregates: Dict mapping (hose_code, radius) to list of shifts
            hybridisations: Dict mapping (hose_code, radius) to hybridisation counts
            neighbour_counts: Dict mapping (hose_code, radius) to neighbour element counts
            ring_counts: Dict mapping (hose_code, radius) to ring membership counts

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

            # Get hybridisation counts if provided
            if hybridisations and (hose_code, radius) in hybridisations:
                hyb_counts = hybridisations[(hose_code, radius)]
                sp3_count = hyb_counts.get("sp3", 0)
                sp2_count = hyb_counts.get("sp2", 0)
                sp1_count = hyb_counts.get("sp1", 0)
            else:
                sp3_count = 0
                sp2_count = 0
                sp1_count = 0

            # Get neighbour counts if provided
            if neighbour_counts and (hose_code, radius) in neighbour_counts:
                nb_counts = neighbour_counts[(hose_code, radius)]
                has_carbon_neighbor = nb_counts.get("C", 0)
                has_oxygen_neighbor = nb_counts.get("O", 0)
                has_nitrogen_neighbor = nb_counts.get("N", 0)
                has_sulfur_neighbor = nb_counts.get("S", 0)
                has_halogen_neighbor = nb_counts.get("halogen", 0)
            else:
                has_carbon_neighbor = 0
                has_oxygen_neighbor = 0
                has_nitrogen_neighbor = 0
                has_sulfur_neighbor = 0
                has_halogen_neighbor = 0

            # Get ring counts if provided
            if ring_counts and (hose_code, radius) in ring_counts:
                rc = ring_counts[(hose_code, radius)]
                in_3ring = rc.get("3ring", 0)
                in_4ring = rc.get("4ring", 0)
                in_aromatic = rc.get("aromatic", 0)
            else:
                in_3ring = 0
                in_4ring = 0
                in_aromatic = 0

            stats.append(
                HOSEStatsRecord(
                    hose_code=hose_code,
                    radius=radius,
                    mean=mean,
                    std=std,
                    count=count,
                    sp3_count=sp3_count,
                    sp2_count=sp2_count,
                    sp1_count=sp1_count,
                    has_carbon_neighbor=has_carbon_neighbor,
                    has_oxygen_neighbor=has_oxygen_neighbor,
                    has_nitrogen_neighbor=has_nitrogen_neighbor,
                    has_sulfur_neighbor=has_sulfur_neighbor,
                    has_halogen_neighbor=has_halogen_neighbor,
                    in_3ring=in_3ring,
                    in_4ring=in_4ring,
                    in_aromatic=in_aromatic,
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
        # Generate aggregates, hybridisation counts, neighbour counts, and ring counts
        aggregates, hybridisations, neighbour_counts, ring_counts = self.generate_all(
            progress=progress
        )

        # Compute statistics
        stats = self.compute_stats(aggregates, hybridisations, neighbour_counts, ring_counts)

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


class ResumableHOSEStatsGenerator:
    """Resumable, checkpointed HOSE statistics generator.

    Unlike HOSEStatsGenerator which loads all data into memory, this generator:
    - Processes compounds in chunks (default 10K)
    - Saves checkpoint after each chunk for resume capability
    - Uses Welford's online algorithm for O(1) memory per HOSE code
    - Supports file-based logging for detached operation (nohup)

    The generator uses incremental database upserts that merge statistics
    using Welford's parallel algorithm, allowing safe resume from any point.

    Usage:
        with DatabaseManager("compounds.db") as db:
            generator = ResumableHOSEStatsGenerator(db, max_radius=6)
            result = generator.run(
                chunk_size=10000,
                log_file="hose_generation.log",
                resume=True,  # Continue from checkpoint
            )
            print(f"Processed {result.compounds_processed} compounds")

    For production runs:
        nohup ailsa database generate-hose-stats --log-file hose.log &
        tail -f hose.log  # Monitor progress
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        max_radius: int = 6,
    ) -> None:
        """Initialize the resumable generator.

        Args:
            db_manager: Database manager for compound iteration and stats insertion
            max_radius: Maximum HOSE code radius (1-6)
        """
        self.db_manager = db_manager
        self.max_radius = max_radius
        self._hose_gen = HOSECodeGenerator()
        self._logger = logging.getLogger("ailsa.hose_stats")

        # Statistics tracking (persisted to checkpoint)
        self._compounds_processed = 0
        self._compounds_failed = 0
        self._shifts_processed = 0
        self._last_compound_id = 0

    def _setup_logging(self, log_file: Path | str | None) -> None:
        """Configure logging for file-based output.

        Args:
            log_file: Path to log file, or None for console only
        """
        self._logger.setLevel(logging.INFO)

        # Clear existing handlers
        self._logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        if log_file:
            # File handler for detached operation
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        else:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

    def _load_checkpoint(self) -> bool:
        """Load checkpoint from database if exists.

        Returns:
            True if checkpoint was loaded, False if starting fresh
        """
        last_id = self.db_manager.get_checkpoint(CHECKPOINT_KEY_LAST_COMPOUND_ID)
        if last_id is None:
            return False

        self._last_compound_id = int(last_id)

        processed = self.db_manager.get_checkpoint(CHECKPOINT_KEY_COMPOUNDS_PROCESSED)
        if processed:
            self._compounds_processed = int(processed)

        failed = self.db_manager.get_checkpoint(CHECKPOINT_KEY_COMPOUNDS_FAILED)
        if failed:
            self._compounds_failed = int(failed)

        shifts = self.db_manager.get_checkpoint(CHECKPOINT_KEY_SHIFTS_PROCESSED)
        if shifts:
            self._shifts_processed = int(shifts)

        return True

    def _save_checkpoint(self) -> None:
        """Save current progress to checkpoint."""
        self.db_manager.set_checkpoint(
            CHECKPOINT_KEY_LAST_COMPOUND_ID, str(self._last_compound_id)
        )
        self.db_manager.set_checkpoint(
            CHECKPOINT_KEY_COMPOUNDS_PROCESSED, str(self._compounds_processed)
        )
        self.db_manager.set_checkpoint(
            CHECKPOINT_KEY_COMPOUNDS_FAILED, str(self._compounds_failed)
        )
        self.db_manager.set_checkpoint(
            CHECKPOINT_KEY_SHIFTS_PROCESSED, str(self._shifts_processed)
        )

    def _clear_checkpoint(self) -> None:
        """Clear all checkpoints."""
        self.db_manager.clear_checkpoint(CHECKPOINT_KEY_LAST_COMPOUND_ID)
        self.db_manager.clear_checkpoint(CHECKPOINT_KEY_COMPOUNDS_PROCESSED)
        self.db_manager.clear_checkpoint(CHECKPOINT_KEY_COMPOUNDS_FAILED)
        self.db_manager.clear_checkpoint(CHECKPOINT_KEY_SHIFTS_PROCESSED)

    def _process_chunk(
        self,
        start_id: int,
        chunk_size: int,
    ) -> tuple[dict[tuple[str, int], WelfordAccumulator], int, int, int, int]:
        """Process a chunk of compounds.

        Args:
            start_id: Start from this compound ID (exclusive)
            chunk_size: Maximum compounds to process in this chunk

        Returns:
            Tuple of:
            - Dict mapping (hose_code, radius) to WelfordAccumulator
            - Number of compounds processed
            - Number of compounds failed
            - Number of shifts processed
            - Last compound ID processed
        """
        accumulators: dict[tuple[str, int], WelfordAccumulator] = defaultdict(
            WelfordAccumulator
        )
        compounds_processed = 0
        compounds_failed = 0
        shifts_processed = 0
        last_id = start_id

        for compound_id, smiles, shifts in self.db_manager.iter_compounds_with_shifts_from(
            start_id=start_id, batch_size=100
        ):
            if compounds_processed >= chunk_size:
                break

            last_id = compound_id
            compounds_processed += 1

            # Parse SMILES
            mol = HOSECodeGenerator.prepare_mol(smiles)
            if mol is None:
                compounds_failed += 1
                continue

            # Process each carbon
            for atom_idx, shift_ppm in shifts:
                if atom_idx is None:
                    continue

                try:
                    atom = mol.GetAtomWithIdx(atom_idx)
                    if atom.GetSymbol() != "C":
                        continue
                except Exception:
                    continue

                # Extract hybridisation once per atom
                hybridisation = extract_hybridisation(atom)

                # Generate HOSE codes at all radii
                for radius in range(1, self.max_radius + 1):
                    try:
                        hose_code = self._hose_gen.generate_for_atom(mol, atom_idx, radius)
                        if hose_code:
                            # Parse sphere 1 for neighbour elements
                            neighbors = parse_sphere_1(hose_code)
                            accumulators[(hose_code, radius)].update_with_rings(
                                shift_ppm, hybridisation, neighbors, atom_idx, mol
                            )
                            shifts_processed += 1
                    except Exception:
                        continue

        return accumulators, compounds_processed, compounds_failed, shifts_processed, last_id

    def _upsert_chunk_stats(
        self,
        accumulators: dict[tuple[str, int], WelfordAccumulator],
    ) -> int:
        """Upsert chunk statistics to database.

        Args:
            accumulators: Dict mapping (hose_code, radius) to WelfordAccumulator

        Returns:
            Number of records upserted
        """
        if not accumulators:
            return 0

        # Convert to tuple format for upsert
        # Prepend hose_code and radius to the 14-element to_tuple() result
        # Result: 16-element tuple for v6 schema
        stats = [
            (hose_code, radius) + acc.to_tuple()
            for (hose_code, radius), acc in accumulators.items()
            if acc.count > 0
        ]

        return self.db_manager.upsert_hose_stats_incremental(stats)

    def run(
        self,
        chunk_size: int = 10000,
        log_file: Path | str | None = None,
        resume: bool = True,
        fresh: bool = False,
    ) -> ResumableHOSEStatsResult:
        """Run the resumable HOSE statistics generation.

        Args:
            chunk_size: Number of compounds to process per chunk
            log_file: Path to log file for detached operation
            resume: If True, resume from checkpoint if exists
            fresh: If True, clear existing stats and checkpoint before starting

        Returns:
            ResumableHOSEStatsResult with generation statistics
        """
        self._setup_logging(log_file)

        # Handle fresh start
        if fresh:
            self._logger.info("Fresh start requested, clearing existing data...")
            self.db_manager.clear_hose_stats()
            self._clear_checkpoint()
            self._last_compound_id = 0
            self._compounds_processed = 0
            self._compounds_failed = 0
            self._shifts_processed = 0

        # Try to resume from checkpoint
        if resume and not fresh:
            if self._load_checkpoint():
                self._logger.info(
                    f"Resuming from checkpoint: last_id={self._last_compound_id}, "
                    f"processed={self._compounds_processed}"
                )
            else:
                self._logger.info("No checkpoint found, starting fresh")

        # Get total compound count and max ID for progress estimation
        total_compounds = self.db_manager.get_compound_count()
        max_compound_id = self.db_manager.get_max_compound_id()

        self._logger.info(
            f"Starting HOSE statistics generation: "
            f"total_compounds={total_compounds}, max_radius={self.max_radius}, "
            f"chunk_size={chunk_size}"
        )

        # Process in chunks
        chunk_num = 0
        total_upserted = 0

        while True:
            chunk_num += 1

            # Process chunk
            accumulators, processed, failed, shifts, last_id = self._process_chunk(
                self._last_compound_id, chunk_size
            )

            if processed == 0:
                # No more compounds to process
                break

            # Update totals
            self._compounds_processed += processed
            self._compounds_failed += failed
            self._shifts_processed += shifts
            self._last_compound_id = last_id

            # Upsert to database
            upserted = self._upsert_chunk_stats(accumulators)
            total_upserted += upserted

            # Save checkpoint
            self._save_checkpoint()

            # Calculate progress
            if max_compound_id > 0:
                progress = (self._last_compound_id / max_compound_id) * 100
            else:
                progress = 100.0

            self._logger.info(
                f"Chunk {chunk_num}: processed={processed}, failed={failed}, "
                f"shifts={shifts}, upserted={upserted}, progress={progress:.1f}%"
            )

        # Clear checkpoint on successful completion
        self._clear_checkpoint()

        total_stats = self.db_manager.get_hose_stats_count()

        self._logger.info(
            f"Generation complete: compounds={self._compounds_processed}, "
            f"failed={self._compounds_failed}, shifts={self._shifts_processed}, "
            f"total_stats={total_stats}"
        )

        return ResumableHOSEStatsResult(
            compounds_processed=self._compounds_processed,
            compounds_failed=self._compounds_failed,
            shifts_processed=self._shifts_processed,
            total_stats=total_stats,
        )

    @property
    def compounds_processed(self) -> int:
        """Number of compounds processed."""
        return self._compounds_processed

    @property
    def compounds_failed(self) -> int:
        """Number of compounds that failed parsing."""
        return self._compounds_failed

    @property
    def shifts_processed(self) -> int:
        """Number of shift observations processed."""
        return self._shifts_processed


@dataclass
class ResumableHOSEStatsResult:
    """Result of resumable HOSE statistics generation."""

    compounds_processed: int
    compounds_failed: int
    shifts_processed: int
    total_stats: int


class SDFHOSEStatsGenerator:
    """Generate HOSE statistics directly from COCONUT SDF file.

    This generator reads mol objects directly from the SDF file rather than
    parsing SMILES, ensuring correct atom indexing. COCONUT uses 1-based
    atom indices in the CNMR_SHIFTS field, which this class handles correctly.

    Key differences from ResumableHOSEStatsGenerator:
    - Reads mol objects directly from SDF (preserves atom ordering)
    - Parses CNMR_SHIFTS field with 1-based to 0-based index conversion
    - Does not use the database for compound iteration (only for stats storage)

    Usage:
        with DatabaseManager("compounds.db") as db:
            generator = SDFHOSEStatsGenerator(
                db, "data/reference/predicted_coconut.sdf", max_radius=6
            )
            result = generator.run(chunk_size=10000)
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        sdf_path: Path | str,
        max_radius: int = 6,
    ) -> None:
        """Initialize the SDF-based generator.

        Args:
            db_manager: Database manager for stats storage
            sdf_path: Path to COCONUT SDF file
            max_radius: Maximum HOSE code radius (1-6)
        """
        from rdkit import Chem

        self.db_manager = db_manager
        self.sdf_path = Path(sdf_path)
        self.max_radius = max_radius
        self._hose_gen = HOSECodeGenerator()
        self._logger = logging.getLogger("ailsa.hose_stats_sdf")

        # Create supplier
        self._supplier = Chem.SDMolSupplier(str(self.sdf_path))

        # Statistics tracking
        self._compounds_processed = 0
        self._compounds_failed = 0
        self._shifts_processed = 0
        self._mol_index = 0

    def _setup_logging(self, log_file: Path | str | None) -> None:
        """Configure logging for file-based output."""
        self._logger.setLevel(logging.INFO)
        self._logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        if log_file:
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        else:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

    def _load_checkpoint(self) -> bool:
        """Load checkpoint from database if exists."""
        mol_idx = self.db_manager.get_checkpoint("sdf_hose_stats_mol_index")
        if mol_idx is None:
            return False

        self._mol_index = int(mol_idx)

        processed = self.db_manager.get_checkpoint("sdf_hose_stats_compounds_processed")
        if processed:
            self._compounds_processed = int(processed)

        failed = self.db_manager.get_checkpoint("sdf_hose_stats_compounds_failed")
        if failed:
            self._compounds_failed = int(failed)

        shifts = self.db_manager.get_checkpoint("sdf_hose_stats_shifts_processed")
        if shifts:
            self._shifts_processed = int(shifts)

        return True

    def _save_checkpoint(self) -> None:
        """Save current progress to checkpoint."""
        self.db_manager.set_checkpoint("sdf_hose_stats_mol_index", str(self._mol_index))
        self.db_manager.set_checkpoint(
            "sdf_hose_stats_compounds_processed", str(self._compounds_processed)
        )
        self.db_manager.set_checkpoint(
            "sdf_hose_stats_compounds_failed", str(self._compounds_failed)
        )
        self.db_manager.set_checkpoint(
            "sdf_hose_stats_shifts_processed", str(self._shifts_processed)
        )

    def _clear_checkpoint(self) -> None:
        """Clear all checkpoints."""
        self.db_manager.clear_checkpoint("sdf_hose_stats_mol_index")
        self.db_manager.clear_checkpoint("sdf_hose_stats_compounds_processed")
        self.db_manager.clear_checkpoint("sdf_hose_stats_compounds_failed")
        self.db_manager.clear_checkpoint("sdf_hose_stats_shifts_processed")

    def _parse_cnmr_shifts(self, field: str) -> list[tuple[int, float]]:
        """Parse CNMR_SHIFTS field from COCONUT SDF.

        Format: 'signal_idx:atom_idx|shift;...'
        Example: '0:2|73.89;1:3|101.13'

        Note: atom_idx in COCONUT is 1-based, we convert to 0-based.

        Args:
            field: The CNMR_SHIFTS field string

        Returns:
            List of (atom_idx_0based, shift_ppm) tuples
        """
        shifts = []
        for part in field.split(";"):
            part = part.strip()
            if not part:
                continue

            pipe_parts = part.split("|")
            if len(pipe_parts) != 2:
                continue

            colon_parts = pipe_parts[0].split(":")
            if len(colon_parts) < 2:
                continue

            try:
                atom_idx_1based = int(colon_parts[1])
                atom_idx_0based = atom_idx_1based - 1  # Convert to 0-based
                shift_ppm = float(pipe_parts[1])
                shifts.append((atom_idx_0based, shift_ppm))
            except ValueError:
                continue

        return shifts

    def _process_chunk(
        self,
        chunk_size: int,
    ) -> tuple[dict[tuple[str, int], WelfordAccumulator], int, int, int]:
        """Process a chunk of molecules from SDF.

        Args:
            chunk_size: Maximum molecules to process in this chunk

        Returns:
            Tuple of:
            - Dict mapping (hose_code, radius) to WelfordAccumulator
            - Number of compounds processed
            - Number of compounds failed
            - Number of shifts processed
        """
        accumulators: dict[tuple[str, int], WelfordAccumulator] = defaultdict(
            WelfordAccumulator
        )
        compounds_processed = 0
        compounds_failed = 0
        shifts_processed = 0

        while compounds_processed < chunk_size:
            if self._mol_index >= len(self._supplier):
                break

            mol = self._supplier[self._mol_index]
            self._mol_index += 1

            if mol is None:
                compounds_failed += 1
                continue

            # Check for CNMR_SHIFTS field
            if not mol.HasProp("CNMR_SHIFTS"):
                compounds_failed += 1
                continue

            shifts_field = mol.GetProp("CNMR_SHIFTS")
            if not shifts_field:
                compounds_failed += 1
                continue

            compounds_processed += 1
            shifts = self._parse_cnmr_shifts(shifts_field)

            # Process each carbon shift
            for atom_idx, shift_ppm in shifts:
                if atom_idx < 0 or atom_idx >= mol.GetNumAtoms():
                    continue

                try:
                    atom = mol.GetAtomWithIdx(atom_idx)
                    if atom.GetSymbol() != "C":
                        continue
                except Exception:
                    continue

                # Extract hybridisation once per atom
                hybridisation = extract_hybridisation(atom)

                # Generate HOSE codes at all radii
                for radius in range(1, self.max_radius + 1):
                    try:
                        hose_code = self._hose_gen.generate_for_atom(mol, atom_idx, radius)
                        if hose_code:
                            # Parse sphere 1 for neighbour elements
                            neighbors = parse_sphere_1(hose_code)
                            accumulators[(hose_code, radius)].update_with_rings(
                                shift_ppm, hybridisation, neighbors, atom_idx, mol
                            )
                            shifts_processed += 1
                    except Exception:
                        continue

        return accumulators, compounds_processed, compounds_failed, shifts_processed

    def _upsert_chunk_stats(
        self,
        accumulators: dict[tuple[str, int], WelfordAccumulator],
    ) -> int:
        """Upsert chunk statistics to database."""
        if not accumulators:
            return 0

        # Prepend hose_code and radius to the 14-element to_tuple() result
        # Result: 16-element tuple for v6 schema
        stats = [
            (hose_code, radius) + acc.to_tuple()
            for (hose_code, radius), acc in accumulators.items()
            if acc.count > 0
        ]

        return self.db_manager.upsert_hose_stats_incremental(stats)

    def run(
        self,
        chunk_size: int = 10000,
        log_file: Path | str | None = None,
        resume: bool = True,
        fresh: bool = False,
    ) -> ResumableHOSEStatsResult:
        """Run the SDF-based HOSE statistics generation.

        Args:
            chunk_size: Number of molecules to process per chunk
            log_file: Path to log file for detached operation
            resume: If True, resume from checkpoint if exists
            fresh: If True, clear existing stats and checkpoint before starting

        Returns:
            ResumableHOSEStatsResult with generation statistics
        """
        self._setup_logging(log_file)

        # Handle fresh start
        if fresh:
            self._logger.info("Fresh start requested, clearing existing data...")
            self.db_manager.clear_hose_stats()
            self._clear_checkpoint()
            self._mol_index = 0
            self._compounds_processed = 0
            self._compounds_failed = 0
            self._shifts_processed = 0

        # Try to resume from checkpoint
        if resume and not fresh:
            if self._load_checkpoint():
                self._logger.info(
                    f"Resuming from checkpoint: mol_index={self._mol_index}, "
                    f"processed={self._compounds_processed}"
                )
            else:
                self._logger.info("No checkpoint found, starting fresh")

        total_mols = len(self._supplier)
        self._logger.info(
            f"Starting SDF HOSE statistics generation: "
            f"total_mols={total_mols}, max_radius={self.max_radius}, "
            f"chunk_size={chunk_size}, sdf={self.sdf_path.name}"
        )

        # Process in chunks
        chunk_num = 0
        total_upserted = 0

        while self._mol_index < total_mols:
            chunk_num += 1

            accumulators, processed, failed, shifts = self._process_chunk(chunk_size)

            if processed == 0 and failed == 0:
                break

            self._compounds_processed += processed
            self._compounds_failed += failed
            self._shifts_processed += shifts

            upserted = self._upsert_chunk_stats(accumulators)
            total_upserted += upserted

            self._save_checkpoint()

            progress = (self._mol_index / total_mols) * 100

            self._logger.info(
                f"Chunk {chunk_num}: processed={processed}, failed={failed}, "
                f"shifts={shifts}, upserted={upserted}, progress={progress:.1f}%"
            )

        self._clear_checkpoint()

        total_stats = self.db_manager.get_hose_stats_count()

        self._logger.info(
            f"Generation complete: compounds={self._compounds_processed}, "
            f"failed={self._compounds_failed}, shifts={self._shifts_processed}, "
            f"total_stats={total_stats}"
        )

        return ResumableHOSEStatsResult(
            compounds_processed=self._compounds_processed,
            compounds_failed=self._compounds_failed,
            shifts_processed=self._shifts_processed,
            total_stats=total_stats,
        )

    @property
    def compounds_processed(self) -> int:
        """Number of compounds processed."""
        return self._compounds_processed

    @property
    def compounds_failed(self) -> int:
        """Number of compounds that failed."""
        return self._compounds_failed

    @property
    def shifts_processed(self) -> int:
        """Number of shift observations processed."""
        return self._shifts_processed
