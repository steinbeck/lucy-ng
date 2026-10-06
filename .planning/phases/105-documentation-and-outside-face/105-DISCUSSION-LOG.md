# Phase 105: Documentation and outside face - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-06
**Phase:** 105-documentation-and-outside-face
**Areas discussed:** Old-name note, Commands before the rename, Deck numbers, figshare and peripheral documents

---

## Old-name note

| Option | Description | Selected |
|--------|-------------|----------|
| One neutral sentence | "developed under the working title lucy-ng", no reason, no origin | |
| Sentence with reason | adds why it was renamed | |
| Sentence plus migration note | name + short section for existing users | |

**User's choice:** Free text — asked where the sentence would go and why it is needed at all ("Nur wegen der git history?"). After the explanation (old links/redirect, `lucy` alias, old DB file name, deck already shown) and a proposal to place it as an upgrade note in the installation section: **drop it entirely and strike the requirement.**
**Notes:** "Nur sehr wenige kennen lucy-ng und ich möchte mit der Veröffentlichung einen Neuanfang. Der Name lucy-ng soll möglichst weitgehend verschwinden."

| Option | Description | Selected |
|--------|-------------|----------|
| Mention nowhere | docs know only `ailsa` / `ailsa-derep.db`; legacy works silently | ✓ |
| Only in CLAUDE.md | developer note so nobody deletes the compat code | |
| Short line in installation guide | one line for existing users | |

---

## Commands before the rename

| Option | Description | Selected |
|--------|-------------|----------|
| Final names now | /ailsa:*, ailsa-* agents, github.com/steinbeck/ailsa; a few days of mismatch | ✓ |
| Today's names, update later | always correct, but 106/107 re-edit the docs | |
| Rename commands/repo first | reorder the roadmap | |

| Option | Description | Selected |
|--------|-------------|----------|
| PyPI upload after the repo rename | end of milestone; every link in the frozen README works | ✓ |
| Directly after this phase | as originally planned; dead links for a few days, frozen until next release | |

---

## Deck numbers

| Option | Description | Selected |
|--------|-------------|----------|
| Own benchmark slide | method, 69 % rank 1, comparison with previous model, large-molecule limit | ✓ |
| Only one number on the numbers slide | replace "8/9" | |

| Option | Description | Selected |
|--------|-------------|----------|
| Keep CASE1–9 slide as examples | retitle from "test set" to examples | ✓ |
| Drop it | benchmark slide carries the message alone | |

---

## figshare and peripheral documents

**figshare route — first ask:** user asked whether a figshare token already exists and to record the answer in memory. Searched env, shell rc files, keychain, git history, `.planning/`, saved session transcripts and the vault: none (vault holds only a login note). Recorded in memory `reference_figshare_token`.

| Option | Description | Selected |
|--------|-------------|----------|
| User edits in browser, Claude drafts | no write token lying around; ~5 minutes | ✓ |
| Create a new token | Claude edits via API, shows diff first | |

| Option | Description | Selected |
|--------|-------------|----------|
| Maintain or remove | rename what is needed, git rm ballast after approval | ✓ |
| Rename everything, delete nothing | rewrites dated drafts | |
| Dated documents stay unchanged | old name stays visible in the repo | |

---

## Claude's Discretion

- Deck: Lineage box → "Get it" box; "12 milestones" tile → current fact; PDF renamed `ailsa-infographics.pdf`.
- Metadata text in `scripts/figshare_upload.py` / `scripts/zenodo_upload.py` updated.
- figshare file name renamed only if possible without a new upload.
- README wording and structure.

## Deferred Ideas

- `~/.lucy` home directory still used in `src/ailsa/database/finder.py` — code, not docs.
- Phase 107's "changelog entry explaining the rename" conflicts with the fresh-start intent — revisit in 107.
