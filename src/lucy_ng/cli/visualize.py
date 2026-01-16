"""CLI commands for NMR correlation diagram visualization."""

from __future__ import annotations

import json
import re
from pathlib import Path

import click

from lucy_ng.lsd.models import Hybridization, LSDAtom, LSDCorrelation, LSDProblem
from lucy_ng.visualization import (
    Correlation,
    CorrelationDiagramGenerator,
    CorrelationType,
    DiagramConfig,
)


@click.group()
def visualize() -> None:
    """Visualization tools for NMR correlation diagrams."""
    pass


@visualize.command("correlations")
@click.argument("smiles", required=False)
@click.option(
    "--sol",
    type=click.Path(exists=True),
    help="Path to LSD solution file (.sol) to generate from solved structure.",
)
@click.option(
    "--lsd-file",
    type=click.Path(exists=True),
    help="Path to LSD input file (.lsd) to extract correlations from.",
)
@click.option(
    "--solution",
    default=1,
    type=int,
    help="Solution number to visualize when using --sol (1-based, default: 1).",
)
@click.option(
    "--correlations",
    "-c",
    multiple=True,
    help="Correlations in format 'type:source:target' (e.g., 'HMBC:0:5'). "
    "Can be specified multiple times. Indices are 0-based.",
)
@click.option(
    "--shifts",
    "-s",
    help="Carbon shifts as JSON dict (e.g., '{\"0\": 22.5, \"2\": 30.2}') or "
    "comma-separated list assigned to atoms in order.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output SVG file path. If not specified, prints to stdout.",
)
@click.option(
    "--width",
    default=800,
    type=int,
    help="Diagram width in pixels (default: 800).",
)
@click.option(
    "--height",
    default=600,
    type=int,
    help="Diagram height in pixels (default: 600).",
)
@click.option(
    "--show-indices/--hide-indices",
    default=False,
    help="Show atom indices on the diagram.",
)
@click.option(
    "--show-hydrogens/--hide-hydrogens",
    default=True,
    help="Show explicit hydrogen atoms.",
)
@click.option(
    "--show-legend/--hide-legend",
    default=True,
    help="Show correlation type legend.",
)
@click.option(
    "--show-atom-numbers/--hide-atom-numbers",
    default=False,
    help="Show publication-style atom numbers (red annotations near atoms).",
)
@click.option(
    "--show-j-coupling/--hide-j-coupling",
    default=False,
    help="Show J-coupling labels (²J, ³J) on HMBC arrows (requires --sol).",
)
def visualize_correlations(
    smiles: str | None,
    sol: str | None,
    lsd_file: str | None,
    solution: int,
    correlations: tuple[str, ...],
    shifts: str | None,
    output: str | None,
    width: int,
    height: int,
    show_indices: bool,
    show_hydrogens: bool,
    show_legend: bool,
    show_atom_numbers: bool,
    show_j_coupling: bool,
) -> None:
    """Generate NMR correlation diagram from SMILES and correlation data.

    SMILES is the molecular structure to visualize (not required with --sol).

    Correlations can be provided via --sol, --lsd-file, or --correlations options.

    Examples:

    \b
      # From LSD solution file (generates structure from .sol)
      lucy visualize correlations --sol compound.sol --lsd-file compound.lsd \\
        --show-atom-numbers --show-j-coupling -o diagram.svg

    \b
      # From explicit correlations
      lucy visualize correlations "CC(C)Cc1ccc(cc1)C(C)C(=O)O" \\
        -c "HMBC:0:3" -c "HMBC:12:10" --output diagram.svg

    \b
      # From LSD problem file
      lucy visualize correlations "CC(=O)C" --lsd-file problem.lsd -o diagram.svg

    \b
      # With chemical shift annotations and atom numbers
      lucy visualize correlations "CCO" -c "HMBC:0:1" \\
        --shifts '{"0": 18.0, "1": 58.0}' --show-atom-numbers -o ethanol.svg
    """
    # Configure diagram
    config = DiagramConfig(
        width=width,
        height=height,
        show_atom_indices=show_indices,
        show_hydrogens=show_hydrogens,
        show_legend=show_legend,
        show_atom_numbers=show_atom_numbers,
    )

    # Generate diagram
    generator = CorrelationDiagramGenerator(config=config)

    # Mode 1: Generate from .sol file (solved structure)
    if sol:
        if not lsd_file:
            raise click.UsageError("--lsd-file is required when using --sol")

        result = generator.generate_from_sol_file(
            sol_path=Path(sol),
            lsd_path=Path(lsd_file),
            solution_number=solution,
            show_j_coupling=show_j_coupling,
        )
    else:
        # SMILES is required for other modes
        if not smiles:
            raise click.UsageError("SMILES is required unless using --sol")

        # Parse LSD file if provided
        lsd_problem = None
        if lsd_file:
            lsd_problem = parse_lsd_input_file(Path(lsd_file))

        # Parse correlations from command line
        parsed_correlations: list[Correlation] = []
        if correlations:
            for corr_str in correlations:
                parsed = parse_correlation_string(corr_str)
                if parsed:
                    parsed_correlations.append(parsed)

        # Parse carbon shifts
        carbon_shifts: dict[int, float] | None = None
        if shifts:
            carbon_shifts = parse_shifts(shifts)

        if lsd_problem:
            # Use LSD problem - generate_from_lsd_problem handles extraction
            result = generator.generate_from_lsd_problem(smiles, lsd_problem)
        else:
            # Use explicit correlations
            result = generator.generate(
                smiles=smiles,
                correlations=parsed_correlations,
                carbon_shifts=carbon_shifts,
            )

    # Output
    if output:
        output_path = Path(output)
        output_path.write_text(result.svg_content)
        click.echo(f"Diagram saved to: {output_path}")
        click.echo(f"  Atoms: {result.atom_count}")
        click.echo(f"  Correlations: {result.correlation_count}")
        click.echo(f"  Arrows: {result.arrows_routed}")
    else:
        click.echo(result.svg_content)


