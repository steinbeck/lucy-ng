"""Database importer for NMRShiftDB and COCONUT SDF files."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rdkit import Chem

from lucy_ng.database.manager import DatabaseManager
from lucy_ng.database.models import CompoundRecord, ShiftRecord
from lucy_ng.dereplication.nmrshiftdb import NMRShiftDBLoader

if TYPE_CHECKING:
    from lucy_ng.dereplication.nmrshiftdb import NMRShiftDBEntry


@dataclass
class ImportResult:
    """Result of a database import operation."""

    source: str  # "nmrshiftdb" or "coconut"
    compounds_imported: int = 0
    compounds_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def __str__(self) -> str:
        """Return human-readable summary."""
        return (
            f"{self.source}: {self.compounds_imported} imported, "
            f"{self.compounds_skipped} skipped, {len(self.errors)} errors "
            f"({self.elapsed_seconds:.1f}s)"
        )


class DatabaseImporter:
    """Import compounds from SDF files into the database."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize with database manager.

        Args:
            db_manager: DatabaseManager instance (should have tables created)
        """
        self.db_manager = db_manager

    def import_nmrshiftdb(
        self,
        sd_file: str | Path,
        batch_size: int = 1000,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ImportResult:
        """Import NMRShiftDB SD file into database.

        Args:
            sd_file: Path to NMRShiftDB SD file
            batch_size: Number of compounds per batch insert
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ImportResult with counts and any errors
        """
        start_time = time.time()
        result = ImportResult(source="nmrshiftdb")

        sd_file = Path(sd_file)
        if not sd_file.exists():
            result.errors.append(f"File not found: {sd_file}")
            return result

        # Use existing loader to parse the file
        loader = NMRShiftDBLoader(sd_file)

        try:
            entries = loader.load()
        except Exception as e:
            result.errors.append(f"Failed to load file: {e}")
            result.elapsed_seconds = time.time() - start_time
            return result

        total = len(entries)
        batch: list[tuple[CompoundRecord, list[ShiftRecord]]] = []

        for i, entry in enumerate(entries):
            try:
                compound, shifts = self._entry_to_records(entry, "nmrshiftdb")
                batch.append((compound, shifts))

                if len(batch) >= batch_size:
                    self.db_manager.insert_compounds_batch(batch, batch_size=batch_size)
                    result.compounds_imported += len(batch)
                    batch = []

                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception as e:
                result.compounds_skipped += 1
                result.errors.append(f"Entry {i}: {e}")

        # Insert remaining batch
        if batch:
            self.db_manager.insert_compounds_batch(batch, batch_size=batch_size)
            result.compounds_imported += len(batch)

        result.elapsed_seconds = time.time() - start_time
        return result

    def import_coconut(
        self,
        sd_file: str | Path,
        batch_size: int = 1000,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ImportResult:
        """Import COCONUT SD file into database using streaming.

        Args:
            sd_file: Path to COCONUT SD file
            batch_size: Number of compounds per batch insert
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ImportResult with counts and any errors
        """
        start_time = time.time()
        result = ImportResult(source="coconut")

        sd_file = Path(sd_file)
        if not sd_file.exists():
            result.errors.append(f"File not found: {sd_file}")
            return result

        # Stream through file to avoid loading 4.5GB into memory
        batch: list[tuple[CompoundRecord, list[ShiftRecord]]] = []
        entry_id = 0

        # First pass: count total entries for progress (optional, can be slow)
        # For now, we'll report progress without total
        total_estimate = 895000  # Approximate COCONUT size

        try:
            supplier = Chem.SDMolSupplier(str(sd_file))

            for mol in supplier:
                if mol is None:
                    result.compounds_skipped += 1
                    continue

                try:
                    record_tuple = self._mol_to_records(mol, entry_id, "coconut")
                    if record_tuple is None:
                        result.compounds_skipped += 1
                        continue

                    batch.append(record_tuple)
                    entry_id += 1

                    if len(batch) >= batch_size:
                        self.db_manager.insert_compounds_batch(
                            batch, batch_size=batch_size
                        )
                        result.compounds_imported += len(batch)
                        batch = []

                        if progress_callback:
                            progress_callback(
                                result.compounds_imported, total_estimate
                            )

                except Exception as e:
                    result.compounds_skipped += 1
                    if len(result.errors) < 100:  # Limit error list size
                        result.errors.append(f"Entry {entry_id}: {e}")

        except Exception as e:
            result.errors.append(f"Failed to process file: {e}")

        # Insert remaining batch
        if batch:
            self.db_manager.insert_compounds_batch(batch, batch_size=batch_size)
            result.compounds_imported += len(batch)

        result.elapsed_seconds = time.time() - start_time
        return result

    def _entry_to_records(
        self, entry: NMRShiftDBEntry, source: str
    ) -> tuple[CompoundRecord, list[ShiftRecord]]:
        """Convert NMRShiftDBEntry to database records.

        Args:
            entry: NMRShiftDBEntry from loader
            source: Source identifier ("nmrshiftdb" or "coconut")

        Returns:
            Tuple of (CompoundRecord, list of ShiftRecord)
        """
        compound = CompoundRecord.from_nmrshiftdb_entry(entry, source=source)
        shifts = compound.shifts
        compound.shifts = []  # Clear for separate insertion
        return compound, shifts

    def _mol_to_records(
        self, mol: Chem.Mol, entry_id: int, source: str
    ) -> tuple[CompoundRecord, list[ShiftRecord]] | None:
        """Convert RDKit Mol to database records for COCONUT.

        Args:
            mol: RDKit Mol object with properties
            entry_id: ID to assign
            source: Source identifier

        Returns:
            Tuple of (CompoundRecord, list of ShiftRecord) or None if invalid
        """
        # Check for required 13C spectrum data
        if not mol.HasProp("CNMR_SHIFTS"):
            return None

        spectrum_field = mol.GetProp("CNMR_SHIFTS")
        if not spectrum_field:
            return None

        # Get molecular formula
        formula = mol.GetProp("Formula") if mol.HasProp("Formula") else ""
        if not formula:
            return None

        # Get molecule name
        name = mol.GetProp("_Name") if mol.HasProp("_Name") else ""

        # Generate SMILES
        try:
            smiles = Chem.MolToSmiles(mol)
        except Exception:
            smiles = ""

        # Generate InChI
        try:
            inchi = Chem.MolToInchi(mol)  # type: ignore[no-untyped-call]
        except Exception:
            inchi = ""

        try:
            inchi_key = Chem.MolToInchiKey(mol) if inchi else ""  # type: ignore[no-untyped-call]
        except Exception:
            inchi_key = ""

        # Count carbons from formula
        carbon_count = self._count_carbons(formula)

        # Parse multiplicity info for hydrogen counts
        mult_map = self._parse_multiplicities(mol)

        # Parse spectrum
        shifts = self._parse_coconut_spectrum(spectrum_field, mult_map)
        if not shifts:
            return None

        compound = CompoundRecord(
            id=entry_id,
            name=name,
            smiles=smiles,
            formula=formula,
            inchi=inchi,
            inchi_key=inchi_key,
            carbon_count=carbon_count,
            source=source,
        )

        return compound, shifts

    def _parse_multiplicities(self, mol: Chem.Mol) -> dict[int, int]:
        """Parse COCONUT multiplicity fields into atom index -> H count map.

        Args:
            mol: RDKit Mol with Quaternaries/Tertiaries/Secondaries/Primaries props

        Returns:
            Dict mapping atom index to hydrogen count (0-3)
        """
        mult_map: dict[int, int] = {}

        # Quaternaries = 0 H (C)
        if mol.HasProp("Quaternaries"):
            for atom_idx in self._parse_mult_field(mol.GetProp("Quaternaries")):
                mult_map[atom_idx] = 0

        # Tertiaries = 1 H (CH)
        if mol.HasProp("Tertiaries"):
            for atom_idx in self._parse_mult_field(mol.GetProp("Tertiaries")):
                mult_map[atom_idx] = 1

        # Secondaries = 2 H (CH2)
        if mol.HasProp("Secondaries"):
            for atom_idx in self._parse_mult_field(mol.GetProp("Secondaries")):
                mult_map[atom_idx] = 2

        # Primaries = 3 H (CH3)
        if mol.HasProp("Primaries"):
            for atom_idx in self._parse_mult_field(mol.GetProp("Primaries")):
                mult_map[atom_idx] = 3

        return mult_map

    @staticmethod
    def _parse_mult_field(field: str) -> list[int]:
        """Parse multiplicity field (tab-separated atom_idx shift pairs).

        Args:
            field: Field content like "5\\t154.84\\n6\\t108.70"

        Returns:
            List of atom indices
        """
        indices: list[int] = []
        if not field:
            return indices

        for line in field.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if parts:
                try:
                    indices.append(int(parts[0]))
                except ValueError:
                    pass

        return indices

    def _parse_coconut_spectrum(
        self, field: str, mult_map: dict[int, int]
    ) -> list[ShiftRecord]:
        """Parse COCONUT CNMR_SHIFTS field.

        Format: 'idx:atom|shift;idx:atom|shift;...'
        Example: '0:2|73.89;1:3|101.13'

        Args:
            field: CNMR_SHIFTS field content
            mult_map: Atom index to hydrogen count mapping

        Returns:
            List of ShiftRecord objects
        """
        shifts = []

        for part in field.strip().split(";"):
            part = part.strip()
            if not part:
                continue

            # Format: idx:atom|shift
            pipe_parts = part.split("|")
            if len(pipe_parts) != 2:
                continue

            try:
                shift_ppm = float(pipe_parts[1])
            except ValueError:
                continue

            # Parse atom index
            atom_index = None
            colon_parts = pipe_parts[0].split(":")
            if len(colon_parts) >= 2:
                try:
                    atom_index = int(colon_parts[1])
                except ValueError:
                    pass

            # Get hydrogen count from multiplicity map
            hydrogen_count = mult_map.get(atom_index) if atom_index is not None else None

            shifts.append(
                ShiftRecord(
                    shift_ppm=shift_ppm,
                    atom_index=atom_index,
                    hydrogen_count=hydrogen_count,
                )
            )

        return shifts

    @staticmethod
    def _count_carbons(formula: str) -> int:
        """Extract carbon count from molecular formula.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            Number of carbons
        """
        import re

        # Match C followed by optional number, excluding other C-elements
        match = re.search(r"C(?![laroudsefgmnptb])(\d*)", formula)
        if not match:
            return 0

        count_str = match.group(1)
        return 1 if count_str == "" else int(count_str)
