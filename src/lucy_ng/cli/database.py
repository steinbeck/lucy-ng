"""CLI commands for database management."""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import click
import requests

from lucy_ng.database import DatabaseImporter, DatabaseManager

# Pre-built database from Figshare
DATABASE_DOI = "10.6084/m9.figshare.31073554"
DATABASE_URL = "https://figshare.com/ndownloader/files/61034746"
DATABASE_SIZE_MB = 343  # Compressed size
DEFAULT_DB_PATH = Path("data/reference/lucy-ng-derep.db")


@click.group()
def database() -> None:
    """Database management commands."""


@database.command()
@click.option(
    "--nmrshiftdb",
    type=click.Path(exists=True, path_type=Path),
    help="Path to NMRShiftDB SD file",
)
@click.option(
    "--coconut",
    type=click.Path(exists=True, path_type=Path),
    help="Path to COCONUT SD file",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("lucy-ng-derep.db"),
    help="Output database path (default: lucy-ng-derep.db)",
)
@click.option(
    "--batch-size",
    default=1000,
    type=int,
    help="Batch size for inserts (default: 1000)",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=None,
    help="Limit number of compounds to import (for testing)",
)
def build(
    nmrshiftdb: Path | None,
    coconut: Path | None,
    output: Path,
    batch_size: int,
    limit: int | None,
) -> None:
    """Build compound database from SDF files.

    Import compounds from NMRShiftDB and/or COCONUT SDF files into
    a SQLite database for fast formula-based lookup.

    Examples:

        lucy database build --nmrshiftdb data/reference/nmrshiftdb2withsignals.sd

        lucy database build --coconut data/reference/predicted_coconut.sdf -o coconut.db

        lucy database build --nmrshiftdb nmrshiftdb.sd --coconut coconut.sdf -o all.db
    """
    if not nmrshiftdb and not coconut:
        raise click.UsageError("At least one of --nmrshiftdb or --coconut is required")

    click.echo(f"Creating database: {output}")
    if limit:
        click.echo(f"  Limit: {limit:,} compounds per source")

    with DatabaseManager(output) as db:
        db.create_tables()
        importer = DatabaseImporter(db)

        if nmrshiftdb:
            click.echo(f"\nImporting NMRShiftDB from: {nmrshiftdb}")

            def nmrshiftdb_progress(current: int, total: int) -> None:
                if current % 1000 == 0 or current == total:
                    pct = (current / total) * 100 if total > 0 else 0
                    click.echo(f"  Progress: {current:,}/{total:,} ({pct:.1f}%)", nl=False)
                    click.echo("\r", nl=False)

            result = importer.import_nmrshiftdb(
                nmrshiftdb,
                batch_size=batch_size,
                progress_callback=nmrshiftdb_progress,
                limit=limit,
            )
            click.echo(f"  {result}")

            if result.errors:
                click.echo(f"  First few errors: {result.errors[:3]}")

        if coconut:
            click.echo(f"\nImporting COCONUT from: {coconut}")
            click.echo("  (This may take several minutes for large files...)")

            last_reported = [0]  # Use list to allow mutation in closure

            def coconut_progress(current: int, total: int) -> None:
                # Report every 10000 compounds
                if current - last_reported[0] >= 10000:
                    pct = (current / total) * 100 if total > 0 else 0
                    click.echo(f"  Progress: {current:,}/{total:,} (~{pct:.1f}%)")
                    last_reported[0] = current

            result = importer.import_coconut(
                coconut,
                batch_size=batch_size,
                progress_callback=coconut_progress,
                limit=limit,
            )
            click.echo(f"  {result}")

            if result.errors:
                click.echo(f"  First few errors: {result.errors[:3]}")

        # Final stats
        click.echo(f"\nDatabase complete: {output}")
        click.echo(f"  Total compounds: {db.get_compound_count():,}")
        click.echo(f"  Unique formulas: {db.get_formula_count():,}")


@database.command()
@click.argument("db_path", type=click.Path(exists=True, path_type=Path))
def info(db_path: Path) -> None:
    """Show database statistics.

    Display information about a compound database including
    total compounds, unique formulas, and source breakdown.

    Example:

        lucy database info compounds.db
    """
    with DatabaseManager(db_path) as db:
        compound_count = db.get_compound_count()
        formula_count = db.get_formula_count()

        click.echo(f"Database: {db_path}")
        click.echo(f"  Schema version: {db.get_schema_version()}")
        click.echo(f"  Total compounds: {compound_count:,}")
        click.echo(f"  Unique formulas: {formula_count:,}")

        # Get source breakdown
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT source, COUNT(*) FROM compounds GROUP BY source ORDER BY COUNT(*) DESC"
        )
        sources = cursor.fetchall()

        if sources:
            click.echo("  Sources:")
            for source, count in sources:
                click.echo(f"    {source or 'unknown'}: {count:,}")