def parse_correlation_string(corr_str: str) -> Correlation | None:
    """Parse correlation string in format 'TYPE:source:target'.

    Args:
        corr_str: String like 'HMBC:0:5' or 'COSY:1:2'

    Returns:
        Correlation object or None if parsing fails
    """
    parts = corr_str.split(":")
    if len(parts) != 3:
        click.echo(f"Warning: Invalid correlation format '{corr_str}', expected TYPE:source:target", err=True)
        return None

    type_str, source_str, target_str = parts

    # Map type string to enum
    type_map = {
        "HMBC": CorrelationType.HMBC,
        "HSQC": CorrelationType.HSQC,
        "HMQC": CorrelationType.HSQC,  # Treat HMQC as HSQC
        "COSY": CorrelationType.COSY,
        "NOESY": CorrelationType.NOESY,
        "ROESY": CorrelationType.ROESY,
    }

    corr_type = type_map.get(type_str.upper())
    if corr_type is None:
        click.echo(f"Warning: Unknown correlation type '{type_str}'", err=True)
        return None

    try:
        source = int(source_str)
        target = int(target_str)
    except ValueError:
        click.echo(f"Warning: Invalid atom indices in '{corr_str}'", err=True)
        return None

    return Correlation(
        source_atom=source,
        target_atom=target,
        correlation_type=corr_type,
    )


def parse_shifts(shifts_str: str) -> dict[int, float]:
    """Parse chemical shifts from string.

    Accepts either JSON dict or comma-separated list.

    Args:
        shifts_str: Either '{"0": 22.5, "2": 30.2}' or '22.5,30.2,45.0'

    Returns:
        Dict mapping atom index to shift value
    """
    shifts_str = shifts_str.strip()

    # Try JSON first
    if shifts_str.startswith("{"):
        try:
            data = json.loads(shifts_str)
            return {int(k): float(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError) as e:
            click.echo(f"Warning: Failed to parse shifts as JSON: {e}", err=True)
            return {}

    # Try comma-separated list
    try:
        values = [float(v.strip()) for v in shifts_str.split(",") if v.strip()]
        return {i: v for i, v in enumerate(values)}
    except ValueError as e:
        click.echo(f"Warning: Failed to parse shifts: {e}", err=True)
        return {}


def parse_lsd_input_file(lsd_path: Path) -> LSDProblem:
    """Parse an LSD input file into an LSDProblem.

    This is a simple parser for LSD input format that extracts:
    - MULT commands (atom definitions)
    - HSQC correlations
    - HMBC correlations
    - COSY correlations

    Args:
        lsd_path: Path to .lsd input file

    Returns:
        LSDProblem object
    """
    content = lsd_path.read_text()
    problem = LSDProblem(name=lsd_path.stem)

    for line in content.split("\n"):
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith(";"):
            continue

        parts = line.split()
        if not parts:
            continue

        cmd = parts[0].upper()

        if cmd == "MULT" and len(parts) >= 5:
            # MULT atom_num element hybridization h_count [charge]
            try:
                index = int(parts[1])
                element = parts[2]
                hyb_val = int(parts[3])
                h_count = int(parts[4])
                charge = int(parts[5]) if len(parts) > 5 else 0

                hyb_map = {1: Hybridization.SP, 2: Hybridization.SP2, 3: Hybridization.SP3}
                hybridization = hyb_map.get(hyb_val, Hybridization.SP3)

                atom = LSDAtom(
                    index=index,
                    element=element,
                    hybridization=hybridization,
                    hydrogen_count=h_count,
                    charge=charge,
                )
                problem.add_atom(atom)
            except (ValueError, IndexError):
                pass

        elif cmd in ("HSQC", "HMQC") and len(parts) >= 3:
            # HSQC carbon_idx proton_idx
            try:
                atom1 = int(parts[1])
                atom2 = int(parts[2])
                corr = LSDCorrelation(
                    atom1_index=atom1,
                    atom2_index=atom2,
                    correlation_type="HSQC",
                )
                problem.add_correlation(corr)
            except ValueError:
                pass

        elif cmd == "HMBC" and len(parts) >= 3:
            # HMBC carbon_idx proton_idx
            try:
                atom1 = int(parts[1])
                atom2 = int(parts[2])
                corr = LSDCorrelation(
                    atom1_index=atom1,
                    atom2_index=atom2,
                    correlation_type="HMBC",
                )
                problem.add_correlation(corr)
            except ValueError:
                pass

        elif cmd == "COSY" and len(parts) >= 3:
            # COSY h_idx1 h_idx2
            try:
                atom1 = int(parts[1])
                atom2 = int(parts[2])
                corr = LSDCorrelation(
                    atom1_index=atom1,
                    atom2_index=atom2,
                    correlation_type="COSY",
                )
                problem.add_correlation(corr)
            except ValueError:
                pass

    return problem
