"""Tests for CLI main module."""

import subprocess
import sys

from click.testing import CliRunner

from lucy_ng import __version__
from lucy_ng.cli import cli


class TestCLIMain:
    """Tests for CLI entry point."""

    def test_version(self) -> None:
        """Test --version returns correct version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help(self) -> None:
        """Test --help shows usage info."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "lucy-ng" in result.output
        assert "Computer-Assisted Structure Elucidation" in result.output

    def test_no_args(self) -> None:
        """Test running with no arguments shows usage."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        # Click shows usage and exits with code 0 or 2 depending on config
        assert "Usage:" in result.output

    def test_invalid_command(self) -> None:
        """Test invalid command shows error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["invalid-command"])
        assert result.exit_code != 0
        assert "No such command" in result.output

    def test_all_command_groups_registered(self) -> None:
        """Test all command groups are registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # All command groups should be visible
        assert "read" in result.output
        assert "pick" in result.output
        assert "analyze" in result.output
        assert "dereplicate" in result.output
        assert "lsd" in result.output
        assert "nus" in result.output

    def test_subcommand_help(self) -> None:
        """Test subcommand help is accessible."""
        runner = CliRunner()
        for cmd in ["read", "pick", "analyze", "dereplicate", "lsd", "nus"]:
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0
            assert "Usage:" in result.output

    def test_nus_help_lists_check_params_schedule(self) -> None:
        """D-02: only the implemented check/params/schedule subcommands are
        registered on `lucy nus`; no dead reconstruct/pipeline stubs."""
        runner = CliRunner()
        result = runner.invoke(cli, ["nus", "--help"])
        assert result.exit_code == 0
        assert "check" in result.output
        assert "params" in result.output
        assert "schedule" in result.output


class TestNusImportSafe:
    """NUS-05: core `lucy` CLI stays importable without the [nus] extra.

    Phase 97's nus/ submodules only use core dependencies (nmrglue, pydantic,
    click stdlib), so this is a plain "does the process exit 0" smoke check --
    there is no optional third-party package to detect a leak of (unlike the
    webview extra's fastapi/uvicorn leak check).
    """

    def test_cli_import_without_nus_extra(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "from lucy_ng.cli import cli"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"lucy_ng.cli failed to import.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestCLIIntegration:
    """Integration tests for CLI workflow."""

    def test_full_pipeline_to_lsd_generate(self) -> None:
        """Test full workflow from reading to LSD generation."""
        runner = CliRunner()

        # 1. Read spectrum
        result = runner.invoke(cli, ["read", "1d", "data/Ibuprofen/2"])
        assert result.exit_code == 0
        assert "13C" in result.output

        # 2. Pick peaks
        result = runner.invoke(cli, ["pick", "1d", "data/Ibuprofen/2"])
        assert result.exit_code == 0
        assert "peaks" in result.output.lower()

        # 3. Raw HSQC peaks (DEPT-guided logic is in AI agent skill now)
        result = runner.invoke(
            cli, ["pick", "hsqc", "data/Ibuprofen/6"]
        )
        assert result.exit_code == 0
        assert "peaks" in result.output.lower()

        # 4. Symmetry analysis
        result = runner.invoke(
            cli,
            ["analyze", "symmetry", "C13H18O2", "data/Ibuprofen/2"],
        )
        assert result.exit_code == 0
        assert "symmetry" in result.output.lower()

        # Note: LSD generate command was removed in earlier phase
        # (LSD file generation is now handled by AI agent through Python API)
