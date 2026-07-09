---
name: lucy-ng:case
description: "Full CASE workflow — autonomous NMR structure elucidation. Use when: unknown compound, determine structure, identify molecule, what is this compound, structure determination from NMR"
argument-hint: "<compound_path> <formula>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Task
  - TeamCreate
  - TeamDelete
  - TaskCreate
  - TaskList
  - TaskUpdate
  - SendMessage
---

<objective>
Orchestrate the full Computer-Assisted Structure Elucidation (CASE) workflow by spawning a 4-agent specialist team (nmr-chemist, lsd-engineer, solution-analyst, devils-advocate), monitoring progress through CASE-PROGRESS.md (which this orchestrator writes as sole author) and TaskList, detecting unproductive loop patterns, diagnosing root causes, intervening with advisory constraints via SendMessage, and escalating to the user after 10 failed intervention cycles per pattern.

This orchestrator does NOT perform CASE work itself—it delegates to a specialist team and handles supervision as team lead.

**ABSOLUTE PROHIBITION:** This orchestrator NEVER attempts dereplication. Dereplication is a completely separate workflow. CASE starts from scratch with NMR spectra only.
</objective>

<process>

<step name="parse_arguments">
Extract compound path and molecular formula from user input.

**Arguments:** `<compound_path> <formula>` — both optional if inferable.

**Resolution logic:**

1. **If both provided:** Use them directly.

2. **If compound_path missing:** Check if cwd looks like a Bruker compound directory:
   ```bash
   ls -d [0-9]*/acqus 2>/dev/null | head -1
   ```
   If numbered subdirectories with `acqus` files exist, use `.` (current directory) as compound_path.

3. **If formula missing:** FIRST look for it on disk in `{compound_path}`, and only ask the
   user if nothing usable is found. Many compound directories ship the formula in a small
   sidecar text file — read it instead of prompting. Search generically (do NOT hard-code one
   filename); check, in order, common formula sidecars:
   ```bash
   # look for a formula sidecar in the compound dir (case-insensitive, several conventions)
   for f in "$CP"/molecular-formula.txt "$CP"/molecular_formula.txt "$CP"/formula.txt \
            "$CP"/molform.txt "$CP"/*.formula; do
     [ -f "$f" ] || continue
     cand=$(tr -d ' \t\r\n' < "$f")
     # accept only a plausible molecular formula token (element symbols + counts)
     if printf '%s' "$cand" | grep -Eq '^([A-Z][a-z]?[0-9]*)+$'; then
       echo "FORMULA_FROM_FILE=$cand ($f)"; break
     fi
   done
   ```
   (`$CP` = `{compound_path}`.) If a plausible formula is found, use it and tell the user which
   file it came from (e.g. "Using formula C13H18O2 from molecular-formula.txt"). Only if no
   sidecar yields a valid formula, ask the user — just the formula, nothing else:
   ```
   What is the molecular formula? (e.g., C9H10O2)
   ```

4. **If neither provided and cwd is not a compound directory:** Show brief usage:
   ```
   cd into your compound directory, then: /lucy-ng:case <formula>
   ```

**Smoke test mode:** If the user's invocation includes `--smoke-test` or `smoke test`:
- Set SMOKE_TEST = true
- Default compound_path to `data/example_compound` if not provided
- Default formula to `C9H10O2` if not provided
- Print header:
  ```
  ========================================
  SMOKE TEST — CASE Pipeline Validation
  ========================================
  Compound: {compound_path}
  Formula: {formula}
  Mode: 1-iteration validation (not full CASE)
  ```
</step>

<step name="validate_prerequisites">
Check environment readiness. Run via Bash — STOP on any failure, do NOT spawn team:

0. `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` — must be "1". Fix: `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
1. `lucy --version` — must succeed. Fix: `pip install lucy-ng`
2. `lucy lsd check` — LSD and outlsd must be available. Fix: download from http://eos.univ-reims.fr/LSD/ and add bin/ to PATH
3. `lucy predict c13 "CCO" --format json 2>/dev/null | head -1` — must succeed. Fix: `lucy database download`
4. `ls <compound_path>` — directory must exist.
</step>

<step name="spawn_case_team">
Spawn the 4-agent CASE specialist team via TeamCreate and Task(team_name).

**CRITICAL:** The orchestrator skill IS the team lead (coordinator). Do NOT spawn a coordinator agent -- the skill itself manages the team, creates tasks, delivers advisories, and handles lifecycle.

**COORDINATION PROTOCOL — PUSH, NEVER PULL (critical — prevents the stall):**
Background teammates go idle between turns and do **NOT** poll the TaskList on their own. A `TaskCreate` by itself will **never** wake an idle agent — the run simply stalls until a message arrives. Therefore the coordinator drives everything by message:
- After creating/assigning ANY task, the coordinator MUST immediately `SendMessage` the specific assignee an explicit `[BEGIN] <task>` directive. Do this right after each `TaskCreate`, and again immediately after the prerequisite agent reports.
- `TaskCreate` / `TaskList` / `TaskUpdate` are a STATUS LEDGER for visibility only — never a work queue that agents poll.
- Agents act ONLY on a received `SendMessage`. They must never "wait for", "monitor", or "claim from" the TaskList.
- A teammate's reply arrives as a conversation turn and wakes the coordinator, which then immediately pushes the next `[BEGIN]` directive. This message ping-pong is the ONLY thing that keeps the workflow moving — there is no autonomous polling. If you ever find yourself "waiting" after a `TaskCreate` without having sent a `[BEGIN]`, that is the bug: push the directive.

**⚠ EXECUTION-MODE CAVEAT — headless / non-interactive (`claude -p`, batch/UAT harness):**
The message ping-pong above assumes a teammate's reply arrives as a conversation turn that
WAKES you. **That wake-up only happens in an interactive session.** When you run
non-interactively/headless there is NO event loop to re-enter a finished turn — if you send a
`[BEGIN]` and then END YOUR TURN saying "I'll wait for [ITERATION-COMPLETE]", the process
simply exits mid-workflow. **This is the `NO_RESULT` failure mode.** Detect this mode from your
environment/system context (no interactive user; invoked via `claude -p` / a harness). In it:
- **Never end a turn expecting to be woken. "Background-and-wait" is forbidden.**
- Drive every stage **INLINE within one continuous turn**: after each `[BEGIN]`, actively POLL
  for completion in a loop — read `TaskList()` status AND check the expected filesystem
  artefacts (`analysis/iteration_NN/solncounter` or `*.sol`, `analysis/final_results.md`) — then
  proceed to the next stage yourself, without waiting for a wake-up.
- Treat teammate replies as best-effort: if a `[*-COMPLETE]` has not arrived but the artefact is
  on disk, read the result from the filesystem (as in the Stall recovery step) and continue.
This keeps the identical push logic; it only changes how you await each reply so headless runs
do not stall. In an interactive session, the normal message-wake path applies unchanged.

**Step 1: Initialize team namespace** ({compound_name} = last path component, e.g., "MyCompound")

```
TeamCreate(team_name="case-{compound_name}", description="CASE workflow for {compound_path} -- formula {formula}")
```

**Step 2: Create initial shared tasks**

```
TaskCreate(
  subject="peak-picking",
  description="Pick 13C, HSQC, HMBC peaks for {compound_path} with formula {formula}.
               Run statistical detection (hybridisation, neighbours, hhb, grouping).
               Write analysis/ directory structure.
               Send structured [SETUP-COMPLETE] message to coordinator via SendMessage with all peak assignments, detection results, and quality assessment.",
  activeForm="Picking NMR peaks"
)

