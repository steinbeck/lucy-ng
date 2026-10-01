#!/usr/bin/env python3
"""Regenerate the dataset table in docs/BENCHMARK.md.

The table is public, so it deliberately carries NO identity columns — no compound
name, SMILES, InChIKey or nmrXiv accession. Most of the benchmark is still to run,
and publishing the CASE -> compound mapping would end the blind evaluation for
every remaining dataset. Formula and heavy-atom count are safe: the solver is
handed the formula anyway. The runs are finished (2026-09-29), but the identities
stay out until the paper is published.

Inputs (all outside this repo, none bundled):
  --truth     TSV with columns case/case_folder + inchikey  (the answer key)
  --index     TSV with case, mf, heavy_atoms, experiments   (metadata)
  --results   one or more <label>=<dir> result trees; one table column per label,
              several dirs may share a label (a later dir wins per case)

Usage:
  python scripts/build_benchmark_table.py \
      --truth ~/…/downloaded_datasets.tsv --index ~/…/case-index.tsv \
      --results "Opus 5=/…/case-uat-results-opus5-rest" \
      --results "Opus 5=/…/case-uat-results-opus5-baseline" \
      --results "Opus 4.8=/…/case-uat-results" \
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

    # One column per model label. Several directories may share a label (the
    # Opus-5 campaign and the Opus-5 re-run are disjoint halves of one model's
    # pass over the benchmark); within a label a later directory wins. Rows are
    # no longer "best run across arms": once every dataset had been run on the
    # current model, mixing arms per row only blurred which model did what.
    labels, by_label = [], {}
    for label, root in arms:
        if not root.is_dir():
            print(f"warning: {root} is not a directory", file=sys.stderr)
            continue
        if label not in by_label:
            labels.append(label)
            by_label[label] = {}
        for cd in sorted(root.glob("CASE*")):
            if (cd / "meta.json").exists() or (cd / "analysis").is_dir():
                by_label[label][cd.name] = rank_for(grader, cd, truth.get(cd.name, ""))

    def num(c):
        return int(c[4:]) if c[4:].isdigit() else 0

    lines = []
    lines.append("| Dataset | Formula | Heavy atoms | Experiments | "
                 + " | ".join(labels) + " |")
    lines.append("|---|---|---:|---|" + "---|" * len(labels))
    tallies = {lb: {"runs": 0, "rank1": 0, "top10": 0, "found": 0, "missed": 0,
                    "noresult": 0} for lb in labels}
    for c in sorted(index, key=num):
        r = index[c]
        mf = col(r, "mf") or "—"
        ha = col(r, "heavy_atoms") or "—"
        ex = condense_experiments(col(r, "experiments"))
        cells = []
        for lb in labels:
            if c not in by_label[lb]:
                cells.append("—")
                continue
            rank = by_label[lb][c]
            t = tallies[lb]
            t["runs"] += 1
            if rank is None:
                t["noresult"] += 1
            elif rank == 0:
                t["missed"] += 1
            else:
                t["found"] += 1
                if rank <= 10:
                    t["top10"] += 1
                if rank == 1:
                    t["rank1"] += 1
            cells.append(verdict(rank))
        lines.append(f"| {c} | {mf} | {ha} | {ex} | " + " | ".join(cells) + " |")

    out = []
    if not a.fragment:
        out.append("# Benchmark dataset table\n")
    for lb in labels:
        t = tallies[lb]
        out.append(f"_{lb}: {t['runs']} datasets run · {t['rank1']} at rank 1 · "
                   f"{t['top10'] - t['rank1']} elsewhere in the top 10 · "
                   f"{t['found'] - t['top10']} found below rank 10 · "
                   f"{t['missed']} missed · {t['noresult']} no report._\n")
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