@database.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_DB_PATH,
    help=f"Output path (default: {DEFAULT_DB_PATH})",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing database",
)
def download(output: Path, force: bool) -> None:
    """Download pre-built compound database from Figshare.

    Downloads the lucy-ng compound database containing 928K compounds
    (COCONUT + NMRShiftDB) with 13C NMR chemical shifts.

    DOI: 10.6084/m9.figshare.31073554

    Examples:

        lucy database download

        lucy database download -o my_compounds.db

        lucy database download --force
    """
    gz_path = output.with_suffix(".db.gz")

    # Check if already exists
    if output.exists() and not force:
        click.echo(f"Database already exists: {output}")
        click.echo("Use --force to overwrite, or run 'lucy database info' to check it.")
        return

    # Create parent directory if needed
    output.parent.mkdir(parents=True, exist_ok=True)

    click.echo("Downloading compound database from Figshare...")
    click.echo(f"  DOI: {DATABASE_DOI}")
    click.echo(f"  Size: ~{DATABASE_SIZE_MB} MB (compressed)")

    # Download with progress
    try:
        response = requests.get(DATABASE_URL, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1 MB chunks

        with open(gz_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    pct = (downloaded / total_size) * 100
                    mb_done = downloaded / 1e6
                    mb_total = total_size / 1e6
                    msg = f"\r  Progress: {mb_done:.0f}/{mb_total:.0f} MB ({pct:.0f}%)"
                    click.echo(msg, nl=False)

        click.echo()  # Newline after progress

    except requests.RequestException as e:
        click.echo(f"\nError downloading: {e}", err=True)
        if gz_path.exists():
            gz_path.unlink()
        raise click.Abort() from e

    # Decompress
    click.echo("  Decompressing...")
    try:
        with gzip.open(gz_path, "rb") as f_in:
            with open(output, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
    except Exception as e:
        click.echo(f"Error decompressing: {e}", err=True)
        raise click.Abort() from e

    # Clean up compressed file
    gz_path.unlink()

    # Verify
    click.echo(f"\nDatabase downloaded: {output}")
    with DatabaseManager(output) as db:
        click.echo(f"  Compounds: {db.get_compound_count():,}")
        click.echo(f"  Formulas: {db.get_formula_count():,}")


@database.command("generate-hose-stats")
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=DEFAULT_DB_PATH,
    help=f"Path to database (default: {DEFAULT_DB_PATH})",
)
@click.option(
    "--sdf",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to COCONUT SDF file (uses correct atom indexing)",
)
@click.option(
    "--max-radius",
    default=6,
    type=click.IntRange(1, 6),
    help="Maximum HOSE code radius (default: 6)",
)
@click.option(
    "--chunk-size",
    default=10000,
    type=int,
    help="Compounds per chunk for resumable mode (default: 10000)",
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Log file for detached operation (nohup)",
)
@click.option(
    "--resume/--no-resume",
    default=True,
    help="Resume from checkpoint if exists (default: --resume)",
)
@click.option(
    "--fresh",
    is_flag=True,
    help="Clear existing stats and checkpoint before starting",
)
@click.option(
    "--legacy",
    is_flag=True,
    help="Use legacy in-memory generator (not recommended for large DBs)",
)
def generate_hose_stats(
    db: Path,
    sdf: Path | None,
    max_radius: int,
    chunk_size: int,
    log_file: Path | None,
    resume: bool,
    fresh: bool,
    legacy: bool,
) -> None:
    """Generate HOSE code statistics from database compounds or SDF file.

    Processes all compounds, generates HOSE codes for each carbon with a
    known shift (at radii 1 through max-radius), and computes aggregated
    statistics (mean, std, count) per HOSE code.

    This populates the hose_stats table for database-backed 13C shift prediction.

    RECOMMENDED: Use --sdf to read directly from the COCONUT SDF file, which
    ensures correct atom indexing (COCONUT uses 1-based indices).

    \b
        lucy database generate-hose-stats --sdf data/reference/predicted_coconut.sdf

    The default mode uses a resumable, chunked generator that:

    \b
    - Processes compounds in chunks (--chunk-size)
    - Saves checkpoints after each chunk for resume capability
    - Supports file-based logging for detached operation (nohup)
    - Uses O(1) memory per HOSE code via Welford's algorithm

    For production runs on large databases:

    \b
        nohup lucy database generate-hose-stats --sdf file.sdf --log-file hose.log &
        tail -f hose.log  # Monitor progress

    To resume after interruption:

    \b
        lucy database generate-hose-stats --sdf file.sdf  # Automatically resumes

    To start fresh (clear existing data):

    \b
        lucy database generate-hose-stats --sdf file.sdf --fresh

    Examples:

    \b
        lucy database generate-hose-stats --sdf data/reference/predicted_coconut.sdf
        lucy database generate-hose-stats --sdf file.sdf --max-radius 4
        lucy database generate-hose-stats --sdf file.sdf --chunk-size 5000 --log-file gen.log
        lucy database generate-hose-stats --sdf file.sdf --fresh --no-resume
    """
    import time

    from lucy_ng.prediction.hose import HOSEGEN_AVAILABLE

    if not HOSEGEN_AVAILABLE:
        click.echo("Error: hosegen library not available.", err=True)
        click.echo("Install with: pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps", err=True)
        raise click.Abort()

    start_time = time.time()

    if sdf:
        # SDF mode - read directly from SDF file with correct atom indexing
        from lucy_ng.prediction import SDFHOSEStatsGenerator

        if not log_file:
            click.echo("Generating HOSE statistics from SDF file...")
            click.echo(f"  SDF file: {sdf}")
            click.echo(f"  Database: {db}")
            click.echo(f"  Max radius: {max_radius}")
            click.echo(f"  Chunk size: {chunk_size:,}")
            click.echo(f"  Resume: {resume}")
            if fresh:
                click.echo("  Fresh start: clearing existing data")

        # Create database if it doesn't exist
        with DatabaseManager(db) as db_manager:
            db_manager.create_tables()

            generator = SDFHOSEStatsGenerator(
                db_manager, sdf, max_radius=max_radius
            )

            if not log_file:
                from rdkit import Chem
                supplier = Chem.SDMolSupplier(str(sdf))
                click.echo(f"  Molecules in SDF: {len(supplier):,}")

            result = generator.run(
                chunk_size=chunk_size,
                log_file=log_file,
                resume=resume,
                fresh=fresh,
            )

            elapsed = time.time() - start_time
            elapsed_min = elapsed / 60

            if not log_file:
                click.echo(f"\nGenerated {result.total_stats:,} statistics from {result.compounds_processed:,} compounds")
                if result.compounds_failed > 0:
                    click.echo(f"  Compounds failed: {result.compounds_failed:,}")
                click.echo(f"  Shifts processed: {result.shifts_processed:,}")
                click.echo(f"  Time: {elapsed_min:.1f} min")
            else:
                click.echo(f"Generation complete. See {log_file} for details.")

    elif legacy:
        # Legacy in-memory mode
        from lucy_ng.prediction import HOSEStatsGenerator

        click.echo("Generating HOSE statistics (legacy mode)...")
        click.echo(f"  Database: {db}")
        click.echo(f"  Max radius: {max_radius}")

        with DatabaseManager(db) as db_manager:
            compound_count = db_manager.get_compound_count()
            click.echo(f"  Compounds to process: {compound_count:,}")

            generator = HOSEStatsGenerator(db_manager, max_radius=max_radius)
            count = generator.populate_database(progress=True, batch_size=chunk_size)

            elapsed = time.time() - start_time
            elapsed_min = elapsed / 60

            click.echo(f"\nGenerated {count:,} statistics from {generator.compounds_processed:,} compounds")
            if generator.compounds_failed > 0:
                click.echo(f"  Compounds failed (invalid SMILES): {generator.compounds_failed:,}")
            click.echo(f"  Shifts processed: {generator.shifts_processed:,}")
            click.echo(f"  Time: {elapsed_min:.1f} min")
    else:
        # Resumable chunked mode (default)
        from lucy_ng.prediction import ResumableHOSEStatsGenerator

        if not log_file:
            click.echo("Generating HOSE statistics (resumable mode)...")
            click.echo(f"  Database: {db}")
            click.echo(f"  Max radius: {max_radius}")
            click.echo(f"  Chunk size: {chunk_size:,}")
            click.echo(f"  Resume: {resume}")
            if fresh:
                click.echo("  Fresh start: clearing existing data")

        with DatabaseManager(db) as db_manager:
            # Ensure checkpoint table exists
            db_manager.create_tables()

            if not log_file:
                compound_count = db_manager.get_compound_count()
                click.echo(f"  Compounds to process: {compound_count:,}")

            generator = ResumableHOSEStatsGenerator(db_manager, max_radius=max_radius)
            result = generator.run(
                chunk_size=chunk_size,
                log_file=log_file,
                resume=resume,
                fresh=fresh,
            )

            elapsed = time.time() - start_time
            elapsed_min = elapsed / 60

            if not log_file:
                click.echo(f"\nGenerated {result.total_stats:,} statistics from {result.compounds_processed:,} compounds")
                if result.compounds_failed > 0:
                    click.echo(f"  Compounds failed (invalid SMILES): {result.compounds_failed:,}")
                click.echo(f"  Shifts processed: {result.shifts_processed:,}")
                click.echo(f"  Time: {elapsed_min:.1f} min")
            else:
                # Minimal output when using log file (for nohup)
                click.echo(f"Generation complete. See {log_file} for details.")
