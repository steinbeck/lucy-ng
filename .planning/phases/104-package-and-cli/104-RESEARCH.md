# Phase 104: Package and CLI - Research

**Researched:** 2026-10-02
**Domain:** Python packaging (hatchling/uv/PyPI), Click CLI entry points, mechanical module rename
**Confidence:** HIGH (every claim below is either `[VERIFIED]` by a command run in this session against this exact repo, or `[CITED]` against this repo's own source)

## Summary

This phase is a mechanical rename plus two small pieces of real engineering: a deprecated-CLI-alias
shim and a database-filename backward-compatibility layer. There is no new technology to evaluate —
`hatchling` (already the build backend), `uv` (already the project's package manager) and `click`
(already the CLI framework) do everything needed. The risk in this phase is not technical difficulty,
it is **completeness** (missing one of ~130 `lucy-ng` string occurrences or ~90 `lucy_ng` module
references across `src/`, `tests/`, `scripts/`) and **not touching what is out of scope** (the
`.claude/` skill tree is protected by a committed SHA-256 byte-unchanged test and must not be touched
by this phase under any circumstances).

Two runtime-state facts, discovered by inspecting this actual machine (not assumed), drive the design
of PKG-05: `data/reference/lucy-ng-derep.db` is a real 3.97 GB file sitting in this working tree right
now, and `data/reference/lucy-ng-fragments.db` (605 MB, not named in the requirements but used by the
same `DatabaseFinder`-adjacent pattern) is also real and present. Both must keep resolving after the
rename without forcing a multi-gigabyte re-download. The mechanism already supports this cleanly: the
`database info` command takes an **explicit path argument** (`click.Path(exists=True)`) so it already
accepts any filename — only the **default path logic** in `DatabaseFinder`/`cli/database.py` needs to
search both the legacy and new names.

The baseline was measured directly in this session (not taken from the 2026-09-23 STATE.md note,
though it reproduces it exactly): **1345 passed, 74 failed, 86 skipped, 1 xfailed** (1506 collected)
`[VERIFIED: pytest run, this session]`. All 74 failures are pre-existing environment gaps (missing
`hosegen`, missing `webview` extra, a `CliRunner(mix_stderr=...)` incompatibility with the installed
Click 8.4.2) — none are product bugs, and none are caused by or related to the rename. `ruff check`
reports 282 pre-existing findings and `mypy --strict` reports 33 pre-existing import errors (all from
optional extras not installed in this dev venv) `[VERIFIED: ruff/mypy run, this session]`. The
planner's job is to reproduce these exact counts after the rename, not to fix them.

**Primary recommendation:** `git mv src/lucy_ng src/ailsa`, then a scripted find/replace pass over
`lucy_ng` -> `ailsa` and `lucy-ng` -> `ailsa` (two separate patterns, case-sensitive) restricted to
`src/`, `tests/`, `scripts/verify_case_solution.py`, `scripts/render_jcamp_spectra.py`, `pyproject.toml`
and the two `schemas/*.json` copies — explicitly excluding `.claude/`, `README.md`, `docs/`, `CLAUDE.md`,
`.planning/`, `scripts/figshare_upload.py`, `scripts/zenodo_upload.py`, `scripts/bootstrap_case_host.sh`,
`scripts/uat_watchdog.py`, `scripts/launchd/*` and `tests/case-benchmark/*` (all Phase 105/106/107
territory, detailed in the scope table below). Add a second `[project.scripts]` entry (`lucy`) that
prints one deprecation line to **stderr** and delegates to the same Click group, so `--format json`
stdout consumers (the CASE agents) are unaffected.

<user_constraints>
## User Constraints (from plan-time decisions)

> No `.planning/phases/104-package-and-cli/104-CONTEXT.md` exists (no `/gsd-discuss-phase` run for
> this phase) — these are the locked decisions the orchestrator supplied directly at research-launch
> time instead. Treat them with the same authority as a CONTEXT.md `## Decisions` section.

### Locked Decisions
- Plan directly from requirements; the planner decides small implementation details itself.
- The actual upload to PyPI is public and irreversible: it must be a separate, human-gated step
  (`checkpoint:human-verify` or equivalent, awaiting explicit user approval), never done
  autonomously. The PyPI name `ailsa` is already reserved by the user (placeholder `0.0.1`,
  https://pypi.org/project/ailsa/); `~/.pypirc` holds an account-wide token.
- Research how the project builds/publishes today (hatch) and what the version number should be —
  addressed in this document's Standard Stack / Open Questions sections (`hatch` CLI is not actually
  installed; `uv build` + `twine upload` is the recommended mechanism).

### Claude's Discretion
- Small implementation details of the rename mechanics (exact grep/sed scripting, file edit order,
  whether to use `git mv` per-file or per-directory, test file organization for new PKG-03/PKG-05
  tests).
- Whether to extend the dual-filename backward-compatibility treatment (built for PKG-05's named
  `lucy-ng-derep.db`) to the unnamed-but-equivalent `lucy-ng-fragments.db` (recommended in Pitfall 7,
  not mandated by the literal requirement text).
- `~/.lucy` config-directory name and the five `LUCY_*` env var names: recommended to leave unchanged
  in this phase (Assumptions A2/A3) since neither is named in any success criterion and both are real
  runtime state outside this phase's edit scope; flagged as Open Questions rather than decided here.

### Deferred Ideas (OUT OF SCOPE for this phase)
- Phase 105: README/docs/`CLAUDE.md`/figshare record/infographic deck — any text-only "outside face"
  renaming.
- Phase 106: the skill system (`.claude/commands/lucy-ng/*`, `.claude/agents/lucy-*.md`) — protected
  by a committed SHA-256 byte-unchanged test (Pitfall 1); must not be touched by this phase.
- Phase 107: repository rename, local folder path, LaunchAgent, remotes, compute-host checkout.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|---------------------|
| PKG-01 | `pip install ailsa` installs the real package; `pyproject.toml` names the project `ailsa` | Standard Stack (uv build/twine mechanism, hatch CLI absence); Validation Architecture test map row |
| PKG-02 | Every import in `src/`, `tests/`, `scripts/` comes from `ailsa`; no `lucy_ng` module/import remains anywhere | Recommended Project Structure; Code Examples (acceptance-gate grep command); exact occurrence counts (86 in `src/`, 89 in `tests/`, 2 in `scripts/`) gathered this session |
| PKG-03 | Every subcommand runs as `ailsa ...`; `lucy ...` still works for one release and prints a one-line deprecation hint pointing at `ailsa` | Architecture Pattern 1 (full code sketch); Pitfall 8 (webview subprocess launcher fallback order); Validation Architecture test map row |
| PKG-04 | Full test suite passes with the same pass count (1345 passed / 74 environment failures), `mypy --strict`/`ruff` report no new findings | Baseline measured directly this session (1345 passed, 74 failed, 86 skipped, 1 xfailed; 33 mypy errors; 282 ruff errors); Pitfall 4 (don't try to "fix" pre-existing findings); Pitfall 5 (slow real-data test handling) |
| PKG-05 | `data/reference/lucy-ng-derep.db` keeps working; `ailsa database download`/`ailsa database info` accept the old file name as well as the new default | Architecture Pattern 2 (dual-name resolver design); Runtime State Inventory (confirms the real 3.97 GB file); Pitfall 7 (fragments DB has the same risk, not literally required but recommended) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Package identity (`pyproject.toml` name/version) | Build/Packaging | — | `hatchling` build backend reads this; PyPI identity is declared here |
| Module tree (`src/lucy_ng` -> `src/ailsa`) | Library/Core | — | Every other tier imports from here; must move first |
| CLI entry points (`ailsa`, deprecated `lucy`) | CLI | Library/Core | Click `[project.scripts]` wires console scripts to `ailsa.cli:cli` |
| Database default-path resolution | Library/Core (`database/finder.py`) | CLI (`cli/database.py`) | Resolution logic lives in the library; the CLI only supplies the `--output`/`db_path` default constant |
| Deprecation hint delivery | CLI (stderr only) | — | Must never touch stdout — stdout is a machine-readable JSON contract for the CASE agents (Phase 106, out of scope but must not regress) |
| PyPI publish | Build/Packaging (human-gated) | — | `uv build` + `twine upload` (or `uv publish`), executed only on explicit user approval |

## Standard Stack

### Core (already in use — no new runtime dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hatchling | build-backend per `pyproject.toml` `[build-system]` | Build backend | Already the declared backend; `uv build` invokes it automatically, no change needed |
| click | 8.4.2 `[VERIFIED: uv run python -c "import click; print(click.__version__)"]` | CLI framework | Already in use for the single `cli` group; supports multiple `[project.scripts]` entries pointing at different callables in the same module |
| uv | 0.9.17 `[VERIFIED: uv --version]` | Package manager / build frontend / publisher | Already the project's installer (`uv.lock` present); `uv build` and `uv publish` work without installing the separate `hatch` CLI |

### Supporting (dev-only, for the publish step)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| twine | 6.2.0, confirmed installed system-wide and via `uvx` `[VERIFIED: twine --version; slopcheck OK]` | Upload to PyPI | Reads `~/.pypirc` automatically (already configured with a `[pypi]` token) — simpler than configuring `UV_PUBLISH_TOKEN` for `uv publish` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `twine upload dist/*` | `uv publish` | `uv publish` needs `UV_PUBLISH_TOKEN` or `--token`; `~/.pypirc` is in the classic twine/setuptools format and is not read by `uv publish` by default. Using twine avoids a second credential path. |
| Installing the standalone `hatch` CLI | `uv build` | `hatch` (the CLI, distinct from `hatchling` the library) is **not installed** on this machine `[VERIFIED: command -v hatch fails]`, despite `CLAUDE.md`/`README.md` documenting `hatch build`. `uv build` reads the same `[build-system]` declaration and produces identical artifacts with zero new installs. Recommend `uv build` for this phase; updating the documented command is Phase 105's job (`CLAUDE.md`/`README.md` are DOC-02/DOC-01 scope). |

**Installation:** No new dependencies to install for the rename itself. For the publish step (human-gated, separate task): `twine` is already present; nothing to add to `pyproject.toml`'s `dev` extra unless the planner wants it pinned there for reproducibility (optional, low-value since publishing happens once per release from a human's machine, not CI).

**Version verification:** `pip index versions ailsa` confirms the PyPI placeholder is `0.0.1` only, summary "AILSA — AI + LSD + Agents: agentic Computer-Assisted Structure Elucidation of natural products from NMR data (name reservation)" `[VERIFIED: pip index + PyPI JSON API, this session]`. Current `pyproject.toml` version is `0.1.0` for `lucy-ng` `[VERIFIED: pyproject.toml read]` — `0.1.0 > 0.0.1`, so **no version bump is strictly required** to satisfy "higher than the placeholder". See Open Questions for the version-number recommendation.

## Package Legitimacy Audit

This phase adds **zero new runtime dependencies**. The only package touched is `twine`, already
installed, used solely for the human-gated publish step (not part of the automated plan).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| twine | PyPI | mature (pypa project, 10+ yrs) | very high | github.com/pypa/twine | `[OK]` `[VERIFIED: slopcheck install twine, this session]` | Approved (already installed, no pyproject.toml change required) |

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                    pyproject.toml
                 (name="ailsa", scripts)
                          |
                          v
        +-----------------------------------+
        |   console entry points (uv/pip)   |
        |   ailsa -> ailsa.cli:cli          |
        |   lucy  -> ailsa.cli:lucy_deprecated  (stderr warning, then delegates)
        +-----------------------------------+
                          |
                          v
              src/ailsa/cli/main.py :: cli (click.Group)
                          |
          +---------------+----------------------------+
          |                                             |
          v                                             v
   database group (cli/database.py)          every other cli/*.py group
          |                                   (read, pick, lsd, nus, ...)
          v
   DatabaseFinder.find_derep_database()
   (src/ailsa/database/finder.py)
          |
          v
   search order: LUCY_DATABASE env var (kept, see Pitfall 6)
     -> data/reference/ailsa-derep.db (new default)
     -> data/reference/lucy-ng-derep.db (legacy name, same directory)
     -> ~/.lucy/{ailsa,lucy-ng}-derep.db
     -> mdfind / Dropbox dev fallback (both filenames)
          |
          v
   data/reference/lucy-ng-derep.db  <-- REAL 3.97 GB file on this machine today
   [VERIFIED: ls -la data/reference/, this session]
```

A reader can trace the primary flow: a user types `ailsa database info` (or `lucy database info`,
deprecated) -> Click dispatches into the same `cli` group regardless of which entry point was
invoked -> `DatabaseFinder` resolves a path checking both the new default name and the legacy name in
the same directory -> the existing 3.97 GB file is found with zero re-download.

### Recommended Project Structure
```
src/
└── ailsa/                  # git mv src/lucy_ng src/ailsa (126 tracked files, no symlinks, no perm issues)
    ├── __init__.py          # package docstring, __version__, __all__ — rewrite "lucy_ng" references
    ├── cli/
    │   ├── __init__.py      # re-exports `cli` (add `lucy_deprecated` if defined here)
    │   ├── main.py           # click.Group `cli`; version_option prog_name -> "ailsa"
    │   └── ...                # 17 other command modules, all `from ailsa...` imports
    ├── database/
    │   └── finder.py          # DEFAULT_DB_PATH / HOME_DB_PATH -> dual-name search (PKG-05 crux)
    ├── fragments/              # same dual-filename concern for lucy-ng-fragments.db (see Pitfall 7)
    ├── webview/static/         # index.html has 2 cosmetic "lucy-ng" text occurrences
    └── ...                      # analysis, data, dereplication, detection, lsd, models, nmrxiv,
                                  # nus, prediction, processing, ranking, readers, solvers,
                                  # visualization — all import lucy_ng.* internally, no exceptions found
```

### Pattern 1: Deprecated CLI alias that never touches stdout

**What:** A second `[project.scripts]` entry pointing at a thin wrapper function that writes one line
to stderr, then calls the exact same Click group object used by the real entry point.

**When to use:** Exactly this situation — a renamed CLI where the old binary name must keep working
for one release, and where some callers (here: the CASE agent team via `--format json`) parse stdout
as a machine-readable contract and must never see the warning.

**Why this matters more than it looks:** `scripts/case-benchmark/blind_case_run.sh` and the live
`.claude/commands/lucy-ng/case.md` orchestrator invoke `lucy ... --format json` and parse the captured
stdout as JSON `[CITED: src/lucy_ng/webview/server.py comment "fall back to python -m lucy_ng.cli"
and this repo's own CLAUDE.md "every one supports --format json"]`. A deprecation line on stdout would
silently corrupt every JSON-parsing caller during the whole Phase 106 transition window — this is a
hard constraint, not a style preference.

**Example (new file content, `src/ailsa/cli/main.py`):**
```python
# Source: this repo's existing cli/main.py pattern, extended per PKG-03
import click
from ailsa import __version__
# ... existing command imports, all from `ailsa.cli.*` ...

@click.group()
@click.version_option(version=__version__, prog_name="ailsa")
def cli() -> None:
    """ailsa: AI-powered Computer-Assisted Structure Elucidation.
    ...
    """

# ... cli.add_command(...) calls unchanged ...


def lucy_deprecated() -> None:
    """Deprecated alias for the ``ailsa`` command.

    Prints a one-line warning to STDERR (never stdout -- `--format json`
    callers, including the CASE agent team, parse stdout as a machine
    contract) and then delegates to the identical ``cli`` group.
    """
    click.echo(
        "Warning: `lucy` is deprecated and will be removed in a future "
        "release; use `ailsa` instead.",
        err=True,
    )
    cli()
```
```toml
# pyproject.toml
[project.scripts]
ailsa = "ailsa.cli:cli"
lucy = "ailsa.cli:lucy_deprecated"
```
`src/ailsa/cli/__init__.py` must export both names (`from ailsa.cli.main import cli, lucy_deprecated`)
for the entry point string `ailsa.cli:lucy_deprecated` to resolve.

### Pattern 2: Backward-compatible default-path resolution (PKG-05)

**What:** `DatabaseFinder.find_derep_database()` (`src/ailsa/database/finder.py`) currently hardcodes
a single filename, `lucy-ng-derep.db`, at every search tier. Change it to try **both** names at each
existing tier, new name first, in the same directories already searched — do not add new search
locations, do not change the search *order* of tiers, only widen each tier's filename check.

**When to use:** Exactly PKG-05's stated requirement — "accept the old file name as well as the new
default" — without forcing a re-download of the verified 3.97 GB local file.

**Example (modification sketch, not literal diff):**
```python
# Source: src/lucy_ng/database/finder.py (existing structure), widened per PKG-05
class DatabaseFinder:
    NEW_DB_NAME = "ailsa-derep.db"
    LEGACY_DB_NAME = "lucy-ng-derep.db"  # PKG-05: must keep resolving, no migration forced

    @staticmethod
    def find_derep_database() -> Path | None:
        # 1. LUCY_DATABASE env var kept working (Pitfall 6) -- checked first, unchanged
        # 2. data/reference/: try NEW_DB_NAME, then LEGACY_DB_NAME
        # 3. ~/.lucy/: try both names
        # 4. mdfind: search for NEW_DB_NAME OR LEGACY_DB_NAME
        # 5. Dropbox dev fallback: try both names
        ...
```
The `database download` command's own logic already does the hard part for free: it extracts
"whatever file in the zip ends in `.db`" into the **caller-chosen `--output` path**
`[VERIFIED: src/lucy_ng/cli/database.py lines ~255-266, this session]` — so renaming
`DEFAULT_DB_PATH` to point at `data/reference/ailsa-derep.db` does not touch the figshare archive's
internal filename at all. The only remaining risk is the **default** behaving badly for a user who
already has the legacy file: if `download` (no `--output` given) is pointed at the new default name
and the legacy file already exists one path over, a naive implementation downloads 830 MB
unnecessarily. Recommend: `download`'s own default-output resolution should call the same
dual-name-aware finder logic (if the legacy file already exists and `--output` wasn't given
explicitly, treat it as "already exists" — print the existing-database message, not re-download).

`database info DB_PATH` already takes an **explicit required argument** typed `click.Path(exists=True)`
`[VERIFIED: src/lucy_ng/cli/database.py info() signature, this session]` — it accepts literally any
filename today with zero code change. PKG-05's "accepts the old file name" clause is satisfied for
`info` by definition; only `download`'s *default* and the auto-detection helpers need the dual-name
widening.

### Anti-Patterns to Avoid
- **Keeping a `lucy_ng` shim package that re-exports from `ailsa`:** success criterion 2 is explicit —
  "no `lucy_ng` module or import remains anywhere in the tree." A compatibility shim would violate this
  literally; do not build one. (It would also be redundant: nothing outside the skill system and host
  scripts — both explicitly deferred to Phases 106/107 — imports `lucy_ng` in Python; the `lucy` CLI
  alias, not a module shim, is what carries backward compatibility.)
- **Renaming `~/.lucy` to `~/.ailsa`:** out of scope and riskier than it looks. `~/.lucy` is a real
  directory on this machine today containing a symlinked `nmrshiftdb.sd`
  `[VERIFIED: ls -la ~/.lucy, this session]`, and four separate source files
  (`database/finder.py`, `prediction/resolver.py`, `cli/dereplicate.py`, `cli/lsd.py`) hardcode
  `Path.home() / ".lucy"` as a cache/config directory. None of PKG-01..05's success criteria mention
  this directory. Renaming it would require either a migration step (copying/symlinking the old
  directory, itself a judgment call outside "small implementation details") or silently breaking any
  user who already has files there. **Recommend leaving `~/.lucy` unchanged in this phase** — flagged
  as an open question below for explicit confirmation, not decided unilaterally here.
- **Touching `.claude/` in this phase:** `tests/test_skill_files_unchanged.py` freezes `case.md` and
  the five `lucy-*.md` agent files by committed SHA-256 hash specifically to catch unintended edits.
  Any edit to those files — even a pure rename of `lucy_ng` path mentions in prose — fails that test
  immediately and is explicitly Phase 106's job, not this phase's.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Building sdist/wheel | A custom `setup.py` or manual zip | `uv build` (already configured via `[build-system] requires = ["hatchling"]`) | Zero new config; `hatchling` already knows how to find `src/ailsa` once `[tool.hatch.build.targets.wheel].packages` is updated |
| Detecting whether `hatch` CLI is needed | Installing `hatch` just to run `hatch build`/`hatch publish` | `uv build` + `twine upload dist/*` | `hatch` (the CLI) is not installed here and is a separate tool from `hatchling` (the build backend); `uv` already does both steps without it |
| Verifying the module rename is complete | A manual visual scan | `grep -rn "lucy_ng" src/ tests/ scripts/` returning zero hits, run as a plan acceptance gate | Exhaustive, scriptable, matches success criterion 2's literal wording |

**Key insight:** every tool needed for this phase is already a declared or installed dependency of the
project. The only genuinely new code is the ~10-line deprecated-alias wrapper and the dual-filename
widening of `DatabaseFinder` — everything else is mechanical renaming.

## Runtime State Inventory

> Rename phase — this section is required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/reference/lucy-ng-derep.db` — **3,970,023,424 bytes (3.97 GB), real file, present now** `[VERIFIED: ls -la data/reference/, this session]`. Also `data/reference/lucy-ng-fragments.db` (605 MB) and `data/reference/lucy-ng-derep.db.zip` (829 MB, the downloaded archive, can be deleted or left). | Code edit only (dual-name resolver, Pattern 2 above) — no data migration; do not rename or move either `.db` file |
| Live service config | PyPI: the `ailsa` 0.0.1 name-reservation placeholder already exists and is owned by this user `[VERIFIED: pip index versions ailsa / PyPI JSON API, this session]`. The real publish (replacing it) is the human-gated checkpoint, not an automated plan task. | Human action at publish time (outside this phase's automated scope) |
| OS-registered state | None touched by this phase. (`~/.lucy` directory, LaunchAgent, host checkouts are Phase 106/107 territory — see scope table.) | None for this phase |
| Secrets/env vars | `LUCY_DATABASE`, `LUCY_NO_WEBVIEW`, `LUCY_NUS_TEST_DATA`, `LUCY_PY_VERSION`, `LUCY_LSD_URL` — five env vars read by code/scripts today `[VERIFIED: grep -rn "LUCY_[A-Z_]*" src/ tests/ scripts/, this session]`. `~/.pypirc` already holds a `[pypi]` token unrelated to any `LUCY_`/`AILSA_` naming — no change needed there. | See Pitfall 6 — code edit, backward-compat decision needed per var |
| Build artifacts | `.venv` has an editable install tied to the old name: `.venv/lib/python3.12/site-packages/_editable_impl_lucy_ng.pth`, `lucy_ng-0.1.0.dist-info/`, and the generated script `.venv/bin/lucy` `[VERIFIED: find .venv -iname "*lucy*", this session]`. These do not auto-update when `pyproject.toml`'s name changes. | Re-run `uv sync --extra dev` (or equivalent) after the rename to regenerate; stale dist-info left behind is a known false-positive-import trap (Pitfall 5) |

**Nothing found in category "secrets requiring value rotation":** none of the five `LUCY_*` env vars
or the `.pypirc` token need their *values* changed — only, potentially, their *names* (open design
question, see Pitfall 6).

## Common Pitfalls

### Pitfall 1: Touching `.claude/` breaks a committed byte-unchanged guard
**What goes wrong:** Any edit to `.claude/commands/lucy-ng/case.md` or the five
`.claude/agents/lucy-*.md` files — even changing `lucy_ng` path mentions in prose — fails
`tests/test_skill_files_unchanged.py`'s parametrized SHA-256 comparison.
**Why it happens:** Phase 102 deliberately froze these files by committed hash specifically to catch
unintended edits to the autonomous CASE orchestrator's instructions (`[CITED: tests/test_skill_files_unchanged.py` docstring, this session]`).
**How to avoid:** Do not include `.claude/` in this phase's find/replace scope, full stop. Updating
these files and their frozen hashes is explicitly Phase 106's job.
**Warning signs:** `test_skill_files_unchanged.py::test_skill_files_are_byte_unchanged[...]` failing
after a plan task that was supposed to be scoped to `src/`/`tests/`/`scripts/`.

### Pitfall 2: Stale editable-install artifacts shadow the renamed package
**What goes wrong:** After `git mv src/lucy_ng src/ailsa` and the `pyproject.toml` edits, `import ailsa`
can still fail, or old entry-point scripts (`.venv/bin/lucy`) can still point at the stale
`lucy_ng-0.1.0.dist-info`'s recorded console-script metadata, if the venv isn't resynced.
**Why it happens:** `uv`'s editable install mechanism writes a `.pth` file and a `.dist-info` directory
keyed to the **old** package name (`_editable_impl_lucy_ng.pth`, `lucy_ng-0.1.0.dist-info/`)
`[VERIFIED: find .venv, this session]`; renaming source files on disk does not touch these.
**How to avoid:** After the `pyproject.toml`/source rename, run `uv sync --extra dev` (reinstalls
cleanly, uv removes stale editable metadata as part of a lockfile-driven sync) or, if problems persist,
`rm -rf .venv && uv sync --extra dev` for a guaranteed-clean rebuild. Verify with
`uv run python -c "import ailsa; print(ailsa.__file__)"` and `uv run which ailsa` / `uv run which lucy`
before running the test suite.
**Warning signs:** `ModuleNotFoundError: No module named 'ailsa'` despite the source tree looking
correct, or `lucy --version`/`ailsa --version` resolving to a cached/stale script.

### Pitfall 3: `uv.lock` is already dirty in the working tree — unrelated to this phase
**What goes wrong:** `git status` shows `M uv.lock` before this phase starts
`[VERIFIED: git status --porcelain, this session]` — a 558-line diff adding `contourpy` and other
transitive deps, almost certainly from a prior local `uv sync --extra webview` or similar, never
committed.
**Why it happens:** Someone (a prior session) resolved extras locally without committing the lockfile
update.
**How to avoid:** This is **not this phase's problem to fix or avoid** — but the plan's Wave 0 should
note the pre-existing dirty state so a later `git diff uv.lock` during this phase's own work isn't
misattributed to the rename. If the rename phase needs to touch `pyproject.toml`'s `name`/`packages`
fields, `uv sync` will regenerate `uv.lock`'s own `[[package]] name = "lucy-ng"` entry (the project's
self-entry) to `"ailsa"` as a side effect — expected and in-scope; the pre-existing unrelated diff is
not.
**Warning signs:** A code reviewer conflating the pre-existing dirty `uv.lock` with the rename's own
(expected, small) lockfile changes.

### Pitfall 4: `mypy`/`ruff` baselines are not clean today — don't try to "fix" them
**What goes wrong:** A plan task that runs `mypy --strict`/`ruff check` after the rename and sees
non-zero output might assume something broke and start "fixing" unrelated pre-existing issues.
**Why it happens:** `mypy src/lucy_ng` reports **33 errors in 24 files today**, before any rename —
all `import-untyped`/`import-not-found` for optional extras not installed in this dev venv
(`nmrglue`, `tqdm`, `hosegen`, `scipy`, `fastapi`, `matplotlib`)
`[VERIFIED: uv run --extra dev mypy src/lucy_ng, this session]`. `ruff check src tests` reports
**282 pre-existing findings** (119 line-too-long, 59 unused-import, 37 unsorted-imports, 23
raise-without-from, plus smaller categories) `[VERIFIED: uv run --extra dev ruff check src tests --statistics, this session]`.
**How to avoid:** Success criterion 4 says "no **new** findings" — the acceptance gate is
`(error count after rename) <= (error count before rename)`, checked per-tool, not "zero errors."
Capture the exact baseline numbers (33 mypy errors / 282 ruff errors) as a Wave-0 task output and diff
against them at the end, rather than aiming for a clean report.
**Warning signs:** A plan task scoped to "fix all ruff/mypy issues" — that is explicit scope creep
beyond PKG-04's literal wording.

### Pitfall 5: The slow real-data test dominates naive "run the full suite" timing
**What goes wrong:** `tests/test_database_importer.py::TestDatabaseImporter::test_import_coconut_real`
has **no limit parameter** despite its own comment claiming otherwise ("Full import takes too long for
tests") — it imports the **entire** 4.7 GB `data/reference/predicted_coconut.sdf` (present on this
machine) with `batch_size=1000` and no row cap `[VERIFIED: tests/test_database_importer.py lines
287-303, this session]`. A first full-suite run in this session was killed after >5 minutes still
stuck inside this one test.
**Why it happens:** `pytest.mark.skipif(not COCONUT_FILE.exists(), ...)` only skips when the file is
*absent*; on a dev machine with the full reference data present (as this one has), the test runs for
real, unbounded.
**How to avoid:** For fast iteration, run `pytest -k "not test_import_coconut_real"` — confirmed in
this session to complete the **entire rest of the 1506-test suite in 79 seconds**
`[VERIFIED: this session, exact command below]`. Reserve the full (slow) run, including this one test,
for the final phase-gate check, or accept that this single test alone may add many extra minutes to a
"full suite" CI-style run on a machine with the real reference data present.
**Warning signs:** A pytest run that appears hung at ~25% progress with no error.

### Pitfall 6: Renaming `LUCY_*` env vars breaks anything already using the old names
**What goes wrong:** `LUCY_DATABASE`, `LUCY_NO_WEBVIEW`, `LUCY_NUS_TEST_DATA` are read by both
library code and tests `[VERIFIED: grep -rn "LUCY_[A-Z_]*", this session]`;
`tests/case-benchmark/blind_case_run.sh` exports `LUCY_NO_WEBVIEW` (line 85) and is explicitly
Phase 106/107 territory (benchmark harness calling `/lucy-ng:case`) — if Phase 104 renames the env var
the code reads without a compatibility fallback, that script silently stops suppressing the webview
dashboard the next time it runs, before Phase 106 has touched it.
**Why it happens:** Env var names are a cross-cutting contract between code and scripts that live in
different phases of this same milestone.
**How to avoid:** Two defensible options, **flagged here as an open decision, not decided
unilaterally**: (a) keep the `LUCY_*` names entirely unchanged in this phase (lowest risk, these are
not literally named in any PKG-01..05 success criterion), or (b) introduce `AILSA_*` names that are
checked first, falling back to the legacy `LUCY_*` name with a one-time stderr notice, mirroring the
`lucy`/`ailsa` CLI pattern. Given PKG-01..05's success criteria name only the package, module, CLI
command and DB filename — not env vars — **recommend option (a)** for this phase (do nothing to the
env var names) and revisit in Phase 106/107 if/when `scripts/` env var naming is in scope there.
**Warning signs:** A benchmark or watchdog script silently losing its opt-out/override behavior after
this phase, with no test coverage catching it (these scripts have no pytest coverage).

### Pitfall 7: `lucy-ng-fragments.db` has the identical default-path risk as the derep DB, but isn't named in PKG-05
**What goes wrong:** `cli/fragment.py`'s `DEFAULT_FRAGMENTS_DB = Path("data/reference/lucy-ng-fragments.db")`
has the exact same shape as the derep DB's `DEFAULT_DB_PATH` — and a real 605 MB file exists at that
path on this machine today `[VERIFIED: ls -la data/reference/, this session]` — but PKG-05's literal
wording only names `data/reference/lucy-ng-derep.db`.
**Why it happens:** The requirement was written against the primary (derep) database; the fragments
database is a separate, smaller subsystem added later (Phase 49-54, Fragment Library milestone) that
happens to share the same naming convention.
**How to avoid:** Apply the identical dual-name-resolution treatment (Pattern 2) to
`DEFAULT_FRAGMENTS_DB` for consistency and to avoid a silent future bug report — this is a
small, mechanical extension of work already being done for the derep DB, not separate scope. Flagged
as a recommendation for the planner's discretion since it is not literally required by PKG-05's
wording, but leaving it inconsistent (derep DB backward-compatible, fragments DB not) would be an odd
asymmetry with no justification found in research.
**Warning signs:** A future `lucy fragment search`/`lucy fragment info` call failing to auto-find the
existing fragments DB after this phase, while the derep DB auto-finds correctly.

### Pitfall 8: `shutil.which("lucy")` in the webview subprocess launcher should prefer `ailsa` first
**What goes wrong:** `src/lucy_ng/webview/server.py` picks a subprocess launcher via
`if shutil.which("lucy"): launcher = ["lucy"] else: launcher = [sys.executable, "-m", "lucy_ng.cli"]`
`[VERIFIED: src/lucy_ng/webview/server.py lines 99-106, this session]`. After the rename, if this is
mechanically changed to check `"ailsa"` only, editable/dev installs where only the deprecated `lucy`
script happens to be on PATH (unlikely but possible during the transition) silently fall through to
the slower `-m` invocation instead of using the available entry point.
**Why it happens:** A naive find/replace of the string `"lucy"` -> `"ailsa"` in this file is correct
for the primary path but loses the fallback.
**How to avoid:** Three-tier check: `ailsa` on PATH -> `lucy` on PATH (still valid during the
deprecation window) -> `python -m ailsa.cli`. See Pattern 1's architecture diagram.
**Warning signs:** Webview dashboard subprocess launch silently using the slower `-m` path in
environments where the deprecated `lucy` script is actually available.

## Code Examples

### Verifying the module rename is complete (acceptance-gate grep)
```bash
# Source: this session, designed against success criterion 2's literal wording
grep -rn "lucy_ng" src/ tests/ scripts/ --include="*.py" | grep -v __pycache__
# Must return zero lines when the rename is complete.
# NOTE: scripts/figshare_upload.py, scripts/zenodo_upload.py, scripts/uat_watchdog.py,
# scripts/bootstrap_case_host.sh do NOT import lucy_ng in Python today [VERIFIED, this session] --
# only scripts/verify_case_solution.py and scripts/render_jcamp_spectra.py do, and both are
# in this phase's scope (generic scripts, not host/skill-specific).
```

### Fast dev-loop test command (excludes the one unbounded real-data test)
```bash
# Source: this session -- confirmed exact numbers
uv run --extra dev pytest -q -p no:cacheprovider -k "not test_import_coconut_real"
# Result on this machine, pre-rename baseline:
# 74 failed, 1344 passed, 86 skipped, 1 deselected, 1 xfailed, 12 warnings in 79.00s
# (the 1 deselected test, run separately/rarely, would add 1 to "passed" for 1345 total --
#  matching the 1345/74/86 figure already recorded in STATE.md/ROADMAP.md exactly)
```

### mypy/ruff baseline commands (for the Wave-0 "capture baseline" task)
```bash
uv run --extra dev mypy src/lucy_ng   # 33 errors today, baseline -- becomes `src/ailsa` after rename
uv run --extra dev ruff check src tests   # 282 errors today, baseline (unaffected by rename, directories unchanged)
```

### Build + publish mechanism (for the human-gated checkpoint, NOT an automated task)
```bash
# Source: this session -- hatch CLI confirmed absent, uv build/twine confirmed to work with existing
# pyproject.toml [build-system] declaration (hatchling) with zero new config beyond the rename itself
uv build                     # produces dist/ailsa-<version>-py3-none-any.whl + dist/ailsa-<version>.tar.gz
twine upload dist/*          # reads ~/.pypirc [pypi] token automatically, already configured
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `hatch build`/`hatch publish` (documented in README.md/CLAUDE.md) | `uv build` + `twine upload` | Discovered this session: `hatch` CLI was never actually installed on this machine | No functional change to the built artifact (same `hatchling` backend); only the invoking command differs. Updating the documented command in README/CLAUDE.md is Phase 105 scope. |
| Single `[project.scripts]` entry (`lucy`) | Two entries (`ailsa` primary, `lucy` deprecated) | This phase | Standard, well-supported pattern — multiple console-script entries pointing at different callables in the same package is native `pyproject.toml`/setuptools/hatchling behavior, nothing exotic |

**Deprecated/outdated:** None specific to this phase's domain beyond the `hatch` CLI documentation
drift noted above (pre-existing, not caused by this phase).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | New version number should be the existing `0.1.0` (no bump needed since it already exceeds the `0.0.1` placeholder) rather than a fresh `1.0.0` | Standard Stack / Open Questions | Low — either choice satisfies "higher than placeholder"; this is purely a judgment call about how the version number should read externally, explicitly deferred to the human-gated publish checkpoint per the task's own instructions |
| A2 | `~/.lucy` config/cache directory name should stay unchanged (not renamed to `~/.ailsa`) | Don't Hand-Roll / Anti-Patterns | Medium if wrong — leaving it as `~/.lucy` means the renamed package reads from a directory whose name no longer matches the project; but renaming it risks breaking the real symlinked file already there (`~/.lucy/nmrshiftdb.sd`) without an explicit migration step, and no success criterion mentions this directory |
| A3 | `LUCY_*` env var names stay unchanged in this phase (no `AILSA_*` introduced yet) | Pitfall 6 | Medium if wrong — if the planner instead renames these, `tests/case-benchmark/blind_case_run.sh` (out of this phase's edit scope, Phase 106/107 territory) would silently lose its `LUCY_NO_WEBVIEW` opt-out until that later phase catches up |
| A4 | `data/reference/lucy-ng-fragments.db`'s default path should receive the same dual-name treatment as the derep DB, even though PKG-05 only names the derep DB literally | Pitfall 7 | Low if wrong (worst case: minor follow-up fix later) — but leaving it inconsistent is also a real, if small, usability regression for a file confirmed to exist on this machine today |

## Open Questions

1. **What PyPI version number should ship first?**
   - What we know: current `pyproject.toml` says `0.1.0`; the PyPI placeholder is `0.0.1`;
     `0.1.0 > 0.0.1` already satisfies "the real package, not the placeholder."
   - What's unclear: whether the user wants a fresh start (e.g. `1.0.0`, signaling "first real
     public release of a mature tool" — the project has 1345 passing tests and a 69% solved-rate
     benchmark) or to just continue the existing `0.x` scheme unchanged.
   - Recommendation: keep `0.1.0` as the default in the plan (zero extra work, satisfies every literal
     requirement), but surface this as an explicit confirmation point at the human-gated publish
     checkpoint rather than deciding silently — this is exactly the kind of judgment call the task's
     own instructions reserve for the user.

2. **Should `~/.lucy` and the five `LUCY_*` env vars be renamed in this phase or a later one?**
   - What we know: neither is named in any PKG-01..05 success criterion; both are real, working state
     on this machine today; renaming either without a migration path risks silent breakage of scripts
     this phase is explicitly not allowed to touch (`tests/case-benchmark/blind_case_run.sh`,
     `scripts/bootstrap_case_host.sh`).
   - What's unclear: whether "small implementation details the planner decides" (per the task's own
     framing) is meant to cover this, or whether it crosses into a decision the user should make.
   - Recommendation: leave both unchanged in Phase 104 (Assumptions A2/A3 above); if the user wants
     them renamed, that is cleanly deferrable to Phase 106 or 107 where the adjacent host/skill files
     are already in scope.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | build, publish, dev workflow | ✓ | 0.9.17 | — |
| hatchling | build backend | ✓ (declared in `[build-system]`, resolved transparently by `uv build`) | per `uv.lock` | — |
| hatch (standalone CLI) | documented (`hatch build`) but not actually needed | ✗ `[VERIFIED: command -v hatch fails]` | — | `uv build` (no install needed) |
| twine | PyPI upload | ✓ (both system `/opt/miniconda3/bin/twine` and via `uvx`) | 7.0.0 (uvx)/6.2.0 (system) | — |
| click | CLI framework | ✓ | 8.4.2 | — |
| `~/.pypirc` configured | publish auth | ✓ (`[pypi]` section with token) | — | — |
| webview extra (`fastapi`/`uvicorn`/`matplotlib`) | 5 of the 74 baseline test failures | ✗ (not installed in this dev venv) | — | pre-existing gap, not this phase's concern (baseline already accounts for these 5 failures) |
| `hosegen` package | 42 of the 74 baseline test failures | ✗ | — | pre-existing gap, not this phase's concern |

**Missing dependencies with no fallback:** none block this phase's work.

**Missing dependencies with fallback:** `hatch` CLI (fallback: `uv build`, already the recommendation).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest, configured via `[tool.pytest.ini_options]` in `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| Config file | `pyproject.toml` (no separate `pytest.ini`/`conftest.py`-level config beyond `tests/conftest.py`, `tests/nus/conftest.py`) |
| Quick run command | `uv run --extra dev pytest -q -p no:cacheprovider -k "not test_import_coconut_real"` — **79s, verified this session** |
| Full suite command | `uv run --extra dev pytest -q -p no:cacheprovider` — includes the unbounded real-data import test; budget 10+ minutes on a machine with `data/reference/predicted_coconut.sdf` present |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| PKG-01 | `pyproject.toml` names the project `ailsa`; package installs | smoke | `uv run python -c "import ailsa; print(ailsa.__file__)"` + `grep -q 'name = "ailsa"' pyproject.toml` | N/A — shell/grep check, no new test file needed |
| PKG-02 | No `lucy_ng` module/import remains in `src/`, `tests/`, `scripts/` | grep acceptance gate | `grep -rn "lucy_ng" src/ tests/ scripts/ --include="*.py" \| grep -v __pycache__` returns empty | N/A — grep check |
| PKG-03 | `ailsa ...` works; `lucy ...` works + prints stderr deprecation hint; stdout untouched | unit + CLI | New test(s) in `tests/test_cli_main.py` (or a new `tests/test_cli_deprecated_alias.py`): `CliRunner().invoke(lucy_deprecated, ["--format", "json", ...])` asserting `result.output` (stdout) is clean JSON/unaffected and the warning appears only via a separate stderr-capturing invocation | ✅ `tests/test_cli_main.py` exists, extend it; ❌ a stderr-specific assertion path may need a small new test |
| PKG-04 | Full suite passes with the same pass count; mypy/ruff report no new findings | full-suite regression | `uv run --extra dev pytest -q -p no:cacheprovider` (compare counts to 1345/74/86/1 baseline below); `uv run --extra dev mypy src/ailsa` (compare to 33-error baseline); `uv run --extra dev ruff check src tests` (compare to 282-error baseline) | N/A — count comparison, not a single test file |
| PKG-05 | `database download`/`database info` accept both old and new DB filenames | unit | New tests in `tests/test_database.py` or `tests/test_cli_database.py`: construct a tmp dir with a file named `lucy-ng-derep.db` only, assert `DatabaseFinder.find_derep_database()` finds it; same for a file named `ailsa-derep.db` only | ✅ `tests/test_database.py`/`tests/test_cli_database.py` exist, extend them |

### Sampling Rate
- **Per task commit:** `uv run --extra dev pytest -q -p no:cacheprovider -k "not test_import_coconut_real"` (79s baseline)
- **Per wave merge:** same fast command, plus `grep -rn "lucy_ng" src/ tests/ scripts/ --include="*.py"` acceptance gate
- **Phase gate:** full suite including the real-data test (`uv run --extra dev pytest -q -p no:cacheprovider`, no `-k` filter) + `mypy --strict` + `ruff check` count comparison against the baselines captured in this research

### Wave 0 Gaps
- [ ] Capture and record the exact baseline numbers as a committed artifact before any rename edit:
      `1345 passed, 74 failed, 86 skipped, 1 xfailed` (full suite), `33` mypy errors, `282` ruff errors
      — **already measured in this research session**, but the plan's Wave 0 should re-run and record
      them as its own first task output (cheap, 79s, and removes any doubt about environment drift
      between research time and execution time).
- [ ] New test(s) for the `lucy` deprecated-alias stderr-only behavior (PKG-03) — no existing test
      covers this exact contract.
- [ ] New test(s) for `DatabaseFinder`'s dual-filename resolution (PKG-05) — existing
      `tests/test_database.py`/`tests/test_cli_database.py` test the single-name behavior only.

*(No framework install gap — pytest, mypy, ruff are all already configured and working.)*

## Security Domain

> `security_enforcement` is absent from `.planning/config.json` — treated as enabled per the protocol default. This phase has essentially no new attack surface: it is a rename plus a CLI deprecation shim plus a filename-resolution widening.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no | N/A — no auth surface touched |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | marginal | `DatabaseFinder`'s widened filename search still only reads local filesystem paths under existing, already-trusted search roots (`data/reference/`, `~/.lucy/`, Dropbox dev path) — no new untrusted input source introduced. `database download`'s zip extraction already restricts to members ending in `.db` and excludes `__MACOSX` `[VERIFIED: cli/database.py, this session]` — unchanged by this phase. |
| V6 Cryptography | no | N/A — no crypto touched; `~/.pypirc` token handling is delegated entirely to `twine`, never read or logged by this phase's own code |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Zip-slip during `database download` extraction | Tampering | Already mitigated pre-existing: extraction targets a hardcoded `output` path via `shutil.copyfileobj`, never `ZipFile.extractall()` with archive-controlled paths `[VERIFIED: cli/database.py download(), this session]` — unaffected by this phase, no new risk introduced |
| Deprecation-hint leaking onto stdout and corrupting a JSON parser | Tampering (of the data contract, not an attacker) | Pattern 1 above — hardcode `err=True` on the one `click.echo()` call added for PKG-03; add the explicit stdout-cleanliness test named in the Validation Architecture table |

## Sources

### Primary (HIGH confidence — verified directly against this repo/machine in this session)
- `pyproject.toml`, `src/lucy_ng/cli/main.py`, `src/lucy_ng/cli/__init__.py`, `src/lucy_ng/cli/__main__.py`, `src/lucy_ng/__init__.py` — read in full, this session
- `src/lucy_ng/database/finder.py`, `src/lucy_ng/cli/database.py`, `src/lucy_ng/identity.py`, `src/lucy_ng/fragments/db.py`, `src/lucy_ng/cli/fragment.py`, `src/lucy_ng/prediction/resolver.py`, `src/lucy_ng/webview/server.py` — read in full/relevant sections, this session
- `tests/test_skill_files_unchanged.py`, `tests/test_cli_main.py`, `tests/test_database_importer.py` — read in full/relevant sections, this session
- `grep -rc "lucy_ng"`/`grep -rc "lucy-ng"` across `src/`, `tests/`, `scripts/` — exact counts obtained, this session
- `uv run --extra dev pytest -q -p no:cacheprovider -k "not test_import_coconut_real"` — exact baseline numbers obtained, this session
- `uv run --extra dev mypy src/lucy_ng`, `uv run --extra dev ruff check src tests --statistics` — exact baseline numbers obtained, this session
- `pip index versions ailsa`, PyPI JSON API `https://pypi.org/pypi/ailsa/json` — placeholder state confirmed, this session
- `~/.pypirc`, `.venv/` contents, `~/.lucy/` contents, `data/reference/` directory listing — local machine state confirmed, this session
- `slopcheck install twine` — package legitimacy confirmed, this session
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md` (Phase 104 section), `./CLAUDE.md` — read in full, this session

### Secondary (MEDIUM confidence)
- None used — every claim in this document was verifiable directly against the repository or this
  machine's actual state; no external web search was needed for this phase's domain (standard Python
  packaging mechanics, already-in-use tooling).

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new technology; every tool (`uv`, `hatchling`, `click`, `twine`) is
  already installed/declared and its behavior was verified directly, not recalled from training data.
- Architecture: HIGH — the deprecated-alias and dual-filename patterns were designed against this
  repo's actual existing code (`cli/main.py`, `database/finder.py`, `cli/database.py`), not a generic
  template.
- Pitfalls: HIGH — all eight pitfalls were discovered by running actual commands against this actual
  repository in this session (test run, grep counts, mypy/ruff runs, filesystem inspection), not
  inferred.

**Research date:** 2026-10-02
**Valid until:** 30 days (stable domain — Python packaging conventions; the one time-sensitive fact,
the PyPI placeholder state, should be re-checked immediately before the publish checkpoint if more
than a few days elapse)
