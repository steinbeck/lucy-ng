"""Tests for fragment database infrastructure (Phase 49).

Covers:
- FragmentDatabaseManager table creation, idempotency, and metadata
- SSCRecord model: field_validator for shift_list parsing, serialization
- SSCMatch model: serialization
- Batch insert with deduplication and bitset handling
- iter_ssc_bitsets and get_ssc_by_id query methods
- Edge cases: empty inputs, missing tables, schema isolation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ailsa.fragments import FragmentDatabaseManager, SSCMatch, SSCRecord
from ailsa.fragments.schema import FRAGMENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_ssc(
    smiles: str,
    shifts: list[float],
    bitset: bytes | None = None,
) -> SSCRecord:
    """Build an SSCRecord with computed avg/min/max from shifts."""
    return SSCRecord(
        smiles=smiles,
        atom_count=len(smiles.replace("(", "").replace(")", "").replace("=", "")),
        shift_list=shifts,
        avg_shift=sum(shifts) / len(shifts),
        min_shift=min(shifts),
        max_shift=max(shifts),
        bitset=bitset,
    )


# ---------------------------------------------------------------------------
# Table Creation
# ---------------------------------------------------------------------------


class TestCreateTables:
    """Tests for FragmentDatabaseManager.create_tables()."""

    def test_create_tables_idempotent(self, tmp_path: Path) -> None:
        """create_tables() must be callable twice without error."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.create_tables()  # second call — must not raise
            assert db.get_schema_version() == FRAGMENT_SCHEMA_VERSION
            assert db.get_bin_size() == 2.0

    def test_bin_size_not_overwritten(self, tmp_path: Path) -> None:
        """bin_size in schema_meta must survive a second create_tables() call.

        Uses INSERT OR IGNORE semantics, so an existing bin_size (e.g. after
        custom extraction with a different value) is preserved.
        """
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            # Manually override bin_size to simulate a custom extraction
            db.connection.execute(
                "UPDATE schema_meta SET value = '3.0' WHERE key = 'bin_size'"
            )
            db.connection.commit()

            db.create_tables()  # should NOT overwrite bin_size
            assert db.get_bin_size() == 3.0, (
                "create_tables() must not overwrite existing bin_size"
            )

    def test_schema_version_correct(self, tmp_path: Path) -> None:
        """Schema version must be 7 (FRAGMENT_SCHEMA_VERSION)."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            assert db.get_schema_version() == 7


# ---------------------------------------------------------------------------
# SSCRecord Model
# ---------------------------------------------------------------------------


class TestSSCRecord:
    """Tests for the SSCRecord Pydantic model."""

    def test_ssc_record_from_json_string(self) -> None:
        """shift_list as a JSON string must be parsed to list[float]."""
        record = _make_ssc("C", [0.0])  # build base record
        record_with_json = SSCRecord(
            smiles="CC=O",
            atom_count=3,
            shift_list="[30.5, 199.1]",  # JSON string input
            avg_shift=114.8,
            min_shift=30.5,
            max_shift=199.1,
        )
        assert record_with_json.shift_list == [30.5, 199.1]
        assert isinstance(record_with_json.shift_list, list)

    def test_ssc_record_from_list(self) -> None:
        """shift_list as a Python list must pass through unchanged."""
        record = SSCRecord(
            smiles="CC=O",
            atom_count=3,
            shift_list=[30.5, 199.1],
            avg_shift=114.8,
            min_shift=30.5,
            max_shift=199.1,
        )
        assert record.shift_list == [30.5, 199.1]

    def test_ssc_record_shift_list_as_json(self) -> None:
        """shift_list_as_json() must return valid JSON matching the list."""
        record = SSCRecord(
            smiles="CC=O",
            atom_count=3,
            shift_list=[30.5, 199.1],
            avg_shift=114.8,
            min_shift=30.5,
            max_shift=199.1,
        )
        result = record.shift_list_as_json()
        assert result == "[30.5, 199.1]"
        # Must be valid JSON
        parsed = json.loads(result)
        assert parsed == [30.5, 199.1]

    def test_ssc_record_model_dump_json(self) -> None:
        """model_dump_json() must include all fields."""
        record = _make_ssc("CCO", [18.1, 57.5, 0.0])
        json_str = record.model_dump_json()
        data = json.loads(json_str)
        assert "smiles" in data
        assert "shift_list" in data
        assert "avg_shift" in data
        assert data["bitset"] is None

    def test_ssc_record_bitset_optional(self) -> None:
        """bitset must default to None."""
        record = _make_ssc("CC", [10.0, 20.0])
        assert record.bitset is None


# ---------------------------------------------------------------------------
# SSCMatch Model
# ---------------------------------------------------------------------------


class TestSSCMatch:
    """Tests for the SSCMatch Pydantic model."""

    def test_ssc_match_serialization(self) -> None:
        """SSCMatch must serialize to JSON with all required fields."""
        match = SSCMatch(
            ssc_id=42,
            smiles="CC=O",
            atom_count=3,
            avg_deviation=1.5,
            matched_shifts=[30.0, 195.0],
            fragment_shifts=[30.5, 199.1],
            rank=1,
        )
        json_str = match.model_dump_json()
        data = json.loads(json_str)
        assert data["ssc_id"] == 42
        assert data["smiles"] == "CC=O"
        assert data["atom_count"] == 3
        assert data["avg_deviation"] == 1.5
        assert data["matched_shifts"] == [30.0, 195.0]
        assert data["fragment_shifts"] == [30.5, 199.1]
        assert data["rank"] == 1

    def test_ssc_match_rank_defaults_to_zero(self) -> None:
        """rank must default to 0 if not provided."""
        match = SSCMatch(
            ssc_id=1,
            smiles="C",
            atom_count=1,
            avg_deviation=0.0,
            matched_shifts=[],
            fragment_shifts=[],
        )
        assert match.rank == 0


# ---------------------------------------------------------------------------
# Batch Insert
# ---------------------------------------------------------------------------


class TestInsertBatch:
    """Tests for FragmentDatabaseManager.insert_ssc_batch()."""

    def test_insert_and_count(self, tmp_path: Path) -> None:
        """Inserting 3 unique SSC records must give get_ssc_count() == 3."""
        db_path = tmp_path / "frag.db"
        records = [
            _make_ssc("CC=O", [30.5, 199.1]),
            _make_ssc("CCO", [18.1, 57.5]),
            _make_ssc("c1ccccc1", [128.0, 128.0, 128.0]),
        ]
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            inserted, skipped = db.insert_ssc_batch(records)
            assert inserted == 3
            assert skipped == 0
            assert db.get_ssc_count() == 3

    def test_insert_deduplication(self, tmp_path: Path) -> None:
        """Inserting the same SMILES twice must return (0, 1) on second call."""
        db_path = tmp_path / "frag.db"
        record = _make_ssc("CC=O", [30.5, 199.1])
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            ins1, skip1 = db.insert_ssc_batch([record])
            assert ins1 == 1 and skip1 == 0

            ins2, skip2 = db.insert_ssc_batch([record])
            assert ins2 == 0 and skip2 == 1

            assert db.get_ssc_count() == 1

    def test_insert_batch_with_bitset(self, tmp_path: Path) -> None:
        """Inserting a record with a 32-byte bitset must store it in ssc_bitset."""
        db_path = tmp_path / "frag.db"
        bitset = bytes(range(32))  # deterministic 32-byte sequence
        record = _make_ssc("CC=O", [30.5, 199.1], bitset=bitset)
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            inserted, skipped = db.insert_ssc_batch([record])
            assert inserted == 1

            bitsets = list(db.iter_ssc_bitsets())
            assert len(bitsets) == 1
            ssc_id, stored_bitset = bitsets[0]
            assert len(stored_bitset) == 32
            assert stored_bitset == bitset


# ---------------------------------------------------------------------------
# Bitset Iteration
# ---------------------------------------------------------------------------


class TestIterSscBitsets:
    """Tests for FragmentDatabaseManager.iter_ssc_bitsets()."""

    def test_iter_ssc_bitsets_empty(self, tmp_path: Path) -> None:
        """Empty database must yield nothing from iter_ssc_bitsets()."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            bitsets = list(db.iter_ssc_bitsets())
            assert bitsets == []

    def test_iter_ssc_bitsets_yields_tuples(self, tmp_path: Path) -> None:
        """iter_ssc_bitsets() must yield (int, bytes) tuples."""
        db_path = tmp_path / "frag.db"
        bitset = b"\xff" * 32
        record = _make_ssc("CC=O", [30.5, 199.1], bitset=bitset)
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.insert_ssc_batch([record])
            items = list(db.iter_ssc_bitsets())
            assert len(items) == 1
            ssc_id, stored = items[0]
            assert isinstance(ssc_id, int)
            assert isinstance(stored, bytes)
            assert stored == bitset


