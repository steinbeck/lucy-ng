# Phase 103: End-to-End Validation (C20H32O2-jcamp) - Pattern Map

**Mapped:** 2026-07-26
**Files analyzed:** 6 (2 source, 2 test, 1 new fixture dir, 1 evidence doc)
**Analogs found:** 6 / 6

This is a small-code, proof-heavy phase (D-09: only `cli/jcamp.py` and
`readers/jcamp.py` may change; `nus/qc.py`, `PeakPicker2D`, the 1D picker,
`case.md` and the 5 agent files are byte-frozen). Every file below already
has a near-identical analog **in the same file or its immediate sibling** —
this phase extends existing, very recently authored (Phase 101/102) code
rather than reaching for a distant pattern.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/lucy_ng/cli/jcamp.py` (add `--threshold`/`--snr-floor` key=value options) | CLI command (Click) | request-response (batch file transform) | itself, `--snr-floor` option + staging/QC/rebuild call sites (same file, lines 75-81, 265-347) | exact (self-extension) |
| `src/lucy_ng/cli/jcamp.py` (key=value multi-value parser) | utility (option parsing) | transform | `src/lucy_ng/cli/visualize.py` `--correlations`/`-c` `multiple=True` option (line 45-50) | role-match (idiom precedent, no existing `key=value` parser to copy verbatim) |
| `src/lucy_ng/readers/jcamp.py` (widen `_PPM_PLAUSIBILITY_BOUNDS["13C"]`) | model/config constant + validation | transform (fail-loud guard) | itself, `_PPM_PLAUSIBILITY_BOUNDS` dict + `_assert_plausible_ppm_axis` (same file, lines 45-51, 140-166) | exact (self-extension, one-constant fix) |
| `tests/test_cli_jcamp.py` (extend `TestJcampCliSurface` + new knob-option tests) | test (CLI-surface) | request-response | itself, `TestJcampCliSurface.test_help_exits_zero_and_documents_options` (lines 87-94) + `TestJcampEndToEnd`'s `CliRunner(mix_stderr=False)` convention (lines 212-226) | exact (self-extension) |
| `tests/readers/test_jcamp.py` (extend plausibility-bound test) | test (unit) | transform | itself, `test_read_2d_ppm_axis_assertion` (lines 39-52) | exact (self-extension) |
| `tests/fixtures/jcamp/known_good_peaks/` + new regression test (D-11.4) | test fixture + regression test | CRUD (read-only fixture) / batch | `tests/nus/test_qc_regression.py` + `tests/fixtures/nus/known_bad_peaks/` / `clean_peaks_synthetic/` + `tests/nus/conftest.py` fixtures (`known_bad_peaks_dir`, `clean_peaks_dir`) | exact (structural analog, different directory) |
| `.planning/phases/103-.../VALIDATION.md` (new) | documentation / evidence ledger | batch (manual proof-level ledger) | `.planning/phases/102-.../102-VALIDATION.md` (layout) + `.planning/phases/100-.../100-03-PLAN.md` (`autonomous: false` handoff-gate shape) | exact (both are named, current-milestone analogs) |

## Pattern Assignments

### `src/lucy_ng/cli/jcamp.py` — per-experiment `key=value` knob wiring (D-01/D-04)

**Analog:** the file's own existing `--snr-floor` option and the two `bridge_peak_pick`/`bridge_peak_pick_1d` call sites that must receive the new per-experiment values, plus `cli/visualize.py`'s `multiple=True` precedent for the parsing idiom.

**Current option block to extend** (`src/lucy_ng/cli/jcamp.py` lines 63-94):
```python
@click.command("jcamp")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--out", "out_dir", type=click.Path(), default=None,
    help=("Output directory for the consumable peak lists "
          "(default: <input-dir>/analysis/nmr_peaks)."),
)
@click.option(
    "--snr-floor", type=float, default=5.0, show_default=True,
    help="SNR floor multiplier k forwarded to both the 1D and 2D pickers.",
)
@click.option(
    "--format", "output_format", type=click.Choice(["text", "json"]),
    default="text", show_default=True, help="Output format.",
)
def jcamp(paths, out_dir, snr_floor, output_format) -> None:
```
D-04 requires `--snr-floor`'s *type* to change from `float` (single value) to
`multiple=True` (a `tuple[str, ...]` of raw strings, each either bare or
`KEY=value`), while preserving `--snr-floor 5.0`'s existing plain-float
behavior for every current caller/test. Add a parallel `--threshold` option
the same way (currently entirely absent from the CLI — D-01).

**`multiple=True` in-repo precedent** (`src/lucy_ng/cli/visualize.py` lines 45-50):
```python
@click.option(
    "--correlations", "-c",
    multiple=True,
    help="Correlations in format 'type:source:target' (e.g., 'HMBC:0:5'). "
    "Can be specified multiple times. Indices are 0-based.",
)
```
This confirms `multiple=True` is idiomatic in this CLI; combining it with
`key=value` parsing is genuinely new syntax (no verbatim source to copy —
RESEARCH.md's own Code Examples "Pattern 3" gives a verified, non-lifted
idiom worth reusing as a starting point):
```python
def _parse_keyed(raw: tuple[str, ...], cast) -> tuple[dict[str, float], float | None]:
    by_key: dict[str, float] = {}
    bare: float | None = None
    for item in raw:
        if "=" in item:
            key, _, value = item.partition("=")
            by_key[key.strip().upper()] = cast(value)
        else:
            bare = cast(item)   # last bare value wins; keyed values always win over it
    return by_key, bare
