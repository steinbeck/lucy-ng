# Phase 104: Package and CLI - Pattern Map

**Mapped:** 2026-10-02
**Files analyzed:** 9 (plus ~126 mechanically-renamed files covered by the find/replace gate, not individually pattern-mapped)
**Analogs found:** 9 / 9

This phase is predominantly a mechanical rename (`git mv src/lucy_ng src/ailsa` + find/replace
`lucy_ng`→`ailsa`, `lucy-ng`→`ailsa` across `src/`, `tests/`, `scripts/`, `pyproject.toml`). The
patterns below cover only the files with genuinely new logic: the deprecated-CLI-alias shim
(PKG-03), the dual-filename database resolver (PKG-05), and the two new test files. For every other
touched file, the "pattern" is identical: open it, s/lucy_ng/ailsa/ + s/lucy-ng/ailsa/, no structural
change.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `src/ailsa/cli/main.py` (renamed from `cli/main.py`, extended) | CLI entry point | request-response | `src/lucy_ng/cli/main.py` (itself, in place) | exact — same file, extend in place |
| `pyproject.toml` `[project.scripts]` | config | request-response | `pyproject.toml` (itself) | exact — same file, add one line |
| `src/ailsa/database/finder.py` `DatabaseFinder` (extended) | service / utility | file-I/O | `src/lucy_ng/database/finder.py` (itself) | exact — widen existing method, same structure |
| `src/ailsa/cli/database.py` `download()` default-output logic | CLI command | file-I/O | `src/ailsa/cli/fragment.py` `DEFAULT_FRAGMENTS_DB` usage | role-match — identical shape, second instance of the same defect |
| `src/ailsa/cli/fragment.py` `DEFAULT_FRAGMENTS_DB` (optional widening, Pitfall 7/A4) | CLI command | file-I/O | `src/ailsa/cli/database.py` `DEFAULT_DB_PATH` (the PKG-05 primary case) | exact — same pattern, second file |
| `src/ailsa/webview/server.py` subprocess launcher (3-tier fallback) | service | event-driven (subprocess) | `src/lucy_ng/webview/server.py` (itself, lines ~99-106) | exact — widen existing `if/else` to 3-tier |
| `tests/test_cli_main.py` (extend) or new `tests/test_cli_deprecated_alias.py` (PKG-03) | test | request-response | `tests/test_cli_dereplicate.py` (stderr-vs-stdout assertions) + `src/lucy_ng/cli/pylsd.py` `pylsd_run()` (the deprecation-warning source pattern) | exact — same stderr/stdout separation idiom already used in this repo |
| `tests/test_database.py` (extend) — `DatabaseFinder` dual-name tests (PKG-05) | test | file-I/O | `tests/test_database.py::TestDatabaseManager` (class/fixture style in the same file) | role-match — no existing `DatabaseFinder`-specific test class exists; follow sibling class style in the same file |
| `src/ailsa/__init__.py` (`__version__`, docstring) | config/module | — | `src/lucy_ng/__init__.py` (itself) | exact — same file, string substitution only |

## Pattern Assignments

### `src/ailsa/cli/main.py` (CLI entry point, request-response)

**Analog:** `src/lucy_ng/cli/main.py` (same file, in place — not a cross-file copy)

**Current imports pattern** (lines 1-21):
```python
"""Main CLI entry point for lucy-ng."""

import click

from lucy_ng import __version__
from lucy_ng.cli.analyze import analyze
from lucy_ng.cli.database import database
from lucy_ng.cli.dereplicate import dereplicate
from lucy_ng.cli.detect import detect
from lucy_ng.cli.fetch import fetch
from lucy_ng.cli.fragment import fragment
from lucy_ng.cli.identify import identify
from lucy_ng.cli.jcamp import jcamp
from lucy_ng.cli.lsd import lsd
from lucy_ng.cli.nus import nus
from lucy_ng.cli.pick import pick
from lucy_ng.cli.predict import predict
from lucy_ng.cli.pylsd import pylsd
from lucy_ng.cli.read import read
from lucy_ng.cli.visualize import visualize
from lucy_ng.cli.webview import webview
```
After rename: every `lucy_ng` → `ailsa` (mechanical, 17 import lines + the module docstring).

