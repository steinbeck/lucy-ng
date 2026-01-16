"""Tests for HOSEStatsGenerator."""

from __future__ import annotations

import pytest

from lucy_ng.database import DatabaseManager
from lucy_ng.database.models import CompoundRecord, HOSEStatsRecord, ShiftRecord
from lucy_ng.prediction import HOSEStatsGenerator
from lucy_ng.prediction.hose import HOSEGEN_AVAILABLE


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with test compounds."""
    db_path = tmp_path / "test.db"
    with DatabaseManager(db_path) as db:
        db.create_tables()

        # Insert test compound: ethanol (CC O)
        # C1: CH3 at ~18 ppm (index 0)
        # C2: CH2 at ~58 ppm (index 1)
        ethanol = CompoundRecord(
            name="Ethanol",
            smiles="CCO",
            formula="C2H6O",
            source="test",
            carbon_count=2,
        )
        ethanol_shifts = [
            ShiftRecord(atom_index=0, shift_ppm=18.0, hydrogen_count=3),  # CH3
            ShiftRecord(atom_index=1, shift_ppm=58.0, hydrogen_count=2),  # CH2
        ]
        db.insert_compound(ethanol, ethanol_shifts)

        # Insert second compound: methanol (CO)
        # C1: CH3 at ~50 ppm (index 0)
        methanol = CompoundRecord(
            name="Methanol",
            smiles="CO",
            formula="CH4O",
            source="test",
            carbon_count=1,
        )
        methanol_shifts = [
            ShiftRecord(atom_index=0, shift_ppm=50.0, hydrogen_count=3),  # CH3
        ]
        db.insert_compound(methanol, methanol_shifts)

        # Insert compound without shifts (should be skipped)
        no_shifts = CompoundRecord(
            name="Empty",
            smiles="C",  # Methane
            formula="CH4",
            source="test",
            carbon_count=1,
        )
        db.insert_compound(no_shifts, [])

    yield db_path


@pytest.fixture
def db_manager(temp_db):
    """Get database manager for test database."""
    with DatabaseManager(temp_db) as db:
        yield db


@pytest.mark.skipif(not HOSEGEN_AVAILABLE, reason="hosegen not available")
class TestHOSEStatsGenerator:
    """Tests for HOSEStatsGenerator class."""

    def test_init(self, db_manager):
        """Test generator initialization."""
        generator = HOSEStatsGenerator(db_manager, max_radius=4)
        assert generator.max_radius == 4
        assert generator.compounds_processed == 0
        assert generator.compounds_failed == 0
        assert generator.shifts_processed == 0

    def test_generate_all(self, db_manager):
        """Test generating HOSE aggregates from all compounds."""
        generator = HOSEStatsGenerator(db_manager, max_radius=3)
        aggregates = generator.generate_all(progress=False)

        # Should have generated some aggregates
        assert len(aggregates) > 0

        # All keys should be (hose_code, radius) tuples
        for key in aggregates:
            assert isinstance(key, tuple)
            assert len(key) == 2
            hose_code, radius = key
            assert isinstance(hose_code, str)
            assert isinstance(radius, int)
            assert 1 <= radius <= 3

        # All values should be non-empty lists of floats
        for shifts in aggregates.values():
            assert isinstance(shifts, list)
            assert len(shifts) > 0
            for shift in shifts:
                assert isinstance(shift, float)

        # Statistics tracking should be updated
        assert generator.compounds_processed == 2  # ethanol + methanol (empty skipped)
        assert generator.shifts_processed > 0

    def test_compute_stats(self, db_manager):
        """Test computing statistics from aggregates."""
        generator = HOSEStatsGenerator(db_manager)

        # Create mock aggregates
        aggregates = {
            ("C(C)(O)", 1): [18.0, 19.0, 17.0],  # 3 observations
            ("C(O)", 1): [50.0],  # 1 observation
        }

        stats = generator.compute_stats(aggregates)

        assert len(stats) == 2

        # Find the C(C)(O) stat
        c_c_o_stat = next(s for s in stats if s.hose_code == "C(C)(O)")
        assert c_c_o_stat.radius == 1
        assert c_c_o_stat.count == 3
        assert abs(c_c_o_stat.mean - 18.0) < 0.1  # mean of 18, 19, 17
        assert c_c_o_stat.std > 0  # should have non-zero std

        # Find the C(O) stat (single observation)
        c_o_stat = next(s for s in stats if s.hose_code == "C(O)")
        assert c_o_stat.radius == 1
        assert c_o_stat.count == 1
        assert c_o_stat.mean == 50.0
        assert c_o_stat.std == 0.0  # single observation = 0 std

    def test_compute_stats_empty_aggregates(self, db_manager):
        """Test that empty aggregates return empty stats."""
        generator = HOSEStatsGenerator(db_manager)
        stats = generator.compute_stats({})
        assert stats == []

    def test_compute_stats_skips_empty_lists(self, db_manager):
        """Test that aggregates with empty lists are skipped."""
        generator = HOSEStatsGenerator(db_manager)
        aggregates = {
            ("C(C)", 1): [25.0],
            ("C(O)", 1): [],  # empty - should be skipped
        }
        stats = generator.compute_stats(aggregates)
        assert len(stats) == 1
        assert stats[0].hose_code == "C(C)"

    def test_populate_database(self, db_manager):
        """Test full pipeline: generate and insert stats."""
        generator = HOSEStatsGenerator(db_manager, max_radius=2)
        count = generator.populate_database(progress=False, batch_size=100)

        # Should have inserted some stats
        assert count > 0

        # Verify stats are in database
        db_count = db_manager.get_hose_stats_count()
        assert db_count == count

    def test_populate_database_idempotent(self, db_manager):
        """Test that populate_database can be run multiple times."""
        generator = HOSEStatsGenerator(db_manager, max_radius=2)

        # Run twice
        count1 = generator.populate_database(progress=False)
        count2 = generator.populate_database(progress=False)

        # Should have same count (INSERT OR REPLACE)
        assert count1 == count2

        # Database should have same count as single run
        db_count = db_manager.get_hose_stats_count()
        assert db_count == count1

    def test_statistics_properties(self, db_manager):
        """Test that statistics properties are tracked correctly."""
        generator = HOSEStatsGenerator(db_manager, max_radius=2)
        generator.generate_all(progress=False)

        # Two compounds with shifts (ethanol + methanol)
        assert generator.compounds_processed == 2

        # No failed compounds in this test
        assert generator.compounds_failed == 0

        # 3 carbons total: 2 from ethanol + 1 from methanol
        # At radii 1 and 2, that's 3 * 2 = 6 shifts processed
        assert generator.shifts_processed >= 6


@pytest.mark.skipif(not HOSEGEN_AVAILABLE, reason="hosegen not available")
class TestHOSEStatsGeneratorEdgeCases:
    """Edge case tests for HOSEStatsGenerator."""

    def test_handles_invalid_smiles(self, tmp_path):
        """Test that invalid SMILES are handled gracefully."""
        db_path = tmp_path / "invalid.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert compound with invalid SMILES
            invalid = CompoundRecord(
                name="Invalid",
                smiles="not_valid_smiles",
                formula="C5H10",
                source="test",
                carbon_count=5,
            )
            invalid_shifts = [
                ShiftRecord(atom_index=0, shift_ppm=25.0),
            ]
            db.insert_compound(invalid, invalid_shifts)

            # Also insert a valid compound
            valid = CompoundRecord(
                name="Methanol",
                smiles="CO",
                formula="CH4O",
                source="test",
                carbon_count=1,
            )
            valid_shifts = [
                ShiftRecord(atom_index=0, shift_ppm=50.0, hydrogen_count=3),
            ]
            db.insert_compound(valid, valid_shifts)

        with DatabaseManager(db_path) as db:
            generator = HOSEStatsGenerator(db, max_radius=2)
            aggregates = generator.generate_all(progress=False)

            # Should still have processed the valid compound
            assert generator.compounds_processed == 2  # Both attempted
            assert generator.compounds_failed == 1  # Invalid SMILES failed
            assert len(aggregates) > 0  # Valid compound generated stats

    def test_handles_invalid_atom_index(self, tmp_path):
        """Test that invalid atom indices are skipped gracefully."""
        db_path = tmp_path / "bad_index.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert compound with out-of-range atom index
            compound = CompoundRecord(
                name="Test",
                smiles="CO",  # Only 2 atoms (C=0, O=1)
                formula="CH4O",
                source="test",
                carbon_count=1,
            )
            shifts = [
                ShiftRecord(atom_index=0, shift_ppm=50.0),  # Valid
                ShiftRecord(atom_index=99, shift_ppm=100.0),  # Invalid index
            ]
            db.insert_compound(compound, shifts)

        with DatabaseManager(db_path) as db:
            generator = HOSEStatsGenerator(db, max_radius=2)
            # Should not raise exception
            aggregates = generator.generate_all(progress=False)

            # Should have processed valid shift only
            assert len(aggregates) > 0
            assert generator.compounds_failed == 0  # Compound itself didn't fail

    def test_handles_none_atom_index(self, tmp_path):
        """Test that None atom indices are skipped."""
        db_path = tmp_path / "none_index.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            compound = CompoundRecord(
                name="Test",
                smiles="CO",
                formula="CH4O",
                source="test",
                carbon_count=1,
            )
            shifts = [
                ShiftRecord(atom_index=None, shift_ppm=50.0),  # None index
            ]
            db.insert_compound(compound, shifts)

        with DatabaseManager(db_path) as db:
            generator = HOSEStatsGenerator(db, max_radius=2)
            aggregates = generator.generate_all(progress=False)

            # Should process compound but skip the shift with None index
            assert generator.compounds_processed == 1
            # No valid shifts to process
            assert generator.shifts_processed == 0
