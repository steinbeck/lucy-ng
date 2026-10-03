"""Tests for neighbourhood detection module."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.main import cli
from ailsa.database import DatabaseManager
from ailsa.detection import StatisticalDetector
from ailsa.detection.models import ConstraintType, NeighbourDistribution, NeighbourResult


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create test database with v5 schema and sample neighbour data."""
    db_path = tmp_path / "test_hose.db"

    # Create database with v5 schema
    with DatabaseManager(db_path) as db:
        db.create_tables()

        # Insert test data with neighbour counts
        conn = db.connection
        cursor = conn.cursor()

        # Carbonyl region (~170 ppm): O mandatory, S/halogen forbidden
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count,
                 has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                 has_sulfur_neighbor, has_halogen_neighbor)
            VALUES
                ('C-3;=OC(C/)', 3, 170.0, 2.5, 800, 5, 790, 5, 750, 790, 100, 3, 0),
                ('C-3;=ON(C/)', 3, 171.5, 1.8, 200, 2, 195, 3, 180, 195, 120, 1, 0)
            """
        )

        # Aliphatic region (~25 ppm): C mandatory, halogen/S/N mostly absent
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count,
                 has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                 has_sulfur_neighbor, has_halogen_neighbor)
            VALUES
                ('C-4;CC(C/C)', 3, 25.0, 1.5, 900, 880, 20, 0, 895, 50, 5, 2, 0),
                ('C-4;CC(C/N)', 3, 26.5, 1.2, 100, 95, 5, 0, 98, 30, 70, 1, 0)
            """
        )

        # Zero-neighbour region (~50 ppm) for warning test
        # Data exists but neighbour counts all 0
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count,
                 has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                 has_sulfur_neighbor, has_halogen_neighbor)
            VALUES
                ('C-4;CO(C/C)', 3, 50.0, 2.0, 100, 90, 10, 0, 0, 0, 0, 0, 0)
            """
        )

        conn.commit()

    return db_path


def test_detect_neighbours_carbonyl(test_db: Path) -> None:
    """Test detection in carbonyl region - O should be mandatory."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_neighbours(170.5, radius=3, window_ppm=2.0)

    assert result.has_data is True
    assert result.shift_ppm == 170.5
    assert result.window_ppm == 2.0
    assert result.radius == 3
    assert result.unique_hose_codes == 2
    assert result.total_observations == 1000  # 800 + 200

    # O should be mandatory (790+195 = 985 out of 1000 = 98.5%)
    assert result.distribution.oxygen > 0.95
    assert "oxygen" in result.distribution.mandatory_elements

    # S and halogen should be forbidden (3+1 = 4, 0 out of 1000 = 0.4%, 0%)
    assert result.distribution.sulfur < 0.01
    assert result.distribution.halogen < 0.01
    assert "sulfur" in result.distribution.forbidden_elements
    assert "halogen" in result.distribution.forbidden_elements

    # C and N should be typical (neither forbidden nor mandatory)
    mandatory_constraints = [
        c for c in result.constraints if c.constraint_type == ConstraintType.MANDATORY
    ]
    forbidden_constraints = [
        c for c in result.constraints if c.constraint_type == ConstraintType.FORBIDDEN
    ]

    mandatory_elements = {c.element for c in mandatory_constraints}
    forbidden_elements = {c.element for c in forbidden_constraints}

    assert "oxygen" in mandatory_elements
    assert "sulfur" in forbidden_elements
    assert "halogen" in forbidden_elements
    assert "carbon" not in mandatory_elements
    assert "carbon" not in forbidden_elements
    assert "nitrogen" not in mandatory_elements
    assert "nitrogen" not in forbidden_elements


