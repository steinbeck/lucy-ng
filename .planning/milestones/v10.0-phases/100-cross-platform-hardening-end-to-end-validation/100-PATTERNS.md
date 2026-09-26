# Phase 100: Cross-Platform Hardening + End-to-End Validation - Pattern Map

**Mapped:** 2026-07-18
**Files analyzed:** 9 (5 new/modified source, 3 new tests, 1 new/modified doc set + CLAUDE.md)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/lucy_ng/nus/platform_check.py` (NEW) | utility | transform (introspection → dict) | `src/lucy_ng/nus/backends/nmrpipe_smile.py` (`missing_tools()`/`smile_plugin_available()`) | role-match (detection helper, same module family) |
| `src/lucy_ng/nus/backends/nmrpipe_smile.py::diagnose()` (MODIFIED, additive) | service (backend detection) | transform | same file, `diagnose()` itself (existing method being extended) | exact |
| `src/lucy_ng/nus/runner.py::NusRunner.reconstruct()` (MODIFIED, additive preflight) | orchestrator | request-response (precondition gate before subprocess dispatch) | same file, the existing RECON-02 F2-plan gate (lines 423-438) and F2-before-F1 guard (lines 453-465) | exact |
| `src/lucy_ng/cli/nus.py::check()` (MODIFIED, additive) | controller (CLI command) | request-response | same file, `check()` itself (lines 67-106); secondary analog `cli/lsd.py::lsd_check()` (lines 23-41) | exact |
| `src/lucy_ng/cli/nus.py::reconstruct()`/`pipeline()` (MODIFIED, add precondition surfacing) | controller (CLI command) | request-response | same file, `pipeline()`'s FAIL-branch exit-1 pattern (lines 544-612) | exact |
| `docs/NUS-PORTABILITY.md` (NEW) | config/docs | transform (static reference) | `docs/INSTALLATION.md` (referenced from README `## Reference database`); README `### LSD solver`/`### Reference database` blocks | role-match |
| `CLAUDE.md` § Local prerequisites (MODIFIED, additive) | config/docs | — | same file, existing LSD-solver + reference-DB bullet entries (lines 21-26) | exact |
| `tests/nus/test_platform_check.py` (NEW) | test | transform (unit, mocked introspection) | `tests/nus/test_runner_faillloud.py` (mocked-subprocess unit style) | role-match |
| `tests/nus/test_platform_preflight_gate.py` (NEW) | test | request-response (precondition-before-dispatch) | `tests/nus/test_reconstruct_orchestration.py::test_f2_before_f1_gate_raises_before_any_subprocess` (lines 74-92) | exact |
| `tests/nus/test_cli_check.py` (NEW) | test | request-response (CLI) | `tests/nus/test_cli_pipeline.py` (`CliRunner`-based command tests) | exact |
| `.../phases/100-.../VALIDATION.md` (NEW) | docs/evidence | batch (manual run record) | no direct analog — new artifact type, see "No Analog Found" | n/a |
| Real reconstructed peak JSONs (`<expdir>/analysis/nmr_peaks/*.json`) | data artifact | file-I/O | `src/lucy_ng/cli/nus.py::pipeline()`'s existing write path (D-07) — no new code, existing `write_peak_json()` | exact (existing code, not modified) |

## Pattern Assignments

### `src/lucy_ng/nus/platform_check.py` (NEW utility, transform)

**Analog:** `src/lucy_ng/nus/backends/nmrpipe_smile.py` (`missing_tools()`, `smile_plugin_available()`, `diagnose()`)

**Imports pattern** (mirror lines 46-49 of `nmrpipe_smile.py`):
```python
import platform
import shutil
import subprocess
from typing import Any
```
Keep this stdlib-only — no new dependency, matching the module docstring's "never a core `pyproject.toml` dependency" convention and RESEARCH's Standard-Stack finding (no pip/npm package needed).

