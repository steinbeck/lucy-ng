"""Blind CASE UAT batch driver.

Runs lucy-ng:case blind on many sanitised datasets via isolated headless
`claude` processes (blind_case_run.sh), sequentially bounded by a concurrency
limit. Resumable (skips runs that already have meta.json).

Optional HARD blindness lockout: if CASE_ANSWERKEY_PATHS is set (colon-separated
files/dirs holding ground truth / compound identities), they are physically moved
to a stash for the whole batch and restored in a finally — so a blind run cannot
read them even accidentally. Grading (grade_blind.py) is run separately AFTER the
batch, once the answer keys are restored.

Usage:
  python blind_case_batch.py --all                       # every CASE* in CASE_DATA_DIR
  python blind_case_batch.py CASE1 CASE4 ...              # explicit list
  python blind_case_batch.py --all -k 3 --mode full
Env:
  CASE_DATA_DIR        (required) dir containing the CASE<name> dataset folders
  CASE_RESULTS_DIR     results root (default: ./results next to this script)
  CASE_ANSWERKEY_PATHS optional ':'-separated paths to stash during the batch
  CASE_STASH_DIR       where to stash them (default: a temp dir)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_SH = HERE / "blind_case_run.sh"
DATA_DIR = Path(os.environ.get("CASE_DATA_DIR", ""))
RESULTS_DEFAULT = os.environ.get("CASE_RESULTS_DIR", str(HERE / "results"))
STASH = Path(os.environ.get("CASE_STASH_DIR",
             os.path.join(os.path.expanduser("~"), ".case-uat-stash")))
ANSWERKEY_PATHS = [p for p in os.environ.get("CASE_ANSWERKEY_PATHS", "").split(":") if p]


def has_dataset(cdir):
    return any((cdir / f).exists()
               for f in ("molecular-formula.txt", "molecularformula.txt"))


def lockout():
    if not ANSWERKEY_PATHS:
        print("[lockout] CASE_ANSWERKEY_PATHS unset -> no lockout", flush=True)
        return
    STASH.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, p in enumerate(dict.fromkeys(ANSWERKEY_PATHS)):
        p = Path(p)
        if p.exists():
            dest = STASH / f"{i:03d}__{p.name}"
            shutil.move(str(p), str(dest))
            manifest.append((str(dest), str(p)))
    (STASH / "manifest.json").write_text(json.dumps(manifest))
    print(f"[lockout] stashed {len(manifest)} answer-key path(s) -> {STASH}", flush=True)


def restore():
    m = STASH / "manifest.json"
    if not m.exists():
        return
    for dest, orig in json.loads(m.read_text()):
        if Path(dest).exists():
            Path(orig).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(dest, orig)
    m.unlink()
    print("[restore] answer-key path(s) restored", flush=True)


def run_one(case_name, results_root, mode):
    rdir = results_root / case_name
    if (rdir / "meta.json").exists():
        return case_name, "skip(done)"
    cdir = DATA_DIR / case_name
    if not has_dataset(cdir):
        return case_name, "skip(no-dataset)"
    subprocess.run(["bash", str(RUN_SH), str(cdir), str(rdir), mode],
                   capture_output=True, text=True)
    try:
        m = json.loads((rdir / "meta.json").read_text())
        return case_name, f"attempts={m.get('attempts')} fr={m.get('final_results')} {m.get('runtime_s')}s"
    except Exception:
        return case_name, "error(no-meta)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("-k", "--concurrency", type=int, default=3)
    ap.add_argument("--mode", default="full", choices=["full", "smoke"])
    ap.add_argument("--results", default=RESULTS_DEFAULT)
    args = ap.parse_args()

    if not DATA_DIR or not DATA_DIR.is_dir():
        sys.exit("CASE_DATA_DIR is unset or not a directory")
    results_root = Path(args.results)
    results_root.mkdir(parents=True, exist_ok=True)
    if args.all:
        cases = sorted(d.name for d in DATA_DIR.glob("CASE*")
                       if d.is_dir() and has_dataset(d))
    else:
        cases = args.cases
    if not cases:
        sys.exit("no cases (use --all or list CASE names)")

    print(f"Blind CASE batch: {len(cases)} datasets, k={args.concurrency}, "
          f"mode={args.mode}, data={DATA_DIR}", flush=True)
    lockout()
    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(run_one, c, results_root, args.mode): c for c in cases}
            for i, fut in enumerate(as_completed(futs), 1):
                name, res = fut.result()
                print(f"[{i}/{len(cases)}] {name}: {res}", flush=True)
    finally:
        restore()

    rows = ["case\tattempts\tfinal_results\truntime_s\ttop_smiles"]
    for d in sorted(results_root.glob("CASE*")):
        try:
            m = json.loads((d / "meta.json").read_text())
            rows.append(f"{m.get('case')}\t{m.get('attempts')}\t{m.get('final_results')}"
                        f"\t{m.get('runtime_s')}\t{m.get('top_smiles', '')}")
        except Exception:
            continue
    (results_root / "summary.tsv").write_text("\n".join(rows) + "\n")
    print(f"\nWrote {results_root}/summary.tsv", flush=True)


if __name__ == "__main__":
    main()
