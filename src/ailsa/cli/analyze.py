"""CLI commands for analysis tools."""

import json
import re

import click

from ailsa.processing import AdaptivePeakPicker
from ailsa.readers import BrukerReader


@click.group()
def analyze() -> None:
    """Analysis tools for structure elucidation."""
    pass


@analyze.command("symmetry")
@click.argument("formula")
@click.argument("c13_path", type=click.Path(exists=True))
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=None,
    help="Peak threshold (auto if not set).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def analyze_symmetry(
    formula: str, c13_path: str, threshold: float | None, output_format: str
) -> None:
    """Compare observed 13C peaks with expected carbon count from formula.

    FORMULA is the molecular formula (e.g., C13H18O2).
    C13_PATH is the path to the 13C Bruker experiment.

    Returns raw comparison of observed signal count vs expected carbon count.
    The AI agent interprets the difference using symmetry detection knowledge.
    """
    # Read 1D spectrum
    spectrum = BrukerReader.read_1d(c13_path)

    # Pick peaks
    picker = AdaptivePeakPicker()
    if threshold is not None:
        peaks = picker.pick_peaks(spectrum, threshold=threshold)
    else:
        peaks = picker.pick_peaks(spectrum)

    # Parse carbon count from formula
    match = re.search(r'C(\d+)', formula)
    if not match:
        click.echo("Error: Could not parse carbon count from formula", err=True)
        raise SystemExit(1)

    expected_carbons = int(match.group(1))
    observed_peaks = len(peaks.peaks)
    difference = expected_carbons - observed_peaks

    if output_format == "json":
        data = {
            "formula": formula,
            "expected_carbons": expected_carbons,
            "observed_peaks": observed_peaks,
            "difference": difference,
            "overcount_alarm": difference < 0,
            "overcount_excess": max(0, -difference),
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Symmetry Analysis for {formula}")
        click.echo(f"  Expected carbons: {expected_carbons}")
        click.echo(f"  Observed peaks: {observed_peaks}")
        click.echo(f"  Difference: {difference}")
        if difference > 0:
            click.echo(f"  → {difference} carbons may be equivalent due to symmetry")
        elif difference < 0:
            click.echo(
                f"  → Warning: more signals than carbons ({observed_peaks} observed vs"
                f" {expected_carbons} expected) — likely noise, not symmetry."
                " Re-pick with --snr-floor 5 or higher before proceeding."
            )


@analyze.command("grouping")
@click.argument("shifts")
@click.option(
    "--multiplicities",
    "-m",
    type=str,
    default=None,
    help="Comma-separated DEPT multiplicities (CH, CH2, CH3, CH/CH3).",
)
@click.option(
    "--tolerance",
    "-t",
    type=float,
    default=0.25,
    help="Distance tolerance in ppm (default: 0.25).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def analyze_grouping(
    shifts: str,
    multiplicities: str | None,
    tolerance: float,
    output_format: str,
) -> None:
    """Group carbon signals by proximity and multiplicity compatibility.

    SHIFTS is a comma-separated list of chemical shifts (e.g., "44.90,45.03,129.38").

    Uses complete linkage clustering with optional DEPT multiplicity filtering.
    Output includes LSD-compatible atom lists for combinatorial exchange commands.
    """
    # Lazy import
    from ailsa.detection.grouping import group_signals

    # Parse shifts
    try:
        shift_list = [float(s.strip()) for s in shifts.split(",")]
    except ValueError as err:
        click.echo("Error: Invalid shift format. Use comma-separated floats.", err=True)
        raise SystemExit(1) from err

    # Parse multiplicities if provided
    mult_list: list[str | None] | None = None
    if multiplicities is not None:
        mult_list = [m.strip() if m.strip() else None for m in multiplicities.split(",")]
        if len(mult_list) != len(shift_list):
            click.echo(
                f"Error: Multiplicity count ({len(mult_list)}) must match "
                f"shift count ({len(shift_list)})",
                err=True,
            )
            raise SystemExit(1)

    # Run grouping
    result = group_signals(shift_list, mult_list, tolerance=tolerance)

    # Output
    if output_format == "json":
        click.echo(result.model_dump_json(indent=2))
    else:
        # Custom text format with LSD atom lists and per-atom details
        click.echo(f"Signal Grouping (tolerance: {tolerance} ppm)")
        click.echo(f"Total signals: {result.total_signals}")
        click.echo(f"Groups found: {len(result.groups)}")
        click.echo(f"Ungrouped: {len(result.ungrouped)}")

        if result.groups:
            click.echo("")
            click.echo("Groups:")
            for i, group in enumerate(result.groups, 1):
                # Show LSD atom list
                click.echo(f"  Group {i}: {group.lsd_atom_list()}")

                # Show per-atom details
                for atom_id, shift, idx in zip(
                    group.atom_ids, group.shifts, group.indices, strict=True
                ):
                    mult_str = ""
                    if group.multiplicities is not None:
                        idx_in_group = group.indices.index(idx)
                        if group.multiplicities[idx_in_group] is not None:
                            mult_str = f" ({group.multiplicities[idx_in_group]})"
                    click.echo(f"    Atom {atom_id}: {shift:.2f} ppm{mult_str}")

                # Show span and centroid
                click.echo(f"    Span: {group.span:.3f} ppm, Centroid: {group.centroid:.2f} ppm")

        if result.ungrouped:
            click.echo("")
            click.echo("Ungrouped (single atoms):")
            for idx in result.ungrouped:
                atom_id = idx + 1  # Convert to 1-based
                shift = shift_list[idx]
                mult_str = ""
                if mult_list is not None and mult_list[idx] is not None:
                    mult_str = f" ({mult_list[idx]})"
                click.echo(f"  Atom {atom_id}: {shift:.2f} ppm{mult_str}")

        if result.warnings:
            click.echo("")
            click.echo("Warnings:")
            for warning in result.warnings:
                click.echo(f"  {warning}")

        # Always show false positive warning
        click.echo("")
        click.echo("Note: Close shifts may represent truly different carbons.")
        click.echo("Verify by checking DEPT multiplicities and HMBC connectivity.")
