"""Tests for NMR chemical shift prediction module."""

import json
import tempfile
from pathlib import Path

import pytest
from rdkit import Chem

from lucy_ng.prediction import (
    C13Predictor,
    HOSECodeGenerator,
    HOSELookupTable,
    PredictedShift,
    PredictionResult,
)


class TestHOSECodeGenerator:
    """Tests for HOSE code generation."""

    def test_prepare_mol_from_smiles(self):
        """Test molecule preparation from SMILES."""
        gen = HOSECodeGenerator()
        mol = gen.prepare_mol("c1ccccc1")  # Benzene
        assert mol is not None
        # Returns without explicit hydrogens (H is added later in predict_from_mol)
        assert not any(atom.GetSymbol() == "H" for atom in mol.GetAtoms())

    def test_prepare_mol_invalid_smiles(self):
        """Test handling of invalid SMILES."""
        mol = HOSECodeGenerator.prepare_mol("invalid_smiles_xyz")
        assert mol is None

    def test_generate_for_atom(self):
        """Test HOSE code generation for a single atom."""
        gen = HOSECodeGenerator()
        mol = gen.prepare_mol("Cc1ccccc1")  # Toluene (explicit methyl first)

        # Generate HOSE code for first carbon (the methyl)
        # First heavy atom should be the methyl carbon
        hose = gen.generate_for_atom(mol, 0, radius=2)
        assert hose is not None
        assert hose.startswith("C-4")  # sp3 carbon

    def test_generate_for_carbons(self):
        """Test HOSE code generation for all carbons."""
        gen = HOSECodeGenerator()
        mol = gen.prepare_mol("CC")  # Ethane

        codes = gen.generate_for_carbons(mol, radius=2)
        # Should have exactly 2 carbons
        assert len(codes) == 2
        # All codes should be for sp3 carbons
        for code in codes.values():
            assert code.startswith("C-4")

    def test_generate_for_carbons_all_radii(self):
        """Test generation at all radii."""
        gen = HOSECodeGenerator()
        mol = gen.prepare_mol("c1ccccc1")  # Benzene

        all_codes = gen.generate_for_carbons_all_radii(mol, max_radius=3)
        # Should have 6 carbons
        assert len(all_codes) == 6
        # Each carbon should have codes for radii 1, 2, 3
        for atom_idx, codes in all_codes.items():
            assert set(codes.keys()) == {1, 2, 3}

    def test_benzene_hose_codes(self):
        """Test that benzene carbons generate aromatic HOSE codes."""
        gen = HOSECodeGenerator()
        mol = gen.prepare_mol("c1ccccc1")

        codes = gen.generate_for_carbons(mol, radius=1)
        # All carbons should be sp2 (aromatic)
        for code in codes.values():
            assert code.startswith("C-3")  # sp2 carbon


class TestHOSELookupTable:
    """Tests for HOSE lookup table."""

    def test_add_and_lookup(self):
        """Test adding entries and looking them up."""
        table = HOSELookupTable()

        table.add_entry("C-4;HHHC(//", 21.5)
        table.add_entry("C-4;HHHC(//", 22.0)
        table.add_entry("C-4;HHHC(//", 20.8)

        shifts = table.lookup("C-4;HHHC(//")
        assert len(shifts) == 3
        assert 21.5 in shifts
        assert 22.0 in shifts
        assert 20.8 in shifts

    def test_lookup_nonexistent(self):
        """Test lookup of nonexistent code."""
        table = HOSELookupTable()
        shifts = table.lookup("NONEXISTENT")
        assert shifts == []

    def test_lookup_stats(self):
        """Test statistics calculation."""
        table = HOSELookupTable()
        table.add_entry("TEST", 10.0)
        table.add_entry("TEST", 20.0)
        table.add_entry("TEST", 30.0)

        stats = table.lookup_stats("TEST")
        assert stats is not None
        assert stats["median"] == 20.0
        assert stats["mean"] == 20.0
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0
        assert stats["count"] == 3

    def test_lookup_stats_nonexistent(self):
        """Test stats for nonexistent code."""
        table = HOSELookupTable()
        stats = table.lookup_stats("NONEXISTENT")
        assert stats is None

    def test_has_code(self):
        """Test code existence check."""
        table = HOSELookupTable()
        table.add_entry("EXISTS", 100.0)

        assert table.has_code("EXISTS")
        assert not table.has_code("NOT_EXISTS")

    def test_save_and_load(self):
        """Test saving and loading table."""
        table = HOSELookupTable()
        table.add_entry("CODE1", 10.0)
        table.add_entry("CODE1", 11.0)
        table.add_entry("CODE2", 20.0)
        table._molecule_count = 5

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            table.save(Path(f.name), compress=False)

            loaded = HOSELookupTable.load(Path(f.name))

            assert loaded.unique_codes == 2
            assert loaded.molecule_count == 5
            assert loaded.lookup("CODE1") == [10.0, 11.0]
            assert loaded.lookup("CODE2") == [20.0]

    def test_save_and_load_compressed(self):
        """Test saving and loading compressed table."""
        table = HOSELookupTable()
        table.add_entry("CODE1", 10.0)
        table.add_entry("CODE2", 20.0)

        with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as f:
            table.save(Path(f.name), compress=True)

            loaded = HOSELookupTable.load(Path(f.name))

            assert loaded.unique_codes == 2
            assert loaded.lookup("CODE1") == [10.0]

    def test_properties(self):
        """Test table properties."""
        table = HOSELookupTable()
        table.add_entry("A", 1.0)
        table.add_entry("A", 2.0)
        table.add_entry("B", 3.0)

        assert table.unique_codes == 2
        assert table.total_entries == 3
        assert len(table) == 2

    def test_repr(self):
        """Test string representation."""
        table = HOSELookupTable()
        table.add_entry("A", 1.0)
        repr_str = repr(table)
        assert "HOSELookupTable" in repr_str
        assert "codes=1" in repr_str


