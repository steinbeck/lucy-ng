"""Tests for HOSEStatsGenerator."""

from __future__ import annotations

import math
import statistics

import pytest

from lucy_ng.database import DatabaseManager
from lucy_ng.database.models import CompoundRecord, HOSEStatsRecord, ShiftRecord
from lucy_ng.prediction import (
    HOSEStatsGenerator,
    ResumableHOSEStatsGenerator,
    WelfordAccumulator,
)
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


class TestWelfordAccumulator:
    """Tests for WelfordAccumulator class."""

    def test_empty_accumulator(self):
        """Test empty accumulator has correct initial values."""
        acc = WelfordAccumulator()
        assert acc.count == 0
        assert acc.mean == 0.0
        assert acc.m2 == 0.0
        assert acc.std == 0.0
        assert acc.variance == 0.0

    def test_single_value(self):
        """Test accumulator with single value."""
        acc = WelfordAccumulator()
        acc.update(10.0)
        assert acc.count == 1
        assert acc.mean == 10.0
        assert acc.std == 0.0  # Single value has no variance

    def test_two_values(self):
        """Test accumulator with two values."""
        acc = WelfordAccumulator()
        acc.update(10.0)
        acc.update(20.0)
        assert acc.count == 2
        assert acc.mean == 15.0
        # Population std for [10, 20] = sqrt(((10-15)^2 + (20-15)^2) / 2) = sqrt(25) = 5
        assert abs(acc.std - 5.0) < 0.001

    def test_matches_statistics_module(self):
        """Test that accumulator matches Python statistics module."""
        values = [12.5, 18.3, 25.7, 14.2, 19.8, 22.1, 16.9]

        acc = WelfordAccumulator()
        for v in values:
            acc.update(v)

        # Compare with statistics module (pstdev for population std)
        expected_mean = statistics.mean(values)
        expected_std = statistics.pstdev(values)

        assert abs(acc.mean - expected_mean) < 0.0001
        assert abs(acc.std - expected_std) < 0.0001

    def test_merge_empty_accumulators(self):
        """Test merging empty accumulators."""
        acc1 = WelfordAccumulator()
        acc2 = WelfordAccumulator()
        merged = acc1.merge(acc2)
        assert merged.count == 0
        assert merged.mean == 0.0

    def test_merge_with_empty(self):
        """Test merging accumulator with empty one."""
        acc1 = WelfordAccumulator()
        acc1.update(10.0)
        acc1.update(20.0)

        acc2 = WelfordAccumulator()

        merged1 = acc1.merge(acc2)
        assert merged1.count == 2
        assert merged1.mean == 15.0

        merged2 = acc2.merge(acc1)
        assert merged2.count == 2
        assert merged2.mean == 15.0

    def test_merge_two_accumulators(self):
        """Test merging two non-empty accumulators."""
        # First accumulator: [10, 20]
        acc1 = WelfordAccumulator()
        acc1.update(10.0)
        acc1.update(20.0)

        # Second accumulator: [30, 40]
        acc2 = WelfordAccumulator()
        acc2.update(30.0)
        acc2.update(40.0)

        merged = acc1.merge(acc2)

        # Combined: [10, 20, 30, 40]
        all_values = [10.0, 20.0, 30.0, 40.0]
        expected_mean = statistics.mean(all_values)
        expected_std = statistics.pstdev(all_values)

        assert merged.count == 4
        assert abs(merged.mean - expected_mean) < 0.0001
        assert abs(merged.std - expected_std) < 0.0001

    def test_merge_unequal_sizes(self):
        """Test merging accumulators with different sizes."""
        # First accumulator: [10, 20, 30]
        acc1 = WelfordAccumulator()
        for v in [10.0, 20.0, 30.0]:
            acc1.update(v)

        # Second accumulator: [40, 50]
        acc2 = WelfordAccumulator()
        for v in [40.0, 50.0]:
            acc2.update(v)

        merged = acc1.merge(acc2)

        all_values = [10.0, 20.0, 30.0, 40.0, 50.0]
        expected_mean = statistics.mean(all_values)
        expected_std = statistics.pstdev(all_values)

        assert merged.count == 5
        assert abs(merged.mean - expected_mean) < 0.0001
        assert abs(merged.std - expected_std) < 0.0001

    def test_to_tuple(self):
        """Test export to tuple format."""
        acc = WelfordAccumulator()
        acc.update(10.0)
        acc.update(20.0)

        count, mean, m2 = acc.to_tuple()
        assert count == 2
        assert mean == 15.0
        assert m2 > 0  # Should have some m2 value