```
Normalize keys against `SUPPORTED_2D = ("HSQC", "HMBC", "COSY")` /
`SUPPORTED_1D = ("1H", "13C")` (same file, lines 33-34) via `.upper()`, and
fail loud (raise, do not silently ignore) on an unrecognized key — this
mirrors the file's existing "fail loud, never silently first-match" idiom
used throughout `readers/jcamp.py::_resolve_dim`.

**Load-bearing call sites the new per-experiment values MUST reach — both, not just one** (same file):

Staging call, inside the per-file loop (lines 261-275):
```python
staged_payload = bridge_peak_pick(
    spectrum,
    experiment=experiment_type,
    qc_report=None,
    recon_meta={"backend": RECON_BACKEND, "iterations": None},
    snr_floor=snr_floor,
)
```
1D staging call (line 234): `payload = bridge_peak_pick_1d(spectrum, snr_floor=snr_floor)`

FAIL-branch rebuild call (lines 306-312) and PASS/PARTIAL rebuild call
(lines 341-347) — **both** must be updated with the identical per-experiment
`threshold=`/`snr_floor=` values used at staging time (deterministic
causal-rebuild invariant already documented in the file's own comments:
"CAUSAL RE-BUILD -- reproduces identical cross-peaks, now with the real
verdict stamped in").

**The single-QC-call invariant that must survive unchanged** (lines 290-294):
```python
# STEP 5 -- QC ONCE. This single call MUST come after every 1D and 2D
# file has been staged, because QcReferenceData.resolve()/
# _load_1d_shifts() glob the whole staged directory -- never invoke the
# QC gate once per file (102-RESEARCH.md Pattern 2 anti-pattern).
report = run_qc_checks(staged_dir)
```
D-04 explicitly requires this call to remain exactly once over the fully
staged set regardless of how many distinct per-experiment knob values are
supplied — the new option only changes what is *passed into* the staging
loop, never the QC call's cardinality.

**Docstring update needed:** the command's docstring at lines 120-124
currently states "This command has no `--ridge-fail`/... threshold-override
flags of its own" — that sentence becomes stale once `--threshold` exists
and must be corrected as part of the same change (a documentation-only but
load-bearing edit, since the docstring is asserted against in
`test_help_exits_zero_and_documents_options`-style tests).

---

### `src/lucy_ng/readers/jcamp.py` — widen `_PPM_PLAUSIBILITY_BOUNDS["13C"]` (D-09)

**Analog:** the module's own constant + guard function (no external analog needed — this is a one-line, self-contained fix).

**Current state** (lines 41-51):
```python
# ppm-axis plausibility bounds per nucleus (101-RESEARCH.md "JC-02 concrete
# assertion bounds"). Deliberately generous -- this is the coarse, fail-loud
# safety net (D-04); the finer JC-02 cross-check against 1D reference peaks
# lives in the test layer (D-03).
_PPM_PLAUSIBILITY_BOUNDS: dict[str, tuple[float, float]] = {
    "1H": (-3.0, 15.0),
    "13C": (-15.0, 230.0),
    "15N": (-50.0, 900.0),
    "31P": (-200.0, 250.0),
}
_PPM_PLAUSIBILITY_FALLBACK: tuple[float, float] = (-1e6, 1e6)
```
RESEARCH.md's verified fix (Pitfall 1): widen the `"13C"` upper bound from
`230.0` to somewhere in `240.0`–`250.0` (verified this session: `250.0` lets
the real HMBC file's `[-4.57, 234.81]` ppm axis pass and produces a
physically sensible axis). The guard function this bound feeds
(`_assert_plausible_ppm_axis`, lines 140-166) does not need to change — only
the dict value. Every place the docstring references `230.0` (the module
docstring at line ~47 area and any test literal) must be updated in lock-step
so the documented bound and the enforced bound never drift apart — this is
exactly the kind of thing `tests/readers/test_jcamp.py::test_read_2d_ppm_axis_assertion`
(below) exists to pin.

**D-09 logging obligation:** per CONTEXT.md D-09, this fix must be logged in
`VALIDATION.md` as an explicit, bounded deviation (genuine reader defect
blocking JVAL-01/JVAL-02), not silently folded into "ran the shipped chain".

---

### `tests/readers/test_jcamp.py` — extend the plausibility-bound test (D-09 coverage)

**Analog:** the file's own existing test, extend in place.

**Current test to extend** (lines 39-52):
```python
def test_read_2d_ppm_axis_assertion(self) -> None:
    """Reader's fail-loud ppm-axis assertion rejects implausible/non-reversed axes (D-04)."""
    from lucy_ng.readers.jcamp import _assert_plausible_ppm_axis

    # Plausible, correctly-reversed 13C axis: no error.
    _assert_plausible_ppm_axis(np.array([175.0, 100.0, 0.0]), "13C")

    # Non-reversed (ascending) axis must raise.
    with pytest.raises(ValueError):
        _assert_plausible_ppm_axis(np.array([0.0, 100.0, 175.0]), "13C")

    # Implausible out-of-range axis must raise.
    with pytest.raises(ValueError):
        _assert_plausible_ppm_axis(np.array([5000.0, 0.0]), "13C")
