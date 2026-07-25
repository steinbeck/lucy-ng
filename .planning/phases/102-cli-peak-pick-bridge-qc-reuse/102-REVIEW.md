---
phase: 102-cli-peak-pick-bridge-qc-reuse
reviewed: 2026-07-25T10:59:38Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/lucy_ng/cli/jcamp.py
  - src/lucy_ng/cli/main.py
  - src/lucy_ng/processing/__init__.py
  - src/lucy_ng/processing/jcamp_1d_bridge.py
  - src/lucy_ng/readers/jcamp.py
  - tests/fixtures/jcamp/_generate_fixture.py
  - tests/readers/test_jcamp.py
  - tests/test_cli_jcamp.py
  - tests/test_jcamp_1d_bridge.py
  - tests/test_skill_files_unchanged.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 102: Code Review Report

**Reviewed:** 2026-07-25T10:59:38Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 102 wires a new `lucy jcamp` command on top of the byte-frozen Phase-99
`nus/bridge.py`/`nus/qc.py` subsystem plus two new, well-tested modules
(`readers/jcamp.py`'s `procs_index` homonuclear-disambiguation addition and
the new `processing/jcamp_1d_bridge.py`). The homonuclear ppm-axis fix in
`readers/jcamp.py` is correct and well-proven (unique-nucleus-match path is
never overridden by the positional hint; the fail-loud `ValueError` still
fires when no hint is supplied and the match is ambiguous). The 1D bridge's
payload shape is schema-identical to `cli/pick.py::pick_1d` and does not
drift into the 2D `cross_peaks` shape that `nus/qc.py::_load_1d_shifts`
would silently swallow. `mypy`/`ruff` are clean on all in-scope files
(pre-existing baseline errors in unrelated modules are unaffected), and the
full targeted test suite (52 tests across these files) passes.

However, direct reproduction against `cli/jcamp.py` found a serious,
concrete defect in the write-boundary logic: **the command never clears its
staging/quarantine/consumable output directories between invocations.**
Re-running `lucy jcamp <dir>` against the same target directory after the
input file set changes (a file removed, or a previous run's verdict was
different) mixes stale data from a prior run into the current run's QC
computation and, worse, leaves a stale, previously-PASS-graded
`analysis/nmr_peaks/*.json` file in place even when the *current* run's QC
verdict is FAIL and correctly refuses to write anything new — silently
defeating the exact D-07 write-boundary guarantee this milestone exists to
provide. This is classified Critical/BLOCKER below, with a live
reproduction included. Two further Warning-level robustness/maintainability
issues and one Info-level documentation nit round out the findings.

## Critical Issues

### CR-01: `lucy jcamp` never clears staging/quarantine/consumable directories across invocations — stale peak data silently pollutes both the QC verdict and the "clean" output

**File:** `src/lucy_ng/cli/jcamp.py:162-171` (directories computed, never reset) and `:256` (the single `run_qc_checks()` call, which globs whatever happens to be sitting in `staged_dir`)

**Issue:**

`work_root`/`staged_dir`/`quarantine_dir`/`out_root` are all computed as
**fixed, run-to-run-identical paths** derived from `--out` (or the default
`<input-dir>/analysis/nmr_peaks`). Nothing in the command ever removes or
resets their prior contents before staging the current invocation's files;
`write_peak_json()` (unchanged, in `nus/bridge.py`) only overwrites the
specific `{experiment}.json` it is asked to write, via
`out_dir.mkdir(parents=True, exist_ok=True)` + `write_text(...)` — it never
touches files for experiment types that are not part of *this* call.

Concretely, `run_qc_checks(staged_dir)` (line 256) globs **the entire
`staged_dir`** by keyword (`nus/qc.py::_glob_by_keyword`/`_load_peaks`), so
any file left over from an earlier invocation that is still sitting in
`staged_dir` is silently included in the QC computation for the *current*
run, even if the corresponding `.dx` input no longer exists on this
invocation. Likewise, files under `out_root` (the consumable directory
`analysis/nmr_peaks/`) and `quarantine_dir` from a previous run are never
removed, so they persist unchanged after a later run that does not
re-produce them.

