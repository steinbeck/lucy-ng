# Phase 97: Backend Integration + Params/Schedule - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 13 (6 new source, 2 modified, 4 new tests, 1 fixture tree)
**Analogs found:** 13 / 13 (all have at least a role-match; 0 "no analog")

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `src/lucy_ng/nus/__init__.py` | package-init | transform (re-export) | `src/lucy_ng/lsd/__init__.py` | exact |
| `src/lucy_ng/nus/backends/__init__.py` | registry/protocol | request-response | `src/lucy_ng/lsd/runner.py` (class shape) | role-match (no Protocol precedent exists yet — first one in repo) |
| `src/lucy_ng/nus/backends/nmrpipe_smile.py` | service (external-binary detection) | request-response (subprocess) | `src/lucy_ng/lsd/runner.py` (`LSDRunner.SEARCH_PATHS`/`_find_lsd`/`is_available`) | exact |
| `src/lucy_ng/nus/params.py` | service (parser/transform) | file-I/O → transform | `src/lucy_ng/readers/bruker.py` (`_get_param_2d`, `_get_2d_params`) | exact |
| `src/lucy_ng/nus/schedule.py` | service (parser/transform + validation) | file-I/O → transform | `src/lucy_ng/readers/bruker.py` (helper reuse) + new validation logic (no direct analog for the hard-fail assertion; closest shape is fail-loud error patterns in `lsd/runner.py`) | role-match |
| `src/lucy_ng/models/nus.py` | model | CRUD (validated data holder) | `src/lucy_ng/models/spectrum.py` (`Spectrum1D`/`Spectrum2D`) | exact |
| `src/lucy_ng/cli/nus.py` | controller (CLI group) | request-response | `src/lucy_ng/cli/webview.py` (import-safe structure) + `src/lucy_ng/cli/lsd.py` (`lsd check`/`--format json` shape) | exact (two-analog blend) |
| `src/lucy_ng/cli/main.py` (modified) | route registration | request-response | itself — additive `cli.add_command(nus)` following the 13 existing entries | exact |
| `pyproject.toml` (modified, `[nus]` extra) | config | batch (packaging) | `[project.optional-dependencies] prediction = []` (empty-extra precedent) + `webview = [...]` (populated-extra precedent) | exact |
| `tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc}/{acqus,acqu2s,nuslist}` | test fixture (data) | file-I/O | `tests/data/Ibuprofen/{1,2}/` (existing real-Bruker-dir fixture convention) | exact |
| `tests/test_nus_params.py` | test | file-I/O → transform | `tests/test_bruker_reader.py` (real-fixture-dir class-per-concern layout) | exact |
| `tests/test_nus_schedule.py` | test | file-I/O → transform + validation | `tests/test_bruker_reader.py` (fixture layout) + `tests/test_lsd_runner.py` (fail-loud assertion tests) | role-match (blend) |
| `tests/test_nus_backends.py` | test | request-response | `tests/test_lsd_runner.py::TestLSDRunnerAvailability` | exact |
| `tests/test_cli_nus.py` | test | request-response | `tests/test_cli_lsd.py` (`TestLSDCheck`, `--format json`) + `tests/test_cli_webview.py` (`TestImportSafety`, subprocess-based fastapi-leak check) + `tests/test_cli_main.py` (`test_all_command_groups_registered`) | exact (three-analog blend) |

## Pattern Assignments

### `src/lucy_ng/nus/__init__.py` (package-init, transform)

**Analog:** `src/lucy_ng/lsd/__init__.py` (full file, 79 lines)

