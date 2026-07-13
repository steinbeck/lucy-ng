"""NUS direct/indirect-dimension post-processing (RECON-02).

Two functions, TWO run_stage-checked stages, bracketing the SMILE call
(SMILE manual Sec.4/Sec.6.1 -- the direct dimension must be fully processed
and transposed BEFORE SMILE can run):

* `process_direct()` -- apodizes/zero-fills/Fourier-transforms/phases/
  baseline-corrects the DIRECT (F2) dimension, THEN transposes (TP). Its
  output (`f2_processed.fid`) IS SMILE's actual input -- a transposed,
  F2-processed FID, never a raw time-domain FID. Runs BEFORE
  `NmrPipeSmileBackend.reconstruct_indirect()` (Plan 03).
* `process_indirect()` -- runs AFTER SMILE: the post-SMILE INDIRECT (F1)
  ZF/FT/phase chain, a final transpose (TP), producing `processed.ft2`.

Phase (F2 `p0`/`p1`, F1 `p0`/`p1`) is always a passed-in, CLI-overridable
constant -- never computed by a blind auto-phase search (D-02). The
magnitude (COSY) branch skips the phase-correction verb entirely.

Each function dispatches its ENTIRE verb chain as ONE `nmrPipe` invocation
with multiple chained `-fn` blocks (idiomatic NMRPipe processing-script
usage -- this is NOT unix-pipe chaining and needs no shell at all: NMRPipe's
own CLI parser applies each `-fn` block in sequence within a single process).
This keeps the whole stage as ONE `subprocess.run()` call (RECON-04's "one
subprocess per pipeline stage" contract) with zero shell interpretation
(never a shell-invocation flag, never string-interpolated user input --
every value threaded into `argv` is a typed float/int or a resolved `Path`).

Also provides the ppm-axis reversal + 1D-calibration cross-check helpers
(pure arithmetic, no external tool) that `process_indirect()` uses to label
its output axes.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lucy_ng.models.nus import NusAcquisitionParams

#: Ground-truth 1D 13C shifts (NUS-RECONSTRUCTION-GUIDE.md Sec.10) -- the
#: calibration cross-check's source of truth is this trusted 1D data, never
#: the reconstruction itself (D-02).
GUIDE_S10_C13: list[float] = [
    142.00,
    135.86,
    79.35,
    69.06,
    67.06,
    51.63,
    37.86,
    37.19,
    36.23,
    35.23,
    34.21,
    33.67,
    30.66,
    29.77,
    27.93,
    27.15,
    25.96,
    23.43,
    22.63,
    21.78,
]

#: Default calibration-check tolerance, in ppm, for `check_calibration()`.
DEFAULT_CALIBRATION_TOL = 0.5


def process_direct(
    converted_fid: Path,
    stage_dir: Path,
    params: NusAcquisitionParams | None = None,
    *,
    f2_p0: float | None,
    f2_p1: float | None,
    magnitude: bool,
    timeout: int = 600,
) -> Path:
    """Process the DIRECT (F2) dimension, then transpose -- SMILE's input.

    Builds ONE `nmrPipe` invocation apodizing/zero-filling/Fourier-
    transforming/phasing/baseline-correcting the direct dimension, THEN a
    final transpose (`TP`) -- the literal, mechanical enforcement of
    RECON-02's F2-before-F1 gate (SMILE manual Sec.4: "the direct dimension
    must be first apodized, zero filled, Fourier transformed, and phased...
    before... the SMILE function can be called"). Does NOT call SMILE.

    Args:
        converted_fid: The still-time-domain FID from
            `NmrPipeSmileBackend.convert()` (Plan 03).
        stage_dir: Directory intermediates are written to (D-03:
            persistent, kept by default).
        params: Already-parsed `NusAcquisitionParams` (Phase 97), currently
            unused by the verb chain itself (apodization window/ZF factor
            are fixed defaults) but accepted for interface symmetry with
            `process_indirect()` and future per-acquisition tuning. Optional
            -- `None` is a legitimate value when only the deterministic
            phase constants are needed.
        f2_p0: F2 zero-order phase (`nmrPipe -fn PS -p0`) -- a fixed,
            CLI-overridable constant (D-02), never computed by a search.
            Required unless `magnitude` is True (COSY skips phase
            entirely), in which case it is ignored.
        f2_p1: F2 first-order phase (`-fn PS -p1`). Same contract as
            `f2_p0`.
        magnitude: True for magnitude-mode (COSY, FnMODE 1/2) processing --
            omits the `PS` phase-correction verb entirely.
        timeout: Per-stage subprocess timeout in seconds, forwarded to
            `run_stage()`.

    Returns:
        Path to the transposed, F2-processed FID (`stage_dir/f2_processed.fid`)
        -- this is SMILE's actual input, never a raw time-domain FID.
    """
    from lucy_ng.nus.runner import run_stage

    converted_fid = Path(converted_fid)
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    f2_processed = stage_dir / "f2_processed.fid"

    argv: list[str] = [
        "nmrPipe",
        "-in",
        str(converted_fid),
        "-fn",
        "SP",
        "-off",
        "0.5",
        "-end",
        "0.98",
        "-pow",
        "2",
        "-c",
        "1.0",
        "-fn",
        "ZF",
        "-auto",
        "-fn",
        "FT",
    ]
    if not magnitude:
        argv += [
            "-fn",
            "PS",
            "-p0",
            str(f2_p0),
            "-p1",
            str(f2_p1),
            "-di",
        ]
    argv += [
        "-fn",
        "POLY",
        "-auto",
        "-ord",
        "2",
        "-fn",
        "TP",
        "-verb",
        "-ov",
        "-out",
        str(f2_processed),
    ]

    run_stage(
        "process_direct",
        argv,
        cwd=stage_dir,
        expected_output=f2_processed,
        timeout=timeout,
    )
    return f2_processed


def process_indirect(
    reconstructed_fid: Path,
    stage_dir: Path,
    params: NusAcquisitionParams | None = None,
    *,
    f1_p0: float | None,
    f1_p1: float | None,
    magnitude: bool,
    timeout: int = 600,
) -> Path:
    """Process the post-SMILE INDIRECT (F1) dimension, then transpose.

    Builds ONE `nmrPipe` invocation zero-filling/Fourier-transforming/
    phasing the indirect dimension, THEN a final transpose (`TP`), producing
    the final processed 2D spectrum. Runs AFTER
    `NmrPipeSmileBackend.reconstruct_indirect()` (SMILE), never before.

    When `params` carries F1 SF/OFFSET/SW_h calibration fields, the reversed,
    1D-calibrated ppm axis is computed (via `ppm_axis_for_dimension()` +
    `calibrate_against_1d_reference()`) and written to a JSON sidecar
    (`stage_dir/processed_ppm_axis.json`) alongside the binary spectrum --
    pure Python arithmetic, no external tool, kept per D-03's
    persistent-intermediates convention. Missing/`None` calibration fields
    (a legitimate pre-processing state) simply skip this labeling step.

    Args:
        reconstructed_fid: SMILE's output
            (`NmrPipeSmileBackend.reconstruct_indirect()`'s return value).
        stage_dir: Directory intermediates are written to (D-03:
            persistent, kept by default).
        params: Already-parsed `NusAcquisitionParams` (Phase 97), used only
            for the optional ppm-axis calibration sidecar. Optional.
        f1_p0: F1 zero-order phase (`nmrPipe -fn PS -p0`) -- a fixed,
            CLI-overridable constant (D-02), never computed by a search.
            Ignored when `magnitude` is True.
        f1_p1: F1 first-order phase (`-fn PS -p1`). Same contract as
            `f1_p0`.
        magnitude: True for magnitude-mode (COSY, FnMODE 1/2) processing --
            omits the `PS` phase-correction verb entirely.
        timeout: Per-stage subprocess timeout in seconds, forwarded to
            `run_stage()`.

    Returns:
        Path to the final processed spectrum (`stage_dir/processed.ft2`).
    """
    from lucy_ng.nus.runner import run_stage

    reconstructed_fid = Path(reconstructed_fid)
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    processed = stage_dir / "processed.ft2"

    argv: list[str] = [
        "nmrPipe",
        "-in",
        str(reconstructed_fid),
        "-fn",
        "ZF",
        "-auto",
        "-fn",
        "FT",
    ]
    if not magnitude:
        argv += [
            "-fn",
            "PS",
            "-p0",
            str(f1_p0),
            "-p1",
            str(f1_p1),
            "-di",
        ]
    argv += [
        "-fn",
        "TP",
        "-verb",
        "-ov",
        "-out",
        str(processed),
    ]

    run_stage(
        "process_indirect",
        argv,
        cwd=stage_dir,
        expected_output=processed,
        timeout=timeout,
    )

    _write_ppm_calibration_sidecar(stage_dir, params)

    return processed


def _write_ppm_calibration_sidecar(
    stage_dir: Path, params: NusAcquisitionParams | None
) -> None:
    """Best-effort ppm-axis reversal + 1D-calibration sidecar (RECON-02).

    Pure arithmetic, no external tool. Silently no-ops when `params` is
    `None` or its F1 SF/OFFSET/SW_h calibration fields are not yet
    populated (a legitimate pre-processing state, not an error).
    """
    if params is None:
        return
    if params.f1_sf is None or params.f1_offset is None:
        return

    import json

    axis = ppm_axis_for_dimension(
        sf=params.f1_sf,
        offset=params.f1_offset,
        sw_h=params.f1_sw_h,
        size=params.nus_td,
    )
    calibrated_axis, offset_applied = calibrate_against_1d_reference(
        axis, GUIDE_S10_C13
    )
    sidecar = stage_dir / "processed_ppm_axis.json"
    sidecar.write_text(
        json.dumps(
            {
                "raw_ppm_axis": axis,
                "calibrated_ppm_axis": calibrated_axis,
                "calibration_offset_ppm": offset_applied,
                "reference_shifts": GUIDE_S10_C13,
            },
            indent=2,
        )
    )


def ppm_scale(sf: float, offset: float, sw_h: float, size: int) -> list[float]:
    """Compute a reversed ppm axis (highest ppm first -- Bruker convention).

    Args:
        sf: Spectrometer frequency (MHz) for this dimension (`SF`).
        offset: ppm-scale offset (Hz), the highest-frequency edge of the
            spectral window (`OFFSET`).
        sw_h: Spectral width in Hz (`SW_h`).
        size: Number of points in the axis.

    Returns:
        A list of `size` ppm values, descending (`scale[0] > scale[-1]`) --
        index 0 is the highest ppm, matching Bruker/NMRPipe display
        convention.

    Raises:
        ValueError: If `size` is not positive.
    """
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    hz_per_point = sw_h / size
    return [(offset - i * hz_per_point) / sf for i in range(size)]


def ppm_axis_for_dimension(
    sf: float, offset: float, sw_h: float, size: int
) -> list[float]:
    """Alias for `ppm_scale()` -- the per-dimension reversed ppm axis.

    Kept as a distinctly-named entry point (`process_indirect()`'s own
    F1-axis labeling call site reads more clearly as
    "ppm axis for [this] dimension") while sharing `ppm_scale()`'s single
    implementation -- see `ppm_scale()` for the full contract.
    """
    return ppm_scale(sf=sf, offset=offset, sw_h=sw_h, size=size)


def calibrate_against_1d_reference(
    computed_axis: Sequence[float],
    reference_shifts: Sequence[float],
    tol: float = 5.0,
) -> tuple[list[float], float]:
    """Cross-check + calibrate a computed ppm axis against 1D ground truth.

    For each reference shift, finds the nearest point on `computed_axis`
    within `tol` ppm and records the signed difference; the mean of those
    differences is the systematic calibration offset, which is then
    subtracted from every point on `computed_axis`. The calibration source
    of truth is the trusted 1D reference data, never the reconstruction
    itself (D-02/RECON-02).

    Args:
        computed_axis: The reconstructed spectrum's raw ppm axis (e.g. from
            `ppm_axis_for_dimension()`).
        reference_shifts: Ground-truth 1D shifts to calibrate against
            (e.g. `GUIDE_S10_C13`).
        tol: Maximum ppm distance for a reference shift to be considered a
            match to a computed-axis point (default 5.0 ppm -- generous,
            since the *uncalibrated* axis may carry a real systematic
            offset this function exists to detect and correct).

    Returns:
        A `(calibrated_axis, offset_applied)` tuple: `calibrated_axis` has
        the same length as `computed_axis` with the offset subtracted;
        `offset_applied` is the mean signed offset found (`0.0` if no
        reference shift matched within `tol`, or if `reference_shifts` is
        empty -- no calibration correction applied in either case).
    """
    computed = list(computed_axis)
    if not reference_shifts or not computed:
        return computed, 0.0

    deltas: list[float] = []
    for ref in reference_shifts:
        nearest = min(computed, key=lambda c: abs(c - ref))
        if abs(nearest - ref) <= tol:
            deltas.append(nearest - ref)

    if not deltas:
        return computed, 0.0

    offset_applied = sum(deltas) / len(deltas)
    calibrated = [c - offset_applied for c in computed]
    return calibrated, offset_applied


def check_calibration(
    observed_ppms: Sequence[float],
    reference_ppms: Sequence[float] = tuple(GUIDE_S10_C13),
    tol: float = DEFAULT_CALIBRATION_TOL,
) -> bool:
    """Flag whether a set of observed carbon shifts is well-calibrated.

    A thin decision wrapper over `calibrate_against_1d_reference()`: returns
    `False` (flagged) when the detected systematic offset exceeds `tol`
    ppm, `True` otherwise. Intended as a post-reconstruction sanity check,
    not a correction step -- `calibrate_against_1d_reference()` is what
    actually corrects the axis.

    Args:
        observed_ppms: Reconstructed carbon shifts to check.
        reference_ppms: Ground-truth 1D reference shifts (default
            `GUIDE_S10_C13`).
        tol: Maximum acceptable systematic offset, in ppm, before flagging
            (default `DEFAULT_CALIBRATION_TOL`).

    Returns:
        `True` if the systematic offset is within `tol` ppm (well
        calibrated, or no reference match found to compare against),
        `False` if a systematic offset beyond `tol` is detected.
    """
    _calibrated, offset_applied = calibrate_against_1d_reference(
        observed_ppms, reference_ppms, tol=max(tol * 10, 5.0)
    )
    return abs(offset_applied) <= tol