TaskCreate(
  subject="lsd-iteration-01",
  description="Build initial LSD file from peak assignments. Use HSQC for MULT definitions,
               add first HMBC batch (3-5 high-confidence correlations). Run LSD from
               analysis/iteration_01/ directory. Send [ITERATION-COMPLETE] message to coordinator after LSD run.
               solutions.smi is produced automatically by lucy lsd run (no manual outlsd step).",
  activeForm="Running LSD iteration 1"
)
```

**Step 3: Spawn 4 specialist teammates**

```
Task(
  name="nmr-chemist",
  team_name="case-{compound_name}",
  subagent_type="lucy-nmr-chemist",
  model="claude-opus-4-8",
  prompt="You are the NMR chemist for CASE of {formula} at {compound_path}.
          Begin ONLY when the coordinator sends you a [BEGIN] peak-picking directive — do NOT poll or wait on the TaskList (idle agents are not woken by tasks, only by messages).
          Execute peak picking and statistical detection using lucy CLI.
          Send [SETUP-COMPLETE] message to coordinator via SendMessage with all peak assignments, detection results, and quality assessment.
          Mark the task completed (TaskUpdate, for the status ledger) and then wait for the coordinator's next [BEGIN] directive — never poll the TaskList for more work."
)

Task(
  name="lsd-engineer",
  team_name="case-{compound_name}",
  subagent_type="lucy-lsd-engineer",
  model="claude-opus-4-8",
  prompt="You are the LSD engineer for CASE of {formula} at {compound_path}.
          Act ONLY on the coordinator's [BEGIN] lsd-iteration directives sent to you via SendMessage — do NOT poll or wait on the TaskList (idle agents are woken by messages, not by tasks).
          On each [BEGIN] lsd-iteration-NN directive: build the LSD file in analysis/iteration_NN/, run the LSD solver.
          Send [ITERATION-COMPLETE] message to coordinator via SendMessage after EVERY iteration.
          CRITICAL: Read previous LSD file, never reconstruct from memory.
          Follow incremental HMBC strategy: 3-5 correlations per iteration.
          After reporting, wait for the coordinator's next [BEGIN] directive — never poll the TaskList. You will receive a shutdown_request when CASE is complete."
)

Task(
  name="solution-analyst",
  team_name="case-{compound_name}",
  subagent_type="lucy-solution-analyst",
  model="claude-opus-4-8",
  prompt="You are the solution analyst for CASE of {formula} at {compound_path}.
          Act ONLY when the coordinator sends you a [BEGIN] ranking directive via SendMessage — do NOT poll or monitor the TaskList (idle agents are woken by messages, not by tasks).
          The [BEGIN] ranking directive embeds the full experimental 13C shift list and the solutions.smi path.
          Assess chemical plausibility of top candidates.
          Write analysis/final_results.md with ranked structures.
          Send [RANKING-COMPLETE] message to coordinator via SendMessage with ranking summary."
)

Task(
  name="devils-advocate",
  team_name="case-{compound_name}",
  subagent_type="lucy-devils-advocate",
  model="claude-opus-4-8",
  prompt="You are the devils advocate for CASE of {formula} at {compound_path}.
          Act ONLY on requests received via SendMessage (from lsd-engineer or the coordinator) — do NOT poll the TaskList.
          On a PRE-SOLVER validation request:
          1. Diff current LSD file against previous iteration
          2. Check for dropped constraints (ring exclusion DEFF F/FEXP, COSY equivalence pairs, grouped notation)
          3. Verify sp2 count is even, H budget matches formula
          4. Send [VALIDATION-PASSED] or [VALIDATION-BLOCKED] to coordinator via SendMessage.
          On a POST-SOLUTION [BEGIN] G-IDENT request (after analysis/final_results.md exists): run ONLY the G-IDENT gate — read the reported trivial name + top SMILES, reason INDEPENDENTLY about whether the name matches the structure (do NOT call lucy identify), apply the CASE4/CASE5 triggers, and reply [G-IDENT-PASSED] or [G-IDENT-FLAGGED] with a one-line rationale.
          Report constraint persistence status after every validation."
)
```

**Step 4: Mandatory model disclosure (observability — catches silent model fallback).**

Every teammate MUST disclose its actual runtime model. Append this line VERBATIM to each of the four `prompt=` strings above (it is intentionally identical for all four):

```
FIRST LINE of your very first SendMessage to the coordinator MUST be exactly: [MODEL] <your exact runtime model id from your environment/system context, e.g. claude-opus-4-8> — copy the real id verbatim, do not guess or use an alias.
```

**Orchestrator capture + cross-check:** As each teammate's first message arrives, read its `[MODEL]` line and record it. After all four have reported (or at the [SETUP-COMPLETE] boundary), write the `## Team Models` block into CASE-PROGRESS.md per progress-format.md, listing each agent's reported runtime model alongside the INTENDED model (`claude-opus-4-8` — the spawn `model=` value). If ANY reported model differs from `claude-opus-4-8`, emit a prominent WARNING line in that block:

```
⚠ MODEL MISMATCH: <agent> requested claude-opus-4-8 but is running <reported> — the model pin did not take effect (silent fallback). Results may not reflect the intended reasoning model.
```

Also record the coordinator's OWN runtime model (read it from your environment/system context) on the `coordinator (orchestrator)` line — the orchestrator has no pin and inherits the session model, so this documents what drives diagnosis/interventions.

This makes the exact model + version of every agent auditable at the top of every run, and surfaces a fallback immediately instead of buried in a footer.

**Step 5: Kick off (mandatory — the team will NOT start on its own).**

Immediately after spawning, the coordinator MUST push the first directive. The freshly-spawned teammates are idle and will do nothing until messaged.

**First, stamp timing** (see the timing step): take the `run_start` stamp (this one also does `mkdir -p <compound_path>/analysis`), then a `phase_start` stamp for `peak-picking` — both BEFORE the push below.

<!-- Phase 95 (SP1-01/SP-02): write the run manifest so the webview's
     spectra.py router can locate the raw Bruker dataset. analysis/
     already exists (created by the run_start stamp above); this write
     must land BEFORE the webview launch below so the dashboard's first
     poll tick can read it. -->

**Write the run manifest (trusted-local absolute path, D-07):**