**Detection pattern to copy** (`nmrpipe_smile.py` lines 86-115, `smile_plugin_available()` — the "probe defensively, never raise" shape):
```python
@classmethod
def smile_plugin_available(cls) -> bool:
    if shutil.which("nmrPipe") is None:
        return False
    try:
        proc = subprocess.run(
            ["nmrPipe", "-fn", "SMILE", "-help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    combined = (proc.stdout + proc.stderr).lower()
    return "smile" in combined and "unknown function" not in combined
```
Apply the identical shape to `detect_platform()`'s Rosetta sub-check: fixed-argv `subprocess.run(["sysctl", "-n", "sysctl.proc_translated"], ...)`, wrapped in `try/except (OSError, subprocess.TimeoutExpired)`, and — per RESEARCH Pitfall 3 — any non-`"0"`/`"1"` output (including the exception path) must resolve to `None` ("not applicable"), never coerced to `False`. Never `int(output)` unconditionally.

**csh/tcsh check** — same one-line idiom already used for tool detection (`missing_tools()`, line 84):
```python
return [t for t in cls.REQUIRED_TOOLS if shutil.which(t) is None]
```
Reuse directly: `shutil.which("csh")`, `shutil.which("tcsh")`.

**Return-shape pattern** — mirror `diagnose()`'s dict contract (lines 128-178): a plain `dict[str, Any]` with explicit, named keys, never a bespoke class/model for this phase's small check surface (D-05 discretion note: "extend... do not rewrite"). Suggested shape consistent with the existing dict style:
```python
def detect_platform() -> dict[str, Any]:
    return {
        "arch": platform.machine(),
        "os": platform.system(),
        "rosetta_translated": _rosetta_translated(),  # True/False/None
        "csh_available": shutil.which("csh") is not None,
        "tcsh_available": shutil.which("tcsh") is not None,
        "critical_platform_issues": [...],   # e.g. ["no csh/tcsh interpreter found"]
        "soft_platform_warnings": [...],     # e.g. ["running under Rosetta 2 translation"]
    }
```

---

### `src/lucy_ng/nus/backends/nmrpipe_smile.py::diagnose()` (MODIFIED, additive)

**Analog:** itself — the existing method (lines 127-178), read in full above.

**Core extension pattern** (Pattern 1 from RESEARCH, "extend a diagnose()-style dict, don't create a parallel reporting path"):
```python
@classmethod
def diagnose(cls) -> dict[str, Any]:
    missing = cls.missing_tools()
    platform_info = detect_platform()          # NEW import from nus/platform_check.py
    result = { ... }                            # existing status/missing_tools/smile_available/hint logic, UNCHANGED
    result["platform"] = platform_info
    return result
```
Keep every existing key (`status`, `missing_tools`, `smile_available`, `hint`) byte-identical in shape — only add the new `"platform"` key, consistent with `lucy nus check --format json`'s existing consumers not breaking.

**Do not rewrite** `missing_tools()`/`smile_plugin_available()`/`is_available()` — those stay untouched (D-05: "extends... does not replace").

---

### `src/lucy_ng/nus/runner.py::NusRunner.reconstruct()` (MODIFIED, add preflight gate)

**Analog:** the existing RECON-02 pattern in the *same file* — this is a "copy the shape of the neighboring gate," not a cross-file analog.

**Precondition-before-dispatch pattern to copy** (lines 423-438, the F2-plan recipe gate):
```python
# Recipe gate (RECON-02): the F2 plan must be resolvable BEFORE any
# subprocess is dispatched -- checked first, raises immediately.
f2_plan = self._resolve_f2_plan(params)
if f2_plan is None:
    raise RuntimeError(
        "F2 (direct-dimension) processing plan not resolved -- "
        "refusing to start F1/SMILE reconstruction out of order "
        "(RECON-02 hard gate)."
    )
```
PORT-01's new platform/backend preflight gate must be inserted **even earlier** than this (before `read_nus_params`/`read_nus_schedule` are even read, per the architecture diagram in RESEARCH), following the identical "resolve a diagnosis dict → check for critical issues → raise `RuntimeError` before any subprocess/stage runs" shape:
```python
diagnosis = self.backend.diagnose()
platform_info = diagnosis.get("platform", {})
critical = list(diagnosis.get("missing_tools", [])) + list(
    platform_info.get("critical_platform_issues", [])
)
if critical:
    raise RuntimeError(
        f"Critical platform/backend issue(s), aborting before any stage "
        f"runs (PORT-01 preflight gate): {critical}"
    )
```
**Critical finding to act on (RESEARCH Pitfall 1):** as of this research, `reconstruct()` has *no* backend-availability check at all — this is a genuinely new call site, not merely new data flowing through an existing one. Wire it as the very first statement of `reconstruct()`, mirroring how the RECON-02 gate is the first substantive check after resolving `stage_dir`.

