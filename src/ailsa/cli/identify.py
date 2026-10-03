"""CLI command: derive + verify compound identity from a SMILES.

``ailsa identify`` adapts the shared deterministic identity core
(:mod:`ailsa.identity`) to Click I/O. It is installed and reachable from any
working directory (incl. an NMR data dir outside the repo), closing GAP-87-A:
the analyst (IDENT-01) and the binding gate (IDENT-02) can call the tool at
runtime, exactly like ``ailsa lsd rank``.

This module contains NO identity logic of its own — it imports
``check_identity_result`` from :mod:`ailsa.identity` (D-05: one shared path).
Identity never hard-fails (D-06): the command always exits 0.
"""

from __future__ import annotations

import json

import click

from ailsa.identity import check_identity_result


@click.command("identify")
@click.option(
    "--smiles",
    required=True,
    help="Solution SMILES to derive an identity for.",
)
@click.option(
    "--reported-name",
    default=None,
    help="Trivial name asserted by the analyst (optional).",
)
@click.option(
    "--database",
    "-d",
    type=click.Path(exists=True),
    default=None,
    help="Path to the dereplication DB (.db). Auto-resolved when omitted.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def identify(
    smiles: str,
    reported_name: str | None,
    database: str | None,
    output_format: str,
) -> None:
    """Derive a deterministic structural identity and gate a reported name.

    Derives an InChIKey + canonical SMILES from SMILES (never a recalled name),
    looks the structure up in the bundled dereplication DB, and — if a name is
    asserted — gates it against the tool-derived identity. A name<->structure
    disagreement downgrades the name to "tentative" with a warning; it never
    hard-fails (D-06). Always exits 0.

    Example:

        ailsa identify --smiles "CC(C)Cc1ccc(cc1)C(C)C(=O)O" --format json
    """
    result = check_identity_result(smiles, reported_name, db_path=database)

    if output_format == "json":
        click.echo(json.dumps(result, indent=2))
        return

    derived = result.get("derived", {})
    if not isinstance(derived, dict):  # pragma: no cover - defensive
        derived = {}

    click.echo(f"Verdict: {result.get('verdict')}")
    derived_name = derived.get("name") or "(no DB name)"
    click.echo(f"Derived name: {derived_name}")
    click.echo(f"InChIKey: {derived.get('inchi_key', '(none)')}")
    click.echo(f"Canonical SMILES: {derived.get('canonical_smiles', '(none)')}")
    if result.get("reported_name") is not None:
        click.echo(f"Reported name: {result.get('reported_name')}")
        click.echo(f"Name match: {result.get('name_match')}")
    warning = result.get("warning")
    if warning:
        click.echo(str(warning))
