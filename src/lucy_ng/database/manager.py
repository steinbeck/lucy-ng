"""Database manager for compound storage and retrieval."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from lucy_ng.database.models import CompoundRecord, HOSEStatsRecord, ShiftRecord
from lucy_ng.database.schema import SCHEMA_STATEMENTS, SCHEMA_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterator


class DatabaseManager:
    """Manager for SQLite compound database.

    Provides methods for creating tables, inserting compounds,
    and querying by molecular formula.

    Usage:
        with DatabaseManager("compounds.db") as db:
            db.create_tables()
            db.insert_compound(compound, shifts)
            results = db.get_by_formula("C13H18O2")
    """

    def __init__(self, db_path: str | Path):
        """Initialize with path to SQLite database.

        Args:
            db_path: Path to SQLite database file. Created if doesn't exist.
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> DatabaseManager:
        """Context manager entry - open connection."""
        self._connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit - close connection."""
        self.close()

    def _connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # Allow multi-threaded access
            )
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    @property
    def connection(self) -> sqlite3.Connection:
        """Get database connection, connecting if needed."""
        return self._connect()

    def create_tables(self) -> None:
        """Create database tables if they don't exist.

        This is idempotent - safe to call multiple times.
        """
        conn = self.connection
        cursor = conn.cursor()

        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)

        # Set schema version
        cursor.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )

        conn.commit()

    def get_schema_version(self) -> int | None:
        """Get current schema version from database.

        Returns:
            Schema version number, or None if not set.
        """
        conn = self.connection
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT value FROM schema_meta WHERE key = ?", ("schema_version",))
            row = cursor.fetchone()
            if row:
                return int(row["value"])
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            pass

        return None

    def insert_compound(
        self,
        compound: CompoundRecord,
        shifts: list[ShiftRecord] | None = None,
    ) -> int:
        """Insert a compound and its shifts into the database.

        Args:
            compound: Compound record to insert
            shifts: Optional list of shift records. Uses compound.shifts if not provided.

        Returns:
            ID of the inserted compound
        """
        conn = self.connection
        cursor = conn.cursor()

        # Insert compound
        formula_norm = compound.formula_normalized or CompoundRecord._normalize_formula(
            compound.formula
        )
        cursor.execute(
            """
            INSERT INTO compounds
                (name, smiles, formula, formula_normalized, inchi, inchi_key,
                 carbon_count, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                compound.name,
                compound.smiles,
                compound.formula,
                formula_norm,
                compound.inchi,
                compound.inchi_key,
                compound.carbon_count,
                compound.source,
            ),
        )
        compound_id = cursor.lastrowid

        # Insert shifts
        shifts_to_insert = shifts if shifts is not None else compound.shifts
        for shift in shifts_to_insert:
            cursor.execute(
                """
                INSERT INTO shifts (compound_id, atom_index, shift_ppm, hydrogen_count)
                VALUES (?, ?, ?, ?)
                """,
                (compound_id, shift.atom_index, shift.shift_ppm, shift.hydrogen_count),
            )

        conn.commit()
        return compound_id  # type: ignore[return-value]

    def insert_compounds_batch(
        self,
        compounds: list[tuple[CompoundRecord, list[ShiftRecord]]],
        batch_size: int = 1000,
    ) -> int:
        """Batch insert compounds for performance.

        Args:
            compounds: List of (compound, shifts) tuples
            batch_size: Number of compounds to insert per transaction

        Returns:
            Number of compounds inserted
        """
        conn = self.connection
        cursor = conn.cursor()
        count = 0

        for i, (compound, shifts) in enumerate(compounds):
            # Insert compound
            formula_norm = compound.formula_normalized or CompoundRecord._normalize_formula(
                compound.formula
            )
            cursor.execute(
                """
                INSERT INTO compounds
                    (name, smiles, formula, formula_normalized, inchi, inchi_key,
                     carbon_count, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    compound.name,
                    compound.smiles,
                    compound.formula,
                    formula_norm,
                    compound.inchi,
                    compound.inchi_key,
                    compound.carbon_count,
                    compound.source,
                ),
            )
            compound_id = cursor.lastrowid

            # Insert shifts
            for shift in shifts:
                cursor.execute(
                    """
                    INSERT INTO shifts (compound_id, atom_index, shift_ppm, hydrogen_count)
                    VALUES (?, ?, ?, ?)
                    """,
                    (compound_id, shift.atom_index, shift.shift_ppm, shift.hydrogen_count),
                )

            count += 1

            # Commit every batch_size compounds
            if (i + 1) % batch_size == 0:
                conn.commit()

        # Final commit for remaining
        conn.commit()
        return count

    def get_by_formula(self, formula: str) -> list[CompoundRecord]:
        """Get all compounds matching a molecular formula.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            List of CompoundRecord with shifts populated
        """
        normalized = CompoundRecord._normalize_formula(formula)
        conn = self.connection
        cursor = conn.cursor()

        # Get compounds
        cursor.execute(
            """
            SELECT id, name, smiles, formula, formula_normalized, inchi, inchi_key,
                   carbon_count, source
            FROM compounds
            WHERE formula_normalized = ?
            """,
            (normalized,),
        )

        results: list[CompoundRecord] = []
        for row in cursor.fetchall():
            compound = CompoundRecord(
                id=row["id"],
                name=row["name"],
                smiles=row["smiles"],
                formula=row["formula"],
                formula_normalized=row["formula_normalized"],
                inchi=row["inchi"],
                inchi_key=row["inchi_key"],
                carbon_count=row["carbon_count"],
                source=row["source"],
            )

            # Get shifts for this compound
            cursor.execute(
                """
                SELECT id, compound_id, atom_index, shift_ppm, hydrogen_count
                FROM shifts
                WHERE compound_id = ?
                """,
                (compound.id,),
            )

            compound.shifts = [
                ShiftRecord(
                    id=shift_row["id"],
                    compound_id=shift_row["compound_id"],
                    atom_index=shift_row["atom_index"],
                    shift_ppm=shift_row["shift_ppm"],
                    hydrogen_count=shift_row["hydrogen_count"],
                )
                for shift_row in cursor.fetchall()
            ]

            results.append(compound)

        return results

    def get_compound_count(self) -> int:
        """Return total number of compounds in database."""
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM compounds")
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_formula_count(self) -> int:
        """Return count of unique molecular formulas."""
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT formula_normalized) FROM compounds")
        row = cursor.fetchone()
        return row[0] if row else 0

    def iter_all_formulas(self) -> Iterator[str]:
        """Iterate over all unique normalized formulas in the database.

        Yields:
            Normalized formula strings
        """
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT formula_normalized FROM compounds ORDER BY formula_normalized"
        )
        for row in cursor:
            yield row[0]

    def iter_compounds_with_shifts(
        self, batch_size: int = 1000
    ) -> Iterator[tuple[int, str, list[tuple[int | None, float]]]]:
        """Iterate over all compounds with their shifts for batch processing.

        Memory-efficient iterator that fetches compounds in batches.
        Only yields compounds that have both SMILES and at least one shift.

        Args:
            batch_size: Number of compounds to fetch per batch

        Yields:
            Tuples of (compound_id, smiles, [(atom_index, shift_ppm), ...])
            Only yields compounds with non-empty SMILES and at least one shift.
        """
        conn = self.connection
        cursor = conn.cursor()

        # Get compounds with SMILES in batches
        cursor.execute(
            """
            SELECT id, smiles FROM compounds
            WHERE smiles IS NOT NULL AND smiles != ''
            ORDER BY id
            """
        )

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            for row in rows:
                compound_id = row["id"]
                smiles = row["smiles"]

                # Get shifts for this compound
                shift_cursor = conn.cursor()
                shift_cursor.execute(
                    """
                    SELECT atom_index, shift_ppm FROM shifts
                    WHERE compound_id = ?
                    """,
                    (compound_id,),
                )
                shifts = [(r["atom_index"], r["shift_ppm"]) for r in shift_cursor.fetchall()]

                # Only yield if compound has shifts
                if shifts:
                    yield (compound_id, smiles, shifts)

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # =========================================================================
    # HOSE Statistics Methods
    # =========================================================================

    def insert_hose_stats_batch(
        self,
        stats: list[HOSEStatsRecord],
        batch_size: int = 10000,
    ) -> int:
        """Batch insert HOSE statistics for performance.

        Uses INSERT OR REPLACE to handle reruns gracefully - existing
        (hose_code, radius) entries will be updated.

        Args:
            stats: List of HOSEStatsRecord to insert
            batch_size: Number of records to insert per transaction

        Returns:
            Number of records inserted/updated
        """
        conn = self.connection
        cursor = conn.cursor()
        count = 0

        for i, stat in enumerate(stats):
            cursor.execute(
                """
                INSERT OR REPLACE INTO hose_stats
                    (hose_code, radius, mean, std, count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (stat.hose_code, stat.radius, stat.mean, stat.std, stat.count),
            )
            count += 1

            # Commit every batch_size records
            if (i + 1) % batch_size == 0:
                conn.commit()

        # Final commit for remaining
        conn.commit()
        return count

    def get_hose_stats(self, hose_code: str, radius: int) -> HOSEStatsRecord | None:
        """Get statistics for a specific HOSE code at a given radius.

        This is the primary query for shift prediction - O(1) lookup.

        Args:
            hose_code: HOSE code string
            radius: Sphere radius (1-6)

        Returns:
            HOSEStatsRecord if found, None otherwise
        """
        conn = self.connection
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT hose_code, radius, mean, std, count
            FROM hose_stats
            WHERE hose_code = ? AND radius = ?
            """,
            (hose_code, radius),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        return HOSEStatsRecord(
            hose_code=row["hose_code"],
            radius=row["radius"],
            mean=row["mean"],
            std=row["std"],
            count=row["count"],
        )

    def get_hose_stats_all_radii(self, hose_code: str) -> list[HOSEStatsRecord]:
        """Get statistics at all available radii for a HOSE code.

        Useful for fallback queries where higher radii are tried first,
        falling back to lower radii when no match is found.

        Args:
            hose_code: HOSE code string

        Returns:
            List of HOSEStatsRecord ordered by radius descending
        """
        conn = self.connection
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT hose_code, radius, mean, std, count
            FROM hose_stats
            WHERE hose_code = ?
            ORDER BY radius DESC
            """,
            (hose_code,),
        )

        return [
            HOSEStatsRecord(
                hose_code=row["hose_code"],
                radius=row["radius"],
                mean=row["mean"],
                std=row["std"],
                count=row["count"],
            )
            for row in cursor.fetchall()
        ]

    def get_hose_stats_count(self) -> int:
        """Return total number of HOSE statistics entries.

        Returns:
            Count of rows in hose_stats table
        """
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM hose_stats")
        row = cursor.fetchone()
        return row[0] if row else 0
