"""CLI commands for LSD structure elucidation."""

import json
from pathlib import Path

import click
import jsonschema

from ailsa.lsd import LSDRunner, LSDSolutionAnalyzer
from ailsa.lsd.parser import LSDOutputParser
from ailsa.prediction.resolver import resolve_c13_predictor
from ailsa.processing import AdaptivePeakPicker
from ailsa.ranking import SolutionRanker
from ailsa.readers import BrukerReader


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
    import ailsa

    package_dir = Path(ailsa.__file__).parent

    # Check project data directory (development install)
    # package_dir = .../ailsa/src/ailsa → project_root = .../ailsa
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
        "Build with: ailsa predict build-table --source nmrshiftdb"
    )


def _get_schema_path() -> Path:
    """Get the constraint inventory v2 JSON Schema path.

    Resolution order:
    1. Bundled within the installed package (src/ailsa/data/schemas/) — works for
       regular pip installs where the schemas/ repo-root directory is not present.
    2. Repo root schemas/ directory — works for editable installs and development.

    This ensures the CLI works when invoked from any directory (e.g. analysis/iteration_NN/)
    and for any install mode.
    """
    import ailsa

    package_dir = Path(ailsa.__file__).parent

    # 1. Bundled within the installed package (pip install)
    bundled = package_dir / "data" / "schemas" / "constraint_inventory_v2.json"
    if bundled.exists():
        return bundled

    # 2. Repo root (editable install / development)
    # src/ailsa -> src -> repo_root
    project_root = package_dir.parent.parent
    repo_schema = project_root / "schemas" / "constraint_inventory_v2.json"
    if repo_schema.exists():
        return repo_schema

    raise FileNotFoundError(
        "Schema not found. Re-install the package or check the schemas/ directory."
    )


def _extract_inventory_block(content: str) -> str | None:
    """Extract JSON from between v2 inventory delimiters, stripping '; ' prefix.

    Returns the extracted JSON string, or None if no v2 inventory block is found
    or if the block is malformed (START delimiter present but END delimiter missing).

    Lines that are exactly ';' (blank comment lines) are mapped to empty strings.
    """
    lines = content.splitlines()
    in_block = False
    found_end = False
    json_lines: list[str] = []
    for line in lines:
        if "=== CONSTRAINT INVENTORY v2 ===" in line:
            in_block = True
            continue
        if "=== END CONSTRAINT INVENTORY ===" in line and in_block:
            found_end = True
            break
        if in_block:
            if line.startswith("; "):
                json_lines.append(line[2:])  # strip "; " prefix (exactly 2 chars)
            elif line == ";":
                json_lines.append("")
    if not json_lines:
        return None
    if not found_end:
        # START delimiter was present but END was never found — malformed block.
        # Returning partial content would mask structural corruption of the LSD file.
        return None
    return "\n".join(json_lines)


