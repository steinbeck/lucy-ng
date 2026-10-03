"""CliRunner tests for the ``ailsa identify`` command.

``ailsa identify`` adapts the shared identity core (:mod:`ailsa.identity`) to
Click I/O. These tests lock the --format json schema (inchi_key + verdict) and
the text-format smoke path, plus the CASE5 (indigo vs isoindigo) mismatch and
CASE4 (chamazulene no-hit) verdicts. The DB-dependent CASE4/CASE5 cases skip
cleanly when the dereplication DB is absent.

Fixtures are reused verbatim from tests/test_verify_case_identity.py.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from ailsa.cli.identify import identify
from ailsa.database.finder import DatabaseFinder

# Reused fixtures (VERIFIED against the live DB, see 87-RESEARCH.md).
CHAMAZULENE_SMILES = "CCc1ccc2ccc(C)c-2c(C)c1"
INDIGO_SMILES = r"O=C1/C(=C2\Nc3ccccc3C2=O)Nc2ccccc21"
ETHANOL_KEY = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"

_DB = DatabaseFinder.find_derep_database()
db_required = pytest.mark.skipif(
    _DB is None,
    reason="dereplication DB not available (find_derep_database() is None)",
)


def test_identify_json_has_inchikey_and_verdict() -> None:
    """``identify --smiles CCO --format json`` → exit 0, JSON with derived.inchi_key + verdict."""
    runner = CliRunner()
    result = runner.invoke(identify, ["--smiles", "CCO", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "verdict" in data
    assert data["derived"]["inchi_key"] == ETHANOL_KEY


def test_identify_invalid_smiles_exits_zero() -> None:
    """Garbage SMILES must NOT crash — exit 0 with a graceful verdict (D-06)."""
    runner = CliRunner()
    result = runner.invoke(identify, ["--smiles", "invalid!!", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["derived"]["matched"] is False
    assert data["verdict"] == "novel"


def test_identify_text_format_smoke() -> None:
    """Default text format prints the InChIKey + verdict and exits 0."""
    runner = CliRunner()
    result = runner.invoke(identify, ["--smiles", "CCO"])
    assert result.exit_code == 0, result.output
    assert "Verdict:" in result.output
    assert ETHANOL_KEY in result.output


@db_required
def test_identify_indigo_mislabel_is_tentative() -> None:
    """CASE5: indigo reported as 'isoindigo' → tentative verdict + non-null warning."""
    runner = CliRunner()
    result = runner.invoke(
        identify,
        ["--smiles", INDIGO_SMILES, "--reported-name", "isoindigo", "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["name_match"] is False
    assert data["verdict"] == "tentative"
    assert data["warning"]


@db_required
def test_identify_chamazulene_no_hit_is_novel() -> None:
    """CASE4: chamazulene is absent from the DB → novel, no asserted name."""
    runner = CliRunner()
    result = runner.invoke(
        identify, ["--smiles", CHAMAZULENE_SMILES, "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["derived"]["matched"] is False
    assert data["verdict"] == "novel"
