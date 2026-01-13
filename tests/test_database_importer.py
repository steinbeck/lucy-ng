"""Tests for database importer module."""

from __future__ import annotations

from pathlib import Path

import pytest

from lucy_ng.database import DatabaseImporter, DatabaseManager, ImportResult
from lucy_ng.dereplication.nmrshiftdb import CarbonSignal, HydrogenCount, NMRShiftDBEntry

# Path to test data
DATA_DIR = Path(__file__).parent.parent / "data"
NMRSHIFTDB_FILE = DATA_DIR / "reference" / "nmrshiftdb2withsignals.sd"
COCONUT_FILE = DATA_DIR / "reference" / "predicted_coconut.sdf"


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_default_values(self) -> None:
        """Test ImportResult default values."""
        result = ImportResult(source="test")
        assert result.source == "test"
        assert result.compounds_imported == 0
        assert result.compounds_skipped == 0
        assert result.errors == []
        assert result.elapsed_seconds == 0.0

    def test_str_representation(self) -> None:
        """Test ImportResult string output."""
        result = ImportResult(
            source="nmrshiftdb",
            compounds_imported=1000,
            compounds_skipped=5,
            errors=["error1", "error2"],
            elapsed_seconds=10.5,
        )
        output = str(result)

        assert "nmrshiftdb" in output
        assert "1000" in output
        assert "5" in output
        assert "2 errors" in output
        assert "10.5s" in output

    def test_errors_list_independent(self) -> None:
        """Test that errors list is independent between instances."""
        result1 = ImportResult(source="a")
        result2 = ImportResult(source="b")

        result1.errors.append("error")
        assert len(result2.errors) == 0


class TestDatabaseImporter:
    """Tests for DatabaseImporter class."""

    def test_entry_to_records(self, tmp_path: Path) -> None:
        """Test conversion from NMRShiftDBEntry to database records."""
        entry = NMRShiftDBEntry(
            nmrshiftdb_id=123,
            name="Test Compound",
            molecular_formula="C10H12O2",
            carbon_count=10,
            inchi="InChI=1S/C10H12O2/...",
            inchi_key="TESTKEY",
            signals=[
                CarbonSignal(shift=125.0, hydrogen_count=HydrogenCount.CH, atom_index=1),
                CarbonSignal(shift=130.0, hydrogen_count=HydrogenCount.C, atom_index=2),
            ],
        )

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            compound, shifts = importer._entry_to_records(entry, "test")

            assert compound.name == "Test Compound"
            assert compound.formula == "C10H12O2"
            assert compound.source == "test"
            assert compound.carbon_count == 10
            assert len(shifts) == 2
            assert shifts[0].shift_ppm == 125.0
            assert shifts[0].hydrogen_count == 1
            assert shifts[1].shift_ppm == 130.0
            assert shifts[1].hydrogen_count == 0

    def test_parse_coconut_spectrum(self, tmp_path: Path) -> None:
        """Test parsing COCONUT CNMR_SHIFTS format."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            # Format: 'idx:atom|shift;idx:atom|shift;...'
            field = "0:2|73.89;1:3|101.13;2:5|154.84"
            mult_map = {2: 1, 3: 0, 5: 0}  # CH, C, C

            shifts = importer._parse_coconut_spectrum(field, mult_map)

            assert len(shifts) == 3
            assert shifts[0].shift_ppm == pytest.approx(73.89)
            assert shifts[0].atom_index == 2
            assert shifts[0].hydrogen_count == 1  # CH
            assert shifts[1].shift_ppm == pytest.approx(101.13)
            assert shifts[1].atom_index == 3
            assert shifts[1].hydrogen_count == 0  # C
            assert shifts[2].shift_ppm == pytest.approx(154.84)
            assert shifts[2].atom_index == 5
            assert shifts[2].hydrogen_count == 0  # C

    def test_parse_mult_field(self, tmp_path: Path) -> None:
        """Test parsing multiplicity field."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            field = "5\t154.84\n6\t108.70\n7\t153.41"
            indices = importer._parse_mult_field(field)

            assert indices == [5, 6, 7]

    def test_parse_mult_field_empty(self, tmp_path: Path) -> None:
        """Test parsing empty multiplicity field."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            indices = importer._parse_mult_field("")
            assert indices == []

    def test_count_carbons(self, tmp_path: Path) -> None:
        """Test carbon counting from formula."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            assert importer._count_carbons("C13H18O2") == 13
            assert importer._count_carbons("C6H12O6") == 6
            assert importer._count_carbons("CH4") == 1
            assert importer._count_carbons("H2O") == 0

    def test_import_file_not_found(self, tmp_path: Path) -> None:
        """Test import with non-existent file."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            result = importer.import_nmrshiftdb(
                tmp_path / "nonexistent.sd",
            )

            assert result.compounds_imported == 0
            assert len(result.errors) == 1
            assert "not found" in result.errors[0].lower()

    def test_progress_callback_called(self, tmp_path: Path) -> None:
        """Test that progress callback is invoked during import."""
        # Create a minimal test SD file
        sd_content = """TestMol
  Test

  1  0  0  0  0  0  0  0  0  0  1 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