**Pattern — module docstring + example usage + explicit re-export list:**
```python
"""LSD (Logic for Structure Determination) integration.
...
"""

from lucy_ng.lsd.analyzer import (...)
from lucy_ng.lsd.generator import LSDInputGenerator
from lucy_ng.lsd.models import Hybridization, LSDAtom, LSDConstraint, LSDCorrelation, LSDProblem
from lucy_ng.lsd.runner import LSDResult, LSDRunner

__all__ = [
    # Models
    "Hybridization", "LSDAtom", "LSDConstraint", "LSDCorrelation", "LSDProblem",
    # Runner
    "LSDRunner", "LSDResult",
    ...
]
```
Apply directly: `nus/__init__.py` should re-export `NusAcquisitionParams`, `NusSchedule` (from `models.nus`, or re-exported from `nus.params`/`nus.schedule` if the planner keeps them there), plus the backend registry entry points (`get_backend`, `list_available_backends`) from `nus.backends`. Group under `__all__` with comment headers exactly as `lsd/__init__.py` does (`# Models`, `# Runner`, etc. → here: `# Params`, `# Schedule`, `# Backends`).

**Note:** `nus/__init__.py` does top-level imports of its submodules (unlike `cli/nus.py`, which must stay import-safe). This is fine — `nus/params.py`/`nus/schedule.py`/`nus/backends/nmrpipe_smile.py` only need core deps (`nmrglue`, `pydantic`, `click` stdlib `shutil`/`subprocess`), all already required by the core CLI. Import-safety only matters at the `cli/nus.py` boundary (D-02), not inside `nus/`.

---

### `src/lucy_ng/nus/backends/nmrpipe_smile.py` (service, request-response/subprocess)

**Analog:** `src/lucy_ng/lsd/runner.py`

**SEARCH_PATHS + shutil.which pattern** (`src/lucy_ng/lsd/runner.py:141-161, 382-400`):
```python
class LSDRunner:
    SEARCH_PATHS = [
        "/usr/local/bin/lsd",
        "/usr/bin/lsd",
        "~/.local/bin/lsd",
        "~/bin/lsd",
        "~/LSD/lsd",
        "~/PyLSD/LSD/lsd",
        "~/LSD-3.5.3/lsd",
    ]

    @classmethod
    def _find_lsd(cls) -> Path | None:
        lsd_in_path = shutil.which("lsd")
        if lsd_in_path:
            return Path(lsd_in_path)
        for path_str in cls.SEARCH_PATHS:
            path = Path(path_str).expanduser()
            if path.exists() and path.is_file():
                return path
        return None
```

**`is_available()` classmethod pattern** (`runner.py:442-449`):
```python
@classmethod
def is_available(cls) -> bool:
    """Check if LSD is available on the system."""
    return cls._find_lsd() is not None
```

**Apply to `nmrpipe_smile.py` as (already validated against RESEARCH.md's corrected tool list — do NOT use `smileNus`):**
```python
class NmrPipeSmileBackend:
    REQUIRED_TOOLS = ["nmrPipe", "bruk2pipe", "nusExpand.tcl"]  # real, which()-able

    @classmethod
    def missing_tools(cls) -> list[str]:
        return [t for t in cls.REQUIRED_TOOLS if shutil.which(t) is None]

    @classmethod
    def smile_plugin_available(cls) -> bool:
        """Capability probe (SMILE is an nmrPipe plugin, not a standalone binary)."""
        if shutil.which("nmrPipe") is None:
            return False
        try:
            proc = subprocess.run(
                ["nmrPipe", "-fn", "SMILE", "-help"],
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        combined = (proc.stdout + proc.stderr).lower()
        return "smile" in combined and "unknown function" not in combined

    @classmethod
    def is_available(cls) -> bool:
        return not cls.missing_tools() and cls.smile_plugin_available()
```
This is the RESEARCH.md Pattern 1 code example — already fully aligned with the `LSDRunner` shape (classmethods, `shutil.which` first, list-argument `subprocess.run`, no `shell=True`).

**Fail-loud subprocess convention** (`runner.py:293-299`, list-args, `capture_output=True`, `text=True`, `timeout=`, no shell string interpolation):
```python
proc = subprocess.run(
    [str(self.lsd_path), lsd_input_name],
    capture_output=True,
    text=True,
    timeout=timeout,
    cwd=output_dir,
)
```
Reuse this exact argument style for the `nmrPipe -fn SMILE -help` probe (already shown above) — matches the Security Domain note in RESEARCH.md (V4/Tampering mitigation: fixed arg list, no shell).

**Diagnostic-state pattern (installed-vs-not-sourced, D-01):** No direct repo precedent exists (this is genuinely new logic) — RESEARCH.md's `diagnose()` code example (lines 429-454 of 97-RESEARCH.md) is the reference implementation; it composes `NmrPipeSmileBackend.missing_tools()` (mirrors `LSDRunner._find_lsd()`'s presence-check idiom) with a new `common_nmrbase` existence probe. Use it directly.

