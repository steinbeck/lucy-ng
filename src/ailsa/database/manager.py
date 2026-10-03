"""Database manager for compound storage and retrieval."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from ailsa.database.models import (
    BondPairStatsRecord,
    CompoundRecord,
    HOSEStatsRecord,
    ShiftRecord,
)
from ailsa.database.schema import (
    SCHEMA_STATEMENTS,
    SCHEMA_VERSION,
    migrate_v3_to_v4,
    migrate_v4_to_v5,
    migrate_v5_to_v6,
)

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

    def migrate_to_v4(self) -> bool:
        """Migrate database to schema version 4.

        Adds hybridisation count columns and shift-window detection index.

        Returns:
            True if migration was performed, False if already at v4+
        """
        current_version = self.get_schema_version()
        if current_version is None or current_version < 4:
            migrate_v3_to_v4(self.connection)
            return True
        return False

    def migrate_to_v5(self) -> bool:
        """Migrate database to schema version 5.

        Adds neighbour element count columns for neighbourhood detection.

        Returns:
            True if migration was performed, False if already at v5+
        """
        current_version = self.get_schema_version()
        if current_version is None or current_version < 5:
            # Ensure at v4 first
            if current_version is None or current_version < 4:
                self.migrate_to_v4()
            migrate_v4_to_v5(self.connection)
            return True
        return False

    def migrate_to_v6(self) -> bool:
        """Migrate database to schema version 6.

        Adds bond_pair_stats table and ring membership columns.

        Returns:
            True if migration was performed, False if already at v6+
        """
        current_version = self.get_schema_version()
        if current_version is None or current_version < 6:
            # Ensure at v5 first
            if current_version is None or current_version < 5:
                self.migrate_to_v5()
            migrate_v5_to_v6(self.connection)
            return True
        return False

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
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO hose_stats
                        (hose_code, radius, mean, std, count,
                         sp3_count, sp2_count, sp1_count,
                         has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                         has_sulfur_neighbor, has_halogen_neighbor,
                         in_3ring, in_4ring, in_aromatic)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stat.hose_code,
                        stat.radius,
                        stat.mean,
                        stat.std,
                        stat.count,
                        stat.sp3_count,
                        stat.sp2_count,
                        stat.sp1_count,
                        stat.has_carbon_neighbor,
                        stat.has_oxygen_neighbor,
                        stat.has_nitrogen_neighbor,
                        stat.has_sulfur_neighbor,
                        stat.has_halogen_neighbor,
                        stat.in_3ring,
                        stat.in_4ring,
                        stat.in_aromatic,
                    ),
                )
            except sqlite3.OperationalError:
                # Backward compatibility: v3 database without hybridisation columns
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

        try:
            cursor.execute(
                """
                SELECT hose_code, radius, mean, std, count,
                       sp3_count, sp2_count, sp1_count,
                       has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                       has_sulfur_neighbor, has_halogen_neighbor,
                       in_3ring, in_4ring, in_aromatic
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
                sp3_count=row["sp3_count"],
                sp2_count=row["sp2_count"],
                sp1_count=row["sp1_count"],
                has_carbon_neighbor=row["has_carbon_neighbor"],
                has_oxygen_neighbor=row["has_oxygen_neighbor"],
                has_nitrogen_neighbor=row["has_nitrogen_neighbor"],
                has_sulfur_neighbor=row["has_sulfur_neighbor"],
                has_halogen_neighbor=row["has_halogen_neighbor"],
                in_3ring=row["in_3ring"],
                in_4ring=row["in_4ring"],
                in_aromatic=row["in_aromatic"],
            )
        except sqlite3.OperationalError:
            # Backward compatibility: v3 database without hybridisation columns
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

        try:
            cursor.execute(
                """
                SELECT hose_code, radius, mean, std, count,
                       sp3_count, sp2_count, sp1_count,
                       has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                       has_sulfur_neighbor, has_halogen_neighbor,
                       in_3ring, in_4ring, in_aromatic
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
                    sp3_count=row["sp3_count"],
                    sp2_count=row["sp2_count"],
                    sp1_count=row["sp1_count"],
                    has_carbon_neighbor=row["has_carbon_neighbor"],
                    has_oxygen_neighbor=row["has_oxygen_neighbor"],
                    has_nitrogen_neighbor=row["has_nitrogen_neighbor"],
                    has_sulfur_neighbor=row["has_sulfur_neighbor"],
                    has_halogen_neighbor=row["has_halogen_neighbor"],
                    in_3ring=row["in_3ring"],
                    in_4ring=row["in_4ring"],
                    in_aromatic=row["in_aromatic"],
                )
                for row in cursor.fetchall()
            ]
        except sqlite3.OperationalError:
            # Backward compatibility: v3 database without hybridisation columns
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

    def get_hose_stats_by_shift_window(
        self,
        shift_ppm: float,
        radius: int,
        window_ppm: float = 2.0,
        min_count: int = 5,
    ) -> list[HOSEStatsRecord]:
        """Query HOSE statistics within a shift window for detection.

        Finds all HOSE codes at a given radius whose mean shift falls within
        [shift_ppm - window_ppm, shift_ppm + window_ppm].

        Used for statistical detection queries (e.g., "what hybridisation
        states are typical for carbons at 130 ppm?").

        Args:
            shift_ppm: Target chemical shift in ppm
            radius: HOSE code radius (1-6)
            window_ppm: Window size in ppm (default: 2.0)
            min_count: Minimum observation count (default: 5)

        Returns:
            List of HOSEStatsRecord matching the criteria
        """
        conn = self.connection
        cursor = conn.cursor()

        min_shift = shift_ppm - window_ppm
        max_shift = shift_ppm + window_ppm

        try:
            cursor.execute(
                """
                SELECT hose_code, radius, mean, std, count,
                       sp3_count, sp2_count, sp1_count,
                       has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                       has_sulfur_neighbor, has_halogen_neighbor,
                       in_3ring, in_4ring, in_aromatic
                FROM hose_stats
                WHERE radius = ?
                  AND mean BETWEEN ? AND ?
                  AND count >= ?
                """,
                (radius, min_shift, max_shift, min_count),
            )

            return [
                HOSEStatsRecord(
                    hose_code=row["hose_code"],
                    radius=row["radius"],
                    mean=row["mean"],
                    std=row["std"],
                    count=row["count"],
                    sp3_count=row["sp3_count"],
                    sp2_count=row["sp2_count"],
                    sp1_count=row["sp1_count"],
                    has_carbon_neighbor=row["has_carbon_neighbor"],
                    has_oxygen_neighbor=row["has_oxygen_neighbor"],
                    has_nitrogen_neighbor=row["has_nitrogen_neighbor"],
                    has_sulfur_neighbor=row["has_sulfur_neighbor"],
                    has_halogen_neighbor=row["has_halogen_neighbor"],
                    in_3ring=row["in_3ring"],
                    in_4ring=row["in_4ring"],
                    in_aromatic=row["in_aromatic"],
                )
                for row in cursor.fetchall()
            ]
        except sqlite3.OperationalError:
            # Backward compatibility: v3 database without hybridisation columns
            cursor.execute(
                """
                SELECT hose_code, radius, mean, std, count
                FROM hose_stats
                WHERE radius = ?
                  AND mean BETWEEN ? AND ?
                  AND count >= ?
                """,
                (radius, min_shift, max_shift, min_count),
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

    def clear_hose_stats(self) -> int:
        """Clear all HOSE statistics from the database.

        Returns:
            Number of rows deleted
        """
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM hose_stats")
        row = cursor.fetchone()
        count: int = row[0] if row else 0
        cursor.execute("DELETE FROM hose_stats")
        conn.commit()
        return count

    def upsert_hose_stats_incremental(
        self,
        stats: list[
            tuple[str, int, int, float, float]
            | tuple[str, int, int, float, float, int, int, int]
            | tuple[str, int, int, float, float, int, int, int, int, int, int, int, int]
            | tuple[str, int, int, float, float, int, int, int, int, int, int, int, int, int, int, int]
        ],
    ) -> int:
        """Incrementally upsert HOSE statistics using Welford's parallel merge algorithm.

        For each (hose_code, radius), if it exists in the database, merge the
        new observations using Welford's parallel algorithm. Otherwise insert.

        This enables chunked processing where each chunk's statistics are
        merged into the database incrementally.

        Args:
            stats: List of tuples, either:
                - (hose_code, radius, count, mean, m2) - backward compatible (v3)
                - (hose_code, radius, count, mean, m2, sp3_count, sp2_count, sp1_count) - v4
                - (hose_code, radius, count, mean, m2, sp3_count, sp2_count, sp1_count,
                   has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                   has_sulfur_neighbor, has_halogen_neighbor) - v5
                - (hose_code, radius, count, mean, m2, sp3_count, sp2_count, sp1_count,
                   has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                   has_sulfur_neighbor, has_halogen_neighbor,
                   in_3ring, in_4ring, in_aromatic) - v6

        Returns:
            Number of records upserted
        """
        import math

        conn = self.connection
        cursor = conn.cursor()
        count = 0

        for stat_tuple in stats:
            # Parse tuple (backward compatible)
            if len(stat_tuple) == 5:
                hose_code, radius, new_count, new_mean, new_m2 = stat_tuple
                new_sp3, new_sp2, new_sp1 = 0, 0, 0
                new_has_c, new_has_o, new_has_n, new_has_s, new_has_hal = 0, 0, 0, 0, 0
                new_in_3ring, new_in_4ring, new_in_aromatic = 0, 0, 0
            elif len(stat_tuple) == 8:
                (
                    hose_code,
                    radius,
                    new_count,
                    new_mean,
                    new_m2,
                    new_sp3,
                    new_sp2,
                    new_sp1,
                ) = stat_tuple
                new_has_c, new_has_o, new_has_n, new_has_s, new_has_hal = 0, 0, 0, 0, 0
                new_in_3ring, new_in_4ring, new_in_aromatic = 0, 0, 0
            elif len(stat_tuple) == 13:
                (
                    hose_code,
                    radius,
                    new_count,
                    new_mean,
                    new_m2,
                    new_sp3,
                    new_sp2,
                    new_sp1,
                    new_has_c,
                    new_has_o,
                    new_has_n,
                    new_has_s,
                    new_has_hal,
                ) = stat_tuple
                new_in_3ring, new_in_4ring, new_in_aromatic = 0, 0, 0
            elif len(stat_tuple) == 16:
                (
                    hose_code,
                    radius,
                    new_count,
                    new_mean,
                    new_m2,
                    new_sp3,
                    new_sp2,
                    new_sp1,
                    new_has_c,
                    new_has_o,
                    new_has_n,
                    new_has_s,
                    new_has_hal,
                    new_in_3ring,
                    new_in_4ring,
                    new_in_aromatic,
                ) = stat_tuple
            else:
                raise ValueError(f"Invalid stats tuple length: {len(stat_tuple)}")

            # Check if entry exists
            try:
                cursor.execute(
                    """
                    SELECT count, mean, m2, sp3_count, sp2_count, sp1_count,
                           has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                           has_sulfur_neighbor, has_halogen_neighbor,
                           in_3ring, in_4ring, in_aromatic
                    FROM hose_stats
                    WHERE hose_code = ? AND radius = ?
                    """,
                    (hose_code, radius),
                )
            except sqlite3.OperationalError:
                # Backward compatibility: v3 database without hybridisation columns
                cursor.execute(
                    """
                    SELECT count, mean, m2 FROM hose_stats
                    WHERE hose_code = ? AND radius = ?
                    """,
                    (hose_code, radius),
                )

            row = cursor.fetchone()

            if row is None:
                # New entry - compute std from m2
                std = math.sqrt(new_m2 / new_count) if new_count > 1 else 0.0
                try:
                    cursor.execute(
                        """
                        INSERT INTO hose_stats (hose_code, radius, mean, std, count, m2,
                                                sp3_count, sp2_count, sp1_count,
                                                has_carbon_neighbor, has_oxygen_neighbor,
                                                has_nitrogen_neighbor, has_sulfur_neighbor,
                                                has_halogen_neighbor,
                                                in_3ring, in_4ring, in_aromatic)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            hose_code,
                            radius,
                            new_mean,
                            std,
                            new_count,
                            new_m2,
                            new_sp3,
                            new_sp2,
                            new_sp1,
                            new_has_c,
                            new_has_o,
                            new_has_n,
                            new_has_s,
                            new_has_hal,
                            new_in_3ring,
                            new_in_4ring,
                            new_in_aromatic,
                        ),
                    )
                except sqlite3.OperationalError:
                    # Backward compatibility: v3 database
                    cursor.execute(
                        """
                        INSERT INTO hose_stats (hose_code, radius, mean, std, count, m2)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (hose_code, radius, new_mean, std, new_count, new_m2),
                    )
            else:
                # Merge using Welford's parallel algorithm
                old_count, old_mean, old_m2 = row["count"], row["mean"], row["m2"]
                combined_count = old_count + new_count

                # Delta between means
                delta = new_mean - old_mean

                # Combined mean
                combined_mean = old_mean + delta * (new_count / combined_count)

                # Combined M2
                combined_m2 = (
                    old_m2
                    + new_m2
                    + delta * delta * (old_count * new_count / combined_count)
                )

                # Compute std from combined M2
                std = (
                    math.sqrt(combined_m2 / combined_count) if combined_count > 1 else 0.0
                )

                # Merge hybridisation, neighbour, and ring counts (simple addition)
                try:
                    old_sp3 = row["sp3_count"]
                    old_sp2 = row["sp2_count"]
                    old_sp1 = row["sp1_count"]
                    old_has_c = row["has_carbon_neighbor"]
                    old_has_o = row["has_oxygen_neighbor"]
                    old_has_n = row["has_nitrogen_neighbor"]
                    old_has_s = row["has_sulfur_neighbor"]
                    old_has_hal = row["has_halogen_neighbor"]
                    old_in_3ring = row["in_3ring"]
                    old_in_4ring = row["in_4ring"]
                    old_in_aromatic = row["in_aromatic"]

                    combined_sp3 = old_sp3 + new_sp3
                    combined_sp2 = old_sp2 + new_sp2
                    combined_sp1 = old_sp1 + new_sp1
                    combined_has_c = old_has_c + new_has_c
                    combined_has_o = old_has_o + new_has_o
                    combined_has_n = old_has_n + new_has_n
                    combined_has_s = old_has_s + new_has_s
                    combined_has_hal = old_has_hal + new_has_hal
                    combined_in_3ring = old_in_3ring + new_in_3ring
                    combined_in_4ring = old_in_4ring + new_in_4ring
                    combined_in_aromatic = old_in_aromatic + new_in_aromatic

                    cursor.execute(
                        """
                        UPDATE hose_stats
                        SET mean = ?, std = ?, count = ?, m2 = ?,
                            sp3_count = ?, sp2_count = ?, sp1_count = ?,
                            has_carbon_neighbor = ?, has_oxygen_neighbor = ?,
                            has_nitrogen_neighbor = ?, has_sulfur_neighbor = ?,
                            has_halogen_neighbor = ?,
                            in_3ring = ?, in_4ring = ?, in_aromatic = ?
                        WHERE hose_code = ? AND radius = ?
                        """,
                        (
                            combined_mean,
                            std,
                            combined_count,
                            combined_m2,
                            combined_sp3,
                            combined_sp2,
                            combined_sp1,
                            combined_has_c,
                            combined_has_o,
                            combined_has_n,
                            combined_has_s,
                            combined_has_hal,
                            combined_in_3ring,
                            combined_in_4ring,
                            combined_in_aromatic,
                            hose_code,
                            radius,
                        ),
                    )
                except (sqlite3.OperationalError, KeyError):
                    # Backward compatibility: v3 database without hybridisation columns
                    cursor.execute(
                        """
                        UPDATE hose_stats
                        SET mean = ?, std = ?, count = ?, m2 = ?
                        WHERE hose_code = ? AND radius = ?
                        """,
                        (combined_mean, std, combined_count, combined_m2, hose_code, radius),
                    )

            count += 1

        conn.commit()
        return count

    # =========================================================================
    # Checkpoint Methods
    # =========================================================================

    def set_checkpoint(self, key: str, value: str) -> None:
        """Save a checkpoint value.

        Args:
            key: Checkpoint key (e.g., "hose_stats_last_compound_id")
            value: Checkpoint value (serialized as string)
        """
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO operation_checkpoint (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            """,
            (key, value),
        )
        conn.commit()

    def get_checkpoint(self, key: str) -> str | None:
        """Get a checkpoint value.

        Args:
            key: Checkpoint key

        Returns:
            Checkpoint value if exists, None otherwise
        """
        conn = self.connection
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT value FROM operation_checkpoint WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            return row["value"] if row else None
        except Exception:
            return None

    def clear_checkpoint(self, key: str) -> bool:
        """Delete a checkpoint.

        Args:
            key: Checkpoint key

        Returns:
            True if checkpoint was deleted, False if not found
        """
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM operation_checkpoint WHERE key = ?",
            (key,),
        )
        conn.commit()
        return cursor.rowcount > 0

    # =========================================================================
    # Extended Iteration Methods
    # =========================================================================

    def iter_compounds_with_shifts_from(
        self,
        start_id: int = 0,
        batch_size: int = 1000,
    ) -> Iterator[tuple[int, str, list[tuple[int | None, float]]]]:
        """Iterate over compounds starting from a specific ID.

        Like iter_compounds_with_shifts but allows resuming from a checkpoint.

        Args:
            start_id: Start from this compound ID (exclusive, i.e., id > start_id)
            batch_size: Number of compounds to fetch per batch

        Yields:
            Tuples of (compound_id, smiles, [(atom_index, shift_ppm), ...])
        """
        conn = self.connection
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, smiles FROM compounds
            WHERE smiles IS NOT NULL AND smiles != ''
              AND id > ?
            ORDER BY id
            """,
            (start_id,),
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

    def get_max_compound_id(self) -> int:
        """Get the maximum compound ID in the database.

        Returns:
            Maximum compound ID, or 0 if no compounds exist
        """
        conn = self.connection
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM compounds")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

    # =========================================================================
    # Bond Pair Statistics Methods (v6+)
    # =========================================================================

    def insert_bond_pair_stats_batch(
        self,
        records: list[BondPairStatsRecord],
        batch_size: int = 10000,
    ) -> int:
        """Batch insert bond pair statistics.

        Uses INSERT OR REPLACE for idempotent reruns.

        Args:
            records: List of BondPairStatsRecord to insert
            batch_size: Records per transaction commit

        Returns:
            Number of records inserted/updated
        """
        conn = self.connection
        cursor = conn.cursor()
        count = 0

        for i, record in enumerate(records):
            cursor.execute(
                """
                INSERT OR REPLACE INTO bond_pair_stats
                    (formula_normalized, element1, element2, compound_count,
                     total_compounds, frequency)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.formula_normalized,
                    record.element1,
                    record.element2,
                    record.compound_count,
                    record.total_compounds,
                    record.frequency,
                ),
            )
            count += 1

            # Commit every batch_size records
            if (i + 1) % batch_size == 0:
                conn.commit()

        # Final commit for remaining
        conn.commit()
        return count

    def get_bond_pair_stats_by_formula(
        self, formula: str
    ) -> list[BondPairStatsRecord]:
        """Get bond pair statistics for a molecular formula.

        Args:
            formula: Molecular formula (normalized automatically)

        Returns:
            List of BondPairStatsRecord ordered by frequency descending
        """
        # Normalize formula
        normalized = CompoundRecord._normalize_formula(formula)

        conn = self.connection
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT formula_normalized, element1, element2, compound_count,
                       total_compounds, frequency
                FROM bond_pair_stats
                WHERE formula_normalized = ?
                ORDER BY frequency DESC
                """,
                (normalized,),
            )

            return [
                BondPairStatsRecord(
                    formula_normalized=row["formula_normalized"],
                    element1=row["element1"],
                    element2=row["element2"],
                    compound_count=row["compound_count"],
                    total_compounds=row["total_compounds"],
                    frequency=row["frequency"],
                )
                for row in cursor.fetchall()
            ]
        except sqlite3.OperationalError:
            # Backward compatibility: v5 database without bond_pair_stats table
            return []

