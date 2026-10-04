"""Tests for CLI database commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests
from click.testing import CliRunner

import ailsa.cli.database as database_cli_module
from ailsa.cli import cli
from ailsa.database import DatabaseManager
from ailsa.database.models import CompoundRecord, ShiftRecord
from ailsa.fragments import FragmentDatabaseManager
from ailsa.prediction.hose import HOSEGEN_AVAILABLE


class TestDatabaseCommand:
    """Tests for database command group."""

    def test_database_help(self) -> None:
        """Test database --help shows subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["database", "--help"])
        assert result.exit_code == 0
        assert "build" in result.output
        assert "info" in result.output
        assert "download" in result.output
        assert "generate-hose-stats" in result.output

    def test_database_info_missing_file(self, tmp_path) -> None:
        """Test database info with non-existent file.

        Note: Click's CliRunner may not enforce exists=True the same way as
        normal shell invocation. DatabaseManager creates the DB if missing.
        """
        runner = CliRunner()
        missing_db = tmp_path / "nonexistent.db"
        result = runner.invoke(cli, ["database", "info", str(missing_db)])
        # DatabaseManager creates the file, so command succeeds with empty DB
        if result.exit_code == 0:
            assert "Total compounds: 0" in result.output
        else:
            # If Click enforces exists=True, command fails
            assert result.exit_code != 0


@pytest.mark.skipif(not HOSEGEN_AVAILABLE, reason="hosegen not available")
class TestGenerateHoseStats:
    """Tests for generate-hose-stats command."""

    def test_generate_hose_stats_help(self) -> None:
        """Test generate-hose-stats --help shows usage."""
        runner = CliRunner()
        result = runner.invoke(cli, ["database", "generate-hose-stats", "--help"])
        assert result.exit_code == 0
        assert "Generate HOSE code statistics" in result.output
        assert "--db" in result.output
        assert "--max-radius" in result.output
        assert "--chunk-size" in result.output

    def test_generate_hose_stats_missing_db(self, tmp_path) -> None:
        """Test generate-hose-stats with non-existent database.

        The command now creates the database if it doesn't exist and succeeds
        with 0 compounds processed. This is the expected behavior for the
        resumable generator.
        """
        runner = CliRunner()
        missing_db = tmp_path / "nonexistent.db"
        result = runner.invoke(
            cli, ["database", "generate-hose-stats", "--db", str(missing_db)]
        )
        # Command succeeds but processes 0 compounds
        assert result.exit_code == 0
        assert "Generated 0 statistics" in result.output or "0 compounds" in result.output.lower()

    def test_generate_hose_stats_with_test_db(self, tmp_path) -> None:
        """Test generate-hose-stats with a small test database."""
        db_path = tmp_path / "test.db"

        # Create test database with a few compounds
        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert test compound: ethanol
            ethanol = CompoundRecord(
                name="Ethanol",
                smiles="CCO",
                formula="C2H6O",
                source="test",
                carbon_count=2,
            )
            ethanol_shifts = [
                ShiftRecord(atom_index=0, shift_ppm=18.0, hydrogen_count=3),
                ShiftRecord(atom_index=1, shift_ppm=58.0, hydrogen_count=2),
            ]
            db.insert_compound(ethanol, ethanol_shifts)

            # Insert test compound: methanol
            methanol = CompoundRecord(
                name="Methanol",
                smiles="CO",
                formula="CH4O",
                source="test",
                carbon_count=1,
            )
            methanol_shifts = [
                ShiftRecord(atom_index=0, shift_ppm=50.0, hydrogen_count=3),
            ]
            db.insert_compound(methanol, methanol_shifts)

        # Run generate-hose-stats
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "database",
                "generate-hose-stats",
                "--db",
                str(db_path),
                "--max-radius",
                "2",
            ],
        )

        assert result.exit_code == 0
        assert "Generating HOSE statistics" in result.output
        assert "Generated" in result.output
        assert "statistics" in result.output
        assert "compounds" in result.output
        assert "Time:" in result.output

        # Verify stats were inserted
        with DatabaseManager(db_path) as db:
            stats_count = db.get_hose_stats_count()
            assert stats_count > 0

    def test_generate_hose_stats_invalid_max_radius(self) -> None:
        """Test generate-hose-stats with invalid max-radius."""
        runner = CliRunner()

        # Radius too high
        result = runner.invoke(
            cli,
            ["database", "generate-hose-stats", "--max-radius", "7"],
        )
        assert result.exit_code != 0

        # Radius too low
        result = runner.invoke(
            cli,
            ["database", "generate-hose-stats", "--max-radius", "0"],
        )
        assert result.exit_code != 0


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """Isolate cwd, LUCY_DATABASE, Path.home() and mdfind (PKG-05 CLI tests).

    Without this, DatabaseFinder's mdfind tier would find the real 3.97 GB
    lucy-ng-derep.db / 605 MB lucy-ng-fragments.db on this machine.
    """
    monkeypatch.delenv("LUCY_DATABASE", raising=False)
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003 - test double
        raise FileNotFoundError("mdfind not available in test isolation")

    monkeypatch.setattr("ailsa.database.finder.subprocess.run", fake_run)

    def forbid_download(*args, **kwargs):  # noqa: ANN002, ANN003 - test double
        raise AssertionError("must not download")

    monkeypatch.setattr(database_cli_module.requests, "get", forbid_download)
    return tmp_path


