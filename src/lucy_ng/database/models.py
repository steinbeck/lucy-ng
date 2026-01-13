"""Pydantic models for database entities."""

from __future__ import annotations

from pydantic import BaseModel, Field

from lucy_ng.dereplication.nmrshiftdb import CarbonSignal, HydrogenCount, NMRShiftDBEntry


class ShiftRecord(BaseModel):
    """A single 13C shift record for database storage."""

    id: int | None = None
    compound_id: int | None = None
    atom_index: int | None = None
    shift_ppm: float
    hydrogen_count: int | None = None  # 0=C, 1=CH, 2=CH2, 3=CH3, None=unknown

    @classmethod
    def from_carbon_signal(
        cls, signal: CarbonSignal, compound_id: int | None = None
    ) -> ShiftRecord:
        """Create ShiftRecord from CarbonSignal."""
        h_count = int(signal.hydrogen_count) if signal.hydrogen_count is not None else None
        return cls(
            compound_id=compound_id,
            atom_index=signal.atom_index,
            shift_ppm=signal.shift,
            hydrogen_count=h_count,
        )

    def to_carbon_signal(self) -> CarbonSignal:
        """Convert to CarbonSignal for compatibility with existing code."""
        h_count = HydrogenCount(self.hydrogen_count) if self.hydrogen_count is not None else None
        return CarbonSignal(
            shift=self.shift_ppm,
            hydrogen_count=h_count,
            atom_index=self.atom_index,
        )


class CompoundRecord(BaseModel):
    """A compound record for database storage."""

    id: int | None = None
    name: str = ""
    smiles: str = ""
    formula: str
    formula_normalized: str = ""
    inchi: str = ""
    inchi_key: str = ""
    carbon_count: int = 0
    source: str = ""  # "nmrshiftdb" or "coconut"

    # Shifts are loaded separately via JOIN, not stored in model
    shifts: list[ShiftRecord] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:
        """Normalize formula after initialization."""
        if not self.formula_normalized and self.formula:
            self.formula_normalized = self._normalize_formula(self.formula)

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        """Normalize molecular formula for consistent comparison.

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

    @classmethod
    def from_nmrshiftdb_entry(
        cls, entry: NMRShiftDBEntry, source: str = "nmrshiftdb"
    ) -> CompoundRecord:
        """Create CompoundRecord from NMRShiftDBEntry."""
        record = cls(
            id=entry.nmrshiftdb_id,
            name=entry.name,
            formula=entry.molecular_formula,
            inchi=entry.inchi,
            inchi_key=entry.inchi_key,
            carbon_count=entry.carbon_count,
            source=source,
        )
        record.shifts = [ShiftRecord.from_carbon_signal(s) for s in entry.signals]
        return record

    def to_nmrshiftdb_entry(self) -> NMRShiftDBEntry:
        """Convert to NMRShiftDBEntry for compatibility with existing code."""
        return NMRShiftDBEntry(
            nmrshiftdb_id=self.id or 0,
            name=self.name,
            molecular_formula=self.formula,
            carbon_count=self.carbon_count,
            inchi=self.inchi,
            inchi_key=self.inchi_key,
            signals=[s.to_carbon_signal() for s in self.shifts],
        )
