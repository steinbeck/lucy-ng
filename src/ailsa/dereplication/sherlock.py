"""Sherlock database loader for 13C reference spectra.

Loads the pre-extracted Sherlock dataset (nmrshiftdb + COCONUT, 928K compounds)
from JSON format for dereplication.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from ailsa.dereplication.nmrshiftdb import (
    CarbonSignal,
    HydrogenCount,
    NMRShiftDBEntry,
    NMRShiftDBLoader,
)


@dataclass
class SherlockEntry:
    """A compound entry from the Sherlock database with 13C spectrum."""

    source: str  # "nmrshiftdb" or "coconut"
    source_id: str
    smiles: str
    molecular_formula: str
    carbon_count: int
    signals: list[CarbonSignal] = field(default_factory=list)

    # Compatibility properties for NMRShiftDBEntry interface
    @property
    def nmrshiftdb_id(self) -> int:
        """Compatibility: return hash of source_id."""
        return hash(f"{self.source}:{self.source_id}") & 0x7FFFFFFF

    @property
    def inchi(self) -> str:
        """Not available in Sherlock export."""
        return ""

    @property
    def inchi_key(self) -> str:
        """Not available in Sherlock export."""
        return ""

    @property
    def shifts(self) -> list[float]:
        """Return just the shift values for simple matching."""
        return [s.shift for s in self.signals]


class SherlockLoader:
    """Loader for Sherlock JSON database (nmrshiftdb + COCONUT).

    The JSON format is indexed by molecular formula for fast lookup:
    {
        "C13H18O2": [
            {"smiles": "...", "source": "nmrshiftdb", "id": "...",
             "signals": [[shift, h_count], ...]},
            ...
        ],
        ...
    }
    """

    def __init__(self, json_file_path: str | Path):
        """Initialize with path to JSON file.

        Args:
            json_file_path: Path to sherlock_13c.json
        """
        self.json_file_path = Path(json_file_path)
        self._data: dict[str, list[dict]] = {}
        self._loaded = False
        self._entry_count = 0

    def load(self) -> int:
        """Load the JSON file into memory.

        Returns:
            Total number of entries loaded
        """
        if self._loaded:
            return self._entry_count

        if not self.json_file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {self.json_file_path}")

        with open(self.json_file_path, "r") as f:
            self._data = json.load(f)

        # Count total entries
        self._entry_count = sum(len(entries) for entries in self._data.values())
        self._loaded = True

        return self._entry_count

    @property
    def formula_count(self) -> int:
        """Number of unique molecular formulas."""
        if not self._loaded:
            self.load()
        return len(self._data)

    @property
    def entry_count(self) -> int:
        """Total number of compound entries."""
        if not self._loaded:
            self.load()
        return self._entry_count

    def get_by_formula(self, formula: str) -> list[SherlockEntry]:
        """Get all entries matching a molecular formula.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            List of SherlockEntry objects with matching molecular formula
        """
        if not self._loaded:
            self.load()

        normalized = self._normalize_formula(formula)
        raw_entries = self._data.get(normalized, [])

        entries = []
        for raw in raw_entries:
            signals = [
                CarbonSignal(
                    shift=sig[0],
                    hydrogen_count=HydrogenCount(sig[1]) if sig[1] is not None else None,
                )
                for sig in raw.get("signals", [])
            ]

            entry = SherlockEntry(
                source=raw.get("source", "unknown"),
                source_id=raw.get("id", ""),
                smiles=raw.get("smiles", ""),
                molecular_formula=normalized,
                carbon_count=NMRShiftDBLoader.count_carbons(normalized),
                signals=signals,
            )
            entries.append(entry)

        return entries

    def has_formula(self, formula: str) -> bool:
        """Check if a molecular formula exists in the database.

        Args:
            formula: Molecular formula to check

        Returns:
            True if formula exists in database
        """
        if not self._loaded:
            self.load()

        normalized = self._normalize_formula(formula)
        return normalized in self._data

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        """Normalize molecular formula for consistent lookup.

        Args:
            formula: Molecular formula in any format

        Returns:
            Normalized formula string
        """
        # Replace subscript digits with regular digits
        subscript_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
        formula = formula.translate(subscript_map)

        # Remove whitespace
        formula = formula.replace(" ", "")

        return formula
