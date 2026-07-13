"""RECON-01/02 stubs: `nus/runner.py::NusRunner.reconstruct()` whole-pipeline orchestration.

Implemented in Plan 05 (`nus/runner.py`). This is the entrypoint that wires
Phase 97's `read_nus_params`/`read_nus_schedule`, the F2-before-F1 hard
ordering gate (a precondition checked BEFORE any subprocess is dispatched,
not merely implicit call ordering), `backend.convert()`,
`postprocess.process_direct()`, `backend.reconstruct_indirect()`, and
`postprocess.process_indirect()` into one `reconstruct(expdir)` call.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 05")
def test_f2_before_f1_gate_raises_before_any_subprocess(
    mock_subprocess_run, nus_fixture_dir, monkeypatch
) -> None:
    """When the F2 (direct-dimension) processing plan cannot be resolved
    (e.g. `_resolve_f2_plan()` returns None), `reconstruct()` must raise
    RuntimeError BEFORE dispatching any subprocess at all -- this is
    SMILE's own hard requirement (Sec.4), not just an internal convention,
    and it must be testable/mockable with zero backend installed (D-04).

    Implementing plan: Plan 05 (`nus/runner.py::NusRunner.reconstruct`).
    """
    from lucy_ng.nus.runner import NusRunner

    runner = NusRunner()
    monkeypatch.setattr(runner, "_resolve_f2_plan", lambda params: None)

    with pytest.raises(RuntimeError, match="F2"):
        runner.reconstruct(nus_fixture_dir("exp3_hsqc"))

    assert mock_subprocess_run["calls"] == []


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 05")
def test_orchestration_sequences_convert_then_direct_then_smile_then_indirect(
    mock_run_stage, nus_fixture_dir
) -> None:
    """The whole-pipeline call order must be: backend.convert() ->
    postprocess.process_direct() (F2 processing + transpose) ->
    backend.reconstruct_indirect() (SMILE) ->
    postprocess.process_indirect() (post-SMILE F1 processing). This is the
    concrete sequencing RECON-01/02 require -- SMILE runs strictly between
    the direct-dimension processing and the indirect-dimension
    post-processing, never immediately after raw conversion.

    Implementing plan: Plan 05 (`nus/runner.py::NusRunner.reconstruct`).
    """
    from lucy_ng.nus.runner import NusRunner

    runner = NusRunner()
    runner.reconstruct(nus_fixture_dir("exp3_hsqc"))

    stage_names = [call[0] for call in mock_run_stage["calls"]]
    assert stage_names.index("convert") < stage_names.index("process_direct")
    assert stage_names.index("process_direct") < stage_names.index("smile")
    assert stage_names.index("smile") < stage_names.index("process_indirect")


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 05")
def test_reconstruct_returns_result_with_stage_paths(nus_fixture_dir) -> None:
    """`reconstruct()` must return a result object (e.g.
    `NusReconstructionResult`) exposing `success`, the backend/params used,
    and the per-stage intermediate file paths under
    `analysis/nus_recon/<expN>/` (D-03: persistent, kept by default) --
    consumed by Phase 99's `nus/bridge.py` (not built in this phase).

    Implementing plan: Plan 05 (`nus/runner.py::NusRunner.reconstruct`).
    """
    from lucy_ng.nus.runner import NusRunner

    runner = NusRunner()
    result = runner.reconstruct(nus_fixture_dir("exp3_hsqc"))

    assert result.success is True
    assert result.output_file.exists()
    assert "nus_recon" in str(result.stage_dir)
