"""PORT-01 tests: `NusRunner.reconstruct()`'s precondition-before-dispatch
preflight gate.

Mirrors `tests/nus/test_reconstruct_orchestration.py::
test_f2_before_f1_gate_raises_before_any_subprocess`'s "assert zero
subprocess calls" proof technique -- here for the NEW preflight gate that
must fire even earlier (before params/schedule are even read).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def _copy_fixture(nus_fixture_dir, tmp_path: Path, name: str) -> Path:
    """Copy a read-only tests/fixtures/nus/<name> dir into tmp_path (mirrors
    test_reconstruct_orchestration.py's helper of the same name)."""
    src = nus_fixture_dir(name)
    dst = tmp_path / name
    shutil.copytree(src, dst)
    return dst


class _DiagnoseOnlyBackend:
    """Minimal backend double exposing only `diagnose()` -- enough to
    exercise the preflight gate without a real convert()/reconstruct_indirect()."""

    def __init__(self, diagnosis: dict) -> None:
        self._diagnosis = diagnosis

    def diagnose(self) -> dict:
        return self._diagnosis


def test_preflight_gate_raises_on_missing_tools(
    mock_subprocess_run, nus_fixture_dir, tmp_path
) -> None:
    """A diagnose() reporting missing_tools must raise RuntimeError BEFORE
    any subprocess is dispatched."""
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")
    backend = _DiagnoseOnlyBackend(
        {"missing_tools": ["nmrPipe"], "platform": {"critical_platform_issues": []}}
    )
    runner = NusRunner(backend=backend)

    with pytest.raises(RuntimeError, match="preflight"):
        runner.reconstruct(expdir)

    assert mock_subprocess_run["calls"] == []


def test_preflight_gate_raises_on_critical_platform_issue(
    mock_subprocess_run, nus_fixture_dir, tmp_path
) -> None:
    """A diagnose() reporting a critical platform issue (e.g. missing
    csh/tcsh) must raise RuntimeError BEFORE any subprocess dispatch, even
    with zero missing_tools."""
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")
    backend = _DiagnoseOnlyBackend(
        {
            "missing_tools": [],
            "platform": {
                "critical_platform_issues": ["no csh/tcsh interpreter found"]
            },
        }
    )
    runner = NusRunner(backend=backend)

    with pytest.raises(RuntimeError, match="preflight"):
        runner.reconstruct(expdir)

    assert mock_subprocess_run["calls"] == []


def test_preflight_gate_passes_when_diagnose_clean(
    nus_fixture_dir, tmp_path, monkeypatch
) -> None:
    """A diagnose() reporting no missing_tools and no critical platform
    issues must NOT raise the preflight RuntimeError -- reconstruct()
    proceeds past the gate (it may still fail later for unrelated reasons
    since this fake backend has no real convert()/reconstruct_indirect())."""
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")

    class _NoMethodsBackend(_DiagnoseOnlyBackend):
        pass

    backend = _NoMethodsBackend(
        {
            "missing_tools": [],
            "platform": {"critical_platform_issues": [], "soft_platform_warnings": []},
        }
    )
    runner = NusRunner(backend=backend)

    # The gate itself must not raise -- proceeding past it hits
    # AttributeError (this fake backend has no convert()), never the
    # preflight RuntimeError.
    with pytest.raises(AttributeError):
        runner.reconstruct(expdir)


def test_preflight_gate_defensive_on_missing_platform_key(
    mock_subprocess_run, nus_fixture_dir, tmp_path
) -> None:
    """A diagnose() dict with no "platform" key at all must still be
    handled defensively (`.get("platform", {})`) rather than raising
    KeyError -- only missing_tools drives the gate in that case."""
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")
    backend = _DiagnoseOnlyBackend({"missing_tools": ["nmrPipe"]})
    runner = NusRunner(backend=backend)

    with pytest.raises(RuntimeError, match="preflight"):
        runner.reconstruct(expdir)

    assert mock_subprocess_run["calls"] == []
