"""Generate HOSE statistics from database compounds."""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from tqdm import tqdm

from lucy_ng.database.models import HOSEStatsRecord

from .hose import HOSECodeGenerator

if TYPE_CHECKING:
    from lucy_ng.database import DatabaseManager


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
            return WelfordAccumulator(count=self.count, mean=self.mean, m2=self.m2)
        if self.count == 0:
            return WelfordAccumulator(count=other.count, mean=other.mean, m2=other.m2)

        combined_count = self.count + other.count
        delta = other.mean - self.mean
        combined_mean = self.mean + delta * (other.count / combined_count)
        combined_m2 = (
            self.m2
            + other.m2
            + delta * delta * (self.count * other.count / combined_count)
        )

        return WelfordAccumulator(
            count=combined_count,
            mean=combined_mean,
            m2=combined_m2,
        )

    def to_tuple(self) -> tuple[int, float, float]:
        """Export as (count, mean, m2) tuple for database storage."""
        return (self.count, self.mean, self.m2)


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
        nohup lucy database generate-hose-stats --log-file hose.log &
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
        self._logger = logging.getLogger("lucy_ng.hose_stats")

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

                # Generate HOSE codes at all radii
                for radius in range(1, self.max_radius + 1):
                    try:
                        hose_code = self._hose_gen.generate_for_atom(mol, atom_idx, radius)
                        if hose_code:
                            accumulators[(hose_code, radius)].update(shift_ppm)
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
        stats = [
            (hose_code, radius, acc.count, acc.mean, acc.m2)
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
    ) -> "ResumableHOSEStatsResult":
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
        self._logger = logging.getLogger("lucy_ng.hose_stats_sdf")

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

                # Generate HOSE codes at all radii
                for radius in range(1, self.max_radius + 1):
                    try:
                        hose_code = self._hose_gen.generate_for_atom(mol, atom_idx, radius)
                        if hose_code:
                            accumulators[(hose_code, radius)].update(shift_ppm)
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

        stats = [
            (hose_code, radius, acc.count, acc.mean, acc.m2)
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