def _perform_ranking(
    smiles_file: str | Path,
    experimental_shifts: list[float],
    top: int = 10,
    tolerance: float = 3.0,
    table: str | Path | None = None,
    output_format: str = "text",
    _silent: bool = False,
    db: str | Path | None = None,
    max_radius: int = 6,
) -> dict | None:
    """Rank LSD solutions by 13C spectrum similarity.

    Module-private helper extracted from lsd_rank so that the pylsd run
    command (Plan 02) can call ranking logic as a direct Python function call
    without spawning a subprocess (D-14).

    The 13C predictor backing the ranker is resolved through the SHARED
    ``resolve_c13_predictor`` ladder (RANK-01) — the exact same DB-first
    4-tier priority used by ``ailsa predict c13`` — so the two CLIs produce
    identical per-shift predictions for the same molecule. Backend selection
    lives ONLY in that helper; this function does not branch on db/table.

    Args:
        smiles_file: Path to a file containing SMILES strings (one per line).
        experimental_shifts: List of experimental 13C shift values in ppm.
        top: Number of top solutions to return.
        tolerance: Tolerance in ppm for shift matching.
        table: Explicit JSON HOSE lookup table path (backend priority 2).
        output_format: 'text' (echo to stdout, return None) or 'json'
            (echo JSON to stdout AND return the data dict for callers).
        _silent: When True, suppress click.echo output (used by pylsd_run to
            avoid the double-JSON-echo bug: _perform_ranking normally echoes
            JSON to stdout when output_format='json', and pylsd_run would then
            echo a second outer wrapper — passing _silent=True prevents the
            inner echo so only the outer wrapper is written).
        db: Explicit SQLite HOSE database path (backend priority 1).
        max_radius: Maximum HOSE radius for prediction (default 6; must match
            ``predict c13`` for identical predictions).

    Returns:
        When output_format == 'json': the data dict (for pylsd_run embedding).
        When output_format == 'text': None.

    Raises:
        SystemExit(1): On file not found, parse failure, empty solutions,
            no resolvable backend, or ranker init failure.
    """
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

    # Resolve the 13C predictor through the SHARED backend ladder (RANK-01),
    # then build the ranker on it. Backend selection (explicit db -> explicit
    # table -> auto-detect DB -> auto-detect JSON table) lives only in
    # resolve_c13_predictor, so this path is identical to predict c13.
    try:
        predictor = resolve_c13_predictor(db=db, table=table, max_radius=max_radius)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    ranker = SolutionRanker(predictor, tolerance=tolerance)

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
                    "has_aromatic_ring": sol.has_aromatic_ring,
                }
                for i, sol in enumerate(result.solutions)
            ],
            "warnings": result.warnings,
        }
        if not _silent:
            click.echo(json.dumps(data, indent=2))
        return data
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
                # Primary line: rank, solution index, match count, MAE with quality label
                click.echo(
                    f"{i+1:3}. Solution {sol.solution_index}: "
                    f"Matched={sol.matched_count}/{sol.total_carbons} "
                    f"MAE={sol.mae:.2f} ppm ({sol.quality_label})"
                )
                # SMILES on second line
                click.echo(f"     {sol.smiles}")
                # Tolerance summary on third line
                click.echo(f"     {sol.tolerance_summary()}")
        else:
            click.echo("No solutions could be ranked.")

        # Print warnings
        if result.warnings:
            click.echo()
            for warning in result.warnings:
                click.echo(f"WARNING: {warning}")

        return None


def _validate_and_parse_inventory(lsd_file: str | Path) -> dict | None:
    """Parse and validate the constraint inventory block in an LSD file.

    Module-private helper extracted from lsd_validate_inventory so that the
    pylsd run command (Plan 02) can call inventory validation as a direct
    Python function call (D-13).

    Args:
        lsd_file: Path to the LSD input file containing a v2 inventory block.

    Returns:
        The parsed inventory instance dict when a valid v2 block is present.
        None when no v2 inventory block is found (not an error — caller decides
        how to handle the no-block case, e.g. pylsd_run treats it as a fallback).

    Raises:
        SystemExit(1): On file read error, v1 block detected, JSON parse
            failure, or schema validation failure. Prints appropriate error
            to stderr via click.echo(err=True) before raising.
    """
    try:
        content = Path(lsd_file).read_text(encoding="utf-8")
    except (PermissionError, OSError) as e:
        click.echo(f"Error: Cannot read file: {e}", err=True)
        raise SystemExit(1)

    # Check for v1 block (per D-02 — emit error and exit 1)
    if "=== CONSTRAINT INVENTORY v1 ===" in content:
        click.echo(
            "Invalid: Legacy v1 inventory detected — upgrade to v2 format",
            err=True,
        )
        raise SystemExit(1)

    # Extract the v2 inventory block
    raw_json = _extract_inventory_block(content)
    if raw_json is None:
        # Distinguish ABSENT (no block at all) from PRESENT-MALFORMED (START without END).
        # MALFORMED is a hard error: a truncated LSD file should not silently fall through
        # to the D-13b grep fallback (D-13a/WR-01 fix).
        if "=== CONSTRAINT INVENTORY v2 ===" in content:
            click.echo(
                "Error: Malformed inventory block — START delimiter found but END "
                "delimiter is missing. Reconcile the LSD file before running pylsd.",
                err=True,
            )
            raise SystemExit(1)
        # No block at all — not an error at this level; caller decides
        return None

    # Parse JSON
    try:
        instance = json.loads(raw_json)
    except json.JSONDecodeError as e:
        click.echo(f"Error: JSON parse failure in inventory block: {e}", err=True)
        raise SystemExit(1)

    # Load schema and validate
    try:
        schema_path = _get_schema_path()
        with open(schema_path) as f:
            schema = json.load(f)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))

    if errors:
        error_dicts = [
            {
                "message": e.message,
                "path": list(e.absolute_path),
                "validator": e.validator,
            }
            for e in errors
        ]
        click.echo(
            f"Error: Invalid constraint inventory v2 ({len(errors)} error(s)): "
            + "; ".join(d["message"] for d in error_dicts),
            err=True,
        )
        raise SystemExit(1)

    return instance


