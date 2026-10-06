# Quick Task 261006-iob: Running the AILSA CASE skill on an open-weight model (Qwen) - Research

**Researched:** 2026-10-06
**Domain:** agent harnesses for local LLMs, local model serving, experiment design for the blind CASE benchmark
**Confidence:** MEDIUM. Harness and model facts come from official docs and model cards. Throughput and VRAM figures are partly computed or community-reported and need a smoke test on the partner lab's machine.

## Summary

The AILSA skill can run on a local Qwen model **without rewriting the method**. Claude Code takes `ANTHROPIC_BASE_URL` and sends Anthropic Messages API requests to it. llama.cpp's `llama-server`, Ollama (v0.14+), vLLM and LiteLLM all expose a compatible `/v1/messages` endpoint. The agent-teams machinery (TeamCreate, TaskCreate/TaskList/TaskUpdate, SendMessage) runs entirely in the client: mailboxes are JSON files under `~/.claude/teams/`, and tasks are files under `~/.claude/tasks/`. So the model behind the endpoint does not matter to it. Anthropic says plainly that it does not *support* routing Claude Code to non-Claude models. "Not supported" is not the same as "prohibited", though, and Qwen's own Qwen3.8-27B model card reports its agentic benchmarks "using the Claude Code harness" [CITED: huggingface.co/Qwen/Qwen3.8-27B].

Every other harness would mean rewriting the orchestrator, which mixes a harness change into a model comparison. Qwen Code comes closest. It accepts Claude-Code agent frontmatter and has an experimental Agent Team mode, but its tool names and command format differ. OpenCode and Codex `--oss` have subagents but no peer messaging or shared task list. Goose would need a full re-implementation.

Qwen3-14B is the weak link, not the harness. Its native context is 32 768 tokens (131 072 with YaRN) [CITED: huggingface.co/Qwen/Qwen3-14B]. Each AILSA agent starts with roughly 30-35 k tokens already loaded: about 20 k of Claude Code system prompt and tool definitions, plus a 10-14 k skill prompt (`case.md` is 56 KB, each agent file 18-43 KB). Qwen3-14B therefore overflows before the first tool result. Two newer models fit a 24 GB RTX 3090, both Apache-2.0 with a 262 k native context: **Qwen3.8-27B** (dense, August 2026, the strongest agentic scores) and **Qwen3.6-35B-A3B** (MoE, April 2026, 3-4x faster).

**Primary recommendation:** Claude Code, pinned to one CLI version, pointed at `llama-server` serving **Qwen3.8-27B at Q4** with a single 128 k-context slot and q8_0 KV cache. Use the unchanged AILSA skill and the existing `blind_case_run.sh` harness. The partner lab returns only the run artefacts, and the project owner grades them with `grade_blind.py`.

## Architectural Responsibility Map

| Capability | Owner | Notes |
|---|---|---|
| Agent loop, slash command, subagents, team mailboxes and task list | Claude Code CLI (client) | Model-independent. Mailboxes and tasks are local files [CITED: code.claude.com/docs/en/agent-teams] |
| Model inference | `llama-server` (or Ollama) on the 3090 | Must expose `/v1/messages`, tool use, streaming, `count_tokens` |
| Chemistry (peak picking, LSD, HOSE prediction, ranking) | `ailsa` CLI + LSD binary + reference SQLite DB | Deterministic. Identical in both arms |
| Blind batch driver | `tests/case-benchmark/blind_case_run.sh` / `blind_case_batch.py` | Already takes `CLAUDE_BIN` and `CLAUDE_MODEL` |
| Grading | `grade_blind.py` + private answer key, on the project owner's side | Never on the partner machine, which keeps the runs blind by construction |

## Q1 - Claude Code against a local model

