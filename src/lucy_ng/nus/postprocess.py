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
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lucy_ng.models.nus import NusAcquisitionParams


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

    Args:
        reconstructed_fid: SMILE's output
            (`NmrPipeSmileBackend.reconstruct_indirect()`'s return value).
        stage_dir: Directory intermediates are written to (D-03:
            persistent, kept by default).
        params: Already-parsed `NusAcquisitionParams` (Phase 97) -- accepted
            for interface symmetry with `process_direct()`; the ppm-axis
            reversal/1D-calibration cross-check (RECON-02) that will use it
            to label this stage's output axes ships in Task 2 of this plan.
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
    return processed
