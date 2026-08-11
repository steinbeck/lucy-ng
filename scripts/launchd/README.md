# Keeping the blind-CASE benchmark alive across reboots

`uat_run_remaining.sh` starts the quota watchdog, but a watchdog only lives as
long as the machine does. On 2026-08-11 the Mac rebooted at 11:21; the watchdog
died with it, `/tmp` was wiped along with its log, and Sheldon sat idle for two
hours before anyone noticed.

The LaunchAgent closes that gap.

## Install

```bash
cp scripts/launchd/de.doktor-steinbeck.lucyng-uat-watchdog.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/de.doktor-steinbeck.lucyng-uat-watchdog.plist
```

## What it does

- **RunAtLoad** — starts the watchdog at every login, so a reboot costs minutes
  instead of hours.
- **KeepAlive / SuccessfulExit=false** — relaunches only after a crash. A clean
  exit means either "every dataset has a result" or "another watchdog already
  owns this"; relaunching those would spin forever.
- Logs to `~/Library/Logs/lucyng-uat-watchdog.log`, which survives reboots —
  unlike `/tmp/uat_watchdog_rest.log`.

Safe to leave loaded permanently: the script recomputes what is outstanding on
every invocation, refuses to start a second watchdog, and exits 0 once the
benchmark is complete.

## Check / remove

```bash
launchctl list | grep lucyng                # loaded?
tail -f ~/Library/Logs/lucyng-uat-watchdog.log
launchctl unload -w ~/Library/LaunchAgents/de.doktor-steinbeck.lucyng-uat-watchdog.plist
```

Note the agent starts the watchdog but does not keep the Mac awake by itself —
the script wraps it in `caffeinate -i`, which only prevents *idle* sleep. A
closed lid or a manual shutdown still stops everything until the next login.