# ---------------------------------------------------------------------------
# get_ssc_by_id
# ---------------------------------------------------------------------------


class TestGetSscById:
    """Tests for FragmentDatabaseManager.get_ssc_by_id()."""

    def test_get_ssc_by_id(self, tmp_path: Path) -> None:
        """get_ssc_by_id must return SSCRecord with correct fields."""
        db_path = tmp_path / "frag.db"
        r1 = _make_ssc("CC=O", [30.5, 199.1])
        r2 = _make_ssc("CCO", [18.1, 57.5])
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.insert_ssc_batch([r1, r2])
            all_ids = [row[0] for row in db.iter_ssc_bitsets()]
            # No bitsets — use direct count to get IDs instead
            db.connection.execute("SELECT id FROM ssc ORDER BY id")
            rows = db.connection.execute("SELECT id, smiles FROM ssc ORDER BY id").fetchall()
            ids = [row["id"] for row in rows]
            smiles_list = [row["smiles"] for row in rows]

            results = db.get_ssc_by_id(ids)
            assert len(results) == 2
            result_smiles = {r.smiles for r in results}
            assert result_smiles == {"CC=O", "CCO"}

            # Verify shift_list is parsed from JSON
            for result in results:
                assert isinstance(result.shift_list, list)
                assert all(isinstance(s, float) for s in result.shift_list)

    def test_get_ssc_by_id_empty(self, tmp_path: Path) -> None:
        """get_ssc_by_id([]) must return an empty list."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            results = db.get_ssc_by_id([])
            assert results == []

    def test_get_ssc_by_id_shift_list_parsed(self, tmp_path: Path) -> None:
        """shift_list in returned SSCRecord must be a Python list, not a JSON string."""
        db_path = tmp_path / "frag.db"
        record = _make_ssc("CC=O", [30.5, 199.1])
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.insert_ssc_batch([record])
            rows = db.connection.execute("SELECT id FROM ssc").fetchall()
            ids = [row["id"] for row in rows]
            results = db.get_ssc_by_id(ids)
            assert results[0].shift_list == [30.5, 199.1]


# ---------------------------------------------------------------------------
# Schema Isolation
# ---------------------------------------------------------------------------


class TestSchemaIsolation:
    """Tests confirming the fragment module does not affect the existing database."""

    def test_schema_version_no_table(self, tmp_path: Path) -> None:
        """Opening a bare SQLite file must return None for get_schema_version()."""
        import sqlite3

        db_path = tmp_path / "bare.db"
        # Create an empty SQLite file (no tables at all)
        conn = sqlite3.connect(str(db_path))
        conn.close()

        with FragmentDatabaseManager(db_path) as db:
            assert db.get_schema_version() is None

    def test_existing_commands_unaffected(self) -> None:
        """Existing database module SCHEMA_VERSION must still be 6.

        This confirms that Phase 49 did not modify database/schema.py and
        that the compound/HOSE database is completely unaffected.
        """
        from ailsa.database.manager import DatabaseManager  # noqa: F401
        from ailsa.database.schema import SCHEMA_VERSION

        assert SCHEMA_VERSION == 6, (
            f"database/schema.py SCHEMA_VERSION must remain 6, got {SCHEMA_VERSION}"
        )


# ---------------------------------------------------------------------------
# Checkpoint Methods (Phase 50, Plan 01)
# ---------------------------------------------------------------------------


class TestCheckpointMethods:
    """Tests for FragmentDatabaseManager checkpoint get/set/clear methods."""

    def test_set_checkpoint_stores_value(self, tmp_path: Path) -> None:
        """set_checkpoint must persist value retrievable by get_checkpoint."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.set_checkpoint("checkpoint_last_id", "42")
            assert db.get_checkpoint("checkpoint_last_id") == "42"

    def test_get_checkpoint_missing_returns_none(self, tmp_path: Path) -> None:
        """get_checkpoint must return None for a key that was never set."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            assert db.get_checkpoint("checkpoint_nonexistent") is None

    def test_set_checkpoint_overwrites(self, tmp_path: Path) -> None:
        """Setting the same checkpoint key twice must keep the latest value."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.set_checkpoint("checkpoint_last_id", "100")
            db.set_checkpoint("checkpoint_last_id", "999")
            assert db.get_checkpoint("checkpoint_last_id") == "999"

    def test_clear_checkpoints_removes_checkpoint_keys(self, tmp_path: Path) -> None:
        """clear_checkpoints must remove all checkpoint_ keys."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.set_checkpoint("checkpoint_x", "aaa")
            db.set_checkpoint("checkpoint_y", "bbb")
            db.clear_checkpoints()
            assert db.get_checkpoint("checkpoint_x") is None
            assert db.get_checkpoint("checkpoint_y") is None

    def test_clear_checkpoints_preserves_schema_metadata(self, tmp_path: Path) -> None:
        """clear_checkpoints must NOT remove schema_version or bin_size rows."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.set_checkpoint("checkpoint_x", "some_value")
            db.clear_checkpoints()
            assert db.get_schema_version() == 7, (
                "schema_version must survive clear_checkpoints()"
            )
            assert db.get_bin_size() == 2.0, (
                "bin_size must survive clear_checkpoints()"
            )

    def test_clear_ssc_data_truncates_tables(self, tmp_path: Path) -> None:
        """clear_ssc_data must delete all rows from ssc (and ssc_bitset)."""
        db_path = tmp_path / "frag.db"
        bitset = bytes(range(32))
        records = [
            _make_ssc("CC=O", [30.5, 199.1], bitset=bitset),
            _make_ssc("CCO", [18.1, 57.5], bitset=bitset),
        ]
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.insert_ssc_batch(records)
            assert db.get_ssc_count() == 2

            db.clear_ssc_data()
            assert db.get_ssc_count() == 0

            # ssc_bitset must also be empty
            bitsets = list(db.iter_ssc_bitsets())
            assert bitsets == [], "ssc_bitset must be empty after clear_ssc_data()"

    def test_clear_ssc_data_also_clears_checkpoints(self, tmp_path: Path) -> None:
        """clear_ssc_data must clear both SSC rows and checkpoint keys."""
        db_path = tmp_path / "frag.db"
        bitset = bytes(range(32))
        record = _make_ssc("CC=O", [30.5, 199.1], bitset=bitset)
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()
            db.set_checkpoint("checkpoint_last_id", "42")
            db.insert_ssc_batch([record])
            assert db.get_ssc_count() == 1

            db.clear_ssc_data()
            assert db.get_ssc_count() == 0
            assert db.get_checkpoint("checkpoint_last_id") is None, (
                "Checkpoint must be cleared by clear_ssc_data()"
            )
