#!/usr/bin/env python3
"""Verify CASE solutions.

Two modes:

* Default (legacy) mode: ``verify_case_solution.py <merged_smi> <formula>`` —
  verify the top-3 SMILES in a merged.smi file for an aromatic ring and exact
  molecular-formula match. Exit 0 if any candidate passes else 1. Unchanged.

* ``check-identity`` mode: derive a deterministic structural identity
  (InChIKey + canonical SMILES) from a solution SMILES, look it up in the
  bundled dereplication DB via two complementary paths (InChIKey-first for the
  nmrshiftdb partition, canonical-SMILES fallback for the COCONUT partition),
  and gate a reported trivial name against the tool-derived identity. A
  name<->structure disagreement DOWNGRADES the name to "tentative" with a
  warning; it never hard-fails (exit 0 always for this subcommand).
"""

import argparse
import json
import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

# The deterministic identity core is single-sourced in the installed package
# (D-05). This script is now a thin adapter: it imports the shared functions
# and constants rather than duplicating them. The legacy positional
# aromatic-ring/formula mode below is unchanged.
from ailsa.identity import (  # noqa: F401  (re-exported for back-compat callers)
    _COCONUT_ACCESSION_RE,
    _name_match,
    _normalize_name,
    _synonym_token_sets,
    check_identity_result,
    derive_identity,
)

_TOP_N = 3


def _parse_top3(path: Path) -> list[str]:
    """Read merged.smi and return at most the first 3 valid SMILES strings.

    Blank lines are skipped.  Invalid SMILES (``Chem.MolFromSmiles`` returns
    ``None``) are skipped rather than raising an exception.

    Args:
        path: Path to the merged.smi file (one SMILES per line, first
              whitespace-delimited field is the SMILES).

    Returns:
        List of up to 3 valid SMILES strings in file order.
    """
    valid: list[str] = []
    for raw_line in path.read_text().splitlines():
        parts = raw_line.strip().split()
        if not parts:
            continue
        smiles = parts[0]
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        valid.append(smiles)
        if len(valid) == _TOP_N:
            break
    return valid


def _check_smiles(smiles: str, formula: str) -> dict:
    """Check a single SMILES against the aromatic-ring and formula criteria.

    Args:
        smiles: A valid SMILES string (callers guarantee it parses).
        formula: Target molecular formula string (e.g. ``"C13H18O2"``).

    Returns:
        Dict with keys: smiles, aromatic_atoms, has_aromatic_ring,
        computed_formula, formula_match, passes.
    """
    mol = Chem.MolFromSmiles(smiles)
    aromatic_atoms = sum(1 for atom in mol.GetAtoms() if atom.GetIsAromatic())
    has_aromatic_ring = aromatic_atoms >= 6
    computed_formula = rdMolDescriptors.CalcMolFormula(mol)
    formula_match = computed_formula == formula
    return {
        "smiles": smiles,
        "aromatic_atoms": aromatic_atoms,
        "has_aromatic_ring": has_aromatic_ring,
        "computed_formula": computed_formula,
        "formula_match": formula_match,
        "passes": has_aromatic_ring and formula_match,
    }


def _check_identity(args: argparse.Namespace) -> None:
    """``check-identity`` subcommand: derive identity, gate the reported name.

    Thin adapter over :func:`ailsa.identity.check_identity_result` — emits the
    identity JSON block and ALWAYS exits 0 (D-06: a name<->structure
    disagreement downgrades to "tentative" + warning; it does not hard-fail).
    """
    result = check_identity_result(
        args.smiles, args.reported_name, db_path=args.db
    )
    print(json.dumps(result, indent=2))
    sys.exit(0)


def main() -> None:
    """Entry point: parse args, verify top-3 SMILES, emit JSON, exit 0/1.

    Supports two invocations: the legacy positional ``<merged_smi> <formula>``
    default mode (exit 0/1) and the ``check-identity`` subcommand (always exit
    0). The subcommand is detected by the first positional argument so the
    legacy two-positional form keeps working unchanged.
    """
    # Route to the identity subcommand when explicitly requested.
    if len(sys.argv) > 1 and sys.argv[1] == "check-identity":
        id_parser = argparse.ArgumentParser(
            prog="verify_case_solution.py check-identity",
            description=(
                "Derive a deterministic structural identity (InChIKey + "
                "canonical SMILES) from a solution SMILES and gate a reported "
                "name against the tool-derived identity."
            ),
        )
        id_parser.add_argument("--smiles", required=True, help="Solution SMILES.")
        id_parser.add_argument(
            "--reported-name",
            default=None,
            help="Trivial name asserted by the analyst (optional).",
        )
        id_parser.add_argument(
            "--db",
            default=None,
            help="Optional explicit path to the dereplication DB.",
        )
        id_args = id_parser.parse_args(sys.argv[2:])
        _check_identity(id_args)
        return  # _check_identity calls sys.exit(0); defensive return.

    parser = argparse.ArgumentParser(
        description=(
            "Verify top-3 SMILES in a merged.smi file for aromatic ring "
            "(>=6 aromatic atoms) and exact molecular formula match."
        )
    )
    parser.add_argument(
        "merged_smi",
        help="Path to merged.smi file (one SMILES per line).",
    )
    parser.add_argument(
        "formula",
        help='Exact molecular formula to match (e.g. "C13H18O2").',
    )
    args = parser.parse_args()

    smi_path = Path(args.merged_smi)
    if not smi_path.exists():
        result = {
            "pass": False,
            "error": "file not found",
            "formula": args.formula,
            "top_n_checked": _TOP_N,
            "checks": [],
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    top3_smiles = _parse_top3(smi_path)

    checks = [_check_smiles(s, args.formula) for s in top3_smiles]
    overall_pass = any(entry["passes"] for entry in checks)

    result = {
        "pass": overall_pass,
        "formula": args.formula,
        "top_n_checked": _TOP_N,
        "checks": checks,
    }
    print(json.dumps(result, indent=2))
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
