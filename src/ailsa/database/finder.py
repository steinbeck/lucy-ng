"""Shared utilities for finding database and lookup table files."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class DatabaseFinder:
    """Utilities for auto-detecting database and lookup table files.

    This class consolidates database finding logic that was previously
    duplicated across CLI modules.
    """

    # Default database locations (preferred over JSON table)
    DEFAULT_DB_PATH = Path("data/reference/lucy-ng-derep.db")
    HOME_DB_PATH = Path.home() / ".lucy" / "lucy-ng-derep.db"

    # Default lookup table locations
    DEFAULT_TABLE_PATH = Path("data/reference/hose_lookup.json.gz")
    HOME_TABLE_PATH = Path.home() / ".lucy" / "hose_lookup.json.gz"

    @staticmethod
    def find_derep_database() -> Path | None:
        """Find SQLite database in default locations.

        Search order:
        1. LUCY_DATABASE environment variable
        2. data/reference/lucy-ng-derep.db (project location)
        3. Common locations (~/.lucy/, ~/ailsa/, etc.)
        4. macOS Spotlight search (mdfind)
        5. Recursive search in home directory (last resort)

        Returns:
            Path to database file if found, None otherwise
        """
        db_name = "lucy-ng-derep.db"

        # 1. Check environment variable first
        env_db = os.environ.get("LUCY_DATABASE")
        if env_db:
            env_path = Path(env_db)
            if env_path.exists() and env_path.suffix == ".db":
                return env_path

        # 2. Check project location
        default_db = Path("data/reference") / db_name
        if default_db.exists():
            return default_db

        # 3. Check common locations
        common_paths = [
            Path.home() / ".lucy" / db_name,
            Path.home() / "lucy-ng" / "data" / "reference" / db_name,
            Path.home() / ".local" / "share" / "lucy-ng" / db_name,
        ]
        for p in common_paths:
            if p.exists():
                return p

        # 4. macOS Spotlight search (fast)
        try:
            result = subprocess.run(
                ["mdfind", "-name", db_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                found_path = Path(result.stdout.strip().split("\n")[0])
                if found_path.exists():
                    return found_path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # mdfind not available or timed out

        # 5. Search in Dropbox/develop (common dev location)
        dropbox_dev = Path.home() / "Dropbox" / "develop" / "lucy-ng" / "data" / "reference" / db_name
        if dropbox_dev.exists():
            return dropbox_dev

        return None

    @staticmethod
    def is_sqlite_database(path: str | Path) -> bool:
        """Check if path refers to a SQLite database file.

        Args:
            path: Path to check

        Returns:
            True if path has .db extension
        """
        return Path(path).suffix == ".db"

    @staticmethod
    def find_hose_database() -> Path | None:
        """Find database with HOSE stats in default locations.

        This searches for the same database as find_derep_database(),
        since the lucy-ng-derep.db contains both compound data and HOSE stats.

        Returns:
            Path to database file if found, None otherwise
        """
        # The HOSE database is the same as the dereplication database
        # Try the comprehensive search from find_derep_database first
        db_path = DatabaseFinder.find_derep_database()
        if db_path:
            return db_path

        # Also check current directory for convenience
        cwd_db = Path("lucy-ng-derep.db")
        if cwd_db.exists():
            return cwd_db

        return None

    @staticmethod
    def find_hose_table() -> Path | None:
        """Find HOSE lookup table in default locations.

        Returns:
            Path to lookup table file if found, None otherwise
        """
        candidates = [
            DatabaseFinder.DEFAULT_TABLE_PATH,
            DatabaseFinder.HOME_TABLE_PATH,
            Path("hose_lookup.json.gz"),
            Path("hose_lookup.json"),
        ]
        for p in candidates:
            if p.exists():
                return p
        return None
