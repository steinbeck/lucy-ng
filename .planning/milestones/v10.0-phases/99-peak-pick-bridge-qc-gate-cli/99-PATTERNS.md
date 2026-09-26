# Phase 99: Peak-Pick Bridge + QC Gate + CLI - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `src/lucy_ng/nus/bridge.py` (NEW) | service (direct-call bridge) | transform (Spectrum2D → picked peaks → JSON) | `src/lucy_ng/cli/lsd.py::_perform_ranking()` (call-pattern) + `src/lucy_ng/readers/bruker.py::read_2d()` (Spectrum construction) + `src/lucy_ng/cli/pick.py` (JSON shape) | exact (composite) |
| `src/lucy_ng/nus/qc.py` (NEW) | service (pure computation) | batch (peak-list → verdict) | `src/lucy_ng/nus/postprocess.py` (pure-arithmetic module + reuse of `check_calibration`) | role-match |
| `src/lucy_ng/models/nus.py` (MODIFIED — add QC models) | model | CRUD (Pydantic validation) | Same file, existing `NusReconstructionResult`/`NusSchedule` classes | exact |
| `src/lucy_ng/cli/nus.py` (MODIFIED — add `qc`, `pipeline`, optional `peak-pick`) | route/controller (CLI) | request-response | Same file, existing `reconstruct` command | exact |
| `tests/nus/test_bridge.py` (NEW) | test | transform | `tests/nus/test_reconstruct_chain.py` / `tests/nus/conftest.py` fixtures | role-match |
| `tests/nus/test_qc_checks.py` (NEW) | test | batch | `tests/nus/test_processing_order.py` (pure-Python assertions on `postprocess.py` functions) | role-match |
| `tests/nus/test_qc_regression.py` (NEW) | test (fixture-driven regression) | batch | `tests/nus/test_reconstruct_integration.py` (real-fixture-driven test) | role-match |
| `tests/nus/test_write_boundary.py` (NEW) | test | event-driven (write-vs-quarantine branch) | `tests/nus/test_runner_faillloud.py` (fail-loud branch testing) | role-match |

## Pattern Assignments

### `src/lucy_ng/nus/bridge.py` (service, transform)

**Analogs:** `src/lucy_ng/readers/bruker.py::read_2d()` (Spectrum2D construction), `src/lucy_ng/cli/lsd.py::_perform_ranking()` (direct-call pattern), `src/lucy_ng/cli/pick.py::pick_hsqc()`/`pick_hmbc()` (per-peak transform + multiplicity-edit detection)

**Imports pattern** — mirror `readers/bruker.py` lines 1-9:
```python
from pathlib import Path
from typing import Any

import nmrglue as ng
import numpy as np

from lucy_ng.models import Spectrum2D
```
Plus, per `nus/postprocess.py` line 39, defer the `nus.runner`-style internal import inside functions if it would otherwise create an import cycle (the `from __future__ import annotations` + deferred-import convention `nus/postprocess.py` lines 33-41, 117 uses for `run_stage`).

