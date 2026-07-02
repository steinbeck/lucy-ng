"""Grade blind CASE UAT results against a ground-truth table.

Run AFTER a blind batch. For each results/<CASE>/analysis/final_results.md, the
run's top-ranked structure is extracted, its InChIKey computed with RDKit, and
its first block compared to the ground-truth InChIKey.

Ground truth is supplied EXTERNALLY (never committed): a TSV given by
$CASE_GROUNDTRUTH with a header containing at least a case column
(`case` or `case_folder`) and an `inchikey` column; an optional `name` column is
shown in the report. This keeps compound identities out of the repo.

Usage:
  CASE_GROUNDTRUTH=/path/truth.tsv python grade_blind.py [--results DIR]
Deps: rdkit (pip install rdkit)  ->  used for canonicalisation + InChIKey.
Output: scorecard on stdout + <results>/scorecard.tsv
"""
import argparse
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def ik_first(ik):
    return (ik or "").split("-")[0]


def inchikey_from_smiles(smi):
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        m = Chem.MolFromSmiles(smi)
        return Chem.MolToInchiKey(m) if m else None
    except Exception:
        return None


def _valid_smiles(tok):
    tok = tok.strip().strip("`*").strip().rstrip(".,;")
    if not tok or " " in tok or len(tok) < 4:
        return None
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        m = Chem.MolFromSmiles(tok)
        if m is None or m.GetNumHeavyAtoms() < 3:
            return None
        return Chem.MolToSmiles(m)
    except Exception:
        return None


def extract_top_smiles(final_results_md):
    """Ordered RDKit-validated candidate SMILES (top first). Robust to markdown
    tables, backtick-quoted SMILES and 'Canonical SMILES:' lines; prose dropped."""
    text = Path(final_results_md).read_text(errors="replace")
    ranked, other = [], []
    for line in text.splitlines():
        low = line.lower()
        near_top = ("smiles" in low or "rank 1" in low or "top" in low
                    or re.match(r"\s*\|?\s*1\s*\|", line))
        toks = re.findall(r"`([^`]+)`", line)
        toks += [c.strip() for c in line.split("|")]
        toks += line.split()
        for t in toks:
            s = _valid_smiles(t)
            if s:
                (ranked if near_top else other).append(s)
    seen, out = set(), []
    for c in ranked + other:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def load_truth():
    path = os.environ.get("CASE_GROUNDTRUTH", "")
    truth = {}
    if not path or not Path(path).exists():
        return truth
    lines = Path(path).read_text().splitlines()
    if not lines:
        return truth
    hdr = [h.strip().lower() for h in lines[0].split("\t")]

    def col(*names):
        for n in names:
            if n in hdr:
                return hdr.index(n)
        return None
    ci, ii, ni = col("case", "case_folder"), col("inchikey", "inchi_key"), col("name")
    if ci is None or ii is None:
        return truth
    for ln in lines[1:]:
        p = ln.split("\t")
        if len(p) > max(ci, ii) and p[ci].startswith("CASE"):
            truth[p[ci]] = {"inchikey": p[ii],
                            "name": p[ni] if ni is not None and len(p) > ni else ""}
    return truth


def grade_one(case_dir, truth):
    name = case_dir.name
    t = truth.get(name, {})
    true_ik = ik_first(t.get("inchikey"))
    rec = {"case": name, "true_name": t.get("name", ""), "true_ik": true_ik,
           "verdict": "NO_RESULT", "matched_rank": "", "top_ik": ""}
    fr = case_dir / "analysis" / "final_results.md"
    if not fr.exists():
        return rec
    cands = extract_top_smiles(fr)
    top_ik, rank = "", None
    for i, smi in enumerate(cands[:25], 1):
        ik = inchikey_from_smiles(smi)
        if not ik:
            continue
        if not top_ik:
            top_ik = ik
        if true_ik and ik.split("-")[0] == true_ik:
            rank = i
            break
    rec["top_ik"] = top_ik.split("-")[0] if top_ik else ""
    if not true_ik:
        rec["verdict"] = "UNGRADED(no-truth)"
    elif rank == 1:
        rec["verdict"] = "SOLVED_TOP1"
    elif rank:
        rec["verdict"] = f"CORRECT_RANK_{rank}"
    else:
        rec["verdict"] = "WRONG"
    rec["matched_rank"] = rank or ""
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.environ.get("CASE_RESULTS_DIR", str(HERE / "results")))
    args = ap.parse_args()
    results = Path(args.results)
    truth = load_truth()
    if not truth:
        print("WARNING: no ground truth (set CASE_GROUNDTRUTH to a TSV) — verdicts will be UNGRADED")
    recs = [grade_one(d, truth) for d in sorted(results.glob("CASE*"))
            if (d / "meta.json").exists()]
    from collections import Counter
    tally = Counter(r["verdict"].split("_RANK")[0] for r in recs)
    print(f"Graded {len(recs)} runs: {dict(tally)}\n")
    print(f"{'CASE':10} {'verdict':18} {'true_name':28} true_ik / top_ik")
    for r in sorted(recs, key=lambda x: x["case"]):
        print(f"{r['case']:10} {r['verdict']:18} {r['true_name'][:28]:28} "
              f"{r['true_ik']} / {r['top_ik']}")
    hdr = "case\tverdict\tmatched_rank\ttrue_name\ttrue_ik\ttop_ik"
    out = [hdr] + ["\t".join(str(r[k]) for k in
                   ["case", "verdict", "matched_rank", "true_name", "true_ik", "top_ik"])
                   for r in recs]
    (results / "scorecard.tsv").write_text("\n".join(out) + "\n")
    print(f"\nWrote {results}/scorecard.tsv")


if __name__ == "__main__":
    main()
