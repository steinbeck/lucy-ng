"""CLI commands for database management."""

from __future__ import annotations

from pathlib import Path

import click

from lucy_ng.database import DatabaseImporter, DatabaseManager


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
    default=Path("compounds.db"),
    help="Output database path (default: compounds.db)",
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
