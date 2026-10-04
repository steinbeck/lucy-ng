"""Regression test for WR-01 (104-REVIEW.md).

``ailsa.identity._resolve_db_path()``'s import-fallback path (taken only
when ``from ailsa.database.finder import DatabaseFinder`` itself raises) must
mirror ``DatabaseFinder.find_derep_database()``'s tier-5 "new filename wins
across every directory before the legacy filename is tried in any
directory" ordering. Before the fix, the Dropbox-dev tier looped directory
outer / filename inner, inverting that guarantee for a cross-matched
layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ailsa import identity as identity_module


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Isolate LUCY_DATABASE, cwd and Path.home() for a clean search."""
    monkeypatch.delenv("LUCY_DATABASE", raising=False)
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return tmp_path, home


def test_fallback_import_failure_new_name_wins_across_directories(isolated, monkeypatch):
    """Cross-matched layout from the REVIEW.md example: the ``ailsa``
    Dropbox-dev dir has only the legacy-named file, the ``lucy-ng`` dir has
    only the new-named file -> the new-named file must win (matches
    DatabaseFinder's tier 5, which tries the new name across every
    directory before the legacy name in any directory). Before the fix,
    this fallback's directory-outer/filename-inner loop returned the
    legacy-named file from the ``ailsa`` dir instead, because that
    directory is checked first and, within it, the legacy name is also
    tried before moving on."""
    _tmp_path, home = isolated

    legacy_dir = home / "Dropbox" / "develop" / "ailsa" / "data" / "reference"
    legacy_dir.mkdir(parents=True)
    legacy = legacy_dir / "lucy-ng-derep.db"
    legacy.touch()

    new_dir = home / "Dropbox" / "develop" / "lucy-ng" / "data" / "reference"
    new_dir.mkdir(parents=True)
    new = new_dir / "ailsa-derep.db"
    new.touch()

    # Force the `from ailsa.database.finder import DatabaseFinder` import
    # inside _resolve_db_path to raise, so the `# pragma: no cover` fallback
    # branch runs instead of delegating to DatabaseFinder itself.
    monkeypatch.setitem(sys.modules, "ailsa.database.finder", None)

    found = identity_module._resolve_db_path(None)
    assert found is not None
    assert found.resolve() == new.resolve()
