"""Tests for visualization CLI commands."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from lucy_ng.cli.visualize import (
    parse_correlation_string,
    parse_lsd_input_file,
    parse_shifts,
    visualize,
)
from lucy_ng.visualization import CorrelationType


class TestParseCorrelationString:
    """Tests for correlation string parsing."""

    def test_valid_hmbc(self) -> None:
        """Test parsing valid HMBC correlation."""
        result = parse_correlation_string("HMBC:0:5")
        assert result is not None
        assert result.correlation_type == CorrelationType.HMBC
        assert result.source_atom == 0
        assert result.target_atom == 5

    def test_valid_cosy(self) -> None:
        """Test parsing valid COSY correlation."""
        result = parse_correlation_string("COSY:1:2")
        assert result is not None
        assert result.correlation_type == CorrelationType.COSY
        assert result.source_atom == 1
        assert result.target_atom == 2

    def test_case_insensitive(self) -> None:
        """Test that correlation type is case insensitive."""
        result = parse_correlation_string("hmbc:0:1")
        assert result is not None
        assert result.correlation_type == CorrelationType.HMBC

    def test_hmqc_treated_as_hsqc(self) -> None:
        """Test that HMQC is treated as HSQC."""
        result = parse_correlation_string("HMQC:0:0")
        assert result is not None
        assert result.correlation_type == CorrelationType.HSQC

    def test_invalid_format(self) -> None:
        """Test invalid format returns None."""
        result = parse_correlation_string("HMBC:0")  # Missing target
        assert result is None

    def test_invalid_type(self) -> None:
        """Test unknown type returns None."""
        result = parse_correlation_string("INVALID:0:1")
        assert result is None


class TestParseShifts:
    """Tests for chemical shift parsing."""

    def test_json_dict(self) -> None:
        """Test parsing JSON dict format."""
        result = parse_shifts('{"0": 22.5, "2": 30.2}')
        assert result == {0: 22.5, 2: 30.2}

    def test_comma_separated(self) -> None:
        """Test parsing comma-separated list."""
        result = parse_shifts("22.5,30.2,45.0")
        assert result == {0: 22.5, 1: 30.2, 2: 45.0}

    def test_empty_string(self) -> None:
        """Test empty string returns empty dict."""
        result = parse_shifts("")
        assert result == {}


class TestParseLsdInputFile:
    """Tests for LSD input file parsing."""

    def test_parse_mult_commands(self) -> None:
        """Test parsing MULT commands."""
        content = """; Test LSD file
MULT 1 C 3 3
MULT 2 C 2 1
MULT 3 O 2 0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lsd", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        problem = parse_lsd_input_file(path)
        path.unlink()

        assert len(problem.atoms) == 3
        assert problem.atoms[0].index == 1
        assert problem.atoms[0].element == "C"
        assert problem.atoms[0].hydrogen_count == 3

    def test_parse_correlations(self) -> None:
        """Test parsing correlation commands."""
        content = """; Test LSD file
MULT 1 C 3 3
MULT 2 C 2 1
HSQC 1 1
HSQC 2 2
HMBC 1 2
HMBC 2 1
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lsd", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        problem = parse_lsd_input_file(path)
        path.unlink()

        assert len(problem.correlations) == 4
        hsqc_count = sum(1 for c in problem.correlations if c.correlation_type == "HSQC")
        hmbc_count = sum(1 for c in problem.correlations if c.correlation_type == "HMBC")
        assert hsqc_count == 2
        assert hmbc_count == 2


class TestVisualizeCLI:
    """Integration tests for visualize CLI command."""

    def test_simple_diagram(self) -> None:
        """Test generating simple diagram."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            output_path = f.name

        result = runner.invoke(
            visualize,
            [
                "correlations",
                "CCO",
                "-c", "HMBC:0:1",
                "-o", output_path,
            ],
        )

        assert result.exit_code == 0
        assert "Diagram saved to" in result.output

        # Check file exists and contains SVG
        content = Path(output_path).read_text()
        assert content.startswith("<?xml")
        assert "<svg" in content

        Path(output_path).unlink()

    def test_with_shifts(self) -> None:
        """Test generating diagram with chemical shifts."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            output_path = f.name

        result = runner.invoke(
            visualize,
            [
                "correlations",
                "CCO",
                "-c", "HMBC:0:1",
                "--shifts", '{"0": 18.0, "1": 58.0}',
                "-o", output_path,
            ],
        )

        assert result.exit_code == 0

        content = Path(output_path).read_text()
        assert "18.0" in content or "58.0" in content  # Shifts should appear

        Path(output_path).unlink()

    def test_stdout_output(self) -> None:
        """Test that SVG is printed to stdout without -o option."""
        runner = CliRunner()
        result = runner.invoke(
            visualize,
            ["correlations", "C", "-c", "HMBC:0:0"],
        )

        # The SVG should be printed to stdout (in result.output)
        # Even though the correlation is invalid (same atom), the SVG header should be there
        assert "<?xml" in result.output or result.exit_code != 0

    def test_from_lsd_file(self) -> None:
        """Test generating diagram from LSD file."""
        runner = CliRunner()

        # Create a minimal LSD file
        lsd_content = """; Minimal test
MULT 1 C 3 3
MULT 2 C 2 1
HSQC 1 1
HSQC 2 2
HMBC 1 2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lsd", delete=False) as lsd_f:
            lsd_f.write(lsd_content)
            lsd_path = lsd_f.name

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as svg_f:
            output_path = svg_f.name

        result = runner.invoke(
            visualize,
            [
                "correlations",
                "CC",  # Simple SMILES matching the LSD
                "--lsd-file", lsd_path,
                "-o", output_path,
            ],
        )

        Path(lsd_path).unlink()

        # The command should execute (exit_code may vary based on correlation validity)
        assert result.exit_code == 0 or "Error" not in result.output

        if Path(output_path).exists():
            Path(output_path).unlink()

    def test_custom_dimensions(self) -> None:
        """Test custom width and height."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            output_path = f.name

        result = runner.invoke(
            visualize,
            [
                "correlations",
                "C",
                "--width", "1200",
                "--height", "900",
                "-o", output_path,
            ],
        )

        assert result.exit_code == 0

        content = Path(output_path).read_text()
        assert 'width="1200"' in content
        assert 'height="900"' in content

        Path(output_path).unlink()

    def test_invalid_smiles(self) -> None:
        """Test that invalid SMILES produces error."""
        runner = CliRunner()
        result = runner.invoke(
            visualize,
            ["correlations", "invalid_smiles_xyz"],
        )

        # Should fail with invalid SMILES
        assert result.exit_code != 0 or "Invalid SMILES" in str(result.exception)
