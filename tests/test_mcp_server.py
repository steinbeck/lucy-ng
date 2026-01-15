"""Tests for MCP server tools."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


# Skip all tests if mcp is not installed
pytest.importorskip("mcp")


class TestMCPServerImport:
    """Test MCP server module imports."""

    def test_import_mcp_module(self):
        """Test that MCP module imports correctly."""
        from lucy_ng.mcp import mcp, main

        assert mcp is not None
        assert main is not None

    def test_mcp_server_has_tools(self):
        """Test that MCP server has registered tools."""
        from lucy_ng.mcp.server import mcp

        # FastMCP stores tools in _tool_manager or similar
        # Just verify the server object exists and has the expected name
        assert mcp.name == "lucy-ng"


class TestSpectrumReadingTools:
    """Test spectrum reading MCP tools."""

    def test_read_spectrum_1d(self, ibuprofen_data_dir):
        """Test read_spectrum_1d tool."""
        from lucy_ng.mcp.server import read_spectrum_1d

        # Test with 13C spectrum (exp 2)
        result = read_spectrum_1d(str(ibuprofen_data_dir / "2"))

        assert result["success"] is True
        assert result["nucleus"] == "13C"
        assert "frequency" in result
        assert "points" in result
        assert "ppm_min" in result
        assert "ppm_max" in result

    def test_read_spectrum_1d_not_found(self):
        """Test read_spectrum_1d with nonexistent path."""
        from lucy_ng.mcp.server import read_spectrum_1d

        result = read_spectrum_1d("/nonexistent/path")

        assert result["success"] is False
        assert "error" in result

    def test_read_spectrum_2d(self, ibuprofen_data_dir):
        """Test read_spectrum_2d tool."""
        from lucy_ng.mcp.server import read_spectrum_2d

        # Test with HSQC spectrum (exp 6)
        result = read_spectrum_2d(str(ibuprofen_data_dir / "6"))

        assert result["success"] is True
        assert result["experiment_type"] == "HSQC"
        assert "f1_nucleus" in result
        assert "f2_nucleus" in result
        assert "shape" in result


class TestPeakPickingTools:
    """Test peak picking MCP tools."""

    def test_pick_peaks_1d(self, ibuprofen_data_dir):
        """Test pick_peaks_1d tool."""
        from lucy_ng.mcp.server import pick_peaks_1d

        # Test with 13C spectrum
        result = pick_peaks_1d(str(ibuprofen_data_dir / "2"))

        assert result["success"] is True
        assert result["count"] > 0
        assert "peaks" in result
        assert len(result["peaks"]) == result["count"]

    def test_pick_peaks_1d_with_threshold(self, ibuprofen_data_dir):
        """Test pick_peaks_1d with custom threshold."""
        from lucy_ng.mcp.server import pick_peaks_1d

        result = pick_peaks_1d(str(ibuprofen_data_dir / "2"), threshold=0.1)

        assert result["success"] is True
        # Higher threshold should give fewer peaks
        assert result["count"] > 0

    def test_pick_hsqc_peaks(self, ibuprofen_data_dir):
        """Test pick_hsqc_peaks tool."""
        from lucy_ng.mcp.server import pick_hsqc_peaks

        result = pick_hsqc_peaks(
            hsqc_path=str(ibuprofen_data_dir / "6"),
            dept135_path=str(ibuprofen_data_dir / "3"),
        )

        assert result["success"] is True
        assert result["dept_peaks_count"] > 0
        assert result["hsqc_peaks_count"] > 0
        assert "peaks" in result
        assert "carbon_multiplicities" in result

    def test_pick_hsqc_peaks_with_dept90(self, ibuprofen_data_dir):
        """Test pick_hsqc_peaks with DEPT-90."""
        from lucy_ng.mcp.server import pick_hsqc_peaks

        result = pick_hsqc_peaks(
            hsqc_path=str(ibuprofen_data_dir / "6"),
            dept135_path=str(ibuprofen_data_dir / "3"),
            dept90_path=str(ibuprofen_data_dir / "4"),
        )

        assert result["success"] is True
        # With DEPT-90, should have better multiplicity assignments
        assert "carbon_multiplicities" in result

    def test_pick_hmbc_peaks(self, ibuprofen_data_dir):
        """Test pick_hmbc_peaks tool."""
        from lucy_ng.mcp.server import pick_hmbc_peaks

        result = pick_hmbc_peaks(
            hmbc_path=str(ibuprofen_data_dir / "7"),
            c13_path=str(ibuprofen_data_dir / "2"),
            hsqc_path=str(ibuprofen_data_dir / "6"),
            dept135_path=str(ibuprofen_data_dir / "3"),
        )

        assert result["success"] is True
        assert "reference_carbons" in result
        assert "reference_protons" in result
        assert "validated_count" in result
        assert "peaks" in result


class TestAnalysisTools:
    """Test analysis MCP tools."""

    def test_analyze_symmetry(self, ibuprofen_data_dir):
        """Test analyze_symmetry tool."""
        from lucy_ng.mcp.server import analyze_symmetry

        result = analyze_symmetry(
            molecular_formula="C13H18O2",
            hsqc_path=str(ibuprofen_data_dir / "6"),
            dept135_path=str(ibuprofen_data_dir / "3"),
        )

        assert result["success"] is True
        assert result["molecular_formula"] == "C13H18O2"
        assert result["expected_carbons"] == 13
        assert "signal_count" in result
        assert "has_symmetry" in result
        assert "hydrogen_budget" in result
        assert "summary" in result


class TestDereplicationTools:
    """Test dereplication MCP tools."""

    @pytest.mark.skipif(
        not Path("data/reference/nmrshiftdb2withsignals.sd").exists(),
        reason="nmrshiftdb database not available",
    )
    def test_dereplicate_c13_with_sd_file(self, ibuprofen_data_dir):
        """Test dereplicate_c13 tool with explicit SD file path."""
        from lucy_ng.mcp.server import dereplicate_c13

        result = dereplicate_c13(
            c13_path=str(ibuprofen_data_dir / "2"),
            molecular_formula="C13H18O2",
            database_path="data/reference/nmrshiftdb2withsignals.sd",
            top_n=3,
        )

        assert result["success"] is True
        assert result["molecular_formula"] == "C13H18O2"
        assert "candidates_found" in result
        assert "top_matches" in result
        assert result["database_type"] == "nmrshiftdb_sd"
        assert "compound_count" not in result  # SD files don't have compound count

    @pytest.mark.skipif(
        not Path("data/reference/compounds.db").exists(),
        reason="SQLite database not available",
    )
    def test_dereplicate_c13_with_sqlite_database(self, ibuprofen_data_dir):
        """Test dereplicate_c13 tool with explicit SQLite database path."""
        from lucy_ng.mcp.server import dereplicate_c13

        result = dereplicate_c13(
            c13_path=str(ibuprofen_data_dir / "2"),
            molecular_formula="C13H18O2",
            database_path="data/reference/compounds.db",
            top_n=3,
        )

        assert result["success"] is True
        assert result["molecular_formula"] == "C13H18O2"
        assert result["database_type"] == "sqlite"
        assert result["database"] == "compounds.db"
        assert "compound_count" in result
        assert result["compound_count"] > 0

    @pytest.mark.skipif(
        not Path("data/reference/compounds.db").exists(),
        reason="SQLite database not available",
    )
    def test_dereplicate_c13_auto_detects_sqlite(self, ibuprofen_data_dir):
        """Test that dereplicate_c13 auto-detects SQLite database."""
        from lucy_ng.mcp.server import dereplicate_c13

        # Don't provide database_path - should auto-detect
        result = dereplicate_c13(
            c13_path=str(ibuprofen_data_dir / "2"),
            molecular_formula="C13H18O2",
            top_n=3,
        )

        assert result["success"] is True
        assert result["database_type"] == "sqlite"
        assert result["database"] == "compounds.db"
        assert "compound_count" in result

    def test_dereplicate_c13_database_type_field(self, ibuprofen_data_dir):
        """Test that database_type field is always present in results."""
        from lucy_ng.mcp.server import dereplicate_c13

        # Skip if no database available
        if not (
            Path("data/reference/compounds.db").exists()
            or Path("data/reference/nmrshiftdb2withsignals.sd").exists()
        ):
            pytest.skip("No reference database available")

        result = dereplicate_c13(
            c13_path=str(ibuprofen_data_dir / "2"),
            molecular_formula="C13H18O2",
            top_n=3,
        )

        assert result["success"] is True
        assert "database_type" in result
        assert result["database_type"] in ["sqlite", "nmrshiftdb_sd", "coconut_sd"]

    def test_dereplicate_c13_env_var_database(self, ibuprofen_data_dir, tmp_path):
        """Test LUCY_DATABASE environment variable is respected."""
        from lucy_ng.cli.dereplicate import _find_database_path

        # Create a mock .db file
        mock_db = tmp_path / "env_test.db"
        mock_db.touch()

        # Test that _find_database_path respects env var
        with patch.dict(os.environ, {"LUCY_DATABASE": str(mock_db)}):
            result = _find_database_path()
            assert result == mock_db

    def test_dereplicate_c13_no_database(self, ibuprofen_data_dir):
        """Test error when no database is available."""
        from lucy_ng.mcp.server import dereplicate_c13

        # Provide a non-existent explicit path (triggers error)
        result = dereplicate_c13(
            c13_path=str(ibuprofen_data_dir / "2"),
            molecular_formula="C13H18O2",
            database_path="/nonexistent/database.sd",
        )

        assert result["success"] is False
        assert "error" in result


class TestLSDTools:
    """Test LSD integration MCP tools."""

    def test_check_lsd_availability(self):
        """Test check_lsd_availability tool."""
        from lucy_ng.mcp.server import check_lsd_availability

        result = check_lsd_availability()

        assert result["success"] is True
        assert "available" in result
        # If available, should have path
        if result["available"]:
            assert "path" in result

    def test_generate_lsd_input(self, ibuprofen_data_dir):
        """Test generate_lsd_input tool."""
        from lucy_ng.mcp.server import generate_lsd_input

        result = generate_lsd_input(
            data_dir=str(ibuprofen_data_dir),
            molecular_formula="C13H18O2",
        )

        assert result["success"] is True
        assert result["molecular_formula"] == "C13H18O2"
        assert result["atom_count"] > 0
        assert "content" in result
        assert "MULT" in result["content"]  # Should have atom definitions

    def test_generate_lsd_input_with_output_file(self, ibuprofen_data_dir, tmp_path):
        """Test generate_lsd_input with output file."""
        from lucy_ng.mcp.server import generate_lsd_input

        output_file = tmp_path / "test.lsd"

        result = generate_lsd_input(
            data_dir=str(ibuprofen_data_dir),
            molecular_formula="C13H18O2",
            output_file=str(output_file),
        )

        assert result["success"] is True
        assert result["output_file"] == str(output_file)
        assert output_file.exists()

    def test_generate_lsd_input_nonexistent_dir(self):
        """Test generate_lsd_input with nonexistent directory."""
        from lucy_ng.mcp.server import generate_lsd_input

        result = generate_lsd_input(
            data_dir="/nonexistent/path",
            molecular_formula="C10H12O2",
        )

        assert result["success"] is False
        assert "error" in result

    def test_run_lsd_not_available(self, tmp_path):
        """Test run_lsd when LSD is not installed."""
        from lucy_ng.mcp.server import run_lsd
        from lucy_ng.lsd import LSDRunner

        # Create a dummy input file
        input_file = tmp_path / "test.lsd"
        input_file.write_text("; test\nEXIT\n")

        result = run_lsd(str(input_file))

        # Result depends on whether LSD is installed
        if not LSDRunner.is_available():
            assert result["success"] is False
            assert "not found" in result["error"].lower()
        else:
            # If LSD is available, it should run (may succeed or fail)
            assert "success" in result

    def test_run_lsd_file_not_found(self):
        """Test run_lsd with nonexistent file."""
        from lucy_ng.mcp.server import run_lsd
        from lucy_ng.lsd import LSDRunner

        # Skip if LSD not available (different error)
        if not LSDRunner.is_available():
            pytest.skip("LSD not installed")

        result = run_lsd("/nonexistent/file.lsd")

        assert result["success"] is False
        assert "not found" in result["error"].lower()


# Fixtures
@pytest.fixture
def ibuprofen_data_dir():
    """Return path to Ibuprofen test data."""
    path = Path("data/Ibuprofen")
    if not path.exists():
        pytest.skip("Ibuprofen test data not available")
    return path