```
Per RESEARCH.md's Wave-0 gap and Open Question #3, add: (a) an axis at
~234.81 ppm (the real HMBC value) now passes at the widened bound, and (b) a
genuinely-wrong axis (e.g. computed from `SFO` instead of `SF`, which
RESEARCH.md documents as producing an error far larger than the ~5-20 ppm
widening margin) still raises — proving the widened bound is not a "raise
the ceiling until it stops complaining" non-fix. Follow the file's own
`from lucy_ng.readers.jcamp import ...` inside-test-body import convention
(module header comment: "Imports of `lucy_ng.readers.jcamp` ... go INSIDE
test function bodies").

---

### `tests/test_cli_jcamp.py` — extend `TestJcampCliSurface` with the new option tests

**Analog:** the file's own existing surface-test class and its documented `CliRunner(mix_stderr=False)` hazard.

**Existing help-text assertion to extend** (lines 87-94):
```python
def test_help_exits_zero_and_documents_options(self) -> None:
    runner = CliRunner()
    result = runner.invoke(jcamp, ["--help"])
    assert result.exit_code == 0, result.output
    assert "--out" in result.output
    assert "--snr-floor" in result.output
    assert "--format" in result.output
    assert "lucy nus qc" in result.output
```
Add `assert "--threshold" in result.output` here, and new tests exercising:
bare `--snr-floor 5.0` still works (backwards compatibility, D-04); a keyed
form `--threshold hsqc=1e4 --threshold hmbc=3e4` routes to the right
experiment; an unrecognized key (e.g. `--threshold hqsc=1` — the typo guard
RESEARCH.md's Pattern 3 calls out) exits non-zero rather than silently
applying nothing.

**The `CliRunner(mix_stderr=False)` hazard to carry forward** (module
docstring lines 1-24 and class docstring lines 212-226):
```python
class TestJcampEndToEnd:
    """... `CliRunner(mix_stderr=False)` is used throughout (rather than the
    default `mix_stderr=True`) so `json.loads(result.output)` is robust to
    nmrglue's `UserWarning: JCAMP-DX key without value: $RELAX` ...
    """
