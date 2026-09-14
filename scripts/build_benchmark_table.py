#!/usr/bin/env python3
"""Regenerate the dataset table in docs/BENCHMARK.md.

The table is public, so it deliberately carries NO identity columns — no compound
name, SMILES, InChIKey or nmrXiv accession. Most of the benchmark is still to run,
and publishing the CASE -> compound mapping would end the blind evaluation for
every remaining dataset. Formula and heavy-atom count are safe: the solver is
handed the formula anyway. Add identity columns only once the campaign is closed.

Inputs (all outside this repo, none bundled):
  --truth     TSV with columns case/case_folder + inchikey  (the answer key)
  --index     TSV with case, mf, heavy_atoms, experiments   (metadata)
  --results   one or more <label>=<dir> result trees, later ones win per case

Usage:
  python scripts/build_benchmark_table.py \
      --truth ~/…/downloaded_datasets.tsv --index ~/…/case-index.tsv \
      --results "Opus 4.8=/…/case-uat-results" \
      --results "Opus 5=/…/case-uat-results-opus5-rest" \
      --out docs/BENCHMARK.md --fragment
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRADER = HERE.parent / "tests" / "case-benchmark" / "grade_blind.py"


def load_grader():
    spec = importlib.util.spec_from_file_location("grade_blind", GRADER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def read_tsv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def col(row, *names):
    for n in names:
        for k in row:
            if k.lower() == n:
                return row[k]
    return ""


def condense_experiments(s: str) -> str:
    """'10:1d-1H;11:1d-13C;12:cosy;14:hsqc(ed)' -> '1H, 13C, COSY, HSQC(ed)'."""
    if not s or s.strip() in {"-", ""}:
        return "—"
    out, seen = [], set()
    for part in s.split(";"):
        tok = part.split(":", 1)[-1].strip()
        tok = re.sub(r"^1d-", "", tok)
        if not tok:
            continue
        pretty = {"1h": "1H", "13c": "13C"}.get(tok.lower(), tok.upper())
        if pretty not in seen:
            seen.add(pretty)
            out.append(pretty)
    return ", ".join(out) if out else "—"


def rank_for(grader, case_dir: Path, true_ik: str):
    """None = no report at all; 0 = report but truth absent from it; n = rank."""
    fr = case_dir / "analysis" / "final_results.md"
    if not fr.exists():
        return None
    if not true_ik:
        return 0
    for i, smi in enumerate(grader.extract_top_smiles(fr)[:25], 1):
        ik = grader.inchikey_from_smiles(smi)
        if ik and ik.split("-")[0] == true_ik:
            return i
    return 0


def quality(rank):
    """Higher is better, so outcomes can be compared across arms."""
    if rank is None:      # no report at all
        return 0
    if rank == 0:         # report, but the true structure is not in it
        return 1
    return 1000 - rank    # rank 1 best


def verdict(rank):
    if rank is None:
        return "no result"
    if rank == 0:
        return "missed"
    if rank == 1:
        return "**rank 1**"
    if rank <= 10:
        return f"top 10 (rank {rank})"
    return f"found (rank {rank})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--results", action="append", default=[], metavar="LABEL=DIR")
    ap.add_argument("--out", default="-")
    ap.add_argument("--fragment", action="store_true",
                    help="emit only the table + tally, for pasting into a page")
    a = ap.parse_args()

    grader = load_grader()
    truth = {}
    for r in read_tsv(a.truth):
        c = col(r, "case", "case_folder").strip()
        if c.startswith("CASE"):
            truth[c] = grader.ik_first(col(r, "inchikey", "inchi_key"))

    index = {}
    for r in read_tsv(a.index):
        c = col(r, "case", "case_folder").strip()
        if c.startswith("CASE"):
            index[c] = r

    arms = []
    for spec in a.results:
        label, _, d = spec.partition("=")
        arms.append((label, Path(d)))

    best, per_arm = {}, {}
    for label, root in arms:
        if not root.is_dir():
            print(f"warning: {root} is not a directory", file=sys.stderr)
            continue
        for cd in sorted(root.glob("CASE*")):
            r = rank_for(grader, cd, truth.get(cd.name, ""))
            per_arm.setdefault(cd.name, {})[label] = r
            prev = best.get(cd.name)
            # Keep the BEST outcome reached so far, not the newest: rank 1 beats
            # rank 5 beats "missed" beats "no report". Ties go to the later arm,
            # which is the more recent evidence.
            if prev is None or quality(r) >= quality(prev[1]):
                best[cd.name] = (label, r)

    def num(c):
        return int(c[4:]) if c[4:].isdigit() else 0

    lines = []
    lines.append("| Dataset | Formula | Heavy atoms | Experiments | Best run | Result |")
    lines.append("|---|---|---:|---|---|---|")
    tally = {"rank1": 0, "top10": 0, "found": 0, "missed": 0, "noresult": 0, "pending": 0}
    for c in sorted(index, key=num):
        r = index[c]
        mf = col(r, "mf") or "—"
        ha = col(r, "heavy_atoms") or "—"
        ex = condense_experiments(col(r, "experiments"))
        if c in best:
            label, rank = best[c]
            v = verdict(rank)
            if rank is None:
                tally["noresult"] += 1
            elif rank == 0:
                tally["missed"] += 1
            elif rank == 1:
                tally["rank1"] += 1
                tally["top10"] += 1
                tally["found"] += 1
            elif rank <= 10:
                tally["top10"] += 1
                tally["found"] += 1
            else:
                tally["found"] += 1
        else:
            label, v = "—", "_pending_"
            tally["pending"] += 1
        lines.append(f"| {c} | {mf} | {ha} | {ex} | {label} | {v} |")

    graded = tally["found"] + tally["missed"]
    out = []
    if not a.fragment:
        out.append("# Benchmark dataset table\n")
    out.append(f"_{len(index)} datasets · {len(best)} with at least one run · "
               f"{tally['pending']} not yet attempted._\n")
    if graded:
        # Deliberately a count, not a rate. Rows come from different arms, so a
        # single percentage over this column would silently blend Opus 4.8 misses
        # with Opus 5 hits. Per-arm rates belong in the page prose, where the
        # sample each one is measured on can be stated.
        out.append(f"_Row counts: {tally['rank1']} at rank 1 · "
                   f"{tally['top10'] - tally['rank1']} elsewhere in the top 10 · "
                   f"{tally['found'] - tally['top10']} found below rank 10 · "
                   f"{tally['missed']} missed · {tally['noresult']} no report. "
                   f"Each row shows the best run so far and which arm produced it; "
                   f"do not read a rate off this column._\n")
    out += lines
    text = "\n".join(out) + "\n"
    if a.out == "-":
        sys.stdout.write(text)
    else:
        Path(a.out).write_text(text)
        print(f"wrote {a.out}: {len(index)} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
