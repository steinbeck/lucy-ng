"""RECON-01/02 tests: `nus/runner.py::NusRunner.reconstruct()` whole-pipeline orchestration.

Implemented in Plan 05 (`nus/runner.py`). This is the entrypoint that wires
Phase 97's `read_nus_params`/`read_nus_schedule`, the F2-before-F1 hard
ordering gate (a precondition checked BEFORE any subprocess is dispatched,
not merely implicit call ordering), `backend.convert()`,
`postprocess.process_direct()`, `backend.reconstruct_indirect()`, and
`postprocess.process_indirect()` into one `reconstruct(expdir)` call.

These tests patch at the four-stage-callable boundary (a fake backend
double's `convert()`/`reconstruct_indirect()`, plus `nus.runner`'s own
imported `process_direct`/`process_indirect` names) rather than the
lower-level `run_stage()`/`subprocess.run()` seam -- this lets the ordering
test assert both call sequence AND that `reconstruct_indirect()` receives
`process_direct()`'s own return value as its `f2_processed_fid` input,
which a `run_stage()`-level mock cannot distinguish (both `convert()`'s
internal bruk2pipe/nusExpand.tcl calls and `process_direct()` produce
`.fid`-suffixed intermediates).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def _copy_fixture(nus_fixture_dir, tmp_path: Path, name: str) -> Path:
    """Copy a read-only tests/fixtures/nus/<name> dir into tmp_path.

    `NusRunner._stage_dir()` writes `analysis/nus_recon/<expN>/` under the
    resolved `expdir` (D-03) -- copying into `tmp_path` first keeps every
    test's stage-dir side effects contained to pytest's own tmp dir rather
    than polluting the tracked `tests/fixtures/nus/` tree.
    """
    src = nus_fixture_dir(name)
    dst = tmp_path / name
    shutil.copytree(src, dst)
    return dst


class _RecordingBackend:
    """Fake backend double recording `convert()`/`reconstruct_indirect()` calls."""

    def __init__(self, calls: list[str], f2_processed_holder: dict) -> None:
        self._calls = calls
        self._f2_processed_holder = f2_processed_holder

    def diagnose(self) -> dict:
        """Clean, gate-passing diagnose() (PORT-01) -- lets the PORT-01
        preflight gate pass so these tests exercise the F2-before-F1
        ordering/orchestration logic, not the new preflight gate."""
        return {
            "status": "available",
            "missing_tools": [],
            "smile_available": True,
            "hint": "",
            "platform": {"critical_platform_issues": [], "soft_platform_warnings": []},
        }

    def convert(self, expdir, params, schedule, stage_dir, *, timeout=600):
        self._calls.append("convert")
        return stage_dir / "converted.fid"

    def reconstruct_indirect(
        self,
        f2_processed_fid,
        *,
        nuslist_path,
        stage_dir,
        fnmode,
        max_iter,
        threshold,
        n_sigma,
        virtual_echo,
        f1_p0,
        f1_p1,
        timeout=600,
    ):
        self._calls.append("smile")
        self._f2_processed_holder["received"] = f2_processed_fid
        return stage_dir / "reconstructed.ft1"


def test_f2_before_f1_gate_raises_before_any_subprocess(
    mock_subprocess_run, nus_fixture_dir, tmp_path, monkeypatch
) -> None:
    """When the F2 (direct-dimension) processing plan cannot be resolved
    (e.g. `_resolve_f2_plan()` returns None), `reconstruct()` must raise
    RuntimeError BEFORE dispatching any subprocess at all -- this is
    SMILE's own hard requirement (Sec.4), not just an internal convention,
    and it must be testable/mockable with zero backend installed (D-04).
    """
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")
    runner = NusRunner()
    # Neutralize the PORT-01 preflight gate (a clean, gate-passing diagnose())
    # so it is the F2-plan-specific RuntimeError that actually fires here,
    # not this dev machine's real (missing-tools) diagnose() output.
    monkeypatch.setattr(
        runner.backend,
        "diagnose",
        lambda: {
            "missing_tools": [],
            "platform": {"critical_platform_issues": []},
        },
    )
    monkeypatch.setattr(runner, "_resolve_f2_plan", lambda params: None)

    with pytest.raises(RuntimeError, match="F2"):
        runner.reconstruct(expdir)

    assert mock_subprocess_run["calls"] == []


def test_f2_before_f1_guard_raises_when_smile_would_get_raw_converted_fid(
    nus_fixture_dir, tmp_path, monkeypatch
) -> None:
    """The reachable F2-before-F1 guard (RECON-02) must raise if the
    pipeline is mis-wired so SMILE would consume the raw converted FID
    instead of process_direct()'s F2-processed output -- exercised here on
    a real fnmode (no impossible-state monkeypatch of _resolve_f2_plan),
    unlike the recipe gate which is defense-in-depth only.
    """
    import lucy_ng.nus.runner as runner_module
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")

    calls: list[str] = []
    backend = _RecordingBackend(calls, {})

    # Mis-wire: process_direct returns the SAME path convert() produced
    # (the raw converted FID), i.e. F2 processing effectively did not run.
    def bad_process_direct(converted_fid, stage_dir, params=None, **kwargs):
        return Path(converted_fid)

    monkeypatch.setattr(runner_module, "process_direct", bad_process_direct)

    runner = NusRunner(backend=backend)
    with pytest.raises(RuntimeError, match="F2-before-F1"):
        runner.reconstruct(expdir)

    # SMILE must never have been dispatched.
    assert "smile" not in calls


def test_orchestration_sequences_convert_then_direct_then_smile_then_indirect(
    nus_fixture_dir, tmp_path, monkeypatch
) -> None:
    """The whole-pipeline call order must be: backend.convert() ->
    postprocess.process_direct() (F2 processing + transpose) ->
    backend.reconstruct_indirect() (SMILE) ->
    postprocess.process_indirect() (post-SMILE F1 processing). This is the
    concrete sequencing RECON-01/02 require -- SMILE runs strictly between
    the direct-dimension processing and the indirect-dimension
    post-processing, never immediately after raw conversion. Also asserts
    `reconstruct_indirect()`'s `f2_processed_fid` argument is exactly
    `process_direct()`'s own return value (SMILE never runs on the raw
    converted FID).
    """
    import lucy_ng.nus.runner as runner_module
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")

    calls: list[str] = []
    f2_processed_holder: dict = {}
    backend = _RecordingBackend(calls, f2_processed_holder)

    f2_processed_path_holder: dict = {}

    def fake_process_direct(converted_fid, stage_dir, params=None, **kwargs):
        calls.append("process_direct")
        path = Path(stage_dir) / "f2_processed.fid"
        f2_processed_path_holder["path"] = path
        return path

    def fake_process_indirect(reconstructed_fid, stage_dir, params=None, **kwargs):
        calls.append("process_indirect")
        return Path(stage_dir) / "processed.ft2"

    monkeypatch.setattr(runner_module, "process_direct", fake_process_direct)
    monkeypatch.setattr(runner_module, "process_indirect", fake_process_indirect)

    runner = NusRunner(backend=backend)
    runner.reconstruct(expdir)

    assert calls.index("convert") < calls.index("process_direct")
    assert calls.index("process_direct") < calls.index("smile")
    assert calls.index("smile") < calls.index("process_indirect")

    # SMILE must run on process_direct()'s own return value, never the raw
    # converted FID.
    assert f2_processed_holder["received"] == f2_processed_path_holder["path"]


def test_reconstruct_returns_result_with_stage_paths(
    nus_fixture_dir, tmp_path, monkeypatch
) -> None:
    """`reconstruct()` must return a `NusReconstructionResult` exposing
    `success`, the backend/params used, and the per-stage intermediate file
    paths under `analysis/nus_recon/<expN>/` (D-03: persistent, kept by
    default) -- consumed by Phase 99's `nus/bridge.py` (not built in this
    phase). The stage dir must exist and not be deleted after the run.
    """
    import lucy_ng.nus.runner as runner_module
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")

    calls: list[str] = []
    backend = _RecordingBackend(calls, {})

    def fake_process_direct(converted_fid, stage_dir, params=None, **kwargs):
        return Path(stage_dir) / "f2_processed.fid"

    def fake_process_indirect(reconstructed_fid, stage_dir, params=None, **kwargs):
        out = Path(stage_dir) / "processed.ft2"
        out.write_bytes(b"\x01\x02\x03\x04")
        return out

    monkeypatch.setattr(runner_module, "process_direct", fake_process_direct)
    monkeypatch.setattr(runner_module, "process_indirect", fake_process_indirect)

    runner = NusRunner(backend=backend)
    result = runner.reconstruct(expdir)

    assert result.success is True
    assert "nus_recon" in result.stage_dir
    assert Path(result.stage_dir).exists()
    assert Path(result.processed_spectrum).exists()
    assert set(result.stage_outputs) == {
        "convert",
        "process_direct",
        "smile",
        "process_indirect",
    }
