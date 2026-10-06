---
phase: quick-261006-iob
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/261006-iob-open-weight-model-qwen-harness-options-f/261006-iob-SUMMARY.md
autonomous: true
requirements:
  - QUICK-261006-iob

must_haves:
  truths:
    - "A German reply to the collaborator thread exists as a DRAFT in the uni-jena drafts folder, threaded to the original message (In-Reply-To set, original quoted underneath)"
    - "The draft answers the collaborators' question from the research: the AILSA skill runs unchanged under Claude Code pointed at a local llama-server; Qwen3-14B is too short-context; Qwen3.8-27B is the recommended model, Qwen3.6-35B-A3B the fast fallback; Qwen Code is the only alternative harness with agent teams and needs an orchestrator port"
    - "Nothing was sent; no repo file contains collaborator names, addresses, quotes or compound identities"
  artifacts:
    - path: "/private/tmp/claude-501/-Users-steinbeck-Dropbox-develop-lucy-ng/b66cec6e-73e0-4091-906c-19f603b4e3f1/scratchpad/email-draft.txt"
      provides: "German email body (own answer only, no quoted original)"
    - path: ".planning/quick/261006-iob-open-weight-model-qwen-harness-options-f/261006-iob-SUMMARY.md"
      provides: "Task summary without personal details"
  key_links:
    - from: "scratchpad/email-draft.txt"
      to: "life_email.py draft -a uni-jena --reply-to <UID>"
      via: "stdin"
      pattern: "life_email.py draft"
---

<objective>
Turn the finished research (261006-iob-RESEARCH.md) into one German email DRAFT that replies to the collaborator thread about running the AILSA CASE skill on an open-weight Qwen model.

Purpose: the collaborators asked which harness supports skills plus agents and how to run the skill on their local Qwen setup. The research answers that; this plan delivers the answer as a reply draft the user reviews and sends himself.
Output: a draft in the uni-jena mailbox, threaded to the original message, plus a SUMMARY.md in the quick-task directory. No code or other repo changes.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/261006-iob-open-weight-model-qwen-harness-options-f/261006-iob-RESEARCH.md

Personal context lives OUTSIDE the repo (the repository is public):
/private/tmp/claude-501/-Users-steinbeck-Dropbox-develop-lucy-ng/b66cec6e-73e0-4091-906c-19f603b4e3f1/scratchpad/email-context.md

That file, supplied by the orchestrator, holds: recipients (To and Cc), the subject line, the UID of the message being replied to (and its mail folder if not INBOX), the user's style with these recipients (salutation, sign-off, Du/Sie, language), the content outline, and a self-check checklist. It is authoritative for everything personal and for tone. The RESEARCH.md is authoritative for technical content. If email-context.md is missing, STOP and report back; do not guess recipients or the UID.

Mail tool interface (verified with `draft --help`):
- `python3 ~/Dropbox/develop/life-ai/tools/life-email/life_email.py draft -a <account> --to <addr> [--cc <a,b>] -s <subject> [--reply-to <UID>] [-f <folder>] [-b <body> | body via stdin]`
- With `--reply-to` the tool appends the quoted original automatically (German style "Am ... schrieb ...:"). The body must therefore contain ONLY the user's own answer.
- `-f/--folder` names the folder that holds the reply-to message; pass it only if email-context.md says the original is not in INBOX.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write the German reply body to the scratchpad and self-check it</name>
  <files>/private/tmp/claude-501/-Users-steinbeck-Dropbox-develop-lucy-ng/b66cec6e-73e0-4091-906c-19f603b4e3f1/scratchpad/email-draft.txt</files>
  <action>
Read email-context.md (scratchpad path above) in full, then the Summary, Q1, Q2, Q3 and Q5 sections of 261006-iob-RESEARCH.md. Write the email body as plain text to scratchpad/email-draft.txt, never into the repo.