@lsd.command("validate-inventory")
@click.argument("lsd_file", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (json for machine-readable, used by devils-advocate).",
)
def lsd_validate_inventory(lsd_file: str, output_format: str) -> None:
    """Validate the constraint inventory block in an LSD file.

    LSD_FILE is the path to the LSD input file containing a v2 inventory block.
    Exits 0 if valid, 1 if invalid or no inventory found.
    """
    # --- File read (needed for format-aware error output on read failures) ---
    try:
        content = Path(lsd_file).read_text(encoding="utf-8")
    except (PermissionError, OSError) as e:
        if output_format == "json":
            click.echo(json.dumps({
                "valid": False,
                "file": lsd_file,
                "errors": [
                    {
                        "message": f"Cannot read file: {e}",
                        "validator": "file_access",
                    }
                ],
            }, indent=2))
        else:
            click.echo(f"Error: Cannot read file: {e}", err=True)
        raise SystemExit(1)

    # --- v1 block check (format-aware output) ---
    if "=== CONSTRAINT INVENTORY v1 ===" in content:
        if output_format == "json":
            click.echo(json.dumps({
                "valid": False,
                "file": lsd_file,
                "errors": [
                    {
                        "message": "Legacy v1 inventory detected — upgrade to v2 format",
                        "validator": "version",
                    }
                ],
            }, indent=2))
        else:
            click.echo(
                "Invalid: Legacy v1 inventory detected — upgrade to v2 format"
            )
        raise SystemExit(1)

    # --- Delegate parsing + validation to helper ---
    # We re-use _validate_and_parse_inventory for the core logic but must handle
    # the "no block" and "schema error" cases with format-aware CLI output.
    # To avoid duplicating the file-read / v1-check already done above, we call
    # the helper and map its behaviour to the CLI's output contract.

    # Extract block directly (avoid re-reading the file)
    raw_json = _extract_inventory_block(content)
    if raw_json is None:
        if output_format == "json":
            click.echo(json.dumps({
                "valid": False,
                "file": lsd_file,
                "errors": [
                    {
                        "message": f"No v2 inventory block found in {lsd_file}",
                        "validator": "block_presence",
                    }
                ],
            }, indent=2))
        else:
            click.echo(f"Invalid: No v2 inventory block found in {lsd_file}")
        raise SystemExit(1)

    # Parse JSON
    try:
        instance = json.loads(raw_json)
    except json.JSONDecodeError as e:
        if output_format == "json":
            click.echo(json.dumps({
                "valid": False,
                "file": lsd_file,
                "errors": [
                    {
                        "message": f"Invalid JSON in inventory block: {e}",
                        "validator": "json_parse",
                    }
                ],
            }, indent=2))
        else:
            click.echo(f"Invalid: JSON parse failure in inventory block: {e}")
        raise SystemExit(1)

    # Load schema and validate
    try:
        schema_path = _get_schema_path()
        with open(schema_path) as f:
            schema = json.load(f)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))

    if not errors:
        if output_format == "json":
            click.echo(json.dumps({
                "valid": True,
                "file": lsd_file,
                "version": 2,
                "inventory": instance,  # full parsed inventory for devils-advocate G2/G3 gates
            }, indent=2))
        else:
            click.echo("Valid constraint inventory v2")
    else:
        error_dicts = [
            {
                "message": e.message,
                "path": list(e.absolute_path),
                "validator": e.validator,
            }
            for e in errors
        ]
        if output_format == "json":
            click.echo(json.dumps({
                "valid": False,
                "file": lsd_file,
                "errors": error_dicts,
            }, indent=2))
        else:
            click.echo(f"Invalid constraint inventory v2 ({len(errors)} error(s)):")
            for err in error_dicts:
                path_str = " > ".join(str(p) for p in err["path"]) if err["path"] else "root"
                click.echo(f"  [{path_str}] {err['message']}")
        raise SystemExit(1)


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
    "--db",
    type=click.Path(exists=True),
    default=None,
    help="Path to SQLite HOSE database (auto-detected if not set).",
)
@click.option(
    "--table",
    type=click.Path(exists=True),
    default=None,
    help="Path to HOSE lookup table (auto-detected if not set).",
)
@click.option(
    "--max-radius",
    type=int,
    default=6,
    help="Maximum HOSE radius (default 6; must match predict c13 for "
    "identical predictions).",
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
    db: str | None,
    table: str | None,
    max_radius: int,
    output_format: str,
) -> None:
    """Rank LSD solutions by 13C spectrum similarity.

    SMILES_FILE is a file containing SMILES strings (one per line),
    typically the output from outlsd.

    Provide experimental shifts via --spectrum (Bruker 13C directory) or
    --shifts (comma-separated ppm values).

    Backend priority mirrors ``ailsa predict c13`` (RANK-01): explicit --db,
    then explicit --table, then auto-detect the SQLite DB, then auto-detect
    the shipped JSON table.

    Examples:

      ailsa lsd rank outlsd.out --spectrum data/Ibuprofen/2

      ailsa lsd rank solutions.smi --shifts "180.5,140.8,137.0,129.4"
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

    _perform_ranking(
        smiles_file,
        experimental_shifts,
        top,
        tolerance,
        table,
        output_format,
        db=db,
        max_radius=max_radius,
    )


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
@click.option(
    "--draw",
    "-d",
    type=click.Path(),
    default=None,
    help="Draw structure with LSD atom numbers. Use {n} for solution number (e.g., 'solution_{n}.png').",
)
def lsd_analyze(
    sol_file: str, lsd_file: str, solution: int | None, output_format: str, draw: str | None
) -> None:
    """Analyze J-coupling path lengths in LSD solutions.

    SOL_FILE is the .sol file containing molecular connectivity from LSD.
    LSD_FILE is the .lsd input file containing HMBC correlations.

    For each HMBC correlation, computes the actual path length (number of bonds)
    between the carbon and proton-bearing carbon using BFS on the molecular graph.
    This determines whether correlations are ²J, ³J, ⁴J, etc.

    Use --draw to generate structure images with LSD atom numbering, useful for
    interpreting the HMBC correlation table.

    Examples:

      ailsa lsd analyze compound.sol compound.lsd

      ailsa lsd analyze compound.sol compound.lsd --solution 2 --format json

      ailsa lsd analyze compound.sol compound.lsd --draw solution_{n}.png
    """
    # Parse solution graphs for drawing (if requested)
    solution_graphs = None
    if draw:
        from ailsa.lsd.analyzer import LSDSolutionAnalyzer as Analyzer
        solution_graphs = {g.solution_number: g for g in Analyzer.parse_sol_file(sol_file)}

    results = LSDSolutionAnalyzer.analyze(
        sol_path=sol_file,
        lsd_path=lsd_file,
        solution_number=solution,
    )

    if not results:
        click.echo("No solutions found or solution number not in file.", err=True)
        raise SystemExit(1)

    if output_format == "json":
        solutions_data = []
        for r in results:
            sol_data = {
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
            # Add SMILES and image path if graphs available
            if solution_graphs and r.solution_number in solution_graphs:
                graph = solution_graphs[r.solution_number]
                sol_data["smiles"] = graph.to_smiles()
                if draw:
                    img_path = draw.replace("{n}", str(r.solution_number))
                    if graph.draw_with_atom_numbers(img_path):
                        sol_data["image_path"] = img_path
            solutions_data.append(sol_data)
        data = {"solutions": solutions_data}
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

            # Generate structure image if requested
            if draw and solution_graphs and r.solution_number in solution_graphs:
                graph = solution_graphs[r.solution_number]
                img_path = draw.replace("{n}", str(r.solution_number))
                if graph.draw_with_atom_numbers(img_path):
                    smiles = graph.to_smiles()
                    click.echo(f"\nSMILES: {smiles}")
                    click.echo(f"Structure image: {img_path}")