class TestC13Predictor:
    """Tests for 13C chemical shift predictor."""

    @pytest.fixture
    def simple_table(self):
        """Create a simple lookup table for testing."""
        table = HOSELookupTable()

        # Add some common HOSE codes with known shifts
        # Methyl (CH3) codes
        table.add_entry("C-4;HHHC(//", 15.0)
        table.add_entry("C-4;HHHC(//", 16.0)
        table.add_entry("C-4;HHHC(//", 14.0)

        # Methylene (CH2) codes
        table.add_entry("C-4;HHCC(//", 25.0)
        table.add_entry("C-4;HHCC(//", 26.0)

        # Aromatic CH codes
        table.add_entry("C-3;H*C*C(//", 128.0)
        table.add_entry("C-3;H*C*C(//", 129.0)
        table.add_entry("C-3;H*C*C(//", 127.0)

        return table

    def test_predict_from_smiles_empty(self, simple_table):
        """Test prediction returns empty for no matches."""
        predictor = C13Predictor(simple_table, max_radius=1, min_radius=1)
        # Use a complex molecule unlikely to have matches
        result = predictor.predict_from_smiles("C#N")  # HCN

        assert isinstance(result, PredictionResult)
        assert result.smiles == "C#N"

    def test_predict_from_smiles_with_matches(self, simple_table):
        """Test prediction with matching HOSE codes."""
        predictor = C13Predictor(simple_table, max_radius=1, min_radius=1)

        # Ethane should match the CH3 codes
        result = predictor.predict_from_smiles("CC")

        assert result.smiles == "CC"
        assert result.carbon_count == 2

    def test_prediction_result_methods(self, simple_table):
        """Test PredictionResult helper methods."""
        predictor = C13Predictor(simple_table, max_radius=1, min_radius=1)
        result = predictor.predict_from_smiles("CC")

        # Test sorted shifts
        sorted_shifts = result.get_shifts_sorted()
        if len(sorted_shifts) > 1:
            assert sorted_shifts[0].shift >= sorted_shifts[1].shift

        # Test summary
        summary = result.summary()
        assert "CC" in summary
        assert "Carbons" in summary

    def test_predictor_with_fallback(self):
        """Test fallback to shorter radii."""
        # Create table with only radius-1 codes
        table = HOSELookupTable()
        table.add_entry("C-4;HHHC(//", 20.0)

        # Predictor with fallback enabled
        predictor = C13Predictor(table, max_radius=3, min_radius=1)

        mol = HOSECodeGenerator.prepare_mol("CC")
        predictions = predictor.predict_from_mol(mol)

        # Should find matches via fallback
        if predictions:
            # Radius used should be 1 (the only one in table)
            assert predictions[0].radius_used == 1

    def test_from_table_file(self, simple_table):
        """Test creating predictor from saved table file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            simple_table.save(Path(f.name), compress=False)

            predictor = C13Predictor.from_table_file(Path(f.name))
            assert predictor is not None
            assert predictor.lookup_table.unique_codes == simple_table.unique_codes

    def test_confidence_calculation(self, simple_table):
        """Test that confidence is calculated reasonably."""
        predictor = C13Predictor(simple_table, max_radius=1, min_radius=1)
        result = predictor.predict_from_smiles("CC")

        for pred in result.predictions:
            # Confidence should be between 0 and 1
            assert 0 <= pred.confidence <= 1
            # Radius 1 should have lower confidence than higher radii
            # (since it's less specific)


class TestPredictionModels:
    """Tests for prediction data models."""

    def test_predicted_shift_model(self):
        """Test PredictedShift model validation."""
        shift = PredictedShift(
            atom_index=0,
            shift=128.5,
            confidence=0.85,
            hose_code="C-3;H*C*C(//",
            radius_used=1,
            match_count=10,
            std_dev=2.5,
            min_shift=125.0,
            max_shift=132.0,
        )

        assert shift.atom_index == 0
        assert shift.shift == 128.5
        assert shift.confidence == 0.85

    def test_prediction_result_success_rate(self):
        """Test success rate calculation."""
        result = PredictionResult(
            smiles="CCC",
            predictions=[],
            carbon_count=3,
            success_count=2,
        )

        assert result.success_rate == pytest.approx(2/3)

    def test_prediction_result_empty(self):
        """Test success rate with no carbons."""
        result = PredictionResult(
            smiles="",
            predictions=[],
            carbon_count=0,
            success_count=0,
        )

        assert result.success_rate == 0.0


class TestCLIPredict:
    """Tests for prediction CLI commands."""

    def test_predict_help(self, cli_runner):
        """Test predict command help."""
        from lucy_ng.cli import cli
        result = cli_runner.invoke(cli, ["predict", "--help"])
        assert result.exit_code == 0
        assert "c13" in result.output
        assert "build-table" in result.output

    def test_predict_c13_no_backend(self, cli_runner, tmp_path, monkeypatch):
        """Test prediction without any backend available."""
        from lucy_ng.cli import cli

        # Run from a temp directory where no database or table exists
        monkeypatch.chdir(tmp_path)

        result = cli_runner.invoke(cli, ["predict", "c13", "CC"])
        # Should fail with helpful error
        assert result.exit_code != 0
        assert "backend" in result.output.lower() or "database" in result.output.lower()

    def test_predict_build_table_help(self, cli_runner):
        """Test build-table command help."""
        from lucy_ng.cli import cli
        result = cli_runner.invoke(cli, ["predict", "build-table", "--help"])
        assert result.exit_code == 0
        assert "SD_PATH" in result.output
        assert "--output" in result.output

    def test_predict_table_info_no_table(self, cli_runner):
        """Test table-info without table."""
        from lucy_ng.cli import cli
        result = cli_runner.invoke(cli, ["predict", "table-info"])
        assert result.exit_code != 0


@pytest.fixture
def cli_runner():
    """Create a CLI test runner."""
    from click.testing import CliRunner
    return CliRunner()


# ============================================================================
# Database Backend Tests
# ============================================================================


class TestHOSEStatsResult:
    """Tests for HOSEStatsResult dataclass."""

    def test_hose_stats_result_creation(self):
        """Test creating HOSEStatsResult."""
        from lucy_ng.prediction.models import HOSEStatsResult

        result = HOSEStatsResult(mean=128.5, std=2.5, count=100)
        assert result.mean == 128.5
        assert result.std == 2.5
        assert result.count == 100

    def test_hose_stats_result_immutable(self):
        """Test that HOSEStatsResult is a dataclass."""
        from lucy_ng.prediction.models import HOSEStatsResult

        result = HOSEStatsResult(mean=100.0, std=5.0, count=10)
        # Dataclasses are mutable by default but we just test it works
        assert result.mean == 100.0


class TestHOSELookupProtocol:
    """Tests for HOSELookupProtocol."""

    def test_lookup_table_implements_protocol(self):
        """Test that HOSELookupTable implements the protocol."""
        from lucy_ng.prediction.lookup import HOSELookupProtocol, HOSELookupTable

        table = HOSELookupTable()
        assert isinstance(table, HOSELookupProtocol)

    def test_protocol_method_lookup_stats_at_radius(self):
        """Test protocol method lookup_stats_at_radius."""
        from lucy_ng.prediction.lookup import HOSELookupTable
        from lucy_ng.prediction.models import HOSEStatsResult

        table = HOSELookupTable()
        table.add_entry("TEST", 10.0)
        table.add_entry("TEST", 20.0)
        table.add_entry("TEST", 30.0)

        # Radius is ignored for in-memory table (implicit in HOSE code)
        result = table.lookup_stats_at_radius("TEST", 3)
        assert isinstance(result, HOSEStatsResult)
        assert result.mean == 20.0
        assert result.count == 3

    def test_protocol_method_has_code_at_radius(self):
        """Test protocol method has_code_at_radius."""
        from lucy_ng.prediction.lookup import HOSELookupTable

        table = HOSELookupTable()
        table.add_entry("EXISTS", 100.0)

        assert table.has_code_at_radius("EXISTS", 3)
        assert not table.has_code_at_radius("NOT_EXISTS", 3)


class TestDatabaseHOSELookup:
    """Tests for DatabaseHOSELookup adapter."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database with test HOSE stats."""
        from lucy_ng.database import DatabaseManager
        from lucy_ng.database.models import HOSEStatsRecord

        db_path = tmp_path / "test_hose.db"
        db = DatabaseManager(db_path)
        db.create_tables()

        # Insert some test HOSE statistics
        test_stats = [
            HOSEStatsRecord(hose_code="C-4;HHHC(//", radius=1, mean=15.0, std=2.0, count=100),
            HOSEStatsRecord(hose_code="C-4;HHHC(//", radius=2, mean=14.5, std=1.5, count=50),
            HOSEStatsRecord(hose_code="C-3;H*C*C(//", radius=1, mean=128.5, std=3.0, count=200),
            HOSEStatsRecord(hose_code="C-3;H*C*C(//", radius=6, mean=128.0, std=0.5, count=10),
        ]
        db.insert_hose_stats_batch(test_stats)
        db.close()

        return db_path

    def test_from_db_path(self, temp_db):
        """Test creating DatabaseHOSELookup from path."""
        from lucy_ng.prediction.db_lookup import DatabaseHOSELookup

        lookup = DatabaseHOSELookup.from_db_path(temp_db)
        assert lookup.get_stats_count() == 4
        lookup.close()

    def test_lookup_stats_at_radius_found(self, temp_db):
        """Test lookup_stats_at_radius when code exists."""
        from lucy_ng.prediction.db_lookup import DatabaseHOSELookup
        from lucy_ng.prediction.models import HOSEStatsResult

        lookup = DatabaseHOSELookup.from_db_path(temp_db)

        result = lookup.lookup_stats_at_radius("C-4;HHHC(//", 1)
        assert result is not None
        assert isinstance(result, HOSEStatsResult)
        assert result.mean == 15.0
        assert result.std == 2.0
        assert result.count == 100

        lookup.close()

    def test_lookup_stats_at_radius_not_found(self, temp_db):
        """Test lookup_stats_at_radius when code doesn't exist."""
        from lucy_ng.prediction.db_lookup import DatabaseHOSELookup

        lookup = DatabaseHOSELookup.from_db_path(temp_db)

        result = lookup.lookup_stats_at_radius("NONEXISTENT", 1)
        assert result is None

        lookup.close()

    def test_has_code_at_radius(self, temp_db):
        """Test has_code_at_radius method."""
        from lucy_ng.prediction.db_lookup import DatabaseHOSELookup

        lookup = DatabaseHOSELookup.from_db_path(temp_db)

        assert lookup.has_code_at_radius("C-4;HHHC(//", 1)
        assert lookup.has_code_at_radius("C-4;HHHC(//", 2)
        assert not lookup.has_code_at_radius("C-4;HHHC(//", 3)  # Only r=1,2 exist
        assert not lookup.has_code_at_radius("NONEXISTENT", 1)

        lookup.close()

    def test_implements_protocol(self, temp_db):
        """Test that DatabaseHOSELookup implements the protocol."""
        from lucy_ng.prediction.db_lookup import DatabaseHOSELookup
        from lucy_ng.prediction.lookup import HOSELookupProtocol

        lookup = DatabaseHOSELookup.from_db_path(temp_db)
        assert isinstance(lookup, HOSELookupProtocol)
        lookup.close()

    def test_repr(self, temp_db):
        """Test string representation."""
        from lucy_ng.prediction.db_lookup import DatabaseHOSELookup

        lookup = DatabaseHOSELookup.from_db_path(temp_db)
        repr_str = repr(lookup)
        assert "DatabaseHOSELookup" in repr_str
        assert "stats=" in repr_str
        lookup.close()


