"""Database query service for formula-based compound lookup."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lucy_ng.database.manager import DatabaseManager
from lucy_ng.database.models import CompoundRecord
from lucy_ng.dereplication.nmrshiftdb import CarbonSignal, HydrogenCount, NMRShiftDBEntry

if TYPE_CHECKING:
    pass


def _int_to_hydrogen_count(value: int | None) -> HydrogenCount | None:
    """Convert integer hydrogen count to HydrogenCount enum.

    Args:
        value: Integer hydrogen count (0-3) or None

    Returns:
        HydrogenCount enum value or None
    """
    if value is None:
        return None
    try:
        return HydrogenCount(value)
    except ValueError:
        return None


class DatabaseQueryService:
    """Query interface for database-backed compound lookup.

    Provides the same interface as NMRShiftDBLoader but queries SQLite
    database instead of parsing SD files. Returns NMRShiftDBEntry objects
    for compatibility with existing SpectrumMatcher.

    Usage:
        with DatabaseQueryService("compounds.db") as query:
            candidates = query.get_by_formula("C13H18O2")
            # candidates is list[NMRShiftDBEntry]

        # Or without context manager
        query = DatabaseQueryService("compounds.db")
        query.open()
        candidates = query.get_by_formula("C13H18O2")
        query.close()
    """

    def __init__(self, db_path: str | Path):
        """Initialize with path to SQLite database.

        Args:
            db_path: Path to compounds database file
        """
        self.db_path = Path(db_path)
        self._manager: DatabaseManager | None = None

    def __enter__(self) -> DatabaseQueryService:
        """Context manager entry - open database connection."""
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit - close database connection."""
        self.close()

    def open(self) -> None:
        """Open database connection."""
        if self._manager is None:
            self._manager = DatabaseManager(self.db_path)
            self._manager._connect()

    def close(self) -> None:
        """Close database connection."""
        if self._manager is not None:
            self._manager.close()
            self._manager = None

    @property
    def is_open(self) -> bool:
        """Check if database connection is open."""
        return self._manager is not None

    def get_by_formula(self, formula: str) -> list[NMRShiftDBEntry]:
        """Get all compounds matching a molecular formula.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            List of NMRShiftDBEntry objects compatible with SpectrumMatcher
        """
        if self._manager is None:
            raise RuntimeError("Database not open. Use context manager or call open().")

        compounds = self._manager.get_by_formula(formula)
        return [self.compound_to_entry(c) for c in compounds]

    def get_by_formulas_batch(
        self, formulas: list[str]
    ) -> dict[str, list[NMRShiftDBEntry]]:
        """Query multiple formulas efficiently.

        Uses single database connection for all queries.

        Args:
            formulas: List of molecular formulas to query

        Returns:
            Dict mapping formula to list of matching entries
        """
        if self._manager is None:
            raise RuntimeError("Database not open. Use context manager or call open().")

        results: dict[str, list[NMRShiftDBEntry]] = {}
        for formula in formulas:
            compounds = self._manager.get_by_formula(formula)
            results[formula] = [self.compound_to_entry(c) for c in compounds]
        return results

    def get_compound_count(self) -> int:
        """Return total number of compounds in database."""
        if self._manager is None:
            raise RuntimeError("Database not open. Use context manager or call open().")
        return self._manager.get_compound_count()

    def get_formula_count(self) -> int:
        """Return count of unique molecular formulas."""
        if self._manager is None:
            raise RuntimeError("Database not open. Use context manager or call open().")
        return self._manager.get_formula_count()

    @staticmethod
    def compound_to_entry(compound: CompoundRecord) -> NMRShiftDBEntry:
        """Convert CompoundRecord to NMRShiftDBEntry.

        Creates an NMRShiftDBEntry that is compatible with SpectrumMatcher.

        Args:
            compound: CompoundRecord with shifts

        Returns:
            NMRShiftDBEntry with signals populated
        """
        # Convert ShiftRecords to CarbonSignals
        signals = [
            CarbonSignal(
                shift=shift.shift_ppm,
                hydrogen_count=_int_to_hydrogen_count(shift.hydrogen_count),
                atom_index=shift.atom_index,
            )
            for shift in compound.shifts
        ]

        return NMRShiftDBEntry(
            nmrshiftdb_id=compound.id or 0,
            name=compound.name or "",
            molecular_formula=compound.formula or "",
            carbon_count=compound.carbon_count or 0,
            inchi=compound.inchi or "",
            inchi_key=compound.inchi_key or "",
            signals=signals,
        )
