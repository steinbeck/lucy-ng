"""CLI-surface tests for `lucy jcamp` (Phase 102, Plan 03).

Covers registration, help text, D-01's "one command, no subcommands"
invariant, argument-validation error paths, and import safety. Fixture-backed
end-to-end behaviour (real read -> pick -> QC -> write over committed
trimmed fixtures) is Plan 04's own test file, not this one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from click.testing import CliRunner

from lucy_ng.cli.jcamp import jcamp

FIXTURES = Path(__file__).parent / "fixtures" / "jcamp"
REAL_13C_FIXTURE = FIXTURES / "C20H32O2_13C.dx"


class TestJcampCliSurface:
    """Registration, help text, and argument-validation error paths."""

    def test_help_exits_zero_and_documents_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, ["--help"])
        assert result.exit_code == 0, result.output
        assert "--out" in result.output
        assert "--snr-floor" in result.output
        assert "--format" in result.output
        assert "lucy nus qc" in result.output

    def test_registered_on_top_level_group(self) -> None:
        from lucy_ng.cli.main import cli

        assert "jcamp" in cli.commands
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0, result.output
        assert "jcamp" in result.output

    def test_no_qc_subcommand_exists(self) -> None:
        """D-01: `lucy jcamp` is a single command, not a group with subcommands."""
        assert not isinstance(jcamp, click.Group)
        runner = CliRunner()
        result = runner.invoke(jcamp, ["qc", "/tmp"])
        assert result.exit_code != 0

    def test_missing_argument_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, [])
        assert result.exit_code != 0

    def test_nonexistent_path_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, ["/no/such/jcamp/dir"])
        assert result.exit_code != 0

    def test_empty_directory_exits_nonzero(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, [str(tmp_path)])
        assert result.exit_code != 0
        assert tmp_path.name in result.output or str(tmp_path) in result.output
        assert not (tmp_path / "analysis").exists()

    def test_directory_mixed_with_files_rejected(self, tmp_path: Path) -> None:
        assert REAL_13C_FIXTURE.exists(), f"missing fixture: {REAL_13C_FIXTURE}"
        runner = CliRunner()
        result = runner.invoke(jcamp, [str(tmp_path), str(REAL_13C_FIXTURE)])
        assert result.exit_code != 0


class TestJcampImportSafety:
    """Mirrors tests/test_cli_nus.py's TestImportSafety."""

    def test_module_imports_cleanly(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import lucy_ng.cli.jcamp"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"lucy_ng.cli.jcamp failed to import cleanly.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_no_eager_domain_imports(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys, lucy_ng.cli.jcamp; "
                    "assert 'lucy_ng.nus.qc' not in sys.modules; "
                    "assert 'lucy_ng.readers.jcamp' not in sys.modules; "
                    "print('OK')"
                ),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"lucy_ng.cli.jcamp leaked an eager domain import.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
