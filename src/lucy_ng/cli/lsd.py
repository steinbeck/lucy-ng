"""CLI commands for LSD structure elucidation."""

import json
from pathlib import Path

import click

from lucy_ng.lsd import LSDInputGenerator, LSDProblem, LSDRunner, LSDSolutionAnalyzer
from lucy_ng.lsd.parser import LSDOutputParser
from lucy_ng.processing import AdaptivePeakPicker, DEPTGuidedPicker
from lucy_ng.processing.hmbc_guided_picker import HMBCGuidedPicker
from lucy_ng.ranking import SolutionRanker
from lucy_ng.readers import BrukerReader


@click.group()
def lsd() -> None:
    """LSD structure elucidation."""
    pass


@lsd.command("check")
def lsd_check() -> None:
    """Check if LSD and outlsd are installed and available."""
    lsd_ok = LSDRunner.is_available()
    outlsd_ok = LSDRunner.is_outlsd_available()

    if lsd_ok:
        click.echo("LSD: available")
    else:
        click.echo("LSD: not found", err=True)

    if outlsd_ok:
        click.echo("outlsd: available (SMILES conversion enabled)")
    else:
        click.echo("outlsd: not found (solution ranking will be limited)")

    if not lsd_ok:
        raise SystemExit(1)


@lsd.command("generate")
@click.argument("data_dir", type=click.Path(exists=True))
@click.argument("formula")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file (stdout if not set).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def lsd_generate(
    data_dir: str, formula: str, output: str | None, output_format: str
) -> None:
    """Generate LSD input file from NMR data directory.

    DATA_DIR is the directory containing Bruker experiments.
    FORMULA is the molecular formula (e.g., C13H18O2).

    The command auto-detects experiment types from Bruker directories
    and requires at minimum: HSQC and DEPT-135 experiments.
    """
    data_path = Path(data_dir)

    # Find experiments by checking subdirectories
    experiments: dict[str, Path] = {}
    for subdir in sorted(data_path.iterdir()):
        if subdir.is_dir() and subdir.name.isdigit():
            try:
                # Try reading as 2D first, then 1D
                try:
                    spec2d = BrukerReader.read_2d(str(subdir))
                    experiments[spec2d.experiment_type.upper()] = subdir
                except Exception:
                    spec1d = BrukerReader.read_1d(str(subdir))
                    # Distinguish DEPT from regular 13C
                    pulse_prog = spec1d.metadata.get("pulse_program", "").lower()
                    if "dept135" in pulse_prog or "dept-135" in pulse_prog:
                        experiments["DEPT135"] = subdir
                    elif "dept90" in pulse_prog or "dept-90" in pulse_prog:
                        experiments["DEPT90"] = subdir
                    elif "dept" in pulse_prog:
                        # Generic DEPT, assume 135
                        experiments["DEPT135"] = subdir
                    elif spec1d.nucleus == "13C":
                        experiments["13C"] = subdir
                    elif spec1d.nucleus == "1H":
                        experiments["1H"] = subdir
            except Exception:
                pass

    # Check required experiments
    if "HSQC" not in experiments:
        click.echo("Error: HSQC experiment not found in data directory", err=True)
        raise SystemExit(1)

    if "DEPT135" not in experiments:
        click.echo("Error: DEPT-135 experiment not found in data directory", err=True)
        raise SystemExit(1)

    # Read required spectra
    hsqc = BrukerReader.read_2d(str(experiments["HSQC"]))
    dept135 = BrukerReader.read_1d(str(experiments["DEPT135"]))

    # DEPT-guided HSQC picking
    dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

    # Optional: HMBC
    hmbc_result = None
    if "HMBC" in experiments:
        hmbc = BrukerReader.read_2d(str(experiments["HMBC"]))
        # Use 13C if available for HMBC filtering
        c13 = None
        if "13C" in experiments:
            c13 = BrukerReader.read_1d(str(experiments["13C"]))

        hmbc_result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            dept135=dept135,
        )

    # Generate LSD problem
    problem = LSDInputGenerator.from_dept_result(
        dept_result=dept_result,
        hmbc_peaks=hmbc_result.peaks if hmbc_result else None,
        molecular_formula=formula,
        name=data_path.name,
    )

    # Generate output
    lsd_content = LSDInputGenerator.generate(problem)

    if output_format == "json":
        data = {
            "molecular_formula": formula,
            "atom_count": len(problem.atoms),
            "correlation_count": len(problem.correlations),
            "experiments_found": list(experiments.keys()),
            "lsd_content": lsd_content,
        }
        output_text = json.dumps(data, indent=2)
    else:
        output_text = lsd_content

    if output:
        Path(output).write_text(output_text)
        click.echo(f"Written to {output}")
    else:
        click.echo(output_text)


