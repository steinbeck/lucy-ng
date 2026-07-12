---
phase: 97-backend-integration-params-schedule
reviewed: 2026-07-12T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/lucy_ng/models/nus.py
  - src/lucy_ng/nus/params.py
  - src/lucy_ng/nus/schedule.py
  - src/lucy_ng/nus/backends/__init__.py
  - src/lucy_ng/nus/backends/nmrpipe_smile.py
  - src/lucy_ng/cli/nus.py
  - src/lucy_ng/cli/main.py
  - src/lucy_ng/nus/__init__.py
findings:
  critical: 0
  warning: 7
  info: 5
  total: 12
status: issues_found
---

# Phase 97: Code Review Report

**Reviewed:** 2026-07-12
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the NUS backend-detection + params/schedule parsing implementation against the phase's own RESEARCH.md/CONTEXT.md ground truth. The domain-correctness crux items called out in the review brief all check out under direct execution against the real C20H32O2 fixtures (`exp2_cosy`/`exp3_hsqc`/`exp4_hmbc`):

- `fnmode_f1`/`nus_td` are read from `acqu2s`, never `acqus`'s vestigial `FnMODE=0` — verified (`params.py` `require("acqu2s", "FnMODE")`).
- The `n_sampled == len(nuslist)` assertion branches correctly: QF/FnMODE=1 → `TD==len` (exp2: 188==188), Echo-AntiEcho/FnMODE=6 → `TD/2==len` (exp3: 50==100//2, exp4: 116==232//2) — verified by running `read_nus_params`/`read_nus_schedule` directly against all three fixtures.
- An unrecognized FnMODE raises `NotImplementedError` rather than guessing (`expected_sample_count`).
- `nuslist` is read via `ng.bruker.read_nuslist()` in on-disk (acquisition) order and never sorted; confirmed unsorted order preserved (`[0, 124, 431, 670, ...]` for exp2).
- The SMILE capability probe (`nmrPipe -fn SMILE -help`) uses a fixed hard-coded arg list, `shell=True` is never used, and no user input is interpolated into the command — matches the security requirement.
- `cli/nus.py`'s `params`/`schedule` commands use `click.Path(exists=True)` + `Path(...).resolve()`.
- `cli/nus.py` has zero top-level `lucy_ng.nus.*` imports (deferred into command bodies); `nus/__init__.py` intentionally does top-level imports of core-dependency-only submodules, as documented and permitted by the phase brief.
- `mypy src/lucy_ng/nus src/lucy_ng/models/nus.py src/lucy_ng/cli/nus.py` produces no new errors beyond the pre-existing, project-wide "nmrglue has no stubs" note (same as `readers/bruker.py`).
- All 83 existing NUS unit/CLI tests pass.

However, several robustness/quality gaps remain that should be fixed before this ships, plus one concrete CI-breaking lint failure. None of the findings below rise to Critical (no security vulnerability, data-loss, or crash was found in the currently-exercised 2D/single-column code paths), but several are latent correctness risks that violate the phase's own stated "never silently drop/guess data" philosophy once the code is exercised outside today's fixture set.

## Warnings

### WR-01: `NusSchedule`'s core invariant (`n_sampled == len(nuslist)`) is not enforced by the model itself

**File:** `src/lucy_ng/models/nus.py:129-156`
**Issue:** The FnMODE-derived hard assertion (`n_sampled == len(nuslist)`) — described everywhere in this phase's docs as "the correctness crux (NUS-03)" — is only enforced procedurally, inside `nus/schedule.py::read_nus_schedule()`, before the model is constructed. `NusSchedule` itself has no `model_validator` cross-checking `n_sampled`/`fnmode_f1`/`td_f1`/`len(nuslist)` against each other. Any other construction path — `NusSchedule(**d)`/`NusSchedule.from_dict(d)` (e.g. deserializing a cached/persisted JSON blob in Phase 98/99, or a future caller that builds the model directly) — silently accepts internally-inconsistent data (e.g. `n_sampled` not matching `len(nuslist)`, or not matching what `fnmode_f1`/`td_f1` imply). This contradicts the model's own docstring claim of being a "Validated NUS sampling schedule."
**Fix:** Add a `model_validator(mode="after")` to `NusSchedule` that re-derives the expected count from `fnmode_f1`/`td_f1` (reusing `expected_sample_count`) and raises if it disagrees with `n_sampled` or `len(nuslist)`, so the invariant holds regardless of construction path:
```python
from pydantic import model_validator

@model_validator(mode="after")
def _validate_sample_count(self) -> "NusSchedule":
    from lucy_ng.nus.schedule import expected_sample_count  # or inline the rule here to avoid a cycle
    expected = expected_sample_count(self.fnmode_f1, self.td_f1)
    if expected != self.n_sampled or self.n_sampled != len(self.nuslist):
        raise ValueError(
            f"Inconsistent NusSchedule: fnmode_f1={self.fnmode_f1} td_f1={self.td_f1} "
            f"implies n_sampled={expected}, but n_sampled={self.n_sampled} and "
            f"len(nuslist)={len(self.nuslist)}."
        )
    return self
```
(Watch for the import cycle — either move `expected_sample_count`/`REAL_FNMODES`/`COMPLEX_FNMODES`-based logic into `models/nus.py` itself, or keep the procedural check in `schedule.py` as today but *also* duplicate a cheap validator in the model so `from_dict`/direct construction stay safe.)

### WR-02: `nuslist` parsing silently truncates any row with more than one column

**File:** `src/lucy_ng/nus/schedule.py:123-126`
**Issue:** `nuslist = [row[0] for row in raw_nuslist]` unconditionally takes only the first element of each `nmrglue`-parsed row. The module's own docstring (lines 13-22) and 97-RESEARCH.md explicitly acknowledge this project's schedules are "single-column" *today*, but nothing asserts that. If a 3D-NUS or otherwise multi-column `nuslist` file were ever fed to this function (malformed input, wrong experiment, future extension), the second+ columns would be silently discarded with no error — directly contradicting the "never sort, regenerate, or silently truncate/pad the schedule" principle this exact module states as its own design law for the `len(nuslist)` count.
**Fix:** Assert row shape before flattening:
```python
for row in raw_nuslist:
    if len(row) != 1:
        raise ValueError(
            f"nuslist row has {len(row)} columns, expected 1 (multi-dimensional "
            "NUS schedules are not supported by this reader): {row!r}"
        )
nuslist = [row[0] for row in raw_nuslist]
```

### WR-03: Malformed/blank-line `nuslist` rows raise an unhandled `IndexError` instead of a clear error

**File:** `src/lucy_ng/nus/schedule.py:126`
**Issue:** `nmrglue.bruker.read_nuslist()` splits the file with `.splitlines()`; a file with a trailing blank line (two trailing newlines) produces an empty-tuple row (`()`). `row[0]` on that row raises `IndexError: tuple index out of range`, which is not caught anywhere in `read_nus_schedule()`. Every documented failure mode for this function is `FileNotFoundError`/`NotImplementedError`/`ValueError` (see its own docstring, lines 105-111) — a bare `IndexError` is a confusing, undocumented crash if the schedule file has been hand-edited or regenerated with different line-ending conventions. (Real project fixtures do not hit this, but the risk is real for any future NUS dataset that isn't hand-curated the way the current fixtures are.)
**Fix:** Guard against empty rows explicitly (can be combined with the WR-02 fix above) and raise a clear `ValueError` naming the offending line, rather than an opaque `IndexError`.

### WR-04: Ruff lint failure — line too long in `cli/nus.py`

**File:** `src/lucy_ng/cli/nus.py:103`
**Issue:** `ruff check src/lucy_ng/cli/nus.py` fails with `E501 Line too long (101 > 100)`:
```
click.echo(f"NUS: amount={model.nus_amount_pct}% seed={model.nus_seed} NusTD={model.nus_td}")
```
Per this project's `CLAUDE.md`, `ruff check src tests` is a required command; this line currently breaks that gate.
**Fix:** Wrap the f-string across lines, e.g.:
```python
click.echo(
    f"NUS: amount={model.nus_amount_pct}% seed={model.nus_seed} "
    f"NusTD={model.nus_td}"
)
```

### WR-05: `nus_amount_pct: int` is too strict for the field it represents

**File:** `src/lucy_ng/models/nus.py:60-61`
**Issue:** `NusAMOUNT` is a NUS sampling percentage. All three real fixtures happen to use whole-number percentages (25, 25, 33), but Bruker's NUS setup UI does not guarantee integral percentages (e.g. 12.5%, 33.3% are legitimate configurations). Pydantic v2's default ("smart") coercion mode accepts a `float` for an `int` field only when it has no fractional part; a genuinely fractional `NusAMOUNT` value from a future NUS experiment would raise a `ValidationError` inside `read_nus_params()`, turning a perfectly valid acquisition into a hard failure with a confusing pydantic error rather than a domain-specific one.
**Fix:** Type `nus_amount_pct: float` (matches how `grpdly`/`decim` are already stored as float "non-integer in practice — never round"), or explicitly document/validate that only integral percentages are supported if that is truly guaranteed by the acquisition hardware.

### WR-06: `smile_plugin_available()` can raise despite its own "never raises" docstring guarantee

**File:** `src/lucy_ng/nus/backends/nmrpipe_smile.py:72-90`
**Issue:** The docstring promises `"Returns: True if the probe succeeds, False otherwise (never raises)."` The `except` clause only catches `(OSError, subprocess.TimeoutExpired)`. `subprocess.run(..., text=True)` decodes stdout/stderr using the platform's default encoding; if the SMILE plugin's `-help` output contains any byte sequence that isn't valid in that encoding (e.g. a stray non-UTF-8 byte on a misconfigured locale), `subprocess.run` raises `UnicodeDecodeError`, which is **not** an `OSError` subclass and is therefore not caught — violating the "never raises" contract that `is_available()`/`diagnose()`/`lucy nus check` all rely on for a clean CLI experience.
**Fix:** Either widen the except clause to also catch `UnicodeDecodeError`, or decode defensively:
```python
try:
    proc = subprocess.run(
        ["nmrPipe", "-fn", "SMILE", "-help"],
        capture_output=True,
        timeout=10,
    )
except (OSError, subprocess.TimeoutExpired):
    return False
combined = (
    proc.stdout.decode("utf-8", errors="replace")
    + proc.stderr.decode("utf-8", errors="replace")
).lower()
```

### WR-07: Calibration parameters silently depend on `nmrglue`'s implicit `pdata` folder-guessing fallback

**File:** `src/lucy_ng/nus/params.py:70-71, 115-118`
**Issue:** The module docstring and `NusAcquisitionParams`'s docstring both state calibration is read from `pdata/1/procs`/`pdata/1/proc2s` specifically. The implementation calls `ng.bruker.read_procs_file(str(resolved))` with no explicit `procs_files` argument, delegating folder selection entirely to `nmrglue`'s internal fallback logic, which (per the installed `nmrglue` source) silently substitutes the *first available* `pdata/<n>` folder if `pdata/1` doesn't exist (e.g. `pdata/2` from a stale/alternate processing run) — with no indication to the caller which folder was actually used. `NusAcquisitionParams`'s `f2_sf`/`f2_offset`/`f1_sf`/`f1_offset` could therefore silently reflect a different processing run's calibration than the one the docstring documents, with no error, warning, or provenance field recording which `pdata/<n>` was actually read.
**Fix:** Pass explicit file paths (e.g. `ng.bruker.read_procs_file(procs_files=[str(resolved / "pdata" / "1" / "procs"), str(resolved / "pdata" / "1" / "proc2s")])`) so the function fails loud (nmrglue emits a `warn()` today, not an exception, for a missing explicit path — verify and upgrade to a raised `ValueError` if it doesn't already) rather than silently falling back to a different pdata folder.

## Info

### IN-01: `VALID_NUCLEI` duplicated verbatim between `models/nus.py` and `models/spectrum.py`

**File:** `src/lucy_ng/models/nus.py:22`
**Issue:** `models/nus.py` defines a module-level `VALID_NUCLEI = {"1H", "13C", "15N", "31P", "19F", "2H"}` constant; `models/spectrum.py:34` defines the identical set inline inside its own `validate_nucleus` method (`valid_nuclei = {...}`). This is a pre-existing duplication pattern that Phase 97 continues rather than consolidates — two independent literals that must be kept in sync by hand if a new nucleus is ever added.
**Fix:** Promote to a single shared constant (e.g. `models/_constants.py` or directly in `models/spectrum.py`, imported by `models/nus.py`) so a future edit to one doesn't silently diverge from the other.

### IN-02: Unneeded `arbitrary_types_allowed=True` on both NUS models

**File:** `src/lucy_ng/models/nus.py:42, 142`
**Issue:** Both `NusAcquisitionParams` and `NusSchedule` set `model_config = ConfigDict(arbitrary_types_allowed=True)`, copied from `Spectrum1D`/`Spectrum2D` (which need it for `NDArray[np.float64]` fields). Neither NUS model has any field type pydantic doesn't natively understand (all are `str`/`int`/`float`/`list[int]`/`None`), so the setting is dead configuration that could mask a future accidental introduction of an unvalidated arbitrary-type field.
**Fix:** Drop `model_config` from both classes (or keep only if a genuine non-native type is added later).

### IN-03: `validate_fnmode_f1` validator logic duplicated between the two models

**File:** `src/lucy_ng/models/nus.py:87-93, 150-156`
**Issue:** The exact same validator body (check membership in `VALID_FNMODES`, raise with the same message shape) is written twice, once per class. `REAL_FNMODES`/`COMPLEX_FNMODES`/`VALID_FNMODES` are correctly shared as module constants, but the validator function itself is copy-pasted.
**Fix:** Factor into a shared helper (e.g. a module-level `_validate_fnmode(v: int) -> int` function both `field_validator`s call), reducing drift risk if the error message or logic changes.

### IN-04: `byte_order`/`dtype_code` accept any `int` with no semantic range check

**File:** `src/lucy_ng/models/nus.py:53-54`
**Issue:** Per the docstrings and 97-RESEARCH.md, `BYTORDA` is only ever `0` (little-endian) or `1` (big-endian), and `DTYPA` is only ever `0` (int32) or `1` (float64) in practice. Neither field has a validator constraining values to `{0, 1}`, so a corrupt or unexpected acqus value (e.g. `2`) would pass model validation silently and could cause a confusing downstream failure in Phase 98's reconstruction code rather than failing loud here where the value was actually read.
**Fix:** Consider a `field_validator` (or `Literal[0, 1]` typing) if the domain truly only ever produces these two values; otherwise document why the field is intentionally left open-ended.

### IN-05: `read_nus_schedule()` couples schedule parsing to the full `NusAcquisitionParams` superset

**File:** `src/lucy_ng/nus/schedule.py:121`
**Issue:** `read_nus_schedule()` calls `read_nus_params()` to obtain `fnmode_f1`/`f1_td`/`nus_td`, which means it also validates (and can fail on) every other field in `NusAcquisitionParams` — nucleus allowlist, `PULPROG`, calibration files, etc. — none of which `NusSchedule` itself needs. This is a defensible DRY tradeoff, but it means `lucy nus schedule <dir>` can fail with an error about, say, an unrecognized nucleus or a missing `PULPROG`, which is confusing for a command whose only documented job is schedule/FnMODE validation.
**Fix:** No change strictly required, but consider either a lighter-weight "read only FnMODE/TD/NusTD" helper for `schedule.py`'s use, or at minimum a note in `cli/nus.py schedule`'s docstring/help text that schedule parsing depends on full acquisition-parameter validity.

---

_Reviewed: 2026-07-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
