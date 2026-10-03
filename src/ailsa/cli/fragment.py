"""CLI commands for fragment library management and search."""

from __future__ import annotations

import json
from pathlib import Path

import click
from click.core import ParameterSource

from ailsa.database import DatabaseManager
from ailsa.fragments import DEFFFormatter, FragmentDatabaseManager
from ailsa.fragments.extractor import SSCExtractor
from ailsa.fragments.searcher import FragmentSearcher

# PKG-05: the fragments DB gets the same dual-filename treatment as the
# derep DB (not literally required by PKG-05's wording, but the identical
# defect against the real 605 MB lucy-ng-fragments.db on this machine).
NEW_FRAGMENTS_DB_NAME = "ailsa-fragments.db"
LEGACY_FRAGMENTS_DB_NAME = "lucy-ng-fragments.db"
DEFAULT_FRAGMENTS_DB = Path("data/reference") / NEW_FRAGMENTS_DB_NAME


def resolve_default_fragments_db() -> Path:
    """Resolve the default fragments-DB path (PKG-05, mirrors DatabaseFinder).

    Prefers an existing new-named file, then an existing legacy-named file,
    then falls back to the new default path when neither exists.
    """
    new_path = Path("data/reference") / NEW_FRAGMENTS_DB_NAME
    if new_path.exists():
        return new_path
    legacy_path = Path("data/reference") / LEGACY_FRAGMENTS_DB_NAME
    if legacy_path.exists():
        return legacy_path
    return new_path


@click.group()
def fragment() -> None:
    """Fragment library management and search."""


@fragment.command()
@click.argument("db_path", type=click.Path(path_type=Path), default=DEFAULT_FRAGMENTS_DB)
def info(db_path: Path) -> None:
    """Show fragment database statistics.

    Display information about a fragment database including schema version,
    SSC count, bin size, and file size.

    With no argument, auto-detects the fragment database (new or legacy
    filename, PKG-05).

    Example:

        ailsa fragment info data/reference/lucy-ng-fragments.db
    """
    if click.get_current_context().get_parameter_source("db_path") == ParameterSource.DEFAULT:
        db_path = resolve_default_fragments_db()

    if not db_path.exists():
        click.echo(
            f"Error: Fragment database not found: {db_path}\n"
            "Run 'ailsa fragment build' to create it, or specify a path with"
            " 'ailsa fragment info <path>'",
            err=True,
        )
        raise click.Abort()

    with FragmentDatabaseManager(db_path) as db:
        version = db.get_schema_version()
        if version != 7:
            click.echo(
                f"Warning: Expected schema version 7, found {version}."
                " This may not be a fragment database.",
                err=True,
            )

        ssc_count = db.get_ssc_count()
        bin_size = db.get_bin_size()
        file_size_mb = db_path.stat().st_size / 1_000_000

        click.echo(f"Fragment database: {db_path}")
        click.echo(f"  Schema version: {version}")
        click.echo(f"  SSC count: {ssc_count:,}")
        click.echo(f"  Bin size: {bin_size:.1f} ppm")
        click.echo(f"  File size: {file_size_mb:.1f} MB")


