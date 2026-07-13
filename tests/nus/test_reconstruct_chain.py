"""RECON-01/02/03: `backend.convert()` + `reconstruct_indirect()` dispatch.

Implemented in Plan 03 (`nus/backends/nmrpipe_smile.py::convert()` +
`reconstruct_indirect()`). Covers the FnMODE-branched conversion dispatch
order (Critical Finding 1), the exact bruk2pipe grid-size parameter source
(Critical Finding 2: NusTD, never sparse F1 TD), the exact non-integer
GRPDLY passthrough (Pitfall 3), SMILE's true input artefact, and the QF
branch's `-EA` omission.

IMPORTANT: there is deliberately NO
`test_dispatches_expand_then_convert_then_smile` test in this file. SMILE
does NOT run immediately after conversion -- the direct (F2) dimension must
be fully processed (apod/ZF/FT/PS/POLY/EXT) and transposed FIRST (see
`test_processing_order.py` / Plan 04, and the whole-pipeline sequencing
test in `test_reconstruct_orchestration.py` / Plan 05). This file only
covers the conversion stage's own two-branch dispatch, not the full chain.
"""

from __future__ import annotations


def test_echo_antiecho_convert_dispatches_expand_then_bruk2pipe(
    mock_run_stage, nus_fixture_dir, tmp_path
) -> None:
    """For FnMODE=6 (echo-antiecho, e.g. exp3 HSQC / exp4 HMBC),
    `convert()` must dispatch `nusExpand.tcl` BEFORE `bruk2pipe` -- the
    fully-worked SMILE-manual order for phase-sensitive indirect dimensions.

    Implementing plan: Plan 03 (`nus/backends/nmrpipe_smile.py::convert`).
    """
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend
    from lucy_ng.nus.params import read_nus_params
    from lucy_ng.nus.schedule import read_nus_schedule

    expdir = nus_fixture_dir("exp3_hsqc")
    params = read_nus_params(expdir)
    schedule = read_nus_schedule(expdir)

    NmrPipeSmileBackend.convert(expdir, params, schedule, stage_dir=tmp_path)

    stage_names = [call[0] for call in mock_run_stage["calls"]]
    assert stage_names.index("nusExpand.tcl") < stage_names.index("bruk2pipe")


def test_qf_convert_dispatches_bruk2pipe_then_expand(
    mock_run_stage, nus_fixture_dir, tmp_path
) -> None:
    """For FnMODE=1 (QF/magnitude, exp2 COSY), `convert()` must dispatch
    `bruk2pipe` BEFORE `nusExpand.tcl` -- the reverse order, since the
    expand-first path is documented to not work for magnitude-mode data.

    Implementing plan: Plan 03 (`nus/backends/nmrpipe_smile.py::convert`).
    """
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend
    from lucy_ng.nus.params import read_nus_params
    from lucy_ng.nus.schedule import read_nus_schedule

    expdir = nus_fixture_dir("exp2_cosy")
    params = read_nus_params(expdir)
    schedule = read_nus_schedule(expdir)

    NmrPipeSmileBackend.convert(expdir, params, schedule, stage_dir=tmp_path)

    stage_names = [call[0] for call in mock_run_stage["calls"]]
    assert stage_names.index("bruk2pipe") < stage_names.index("nusExpand.tcl")


def test_smile_argv_carries_default_knobs(mock_run_stage, tmp_path) -> None:
    """`reconstruct_indirect()`'s SMILE invocation argv must carry the
    RECON-05 default knobs (-maxIter upper bound, -nSigma/-thresh
    convergence check, -EA where applicable) -- never a bare `nmrPipe -fn
    SMILE` with no knobs.

    Implementing plan: Plan 03 (`nus/backends/nmrpipe_smile.py::reconstruct_indirect`).
    """
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend

    f2_processed_fid = tmp_path / "f2_processed.fid"
    f2_processed_fid.write_bytes(b"\x01" * 64)

    NmrPipeSmileBackend.reconstruct_indirect(
        f2_processed_fid, nuslist_path=tmp_path / "nuslist", stage_dir=tmp_path
    )

    argv = mock_run_stage["calls"][-1][1]
    assert "-maxIter" in argv
    assert "-nSigma" in argv or "-thresh" in argv


def test_bruk2pipe_uses_nus_td_not_f1_td(mock_run_stage, nus_fixture_dir, tmp_path) -> None:
    """`convert()`'s bruk2pipe invocation must use `NusSchedule.nus_td` /
    `NusAcquisitionParams.nus_td` (the full expanded grid size) for its
    `-yN`/`-yT` flags -- NEVER the sparse `f1_td` (acqu2s TD) and NEVER a
    re-derived `max(nuslist)+1` (Critical Finding 2).

    Implementing plan: Plan 03 (`nus/backends/nmrpipe_smile.py::convert`).
    """
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend
    from lucy_ng.nus.params import read_nus_params
    from lucy_ng.nus.schedule import read_nus_schedule

    expdir = nus_fixture_dir("exp3_hsqc")
    params = read_nus_params(expdir)
    schedule = read_nus_schedule(expdir)
    assert params.f1_td == 100
    assert schedule.nus_td == 400

    NmrPipeSmileBackend.convert(expdir, params, schedule, stage_dir=tmp_path)

    bruk2pipe_argv = next(
        call[1] for call in mock_run_stage["calls"] if call[0] == "bruk2pipe"
    )
    assert "400" in bruk2pipe_argv
    assert "100" not in bruk2pipe_argv