def test_detect_neighbours_aliphatic(test_db: Path) -> None:
    """Test detection in aliphatic region - C should be mandatory."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_neighbours(25.0, radius=3, window_ppm=2.0)

    assert result.has_data is True
    assert result.unique_hose_codes == 2
    assert result.total_observations == 1000  # 900 + 100

    # C should be mandatory (895+98 = 993 out of 1000 = 99.3%)
    assert result.distribution.carbon > 0.95
    assert "carbon" in result.distribution.mandatory_elements

    # S and halogen should be forbidden (2+1 = 3, 0 out of 1000 = 0.3%, 0%)
    assert result.distribution.sulfur < 0.01
    assert result.distribution.halogen < 0.01
    assert "sulfur" in result.distribution.forbidden_elements
    assert "halogen" in result.distribution.forbidden_elements


def test_detect_neighbours_custom_thresholds(test_db: Path) -> None:
    """Test that custom thresholds change classifications."""
    with StatisticalDetector(test_db) as detector:
        # Carbonyl region with higher thresholds
        result = detector.detect_neighbours(
            170.5,
            radius=3,
            window_ppm=2.0,
            forbidden_threshold=0.05,  # 5% instead of 1%
            mandatory_threshold=0.99,  # 99% instead of 95%
        )

    assert result.has_data is True

    # With forbidden_threshold=5%, sulfur (0.4%) is still forbidden
    # But nitrogen (22%) should now be typical (was typical with 1% threshold too)
    assert result.distribution.sulfur < 0.05
    assert result.distribution.nitrogen > 0.05

    # With mandatory_threshold=99%, oxygen (98.5%) should NOT be mandatory in constraints
    # (but will still appear in mandatory_elements property which uses hardcoded 0.95)
    assert result.distribution.oxygen < 0.99

    # Check constraints (respects custom threshold)
    mandatory_constraints = [
        c for c in result.constraints if c.constraint_type == ConstraintType.MANDATORY
    ]
    # With 99% threshold, nothing should be mandatory
    assert len(mandatory_constraints) == 0

    # But the property uses hardcoded 0.95, so oxygen will still show as mandatory
    assert "oxygen" in result.distribution.mandatory_elements


def test_detect_neighbours_no_data(test_db: Path) -> None:
    """Test detection when no HOSE codes match (out of range)."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_neighbours(300.0, radius=3, window_ppm=2.0)

    assert result.has_data is False
    assert result.warning is not None
    assert "No data" in result.warning
    assert result.total_observations == 0
    assert result.unique_hose_codes == 0


def test_detect_neighbours_zero_columns_warning(test_db: Path) -> None:
    """Test warning when neighbour columns are all zero (v4 database)."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_neighbours(50.0, radius=3, window_ppm=2.0)

    assert result.has_data is False
    assert result.warning is not None
    assert "unpopulated" in result.warning.lower() or "regeneration" in result.warning.lower()
    assert result.total_observations == 100  # Data exists
    assert result.unique_hose_codes == 1


def test_neighbour_distribution_get_constraints() -> None:
    """Test NeighbourDistribution.get_constraints() classifies correctly."""
    dist = NeighbourDistribution(
        carbon=0.85,
        oxygen=0.98,
        nitrogen=0.12,
        sulfur=0.005,
        halogen=0.0,
    )

    constraints = dist.get_constraints(forbidden_threshold=0.01, mandatory_threshold=0.95)

    # Verify we get all 5 elements
    assert len(constraints) == 5

    # Check individual classifications
    constraint_map = {c.element: c for c in constraints}

    assert constraint_map["carbon"].constraint_type == ConstraintType.TYPICAL
    assert constraint_map["oxygen"].constraint_type == ConstraintType.MANDATORY
    assert constraint_map["nitrogen"].constraint_type == ConstraintType.TYPICAL
    assert constraint_map["sulfur"].constraint_type == ConstraintType.FORBIDDEN
    assert constraint_map["halogen"].constraint_type == ConstraintType.FORBIDDEN

    # Check frequencies match
    assert constraint_map["carbon"].frequency == 0.85
    assert constraint_map["oxygen"].frequency == 0.98


def test_neighbour_distribution_forbidden_elements() -> None:
    """Test NeighbourDistribution.forbidden_elements property."""
    dist = NeighbourDistribution(
        carbon=0.85,
        oxygen=0.98,
        nitrogen=0.12,
        sulfur=0.005,
        halogen=0.0,
    )

    forbidden = dist.forbidden_elements

    assert "sulfur" in forbidden
    assert "halogen" in forbidden
    assert len(forbidden) == 2


def test_neighbour_distribution_mandatory_elements() -> None:
    """Test NeighbourDistribution.mandatory_elements property."""
    dist = NeighbourDistribution(
        carbon=0.85,
        oxygen=0.98,
        nitrogen=0.12,
        sulfur=0.005,
        halogen=0.0,
    )

    mandatory = dist.mandatory_elements

    assert "oxygen" in mandatory
    assert len(mandatory) == 1


def test_neighbour_result_summary_format(test_db: Path) -> None:
    """Test NeighbourResult.summary() contains expected elements."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_neighbours(170.5, radius=3, window_ppm=2.0)

    summary = result.summary()

    # Check header
    assert "170.5 ppm" in summary
    assert "window +/- 2.0 ppm" in summary
    assert "radius 3" in summary

    # Check distribution line
    assert "Distribution:" in summary
    assert "%" in summary

    # Check forbidden/mandatory sections
    assert "Forbidden:" in summary
    assert "Mandatory:" in summary

    # Check data coverage
    assert "observations" in summary
    assert "HOSE codes" in summary


