"""HOSE code to chemical shift lookup table."""

import gzip
import json
import multiprocessing as mp
import os
import statistics
from collections import defaultdict
from functools import partial
from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable

from rdkit import Chem, RDLogger
from tqdm import tqdm

from .hose import HOSECodeGenerator
from .models import HOSEStatsResult, ShiftEntry


@runtime_checkable
class HOSELookupProtocol(Protocol):
    """Protocol for HOSE code lookup backends.

    Both in-memory lookup tables and database adapters implement this protocol,
    allowing C13Predictor to work with either backend.
    """

    def lookup_stats_at_radius(
        self, hose_code: str, radius: int
    ) -> HOSEStatsResult | None:
        """Look up statistics for a HOSE code at a specific radius.

        Args:
            hose_code: HOSE code string
            radius: Sphere radius (1-6)

        Returns:
            HOSEStatsResult with mean, std, count; or None if not found
        """
        ...

    def has_code_at_radius(self, hose_code: str, radius: int) -> bool:
        """Check if a HOSE code exists at a specific radius.

        Args:
            hose_code: HOSE code string
            radius: Sphere radius (1-6)

        Returns:
            True if the code exists at this radius
        """
        ...

# Suppress RDKit warnings in worker processes
RDLogger.DisableLog("rdApp.*")