**Live reproduction (verified against this worktree):**

1. Run `lucy jcamp <dir>` on a directory containing `HSQC`, `COSY`, `1H`,
   `13C` fixtures → `analysis/jcamp_ingest/staged/` ends up with
   `13C.json, 1H.json, COSY.json, HSQC.json`.
2. Delete `C20H32O2_COSY_trimmed.dx` from `<dir>` and re-run `lucy jcamp
   <dir>` with the exact same command.
3. `analysis/jcamp_ingest/staged/COSY.json` **is still present**
   (unchanged, from run 1) and `run_qc_checks()` for run 2 reports:
   ```
   signal_to_ridge   False  max ridge_fraction=0.73 at COSY.h1a_ppm
   cosy_diagonal_symmetry  False  1% of COSY cross-peaks have a diagonal mirror
   ```
   — even though **no COSY file was read or staged in run 2 at all**. The
   quarantine directory (`jcamp_ingest/qc_failed/`) also still contains a
   stale `COSY.json` from run 1's quarantine.

**Second reproduction — the write boundary itself is bypassable:**

1. With a monkeypatched `run_qc_checks` forced to `PASS`, run `lucy jcamp
   <dir>` on `HSQC + 1H + 13C` fixtures → `analysis/nmr_peaks/HSQC.json`
   is written with `"qc_verdict": "PASS"`.
