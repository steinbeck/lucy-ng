# Phase 98: Reconstruction + Processing - Pattern Map

**Mapped:** 2026-07-13
**Files analyzed:** 6 (3 new modules, 2 modified, 1 test group covering 3+ new test files)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `src/lucy_ng/nus/runner.py` (NEW) | service (orchestrator) | event-driven / batch (multi-stage pipeline) | `src/lucy_ng/lsd/runner.py::LSDRunner` | exact (same role: subprocess-orchestrating runner class, fail-loud wrapper, `is_available()`-style detection reuse) |
| `src/lucy_ng/nus/postprocess.py` (NEW — `process_direct()` before SMILE + `process_indirect()` after) | service (DSP stage) | transform / batch | `src/lucy_ng/nus/runner.py` (itself, once written) + `run_stage()` helper shared from runner | role-match (same fail-loud subprocess-per-stage convention, narrower scope: FT/apod/phase/baseline only) |
| `src/lucy_ng/nus/backends/nmrpipe_smile.py::convert()` + `reconstruct_indirect()` (MODIFY — add method bodies) | service (external-tool integration) | request-response (params+schedule in → converted/reconstructed FID out) | Same file's existing `smile_plugin_available()`/`diagnose()` classmethods (Phase 97) | exact (same module, same subprocess-safety convention: fixed arg list, no `shell=True`, `capture_output=True`, explicit `timeout`) |
| `src/lucy_ng/models/nus.py` (MODIFY — add `NusReconstructionResult` or similar) | model | CRUD (construct/serialize) | `src/lucy_ng/models/nus.py::NusAcquisitionParams`/`NusSchedule` (same file, Phase 97) | exact (same file, same Pydantic v2 `to_dict()`/`from_dict()` convention) |
| `src/lucy_ng/cli/nus.py` (MODIFY — add `reconstruct` command) | route/controller (CLI) | request-response | Same file's existing `params`/`schedule` commands (Phase 97) | exact (same file, same deferred-import + `--format json` convention) |
| `tests/nus/test_nus_runner.py`, `tests/nus/test_nus_postprocess.py`, `tests/test_cli_nus.py::TestReconstructCommand` (NEW/MODIFY) | test | mixed (unit + skipif-guarded integration) | `tests/test_lsd_runner.py` (mocked-subprocess unit tests + skipif integration tests) + `tests/test_hmbc_peak_picking_integrity.py` (external-path `Path(...).exists()` skipif pattern) | exact |

## Pattern Assignments

### `src/lucy_ng/nus/runner.py` (service/orchestrator, event-driven pipeline)

**Analog:** `src/lucy_ng/lsd/runner.py::LSDRunner`

**Imports pattern** (lsd/runner.py lines 1-10):
```python
"""LSD (Logic for Structure Determination) runner."""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from lucy_ng.lsd.generator import LSDInputGenerator
from lucy_ng.lsd.models import LSDProblem
```
For `nus/runner.py`, mirror this shape but import from Phase 97 modules instead of re-parsing:
```python
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import nmrglue as ng

from lucy_ng.models.nus import (
    COMPLEX_FNMODES,
    REAL_FNMODES,
    NusAcquisitionParams,
    NusSchedule,
)
from lucy_ng.nus.params import read_nus_params
from lucy_ng.nus.schedule import read_nus_schedule
from lucy_ng.nus.backends import get_backend
```
Do **not** re-parse `acqus`/`acqu2s` inside `runner.py` — always call `read_nus_params`/`read_nus_schedule` (RESEARCH.md Code Examples section, "GRPDLY / byte-order / NUS-parameter sourcing").

