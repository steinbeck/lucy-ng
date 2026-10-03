"""Tests for database schema v5 to v6 migration."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from ailsa.database.manager import DatabaseManager
from ailsa.database.models import BondPairStatsRecord, HOSEStatsRecord
from ailsa.database.schema import (
    CREATE_COMPOUNDS_TABLE,
    CREATE_FORMULA_INDEX,
    CREATE_HOSE_STATS_INDEX,
    CREATE_HOSE_STATS_MEAN_RADIUS_INDEX,
    CREATE_HOSE_STATS_TABLE,
    CREATE_SCHEMA_META_TABLE,
    CREATE_SHIFTS_COMPOUND_INDEX,
    CREATE_SHIFTS_TABLE,
    migrate_v4_to_v5,
    migrate_v5_to_v6,
)


def create_v5_database(db_path: Path) -> None:
    """Create a v5 database with hose_stats data."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create v3 schema first
    for statement in [
        CREATE_COMPOUNDS_TABLE,
        CREATE_SHIFTS_TABLE,
        CREATE_FORMULA_INDEX,
        CREATE_SHIFTS_COMPOUND_INDEX,
        CREATE_SCHEMA_META_TABLE,
    ]:
        cursor.execute(statement)

    # Create v3 hose_stats table (without hybridisation/neighbour columns)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS hose_stats (
            hose_code TEXT NOT NULL,
            radius INTEGER NOT NULL,
            mean REAL NOT NULL,
            std REAL NOT NULL,
            count INTEGER NOT NULL,
            m2 REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (hose_code, radius)
        )
        """
    )
    cursor.execute(CREATE_HOSE_STATS_INDEX)

    # Set schema version to v3
    cursor.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", "3"),
    )
    conn.commit()

    # Migrate to v4 (adds hybridisation columns)
    from ailsa.database.schema import migrate_v3_to_v4

    migrate_v3_to_v4(conn)

    # Migrate to v5 (adds neighbour columns)
    migrate_v4_to_v5(conn)

    # Insert test data
    cursor.execute(
        """
        INSERT INTO hose_stats
            (hose_code, radius, mean, std, count, m2,
             sp3_count, sp2_count, sp1_count,
             has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
             has_sulfur_neighbor, has_halogen_neighbor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("C-4;C(//)", 1, 25.0, 5.0, 100, 250.0, 80, 15, 5, 100, 10, 5, 0, 0),
    )
    conn.commit()
    conn.close()


def test_migrate_v5_to_v6() -> None:
    """Test migration from v5 to v6 adds ring columns and bond_pair_stats table."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        # Create v5 database
        create_v5_database(db_path)

        # Migrate to v6
        with DatabaseManager(db_path) as db:
            assert db.get_schema_version() == 5
            db.migrate_to_v6()
            assert db.get_schema_version() == 6

            # Verify bond_pair_stats table exists
            cursor = db.connection.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bond_pair_stats'"
            )
            assert cursor.fetchone() is not None

            # Verify ring columns exist in hose_stats
            cursor.execute("PRAGMA table_info(hose_stats)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "in_3ring" in columns
            assert "in_4ring" in columns
            assert "in_aromatic" in columns

            # Verify existing data preserved with ring columns defaulted to 0
            stats = db.get_hose_stats("C-4;C(//)", 1)
            assert stats is not None
            assert stats.mean == 25.0
            assert stats.count == 100
            assert stats.in_3ring == 0  # DEFAULT 0
            assert stats.in_4ring == 0  # DEFAULT 0
            assert stats.in_aromatic == 0  # DEFAULT 0

    finally:
        db_path.unlink()


def test_insert_and_query_bond_pair_stats() -> None:
    """Test insertion and querying of bond pair statistics."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert bond pair statistics
            records = [
                BondPairStatsRecord(
                    formula_normalized="C10H14O2",
                    element1="N",
                    element2="O",
                    compound_count=5,
                    total_compounds=100,
                    frequency=0.05,
                ),
                BondPairStatsRecord(
                    formula_normalized="C10H14O2",
                    element1="O",
                    element2="O",
                    compound_count=1,
                    total_compounds=100,
                    frequency=0.01,
                ),
                BondPairStatsRecord(
                    formula_normalized="C10H14O2",
                    element1="N",
                    element2="S",
                    compound_count=15,
                    total_compounds=100,
                    frequency=0.15,
                ),
            ]
            db.insert_bond_pair_stats_batch(records)

            # Query by formula
            results = db.get_bond_pair_stats_by_formula("C10H14O2")
            assert len(results) == 3

            # Verify order (descending by frequency)
            assert results[0].element1 == "N"
            assert results[0].element2 == "S"
            assert results[0].frequency == 0.15

            assert results[1].element1 == "N"
            assert results[1].element2 == "O"
            assert results[1].frequency == 0.05

            assert results[2].element1 == "O"
            assert results[2].element2 == "O"
            assert results[2].frequency == 0.01

    finally:
        db_path.unlink()


def test_upsert_with_ring_columns() -> None:
    """Test upserting 16-element tuples with ring columns."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Upsert 16-element tuple (v6 format)
            stats = [
                (
                    "C-4;C(//)",
                    1,
                    100,
                    25.0,
                    250.0,
                    80,
                    15,
                    5,
                    100,
                    10,
                    5,
                    0,
                    0,
                    5,
                    2,
                    90,
                )
            ]
            db.upsert_hose_stats_incremental(stats)

            # Read back and verify
            record = db.get_hose_stats("C-4;C(//)", 1)
            assert record is not None
            assert record.count == 100
            assert record.mean == 25.0
            assert record.sp3_count == 80
            assert record.has_carbon_neighbor == 100
            assert record.in_3ring == 5
            assert record.in_4ring == 2
            assert record.in_aromatic == 90

    finally:
        db_path.unlink()


def test_backward_compat_v5_tuples() -> None:
    """Test that 13-element tuples (v5) still work, ring columns default to 0."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Upsert 13-element tuple (v5 format)
            stats = [("C-4;O(//)", 1, 50, 60.0, 125.0, 40, 5, 5, 50, 50, 10, 5, 0)]
            db.upsert_hose_stats_incremental(stats)

            # Read back and verify ring columns default to 0
            record = db.get_hose_stats("C-4;O(//)", 1)
            assert record is not None
            assert record.count == 50
            assert record.mean == 60.0
            assert record.has_oxygen_neighbor == 50
            assert record.in_3ring == 0  # DEFAULT
            assert record.in_4ring == 0  # DEFAULT
            assert record.in_aromatic == 0  # DEFAULT

    finally:
        db_path.unlink()


def test_bond_pair_stats_backward_compatibility() -> None:
    """Test that querying bond_pair_stats on v5 database returns empty list."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        # Create v5 database
        create_v5_database(db_path)

        with DatabaseManager(db_path) as db:
            assert db.get_schema_version() == 5

            # Query bond_pair_stats should return empty (table doesn't exist)
            results = db.get_bond_pair_stats_by_formula("C10H14O2")
            assert results == []

    finally:
        db_path.unlink()
