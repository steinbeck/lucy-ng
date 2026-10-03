"""Tests for CLI LSD commands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.lsd import lsd


# ---------------------------------------------------------------------------
# TestPerformRanking — direct import tests (no Click context needed)
# ---------------------------------------------------------------------------


class TestPerformRanking:
    """Tests for the _perform_ranking module-private helper."""

    def test_importable_without_click_context(self) -> None:
        """_perform_ranking must be importable directly from ailsa.cli.lsd."""
        from ailsa.cli.lsd import _perform_ranking  # noqa: F401
        assert callable(_perform_ranking)

    def test_callable_with_smiles_file_and_shifts(self, tmp_path: Path) -> None:
        """_perform_ranking must be callable without any Click context."""
        from ailsa.cli.lsd import _perform_ranking

        # Write a minimal SMILES file (ethanol)
        smiles_file = tmp_path / "solutions.smi"
        smiles_file.write_text("CCO\n")

        # Must not raise — just needs to find/load the HOSE table
        # If the table is available, it will run; if not, SystemExit(1) is acceptable
        try:
            _perform_ranking(
                smiles_file=str(smiles_file),
                experimental_shifts=[18.0, 58.0],
                top=5,
                tolerance=3.0,
                table=None,
                output_format="text",
            )
        except SystemExit as exc:
            # Table not available in test environment is acceptable
            assert exc.code == 1
        except Exception as exc:
            pytest.fail(f"_perform_ranking raised unexpected exception: {exc}")

    def test_empty_smiles_file_raises_system_exit(self, tmp_path: Path) -> None:
        """Empty SMILES file must raise SystemExit(1) — not an unhandled exception."""
        from ailsa.cli.lsd import _perform_ranking

        smiles_file = tmp_path / "empty.smi"
        smiles_file.write_text("")

        with pytest.raises(SystemExit) as exc_info:
            _perform_ranking(
                smiles_file=str(smiles_file),
                experimental_shifts=[18.0, 58.0],
                top=5,
                tolerance=3.0,
                table=None,
                output_format="text",
            )
        assert exc_info.value.code == 1

    def test_json_output_format_returns_dict(self, tmp_path: Path) -> None:
        """_perform_ranking with output_format='json' must return a dict (not None)."""
        from ailsa.cli.lsd import _perform_ranking

        smiles_file = tmp_path / "solutions.smi"
        smiles_file.write_text("CCO\n")

        # This test only runs fully if a HOSE table is available
        try:
            result = _perform_ranking(
                smiles_file=str(smiles_file),
                experimental_shifts=[18.0, 58.0],
                top=5,
                tolerance=3.0,
                table=None,
                output_format="json",
            )
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert "total_solutions" in result
        except SystemExit:
            pass  # table not available — acceptable in CI


class TestLSDCheck:
    """Tests for ailsa lsd check command."""

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


class TestLSDRun:
    """Tests for ailsa lsd run command."""

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
    """Tests for ailsa lsd analyze command."""

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
