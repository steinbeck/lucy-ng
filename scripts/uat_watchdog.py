#!/usr/bin/env python3
"""Drive the blind CASE benchmark on Sheldon without exhausting the account.

The Max20 plan has two rolling quotas -- a 5-hour window and a 7-day window --
and a full benchmark run drains both. This watchdog launches the benchmark in
small chunks, checking the live quota before each one, so the user keeps
headroom to work.

WHERE THE NUMBERS COME FROM
    Claude Code hands the statusline a JSON blob on stdin containing
    `rate_limits.five_hour.used_percentage` / `.seven_day.used_percentage`
    (plus `resets_at` as unix seconds). That is the ONLY source -- there is no
    CLI command and nothing on disk. claude-hud can mirror it to a file via
    `display.externalUsageWritePath`; this watchdog reads that file.

    Consequence, and it is deliberate: the snapshot only refreshes while a
    Claude Code session renders its statusline on this Mac. If the snapshot
    goes stale the watchdog launches nothing. No data means no burn -- the
    benchmark therefore progresses only while you are actually at the machine,
    which is also exactly when you need the headroom it is protecting.

WHAT IT WILL NOT DO
    It never kills a running chunk. Killing mid-case throws the case away and
    the quota spent on it. Chunk size is the control lever instead: small
    chunks bound how far past a threshold a launch can carry you.
"""
from __future__ import annotations

import argparse
import base64
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT = Path.home() / ".claude" / "usage-snapshot.json"

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-p", "2222",
       "chris@35.198.180.5"]

REMOTE_REPO = "/mnt/raid_drive/chris/lucy-ng"
REMOTE_DATA = "/mnt/raid_drive/chris/case-data"
REMOTE_RESULTS = "/mnt/raid_drive/chris/case-uat-results"
REMOTE_HARNESS = "tests/case-benchmark/blind_case_batch.py"

# The harness takes its paths from the environment, not from flags -- omitting
# CASE_DATA_DIR makes it resolve datasets against '.' and silently report
# skip(no-dataset) for every case, which looks like a completed chunk.
REMOTE_TRUTH = "/mnt/raid_drive/chris/nmr-dataset-assembly/downloaded_datasets.tsv"
REMOTE_ENV = {
    "CASE_DATA_DIR": REMOTE_DATA,
    "CASE_RESULTS_DIR": REMOTE_RESULTS,
    # blind_case_run.sh defaults to claude-opus-4-8, which is what the first
    # 102 runs used. Pinning Opus 5 from here on is deliberate -- note that it
    # makes the two halves of the benchmark not strictly comparable.
    "CLAUDE_MODEL": "claude-opus-5",
    # Pin the CLI for comparability, not because anything is broken: the 102
    # baseline runs used 2.1.204/205, so holding it fixed keeps a later
    # difference attributable to the model. ("Execution error" in a run log
    # is `claude -p` being killed by the 3600 s call timeout, not a fault --
    # see blind_case_run.sh.)
    "CLAUDE_BIN": "/home/chris/.local/share/claude/versions/2.1.205",
    # Hard blindness lockout: the harness physically moves this file to
    # CASE_STASH_DIR for the batch and restores it in a finally. That is why
    # this watchdog never kills a chunk -- a SIGKILL skips the finally and
    # leaves the ground truth stashed.
    "CASE_ANSWERKEY_PATHS": REMOTE_TRUTH,
}

# Defaults chosen to leave roughly half of each window for interactive work.
DEFAULT_SEVEN_DAY_MAX = 60.0
DEFAULT_FIVE_HOUR_MAX = 70.0
DEFAULT_CHUNK = 4

# A running chunk used to be untouchable: the loop logged "chunk still running"
# and ignored the gate entirely, so four cases x 3 h could keep burning quota
# long after the ceiling was crossed. Past this margin above the ceiling the
# watchdog stops the chunk instead of watching it.
ABORT_MARGIN_PCT = 5.0