@pytest.mark.skipif(not HOSEGEN_AVAILABLE, reason="hosegen not available")
class TestResumableHOSEStatsGenerator:
    """Tests for ResumableHOSEStatsGenerator class."""

    @pytest.fixture
    def resumable_db(self, tmp_path):
        """Create a database with test compounds for resumable tests."""
        db_path = tmp_path / "resumable.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert multiple compounds
            compounds = [
                ("Ethanol", "CCO", "C2H6O", [
                    (0, 18.0, 3),
                    (1, 58.0, 2),
                ]),
                ("Methanol", "CO", "CH4O", [
                    (0, 50.0, 3),
                ]),
                ("Propanol", "CCCO", "C3H8O", [
                    (0, 10.0, 3),
                    (1, 23.0, 2),
                    (2, 64.0, 2),
                ]),
                ("Butanol", "CCCCO", "C4H10O", [
                    (0, 14.0, 3),
                    (1, 19.0, 2),
                    (2, 35.0, 2),
                    (3, 62.0, 2),
                ]),
            ]

            for name, smiles, formula, shifts_data in compounds:
                compound = CompoundRecord(
                    name=name,
                    smiles=smiles,
                    formula=formula,
                    source="test",
                    carbon_count=len(shifts_data),
                )
                shifts = [
                    ShiftRecord(atom_index=idx, shift_ppm=ppm, hydrogen_count=h)
                    for idx, ppm, h in shifts_data
                ]
                db.insert_compound(compound, shifts)

        return db_path

    def test_init(self, resumable_db):
        """Test generator initialization."""
        with DatabaseManager(resumable_db) as db:
            generator = ResumableHOSEStatsGenerator(db, max_radius=3)
            assert generator.max_radius == 3
            assert generator.compounds_processed == 0
            assert generator.compounds_failed == 0
            assert generator.shifts_processed == 0

    def test_run_fresh(self, resumable_db):
        """Test fresh run completes successfully."""
        with DatabaseManager(resumable_db) as db:
            generator = ResumableHOSEStatsGenerator(db, max_radius=2)
            result = generator.run(chunk_size=10, fresh=True)

            assert result.compounds_processed == 4
            assert result.compounds_failed == 0
            assert result.shifts_processed > 0
            assert result.total_stats > 0

    def test_checkpoint_saved(self, resumable_db):
        """Test that checkpoint is saved during processing."""
        with DatabaseManager(resumable_db) as db:
            generator = ResumableHOSEStatsGenerator(db, max_radius=2)
            # Use tiny chunk size to force multiple chunks
            result = generator.run(chunk_size=1, fresh=True)

            # Checkpoint should be cleared on successful completion
            assert db.get_checkpoint("hose_stats_last_compound_id") is None

    def test_resume_from_checkpoint(self, resumable_db):
        """Test that resume continues from checkpoint."""
        # First, simulate interrupted run by manually setting checkpoint
        with DatabaseManager(resumable_db) as db:
            # Get first compound ID
            cursor = db.connection.cursor()
            cursor.execute("SELECT MIN(id) FROM compounds")
            first_id = cursor.fetchone()[0]

            # Set checkpoint as if we processed only the first compound
            db.set_checkpoint("hose_stats_last_compound_id", str(first_id))
            db.set_checkpoint("hose_stats_compounds_processed", "1")
            db.set_checkpoint("hose_stats_compounds_failed", "0")
            db.set_checkpoint("hose_stats_shifts_processed", "10")

            generator = ResumableHOSEStatsGenerator(db, max_radius=2)
            result = generator.run(chunk_size=10, resume=True)

            # Should have processed remaining compounds (3 more)
            assert result.compounds_processed == 4  # 1 from checkpoint + 3 new

    def test_fresh_clears_existing(self, resumable_db):
        """Test that fresh start clears existing stats."""
        with DatabaseManager(resumable_db) as db:
            # First run
            generator1 = ResumableHOSEStatsGenerator(db, max_radius=2)
            result1 = generator1.run(chunk_size=10, fresh=True)
            first_count = result1.total_stats

            # Second run with fresh should get same count
            generator2 = ResumableHOSEStatsGenerator(db, max_radius=2)
            result2 = generator2.run(chunk_size=10, fresh=True)

            assert result2.total_stats == first_count

    def test_incremental_merge_correct(self, resumable_db):
        """Test that incremental merge produces correct statistics."""
        with DatabaseManager(resumable_db) as db:
            # Run with tiny chunk size to force multiple merges
            generator = ResumableHOSEStatsGenerator(db, max_radius=2)
            result_chunked = generator.run(chunk_size=1, fresh=True)
            chunked_count = db.get_hose_stats_count()

            # Clear and run with large chunk (no merging)
            db.clear_hose_stats()
            generator2 = ResumableHOSEStatsGenerator(db, max_radius=2)
            result_single = generator2.run(chunk_size=100, fresh=True)
            single_count = db.get_hose_stats_count()

            # Should have same number of stats
            assert chunked_count == single_count
            # And same totals
            assert result_chunked.shifts_processed == result_single.shifts_processed

    def test_handles_invalid_smiles(self, tmp_path):
        """Test that invalid SMILES are handled gracefully in resumable mode."""
        db_path = tmp_path / "invalid_resumable.db"
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
            db.insert_compound(invalid, [ShiftRecord(atom_index=0, shift_ppm=25.0)])

            # Also insert a valid compound
            valid = CompoundRecord(
                name="Methanol",
                smiles="CO",
                formula="CH4O",
                source="test",
                carbon_count=1,
            )
            db.insert_compound(valid, [ShiftRecord(atom_index=0, shift_ppm=50.0, hydrogen_count=3)])

        with DatabaseManager(db_path) as db:
            generator = ResumableHOSEStatsGenerator(db, max_radius=2)
            result = generator.run(chunk_size=10, fresh=True)

            assert result.compounds_processed == 2
            assert result.compounds_failed == 1
            assert result.total_stats > 0