**Where NOT to put it:** do not bury it inside `cli/nus.py` only — RESEARCH's Pitfall 1 explicitly warns that gating only in the CLI (and not in `NusRunner.reconstruct()` itself) satisfies "reports readiness" but not "hard-blocks" for any other caller of `NusRunner` directly (e.g. the VAL-01 pipeline's own reconstruct call, tests). Put the gate in `reconstruct()`; `cli/nus.py`'s `reconstruct`/`pipeline` commands then get it for free by calling `NusRunner().reconstruct(...)`.

---

### `src/lucy_ng/cli/nus.py::check()` (MODIFIED, additive platform section)

**Analog:** itself (lines 67-106) plus `src/lucy_ng/cli/lsd.py::lsd_check()` (lines 23-41) as the cross-command precedent for the exit-code contract.

**Imports pattern** (existing, unchanged — file stays import-safe per its own module docstring, lines 1-18):
```python
from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING
import click
```
All `lucy_ng.nus.*` imports stay deferred inside the command body (NUS-05 dependency-free-core invariant) — do not hoist `from lucy_ng.nus.backends import get_backend` to module level.

**Core CLI pattern to copy** (lines 76-105, verbatim structure):
```python
def check(output_format: str) -> None:
    from lucy_ng.nus.backends import get_backend

    backend = get_backend()
    diagnosis = backend.diagnose()
    usable = diagnosis["status"] == "available"

    if output_format == "json":
        click.echo(json.dumps(diagnosis, indent=2))
    else:
        if usable:
            click.echo("NMRPipe+SMILE: available")
        else:
            click.echo(f"NMRPipe+SMILE: not available ({diagnosis['status']})", err=True)
            if diagnosis["missing_tools"]:
                click.echo(f"  Missing tools: {', '.join(diagnosis['missing_tools'])}")
            click.echo(f"  {diagnosis['hint']}")

    if not usable:
        raise SystemExit(1)
```
Extend the text-mode branch with a platform sub-report (arch/Rosetta/csh lines) and fold `platform_info["critical_platform_issues"]` into the `usable`/exit-1 computation — `diagnosis["platform"]` is already present in the JSON dump for free once `diagnose()` is extended (no separate JSON-shape work needed here).

**Cross-command precedent for the fail-loud exit contract** (`cli/lsd.py` lines 23-41):
```python
@lsd.command("check")
def lsd_check() -> None:
    lsd_ok = LSDRunner.is_available()
    ...
    if not lsd_ok:
        raise SystemExit(1)
```
Confirms the project-wide convention: `lucy <group> check` always prints per-component status then `raise SystemExit(1)` only if something *critical* is missing — soft/warn-only conditions must never trigger this exit path (D-05).

---

### `src/lucy_ng/cli/nus.py::reconstruct()`/`pipeline()` (MODIFIED, surface preflight failure)