**Works:**
- `ANTHROPIC_BASE_URL=http://<host>:<port>`, `ANTHROPIC_AUTH_TOKEN=<any>`, `ANTHROPIC_API_KEY=""`, and `--model <local-alias>`. With a gateway credential set, Claude Code does not need an Anthropic login [CITED: docs.ollama.com/integrations/claude-code; code.claude.com/docs/en/llm-gateway].
- `llama-server` has native `/v1/messages` support with SSE streaming, tool use (requires `--jinja`) and `/v1/messages/count_tokens` [CITED: huggingface.co/blog/ggml-org/anthropic-messages-api-in-llamacpp].
- Ollama ≥ 0.14 ships `ollama launch claude`, which sets the environment variables for you [CITED: docs.ollama.com/integrations/claude-code].
- vLLM and LiteLLM also translate.
- Unsloth documents Qwen3.6 with Claude Code over `llama-server` [CITED: unsloth.ai/docs/models/qwen3.6].

**What breaks or needs care:**

| Issue | Effect | Fix |
|---|---|---|
| Attribution header changes on every request | Breaks the llama.cpp prefix KV cache, so every turn re-prefills (reported ~90 % slowdown) | `"env": {"CLAUDE_CODE_ATTRIBUTION_HEADER": "0"}` in `~/.claude/settings.json`. Exporting it in the shell reportedly does **not** work [CITED: Unsloth guide via agent-wars.com, ryanorban.com] |
| Ollama default context 4 k | Silent truncation of the ~20 k system prompt and hallucinated tool calls | Set the context to ≥ 128 k (`OLLAMA_CONTEXT_LENGTH` / `num_ctx`) |
| vLLM strict role validation | Claude Code ≥ 2.1.154 sends roles vLLM 0.20.x rejects with HTTP 400 [CITED: github.com/vllm-project/vllm/issues/44000] | Prefer llama.cpp, or use a vLLM release that contains PR #44283 |
| Pinned model names | `case.md` spawns every teammate with `model="claude-opus-4-8"` (lines 162-201). Claude Code also calls a "small fast" model in the background | Set `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`/`_SONNET_`/`_HAIKU_MODEL` and `CLAUDE_CODE_SUBAGENT_MODEL` to the local alias. On CLI ≥ 2.1.257 also set `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`; before 2.1.251, `CLAUDE_CODE_SUBAGENT_MODEL` already took precedence [CITED: code.claude.com/docs/en/agent-teams]. `llama-server` with one loaded model most likely ignores the requested name [ASSUMED]. Ollama does not, so add an alias there with `ollama cp <model> claude-opus-4-8` |
| Model self-report gate | Each teammate reports a `[MODEL]` line, and the orchestrator writes "⚠ MODEL MISMATCH" when it is not `claude-opus-4-8` | A warning only. Use it as the positive control that the swap took effect |
| Agent teams in headless `-p` mode | Teammates are not spawned in `-p` mode; named agents run as ordinary subagents [CITED: agent-teams docs] | Same as the Opus benchmark runs, since `blind_case_run.sh` uses `-p`. The arms stay comparable |
| Thinking blocks | Pass-through varies by server | Control thinking server-side (`--chat-template-kwargs '{"enable_thinking":true}'`) |
| Outbound telemetry | Internal server may lack internet access | `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `DISABLE_AUTOUPDATER=1` [ASSUMED var names, standard in docs] |

**Licence and terms:** Claude Code's licence reads "© Anthropic PBC. All rights reserved. Use is subject to Anthropic's Commercial Terms of Service" [CITED: github.com/anthropics/claude-code/blob/main/LICENSE.md]. The gateway docs say Anthropic "doesn't support routing Claude Code to non-Claude models through any gateway" [CITED: code.claude.com/docs/en/llm-gateway]. That disclaims support; it is not a prohibition. I found no explicit prohibition in this session, and the setup is publicly documented by Ollama, llama.cpp, Unsloth and Qwen. Still, the partner lab should read the Commercial Terms itself [ASSUMED low risk, not a legal opinion].

## Q2 - Alternative open harnesses

| Harness | Subagents | Peer messaging / shared task list | Reads Claude-Code files | Rewrite needed for AILSA |
|---|---|---|---|---|
| **Claude Code + local endpoint** | yes | yes (client-side) | native | **none** |
| **Qwen Code** v0.25.0, Apache-2.0 | yes. Accepts CC 2.1.168 frontmatter: drop agent files into `.qwen/agents/` [CITED: qwenlm.github.io/qwen-code-docs …/sub-agents] | Experimental Agent Team since v0.18 (`QWEN_CODE_ENABLE_AGENT_TEAM=1`): named teammates, messages, shared task list [CITED: weekly update 2026-06-18] | Agents: yes. Plugins from the Claude Code marketplace convert. Commands: not confirmed | Medium. `case.md` calls TeamCreate/TaskCreate/SendMessage by name 40+ times, and those must be mapped to Qwen's tools. Whether teammates may run shell commands is undocumented (the investigator role is read-only by default) |
| **OpenCode** | yes (Task tool, `@agent`) | not documented | `.claude/skills` yes; agents only from `.opencode/agents/` [CITED: opencode.ai/docs/agents, /skills] | Large. The orchestrator has to become hub-and-spoke, with no peer messages |
| **Codex CLI `--oss`** | skills + MCP | not documented | no | Large [CITED: community guides; LOW] |
| **Goose** | parallel subagents via subrecipes; tools via MCP | no | no | Full re-implementation [CITED: goose-docs.ai; MEDIUM] |

**Verdict:** for a "does the method transfer to open weights" question, only Claude Code keeps the method fixed. Qwen Code is a sensible *second* experiment later ("native harness for native model"), but it changes two variables at once.

## Q3 - Model choice for RTX 3090 (24 GB) + 62 GB RAM

| Model | Release | Native ctx | Weights at Q4 | Full-attention KV per token* | Decode on 3090 | Fit for AILSA |
|---|---|---|---|---|---|---|
| Qwen3-14B (current) | May 2025 | 32 k (131 k YaRN) | ~9 GB | n/a | fast | **Poor.** Context too short for the ~30-35 k start, and two generations old |
| **Qwen3.8-27B** (dense, hybrid DeltaNet + gated attention, 64 layers, 16 with full attention, 4 KV heads) | 2026-08-14 | 262 k | ~17-18 GB | ~64 KB fp16 / ~32 KB q8 | ~25-42 tok/s (measured for 3.6-27B) [CITED: llmkube.com, insiderllm.com] | **Best quality.** One 128 k slot at q8 KV ≈ 4 GB: fits, tightly |
| Qwen3.6-27B | 2026-04 | 262 k | ~18 GB | same | same | Superseded by 3.8-27B |
| **Qwen3.6-35B-A3B** (MoE, 3 B active, 40 layers, 10 with full attention, 2 KV heads) | 2026-04-16 | 262 k | 17 GB (Q2_K_XL) - 23 GB (Q4_K_XL) [CITED: unsloth.ai/docs/models/qwen3.6] | ~20 KB fp16 | 120-158 tok/s at Q3, fully on GPU [CITED: HF discussion #37, insiderllm.com] | **Fast fallback.** Weaker reasoning. Q4 needs `--n-cpu-moe` expert offload into the 62 GB RAM |
| Qwen3.8-35B-A3B | spotted on ModelScope, **not released** (mid-Aug 2026) | - | - | - | - | Would be ideal if it lands |

*Computed from the model-card architecture: layers with full attention × 2 × KV heads × head_dim 256 × bytes per value. The DeltaNet layers hold a fixed-size state per slot [ASSUMED arithmetic, verify by smoke test].

Qwen3.8-27B reports SWE-bench Pro 61.7 %, Terminal Bench 2.1 73.0 % and CoWorkBench 70.7 %, evaluated in the Claude Code harness [CITED: huggingface.co/Qwen/Qwen3.8-27B]. A 3090 user running 35B-A3B reports good multi-step agentic results but notes having to "reinforce prompts, adapt my skills" where Opus works one-shot [CITED: HF Qwen3.6-35B-A3B discussion #37]. Expect the same here: following the push protocol and the strict message formats will be the main source of failure.

**Throughput pitfall:** with one server slot and five agents, every switch between agents evicts the previous agent's KV cache. The next request then re-prefills 30-100 k tokens, roughly 1-2 minutes per switch on a 27B dense model. Prefix caching on hybrid DeltaNet models in llama.cpp relies on context checkpoints, and partial-prefix reuse is limited [ASSUMED]. Budget **3-6 h per dataset** against the 30-60 min typical on Opus [ASSUMED]. Use the q8_0 or bf16 KV cache (the f16 default has been reported to degrade output), and avoid CUDA 13.2 [CITED: unsloth.ai/docs/models/qwen3.6].

## Q4 - Experiment design

Three cells of a 2×2 design (model × method) can be run, and the fourth is free:

| | AILSA method (skill + toolchain) | Plain prompt (no tools) |
|---|---|---|
| **Opus 5** | already measured for all 256 datasets (no new runs) | optional, cheap via API. Isolates the method effect on a frontier model |
| **Qwen (local)** | **arm (a)** - does the method transfer? | **arm (b)** - the partner lab's baseline |

**What must be identical across cells:**
- The same dataset sample, **drawn with a fixed seed and frozen before any run**. Stratify it by heavy-atom count, because large molecules (≥ 26 heavy atoms) fail even on Opus.
- The same input: sanitised Bruker directory + molecular formula only.
- The same output contract: `analysis/final_results.md` with up to 10 ranked SMILES.
- The same grader (`grade_blind.py`, first InChIKey block, rank 1 and top 10).
- The same `ailsa` git commit and LSD version, and one pinned Claude Code version. Record it in `meta.json`.
- A wall-clock limit equal to the Opus runs for the primary result, optionally reported again with an extended limit. Local inference is slower, and a time-out is not a chemistry failure.

**Arm (b) needs a defined input,** because an LLM without tools cannot read Bruker binaries. Recommended: the peak tables from `ailsa`'s deterministic peak picker (13C, 1H, HSQC/DEPT multiplicities, HMBC, COSY) as text, plus the formula. One prompt, thinking allowed, no tools, answer as a ranked SMILES list written in the grader's format. Say explicitly in the write-up that this baseline still uses AILSA's peak picking.

**Sample size:** 40-60 datasets gives a usable paired McNemar comparison against the existing Opus results if the effect is large (likely here) [ASSUMED]. At 3-6 h per run on one GPU, 40 datasets take about 5-10 days of continuous running.

**Minimal setup on the partner machine (Linux + CUDA):**
1. `pip install git+https://github.com/steinbeck/lucy-ng@<pinned-commit>`. The PyPI `ailsa 0.0.1` is only a name reservation, and the 0.1.0 upload is deferred, so **do not `pip install ailsa`** yet [VERIFIED: pypi.org/pypi/ailsa/json].
2. LSD binaries (`LSD`, `outlsd`) on PATH, from eos.univ-reims.fr/LSD. Check with `ailsa lsd check`.
3. Reference DB: `ailsa database download` (~830 MB, 2.8 GB unpacked, figshare DOI 10.6084/m9.figshare.31073554).
4. Claude Code CLI (npm `@anthropic-ai/claude-code`, current 2.1.291 [VERIFIED: npm view]), pinned. Skill files: copy or symlink `.claude/commands/lucy-ng/` and `.claude/agents/lucy-*.md` into `~/.claude/`. The `/ailsa:case` rename is still in flight, so pin the commit.
5. llama.cpp built with CUDA, plus the GGUF of the chosen model, then `llama-server --jinja -c 131072 -np 1 --cache-type-k q8_0 --cache-type-v q8_0 …`.
6. The sampled datasets, shipped privately **without any answer key**. The partner returns `results/<CASE>/analysis/` plus `meta.json`, and the project owner grades. This keeps the runs blind by construction and keeps compound identities off third-party machines (the public-repo rule).
7. NMRPipe is only needed if a sampled dataset is NUS. Exclude NUS datasets from the sample for simplicity [ASSUMED].