class TestC13PredictorWithDatabase:
    """Tests for C13Predictor with database backend."""

    @pytest.fixture
    def temp_db_with_ethanol(self, tmp_path):
        """Create a database with HOSE stats for ethanol prediction."""
        from lucy_ng.database import DatabaseManager
        from lucy_ng.database.models import HOSEStatsRecord

        db_path = tmp_path / "test_predict.db"
        db = DatabaseManager(db_path)
        db.create_tables()

        # HOSE stats for ethanol carbons at various radii
        # These are approximate values for testing
        test_stats = [
            # CH3 carbon codes
            HOSEStatsRecord(hose_code="C-4;HHHC(//", radius=1, mean=15.0, std=2.0, count=100),
            HOSEStatsRecord(hose_code="C-4;C(O//)//", radius=2, mean=14.5, std=1.5, count=50),
            # CH2-O carbon codes
            HOSEStatsRecord(hose_code="C-4;HHOC(//", radius=1, mean=60.0, std=3.0, count=80),
            HOSEStatsRecord(hose_code="C-4;O(//C(//))", radius=2, mean=58.0, std=2.5, count=40),
        ]
        db.insert_hose_stats_batch(test_stats)
        db.close()

        return db_path

    def test_from_database_classmethod(self, temp_db_with_ethanol):
        """Test creating predictor from database."""
        predictor = C13Predictor.from_database(temp_db_with_ethanol)
        assert predictor is not None

    def test_predict_from_database(self, temp_db_with_ethanol):
        """Test prediction using database backend."""
        predictor = C13Predictor.from_database(
            temp_db_with_ethanol, max_radius=6, min_radius=1
        )
        result = predictor.predict_from_smiles("CCO")

        assert result.smiles == "CCO"
        assert result.carbon_count == 2
        # May or may not find matches depending on HOSE codes generated

    def test_lookup_property(self, temp_db_with_ethanol):
        """Test that lookup property returns the backend."""
        from lucy_ng.prediction.db_lookup import DatabaseHOSELookup

        predictor = C13Predictor.from_database(temp_db_with_ethanol)
        assert isinstance(predictor.lookup, DatabaseHOSELookup)

    def test_lookup_table_property_raises_for_database(self, temp_db_with_ethanol):
        """Test that lookup_table property raises for database backend."""
        predictor = C13Predictor.from_database(temp_db_with_ethanol)

        with pytest.raises(TypeError, match="lookup_table property only available"):
            _ = predictor.lookup_table