**Result dataclass pattern** (lsd/runner.py lines 90-128, `LSDResult`):
```python
@dataclass
class LSDResult:
    """Result from LSD execution."""

    success: bool
    solution_count: int
    solutions: list[str] = field(default_factory=list)
    output_files: list[Path] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    input_file: Path | None = None
    output_dir: Path | None = None

    def summary(self) -> str:
        ...
```
Mirror this shape for a `NusReconstructionResult` (either a `@dataclass` here in `runner.py`, or a Pydantic model in `models/nus.py` — planner's discretion per CONTEXT.md — but keep the same fields-and-`summary()` convention: `success`, per-stage `output_files`/paths under `analysis/nus_recon/<expN>/`, `stdout`/`stderr` or a per-stage log list, and the backend/params used).

**Class skeleton + `SEARCH_PATHS`/`is_available()` precedent** (lsd/runner.py lines 131-175, 442-449):
```python
class LSDRunner:
    """Execute LSD solver."""

    SEARCH_PATHS = [
        "/usr/local/bin/lsd",
        "/usr/bin/lsd",
        ...
    ]

    def __init__(self, lsd_path: str | Path | None = None):
        if lsd_path:
            self.lsd_path = Path(lsd_path).expanduser()
        else:
            self.lsd_path = self._find_lsd()
        ...

    @classmethod
    def is_available(cls) -> bool:
        """Check if LSD is available on the system."""
        return cls._find_lsd() is not None
```
`nus/runner.py`'s `NusRunner` (or equivalent) does **not** need its own `SEARCH_PATHS`/`is_available()` — that already exists on `NmrPipeSmileBackend` (Phase 97, `nus/backends/nmrpipe_smile.py`). `NusRunner.__init__` should accept/resolve a backend via `get_backend()` (see `nus/backends/__init__.py` registry, lines 57-76) rather than re-implementing binary discovery.

**Fail-loud subprocess pattern to mirror (`_execute_lsd`, lsd/runner.py lines 262-352):**
```python
proc = subprocess.run(
    [str(self.lsd_path), lsd_input_name],
    capture_output=True,
    text=True,
    timeout=timeout,
    cwd=output_dir,
)
...
success = sol_file.exists() and smiles_path is not None
return LSDResult(success=success, ..., return_code=proc.returncode)
```
Key precedent to copy exactly: **`success` is derived from checking the actual output artefact on disk (`sol_file.exists()`), never just `proc.returncode == 0`** — this is the direct precedent for RECON-04's fail-loud wrapper (RESEARCH.md Pattern 2's `run_stage()` helper: exit code AND output-file non-emptiness AND, where computable, an `nmrglue.fileio.pipe.read()` non-zero-data check). Timeout handling on `subprocess.TimeoutExpired` returns a failed result rather than raising uncaught (lsd/runner.py lines 338-352) — follow the same graceful-catch-into-result-object convention for stage-level failures if `NusRunner` returns a result object rather than raising; but note RECON-02's ordering-gate precondition (see below) **must raise**, not return a failed-but-caught result, per D-04's "must raise before any reconstruction runs" requirement.

**F2-before-F1 ordering gate — explicit precondition, not implicit sequencing** (RESEARCH.md Pattern 1, illustrative):
```python
def reconstruct(self, expdir: Path) -> NusReconstructionResult:
    params = read_nus_params(expdir)
    schedule = read_nus_schedule(expdir)
    stage_dir = self._stage_dir(expdir)

    f2_plan = self._resolve_f2_plan(params)   # raises if phase/apod params unresolved
    if f2_plan is None:
        raise RuntimeError(
            "F2 (direct-dimension) processing plan not resolved — refusing to start "
            "F1/SMILE reconstruction out of order (RECON-02 hard gate)."
        )
    ...
```
This precondition check is what D-04's "an out-of-order attempt must raise before any reconstruction runs" test targets — implement it as an assertion/raise at the very top of `reconstruct()`, before any `subprocess.run()` call, so it is mockable/testable with zero backend installed.

**FnMODE-driven stage-order branch (Critical Finding 1, RESEARCH.md):** reuse `REAL_FNMODES`/`COMPLEX_FNMODES` from `models/nus.py` (already imported by `nus/schedule.py`, lines 29, 51-58 of `schedule.py`) — do not re-derive a second FnMODE-branching table. Add a small helper mirroring `nus/schedule.py::expected_sample_count()`'s refuse-to-guess convention:
```python
# Source: nus/schedule.py's own expected_sample_count() refuse-to-guess convention
def _ordering_for_fnmode(fnmode: int) -> str:
    if fnmode in COMPLEX_FNMODES:
        return "expand_first"   # nusExpand.tcl before bruk2pipe (echo-antiecho)
    if fnmode in REAL_FNMODES:
        return "convert_first"  # bruk2pipe before nusExpand.tcl (QF/magnitude COSY)
    raise NotImplementedError(f"FnMODE={fnmode} has no known stage-order recipe")
```

