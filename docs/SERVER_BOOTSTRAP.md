# Headless CASE Host Bootstrap

Authoritative, end-to-end guide to provision a **fresh headless server** (e.g. the
`sheldon` compute host) so it can run the full autonomous CASE skill `/lucy-ng:case`
— not just the `lucy` CLI. This is the canonical "what does a CASE-capable host need"
reference; the per-package details live in [INSTALLATION.md](INSTALLATION.md).

A CASE run needs **five** things present together. Missing any one makes
`/lucy-ng:case` fail at its prerequisite gate:

1. A compatible **Python** (3.11/3.12 — **not** 3.13/3.14) + the `lucy-ng` package
2. The **LSD solver** (`LSD` + `outlsd`) on `PATH`
3. The **reference DB** (`lucy database download` → `data/reference/lucy-ng-derep.db`)
4. The **CASE skill**: the `/lucy-ng:*` commands **and the 4 team agents** symlinked into `~/.claude`
5. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in the environment (the team spawns require it)

> A one-shot installer that performs steps 1–5 lives at
> [`scripts/bootstrap_case_host.sh`](../scripts/bootstrap_case_host.sh). This document
> explains each step so the script can be audited and steps can be run by hand.

---

## 0. Prerequisites already on the host

- `git`, `tmux`, a recent **Claude Code** CLI (`claude --version`), and GSD installed in `~/.claude`.
- Outbound network to GitHub, Figshare (the DB), and `http://eos.univ-reims.fr/LSD/` (the solver).

## 1. Python — avoid 3.13/3.14

RDKit / nmrglue / numpy wheels lag the newest CPython. A bare host whose only
`python3` is 3.13+ (sheldon ships 3.14) **will fail** to install the deps. Use a
pinned 3.12 via `uv` (preferred — the repo ships a `uv.lock`) or `pyenv`.

```bash
git clone https://github.com/steinbeck/lucy-ng.git
cd lucy-ng

# Preferred: uv (reproducible from uv.lock, brings its own Python 3.12)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv sync                       # creates .venv from uv.lock
source .venv/bin/activate

# Alternative: pyenv + venv
# pyenv install 3.12.8 && pyenv local 3.12.8
# python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,mcp]"
```

### 13C prediction dependency (required for CASE ranking)

`hose-code-generator` has a broken test dep on 3.12+; install it without deps:

```bash
uv pip install "git+https://github.com/Ratsemaat/HOSE_code_generator.git" --no-deps
# (or: pip install ... --no-deps  in a plain venv)
```

### Expose `lucy` on PATH (required for CASE runs)

A CASE run starts from an NMR **data dir outside this repo**, with the venv **not
activated** — so `lucy` must be on PATH without activation. Symlink the venv
console-script into `~/.local/bin` (on PATH by default on Linux; the script has an
absolute shebang, so no activation is needed):

```bash
mkdir -p ~/.local/bin
ln -sfn "$PWD/.venv/bin/lucy" ~/.local/bin/lucy
```

## 2. LSD solver (`LSD` + `outlsd`)

The solver is an **external** download (not on PyPI). `outlsd` (SMILES conversion) is
required for ranking — without it CASE cannot produce rankable solutions.

```bash
mkdir -p ~/opt && cd ~/opt
# Fetch the current LSD release from http://eos.univ-reims.fr/LSD/ (version may differ)
# e.g.:  wget http://eos.univ-reims.fr/LSD/LSD-3.5.3.tar.gz && tar -xzf LSD-3.5.3.tar.gz
cd LSD-*/ && make 2>/dev/null || true
# put BOTH binaries on PATH (persist in the shell profile):
echo 'export PATH="$HOME/opt/'"$(basename "$PWD")"'/bin:$PATH"' >> ~/.bashrc
export PATH="$PWD/bin:$PATH"
```

Verify (this is the gate — fix until both report available):

```bash
lucy lsd check        # must show: LSD available + outlsd available
```

The `~/.bashrc` PATH entry above only applies to **interactive** shells; CASE runs in
non-interactive ones. Mirror the binaries into `~/.local/bin` so they're found from any
data dir:

```bash
for b in lsd outlsd genpos mol2ab; do ln -sfn "$(command -v "$b")" ~/.local/bin/$b; done
```

## 3. Reference database (pre-built SQLite)

CASE ranking + dereplication use one pre-built SQLite DB (~830 MB download → ~2.8 GB),
NOT raw SD files. Fetch it with the CLI (Figshare, DOI 10.6084/m9.figshare.31073554):