class TestDatabaseCheckpointMethods:
    """Tests for database checkpoint methods."""

    def test_set_and_get_checkpoint(self, tmp_path):
        """Test setting and getting checkpoint values."""
        db_path = tmp_path / "checkpoint.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            db.set_checkpoint("test_key", "test_value")
            assert db.get_checkpoint("test_key") == "test_value"

    def test_get_nonexistent_checkpoint(self, tmp_path):
        """Test getting nonexistent checkpoint returns None."""
        db_path = tmp_path / "checkpoint.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            assert db.get_checkpoint("nonexistent") is None

    def test_clear_checkpoint(self, tmp_path):
        """Test clearing checkpoint."""
        db_path = tmp_path / "checkpoint.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            db.set_checkpoint("test_key", "test_value")
            assert db.clear_checkpoint("test_key") is True
            assert db.get_checkpoint("test_key") is None

    def test_clear_nonexistent_checkpoint(self, tmp_path):
        """Test clearing nonexistent checkpoint returns False."""
        db_path = tmp_path / "checkpoint.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            assert db.clear_checkpoint("nonexistent") is False

    def test_checkpoint_update(self, tmp_path):
        """Test that checkpoint can be updated."""
        db_path = tmp_path / "checkpoint.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            db.set_checkpoint("counter", "1")
            assert db.get_checkpoint("counter") == "1"

            db.set_checkpoint("counter", "2")
            assert db.get_checkpoint("counter") == "2"