# The snapshot only refreshes when an interactive session renders its
# statusline, i.e. when the user types. Overnight it goes stale and the
# watchdog used to stop entirely -- roughly half of the available time was
# lost that way. There is no programmatic alternative: the OAuth usage
# endpoint is undocumented and Cloudflare-blocked, hooks do not receive
# rate_limits (anthropics/claude-code#33820), and the Admin APIs cover the
# API platform, not the subscription windows.
#
# So extrapolate instead: assume the benchmark keeps burning quota at
# STALE_DRIFT_PCT_PER_HOUR while unobserved, and treat that estimate as if it
# were measured. Two points per hour is deliberately pessimistic -- the paired
# sample burnt about 1.5 per case at k=2, so the estimate outruns reality and
# the ceiling arrives early rather than late.
#
# Past STALE_HARD_LIMIT_S the estimate has drifted too far to mean anything,
# and the watchdog stops for real.
STALE_DRIFT_PCT_PER_HOUR = 2.0
STALE_HARD_LIMIT_S = 12 * 3600
DEFAULT_CONCURRENCY = 1
DEFAULT_POLL_SECONDS = 300
DEFAULT_MAX_SNAPSHOT_AGE = 900  # 15 min


# Datasets deliberately out of the benchmark. CASE217 is ethane -- degenerate
# and mislabelled; `CASE-UAT-LOG.md` records "remove CASE217" as a follow-up.
# It never produces a final_results.md, so without this it would be retried
# on every pass.
RETIRED = {"CASE217"}


class Halt(Exception):
    """Raised for conditions the watchdog must not paper over."""


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------- quota state

def read_snapshot(path: Path) -> dict:
    """Return the parsed usage snapshot, or raise Halt with the reason."""
    if not path.exists():
        raise Halt(
            f"no usage snapshot at {path}.\n"
            "  Set claude-hud's write path, then let one statusline render:\n"
            '    ~/.claude/plugins/claude-hud/config.json  ->\n'
            f'      {{"display": {{"externalUsageWritePath": "{path}"}}}}'
        )
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise Halt(f"cannot read {path}: {exc}") from exc

    try:
        updated = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError) as exc:
        raise Halt(f"snapshot has no usable updated_at: {exc}") from exc

    data["_age_seconds"] = (datetime.now(timezone.utc) - updated).total_seconds()
    return data


def window(snapshot: dict, name: str) -> tuple[float | None, datetime | None]:
    """Extract (used_percentage, resets_at) for 'five_hour' or 'seven_day'."""
    block = snapshot.get(name) or {}
    pct = block.get("used_percentage")
    pct = float(pct) if isinstance(pct, (int, float)) else None
    raw = block.get("resets_at")
    reset = None
    if isinstance(raw, str) and raw:
        try:
            reset = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            reset = None
    return pct, reset


_last_seven: float | None = None
_last_reset: datetime | None = None


def implausible(snapshot: dict) -> str | None:
    """Reject a usage reading that cannot be true, instead of acting on it.

    Observed 2026-08-13: the 7-day figure went 70 % -> 23 % -> 72 % across
    consecutive polls, four days before its reset. A wrong LOW reading is the
    dangerous direction -- it would wave a chunk through at a moment the
    ceiling was actually exceeded. Treat it as no reading at all.

    A drop is legitimate when the window itself turned over. Do NOT test that
    against the CURRENT snapshot's resets_at: right after a reset that field
    already names the NEXT window, so the check would never fire and every
    real reset would be rejected as noise (which is exactly what happened on
    2026-08-25, 75 % -> 1 %). Compare against the window we saw last instead:
    a changed resets_at means a new window, and a previously-announced reset
    that has since passed means the same.
    """
    global _last_seven, _last_reset
    seven, reset = window(snapshot, "seven_day")
    if seven is None:
        return None
    prev, prev_reset = _last_seven, _last_reset
    _last_seven, _last_reset = seven, reset
    if prev is None or seven >= prev:
        return None
    if prev_reset is not None and reset is not None and reset != prev_reset:
        return None                       # window rolled over -- drop is real
    if prev_reset is not None and datetime.now(timezone.utc) >= prev_reset:
        return None                       # the reset we were told about happened
    if (prev - seven) <= 2.0:
        return None                       # rounding jitter
    _last_seven, _last_reset = prev, prev_reset   # keep the trustworthy pair
    return (f"7-day window dropped {prev:.0f} % -> {seven:.0f} % with no reset "
            f"due -- snapshot not trusted")


