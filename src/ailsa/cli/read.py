"""CLI commands for reading NMR spectra."""

import json

import click

from ailsa.readers import BrukerReader


@click.group()
def read() -> None:
    """Read NMR spectra."""
    pass


@read.command("1d")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def read_1d(path: str, output_format: str) -> None:
    """Read a Bruker 1D spectrum and display info.

    PATH is the path to the Bruker experiment directory.
    """
    spectrum = BrukerReader.read_1d(path)

    if output_format == "json":
        # Use to_dict for JSON serialization (handles numpy arrays)
        data = {
            "nucleus": spectrum.nucleus,
            "frequency": spectrum.frequency,
            "solvent": spectrum.solvent,
            "points": len(spectrum.data),
            "ppm_min": float(spectrum.ppm_scale.min()),
            "ppm_max": float(spectrum.ppm_scale.max()),
            "metadata": spectrum.metadata,
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Nucleus: {spectrum.nucleus}")
        click.echo(f"Frequency: {spectrum.frequency:.2f} MHz")
        if spectrum.solvent:
            click.echo(f"Solvent: {spectrum.solvent}")
        click.echo(f"Points: {len(spectrum.data)}")
        click.echo(
            f"PPM range: {spectrum.ppm_scale.min():.2f} - {spectrum.ppm_scale.max():.2f}"
        )


@read.command("2d")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def read_2d(path: str, output_format: str) -> None:
    """Read a Bruker 2D spectrum and display info.

    PATH is the path to the Bruker experiment directory.
    """
    spectrum = BrukerReader.read_2d(path)

    if output_format == "json":
        data = {
            "experiment_type": spectrum.experiment_type,
            "f1_nucleus": spectrum.f1_nucleus,
            "f2_nucleus": spectrum.f2_nucleus,
            "frequency": spectrum.frequency,
            "shape": list(spectrum.data.shape),
            "f1_ppm_min": float(spectrum.f1_ppm_scale.min()),
            "f1_ppm_max": float(spectrum.f1_ppm_scale.max()),
            "f2_ppm_min": float(spectrum.f2_ppm_scale.min()),
            "f2_ppm_max": float(spectrum.f2_ppm_scale.max()),
            "metadata": spectrum.metadata,
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Experiment: {spectrum.experiment_type}")
        click.echo(f"F1 nucleus: {spectrum.f1_nucleus}")
        click.echo(f"F2 nucleus: {spectrum.f2_nucleus}")
        click.echo(f"Frequency: {spectrum.frequency:.2f} MHz")
        click.echo(f"Shape: {spectrum.data.shape[0]} x {spectrum.data.shape[1]}")
        click.echo(
            f"F1 PPM range: {spectrum.f1_ppm_scale.min():.2f} - "
            f"{spectrum.f1_ppm_scale.max():.2f}"
        )
        click.echo(
            f"F2 PPM range: {spectrum.f2_ppm_scale.min():.2f} - "
            f"{spectrum.f2_ppm_scale.max():.2f}"
        )