def test_grpdly_passed_exact_non_integer(mock_run_stage, nus_fixture_dir, tmp_path) -> None:
    """`convert()`'s bruk2pipe invocation must pass the EXACT non-integer
    GRPDLY value parsed from `acqus` (e.g. 67.9841918945312...) via
    `-grpdly` -- never rounded/truncated to an integer (Pitfall 3, resolved
    via bruk2pipe's own built-in digital-filter-removal flag).

    Implementing plan: Plan 03 (`nus/backends/nmrpipe_smile.py::convert`).
    """
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend
    from lucy_ng.nus.params import read_nus_params
    from lucy_ng.nus.schedule import read_nus_schedule

    expdir = nus_fixture_dir("exp3_hsqc")
    params = read_nus_params(expdir)
    schedule = read_nus_schedule(expdir)

    NmrPipeSmileBackend.convert(expdir, params, schedule, stage_dir=tmp_path)

    bruk2pipe_argv = next(
        call[1] for call in mock_run_stage["calls"] if call[0] == "bruk2pipe"
    )
    grpdly_idx = bruk2pipe_argv.index("-grpdly")
    passed_value = float(bruk2pipe_argv[grpdly_idx + 1])
    assert passed_value == params.grpdly
    assert passed_value != int(passed_value)


def test_smile_input_is_f2_processed_not_raw_converted_fid(mock_run_stage, tmp_path) -> None:
    """`reconstruct_indirect()` must be invoked with the TRANSPOSED,
    F2-processed FID (`f2_processed.fid`, produced by
    `postprocess.process_direct()`, Plan 04) as its input -- NOT the raw
    time-domain FID straight out of `convert()`. SMILE consumes the
    direct-dimension-processed-and-transposed data, per SMILE manual Sec.4:
    "the direct dimension must be first apodized, zero filled, Fourier
    transformed, and phased... before... the SMILE function can be called."

    Implementing plan: Plan 03/05 (`nus/backends/nmrpipe_smile.py
    ::reconstruct_indirect` input contract; wired end-to-end by
    `nus/runner.py` in Plan 05).
    """
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend

    f2_processed_fid = tmp_path / "f2_processed.fid"
    f2_processed_fid.write_bytes(b"\x01" * 64)
    raw_converted_fid = tmp_path / "converted.fid"
    raw_converted_fid.write_bytes(b"\x02" * 64)

    NmrPipeSmileBackend.reconstruct_indirect(
        f2_processed_fid, nuslist_path=tmp_path / "nuslist", stage_dir=tmp_path
    )

    argv = mock_run_stage["calls"][-1][1]
    assert str(f2_processed_fid) in argv or "f2_processed" in " ".join(argv)
    assert str(raw_converted_fid) not in argv


def test_reconstruct_indirect_omits_ea_for_qf_fnmode(mock_run_stage, tmp_path) -> None:
    """`reconstruct_indirect()` must NOT pass `-EA` for FnMODE=1 (QF/
    magnitude COSY, `REAL_FNMODES`) -- `-EA` (virtual echo / Echo-AntiEcho
    reconstruction) only applies to `COMPLEX_FNMODES` per
    `FnModeRecipe.smile_ea`. The default (FnMODE=6, echo-antiecho) DOES
    carry `-EA`, confirming the branch is genuinely FnMODE-driven rather
    than always-on or always-off.

    Implementing plan: Plan 03 (`nus/backends/nmrpipe_smile.py
    ::reconstruct_indirect`), Task 2 (QF branch).
    """
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend

    f2_processed_fid = tmp_path / "f2_processed.fid"
    f2_processed_fid.write_bytes(b"\x01" * 64)

    NmrPipeSmileBackend.reconstruct_indirect(
        f2_processed_fid,
        nuslist_path=tmp_path / "nuslist",
        stage_dir=tmp_path,
        fnmode=6,
    )
    echo_antiecho_argv = mock_run_stage["calls"][-1][1]
    assert "-EA" in echo_antiecho_argv

    NmrPipeSmileBackend.reconstruct_indirect(
        f2_processed_fid,
        nuslist_path=tmp_path / "nuslist",
        stage_dir=tmp_path,
        fnmode=1,
    )
    qf_argv = mock_run_stage["calls"][-1][1]
    assert "-EA" not in qf_argv