def stale_gate(snapshot: dict, args, age: float) -> tuple[bool, str]:
    """Decide on an aged snapshot by extrapolating from its last real reading.

    The stale snapshot still carries the last genuinely measured value and the
    moment it was taken, so no extra state is needed. Deliberately NOT routed
    through implausible(): an estimate must never become the reference the next
    real reading is judged against, or a fresh low value after a reset would
    look like a drop from an invented number.
    """
    if age > STALE_HARD_LIMIT_S:
        return False, (f"snapshot is {age/3600:.1f} h old (hard limit "
                       f"{STALE_HARD_LIMIT_S/3600:.0f} h) -- estimate would be "
                       f"meaningless; open Claude Code to refresh")

    seven, seven_reset = window(snapshot, "seven_day")
    if seven is None:
        return False, f"snapshot is {age/60:.0f} min old and carries no 7-day figure"

    # A reset during the blind window wipes the debt; anything else accrues it.
    if seven_reset is not None and datetime.now(timezone.utc) >= seven_reset:
        return False, (f"snapshot is {age/60:.0f} min old and its window reset "
                       f"meanwhile -- waiting for a real reading")

    est = seven + STALE_DRIFT_PCT_PER_HOUR * (age / 3600.0)
    shown = (f"estimated 7d {est:.0f} % (last measured {seven:.0f} % "
             f"{age/60:.0f} min ago, +{STALE_DRIFT_PCT_PER_HOUR:.0f} pt/h)")
    if est >= args.seven_day_max:
        return False, f"{shown} -- at or past the {args.seven_day_max:.0f} % ceiling"
    return True, shown


def gate(snapshot: dict, args) -> tuple[bool, str]:
    """Decide whether a new chunk may start. Returns (ok, reason)."""
    age = snapshot["_age_seconds"]
    if age > args.max_snapshot_age:
        return stale_gate(snapshot, args, age)

    bogus = implausible(snapshot)
    if bogus:
        return False, bogus

    five, five_reset = window(snapshot, "five_hour")
    seven, seven_reset = window(snapshot, "seven_day")

    if five is None and seven is None:
        return False, "snapshot carries no percentages"

    if seven is not None and seven >= args.seven_day_max:
        until = f", resets {seven_reset:%d.%m. %H:%M}" if seven_reset else ""
        return False, f"7-day window at {seven:.0f} % (max {args.seven_day_max:.0f} %{until})"

    if five is not None and five >= args.five_hour_max:
        until = f", resets {five_reset:%H:%M}" if five_reset else ""
        return False, f"5-hour window at {five:.0f} % (max {args.five_hour_max:.0f} %{until})"

    parts = []
    if five is not None:
        parts.append(f"5h {five:.0f} %")
    if seven is not None:
        parts.append(f"7d {seven:.0f} %")
    return True, " · ".join(parts)


# ------------------------------------------------------------------- Sheldon

def ssh_run(remote_cmd: str, timeout: int = 60) -> str:
    proc = subprocess.run(SSH + [remote_cmd], capture_output=True,
                          text=True, timeout=timeout)
    if proc.returncode != 0:
        raise Halt(f"ssh failed ({proc.returncode}): {proc.stderr.strip()[:300]}")
    return proc.stdout


