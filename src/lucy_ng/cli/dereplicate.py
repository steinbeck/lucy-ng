"""CLI commands for dereplication against reference databases."""

import gzip
import json
import shutil
from pathlib import Path

import click

from lucy_ng.dereplication import CoconutLoader, DereplicationService, NMRShiftDBLoader
from lucy_ng.readers import BrukerReader


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
    help="Path to reference SD file (COCONUT or nmrshiftdb). Uses COCONUT if available.",
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
    Uses COCONUT database by default (larger), falls back to nmrshiftdb if unavailable.
    """
    # Find database path
    is_coconut = False
    if database is None:
        # Try default locations (COCONUT first - larger database)
        # Also check for .gz compressed versions
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
                # If it's a .gz file, decompress it first
                if p.suffix == ".gz":
                    p = _decompress_gz_if_needed(p)
                database = str(p)
                is_coconut = coconut
                break

        if database is None:
            click.echo(
                "Error: No reference database found. "
                "Specify path with --database or place nmrshiftdb2withsignals.sd.gz in data/reference/",
                err=True,
            )
            raise SystemExit(1)
    else:
        # Auto-detect format from filename
        is_coconut = "coconut" in Path(database).name.lower()
        # Handle .gz files
        db_path = Path(database)
        if db_path.suffix == ".gz":
            database = str(_decompress_gz_if_needed(db_path))

    # Create loader (streaming - no upfront load needed)
    try:
        if is_coconut:
            loader = CoconutLoader(database)
        else:
            loader = NMRShiftDBLoader(database)
            loader.load()  # nmrshiftdb is small enough to load fully
    except Exception as e:
        click.echo(f"Error initializing database: {e}", err=True)
        raise SystemExit(1)

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
