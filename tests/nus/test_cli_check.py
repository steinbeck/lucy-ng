"""PORT-01 tests: `lucy nus check`'s extended platform section + exit-code
semantics (D-05: critical = exit 1, soft-only = exit 0).

Mocks `get_backend()`/`diagnose()` at the CLI-invocation boundary (mirrors
`tests/nus/test_cli_pipeline.py`'s `CliRunner`-based command-test style).
"""

from __future__ import annotations

import json


def _clean_diagnosis() -> dict:
    return {
        "status": "available",
        "missing_tools": [],
        "smile_available": True,
        "hint": "NMRPipe+SMILE backend fully available.",
        "platform": {
            "arch": "arm64",
            "os": "Darwin",
            "rosetta_translated": False,
            "csh_available": True,
            "tcsh_available": True,
            "critical_platform_issues": [],
            "soft_platform_warnings": [],
        },
    }


def _soft_only_diagnosis() -> dict:
    diagnosis = _clean_diagnosis()
    diagnosis["platform"] = {
        "arch": "x86_64",
        "os": "Darwin",
        "rosetta_translated": True,
        "csh_available": True,
        "tcsh_available": True,
        "critical_platform_issues": [],
        "soft_platform_warnings": ["running under Rosetta 2 x86_64 translation"],
    }
    return diagnosis


def _critical_diagnosis() -> dict:
    diagnosis = _clean_diagnosis()
    diagnosis["platform"] = {
        "arch": "arm64",
        "os": "Darwin",
        "rosetta_translated": False,
        "csh_available": False,
        "tcsh_available": False,
        "critical_platform_issues": ["no csh/tcsh interpreter found"],
        "soft_platform_warnings": [],
    }
    return diagnosis


def _invoke_check(monkeypatch, diagnosis: dict, args: list[str]):
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    class _FakeBackend:
        @staticmethod
        def diagnose():
            return diagnosis

    monkeypatch.setattr(
        "lucy_ng.nus.backends.get_backend", lambda name="nmrpipe_smile": _FakeBackend
    )

    runner = CliRunner()
    return runner.invoke(nus, ["check", *args])


def test_check_json_includes_platform_object(monkeypatch) -> None:
    result = _invoke_check(monkeypatch, _clean_diagnosis(), ["--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "platform" in payload
    assert "arch" in payload["platform"]
    assert "csh_available" in payload["platform"]


def test_check_exit_code_zero_on_soft_only_warning(monkeypatch) -> None:
    result = _invoke_check(monkeypatch, _soft_only_diagnosis(), ["--format", "json"])
    assert result.exit_code == 0, result.output


def test_check_exit_code_one_on_critical_platform_issue(monkeypatch) -> None:
    result = _invoke_check(monkeypatch, _critical_diagnosis(), ["--format", "json"])
    assert result.exit_code == 1, result.output


def test_check_text_mode_reports_platform_section(monkeypatch) -> None:
    result = _invoke_check(monkeypatch, _clean_diagnosis(), [])
    assert result.exit_code == 0, result.output
    assert "Platform:" in result.output
    assert "arch=arm64" in result.output


def test_reconstruct_and_pipeline_help_list_n_sigma() -> None:
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    reconstruct_result = runner.invoke(nus, ["reconstruct", "--help"])
    pipeline_result = runner.invoke(nus, ["pipeline", "--help"])

    assert reconstruct_result.exit_code == 0
    assert "--n-sigma" in reconstruct_result.output
    assert pipeline_result.exit_code == 0
    assert "--n-sigma" in pipeline_result.output