## Q5 - Recommendation

**1st choice:** Claude Code (pinned) → `llama-server` (CUDA, `--jinja`) → **Qwen3.8-27B Q4_K_M/UD-Q4_K_XL**, 128 k context, q8 KV, thinking on, `CLAUDE_CODE_ATTRIBUTION_HEADER=0` in settings.json, every model variable set to the local alias. Run the existing `blind_case_run.sh` with `CLAUDE_MODEL=<alias>`. First do 2-3 smoke runs on small datasets the owner can grade, and check the `[MODEL]` lines.
**Main risk:** the 27B model fails to follow the long push-protocol and message-format instructions (stalls, malformed `[*-COMPLETE]` messages, early stopping), so runs end with no report rather than wrong answers. The secondary risk is runtime from KV-cache thrash between agents.
**Fallback:** the same stack with **Qwen3.6-35B-A3B** (Q3/Q4, MoE offload). It is 3-4x faster and makes the sample affordable, at lower reasoning quality. If Claude Code against the local server proves unworkable, use Qwen Code with Agent Team mode, but only after porting the orchestrator, and report it as a harness change.

## Package Legitimacy Audit

No packages are added to this repository. The tools the partner lab installs are established upstream projects: Claude Code (npm `@anthropic-ai/claude-code` 2.1.291), Qwen Code (npm `@qwen-code/qwen-code` 0.25.0), vLLM (PyPI 0.31.0), llama.cpp and Ollama (GitHub binaries). slopcheck was not run because this is a quick task with no install in this repo, so all of them are [ASSUMED] for legitimacy purposes. Install from the official sites only.

