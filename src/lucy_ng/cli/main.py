"""Main CLI entry point for lucy-ng."""

import click

from lucy_ng import __version__
from lucy_ng.cli.analyze import analyze
from lucy_ng.cli.database import database
from lucy_ng.cli.dereplicate import dereplicate
from lucy_ng.cli.fetch import fetch
from lucy_ng.cli.lsd import lsd
from lucy_ng.cli.pick import pick
from lucy_ng.cli.predict import predict
from lucy_ng.cli.read import read
from lucy_ng.cli.visualize import visualize


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
      predict     Predict NMR chemical shifts
      lsd         LSD structure elucidation
      visualize   Generate NMR correlation diagrams
      fetch       Fetch data from external sources
      database    Database management (build, info)
    """
    pass


# Register command groups
cli.add_command(read)
cli.add_command(pick)
cli.add_command(analyze)
cli.add_command(dereplicate)
cli.add_command(predict)
cli.add_command(lsd)
cli.add_command(visualize)
cli.add_command(fetch)
cli.add_command(database)