**Analog:** `pipeline()`'s own existing FAIL-branch pattern (lines 544-573, 611-612) — the established "clean err-echo + `raise SystemExit(1)`" shape already used for the QC-FAIL boundary:
```python
if report.verdict == QcVerdict.FAIL:
    ...
    click.echo(
        f"QC verdict FAIL -- critical violations: "
        f"{', '.join(report.critical_violations())}. Peaks quarantined to "
        f"{quarantine_dir}; nothing written to {nmr_peaks_dir}.",
        err=True,
    )
...
if report.verdict == QcVerdict.FAIL:
    raise SystemExit(1)
```
When `NusRunner.reconstruct()` raises the new preflight `RuntimeError` (see above), `reconstruct`/`pipeline` command bodies do not need a new try/except — Click already surfaces an uncaught exception as a non-zero exit with a traceback. If a cleaner one-line message is wanted (consistent with the rest of the file's UX), wrap the `NusRunner().reconstruct(...)` call:
```python
try:
    result = NusRunner().reconstruct(resolved, ...)
except RuntimeError as e:
    click.echo(f"NUS pipeline: {e}", err=True)
    raise SystemExit(1) from e
```
This mirrors the existing `if not result.processed_spectrum:` early-exit block already in `pipeline()` (lines 517-523).

---

### `docs/NUS-PORTABILITY.md` (NEW)

**Analog:** `README.md` `### LSD solver` / `### Reference database` blocks (lines 237-260) and `docs/INSTALLATION.md` (referenced but not modified) — the established "prerequisite + verify-with-CLI-command + link" doc shape.

**Structure pattern to copy** (README lines 237-245):
```markdown
### <Tool name>

<One-line description + link>. Download it, extract it, add its `bin/` directory to `PATH`.
Verify with:

\`\`\`bash
lucy <group> check     # must report ...
\`\`\`
```
Apply this shape per-row for the D-06 portability matrix (macOS-arm64-native / Linux-native / Windows-WSL2-gap), plus an explicit "documented, untested" callout on the WSL2 row (D-06). Link `docs/NUS-PORTABILITY.md` from CLAUDE.md § Local prerequisites and (optionally) from README, following the existing `docs/INSTALLATION.md#reference-database` cross-link convention (README line 260).

---

### `CLAUDE.md` § Local prerequisites (MODIFIED, additive)

**Analog:** itself — existing bullet-list entries (lines 21-26 as read):
```markdown
### Local prerequisites

Needed to run the full test suite and the dereplication/prediction paths locally:

- **LSD solver** — `lucy lsd check` must report both `LSD` and `outlsd` on PATH. Download from http://eos.univ-reims.fr/LSD/, extract, add the `bin/` directory to PATH.
- **Reference database** — `lucy database download` fetches the pre-built SQLite DB (~830 MB compressed → ~2.8 GB) to `data/reference/lucy-ng-derep.db`. Verify with `lucy database info data/reference/lucy-ng-derep.db`. See *Database Reference* below.
```
Add a third bullet in the exact same shape:
```markdown
- **NMRPipe + SMILE** — `lucy nus check` must report the backend `available` (and the new platform section clear of critical issues). Install NMRPipe (native `mac11_arm64`/Linux build) **and** the separate SMILE companion plugin (`plugin.smile.tZ`) from https://www.ibbr.umd.edu/nmrpipe/install, source its environment script, add `bin/` to `PATH`. See `docs/NUS-PORTABILITY.md` for the full per-platform matrix (macOS-arm64-native / Linux-native / Windows-WSL2-gap).
```

---

### `tests/nus/test_platform_check.py` (NEW)

**Analog:** `tests/nus/test_runner_faillloud.py` (mocked-`subprocess.run` unit style) and `tests/nus/conftest.py::mock_subprocess_run` fixture (lines 372-...).

**Pattern to copy** — mock `subprocess.run`/`shutil.which`/`platform.machine` per-branch, never touch the real system:
```python
def test_nonzero_exit_raises(mock_subprocess_run, make_valid_intermediate, tmp_path) -> None:
    from lucy_ng.nus.runner import run_stage
    ...
```
Adapt this shape: for each branch (native arm64, Rosetta-translated, genuine Intel, Linux, Windows-simulated, missing csh), monkeypatch `platform.machine`/`platform.system`/`shutil.which`/`subprocess.run` and assert `detect_platform()`'s returned dict classifies the issue into `critical_platform_issues` vs `soft_platform_warnings` correctly (per D-05). Follow `conftest.py`'s existing `monkeypatch` fixture convention (string-target patching, `raising=False` where appropriate per the `mock_run_stage` fixture docstring, lines 209-231).

---

### `tests/nus/test_platform_preflight_gate.py` (NEW)

**Analog:** `tests/nus/test_reconstruct_orchestration.py::test_f2_before_f1_gate_raises_before_any_subprocess` (lines 74-92) — the exact shape for "precondition raises before any subprocess is dispatched."

**Pattern to copy verbatim (adapt the monkeypatch target):**
```python
def test_f2_before_f1_gate_raises_before_any_subprocess(
    mock_subprocess_run, nus_fixture_dir, tmp_path, monkeypatch
) -> None:
    from lucy_ng.nus.runner import NusRunner

    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")
    runner = NusRunner()
    monkeypatch.setattr(runner, "_resolve_f2_plan", lambda params: None)

    with pytest.raises(RuntimeError, match="F2"):
        runner.reconstruct(expdir)

    assert mock_subprocess_run["calls"] == []
```
For PORT-01's new gate: `monkeypatch.setattr(runner.backend, "diagnose", lambda: {"missing_tools": ["nmrPipe"], "platform": {"critical_platform_issues": []}})`, then assert `pytest.raises(RuntimeError, match="preflight")` (or whatever match string the implementation uses) and `mock_subprocess_run["calls"] == []` — same "assert zero subprocess calls" proof technique. Use the `_copy_fixture` helper (lines 29-40 of the orchestration test file) to avoid polluting `tests/fixtures/nus/`.

---

### `tests/nus/test_cli_check.py` (NEW)

**Analog:** `tests/nus/test_cli_pipeline.py` (`CliRunner`-based command tests, e.g. `test_qc_command_json_format`, `test_pipeline_help_lists_reconstruction_and_qc_flags`, `test_all_nus_subcommands_support_format_json`).

**Pattern to copy:**
```python
def test_qc_command_json_format(known_bad_peaks_dir) -> None:
    from click.testing import CliRunner
    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(known_bad_peaks_dir), "--format", "json"])
    ...
```
Adapt for `check`: invoke `nus, ["check", "--format", "json"]`, assert the output dict contains a `"platform"` key with the expected sub-keys (mock `get_backend()`/`diagnose()` at the CLI-invocation boundary, not the raw subprocess level, since this is a controller-layer test). Also add a text-mode invocation test and an exit-code test (critical issue → `result.exit_code == 1`; soft-only warning → `result.exit_code == 0`), mirroring `test_qc_command_threshold_override_changes_verdict`'s style of asserting on both output content and exit behavior.

---

## Shared Patterns

### Fail-loud precondition-before-dispatch
**Source:** `src/lucy_ng/nus/runner.py` lines 423-465 (RECON-02 F2-plan gate + F2-before-F1 guard); `src/lucy_ng/nus/runner.py::run_stage()` lines 51-118 (RECON-04)
**Apply to:** `NusRunner.reconstruct()`'s new PORT-01 preflight gate, and its CLI surfacing in `cli/nus.py::reconstruct`/`pipeline`.
```python
if <critical condition>:
    raise RuntimeError(
        "<what precondition failed> -- refusing to <action> "
        "(<REQ-ID> hard gate)."
    )
```
Always raise **before** any `subprocess.run`/`run_stage()` call — never wrap the check in a try/except that could swallow it, and never place it only in the CLI layer without also gating the underlying `NusRunner` method (Pitfall 1).

### diagnose()-style structured dict, extended not replaced
**Source:** `src/lucy_ng/nus/backends/nmrpipe_smile.py::diagnose()` lines 127-178
**Apply to:** `platform_check.py::detect_platform()`'s return shape, merged into `diagnose()` under a `"platform"` key.
```python
result["platform"] = platform_info   # additive; existing keys (status/missing_tools/smile_available/hint) unchanged
```

### `lucy <group> check` CLI contract
**Source:** `src/lucy_ng/cli/nus.py::check()` lines 67-106; `src/lucy_ng/cli/lsd.py::lsd_check()` lines 23-41
**Apply to:** the extended `lucy nus check` — text/json dual-format, per-component status lines, `raise SystemExit(1)` only on a genuinely critical/unusable condition.

### Deferred-import, dependency-free-core CLI module
**Source:** `src/lucy_ng/cli/nus.py` module docstring (lines 1-18) — "This module is import-safe... All `lucy_ng.nus.*` imports are deferred into command bodies."
**Apply to:** every modified command body in `cli/nus.py`; keep `from lucy_ng.nus.platform_check import detect_platform` (or wherever it's called from) deferred inside function bodies, never at module level.

### Fixed-argv subprocess calls only (security convention, ASVS V5)
**Source:** `src/lucy_ng/nus/backends/nmrpipe_smile.py::smile_plugin_available()` lines 100-115; `src/lucy_ng/nus/runner.py::run_stage()` line 85
**Apply to:** `platform_check.py`'s `sysctl`/`shutil.which` calls — always a fixed `list[str]` argv, `capture_output=True, text=True, timeout=...`, wrapped in `try/except (OSError, subprocess.TimeoutExpired)`; never `shell=True`, never a user/CLI-supplied string interpolated into a shell command.

### Skipif-guarded backend-gated real-data test
**Source:** `tests/nus/test_reconstruct_integration.py` (full file, 71 lines)
**Apply to:** any new automated (non-manual) test that needs the real NMRPipe+SMILE backend for VAL-adjacent verification — reuse the `_backend_available()` + `_EXTERNAL_DATA.exists()` skip condition and `LUCY_NUS_TEST_DATA` env-var override; do not invent a second skip convention.

### Known-bad fixture non-collision boundary
**Source:** `tests/nus/conftest.py::known_bad_peaks_dir` (lines 47-51) → resolves to `tests/fixtures/nus/known_bad_peaks/` (repo-committed copy, verified present: `13C_exp6_narrow.json`, `13C_exp7_wide.json`, `1H_exp1.json`, `COSY_exp2.json`, `HMBC_exp4.json`, `HSQC_exp3.json`)
**Apply to:** VAL-01's real run — the automated regression suite already reads only this repo-committed copy, never the external `.../C20H32O2/analysis/nmr_peaks/` path, so the real `lucy nus pipeline` run is safe to execute against the external data without touching this fixture directory. The only remaining care point is archiving the external known-bad files (project-history preservation, not test-suite safety) before they get overwritten in place.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.planning/phases/100-.../VALIDATION.md` | docs/evidence | batch (one-off manual run record) | No prior phase in this milestone produced a dedicated per-phase `VALIDATION.md`; this is a genuinely new artifact type (D-01/D-02/D-03 evidence record). Planner discretion on exact layout — recommend: one `##` section per experiment (exp2/exp3/exp4) with §8 checklist items + QC verdict + link to the committed peak JSON, then a `## CASE Convergence (VAL-02)` section, then (if applicable) a `## Documented Limitation` section naming RECON-F1, consistent in tone with existing `.planning/phases/*/`-level completion docs (e.g. `99-04-SUMMARY.md`-style prose) but scoped to empirical results rather than plan execution. |
| Tuning-budget sweep driver (D-04, if `--n-sigma` CLI flag is added) | CLI option | request-response | No existing `--n-sigma` flag on `lucy nus reconstruct`/`pipeline` (RESEARCH Pitfall 7/Open Question 1) — if the planner chooses to add it, the closest analog is the sibling `--threshold`/`--iterations` `click.option` blocks already in `cli/nus.py` (e.g. lines 370-378, 379-385 of the `pipeline` command) — same `type=float`/`type=int`, `show_default=True`, forwarded 1:1 into `NusRunner().reconstruct(n_sigma=...)`. |

## Metadata

**Analog search scope:** `src/lucy_ng/nus/`, `src/lucy_ng/nus/backends/`, `src/lucy_ng/cli/`, `tests/nus/`, `tests/fixtures/nus/`, `docs/`, `README.md`, `CLAUDE.md`
**Files scanned:** `nus/backends/nmrpipe_smile.py` (548 lines, read in full), `nus/backends/__init__.py` (95 lines, read in full), `nus/runner.py` (offsets 1-130, 248-503), `nus/qc.py` (defs grepped), `cli/nus.py` (offsets 1-107, 367-612), `cli/lsd.py` (offsets 1-42, defs grepped), `tests/nus/test_reconstruct_integration.py` (71 lines, read in full), `tests/nus/test_reconstruct_orchestration.py` (offset 1-110), `tests/nus/test_runner_faillloud.py` (defs grepped), `tests/nus/conftest.py` (defs grepped), `tests/nus/test_cli_pipeline.py` (defs grepped), `README.md` (offset 209-263), `CLAUDE.md` (Local prerequisites section), `docs/` directory listing, `tests/fixtures/nus/known_bad_peaks/` directory listing
**Pattern extraction date:** 2026-07-18