```bash
cat > "<compound_path>/analysis/.run_manifest.json" <<JSON
{"bruker_data_dir": "<compound_path (absolute)>", "formula": "<formula>"}
JSON
```

<!-- WV-07: Launch webview dashboard before the first [BEGIN] push.
     analysis/ was just created by the run_start timing stamp above.
     lucy webview serve is non-blocking (~0.5 s startup probe) — it does NOT
     violate the headless/non-interactive rule. The spawned uvicorn process
     uses start_new_session=True and outlives this orchestrator session.
     Do NOT use & (background operator), --port, or --open. -->

**Launch the webview dashboard (non-blocking — exits in ~0.5 s):**

```bash
WEBVIEW_OUTPUT=$(lucy webview serve "<compound_path>/analysis" 2>&1)
WEBVIEW_EXIT=$?
if [ $WEBVIEW_EXIT -eq 0 ]; then
  echo "$WEBVIEW_OUTPUT"
else
  echo "Note: Webview dashboard unavailable — $WEBVIEW_OUTPUT"
  echo "Install lucy-ng[webview] to enable the live dashboard."
fi
```

This call is foreground and non-blocking: `lucy webview serve` launches a detached uvicorn subprocess via `start_new_session=True`, waits ~0.5 s for a startup probe, then returns. Do NOT append `&`, do NOT background-and-wait, do NOT pass `--port` or `--open`, and do NOT abort the CASE run if the call fails — the dashboard is observability only.

When the server starts successfully the output already contains:
- `Webview server running at http://127.0.0.1:NNNNN`
- `Stop with: lucy webview stop <compound_path>/analysis`

Store the URL from the output in a variable (e.g. `WEBVIEW_URL`) so it can be recorded in the CASE-PROGRESS.md header `**Dashboard:**` field (see write_progress). The `analysis/` directory exists because the `run_start` stamp above created it — this is why the launch block sits after that stamp.

**Now create the CASE-PROGRESS.md header — BEFORE the `[BEGIN] peak-picking` push, not at `[SETUP-COMPLETE]`.** Using the `write_progress` File-header trigger (progress-format.md trigger 1), write `<compound_path>/analysis/CASE-PROGRESS.md` with `**Compound:**` (the data path), `**Formula:**` (the molecular formula — both are already known at run start), `**Started (UTC):**` (the `run_start` stamp), `**Team:**`, and `**Dashboard:**` (`WEBVIEW_URL`, or the "unavailable — [webview] extra not installed" note if the launch warned). This populates the dashboard **Run Log** panel with the run context from t=0 instead of leaving it "Waiting for log data…" until peak-picking finishes. Do NOT defer the header to `[SETUP-COMPLETE]`.

Continue to the `phase_start` stamp and the `[BEGIN] peak-picking` push regardless of webview outcome.

```
SendMessage(
  type="message",
  recipient="nmr-chemist",
  content="[BEGIN] peak-picking — start now. Pick 13C/HSQC/HMBC for {compound_path} (formula {formula}), run statistical detection, write the analysis/ structure, then send [SETUP-COMPLETE] with all peak assignments, detection results, and quality assessment. Prepend your first message with the [MODEL] line.",
  summary="Kick off nmr-chemist peak-picking"
)
```

Do NOT proceed to a passive wait. After this push, enter monitor_progress: each teammate reply arrives as a turn that wakes you; on each reply, immediately push the next `[BEGIN]` directive (never rely on the teammate to poll the TaskList).
</step>

<step name="write_progress">
Read the full CASE-PROGRESS.md format template before writing any progress entries:

Read file: ~/.claude/commands/lucy-ng/references/progress-format.md

The orchestrator is the SOLE AUTHOR of CASE-PROGRESS.md. Create the file with its **header at run-start** — in spawn_case_team Step 5, right after the webview launch, using the File-header trigger (trigger 1 below). Do NOT wait for [SETUP-COMPLETE]: the header must exist from t=0 so the dashboard **Run Log** panel shows the run context (compound path, formula, dashboard URL) immediately rather than "Waiting for log data…". Then **append** the `## Setup` section after receiving [SETUP-COMPLETE] from nmr-chemist, and update after every [ITERATION-COMPLETE], [VALIDATION-PASSED/BLOCKED], and [RANKING-COMPLETE] message. When writing the file header, record the dashboard URL captured from the `lucy webview serve` output (stored in `WEBVIEW_URL` from spawn_case_team Step 5) into the `**Dashboard:**` field — or write "unavailable — [webview] extra not installed" if the launch warned.

<!--
RELOAD NOTE: case.md is a repo `.claude/` skill prompt symlinked into `~/.claude`. Behavior
changes here are MARKDOWN PROMPT EDITS — a FRESH Claude Code session is REQUIRED to reload the
edited orchestrator. They are NOT unit-testable this session; functional validation is the blind
CASE4 re-run (UAT-01 / Phase 89).
-->

**`## Multiplicity Coverage` ledger (only when a `[MULTIPLICITY-AMBIGUOUS]` record exists).**
When the nmr-chemist has emitted a `[MULTIPLICITY-AMBIGUOUS]` signal (see lucy-nmr-chemist.md
Section 5b), maintain a `## Multiplicity Coverage` section in CASE-PROGRESS.md as the single
source of truth the pre-accept coverage gate reads. Record four things:

- **viable_families** — the numbered list from the nmr-chemist's `[MULTIPLICITY-AMBIGUOUS]`
  signal (e.g. `iPr (3×CH₃+CH)`, `ethyl (2×CH₃+CH₂+CH₂)`).
- **searched_families** — one entry per family that produced **its own `iteration_NN_<family>/`
  run + a matching `[ITERATION-COMPLETE]`**. Count a family as SEARCHED **even if its
  `solutions.smi` conversion was skipped** because the count was large (the SEARCHED-not-RANKED
  rule from Plan 88-02). Do NOT require a ranked `solutions.smi` and do NOT key this off MAE or
  plausibility — searched means the constrained LSD run ran and signalled, nothing more.
- **DA-mandated models** — every model X from a Devils-Advocate `[MULT-EVIDENCE-FOR] model=X`
  message (G-MULT). These are binding mandatory-search items closeable ONLY by an actual
  `iteration_NN_X/` search.
- **gate verdict** — PASS / FAIL written by the coverage_gate step (see below).

If no `[MULTIPLICITY-AMBIGUOUS]` record exists, omit this section entirely — the single-family
flow is unaffected.
</step>

<step name="timing">
**Wall-clock timing capture — real UTC timestamps at every phase boundary and agent hand-back,
so a run's total and per-phase duration can be reported reproducibly (e.g. in a publication).**

<!--
RELOAD NOTE: case.md is symlinked into ~/.claude. Prompt edit — a FRESH Claude Code session is
required to reload. Not unit-testable this session; validated by the next full CASE run.
-->

**Two hard rules:**
1. **NEVER infer a timestamp** from context / `currentDate` (that only knows the calendar day).
   ALWAYS read the real clock with `date -u`. That is the whole point — the old `<timestamp>`
   placeholders were being filled from context and had no wall-clock time.
