#!/bin/zsh
# Keep Sheldon busy with the remaining blind-CASE datasets.
#
# Recomputes what is still outstanding, orders it, and starts the quota
# watchdog. Safe to re-run: the watchdog intersects the request with what is
# genuinely unfinished, so nothing already done runs twice. Run it again after
# a reboot, after the watchdog dies, or whenever Sheldon has gone quiet.
#
#   ./scripts/uat_run_remaining.sh            # start
#   ./scripts/uat_run_remaining.sh --dry-run  # show what it would launch
#
# Ordering: ascending heavy-atom count. The paired Opus-5 sample showed small
# molecules finishing in 38-60 min on one attempt while large ones burn the
# full 3 h deadline and fail disproportionately, so smallest-first buys the
# most completed cases per unit of quota. Note the bias this creates if the
# run is stopped early: the finished subset is then skewed small, and its hit
# rate is NOT comparable to the 4.8 baseline's.
#
# Quota ceilings are NOT passed here on purpose: uat_watchdog.py's
# DEFAULT_SEVEN_DAY_MAX / DEFAULT_FIVE_HOUR_MAX are the single source of truth.
# This script used to hard-code --seven-day-max 80, which silently overrode a
# lowered default and would have started a chunk at 72 %.
#
# NOTE (zsh): `$CASES` does not word-split here the way it would in bash --
# `${=CASES}` is required, otherwise the watchdog receives one argument
# holding 154 names and reports "nothing to do".

set -e
cd "$(dirname "$0")/.."

REMOTE="chris@35.198.180.5"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15 -p 2222 "$REMOTE")
RESULTS=/mnt/raid_drive/chris/case-uat-results-opus5-rest
LOG=/tmp/uat_watchdog_rest.log

# Contaminated: CASE7 holds a previous run's final_results.md in its own
# dataset dir, so a run there would not be blind. Retired: CASE217 is ethane,
# degenerate/mislabelled. The watchdog blocks both anyway; excluding them here
# keeps the request list honest.
CASES=$("${SSH[@]}" 'python3 - <<PY
import csv, glob, json, os, sys
DATA = "/mnt/raid_drive/chris/case-data"
RESULT_DIRS = ["/mnt/raid_drive/chris/case-uat-results",
               "/mnt/raid_drive/chris/case-uat-results-opus5-paired",
               "/mnt/raid_drive/chris/case-uat-results-opus5-rest"]
TRUTH = "/mnt/raid_drive/chris/nmr-dataset-assembly/downloaded_datasets.tsv"
BLOCKED = {"CASE217", "CASE7"}

# The truth table carries heavy_atoms, which drives the ordering. While a
# blind batch runs, the lockout physically moves it to ~/.case-uat-stash --
# reading it from there would defeat the lockout, so fall back to numeric
# order instead. Ordering is an optimisation, not a correctness requirement.
try:
    tt = {r["case_folder"]: r for r in csv.DictReader(open(TRUTH), delimiter="\t")}
except OSError:
    tt = {}
    print("# truth table unavailable (locked out?) -- ordering by case number",
          file=sys.stderr)

todo = {os.path.basename(p.rstrip("/")) for p in glob.glob(DATA + "/CASE*/")}

done = set()
for res in RESULT_DIRS:
    done |= {p.split("/")[-3] for p in glob.glob(res + "/CASE*/analysis/final_results.md")}
    for p in glob.glob(res + "/CASE*/meta.json"):
        try:
            m = json.load(open(p))
        except Exception:
            continue
        if m.get("final_results") or (m.get("runtime_s") or 0) >= 600:
            done.add(p.split("/")[-2])

def heavy(c):
    try:
        return int(tt[c]["heavy_atoms"])
    except Exception:
        # No size known -- sort by case number so the order stays stable and
        # reproducible rather than arbitrary.
        return 999

print(" ".join(sorted(todo - done - BLOCKED, key=lambda c: (heavy(c), int(c[4:]) if c[4:].isdigit() else 0))))
PY')

if [[ -z "$CASES" ]]; then
  echo "Nothing outstanding — every dataset has a result."
  exit 0
fi

echo "outstanding: $(echo ${=CASES} | wc -w) case(s)"
echo "first (smallest): $(echo ${=CASES} | cut -d' ' -f1-6)"

if [[ "$1" == "--dry-run" ]]; then
  exec python3 -u scripts/uat_watchdog.py --cases ${=CASES} \
    --results-dir "$RESULTS" --chunk 4 -k 2 \
    --max-snapshot-age 7200 --once --dry-run
fi

if pgrep -f "uat_watchdog.py" >/dev/null; then
  echo "A watchdog is already running (PID $(pgrep -f uat_watchdog.py | head -1)). Not starting a second."
  exit 0
fi

# caffeinate -i keeps the Mac out of idle sleep. Without it the watchdog
# pauses with the machine and the usage snapshot goes stale -- observed
# 2026-08-09, two maintenance-sleep windows swallowed three poll cycles.
nohup caffeinate -i -m python3 -u scripts/uat_watchdog.py \
  --cases ${=CASES} \
  --results-dir "$RESULTS" \
  --chunk 4 -k 2 \
  --max-snapshot-age 7200 --poll 600 \
  >> "$LOG" 2>&1 &

echo "watchdog started (PID $!), logging to $LOG"
