#!/bin/zsh
# Re-run the 103 baseline datasets on Opus 5.
#
# Why this exists next to uat_run_remaining.sh: that script launches whatever is
# still *outstanding*, and these 103 are not outstanding -- they all have a
# result from the Opus-4.8 arm. This one deliberately re-runs them into a NEW
# results directory so the whole 258-dataset benchmark ends up on one model and
# the 4.8/5 change stops being a confound. The 4.8 arm at
# /mnt/raid_drive/chris/case-uat-results is the historical comparison and is
# NEVER written to -- read only, to derive the case list.
#
#   ./scripts/uat_run_baseline_opus5.sh              # start, detached
#   ./scripts/uat_run_baseline_opus5.sh --dry-run    # show what it would launch
#   ./scripts/uat_run_baseline_opus5.sh --foreground # BECOME the watchdog (launchd)
#
# Safe to re-run: pending_cases() intersects the request with what is genuinely
# unfinished *in the new directory*, so nothing runs twice.
#
# Ordering is ascending heavy-atom count, as in uat_run_remaining.sh: small
# molecules finish in one attempt, large ones burn the deadline, so
# smallest-first buys the most completed cases per unit of quota. The bias that
# creates if the run is stopped early -- a finished subset skewed small -- is
# the same one documented there, and matters MORE here because the comparison
# target is the 4.8 arm over the same 103. Compare only case-by-case, never
# hit-rate-to-hit-rate on a partial run.
#
# zsh: `${=CASES}` is required for word splitting; a bare "$CASES" hands the
# watchdog one argument holding 100+ names and it reports "nothing to do".

set -e
cd "$(dirname "$0")/.."

REMOTE="chris@35.198.180.5"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15 -p 2222 "$REMOTE")
RESULTS=/mnt/raid_drive/chris/case-uat-results-opus5-baseline
# NOT /tmp: macOS clears it on reboot, and on 2026-09-18 that took the log with
# it — so why the run had stopped two days earlier could no longer be shown.
LOG="$HOME/Library/Logs/lucyng-uat-baseline.log"

CASES=$("${SSH[@]}" 'python3 - <<PY
import csv, glob, json, os, sys
BASELINE = "/mnt/raid_drive/chris/case-uat-results"          # read-only: the 4.8 arm
NEW      = "/mnt/raid_drive/chris/case-uat-results-opus5-baseline"
DATA     = "/mnt/raid_drive/chris/case-data"
TRUTH    = "/mnt/raid_drive/chris/nmr-dataset-assembly/downloaded_datasets.tsv"
# CASE217 is ethane -- degenerate/mislabelled, retired from the benchmark.
BLOCKED = {"CASE217"}

want = {os.path.basename(p.rstrip("/")) for p in glob.glob(BASELINE + "/CASE*/")}
have = {os.path.basename(os.path.dirname(p)) for p in glob.glob(DATA + "/CASE*/")}
want &= have                                                  # dataset must still exist

done = {p.split("/")[-3] for p in glob.glob(NEW + "/CASE*/analysis/final_results.md")}
for p in glob.glob(NEW + "/CASE*/meta.json"):
    try:
        m = json.load(open(p))
    except Exception:
        continue
    if m.get("final_results") or (m.get("runtime_s") or 0) >= 600:
        done.add(p.split("/")[-2])

try:
    tt = {r["case_folder"]: r for r in csv.DictReader(open(TRUTH), delimiter="\t")}
except OSError:
    tt = {}
    print("# truth table unavailable (stashed by a running batch?) -- ordering by case number",
          file=sys.stderr)

def heavy(c):
    try:
        return int(tt[c]["heavy_atoms"])
    except Exception:
        return 999

print(" ".join(sorted(want - done - BLOCKED,
                      key=lambda c: (heavy(c), int(c[4:]) if c[4:].isdigit() else 0))))
PY')

if [[ -z "$CASES" ]]; then
  echo "Nothing to do — every baseline dataset already has an Opus-5 result."
  exit 0
fi

echo "results dir:  $RESULTS"
echo "to run:       $(echo ${=CASES} | wc -w) case(s)"
echo "first (smallest): $(echo ${=CASES} | cut -d' ' -f1-8)"

if [[ "$1" == "--dry-run" ]]; then
  exec python3 -u scripts/uat_watchdog.py --cases ${=CASES} \
    --results-dir "$RESULTS" --chunk 4 -k 2 \
    --max-snapshot-age 7200 --once --dry-run
fi

if pgrep -f "uat_watch""dog\.py" >/dev/null; then
  echo "A watchdog is already running (PID $(pgrep -f 'uat_watch''dog\.py' | head -1)). Not starting a second."
  exit 0
fi

# caffeinate -i keeps this Mac out of idle sleep; without it the watchdog pauses
# with the machine and the usage snapshot goes stale.
WATCHDOG=(caffeinate -i -m python3 -u scripts/uat_watchdog.py
          --cases ${=CASES}
          --results-dir "$RESULTS"
          --chunk 4 -k 2
          --max-snapshot-age 7200 --poll 600)

if [[ "$1" == "--foreground" ]]; then
  # Under launchd the watchdog must BE the job, not a child of it. Backgrounding
  # it and exiting looks like it works -- the script prints a PID and returns 0 --
  # but launchd treats the job as finished and reaps the process group, so the
  # watchdog is dead seconds later. Demonstrated 2026-09-22 with a throwaway agent
  # using the same shape: the child was gone before the next poll. It cost the
  # night of 2026-09-21: the machine rebooted, the agent started correctly, logged
  # "watchdog started (PID 1540)", and that watchdog never wrote a single line.
  echo "$(date '+%H:%M:%S') becoming the watchdog in the foreground (launchd)" >> "$LOG"
  exec "${WATCHDOG[@]}" >> "$LOG" 2>&1
fi

nohup "${WATCHDOG[@]}" >> "$LOG" 2>&1 &
echo "watchdog started (PID $!), logging to $LOG"