@lsd.command("run")
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--timeout",
    type=int,
    default=60,
    help="Timeout in seconds.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=None,
    help="Directory for solution files.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def lsd_run(
    input_file: str, timeout: int, output_dir: str | None, output_format: str
) -> None:
    """Run LSD on an input file.

    INPUT_FILE is the path to the LSD input file.
    """
    if not LSDRunner.is_available():
        click.echo("Error: LSD is not installed or not in PATH", err=True)
        raise SystemExit(1)

    # Read input file and create problem
    input_content = Path(input_file).read_text()

    # Parse basic info from content
    atom_count = input_content.count("\nMULT ")
    corr_count = input_content.count("\nHMBC ") + input_content.count("\nHSQC ")

    # Run LSD
    runner = LSDRunner()
    result = runner.run_file(
        input_file=Path(input_file),
        output_dir=Path(output_dir) if output_dir else None,
        timeout=timeout,
    )

    if output_format == "json":
        data = {
            "success": result.success,
            "solution_count": result.solution_count,
            "return_code": result.return_code,
            "output_files": [str(f) for f in result.output_files],
            "stderr": result.stderr,
        }
        click.echo(json.dumps(data, indent=2))
    else:
        if result.success:
            click.echo(f"LSD completed successfully")
            click.echo(f"  Solutions found: {result.solution_count}")
            if result.output_files:
                click.echo(f"  Output files:")
                for f in result.output_files:
                    click.echo(f"    - {f}")
        else:
            click.echo(f"LSD failed (return code: {result.return_code})")
            if result.stderr:
                click.echo(f"  Error: {result.stderr[:500]}")


def _get_default_table_path() -> Path:
    """Get the default HOSE lookup table path."""
    import lucy_ng

    package_dir = Path(lucy_ng.__file__).parent

    # Check project data directory (development install)
    # package_dir = .../lucy-ng/src/lucy_ng → project_root = .../lucy-ng
    project_root = package_dir.parent.parent
    project_table = project_root / "data" / "reference" / "hose_nmrshiftdb.json.gz"
    if project_table.exists():
        return project_table

    # Check package data (pip install)
    package_table = package_dir / "data" / "hose_nmrshiftdb.json.gz"
    if package_table.exists():
        return package_table

    # Check user home directory
    home_table = Path.home() / ".lucy" / "hose_nmrshiftdb.json.gz"
    if home_table.exists():
        return home_table

    raise FileNotFoundError(
        "HOSE lookup table not found. "
        "Build with: lucy predict build-table --source nmrshiftdb"
    )


