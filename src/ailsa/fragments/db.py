"""Database manager for the fragment (SSC) database.

Manages ``lucy-ng-fragments.db`` — a separate SQLite file from the main
compound/HOSE database (``lucy-ng-derep.db``).  This module has ZERO
imports from ``ailsa.database`` to preserve full independence.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from ailsa.fragments.models import SSCRecord
from ailsa.fragments.schema import FRAGMENT_SCHEMA_STATEMENTS, FRAGMENT_SCHEMA_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterator


class FragmentDatabaseManager:
    """Manager for the SQLite fragment (SSC) database.

    Provides methods for creating tables, inserting SSC records, and querying
    by ID or iterating bitsets.  Fully independent of :class:`DatabaseManager`
    — no shared state, no shared file.

    Usage::

        with FragmentDatabaseManager("lucy-ng-fragments.db") as db:
            db.create_tables()
            inserted, skipped = db.insert_ssc_batch(records)
            count = db.get_ssc_count()
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialise with path to SQLite database.

        Args:
            db_path: Path to SQLite database file.  Created if it doesn't exist.
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> FragmentDatabaseManager:
        """Context manager entry — open connection."""
        self._connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit — close connection."""
        self.close()

    def _connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    @property
    def connection(self) -> sqlite3.Connection:
        """Get database connection, connecting if needed."""
        return self._connect()

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # =========================================================================
    # Schema Methods
    # =========================================================================

    def create_tables(self) -> None:
        """Create fragment tables if they don't exist.

        This method is idempotent — safe to call multiple times.  All CREATE
        statements use ``IF NOT EXISTS``.

        After creating tables, writes two rows to ``schema_meta``:

        - ``schema_version`` — always updated to :data:`FRAGMENT_SCHEMA_VERSION`
          (``INSERT OR REPLACE``).
        - ``bin_size`` — written only if not already present
          (``INSERT OR IGNORE``), protecting existing SSC data built with a
          different bin size.
        """
        conn = self.connection
        cursor = conn.cursor()

        for statement in FRAGMENT_SCHEMA_STATEMENTS:
            cursor.execute(statement)

        # Always update schema version so re-runs reflect the current code.
        cursor.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(FRAGMENT_SCHEMA_VERSION)),
        )

        # Protect bin_size: INSERT OR IGNORE so an existing populated database
        # keeps its bin_size even if create_tables() is called again.
        cursor.execute(
            "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, ?)",
            ("bin_size", "2.0"),
        )

        conn.commit()

    def get_schema_version(self) -> int | None:
        """Get current schema version from the database.

        Returns:
            Schema version number, or ``None`` if not set or table missing.
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                ("schema_version",),
            )
            row = cursor.fetchone()
            if row:
                return int(row["value"])
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            pass
        return None

    def get_bin_size(self) -> float | None:
        """Get the fingerprint bin size recorded in the database.

        Returns:
            Bin size in ppm (e.g. ``2.0``), or ``None`` if not set.
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                ("bin_size",),
            )
            row = cursor.fetchone()
            if row:
                return float(row["value"])
        except sqlite3.OperationalError:
            pass
        return None

    # =========================================================================
    # Checkpoint Methods
    # =========================================================================

    def set_checkpoint(self, key: str, value: str) -> None:
        """Store a checkpoint value in schema_meta.

        Uses INSERT OR REPLACE to upsert.  Checkpoint keys MUST use the
        ``checkpoint_`` prefix to distinguish them from schema metadata
        (``schema_version``, ``bin_size``).

        Args:
            key: Checkpoint key (e.g. ``"checkpoint_ssc_last_compound_id"``).
            value: Checkpoint value as string.
        """
        self.connection.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.connection.commit()

    def get_checkpoint(self, key: str) -> str | None:
        """Retrieve a checkpoint value from schema_meta.

        Args:
            key: Checkpoint key to look up.

        Returns:
            Checkpoint value as string, or ``None`` if not found.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT value FROM schema_meta WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        return row["value"] if row else None

    def clear_checkpoints(self) -> None:
        """Remove all checkpoint_ keys from schema_meta.

        Preserves non-checkpoint metadata (``schema_version``, ``bin_size``).
        Used internally by :meth:`clear_ssc_data` and directly when resuming
        a fresh extraction run without discarding SSC data.
        """
        self.connection.execute(
            "DELETE FROM schema_meta WHERE key LIKE 'checkpoint_%'"
        )
        self.connection.commit()

    def clear_ssc_data(self) -> None:
        """Delete all SSC data and checkpoint state.

        Truncates ``ssc_bitset`` first (foreign-key cascade would handle it,
        but explicit deletion is clearer), then ``ssc``, then clears all
        ``checkpoint_`` keys from ``schema_meta``.

        Used by the ``--fresh`` flag in the SSC extraction pipeline
        (Phase 50, Plan 02) to start a clean extraction run.
        """
        conn = self.connection
        conn.execute("DELETE FROM ssc_bitset")
        conn.execute("DELETE FROM ssc")
        conn.commit()
        self.clear_checkpoints()

    # =========================================================================
    # SSC Count
    # =========================================================================

    def get_ssc_count(self) -> int:
        """Return total number of SSC records in the database.

        Returns:
            Row count of the ``ssc`` table.  Returns 0 if the table is empty.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM ssc")
        row = cursor.fetchone()
        return row[0] if row else 0

    # =========================================================================
    # Batch Insert
    # =========================================================================

    def insert_ssc_batch(
        self,
        records: list[SSCRecord],
        batch_size: int = 10000,
    ) -> tuple[int, int]:
        """Batch insert SSC records with deduplication.

        Uses ``INSERT OR IGNORE`` semantics — records with a duplicate SMILES
        are silently skipped (UNIQUE constraint on ``ssc.smiles``).

        If a record has a non-``None`` ``bitset``, the bitset is inserted into
        the ``ssc_bitset`` table using the newly assigned ``ssc_id``.

        Args:
            records: SSC records to insert.
            batch_size: Number of records per commit transaction.

        Returns:
            ``(inserted, skipped)`` tuple where ``inserted`` is the number of
            new rows written and ``skipped`` is the number of duplicates.
        """
        conn = self.connection
        cursor = conn.cursor()
        inserted = 0
        skipped = 0

        for i, record in enumerate(records):
            cursor.execute(
                """
                INSERT OR IGNORE INTO ssc
                    (smiles, atom_count, shift_list, avg_shift, min_shift, max_shift)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.smiles,
                    record.atom_count,
                    record.shift_list_as_json(),
                    record.avg_shift,
                    record.min_shift,
                    record.max_shift,
                ),
            )

            if cursor.rowcount > 0:
                inserted += 1
                # Insert bitset if provided
                if record.bitset is not None:
                    ssc_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT OR IGNORE INTO ssc_bitset (ssc_id, bitset) VALUES (?, ?)",
                        (ssc_id, record.bitset),
                    )
            else:
                skipped += 1

            if (i + 1) % batch_size == 0:
                conn.commit()

        conn.commit()
        return (inserted, skipped)

    # =========================================================================
    # Bitset Iteration
    # =========================================================================

    def iter_ssc_bitsets(
        self, batch_size: int = 100_000
    ) -> Iterator[tuple[int, bytes]]:
        """Iterate over all ``(ssc_id, bitset)`` pairs for pre-screening.

        Memory-efficient: fetches rows in batches of ``batch_size``.
        Phase 51 uses this iterator for Boolean-AND pre-screening during
        fragment search.

        Args:
            batch_size: Number of rows to fetch per database round-trip.

        Yields:
            ``(ssc_id, bitset_bytes)`` tuples in ascending ``ssc_id`` order.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT ssc_id, bitset FROM ssc_bitset ORDER BY ssc_id")

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                yield (row["ssc_id"], bytes(row["bitset"]))

    # =========================================================================
    # ID-Based Lookup
    # =========================================================================

    def get_ssc_by_id(self, ssc_ids: list[int]) -> list[SSCRecord]:
        """Fetch SSC records by their database IDs.

        Used by Phase 51 after pre-screening identifies candidate ``ssc_id``s
        for fine-matching against the experimental spectrum.

        The ``shift_list`` JSON string is parsed automatically by the
        ``SSCRecord.parse_shift_list`` validator.

        Args:
            ssc_ids: List of ``ssc.id`` values to fetch.

        Returns:
            List of :class:`SSCRecord` in arbitrary order.
            Returns an empty list if ``ssc_ids`` is empty.
        """
        if not ssc_ids:
            return []

        cursor = self.connection.cursor()
        placeholders = ",".join("?" * len(ssc_ids))
        cursor.execute(
            f"SELECT id, smiles, atom_count, shift_list, avg_shift, min_shift, max_shift"
            f" FROM ssc WHERE id IN ({placeholders})",
            ssc_ids,
        )

        return [
            SSCRecord(
                id=row["id"],
                smiles=row["smiles"],
                atom_count=row["atom_count"],
                shift_list=row["shift_list"],  # field_validator parses JSON string
                avg_shift=row["avg_shift"],
                min_shift=row["min_shift"],
                max_shift=row["max_shift"],
            )
            for row in cursor.fetchall()
        ]