@fragment.command()
@click.option(
    "--shifts",
    required=True,
    type=str,
    help="Comma-separated 13C chemical shifts in ppm.",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_FRAGMENTS_DB,
    show_default=True,
    help="Path to fragment database.",
)
@click.option(
    "--dev-threshold",
    type=float,
    default=2.0,
    show_default=True,
    help="Max per-signal deviation for fine matching (ppm).",
)
@click.option(
    "--avgdev-threshold",
    type=float,
    default=1.0,
    show_default=True,
    help="Max average deviation for fine matching (ppm).",
)
@click.option(
    "--top",
    "max_results",
    type=int,
    default=5,
    show_default=True,
    help="Maximum number of fragments to return.",
)
@click.option(
    "--min-atoms",
    "min_atom_count",
    type=int,
    default=3,
    show_default=True,
    help="Minimum fragment heavy atom count.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Show pre-screen and fine-match counts on stderr.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="json",
    show_default=True,
    help="Output format.",
)
def search(
    shifts: str,
    db_path: Path,
    dev_threshold: float,
    avgdev_threshold: float,
    max_results: int,
    min_atom_count: int,
    verbose: bool,
    output_format: str,
) -> None:
    """Search fragment database for SSC matches to experimental 13C shifts.

    Runs a two-phase pipeline: fingerprint pre-screening followed by greedy
    nearest-neighbour fine matching. Results are ranked by atom count
    (descending) then average deviation (ascending).

    \b
    Examples:
        ailsa fragment search --shifts "155.08,151.58,130.2"

        ailsa fragment search --shifts "128.0,130.5,199.1" --format text

        ailsa fragment search --shifts "128.0,130.5" --verbose --top 10
    """
    # PKG-05: an explicit --db is honoured as given; the default picks up an
    # existing legacy-named fragments database in place of the new default.
    if click.get_current_context().get_parameter_source("db_path") == ParameterSource.DEFAULT:
        db_path = resolve_default_fragments_db()

    # Parse shifts
    try:
        shift_list = [float(s.strip()) for s in shifts.split(",")]
    except ValueError as e:
        click.echo(
            "Error: Invalid shifts format. Use comma-separated numbers.",
            err=True,
        )
        raise click.Abort() from e

    if not shift_list:
        click.echo("Error: No shifts provided.", err=True)
        raise click.Abort()

    # Validate database exists
    if not db_path.exists():
        click.echo(
            f"Error: Fragment database not found: {db_path}\n"
            "Run 'ailsa fragment build' to create it, or specify a path with"
            " --db <path>",
            err=True,
        )
        raise click.Abort()

    # Run search
    with FragmentSearcher(db_path) as searcher:
        matches = searcher.search(
            experimental_shifts=shift_list,
            dev_threshold=dev_threshold,
            avgdev_threshold=avgdev_threshold,
            max_results=max_results,
            min_atom_count=min_atom_count,
            verbose=verbose,
        )
        prescreening_count = searcher.prescreening_count
        fine_match_count = searcher.fine_match_count

    # Build DEFF commands (double quotes required by LSD 3.4.9)
    # NOTE: Multi-fragment output uses F1..Fn. For CASE workflow, use ailsa fragment to-lsd
    # with --filter-index 3 (reserves F1/F2 for ring exclusion per Phase 75 convention).
    deff_commands = [
        f'DEFF F{i + 1} "fragment_{i + 1}.lsd"' for i in range(len(matches))
    ]

    # Build FEXP command (double quotes required by LSD 3.4.9)
    if len(matches) == 0:
        fexp_command = ""
    elif len(matches) == 1:
        fexp_command = 'FEXP "F1"'
    else:
        parts = " OR ".join(f"F{i + 1}" for i in range(len(matches)))
        fexp_command = f'FEXP "{parts}"'

    # Output
    if output_format == "json":
        output = {
            "query_shifts": shift_list,
            "prescreening_count": prescreening_count,
            "fine_match_count": fine_match_count,
            "result_count": len(matches),
            "fragments": [m.model_dump() for m in matches],
            "deff_commands": deff_commands,
            "fexp_command": fexp_command,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        # Text output
        click.echo(
            f"Fragment search results ({len(matches)} fragments"
            f" from {fine_match_count} candidates):"
        )
        click.echo()
        if matches:
            click.echo(f" {'Rank':>4}  {'Atoms':>5}  {'AVGDEV':>6}  SMILES")
            for m in matches:
                click.echo(
                    f" {m.rank:>4}  {m.atom_count:>5}  {m.avg_deviation:>6.2f}"
                    f"  {m.smiles}"
                )
            click.echo()
            click.echo("DEFF commands:")
            for cmd in deff_commands:
                click.echo(f"  {cmd}")
            click.echo(f"  {fexp_command}")
        else:
            click.echo("  No matching fragments found.")


@fragment.command()
@click.argument("compound_db", type=click.Path(exists=True, path_type=Path))
@click.argument("fragment_db", type=click.Path(path_type=Path), default=DEFAULT_FRAGMENTS_DB)
@click.option(
    "--chunk-size",
    default=1000,
    type=int,
    show_default=True,
    help="Compounds per checkpoint batch",
)
@click.option(
    "--sample",
    type=int,
    default=None,
    help="Process only N compounds (for bin-size validation)",
)
@click.option(
    "--resume/--fresh",
    default=True,
    help="Resume from checkpoint (default) or restart from scratch",
)
def build(
    compound_db: Path,
    fragment_db: Path,
    chunk_size: int,
    sample: int | None,
    resume: bool,
) -> None:
    """Build fragment (SSC) database from compound database.

    Extracts substructure-subspectrum correlations from all compounds with
    atom-indexed 13C shifts. Supports checkpointing for multi-hour runs.

    COMPOUND_DB: Path to lucy-ng-derep.db (source compounds).
    FRAGMENT_DB: Path to lucy-ng-fragments.db (output, created if not exists).

    \b
    Examples:
        # Validate bin size on 1000 compounds
        ailsa fragment build data/reference/lucy-ng-derep.db --sample 1000

        # Full extraction (resumable)
        ailsa fragment build data/reference/lucy-ng-derep.db

        # Restart from scratch
        ailsa fragment build data/reference/lucy-ng-derep.db --fresh
    """
    if click.get_current_context().get_parameter_source("fragment_db") == ParameterSource.DEFAULT:
        fragment_db = resolve_default_fragments_db()

    with DatabaseManager(compound_db) as compound_db_mgr, \
         FragmentDatabaseManager(fragment_db) as fragment_db_mgr:
        fragment_db_mgr.create_tables()

        extractor = SSCExtractor(
            compound_db=compound_db_mgr,
            fragment_db=fragment_db_mgr,
        )

        # --resume gives resume=True, --fresh gives resume=False
        result = extractor.run(
            chunk_size=chunk_size,
            sample=sample,
            resume=resume,
            fresh=not resume,
        )

        click.echo(f"Compounds processed: {result.compounds_processed:,}")
        click.echo(f"Compounds skipped:   {result.compounds_skipped:,}")
        click.echo(f"SSCs extracted:      {result.sscs_extracted:,}")
        click.echo(f"SSCs duplicate:      {result.sscs_duplicate:,}")

        # Self-search recall validation when sample mode used with 100+ compounds
        if sample is not None and sample >= 100:
            click.echo("")
            click.echo("Running self-search recall validation...")
            recall = extractor.validate_self_search(sample_size=100)
            hits = round(recall * 100)
            click.echo(f"Self-search recall: {recall:.1%} ({hits}/100)")
            if recall < 0.99:
                click.echo(
                    "WARNING: Recall below 99% — bin size may need adjustment",
                    err=True,
                )

        total_count = fragment_db_mgr.get_ssc_count()
        click.echo("")
        click.echo(f"Fragment DB total SSCs: {total_count:,}")


@fragment.command("to-lsd")
@click.argument("smiles", type=str)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory to write fragment file. Defaults to current directory.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--filter-index",
    "filter_index",
    type=int,
    default=3,
    show_default=True,
    help=(
        "DEFF filter index for the goodlist fragment (default 3). "
        "F1 and F2 are reserved for ring exclusion (DEFF F1 ring3, DEFF F2 ring4). "
        "Use 3 or higher when ring exclusion is active (Phase 75 convention). "
        "Use --filter-index 1 only when ring exclusion is not active (backward compat)."
    ),
)
def to_lsd(smiles: str, output_dir: Path | None, output_format: str, filter_index: int) -> None:
    """Generate an LSD fragment file from SMILES.

    Converts a SMILES string to an LSD SSTR/LINK fragment definition file
    and writes it to the output directory (or current directory by default).

    The generated file can be referenced from an LSD input file using the
    printed DEFF/FEXP commands.

    \b
    Examples:
        ailsa fragment to-lsd "Cc1ccccc1"

        ailsa fragment to-lsd "c1ccccc1" --format text

        ailsa fragment to-lsd "c1ccccc1" --output-dir analysis/iteration_01/
    """
    try:
        written_path = DEFFFormatter.write_fragment_file(
            smiles, output_dir=output_dir
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    deff_cmd = DEFFFormatter.deff_command(filter_index, written_path.name)
    fexp_cmd = DEFFFormatter.fexp_command([filter_index])
    content = written_path.read_text()

    # Count SSTR lines for atom count
    atom_count = sum(1 for ln in content.splitlines() if ln.startswith("SSTR"))

    # Extract canonical SMILES from comment line
    canonical = ""
    for line in content.splitlines():
        if line.startswith("; Fragment:"):
            canonical = line.split(": ", 1)[1].strip()
            break

    if output_format == "json":
        output = {
            "smiles": smiles,
            "canonical": canonical,
            "filename": written_path.name,
            "path": str(written_path),
            "deff_command": deff_cmd,
            "fexp_command": fexp_cmd,
            "atom_count": atom_count,
            "content": content,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(f"Fragment file written: {written_path}")
        click.echo(f"Atoms: {atom_count}")
        click.echo(f"DEFF command: {deff_cmd}")
        click.echo(f"FEXP command: {fexp_cmd}")
