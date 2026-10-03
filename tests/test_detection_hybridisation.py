"""Tests for hybridisation detection module."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.main import cli
from ailsa.database import DatabaseManager
from ailsa.detection import StatisticalDetector
from ailsa.detection.models import HybridisationDistribution


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create in-memory test database with v4 schema and sample data."""
    db_path = tmp_path / "test_hose.db"

    # Create database with v4 schema
    with DatabaseManager(db_path) as db:
        db.create_tables()

        # Insert test data with varied hybridisation distributions
        conn = db.connection
        cursor = conn.cursor()

        # Aromatic region (~130 ppm): sp2 dominant
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count)
            VALUES
                ('C-3;=CC(=C/)', 3, 130.0, 2.5, 915, 10, 900, 5),
                ('C-3;=CC(=N/)', 3, 131.5, 1.8, 205, 5, 195, 5),
                ('C-3;=CN(=C/)', 3, 129.0, 2.0, 110, 2, 108, 0)
            """
        )

        # Aliphatic region (~25 ppm): sp3 dominant
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count)
            VALUES
                ('C-4;CC(C/C)', 3, 25.0, 1.5, 990, 950, 40, 0),
                ('C-4;CC(C/N)', 3, 26.5, 1.2, 510, 500, 10, 0)
            """
        )

        # Alkyne region (~85 ppm): sp1 dominant
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count)
            VALUES
                ('C-2;#CC(//)', 3, 85.0, 3.0, 815, 5, 10, 800),
                ('C-2;#CN(//)', 3, 86.0, 2.5, 210, 3, 7, 200)
            """
        )

        # Out of range region (for no-data test)
        # No entries at 300 ppm

        # Zero hybridisation data region (~50 ppm) for warning test
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count)
            VALUES
                ('C-4;CO(C/C)', 3, 50.0, 2.0, 100, 0, 0, 0)
            """
        )

        conn.commit()

    return db_path


def test_detect_hybridisation_aromatic(test_db: Path) -> None:
    """Test detection in aromatic region - sp2 should dominate."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_hybridisation(130.5, radius=3, window_ppm=2.0)

    assert result.has_data is True
    assert result.shift_ppm == 130.5
    assert result.window_ppm == 2.0
    assert result.radius == 3
    assert result.unique_hose_codes == 3

    # sp2 should be dominant (900+195+108 = 1203 out of 1230 total)
    assert result.distribution.dominant == "sp2"
    assert result.distribution.sp2 > 0.9  # >90%
    assert result.distribution.sp3 < 0.1  # <10%


def test_detect_hybridisation_aliphatic(test_db: Path) -> None:
    """Test detection in aliphatic region - sp3 should dominate."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_hybridisation(25.0, radius=3, window_ppm=2.0)

    assert result.has_data is True
    assert result.unique_hose_codes == 2

    # sp3 should be dominant (950+500 = 1450 out of 1500 total)
    assert result.distribution.dominant == "sp3"
    assert result.distribution.sp3 > 0.9  # >90%
    assert result.distribution.sp2 < 0.1  # <10%


def test_detect_hybridisation_alkyne(test_db: Path) -> None:
    """Test detection in alkyne region - sp1 should dominate."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_hybridisation(85.0, radius=3, window_ppm=2.0)

    assert result.has_data is True
    assert result.unique_hose_codes == 2

    # sp1 should be dominant (800+200 = 1000 out of 1025 total)
    assert result.distribution.dominant == "sp1"
    assert result.distribution.sp1 > 0.9  # >90%


def test_detect_threshold_filters(test_db: Path) -> None:
    """Test that threshold filtering excludes low-frequency states."""
    with StatisticalDetector(test_db) as detector:
        # Aliphatic region has sp3=950, sp2=50, sp1=0 (total=1500)
        # sp2 frequency = 50/1500 = 3.3%
        # With 1% threshold, sp2 should be included
        # With 5% threshold, sp2 should be excluded (filtered to 0)
        result = detector.detect_hybridisation(
            25.0, radius=3, window_ppm=2.0, threshold=0.05  # 5%
        )

    assert result.has_data is True
    # After filtering, only sp3 should remain (normalized to 1.0)
    assert result.distribution.sp3 == 1.0
    assert result.distribution.sp2 == 0.0
    assert result.distribution.sp1 == 0.0


def test_detect_no_data(test_db: Path) -> None:
    """Test detection when no HOSE codes match (out of range)."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_hybridisation(300.0, radius=3, window_ppm=2.0)

    assert result.has_data is False
    assert result.warning is not None
    assert "No hybridisation data" in result.warning
    assert result.total_observations == 0
    assert result.distribution.dominant == "unknown"