**Group definition + version_option** (lines 24-26):
```python
@click.group()
@click.version_option(version=__version__, prog_name="lucy")
def cli() -> None:
```
`prog_name="lucy"` must become `prog_name="ailsa"` (PKG-01/PKG-03) — this is the string the
`--version` output prints, and `tests/test_cli_main.py::test_version` only asserts `__version__` is
in the output, not `prog_name`, so this change is safe but must not be forgotten (grep gate on
`lucy_ng`/`lucy-ng` will not catch a bare `"lucy"` string — manual check needed).

**New: deprecated-alias wrapper to add** (new code, modeled on the stderr-warning idiom at
`src/lucy_ng/cli/pylsd.py` lines 185-191):
```python
# Existing analog in this exact repo — src/lucy_ng/cli/pylsd.py lines 185-191:
def pylsd_run(...) -> None:
    """Run PyLSD orchestration (DEPRECATED — use lucy lsd run with ELIM escalation per D-05)."""
    click.echo(
        "Warning: lucy pylsd run is deprecated (Phase 80 D-05). "
        "Use lucy lsd run with ELIM escalation instead. "
        "See .planning/phases/80-long-range-4j-hmbc-connectivity-defect/80-CONTEXT.md",
        err=True,
    )
    # ... continues to execute the real command, does not exit early ...
```
This is the exact shape to copy for PKG-03's `lucy` top-level alias: a `click.echo(..., err=True)`
warning, immediately followed by executing the real command (never short-circuiting). Research's
`Pattern 1` sketch (`lucy_deprecated()` calling `cli()` after the warning) is this same idiom lifted
to the top-level group instead of a single subcommand — follow pylsd.py's `"Warning: ..."` message
phrasing for consistency with the existing deprecation voice in this codebase.

**`cli.add_command(...)` block** (lines 54-70): mechanical, no structural change — the 14
`cli.add_command(x)` calls stay as-is; only the import lines above them change.

---

### `pyproject.toml` (config)

**Analog:** itself, in place.

**Current `[project.scripts]`** (lines 42-43):
```toml
[project.scripts]
lucy = "lucy_ng.cli:cli"
```

**Target shape** (per Research Pattern 1, PKG-01 + PKG-03):
```toml
[project.scripts]
ailsa = "ailsa.cli:cli"
lucy = "ailsa.cli:lucy_deprecated"
```
`src/ailsa/cli/__init__.py` must export both names for the second entry-point string to resolve —
see next section.

Also requires updates (mechanical, same file):
```toml
[project]
name = "lucy-ng"        # -> "ailsa"
...
[tool.hatch.build.targets.wheel]
packages = ["src/lucy_ng"]    # -> ["src/ailsa"]
artifacts = [
    "src/lucy_ng/data/schemas/*",     # -> "src/ailsa/data/schemas/*"
    "src/lucy_ng/lsd/filters/*",      # -> "src/ailsa/lsd/filters/*"
    "src/lucy_ng/webview/static/*",   # -> "src/ailsa/webview/static/*"
]
...
[tool.mypy]
packages = ["lucy_ng"]   # -> ["ailsa"]
```

---

### `src/ailsa/cli/__init__.py` (barrel re-export)

**Analog:** `src/lucy_ng/cli/__init__.py` (itself, in place), 5 lines total:
```python
"""Command-line interface for lucy-ng."""

from lucy_ng.cli.main import cli

__all__ = ["cli"]
```
Target (PKG-03 requires the entry-point string `ailsa.cli:lucy_deprecated` to resolve, per Research
Pattern 1):
```python
"""Command-line interface for ailsa."""

from ailsa.cli.main import cli, lucy_deprecated

__all__ = ["cli", "lucy_deprecated"]
```

---

### `src/ailsa/cli/__main__.py` (module-exec entry point)

**Analog:** `src/lucy_ng/cli/__main__.py` (itself, in place):
```python
"""Entry point for ``python -m lucy_ng.cli``.
...
This is used as a subprocess-launch fallback by :func:`lucy_ng.webview.server.start`
when the ``lucy`` script is not on PATH (e.g. in an editable/dev install).
"""

from lucy_ng.cli import cli

if __name__ == "__main__":
    cli()
```
Mechanical rename only (`lucy_ng` → `ailsa` in both the docstring and the import), but the docstring
cross-reference to `webview.server.start`'s fallback behavior must stay accurate — see next pattern.

---

### `src/ailsa/database/finder.py::DatabaseFinder` (service/utility, file-I/O) — PKG-05 crux

