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
DEFAULT_SEVEN_DAY_MAX = 55.0
DEFAULT_FIVE_HOUR_MAX = 70.0
DEFAULT_CHUNK = 4
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


def gate(snapshot: dict, args) -> tuple[bool, str]:
    """Decide whether a new chunk may start. Returns (ok, reason)."""
    age = snapshot["_age_seconds"]
    if age > args.max_snapshot_age:
        return False, (f"snapshot is {age/60:.0f} min old (limit "
                       f"{args.max_snapshot_age/60:.0f}) -- is Claude Code open?")

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
           results_dir: str = REMOTE_RESULTS) -> None:
    joined = " ".join(shlex.quote(c) for c in cases)
    logfile = f"/tmp/uat_chunk_{int(time.time())}.log"
    env_map = dict(REMOTE_ENV, CASE_RESULTS_DIR=results_dir)
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
                launch(batch, args.concurrency, args.dry_run, args.results_dir)
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
