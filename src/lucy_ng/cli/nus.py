"""Lucy NUS (Non-Uniform Sampling) reconstruction CLI commands.

This module is import-safe: it does NOT import ``lucy_ng.nus.params``,
``lucy_ng.nus.schedule``, or ``lucy_ng.nus.backends`` at the top level. All
``lucy_ng.nus.*`` imports are deferred into command bodies so that the core
``lucy`` CLI stays importable without the optional ``[nus]`` extra (NUS-05).

Phase 97 only implements the ``check``/``params``/``schedule`` subcommands
(backend detection + pure-Python acquisition/schedule parsing). Reconstruction
(``reconstruct``) and the full processing pipeline (``pipeline``) are Phase
98/99 deliverables and are deliberately NOT registered here (D-02: no dead
stubs) -- this establishes the deferred-import convention now so those later
commands slot in without a refactor.
"""

from __future__ import annotations

import json
from pathlib import Path

import click


@click.group()
def nus() -> None:
    """NUS (Non-Uniform Sampling) 2D reconstruction commands."""


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
