"""Main CLI entry point for ailsa."""

from collections.abc import Sequence

import click

from ailsa import __version__
from ailsa.cli.analyze import analyze
from ailsa.cli.database import database
from ailsa.cli.dereplicate import dereplicate
from ailsa.cli.detect import detect
from ailsa.cli.fetch import fetch
from ailsa.cli.fragment import fragment
from ailsa.cli.identify import identify
from ailsa.cli.jcamp import jcamp
from ailsa.cli.lsd import lsd
from ailsa.cli.nus import nus
from ailsa.cli.pick import pick
from ailsa.cli.predict import predict
from ailsa.cli.pylsd import pylsd
from ailsa.cli.read import read
from ailsa.cli.visualize import visualize
from ailsa.cli.webview import webview


@click.group()
@click.version_option(version=__version__, prog_name="ailsa")
def cli() -> None:
    """ailsa: AI-powered Computer-Assisted Structure Elucidation.

    A command-line interface for NMR processing and structure elucidation
    of organic natural products.

    Commands:

    \b
      read        Read NMR spectra (1D, 2D)
      pick        Peak picking from spectra
      analyze     Analysis tools (symmetry detection)
      dereplicate Match against reference databases
      identify    Derive + verify compound identity (SMILES -> InChIKey + DB name)
      predict     Predict NMR chemical shifts
      detect      Statistical detection (hybridisation)
      lsd         LSD structure elucidation
      visualize   Generate NMR correlation diagrams
      fetch       Fetch data from external sources
      database    Database management (build, info)
      fragment    Fragment library (build, search, info)
      webview     Dashboard server for live CASE runs
      nus         NUS (Non-Uniform Sampling) 2D reconstruction
      jcamp       JCAMP-DX ingestion (read -> pick -> QC -> write)
    """
    pass


# Register command groups
cli.add_command(read)
cli.add_command(pick)
cli.add_command(analyze)
cli.add_command(dereplicate)
cli.add_command(identify)
cli.add_command(predict)
cli.add_command(detect)
cli.add_command(lsd)
cli.add_command(pylsd)
cli.add_command(visualize)
cli.add_command(fetch)
cli.add_command(database)
cli.add_command(fragment)
cli.add_command(webview)
cli.add_command(nus)
cli.add_command(jcamp)


LUCY_DEPRECATION_MESSAGE = (
    "Warning: `lucy` is deprecated and will be removed in the next release; "
    "use `ailsa` instead."
)


def lucy_deprecated(args: Sequence[str] | None = None) -> None:
    """Deprecated alias for the ``ailsa`` command.

    Exists for one release to give existing ``lucy`` callers (notably the
    CASE agent team and the benchmark harness, both of which parse
    ``--format json`` stdout as a machine-readable contract) time to switch
    to ``ailsa``. Prints exactly one warning line to STDERR -- never
    stdout -- and then delegates to the identical ``cli`` group, so stdout
    stays byte-identical to the ``ailsa`` entry point (D-04). Like the
    ``ailsa`` entry point, this raises ``SystemExit`` via ``cli.main``'s
    default standalone mode; it never returns before that call.
    """
    click.echo(LUCY_DEPRECATION_MESSAGE, err=True)
    cli.main(args=list(args) if args is not None else None, prog_name="lucy")