**Intermediate-file location (D-03):** follow `LSDRunner.run()`'s `output_dir` handling (lsd/runner.py lines 176-227: `output_dir.mkdir(parents=True, exist_ok=True)`) but target `analysis/nus_recon/<expN>/` under the *experiment* directory (not a temp dir, and — unlike LSD's temp-dir-with-cleanup default — **default is keep, no `shutil.rmtree`**, per D-03).

---

### `src/lucy_ng/nus/postprocess.py` (service, transform/batch — F2 direct + F1 indirect processing)

**Analog:** the `run_stage()` helper this phase is expected to introduce (shared with `runner.py`), plus `LSDRunner`'s subprocess-safety conventions (same as above).

**CRITICAL — F2 processing runs BEFORE SMILE, not after (SMILE manual §4/§6.1).** `postprocess.py` exposes TWO functions, not one `process_direct_then_indirect`:
- `process_direct(converted_fid, stage_dir, params, *, f2_p0, f2_p1, magnitude, timeout=600) -> Path` — apodize/ZF/FT/PS(f2_p0,f2_p1)/POLY/EXT the DIRECT (F2) dimension, THEN transpose (TP). Its output (`f2_processed.fid`) is SMILE's ACTUAL input — a transposed, F2-processed FID, **not** a raw time-domain FID. This runs BEFORE `backend.reconstruct_indirect()` (SMILE).
- `process_indirect(reconstructed_fid, stage_dir, params, *, f1_p0, f1_p1, magnitude, timeout=600) -> Path` — post-SMILE INDIRECT (F1) ZF/FT/PS(f1_p0,f1_p1), final transpose (TP), reversed 1D-calibrated ppm axes → `processed.ft2`. This runs AFTER SMILE.
The runner (Plan 05) interleaves SMILE between these two: convert → `process_direct` → SMILE → `process_indirect`. The manual's worked pipe (§6.1) makes this order explicit: F2-processing → TP → SMILE → post-SMILE F1 processing → TP → output.

**Core `run_stage()` fail-loud wrapper — RECON-04's correctness anchor** (RESEARCH.md Pattern 2, to be placed likely in `runner.py` and imported by `postprocess.py`, or in a small shared module):
```python
# Source: Pitfall 14 mitigation + LSDRunner's subprocess.run(..., capture_output=True,
# text=True, timeout=..., cwd=...) precedent; nmrglue.fileio.pipe.read for the shape check
import subprocess
from pathlib import Path
import nmrglue as ng

def run_stage(name: str, argv: list[str], cwd: Path, expected_output: Path,
              timeout: int = 600) -> None:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(
            f"NUS stage '{name}' failed (exit {proc.returncode}): {proc.stderr[:500]!r}"
        )
    if not expected_output.exists() or expected_output.stat().st_size == 0:
        raise RuntimeError(
            f"NUS stage '{name}' reported success but output file "
            f"{expected_output} is missing or empty — refusing to continue "
            "(csh-piped NMRPipe stages can silently pass through truncated data, Pitfall 14)."
        )
    if expected_output.suffix in {".fid", ".ft2"}:
        _dic, data = ng.fileio.pipe.read(str(expected_output))
        if data.size == 0 or not data.any():
            raise RuntimeError(
                f"NUS stage '{name}' output {expected_output} parses but is all-zero/empty "
                "data — treat as a hard failure, not a legitimate empty result."
            )
```
This is the single shared helper both `runner.py`'s bruk2pipe/nusExpand.tcl/SMILE stages **and** `postprocess.py`'s FT/PS/baseline stage must call — do not duplicate the exit-code/non-emptiness check per module.

