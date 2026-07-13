"""RECON-04 stubs: the shared `run_stage()` fail-loud wrapper.

Implemented in Plan 02 (`nus/runner.py::run_stage`). Every external-tool
invocation in Phase 98 (bruk2pipe, nusExpand.tcl, SMILE, post-processing)
must go through this one helper -- exit code AND output-file non-emptiness
(and, where computable via nmrglue, non-all-zero data) are both checked; a
stage that "succeeds" (exit 0) but produces an empty/truncated file must
still raise (Pitfall 14: csh-piped NMRPipe stages can silently pass through
truncated data).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_nonzero_exit_raises(mock_subprocess_run, make_valid_intermediate, tmp_path) -> None:
    """`run_stage()` must raise RuntimeError when the subprocess exit code is
    non-zero, regardless of whether an output file happens to exist.

    Implementing plan: Plan 02 (`nus/runner.py::run_stage`).
    """
    from lucy_ng.nus.runner import run_stage

    mock_subprocess_run["returncode"] = 1
    mock_subprocess_run["stderr"] = "bruk2pipe: fatal error"
    output = make_valid_intermediate(name="converted", suffix=".fid")

    with pytest.raises(RuntimeError, match="exit"):
        run_stage("bruk2pipe", ["bruk2pipe", "-in", "ser"], tmp_path, output)


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_empty_output_raises(mock_subprocess_run, make_empty_intermediate, tmp_path) -> None:
    """`run_stage()` must raise RuntimeError when the subprocess reports exit
    0 but the declared expected_output file is zero-byte / missing.

    Implementing plan: Plan 02 (`nus/runner.py::run_stage`).
    """
    from lucy_ng.nus.runner import run_stage

    mock_subprocess_run["returncode"] = 0
    output = make_empty_intermediate(name="converted", suffix=".fid")

    with pytest.raises(RuntimeError, match="empty|missing"):
        run_stage("bruk2pipe", ["bruk2pipe", "-in", "ser"], tmp_path, output)


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_truncated_all_zero_output_raises(
    mock_subprocess_run, make_truncated_intermediate, tmp_path
) -> None:
    """`run_stage()` must raise RuntimeError when the subprocess reports exit
    0 and the output file is non-empty but all-zero/truncated (parses via
    nmrglue but carries no real data) -- Pitfall 14's specific failure mode.

    Implementing plan: Plan 02 (`nus/runner.py::run_stage`).
    """
    from lucy_ng.nus.runner import run_stage

    mock_subprocess_run["returncode"] = 0
    output = make_truncated_intermediate(name="converted", suffix=".fid")

    with pytest.raises(RuntimeError, match="all-zero|truncated|empty"):
        run_stage("bruk2pipe", ["bruk2pipe", "-in", "ser"], tmp_path, output)


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_valid_output_passes(mock_subprocess_run, make_valid_intermediate, tmp_path) -> None:
    """`run_stage()` must NOT raise when the subprocess reports exit 0 and
    the output file is non-empty (the success path).

    Implementing plan: Plan 02 (`nus/runner.py::run_stage`).
    """
    from lucy_ng.nus.runner import run_stage

    mock_subprocess_run["returncode"] = 0
    output = make_valid_intermediate(name="converted", suffix=".fid")

    run_stage("bruk2pipe", ["bruk2pipe", "-in", "ser"], tmp_path, output)
