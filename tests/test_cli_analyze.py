"""Tests for CLI analyze commands."""

import json

from click.testing import CliRunner

from ailsa.cli.analyze import analyze


class TestAnalyzeSymmetry:
    """Tests for ailsa analyze symmetry command."""

    def test_analyze_symmetry_text(self) -> None:
        """Test symmetry analysis with text output."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            ["symmetry", "C13H18O2", "data/Ibuprofen/2"],
        )
        assert result.exit_code == 0
        assert "Symmetry Analysis" in result.output
        assert "C13H18O2" in result.output
        assert "Expected carbons:" in result.output
        assert "Observed peaks:" in result.output
        assert "Difference:" in result.output

    def test_analyze_symmetry_calculates_difference(self) -> None:
        """Test that symmetry analysis calculates carbon difference."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            ["symmetry", "C13H18O2", "data/Ibuprofen/2"],
        )
        assert result.exit_code == 0
        # Should show expected vs observed comparison
        assert "Expected carbons:" in result.output
        assert "Observed peaks:" in result.output
        assert "Difference:" in result.output
        # Either suggests equivalents or warns about more peaks
        assert ("equivalent" in result.output.lower() or "Warning:" in result.output)

    def test_analyze_symmetry_json(self) -> None:
        """Test symmetry analysis with JSON output."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            [
                "symmetry",
                "C13H18O2",
                "data/Ibuprofen/2",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["formula"] == "C13H18O2"
        assert "expected_carbons" in data
        assert "observed_peaks" in data
        assert "difference" in data
        assert data["expected_carbons"] == 13

    def test_analyze_symmetry_json_structure(self) -> None:
        """Test JSON output has correct structure."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            [
                "symmetry",
                "C13H18O2",
                "data/Ibuprofen/2",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)

        # Check basic structure
        assert "formula" in data
        assert "expected_carbons" in data
        assert "observed_peaks" in data
        assert "difference" in data
        assert isinstance(data["expected_carbons"], int)
        assert isinstance(data["observed_peaks"], int)
        assert isinstance(data["difference"], int)

    def test_analyze_symmetry_invalid_path(self) -> None:
        """Test error on invalid paths."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            ["symmetry", "C13H18O2", "data/NonExistent/6"],
        )
        assert result.exit_code != 0

    # --- FIX-08 overcount alarm tests ---

    def test_analyze_symmetry_overcount_text_contains_warning(self) -> None:
        """Overcount: text output contains 'Warning:' (case-sensitive) and 'more signals than carbons'."""
        runner = CliRunner()
        # C4H8 has 4 expected carbons; Ibuprofen/2 has ~13 observed → overcount
        result = runner.invoke(
            analyze,
            ["symmetry", "C4H8", "data/Ibuprofen/2"],
        )
        assert result.exit_code == 0
        assert "Warning:" in result.output  # case-sensitive assertion
        assert "more signals than carbons" in result.output

    def test_analyze_symmetry_overcount_json_alarm_true(self) -> None:
        """Overcount: JSON output has overcount_alarm=true and overcount_excess>0."""
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            ["symmetry", "C4H8", "data/Ibuprofen/2", "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["overcount_alarm"] is True
        assert data["overcount_excess"] > 0

    def test_analyze_symmetry_normal_json_alarm_false(self) -> None:
        """Normal case (no overcount): JSON output has overcount_alarm=false.

        Uses C200H300O5 so expected carbons (200) always exceeds any realistic
        peak count from the Ibuprofen/2 spectrum.
        """
        runner = CliRunner()
        result = runner.invoke(
            analyze,
            ["symmetry", "C200H300O5", "data/Ibuprofen/2", "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["overcount_alarm"] is False
        assert data["overcount_excess"] == 0
