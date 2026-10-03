"""Tests for the deprecated ``lucy`` console-script alias (PKG-03, D-04).

These tests prove the contract that matters most for the CASE agent team and
the benchmark harness, both of which still invoke ``lucy ... --format json``
and parse captured stdout as a machine-readable payload: the deprecation hint
must land on stderr only, and stdout for the ``lucy`` alias must be
byte-identical to stdout for the real ``ailsa`` entry point.

Do not use ``CliRunner(mix_stderr=False)`` here -- that constructor kwarg was
removed in the installed Click 8.4.2 and is part of this repo's own
pre-existing 74-failure baseline (see 104-PATTERNS.md). Use plain
``CliRunner()`` and read ``result.stdout``/``result.stderr`` separately.
"""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ailsa.cli.main import LUCY_DEPRECATION_MESSAGE, cli, lucy_deprecated

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestLucyDeprecatedAlias:
    """Tests for PKG-03 / D-04: the deprecated ``lucy`` alias."""

    def test_version_warns_on_stderr_only(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``lucy_deprecated(["--version"])`` exits 0, warns on stderr only."""
        with pytest.raises(SystemExit) as exc_info:
            lucy_deprecated(["--version"])
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "ailsa, version" in captured.out
        from ailsa import __version__

        assert __version__ in captured.out
        assert "deprecated" not in captured.out

        stderr_lines = [line for line in captured.err.splitlines() if line.strip()]
        assert len(stderr_lines) == 1
        assert "deprecated" in stderr_lines[0]
        assert "`ailsa`" in stderr_lines[0]

    def test_subprocess_stdout_byte_identical_to_ailsa(self) -> None:
        """A real subprocess run of the alias and of ``ailsa`` produce
        byte-identical stdout for ``--format json``, and only the alias
        prints the deprecation line on stderr."""
        alias_result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from ailsa.cli import lucy_deprecated; lucy_deprecated()",
                "identify",
                "--smiles",
                "CCO",
                "--format",
                "json",
            ],
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=120,
        )
        ailsa_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ailsa.cli",
                "identify",
                "--smiles",
                "CCO",
                "--format",
                "json",
            ],
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=120,
        )

        assert alias_result.returncode == ailsa_result.returncode
        assert alias_result.stdout == ailsa_result.stdout
        json.loads(alias_result.stdout)

        assert b"deprecated" in alias_result.stderr
        assert b"deprecated" not in ailsa_result.stderr

    def test_every_subcommand_help_matches_between_names(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every registered subcommand is reachable through both ``lucy``
        and ``ailsa``, with identical help text (modulo the prog name).

        Do not compare against ``CliRunner().invoke(cli, ...)`` -- CliRunner
        derives the prog name "cli" from the group object, not "ailsa".
        """
        for name in cli.commands:
            with pytest.raises(SystemExit) as exc_a:
                lucy_deprecated([name, "--help"])
            assert exc_a.value.code == 0
            out_a = capsys.readouterr().out

            with pytest.raises(SystemExit) as exc_b:
                cli.main(args=[name, "--help"], prog_name="ailsa")
            assert exc_b.value.code == 0
            out_b = capsys.readouterr().out

            assert out_a.replace("Usage: lucy ", "Usage: ailsa ", 1) == out_b

    def test_console_script_entry_points_registered(self) -> None:
        """Both console scripts are registered, pointing at the right
        callables -- skipped if the ``ailsa`` distribution isn't installed."""
        try:
            eps = importlib.metadata.entry_points(group="console_scripts")
        except importlib.metadata.PackageNotFoundError:
            pytest.skip("ailsa distribution not installed")

        names = {ep.name: ep.value for ep in eps if ep.name in ("ailsa", "lucy")}
        if not names:
            pytest.skip("ailsa distribution not installed")

        assert names.get("ailsa") == "ailsa.cli:cli"
        assert names.get("lucy") == "ailsa.cli:lucy_deprecated"

    def test_deprecation_message_has_no_newline(self) -> None:
        """The warning constant is a single line (so the stderr-line-count
        assertion above stays meaningful)."""
        assert "\n" not in LUCY_DEPRECATION_MESSAGE