**Analog:** `src/lucy_ng/database/finder.py` (itself, in place) — widen in place, do not rewrite from
scratch.

**Current single-name search** (lines 17-19, 26-83):
```python
class DatabaseFinder:
    DEFAULT_DB_PATH = Path("data/reference/lucy-ng-derep.db")
    HOME_DB_PATH = Path.home() / ".lucy" / "lucy-ng-derep.db"
    ...
    @staticmethod
    def find_derep_database() -> Path | None:
        db_name = "lucy-ng-derep.db"

        # 1. Check environment variable first
        env_db = os.environ.get("LUCY_DATABASE")
        if env_db:
            env_path = Path(env_db)
            if env_path.exists() and env_path.suffix == ".db":
                return env_path

        # 2. Check project location
        default_db = Path("data/reference") / db_name
        if default_db.exists():
            return default_db

        # 3. Check common locations
        common_paths = [
            Path.home() / ".lucy" / db_name,
            Path.home() / "lucy-ng" / "data" / "reference" / db_name,
            Path.home() / ".local" / "share" / "lucy-ng" / db_name,
        ]
        for p in common_paths:
            if p.exists():
                return p

        # 4. macOS Spotlight search (fast)
        try:
            result = subprocess.run(
                ["mdfind", "-name", db_name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                found_path = Path(result.stdout.strip().split("\n")[0])
                if found_path.exists():
                    return found_path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # 5. Search in Dropbox/develop (common dev location)
        dropbox_dev = Path.home() / "Dropbox" / "develop" / "lucy-ng" / "data" / "reference" / db_name
        if dropbox_dev.exists():
            return dropbox_dev

        return None
```

**Widening per Research Pattern 2** (both names tried at each existing tier, new name first; env var
name `LUCY_DATABASE` stays unchanged per Assumption A3 / Pitfall 6):
```python
class DatabaseFinder:
    NEW_DB_NAME = "ailsa-derep.db"
    LEGACY_DB_NAME = "lucy-ng-derep.db"  # PKG-05: must keep resolving, no forced migration
    DEFAULT_DB_PATH = Path("data/reference") / NEW_DB_NAME
    HOME_DB_PATH = Path.home() / ".lucy" / NEW_DB_NAME

    @staticmethod
    def find_derep_database() -> Path | None:
        names = (DatabaseFinder.NEW_DB_NAME, DatabaseFinder.LEGACY_DB_NAME)

        # 1. env var unchanged (LUCY_DATABASE) — accepts any filename already, no change needed
        env_db = os.environ.get("LUCY_DATABASE")
        if env_db:
            env_path = Path(env_db)
            if env_path.exists() and env_path.suffix == ".db":
                return env_path

        # 2. project location — try both names, new first
        for name in names:
            candidate = Path("data/reference") / name
            if candidate.exists():
                return candidate

        # 3. common locations — try both names at each existing path
        for name in names:
            for p in (
                Path.home() / ".lucy" / name,
                Path.home() / "ailsa" / "data" / "reference" / name,  # directory itself stays
                Path.home() / ".local" / "share" / "ailsa" / name,
            ):
                if p.exists():
                    return p
        ...  # tiers 4 (mdfind) and 5 (Dropbox dev) widened the same way, same order
```
Apply the identical widening to `find_hose_database()` (lines 97-118, which delegates to
`find_derep_database()` plus one extra `cwd_db = Path("lucy-ng-derep.db")` check that also needs
both-name treatment).

**Note on scope of the `Path.home() / "lucy-ng"` and Dropbox-dev-path directory names** inside
`common_paths`/tier 5: those are *directory* names (`~/lucy-ng/...`, `~/Dropbox/develop/lucy-ng/...`),
not the database filename — whether to also rename these to `~/ailsa/...`/`.../develop/ailsa/...`
is a judgment call for the planner (the repo's own working directory is literally
`~/Dropbox/develop/lucy-ng` today per the environment block, unrenamed until Phase 107). Recommend
widening these directory paths to try both `lucy-ng` and `ailsa` directory names too, mirroring the
filename treatment, since Phase 107 (repo rename) is not guaranteed to have landed when this code
runs.

---

### `src/ailsa/cli/database.py::download()` (CLI command, file-I/O) — PKG-05 default-output

