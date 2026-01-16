"""Tests for CLI LSD commands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from lucy_ng.cli.lsd import lsd


class TestLSDCheck:
    """Tests for lucy lsd check command."""

    def test_lsd_check(self) -> None:
        """Test LSD availability check."""
        runner = CliRunner()
        result = runner.invoke(lsd, ["check"])
        # May pass or fail depending on LSD installation
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            assert "available" in result.output.lower()
        else:
            assert "not" in result.output.lower()


class TestLSDGenerate:
    """Tests for lucy lsd generate command."""

    def test_generate_text(self) -> None:
        """Test LSD input generation with text output."""
        runner = CliRunner()
        result = runner.invoke(lsd, ["generate", "data/Ibuprofen", "C13H18O2"])
        assert result.exit_code == 0
        # Should contain LSD commands
        assert "MULT" in result.output
        # Should have header comments
        assert "lucy-ng" in result.output
        assert "C13H18O2" in result.output

    def test_generate_json(self) -> None:
        """Test LSD input generation with JSON output."""
        runner = CliRunner()
        result = runner.invoke(
            lsd, ["generate", "data/Ibuprofen", "C13H18O2", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["molecular_formula"] == "C13H18O2"
        assert "atom_count" in data
        assert "correlation_count" in data
        assert "lsd_content" in data
        assert "MULT" in data["lsd_content"]

    def test_generate_experiments_detected(self) -> None:
        """Test that experiments are correctly detected."""
        runner = CliRunner()
        result = runner.invoke(
            lsd, ["generate", "data/Ibuprofen", "C13H18O2", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Should detect key experiments
        assert "experiments_found" in data
        assert "HSQC" in data["experiments_found"]
        assert "DEPT135" in data["experiments_found"]

    def test_generate_to_file(self, tmp_path: Path) -> None:
        """Test writing LSD input to file."""
        output_file = tmp_path / "test.lsd"
        runner = CliRunner()
        result = runner.invoke(
            lsd,
            ["generate", "data/Ibuprofen", "C13H18O2", "-o", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "MULT" in content

    def test_generate_missing_hsqc(self) -> None:
        """Test error when HSQC not found."""
        runner = CliRunner()
        # Use a directory that doesn't have required experiments
        result = runner.invoke(lsd, ["generate", "data/Ibuprofen/1", "C13H18O2"])
        assert result.exit_code != 0
        assert "HSQC" in result.output or "DEPT" in result.output


class TestLSDRun:
    """Tests for lucy lsd run command."""

    def test_run_without_lsd(self, tmp_path: Path) -> None:
        """Test error when LSD not installed."""
        # Create a minimal LSD input file
        lsd_file = tmp_path / "test.lsd"
        lsd_file.write_text("; Test\nMULT 1 C 3 3\nEXIT\n")

        runner = CliRunner()
        result = runner.invoke(lsd, ["run", str(lsd_file)])

        # Should either succeed (if LSD installed) or fail with clear message
        if result.exit_code != 0:
            assert "not installed" in result.output.lower() or "not in path" in result.output.lower()

    def test_run_help(self) -> None:
        """Test run command help."""
        runner = CliRunner()
        result = runner.invoke(lsd, ["run", "--help"])
        assert result.exit_code == 0
        assert "--timeout" in result.output
        assert "--output-dir" in result.output


class TestLSDAnalyze:
    """Tests for lucy lsd analyze command."""

    def test_analyze_help(self) -> None:
        """Test analyze command help."""
        runner = CliRunner()
        result = runner.invoke(lsd, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "SOL_FILE" in result.output
        assert "LSD_FILE" in result.output
        assert "--solution" in result.output

    def test_analyze_text_output(self, tmp_path: Path) -> None:
        """Test analyze with text output."""
        # Create minimal .sol file
        sol_file = tmp_path / "test.sol"
        sol_file.write_text("""OUTLSD
2 1
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
0
""")
        # Create minimal .lsd file
        lsd_file = tmp_path / "test.lsd"
        lsd_file.write_text("""MULT 1 C 3 3
MULT 2 C 3 3
SHIX 1 20.0
SHIX 2 30.0
HSQC 1 1
HSQC 2 2
HMBC 1 2
EXIT
""")

        runner = CliRunner()
        result = runner.invoke(lsd, ["analyze", str(sol_file), str(lsd_file)])
        assert result.exit_code == 0
        assert "Solution 1" in result.output
        assert "²J" in result.output

    def test_analyze_json_output(self, tmp_path: Path) -> None:
        """Test analyze with JSON output."""
        # Create minimal .sol file
        sol_file = tmp_path / "test.sol"
        sol_file.write_text("""OUTLSD
2 1
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
0
""")
        # Create minimal .lsd file
        lsd_file = tmp_path / "test.lsd"
        lsd_file.write_text("""MULT 1 C 3 3
MULT 2 C 3 3
HSQC 1 1
HSQC 2 2
HMBC 1 2
EXIT
""")

        runner = CliRunner()
        result = runner.invoke(lsd, ["analyze", str(sol_file), str(lsd_file), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "solutions" in data
        assert len(data["solutions"]) == 1
        assert data["solutions"][0]["solution_number"] == 1
        assert data["solutions"][0]["all_2j_3j"] is True

    def test_analyze_specific_solution(self, tmp_path: Path) -> None:
        """Test analyzing a specific solution."""
        # Create .sol file with 2 solutions
        sol_file = tmp_path / "test.sol"
        sol_file.write_text("""OUTLSD
2 1
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
2 2
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
0
""")
        lsd_file = tmp_path / "test.lsd"
        lsd_file.write_text("""MULT 1 C 3 3
MULT 2 C 3 3
HSQC 1 1
HSQC 2 2
HMBC 1 2
EXIT
""")

        runner = CliRunner()
        result = runner.invoke(
            lsd, ["analyze", str(sol_file), str(lsd_file), "--solution", "2", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["solutions"]) == 1
        assert data["solutions"][0]["solution_number"] == 2