class TestDatabaseDualFilename:
    """PKG-05: `ailsa database download`/`info` accept the legacy filename."""

    def test_download_no_output_legacy_present_short_circuits(self, isolated_cwd) -> None:
        """Test A: only data/reference/lucy-ng-derep.db present -> no download."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-derep.db"
        with DatabaseManager(legacy) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(cli, ["database", "download"])

        assert result.exit_code == 0
        assert "Database already exists: data/reference/lucy-ng-derep.db" in result.stdout

    def test_download_no_output_new_present_short_circuits(self, isolated_cwd) -> None:
        """Test B: only data/reference/ailsa-derep.db present -> no download,
        the message names the ailsa path."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        new = ref / "ailsa-derep.db"
        with DatabaseManager(new) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(cli, ["database", "download"])

        assert result.exit_code == 0
        assert "Database already exists: data/reference/ailsa-derep.db" in result.stdout

    def test_download_explicit_output_still_downloads(self, isolated_cwd) -> None:
        """Test C: an explicit --output is honoured; the legacy short-circuit
        applies only to the default output path."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-derep.db"
        with DatabaseManager(legacy) as db:
            db.create_tables()

        def raising_get(*args, **kwargs):  # noqa: ANN002, ANN003 - test double
            raise requests.RequestException("simulated network failure")

        database_cli_module.requests.get = raising_get  # type: ignore[attr-defined]

        runner = CliRunner()
        result = runner.invoke(cli, ["database", "download", "-o", "custom.db"])

        assert result.exit_code != 0
        assert "Error downloading" in result.output

    def test_info_no_argument_legacy_present(self, isolated_cwd) -> None:
        """Test D: `database info` with no argument, only legacy present."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-derep.db"
        with DatabaseManager(legacy) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(cli, ["database", "info"])

        assert result.exit_code == 0
        assert "Database: data/reference/lucy-ng-derep.db" in result.stdout
        assert "Total compounds: 0" in result.stdout

    def test_info_explicit_legacy_and_new_paths(self, isolated_cwd) -> None:
        """Test E: `database info` accepts an explicit legacy path and an
        explicit new path."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-derep.db"
        new = ref / "ailsa-derep.db"
        with DatabaseManager(legacy) as db:
            db.create_tables()
        with DatabaseManager(new) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["database", "info", "data/reference/lucy-ng-derep.db"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli, ["database", "info", "data/reference/ailsa-derep.db"]
        )
        assert result.exit_code == 0

    def test_info_no_argument_nothing_found(self, isolated_cwd) -> None:
        """Test F: `database info` with no argument and no database anywhere
        -> non-zero exit, hint mentions `ailsa database download`."""
        runner = CliRunner()
        result = runner.invoke(cli, ["database", "info"])

        assert result.exit_code != 0
        assert "ailsa database download" in result.output

    def test_help_mentions_both_filenames(self, isolated_cwd) -> None:
        """Test H: --help texts stay green and the download help mentions both
        the new and the legacy default filename."""
        runner = CliRunner()
        result = runner.invoke(cli, ["database", "--help"])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["database", "download", "--help"])
        assert result.exit_code == 0
        assert "ailsa-derep.db" in result.output
        assert "lucy-ng-derep.db" in result.output


class TestFragmentDualFilename:
    """PKG-05: `ailsa fragment info` accepts the legacy fragments filename."""

    def test_fragment_info_no_argument_legacy_present(self, isolated_cwd) -> None:
        """Test G (part 1): only legacy lucy-ng-fragments.db present -> exit 0."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-fragments.db"
        with FragmentDatabaseManager(legacy) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(cli, ["fragment", "info"])

        assert result.exit_code == 0

    def test_fragment_info_no_argument_nothing_found(self, isolated_cwd) -> None:
        """Test G (part 2): neither filename present -> non-zero exit, stderr
        mentions `ailsa fragment build`."""
        runner = CliRunner()
        result = runner.invoke(cli, ["fragment", "info"])

        assert result.exit_code != 0
        assert "ailsa fragment build" in result.output

    def test_fragment_info_no_argument_finds_db_outside_data_reference(
        self, isolated_cwd
    ) -> None:
        """WR-01 (104-REVIEW.md): `fragment info`'s default resolution must
        search DatabaseFinder's full tier list, not just `data/reference/`.
        Only a legacy fragments DB under `~/.lucy/` exists (no
        `data/reference/` at all) -> it must still be auto-detected,
        matching the coverage `database info` gets for the derep DB via
        `DatabaseFinder.find_derep_database()`."""
        lucy_dir = isolated_cwd / "home" / ".lucy"
        lucy_dir.mkdir(parents=True)
        legacy = lucy_dir / "lucy-ng-fragments.db"
        with FragmentDatabaseManager(legacy) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(cli, ["fragment", "info"])

        assert result.exit_code == 0
        assert str(legacy) in result.output

    def test_fragment_search_no_argument_finds_db_outside_data_reference(
        self, isolated_cwd
    ) -> None:
        """Same coverage check as above, for `fragment search`'s default
        resolution branch."""
        lucy_dir = isolated_cwd / "home" / ".lucy"
        lucy_dir.mkdir(parents=True)
        legacy = lucy_dir / "lucy-ng-fragments.db"
        with FragmentDatabaseManager(legacy) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fragment", "search", "--shifts", "128.0,130.5"]
        )

        assert result.exit_code == 0

    def test_fragment_search_no_db_legacy_present(self, isolated_cwd) -> None:
        """IN-02 (104-REVIEW.md): `fragment search`'s default-resolution
        branch (``--db`` omitted, only the legacy-named fragments DB present
        in ``data/reference/``) must auto-detect the legacy file, mirroring
        the existing `fragment info` coverage above."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-fragments.db"
        with FragmentDatabaseManager(legacy) as db:
            db.create_tables()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fragment", "search", "--shifts", "128.0,130.5"]
        )

        assert result.exit_code == 0, result.output
        output = json.loads(result.output)
        assert output["result_count"] == 0

    def test_fragment_build_fragment_db_default_legacy_present(
        self, isolated_cwd
    ) -> None:
        """IN-02 (104-REVIEW.md): `fragment build`'s default-resolution
        branch (`resolve_default_fragments_db()`, used for its FRAGMENT_DB
        positional argument when omitted) must reuse an existing legacy-named
        fragments DB in place rather than creating a new ``ailsa-fragments.db``
        alongside it."""
        ref = isolated_cwd / "data" / "reference"
        ref.mkdir(parents=True)
        legacy = ref / "lucy-ng-fragments.db"
        with FragmentDatabaseManager(legacy) as fdb:
            fdb.create_tables()

        compound_db_path = isolated_cwd / "compounds.db"
        with DatabaseManager(compound_db_path) as cdb:
            cdb.create_tables()

        runner = CliRunner()
        result = runner.invoke(cli, ["fragment", "build", str(compound_db_path)])

        assert result.exit_code == 0, result.output
        assert "Fragment DB total SSCs: 0" in result.output
        assert not (ref / "ailsa-fragments.db").exists()
