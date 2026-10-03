"""Dual-filename tests for :class:`ailsa.database.finder.DatabaseFinder` (PKG-05).

Every test isolates the filesystem search: no ``LUCY_DATABASE`` env var leaks in, the
cwd is a fresh ``tmp_path``, ``Path.home()`` is patched to a throwaway directory, and
``subprocess.run`` (used by the macOS Spotlight / ``mdfind`` tier) is patched so the
real 3.97 GB ``lucy-ng-derep.db`` on this machine is never found by accident.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ailsa.database.finder import DatabaseFinder


class _FakeCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess used by fake_run."""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Isolate LUCY_DATABASE, cwd, Path.home() and subprocess.run (mdfind)."""
    monkeypatch.delenv("LUCY_DATABASE", raising=False)
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003 - test double
        raise FileNotFoundError("mdfind not available in test isolation")

    monkeypatch.setattr("ailsa.database.finder.subprocess.run", fake_run)
    return tmp_path, home


class TestDatabaseFinderDualName:
    """PKG-05: find_derep_database()/find_hose_database() accept both filenames."""

    def test_legacy_name_only_in_project_location(self, isolated) -> None:
        """Test 1: only data/reference/lucy-ng-derep.db exists."""
        tmp_path, _home = isolated
        ref = tmp_path / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-derep.db"
        legacy.touch()

        # find_derep_database() returns a path relative to the cwd for this
        # tier (unchanged pre-rename behaviour) — compare resolved paths.
        found = DatabaseFinder.find_derep_database()
        assert found is not None
        assert found.resolve() == legacy.resolve()

    def test_new_name_only_in_project_location(self, isolated) -> None:
        """Test 2: only data/reference/ailsa-derep.db exists."""
        tmp_path, _home = isolated
        ref = tmp_path / "data" / "reference"
        ref.mkdir(parents=True)
        new = ref / "ailsa-derep.db"
        new.touch()

        found = DatabaseFinder.find_derep_database()
        assert found is not None
        assert found.resolve() == new.resolve()

    def test_new_name_wins_when_both_exist(self, isolated) -> None:
        """Test 3: both exist -> the new name wins."""
        tmp_path, _home = isolated
        ref = tmp_path / "data" / "reference"
        ref.mkdir(parents=True)
        new = ref / "ailsa-derep.db"
        legacy = ref / "lucy-ng-derep.db"
        new.touch()
        legacy.touch()

        found = DatabaseFinder.find_derep_database()
        assert found is not None
        assert found.resolve() == new.resolve()

    def test_neither_name_found_anywhere_returns_none(self, isolated) -> None:
        """Test 4: neither name exists anywhere -> None (mdfind mocked out)."""
        assert DatabaseFinder.find_derep_database() is None

    def test_home_lucy_dir_legacy_and_new(self, isolated) -> None:
        """Test 5: only home/.lucy/lucy-ng-derep.db exists -> found; adding the new
        name alongside it -> the new name wins."""
        _tmp_path, home = isolated
        lucy_dir = home / ".lucy"
        lucy_dir.mkdir()
        legacy = lucy_dir / "lucy-ng-derep.db"
        legacy.touch()

        assert DatabaseFinder.find_derep_database() == legacy

        new = lucy_dir / "ailsa-derep.db"
        new.touch()

        assert DatabaseFinder.find_derep_database() == new

    def test_env_var_precedence_unchanged(self, isolated, monkeypatch) -> None:
        """Test 6: LUCY_DATABASE points at an existing custom.db -> returned,
        unchanged precedence over every filename-based tier."""
        tmp_path, _home = isolated
        custom = tmp_path / "custom.db"
        custom.touch()
        monkeypatch.setenv("LUCY_DATABASE", str(custom))

        assert DatabaseFinder.find_derep_database() == custom

    def test_mdfind_query_order_new_then_legacy(self, isolated, monkeypatch) -> None:
        """Test 7: the mdfind names queried are ["ailsa-derep.db", "lucy-ng-derep.db"],
        in that order."""
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):  # noqa: ANN001, ANN003 - test double
            calls.append(args)
            return _FakeCompletedProcess(returncode=0, stdout="")

        monkeypatch.setattr("ailsa.database.finder.subprocess.run", fake_run)

        assert DatabaseFinder.find_derep_database() is None
        queried_names = [call[2] for call in calls if call[:2] == ["mdfind", "-name"]]
        assert queried_names == ["ailsa-derep.db", "lucy-ng-derep.db"]

    def test_find_hose_database_cwd_legacy_and_new(self, isolated) -> None:
        """Test 8: find_hose_database() checks the cwd for both filenames."""
        tmp_path, _home = isolated
        legacy = tmp_path / "lucy-ng-derep.db"
        legacy.touch()

        found = DatabaseFinder.find_hose_database()
        assert found is not None
        assert found.resolve() == legacy.resolve()

        legacy.unlink()
        new = tmp_path / "ailsa-derep.db"
        new.touch()

        found = DatabaseFinder.find_hose_database()
        assert found is not None
        assert found.resolve() == new.resolve()

    def test_resolve_default_derep_path(self, isolated) -> None:
        """Test 9: resolve_default_derep_path() picks new path when neither exists,
        the legacy path when only legacy exists, and the new path when both exist."""
        tmp_path, _home = isolated
        ref = tmp_path / "data" / "reference"
        ref.mkdir(parents=True)
        new_path = ref / "ailsa-derep.db"
        legacy_path = ref / "lucy-ng-derep.db"

        assert DatabaseFinder.resolve_default_derep_path().resolve() == new_path.resolve()

        legacy_path.touch()
        assert DatabaseFinder.resolve_default_derep_path().resolve() == legacy_path.resolve()

        new_path.touch()
        assert DatabaseFinder.resolve_default_derep_path().resolve() == new_path.resolve()

    def test_dropbox_dev_tier_legacy_and_new_project_dirs(self, isolated) -> None:
        """Test 10: ~/Dropbox/develop/lucy-ng/data/reference/lucy-ng-derep.db only ->
        found (tier 5), and ~/Dropbox/develop/ailsa/data/reference/ailsa-derep.db
        only -> found."""
        _tmp_path, home = isolated
        legacy_dir = home / "Dropbox" / "develop" / "lucy-ng" / "data" / "reference"
        legacy_dir.mkdir(parents=True)
        legacy = legacy_dir / "lucy-ng-derep.db"
        legacy.touch()

        assert DatabaseFinder.find_derep_database() == legacy

        legacy.unlink()
        new_dir = home / "Dropbox" / "develop" / "ailsa" / "data" / "reference"
        new_dir.mkdir(parents=True)
        new = new_dir / "ailsa-derep.db"
        new.touch()

        assert DatabaseFinder.find_derep_database() == new