**Analog:** `src/lucy_ng/cli/database.py` (itself, in place), lines 22 and 191-217:
```python
DEFAULT_DB_PATH = Path("data/reference/lucy-ng-derep.db")
...
@database.command()
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_DB_PATH,
    help=f"Output path (default: {DEFAULT_DB_PATH})",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing database")
def download(output: Path, force: bool) -> None:
    ...
    # Check if already exists
    if output.exists() and not force:
        click.echo(f"Database already exists: {output}")
        click.echo("Use --force to overwrite, or run 'lucy database info' to check it.")
        return
    ...
```
Per Research Pattern 2's closing paragraph: `DEFAULT_DB_PATH` becomes
`Path("data/reference") / DatabaseFinder.NEW_DB_NAME`, but the `output.exists()` check needs to also
check the legacy filename when `--output` was not explicitly supplied, to avoid re-downloading 830 MB
when the user already has `lucy-ng-derep.db`. Concrete widening:
```python
if output == DEFAULT_DB_PATH:
    # No explicit --output: treat the legacy file as "already exists" too
    legacy = Path("data/reference") / DatabaseFinder.LEGACY_DB_NAME
    if legacy.exists() and not force:
        click.echo(f"Database already exists: {legacy}")
        click.echo("Use --force to overwrite, or run 'ailsa database info' to check it.")
        return
if output.exists() and not force:
    click.echo(f"Database already exists: {output}")
    click.echo("Use --force to overwrite, or run 'ailsa database info' to check it.")
    return
```
`info()` (lines 142-152) needs **zero logic change** — it already takes `db_path: Path` as a required
`click.Path(exists=True)` argument (PKG-05 is satisfied by definition for `info`, per Research). Only
the docstring example `lucy database info lucy-ng-derep.db` needs its `lucy` → `ailsa` mechanical
rename (keep the example filename as `lucy-ng-derep.db` or update to the new default — planner's
discretion, either is a valid, still-working example after the dual-name widening).

---

### `src/ailsa/cli/fragment.py::DEFAULT_FRAGMENTS_DB` (optional, Pitfall 7 / Assumption A4)

**Analog:** `src/ailsa/cli/database.py`'s `DEFAULT_DB_PATH` widening above — apply the identical
transformation:
```python
# Current (src/lucy_ng/cli/fragment.py line 15):
DEFAULT_FRAGMENTS_DB = Path("data/reference/lucy-ng-fragments.db")
```
Widen the same way as the derep DB (new `NEW_FRAGMENTS_DB_NAME = "ailsa-fragments.db"` /
`LEGACY_FRAGMENTS_DB_NAME = "lucy-ng-fragments.db"`, dual-check at the default-path use sites: lines
24, 75, 237, 269 per the earlier grep). Not literally required by PKG-05's wording — flagged in
research as a discretionary consistency extension (Assumption A4) given the real 605 MB file
confirmed present on this machine.

---

### `src/ailsa/webview/server.py` subprocess launcher (service, event-driven)

**Analog:** `src/lucy_ng/webview/server.py` (itself, in place), lines ~99-106:
```python
# Build subprocess command.  Use ``lucy`` from PATH when available so
# that installed packages work; fall back to ``python -m lucy_ng.cli``
# for editable/dev installs.
launcher: list[str]
if shutil.which("lucy"):
    launcher = ["lucy"]
else:
    launcher = [sys.executable, "-m", "lucy_ng.cli"]
```
Per Research Pitfall 8, widen to a 3-tier check (not a naive `"lucy"` → `"ailsa"` swap, which would
drop the deprecated-but-still-valid `lucy` fallback during the transition window):
```python
launcher: list[str]
if shutil.which("ailsa"):
    launcher = ["ailsa"]
elif shutil.which("lucy"):
    launcher = ["lucy"]
else:
    launcher = [sys.executable, "-m", "ailsa.cli"]
```
Module docstring at the top of this file (lines 1-15) also says `lucy-ng webview server` / `the core
``lucy`` CLI` / `lucy_ng.cli.app` — mechanical rename, update to reflect the new 3-tier order.

---

### `tests/test_cli_main.py` or new `tests/test_cli_deprecated_alias.py` (test, request-response) — PKG-03

**Analog 1 — stderr/stdout separation idiom:** `tests/test_cli_dereplicate.py` lines 109-123:
```python
@pytest.mark.skipif(
    not Path("data/reference/compounds.db").exists(),
    reason="SQLite database not available",
)
def test_dereplicate_uses_sqlite_database(self) -> None:
    """Test that SQLite database is used when present."""
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        dereplicate,
        ["c13", "data/<dataset>/2", "<formula>"],
    )
    assert result.exit_code == 0
    # Check stderr for database usage message
    assert "Using database:" in result.stderr
    assert "compounds" in result.stderr.lower()
```