---

### `src/lucy_ng/nus/params.py` (service, file-I/O → transform)

**Analog:** `src/lucy_ng/readers/bruker.py`

**Helper reuse — import directly, do not duplicate** (`readers/bruker.py:12-48`):
```python
def _strip_brackets(value: str) -> str:
    """Strip angle brackets from Bruker parameter strings."""
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1]
    return value


def _get_param_2d(dic: dict[str, Any], param_dict: str, key: str, default: Any = None) -> Any:
    """Safely get a parameter from a specific parameter dictionary (acqus or acqu2s)."""
    try:
        value = dic[param_dict][key]
        if isinstance(value, str):
            return _strip_brackets(value)
        return value
    except KeyError:
        return default
```
Import in `nus/params.py` as: `from lucy_ng.readers.bruker import _get_param_2d, _strip_brackets` (per CONTEXT.md Claude's Discretion — reuse via direct underscore-import, do not promote to a shared module unless the planner prefers that). `_get_param_2d`'s `param_dict` argument already generalizes to `"procs"`/`"proc2s"` (verified in RESEARCH.md) — no signature change needed for D-04's SF/OFFSET fields.

**Dict-building pattern to mirror** (`readers/bruker.py:102-127`, `_get_2d_params`):
```python
def _get_2d_params(dic: dict[str, Any]) -> dict[str, Any]:
    return {
        "f2_nucleus": _get_param_2d(dic, "acqus", "NUC1"),
        "f2_frequency": _get_param_2d(dic, "acqus", "SFO1"),
        "f2_sw": _get_param_2d(dic, "acqus", "SW_h"),
        "f1_nucleus": _get_param_2d(dic, "acqu2s", "NUC1"),
        "f1_frequency": _get_param_2d(dic, "acqu2s", "SFO1"),
        "f1_sw": _get_param_2d(dic, "acqu2s", "SW_h"),
        "solvent": _get_param_2d(dic, "acqus", "SOLVENT"),
        "pulse_program": _get_param_2d(dic, "acqus", "PULPROG"),
        "num_scans": _get_param_2d(dic, "acqus", "NS"),
    }
```
`nus/params.py`'s `read_nus_params()` should follow this exact flat-dict-then-model-construction shape (RESEARCH.md's own code example at lines 360-393 of 97-RESEARCH.md is the direct extension of this pattern — reuse it verbatim, it already reads `dic["procs"]`/`dic["proc2s"]` correctly per the SF/OFFSET correction).

**Read entry point — use `ng.bruker.read()`, never `read_pdata()`** (contrast with `readers/bruker.py:154-158, 218-222` which DOES call `read_pdata()` because processed 1r/2rr binaries exist for already-reconstructed data):
```python
# readers/bruker.py (existing, DO NOT copy this call for nus/params.py):
pdata_dir = experiment_dir / "pdata" / "1"
dic, data = ng.bruker.read_pdata(str(pdata_dir))   # <- NUS dirs have no processed binary; this raises OSError
```
`nus/params.py` must instead do `dic, data = ng.bruker.read(expdir)` only (per RESEARCH.md Anti-Patterns) — this is the one place `nus/params.py` deliberately diverges from the `BrukerReader.read_2d` analog, not an oversight.