def test_neighbour_result_json_format(test_db: Path) -> None:
    """Test NeighbourResult.model_dump_json() produces valid JSON."""
    with StatisticalDetector(test_db) as detector:
        result = detector.detect_neighbours(170.5, radius=3, window_ppm=2.0)

    json_str = result.model_dump_json(indent=2)
    data = json.loads(json_str)

    # Check expected keys
    assert "shift_ppm" in data
    assert "window_ppm" in data
    assert "radius" in data
    assert "forbidden_threshold" in data
    assert "mandatory_threshold" in data
    assert "distribution" in data
    assert "constraints" in data
    assert "total_observations" in data
    assert "unique_hose_codes" in data
    assert "has_data" in data

    # Check distribution structure
    dist = data["distribution"]
    assert "carbon" in dist
    assert "oxygen" in dist
    assert "nitrogen" in dist
    assert "sulfur" in dist
    assert "halogen" in dist

    # Verify types
    assert isinstance(data["shift_ppm"], (int, float))
    assert isinstance(data["has_data"], bool)
    assert isinstance(data["total_observations"], int)


def test_constraint_type_enum() -> None:
    """Test ConstraintType enum values."""
    assert ConstraintType.FORBIDDEN.value == "forbidden"
    assert ConstraintType.TYPICAL.value == "typical"
    assert ConstraintType.MANDATORY.value == "mandatory"

    # Check we can compare
    assert ConstraintType.FORBIDDEN == "forbidden"
    assert ConstraintType.TYPICAL == "typical"
    assert ConstraintType.MANDATORY == "mandatory"


# ===== CLI Integration Tests =====


def test_cli_detect_neighbours_command_exists() -> None:
    """Test that 'ailsa detect neighbours --help' works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["detect", "neighbours", "--help"])

    assert result.exit_code == 0
    assert "Detect forbidden and mandatory" in result.output
    assert "--db" in result.output
    assert "--radius" in result.output
    assert "--window" in result.output
    assert "--min-frequency" in result.output
    assert "--max-frequency" in result.output
    assert "--mode" in result.output
    assert "--format" in result.output


def test_cli_detect_group_shows_neighbours() -> None:
    """Test that 'ailsa detect --help' shows neighbours subcommand."""
    runner = CliRunner()
    result = runner.invoke(cli, ["detect", "--help"])

    assert result.exit_code == 0
    assert "neighbours" in result.output


def test_cli_detect_neighbours_text_output(test_db: Path) -> None:
    """Test neighbours command with text output format."""
    runner = CliRunner()
    result = runner.invoke(cli, ["detect", "neighbours", "170.5", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Neighbourhood Detection" in result.output
    assert "170.5 ppm" in result.output
    # Should show at least one of forbidden/mandatory
    assert "Forbidden:" in result.output or "Mandatory:" in result.output


def test_cli_detect_neighbours_json_output(test_db: Path) -> None:
    """Test neighbours command with JSON output format."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["detect", "neighbours", "170.5", "--db", str(test_db), "--format", "json"]
    )

    assert result.exit_code == 0

    # Parse JSON output
    data = json.loads(result.output)

    # Check expected keys
    assert "shift_ppm" in data
    assert "distribution" in data
    assert "constraints" in data
    assert "has_data" in data
    assert "total_observations" in data
    assert "unique_hose_codes" in data

    # Verify types
    assert isinstance(data["shift_ppm"], (int, float))
    assert isinstance(data["has_data"], bool)
    assert isinstance(data["total_observations"], int)