## Assumptions Log

| # | Claim | Risk if wrong |
|---|---|---|
| A1 | `llama-server` with a single model ignores the requested model name | 404s on spawn. Fix with an alias or `CLAUDE_CODE_SUBAGENT_MODEL(_FORCE)` |
| A2 | KV and VRAM arithmetic; 128 k q8 slot fits next to 27B Q4 | Must drop to 64-96 k context or a smaller quant |
| A3 | 3-6 h per dataset | Sample size or schedule has to shrink |
| A4 | Using Claude Code with non-Claude models is allowed under the Commercial Terms (only "unsupported" was found) | Partner lab should confirm. Fall back to Qwen Code |
| A5 | 40-60 datasets suffice | Weaker statistics if Qwen's arms land close together |
| A6 | Hybrid-model prefix caching in llama.cpp is limited | Slower than estimated; vLLM is an alternative once the role bug is fixed |

## Sources

**Primary (HIGH):**
- [Claude Code agent teams docs](https://code.claude.com/docs/en/agent-teams)
- [Claude Code LLM gateway docs](https://code.claude.com/docs/en/llm-gateway)
- [Claude Code LICENSE](https://github.com/anthropics/claude-code/blob/main/LICENSE.md)
- [Ollama: Claude Code integration](https://docs.ollama.com/integrations/claude-code)
- [llama.cpp Anthropic Messages API](https://huggingface.co/blog/ggml-org/anthropic-messages-api-in-llamacpp)
- [Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B)
- [Qwen3.6 collection](https://huggingface.co/collections/Qwen/qwen36)
- [Qwen3.6-35B-A3B model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
- [Qwen3-14B model card](https://huggingface.co/Qwen/Qwen3-14B)
- [Qwen Code subagents](https://qwenlm.github.io/qwen-code-docs/en/users/features/sub-agents/)
- [Qwen Code Agent Team update](https://qwenlm.github.io/qwen-code-docs/en/blog/updates/weekly-update-2026-06-18/)
- [OpenCode agents](https://opencode.ai/docs/agents/)
- [OpenCode skills](https://opencode.ai/docs/skills/)

**Secondary (MEDIUM):**
- [Unsloth Qwen3.6 guide](https://unsloth.ai/docs/models/qwen3.6)
- [vLLM issue #44000](https://github.com/vllm-project/vllm/issues/44000)
- [Attribution-header KV-cache bug](https://agent-wars.com/news/2026-03-13-unsloth-guide-exposes-claude-code-bug-local-model-performance)
- [3090 report for 35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/37)
- [Qwen 3.6 local guide](https://insiderllm.com/guides/qwen-3-6-local-ai-guide/)
- [Qwen3.6-27B consumer-GPU bake-off](https://llmkube.com/blog/qwen3-6-27b-bakeoff)
- [Qwen 3.5-3.8 overview](https://codersera.com/blog/qwen-3-5-complete-guide-2026/)
- [Goose providers](https://goose-docs.ai/docs/getting-started/providers/)

**Tertiary (LOW):**
- [Codex CLI `--oss` guides](https://ynaito.dev/en/writing/codex-cli-local-models-oss/)
- [Claude Code + local LLM gist](https://gist.github.com/renezander030/39249215616a095d74fe6c66b0348641)

**Valid until:** about 2026-10-20. Model releases and CLI versions move fast; re-check whether Qwen3.8-35B-A3B has shipped.