class HOSELookupTable:
    """HOSE code to chemical shift lookup table.

    Stores mappings from HOSE codes to observed chemical shifts,
    enabling prediction of shifts for new molecules by HOSE code matching.
    """

    def __init__(self) -> None:
        """Initialize an empty lookup table."""
        # Structure: {hose_code: [shift1, shift2, ...]}
        # Simplified to just store shifts for memory efficiency
        self._table: dict[str, list[float]] = defaultdict(list)
        self._molecule_count: int = 0
        self._entry_count: int = 0

    def add_entry(self, hose_code: str, shift: float) -> None:
        """Add a shift entry for a HOSE code.

        Args:
            hose_code: HOSE code string
            shift: Chemical shift in ppm
        """
        self._table[hose_code].append(shift)
        self._entry_count += 1

    def lookup(self, hose_code: str) -> list[float]:
        """Get all known shifts for a HOSE code.

        Args:
            hose_code: HOSE code to look up

        Returns:
            List of chemical shifts, empty if not found
        """
        return self._table.get(hose_code, [])

    def lookup_stats(self, hose_code: str) -> dict | None:
        """Get statistics for a HOSE code's shifts.

        Args:
            hose_code: HOSE code to look up

        Returns:
            Dict with median, mean, std, min, max, count; or None if not found
        """
        shifts = self.lookup(hose_code)
        if not shifts:
            return None

        return {
            "median": statistics.median(shifts),
            "mean": statistics.mean(shifts),
            "std": statistics.stdev(shifts) if len(shifts) > 1 else 0.0,
            "min": min(shifts),
            "max": max(shifts),
            "count": len(shifts),
        }

    def lookup_stats_at_radius(
        self, hose_code: str, radius: int  # noqa: ARG002
    ) -> HOSEStatsResult | None:
        """Look up statistics for a HOSE code (protocol method).

        For in-memory tables, the radius is implicit in the HOSE code structure,
        so the radius parameter is ignored. The HOSE code itself determines
        the specificity of the lookup.

        Args:
            hose_code: HOSE code string
            radius: Sphere radius (ignored - implicit in hose_code)

        Returns:
            HOSEStatsResult with mean, std, count; or None if not found
        """
        shifts = self.lookup(hose_code)
        if not shifts:
            return None

        return HOSEStatsResult(
            mean=statistics.mean(shifts),
            std=statistics.stdev(shifts) if len(shifts) > 1 else 0.0,
            count=len(shifts),
        )

    def has_code_at_radius(
        self, hose_code: str, radius: int  # noqa: ARG002
    ) -> bool:
        """Check if a HOSE code exists (protocol method).

        Args:
            hose_code: HOSE code string
            radius: Sphere radius (ignored - implicit in hose_code)

        Returns:
            True if the code exists
        """
        return self.has_code(hose_code)

    def has_code(self, hose_code: str) -> bool:
        """Check if a HOSE code exists in the table.

        Args:
            hose_code: HOSE code to check

        Returns:
            True if the code exists
        """
        return hose_code in self._table

    @property
    def unique_codes(self) -> int:
        """Number of unique HOSE codes in the table."""
        return len(self._table)

    @property
    def total_entries(self) -> int:
        """Total number of shift entries in the table."""
        return self._entry_count

    @property
    def molecule_count(self) -> int:
        """Number of molecules processed to build the table."""
        return self._molecule_count

    def save(self, path: Path, compress: bool = True) -> None:
        """Save lookup table to file.

        Args:
            path: Output file path
            compress: If True, use gzip compression (recommended)
        """
        data = {
            "version": 1,
            "molecule_count": self._molecule_count,
            "entry_count": self._entry_count,
            "table": dict(self._table),
        }

        path = Path(path)
        if compress or path.suffix == ".gz":
            if not path.suffix == ".gz":
                path = path.with_suffix(path.suffix + ".gz")
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(data, f)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)

    @classmethod
    def load(cls, path: Path) -> "HOSELookupTable":
        """Load lookup table from file.

        Args:
            path: Input file path

        Returns:
            Loaded HOSELookupTable instance
        """
        path = Path(path)
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

        table = cls()
        table._molecule_count = data.get("molecule_count", 0)
        table._entry_count = data.get("entry_count", 0)
        table._table = defaultdict(list, data.get("table", {}))

        return table

    @classmethod
    def build_from_coconut(
        cls,
        sd_path: Path,
        max_radius: int = 6,
        progress: bool = True,
        limit: int | None = None,
    ) -> "HOSELookupTable":
        """Build lookup table from COCONUT SD file.

        Streams through the SD file to avoid memory issues with large files.
        Generates HOSE codes at all radii from 1 to max_radius.

        Args:
            sd_path: Path to COCONUT SD file
            max_radius: Maximum HOSE code radius (default 6)
            progress: Show progress bar
            limit: Optional limit on number of molecules to process

        Returns:
            Populated HOSELookupTable
        """
        table = cls()
        hose_gen = HOSECodeGenerator()

        # Stream through SD file
        mol_iter: Iterator = cls._stream_sd_file(sd_path)

        if progress:
            mol_iter = tqdm(mol_iter, desc="Building HOSE table", unit=" mol")

        processed = 0
        for mol, shifts_by_atom in mol_iter:
            if mol is None:
                continue

            if limit and processed >= limit:
                break

            # Add explicit hydrogens for HOSE generation
            mol_with_h = Chem.AddHs(mol)

            # Generate HOSE codes at all radii for each carbon with a known shift
            for atom_idx, shift in shifts_by_atom.items():
                # Verify it's a carbon
                atom = mol_with_h.GetAtomWithIdx(atom_idx)
                if atom.GetSymbol() != "C":
                    continue

                # Generate HOSE codes at all radii
                for radius in range(1, max_radius + 1):
                    try:
                        hose_code = hose_gen.generate_for_atom(
                            mol_with_h, atom_idx, radius=radius
                        )
                        table.add_entry(hose_code, shift)
                    except Exception:
                        # Skip atoms that fail HOSE generation
                        continue

            table._molecule_count += 1
            processed += 1

        return table

    @staticmethod
    def _stream_sd_file(
        sd_path: Path,
    ) -> Iterator[tuple[Chem.Mol | None, dict[int, float]]]:
        """Stream molecules and their 13C shifts from COCONUT SD file.

        Args:
            sd_path: Path to SD file

        Yields:
            Tuples of (mol, {atom_idx: shift})
        """
        sd_path = Path(sd_path)
        if not sd_path.exists():
            raise FileNotFoundError(f"SD file not found: {sd_path}")

        supplier = Chem.SDMolSupplier(str(sd_path), removeHs=False)

        for mol in supplier:
            if mol is None:
                yield None, {}
                continue

            # Parse CNMR_SHIFTS field from COCONUT
            shifts_by_atom: dict[int, float] = {}

            if mol.HasProp("CNMR_SHIFTS"):
                spectrum_field = mol.GetProp("CNMR_SHIFTS")
                shifts_by_atom = HOSELookupTable._parse_coconut_shifts(spectrum_field)

            yield mol, shifts_by_atom

    @staticmethod
    def _parse_coconut_shifts(field: str) -> dict[int, float]:
        """Parse COCONUT CNMR_SHIFTS field.

        Format: 'idx:atom|shift;idx:atom|shift;...'
        Example: '0:2|73.89;1:3|101.13;2:5|154.84'

        Args:
            field: CNMR_SHIFTS field string

        Returns:
            Dict mapping atom index to chemical shift
        """
        shifts: dict[int, float] = {}

        for part in field.strip().split(";"):
            part = part.strip()
            if not part:
                continue

            # Format: idx:atom|shift
            pipe_parts = part.split("|")
            if len(pipe_parts) != 2:
                continue

            try:
                shift = float(pipe_parts[1])
            except ValueError:
                continue

            # Parse atom index from idx:atom format
            colon_parts = pipe_parts[0].split(":")
            if len(colon_parts) >= 2:
                try:
                    atom_idx = int(colon_parts[1])
                    shifts[atom_idx] = shift
                except ValueError:
                    continue

        return shifts

    @classmethod
    def build_from_nmrshiftdb(
        cls,
        sd_path: Path,
        max_radius: int = 6,
        progress: bool = True,
        limit: int | None = None,
        n_jobs: int | None = None,
    ) -> "HOSELookupTable":
        """Build lookup table from nmrshiftdb2 SD file with parallel processing.

        Args:
            sd_path: Path to nmrshiftdb2 SD file
            max_radius: Maximum HOSE code radius (default 6)
            progress: Show progress bar
            limit: Optional limit on number of molecules to process
            n_jobs: Number of parallel workers (default: CPU count)

        Returns:
            Populated HOSELookupTable
        """
        sd_path = Path(sd_path)
        if not sd_path.exists():
            raise FileNotFoundError(f"SD file not found: {sd_path}")

        # Collect molecules with shifts
        mol_data = cls._collect_molecules_nmrshiftdb(sd_path, limit)

        if not mol_data:
            return cls()

        # Process in parallel
        n_jobs = n_jobs or mp.cpu_count()
        worker = partial(_process_molecule_worker, max_radius=max_radius)

        table = cls()

        if n_jobs > 1:
            with mp.Pool(n_jobs) as pool:
                if progress:
                    results = list(
                        tqdm(
                            pool.imap(worker, mol_data, chunksize=50),
                            total=len(mol_data),
                            desc="Building HOSE table",
                            unit=" mol",
                        )
                    )
                else:
                    results = pool.map(worker, mol_data, chunksize=50)
        else:
            # Serial processing
            if progress:
                mol_data = tqdm(mol_data, desc="Building HOSE table", unit=" mol")
            results = [worker(md) for md in mol_data]

        # Aggregate results
        for entries in results:
            for hose_code, shift in entries:
                table.add_entry(hose_code, shift)
            if entries:
                table._molecule_count += 1

        return table

    @staticmethod
    def _collect_molecules_nmrshiftdb(
        sd_path: Path,
        limit: int | None = None,
    ) -> list[tuple[str, dict[int, float]]]:
        """Collect molecules and shifts from nmrshiftdb2 SD file.

        Returns list of (molblock, {atom_idx: shift}) tuples for parallel processing.
        """
        supplier = Chem.SDMolSupplier(str(sd_path), removeHs=False)
        mol_data = []

        for mol in supplier:
            if mol is None:
                continue

            # Parse shifts from nmrshiftdb2 format
            shifts = HOSELookupTable._parse_nmrshiftdb_shifts(mol)
            if not shifts:
                continue

            # Store molblock for serialization to workers
            molblock = Chem.MolToMolBlock(mol)
            mol_data.append((molblock, shifts))

            if limit and len(mol_data) >= limit:
                break

        return mol_data

    @staticmethod
    def _parse_nmrshiftdb_shifts(mol: Chem.Mol) -> dict[int, float]:
        """Parse nmrshiftdb2 Spectrum 13C field.

        Format: 'shift;coupling;atom_idx|shift;coupling;atom_idx|...'
        Example: '17.6;0.0Q;10|18.3;0.0T;0|22.6;0.0Q;12|'

        Args:
            mol: RDKit Mol with properties

        Returns:
            Dict mapping atom index to chemical shift
        """
        shifts: dict[int, float] = {}

        if not mol.HasProp("Spectrum 13C 0"):
            return shifts

        field = mol.GetProp("Spectrum 13C 0")

        for part in field.strip().split("|"):
            part = part.strip()
            if not part:
                continue

            # Format: shift;coupling;atom_idx
            parts = part.split(";")
            if len(parts) < 3:
                continue

            try:
                shift = float(parts[0])
                atom_idx = int(parts[2])
                shifts[atom_idx] = shift
            except (ValueError, IndexError):
                continue

        return shifts

    def __len__(self) -> int:
        """Return number of unique HOSE codes."""
        return len(self._table)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"HOSELookupTable(codes={self.unique_codes}, "
            f"entries={self.total_entries}, molecules={self.molecule_count})"
        )


def _process_molecule_worker(
    mol_data: tuple[str, dict[int, float]],
    max_radius: int = 6,
) -> list[tuple[str, float]]:
    """Worker function to process a single molecule.

    Args:
        mol_data: Tuple of (molblock, {atom_idx: shift})
        max_radius: Maximum HOSE code radius

    Returns:
        List of (hose_code, shift) tuples
    """
    from hosegen import HoseGenerator

    molblock, shifts = mol_data
    entries: list[tuple[str, float]] = []

    # Use molecule WITHOUT explicit hydrogens for HOSE code generation
    mol = Chem.MolFromMolBlock(molblock, removeHs=True)
    if mol is None:
        return entries

    hose_gen = HoseGenerator()

    for atom_idx, shift in shifts.items():
        try:
            atom = mol.GetAtomWithIdx(atom_idx)
            if atom.GetSymbol() != "C":
                continue

            for radius in range(1, max_radius + 1):
                try:
                    hose_code = hose_gen.get_Hose_codes(mol, atom_idx, max_radius=radius)
                    if hose_code:
                        entries.append((hose_code, shift))
                except Exception:
                    pass
        except Exception:
            pass

    return entries
