"""CLI commands for fetching NMR data from external sources."""

import json
import sys

import click


@click.group()
def fetch() -> None:
    """Fetch NMR data from external repositories.

    Download NMR spectra from online databases for local analysis.

    \b
    Commands:
      nmrxiv    Download from NMRXiv repository
    """
    pass


@fetch.command("nmrxiv")
@click.argument("identifier")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=".",
    help="Output directory (default: current directory)",
)
@click.option(
    "--study",
    type=str,
    default=None,
    help="Specific study ID to download (overrides DOI study)",
)
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    default=False,
    help="Download all studies (even if DOI specifies one)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress progress output",
)
def fetch_nmrxiv(
    identifier: str,
    output: str,
    study: str | None,
    download_all: bool,
    output_format: str,
    quiet: bool,
) -> None:
    """Download NMR dataset from NMRXiv repository.

    IDENTIFIER can be:

    \b
    - DOI: 10.57992/NMRXIV.P10.S69
    - Project ID: P10
    - URL: https://nmrxiv.org/P10

    When a DOI specifies a study (e.g., P10.S69), only that study is downloaded.
    Use --all to download the entire project instead.

    \b
    Examples:
      ailsa fetch nmrxiv 10.57992/NMRXIV.P10.S69 --output ./data/
      ailsa fetch nmrxiv P10 --output ./data/
      ailsa fetch nmrxiv P10 --study S69
      ailsa fetch nmrxiv P10 --all --format json
    """
    from ailsa.nmrxiv import NMRXivClient, NMRXivError

    try:
        with NMRXivClient() as client:
            # Parse identifier first to show what we're fetching
            parsed = client.parse_identifier(identifier)

            if output_format == "text" and not quiet:
                click.echo(f"Fetching from NMRXiv: {parsed.project_id}")
                if parsed.study_id and not download_all:
                    click.echo(f"  Study: {parsed.study_id}")
                elif download_all:
                    click.echo("  Downloading all studies")
                click.echo()

            # Download
            result = client.download(
                identifier=identifier,
                output_dir=output,
                study_id=study,
                download_all=download_all,
                progress=not quiet and output_format == "text",
            )

            if output_format == "json":
                output_data = {
                    "success": True,
                    "project_id": result.project_id,
                    "project_name": result.project_name,
                    "doi": result.doi,
                    "output_path": result.output_path,
                    "studies_downloaded": result.studies_downloaded,
                    "total_datasets": result.total_datasets,
                    "total_files": result.total_files,
                    "total_size_mb": round(result.total_size_mb, 2),
                }
                click.echo(json.dumps(output_data, indent=2))
            else:
                click.echo()
                click.echo(f"Project: {result.project_name}")
                if result.doi:
                    click.echo(f"DOI: {result.doi}")
                click.echo(f"Studies: {', '.join(result.studies_downloaded)}")
                click.echo()
                click.echo(
                    f"Downloaded {result.total_files} files "
                    f"({result.total_datasets} datasets, "
                    f"{result.total_size_mb:.1f} MB)"
                )
                click.echo(f"Output: {result.output_path}")

    except NMRXivError as e:
        if output_format == "json":
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)
