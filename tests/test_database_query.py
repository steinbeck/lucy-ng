"""Tests for database query service."""

from __future__ import annotations

from pathlib import Path

import pytest

from lucy_ng.database import (
    CompoundRecord,
    DatabaseManager,
    DatabaseQueryService,
    ShiftRecord,
)
from lucy_ng.dereplication.nmrshiftdb import HydrogenCount


class TestCompoundConversion:
    """Tests for CompoundRecord to NMRShiftDBEntry conversion."""

    def test_compound_to_entry_basic(self) -> None:
        """Test basic conversion without shifts."""
        compound = CompoundRecord(
            id=42,
            name="Test Compound",
            formula="C10H12O2",
            carbon_count=10,
            source="test",
        )

        entry = DatabaseQueryService.compound_to_entry(compound)

        assert entry.nmrshiftdb_id == 42
        assert entry.name == "Test Compound"
        assert entry.molecular_formula == "C10H12O2"
        assert entry.carbon_count == 10
        assert entry.signals == []

    def test_compound_to_entry_with_shifts(self) -> None:
        """Test conversion with shifts."""
        compound = CompoundRecord(
            id=1,
            name="Methanol",
            formula="CH4O",
            carbon_count=1,
            inchi="InChI=1S/CH4O/c1-2/h2H,1H3",
            inchi_key="OKKJLVBELUTLKV-UHFFFAOYSA-N",
            source="nmrshiftdb",
            shifts=[
                ShiftRecord(
                    id=1,
                    compound_id=1,
                    atom_index=0,
                    shift_ppm=49.5,
                    hydrogen_count=3,  # CH3
                ),
            ],
        )

        entry = DatabaseQueryService.compound_to_entry(compound)

        assert entry.nmrshiftdb_id == 1
        assert entry.name == "Methanol"
        assert entry.inchi == "InChI=1S/CH4O/c1-2/h2H,1H3"
        assert entry.inchi_key == "OKKJLVBELUTLKV-UHFFFAOYSA-N"
        assert len(entry.signals) == 1
        assert entry.signals[0].shift == pytest.approx(49.5)
        assert entry.signals[0].hydrogen_count == HydrogenCount.CH3
        assert entry.signals[0].atom_index == 0

    def test_hydrogen_count_mapping(self) -> None:
        """Test integer to HydrogenCount enum mapping."""
        compound = CompoundRecord(
            id=1,
            name="Test",
            formula="C4H10",
            carbon_count=4,
            source="test",
            shifts=[
                ShiftRecord(compound_id=1, shift_ppm=10.0, hydrogen_count=0),  # C
                ShiftRecord(compound_id=1, shift_ppm=20.0, hydrogen_count=1),  # CH
                ShiftRecord(compound_id=1, shift_ppm=30.0, hydrogen_count=2),  # CH2
                ShiftRecord(compound_id=1, shift_ppm=40.0, hydrogen_count=3),  # CH3
                ShiftRecord(compound_id=1, shift_ppm=50.0, hydrogen_count=None),  # Unknown
            ],
        )

        entry = DatabaseQueryService.compound_to_entry(compound)

        assert entry.signals[0].hydrogen_count == HydrogenCount.C
        assert entry.signals[1].hydrogen_count == HydrogenCount.CH
        assert entry.signals[2].hydrogen_count == HydrogenCount.CH2
        assert entry.signals[3].hydrogen_count == HydrogenCount.CH3
        assert entry.signals[4].hydrogen_count is None

    def test_compound_to_entry_default_values(self) -> None:
        """Test conversion handles default/minimal values gracefully."""
        # CompoundRecord requires formula, others have defaults
        compound = CompoundRecord(
            formula="C6H12O6",
            source="test",
        )

        entry = DatabaseQueryService.compound_to_entry(compound)

        # id=None converts to 0
        assert entry.nmrshiftdb_id == 0
        # name defaults to empty string
        assert entry.name == ""
        assert entry.molecular_formula == "C6H12O6"
        # carbon_count defaults to 0
        assert entry.carbon_count == 0