2. **All timing work happens in the coordinator** (this orchestrator), never in the teammates.
   It therefore CANNOT delay the lsd-engineer's "[ITERATION-COMPLETE] the instant the solver
   exits" anti-hang rule. A `date` call is instantaneous; still, always take the `phase_end`
   stamp for an arriving reply FIRST, then write its CASE-PROGRESS.md section and push the next
   `[BEGIN]` — never let stamping gate the next directive.

**Mechanism — one atomic append per event.** At each timing point, run exactly one Bash call
that reads the clock and appends one JSON line to the append-only log (survives restarts):

```bash
printf '{"utc":"%s","epoch":%s,"event":"%s","phase":"%s","agent":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(date -u +%s)" "<event>" "<phase>" "<agent>" \
  >> <compound_path>/analysis/timing.jsonl
```

(The very first call — `run_start` — must create the dir first: prefix it with
`mkdir -p <compound_path>/analysis && `.)

**When to stamp (phase boundaries + agent hand-backs — plenty, but not every message):**

| event | phase value | when |
|-------|-------------|------|
| `run_start` | `run` | ONCE, at team spawn, BEFORE the first `[BEGIN]` push |
| `phase_start` | the task name (`peak-picking`, `lsd-iteration-NN`, `hmbc-selection-NN`, `ranking`, `coverage_gate`, `identity_gate`) | immediately BEFORE you SendMessage each `[BEGIN]` directive |
| `phase_end` | same phase name | immediately as the matching `[*-COMPLETE]` / `[VALIDATION-*]` / `[G-IDENT-*]` reply arrives (before writing its section) |
| `run_end` | `run` | ONCE, after the gates pass and results are ready, BEFORE terminate_team |

Rule of thumb: **every `[BEGIN]` you send → one `phase_start`; every completion reply you
receive → one `phase_end`.** That gives start+end for every phase and a stamp for every agent
hand-back, without stamping routine chatter. Also mirror the human-readable UTC value into the
matching CASE-PROGRESS.md field (`**Started (UTC):**`, `**Phase start (UTC):**`,
`**Reported (UTC):**` — see progress-format.md).

**Finalize (run ONCE, right after the `run_end` stamp, before terminate_team).** This also runs
on the escalate and smoke-test exits (any path into terminate_team), so a duration is always
recorded. Convert the log into the machine-readable `timing.json` + a human table
deterministically (python does the arithmetic — do NOT compute durations by hand):

```bash
python3 - <<'PY' <compound_path>
import json, sys, pathlib
d = pathlib.Path(sys.argv[1]) / "analysis"
ev = [json.loads(l) for l in (d/"timing.jsonl").read_text().splitlines() if l.strip()]
def hms(s): return None if s is None else f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"
starts, phases = {}, []
for e in ev:
    if e["event"] == "phase_start":
        starts[e["phase"]] = e
    elif e["event"] == "phase_end" and e["phase"] in starts:
        s = starts.pop(e["phase"])
        phases.append({"phase": e["phase"], "agent": e.get("agent", ""),
                       "start_utc": s["utc"], "end_utc": e["utc"],
                       "duration_s": int(e["epoch"]) - int(s["epoch"])})
run = {x["event"]: x for x in ev if x["event"] in ("run_start", "run_end")}
total = (int(run["run_end"]["epoch"]) - int(run["run_start"]["epoch"])) if {"run_start","run_end"} <= run.keys() else None
out = {"run_start_utc": run.get("run_start", {}).get("utc"),
       "run_end_utc": run.get("run_end", {}).get("utc"),
       "total_duration_s": total, "total_duration_hms": hms(total), "phases": phases}
(d/"timing.json").write_text(json.dumps(out, indent=2))
rows = "\n".join(f"| {p['phase']} | {p['agent']} | {p['start_utc']} | {p['end_utc']} | {hms(p['duration_s'])} |" for p in phases)
print("\n## Timing Summary\n\n"
      f"**Run start (UTC):** {out['run_start_utc']}  \n"
      f"**Run end (UTC):** {out['run_end_utc']}  \n"
      f"**Total wall-clock:** {out['total_duration_hms']}\n\n"
      "| Phase | Agent | Start (UTC) | End (UTC) | Duration |\n"
      "|-------|-------|-------------|-----------|----------|\n" + rows + "\n")
PY
```