M  END
>  <Spectrum 13C 0>
25.0;0.0Q;1

>  <INChI>
InChI=1S/CH4/h1H4

>  <INChI key>
VNWKTOKETHGBQD-UHFFFAOYSA-N

$$$$
TestMol2
  Test

  1  0  0  0  0  0  0  0  0  0  1 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
M  END
>  <Spectrum 13C 0>
30.0;0.0Q;1

>  <INChI>
InChI=1S/CH4/h1H4

>  <INChI key>
VNWKTOKETHGBQD-UHFFFAOYSA-N

$$$$
"""
        sd_file = tmp_path / "test.sd"
        sd_file.write_text(sd_content)

        db_path = tmp_path / "test.db"
        progress_calls: list[tuple[int, int]] = []

        def track_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            result = importer.import_nmrshiftdb(
                sd_file,
                batch_size=1,
                progress_callback=track_progress,
            )

            # Should have imported 2 compounds
            assert result.compounds_imported == 2
            # Should have made progress calls
            assert len(progress_calls) >= 1
            # Total should be 2 entries
            if progress_calls:
                assert progress_calls[-1][1] == 2

    def test_batch_insert(self, tmp_path: Path) -> None:
        """Test that batch insert works correctly."""
        # Create a test SD file with multiple entries
        sd_content = ""
        for i in range(5):
            sd_content += f"""TestMol{i}
  Test

  1  0  0  0  0  0  0  0  0  0  1 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
M  END
>  <Spectrum 13C 0>
{25.0 + i};0.0Q;1

>  <INChI>
InChI=1S/CH4/h1H4

>  <INChI key>
VNWKTOKETHGBQD-UHFFFAOYSA-N

$$$$
"""
        sd_file = tmp_path / "test.sd"
        sd_file.write_text(sd_content)

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            result = importer.import_nmrshiftdb(
                sd_file,
                batch_size=2,  # Small batch size to test batching
            )

            assert result.compounds_imported == 5
            assert db.get_compound_count() == 5


class TestDatabaseImporterIntegration:
    """Integration tests that require actual data files."""

    @pytest.mark.skipif(not NMRSHIFTDB_FILE.exists(), reason="NMRShiftDB file not available")
    def test_import_nmrshiftdb_real(self, tmp_path: Path) -> None:
        """Test importing actual NMRShiftDB file (first 100 entries)."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            result = importer.import_nmrshiftdb(
                NMRSHIFTDB_FILE,
                batch_size=100,
            )

            # Should have imported many compounds
            assert result.compounds_imported > 100
            assert db.get_compound_count() > 100
            assert result.source == "nmrshiftdb"

    @pytest.mark.skipif(not COCONUT_FILE.exists(), reason="COCONUT file not available")
    def test_import_coconut_real(self, tmp_path: Path) -> None:
        """Test importing actual COCONUT file (partial)."""
        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as db:
            db.create_tables()
            importer = DatabaseImporter(db)

            # This will import until we get some data
            # Note: Full import takes too long for tests
            result = importer.import_coconut(
                COCONUT_FILE,
                batch_size=1000,
            )

            # Should have imported many compounds
            assert result.compounds_imported > 0
            assert result.source == "coconut"