class TestDatabaseQueryService:
    """Tests for DatabaseQueryService class."""

    def test_get_by_formula_empty_db(self, tmp_path: Path) -> None:
        """Test query against empty database."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

        with DatabaseQueryService(db_path) as query:
            results = query.get_by_formula("C10H12O2")

        assert results == []

    def test_get_by_formula_single_result(self, tmp_path: Path) -> None:
        """Test query returning single compound."""
        db_path = tmp_path / "test.db"

        # Create database with one compound
        with DatabaseManager(db_path) as db:
            db.create_tables()
            compound = CompoundRecord(
                name="Ibuprofen",
                formula="C13H18O2",
                carbon_count=13,
                source="test",
            )
            shifts = [
                ShiftRecord(compound_id=0, shift_ppm=15.1, hydrogen_count=3),
                ShiftRecord(compound_id=0, shift_ppm=22.4, hydrogen_count=2),
            ]
            db.insert_compound(compound, shifts)

        with DatabaseQueryService(db_path) as query:
            results = query.get_by_formula("C13H18O2")

        assert len(results) == 1
        assert results[0].name == "Ibuprofen"
        assert results[0].molecular_formula == "C13H18O2"
        assert len(results[0].signals) == 2
        assert results[0].signals[0].shift == pytest.approx(15.1)
        assert results[0].signals[0].hydrogen_count == HydrogenCount.CH3

    def test_get_by_formula_multiple_results(self, tmp_path: Path) -> None:
        """Test query returning multiple compounds."""
        db_path = tmp_path / "test.db"

        # Create database with multiple compounds with same formula
        with DatabaseManager(db_path) as db:
            db.create_tables()

            for i in range(3):
                compound = CompoundRecord(
                    name=f"Compound_{i}",
                    formula="C10H12O2",
                    carbon_count=10,
                    source="test",
                )
                shifts = [
                    ShiftRecord(compound_id=0, shift_ppm=100.0 + i, hydrogen_count=1),
                ]
                db.insert_compound(compound, shifts)

        with DatabaseQueryService(db_path) as query:
            results = query.get_by_formula("C10H12O2")

        assert len(results) == 3
        names = {r.name for r in results}
        assert names == {"Compound_0", "Compound_1", "Compound_2"}

    def test_get_by_formulas_batch(self, tmp_path: Path) -> None:
        """Test batch query for multiple formulas."""
        db_path = tmp_path / "test.db"

        # Create database with compounds of different formulas
        with DatabaseManager(db_path) as db:
            db.create_tables()

            for formula in ["C10H12O2", "C13H18O2", "C6H12O6"]:
                compound = CompoundRecord(
                    name=f"Compound_{formula}",
                    formula=formula,
                    carbon_count=10,
                    source="test",
                )
                db.insert_compound(compound, [])

        with DatabaseQueryService(db_path) as query:
            results = query.get_by_formulas_batch(
                ["C10H12O2", "C13H18O2", "C20H30O5"]
            )

        assert len(results) == 3
        assert len(results["C10H12O2"]) == 1
        assert len(results["C13H18O2"]) == 1
        assert len(results["C20H30O5"]) == 0  # No match

    def test_formula_normalization(self, tmp_path: Path) -> None:
        """Test that formula lookup handles normalization."""
        db_path = tmp_path / "test.db"

        with DatabaseManager(db_path) as db:
            db.create_tables()
            compound = CompoundRecord(
                name="Test",
                formula="C10H12O2",  # Standard format
                carbon_count=10,
                source="test",
            )
            db.insert_compound(compound, [])

        with DatabaseQueryService(db_path) as query:
            # Query with different format (spaces, subscripts would be normalized)
            results = query.get_by_formula("C10H12O2")

        assert len(results) == 1

    def test_context_manager(self, tmp_path: Path) -> None:
        """Test context manager properly opens and closes connection."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

        query = DatabaseQueryService(db_path)
        assert not query.is_open

        with query:
            assert query.is_open
            query.get_by_formula("C10H12O2")

        assert not query.is_open

    def test_not_open_error(self, tmp_path: Path) -> None:
        """Test that operations fail gracefully when not opened."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

        query = DatabaseQueryService(db_path)

        with pytest.raises(RuntimeError, match="Database not open"):
            query.get_by_formula("C10H12O2")

    def test_get_compound_count(self, tmp_path: Path) -> None:
        """Test get_compound_count method."""
        db_path = tmp_path / "test.db"

        with DatabaseManager(db_path) as db:
            db.create_tables()
            for i in range(5):
                compound = CompoundRecord(
                    name=f"Compound_{i}",
                    formula=f"C{i+1}H{2*i+2}",
                    carbon_count=i + 1,
                    source="test",
                )
                db.insert_compound(compound, [])

        with DatabaseQueryService(db_path) as query:
            count = query.get_compound_count()

        assert count == 5

    def test_get_formula_count(self, tmp_path: Path) -> None:
        """Test get_formula_count method."""
        db_path = tmp_path / "test.db"

        with DatabaseManager(db_path) as db:
            db.create_tables()
            # Add 3 compounds with same formula, 2 with different
            for i in range(3):
                compound = CompoundRecord(
                    name=f"Compound_{i}",
                    formula="C10H12O2",
                    carbon_count=10,
                    source="test",
                )
                db.insert_compound(compound, [])

            for i in range(2):
                compound = CompoundRecord(
                    name=f"Other_{i}",
                    formula=f"C{i+5}H{2*i+10}",
                    carbon_count=i + 5,
                    source="test",
                )
                db.insert_compound(compound, [])

        with DatabaseQueryService(db_path) as query:
            count = query.get_formula_count()

        assert count == 3  # C10H12O2, C5H10, C6H12
