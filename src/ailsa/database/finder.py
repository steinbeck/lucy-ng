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

    # PKG-05: the project/package was renamed lucy-ng -> ailsa, but an
    # existing install's ~3.97 GB data/reference/lucy-ng-derep.db must keep
    # resolving forever (never renamed, moved or re-downloaded). The new
    # filename always wins when both exist.
    NEW_DB_NAME = "ailsa-derep.db"
    LEGACY_DB_NAME = "lucy-ng-derep.db"
    DB_NAMES = (NEW_DB_NAME, LEGACY_DB_NAME)

    # The checkout directory name used by tiers 3 and 5 below. "lucy-ng" is
    # the pre-rename directory name and stays valid search input until the
    # repository itself is renamed/moved (Phase 107).
    PROJECT_DIR_NAMES = ("ailsa", "lucy-ng")

    # Default database locations (preferred over JSON table)
    DEFAULT_DB_PATH = Path("data/reference") / NEW_DB_NAME
    HOME_DB_PATH = Path.home() / ".lucy" / NEW_DB_NAME

    # Default lookup table locations
    DEFAULT_TABLE_PATH = Path("data/reference/hose_lookup.json.gz")
    HOME_TABLE_PATH = Path.home() / ".lucy" / "hose_lookup.json.gz"

    @staticmethod
    def find_derep_database() -> Path | None:
        """Find SQLite database in default locations.

        Accepts either the new filename (``ailsa-derep.db``) or the legacy
        filename (``lucy-ng-derep.db``, PKG-05) at every tier; the new name
        is tried first so it wins when both exist.

        Search order:
        1. LUCY_DATABASE environment variable
        2. data/reference/ (project location)
        3. Common locations (~/.lucy/, ~/ailsa/, ~/lucy-ng/, etc.)
        4. macOS Spotlight search (mdfind)
        5. Recursive search in home directory (last resort)

        Returns:
            Path to database file if found, None otherwise
        """
        # 1. Check environment variable first (unchanged, any existing *.db)
        env_db = os.environ.get("LUCY_DATABASE")
        if env_db:
            env_path = Path(env_db)
            if env_path.exists() and env_path.suffix == ".db":
                return env_path

        # 2. Check project location — try both names, new first
        for name in DatabaseFinder.DB_NAMES:
            default_db = Path("data/reference") / name
            if default_db.exists():
                return default_db

        # 3. Check common locations — try both names at each existing path
        for name in DatabaseFinder.DB_NAMES:
            common_paths = [Path.home() / ".lucy" / name]
            for project_dir in DatabaseFinder.PROJECT_DIR_NAMES:
                common_paths.append(Path.home() / project_dir / "data" / "reference" / name)
                common_paths.append(Path.home() / ".local" / "share" / project_dir / name)
            for p in common_paths:
                if p.exists():
                    return p

        # 4. macOS Spotlight search (fast) — query both names, new first
        for name in DatabaseFinder.DB_NAMES:
            try:
                result = subprocess.run(
                    ["mdfind", "-name", name],
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

        # 5. Search in Dropbox/develop (common dev location) — both names
        for name in DatabaseFinder.DB_NAMES:
            for project_dir in DatabaseFinder.PROJECT_DIR_NAMES:
                dropbox_dev = (
                    Path.home() / "Dropbox" / "develop" / project_dir / "data" / "reference" / name
                )
                if dropbox_dev.exists():
                    return dropbox_dev

        return None

    @staticmethod
    def resolve_default_derep_path() -> Path:
        """Resolve the default output/lookup path for the dereplication DB.

        Prefers the existing new-named file, then the existing legacy-named
        file, then falls back to the new default path when neither exists
        (e.g. for a fresh ``download``). Used by CLI commands whose
        ``--output``/``--db`` option was not explicitly given, so that an
        existing legacy install is used in place rather than triggering a
        second ~4 GB download under the new name (PKG-05).

        Returns:
            The new default path, the existing legacy path, or the new path.
        """
        new_path = Path("data/reference") / DatabaseFinder.NEW_DB_NAME
        if new_path.exists():
            return new_path
        legacy_path = Path("data/reference") / DatabaseFinder.LEGACY_DB_NAME
        if legacy_path.exists():
            return legacy_path
        return new_path

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
        since the derep database contains both compound data and HOSE
        stats, under either the new or the legacy filename (PKG-05).

        Returns:
            Path to database file if found, None otherwise
        """
        # The HOSE database is the same as the dereplication database
        # Try the comprehensive search from find_derep_database first
        db_path = DatabaseFinder.find_derep_database()
        if db_path:
            return db_path

        # Also check current directory for convenience — both names
        for name in DatabaseFinder.DB_NAMES:
            cwd_db = Path(name)
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