2. Re-run the identical command with `run_qc_checks` now forced to `FAIL`
   (simulating "the reconstruction later degraded" or simply "the operator
   reran after the input changed").
3. The CLI correctly exits `1` and correctly does **not** write a new
   `HSQC.json` — but `analysis/nmr_peaks/HSQC.json` **from step 1 is still
   present on disk, unchanged, still reporting `"qc_verdict": "PASS"`.**

A downstream consumer (e.g. the CASE orchestrator, which per this
milestone's own design treats "does `analysis/nmr_peaks/HSQC.json` exist"
as evidence the reconstruction is QC-graded and usable) would read a
stale, previously-passing file and have no way to know the *most recent*
invocation actually FAILED QC. This is precisely the "plausible but wrong
data silently presented as clean" defect class this milestone's whole
design (the D-07 write boundary, the QC gate itself) exists to prevent —
it is just reintroduced one layer up, via directory statefulness that was
never reset.

Note: `cli/nus.py::pipeline` (the byte-frozen sibling this command's
staged/final two-pass pattern is explicitly modeled on) does not have this
exposure in practice, because its `stage_dir` is scoped to exactly one
experiment per invocation and every write there is a full overwrite of the
only file that can ever exist in that directory. `cli/jcamp.py` is a
*multi-file, whole-directory* command — the design that pattern was copied
into does not carry the same safety property, and nothing in Phase 102
compensates for that.

**Fix:** Reset all three of the command's own working trees at the start
of every invocation, before STEP 3 begins staging:

```python
import shutil

# STEP 2.5 -- every invocation must reflect ONLY the files discovered this
# run: clear any stale staged/quarantine/consumable state left by a
# previous invocation before staging begins (prevents stale cross-peaks
# from polluting run_qc_checks(), and prevents a stale PASS-graded file
# surviving a later FAIL run).
shutil.rmtree(work_root, ignore_errors=True)
shutil.rmtree(out_root, ignore_errors=True)
```

placed immediately after `work_root`/`staged_dir`/`quarantine_dir`/`out_root`
are computed (after line 171) and before the STEP 3 loop begins. Add a
regression test that runs `lucy jcamp <dir>` twice with a changing file set
(or changing verdict) and asserts the second run's `report`/output
directory reflect only the second run's inputs.

## Warnings

### WR-01: Bare `assert isinstance(spectrum, Spectrum2D)` used for control-flow type narrowing

**File:** `src/lucy_ng/cli/jcamp.py:208`

**Issue:** The 2D branch of the per-file dispatch loop is guarded only by
`assert isinstance(spectrum, Spectrum2D)`. `assert` statements are removed
under Python's `-O`/`-OO` optimization flags. If `JcampReader.read()` were
ever to return something that is neither `Spectrum1D` nor `Spectrum2D` (a
future refactor, a third dimensionality branch, etc.), running under `-O`
would silently skip the narrowing and proceed to access
`spectrum.experiment_type` on an unverified object rather than failing
loudly at the intended checkpoint. This is purely a defensive-robustness
concern (today's `JcampReader.read()` signature guarantees only these two
types), but relying on `assert` for a load-bearing control-flow branch in a
data-processing pipeline that has "fail loud, never silently mis-process"
as an explicit design goal elsewhere in this same phase is inconsistent
with that goal.

**Fix:**
```python
if not isinstance(spectrum, Spectrum2D):
    raise TypeError(f"Unexpected JcampReader.read() result type: {type(spectrum)!r}")
```

### WR-02: `SUPPORTED_2D`/`SUPPORTED_1D` are hand-duplicated copies of the reused subsystems' own supported-experiment sets, with no drift guard

**File:** `src/lucy_ng/cli/jcamp.py:32-33`

**Issue:** The module comment at line 30 explicitly acknowledges this is a
deliberate duplicate of `nus/bridge.py`'s private `_VALID_BRIDGE_EXPERIMENTS`
(`{"HSQC", "HMBC", "COSY"}`) rather than an import of it, and
`processing/jcamp_1d_bridge.py`'s `_VALID_1D_NUCLEI` (`{"1H", "13C"}`) is a
third, independent copy of the same idea. There is no test asserting these
three sets stay in sync. If a future phase extends
`_VALID_BRIDGE_EXPERIMENTS` (e.g. adds TOCSY) or `_VALID_1D_NUCLEI`, this
command's `SUPPORTED_2D`/`SUPPORTED_1D` tuples will silently continue
routing the newly-supported experiment type to the D-06 "skip" path
(`experiment_type is not supported by the peak-pick bridge`) instead of
picking it — a silent capability regression that would only be caught by
a human noticing the skip warning, not by any test or type check.

**Fix:** Add a cheap unit test in `tests/test_cli_jcamp.py` that imports
`lucy_ng.nus.bridge._VALID_BRIDGE_EXPERIMENTS` and
`lucy_ng.processing.jcamp_1d_bridge._VALID_1D_NUCLEI` and asserts
`set(SUPPORTED_2D) == _VALID_BRIDGE_EXPERIMENTS` /
`set(SUPPORTED_1D) == _VALID_1D_NUCLEI`, so any future drift fails loudly
in CI rather than silently changing routing behaviour.

## Info

### IN-01: Misleading rationale for the all-zero-spectrum guard in `bridge_peak_pick_1d`

**File:** `src/lucy_ng/processing/jcamp_1d_bridge.py:56-60, 80-87`

**Issue:** The docstring/comment claims the explicit `max_abs == 0.0` guard
prevents "a divide-adjacent edge case" that `cli/pick.py::pick_1d` "does
not guard". In fact neither function performs any division here —
`pick_1d`'s unguarded expression is `-effective_threshold * max_abs`, a
multiplication. For an all-zero spectrum this evaluates to `-0.0`, and
`np.min(spectrum.data) < -0.0` is `False` for an all-zero array regardless
of the guard (float comparison, `0.0 < -0.0` is `False`). So the guard is
behaviourally a no-op versus `pick_1d`'s own (unguarded) formula for this
input — it doesn't change the output, and there is no division anywhere to
protect against. This doesn't cause incorrect behaviour, but the comment
overstates the risk being mitigated and could mislead a future maintainer
into thinking `pick_1d` has a latent crash bug it does not have.

**Fix:** Either drop the guard (it changes nothing) or correct the
docstring to state the true, narrower rationale (defensive clarity for
future maintainers reading the SNR-mode branch, not a division/crash
guard).

---

_Reviewed: 2026-07-25T10:59:38Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
