"""RECON-02 stubs: `nus/postprocess.py` direct/indirect processing + ppm calibration.

Implemented in Plan 04 (`nus/postprocess.py::process_direct()` +
`process_indirect()`). SMILE manual Sec.4/Sec.6.1: the direct (F2) dimension
must be fully apodized/zero-filled/Fourier-transformed/phased/baseline
corrected and then transposed (TP) BEFORE SMILE is called -- this is the
literal, mechanical enforcement of RECON-02's F2-before-F1 gate, not merely
a design convention. `process_indirect()` runs AFTER SMILE and produces the
final reversed, 1D-calibrated ppm axes.
"""

from __future__ import annotations


def test_f2_direct_chain_runs_before_transpose_before_smile_input(
    mock_run_stage, tmp_path
) -> None:
    """`process_direct()`'s verb chain (apod/ZF/FT/PS/POLY/EXT) must end
    with a transpose (TP) -- its output IS the transposed, F2-processed
    FID that becomes SMILE's input (`f2_processed.fid`).

    Implementing plan: Plan 04 (`nus/postprocess.py::process_direct`).
    """
    from lucy_ng.nus.postprocess import process_direct

    converted_fid = tmp_path / "converted.fid"
    converted_fid.write_bytes(b"\x01" * 64)

    result = process_direct(
        converted_fid, stage_dir=tmp_path, f2_p0=-24.0, f2_p1=0.0, magnitude=False
    )

    assert result.name == "f2_processed.fid"
    argv = mock_run_stage["calls"][-1][1]
    assert "TP" in " ".join(str(a) for a in argv)

    # Structural guard (would have caught the Phase-100 real-data bug):
    # each NMRPipe verb MUST be its OWN process -- NMRPipe honours only the
    # first `-fn` per invocation, so SP/ZF/FT/PS/POLY/TP cannot share one
    # process. Assert the pipeline is per-verb and TP is the last stage.
    stages = mock_run_stage["pipelines"]["process_direct"]
    fn_verbs = [s[s.index("-fn") + 1] for s in stages if "-fn" in s]
    assert fn_verbs == ["SP", "ZF", "FT", "PS", "POLY", "TP"]
    assert stages[0][:2] == ["nmrPipe", "-in"]  # first stage reads the file
    assert "-out" in stages[-1] and "-fn" in stages[-1]  # last transposes + writes
    assert stages[-1][stages[-1].index("-fn") + 1] == "TP"


def test_f2_phase_constants_thread_through(mock_run_stage, tmp_path) -> None:
    """`process_direct()`'s deterministic F2 phase constants (p0/p1) must
    appear verbatim in the nmrPipe PS invocation -- never derived via a
    blind auto-phase search (D-02).

    Implementing plan: Plan 04 (`nus/postprocess.py::process_direct`).
    """
    from lucy_ng.nus.postprocess import process_direct

    converted_fid = tmp_path / "converted.fid"
    converted_fid.write_bytes(b"\x01" * 64)

    process_direct(
        converted_fid, stage_dir=tmp_path, f2_p0=-24.0, f2_p1=0.0, magnitude=False
    )

    argv_str = " ".join(str(a) for a in mock_run_stage["calls"][-1][1])
    assert "-24" in argv_str


def test_magnitude_branch_skips_phase(mock_run_stage, tmp_path) -> None:
    """When `magnitude=True` (COSY, FnMODE=1), `process_direct()`/
    `process_indirect()` must NOT apply a PS (phase) step at all -- COSY is
    processed in magnitude mode (D-02), not phase-corrected.

    Implementing plan: Plan 04 (`nus/postprocess.py::process_direct`).
    """
    from lucy_ng.nus.postprocess import process_direct

    converted_fid = tmp_path / "converted.fid"
    converted_fid.write_bytes(b"\x01" * 64)

    process_direct(
        converted_fid, stage_dir=tmp_path, f2_p0=None, f2_p1=None, magnitude=True
    )

    argv_str = " ".join(str(a) for a in mock_run_stage["calls"][-1][1])
    assert "-fn PS" not in argv_str


def test_ppm_axes_reversed(tmp_path) -> None:
    """The final processed spectrum's ppm axes must be reversed (highest
    ppm first, Bruker convention) on both dimensions -- RECON-02.

    Implementing plan: Plan 04 (`nus/postprocess.py::process_indirect` /
    its ppm-axis helper).
    """
    from lucy_ng.nus.postprocess import ppm_axis_for_dimension

    reconstructed_fid = tmp_path / "reconstructed.ft1"
    reconstructed_fid.write_bytes(b"\x01" * 64)

    axis = ppm_axis_for_dimension(sf=150.9, offset=200.0, sw_h=25000.0, size=1024)

    assert axis[0] > axis[-1]
    # WR-04: Bruker OFFSET is already in ppm -- the axis must START at the
    # OFFSET value (~200 ppm for this 13C window), NOT at offset/sf (~1.3
    # ppm, the old Hz-misinterpretation bug). Pin the start so a regression
    # to dividing OFFSET by SF is caught here rather than silently
    # producing an axis shifted ~140+ ppm off scale.
    assert axis[0] == 200.0


def test_ppm_calibrated_to_1d_reference(tmp_path) -> None:
    """The processed spectrum's ppm calibration must be cross-checked
    against the reliable 1D ground-truth reference shifts (NUS-RECONSTRUCTION-
    GUIDE.md Sec.10) -- the calibration source of truth is the trusted 1D
    data, not the reconstruction itself (RECON-02).

    Implementing plan: Plan 04 (`nus/postprocess.py::process_indirect` /
    its calibration cross-check helper).
    """
    from lucy_ng.nus.postprocess import calibrate_against_1d_reference

    computed_axis = [200.0, 150.0, 100.0, 50.0, 0.0]
    reference_shifts = [145.2, 42.1]

    calibrated_axis, offset_applied = calibrate_against_1d_reference(
        computed_axis, reference_shifts
    )

    assert len(calibrated_axis) == len(computed_axis)
    assert isinstance(offset_applied, float)
