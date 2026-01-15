"""CLI commands for dereplication against reference databases."""

from __future__ import annotations

import gzip
import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from lucy_ng.database import DatabaseQueryService
from lucy_ng.dereplication import CoconutLoader, DereplicationService, NMRShiftDBLoader
from lucy_ng.readers import BrukerReader

if TYPE_CHECKING:
    # Loader is any object with get_by_formula method
    pass


def _find_database_path() -> Path | None:
    """Find SQLite database in default locations.

    Search order:
    1. LUCY_DATABASE environment variable
    2. data/reference/lucy-ng-derep.db (project location)
    3. Common locations (~/.lucy/, ~/lucy-ng/, etc.)
    4. macOS Spotlight search (mdfind)
    5. Recursive search in home directory (last resort)

    Returns:
        Path to database file if found, None otherwise
    """
    import subprocess

    db_name = "lucy-ng-derep.db"

    # 1. Check environment variable first
    env_db = os.environ.get("LUCY_DATABASE")
    if env_db:
        env_path = Path(env_db)
        if env_path.exists() and env_path.suffix == ".db":
            return env_path

    # 2. Check project location
    default_db = Path("data/reference") / db_name
    if default_db.exists():
        return default_db

    # 3. Check common locations
    common_paths = [
        Path.home() / ".lucy" / db_name,
        Path.home() / "lucy-ng" / "data" / "reference" / db_name,
        Path.home() / ".local" / "share" / "lucy-ng" / db_name,
    ]
    for p in common_paths:
        if p.exists():
            return p

    # 4. macOS Spotlight search (fast)
    try:
        result = subprocess.run(
            ["mdfind", "-name", db_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            found_path = Path(result.stdout.strip().split("\n")[0])
            if found_path.exists():
                return found_path
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # mdfind not available or timed out

    # 5. Search in Dropbox/develop (common dev location)
    dropbox_dev = Path.home() / "Dropbox" / "develop" / "lucy-ng" / "data" / "reference" / db_name
    if dropbox_dev.exists():
        return dropbox_dev

    return None


def _is_sqlite_database(path: str | Path) -> bool:
    """Check if path refers to a SQLite database file.

    Args:
        path: Path to check

    Returns:
        True if path has .db extension
    """
    return Path(path).suffix == ".db"


def _decompress_gz_if_needed(gz_path: Path) -> Path:
    """Decompress a .gz file if the uncompressed version doesn't exist.

    Args:
        gz_path: Path to the .gz file

    Returns:
        Path to the uncompressed file
    """
    # Target path is the same without .gz extension
    uncompressed_path = gz_path.with_suffix("")

    if not uncompressed_path.exists():
        click.echo(f"Decompressing {gz_path.name}...", err=True)
        with gzip.open(gz_path, "rb") as f_in:
            with open(uncompressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        click.echo(f"Created {uncompressed_path.name}", err=True)

    return uncompressed_path


@click.group()
def dereplicate() -> None:
    """Dereplication against reference databases."""
    pass


@dereplicate.command("c13")
@click.argument("c13_path", type=click.Path(exists=True))
@click.argument("formula")
@click.option(
    "--database",
    "-d",
    type=click.Path(exists=True),
    default=None,
    help="Path to database (.db) or SD file (.sd/.sdf). Auto-detects SQLite database first.",
)
@click.option(
    "--top",
    "-n",
    type=int,
    default=5,
    help="Number of top matches to show.",
)
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=0.7,
    help="Match threshold (0-1). Default: 0.7.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def dereplicate_c13(
    c13_path: str,
    formula: str,
    database: str | None,
    top: int,
    threshold: float,
    output_format: str,
) -> None:
    """Dereplicate 13C spectrum against reference database.

    C13_PATH is the path to the 13C Bruker experiment.
    FORMULA is the molecular formula (e.g., C13H18O2).

    Matches observed 13C peaks against reference spectra filtered by molecular formula.
    Uses SQLite database by default (fastest), falls back to SD files if unavailable.
    """
    # Loader can be DatabaseQueryService, NMRShiftDBLoader, or CoconutLoader
    # All have get_by_formula() method returning list[NMRShiftDBEntry]
    loader: Any = None
    db_query_service: DatabaseQueryService | None = None

    # Determine database source
    if database is not None and _is_sqlite_database(database):
        # Explicit SQLite database path provided
        try:
            db_query_service = DatabaseQueryService(database)
            db_query_service.open()
            compound_count = db_query_service.get_compound_count()
            click.echo(
                f"Using database: {Path(database).name} ({compound_count:,} compounds)",
                err=True,
            )
            loader = db_query_service
        except Exception as e:
            click.echo(f"Error opening database: {e}", err=True)
            raise SystemExit(1) from None
    elif database is None:
        # No explicit path - try SQLite database first, then SD files
        db_path = _find_database_path()
        if db_path is not None:
            try:
                db_query_service = DatabaseQueryService(db_path)
                db_query_service.open()
                compound_count = db_query_service.get_compound_count()
                click.echo(
                    f"Using database: {db_path.name} ({compound_count:,} compounds)",
                    err=True,
                )
                loader = db_query_service
            except Exception as e:
                click.echo(f"Warning: Could not open database: {e}", err=True)
                # Fall through to SD file loading

    # If no database found/loaded, fall back to SD files
    if loader is None:
        is_coconut = False
        sd_database: str | None = database  # May be explicit SD path or None

        if sd_database is None:
            # Try default SD file locations
            default_paths = [
                (Path("data/reference/coconut_predicted.sd"), True),
                (Path("data/reference/coconut_predicted.sd.gz"), True),
                (Path("data/reference/nmrshiftdb2withsignals.sd"), False),
                (Path("data/reference/nmrshiftdb2withsignals.sd.gz"), False),
                (Path("data/nmrshiftdb.sd"), False),
                (Path.home() / ".lucy" / "coconut_predicted.sd", True),
                (Path.home() / ".lucy" / "coconut_predicted.sd.gz", True),
                (Path.home() / ".lucy" / "nmrshiftdb.sd", False),
                (Path.home() / ".lucy" / "nmrshiftdb.sd.gz", False),
            ]
            for p, coconut in default_paths:
                if p.exists():
                    if p.suffix == ".gz":
                        p = _decompress_gz_if_needed(p)
                    sd_database = str(p)
                    is_coconut = coconut
                    break

            if sd_database is None:
                click.echo(
                    "Error: No reference database found. "
                    "Run 'lucy database download' to get the database, "
                    "or specify path with --database.",
                    err=True,
                )
                raise SystemExit(1)
        else:
            # Explicit SD file path provided
            is_coconut = "coconut" in Path(sd_database).name.lower()
            db_path_obj = Path(sd_database)
            if db_path_obj.suffix == ".gz":
                sd_database = str(_decompress_gz_if_needed(db_path_obj))

        # Create SD file loader
        try:
            if is_coconut:
                loader = CoconutLoader(sd_database)
                click.echo(f"Using SD file: {Path(sd_database).name} (streaming)", err=True)
            else:
                loader = NMRShiftDBLoader(sd_database)
                entries = loader.load()  # Load returns list of entries
                click.echo(
                    f"Using SD file: {Path(sd_database).name} ({len(entries):,} entries)",
                    err=True,
                )
            click.echo(
                "Hint: Run 'lucy database download' for faster dereplication.",
                err=True,
            )
        except Exception as e:
            click.echo(f"Error initializing database: {e}", err=True)
            raise SystemExit(1) from None

    try:
        # Read spectrum
        spectrum = BrukerReader.read_1d(c13_path)

        # Run dereplication
        service = DereplicationService(loader)
        result = service.dereplicate_from_spectrum(
            spectrum=spectrum,
            molecular_formula=formula,
            top_n=top,
            match_threshold=threshold,
        )

        if output_format == "json":
            data = {
                "molecular_formula": result.molecular_formula,
                "expected_carbons": result.expected_carbons,
                "observed_peaks": result.observed_peaks,
                "candidates_found": result.candidates_found,
                "best_score": result.best_score,
                "is_match": result.is_match,
                "match_mode": result.match_mode.value,
                "top_matches": [
                    {
                        "name": m.entry.name,
                        "formula": m.entry.molecular_formula,
                        "inchi": m.entry.inchi,
                        "score": m.score,
                        "matched_peaks": m.matched_peaks,
                        "unmatched_observed": m.unmatched_observed,
                        "unmatched_reference": m.unmatched_reference,
                    }
                    for m in result.top_matches
                ],
            }
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Dereplication: {result.molecular_formula}")
            click.echo(f"  Observed peaks: {result.observed_peaks}")
            click.echo(f"  Candidates found: {result.candidates_found}")
            click.echo(f"  Best score: {result.best_score:.3f}")
            click.echo(f"  Is match: {result.is_match}")
            click.echo()

            if result.top_matches:
                click.echo("Top matches:")
                for i, m in enumerate(result.top_matches, 1):
                    click.echo(f"  {i}. {m.entry.name or m.entry.inchi_key}")
                    click.echo(f"     Score: {m.score:.3f}")
                    click.echo(f"     Formula: {m.entry.molecular_formula}")
                    click.echo(f"     Matched: {m.matched_peaks}/{result.observed_peaks} peaks")
            else:
                click.echo("No matches found.")
    finally:
        # Clean up database connection if using SQLite
        if db_query_service is not None:
            db_query_service.close()