**Deterministic phase, never blind auto-phase (D-02):** F2 phase (`-p0`/`-p1`) and F1 phase (`-xP0`/`-xP1`) are **named constants passed as CLI-overridable parameters**, never computed via a search loop. Worked example (RESEARCH.md Code Examples, verbatim from SMILE manual, csh — illustrates the parameter values `postprocess.py`'s Python call must thread through, not literal code to copy 1:1 since D-01 forbids the single-csh-chain shape for the *stage boundary*, though NMRPipe's own internal `|` chaining within the post-processing stage is fine per the Anti-Patterns note):
```
nmrPipe -in test.fid \
| nmrPipe  -fn POLY -time \
| nmrPipe  -fn GMB -lb -4 -gb 0.8 -c 1.0 \
| nmrPipe  -fn ZF -zf 2 -auto \
| nmrPipe  -fn FT \
| nmrPipe  -fn PS -p0 -24 -p1 0 -di \
...
```
Note the manual pipe above ends the F2 (direct) block with `TP` **before** the `SMILE` verb — i.e. everything up to and including that first `TP` is `process_direct`'s job, and everything after the SMILE call (the second `ZF`→`FT`→`PS`→`TP`) is `process_indirect`'s job. Each of `process_direct` and `process_indirect` should build its own verb chain as **one D-01 stage** (one shell command string / one `.com` script executed with a fixed argv / one `subprocess.Popen`-piped chain — `shell=True` avoided), with the *stage's own final output* (`f2_processed.fid` and `processed.ft2` respectively) checked via `run_stage()`. Do not decompose into N separate `subprocess.run()` calls per NMRPipe verb (Anti-Patterns, RESEARCH.md).

**ppm-axis reversal + 1D calibration cross-check (RECON-02):** no existing lucy-ng analog for ppm-axis math exists yet in `nus/`; use `models/nus.py`'s already-parsed `f2_sf`/`f2_offset`/`f1_sf`/`f1_offset` fields (params.py lines 112-118, models/nus.py lines 72-77) as the calibration inputs — compare against `NUS-RECONSTRUCTION-GUIDE.md` §10 ground-truth 1D shifts (per CONTEXT.md/RESEARCH.md).

---

### `src/lucy_ng/nus/backends/nmrpipe_smile.py::convert()` + `reconstruct_indirect()` (service, external-tool integration)

**Analog:** the same file's existing classmethods (`smile_plugin_available()`, lines 61-90; `diagnose()`, lines 102-153) — same module, same conventions, this phase adds new methods rather than a new file.

**Why two methods, not one `reconstruct()`:** the DIRECT-dimension (F2) processing + transpose must run BETWEEN conversion and SMILE (SMILE manual §4). So the backend exposes `convert()` (FnMODE-branched bruk2pipe/nusExpand → `converted.fid`) and `reconstruct_indirect()` (SMILE on the transposed, F2-processed FID → `reconstructed.ft1`), and the runner (Plan 05) calls `postprocess.process_direct()` in between. `reconstruct_indirect()`'s input parameter is the F2-processed transposed FID, NOT a raw time-domain FID — name it accordingly (e.g. `f2_processed_fid`).

**Subprocess-safety convention to preserve exactly** (nmrpipe_smile.py lines 75-90):
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
Both `convert()` and `reconstruct_indirect()` should reuse this "fixed arg list, never `shell=True`, `capture_output=True`, explicit `timeout`" shape for every subprocess/SMILE invocation, but — unlike `smile_plugin_available()`'s "never raises" contract (a probe) — their own subprocess calls **should raise** via the shared `run_stage()` helper (RECON-04 is fail-loud, not "return False silently"). `REQUIRED_TOOLS` (line 33) and `missing_tools()` (lines 52-59) are the pre-flight check `convert()` should call first (raise `FileNotFoundError`/`RuntimeError` if any required tool is missing, mirroring `LSDRunner.run()`'s `FileNotFoundError` when `lsd_path is None`, lsd/runner.py lines 198-201).

