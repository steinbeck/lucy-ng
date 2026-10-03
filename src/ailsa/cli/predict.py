"""CLI commands for NMR chemical shift prediction."""

import json
from pathlib import Path

import click

from ailsa.database import DatabaseFinder
from ailsa.prediction import HOSELookupTable
from ailsa.prediction.resolver import resolve_c13_predictor


@click.group()
def predict() -> None:
    """Predict NMR chemical shifts from structure."""
    pass


@predict.command("c13")
@click.argument("smiles")
@click.option(
    "--db",
    "-d",
    type=click.Path(exists=True),
    default=None,
    help="Path to SQLite database with HOSE stats (preferred over JSON table).",
)
@click.option(
    "--table",
    "-t",
    type=click.Path(exists=True),
    default=None,
    help="Path to HOSE lookup table (JSON). Database is preferred if available.",
)
@click.option(
    "--max-radius",
    "-r",
    type=int,
    default=6,
    help="Maximum HOSE radius (default: 6).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def predict_c13(
    smiles: str,
    db: str | None,
    table: str | None,
    max_radius: int,
    output_format: str,
) -> None:
    """Predict 13C NMR chemical shifts for a molecule.

    SMILES is the molecular structure in SMILES format.

    Predicts chemical shifts using HOSE code lookup against a reference database.
    Falls back to shorter HOSE radii when exact matches aren't found.

    Backend priority:
    1. Explicit --db option
    2. Explicit --table option
    3. Auto-detect database in default locations
    4. Auto-detect JSON table in default locations

    Example:

        ailsa predict c13 "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
    """
    # Resolve the predictor through the SHARED backend ladder (RANK-01) so
    # `ailsa predict c13` and `ailsa lsd rank` use literally the same code path
    # (explicit --db -> explicit --table -> auto-detect DB -> auto-detect JSON).
    try:
        predictor = resolve_c13_predictor(db=db, table=table, max_radius=max_radius)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Predict
    result = predictor.predict_from_smiles(smiles)

    if output_format == "json":
        data = {
            "smiles": result.smiles,
            "carbon_count": result.carbon_count,
            "success_count": result.success_count,
            "success_rate": result.success_rate,
            "predictions": [
                {
                    "atom_index": p.atom_index,
                    "shift": p.shift,
                    "confidence": p.confidence,
                    "radius_used": p.radius_used,
                    "match_count": p.match_count,
                    "std_dev": round(p.std_dev, 2),
                    "min_shift": p.min_shift,
                    "max_shift": p.max_shift,
                    "hose_code": p.hose_code,
                }
                for p in result.get_shifts_sorted()
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(result.summary())


@predict.command("build-table")
@click.argument("sd_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=str(DatabaseFinder.DEFAULT_TABLE_PATH),
    help=f"Output file path (default: {DatabaseFinder.DEFAULT_TABLE_PATH}).",
)
@click.option(
    "--source",
    "-s",
    type=click.Choice(["coconut", "nmrshiftdb", "auto"]),
    default="auto",
    help="Source format (auto-detects by default).",
)
@click.option(
    "--max-radius",
    "-r",
    type=int,
    default=6,
    help="Maximum HOSE radius (default: 6).",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Limit number of molecules to process (for testing).",
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=None,
    help="Number of parallel workers (default: CPU count).",
)
@click.option(
    "--no-compress",
    is_flag=True,
    help="Don't compress output file.",
)
def build_table(
    sd_path: str,
    output: str,
    source: str,
    max_radius: int,
    limit: int | None,
    workers: int | None,
    no_compress: bool,
) -> None:
    """Build HOSE lookup table from SD file with 13C shifts.

    SD_PATH is the path to an SD file with 13C chemical shifts.
    Supports COCONUT (CNMR_SHIFTS field) and nmrshiftdb2 (Spectrum 13C 0 field).

    Uses parallel processing for faster table building on multi-core machines.

    Examples:

        ailsa predict build-table data/reference/nmrshiftdb2withsignals.sd

        ailsa predict build-table data/reference/coconut_predicted.sd -w 8
    """
    import multiprocessing as mp

    # Auto-detect source format
    if source == "auto":
        source = _detect_sd_format(sd_path)
        click.echo(f"Auto-detected format: {source}")

    n_workers = workers or mp.cpu_count()
    click.echo(f"Building HOSE lookup table from: {sd_path}")
    click.echo(f"Source format: {source}")
    click.echo(f"Max radius: {max_radius}")
    click.echo(f"Workers: {n_workers}")
    if limit:
        click.echo(f"Limit: {limit} molecules")

    try:
        if source == "nmrshiftdb":
            table = HOSELookupTable.build_from_nmrshiftdb(
                sd_path=Path(sd_path),
                max_radius=max_radius,
                progress=True,
                limit=limit,
                n_jobs=n_workers,
            )
        else:
            table = HOSELookupTable.build_from_coconut(
                sd_path=Path(sd_path),
                max_radius=max_radius,
                progress=True,
                limit=limit,
            )
    except Exception as e:
        click.echo(f"Error building table: {e}", err=True)
        raise SystemExit(1)

    # Ensure output directory exists
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save table
    click.echo(f"\nSaving to: {output_path}")
    table.save(output_path, compress=not no_compress)

    click.echo(f"\nTable built successfully:")
    click.echo(f"  Molecules processed: {table.molecule_count:,}")
    click.echo(f"  Unique HOSE codes: {table.unique_codes:,}")
    click.echo(f"  Total entries: {table.total_entries:,}")


def _detect_sd_format(sd_path: str) -> str:
    """Auto-detect SD file format by checking field names."""
    from rdkit import Chem

    supplier = Chem.SDMolSupplier(sd_path, removeHs=False)

    # Check first few molecules
    for i, mol in enumerate(supplier):
        if mol is None:
            continue
        if mol.HasProp("Spectrum 13C 0"):
            return "nmrshiftdb"
        if mol.HasProp("CNMR_SHIFTS"):
            return "coconut"
        if i > 10:
            break

    # Default to coconut
    return "coconut"


@predict.command("table-info")
@click.option(
    "--table",
    "-t",
    type=click.Path(exists=True),
    default=None,
    help="Path to HOSE lookup table.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def table_info(
    table: str | None,
    output_format: str,
) -> None:
    """Show information about a HOSE lookup table."""
    # Find lookup table
    table_path = Path(table) if table else find_lookup_table()
    if table_path is None or not table_path.exists():
        click.echo("Error: No HOSE lookup table found.", err=True)
        raise SystemExit(1)

    try:
        lookup = HOSELookupTable.load(table_path)
    except Exception as e:
        click.echo(f"Error loading table: {e}", err=True)
        raise SystemExit(1)

    if output_format == "json":
        data = {
            "path": str(table_path),
            "molecule_count": lookup.molecule_count,
            "unique_codes": lookup.unique_codes,
            "total_entries": lookup.total_entries,
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"HOSE Lookup Table: {table_path}")
        click.echo(f"  Molecules: {lookup.molecule_count:,}")
        click.echo(f"  Unique HOSE codes: {lookup.unique_codes:,}")
        click.echo(f"  Total entries: {lookup.total_entries:,}")
        if lookup.unique_codes > 0:
            avg_entries = lookup.total_entries / lookup.unique_codes
            click.echo(f"  Avg entries per code: {avg_entries:.1f}")