**Error handling convention** (`readers/bruker.py:149-150, 231-236`, fail-loud on missing required params):
```python
if not experiment_dir.exists():
    raise FileNotFoundError(f"Experiment directory not found: {experiment_dir}")
...
if f1_nucleus is None:
    raise ValueError("NUC1 parameter not found in acqu2s (F1 dimension)")
```
Apply the same explicit-`None`-check-then-`raise ValueError` idiom for any of the D-04 superset fields `nus/params.py` treats as required (vs. the SF/OFFSET fields, which RESEARCH.md says may legitimately be `None` pre-reconstruction — do NOT raise for those, only log/allow `None`).

---

### `src/lucy_ng/nus/schedule.py` (service, file-I/O → transform + validation)

**Analog:** `src/lucy_ng/readers/bruker.py` (file-reading shape) — the FnMODE-derived hard-fail assertion itself has no direct repo precedent; use RESEARCH.md's own verified code example as the reference implementation (lines 397-421 of 97-RESEARCH.md):

```python
REAL_FNMODES = {1, 2}        # QF, QSEQ
COMPLEX_FNMODES = {4, 5, 6}  # States, States-TPPI, Echo-AntiEcho

def expected_sample_count(fnmode: int, td_f1: int) -> int:
    if fnmode in REAL_FNMODES:
        return td_f1
    if fnmode in COMPLEX_FNMODES:
        return td_f1 // 2
    raise NotImplementedError(
        f"FnMODE={fnmode} is not a recognized real/complex mode; "
        "refusing to guess a sample-count relationship."
    )

def validate_schedule(fnmode: int, td_f1: int, nuslist: list[int]) -> None:
    n_sampled = expected_sample_count(fnmode, td_f1)
    if n_sampled != len(nuslist):
        raise ValueError(
            f"NUS schedule length mismatch: FnMODE={fnmode} implies "
            f"n_sampled={n_sampled} (from TD={td_f1}), but nuslist has "
            f"{len(nuslist)} entries. Refusing to proceed — never sort, "
            "regenerate, or silently truncate/pad the schedule."
        )
```