@lsd.command("rank")
@click.argument("smiles_file", type=click.Path(exists=True))
@click.option(
    "--spectrum",
    "-s",
    type=click.Path(exists=True),
    default=None,
    help="Path to Bruker 13C spectrum directory for experimental shifts.",
)
@click.option(
    "--shifts",
    type=str,
    default=None,
    help="Comma-separated list of experimental 13C shifts in ppm.",
)
@click.option(
    "--top",
    "-n",
    type=int,
    default=10,
    help="Number of top results to show.",
)
@click.option(
    "--tolerance",
    "-t",
    type=float,
    default=3.0,
    help="Tolerance in ppm for shift matching.",
)
@click.option(
    "--table",
    type=click.Path(exists=True),
    default=None,
    help="Path to HOSE lookup table (auto-detected if not set).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def lsd_rank(
    smiles_file: str,
    spectrum: str | None,
    shifts: str | None,
    top: int,
    tolerance: float,
    table: str | None,
    output_format: str,
) -> None:
    """Rank LSD solutions by 13C spectrum similarity.

    SMILES_FILE is a file containing SMILES strings (one per line),
    typically the output from outlsd.

    Provide experimental shifts via --spectrum (Bruker 13C directory) or
    --shifts (comma-separated ppm values).

    Examples:

      lucy lsd rank outlsd.out --spectrum data/Ibuprofen/2

      lucy lsd rank solutions.smi --shifts "180.5,140.8,137.0,129.4"
    """
    # Get experimental shifts
    if spectrum and shifts:
        click.echo("Error: Provide either --spectrum or --shifts, not both", err=True)
        raise SystemExit(1)

    if not spectrum and not shifts:
        click.echo("Error: Provide --spectrum or --shifts", err=True)
        raise SystemExit(1)

    experimental_shifts: list[float] = []

    if shifts:
        # Parse comma-separated shifts
        try:
            experimental_shifts = [float(s.strip()) for s in shifts.split(",")]
        except ValueError:
            click.echo("Error: Invalid shifts format. Use comma-separated numbers.", err=True)
            raise SystemExit(1)
    else:
        # Read from spectrum
        try:
            spec = BrukerReader.read_1d(str(spectrum))
            if spec.nucleus != "13C":
                click.echo(f"Warning: Spectrum is {spec.nucleus}, expected 13C", err=True)
            # Pick peaks
            peaks = AdaptivePeakPicker.pick_peaks(spec)
            experimental_shifts = [p.ppm for p in peaks]
        except Exception as e:
            click.echo(f"Error reading spectrum: {e}", err=True)
            raise SystemExit(1)

    if not experimental_shifts:
        click.echo("Error: No experimental shifts found", err=True)
        raise SystemExit(1)

    # Load solutions from SMILES file
    try:
        solutions = LSDOutputParser.parse_smiles_file(smiles_file)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Error loading SMILES file: {e}", err=True)
        raise SystemExit(1)

    if not solutions:
        click.echo("Error: No SMILES found in file", err=True)
        raise SystemExit(1)

    # Get table path
    table_path: Path
    if table:
        table_path = Path(table)
    else:
        try:
            table_path = _get_default_table_path()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    # Create ranker and rank solutions
    try:
        ranker = SolutionRanker.from_table_file(
            table_path=str(table_path),
            tolerance=tolerance,
        )
    except Exception as e:
        click.echo(f"Error loading HOSE table: {e}", err=True)
        raise SystemExit(1)

    result = ranker.rank(solutions, experimental_shifts, top_n=top)

    # Output results
    if output_format == "json":
        data = {
            "total_solutions": result.total_solutions,
            "ranked_count": result.ranked_count,
            "skipped_count": result.skipped_count,
            "experimental_shifts": result.experimental_shifts,
            "tolerance": result.tolerance,
            "solutions": [
                {
                    "rank": i + 1,
                    "solution_index": sol.solution_index,
                    "smiles": sol.smiles,
                    "mae": round(sol.mae, 3),
                    "quality": sol.quality_label,
                    "deviations": [round(d, 2) for d in sol.all_deviations],
                    "within_3ppm": sol.within_tolerance(3.0),
                    "within_5ppm": sol.within_tolerance(5.0),
                    "total_carbons": sol.total_carbons,
                    "max_deviation": round(sol.max_deviation, 2),
                    "prediction_rate": round(sol.prediction_rate, 3),
                    # Keep matched_count for backward compatibility
                    "matched_count": sol.matched_count,
                }
                for i, sol in enumerate(result.solutions)
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Ranking {result.total_solutions} LSD solutions")
        click.echo(f"  Successfully ranked: {result.ranked_count}")
        click.echo(f"  Skipped (no SMILES): {result.skipped_count}")
        click.echo(f"  Experimental peaks: {len(experimental_shifts)}")
        click.echo()

        if result.solutions:
            click.echo(f"Top {len(result.solutions)} solutions:")
            click.echo("-" * 70)
            for i, sol in enumerate(result.solutions):
                # Primary line: rank, solution index, MAE with quality label
                click.echo(
                    f"{i+1:3}. Solution {sol.solution_index}: "
                    f"MAE={sol.mae:.2f} ppm ({sol.quality_label})"
                )
                # SMILES on second line
                click.echo(f"     {sol.smiles}")
                # Tolerance summary on third line
                click.echo(f"     {sol.tolerance_summary()}")
        else:
            click.echo("No solutions could be ranked.")


@lsd.command("analyze")
@click.argument("sol_file", type=click.Path(exists=True))
@click.argument("lsd_file", type=click.Path(exists=True))
@click.option(
    "--solution",
    "-s",
    type=int,
    default=None,
    help="Analyze specific solution number (1-based). All if not set.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def lsd_analyze(
    sol_file: str, lsd_file: str, solution: int | None, output_format: str
) -> None:
    """Analyze J-coupling path lengths in LSD solutions.

    SOL_FILE is the .sol file containing molecular connectivity from LSD.
    LSD_FILE is the .lsd input file containing HMBC correlations.

    For each HMBC correlation, computes the actual path length (number of bonds)
    between the carbon and proton-bearing carbon using BFS on the molecular graph.
    This determines whether correlations are ²J, ³J, ⁴J, etc.

    Examples:

      lucy lsd analyze compound.sol compound.lsd

      lucy lsd analyze compound.sol compound.lsd --solution 2 --format json
    """
    results = LSDSolutionAnalyzer.analyze(
        sol_path=sol_file,
        lsd_path=lsd_file,
        solution_number=solution,
    )

    if not results:
        click.echo("No solutions found or solution number not in file.", err=True)
        raise SystemExit(1)

    if output_format == "json":
        data = {
            "solutions": [
                {
                    "solution_number": r.solution_number,
                    "all_2j_3j": r.all_2j_3j,
                    "max_j": r.max_j,
                    "correlations": [
                        {
                            "carbon_idx": c.carbon_idx,
                            "proton_idx": c.proton_idx,
                            "carbon_shift": c.carbon_shift,
                            "path_length": c.path_length,
                            "j_coupling": c.j_coupling,
                            "j_notation": c.j_notation,
                        }
                        for c in r.correlations
                    ],
                }
                for r in results
            ]
        }
        click.echo(json.dumps(data, indent=2))
    else:
        for r in results:
            click.echo(r.summary())
            click.echo()
            click.echo("HMBC Correlations:")
            click.echo("-" * 55)
            click.echo(f"{'C#':>4} {'H#':>4} {'C (ppm)':>10} {'Path':>6} {'J-coupling':>12}")
            click.echo("-" * 55)

            for c in r.correlations:
                shift_str = f"{c.carbon_shift:.2f}" if c.carbon_shift else "?"
                path_str = str(c.path_length) if c.path_length is not None else "?"
                click.echo(
                    f"{c.carbon_idx:>4} {c.proton_idx:>4} {shift_str:>10} {path_str:>6} {c.j_notation:>12}"
                )

            click.echo()
            if r.all_2j_3j:
                click.echo("All correlations are ²J or ³J - no ELIM needed.")
            else:
                click.echo(
                    f"Contains {r.max_j}J correlations - ELIM may have been required."
                )