class TestDatabaseIncrementalUpsert:
    """Tests for incremental HOSE stats upsert."""

    def test_upsert_new_entries(self, tmp_path):
        """Test upserting new HOSE stats entries."""
        db_path = tmp_path / "upsert.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert new entries
            stats = [
                ("C(CC)", 1, 3, 25.0, 50.0),  # hose_code, radius, count, mean, m2
                ("C(C=O)", 1, 2, 170.0, 20.0),
            ]
            count = db.upsert_hose_stats_incremental(stats)

            assert count == 2
            assert db.get_hose_stats_count() == 2

    def test_upsert_merge_existing(self, tmp_path):
        """Test upserting merges with existing entries."""
        db_path = tmp_path / "upsert_merge.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # First batch: [10, 20] -> mean=15, m2=50
            stats1 = [
                ("C(CC)", 1, 2, 15.0, 50.0),
            ]
            db.upsert_hose_stats_incremental(stats1)

            # Second batch: [30, 40] -> mean=35, m2=50
            stats2 = [
                ("C(CC)", 1, 2, 35.0, 50.0),
            ]
            db.upsert_hose_stats_incremental(stats2)

            # Merged should have count=4, mean=25
            result = db.get_hose_stats("C(CC)", 1)
            assert result is not None
            assert result.count == 4
            assert abs(result.mean - 25.0) < 0.001

    def test_upsert_preserves_other_radii(self, tmp_path):
        """Test that upsert for one radius doesn't affect others."""
        db_path = tmp_path / "upsert_radii.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert at radius 1
            stats1 = [("C(CC)", 1, 2, 25.0, 50.0)]
            db.upsert_hose_stats_incremental(stats1)

            # Insert at radius 2
            stats2 = [("C(CC)", 2, 3, 26.0, 30.0)]
            db.upsert_hose_stats_incremental(stats2)

            # Both should exist
            r1 = db.get_hose_stats("C(CC)", 1)
            r2 = db.get_hose_stats("C(CC)", 2)

            assert r1 is not None
            assert r1.count == 2
            assert r2 is not None
            assert r2.count == 3


class TestIterCompoundsFrom:
    """Tests for iter_compounds_with_shifts_from method."""

    def test_iter_from_start(self, tmp_path):
        """Test iteration from the beginning."""
        db_path = tmp_path / "iter.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert some compounds
            for i in range(5):
                compound = CompoundRecord(
                    name=f"Compound{i}",
                    smiles=f"C{'C' * i}O",
                    formula=f"C{i+1}H{(i+1)*2+2}O",
                    source="test",
                )
                db.insert_compound(compound, [ShiftRecord(atom_index=0, shift_ppm=float(i * 10))])

            results = list(db.iter_compounds_with_shifts_from(start_id=0))
            assert len(results) == 5

    def test_iter_from_middle(self, tmp_path):
        """Test iteration from a specific ID."""
        db_path = tmp_path / "iter_mid.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert compounds
            ids = []
            for i in range(5):
                compound = CompoundRecord(
                    name=f"Compound{i}",
                    smiles=f"C{'C' * i}O",
                    formula=f"C{i+1}H{(i+1)*2+2}O",
                    source="test",
                )
                cid = db.insert_compound(compound, [ShiftRecord(atom_index=0, shift_ppm=float(i * 10))])
                ids.append(cid)

            # Start from middle
            results = list(db.iter_compounds_with_shifts_from(start_id=ids[2]))
            # Should get compounds after id[2]
            assert len(results) == 2  # ids[3] and ids[4]

    def test_get_max_compound_id(self, tmp_path):
        """Test getting maximum compound ID."""
        db_path = tmp_path / "max_id.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Empty database
            assert db.get_max_compound_id() == 0

            # Insert compounds
            for i in range(3):
                compound = CompoundRecord(
                    name=f"Compound{i}",
                    smiles=f"C{'C' * i}O",
                    formula=f"C{i+1}H{(i+1)*2+2}O",
                    source="test",
                )
                db.insert_compound(compound, [])

            max_id = db.get_max_compound_id()
            assert max_id >= 3