_ABORT_SCRIPT = """
set -u
# SIGTERM first: blind_case_batch stashes the ground-truth table and only puts
# it back in a finally. SIGKILL skips that and leaves the answer key hidden,
# which silently breaks the next grading run.
pkill -TERM -f '[b]lind_case_batch.py' 2>/dev/null || true
for _ in 1 2 3 4 5 6 7 8 9 10; do
  pgrep -f '[b]lind_case_batch.py' >/dev/null || break
  sleep 1
done
pkill -KILL -f '[b]lind_case_batch.py' 2>/dev/null || true
pkill -TERM -f '[t]imeout 3600' 2>/dev/null || true
sleep 3
pkill -KILL -f '[t]imeout 3600' 2>/dev/null || true
pkill -KILL -f '[c]laude -p /lucy-ng:case' 2>/dev/null || true
pkill -KILL -f '[c]laude --resume' 2>/dev/null || true

# Whatever the finally did or did not manage, reconcile against the manifest.
python3 - <<'PYEOF'
import json, os, shutil
man = os.path.expanduser("~/.case-uat-stash/manifest.json")
if not os.path.exists(man):
    print("stash clean")
else:
    for src, dst in json.load(open(man)):
        if os.path.exists(dst):
            print(f"already restored: {dst}")
        elif os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            print(f"restored: {dst}")
        else:
            print(f"LOST: neither {src} nor {dst} exists")
    os.remove(man)
PYEOF
echo "batches_left=$(pgrep -f '[b]lind_case_batch.py' | wc -l)"
echo "agents_left=$(pgrep -f '[t]imeout 3600' | wc -l)"
"""


def abort_chunk() -> str:
    """Stop a running chunk and make sure the answer key is back in place.

    Used when the quota ceiling is crossed mid-chunk. Returns the remote
    output so the caller can log what happened.
    """
    probe = base64.b64encode(_ABORT_SCRIPT.encode()).decode()
    return ssh_run(f"echo {probe} | base64 -d | bash", timeout=90)


def chunk_running() -> bool:
    """True when a benchmark chunk is still working on Sheldon.

    The bracket in `[b]lind_case_batch` keeps pgrep from matching the very
    shell that carries this pattern in its own command line -- without it the
    check reports RUNNING forever and the watchdog never launches anything.
    """
    out = ssh_run("pgrep -f '[b]lind_case_batch' >/dev/null && echo RUNNING || echo IDLE")
    return "RUNNING" in out


def contaminated_cases() -> set[str]:
    """Datasets whose own directory already holds a previous run's output.

    The harness writes to `--results`, but the CASE agent is pointed at the
    *dataset* directory. A leftover `analysis/final_results.md` there hands it
    the answer, and the run is no longer blind -- its result would be
    worthless and, worse, would look like a success. CASE7 is in this state
    from an independent validation on 2026-06-30.

    Refusing to run these is the watchdog's job; cleaning them up is not --
    that would destroy a validation record without being asked.
    """
    out = ssh_run(
        f"ls {REMOTE_DATA}/*/analysis/final_results.md 2>/dev/null || true"
    )
    names = set()
    for line in out.splitlines():
        parts = line.strip().split("/")
        if len(parts) >= 3:
            names.add(parts[-3])
    return names


# A run that exhausted its deadline and produced nothing is FINISHED, not
# pending. Keying "done" on final_results.md alone made such cases reappear in
# every chunk forever; blind_case_batch then skip(done)'d them and the chunk
# ran at reduced width. Observed 2026-08-09: three exhausted cases occupied
# three of four slots, so the last five cases ran one at a time.
#
# The original concern stays valid though -- a run that dies instantly (an
# unauthenticated `claude`, say) also writes meta.json, and retiring those
# would silently drop them. Runtime separates the two: a genuine exhausted
# attempt burns at least one deadline round, an instant death burns seconds.
EXHAUSTED_MIN_RUNTIME_S = 600

_PENDING_PROBE = """
import glob, json, os, sys
data, res, floor = sys.argv[1], sys.argv[2], int(sys.argv[3])
todo = {os.path.basename(p.rstrip("/")) for p in glob.glob(data + "/CASE*/")}
done = {p.split("/")[-3] for p in glob.glob(res + "/CASE*/analysis/final_results.md")}
for p in glob.glob(res + "/CASE*/meta.json"):
    try:
        m = json.load(open(p))
    except Exception:
        continue
    if m.get("final_results") or (m.get("runtime_s") or 0) >= floor:
        done.add(p.split("/")[-2])
print("\\n".join(sorted(todo - done)))
"""