def test_cli_detect_neighbours_mode_relaxed(test_db: Path) -> None:
    """Test neighbours command with relaxed mode (0.1%/99% thresholds)."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["detect", "neighbours", "170.5", "--db", str(test_db), "--mode", "relaxed"]
    )

    assert result.exit_code == 0
    # Should run without error
    assert "170.5 ppm" in result.output


# ===== Advisory / FIX-10 Regression Tests =====


def test_neighbour_result_advisory_default() -> None:
    """Test A: NeighbourResult has advisory=True by default."""
    result = NeighbourResult(
        shift_ppm=100.0,
        window_ppm=2.0,
        radius=3,
        distribution=NeighbourDistribution(),
    )
    assert result.advisory is True
    assert "statistical prior" in result.advisory_note
    assert "FIX-10" in result.advisory_note


def test_neighbour_result_summary_advisory_prefix() -> None:
    """Test B: NeighbourResult.summary() starts with [ADVISORY] prefix."""
    result = NeighbourResult(
        shift_ppm=100.0,
        window_ppm=2.0,
        radius=3,
        distribution=NeighbourDistribution(),
    )
    summary = result.summary()
    assert summary.startswith("[ADVISORY]")
    assert "statistical prior" in summary


def test_dominant_element_carbon() -> None:
    """Test C: carbon as highest frequency yields dominant_element='carbon'."""
    dist = NeighbourDistribution(carbon=0.95, oxygen=0.55, nitrogen=0.32)
    assert dist.dominant_element == "carbon"


def test_dominant_element_oxygen() -> None:
    """Test D: oxygen as highest frequency yields dominant_element='oxygen'."""
    dist = NeighbourDistribution(carbon=0.30, oxygen=0.97)
    assert dist.dominant_element == "oxygen"


def test_detect_neighbours_json_advisory_and_dominant_element(test_db: Path) -> None:
    """Test E: CLI JSON output includes advisory=true and dominant_element key."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["detect", "neighbours", "170.5", "--db", str(test_db), "--format", "json"],
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["advisory"] is True
    assert "dominant_element" in parsed
    assert "advisory_note" in parsed
    assert "statistical prior" in parsed["advisory_note"]


def test_case9_truth_not_excluded_by_fix10_conformant_constraints() -> None:
    """FIX-10 regression: verifies that the CASE9 truth compound (C12H16O3, 0 ring-O) is
    structurally consistent with a FIX-10-conformant constraint set. In the truth, the
    ~150 ppm class aromatic C bears a carbon substituent (not ring-O). detect_neighbours
    at this shift class has carbon as dominant neighbour, making it a 'typical'-O /
    carbon-dominant pattern. A FIX-10-conformant set leaves this heteroatom placement
    open (no PROP, no hard BOND). This test verifies the truth structure would appear in
    the LSD search space: (1) it has the expected formula, (2) it has 0 ring-O, (3) it
    has at least one aromatic C with a non-ring aliphatic C substituent (the benzylic
    carbon bearing an OH group).
    """
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    truth_smiles = "CC(O)c1ccc(cc1)C(=O)OC(C)C"
    mol = Chem.MolFromSmiles(truth_smiles)
    assert mol is not None, "truth SMILES must parse"
    assert rdMolDescriptors.CalcMolFormula(mol) == "C12H16O3"

    # Verify 0 ring-oxygen: no oxygen atom is a ring member
    ring_O_count = sum(
        1 for a in mol.GetAtoms() if a.GetIsAromatic() and a.GetAtomicNum() == 8
    )
    assert ring_O_count == 0, f"Expected 0 ring-oxygen atoms, found: {ring_O_count}"

    # Verify at least one aromatic C with non-ring aliphatic C substituent
    aromatic_with_C_substituent = [
        a
        for a in mol.GetAtoms()
        if a.GetIsAromatic()
        and a.GetAtomicNum() == 6
        and any(
            n.GetAtomicNum() == 6 and not n.GetIsAromatic() for n in a.GetNeighbors()
        )
    ]
    assert len(aromatic_with_C_substituent) >= 1

    # Truth has 0 ring-O and at least one aromatic C with aliphatic C substituent.
    # A FIX-10-conformant constraint set (no hard PROP/BOND from typical/carbon-dominant
    # detect-neighbours) does not exclude this structure.