**CRITICAL — this exact idiom is broken under the installed Click 8.4.2** (verified this session):
```
>>> import inspect; from click.testing import CliRunner
>>> inspect.signature(CliRunner.__init__)
(self, charset='utf-8', env=None, echo_stdin=False, catch_exceptions=True, capture='sys') -> None
```
`mix_stderr` was **removed** as a `CliRunner.__init__` parameter in this Click version —
`CliRunner(mix_stderr=False)` now raises `TypeError: unexpected keyword argument 'mix_stderr'`. This
is one of the 74 pre-existing baseline failures named in Research/Validation (do not "fix" the
existing `test_cli_dereplicate.py` calls — out of this phase's scope per Pitfall 4 — but **do not
copy the `mix_stderr=False` constructor call into new PKG-03 tests**).

**Verified replacement, this session** — plain `CliRunner()` (no `mix_stderr` arg) already separates
the streams in Click 8.4.2; `result.stdout` and `result.stderr` work correctly, `result.output` is
the combined legacy-compat view:
```python
# Verified this session against the installed Click 8.4.2:
from click.testing import CliRunner
import click

@click.command()
def cmd():
    click.echo("to stdout")
    click.echo("to stderr", err=True)

runner = CliRunner()                 # no mix_stderr kwarg at all
result = runner.invoke(cmd, [])
result.output  # 'to stdout\nto stderr\n'  (combined, legacy view)
result.stdout  # 'to stdout\n'             (clean)
result.stderr  # 'to stderr\n'             (clean)
```
**Use this pattern (plain `CliRunner()`, assert on `result.stdout`/`result.stderr` separately) for
the new PKG-03 test(s)**, not the repo's own pre-existing `CliRunner(mix_stderr=False)` idiom.

**Analog 2 — the deprecation-warning content/voice to assert against:** `src/lucy_ng/cli/pylsd.py`
lines 186-191 (see CLI pattern above) — follow the `"Warning: ... is deprecated ... use ... instead"`
phrasing already established in this codebase for the new top-level `lucy` → `ailsa` message text
asserted in the new test.

**Sketch for the new test** (not literal, composed from the two analogs above):
```python
from click.testing import CliRunner
from ailsa.cli import cli, lucy_deprecated

def test_lucy_deprecated_alias_warns_on_stderr_not_stdout() -> None:
    runner = CliRunner()  # NOT mix_stderr=False -- removed in this Click version
    result = runner.invoke(lucy_deprecated, ["--version"])
    assert "deprecated" in result.stderr.lower()
    assert "ailsa" in result.stderr
    assert "deprecated" not in result.stdout.lower()  # stdout stays clean for --format json callers
```

**Existing structural analog for the test file itself:** `tests/test_cli_main.py` lines 1-20 (imports
+ `TestCLIMain` class shape) — if extending that file rather than creating a new one, follow its
existing `class TestCLIMain:` / plain `def test_x(self) -> None:` method style (no fixtures needed,
same as the rest of the file).

---

### `tests/test_database.py` — `DatabaseFinder` dual-name tests (PKG-05)

**No existing `DatabaseFinder`-specific test class found** in this repo (`grep -rln DatabaseFinder
tests/` returns `test_prediction.py`, `test_verify_case_identity.py`, `test_ranking.py`,
`test_cli_dereplicate.py`, `test_cli_identify.py` — all *consumers* of `DatabaseFinder`, none test the
class itself directly). This is a genuine new-test gap, matching Research's Wave 0 Gaps list.