Append the printed `## Timing Summary` block to `analysis/CASE-PROGRESS.md`, and also to
`analysis/final_results.md` **if it exists** (it won't on the escalate/smoke exits).
`analysis/timing.json` is the machine-readable artefact for aggregating across many runs.
</step>

<step name="validate_message">
Validate incoming structured messages before processing. Each message type has required fields. If any are missing, request resend via SendMessage.

**Required fields by message type:**

[SETUP-COMPLETE]:
- DBE, Spectra found, Peak counts, Symmetry, Multiplicities, Quality assessment
- Statistical detection, Grouping, HHB, Aromatic expectation
- Conflicts with NMR evidence, Key observations

[ITERATION-COMPLETE]:
- LSD file, Solution count, Constraints added, Constraints removed
- Constraint inventory delta, sp2 count, H budget
- HMBC correlations used, Why, Constraint effectiveness, Confidence
- Fragment search, Fragment file

[RANKING-COMPLETE]:
- Solutions, Top solution, Strained rings, Aromatic warning
- Chemical plausibility, Quality, Recommendation

**Validation procedure:**

On receiving any structured message (identified by `[TAG]` prefix):
1. Identify message type from tag
2. Check message text for each required field label (case-insensitive substring match of the field name followed by `:`)
3. If any required field label is missing:
   - DO NOT process the message
   - Send back to originating agent:
     ```
     SendMessage(
       type="message",
       recipient="{agent_name}",
       content="[RESEND-REQUIRED] Your [{TAG}] message is missing required fields: {list}.
                Please resend the complete message with all required fields.
                See your agent definition for the full template.",
       summary="Requesting resend of [{TAG}] — missing fields"
     )
     ```
   - Log: "Message validation failed for [{TAG}] from {agent}: missing {fields}"
4. If all required fields present: proceed to process in monitor_progress

**Important:** "None detected", "N/A", "None", and "0" are all VALID values. Only truly missing field labels trigger resend.
</step>

<step name="monitor_progress">
Monitor team progress via incoming SendMessage notifications (teammate replies arrive as conversation turns and wake you). TaskList is read only as a status ledger — the workflow advances because you PUSH the next `[BEGIN]` directive after each reply, never because a teammate polls.

Before processing any structured message, run validate_message to check for required fields.

**Shift list retention:** When processing [SETUP-COMPLETE] from nmr-chemist, extract and retain the experimental 13C shift list (comma-separated ppm values). This is needed later for creating ranking tasks.

**Push iteration 1 (mandatory after [SETUP-COMPLETE]):** the lsd-iteration-01 task created at spawn will NOT start on its own. Immediately after writing the Setup section, push the lsd-engineer:
```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[BEGIN] lsd-iteration-01 — peak assignments are ready (see analysis/CASE-PROGRESS.md ## Setup). Build the initial LSD file in analysis/iteration_01/ (MULT from HSQC, first 3-5 HMBC), request DA validation, run the solver. Send [ITERATION-COMPLETE] with the solution count the INSTANT the solver exits — do NOT block it on SMILES conversion (skip conversion if the count is large); ending your turn after a solver run without [ITERATION-COMPLETE] hangs the whole run.",
  summary="Kick off LSD iteration 1"
)
```

**Monitoring loop:** Receive structured messages from teammates (arrive as conversation turns) + optionally read `TaskList()` for status + read `<compound_path>/analysis/CASE-PROGRESS.md` for loop detection. On each structured message ([SETUP-COMPLETE], [ITERATION-COMPLETE], [VALIDATION-PASSED], [VALIDATION-BLOCKED], [RANKING-COMPLETE]): **take the `phase_end` timing stamp first** (see the timing step), then write the corresponding section to CASE-PROGRESS.md per write_progress, then take a `phase_start` stamp for and **push the next `[BEGIN]` directive** to whichever agent owns the next step, then continue monitoring. (Timing invariant: every `[BEGIN]` you push is preceded by a `phase_start`; every completion reply you receive is preceded by a `phase_end`.)

**Stall recovery (missing [ITERATION-COMPLETE]) — self-rescue when you are awoken:**
The primary defence is the lsd-engineer sending [ITERATION-COMPLETE] the instant the solver
exits (reinforced in every lsd-iteration directive). As a backstop: whenever you are awoken
for ANY reason (another teammate's message, a user nudge) and an lsd-iteration directive is
still outstanding with no [ITERATION-COMPLETE], do NOT passively wait again — check the
filesystem directly: if `analysis/iteration_NN/solncounter` (or a `*.sol` file) exists and no
LSD process is running, the solver already finished and the engineer stalled before signalling.
Read the solution count from `solncounter` yourself, write the [ITERATION-COMPLETE] section to
CASE-PROGRESS.md from the filesystem, and resume the workflow (push the next directive). This
converts an indefinite hang into an immediate recovery.

**Parse from CASE-PROGRESS.md:** solution count per iteration, constraints added/removed, sp2 checks, H budget status, HMBC correlations used (X/Y), last iteration number.

**Smoke test early exit:**
If SMOKE_TEST is true, track these checkpoints as they arrive:
- [ ] [SETUP-COMPLETE] received from nmr-chemist (peak picking done)
- [ ] [ITERATION-COMPLETE] received from lsd-engineer (LSD file built and run)
- [ ] [VALIDATION-PASSED] or [VALIDATION-BLOCKED] received from devils-advocate

When all 3 checkpoints are complete (or any checkpoint fails with error/timeout after 5 minutes):
- Do NOT create further iteration tasks
- Do NOT proceed to ranking
- Proceed directly to smoke_test_report step

**Completion signals (normal mode only, when SMOKE_TEST is false):** solution_count <= 10 → ranking → **coverage_gate** (when ambiguous) → identity_gate | [RANKING-COMPLETE] received → **coverage_gate** (when ambiguous) → **identity_gate** (post-solution G-IDENT review) → present_results | 10 iterations reached → ranking → coverage_gate (when ambiguous) → identity_gate → present_results with caveats | DA flags issue → detect_loops.

**IMPORTANT — never go straight from [RANKING-COMPLETE] to present_results/terminate_team.** Once `analysis/final_results.md` exists, the run is NOT done until (a) — **when a `[MULTIPLICITY-AMBIGUOUS]` record exists** — the pre-accept **coverage_gate** step has PASSED, and (b) the post-solution identity_gate step has run (the devils-advocate's independent G-IDENT name↔structure cross-check). The coverage_gate runs FIRST (it can REOPEN the run to search a missing family); only once it passes does identity_gate run. Skipping the identity_gate silently drops the D-04 advisory layer (the CASE5 failure); skipping the coverage_gate silently accepts a run where a viable multiplicity family was never searched (the CASE4 failure).

**Iteration management (create next tasks):**

After receiving [ITERATION-COMPLETE] from lsd-engineer AND [VALIDATION-PASSED] or [VALIDATION-BLOCKED] from devils-advocate, AND after writing both sections to CASE-PROGRESS.md:

After writing the Devils-Advocate section to CASE-PROGRESS.md, relay the approval decision to lsd-engineer:

If [VALIDATION-PASSED] was received:
```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[DA-APPROVED] Iteration {N} — Validation passed. Proceed with solver run.
           DA findings: {brief summary from [VALIDATION-PASSED] message}",
  summary="DA approved iteration {N} — proceed with solver"
)
```

If [VALIDATION-BLOCKED] was received:
```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[DA-BLOCKED] Iteration {N} — Validation blocked. Critical issues:
           {issues from [VALIDATION-BLOCKED] message}
           Fix these before running solver.",
  summary="DA blocked iteration {N} — fix required"
)
```

1. Extract solution_count from the [ITERATION-COMPLETE] message
2. Run detect_loops (existing step)
3. **If no loop AND solution_count > 10 AND iterations < 10 (safety cap):**

   Retain the shift list from the [SETUP-COMPLETE] message received earlier (the orchestrator wrote these to ## Setup / ### NMR-Chemist in CASE-PROGRESS.md — read from there if needed).

   Create next iteration task:
   ```
   TaskCreate(
     subject="lsd-iteration-{next_iter:02d}",
     description="Build LSD file for iteration {next_iter} of {formula} at {compound_path}.
                  Read previous: analysis/iteration_{current_iter:02d}/compound.lsd
                  Use constraint inventory to copy ALL constraints forward.
                  Add next HMBC batch (3-5 correlations, best remaining from CASE-PROGRESS.md Setup).
                  Send validation request to devils-advocate.
                  WAIT for approval before running solver.
                  Run LSD from analysis/iteration_{next_iter:02d}/.
                  Send [ITERATION-COMPLETE] to coordinator.",
     activeForm="LSD iteration {next_iter}"
   )
   ```

   **Then immediately push it** (the lsd-engineer is idle and will not pick this up on its own):
   ```
   SendMessage(
     type="message",
     recipient="lsd-engineer",
     content="[BEGIN] lsd-iteration-{next_iter:02d} — build iteration {next_iter} now: read analysis/iteration_{current_iter:02d}/compound.lsd, carry ALL constraints forward, add the next HMBC batch, request DA validation, then run the solver. Send [ITERATION-COMPLETE] with the solution count the INSTANT the solver exits — do NOT block it on SMILES conversion (skip conversion if the count is large); ending your turn after a solver run without [ITERATION-COMPLETE] hangs the whole run.",
     summary="Kick off LSD iteration {next_iter}"
   )
   ```

   **Parallel task creation (when solution_count is 10-50 and iterations >= 2):**
   Additionally create an HMBC selection task for nmr-chemist:
   ```
   TaskCreate(
     subject="hmbc-selection-{next_iter:02d}",
     description="Select next HMBC batch (3-5 correlations) for iteration {next_iter}.
                  Review CASE-PROGRESS.md for already-used correlations.
                  Apply selection criteria: isolated carbons, unique protons, strong intensity.
                  Send selected batch to lsd-engineer via SendMessage.",
     activeForm="Selecting HMBC batch {next_iter}"
   )
   ```

   **Then immediately push it** to nmr-chemist:
   ```
   SendMessage(
     type="message",
     recipient="nmr-chemist",
     content="[BEGIN] hmbc-selection-{next_iter:02d} — select the next 3-5 HMBC correlations now (avoid already-used ones in CASE-PROGRESS.md) and send the batch to lsd-engineer.",
     summary="Kick off HMBC selection {next_iter}"
   )
   ```

4. **If solution_count <= 10:**

   Read the shift list from CASE-PROGRESS.md ## Setup / ### NMR-Chemist section (the 13C peak positions written from [SETUP-COMPLETE]).

   Create ranking task with embedded shifts:
   ```
   TaskCreate(
     subject="ranking-iteration-{current_iter:02d}",
     description="Rank LSD solutions from iteration {current_iter}.
                  solutions.smi path: analysis/iteration_{current_iter:02d}/solutions.smi
                  Experimental 13C shifts: {shift_list}
                  Run: lucy lsd rank analysis/iteration_{current_iter:02d}/solutions.smi --shifts '{shift_list}'
                  Assess chemical plausibility of top candidates.
                  Write analysis/final_results.md with full report.
                  Send [RANKING-COMPLETE] to coordinator.",
     activeForm="Ranking LSD solutions"
   )
   ```

   **Then immediately push it** to solution-analyst (embed the shift list + path in the message so it never needs the TaskList):
   ```
   SendMessage(
     type="message",
     recipient="solution-analyst",
     content="[BEGIN] ranking — rank solutions now. solutions.smi: analysis/iteration_{current_iter:02d}/solutions.smi ; experimental 13C: {shift_list}. Assess plausibility, write analysis/final_results.md, send [RANKING-COMPLETE].",
     summary="Kick off ranking"
   )
   ```

5. **If iterations >= 10 (safety cap) AND solution_count > 10:**

   Create ranking task (same as above), push the [BEGIN] ranking directive to solution-analyst, AND proceed to present_results with caveat.

After creating a task you MUST have pushed its `[BEGIN]` directive — then return to monitoring. Never end a turn on a bare `TaskCreate`; an un-pushed task is a stall.
</step>

<step name="detect_loops">
Read the full loop pattern definitions before analyzing iteration patterns:

Read file: ~/.claude/commands/lucy-ng/references/loop-patterns.md

Five patterns to detect: ELIM Thrashing, Zero-Solution Loop, Solution Explosion, Constraint Churning, Quality Convergence Failure.

**Quick detection criteria (check against parsed iteration history):**

**Pattern 1: ELIM Escalation (runaway-N detection)** — `elim_budget > 3` in consecutive `[ITERATION-COMPLETE]` messages without a plausible solution (runaway ELIM escalation). At N=3 with 0 plausible solutions, the problem is a constraint conflict, not a 4J issue.

**Pattern 2: Zero-Solution Loop** — 3+ consecutive iterations with solution_count = 0.

**Pattern 3: Solution Explosion** — Last 3 iterations all have solution_count > 100 AND each iteration reduces count by less than 10%.

**Pattern 4: Constraint Churning** — Last 5 iterations show >10 constraints added AND >5 constraints removed AND most recent solution_count > 50.

**Pattern 5: Quality Convergence Failure** — Most recent [RANKING-COMPLETE] message (or
CASE-PROGRESS.md ## Ranking section for current iteration) shows Chemical plausibility =
IMPLAUSIBLE or QUESTIONABLE for ALL top-3 candidates.
OR-trigger: best-MAE > 4.0 ppm AND solution_count ≤ 20.
Guard: only fire if a [RANKING-COMPLETE] record exists for the current iteration.
Do NOT fire if solution_count = 0 (Pattern 2 covers that case).

If no loop pattern detected, check convergence:
- **If solution_count <= 10:** SUCCESS, proceed to present_results
- **If iterations >= 10 and solution_count > 10:** Safety cap reached, proceed to present_results with caveats
- **If solution_count > 10 and iterations < 10:** Agent is still progressing, allow to continue

If a loop pattern is detected, proceed to diagnose step.
</step>

<step name="diagnose">
For the detected loop pattern, perform basic diagnosis to identify root cause.

**For ELIM Escalation (runaway N):**
1. Read the latest LSD file from the most recent iteration
2. Confirm elim_budget > 3 by checking `[ITERATION-COMPLETE]` history
3. Count MULT commands with hybridization = 2 (sp2 atoms) — verify EVEN
4. Sum all hydrogen counts from MULT commands — verify matches formula
5. Check latest HMBC correlations against HSQC positions for 1J artifacts:
   - 1J artifact if HMBC (C, H) within ±1.5 ppm (carbon) and ±0.3 ppm (proton) of any HSQC correlation
6. If all checks pass at N=3 and still 0 solutions → constraint conflict, not 4J → escalate to diagnostic specialist

**For Zero-Solution Loop:**
1. Identify which iteration first returned 0 solutions
2. Identify constraints added in that iteration
3. Check if any HMBC correlations match HSQC positions (1J artifacts, ±1.5 ppm C, ±0.3 ppm H)
4. Check if carbons in that batch are within 3 ppm of each other (ambiguous assignment)

**For Solution Explosion:**
1. Check if ELIM command is present in latest LSD file
2. Check if heteroatom constraints (BOND, LIST, PROP) are present in LSD file
3. Review recent HMBC correlations to determine if they connect new fragments or redundant connections

**For Constraint Churning:**
1. Review last 5 iterations for systematic vs random correlation selection
2. Check if correlations selected by criteria (isolated carbons, unique protons, strong intensity)
3. Check if correlations selected randomly without clear strategy

Document diagnostic findings for intervention generation.
</step>

<step name="intervene">
Based on diagnosis findings, generate an advisory intervention that tells the agent WHAT to fix, not HOW to fix it.

**Advisory templates by pattern:**

**ELIM Escalation (runaway N):**
```
Runaway ELIM escalation detected. At N=3 with 0 plausible solutions, this is a constraint conflict — not a 4J issue.

Do NOT escalate ELIM beyond N=3. Instead:

1. Verify sp2 count is even (current count: <N>)
   - Re-examine DEPT-135 spectrum to verify sp2 assignments
   - Common sp2 atoms: carbonyl C, carbonyl O, aromatic C

2. Verify hydrogen budget matches formula
   - Sum of MULT H-counts: <N>
   - Formula H-count: <N>
   - If mismatch, review HSQC peak assignments

3. Check HMBC correlations for 1J artifacts
   - Compare against HSQC positions (±1.5 ppm C, ±0.3 ppm H)
   - Exclude flagged artifacts

Escalate to diagnostic specialist — do NOT continue ELIM escalation.
```

**Zero-Solution Loop:**
```
Zero-solution loop detected (3 consecutive iterations with 0 solutions).

Diagnose:
1. Remove last HMBC batch (iteration <N> constraints)
2. Confirm solutions return
3. Test each correlation individually to find the conflict
4. Check if any carbons are within 3 ppm (could be misassigned due to digital resolution)
5. Check for 1J artifacts (compare HMBC to HSQC per skill/SKILL.md Section 2.3)

Only re-add correlations after resolving the conflict.
```

**Solution Explosion:**
```
Solution explosion stalled (3 iterations, <10% reduction each, still >100 solutions).

Check:
1. Verify recent HMBC correlations connect NEW fragments (not already-connected atoms)
2. Add heteroatom constraints:
   - Use BOND for known positions (e.g., carbonyl O bonded to specific C)
   - Use LIST/PROP for ambiguous positions (see skill/SKILL.md Section 10.2)
3. Check quaternary carbons — if 0 HMBC correlations, add shift-based constraints
   (see skill/SKILL.md Section 10.3)
4. ELIM is the final zero-solution recovery mechanism. If ELIM N=3 yields 0 plausible solutions, escalate to diagnostic specialist — this is a constraint conflict, not a 4J issue. Do NOT remove ELIM as a first response to solution explosion; large solution sets are expected with ELIM and handled by ranking.

Focus on high-leverage constraints that separate structural classes.
```

**Constraint Churning:**
```
Constraint churning detected (high add/remove activity without convergence).

Reset to last known-good state (iteration <N> with <X> solutions).

Follow incremental HMBC strategy from skill/SKILL.md Section 7:
1. Select 3-5 HIGH-CONFIDENCE correlations per batch:
   - Isolated carbon shifts (>3 ppm from nearest neighbor)
   - Unique proton assignments
   - Strong peak intensities (top quartile)
2. Add batch, run LSD, evaluate effectiveness
3. If reduction >= 30%, continue with next batch
4. If reduction < 10%, re-evaluate selection criteria

Do NOT add/remove randomly. Be systematic.
```

Proceed to track_and_decide step with the generated advisory.
</step>

<step name="track_and_decide">
Track intervention count for this specific pattern and decide whether to re-spawn agent, delegate to diagnostic specialist, or escalate.

**Per-pattern intervention counters:**
Maintain separate counters for each pattern:
- ELIM_THRASHING: count_elim
- ZERO_SOLUTION_LOOP: count_zero
- SOLUTION_EXPLOSION: count_explosion
- CONSTRAINT_CHURNING: count_churning
- QUALITY_CONVERGENCE_FAILURE: count_quality

**After intervention generated:**
Increment the counter for THIS pattern only.

**Decision logic:**
- **If counter for this pattern == 0 or 1:** Basic intervention (diagnose + intervene steps produce advisory, proceed to deliver_advisory step)
- **If counter for this pattern == 2:** Delegate to diagnostic specialist (proceed to delegate_specialist step)
- **If counter for this pattern >= 3 and < 10:** Use specialist-informed advisory if analysis/DIAGNOSTIC-REPORT.md exists in compound directory, else fall back to basic advisory (proceed to deliver_advisory step)
- **If counter for this pattern >= 10:** Escalate to user (proceed to escalate step)

Threshold = 2: basic diagnosis handles common issues (odd sp2, missing H); specialist escalation prevents wasted cycles on complex root causes. Per-pattern counters avoid masking which failure mode recurs.

**Decision for QUALITY_CONVERGENCE_FAILURE:**
- count_quality == 0: deliver assumption-reexamination advisory (proceed to deliver_advisory_and_results step using quality_convergence_advisory template from advisory-templates.md)
- count_quality >= 1: honest termination — do NOT escalate to diagnostic specialist
  (the diagnostic specialist is LSD-focused; quality convergence failure is a peak-picking issue).
  Send to coordinator: "Assumption re-examination complete. No correctable peak-picking defect found after
  1 re-examination cycle. Additional experiments may be needed."
</step>

<step name="escalate">
After 10 failed intervention cycles for the SAME pattern, escalate to user with structured report.

**Escalation report format:**

```markdown
## CASE Escalation Required

**Compound:** <compound_path> | **Formula:** <formula> | **Pattern:** <pattern_name> | **Attempts:** 10

### What Was Detected
<Loop pattern description per detect_loops definitions>

### Diagnostics Attempted
<List diagnostic approaches across the 10 cycles>

### Current State
- Solution count: <count> | HMBC used: X/Y | Iterations: <N> | LSD: <latest_filename>

### Supervisor Recommendation
<Pattern-specific recommendation based on diagnostic findings>

### Next Steps
Manual review required. See CASE-PROGRESS.md for full iteration history.
```

**After presenting escalation report:** STOP. User must investigate.
</step>

<step name="coverage_gate">
**Pre-accept multiplicity coverage gate (D-04 / MULT-02 — deterministic, MAE-INDEPENDENT).**

<!--
RELOAD NOTE: case.md is symlinked into ~/.claude. This is a MARKDOWN PROMPT EDIT — a FRESH
Claude Code session is REQUIRED to reload. NOT unit-testable this session; functional
validation is the blind CASE4 re-run (UAT-01 / Phase 89).
-->

**Guard — when this step runs:** ONLY when a `[MULTIPLICITY-AMBIGUOUS]` record exists for this
run (i.e. a `## Multiplicity Coverage` ledger is present in CASE-PROGRESS.md). If there is no
`[MULTIPLICITY-AMBIGUOUS]` record, **SKIP this step entirely** and proceed straight to
identity_gate — the single-family flow is completely unaffected.

**Lifecycle position:** This runs at the SAME pre-accept lifecycle point as identity_gate —
after the union has been ranked and `analysis/final_results.md` exists, BEFORE accept /
present_results — and it runs BEFORE identity_gate (it may REOPEN the run, so it must resolve
first). It is the COVERAGE-triggered analogue of detect_loops Pattern 5 "Quality Convergence
Failure" (which reopens on MAE); coverage_gate reopens on missing-family COVERAGE, not MAE.

**The gate is deterministic and MAE-INDEPENDENT.** It does NOT look at MAE, plausibility, or
rank. (The CASE4 wrong-class structure scored MAE 1.75 "PLAUSIBLE" and the MAE>4 quality loop
stayed silent — that is exactly why this gate must NOT key off MAE.) Read the
`## Multiplicity Coverage` ledger and evaluate two set-containment conditions:

1. `viable_families ⊆ searched_families` — every family the nmr-chemist enumerated has its own
   `iteration_NN_<family>/` run + `[ITERATION-COMPLETE]`. Count by **SEARCHED, not RANKED**: a
   family whose `solutions.smi` conversion was skipped for size still counts as searched (do NOT
   require a ranked `solutions.smi`).
2. every **DA-mandated model** (each `[MULT-EVIDENCE-FOR] model=X` from G-MULT) `∈ searched_families`.

**Verdict:**

- **PASS** — both conditions hold. Write `gate verdict: PASS` to the `## Multiplicity Coverage`
  ledger and proceed to identity_gate.
- **FAIL** — any viable family OR any DA-mandated model is NOT in searched_families. The run
  does **NOT accept**. Write `gate verdict: FAIL — missing: <family/model list>` to the ledger,
  then **REOPEN**: push the lsd-engineer (via the multiplicity-coverage reopen advisory in
  references/advisory-templates.md — WHAT not HOW: name the missing family/model and that it
  must be searched in its own `iteration_NN_<family>/` dir) to run the missing family(ies)/
  model(s). When their `[ITERATION-COMPLETE]`s arrive, re-run the deduped union rank
  (per the lsd-engineer's union-ranking contract), update searched_families in the ledger, and
  **re-enter coverage_gate**. Do not advance to identity_gate until the gate PASSES.

This gate triggers on COVERAGE, never on MAE. A converged, plausible-looking, low-MAE run is
STILL rejected if a viable family or a DA-mandated model was never searched. See
references/loop-patterns.md "Multiplicity Coverage Gap" for the reopen pattern.

After the gate PASSES, proceed to identity_gate.
</step>

<step name="identity_gate">
**Post-solution G-IDENT review (mandatory before present_results — the D-04 independent advisory layer).**

This step runs ONCE, after `[RANKING-COMPLETE]` (i.e. `analysis/final_results.md` exists) and BEFORE `deliver_advisory_and_results` / `terminate_team`. It is the genuinely independent second opinion on the reported name↔structure mapping. The solution-analyst's own run of the deterministic `lucy identify` is the BINDING check; this G-IDENT pass is the separate LLM cross-check (it must NOT re-run `lucy identify`).

The devils-advocate is idle and will not act on its own — you MUST push the trigger:

```
SendMessage(
  type="message",
  recipient="devils-advocate",
  content="[BEGIN] G-IDENT — post-solution name↔structure review. analysis/final_results.md is written. Run ONLY the G-IDENT gate (Section 5 / post-solution): read the reported trivial name + the top SMILES, reason INDEPENDENTLY about whether the name plausibly matches the drawn structure — do NOT call lucy identify / derive_identity (that is the analyst's binding layer). Apply the CASE4 (wrong-isomer/literature name) and CASE5 (indigo↔isoindigo↔indirubin) triggers. Reply [G-IDENT-PASSED] or [G-IDENT-FLAGGED] with a one-line rationale.",
  summary="Post-solution G-IDENT review"
)
```

Then wait for the devils-advocate's reply (it arrives as a turn and wakes you). On reply:
- Write a `### Devils-Advocate (G-IDENT post-solution)` entry into CASE-PROGRESS.md with the verdict + rationale.
- **[G-IDENT-FLAGGED]** is advisory and NEVER blocks the report. If flagged, ensure the reported trivial name in `final_results.md` is rendered `(tentative, unverified)` and carry the DA's concern into the results presentation. Then proceed.
- **[G-IDENT-PASSED]**: proceed.

If the devils-advocate errors or does not reply within a reasonable window, note "G-IDENT review unavailable" in CASE-PROGRESS.md and proceed (advisory, non-blocking) — do NOT hang the run waiting on it.

After recording the G-IDENT outcome, proceed to deliver_advisory_and_results.
</step>

<step name="deliver_advisory_and_results">
Read advisory delivery, result presentation, diagnostic delegation, and anti-pattern templates:

Read file: ~/.claude/commands/lucy-ng/references/advisory-templates.md

This reference covers: advisory message formatting, result presentation (success/incomplete/failed), diagnostic specialist delegation, diagnostic findings extraction, and anti-patterns to avoid.
</step>

<step name="smoke_test_report">
Generate smoke test pass/fail report. Only runs when SMOKE_TEST is true.

**Determine result for each checkpoint:**
- PASS: message received with all required fields validated
- FAIL: message not received, or validate_message rejected it, or agent error/timeout (> 5 minutes)

**Print report:**
```
========================================
SMOKE TEST RESULTS
========================================

| Checkpoint               | Status    | Details                    |
|--------------------------|-----------|----------------------------|
| Team spawned             | PASS/FAIL | 4 agents created           |
| NMR-chemist peak pick    | PASS/FAIL | [SETUP-COMPLETE] received  |
| LSD-engineer build file  | PASS/FAIL | [ITERATION-COMPLETE] received |
| Devils-advocate validate | PASS/FAIL | [VALIDATION-PASSED/BLOCKED] |

Overall: PASS / FAIL (N/4 checkpoints passed)
```

**After report:** Proceed to terminate_team step (normal team cleanup).
</step>

<step name="terminate_team">
Gracefully shut down all teammates and clean up team resources.

**This step executes after:** present_results (successful or failed CASE), OR escalate (user escalation), OR smoke_test_report (smoke test mode).

**Note (WV-07):** The webview server started at run_start is intentionally left running here. It remains accessible so the user can review the dashboard after the CASE run ends. The manual stop hint was printed at run-start (spawn_case_team Step 5). Do NOT add a stop call to this step.

**Step 0: Finalize timing (before shutdown).** Take the `run_end` stamp, then run the timing finalize (see the timing step): it writes `analysis/timing.json` and prints the `## Timing Summary` block, which you append to `analysis/CASE-PROGRESS.md` (and to `analysis/final_results.md` if it exists). Do this on every exit path — success, escalation, or smoke test — so a wall-clock duration is always on record.

**Step 1: Send shutdown requests to all 4 teammates:**
```
SendMessage(type="shutdown_request", recipient="nmr-chemist",
            content="CASE workflow complete. Shutting down team.")
SendMessage(type="shutdown_request", recipient="lsd-engineer",
            content="CASE workflow complete. Shutting down team.")
SendMessage(type="shutdown_request", recipient="solution-analyst",
            content="CASE workflow complete. Shutting down team.")
SendMessage(type="shutdown_request", recipient="devils-advocate",
            content="CASE workflow complete. Shutting down team.")
```

**Step 2: Wait for shutdown confirmations.**
Teammates approve shutdown automatically (they have no reason to reject after CASE completes).

**Step 3: Clean up team resources:**
```
TeamDelete()
```

This removes:
- ~/.claude/teams/case-{compound_name}/
- ~/.claude/tasks/case-{compound_name}/

**If TeamDelete fails (teammates still active):** Wait 30 seconds and retry. If still failing, report: "Team cleanup incomplete. Manual cleanup may be needed: rm -rf ~/.claude/teams/case-{compound_name} ~/.claude/tasks/case-{compound_name}"
</step>

</process>