```
Any new test that invokes `jcamp` with `--format json` and parses
`result.output` as JSON MUST use `CliRunner(mix_stderr=False)`, exactly as
every existing `TestJcampEndToEnd`/`TestJcampQcDiscrimination` test does
(e.g. lines 234, 262, 276, 295, 309, 327, 349, 364, 377, 406, 572, 602,
636, 669) — this is a proven, file-wide convention, not per-test discretion.

**Fixture-copy discipline to reuse unchanged** (lines 55-68):
```python
def _copy_fixtures(tmp_path: Path, names: tuple[str, ...] = ALL_FIXTURE_NAMES) -> Path:
    """Copy the named committed `.dx` fixtures into `tmp_path`.
    ALWAYS copy, never invoke the CLI against the tracked fixture directory
    directly -- the command creates `analysis/nmr_peaks/` and
    `analysis/jcamp_ingest/` side effects that must never pollute the
    committed `tests/fixtures/jcamp/` tree ...
    """
```
Any new knob-option test that runs the CLI against the six committed `.dx`
fixtures must go through this same `_copy_fixtures(tmp_path)` helper, never
invoke against `FIXTURES` directly.

---

### `tests/fixtures/jcamp/known_good_peaks/` + regression test (D-11.4 positive fixture)

**Analog:** `tests/nus/test_qc_regression.py` + its two paired fixture directories + `tests/nus/conftest.py`'s fixture-resolution pattern.

**Structure to mirror** (`tests/nus/test_qc_regression.py`, full file, 42 lines):
```python
"""QC-02: the discrimination regression floor. ..."""
from __future__ import annotations

def test_known_bad_dir_fails(known_bad_peaks_dir) -> None:
    from lucy_ng.models.nus import QcVerdict
    from lucy_ng.nus.qc import run_qc_checks
    report = run_qc_checks(known_bad_peaks_dir)
    assert report.verdict == QcVerdict.FAIL

def test_synthetic_clean_dir_passes(clean_peaks_dir) -> None:
    from lucy_ng.models.nus import QcVerdict
    from lucy_ng.nus.qc import run_qc_checks
    report = run_qc_checks(clean_peaks_dir)
    assert report.verdict == QcVerdict.PASS
```
The new test mirrors this exact two-function shape but with a THIRD
directory (the new real-data JCAMP fixture), e.g.
`test_jcamp_known_good_dir_passes_or_soft_partial(jcamp_known_good_peaks_dir)`
asserting `report.verdict in (QcVerdict.PASS, QcVerdict.PARTIAL)` (soft-only,
per D-06/D-07) rather than a strict `PASS` — because D-07 explicitly allows
a soft-PARTIAL + chemist-confirmed outcome as a valid positive result, unlike
the strict binary PASS/FAIL of the existing known-bad/clean-synthetic pair.

**Fixture-directory resolution convention to mirror** (`tests/nus/conftest.py` lines 27-56):
```python
_NUS_FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "nus"
_KNOWN_BAD_PEAKS_DIR = _NUS_FIXTURES_ROOT / "known_bad_peaks"
_CLEAN_PEAKS_DIR = _NUS_FIXTURES_ROOT / "clean_peaks_synthetic"

@pytest.fixture
def known_bad_peaks_dir() -> Path:
    """Resolve `tests/fixtures/nus/known_bad_peaks` (QC-02 FAIL-side fixture)."""
    return _KNOWN_BAD_PEAKS_DIR

@pytest.fixture
def clean_peaks_dir() -> Path:
    """Resolve `tests/fixtures/nus/clean_peaks_synthetic` (QC-02 PASS-side fixture)."""
    return _CLEAN_PEAKS_DIR
