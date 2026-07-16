"""Lucy NUS (Non-Uniform Sampling) reconstruction CLI commands.

This module is import-safe: it does NOT import ``lucy_ng.nus.params``,
``lucy_ng.nus.schedule``, ``lucy_ng.nus.backends``, or ``lucy_ng.nus.runner``
at the top level. All ``lucy_ng.nus.*`` imports are deferred into command
bodies so that the core ``lucy`` CLI stays importable without the optional
``[nus]`` extra (NUS-05).

Phase 97 implemented the ``check``/``params``/``schedule`` subcommands
(backend detection + pure-Python acquisition/schedule parsing). Phase 98
(Plan 06) added ``reconstruct`` -- the whole-pipeline CLI wrapper around
``lucy_ng.nus.runner.NusRunner`` -- following the exact same deferred-import
convention. Phase 99 (Plan 04) adds ``qc`` (the standalone QC-02 gate,
D-08's ``lucy nus qc <peaks-dir>`` contract) and ``pipeline`` (the full
params -> schedule -> reconstruct -> process -> peak-pick -> QC chain,
D-07's write/quarantine boundary) -- both following the same deferred-import
convention; ``case.md`` and the CASE pipeline are not touched by either.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from lucy_ng.nus.qc import QcConfig


@click.group()
def nus() -> None:
    """NUS (Non-Uniform Sampling) 2D reconstruction commands."""


def _build_qc_config(
    ridge_fail: float | None,
    coverage_floor: float | None,
    c13_tol: float | None,
    h1_tol: float | None,
) -> QcConfig:
    """Build a `QcConfig` from optional CLI threshold overrides (D-04).

    `None` values keep `QcConfig.default()`'s seed thresholds; only
    explicitly-passed flags override -- shared by `qc` and `pipeline` so
    the two commands' threshold-override semantics never diverge.
    """
    from lucy_ng.nus.qc import QcConfig

    defaults = QcConfig.default()
    return QcConfig(
        c13_tol=c13_tol if c13_tol is not None else defaults.c13_tol,
        h1_tol=h1_tol if h1_tol is not None else defaults.h1_tol,
        ridge_fraction_fail=(
            ridge_fail if ridge_fail is not None else defaults.ridge_fraction_fail
        ),
        hsqc_coverage_floor=(
            coverage_floor if coverage_floor is not None else defaults.hsqc_coverage_floor
        ),
        edited_sign_tol=defaults.edited_sign_tol,
        cosy_symmetry_floor=defaults.cosy_symmetry_floor,
        known_quaternary_shifts=defaults.known_quaternary_shifts,
    )


@nus.command("check")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def check(output_format: str) -> None:
    """Check NMRPipe+SMILE reconstruction backend availability.

    Reports whether the required external tools (nmrPipe, bruk2pipe,
    nusExpand.tcl) are on PATH and whether the SMILE plugin capability probe
    succeeds. Exits 1 when the backend is not usable.
    """
    from lucy_ng.nus.backends import get_backend

    backend = get_backend()
    diagnosis = backend.diagnose()
    usable = diagnosis["status"] == "available"

    if output_format == "json":
        click.echo(json.dumps(diagnosis, indent=2))
    else:
        if usable:
            click.echo("NMRPipe+SMILE: available")
        else:
            click.echo(
                f"NMRPipe+SMILE: not available ({diagnosis['status']})", err=True
            )
            if diagnosis["missing_tools"]:
                click.echo(
                    f"  Missing tools: {', '.join(diagnosis['missing_tools'])}"
                )
            click.echo(f"  {diagnosis['hint']}")

    if not usable:
        raise SystemExit(1)


@nus.command("params")
@click.argument("expdir", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def params(expdir: str, output_format: str) -> None:
    """Parse Bruker NUS acquisition + calibration parameters from EXPDIR.

    EXPDIR is a Bruker NUS experiment directory (contains acqus, acqu2s,
    pdata/1/procs, pdata/1/proc2s).
    """
    from lucy_ng.nus.params import read_nus_params

    resolved = Path(expdir).resolve()
    model = read_nus_params(resolved)

    if output_format == "json":
        click.echo(json.dumps(model.to_dict(), indent=2))
    else:
        click.echo(f"Pulse program: {model.pulse_program}")
        click.echo(
            f"F2 ({model.f2_nucleus}): SFO1={model.f2_sfo1} SW_h={model.f2_sw_h} "
            f"TD={model.f2_td}"
        )
        click.echo(
            f"F1 ({model.f1_nucleus}): SFO1={model.f1_sfo1} SW_h={model.f1_sw_h} "
            f"O1={model.f1_o1} TD={model.f1_td} FnMODE={model.fnmode_f1}"
        )
        click.echo(
            f"NUS: amount={model.nus_amount_pct}% seed={model.nus_seed} "
            f"NusTD={model.nus_td}"
        )
        click.echo(
            f"Calibration: F2 SF={model.f2_sf} OFFSET={model.f2_offset}; "
            f"F1 SF={model.f1_sf} OFFSET={model.f1_offset}"
        )


@nus.command("schedule")
@click.argument("expdir", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def schedule(expdir: str, output_format: str) -> None:
    """Parse the Bruker NUS sampling schedule (nuslist) from EXPDIR.

    EXPDIR is a Bruker NUS experiment directory (contains acqus, acqu2s,
    nuslist). The FnMODE-derived sample-count assertion (NUS-03) runs before
    any output is produced -- a mismatch raises and this command fails loud.
    """
    from lucy_ng.nus.schedule import read_nus_schedule

    resolved = Path(expdir).resolve()
    model = read_nus_schedule(resolved)

    if output_format == "json":
        click.echo(json.dumps(model.to_dict(), indent=2))
    else:
        click.echo(f"FnMODE (F1): {model.fnmode_f1}")
        click.echo(f"TD (F1): {model.td_f1}")
        click.echo(f"NusTD: {model.nus_td}")
        click.echo(f"Sampled points: {model.n_sampled} / {model.nus_td}")


@nus.command("reconstruct")
@click.argument("expdir", type=click.Path(exists=True))
@click.option(
    "--iterations",
    type=int,
    default=500,
    show_default=True,
    help=(
        "SMILE -maxIter upper bound. This is NOT the sole stopping rule -- "
        "the real stopping condition is the -nSigma/-thresh noise-threshold "
        "convergence check; -maxIter only prevents an unbounded run."
    ),
)
@click.option(
    "--threshold",
    type=float,
    default=0.8,
    show_default=True,
    help="SMILE -thresh value (noise-threshold convergence check).",
)
@click.option(
    "--virtual-echo/--no-virtual-echo",
    "virtual_echo",
    default=True,
    show_default=True,
    help=(
        "Request virtual-echo/Echo-AntiEcho (-EA) reconstruction when the "
        "FnMODE recipe allows it (echo-antiecho experiments only; ignored "
        "for QF/magnitude-mode FnMODEs)."
    ),
)
@click.option(
    "--f2-p0",
    type=float,
    default=0.0,
    show_default=True,
    help="F2 (direct-dimension) zero-order phase override (D-02, PROVISIONAL default).",
)
@click.option(
    "--f2-p1",
    type=float,
    default=0.0,
    show_default=True,
    help="F2 (direct-dimension) first-order phase override (D-02).",
)
@click.option(
    "--f1-p0",
    type=float,
    default=90.0,
    show_default=True,
    help="F1 (indirect-dimension) zero-order phase override (D-02, PROVISIONAL default).",
)
@click.option(
    "--f1-p1",
    type=float,
    default=0.0,
    show_default=True,
    help="F1 (indirect-dimension) first-order phase override (D-02).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def reconstruct(
    expdir: str,
    iterations: int,
    threshold: float,
    virtual_echo: bool,
    f2_p0: float,
    f2_p1: float,
    f1_p0: float,
    f1_p1: float,
    output_format: str,
) -> None:
    """Run the whole NUS reconstruction + processing pipeline on EXPDIR.

    EXPDIR is a Bruker NUS experiment directory (contains `ser`, `nuslist`,
    `acqus`, `acqu2s`). Drives bruk2pipe -> nusExpand.tcl -> SMILE ->
    FT/phase/baseline fully automatically (RECON-01), enforcing the
    F2-before-F1 hard ordering gate (RECON-02) and FnMODE-aware branching
    (RECON-03) via `NusRunner.reconstruct()`. Intermediates are written to
    `analysis/nus_recon/<expN>/` under EXPDIR and kept (D-03).
    """
    from lucy_ng.nus.runner import NusRunner

    resolved = Path(expdir).resolve()
    result = NusRunner().reconstruct(
        resolved,
        max_iter=iterations,
        threshold=threshold,
        virtual_echo=virtual_echo,
        f1_p0=f1_p0,
        f1_p1=f1_p1,
        f2_p0=f2_p0,
        f2_p1=f2_p1,
    )

    if output_format == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        click.echo(f"Backend: {result.backend}")
        click.echo(f"Success: {result.success}")
        click.echo(f"Stage dir: {result.stage_dir}")
        click.echo(f"Processed spectrum: {result.processed_spectrum}")


@nus.command("qc")
@click.argument("peaks_dir", type=click.Path(exists=True))
@click.option(
    "--ridge-fail",
    type=float,
    default=None,
    help="Override the signal-to-ridge FAIL threshold (D-04, default 0.5).",
)
@click.option(
    "--coverage-floor",
    type=float,
    default=None,
    help="Override the HSQC-coverage FAIL floor (D-04, default 0.8).",
)
@click.option(
    "--c13-tol",
    type=float,
    default=None,
    help="Override the 13C tolerance in ppm (D-04, default 0.5).",
)
@click.option(
    "--h1-tol",
    type=float,
    default=None,
    help="Override the 1H tolerance in ppm (D-04, default 0.05).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def qc(
    peaks_dir: str,
    ridge_fail: float | None,
    coverage_floor: float | None,
    c13_tol: float | None,
    h1_tol: float | None,
    output_format: str,
) -> None:
    """Run the headless QC gate (QC-01/QC-02) against PEAKS_DIR.

    PEAKS_DIR is any directory containing reconstructed HSQC/HMBC/COSY
    cross-peak JSON files (keyword-glob matched, e.g. `HSQC_exp3.json` or
    `HSQC.json` -- never a hardcoded experiment-number suffix, D-08) plus
    the trusted 1D reference lists (`13C_exp*.json`/`1H_exp1.json`, D-03).
    Cross-checks every reconstructed correlation via six named checks
    (D-02: quaternary-carbon exclusion, ppm calibration, signal-to-ridge,
    HSQC coverage critical; edited-sign self-consistency, COSY diagonal
    symmetry soft) and exits non-zero on a FAIL verdict (QC-03).
    """
    from lucy_ng.nus.qc import run_qc_checks

    resolved = Path(peaks_dir).resolve()
    config = _build_qc_config(ridge_fail, coverage_floor, c13_tol, h1_tol)
    report = run_qc_checks(resolved, config)

    if output_format == "json":
        click.echo(json.dumps(report.to_dict(), indent=2))
    else:
        click.echo(f"QC verdict: {report.verdict.value}")
        violated = report.violated_checks()
        if violated:
            click.echo(f"Violated checks: {', '.join(violated)}")
        else:
            click.echo("All checks passed.")
        if report.errors:
            click.echo(f"Errors: {'; '.join(report.errors)}")

    if report.verdict.value == "FAIL":
        raise SystemExit(1)


@nus.command("pipeline")
@click.argument("expdir", type=click.Path(exists=True))
@click.option(
    "--iterations",
    type=int,
    default=500,
    show_default=True,
    help=(
        "SMILE -maxIter upper bound, forwarded to NusRunner.reconstruct() "
        "(RECON-05)."
    ),
)
@click.option(
    "--threshold",
    type=float,
    default=0.8,
    show_default=True,
    help="SMILE -thresh value (noise-threshold convergence check).",
)
@click.option(
    "--virtual-echo/--no-virtual-echo",
    "virtual_echo",
    default=True,
    show_default=True,
    help=(
        "Request virtual-echo/Echo-AntiEcho (-EA) reconstruction when the "
        "FnMODE recipe allows it (echo-antiecho experiments only; ignored "
        "for QF/magnitude-mode FnMODEs)."
    ),
)
@click.option(
    "--f2-p0",
    type=float,
    default=0.0,
    show_default=True,
    help="F2 (direct-dimension) zero-order phase override (D-02, PROVISIONAL default).",
)
@click.option(
    "--f2-p1",
    type=float,
    default=0.0,
    show_default=True,
    help="F2 (direct-dimension) first-order phase override (D-02).",
)
@click.option(
    "--f1-p0",
    type=float,
    default=90.0,
    show_default=True,
    help="F1 (indirect-dimension) zero-order phase override (D-02, PROVISIONAL default).",
)
@click.option(
    "--f1-p1",
    type=float,
    default=0.0,
    show_default=True,
    help="F1 (indirect-dimension) first-order phase override (D-02).",
)
@click.option(
    "--ridge-fail",
    type=float,
    default=None,
    help="Override the signal-to-ridge FAIL threshold (D-04, default 0.5).",
)
@click.option(
    "--coverage-floor",
    type=float,
    default=None,
    help="Override the HSQC-coverage FAIL floor (D-04, default 0.8).",
)
@click.option(
    "--c13-tol",
    type=float,
    default=None,
    help="Override the 13C tolerance in ppm (D-04, default 0.5).",
)
@click.option(
    "--h1-tol",
    type=float,
    default=None,
    help="Override the 1H tolerance in ppm (D-04, default 0.05).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def pipeline(
    expdir: str,
    iterations: int,
    threshold: float,
    virtual_echo: bool,
    f2_p0: float,
    f2_p1: float,
    f1_p0: float,
    f1_p1: float,
    ridge_fail: float | None,
    coverage_floor: float | None,
    c13_tol: float | None,
    h1_tol: float | None,
    output_format: str,
) -> None:
    """Run the full NUS pipeline on EXPDIR: reconstruct -> peak-pick -> QC -> write.

    EXPDIR is a Bruker NUS experiment directory (contains `ser`, `nuslist`,
    `acqus`, `acqu2s`). Wires params -> schedule -> reconstruct
    (`NusRunner.reconstruct()`, Phase 98, unchanged) -> peak-pick
    (`nus.bridge`, Phase 99) -> QC (`nus.qc.run_qc_checks()` -- the SAME
    code path `lucy nus qc` calls standalone, D-08) -> write-boundary
    enforcement in one process (D-07):

    \b
    - PASS/PARTIAL: writes the verdict-annotated consumable peaks to
      `analysis/nmr_peaks/*.json` (D-05 metadata block, D-06 confidence).
      PARTIAL additionally prints a warning naming the soft violations.
    - FAIL: writes nothing to `analysis/nmr_peaks/`; quarantines the
      verdict-annotated peaks + the QC report to
      `analysis/nus_recon/<expN>/qc_failed/` and exits non-zero (QC-03,
      extending the FIX-10 constraint-hardness-guard spirit to
      reconstruction-derived peaks). `case.md` is not touched -- this is
      the single pipeline-boundary barrier (D-07).
    """
    from lucy_ng.models.nus import QcVerdict
    from lucy_ng.nus.bridge import bridge_peak_pick, build_spectrum2d, write_peak_json
    from lucy_ng.nus.params import read_nus_params
    from lucy_ng.nus.qc import run_qc_checks
    from lucy_ng.nus.runner import NusRunner
    from lucy_ng.readers.bruker import _detect_experiment_type

    resolved = Path(expdir).resolve()
    config = _build_qc_config(ridge_fail, coverage_floor, c13_tol, h1_tol)

    params = read_nus_params(resolved)
    experiment_type = _detect_experiment_type(
        params.pulse_program, params.f1_nucleus, params.f2_nucleus
    )

    result = NusRunner().reconstruct(
        resolved,
        max_iter=iterations,
        threshold=threshold,
        virtual_echo=virtual_echo,
        f1_p0=f1_p0,
        f1_p1=f1_p1,
        f2_p0=f2_p0,
        f2_p1=f2_p1,
    )
    if not result.processed_spectrum:
        click.echo(
            f"NUS pipeline: reconstruction reported no processed spectrum "
            f"(backend={result.backend!r}).",
            err=True,
        )
        raise SystemExit(1)

    spectrum = build_spectrum2d(Path(result.processed_spectrum), params, experiment_type)
    recon_meta = {"backend": result.backend, "iterations": result.smile_iterations}
    stage_dir = Path(result.stage_dir)

    # STAGED pass (verdict-less): peaks must exist before QC can grade them
    # (the causal-ordering fix, Plan 03's bridge_peak_pick() docstring).
    staged_payload = bridge_peak_pick(
        spectrum, experiment=experiment_type, qc_report=None, recon_meta=recon_meta
    )
    staged_dir = stage_dir / "staged"
    write_peak_json(staged_dir, experiment_type, staged_payload)

    # QC gate -- the SAME code path `lucy nus qc` calls standalone (D-08).
    report = run_qc_checks(staged_dir, config)

    nmr_peaks_dir = resolved / "analysis" / "nmr_peaks"
    written: list[str] = []
    quarantine: str | None = None

    if report.verdict == QcVerdict.FAIL:
        # bridge_peak_pick() intentionally refuses to derive a confidence
        # value for a FAIL verdict (D-06 -- FAIL peaks are never
        # consumable, so there is no honest confidence to emit; re-calling
        # it with qc_report=report would raise ValueError). Quarantine the
        # staged (verdict-less) payload with its "reconstruction" block
        # replaced by the real FAIL verdict/violated-checks instead.
        final_payload = dict(staged_payload)
        final_payload["reconstruction"] = {
            "backend": recon_meta["backend"],
            "iterations": recon_meta["iterations"],
            "qc_verdict": report.verdict.value,
            "violated_checks": report.violated_checks(),
            "thresholds_used": dict(report.thresholds_used),
        }
        final_payload["caveat"] = (
            f"Reconstructed via {recon_meta['backend']}. QC verdict: FAIL. "
            f"Violated checks: {', '.join(report.violated_checks())}."
        )
        quarantine_dir = stage_dir / "qc_failed"
        out_path = write_peak_json(quarantine_dir, experiment_type, final_payload)
        (quarantine_dir / "qc_report.json").write_text(json.dumps(report.to_dict(), indent=2))
        quarantine = str(out_path)
        click.echo(
            f"QC verdict FAIL -- critical violations: "
            f"{', '.join(report.critical_violations())}. Peaks quarantined to "
            f"{quarantine_dir}; nothing written to {nmr_peaks_dir}.",
            err=True,
        )
    else:
        # CAUSAL RE-BUILD: peak positions are deterministic for the same
        # spectrum, so this reproduces identical cross-peaks but now
        # stamps the verdict-derived D-05/D-06 metadata/confidence -- the
        # step-3 staged (verdict-less) payload above is never written to
        # the consumable location.
        final_payload = bridge_peak_pick(
            spectrum, experiment=experiment_type, qc_report=report, recon_meta=recon_meta
        )
        out_path = write_peak_json(nmr_peaks_dir, experiment_type, final_payload)
        written.append(str(out_path))
        if report.verdict == QcVerdict.PARTIAL:
            click.echo(
                f"QC verdict PARTIAL -- violated checks: "
                f"{', '.join(report.violated_checks())}. Peaks written to {out_path}.",
                err=True,
            )

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "verdict": report.verdict.value,
                    "written": written,
                    "quarantine": quarantine,
                    "report": report.to_dict(),
                },
                indent=2,
            )
        )
    else:
        click.echo(f"Experiment: {experiment_type}")
        click.echo(f"QC verdict: {report.verdict.value}")
        if written:
            click.echo(f"Written: {', '.join(written)}")
        if quarantine:
            click.echo(f"Quarantined: {quarantine}")

    if report.verdict == QcVerdict.FAIL:
        raise SystemExit(1)
