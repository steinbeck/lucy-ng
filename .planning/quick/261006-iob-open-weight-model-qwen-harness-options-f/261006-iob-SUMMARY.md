---
phase: quick-261006-iob
plan: 01
status: complete
subsystem: research / collaboration
tags: [open-weight, qwen, claude-code, llama.cpp, benchmark-design]
requires: [261006-iob-RESEARCH.md]
provides: [reply draft to collaborator thread (in mailbox, not in repo)]
affects: []
key-files:
  created:
    - .planning/quick/261006-iob-open-weight-model-qwen-harness-options-f/261006-iob-SUMMARY.md
  modified: []
decisions:
  - "Recommend Claude Code against a local llama-server as the harness for the open-weight arm, so that only the model changes"
  - "Recommend Qwen3.8-27B (Q4, 128k context) over Qwen3-14B; Qwen3.6-35B-A3B as the fast fallback"
metrics:
  completed: 2026-10-06
  tasks: 2
  files: 1
---

# Quick Task 261006-iob: Open-weight model (Qwen) harness options - Summary

German reply draft created for the collaborator thread: AILSA runs unchanged under Claude Code pointed at a local llama-server, with Qwen3.8-27B recommended in place of the too-short-context Qwen3-14B.

## What the research concluded

The AILSA skill does not need rewriting to run on an open-weight model. Claude Code can send its Anthropic Messages API requests to a local server (llama.cpp `llama-server` with `--jinja`, or Ollama 0.14+). The agent-team machinery runs on the client side, so it does not depend on the model. Qwen Code is the only alternative harness with agent teams, and it would need the orchestrator ported, which changes harness and model at once. Qwen3-14B is too short-context, because each agent starts at roughly 30-35k tokens against a 32k native window. On a 24 GB RTX 3090 the recommendation is Qwen3.8-27B at Q4 with a 128k context and q8 KV cache, and Qwen3.6-35B-A3B is the faster fallback. The proposed design has two Qwen arms: inside AILSA, and with a plain prompt plus text peak lists. It runs on a blind, stratified sample of 40-60 datasets that is fixed in advance, and grading stays on the project owner's side.

## Outcome

- A German reply draft was saved in the uni-jena drafts folder. It is threaded to the original message, the tool quoted the original underneath, and the collaborators are in To/Cc.
- **Nothing was sent.** The draft is waiting for the user to review and send it.
- No repository files changed except this SUMMARY. No commits were made by the executor.

## Caveats to check before sending

- **Licence:** the research found only Anthropic's "not supported" for non-Claude models, no prohibition. That is not a legal opinion. The draft asks the partner lab to read the terms itself.
- **VRAM fit:** the claim that a 128k q8 KV slot fits next to 27B Q4 on 24 GB is computed, not measured. A smoke test may force 64-96k context.
- **Runtime:** "several hours per dataset" is an estimate (3-6 h in the research), and KV-cache thrash between agents is the main uncertainty.
- **Length:** the own text is about 400 words, at the upper end of the target range.
- The draft offers a step-by-step setup note and small test datasets. These do not exist yet and would be a follow-up task if the offer is accepted.

## Deviations from Plan

None. The plan was executed as written, and the draft was created exactly once.

## Self-Check: PASSED

- Draft tool reported "Draft saved to uni-jena:Drafts" with In-Reply-To set.
- SUMMARY contains no names, addresses, subject line or quotes.
