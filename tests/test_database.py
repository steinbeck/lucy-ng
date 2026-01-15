"""Tests for database module."""

from __future__ import annotations

import pytest

from lucy_ng.database import (
    CompoundRecord,
    DatabaseManager,
    HOSEStatsRecord,
    ShiftRecord,
    SCHEMA_VERSION,
)
from lucy_ng.dereplication.nmrshiftdb import CarbonSignal, HydrogenCount, NMRShiftDBEntry


class TestShiftRecord:
    """Tests for ShiftRecord model."""

    def test_basic_creation(self) -> None:
        """Test creating a ShiftRecord with required fields."""
        shift = ShiftRecord(shift_ppm=125.5)
        assert shift.shift_ppm == 125.5
        assert shift.id is None
        assert shift.compound_id is None
        assert shift.atom_index is None
        assert shift.hydrogen_count is None

    def test_full_creation(self) -> None:
        """Test creating a ShiftRecord with all fields."""
        shift = ShiftRecord(
            id=1,
            compound_id=10,
            atom_index=5,
            shift_ppm=45.3,
            hydrogen_count=2,
        )
        assert shift.id == 1
        assert shift.compound_id == 10
        assert shift.atom_index == 5
        assert shift.shift_ppm == 45.3
        assert shift.hydrogen_count == 2

    def test_from_carbon_signal(self) -> None:
        """Test conversion from CarbonSignal."""
        signal = CarbonSignal(
            shift=130.5,
            hydrogen_count=HydrogenCount.CH,
            atom_index=3,
        )
        shift = ShiftRecord.from_carbon_signal(signal, compound_id=42)

        assert shift.shift_ppm == 130.5
        assert shift.hydrogen_count == 1
        assert shift.atom_index == 3
        assert shift.compound_id == 42

    def test_from_carbon_signal_no_hydrogen_count(self) -> None:
        """Test conversion from CarbonSignal without hydrogen count."""
        signal = CarbonSignal(shift=150.0, hydrogen_count=None, atom_index=1)
        shift = ShiftRecord.from_carbon_signal(signal)

        assert shift.shift_ppm == 150.0
        assert shift.hydrogen_count is None

    def test_to_carbon_signal(self) -> None:
        """Test conversion to CarbonSignal."""
        shift = ShiftRecord(
            shift_ppm=25.0,
            hydrogen_count=3,
            atom_index=7,
        )
        signal = shift.to_carbon_signal()

        assert signal.shift == 25.0
        assert signal.hydrogen_count == HydrogenCount.CH3
        assert signal.atom_index == 7

    def test_to_carbon_signal_no_hydrogen_count(self) -> None:
        """Test conversion to CarbonSignal without hydrogen count."""
        shift = ShiftRecord(shift_ppm=200.0, hydrogen_count=None)
        signal = shift.to_carbon_signal()

        assert signal.shift == 200.0
        assert signal.hydrogen_count is None