**Analog — file/class/import style to follow:** `tests/test_database.py` lines 1-20 (module docstring
+ `from __future__ import annotations` + grouped `lucy_ng.database` imports + `class
TestDatabaseManager:` as the sibling class to pattern-match for a new `class TestDatabaseFinder:`):
```python
"""Tests for database module."""

from __future__ import annotations

import pytest

from lucy_ng.database import (            # -> from ailsa.database import (...)
    CompoundRecord,
    DatabaseManager,
    HOSEStatsRecord,
    ShiftRecord,
    SCHEMA_VERSION,
)
```
**Sketch for the new tests** (uses `tmp_path` + `monkeypatch` — both already pytest fixtures used
throughout this test file's sibling classes, e.g. `tests/test_cli_database.py`'s `tmp_path` usage):
```python
class TestDatabaseFinder:
    """Tests for PKG-05 dual-filename resolution."""

    def test_finds_legacy_filename_only(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data" / "reference").mkdir(parents=True)
        legacy = tmp_path / "data" / "reference" / "lucy-ng-derep.db"
        legacy.touch()
        assert DatabaseFinder.find_derep_database() == legacy

    def test_finds_new_filename_only(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data" / "reference").mkdir(parents=True)
        new = tmp_path / "data" / "reference" / "ailsa-derep.db"
        new.touch()
        assert DatabaseFinder.find_derep_database() == new

    def test_prefers_new_filename_when_both_present(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ref = tmp_path / "data" / "reference"
        ref.mkdir(parents=True)
        (ref / "ailsa-derep.db").touch()
        (ref / "lucy-ng-derep.db").touch()
        assert DatabaseFinder.find_derep_database() == ref / "ailsa-derep.db"
```

---

## Shared Patterns

### Deprecation-hint-on-stderr-only (applies to: `cli/main.py`'s new `lucy_deprecated`)
**Source:** `src/lucy_ng/cli/pylsd.py` lines 185-191 (see excerpt above) — this repo's own
established idiom for a deprecated-command warning: `click.echo("Warning: ... deprecated ... use ...
instead ...", err=True)` immediately followed by executing the real command unconditionally (never
`return`/`sys.exit` early). Apply verbatim to the new `lucy_deprecated()` wrapper in `cli/main.py`.

### `err=True` stderr convention (applies to all CLI modules touched by the rename)
**Source:** `src/lucy_ng/cli/dereplicate.py` (10+ occurrences), `cli/detect.py`, `cli/analyze.py` —
every user-facing warning/error/status-of-resolution message in this codebase already uses
`click.echo(..., err=True)`; stdout is reserved for the actual command output / `--format json`
payload. No new convention needed — the rename must not accidentally flip any of these.

### `CliRunner()` without `mix_stderr` (applies to: any new test asserting stderr separately)
**Source:** verified directly against the installed Click 8.4.2 this session (see test-pattern
section above). The repo's own pre-existing `CliRunner(mix_stderr=False)` calls in
`tests/test_cli_dereplicate.py` and `tests/test_pylsd_cli.py` (lines 202-203, 441) are currently
broken under this Click version and are part of the 74-failure baseline — do not copy that
constructor call into new code; use plain `CliRunner()` and read `result.stdout`/`result.stderr`
directly.

### Dual-filename default-path resolution (applies to: `database/finder.py`, `cli/database.py`,
optionally `cli/fragment.py`)
**Source:** Research Architecture Pattern 2, grounded in `src/lucy_ng/database/finder.py`'s existing
5-tier search structure — widen each tier's filename check to try the new name first, then the legacy
name, without adding new tiers or changing tier order. Same shape applies to the fragments DB if the
planner takes up Pitfall 7/A4.

## No Analog Found

None — every file with genuinely new logic in this phase (the deprecated-alias wrapper, the
dual-filename resolver, the two new test suites) has a concrete, in-repo analog as mapped above. The
remaining ~120 touched files (everything under `src/ailsa/*` not listed individually, plus ~89 test
files in `tests/`, plus `scripts/verify_case_solution.py` and `scripts/render_jcamp_spectra.py`) are
pure mechanical `lucy_ng`→`ailsa` / `lucy-ng`→`ailsa` string substitutions with no structural change —
the acceptance gate for all of them is the grep command in Research's Code Examples section:
```bash
grep -rn "lucy_ng" src/ tests/ scripts/ --include="*.py" | grep -v __pycache__
# must return zero lines
```

## Metadata

**Analog search scope:** `src/lucy_ng/cli/`, `src/lucy_ng/database/`, `src/lucy_ng/webview/`,
`tests/test_cli_main.py`, `tests/test_cli_database.py`, `tests/test_cli_dereplicate.py`,
`tests/test_database.py`, `tests/test_pylsd_cli.py`, `src/lucy_ng/cli/pylsd.py`,
`src/lucy_ng/cli/fragment.py`, `pyproject.toml`
**Files scanned (read in full or targeted sections):** 13
**Pattern extraction date:** 2026-10-02