**Module docstring convention** (nmrpipe_smile.py lines 1-23) — the file already documents *why* SMILE is a plugin-probe not a `which()`-able binary; extend this docstring (don't replace it) when adding `convert()`/`reconstruct_indirect()`, keeping the "mirrors `LSDRunner`" framing explicit for future maintainers.

---

### `src/lucy_ng/models/nus.py` (model, CRUD — possible new `NusReconstructionResult`)

**Analog:** same file's `NusAcquisitionParams`/`NusSchedule` (Phase 97, lines 33-172).

**Pydantic v2 model + `to_dict()`/`from_dict()` convention** (models/nus.py lines 129-171, `NusSchedule`):
```python
class NusSchedule(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    nuslist: list[int]
    fnmode_f1: int
    td_f1: int
    nus_td: int
    n_sampled: int

    @field_validator("fnmode_f1")
    @classmethod
    def validate_fnmode_f1(cls, v: int) -> int:
        if v not in VALID_FNMODES:
            raise ValueError(f"Unknown FnMODE: {v}. Valid: {sorted(VALID_FNMODES)}")
        return v

    def to_dict(self) -> dict[str, Any]:
        return {"nuslist": list(self.nuslist), ...}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NusSchedule":
        return cls(**d)
```
If the planner decides a `NusReconstructionResult`/processed-spectrum model belongs here (vs. a plain `@dataclass` in `runner.py` — CONTEXT.md leaves this to planner/executor discretion), follow this exact shape: `ConfigDict(arbitrary_types_allowed=True)`, explicit typed fields (no `Any` where avoidable), a `field_validator` only where a real invariant exists (e.g. FnMODE-recognition reuse), and `to_dict()`/`from_dict()` pair for JSON CLI output — matching the existing `--format json` convention in `cli/nus.py`.

---

### `src/lucy_ng/cli/nus.py` (route/controller, request-response)

**Analog:** same file's existing `params`/`schedule` commands (Phase 97, lines 70-142).

**Import-safe deferred-import group pattern** (cli/nus.py lines 1-26):
```python
"""Lucy NUS (Non-Uniform Sampling) reconstruction CLI commands.

This module is import-safe: it does NOT import ``lucy_ng.nus.params``,
``lucy_ng.nus.schedule``, or ``lucy_ng.nus.backends`` at the top level. All
``lucy_ng.nus.*`` imports are deferred into command bodies so that the core
``lucy`` CLI stays importable without the optional ``[nus]`` extra (NUS-05).
"""

from __future__ import annotations

import json
from pathlib import Path

import click


@click.group()
def nus() -> None:
    """NUS (Non-Uniform Sampling) 2D reconstruction commands."""
```

**Command skeleton to copy for `reconstruct`** (cli/nus.py lines 113-141, `schedule` command — closest existing command since it both parses an `expdir` and reports a computed/validated result):
```python
@nus.command("schedule")
@click.argument("expdir", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def schedule(expdir: str, output_format: str) -> None:
    """Parse the Bruker NUS sampling schedule (nuslist) from EXPDIR.
    ...
    """
    from lucy_ng.nus.schedule import read_nus_schedule

    resolved = Path(expdir).resolve()
    model = read_nus_schedule(resolved)

    if output_format == "json":
        click.echo(json.dumps(model.to_dict(), indent=2))
    else:
        click.echo(f"FnMODE (F1): {model.fnmode_f1}")
        ...
```
`reconstruct` should follow this exact shape: `@click.argument("expdir", type=click.Path(exists=True))`, the same `--format` option, a deferred `from lucy_ng.nus.runner import NusRunner` (or equivalent) inside the command body, and `--format json` emitting the result's `to_dict()`. Add RECON-05's iteration-count/threshold/virtual-echo flags as additional `@click.option`s on the same command (e.g. `--max-iter`, `--threshold`, `--virtual-echo/--no-virtual-echo`), following the descriptive-flag-naming recommendation in RESEARCH.md's Alternatives Considered table (lucy-ng's own names, mapped internally to SMILE's `-maxIter`/`-thresh`/`-EA`).

**D-02's "no dead stubs" note (cli/nus.py lines 10-13, 138-141):** the existing test `TestImportSafety::test_nus_group_help_lists_only_implemented_subcommands` (tests/test_cli_nus.py lines 138-147) currently hard-asserts `set(nus.commands) == {"check", "params", "schedule"}` — this assertion **must be updated** in the same change that adds `reconstruct` (add `"reconstruct"` to the expected set), otherwise this phase's own CI will fail on an intentionally-outdated regression guard. Flag this explicitly to the planner as a required companion edit to `tests/test_cli_nus.py`.

**`_require_*_extra()` pattern (only if a new pip dependency is introduced — RESEARCH.md says none should be):** `cli/webview.py` lines 22-35:
```python
def _require_webview() -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as exc:
        raise click.ClickException(
            "The webview extra is not installed.\n"
            "Install with: pip install lucy-ng[webview]"
        ) from exc
```
Not needed this phase per RESEARCH.md ("No new pip-installable Python packages are required") — included here only in case an executor discovers a genuine new pip dependency mid-implementation; do not add a `[nus]` extra guard for external binaries (those already use `NmrPipeSmileBackend.diagnose()`/`is_available()`, not a pip-import guard).

---

## Shared Patterns

### Fail-loud subprocess wrapper (RECON-04 correctness anchor)
**Source:** `src/lucy_ng/lsd/runner.py::LSDRunner._execute_lsd` (lines 262-352, the "check the actual output artefact, not just returncode" convention) + RESEARCH.md Pattern 2's concrete `run_stage()` implementation (quoted in full above).
**Apply to:** every external-tool invocation in `nus/runner.py` (bruk2pipe, nusExpand.tcl, SMILE) and `nus/postprocess.py` (FT/PS/baseline). One shared helper — do not duplicate the check per call site.

### Fixed-arg-list, never-`shell=True` subprocess safety
**Source:** `src/lucy_ng/nus/backends/nmrpipe_smile.py::smile_plugin_available` (lines 75-90) and `src/lucy_ng/lsd/runner.py` throughout (e.g. lines 293-299).
**Apply to:** every new subprocess call this phase introduces. `expdir` is resolved via `Path(expdir).resolve()` first (existing convention in `nus/params.py` line 64, `nus/schedule.py` line 117) — never string-concatenated into a shell command.

### Refuse-to-guess on unrecognized FnMODE
**Source:** `src/lucy_ng/nus/schedule.py::expected_sample_count()` (lines 33-58) — raises `NotImplementedError` rather than defaulting to either real/complex branch.
**Apply to:** the new `_ordering_for_fnmode()`-style helper in `runner.py` (Critical Finding 1's stage-order branch) — same refuse-to-guess convention, same `REAL_FNMODES`/`COMPLEX_FNMODES` constants imported from `models/nus.py`, never a second divergent FnMODE table.

### Consume Phase 97 params/schedule, never re-parse
**Source:** `src/lucy_ng/nus/params.py::read_nus_params` / `src/lucy_ng/nus/schedule.py::read_nus_schedule` (full files, already complete).
**Apply to:** `nus/runner.py`'s `reconstruct()` entrypoint — call these two functions once at the top; never call `ng.bruker.read_acqus_file`/`read_procs_file`/`read_nuslist` a second time inside `runner.py` or `postprocess.py`. Use `NusSchedule.nus_td`/`NusAcquisitionParams.nus_td` for bruk2pipe's `-yN`/`-yT` (Critical Finding 2) — never `max(nuslist)+1` or `f1_td`.

### CLI: deferred imports + `--format json` + `Path.resolve()`
**Source:** `src/lucy_ng/cli/nus.py` (whole file, Phase 97) — `params`/`schedule` commands.
**Apply to:** the new `reconstruct` command in the same file.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| ppm-axis reversal + 1D-calibration arithmetic (likely a small function inside `nus/postprocess.py`) | utility (transform) | transform | No existing lucy-ng module does ppm-axis math from SF/OFFSET/O1; nearest conceptual precedent is `models/nus.py`'s already-parsed calibration fields (`f2_sf`/`f2_offset`/`f1_sf`/`f1_offset`) plus the ground-truth 1D shifts in `NUS-RECONSTRUCTION-GUIDE.md` §10 — planner should treat RESEARCH.md's own arithmetic description as the spec, not an in-repo analog. |
| COSY (QF/magnitude) bruk2pipe↔nusExpand.tcl exact flag/order recipe | service (external-tool integration) | request-response | RESEARCH.md's own Assumptions Log A1/A3 flags this as unverified against a primary source (SMILE manual only fully documents the echo-antiecho/expand-first path); planner should schedule an implementation-time spike against real exp2 data rather than trust a hard-coded guess, per RESEARCH.md's explicit recommendation. |

## Test Patterns (D-04)

**Mocked-subprocess unit tests — analog:** `tests/test_lsd_runner.py::TestLSDRunnerMocked` (lines 208-253) and `TestInvokeOutlsd` (lines 494-539):
```python
class TestLSDRunnerMocked:
    """Tests with mocked subprocess for consistent behavior."""

    def test_timeout_handling(self, monkeypatch):
        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="lsd", timeout=60)
        monkeypatch.setattr(subprocess, "run", mock_run)
        ...
```
and `tests/test_nus_backends.py::TestNusBackendSubprocessSafety::test_probe_uses_fixed_arg_list_no_shell` (lines 139-160) — capture `subprocess.run`'s args/kwargs via a fake, then assert argv/timeout/no-`shell` kwarg. Use this exact `monkeypatch.setattr(subprocess, "run", ...)` shape for:
- RECON-01: mocked dispatch test (assert bruk2pipe/nusExpand.tcl/SMILE argv sequences)
- RECON-02: ordering-gate test (mock `_resolve_f2_plan` to return `None`, assert `RuntimeError` raised **before** `subprocess.run` is ever called — reuse the `_fail_if_called` assertion-in-mock trick from `tests/test_nus_backends.py` lines 42-47)
- RECON-03: FnMODE branching test (assert `_ordering_for_fnmode(6) == "expand_first"`, `_ordering_for_fnmode(1) == "convert_first"`, unrecognized FnMODE raises `NotImplementedError`)
- RECON-04: fail-loud wrapper tests (non-zero exit → raises; exit 0 but empty output file → raises) — mirror `tests/test_lsd_runner.py::TestInvokeOutlsd::test_fail_loud_on_empty_output` (lines 519-539)

**Backend-gated real integration test (external data path, not copied into repo) — analog:** `tests/test_hmbc_peak_picking_integrity.py` lines 51-56 + 143-156 (external-path `Path(...).exists()` skipif) combined with `tests/test_lsd_runner.py::TestLSDRunnerFixed` lines 265-269 (`shutil.which(...)` skipif):
```python
# External data path (outside the repo), mirrors the CASE1-external skipif pattern.
C20H32O2_EXTERNAL = Path(
    "/Users/steinbeck/Dropbox/develop/data/nmrdata"
    "/active-lucy-ng-testprojects/C20H32O2"
)

@pytest.mark.skipif(
    not NmrPipeSmileBackend.is_available() or not C20H32O2_EXTERNAL.exists(),
    reason="NMRPipe+SMILE backend or external C20H32O2 data not available",
)
def test_reconstruct_exp3_hsqc_end_to_end(tmp_path: Path) -> None:
    ...
```
This combined `backend.is_available() or not data.exists()` skipif condition is the correct D-04 shape — do not split into two separate always-both-present assumptions; either missing condition should skip cleanly (matches `tests/test_nus_backends.py`'s own "this dev machine has no NMRPipe" framing, lines 1-6).

**CLI flag surface test — analog:** `tests/test_cli_nus.py::TestNusParams`/`TestNusSchedule` (JSON assertions against fixture dirs, lines 44-121) for the *shape* of a new `TestReconstructCommand` class; use `CliRunner().invoke(nus, ["reconstruct", ...])` the same way.

## Metadata

**Analog search scope:** `src/lucy_ng/lsd/`, `src/lucy_ng/nus/`, `src/lucy_ng/models/nus.py`, `src/lucy_ng/models/spectrum.py`, `src/lucy_ng/cli/nus.py`, `src/lucy_ng/cli/webview.py`, `src/lucy_ng/cli/lsd.py`, `tests/test_lsd_runner.py`, `tests/test_nus_backends.py`, `tests/test_cli_nus.py`, `tests/test_hmbc_peak_picking_integrity.py`
**Files scanned:** 13
**Pattern extraction date:** 2026-07-13
