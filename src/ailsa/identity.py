"""Deterministic structural-identity core for CASE solutions.

This module is the SINGLE shared implementation (D-05) of the Phase-87
identity logic: derive a deterministic structural identity (InChIKey +
canonical SMILES) from a solution SMILES, look it up in the bundled
dereplication DB via two complementary paths (InChIKey-first for the
nmrshiftdb partition, canonical-SMILES fallback for the COCONUT partition),
and gate a reported trivial name against the tool-derived identity.

It is consumed by BOTH the installed ``ailsa identify`` CLI command
(``ailsa.cli.identify``) and the legacy ``scripts/verify_case_solution.py
check-identity`` adapter. The logic was extracted verbatim from 87-01 — it
encodes the COCONUT-accession + empty-name fixes (commit 2867dc4) and the
tolerant token-set name matching. This module is pure library code: it does
NOT import argparse, click, or sys, never prints, and never calls sys.exit
(D-06: identity never hard-fails — a name<->structure disagreement downgrades
to "tentative" with a warning).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from rdkit import Chem

# COCONUT accession pattern (e.g. "CNP0220816" or the dot-suffixed
# "CNP0220816.1"): a DB hit whose name is an accession means the structure is
# known but no human/trivial name is stored. ~55% of COCONUT rows carry the
# ".N" suffix, so the optional suffix MUST be matched or those hits leak the
# accession into the trivial-name slot and the name gate false-trips.
_COCONUT_ACCESSION_RE = re.compile(r"^CNP\d+(?:\.\d+)?$", re.IGNORECASE)

# Generic filler tokens dropped before token-set name comparison.
_NAME_FILLER_TOKENS = frozenset({"dye", "the", "a", "an", "of"})


def _resolve_db_path(db_path: str | Path | None) -> Path | None:
    """Resolve the dereplication DB path.

    Prefers the explicit ``db_path`` arg, then ``DatabaseFinder``. Falls back to
    an inline probe (``LUCY_DATABASE`` env -> ``data/reference/`` -> Dropbox dev
    path) when ``ailsa`` is not importable (RESEARCH Pitfall 5).
    """
    if db_path is not None:
        p = Path(db_path)
        return p if p.exists() else None

    try:
        from ailsa.database.finder import DatabaseFinder

        return DatabaseFinder.find_derep_database()
    except Exception:  # pragma: no cover - import fallback path
        import os

        # PKG-05: this branch runs exactly when the DatabaseFinder import
        # failed, so it cannot import DatabaseFinder.DB_NAMES/PROJECT_DIR_NAMES
        # — the new and legacy filenames/directory names are literals here.
        env_db = os.environ.get("LUCY_DATABASE")
        candidates = [Path(env_db) if env_db else None]
        for name in ("ailsa-derep.db", "lucy-ng-derep.db"):
            candidates.append(Path("data/reference") / name)
        for project_dir in ("ailsa", "lucy-ng"):
            for name in ("ailsa-derep.db", "lucy-ng-derep.db"):
                candidates.append(
                    Path.home()
                    / "Dropbox"
                    / "develop"
                    / project_dir
                    / "data"
                    / "reference"
                    / name
                )
        for cand in candidates:
            if cand is not None and cand.exists():
                return cand
        return None


def derive_identity(smiles: str, db_path: str | Path | None = None) -> dict[str, object]:
    """Derive a deterministic structural identity for ``smiles`` and look it up.

    Identity is derived with RDKit (never a recalled name): canonical SMILES via
    ``Chem.MolToSmiles`` with DEFAULT flags only (byte-equality with the
    importer's stored canonicalization, RESEARCH Finding 2) and an InChIKey via
    ``Chem.MolToInchiKey``.

    DB lookup is two-path and COMPLEMENTARY:

    * Path 1 (InChIKey-first) reaches the nmrshiftdb partition (inchi_key
      populated, smiles empty).
    * Path 2 (canonical-SMILES fallback, only if Path 1 misses) reaches the
      COCONUT partition (smiles populated, inchi_key empty).

    Args:
        smiles: A solution SMILES string (semi-trusted CASE-pipeline output).
        db_path: Optional explicit DB path; auto-resolved when None.

    Returns:
        A dict always carrying ``matched`` plus ``confidence``. On a hit it adds
        ``name``, ``source``, ``inchi_key``, ``canonical_smiles``. On no hit it
        carries the structural identity with ``confidence == "novel"``. Invalid
        SMILES return ``{"matched": False, "error": ..., "confidence": "novel"}``.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"matched": False, "error": "invalid smiles", "confidence": "novel"}

    canonical_smiles = Chem.MolToSmiles(mol)
    inchi_key = Chem.MolToInchiKey(mol)  # type: ignore[no-untyped-call]

    resolved_db = _resolve_db_path(db_path)
    if resolved_db is None:
        return {
            "matched": False,
            "inchi_key": inchi_key,
            "canonical_smiles": canonical_smiles,
            "confidence": "novel",
            "db_unavailable": True,
        }

    try:
        con = sqlite3.connect(f"file:{resolved_db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            # Path 1: InChIKey-first (reaches nmrshiftdb partition).
            row = con.execute(
                "SELECT name, source FROM compounds "
                "WHERE inchi_key = ? AND inchi_key != '' LIMIT 1",
                (inchi_key,),
            ).fetchone()
            # Path 2: canonical-SMILES fallback (reaches coconut partition).
            if row is None:
                row = con.execute(
                    "SELECT name, source FROM compounds "
                    "WHERE smiles = ? AND smiles != '' LIMIT 1",
                    (canonical_smiles,),
                ).fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        # Corrupt / truncated / non-DB file (a documented failure mode for the
        # ~830 MB bundled DB): degrade gracefully — NEVER hard-fail the gate
        # (D-06). The structural identity is still firm; only the name lookup
        # is unavailable.
        return {
            "matched": False,
            "inchi_key": inchi_key,
            "canonical_smiles": canonical_smiles,
            "confidence": "novel",
            "db_unavailable": True,
            "error": f"db read failed: {exc}",
        }

    if row is None:
        return {
            "matched": False,
            "inchi_key": inchi_key,
            "canonical_smiles": canonical_smiles,
            "confidence": "novel",
        }

    name = row["name"]
    result: dict[str, object] = {
        "matched": True,
        "name": name,
        "source": row["source"],
        "inchi_key": inchi_key,
        "canonical_smiles": canonical_smiles,
    }
    # Structure known but no human/trivial name => structure-only confidence.
    # Covers COCONUT accessions (incl. dot-suffixed) AND empty/None stored names
    # (e.g. ~7.9k nmrshiftdb rows with a blank name); both must NOT be reported
    # as a confirmed trivial name.
    stripped = name.strip() if name else ""
    if not stripped or _COCONUT_ACCESSION_RE.match(stripped):
        result["confidence"] = "confirmed-structure"
        result["trivial_name_confirmed"] = False
    else:
        result["confidence"] = "confirmed"
    return result


def _normalize_name(name: str | None) -> set[str]:
    """Token-normalise a (possibly ';'-delimited) chemical name for matching.

    Drops COCONUT-accession tokens, splits ';'-delimited synonym lists,
    lowercases, replaces punctuation with spaces, splits into tokens, and
    discards generic filler tokens. Returns the union token set across all
    synonyms. Used ONLY for the tolerant ``name_match`` decision — never for
    structural identity.
    """
    if not name:
        return set()
    tokens: set[str] = set()
    for synonym in name.split(";"):
        synonym = synonym.strip()
        if not synonym or _COCONUT_ACCESSION_RE.match(synonym):
            continue
        cleaned = re.sub(r"[,()'\-–—.]", " ", synonym.lower())
        for tok in cleaned.split():
            if tok and tok not in _NAME_FILLER_TOKENS:
                tokens.add(tok)
    return tokens


def _synonym_token_sets(name: str | None) -> list[set[str]]:
    """Return one token set per ';'-delimited synonym (filler/accession dropped)."""
    if not name:
        return []
    sets: list[set[str]] = []
    for synonym in name.split(";"):
        synonym = synonym.strip()
        if not synonym or _COCONUT_ACCESSION_RE.match(synonym):
            continue
        cleaned = re.sub(r"[,()'\-–—.]", " ", synonym.lower())
        toks = {t for t in cleaned.split() if t and t not in _NAME_FILLER_TOKENS}
        if toks:
            sets.append(toks)
    return sets


def _name_match(reported_name: str | None, derived_name: str | None) -> bool:
    """Tolerant token-set comparison (NOT exact, NOT naive substring).

    True iff the reported-name token set shares its chemical token(s) with any
    ';'-split synonym of the derived name — specifically when the reported token
    set is a non-empty subset of some synonym's token set, OR the two sets are
    equal. Whole-token equality is required (so "in" does NOT match "indigo"),
    and synonym-list / punctuation / word-order differences do not false-fail.
    """
    reported = _normalize_name(reported_name)
    if not reported:
        return False
    for syn_tokens in _synonym_token_sets(derived_name):
        if not syn_tokens:
            continue
        if reported == syn_tokens or reported <= syn_tokens:
            return True
    return False


def check_identity_result(
    smiles: str,
    reported_name: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, object]:
    """Derive identity, gate the reported name, and return the verdict dict.

    Pure function: it NEVER prints and NEVER calls sys.exit (D-06). A
    name<->structure disagreement downgrades the reported name to "tentative"
    with a warning; it does not hard-fail. Callers (the ``ailsa identify`` CLI
    and the legacy ``check-identity`` script adapter) handle I/O and exit codes.

    Args:
        smiles: A solution SMILES string (semi-trusted CASE-pipeline output).
        reported_name: Trivial name asserted by the analyst (optional).
        db_path: Optional explicit DB path; auto-resolved when None.

    Returns:
        ``{mode, reported_name, derived, name_match, verdict, warning}`` where
        ``verdict`` is one of confirmed / confirmed-structure / tentative /
        novel, ``derived`` is the :func:`derive_identity` result, ``name_match``
        is True/False/None, and ``warning`` is a string or None.
    """
    derived = derive_identity(smiles, db_path=db_path)
    matched = derived.get("matched", False)

    derived_name = derived.get("name")
    if reported_name is None or not matched:
        name_match: bool | None = None
    else:
        name_match = _name_match(
            reported_name, derived_name if isinstance(derived_name, str) else None
        )

    warning: str | None = None
    if matched and (name_match is True or reported_name is None):
        # Preserve the structure-only confidence for COCONUT-accession hits.
        verdict = (
            "confirmed-structure"
            if derived.get("confidence") == "confirmed-structure"
            else "confirmed"
        )
    elif (matched and name_match is False) or (not matched and reported_name is not None):
        verdict = "tentative"
        derived_label = derived.get("name") or (
            "none (structure in DB but no trivial name stored)"
            if matched
            else "none (structure not in DB)"
        )
        warning = (
            f"WARNING: reported name '{reported_name}' does not match "
            f"tool-derived identity '{derived_label}'; name downgraded to tentative."
        )
    else:
        verdict = "novel"

    return {
        "mode": "identity",
        "reported_name": reported_name,
        "derived": derived,
        "name_match": name_match,
        "verdict": verdict,
        "warning": warning,
    }
