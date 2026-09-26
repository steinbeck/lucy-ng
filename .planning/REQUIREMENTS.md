# Requirements — Milestone v11.0 AILSA Rename

**Goal:** rename the project from the working title *lucy-ng* to **AILSA** (*AI + LSD + Agents*) everywhere it is visible, without breaking the running benchmark or rewriting the historical record.

**Ordering constraint:** the skill system and the repository (SKILL-*, REPO-*) may only change after the Opus-5 baseline re-run on the compute host has finished — the blind runner there calls `/lucy-ng:case`, and the watchdog on the Mac runs from the absolute path `…/lucy-ng/scripts/`. Package and documentation (PKG-*, DOC-*) can go first.

## v11.0 Requirements

### Package and CLI (PKG)

- [ ] **PKG-01**: A user can `pip install ailsa` from PyPI and get the real package (replacing the 0.0.1 name-reservation placeholder), with `pyproject.toml` naming the project `ailsa`.
- [ ] **PKG-02**: A developer imports everything from the Python module `ailsa`; no `lucy_ng` module or import remains in `src/`, `tests/` or `scripts/`.
- [ ] **PKG-03**: A user runs every subcommand as `ailsa …`; `lucy …` still works for one release and prints a one-line deprecation hint pointing to `ailsa`.
- [ ] **PKG-04**: The full test suite passes on the renamed tree with the same pass count as before (1345 passed / 74 environment failures), and `mypy --strict` and `ruff` report no new findings.
- [ ] **PKG-05**: A user with the existing database file `data/reference/lucy-ng-derep.db` keeps working; `ailsa database download` and `ailsa database info` accept the old file name as well as the new default.

### Documentation and outside face (DOC)

- [ ] **DOC-01**: A reader of the README sees the project as AILSA, with the expansion *AI + LSD + Agents*, LSD and Jean-Marc Nuzillard credited up front, and a short note that the project was formerly called lucy-ng.
- [ ] **DOC-02**: `docs/` (ARCHITECTURE, USER_GUIDE, BENCHMARK, NUS-PORTABILITY and the rest) and `CLAUDE.md` refer to the project, package, CLI and commands by the new names; no living document still instructs the reader to type `lucy`.
- [ ] **DOC-03**: The figshare record of the reference database carries the new project name in title and description; the DOI and the uploaded file are unchanged.
- [ ] **DOC-04**: The infographic deck (`docs/infographics/build.py`) is rebuilt under the new name with the current headline numbers (this also clears the "stale deck" backlog item).

### Skill system (SKILL)

- [ ] **SKILL-01**: A user runs `/ailsa:case`, `/ailsa:dereplicate`, `/ailsa:predict`, `/ailsa:sanitise` and `/ailsa:status`; the `/lucy-ng:*` commands are gone and the symlinks under `~/.claude/commands` point at the new directory.
- [ ] **SKILL-02**: The five agents are `ailsa-nmr-chemist`, `ailsa-lsd-engineer`, `ailsa-solution-analyst`, `ailsa-devils-advocate` and `ailsa-diagnostic`; `case.md`, the supervisor and the SHA-256 byte-unchanged guard reference the new files, and the `~/.claude/agents` symlinks are updated.
- [ ] **SKILL-03**: One blind CASE run on the compute host, started through the renamed command with the renamed agents, completes and grades correctly — the proof that the chain works under the new name.
- [ ] **SKILL-04**: The blind runner script and the watchdog scripts call the new command and paths, and the LaunchAgent (label, program path, log name) is re-registered under the new name.

### Repository and hosts (REPO)

- [ ] **REPO-01**: The GitHub repository is `steinbeck/ailsa`; the old URL redirects; the remotes of the local clone and of the compute host's checkout point at the new name.
- [ ] **REPO-02**: The local working copy lives at `~/Dropbox/develop/ailsa`; the auto-memory directory is moved with it so the next session starts with its memory; every absolute path on the Mac (LaunchAgent, symlinks, scripts) is updated.
- [ ] **REPO-03**: `.planning/PROJECT.md`, `STATE.md`, `ROADMAP.md`, `MEMORY.md` and the CASE identity/UAT files speak the new name; `.planning/phases/` history, `milestones/`, git history and the compute host's result directories are untouched.
- [ ] **REPO-04**: A release tag `v11.0` marks the first release under the new name, with a changelog entry explaining the rename.

## Future Requirements

- Backlog items untouched by the rename: sanitiser hardening and the constraint-traceability check (publication needs both), PROV-01, JVAL-F2, spec `49057ef`, tags `v4.0`/`v5.0`.

## Out of Scope

- **Rewriting git history** — the old name stays in every historical commit; the user decided on 2026-09-09 never to rewrite published history.
- **Rewriting `.planning/phases/` and `milestones/`** — 344 files and 6,646 mentions of the old name are the record of how the project was built; they stay.
- **Renaming result directories on the compute host** (`case-uat-results*`) — historical arms, read-only.
- **The manuscript** — lives in the private repository `steinbeck/ailsa-paper`.
- **A new figshare upload** — the 830 MB database file and its DOI stay; only the record's text changes.

## Traceability

| Requirement | Phase |
|-------------|-------|
| PKG-01 | 104 |
| PKG-02 | 104 |
| PKG-03 | 104 |
| PKG-04 | 104 |
| PKG-05 | 104 |
| DOC-01 | 105 |
| DOC-02 | 105 |
| DOC-03 | 105 |
| DOC-04 | 105 |
| SKILL-01 | 106 |
| SKILL-02 | 106 |
| SKILL-03 | 106 |
| SKILL-04 | 106 |
| REPO-01 | 107 |
| REPO-02 | 107 |
| REPO-03 | 107 |
| REPO-04 | 107 |