Language, salutation, sign-off, Du/Sie and tone come exclusively from the style notes in email-context.md (the user's established style with these recipients). Follow its content outline in its order. Where the outline is silent, the technical substance to convey, in plain German and without project jargon, is:
1. Harness: the skill runs unchanged under Claude Code when it is pointed at a local server that speaks the Anthropic Messages API (llama.cpp `llama-server` with `--jinja`, or Ollama 0.14+). The agent team (shared task list, messages between agents) runs on the client side, so the model behind it does not matter. Anthropic does not support this setup but does not forbid it either; Qwen itself benchmarks its models in Claude Code. Their lab should read the Commercial Terms themselves.
2. Alternatives: Qwen Code reads Claude-Code agent files and has an experimental agent-team mode, but the orchestrator would have to be ported, which changes harness and model at once. OpenCode, Codex `--oss` and Goose lack peer messaging between agents.
3. Model: Qwen3-14B is too small in context (32k native; each agent starts at roughly 30-35k tokens). Recommended on the RTX 3090: Qwen3.8-27B at Q4 with a 128k context and q8 KV cache; fast fallback Qwen3.6-35B-A3B.
4. Practical pitfalls worth one line each: set `CLAUDE_CODE_ATTRIBUTION_HEADER=0` in settings.json (otherwise the KV cache is rebuilt on every turn), raise Ollama's default context, set all model variables to the local alias, expect several hours per dataset.
5. Next step / experiment shape only as far as email-context.md asks for it (e.g. small smoke test first, datasets shipped without answer key, grading on our side).

Keep it as long as needed and no longer; an email, not a report. Use concrete names (model names, tool names, flags) but no internal identifiers, phase numbers, task codes or file paths from this repo. Never name any benchmark compound or dataset identity. Do not include the quoted original; the mail tool adds it.

Then run the checklist from email-context.md against the file item by item and fix any failure. Additionally confirm: no "Sie" if the style is Du (or vice versa), no internal IDs matching the pattern of letters-dash-digits such as D-01 or T-25-03, no emojis.
  </action>
  <verify>
    <automated>F=/private/tmp/claude-501/-Users-steinbeck-Dropbox-develop-lucy-ng/b66cec6e-73e0-4091-906c-19f603b4e3f1/scratchpad/email-draft.txt; test -s "$F" && grep -q "Qwen3.8-27B" "$F" && grep -qi "llama" "$F" && grep -q "Qwen Code" "$F" && ! grep -Eq '\b[A-Z]{1,4}-[0-9]{2}(-[0-9]{2})?\b' "$F" && ! grep -q '^>' "$F" && echo OK</automated>
  </verify>
  <done>email-draft.txt exists, is in German, follows the salutation/sign-off/tone in email-context.md, covers harness, alternatives, model choice and pitfalls, passes every item of the email-context.md checklist, contains no quoted original, no internal identifiers and no compound identities.</done>
</task>

<task type="auto">
  <name>Task 2: Create the reply draft in the uni-jena mailbox and write the SUMMARY</name>
  <files>.planning/quick/261006-iob-open-weight-model-qwen-harness-options-f/261006-iob-SUMMARY.md</files>
  <action>
Take To, Cc, subject, reply-to UID (and folder, if given) from email-context.md. Create the draft by piping email-draft.txt into the mail tool: `python3 ~/Dropbox/develop/life-ai/tools/life-email/life_email.py draft -a uni-jena --to <to> --cc <cc> -s "<subject>" --reply-to <UID>` (add `-f <folder>` only if email-context.md names one; omit `--cc` only if it lists no Cc). Run it exactly once. NEVER send, and never use Gmail or MCP mail tools (user's global rule: all mail via life_email.py, drafts only).

Read the tool output and confirm it reports the draft as saved. If it errors (e.g. UID not found), fix the cause, for example the folder, and retry once; if it still fails, stop and report the exact error rather than creating an unthreaded draft. If a retry might have created a duplicate, say so in the report so the user can delete one.

Then write 261006-iob-SUMMARY.md in the quick-task directory: what the research concluded (one short paragraph), that a German reply draft was created in the uni-jena drafts folder for the collaborator thread and is awaiting the user's review and sending, and any caveats the user should check before sending (for example the assumptions flagged in the research: licence reading, VRAM fit, runtime per dataset). The SUMMARY must contain NO recipient names, email addresses, subject line, quotes from the thread, or compound identities, because the repository is public.
  </action>
  <verify>
    <automated>S=/Users/steinbeck/Dropbox/develop/lucy-ng/.planning/quick/261006-iob-open-weight-model-qwen-harness-options-f/261006-iob-SUMMARY.md; test -s "$S" && ! grep -Eq '@[A-Za-z0-9.-]+\.[a-z]{2,}' "$S" && grep -qi "draft\|Entwurf" "$S" && echo OK</automated>
  </verify>
  <done>The mail tool reported the draft as saved in the uni-jena account with --reply-to set (so it is threaded and quotes the original); nothing was sent; SUMMARY.md exists, states the draft awaits the user's review, and contains no personal details or addresses.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| scratchpad -> public repo | Personal data (names, addresses, quotes) lives only in the scratchpad; the repo is public |
| executor -> mailbox | The executor writes into the user's real mailbox |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-iob-01 | Information disclosure | PLAN.md / SUMMARY.md | mitigate | No names, addresses, subject or quotes in repo files; Task 2 verify greps the SUMMARY for email addresses |
| T-iob-02 | Information disclosure | email body | mitigate | Task 1 forbids benchmark compound/dataset identities in the email (public-repo and blind-benchmark rule) |
| T-iob-03 | Repudiation / irreversible action | life_email.py | mitigate | Only the `draft` subcommand is used; no send command anywhere in the plan; user sends himself |
| T-iob-04 | Tampering | wrong thread | mitigate | UID taken from email-context.md; on failure stop instead of creating an unthreaded draft |
</threat_model>

<verification>
- Draft exists in the uni-jena drafts folder, threaded to the collaborator thread, body in German in the user's established style with these recipients.
- No email was sent.
- `git status` shows only the new SUMMARY.md (plus this PLAN.md) under the quick-task directory; no other repo files changed.
</verification>

<success_criteria>
- One German reply draft, created via life_email.py with --reply-to, covering harness choice, alternatives, model choice and practical pitfalls from the research.
- SUMMARY.md written, free of personal details.
- Zero repo changes outside the quick-task directory.
</success_criteria>

<output>
Create `.planning/quick/261006-iob-open-weight-model-qwen-harness-options-f/261006-iob-SUMMARY.md` when done (Task 2).
</output>