def pending_cases(results_dir: str = REMOTE_RESULTS) -> tuple[list[str], set[str]]:
    """Return (runnable cases in natural order, skipped-as-contaminated).

    Done means the run produced a `final_results.md`, OR a `meta.json`
    recording an attempt that ran at least EXHAUSTED_MIN_RUNTIME_S before
    giving up. The second clause retires genuine failures so they stop
    consuming a chunk slot on every pass; the runtime floor keeps
    instant-death runs (which also write meta.json) pending, since those
    deserve a retry.
    """
    probe = base64.b64encode(_PENDING_PROBE.encode()).decode()
    out = ssh_run(
        f"echo {probe} | base64 -d | python3 - "
        f"{shlex.quote(REMOTE_DATA)} {shlex.quote(results_dir)} "
        f"{EXHAUSTED_MIN_RUNTIME_S}"
    )
    cases = [c.strip() for c in out.splitlines() if c.strip()]
    cases.sort(key=lambda c: (len(c), c))  # CASE104 before CASE1040

    tainted = contaminated_cases()
    blocked = {c for c in cases if c in tainted or c in RETIRED}
    return [c for c in cases if c not in blocked], blocked


def describe_blocked(blocked: set[str]) -> str:
    """Give each excluded case its own reason -- they are not the same."""
    tainted = contaminated_cases()
    parts = []
    leaky = sorted(c for c in blocked if c in tainted)
    retired = sorted(c for c in blocked if c in RETIRED and c not in tainted)
    if leaky:
        parts.append(f"{', '.join(leaky)} (own directory holds a previous "
                     f"run's final_results.md — a run there would not be blind)")
    if retired:
        parts.append(f"{', '.join(retired)} (retired: degenerate/mislabelled, "
                     f"never produces a result)")
    return "; ".join(parts)


def preflight() -> None:
    """Refuse to launch unless Sheldon can actually run a case.

    An unauthenticated `claude` fails in ~1.5 s per attempt, so a chunk
    "completes" in seconds having produced nothing but empty result
    directories. Left unchecked the watchdog would march through all 155
    remaining cases in minutes and retire every one of them.
    """
    binary = REMOTE_ENV["CLAUDE_BIN"]
    out = ssh_run(
        f"bash -lc 'command -v {shlex.quote(binary)} >/dev/null "
        f"|| echo NO_BINARY; "
        f"timeout 25 {shlex.quote(binary)} -p hi </dev/null 2>&1 | head -3'",
        timeout=60,
    )
    if "NO_BINARY" in out:
        raise Halt(f"{REMOTE_ENV['CLAUDE_BIN']} is not executable on Sheldon")
    if "Not logged in" in out or "/login" in out:
        raise Halt(
            "Claude Code on Sheldon is not authenticated "
            "('Not logged in · Please run /login').\n"
            "  Log in there interactively, then re-run this watchdog:\n"
            "    ssh -p 2222 chris@35.198.180.5   →   claude   →   /login"
        )


def launch(cases: list[str], concurrency: int, dry_run: bool,
           results_dir: str = REMOTE_RESULTS, deadline: int = 0) -> None:
    joined = " ".join(shlex.quote(c) for c in cases)
    logfile = f"/tmp/uat_chunk_{int(time.time())}.log"
    env_map = dict(REMOTE_ENV, CASE_RESULTS_DIR=results_dir)
    if deadline:
        env_map["CASE_RUN_DEADLINE_S"] = str(deadline)
    env = " ".join(f"export {k}={shlex.quote(v)};" for k, v in env_map.items())
    cmd = (
        f"cd {REMOTE_REPO} && source .venv/bin/activate && {env} "
        f"nohup python {REMOTE_HARNESS} {joined} "
        f"-k {concurrency} --mode full --results {results_dir} "
        f"> {logfile} 2>&1 &"
    )
    if dry_run:
        log(f"DRY-RUN, would launch: {cmd}")
        return
    ssh_run(f"bash -lc {shlex.quote(cmd)}")
    log(f"launched {len(cases)} case(s): {', '.join(cases)}  (log {logfile})")


