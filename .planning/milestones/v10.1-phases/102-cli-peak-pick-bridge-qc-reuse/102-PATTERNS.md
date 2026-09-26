# Phase 102: CLI + Peak-Pick Bridge + QC Reuse - Pattern Map

**Mapped:** 2026-07-25
**Files analyzed:** 8 (2 new production modules, 1 modified reader, 1 modified CLI registration, 4 new test files, 1 new fixture)
**Analogs found:** 8 / 8

All findings below were verified directly against the current on-disk source
(commit `22f2b52`, matches the repo's current `git log` HEAD) — the phase's
own RESEARCH.md is HIGH confidence and its file/line citations were spot
checked; two corrections to the brief are noted inline (see "Corrections to
the expected file list" below).

## Corrections to the expected file list

- **`src/lucy_ng/processing/edited_sign.py` is NOT a file to create/modify —
  it already exists** (Phase 99) and should simply be imported (or its
  detection logic re-derived) by the new 1D bridge if negative-peak
  auto-detection parity with `cli/pick.py::pick_1d` is wanted (RESEARCH.md
  Open Question 2). Do not re-invent it.
- **`src/lucy_ng/readers/jcamp.py::_resolve_dim` really does raise
  `ValueError` today for homonuclear nucleus lists** (verified by reading
  lines 169–228 directly) — this is a real, in-scope blocking prerequisite,
  not a hypothetical. The fix branch belongs inside this same function
  (extend the `len(matches) > 1` branch), not a new function.
  `readers/jcamp.py` is **not** in the byte-unchanged protected set.
- **The "byte-unchanged skill-file guard" analogs are two DIFFERENT
  mechanisms, not one**: `tests/test_case_md_wv07.py` is a **substring
  content-contract test** (asserts specific text is present/absent — verified
  by reading the file in full, all 4 tests are `case_text = CASE_MD.read_text()`
  + `assert "..." in case_text` style, no hashing). `tests/nus/test_write_boundary.py`
  contains **no** git-diff assertion at all (verified: `grep` for
  `git diff|subprocess` in that file returns nothing) — the `git diff
  --exit-code` idiom the research cites lives only in **plan `<automated>`
  verify-command strings** (`.planning/phases/99-.../99-03-PLAN.md`,
  `99-04-PLAN.md`) and **prose in SUMMARY/VERIFICATION docs**, never as a
  committed pytest test. There is genuinely no prior committed pytest
  byte-unchanged test in this repo — the planner must design one from
  scratch (SHA-256 golden-hash, per RESEARCH.md Pitfall 5's precomputed
  baseline table, is the cleanest new mechanism; a `subprocess.run(["git",
  "diff", "--exit-code", ...])`-based pytest test is the alternative if the
  planner prefers mirroring the plan-verify-command idiom instead).
- **`src/lucy_ng/processing/peak_picker.py`'s 1D class is `AdaptivePeakPicker`**
  (static method `AdaptivePeakPicker.pick_peaks(spectrum, threshold=0.05,
  detect_negative=False, snr_floor=5.0, use_snr=True) -> PeakList1D`) — the
  phase brief's "PeakPicker" name is informal/approximate, confirmed exact
  name via `grep "^class"`.
- **The 1D-bridge fixture (COSY-shaped) does not exist yet** and there is no
  existing script that trims a homonuclear file — `tests/fixtures/jcamp/_generate_fixture.py`
  currently only builds the **HSQC** trimmed fixture + copies the two 1D
  references; it does **not** trim COSY/NOESY. It DOES already contain a
  `spotcheck_cosy_noesy()` step (reads one page from each real external
  COSY/NOESY file and confirms `_parse_data` decodes it) — this proves the
  real files are structurally readable, but produces no committed fixture.
  The planner must **extend** this script (not invent a new one) with a
  `build_trimmed_cosy()` mirroring `build_trimmed_hsqc()`'s exact
  page-window-slicing logic, then commit the resulting trimmed `.dx`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/lucy_ng/cli/jcamp.py` (NEW) | CLI command | request-response (batch: read→pick→QC→write) | `src/lucy_ng/cli/nus.py` (`pipeline` command, lines 405–667) | exact |
| `src/lucy_ng/processing/jcamp_1d_bridge.py` (NEW, exact name is planner discretion) | service/bridge | transform (direct in-memory call) | `src/lucy_ng/nus/bridge.py::bridge_peak_pick` (lines 284–368) for the direct-call idiom; `src/lucy_ng/cli/pick.py::pick_1d` (lines 81–159) for the exact output shape | exact (composite of two analogs) |
| `src/lucy_ng/readers/jcamp.py::_resolve_dim` (MODIFIED, lines 169–228) | reader/utility | transform | itself — the heteronuclear branch (`len(matches) == 1`, lines 227–228) is the analog for the new homonuclear positional-fallback branch | exact (same function, extend existing branch) |
| `src/lucy_ng/cli/main.py` (MODIFIED) | config/registration | — | itself — the existing `nus` registration (import line 14, `cli.add_command(nus)` line 67) | exact |
| `tests/test_cli_jcamp.py` (NEW) | test | integration (CLI) | `tests/nus/test_cli_pipeline.py` / `tests/nus/test_write_boundary.py` (staged/final + write-boundary assertions) + `tests/test_cli_nus.py` (`CliRunner` + `TestImportSafety` pattern) | role-match |
| `tests/processing/test_jcamp_1d_bridge.py` (NEW) | test | unit | `tests/nus/test_bridge.py` (synthetic-spectrum + direct-call pattern, lines 1–120) + `tests/test_cli_pick.py` (JSON-shape assertions for `pick_1d`) | role-match |
| `tests/readers/test_jcamp.py` (MODIFIED — extend, not new file) | test | unit | itself — `TestJcampReader2D`/`TestJcampReaderPpmCrossCheck` (lines 26–95) is the exact analog for a new `TestJcampReaderHomonuclear` class | exact |
| `tests/test_case_byte_unchanged.py` (NEW) | test | unit (golden-hash) | `tests/test_case_md_wv07.py` (repo-relative `Path(...).read_text()` convention) — but note this is a DIFFERENT mechanism (content-contract, not hash); no true byte-unchanged analog exists | no analog (build fresh) |
| `tests/fixtures/jcamp/_generate_fixture.py` (MODIFIED — extend with `build_trimmed_cosy()`) | fixture-gen script | file I/O (batch) | itself — `build_trimmed_hsqc()` (lines 107–144) | exact |

## Pattern Assignments

### `src/lucy_ng/cli/jcamp.py` (CLI command, request-response/batch)

**Analog:** `src/lucy_ng/cli/nus.py`

**Module docstring / import-safety pattern** (lines 1–29):
```python
"""Lucy NUS (Non-Uniform Sampling) reconstruction CLI commands.

This module is import-safe: it does NOT import ``lucy_ng.nus.params``,
``lucy_ng.nus.schedule``, ``lucy_ng.nus.backends``, or ``lucy_ng.nus.runner``
at the top level. All ``lucy_ng.nus.*`` imports are deferred into command
bodies so that the core ``lucy`` CLI stays importable without the optional
``[nus]`` extra (NUS-05).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from lucy_ng.nus.qc import QcConfig
```
`lucy jcamp` should follow this exact convention even though nmrglue/click
are already core deps — deferred imports of `lucy_ng.readers.jcamp`,
`lucy_ng.nus.bridge`, `lucy_ng.nus.qc`, and the new 1D bridge module should
all live inside the command body, not at module top level, per the phase's
own "mirror the import-safe `cli/nus.py` registration pattern" discretion note.

**`--format json` option block** (repeated verbatim on every subcommand,
e.g. lines 67–75):
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

**`_build_qc_config()` helper** (lines 37–64) — reuse directly, unmodified,
by importing it from `cli/nus.py` rather than duplicating it (it is a
private module-level function, not exported via `__init__`, so import as
`from lucy_ng.cli.nus import _build_qc_config` or re-implement an identical
thin wrapper if the planner prefers not to reach into another CLI module's
internals — planner discretion, but do not fork the threshold-override
semantics):
```python
def _build_qc_config(
    ridge_fail: float | None,
    coverage_floor: float | None,
    c13_tol: float | None,
    h1_tol: float | None,
) -> QcConfig:
    from lucy_ng.nus.qc import QcConfig

    defaults = QcConfig.default()
    return QcConfig(
        c13_tol=c13_tol if c13_tol is not None else defaults.c13_tol,
        h1_tol=h1_tol if h1_tol is not None else defaults.h1_tol,
        ridge_fraction_fail=(
            ridge_fail if ridge_fail is not None else defaults.ridge_fraction_fail
        ),
        hsqc_coverage_floor=(
            coverage_floor if coverage_floor is not None else defaults.hsqc_coverage_floor
        ),
        edited_sign_tol=defaults.edited_sign_tol,
        cosy_symmetry_floor=defaults.cosy_symmetry_floor,
        known_quaternary_shifts=defaults.known_quaternary_shifts,
    )
```

**Core staged/final two-call QC wiring** (`pipeline`, lines 542–667) — this
is THE pattern to copy for `lucy jcamp`'s own read→pick→QC→write chain,
adapted for a directory of independent files instead of one `expdir`:
```python
from lucy_ng.models.nus import QcVerdict
from lucy_ng.nus.bridge import bridge_peak_pick, build_spectrum2d, write_peak_json
from lucy_ng.nus.qc import run_qc_checks

# STAGED pass (verdict-less): peaks must exist before QC can grade them.
staged_payload = bridge_peak_pick(
    spectrum, experiment=experiment_type, qc_report=None, recon_meta=recon_meta
)
staged_dir = stage_dir / "staged"
write_peak_json(staged_dir, experiment_type, staged_payload)

# QC gate — the SAME code path `lucy nus qc` calls standalone.
report = run_qc_checks(staged_dir, config)

if report.verdict == QcVerdict.FAIL:
    final_payload = dict(staged_payload)
    final_payload["reconstruction"] = {
        "backend": recon_meta["backend"],
        "iterations": recon_meta["iterations"],
        "qc_verdict": report.verdict.value,
        "violated_checks": report.violated_checks(),
        "thresholds_used": dict(report.thresholds_used),
    }
    final_payload["caveat"] = (
        f"Reconstructed via {recon_meta['backend']}. QC verdict: FAIL. "
        f"Violated checks: {', '.join(report.violated_checks())}."
    )
    quarantine_dir = stage_dir / "qc_failed"
    out_path = write_peak_json(quarantine_dir, experiment_type, final_payload)
    (quarantine_dir / "qc_report.json").write_text(json.dumps(report.to_dict(), indent=2))
else:
    # CAUSAL RE-BUILD — reproduces identical cross-peaks, now with the real verdict.
    final_payload = bridge_peak_pick(
        spectrum, experiment=experiment_type, qc_report=report, recon_meta=recon_meta
    )
    out_path = write_peak_json(nmr_peaks_dir, experiment_type, final_payload)
```
**Critical difference from the NUS case (D-06/Pattern in RESEARCH.md
Pattern 2):** `lucy jcamp` processes a *directory* of independent `.dx`
files (1D + several 2D), not one `expdir`/one experiment. The staged
directory must accumulate ALL staged files (every 1D reference AND every
supported 2D correlation) before `run_qc_checks()` is invoked **once** —
never once per file — because `QcReferenceData.resolve()` /
`_load_1d_shifts()` glob the *whole* staged directory for `13c`/`1h`
keyword matches.

**D-06 non-fatal skip pattern** (new — no existing analog does exactly this
per-file catch/skip inside a directory loop; nearest structural analog is
`nus/qc.py::_load_peaks()`'s per-file try/except at lines 223–254, which
also "collect errors, never crash the whole run, never silently treat as
clean"):
```python
# nus/qc.py::_load_peaks (lines 241-253) — the per-file try/except idiom to mirror:
for path in matches:
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name}: {exc}")
        continue
    cross_peaks = data.get("cross_peaks")
    if cross_peaks is None:
        errors.append(f"{path.name}: missing 'cross_peaks' key")
        continue
    merged.extend(cross_peaks)
```
Apply the same shape to `lucy jcamp`'s directory loop: `bridge_peak_pick`
raises `ValueError` for any `experiment not in {HSQC, HMBC, COSY}` (`nus/bridge.py`
lines 330–334) — catch that specific `ValueError`, log a visible warning
naming the file and reason, and `continue` to the next file rather than
aborting the whole run (D-06).

### `src/lucy_ng/processing/jcamp_1d_bridge.py` (NEW — thin 1D bridge; service/transform)

**Analog 1 (direct-call idiom to mirror):** `src/lucy_ng/nus/bridge.py::bridge_peak_pick`
(lines 284–368, full function read above) — build/receive the in-memory
model, call the existing picker directly, no subprocess, no new picker.

**Analog 2 (EXACT output shape to reproduce):** `src/lucy_ng/cli/pick.py::pick_1d`
(lines 81–159). The 1D bridge MUST emit this exact top-level/per-peak key
structure (verified against `nus/qc.py::_load_1d_shifts`, which reads
`data.get("peaks", [])` and each peak's `"ppm"` key — NOT the 2D
`cross_peaks`/`c13_ppm`/`h1_ppm` shape):
```python
# Source: src/lucy_ng/cli/pick.py lines 91-148 (pick_1d command body)
spectrum = BrukerReader.read_1d(path)  # <-- swap for JcampReader.read_1d(path)

effective_threshold = threshold if threshold is not None else 0.05
max_abs = float(np.max(np.abs(spectrum.data)))
has_significant_negative = bool(np.min(spectrum.data) < -effective_threshold * max_abs)

use_snr = threshold is None
peaks = AdaptivePeakPicker.pick_peaks(
    spectrum,
    detect_negative=has_significant_negative,
    use_snr=use_snr,
)

if not use_snr:
    snr_floor_used: float | None = None
elif snr_floor is not None:
    snr_floor_used = snr_floor
else:
    snr_floor_used = 5.0

data = {
    "count": len(peaks.peaks),
    "noise_sigma": peaks.noise_sigma,
    "negative_detected": has_significant_negative,
    "snr_floor_used": snr_floor_used,
    "peaks": [
        {"ppm": p.position, "intensity": p.intensity, "snr": p.snr}
        for p in peaks.peaks
    ],
}
```
`AdaptivePeakPicker` lives in `src/lucy_ng/processing/peak_picker.py`
(class at line 129; static `pick_peaks(spectrum, threshold=0.05,
detect_negative=False, snr_floor=5.0, use_snr=True) -> PeakList1D` at
line 158). Import as `from lucy_ng.processing import AdaptivePeakPicker`
(already re-exported, per `cli/pick.py` line 9-12's own import).

**Where it should live:** `processing/jcamp_1d_bridge.py` is the
RESEARCH.md recommendation, parallel to `processing/edited_sign.py`'s
precedent of a small, testable, dependency-light "importable twin" module
under `processing/` with zero `nus/` coupling (this function needs no
`nus.*` imports at all, unlike the 2D path) — but this is explicitly
Claude's Discretion per CONTEXT.md; `cli/jcamp.py`-adjacent is an equally
valid alternative location.

**Serialization target filenames** (Pitfall 3 in RESEARCH.md, keyword-glob
discoverability): write to `13C.json` / `1H.json` (or any name whose
lowercased form contains `"13c"`/`"1h"` as a substring — `_glob_by_keyword`,
`nus/qc.py` lines 146–155, is case-insensitive substring match). Reuse
`nus/bridge.py::write_peak_json(out_dir, experiment, payload)`'s
`f"{experiment}.json"` convention (line 371–383) rather than inventing a
new writer — it is generic enough to serve both 1D and 2D payloads (it
just does `json.dumps` + `mkdir(parents=True, exist_ok=True)`).

### `src/lucy_ng/readers/jcamp.py::_resolve_dim` (MODIFIED — homonuclear fix)

**Analog:** the function's own existing heteronuclear branch (lines
211–228, same function — this is a same-function extension, not a
different-file analog):
```python
# Current (lines 200-228) — the branch to extend is len(matches) > 1:
nuc1_raw = inner["$NUC1"]
sf_raw = inner["$SF"]
offset_raw = inner["$OFFSET"]
...
nuclei = [_clean_nucleus_label(str(n)) for n in nuc1_raw]
matches = [i for i, n in enumerate(nuclei) if n == target_nucleus]

if len(matches) == 0:
    raise ValueError(...)
if len(matches) > 1:
    raise ValueError(
        f"Ambiguous nucleus '{target_nucleus}' appears {len(matches)} times in "
        f"$NUC1={nuclei} -- homonuclear axis resolution (e.g. COSY/NOESY) is "
        "out of scope for this phase (deferred to Phase 103, which resolves by "
        "positional SYMBOL order); refusing to silently first-match"
    )

index = matches[0]
return float(offset_raw[index]), float(sf_raw[index])
```
The fix (per RESEARCH.md Pitfall 1 + Assumption A1, verified against the
real external `C20H32O2_COSY.dx` with two distinct `$OFFSET` values
7.050608/7.051546 at the same `$SF`=499.92) replaces the `len(matches) > 1`
`raise` with a **positional** fallback using the SYMBOL F1/F2 declared
order already established for `.NUCLEUS` in `read_2d` (lines 448–458,
"`.NUCLEUS`'s comma-split order is guaranteed to match SYMBOL's declared
F1,F2 dimension order"): when `target_nucleus` appears exactly twice and
both matched entries share the same nucleus, resolve index 0 to whichever
of F1/F2 is being asked for by using `dims.index("F1")`/`dims.index("F2")`
position parity — the same "procs-then-proc2s" convention the heteronuclear
case already trusts implicitly. Note the call sites (lines 472, 490) each
pass a `target_nucleus` string (`f2_nucleus`, `f1_nucleus`) — for a
homonuclear file these two calls pass the SAME string twice, so the
degeneracy-resolution logic needs to know *which* dimension (F1 vs F2) the
caller wants, not just the nucleus name; the cleanest fix threads a
positional hint (e.g. an optional `dim_index: int | None` parameter set by
the two call sites at lines 472/490 to `f2_index`/`dims.index("F1")`
respectively) into `_resolve_dim`, used only when `len(matches) > 1`.

**Verification idiom to reuse:** the same JC-02 cross-check pattern from
`tests/readers/test_jcamp.py::TestJcampReaderPpmCrossCheck` (lines 65–95) —
project the resolved 2D axis onto known real 1D reference peaks and assert
tolerance, not just "does not raise" (RESEARCH.md Assumption A1's own
stated risk: a wrong-but-plausible positional resolution could silently
swap F1/F2 for COSY).

### `src/lucy_ng/cli/main.py` (MODIFIED — command registration)

**Analog:** itself, the existing `nus` registration pattern (verified,
lines 1–67 read in full):
```python
# import block (line 14):
from lucy_ng.cli.nus import nus
...
# registration (line 67, last in the list):
cli.add_command(nus)
```
Add `from lucy_ng.cli.jcamp import jcamp` to the import block and
`cli.add_command(jcamp)` to the registration block; also add a one-line
entry to the `cli()` group docstring's `\b`-fenced command list (lines
31–48) mirroring the existing `nus         NUS (Non-Uniform Sampling) 2D
reconstruction` line format, e.g. `jcamp       JCAMP-DX ingestion (read →
pick → QC → write)`.

### `tests/test_cli_jcamp.py` (NEW — CLI integration tests)

**Analogs:** `tests/nus/test_write_boundary.py` (full file read above,
124 lines) for the PASS/PARTIAL/FAIL write-boundary assertion shape
(`assert not (expdir / "analysis" / "nmr_peaks").exists()` on FAIL,
`assert payload["reconstruction"]["qc_verdict"] == ...` on PASS/PARTIAL)
and `tests/test_cli_nus.py` for the `CliRunner` + `TestImportSafety`
conventions:
```python
# Source: tests/test_cli_nus.py lines 124-136 (TestImportSafety pattern)
class TestImportSafety:
    def test_no_top_level_nus_submodule_import(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import lucy_ng.cli.nus"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, ...
```
```python
# Source: tests/nus/test_write_boundary.py lines 29-64 (FAIL-verdict shape)
def test_fail_verdict_quarantines_and_exits_nonzero(tmp_path, mock_pipeline_stages) -> None:
    ...
    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(expdir)])
    assert result.exit_code != 0, result.output
    assert not (expdir / "analysis" / "nmr_peaks").exists()
    quarantine_dir = expdir / "analysis" / "nus_recon" / expdir.name / "qc_failed"
    assert quarantine_dir.exists()
```
Adapt: `lucy jcamp <dir>` takes a directory of independent `.dx` files
instead of one Bruker `expdir`, so mocking needs to substitute
`JcampReader.read`/`read_1d`/`read_2d` (or use the real trimmed HSQC + 1H/13C
fixtures directly, which is preferable per the Phase-100 meta-lesson: prefer
real fixture-backed tests over mocks wherever a real fixture already exists).

### `tests/processing/test_jcamp_1d_bridge.py` (NEW — 1D bridge schema tests)

**Analog:** `tests/nus/test_bridge.py` (lines 1–120 read in full) for the
synthetic-`Spectrum`-construction + direct-call pattern:
```python
# Source: tests/nus/test_bridge.py lines 68-102 (_build_synthetic_spectrum pattern)
def _build_synthetic_spectrum(...) -> Spectrum2D:
    rng = np.random.default_rng(7)
    n1, n2 = 32, 48
    data = rng.normal(0.0, 50.0, size=(n1, n2))
    f1_scale = np.linspace(200.0, 0.0, n1, dtype=np.float64)
    f2_scale = np.linspace(10.0, 0.0, n2, dtype=np.float64)
    for f1_ppm, f2_ppm in positive_peaks:
        data[_idx(f1_scale, f1_ppm), _idx(f2_scale, f2_ppm)] = 1.0e6
    return Spectrum2D(data=data, f1_ppm_scale=f1_scale, f2_ppm_scale=f2_scale, ...)
```
Adapt to a synthetic `Spectrum1D` (a 1D analog of this: linspace ppm_scale
+ gaussian noise floor + explicit single-point maxima placed at known ppm).
Per RESEARCH.md Pitfall 2, the two required assertions are: (1) the raw
dict has a top-level `"peaks"` key whose elements have a `"ppm"` key
(matching `pick_1d`'s exact shape — NOT `cross_peaks`/`c13_ppm`); (2) a
`run_qc_checks()`/`QcReferenceData.resolve()` run against a directory
containing ONLY the 1D bridge's output asserts `classification_source
!= "insufficient_reference_data"` and `trusted_c13` is non-empty — proving
real discovery, not just shape-matching by inspection.

### `tests/readers/test_jcamp.py` (MODIFIED — extend, homonuclear test class)

**Analog:** itself — `TestJcampReader2D`/`TestJcampReaderPpmCrossCheck`
(lines 26–95, full class definitions read above) is the exact structural
template for a new `TestJcampReaderHomonuclear` class:
```python
class TestJcampReader2D:
    def test_read_2d_shape(self) -> None:
        from lucy_ng.readers.jcamp import JcampReader
        spectrum = JcampReader.read_2d(HSQC_TRIMMED)
        assert spectrum.data.shape == (16, 2048)
```
The new class needs a `COSY_TRIMMED` fixture path (see fixture-gen section
below) and should assert (a) `read_2d()` does NOT raise for the homonuclear
file, (b) `spectrum.f1_nucleus == spectrum.f2_nucleus == "1H"`, and (c) — per
RESEARCH.md's own warning that "doesn't raise" alone is insufficient — a
JC-02-style cross-check against the real 1H reference peaks, mirroring
`TestJcampReaderPpmCrossCheck.test_read_2d_ppm_axes_match_1d_reference`
(lines 68–95) exactly, substituting the COSY fixture's F1 AND F2 axes
(both 1H) against `REF_1H`.

### `tests/test_case_byte_unchanged.py` (NEW — no true analog, build fresh)

**Nearest structural analog (repo-relative path convention only):**
`tests/test_case_md_wv07.py` lines 1–33:
```python
from pathlib import Path

CASE_MD = Path(".claude/commands/lucy-ng/case.md")
PROGRESS_FORMAT_MD = Path(".claude/commands/lucy-ng/references/progress-format.md")
```
This file's testing STRATEGY (substring-contract) is NOT the pattern to
copy for a byte-unchanged guard — only its repo-relative path convention is
reusable. Build a genuinely new SHA-256 hash-comparison test using
RESEARCH.md Pitfall 5's precomputed baseline table (verified current,
commit `22f2b52` matches current HEAD per git status):

| File | SHA-256 |
|------|---------|
| `.claude/commands/lucy-ng/case.md` | `8299791ead74294fa31424bae990de62d7bf73260d5dbdbe1e776539e7148d8b` |
| `.claude/agents/lucy-nmr-chemist.md` | `4dd7766e3746074062e5f05cefc4462ce85ee444c264c426298fb830c2760839` |
| `.claude/agents/lucy-lsd-engineer.md` | `0e9ffcbe4856f9980ed19b5384fb9c7050b20d6427901d0e1ae3ffc1a8507f3b` |
| `.claude/agents/lucy-solution-analyst.md` | `dbe9da127ed576aca22fd9d34bf6b599b2e7765b29dffb90fcae83e29dc290f2` |
| `.claude/agents/lucy-devils-advocate.md` | `ee80ace79e5785b810e6d9da295f1d31e01ecfa6758f71a3b77d7768c5cbb34f` |
| `.claude/agents/lucy-diagnostic.md` | `74bd725c4067be5f076c78424632b7f9d6b4111322d9947fbcbe804a8cfcdbb2` |

**Do NOT include** `.claude/agents/supervisor.md` — it is not part of "the
5-agent team" per CLAUDE.md's own roster (`lucy-nmr-chemist`,
`lucy-lsd-engineer`, `lucy-solution-analyst`, `lucy-devils-advocate` +
`lucy-diagnostic` on escalation) nor CONTEXT.md's list. Re-verify these
hashes at implementation time with `shasum -a 256 <path>` (cheap, and the
whole point of the test is to catch drift — a stale baseline recorded here
must not silently become the new "acceptable" state without an explicit
decision).

Alternative mechanism (if the planner prefers mirroring the existing
plan-verify-command idiom instead of a hash table): a pytest test that
shells out `subprocess.run(["git", "diff", "--exit-code", "<ref>", "--",
"<path>"])` per the prose already used in `.planning/phases/99-.../99-04-PLAN.md`
line 165 and `99-VERIFICATION.md` line 84 — but this requires pinning a
git ref and has never actually been wrapped in a committed pytest test
anywhere in this repo; the hash-table approach avoids the git-subprocess/
shallow-clone concern RESEARCH.md itself flags as the reason to prefer it.

### `tests/fixtures/jcamp/_generate_fixture.py` (MODIFIED — add `build_trimmed_cosy()`)

**Analog:** itself — `build_trimmed_hsqc()` (lines 107–144, full function
read above):
```python
PAGE_WINDOW = slice(1735, 1751)  # 16 pages, HSQC-specific

def build_trimmed_hsqc() -> None:
    if not HSQC_SOURCE.exists():
        raise FileNotFoundError(...)
    lines = HSQC_SOURCE.read_text(encoding="latin-1").splitlines(keepends=True)
    ntuples_idx, first_page_idx, page_indices = _find_ntuples_block(lines)
    header = _trim_header(lines[:ntuples_idx])
    ntuples_header = [
        _update_var_dim(line, PAGE_WINDOW.stop - PAGE_WINDOW.start)
        if line.startswith("##VAR_DIM=") else line
        for line in lines[ntuples_idx:first_page_idx]
    ]
    end_idx = next(i for i, line in enumerate(lines) if line.startswith("##END NTUPLES"))
    selected_indices = page_indices[PAGE_WINDOW]
    page_blocks: list[str] = []
    for start in selected_indices:
        pos_in_all = page_indices.index(start)
        stop = page_indices[pos_in_all + 1] if pos_in_all + 1 < len(page_indices) else end_idx
        page_blocks.extend(lines[start:stop])
    footer = ["##END NTUPLES=nD NMR SPECTRUM\n", "##END=\n"]
    out_lines = header + ntuples_header + page_blocks + footer
    HSQC_TRIMMED.write_text("".join(out_lines), encoding="latin-1")
```
Add a parallel `build_trimmed_cosy()` with a NEW, COSY-appropriate
`COSY_PAGE_WINDOW` (must be independently chosen/verified against the real
external `C20H32O2_COSY.dx` for a page range containing real, non-noise
diagonal + cross peaks — do not reuse the HSQC window verbatim, the file
is different). `KEEP_HEADER_PREFIXES` (lines 59–77) should be reviewed:
the COSY file's homonuclear `$NUC1`/`.NUCLEUS` values need the SAME header
keys the HSQC trim keeps (`##$NUC1=`, `##$OFFSET=`, `##$SF=`, `##.NUCLEUS=`
— note `.NUCLEUS` is read via `##.NUCLEUS=` at `read_2d` line 448, confirm
this key is also in `KEEP_HEADER_PREFIXES` since HSQC's own header-trim
already needs it too — verify before assuming it is already covered).
Update `main()` (lines 183–187) to call the new function alongside the
existing three.

## Shared Patterns

### Import-safe CLI registration (deferred `lucy_ng.nus.*`/`lucy_ng.readers.jcamp` imports)
**Source:** `src/lucy_ng/cli/nus.py` lines 1–29 (module docstring +
`TYPE_CHECKING` guard) and every command body (e.g. `check`, line 86:
`from lucy_ng.nus.backends import get_backend` inside the function, not
at module top).
**Apply to:** `cli/jcamp.py` (the only new CLI module this phase adds).

### `--format json` option block
**Source:** `src/lucy_ng/cli/nus.py`, repeated verbatim on every
subcommand (e.g. lines 67–75, 356–363).
**Apply to:** the single `lucy jcamp` command (D-01: one command, not a
group with subcommands).

### Staged/final two-call QC wiring (causal-ordering fix)
**Source:** `src/lucy_ng/cli/nus.py::pipeline`, lines 584–637 (full excerpt
in Pattern Assignments above).
**Apply to:** `cli/jcamp.py`'s own read→pick→QC→write chain — this is the
central pattern this whole phase reuses; do not re-derive it.

### Per-file fail-loud-but-non-fatal error collection
**Source:** `src/lucy_ng/nus/qc.py::_load_peaks`, lines 223–254.
**Apply to:** `cli/jcamp.py`'s directory-discovery loop (D-06: malformed/
unsupported `.dx` files must not abort the whole run, but also must not be
silently treated as "0 peaks, clean").

### 1D peak-list JSON schema (`peaks[].ppm`, not `cross_peaks`)
**Source:** `src/lucy_ng/cli/pick.py::pick_1d`, lines 134–149 (exact dict
literal above in Pattern Assignments).
**Apply to:** the new 1D bridge — this is the single most safety-critical
shared contract in the phase (RESEARCH.md Pitfall 2: a schema mismatch
here is a SILENT failure, not a loud one, because `_load_1d_shifts()`
defaults to `[]` rather than raising on a missing `"peaks"` key).

### Byte-unchanged / write-boundary reused seams (call, do not edit)
**Source:** `src/lucy_ng/nus/bridge.py::bridge_peak_pick`/`write_peak_json`
(lines 284–383) and `src/lucy_ng/nus/qc.py::run_qc_checks`
(lines 618–692) — both consumed as-is, zero modification.
**Apply to:** every 2D file in `cli/jcamp.py`'s directory loop and the
final QC pass.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_case_byte_unchanged.py` | test | unit (golden-hash) | No prior committed pytest test in this repo performs a byte/hash-equality check on any file (confirmed by grepping the whole `tests/` tree for `sha256`/`hashlib`/`git diff`); must be designed fresh using RESEARCH.md Pitfall 5's precomputed baseline hash table (reproduced above) |

## Metadata

**Analog search scope:** `src/lucy_ng/cli/`, `src/lucy_ng/nus/`,
`src/lucy_ng/readers/`, `src/lucy_ng/processing/`, `tests/`,
`tests/nus/`, `tests/readers/`, `tests/fixtures/jcamp/`.
**Files scanned (read in full or targeted-section):** `cli/nus.py` (667
lines, full), `nus/bridge.py` (383 lines, full), `nus/qc.py` (692 lines,
full), `cli/pick.py` (351 lines, full), `cli/main.py` (67 lines, full),
`readers/jcamp.py` (556 lines, full), `processing/edited_sign.py` (59
lines, full), `processing/peak_picker.py` (targeted: class/method
signatures + `pick_peaks` docstring), `tests/fixtures/jcamp/_generate_fixture.py`
(192 lines, full), `tests/test_case_md_wv07.py` (187 lines, full),
`tests/nus/test_write_boundary.py` (154 lines, full), `tests/nus/test_bridge.py`
(targeted: header + first 120 lines), `tests/readers/test_jcamp.py` (128
lines, full), `tests/test_cli_nus.py` (targeted: header + `TestImportSafety`).
**Pattern extraction date:** 2026-07-25
