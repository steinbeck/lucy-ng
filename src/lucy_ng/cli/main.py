"""Main CLI entry point for lucy-ng."""

import click

from lucy_ng import __version__
from lucy_ng.cli.analyze import analyze
from lucy_ng.cli.database import database
from lucy_ng.cli.dereplicate import dereplicate
from lucy_ng.cli.detect import detect
from lucy_ng.cli.fetch import fetch
from lucy_ng.cli.fragment import fragment
from lucy_ng.cli.identify import identify
from lucy_ng.cli.jcamp import jcamp
from lucy_ng.cli.lsd import lsd
from lucy_ng.cli.nus import nus
from lucy_ng.cli.pick import pick
from lucy_ng.cli.predict import predict
from lucy_ng.cli.pylsd import pylsd
from lucy_ng.cli.read import read
from lucy_ng.cli.visualize import visualize
from lucy_ng.cli.webview import webview


@click.group()
@click.version_option(version=__version__, prog_name="lucy")
def cli() -> None:
    """lucy-ng: AI-powered Computer-Assisted Structure Elucidation.

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
