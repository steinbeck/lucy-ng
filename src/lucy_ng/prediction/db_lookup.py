"""Database-backed HOSE code lookup adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .models import HOSEStatsResult

if TYPE_CHECKING:
    from lucy_ng.database import DatabaseManager


class DatabaseHOSELookup:
    """HOSE code lookup adapter backed by SQLite database.

    Queries the hose_stats table for pre-computed statistics instead of
    computing them on-the-fly from raw shift lists. This provides O(1)
    lookup time and eliminates the need to load large JSON tables into memory.

    Implements HOSELookupProtocol for use with C13Predictor.
    """

    def __init__(self, db: DatabaseManager) -> None:
        """Initialize with database connection.

        Args:
            db: DatabaseManager instance (connection should already be open)
        """
        self._db = db

    @classmethod
    def from_db_path(cls, db_path: Path | str) -> DatabaseHOSELookup:
        """Create lookup adapter from database file path.

        Opens a connection to the database and returns the adapter.

        Args:
            db_path: Path to SQLite database file

        Returns:
            DatabaseHOSELookup instance with open connection
        """
        from lucy_ng.database import DatabaseManager

        db = DatabaseManager(db_path)
        db._connect()  # Ensure connection is open
        return cls(db)

    def lookup_stats_at_radius(
        self, hose_code: str, radius: int
    ) -> HOSEStatsResult | None:
        """Look up statistics for a HOSE code at a specific radius.

        Queries the hose_stats table for the given (hose_code, radius) pair.

        Args:
            hose_code: HOSE code string
            radius: Sphere radius (1-6)

        Returns:
            HOSEStatsResult with mean, std, count; or None if not found
        """
        record = self._db.get_hose_stats(hose_code, radius)
        if record is None:
            return None

        return HOSEStatsResult(
            mean=record.mean,
            std=record.std,
            count=record.count,
        )

    def has_code_at_radius(self, hose_code: str, radius: int) -> bool:
        """Check if a HOSE code exists at a specific radius.

        Args:
            hose_code: HOSE code string
            radius: Sphere radius (1-6)

        Returns:
            True if the code exists at this radius in the database
        """
        return self._db.get_hose_stats(hose_code, radius) is not None

    def get_stats_count(self) -> int:
        """Get total number of HOSE statistics entries in the database.

        Returns:
            Count of rows in hose_stats table
        """
        return self._db.get_hose_stats_count()

    def close(self) -> None:
        """Close the database connection."""
        self._db.close()

    def __repr__(self) -> str:
        """Return string representation."""
        try:
            count = self.get_stats_count()
            return f"DatabaseHOSELookup(stats={count:,}, db={self._db.db_path})"
        except Exception:
            return f"DatabaseHOSELookup(db={self._db.db_path})"