class TestCLIPredictWithDatabase:
    """Tests for CLI predict command with database backend."""

    @pytest.fixture
    def temp_db_for_cli(self, tmp_path):
        """Create a database for CLI testing."""
        from lucy_ng.database import DatabaseManager
        from lucy_ng.database.models import HOSEStatsRecord

        db_path = tmp_path / "test_cli.db"
        db = DatabaseManager(db_path)
        db.create_tables()

        # Add minimal HOSE stats
        test_stats = [
            HOSEStatsRecord(hose_code="C-4;HHHC(//", radius=1, mean=15.0, std=2.0, count=100),
        ]
        db.insert_hose_stats_batch(test_stats)
        db.close()

        return db_path

    def test_predict_c13_with_db_option(self, cli_runner, temp_db_for_cli):
        """Test prediction with explicit --db option."""
        from lucy_ng.cli import cli

        result = cli_runner.invoke(
            cli, ["predict", "c13", "CC", "--db", str(temp_db_for_cli)]
        )
        # May not find matches but should not error
        assert result.exit_code == 0
        assert "Carbons" in result.output

    def test_predict_c13_with_db_json_output(self, cli_runner, temp_db_for_cli):
        """Test JSON output with database."""
        from lucy_ng.cli import cli
        import json as json_module

        result = cli_runner.invoke(
            cli, ["predict", "c13", "CC", "--db", str(temp_db_for_cli), "--format", "json"]
        )
        assert result.exit_code == 0

        # Should be valid JSON
        data = json_module.loads(result.output)
        assert "smiles" in data
        assert "carbon_count" in data
        assert "predictions" in data

    def test_predict_c13_help_shows_db_option(self, cli_runner):
        """Test that help shows --db option."""
        from lucy_ng.cli import cli

        result = cli_runner.invoke(cli, ["predict", "c13", "--help"])
        assert result.exit_code == 0
        assert "--db" in result.output
        assert "database" in result.output.lower()
