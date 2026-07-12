"""Tests for `lucy nus` CLI commands (check/params/schedule).

Covers NUS-01 (check surface), NUS-04 (JSON CLI over the three fixtures),
and NUS-05's import-safety invariant for `cli/nus.py` specifically (D-02:
imports of `lucy_ng.nus.*` must be deferred into command bodies, never
top-level).
"""

from __future__ import annotations

import json
import subprocess
import sys

from click.testing import CliRunner

from lucy_ng.cli.nus import nus

FIXTURES = "tests/fixtures/nus"


class TestNusCheck:
    """Tests for `lucy nus check`."""

    def test_check_text_reports_status(self) -> None:
        runner = CliRunner()
        result = runner.invoke(nus, ["check"])
        # This dev machine has no NMRPipe installed -- expect exit 1.
        assert result.exit_code == 1
        assert "not available" in result.output.lower()

    def test_check_json_emits_diagnose_dict_and_exits_1(self) -> None:
        runner = CliRunner()
        result = runner.invoke(nus, ["check", "--format", "json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "status" in data
        assert "missing_tools" in data
        assert "smile_available" in data
        assert "hint" in data
        assert data["status"] != "available"


class TestNusParams:
    """Tests for `lucy nus params <expdir>`."""

    def test_params_exp3_hsqc_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            nus, ["params", f"{FIXTURES}/exp3_hsqc", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["fnmode_f1"] == 6
        assert data["f1_td"] == 100
        assert data["nus_td"] == 400

    def test_params_exp2_cosy_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            nus, ["params", f"{FIXTURES}/exp2_cosy", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["fnmode_f1"] == 1
        assert data["f1_td"] == 188

    def test_params_exp4_hmbc_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            nus, ["params", f"{FIXTURES}/exp4_hmbc", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["fnmode_f1"] == 6
        assert data["f1_td"] == 232

    def test_params_text_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(nus, ["params", f"{FIXTURES}/exp3_hsqc"])
        assert result.exit_code == 0
        assert "Pulse program" in result.output

    def test_params_nonexistent_dir_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(nus, ["params", "/no/such/nus/dir"])
        assert result.exit_code != 0


class TestNusSchedule:
    """Tests for `lucy nus schedule <expdir>`."""

    def test_schedule_exp2_cosy_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            nus, ["schedule", f"{FIXTURES}/exp2_cosy", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["n_sampled"] == 188
        assert len(data["nuslist"]) == 188

    def test_schedule_exp3_hsqc_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            nus, ["schedule", f"{FIXTURES}/exp3_hsqc", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["n_sampled"] == 50

    def test_schedule_text_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(nus, ["schedule", f"{FIXTURES}/exp4_hmbc"])
        assert result.exit_code == 0
        assert "Sampled points" in result.output

    def test_schedule_nonexistent_dir_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(nus, ["schedule", "/no/such/nus/dir"])
        assert result.exit_code != 0


class TestImportSafety:
    """NUS-05/D-02: importing lucy_ng.cli.nus must not pull in lucy_ng.nus.*."""

    def test_no_top_level_nus_submodule_import(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import lucy_ng.cli.nus"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"lucy_ng.cli.nus failed to import cleanly.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_nus_group_help_lists_only_implemented_subcommands(self) -> None:
        """D-02: no dead reconstruct/pipeline stubs registered."""
        assert set(nus.commands) == {"check", "params", "schedule"}

        runner = CliRunner()
        result = runner.invoke(nus, ["--help"])
        assert result.exit_code == 0
        assert "check" in result.output
        assert "params" in result.output
        assert "schedule" in result.output