# ---------------------------------------------------------------------- main

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seven-day-max", type=float, default=DEFAULT_SEVEN_DAY_MAX)
    p.add_argument("--five-hour-max", type=float, default=DEFAULT_FIVE_HOUR_MAX)
    p.add_argument("--chunk", type=int, default=DEFAULT_CHUNK,
                   help="cases per launch; smaller = finer control")
    p.add_argument("-k", "--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument("--poll", type=int, default=DEFAULT_POLL_SECONDS)
    p.add_argument("--max-snapshot-age", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE)
    p.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    p.add_argument("--limit", type=int, default=0,
                   help="stop after N chunks (0 = until cases run out)")
    p.add_argument("--cases", nargs="+", metavar="CASE",
                   help="run exactly these cases instead of everything "
                        "pending; use with --results-dir for paired re-runs")
    p.add_argument("--deadline", type=int, default=0,
                   help="CASE_RUN_DEADLINE_S per dataset (0 = harness default "
                        "9000 s). Raise it for cases that ran out of time "
                        "rather than out of ideas.")
    p.add_argument("--results-dir", default=REMOTE_RESULTS,
                   help="remote results root. Point paired re-runs somewhere "
                        "else so the 4.8 baseline stays untouched")
    p.add_argument("--dry-run", action="store_true",
                   help="report decisions, never launch anything")
    p.add_argument("--once", action="store_true",
                   help="evaluate once and exit (status check)")
    args = p.parse_args()

    log(f"thresholds: 7d < {args.seven_day_max:.0f} %  ·  5h < {args.five_hour_max:.0f} %  "
        f"·  chunk {args.chunk}  ·  k {args.concurrency}"
        + ("  ·  DRY-RUN" if args.dry_run else ""))

    launched = 0
    while True:
        try:
            snapshot = read_snapshot(args.snapshot)
            ok, reason = gate(snapshot, args)

            if chunk_running():
                # A running chunk is normally left alone -- killing one wastes
                # the work already done. But past ABORT_MARGIN_PCT above the
                # ceiling that trade flips: four cases x 3 h keep burning quota
                # the user needs elsewhere. abort_chunk() stops it the safe way
                # and puts the answer key back.
                seven, _ = window(snapshot, "seven_day")
                over = (seven is not None
                        and seven >= args.seven_day_max + ABORT_MARGIN_PCT)
                if over:
                    log(f"ABORTING running chunk — 7d at {seven:.0f} % is "
                        f"{ABORT_MARGIN_PCT:.0f} pt past the {args.seven_day_max:.0f} % "
                        f"ceiling")
                    for line in abort_chunk().splitlines():
                        if line.strip():
                            log(f"  abort: {line.strip()}")
                else:
                    log(f"chunk still running — waiting ({reason})")
            elif not ok:
                log(f"holding: {reason}")
            else:
                if args.cases:
                    # Intersect the request with what is genuinely still
                    # outstanding *in this results dir*, so re-invoking the
                    # same command resumes rather than re-running finished
                    # cases. Order follows the request, not the scan.
                    outstanding, _ = pending_cases(args.results_dir)
                    pending = [c for c in args.cases if c in set(outstanding)]
                    blocked = set()
                    if not pending:
                        log("every requested case already has a result in "
                            f"{args.results_dir} — nothing to do")
                        return 0
                else:
                    pending, blocked = pending_cases(args.results_dir)
                if blocked:
                    log(f"SKIPPING {len(blocked)}: {describe_blocked(blocked)}")
                if not pending:
                    log("no runnable cases left — benchmark complete")
                    return 0
                batch = pending[: args.chunk]
                log(f"clear ({reason}) — {len(pending)} case(s) pending")
                if not args.dry_run:
                    preflight()
                launch(batch, args.concurrency, args.dry_run,
                       args.results_dir, args.deadline)
                launched += 1
                if args.dry_run:
                    return 0
                if args.limit and launched >= args.limit:
                    log(f"chunk limit {args.limit} reached — stopping")
                    return 0

        except Halt as exc:
            log(f"HALT: {exc}")
            if args.once or args.dry_run:
                return 1
        except subprocess.TimeoutExpired:
            log("ssh timed out — will retry next poll")

        if args.once:
            return 0
        time.sleep(args.poll)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("interrupted — nothing new launched; any running chunk continues")
        sys.exit(130)