def test_detect_all_zeros_warning(test_db: Path) -> None:
    """Test warning when hybridisation counts are all zero."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_hybridisation(50.0, radius=3, window_ppm=2.0)

    assert result.has_data is False
    assert result.warning is not None
    assert "regeneration" in result.warning.lower()
    assert result.total_observations == 0


def test_hybridisation_distribution_dominant() -> None:
    """Test HybridisationDistribution.dominant property."""
    # sp3 dominant
    dist = HybridisationDistribution(sp3=0.8, sp2=0.15, sp1=0.05)
    assert dist.dominant == "sp3"

    # sp2 dominant
    dist = HybridisationDistribution(sp3=0.1, sp2=0.85, sp1=0.05)
    assert dist.dominant == "sp2"

    # sp1 dominant
    dist = HybridisationDistribution(sp3=0.05, sp2=0.1, sp1=0.85)
    assert dist.dominant == "sp1"

    # All zero
    dist = HybridisationDistribution(sp3=0.0, sp2=0.0, sp1=0.0)
    assert dist.dominant == "unknown"


def test_hybridisation_distribution_is_definitive() -> None:
    """Test HybridisationDistribution.is_definitive property."""
    # >95% - definitive
    dist = HybridisationDistribution(sp3=0.96, sp2=0.03, sp1=0.01)
    assert dist.is_definitive is True

    # =95% - not definitive
    dist = HybridisationDistribution(sp3=0.95, sp2=0.04, sp1=0.01)
    assert dist.is_definitive is False

    # <95% - not definitive
    dist = HybridisationDistribution(sp3=0.85, sp2=0.10, sp1=0.05)
    assert dist.is_definitive is False


def test_hybridisation_result_summary_format(test_db: Path) -> None:
    """Test HybridisationResult.summary() contains expected elements."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_hybridisation(130.5, radius=3, window_ppm=2.0)

    summary = result.summary()

    # Check header
    assert "130.5 ppm" in summary
    assert "window +/- 2.0 ppm" in summary
    assert "radius 3" in summary

    # Check distribution line
    assert "Distribution:" in summary
    assert "sp2=" in summary  # sp2 should be present
    assert "%" in summary

    # Check dominant state
    assert "Dominant:" in summary
    assert "sp2" in summary

    # Check data coverage
    assert "observations" in summary
    assert "HOSE codes" in summary


def test_hybridisation_result_json_format(test_db: Path) -> None:
    """Test HybridisationResult.model_dump_json() produces valid JSON."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_hybridisation(130.5, radius=3, window_ppm=2.0)

    json_str = result.model_dump_json(indent=2)
    data = json.loads(json_str)

    # Check expected keys
    assert "shift_ppm" in data
    assert "window_ppm" in data
    assert "radius" in data
    assert "threshold" in data
    assert "distribution" in data
    assert "total_observations" in data
    assert "unique_hose_codes" in data
    assert "has_data" in data

    # Check distribution structure
    assert "sp3" in data["distribution"]
    assert "sp2" in data["distribution"]
    assert "sp1" in data["distribution"]

    # Verify types
    assert isinstance(data["shift_ppm"], (int, float))
    assert isinstance(data["has_data"], bool)
    assert isinstance(data["total_observations"], int)


def test_cli_detect_command_exists() -> None:
    """Test that 'ailsa detect hybridisation --help' works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["detect", "hybridisation", "--help"])

    assert result.exit_code == 0
    assert "Detect hybridisation state" in result.output
    assert "--db" in result.output
    assert "--radius" in result.output
    assert "--window" in result.output
    assert "--threshold" in result.output
    assert "--format" in result.output


def test_cli_detect_group_exists() -> None:
    """Test that 'ailsa detect --help' shows hybridisation subcommand."""
    runner = CliRunner()
    result = runner.invoke(cli, ["detect", "--help"])

    assert result.exit_code == 0
    assert "Statistical detection" in result.output
    assert "hybridisation" in result.output