class TestCompoundRecord:
    """Tests for CompoundRecord model."""

    def test_basic_creation(self) -> None:
        """Test creating a CompoundRecord with required fields."""
        compound = CompoundRecord(formula="C6H12O6")
        assert compound.formula == "C6H12O6"
        assert compound.formula_normalized == "C6H12O6"
        assert compound.id is None
        assert compound.name == ""
        assert compound.smiles == ""
        assert compound.shifts == []

    def test_formula_normalization_subscripts(self) -> None:
        """Test that subscript digits are normalized."""
        compound = CompoundRecord(formula="C₆H₁₂O₆")
        assert compound.formula_normalized == "C6H12O6"

    def test_formula_normalization_whitespace(self) -> None:
        """Test that whitespace is removed from formula."""
        compound = CompoundRecord(formula="C6 H12 O6")
        assert compound.formula_normalized == "C6H12O6"

    def test_formula_normalization_combined(self) -> None:
        """Test combined normalization."""
        compound = CompoundRecord(formula="C₁₃ H₁₈ O₂")
        assert compound.formula_normalized == "C13H18O2"

    def test_full_creation(self) -> None:
        """Test creating a CompoundRecord with all fields."""
        shifts = [ShiftRecord(shift_ppm=125.0), ShiftRecord(shift_ppm=130.0)]
        compound = CompoundRecord(
            id=1,
            name="Test Compound",
            smiles="CCCC",
            formula="C4H10",
            inchi="InChI=1S/C4H10/c1-3-4-2/h3-4H2,1-2H3",
            inchi_key="IJDNQMDRQITEOD-UHFFFAOYSA-N",
            carbon_count=4,
            source="test",
            shifts=shifts,
        )
        assert compound.id == 1
        assert compound.name == "Test Compound"
        assert compound.smiles == "CCCC"
        assert compound.formula == "C4H10"
        assert compound.carbon_count == 4
        assert compound.source == "test"
        assert len(compound.shifts) == 2

    def test_from_nmrshiftdb_entry(self) -> None:
        """Test conversion from NMRShiftDBEntry."""
        entry = NMRShiftDBEntry(
            nmrshiftdb_id=12345,
            name="Caffeine",
            molecular_formula="C8H10N4O2",
            carbon_count=8,
            inchi="InChI=1S/C8H10N4O2/...",
            inchi_key="RYYVLZVUVIJVGH-UHFFFAOYSA-N",
            signals=[
                CarbonSignal(shift=151.5, hydrogen_count=None, atom_index=2),
                CarbonSignal(shift=148.5, hydrogen_count=HydrogenCount.CH, atom_index=8),
            ],
        )
        compound = CompoundRecord.from_nmrshiftdb_entry(entry)

        assert compound.id == 12345
        assert compound.name == "Caffeine"
        assert compound.formula == "C8H10N4O2"
        assert compound.carbon_count == 8
        assert compound.source == "nmrshiftdb"
        assert len(compound.shifts) == 2
        assert compound.shifts[0].shift_ppm == 151.5
        assert compound.shifts[1].hydrogen_count == 1

    def test_to_nmrshiftdb_entry(self) -> None:
        """Test conversion to NMRShiftDBEntry."""
        compound = CompoundRecord(
            id=999,
            name="Test",
            formula="C10H12O2",
            carbon_count=10,
            inchi="InChI=...",
            inchi_key="TEST-KEY",
            shifts=[
                ShiftRecord(shift_ppm=125.0, hydrogen_count=1, atom_index=1),
                ShiftRecord(shift_ppm=130.0, hydrogen_count=0, atom_index=2),
            ],
        )
        entry = compound.to_nmrshiftdb_entry()

        assert entry.nmrshiftdb_id == 999
        assert entry.name == "Test"
        assert entry.molecular_formula == "C10H12O2"
        assert entry.carbon_count == 10
        assert len(entry.signals) == 2
        assert entry.signals[0].shift == 125.0
        assert entry.signals[0].hydrogen_count == HydrogenCount.CH


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    def test_create_tables(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that create_tables creates all required tables."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Check tables exist
            cursor = db.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            assert "compounds" in tables
            assert "shifts" in tables
            assert "schema_meta" in tables

    def test_create_tables_idempotent(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that create_tables can be called multiple times safely."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            db.create_tables()  # Should not raise

            # Verify schema version is set
            assert db.get_schema_version() == SCHEMA_VERSION

    def test_schema_version(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test schema version tracking."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            # Before tables exist
            assert db.get_schema_version() is None

            db.create_tables()
            assert db.get_schema_version() == SCHEMA_VERSION

    def test_indexes_created(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that indexes are created."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            cursor = db.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

            assert "idx_compounds_formula_normalized" in indexes
            assert "idx_shifts_compound_id" in indexes

    def test_insert_compound(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test inserting a compound with shifts."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            compound = CompoundRecord(
                name="Test",
                smiles="CC",
                formula="C2H6",
                carbon_count=2,
                source="test",
            )
            shifts = [
                ShiftRecord(shift_ppm=15.0, atom_index=1, hydrogen_count=3),
                ShiftRecord(shift_ppm=15.0, atom_index=2, hydrogen_count=3),
            ]

            compound_id = db.insert_compound(compound, shifts)
            assert compound_id is not None
            assert compound_id > 0

    def test_insert_compound_with_model_shifts(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test inserting a compound using shifts from the model."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            compound = CompoundRecord(
                name="Propane",
                smiles="CCC",
                formula="C3H8",
                carbon_count=3,
                source="test",
                shifts=[
                    ShiftRecord(shift_ppm=16.0, atom_index=1, hydrogen_count=3),
                    ShiftRecord(shift_ppm=16.0, atom_index=3, hydrogen_count=3),
                    ShiftRecord(shift_ppm=17.0, atom_index=2, hydrogen_count=2),
                ],
            )

            # Insert without explicit shifts - should use compound.shifts
            compound_id = db.insert_compound(compound)
            assert compound_id is not None

            # Verify shifts were stored
            results = db.get_by_formula("C3H8")
            assert len(results) == 1
            assert len(results[0].shifts) == 3

    def test_get_by_formula(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test retrieving compounds by formula."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert two compounds with same formula
            for name in ["Compound A", "Compound B"]:
                compound = CompoundRecord(
                    name=name,
                    formula="C6H12O6",
                    source="test",
                )
                db.insert_compound(compound, [ShiftRecord(shift_ppm=70.0)])

            # Insert compound with different formula
            other = CompoundRecord(name="Other", formula="C10H20", source="test")
            db.insert_compound(other, [])

            # Query by formula
            results = db.get_by_formula("C6H12O6")
            assert len(results) == 2
            assert {r.name for r in results} == {"Compound A", "Compound B"}

    def test_get_by_formula_normalization(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that get_by_formula normalizes input formula."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            compound = CompoundRecord(
                name="Test",
                formula="C13H18O2",
                source="test",
            )
            db.insert_compound(compound, [])

            # Query with subscripts
            results = db.get_by_formula("C₁₃H₁₈O₂")
            assert len(results) == 1
            assert results[0].name == "Test"

            # Query with whitespace
            results = db.get_by_formula("C13 H18 O2")
            assert len(results) == 1

    def test_get_by_formula_with_shifts(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that get_by_formula returns compounds with shifts populated."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            compound = CompoundRecord(
                name="Multi-shift",
                formula="C5H10",
                source="test",
            )
            shifts = [
                ShiftRecord(shift_ppm=10.0, atom_index=1, hydrogen_count=3),
                ShiftRecord(shift_ppm=20.0, atom_index=2, hydrogen_count=2),
                ShiftRecord(shift_ppm=30.0, atom_index=3, hydrogen_count=2),
            ]
            db.insert_compound(compound, shifts)

            results = db.get_by_formula("C5H10")
            assert len(results) == 1
            assert len(results[0].shifts) == 3
            assert results[0].shifts[0].shift_ppm == 10.0

    def test_get_by_formula_not_found(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that get_by_formula returns empty list for non-existent formula."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            results = db.get_by_formula("C100H200")
            assert results == []

    def test_batch_insert(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test batch insert of compounds."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            compounds: list[tuple[CompoundRecord, list[ShiftRecord]]] = []
            for i in range(50):
                compound = CompoundRecord(
                    name=f"Compound {i}",
                    formula="C10H20",
                    source="batch",
                )
                shifts = [ShiftRecord(shift_ppm=float(i * 10))]
                compounds.append((compound, shifts))

            count = db.insert_compounds_batch(compounds, batch_size=10)
            assert count == 50
            assert db.get_compound_count() == 50

    def test_get_compound_count(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test compound count."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            assert db.get_compound_count() == 0

            for i in range(5):
                compound = CompoundRecord(name=f"C{i}", formula=f"C{i}H{i}", source="test")
                db.insert_compound(compound, [])

            assert db.get_compound_count() == 5

    def test_get_formula_count(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test unique formula count."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Add 3 compounds with formula A
            for i in range(3):
                compound = CompoundRecord(name=f"A{i}", formula="C10H20", source="test")
                db.insert_compound(compound, [])

            # Add 2 compounds with formula B
            for i in range(2):
                compound = CompoundRecord(name=f"B{i}", formula="C20H40", source="test")
                db.insert_compound(compound, [])

            assert db.get_compound_count() == 5
            assert db.get_formula_count() == 2

    def test_iter_all_formulas(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test iterating over unique formulas."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            formulas = ["C10H20", "C5H10", "C15H30", "C10H20"]  # One duplicate
            for i, formula in enumerate(formulas):
                compound = CompoundRecord(name=f"C{i}", formula=formula, source="test")
                db.insert_compound(compound, [])

            unique_formulas = list(db.iter_all_formulas())
            assert len(unique_formulas) == 3
            # Should be sorted
            assert unique_formulas == sorted(unique_formulas)

    def test_context_manager(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that context manager properly closes connection."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)

        with db:
            db.create_tables()
            assert db._conn is not None

        assert db._conn is None

    def test_close(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test explicit close."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        db.create_tables()
        assert db._conn is not None

        db.close()
        assert db._conn is None

        # Double close should be safe
        db.close()

    def test_foreign_keys_cascade(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that deleting compound cascades to shifts."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            compound = CompoundRecord(name="Test", formula="C5H10", source="test")
            shifts = [ShiftRecord(shift_ppm=25.0), ShiftRecord(shift_ppm=30.0)]
            compound_id = db.insert_compound(compound, shifts)

            # Delete compound directly
            db.connection.execute("DELETE FROM compounds WHERE id = ?", (compound_id,))
            db.connection.commit()

            # Shifts should be gone too
            cursor = db.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM shifts WHERE compound_id = ?", (compound_id,))
            assert cursor.fetchone()[0] == 0


class TestHOSEStatsRecord:
    """Tests for HOSEStatsRecord model."""

    def test_basic_creation(self) -> None:
        """Test creating a HOSEStatsRecord with required fields."""
        stat = HOSEStatsRecord(
            hose_code="C(CC)",
            radius=3,
            mean=25.5,
            std=2.1,
            count=150,
        )
        assert stat.hose_code == "C(CC)"
        assert stat.radius == 3
        assert stat.mean == 25.5
        assert stat.std == 2.1
        assert stat.count == 150


class TestHOSEStatsDatabase:
    """Tests for HOSE statistics database methods."""

    def test_hose_stats_table_created(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that hose_stats table is created."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            cursor = db.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            assert "hose_stats" in tables

    def test_hose_stats_index_created(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that hose_stats index is created."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            cursor = db.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

            assert "idx_hose_stats_code" in indexes

    def test_insert_hose_stats_batch(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test batch inserting HOSE statistics."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            stats = [
                HOSEStatsRecord(hose_code="C(CC)", radius=1, mean=25.0, std=2.0, count=100),
                HOSEStatsRecord(hose_code="C(CC)", radius=2, mean=25.5, std=1.8, count=80),
                HOSEStatsRecord(hose_code="C(CC)", radius=3, mean=25.8, std=1.5, count=50),
                HOSEStatsRecord(hose_code="C(C=O)", radius=1, mean=170.0, std=5.0, count=200),
            ]

            count = db.insert_hose_stats_batch(stats)
            assert count == 4
            assert db.get_hose_stats_count() == 4

    def test_insert_hose_stats_batch_replace(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that batch insert replaces existing entries."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert initial stats
            stats1 = [
                HOSEStatsRecord(hose_code="C(CC)", radius=1, mean=25.0, std=2.0, count=100),
            ]
            db.insert_hose_stats_batch(stats1)

            # Insert again with different values - should replace
            stats2 = [
                HOSEStatsRecord(hose_code="C(CC)", radius=1, mean=26.0, std=1.5, count=150),
            ]
            db.insert_hose_stats_batch(stats2)

            # Should still be 1 entry, not 2
            assert db.get_hose_stats_count() == 1

            # Should have updated values
            result = db.get_hose_stats("C(CC)", 1)
            assert result is not None
            assert result.mean == 26.0
            assert result.std == 1.5
            assert result.count == 150

    def test_get_hose_stats(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test getting HOSE stats for specific code and radius."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            stats = [
                HOSEStatsRecord(hose_code="C(CC)", radius=3, mean=25.5, std=2.1, count=150),
                HOSEStatsRecord(hose_code="C(CC)", radius=4, mean=25.8, std=1.8, count=80),
            ]
            db.insert_hose_stats_batch(stats)

            # Get specific entry
            result = db.get_hose_stats("C(CC)", 3)
            assert result is not None
            assert result.hose_code == "C(CC)"
            assert result.radius == 3
            assert result.mean == 25.5
            assert result.std == 2.1
            assert result.count == 150

            # Get different radius
            result = db.get_hose_stats("C(CC)", 4)
            assert result is not None
            assert result.radius == 4
            assert result.mean == 25.8

    def test_get_hose_stats_not_found(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test getting HOSE stats for non-existent entry."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Non-existent HOSE code
            result = db.get_hose_stats("NONEXISTENT", 3)
            assert result is None

            # Add some data
            stats = [HOSEStatsRecord(hose_code="C(CC)", radius=3, mean=25.0, std=2.0, count=100)]
            db.insert_hose_stats_batch(stats)

            # Existing code, non-existent radius
            result = db.get_hose_stats("C(CC)", 6)
            assert result is None

    def test_get_hose_stats_all_radii(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test getting HOSE stats at all radii for a code."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert stats at multiple radii
            stats = [
                HOSEStatsRecord(hose_code="C(CC)", radius=1, mean=25.0, std=3.0, count=200),
                HOSEStatsRecord(hose_code="C(CC)", radius=2, mean=25.3, std=2.5, count=150),
                HOSEStatsRecord(hose_code="C(CC)", radius=4, mean=25.7, std=1.5, count=50),
                # Different code - should not be returned
                HOSEStatsRecord(hose_code="C(C=O)", radius=1, mean=170.0, std=5.0, count=100),
            ]
            db.insert_hose_stats_batch(stats)

            results = db.get_hose_stats_all_radii("C(CC)")
            assert len(results) == 3

            # Should be ordered by radius descending
            assert results[0].radius == 4
            assert results[1].radius == 2
            assert results[2].radius == 1

            # Verify values
            assert results[0].mean == 25.7
            assert results[2].count == 200

    def test_get_hose_stats_all_radii_not_found(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Test getting HOSE stats for non-existent code returns empty list."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            results = db.get_hose_stats_all_radii("NONEXISTENT")
            assert results == []

    def test_get_hose_stats_count(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test counting HOSE stats entries."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            assert db.get_hose_stats_count() == 0

            stats = [
                HOSEStatsRecord(hose_code="C(CC)", radius=r, mean=25.0, std=2.0, count=100)
                for r in range(1, 7)
            ]
            db.insert_hose_stats_batch(stats)

            assert db.get_hose_stats_count() == 6

    def test_insert_hose_stats_batch_large(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test batch insert with batch_size commits."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert 250 records with batch_size=100
            stats = [
                HOSEStatsRecord(
                    hose_code=f"C{i}(CC)",
                    radius=1,
                    mean=float(i),
                    std=1.0,
                    count=10,
                )
                for i in range(250)
            ]

            count = db.insert_hose_stats_batch(stats, batch_size=100)
            assert count == 250
            assert db.get_hose_stats_count() == 250
