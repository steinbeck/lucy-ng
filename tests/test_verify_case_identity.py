"""Tests for the identity-derivation core and name<->structure gate.

The deterministic identity core now lives in the installed package
(``ailsa.identity``, D-05). These tests import it directly. The
``check-identity`` subprocess invocations exercise the thin
``scripts/verify_case_solution.py`` adapter that imports the same core, so the
back-compat CLI contract stays locked.

Two layers are exercised:

1. Direct import of ``derive_identity`` / ``check_identity_result`` (and the
   ``_normalize_name`` token helper + ``_COCONUT_ACCESSION_RE`` constant) from
   ``ailsa.identity``.
2. A subprocess invocation of ``check-identity`` to lock the CLI contract.

Regression fixtures (VERIFIED against the live DB, see 87-RESEARCH.md):

- Chamazulene  CCc1ccc2ccc(C)c-2c(C)c1            FVZVDQVUOAAMCG-UHFFFAOYSA-N  NO DB HIT
- Indigo       O=C1/C(=C2\\Nc3ccccc3C2=O)Nc2ccccc21 COHYTHOBJLSHDF-BUHFOSPRSA-N  HIT (nmrshiftdb)
                 DB name: "2,2'-Bis(2,3-dihydro-3- oxoindolyliden); Indigo"
- Isoindigo    O=C1Nc2ccccc2/C1=C1/C(=O)Nc2ccccc21 MLCPSWPIYHDOKG-YPKPFQOOSA-N  NO HIT
- Ibuprofen    CC(Cc1ccc(C(C)C)cc1)C(=O)O          FLMVHZOJMRGXRO-UHFFFAOYSA-N  NO HIT

DB-dependent tests are skipped cleanly when
``DatabaseFinder.find_derep_database()`` returns None (CI without the 2.8 GB DB).
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from ailsa import identity as lucy_identity
from ailsa.database.finder import DatabaseFinder
from ailsa.identity import derive_identity

SCRIPT = Path(__file__).parent.parent / "scripts" / "verify_case_solution.py"

# --- fixtures ----------------------------------------------------------------
CHAMAZULENE_SMILES = "CCc1ccc2ccc(C)c-2c(C)c1"
CHAMAZULENE_KEY = "FVZVDQVUOAAMCG-UHFFFAOYSA-N"
INDIGO_SMILES = r"O=C1/C(=C2\Nc3ccccc3C2=O)Nc2ccccc21"
INDIGO_KEY = "COHYTHOBJLSHDF-BUHFOSPRSA-N"
IBUPROFEN_SMILES = "CC(Cc1ccc(C(C)C)cc1)C(=O)O"
ETHANOL_KEY = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"

_DB = DatabaseFinder.find_derep_database()
db_required = pytest.mark.skipif(
    _DB is None,
    reason="dereplication DB not available (find_derep_database() is None)",
)


def _run_cli(*args: str) -> tuple[int, dict]:
    """Run ``verify_case_solution.py check-identity`` and parse JSON stdout."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check-identity", *args],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, data


# ---------------------------------------------------------------------------
# derive_identity — structural derivation (IDENT-01)
# ---------------------------------------------------------------------------


def test_inchikey_and_canonical_smiles_derived() -> None:
    """Ethanol → deterministic InChIKey + canonical SMILES; no asserted name."""
    out = derive_identity("CCO")
    assert out["inchi_key"] == ETHANOL_KEY
    assert out["canonical_smiles"] == "CCO"
    # When not matched, the function must not assert a name field.
    if out.get("matched") is False:
        assert "name" not in out or out.get("name") is None


def test_invalid_smiles_returns_novel() -> None:
    """Garbage SMILES → graceful novel verdict with an error key, no crash."""
    out = derive_identity("not-a-smiles")
    assert out["matched"] is False
    assert out["confidence"] == "novel"
    assert "error" in out


def test_chamazulene_no_hit() -> None:
    """Chamazulene is absent from the DB → novel; InChIKey pinned."""
    out = derive_identity(CHAMAZULENE_SMILES)
    assert out["matched"] is False
    assert out["confidence"] == "novel"
    assert out["inchi_key"] == CHAMAZULENE_KEY


def test_ibuprofen_no_hit() -> None:
    """Ibuprofen (a drug) is also absent → proves no-hit is common."""
    out = derive_identity(IBUPROFEN_SMILES)
    assert out["matched"] is False


# ---------------------------------------------------------------------------
# Two-path DB lookup (IDENT-01 / D-02) — DB-guarded
# ---------------------------------------------------------------------------


@db_required
def test_indigo_found_via_inchikey() -> None:
    """Indigo is found via the InChIKey path → reaches the nmrshiftdb partition."""
    out = derive_identity(INDIGO_SMILES)
    assert out["matched"] is True
    assert out["source"] == "nmrshiftdb"
    assert "indigo" in out["name"].lower()


@db_required
def test_coconut_found_via_smiles_fallback() -> None:
    """A live COCONUT canonical SMILES round-trips via the SMILES fallback path."""
    con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT smiles FROM compounds WHERE smiles != '' AND source = 'coconut' LIMIT 1"
    ).fetchone()
    con.close()
    assert row is not None, "no coconut row with a SMILES found"
    out = derive_identity(row["smiles"])
    assert out["matched"] is True
    assert out["source"] == "coconut"
    assert out["confidence"] == "confirmed-structure"


