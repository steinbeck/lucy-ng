# Quick Task 261006-iob (follow-up): OpenCode as a harness for the AILSA CASE skill on Qwen

**Researched:** 2026-10-06
**Subject:** OpenCode = **anomalyco/opencode** (formerly sst/opencode; the old URL redirects), npm `opencode-ai`, latest release **v1.18.34** (2026-09-30), MIT [VERIFIED: GitHub API, npm]. Not the older opencode-ai/opencode, which has been archived since 2025-09 and continues as Charm's **Crush** under FSL-1.1-MIT [VERIFIED: GitHub API]. None of the facts below concern Crush.
**Method:** official docs, plus the source at commit `3f393d7` (2026-10-06), plus tool-call counts from the existing headless benchmark transcripts on the compute host.
**Confidence:** HIGH for OpenCode capabilities, which were read in source. HIGH for the benchmark-transcript finding. MEDIUM for local-model fitness. LOW for the effort estimate.

## Summary: round 1 framed the comparison wrongly

Round 1 compared OpenCode with the AILSA skill *as written*: agent teams, SendMessage between peers, a shared task list. The benchmark does not run that version. It runs `claude -p`, and in `-p` mode "Claude doesn't spawn teammates, and a subagent that Claude names runs as an ordinary subagent even with agent teams enabled" [CITED: code.claude.com/docs/en/agent-teams]. The transcripts confirm it.

| Tool use in 169 headless Opus-5 runs (2026-09-01 to 09-29) | Count |
|---|---|
| `TeamCreate` | **0 runs** |
| Specialist spawns (`Agent`) | 1 125 (≈ 7 per run; 21 runs had one or more background spawns) |
| `SendMessage` by the lead | 264 calls in 55 runs. In `-p` this resumes a named subagent |
| `SendMessage` by the specialists | **7 in total** (vs 25 942 Bash calls) |
| `TaskCreate` / `TaskUpdate` (lead only) | 393 / 334 |

[VERIFIED: transcript JSONL on the compute host; tool names counted only, no content read]

The method that produced the published 69 % is therefore **hub-and-spoke**: the coordinator spawns a specialist, the specialist works and returns its final message, the coordinator writes CASE-PROGRESS.md and spawns or resumes the next one. That is exactly OpenCode's native model. The port is a **mechanical change of tool vocabulary, not an architectural rewrite**.

## 1. Skills
- **Directories:** `.opencode/skills/`, `.claude/skills/` and `.agents/skills/` at project level (walking up to the git worktree), plus `~/.config/opencode/skills/`, `~/.claude/skills/` and `~/.agents/skills/` globally [CITED: opencode.ai/docs/skills; VERIFIED: `src/skill/index.ts`].
- **Loading:** the agent sees an `<available_skills>` list and loads a skill on demand with the `skill` tool.
- **Format:** `name` (1-64 chars, `^[a-z0-9]+(-[a-z0-9]+)*$`, must match the directory) and `description` (≤ 1 024 chars). Unknown fields are ignored. Access is set per agent via `permission.skill`.
- **Not relevant to AILSA:** AILSA is a command plus agents, not a SKILL.md skill.
- **Blindness hazard:** OpenCode also reads `CLAUDE.md` / `~/.claude/CLAUDE.md` by default. Set `OPENCODE_DISABLE_CLAUDE_CODE=1` for blind runs [CITED: docs/rules].

## 2. Commands
- **Location:** `.opencode/commands/**/*.md` or `~/.config/opencode/commands/`, **not** `.claude/commands/` [VERIFIED: `config/command.ts`; core only scans `.opencode`, the global config dir and `OPENCODE_CONFIG_DIR`].
- **Naming:** subdirectories become part of the name, so `commands/ailsa/case.md` → `/ailsa/case`.
- **Frontmatter:** `description`, `agent`, `model`, `variant`, `subtask`. Unknown keys such as `allowed-tools` and `argument-hint` are ignored.
- **Arguments:** `$ARGUMENTS`, `$1..$n`. With no placeholder, arguments are appended at the end, the same as in Claude Code [VERIFIED: `session/prompt.ts`].
- **Two template traps:**
  - Every `` !`cmd` `` in the template is **executed** when the template is expanded.
  - `$1`, `$2` are substituted.

  `case.md` contains neither today; check both after every edit.
