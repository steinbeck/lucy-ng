"""Tests for CLI dereplicate commands."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from lucy_ng.cli.dereplicate import (
    _find_database_path,
    _is_sqlite_database,
    dereplicate,
)


class TestDatabaseDetection:
    """Tests for database detection helper functions."""

    def test_is_sqlite_database_with_db_extension(self) -> None:
        """Test .db files are recognized as SQLite databases."""
        assert _is_sqlite_database("compounds.db") is True
        assert _is_sqlite_database("/path/to/compounds.db") is True
        assert _is_sqlite_database(Path("data/reference/compounds.db")) is True

    def test_is_sqlite_database_with_sd_extension(self) -> None:
        """Test .sd files are not recognized as SQLite databases."""
        assert _is_sqlite_database("nmrshiftdb.sd") is False
        assert _is_sqlite_database("coconut.sdf") is False
        assert _is_sqlite_database("file.sd.gz") is False

    def test_find_database_path_with_env_var(self, tmp_path: Path) -> None:
        """Test LUCY_DATABASE environment variable is used."""
        db_file = tmp_path / "custom.db"
        db_file.touch()

        with patch.dict(os.environ, {"LUCY_DATABASE": str(db_file)}):
            result = _find_database_path()
            assert result == db_file

    def test_find_database_path_env_var_ignores_non_db(self, tmp_path: Path) -> None:
        """Test LUCY_DATABASE is ignored for non-.db files."""
        sd_file = tmp_path / "custom.sd"
        sd_file.touch()

        with patch.dict(os.environ, {"LUCY_DATABASE": str(sd_file)}, clear=False):
            # Should not return the SD file even if env var is set
            result = _find_database_path()
            # Result depends on whether data/reference/compounds.db exists
            if result is not None:
                assert result.suffix == ".db"

    def test_find_database_path_nonexistent_env(self) -> None:
        """Test nonexistent LUCY_DATABASE path returns None or default."""
        with patch.dict(os.environ, {"LUCY_DATABASE": "/nonexistent/path.db"}, clear=False):
            result = _find_database_path()
            # Should fall through to default location
            if result is not None:
                assert result != Path("/nonexistent/path.db")


class TestDereplicateC13:
    """Tests for lucy dereplicate c13 command."""

    def test_dereplicate_invalid_database(self) -> None:
        """Test error when specified database does not exist."""
        runner = CliRunner()
        result = runner.invoke(
            dereplicate,
            ["c13", "data/Ibuprofen/2", "C13H18O2", "--database", "/nonexistent/db.sd"],
        )
        # Should fail because specified database path doesn't exist
        assert result.exit_code != 0

    def test_dereplicate_help(self) -> None:
        """Test help message shows options."""
        runner = CliRunner()
        result = runner.invoke(dereplicate, ["c13", "--help"])
        assert result.exit_code == 0
        assert "--database" in result.output
        assert "--top" in result.output
        assert "--threshold" in result.output
        assert "--format" in result.output

    def test_dereplicate_invalid_path(self) -> None:
        """Test error on invalid spectrum path."""
        runner = CliRunner()
        result = runner.invoke(dereplicate, ["c13", "data/NonExistent/2", "C13H18O2"])
        assert result.exit_code != 0

    @pytest.mark.skipif(
        not any(
            p.exists()
            for p in [
                pytest.importorskip("pathlib").Path("data/reference/coconut_predicted.sd"),
                pytest.importorskip("pathlib").Path("data/reference/nmrshiftdb2withsignals.sd"),
            ]
        ),
        reason="Reference database not available",
    )
    def test_dereplicate_with_database(self) -> None:
        """Test dereplication with actual database (COCONUT or nmrshiftdb)."""
        runner = CliRunner()
        result = runner.invoke(
            dereplicate,
            ["c13", "data/Ibuprofen/2", "C13H18O2"],
        )
        assert result.exit_code == 0
        assert "Dereplication" in result.output
        assert "Observed peaks" in result.output

    @pytest.mark.skipif(
        not Path("data/reference/compounds.db").exists(),
        reason="SQLite database not available",
    )
    def test_dereplicate_uses_sqlite_database(self) -> None:
        """Test that SQLite database is used when present."""
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            dereplicate,
            ["c13", "data/Ibuprofen/2", "C13H18O2"],
        )
        assert result.exit_code == 0
        # Check stderr for database usage message
        assert "Using database:" in result.stderr
        assert "compounds" in result.stderr.lower()

    @pytest.mark.skipif(
        not Path("data/reference/compounds.db").exists(),
        reason="SQLite database not available",
    )
    def test_dereplicate_explicit_database_flag(self) -> None:
        """Test explicit --database flag with SQLite database."""
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            dereplicate,
            ["c13", "data/Ibuprofen/2", "C13H18O2", "--database", "data/reference/compounds.db"],
        )
        assert result.exit_code == 0
        assert "Using database:" in result.stderr
        assert "compounds.db" in result.stderr

    @pytest.mark.skipif(
        not Path("data/reference/nmrshiftdb2withsignals.sd").exists(),
        reason="NMRShiftDB SD file not available",
    )
    def test_dereplicate_explicit_sd_file(self) -> None:
        """Test explicit --database flag with SD file."""
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            dereplicate,
            [
                "c13",
                "data/Ibuprofen/2",
                "C13H18O2",
                "--database",
                "data/reference/nmrshiftdb2withsignals.sd",
            ],
        )
        assert result.exit_code == 0
        assert "Using SD file:" in result.stderr
        assert "nmrshiftdb" in result.stderr.lower()

    def test_dereplicate_json_output(self) -> None:
        """Test JSON output format."""
        # Skip if no database available
        if not (
            Path("data/reference/compounds.db").exists()
            or Path("data/reference/nmrshiftdb2withsignals.sd").exists()
        ):
            pytest.skip("No reference database available")

        runner = CliRunner()
        result = runner.invoke(
            dereplicate,
            ["c13", "data/Ibuprofen/2", "C13H18O2", "--format", "json"],
        )
        assert result.exit_code == 0
        # Parse JSON output (exclude stderr lines starting with "Using")
        import json

        # stdout should be valid JSON
        output_lines = [
            line for line in result.output.split("\n") if not line.startswith("Using")
        ]
        output_text = "\n".join(output_lines)
        try:
            data = json.loads(output_text)
            assert "molecular_formula" in data
            assert "top_matches" in data
        except json.JSONDecodeError:
            # The JSON might be mixed with stderr, just check for JSON markers
            assert "{" in result.output
            assert '"molecular_formula"' in result.output