```bash
mkdir -p data/reference
lucy database download -o data/reference/lucy-ng-derep.db
lucy database info data/reference/lucy-ng-derep.db   # sanity-check row counts
```

`DatabaseFinder` only finds `data/reference/lucy-ng-derep.db` when the CWD is the repo.
A CASE run starts from a data dir, so symlink the DB into `~/.lucy/` — `DatabaseFinder`
checks there (step 3 of its search order) regardless of CWD. **Without this, CASE
silently falls back to a tiny bundled HOSE table (~11 matches) instead of the full
928k-compound DB:**

```bash
mkdir -p ~/.lucy
ln -sfn "$PWD/data/reference/lucy-ng-derep.db" ~/.lucy/lucy-ng-derep.db
```

## 4. Install the CASE skill (commands + agents) into `~/.claude`

The skill is the `/lucy-ng:*` **commands** PLUS the **CASE team agents**. Symlink the
repo's `.claude/` content so edits stay in sync (mirrors the dev-machine setup). Copy
instead of symlink only if you want a frozen snapshot.

```bash
REPO="$(pwd)"                       # the cloned lucy-ng checkout
mkdir -p ~/.claude/agents ~/.claude/commands

# Commands (directory symlink): case.md, references/, dereplicate/predict/sanitise/status
ln -sfn "$REPO/.claude/commands/lucy-ng" ~/.claude/commands/lucy-ng

# CASE team agents (per-file symlinks) — REQUIRED for /lucy-ng:case to spawn its team
for a in "$REPO"/.claude/agents/lucy-*.md; do
  ln -sfn "$a" ~/.claude/agents/"$(basename "$a")"
done
```

Agents linked: `lucy-nmr-chemist`, `lucy-lsd-engineer`, `lucy-solution-analyst`,
`lucy-devils-advocate` (the 4-agent team) + `lucy-diagnostic` (escalation).

> **Blind-UAT hygiene (read if this host runs blind benchmarks):** link ONLY the
> decontaminated repo `.claude/` (FIX-09 removed answer keys/dev-meta from it). Keep any
> ground-truth/answer-key manifest and compound-identity auto-memory **off the run path**
> — never in this host's `~/.claude` or in a CASE data directory a blind instance reads.

## 5. Enable agent teams

`/lucy-ng:case` spawns a multi-agent team; Claude Code requires this experimental flag:

```bash
echo 'export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1' >> ~/.bashrc
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

## 6. Verify the full CASE prerequisite chain

These are exactly the gates `case.md` checks at startup — all four must pass:

```bash
echo "$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"           # -> 1
lucy --version                                          # CLI installed
lucy lsd check                                          # LSD + outlsd available
lucy predict c13 "CCO" --format json | head -1          # DB + hosegen working
```

Then confirm they also work **from outside the repo** — a CASE run never starts in the
repo, so this is what actually exercises the `~/.local/bin` and `~/.lucy` symlinks from
§1–§3 (`predict` here must report the full DB, not a ~11-match fallback):

```bash
( cd /tmp && lucy --version && lucy lsd check && lucy predict c13 "CCO" --format json >/dev/null && echo "OK: discoverable from any dir" )
```

Then a **smoke CASE** on bundled test data (non-blind, just proves the pipeline):

```bash
cd data/Ibuprofen   # or any Bruker dir with the needed experiments
# In a fresh Claude Code session on the host:  /lucy-ng:case . C13H18O2
```

If the team spawns, runs to `final_results.md`, and `lucy lsd check`/DB/prediction all
pass, the host is CASE-capable.

---

## Provisioning checklist (copy/paste)

- [ ] `git clone` the repo; `uv sync` with Python 3.12; activate `.venv`
- [ ] `hose-code-generator` installed `--no-deps`
- [ ] LSD + outlsd on PATH (`lucy lsd check` green)
- [ ] `lucy database download` → `data/reference/lucy-ng-derep.db` (`lucy database info` ok)
- [ ] **discoverability:** `lucy` + LSD binaries symlinked into `~/.local/bin`, DB into `~/.lucy/` (so a CASE run from a data dir finds them)
- [ ] commands symlink + **agents symlinks** in `~/.claude`
- [ ] `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` persisted
- [ ] all four `case.md` prereq gates pass + a smoke CASE completes
- [ ] (blind hosts) answer-key manifest is OFF the run path

See also: [INSTALLATION.md](INSTALLATION.md) (package detail), [../CLAUDE.md](../CLAUDE.md)
(local-prerequisites + DB reference), [USER_GUIDE.md](USER_GUIDE.md).