- **Do not set `subtask: true`:** it would make the coordinator a subagent, which then hits the depth limit when it tries to spawn the team.
- **Port fidelity:** a 1:1 port of `case.md` works as a file. Its *content* needs the vocabulary change in §4.

## 3. Agents
- **Modes:** `primary`, `subagent` or `all`.
- **Locations:** `.opencode/agents/` or `~/.config/opencode/agents/` (markdown + frontmatter) or `opencode.json`.
- **Fields:** `description`, `mode`, `model` (`provider/id`), `variant`, `temperature`, `top_p`, `steps`, `permission`, `hidden`, `color` [CITED: docs/agents; VERIFIED: `core/src/v1/config/agent.ts`].
- **Claude Code agents are not compatible as-is:**
  - `.claude/agents/` is not read.
  - The CC `tools:` **YAML list fails schema validation**: OpenCode's deprecated `tools` is a `{name: bool}` map, and an invalid file throws `InvalidError` instead of being skipped.
  - Fix: drop `tools:`, add `mode: subagent`, and express restrictions as `permission: {edit: deny}` (devil's advocate) and similar.
- **Body handling:** the body replaces OpenCode's default system prompt (`agent.prompt ? [agent.prompt] : provider prompt`) [VERIFIED: `session/llm/request.ts`].
- **Subagent defaults:** `todowrite` and `task` are denied unless the agent's permission grants them [VERIFIED: `tool/task.ts`].

## 4. Multi-agent orchestration (the crux)
**Core OpenCode, v1.18.34** [VERIFIED: `tool/task.ts`, `task.txt`, config schema]:
- **Parallel spawns:** several `task` calls in one message run concurrently. The tool prompt says so explicitly.
- **Resume = SendMessage-to-subagent equivalent:** every result carries `task_id` (the child session ID). Calling `task(subagent_type, task_id=…, prompt=…)` continues the same subagent session with its history. Sessions persist in SQLite.
- **Nested spawns:** `subagent_depth` defaults to 1, so subagents cannot spawn. Set it to `2` and grant `permission.task` to allow it. In the source, any session can resume any `task_id`, which would let the LSD engineer reach the devil's advocate's session directly. That is untested; route via the coordinator instead.
- **Background subagents:** experimental (`OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`, `background=true`). Results are injected into the parent as a synthetic turn that wakes it, and a further `task_id` call to a running job injects extra context.
- **No teams:** core has no peer messaging, shared task board or team concept. The design issue #12711 has been open since 2026-02 and its PR #12730 is unmerged. The bot closed #38963/#38964 ("subagent cannot ask its parent", "siblings cannot talk").

**Plugins (only if real teams are ever wanted, not needed here):**
- **opencode-ensemble:** MIT, 230★, v0.19.0 (2026-09-18). Adds a team, spawn, messaging and a task board with dependencies, closest to CC agent teams.
- **oh-my-openagent** (formerly oh-my-opencode): ~70 k★, background agents, but **Sustainable Use License (non-commercial)**, and it is moving towards its own harness.
- **oh-my-opencode-slim:** MIT, 9 k★.
- **team / intercom / agentpost plugins:** 1-4★, days to months old.

None are needed for parity, and each adds an uncontrolled variable [VERIFIED: GitHub API].

**Mapping, based on what the benchmark actually executes:**

| AILSA as written | What `-p` actually does | OpenCode |
|---|---|---|
| `TeamCreate` / `TeamDelete` / `shutdown_request` | never called | delete |
| `Task(name, team_name, subagent_type, model=…)` | foreground named subagent | `task(subagent_type, description, prompt)`; model from agent frontmatter or inherited |
| `SendMessage(to, "[BEGIN] …")` | resume named subagent, or fresh spawn | `task(..., task_id=<stored>, prompt="[BEGIN] …")`, or a fresh `task` (the dominant pattern) |
| `[*-COMPLETE]` sent via SendMessage | specialist's final message | specialist's final message = `<task_result>`. Same template, "end your turn with it" |
| LSD engineer → devil's advocate "ready for validation" | already routed via the lead | lead: build → spawn DA → resume LSD engineer to run the solver |
| `TaskCreate` / `TaskUpdate` ledger | used by the lead | `todowrite` (primary only) or drop; CASE-PROGRESS.md is the real ledger |
| CASE-PROGRESS.md, timing stamps, webview, `[MODEL]` line | Bash/Write by the lead | unchanged. Model also recorded authoritatively in task metadata / `opencode export` |
| anti-stall headless caveat | needed | still needed: `opencode run` exits when the parent goes idle (below) |

**Survives unchanged:** all chemistry and method content, i.e. ≈ 90 % of the ~4 600 lines. That covers the specialists' procedures, message templates, gates, loop detection, progress format, timing and the `ailsa` CLI calls.

**Must change:**
- About 110 harness-tool mentions: `case.md` 30 SendMessage + 26 Task* + 6 Team* + spawn block (~150-200 lines); `advisory-templates.md` 14; ≈ 10 lines per agent file.
- The agent frontmatter.
- One new `opencode.json`.
- One `blind_case_run_opencode.sh`.

**Effort** [ASSUMED]:

| Work item | Estimate |
|---|---|
| Port | 2-3 days |
| Calibration smoke runs | 1-2 days |
| Harness script | 0.5 day |
| **Total** | **≈ 4-6 working days** |

Add +1 day for a small generator that renders the OpenCode variant from the Claude Code source, so the two copies cannot drift.

## 5. Local models
- **Provider:** `@ai-sdk/openai-compatible` with `baseURL: http://127.0.0.1:8080/v1` (llama-server `/v1/chat/completions`). The docs show Ollama, LM Studio and llama.cpp examples [CITED: docs/providers].
- **Advantages over Claude Code + local endpoint:**
  - No Anthropic-API translation, so the attribution-header cache bug does not apply.
  - **Much smaller fixed overhead:** default prompt 8.5 KB, all tool descriptions ~15 KB, and the agent body *replaces* the default prompt. Each AILSA agent therefore starts at roughly 16-20 k tokens instead of ~30-35 k [VERIFIED byte counts; token estimate ASSUMED at ~4 chars/token]. That matters for a 27B model at 128 k.
- **Required settings:**
  - `limit.context` / `limit.output` per model; otherwise compaction misjudges the window.
  - Output cap ≥ 32 k. In a Qwen3.8-27B + OpenCode tuning report on a 3090, raising the cap from 8 k to 32 k raised task deliveries from 5/24 to 20/24 [CITED: dev.to/zjshen14; LOW, single source; it names an "OpenCode 2.0.20" that is not on npm].
  - Ollama `num_ctx` ≥ 16-32 k, though llama-server is preferable: #46506 reports Qwen3.8-27B via Ollama ~7x slower inside OpenCode.
- **Open issues relevant here:**

  | Issue | Problem | Mitigation |
  |---|---|---|
  | #53202 | Qwen3.8's llama.cpp template rejects effort `high`, and OpenCode retries the HTTP 500 five times | use `Default`, set effort server-side |
  | #24316 | Qwen3.6-35B-A3B emits "naked" tool calls inside thinking, and the run halts | none listed; weighs on the MoE fallback model |
  | #53478 | chat-template special tokens in tool output truncate turns | LSD/CLI output is unlikely to contain them |
  | #15533 | auto-compaction "Continue" loop | `OPENCODE_DISABLE_AUTOCOMPACT=1` for benchmark runs |

  [VERIFIED: GitHub issues, all open as of 2026-10-06]
- **Field evidence:** a public recipe runs Qwen3.8-27B Q4 + llama.cpp (MTP, q8 KV, 128 k) + OpenCode on one 24 GB card at ~38-40 tok/s [CITED: github.com/mikecovlee/qwen3.8-27b-24gb-recipe]. I found **no report of multi-agent, hours-long, non-coding runs** on Qwen in OpenCode.

## 6. Headless / batch
- **Replacement for `claude -p`:**
  ```
  opencode run --command ailsa/case --model llamacpp/<alias> --format json --auto "<path> <MF>"
  ```
  The JSON stream carries the session ID. Resume-on-stall becomes `opencode run --session <id> "<nudge>"`. Use `--fork` for branching [VERIFIED: `cli/cmd/run.ts`].
- **Gaps against `blind_case_run.sh`:**
  - **No `--append-system-prompt`:** put the blindness fence in an `AGENTS.md` in the scratch cwd, or in `instructions` in the config.
  - **Permissions:** headless mode **auto-rejects every `ask` permission**, and by default `external_directory` and `doom_loop` are `ask`. The dataset lies outside the scratch cwd, so pass `--auto` or set `OPENCODE_PERMISSION='{"external_directory":"allow","doom_loop":"allow"}'`.
  - **Timeouts:** no per-call timeout of its own (keep `timeout`). The bash tool defaults to **2 min**, so raise `OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS` for LSD.
- **The run exits when the parent session goes idle,** so background subagents die with it. Use foreground `task` only, which is the same lesson as the CC headless caveat.
- **Server mode:** `opencode serve` + SDK keeps background jobs alive, and their results wake the coordinator. That is closest to the push protocol, but needs a small driver.
- **Transcripts:** `opencode export <sessionID> [--sanitize]` gives JSON per session. Child sessions are exported separately via `opencode session list`.

## 7. Licence / terms
OpenCode is MIT [VERIFIED], with no restriction on which model is used, so there is no ToS question for a partner lab. By contrast, Claude Code is proprietary and Anthropic "doesn't support" non-Claude models (round 1).

Running **Opus inside OpenCode** for a calibration needs a **pay-per-token API key**. Anthropic has blocked Pro/Max subscription OAuth in third-party harnesses since 2026-04-04 [CITED: news coverage, MEDIUM].

Two further licence points:
- oh-my-openagent's SUL is non-commercial.
- Crush is FSL. Avoid both in a published method.

## 8. Verdict
**OpenCode is the better choice when:**
- the partner lab cannot or will not run Claude Code against a local model, which is a ToS comfort issue;
- context is tight (≈ 15 k fewer tokens per agent on a 27B model);
- reviewers ask whether the result depends on Claude Code: a "native open harness" arm answers that.

**Cost and risk:**
- 4-6 days of porting, plus a second copy of the skill to maintain.
- The arm changes the harness, so any difference in its results can come from the harness instead of the model.
- Experimental flags, and a v2 rewrite in progress (a `2.0` branch, `sdk-next`). **Pin v1.18.34.**

**Recommendation for the paper:**
- **Primary arm: Claude Code + local endpoint**, with the skill files unchanged and the model as the only variable.
- **OpenCode as a secondary harness arm,** only after a **calibration gate**: run the OpenCode port with **Opus 5 via API** on 10-15 already-graded datasets. Proceed only if rank-1 matches the Claude Code result within noise, i.e. no significant McNemar difference on the paired set. Only then run Qwen in OpenCode.
- This yields a small model × harness grid that separates "the method transfers" from "the harness matters".
- **If the partner lab vetoes Claude Code, swap the roles.** OpenCode becomes primary, and the calibration gate becomes mandatory, not optional.

## Assumptions log
| # | Claim | Risk if wrong |
|---|---|---|
| A1 | Port effort 4-6 days | Schedule slips; the calibration gate catches a bad port |
| A2 | ~16-20 k start tokens per agent | Less context headroom than claimed |
| A3 | Resuming another session's `task_id` from a sibling works | Irrelevant if routed via the coordinator, which is the recommended design |
| A4 | Transcript sample (169 September runs) is representative of the 256-run benchmark | Earlier runs may have used teams. They ran under the same `-p` rule, so this is unlikely |

## Sources
**Primary (HIGH):**
- [OpenCode skills](https://opencode.ai/docs/skills/)
- [OpenCode agents](https://opencode.ai/docs/agents/)
- [OpenCode commands](https://opencode.ai/docs/commands/)
- [OpenCode tools](https://opencode.ai/docs/tools/)
- [OpenCode providers](https://opencode.ai/docs/providers/)
- [OpenCode rules (Claude Code compatibility)](https://opencode.ai/docs/rules/)
- [OpenCode config](https://opencode.ai/docs/config/)
- [OpenCode CLI env vars](https://opencode.ai/docs/cli/)
- Source [anomalyco/opencode @3f393d7](https://github.com/anomalyco/opencode): `packages/opencode/src/tool/task.ts`, `task.txt`, `config/agent.ts`, `config/command.ts`, `session/prompt.ts`, `session/llm/request.ts`, `agent/agent.ts`, `cli/cmd/run.ts`, `cli/cmd/export.ts`; `packages/core/src/v1/config/{agent,command,config}.ts`
- [Claude Code agent teams (`-p` spawns no teammates)](https://code.claude.com/docs/en/agent-teams)
- [Claude Code subagents (SendMessage resume)](https://code.claude.com/docs/en/sub-agents)
- [Archived opencode-ai/opencode → Crush](https://github.com/opencode-ai/opencode)
- [Crush licence](https://github.com/charmbracelet/crush)

**Secondary (MEDIUM):**
- GitHub issues:
  - [#12711 Agent Teams design](https://github.com/anomalyco/opencode/issues/12711)
  - [#38964](https://github.com/anomalyco/opencode/issues/38964)
  - [#38963](https://github.com/anomalyco/opencode/issues/38963)
  - [#53202](https://github.com/anomalyco/opencode/issues/53202)
  - [#53478](https://github.com/anomalyco/opencode/issues/53478)
  - [#24316](https://github.com/anomalyco/opencode/issues/24316)
  - [#15533](https://github.com/anomalyco/opencode/issues/15533)
  - [#46506](https://github.com/anomalyco/opencode/issues/46506)
- Plugins:
  - [opencode-ensemble](https://github.com/hueyexe/opencode-ensemble)
  - [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)
  - [oh-my-opencode-slim](https://github.com/alvinunreal/oh-my-opencode-slim)
  - [opencode-team-plugin](https://github.com/jabr/opencode-team-plugin)
  - [opencode-agent-intercom](https://github.com/feanor5555/opencode-agent-intercom)
- [Qwen3.8-27B 24 GB recipe](https://github.com/mikecovlee/qwen3.8-27b-24gb-recipe)
- [Anthropic third-party harness block](https://news.ycombinator.com/item?id=46549823)
- [dev.to coverage](https://dev.to/mcrolly/anthropic-kills-claude-subscription-access-for-third-party-tools-like-openclaw-what-it-means-for-3ipc)

**Tertiary (LOW):**
- [Tuning a local Qwen coding agent](https://dev.to/zjshen14/tuning-a-local-qwen-coding-agent-what-changed-what-still-fails-4554)
- [Porting CC agent teams to OpenCode](https://dev.to/uenyioha/porting-claude-codes-agent-teams-to-opencode-4hol)

**Valid until** about 2026-10-20 (OpenCode ships weekly and a v2 is in progress).
