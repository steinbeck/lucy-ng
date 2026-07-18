"""PORT-01 tests: `nus/platform_check.py::detect_platform()` classification.

Every branch monkeypatches `platform.machine`/`platform.system`/
`shutil.which`/`subprocess.run` -- never touches the real system (mirrors
`tests/nus/conftest.py`'s string-target monkeypatch convention for
`nus/runner.py::run_stage`).
"""

from __future__ import annotations

import subprocess

import pytest


def test_native_arm64_no_critical_no_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Native Apple-Silicon arm64, csh+tcsh present -> clean bill of health."""
    from lucy_ng.nus import platform_check

    monkeypatch.setattr(platform_check.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(platform_check.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        platform_check.shutil, "which", lambda name: f"/bin/{name}"
    )

    class _Proc:
        stdout = "0\n"
        stderr = ""

    monkeypatch.setattr(
        platform_check.subprocess, "run", lambda *a, **k: _Proc()
    )

    result = platform_check.detect_platform()

    assert result["arch"] == "arm64"
    assert result["rosetta_translated"] is False
    assert result["csh_available"] is True
    assert result["tcsh_available"] is True
    assert result["critical_platform_issues"] == []
    assert result["soft_platform_warnings"] == []


def test_rosetta_translated_soft_warning_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rosetta-translated x86_64 process on Darwin -> soft warning, never critical."""
    from lucy_ng.nus import platform_check

    monkeypatch.setattr(platform_check.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(platform_check.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        platform_check.shutil, "which", lambda name: f"/bin/{name}"
    )

    class _Proc:
        stdout = "1\n"
        stderr = ""

    monkeypatch.setattr(
        platform_check.subprocess, "run", lambda *a, **k: _Proc()
    )

    result = platform_check.detect_platform()

    assert result["rosetta_translated"] is True
    assert result["critical_platform_issues"] == []
    assert len(result["soft_platform_warnings"]) == 1


def test_missing_csh_and_tcsh_is_critical(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both csh and tcsh absent from PATH -> a critical_platform_issue is present."""
    from lucy_ng.nus import platform_check

    monkeypatch.setattr(platform_check.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(platform_check.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform_check.shutil, "which", lambda name: None)

    class _Proc:
        stdout = "0\n"
        stderr = ""

    monkeypatch.setattr(
        platform_check.subprocess, "run", lambda *a, **k: _Proc()
    )

    result = platform_check.detect_platform()

    assert result["csh_available"] is False
    assert result["tcsh_available"] is False
    assert len(result["critical_platform_issues"]) == 1
    assert "csh" in result["critical_platform_issues"][0]


def test_genuine_intel_or_indeterminate_sysctl_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sysctl probe that errors/returns a non-0/1 value -> rosetta_translated
    is None, never coerced to False, and never raises."""
    from lucy_ng.nus import platform_check

    monkeypatch.setattr(platform_check.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(platform_check.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        platform_check.shutil, "which", lambda name: f"/bin/{name}"
    )

    def _raise(*a, **k):
        raise OSError("sysctl not found")

    monkeypatch.setattr(platform_check.subprocess, "run", _raise)

    result = platform_check.detect_platform()

    assert result["rosetta_translated"] is None
    assert result["critical_platform_issues"] == []


def test_linux_rosetta_not_applicable(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Linux, sysctl is not applicable -> rosetta_translated is None;
    csh presence still governs critical status."""
    from lucy_ng.nus import platform_check

    monkeypatch.setattr(platform_check.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(platform_check.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        platform_check.shutil, "which", lambda name: f"/bin/{name}"
    )

    def _fail_if_called(*a, **k):
        raise AssertionError("subprocess.run should not be called on Linux")

    monkeypatch.setattr(platform_check.subprocess, "run", _fail_if_called)

    result = platform_check.detect_platform()

    assert result["rosetta_translated"] is None
    assert result["critical_platform_issues"] == []


def test_timeout_expired_resolves_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A TimeoutExpired from the sysctl probe resolves to None, not a crash."""
    from lucy_ng.nus import platform_check

    monkeypatch.setattr(platform_check.platform, "system", lambda: "Darwin")

    def _timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd=["sysctl"], timeout=10)

    monkeypatch.setattr(platform_check.subprocess, "run", _timeout)

    assert platform_check._rosetta_translated() is None


def test_diagnose_carries_additive_platform_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """`diagnose()` returns a "platform" value equal to `detect_platform()`'s
    output, and all four pre-existing keys stay present and unchanged in
    shape."""
    from lucy_ng.nus.backends import nmrpipe_smile
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend

    fake_platform_info = {
        "arch": "arm64",
        "os": "Darwin",
        "rosetta_translated": False,
        "csh_available": True,
        "tcsh_available": True,
        "critical_platform_issues": [],
        "soft_platform_warnings": [],
    }
    monkeypatch.setattr(
        nmrpipe_smile, "detect_platform", lambda: fake_platform_info
    )

    diagnosis = NmrPipeSmileBackend.diagnose()

    assert diagnosis["platform"] == fake_platform_info
    for key in ("status", "missing_tools", "smile_available", "hint"):
        assert key in diagnosis
