"""Tests for CLI database commands."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from lucy_ng.cli import cli
from lucy_ng.database import DatabaseManager
from lucy_ng.database.models import CompoundRecord, ShiftRecord
from lucy_ng.prediction.hose import HOSEGEN_AVAILABLE


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

    def test_database_info_missing_file(self) -> None:
        """Test database info with non-existent file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["database", "info", "nonexistent.db"])
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
        assert "--batch-size" in result.output

    def test_generate_hose_stats_missing_db(self) -> None:
        """Test generate-hose-stats with non-existent database."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["database", "generate-hose-stats", "--db", "nonexistent.db"]
        )
        assert result.exit_code != 0

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