**Nearest "raise, never warn" precedent in the codebase** (`lsd/runner.py`'s success-gating idiom, `runner.py:325-326`):
```python
# Success requires .sol file AND SMILES conversion (no silent false-positive)
success = sol_file.exists() and smiles_path is not None
```
This is the same "fail loud, never silently degrade" philosophy CONTEXT.md/RESEARCH.md require for the `n_sampled == len(nuslist)` assertion — cite it as the project convention precedent even though the mechanics differ (boolean gate vs. raised exception).

**`nuslist` acquisition-order parsing:** use `ng.bruker.read(expdir)["nuslist"]` directly (nmrglue already returns it in acquisition order as `list[tuple[int, ...]]` — verified in RESEARCH.md). Do not hand-roll a text parser (this mirrors the existing project convention in `readers/bruker.py` of delegating all Bruker parsing to `nmrglue`, never regex).

---

### `src/lucy_ng/models/nus.py` (model, CRUD/validated-data)

**Analog:** `src/lucy_ng/models/spectrum.py` (full file, 157 lines)

**ConfigDict + field types pattern** (`models/spectrum.py:10-20`):
```python
class Spectrum1D(BaseModel):
    """1D NMR spectrum data model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: NDArray[np.float64]
    ppm_scale: NDArray[np.float64]
    nucleus: str
    frequency: float
    solvent: str | None = None
    metadata: dict[str, Any] = {}
```
`NusAcquisitionParams`/`NusSchedule` are plain scalar/list fields (no `NDArray`), so `arbitrary_types_allowed=True` may not even be needed — but keep the `model_config = ConfigDict(...)` line present for consistency, and use `str | None = None` for the optional SF/OFFSET fields (pre-reconstruction case).

**field_validator pattern for domain-restricted strings** (`models/spectrum.py:30-37`):
```python
@field_validator("nucleus")
@classmethod
def validate_nucleus(cls, v: str) -> str:
    """Validate nucleus is a known NMR-active nucleus."""
    valid_nuclei = {"1H", "13C", "15N", "31P", "19F", "2H"}
    if v not in valid_nuclei:
        raise ValueError(f"Unknown nucleus: {v}. Valid: {valid_nuclei}")
    return v
```
Apply the identical shape to `NusAcquisitionParams.f1_nucleus`/`f2_nucleus` (reuse the same `{"1H", "13C", ...}` set for consistency with `Spectrum2D`) and to a new validator on `NusAcquisitionParams.fnmode_f1` restricting to `{1, 2, 4, 5, 6}` (mirrors `nus/schedule.py`'s `REAL_FNMODES | COMPLEX_FNMODES`, but as a Pydantic-level guard rather than a raised assertion — the two should agree, not duplicate divergent logic; consider having the validator call the same `expected_sample_count`-adjacent constant).

**to_dict/from_dict + numpy-coercion `field_validator(mode="before")` pattern** (`models/spectrum.py:22-28, 39-53`):
```python
@field_validator("data", "ppm_scale", mode="before")
@classmethod
def convert_to_numpy(cls, v: Any) -> NDArray[np.float64]:
    if isinstance(v, np.ndarray):
        return v.astype(np.float64)
    return np.array(v, dtype=np.float64)

def to_dict(self) -> dict[str, Any]:
    """Convert to JSON-serializable dictionary."""
    return {"data": self.data.tolist(), ...}

@classmethod
def from_dict(cls, d: dict[str, Any]) -> "Spectrum1D":
    return cls(**d)
```
`NusSchedule.nuslist` is a plain `list[int]` (JSON-native already, no numpy coercion needed) but should still expose `to_dict()`/`from_dict()` for symmetry with `Spectrum1D`/`Spectrum2D` and to give `cli/nus.py`'s `--format json` output a single canonical serialization path (`json.dumps(model.to_dict())` — matches `cli/lsd.py`'s `json.dumps(data, indent=2)` convention below).

**Cross-field validation (F1/F2 distinction, D-04's "sharper Pitfall 1" trap):** No direct Pydantic `model_validator` precedent exists yet in `models/spectrum.py` (its validators are all single-field). If the planner wants a cross-field guard (e.g. asserting `fnmode_f1` was read from `acqu2s` not `acqus`), this would be the first `@model_validator(mode="after")` in the `models/` package — flag as novel, not a copy-paste case.

---

### `src/lucy_ng/cli/nus.py` (controller, request-response)

**Analog 1 — import-safety structure:** `src/lucy_ng/cli/webview.py` (full file, 163 lines)

**Module docstring declaring the import-safety contract** (`cli/webview.py:1-7`):
```python
"""Lucy webview dashboard server CLI commands.

This module is import-safe: it does NOT import fastapi, uvicorn, or any module
from ``lucy_ng.webview.app`` at the top level.  All webview-extra imports are
deferred into command bodies or into the :func:`_require_webview` guard so that
the core ``lucy`` CLI stays importable without the optional extra (WV-08).
"""
```
`cli/nus.py` should carry an equivalent docstring, adjusted: `nus/params.py`/`nus/schedule.py`/`nus/backends/` use only core deps, so strict deferred-import is not required for *those* by NUS-05 — but Phase 98/99 will add `reconstruct`/`pipeline` commands with real `[nus]` deps, so establishing the deferred-import convention now (even though nothing forces it yet) avoids a Phase 98 refactor. Recommended: defer `from lucy_ng.nus.backends import ...` / `from lucy_ng.nus.params import ...` / `from lucy_ng.nus.schedule import ...` into each command body, exactly as `webview.py` defers `import lucy_ng.webview.server as server` (line 70, 98, 123).

**`_require_*_extra()` guard pattern** (`cli/webview.py:22-35`):
```python
def _require_webview() -> None:
    """Raise a friendly click.ClickException when the webview extra is absent."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as exc:
        raise click.ClickException(
            "The webview extra is not installed.\n"
            "Install with: pip install lucy-ng[webview]"
        ) from exc
```
Not needed verbatim in Phase 97 (zero new deps in `[nus]`), but keep the naming convention (`_require_nus()`) as a documented no-op or omit entirely — planner discretion; if omitted, add a one-line comment noting it will be needed once Phase 98/99 add real `[nus]` deps.

**Command group + `--format json` option pattern** (`cli/webview.py:17-19, 42-62`):
```python
@click.group()
def webview() -> None:
    """Webview dashboard server commands."""


@webview.command("serve")
@click.argument("analysis_dir", type=click.Path(path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def serve(analysis_dir: Path, ..., output_format: str) -> None:
    ...
    if output_format == "json":
        click.echo(json.dumps({"url": state.url, "pid": state.pid, "port": state.port}))
    else:
        click.echo(f"Webview server running at {state.url}")
```

**Analog 2 — `check` command exit-loud shape:** `src/lucy_ng/cli/lsd.py:17-40`
```python
@click.group()
def lsd() -> None:
    """LSD structure elucidation."""
    pass


@lsd.command("check")
def lsd_check() -> None:
    """Check if LSD and outlsd are installed and available."""
    lsd_ok = LSDRunner.is_available()
    outlsd_ok = LSDRunner.is_outlsd_available()

    if lsd_ok:
        click.echo("LSD: available")
    else:
        click.echo("LSD: not found", err=True)

    if outlsd_ok:
        click.echo("outlsd: available (SMILES conversion enabled)")
    else:
        click.echo("outlsd: not found (solution ranking will be limited)")

    if not lsd_ok:
        raise SystemExit(1)
```
`lucy nus check` should follow this exact shape: `NmrPipeSmileBackend.missing_tools()`/`.smile_plugin_available()` in place of `LSDRunner.is_available()`/`is_outlsd_available()`, `click.echo(..., err=True)` for the failure line, `raise SystemExit(1)` at the end when unusable (D-01's "fails loud, like `lucy lsd check`" is a literal instruction to copy this function). Add the D-01 diagnostic-state hint (`installed_not_sourced` vs `not_installed`) as extra `click.echo` lines before the `SystemExit(1)`, and support `--format json` (not present on `lsd check` today — `cli/nus.py` should be a superset, per NUS-04/NUS-01 both requiring JSON where sensible; `lsd check` lacking `--format json` is a known gap in the analog, not something to replicate).

`lucy nus params <expdir> --format json` / `lucy nus schedule <expdir> --format json` should follow `lsd_run`'s output-format branching (`cli/lsd.py:91-111`):
```python
if output_format == "json":
    data = {
        "success": result.success,
        "solution_count": result.solution_count,
        ...
    }
    click.echo(json.dumps(data, indent=2))
else:
    if result.success:
        click.echo(f"LSD completed successfully")
        ...
```
For `nus params`/`nus schedule`, `data = model.to_dict()` (from `models/nus.py`, per the `Spectrum1D.to_dict()` pattern above) replaces the hand-built dict — simpler than `lsd_run`'s case since the model already owns serialization.

**`click.Path(exists=True)` argument convention** (`cli/lsd.py:44`, matches Security Domain's V5 mitigation in RESEARCH.md):
```python
@lsd.command("run")
@click.argument("input_file", type=click.Path(exists=True))
```
Apply to `<expdir>` arguments on `nus params`/`nus schedule` (and any path input `nus check` might eventually take).

---

### `src/lucy_ng/cli/main.py` (modified, additive registration)

**Analog:** the file itself — pure additive pattern, no structural change.

**Import block** (`cli/main.py:6-19`):
```python
from lucy_ng.cli.analyze import analyze
...
from lucy_ng.cli.webview import webview
```
Add: `from lucy_ng.cli.nus import nus` (alphabetical-ish placement between `identify`/`lsd` per existing rough ordering — actual codebase order is not strictly alphabetical, e.g. `pylsd`/`read` — match by inserting near `lsd`/`pylsd` since NUS-01 groups conceptually with `lsd`).

**Registration block** (`cli/main.py:50-64`):
```python
cli.add_command(read)
cli.add_command(pick)
...
cli.add_command(webview)
```
Add: `cli.add_command(nus)` as the final line (matches the file's existing convention of appending new groups at the end — `webview` itself was appended last in a prior phase).

**Docstring command-list update** (`cli/main.py:30-46`, the `\b`-prefixed command summary block in `cli()`'s docstring) — add a `nus` line: `  nus         NUS 2D reconstruction (backend check, params, schedule)` (or similar), matching the one-line-per-group style already used for all 13 existing entries.

---

### `pyproject.toml` (modified, `[nus]` extra)

**Analog — empty-extra precedent** (`pyproject.toml:56-60`):
```toml
prediction = [
    # NOTE: hose-code-generator has broken dependencies (xmlrunner) on Python 3.12
    # Install manually: pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
    # Then install its actual runtime deps: pip install rdkit
]
```

**Analog — populated-extra precedent, for future Phase 98/99 reference** (`pyproject.toml:61-65`):
```toml
webview = [
    "fastapi>=0.100",
    "uvicorn>=0.20",
    "matplotlib>=3.7",
]
```

**Apply (per RESEARCH.md Pattern 2, D-04 discretion resolved to empty-but-present):**
```toml
nus = [
    # No dependencies yet — NUS-01..05 (Phase 97) use only nmrglue/pydantic/click,
    # already core dependencies. Reserved for Phase 98/99 pip-installable pieces
    # (e.g. QC-plotting deps), following the [webview] extra's lazy-import pattern.
]
```
Insert alphabetically or near `prediction`/`webview` in `[project.optional-dependencies]` (existing order is `dev`, `prediction`, `webview` — not strictly alphabetical; append `nus` after `webview` or interleave, planner discretion, low-stakes).

---

## Shared Patterns

### External-binary detection (backend availability)
**Source:** `src/lucy_ng/lsd/runner.py:141-161, 382-400, 442-449`
**Apply to:** `nus/backends/nmrpipe_smile.py`, `nus/backends/__init__.py`'s registry
```python
SEARCH_PATHS = [...]

@classmethod
def _find_x(cls) -> Path | None:
    in_path = shutil.which("x")
    if in_path:
        return Path(in_path)
    for path_str in cls.SEARCH_PATHS:
        path = Path(path_str).expanduser()
        if path.exists() and path.is_file():
            return path
    return None

@classmethod
def is_available(cls) -> bool:
    return cls._find_x() is not None
```

### Import-safe CLI module (core CLI stays dependency-free)
**Source:** `src/lucy_ng/cli/webview.py:1-7, 22-35, 68-70`
**Apply to:** `cli/nus.py` (structural convention now; load-bearing once Phase 98/99 add `[nus]` deps)
```python
"""... This module is import-safe: it does NOT import <heavy-lib> at the top
level. All <extra>-extra imports are deferred into command bodies ... """

def _require_<extra>() -> None:
    try:
        import <heavy_lib>  # noqa: F401
    except ImportError as exc:
        raise click.ClickException(
            "The <extra> extra is not installed.\n"
            "Install with: pip install lucy-ng[<extra>]"
        ) from exc

@group.command("cmd")
def cmd(...) -> None:
    _require_<extra>()
    import <heavy_module>  # deferred
    ...
```

### `--format json` CLI convention
**Source:** `src/lucy_ng/cli/lsd.py:58-64, 91-99`; `src/lucy_ng/cli/webview.py:48-55, 79-82`
**Apply to:** every `lucy nus <subcommand>` (NUS-04 explicitly requires this)
```python
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def cmd(..., output_format: str) -> None:
    ...
    if output_format == "json":
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(<human-readable summary>)
```

### Fail-loud availability check with `SystemExit(1)`
**Source:** `src/lucy_ng/cli/lsd.py:23-40`
**Apply to:** `lucy nus check`
```python
@group.command("check")
def check() -> None:
    ok = Backend.is_available()
    if ok:
        click.echo("<tool>: available")
    else:
        click.echo("<tool>: not found", err=True)
    if not ok:
        raise SystemExit(1)
```

### Pydantic v2 model conventions
**Source:** `src/lucy_ng/models/spectrum.py:10-20, 30-37, 39-53`
**Apply to:** `models/nus.py` (`NusAcquisitionParams`, `NusSchedule`)
```python
class NusX(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)  # keep for consistency even if unused

    field: type
    optional_field: type | None = None
    metadata: dict[str, Any] = {}

    @field_validator("restricted_field")
    @classmethod
    def validate_restricted_field(cls, v: T) -> T:
        valid = {...}
        if v not in valid:
            raise ValueError(f"Unknown value: {v}. Valid: {valid}")
        return v

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NusX": return cls(**d)
```

### Bruker acqus/acqu2s param extraction (reuse, don't duplicate)
**Source:** `src/lucy_ng/readers/bruker.py:12-48`
**Apply to:** `nus/params.py`, `nus/schedule.py` (direct import, per CONTEXT.md Claude's Discretion)
```python
from lucy_ng.readers.bruker import _get_param_2d, _strip_brackets
```

### Test layout — real-fixture-dir, class-per-concern
**Source:** `tests/test_bruker_reader.py:1-13` (DATA_DIR constant + per-nucleus test classes); `tests/test_lsd_runner.py:1-14, 61-73` (`TestLSDRunnerAvailability` isolated class for boolean/availability checks); `tests/test_cli_lsd.py:1-20, 90-98` (`TestLSDCheck`-style CLI class); `tests/test_cli_webview.py:1-13, 38-62` (`TestImportSafety`, subprocess-based leak check)
**Apply to:** all four new test files
```python
DATA_DIR = Path(__file__).parent / "fixtures" / "nus"
EXP2_COSY = DATA_DIR / "exp2_cosy"
EXP3_HSQC = DATA_DIR / "exp3_hsqc"
EXP4_HMBC = DATA_DIR / "exp4_hmbc"

class TestNusParamsCOSY:
    def test_fnmode_f1(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.fnmode_f1 == 1
    ...

class TestNusBackendAvailability:
    def test_is_available_returns_bool(self) -> None:
        assert isinstance(NmrPipeSmileBackend.is_available(), bool)

class TestCliNusCheck:
    def test_check_exit_code_when_unavailable(self) -> None:
        runner = CliRunner()
        result = runner.invoke(nus, ["check"])
        assert result.exit_code == 1  # dev Mac has no NMRPipe installed (RESEARCH.md Environment Availability)
```

## No Analog Found

None. Every file has at least a role-match analog (see table). The two genuinely novel pieces of logic — the FnMODE→sample-count hard-fail assertion (`nus/schedule.py`) and the SMILE plugin capability-probe diagnostic states (`nus/backends/nmrpipe_smile.py`'s `diagnose()`) — have no repo precedent to copy structurally, but RESEARCH.md supplies fully-worked, already-verified-against-real-fixtures reference implementations for both (reproduced in full above); treat those RESEARCH.md code blocks as the authoritative "analog" for these two cases.

## Metadata

**Analog search scope:** `src/lucy_ng/{lsd,cli,readers,models}/`, `tests/` (test_lsd_*, test_cli_*, test_bruker_reader.py), `pyproject.toml`
**Files scanned:** `lsd/runner.py`, `lsd/__init__.py`, `cli/lsd.py`, `cli/webview.py`, `cli/main.py`, `readers/bruker.py`, `models/spectrum.py`, `models/__init__.py`, `pyproject.toml`, `tests/test_lsd_runner.py`, `tests/test_cli_lsd.py`, `tests/test_cli_webview.py`, `tests/test_cli_main.py`, `tests/test_bruker_reader.py`
**Pattern extraction date:** 2026-07-12