# ---------------------------------------------------------------------------
# check-identity CLI contract + verdicts (IDENT-02 / IDENT-03 / D-06)
# ---------------------------------------------------------------------------


@db_required
def test_indigo_mislabel_mismatch() -> None:
    """CASE5: indigo reported as 'isoindigo' → name_match False, tentative + warning."""
    code, data = _run_cli(
        "--smiles", INDIGO_SMILES, "--reported-name", "isoindigo"
    )
    assert code == 0
    assert data["name_match"] is False
    assert data["verdict"] == "tentative"
    assert data["warning"]


@db_required
def test_name_match_tolerant_to_punctuation_and_word_order() -> None:
    """'Indigo' matches the ';'-delimited DB synonym list → confirmed, no false-fail."""
    code, data = _run_cli(
        "--smiles", INDIGO_SMILES, "--reported-name", "Indigo"
    )
    assert code == 0
    assert data["name_match"] is True
    assert data["verdict"] == "confirmed"


@db_required
def test_no_false_substring_match() -> None:
    """A bare substring ('in') of the derived name ('Indigo') must NOT match."""
    code, data = _run_cli("--smiles", INDIGO_SMILES, "--reported-name", "in")
    assert code == 0
    assert data["name_match"] is False


def test_chamazulene_asserted_name_is_tentative() -> None:
    """CASE4: a trivial name asserted on a no-hit structure → tentative + warning."""
    code, data = _run_cli(
        "--smiles", CHAMAZULENE_SMILES, "--reported-name", "chamazulene"
    )
    assert code == 0
    assert data["derived"]["matched"] is False
    assert data["verdict"] == "tentative"
    assert data["warning"]
    assert data["name_match"] in (None, False)


def test_novel_no_asserted_name_is_clean() -> None:
    """No reported name on a no-hit structure → novel, no warning, name_match None."""
    code, data = _run_cli("--smiles", CHAMAZULENE_SMILES)
    assert code == 0
    assert data["derived"]["matched"] is False
    assert data["verdict"] == "novel"
    assert data["warning"] is None
    assert data["name_match"] is None


# ---------------------------------------------------------------------------
# Accession / empty-name handling (WR-01/02/03 regressions) — structure-only
# ---------------------------------------------------------------------------


def test_dotsuffixed_coconut_accession_is_recognised() -> None:
    """~55% of COCONUT names are dot-suffixed (CNP….N); the regex MUST match
    them, else the accession leaks into the trivial-name slot (WR-01/WR-02)."""
    assert lucy_identity._COCONUT_ACCESSION_RE.match("CNP0220816")
    assert lucy_identity._COCONUT_ACCESSION_RE.match("CNP0220816.1")
    assert lucy_identity._COCONUT_ACCESSION_RE.match("CNP0220816.12")
    # An accession (suffixed or not) must contribute NO name-match tokens.
    assert lucy_identity._normalize_name("CNP0220816.1") == set()
    assert lucy_identity._normalize_name("CNP0220816") == set()


@db_required
def test_dotsuffixed_coconut_row_is_structure_only() -> None:
    """A live dot-suffixed COCONUT row → confirmed-structure, not confirmed."""
    con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT smiles FROM compounds "
        "WHERE smiles != '' AND source = 'coconut' AND name LIKE 'CNP%.%' LIMIT 1"
    ).fetchone()
    con.close()
    if row is None:
        pytest.skip("no dot-suffixed coconut row found")
    out = derive_identity(row["smiles"])
    assert out["matched"] is True
    assert out["confidence"] == "confirmed-structure"
    assert out.get("trivial_name_confirmed") is False


def test_empty_name_match_warns_in_db_not_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matched structure whose DB row has an empty name must NOT produce the
    'structure not in DB' warning (WR-03) — the structure IS in the DB."""
    monkeypatch.setattr(
        lucy_identity,
        "derive_identity",
        lambda *a, **k: {
            "matched": True,
            "name": "",
            "source": "nmrshiftdb",
            "inchi_key": "X",
            "canonical_smiles": "CCO",
            "confidence": "confirmed-structure",
            "trivial_name_confirmed": False,
        },
    )
    data = lucy_identity.check_identity_result("CCO", reported_name="ethanol")
    assert data["verdict"] == "tentative"
    assert data["warning"] is not None
    assert "not in DB" not in data["warning"]
    assert "no trivial name" in data["warning"]


def test_corrupt_db_degrades_gracefully(tmp_path: Path) -> None:
    """A corrupt/non-DB file passed as db_path must NOT raise (D-06): the gate
    degrades to db_unavailable + novel, never crashes the report (CR-01)."""
    bogus = tmp_path / "not_a_real.db"
    bogus.write_text("this is plainly not a sqlite database")
    out = derive_identity("CCO", db_path=bogus)
    assert out["matched"] is False
    assert out.get("db_unavailable") is True
    assert out["confidence"] == "novel"
    # The structural identity is still firm even when the DB is unreadable.
    assert out["inchi_key"] == ETHANOL_KEY
    # And the full gate still exits-0-equivalent (returns, never raises).
    data = lucy_identity.check_identity_result("CCO", reported_name="ethanol", db_path=bogus)
    assert data["verdict"] in ("novel", "tentative")