```
Add an equivalent `jcamp_known_good_peaks_dir` fixture, either in a new
`tests/fixtures/jcamp/conftest.py` (if one doesn't already exist for that
tree) or alongside the existing `tests/nus/conftest.py` pattern — planner
discretion per CONTEXT.md's "Layout of `VALIDATION.md` and where the
committed peak JSONs / positive fixture live" discretion point. **Hard
constraint (D-11):** this new fixture directory must be physically distinct
from — and must never write into or overwrite — `tests/fixtures/nus/known_bad_peaks/`
or the external `.../C20H32O2/analysis/nmr_peaks/` known-bad lists.

**Peak-JSON schema to match exactly** (`tests/fixtures/nus/known_bad_peaks/HSQC_exp3.json`,
lines 1-13 — the same schema `bridge_peak_pick`/`write_peak_json` in
`nus/bridge.py` produce, so the new fixture's shape is not invented, only
populated with real numbers):
```json
{
 "experiment": "HSQC edited (exp3, hsqcedetgpsp.3)",
 "caveat": "...",
 "n_cross_peaks": 27,
 "cross_peaks": [
  {
   "c13_ppm": 69.06,
   "h1_ppm": 0.99,
   "edited_sign": "positive(CH_or_CH3)",
   "multiplicity_hint": "CH_or_CH3",
   "confidence": "low",
   "note": "..."
  },
  ...
```
The new "known-good" fixture is simply the real, accepted `lucy jcamp`
output copied in (with `confidence` reading `"high"` where the QC verdict is
PASS, matching the existing `confidence_from_verdict()` contract already
proven in `tests/test_cli_jcamp.py::TestJcampQcDiscrimination::test_pass_verdict_writes_consumable_peaks`,
line 581: `assert all(p["confidence"] == "high" for p in payload["cross_peaks"])`).

---

### `.planning/phases/103-.../VALIDATION.md` — evidence ledger + handoff-gate plan shape

**Analog 1 — layout/ledger shape:** `.planning/phases/102-cli-peak-pick-bridge-qc-reuse/102-VALIDATION.md` (full file, 130 lines).

Key sections to mirror verbatim in structure:
```markdown
## Test Infrastructure
| Property | Value |
...
## Sampling Rate
...
## Per-Task Verification Map
| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
...
## Manual-Only Verifications
| Behavior | Requirement | Why Manual | Test Instructions |
...
## Proof-Level Ledger (honesty gate)
| Level | What it covers in Phase 102 |
|-------|------------------------------|
| **FIXTURE-COVERED (real committed data)** | ... |
| **SYNTHETIC** | ... |
| **MOCK-COVERED (real peaks, injected verdict)** | ... |
| **NOT PROVEN — Phase 103 / JVAL** | Peak-count plausibility, full-matrix SNR behaviour, §8-quality green verdict, CASE convergence, and any claim that a verdict is chemically correct |
## Validation Sign-Off
- [x] All tasks have `<automated>` verify commands
...
```
Phase 103's `VALIDATION.md` is explicitly the document that **moves these
exact four "NOT PROVEN — Phase 103 / JVAL" rows** into a real level
(FIXTURE-COVERED / REAL-DATA / MANUAL-VERIFIED-BY-CHEMIST) — reuse the same
row wording so the before/after is traceable across phases.

**Analog 2 — `autonomous: false` handoff-gate plan shape:**
`.planning/phases/100-cross-platform-hardening-end-to-end-validation/100-03-PLAN.md`
(full file, 275 lines) — the precedent CONTEXT.md D-16 explicitly names
("Mirrors `100-03-PLAN.md`'s honest `autonomous: false` shape").

Frontmatter shape to mirror (lines 1-38):
```yaml
---
phase: 100-cross-platform-hardening-end-to-end-validation
plan: 03
type: execute
wave: 2
depends_on: [100-01, 100-02]
files_modified:
  - .planning/phases/100-.../VALIDATION.md
  - .planning/ROADMAP.md
autonomous: false
requirements: [VAL-01, VAL-02]

user_setup:
  - service: ...
    why: "..."
    ...

must_haves:
  truths:
    - "..."
  artifacts:
    - path: ".planning/phases/100-.../VALIDATION.md"
      provides: "..."
      contains: "VAL-01"
  key_links:
    - from: "..."
      to: "..."
      via: "..."
      pattern: "qc"
---
```
Task-type pattern to mirror for the JVAL-01 knob/QC/chemist-gate work vs.
the JVAL-02 handoff:
- `<task type="checkpoint:human-verify" gate="blocking">` for Task 2's
  reconstruct/grade/tuning-budget/consolidate/write-VALIDATION.md shape
  (lines 134-196) — directly analogous to this phase's D-03 knob matrix +
  D-05 §10 table + D-07 chemist gate.
- `<task type="checkpoint:human-verify" gate="blocking">` for Task 3's fresh
  CASE-run observation (lines 198-237) — directly analogous to this phase's
  D-14 fresh-session handoff: "Claude launches the run; no code is added or
  instrumented ... observe (do NOT instrument) whether LSDRunner
  terminates ... Write a `## CASE Convergence` section into VALIDATION.md."
  D-14 differs in *who* starts the session (the user, not the executor) but
  the "observe, do not instrument" discipline and the VALIDATION.md section
  shape (`## CASE Convergence (VAL-02)` → this phase's JVAL-02 section)
  transfer directly.
- The `<verify><human-check>...</human-check></verify>` and
  `<resume-signal>` tags (lines 125, 131, 186, 196, 229, 236) are the
  concrete mechanism for D-16's "ends with an explicit handoff… stops".

## Shared Patterns

### Staged/final two-call QC wiring (unchanged, load-bearing)
**Source:** `src/lucy_ng/cli/jcamp.py` lines 290-294 (comment + call), reused by every 2D/1D staging and rebuild call site (lines 234, 265-275, 306-312, 341-347).
**Apply to:** the CLI knob-wiring change — the new per-experiment values must flow into every one of these four call sites without adding a second `run_qc_checks()` invocation anywhere.

### CR-01 stale-state clearing (unchanged, must not regress)
**Source:** `src/lucy_ng/cli/jcamp.py` lines 174-203 (`STEP 2.5`).
**Apply to:** any change to `cli/jcamp.py` — this clearing logic runs before staging begins on every invocation and must continue to run unconditionally regardless of which knob values are passed.

### Fail-loud, never-first-match validation idiom
**Source:** `src/lucy_ng/readers/jcamp.py::_resolve_dim` (lines 242-260) — raises `ValueError` on an unresolvable/ambiguous case rather than silently guessing.
**Apply to:** the new `key=value` option parser's unrecognized-experiment-key case (D-04's typo guard) and any reader-bound edge case introduced by the D-09 widening.

### `CliRunner(mix_stderr=False)` for any JSON-parsing CLI test
**Source:** `tests/test_cli_jcamp.py` class docstring, lines 212-226.
**Apply to:** every new test in `tests/test_cli_jcamp.py` that invokes `jcamp` with `--format json` and calls `json.loads(result.output)`.

### `_copy_fixtures(tmp_path)` — never invoke the CLI against the tracked fixture directory
**Source:** `tests/test_cli_jcamp.py` lines 55-68.
**Apply to:** every new CLI-surface test exercising the real committed `.dx` fixtures.

### Proof-level ledger vocabulary (FIXTURE-COVERED / SYNTHETIC / MOCK-COVERED / NOT PROVEN / REAL-DATA / MANUAL-ONLY)
**Source:** `102-VALIDATION.md` § "Proof-Level Ledger"; extended by `103-RESEARCH.md` § "Proof-Level Ledger" with a new **REAL-DATA** tier for claims verified directly against the real dataset this research session.
**Apply to:** `VALIDATION.md`'s own ledger section — every JVAL-01/JVAL-02 claim must be filed under exactly one of these levels, reusing identical wording across phases so drift is traceable.

### `autonomous: false` handoff-gate task shape
**Source:** `100-03-PLAN.md` tasks 1-3 (`checkpoint:human-action`/`checkpoint:human-verify`, `<verify><human-check>`, `<resume-signal>`).
**Apply to:** the single Phase-103 plan's structure per D-16 — one plan, `autonomous: false`, ending in an explicit D-14 handoff gate with a `<resume-signal>` the user answers after running `/lucy-ng:case` in a fresh session.

## No Analog Found

None — every file this phase touches or creates has a strong, recent, same-repo analog (the phase deliberately reuses Phase 101/102 code and Phase 100/102's own validation-artifact conventions). The one item with only a *documented pattern*, not a copyable source excerpt, is the `key=value` Click-option parser (D-04) — `visualize.py`'s `multiple=True` option proves the base idiom is used in this codebase, but the `key=value` splitting logic itself is genuinely new syntax; RESEARCH.md's own Code Examples "Pattern 3" is the closest available written idiom and is excerpted above in full.

## Metadata

**Analog search scope:** `src/lucy_ng/cli/`, `src/lucy_ng/readers/`, `src/lucy_ng/nus/`, `src/lucy_ng/processing/`, `tests/`, `tests/fixtures/nus/`, `tests/fixtures/jcamp/`, `.planning/phases/100-*`, `.planning/phases/102-*`.
**Files scanned:** `src/lucy_ng/cli/jcamp.py`, `src/lucy_ng/cli/visualize.py`, `src/lucy_ng/readers/jcamp.py`, `src/lucy_ng/nus/bridge.py`, `src/lucy_ng/processing/jcamp_1d_bridge.py`, `tests/test_cli_jcamp.py`, `tests/readers/test_jcamp.py`, `tests/nus/test_qc_regression.py`, `tests/nus/conftest.py`, `tests/fixtures/nus/known_bad_peaks/HSQC_exp3.json`, `102-VALIDATION.md`, `100-03-PLAN.md`.
**Pattern extraction date:** 2026-07-26
</content>