**Spectrum2D construction from `processed.ft2`** (mirrors `readers/bruker.py::read_2d()` lines 197-281, swapping `ng.bruker.*` for `ng.pipe.*`):
```python
# readers/bruker.py:246-281 — the exact idiom to port, format-agnostic via uc_from_udic
udic = ng.bruker.guess_udic(dic, data)          # becomes ng.pipe.guess_udic(dic, data)
uc_f1 = ng.fileiobase.uc_from_udic(udic, dim=0)  # F1 = indirect (13C)
f1_ppm_scale = uc_f1.ppm_scale()
uc_f2 = ng.fileiobase.uc_from_udic(udic, dim=1)  # F2 = direct (1H)
f2_ppm_scale = uc_f2.ppm_scale()

return Spectrum2D(
    data=np.array(data, dtype=np.float64),
    f1_ppm_scale=np.array(f1_ppm_scale, dtype=np.float64),
    f2_ppm_scale=np.array(f2_ppm_scale, dtype=np.float64),
    f1_nucleus=f1_nucleus,
    f2_nucleus=f2_nucleus,
    experiment_type=experiment_type,
    frequency=float(frequency),
    metadata=metadata,
)
```
**F1-axis override:** when `processed_ppm_axis.json` sidecar exists next to `processed.ft2` (written by `nus/postprocess.py::_write_ppm_calibration_sidecar()`, line 306), read its `"calibrated_ppm_axis"` key and use it as `f1_ppm_scale` instead of the raw `ng.pipe.guess_udic` F1 axis — this is the already-1D-calibrated axis (see `nus/postprocess.py` lines 341-365 for the sidecar's exact JSON keys: `raw_ppm_axis`, `calibrated_ppm_axis`, `calibration_offset_ppm`, `reference_shifts`, `axis_size`, `axis_size_source`, `intended_raw_grid_size`, `processed_f1_size`).

**Direct-call pattern** (mirrors `cli/lsd.py::_perform_ranking()` lines 208-282 — build inputs in memory, call the existing subsystem directly, no subprocess):
```python
# cli/lsd.py:280-282
ranker = SolutionRanker(predictor, tolerance=tolerance)
result = ranker.rank(solutions, experimental_shifts, top_n=top)
# bridge.py equivalent:
peaks = PeakPicker2D.pick_peaks(spectrum, threshold=..., use_snr=..., snr_floor=...)
```

**Per-peak JSON schema — CRITICAL, do NOT copy `cli/pick.py`'s raw shape verbatim.** `cli/pick.py::pick_hsqc()`/`pick_hmbc()`/`pick_2d()` (lines 239-253, 326-340, 185-197) emit `f1_position`/`f2_position`/`intensity`/`snr` — this is the **raw picker output shape**, not the CASE-consumed `analysis/nmr_peaks/*.json` schema. The actual target schema (verified by reading the real fixtures on disk) is:
- **HSQC** (`HSQC_exp3.json` real structure): top-level `{"experiment", "caveat", "n_cross_peaks", "cross_peaks"}`; each cross-peak `{"c13_ppm", "h1_ppm", "edited_sign", "multiplicity_hint", "confidence", "note"}`.
- **HMBC** (`HMBC_exp4.json`): cross-peak `{"c13_ppm", "h1_ppm", "rel_intensity", "rank_in_carbon", "suspected_1J_artifact", "confidence", "note"}`.
- **COSY** (`COSY_exp2.json`): cross-peak `{"h1a_ppm", "h1b_ppm", "rel_intensity", "confidence", "note"}`.

The bridge must transform `PeakPicker2D`'s `f1_position`/`f2_position`/`intensity`/`snr` output (F1=13C, F2=1H per `Spectrum2D` convention) into this schema: `c13_ppm = f1_position`, `h1_ppm = f2_position`, `rel_intensity = intensity / max(|intensity|)`. `edited_sign`/`multiplicity_hint` reuse `cli/pick.py::_detect_multiplicity_edited()` (lines 22-55) — currently module-private; promote/export it (planner discretion per Assumption A5) rather than reimplementing the `-0.05 * max_abs` cutoff heuristic. `confidence`/`note` are now QC-verdict-derived (D-06), replacing the blanket `"confidence": "low"` — see the QC section below for the mapping.

**`_detect_multiplicity_edited()` reuse** (`cli/pick.py` lines 22-55, verbatim signature):
```python
def _detect_multiplicity_edited(data: "np.ndarray[Any, Any]") -> tuple[bool, int]:
    """... np.min(data) < -0.05 * max_abs ..."""
    if data.size == 0:
        return False, 0
    finite = np.isfinite(data)
    if not bool(finite.any()):
        return False, 0
    max_abs = float(np.max(np.abs(data[finite])))
    if max_abs == 0.0:
        return False, 0
    cutoff = -0.05 * max_abs
    negative_crosspeak_count = int(np.count_nonzero(finite & (data < cutoff)))
    multiplicity_edited = negative_crosspeak_count > 0
    return multiplicity_edited, negative_crosspeak_count
```

**Error handling pattern** — no fail-loud subprocess wrapper needed here (bridge is pure-Python, no subprocess); instead wrap `json.loads()` on any peak-list file per the project's fail-loud convention (`nus/params.py::read_nus_params` style — raise a clear, typed error rather than propagating a raw `JSONDecodeError`; see Security Domain note in RESEARCH.md V5).

---

### `src/lucy_ng/nus/qc.py` (service, batch)

**Analogs:** `src/lucy_ng/nus/postprocess.py` (pure-Python-arithmetic module structure + direct reuse of `check_calibration()`), `src/lucy_ng/detection/detector.py::detect_hybridisation()` (tier-2 fallback shape, LIMITED — see below)

**Imports pattern** (mirrors `nus/postprocess.py` lines 33-41 — module-level imports for pure computation, deferred imports only where cross-module coupling risk exists):
```python
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
```

**Reuse Phase-98's calibration check — do NOT reimplement** (`nus/postprocess.py` lines 462-490, imported directly):
```python
from lucy_ng.nus.postprocess import check_calibration, GUIDE_S10_C13, DEFAULT_CALIBRATION_TOL

def qc_check_ppm_calibration(hsqc_c13_shifts: list[float]) -> bool:
    return check_calibration(hsqc_c13_shifts, GUIDE_S10_C13, tol=DEFAULT_CALIBRATION_TOL)
    # DEFAULT_CALIBRATION_TOL == 0.5, matching D-04's seed 13C tolerance exactly.
```
`GUIDE_S10_C13` (postprocess.py lines 45-66) is the full 20-shift ground-truth list already in the codebase — use it directly rather than re-deriving from `NUS-RECONSTRUCTION-GUIDE.md` §10.

**Ridge-fraction (signal-to-ridge, critical check) — genuinely new code, peak-list-only:**
```python
# New — grounded against known-bad COSY_exp2.json fixture (7/7 peaks share h1a_ppm=5.32)
from collections import Counter

def ridge_fraction(peaks: list[dict], axis_key: str, tol: float = 0.05) -> float:
    if not peaks:
        return 0.0
    buckets = Counter(round(p[axis_key] / tol) for p in peaks)
    return max(buckets.values()) / len(peaks)
# Recommended starting FAIL threshold: ridge_fraction > 0.5 (unvalidated on PASS side — Phase 100).
```

**Edited-sign self-consistency (soft check):**
```python
from collections import defaultdict

def edited_sign_self_consistent(hsqc_peaks: list[dict], tol: float = 0.5) -> tuple[bool, list[float]]:
    by_carbon: dict[float, set[str]] = defaultdict(set)
    for p in hsqc_peaks:
        key = round(p["c13_ppm"] / tol) * tol
        by_carbon[key].add(p["multiplicity_hint"])
    violations = [c for c, hints in by_carbon.items() if len(hints) > 1]
    return (len(violations) == 0, violations)
# Known-bad HSQC_exp3.json: violations at 22.63, 23.43, 67.06 — the calibration anchor.
```

**Quaternary-exclusion (critical check) — explicit override, NOT `detection/`:**
Known-bad `HSQC_exp3.json`: 4/27 peaks (14.8%) land within ±0.5 ppm of a known-quaternary shift. Use an explicit `known_quaternary_shifts: list[float]` config value (the 5 named quaternaries: 142.00, 135.86, 79.35, 36.23, 37.86 — a subset of `GUIDE_S10_C13`), NOT `detection.detector.StatisticalDetector.detect_hybridisation()`. **Confirmed gap:** `detect_hybridisation()` (`detection/detector.py` lines 58-88) returns only `sp3_count`/`sp2_count`/`sp1_count` distributions — it has NO hydrogen-count / CH-vs-Cq field. Do not call it for prot/quaternary classification; it will silently misclassify a quaternary sp3 carbon (e.g. 36.23) as "protonated." Three-tier resolution (DEPT if present → explicit override → `"insufficient_reference_data"` honest soft-skip) per RESEARCH.md Pitfall 1.

**Verdict aggregation (D-02 — critical vs. soft):**
```python
# Pattern: aggregate_verdict() — the one auditable function, analogous to
# nus/runner.py::recipe_for_fnmode()'s "single auditable table" style (lines 223-245)
CRITICAL_CHECKS = {"quaternary_exclusion", "ppm_calibration", "signal_to_ridge", "hsqc_coverage"}
SOFT_CHECKS = {"edited_sign_consistency", "cosy_diagonal_symmetry"}

def aggregate_verdict(results: dict[str, bool]) -> QcVerdict:
    if any(not results[c] for c in CRITICAL_CHECKS if c in results):
        return QcVerdict.FAIL
    if any(not results[c] for c in SOFT_CHECKS if c in results):
        return QcVerdict.PARTIAL
    return QcVerdict.PASS
```

**Error handling pattern:** wrap per-file JSON parsing (`json.loads()` on `analysis/nmr_peaks/*.json` and the arbitrary `<peaks-dir>` glob targets) in try/except reporting a clear per-file error inside `QcReport`, never crashing the whole `qc`/`pipeline` command (Security Domain V5 note in RESEARCH.md). Mirrors the existing fail-loud-but-typed-error convention in `nus/runner.py::run_stage()` (lines 88-118) — raise a specific, descriptive error, never a bare traceback.

---

### `src/lucy_ng/models/nus.py` (model, CRUD — additive)

**Analog:** same file, existing `NusReconstructionResult` class (lines 174-233) and `NusSchedule` (lines 129-171)

**Pattern to copy** — Pydantic v2 model with `model_config = ConfigDict(arbitrary_types_allowed=True)`, `field_validator`, `to_dict()`/`from_dict()` pair, and (for the top-level result) a `summary()` human-readable method:
```python
# models/nus.py:174-233 structure to mirror for QcVerdict/QcCheckResult/QcReport
class NusReconstructionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    success: bool
    backend: str
    ...
    def to_dict(self) -> dict[str, Any]:
        return {...}
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NusReconstructionResult":
        return cls(**d)
    def summary(self) -> str:
        ...
```
Add: `QcVerdict` (str `Enum`: `PASS`/`PARTIAL`/`FAIL`, matching the project's plain-string-Choice convention used elsewhere, e.g. `click.Choice(["text", "json"])`), `QcCheckResult` (per-check name/passed/critical/details), `QcReport` (verdict + list of `QcCheckResult` + thresholds-used dict — same `to_dict()`/`from_dict()` convention).

---

### `src/lucy_ng/cli/nus.py` (route/controller, request-response — MODIFY, add commands)

**Analog:** same file, existing `reconstruct` command (lines 146-254) and the file's own import-safe module docstring convention (lines 1-16)

**Import-safe pattern — MUST preserve** (file docstring, lines 1-16, and `_require_webview()` pattern in `cli/webview.py` lines 22-35): `cli/nus.py` does NOT import `lucy_ng.nus.*` at module level. All `lucy_ng.nus.*` imports are deferred into command bodies:
```python
# cli/nus.py:31-50 (check command) — the deferred-import convention to copy verbatim
@nus.command("check")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True, help="Output format.")
def check(output_format: str) -> None:
    from lucy_ng.nus.backends import get_backend  # deferred, inside command body
    backend = get_backend()
    ...
```
Apply the same deferred-import shape to `qc` (`from lucy_ng.nus.qc import run_qc_checks`) and `pipeline` (`from lucy_ng.nus.runner import NusRunner`, `from lucy_ng.nus.bridge import bridge_peak_pick`, `from lucy_ng.nus.qc import run_qc_checks`).

**`--format json` convention** — every subcommand, verbatim option block (lines 32-39, repeated per command):
```python
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
```

**Thin-CLI-wrapper-over-library pattern** — `reconstruct` command body (lines 233-253) is the exact shape `pipeline` should follow: resolve path, call the library function/class, branch on `output_format`:
```python
def reconstruct(expdir: str, ..., output_format: str) -> None:
    from lucy_ng.nus.runner import NusRunner
    resolved = Path(expdir).resolve()
    result = NusRunner().reconstruct(resolved, ...)
    if output_format == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        click.echo(f"Backend: {result.backend}")
        ...
```
Per RESEARCH.md Open Question 1 recommendation: keep `nus/qc.py` pure (compute `QcReport`, file-reads only for reference JSON); put the write/quarantine branching (D-07) in `cli/nus.py::pipeline`'s command body, matching this thin-CLI convention (fat library, thin command).

**`lucy nus qc <peaks-dir>` command shape** (new, but same skeleton as `params`/`schedule` commands, lines 72-113 and 115-143 — `click.argument(..., type=click.Path(exists=True))` + `Path(...).resolve()` + `--format json`):
```python
@nus.command("qc")
@click.argument("peaks_dir", type=click.Path(exists=True))
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True, help="Output format.")
def qc(peaks_dir: str, output_format: str) -> None:
    from lucy_ng.nus.qc import run_qc_checks
    resolved = Path(peaks_dir).resolve()
    report = run_qc_checks(resolved)
    if output_format == "json":
        click.echo(json.dumps(report.to_dict(), indent=2))
    else:
        ...
    if report.verdict == "FAIL":
        raise SystemExit(1)
```

---

## Shared Patterns

### Direct-call bridge (no subprocess)
**Source:** `src/lucy_ng/cli/lsd.py::_perform_ranking()` (lines 208-282)
**Apply to:** `nus/bridge.py`, and `pipeline`'s in-process orchestration of bridge + qc after `NusRunner.reconstruct()` returns.
```python
# build inputs in memory -> direct Python call to existing subsystem -> return/echo result
predictor = resolve_c13_predictor(db=db, table=table, max_radius=max_radius)
ranker = SolutionRanker(predictor, tolerance=tolerance)
result = ranker.rank(solutions, experimental_shifts, top_n=top)
```

### Fail-loud stage wrapper style (subprocess boundary — NOT used by bridge/qc directly, but sets the project's error-handling idiom)
**Source:** `src/lucy_ng/nus/runner.py::run_stage()` (lines 51-118)
**Apply to:** Any error path in `bridge.py`/`qc.py` that needs a specific, typed `RuntimeError` rather than a bare exception — same message-construction convention (`f"NUS stage '{name}' failed ...": {detail!r}"`).

### Pydantic v2 model convention (`to_dict`/`from_dict`, `ConfigDict(arbitrary_types_allowed=True)`)
**Source:** `src/lucy_ng/models/nus.py` (all three existing classes, e.g. `NusReconstructionResult` lines 174-233)
**Apply to:** New `QcVerdict`/`QcCheckResult`/`QcReport` models.

### Import-safe CLI group + deferred `lucy_ng.nus.*` imports
**Source:** `src/lucy_ng/cli/nus.py` module docstring (lines 1-16) + every existing command body; also `src/lucy_ng/cli/webview.py::_require_webview()` (lines 22-35) for the "friendly ClickException on missing optional extra" variant (not needed here since no new external dep is introduced, but the pattern is available if planner decides otherwise).
**Apply to:** `qc`, `pipeline`, optional `peak-pick` commands in `cli/nus.py`.

### `--format json` on every subcommand
**Source:** `src/lucy_ng/cli/nus.py` (all four existing commands), `src/lucy_ng/cli/webview.py` (all four commands)
**Apply to:** `qc`, `pipeline`, optional `peak-pick`.

### Reuse Phase-98 calibration check, do not reimplement
**Source:** `src/lucy_ng/nus/postprocess.py::check_calibration()` / `calibrate_against_1d_reference()` (lines 413-490)
**Apply to:** `qc.py`'s ppm-calibration critical check.

### Test fixture conventions (mocked subprocess boundary, real-fixture regression)
**Source:** `tests/nus/conftest.py` (`nus_fixture_dir`, `make_valid_intermediate`/`make_empty_intermediate`/`make_truncated_intermediate`, `mock_run_stage`, `mock_subprocess_run`)
**Apply to:** `tests/nus/test_bridge.py` (may need its own `make_valid_ft2`-style factory, analogous to `make_valid_intermediate` but nmrglue-readable), `tests/nus/test_write_boundary.py` (mocked reconstruction + peak-pick, real QC-gate logic, mirroring `test_runner_faillloud.py`'s fail-loud-branch assertions).

---

## No Analog Found

None — every file in this phase's scope has at least a role-match analog in the existing codebase (this phase is explicitly "glue + new domain logic over existing, already-tested primitives" per RESEARCH.md Summary). The two genuinely new algorithms (`ridge_fraction()` peak-list-only ridge detection, `aggregate_verdict()` critical/soft aggregation) have no direct code precedent — they are net-new, grounded instead in real fixture data (see RESEARCH.md Common Pitfalls #5 and Code Examples) and in the *structural* pattern of `nus/runner.py::recipe_for_fnmode()`'s "one auditable table" style for the aggregation function.

**Load-bearing test fixtures with no existing analog (net-new, not just no-code-analog):**
| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/fixtures/nus/known_bad_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2}.json` | test fixture | batch | Copy of real known-bad files already on disk at `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/nmr_peaks/` — no repo-tree analog exists yet; small files (~5-13 KB), safe to commit per RESEARCH.md Wave 0 Gaps. |
| `tests/fixtures/nus/clean_peaks_synthetic/` | test fixture | batch | Hand-authored, no real clean reconstruction exists until Phase 100 — this is the phase's own load-bearing new fixture (QC-02's PASS side cannot be proven without it). |

## Metadata

**Analog search scope:** `src/lucy_ng/cli/`, `src/lucy_ng/nus/`, `src/lucy_ng/models/`, `src/lucy_ng/readers/`, `src/lucy_ng/processing/`, `src/lucy_ng/detection/`, `tests/nus/`
**Files read in full:** `src/lucy_ng/cli/lsd.py` (lines 1-330), `src/lucy_ng/readers/bruker.py` (full, 281 lines), `src/lucy_ng/cli/pick.py` (full, 351 lines), `src/lucy_ng/nus/runner.py` (full, 503 lines), `src/lucy_ng/nus/postprocess.py` (full, 490 lines), `src/lucy_ng/cli/nus.py` (full, 253 lines), `src/lucy_ng/cli/webview.py` (full, 162 lines), `src/lucy_ng/models/spectrum.py` (full, 156 lines), `src/lucy_ng/models/nus.py` (full, 233 lines), `src/lucy_ng/processing/peak_picker_2d.py` (full, 289 lines), `src/lucy_ng/nus/backends/nmrpipe_smile.py` (targeted, lines 120-260), `src/lucy_ng/detection/detector.py` (targeted, `detect_hybridisation` lines 58-88), `tests/nus/conftest.py` (full, 166 lines)
**Real fixture data inspected:** `HSQC_exp3.json`, `COSY_exp2.json`, `HMBC_exp4.json` at `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/nmr_peaks/` (top-level keys + first cross-peak of each, confirming the exact per-peak schema the bridge must reproduce)
**Pattern extraction date:** 2026-07-16
