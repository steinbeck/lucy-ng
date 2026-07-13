---
phase: 98-reconstruction-processing
reviewed: 2026-07-13T13:04:10Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - src/lucy_ng/nus/runner.py
  - src/lucy_ng/nus/postprocess.py
  - src/lucy_ng/nus/backends/nmrpipe_smile.py
  - src/lucy_ng/models/nus.py
  - src/lucy_ng/cli/nus.py
  - tests/nus/conftest.py
  - tests/nus/test_runner_faillloud.py
  - tests/nus/test_fnmode_branching.py
  - tests/nus/test_reconstruct_chain.py
  - tests/nus/test_processing_order.py
  - tests/nus/test_reconstruct_orchestration.py
  - tests/nus/test_reconstruct_integration.py
  - tests/nus/test_cli_reconstruct.py
  - tests/test_cli_nus.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 98: Code Review Report

**Reviewed:** 2026-07-13T13:04:10Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Reviewed the Phase 98 headless NUS 2D reconstruction pipeline: the fail-loud
`run_stage()` wrapper, the FnMODE-branched stage-order recipe table, the
`NmrPipeSmileBackend.convert()`/`reconstruct_indirect()` stages, the F2/F1
post-processing (`postprocess.py`), the `NusRunner.reconstruct()` orchestrator,
the CLI wrapper, and the test suite.

**Subprocess safety is sound.** Every external invocation uses a fixed `argv`
list, never `shell=True`, never a shell-invocation flag, and every value
threaded into `argv` is a typed `float`/`int` or a resolved `Path` (verified in
`_bruk2pipe_argv`, `process_direct`/`process_indirect`, `reconstruct_indirect`,
and the `nusExpand.tcl`/SMILE argv builders). All stages carry a `timeout`.
`expdir` is user-owned and `.resolve()`d; all intermediate paths are derived
under `expdir/analysis/nus_recon/<expN>/` from fixed literal filenames, with no
untrusted path component reaching a filesystem or subprocess call — no path
traversal or injection surface found.

The QF/COSY `convert_first` branch, the `-yMODE QF/QSEQ` provisional values, and
the F1 phase defaults are annotated PROVISIONAL and deferred to Phase 100 per the
review brief; they are NOT flagged below.

The four warnings concern correctness/robustness of the *non-provisional* paths:
a gap in the fail-loud data-integrity guard for the SMILE output, a structurally
unreachable "hard gate", and two defects in the ppm-calibration sidecar
(axis-size mismatch and an OFFSET unit error).

## Warnings

### WR-01: Fail-loud all-zero data check silently skips the SMILE output (`.ft1`)

**File:** `src/lucy_ng/nus/runner.py:97`
**Issue:** `run_stage()`'s all-zero/truncated-data guard — the specific defense
against Pitfall 14 ("csh-piped NMRPipe stages can silently pass through truncated
data") — only fires when `expected_output.suffix in {".fid", ".ft2"}`. The SMILE
reconstruction step writes `reconstructed.ft1` (`reconstruct_indirect()`,
`nmrpipe_smile.py:513`), whose suffix `.ft1` is **not** in that set. SMILE is the
single stage most prone to producing plausible-but-garbage/empty output (it is
the sparse iterative reconstruction itself), yet its output receives only the
`exists()`/`st_size == 0` check, never the nmrglue all-zero parse check. A
non-empty but all-zero `.ft1` would pass the gate and propagate a silently-dead
spectrum into `process_indirect()`.
**Fix:** Include `.ft1` (and any other real NMRPipe-parseable intermediate
suffix) in the data-integrity check:
```python
if expected_output.suffix in {".fid", ".ft1", ".ft2"}:
```
Consider driving this off "is this an nmrglue-readable NMRPipe artifact" rather
than an allowlist of suffixes so future stages are covered by default.

### WR-02: F2-before-F1 "hard gate" is structurally unreachable in production

**File:** `src/lucy_ng/nus/runner.py:422-428` (with `_resolve_f2_plan`, 337-341)
**Issue:** `reconstruct()` advertises the F2-before-F1 ordering as an explicit
precondition (RECON-02) that raises "BEFORE any subprocess is dispatched". In
practice the gate can never trigger: `_resolve_f2_plan()` returns `None` only when
`recipe_for_fnmode(params.fnmode_f1)` raises `NotImplementedError`, which happens
only for a `fnmode` outside `VALID_FNMODES`. But `params.fnmode_f1` is already
Pydantic-validated to be in `VALID_FNMODES` at parse time
(`models/nus.py:87-93`), and `_FNMODE_RECIPES` covers exactly that same set. So
`f2_plan is None` is dead code — the only way to exercise it is the monkeypatch in
`test_f2_before_f1_gate_raises_before_any_subprocess`. The actual F2-before-F1
ordering is therefore enforced *solely* by the statement order of the four calls
in `reconstruct()`, not by the advertised precondition. The "gate" gives a false
sense of an independent ordering guarantee.
**Fix:** Either (a) make the gate meaningful — assert the concrete precondition it
claims to protect, e.g. that `process_direct()`'s transposed output exists and is
non-empty before dispatching SMILE (already partly covered by `run_stage`, so this
would be a redundant explicit check), or (b) drop the unreachable `None` branch
and document that ordering is enforced by call sequence, so the code no longer
implies a runtime guard that does not exist.

### WR-03: ppm-calibration sidecar axis is built with the raw grid size, not the processed (zero-filled) F1 size

**File:** `src/lucy_ng/nus/postprocess.py:290-295`
**Issue:** `_write_ppm_calibration_sidecar()` computes the F1 ppm axis with
`size=params.nus_td` (the raw full-grid point count). But `process_indirect()`'s
verb chain applies `ZF -auto` then `FT` (`postprocess.py:238-241`) before the
transpose, so the actual F1 axis of the produced `processed.ft2` has the
zero-filled point count (typically the next power of two ≥ `nus_td`), not
`nus_td`. The sidecar's `raw_ppm_axis`/`calibrated_ppm_axis` therefore have the
wrong length and per-point spacing relative to the spectrum they are meant to
label — a downstream consumer aligning peaks to this axis will read shifts off a
mismatched grid.
**Fix:** Derive the axis size from the actual processed F1 dimension (read it back
from the `.ft2` header via `nmrglue`, or compute the ZF size the same way the `ZF
-auto` verb does) rather than from `params.nus_td`. At minimum, record the
intended vs. actual size discrepancy so this is not silently wrong when Phase 100
validates against real data.

### WR-04: `ppm_scale()` treats Bruker OFFSET as Hz, but the parsed `f1_offset` is in ppm

**File:** `src/lucy_ng/nus/postprocess.py:313-334` (fed by `params.f1_offset`)
**Issue:** `ppm_scale()` computes `(offset - i * hz_per_point) / sf` and documents
`offset` as "ppm-scale offset (Hz)". The per-point spacing term
`i*(sw_h/size)/sf` correctly yields ppm/point, but dividing `offset` by `sf` is
only correct if `offset` is in Hz. The value actually threaded in is
`params.f1_offset`, read from Bruker `pdata/1/proc2s` `OFFSET`
(`params.py:118`), which Bruker stores **in ppm** (the ppm of the leftmost/highest
point). Dividing a ppm value by `sf` (≈150 MHz for 13C) collapses the axis start
to ~1 ppm instead of ~200 ppm, so the entire computed axis is shifted by a large
constant. This is not rescued by `calibrate_against_1d_reference()`: because every
computed point is shifted ~140+ ppm away from the true scale, no reference shift
falls within `tol=5.0` ppm of any computed point, so `deltas` is empty and
`offset_applied` is `0.0` (no correction applied). The sidecar's axis is therefore
genuinely wrong, not merely uncalibrated.
**Fix:** Use `offset` (ppm) directly for the axis start and divide only the
spacing term by `sf`:
```python
ppm_per_point = (sw_h / sf) / size
return [offset - i * ppm_per_point for i in range(size)]
```
and correct the docstring to state `OFFSET` is in ppm. Verify units against a
known 1D `proc2s`/`procs` pair before Phase 100.

## Info

### IN-01: `run_stage()` timeout raises `TimeoutExpired`, not the documented `RuntimeError`

**File:** `src/lucy_ng/nus/runner.py:82-83`
**Issue:** The docstring's `Raises:` block promises `RuntimeError` for stage
failures, but `subprocess.run(..., timeout=timeout)` raises
`subprocess.TimeoutExpired` on timeout, which propagates uncaught. This is still
fail-loud, but callers/tests matching on `RuntimeError` will miss the timeout
case, and the contract is inaccurate.
**Fix:** Either catch `TimeoutExpired` and re-raise as `RuntimeError` (uniform
fail-loud type), or document `TimeoutExpired` as an expected raised type.

### IN-02: `NusReconstructionResult.smile_iterations` is never populated

**File:** `src/lucy_ng/nus/runner.py:477`
**Issue:** `reconstruct()` always passes `smile_iterations=None`. The model field
and `summary()` support it ("iterations SMILE actually ran, if known"), but
nothing parses SMILE's `-verb` output to fill it, so it is dead in every result.
**Fix:** Parse the iteration count from SMILE's captured stdout/stderr (requires
`run_stage()` to surface captured output), or drop the field until it is wired up
to avoid a permanently-null result attribute.

### IN-03: CLI `reconstruct` surfaces pipeline errors as raw tracebacks

**File:** `src/lucy_ng/cli/nus.py:233-245`
**Issue:** `reconstruct()` lets `RuntimeError`/`NotImplementedError`/
`FileNotFoundError` from `NusRunner.reconstruct()` propagate uncaught, producing a
full Python traceback instead of a clean message + non-zero exit. This is
inconsistent with the sibling `check` command, which formats a diagnostic and
`raise SystemExit(1)`. (The `params`/`schedule` commands share the same
propagate-raw pattern, so this is a pre-existing project convention, not new to
this phase — hence Info.)
**Fix:** Wrap the `reconstruct()` call, `click.echo(str(exc), err=True)` on the
known failure types, and `raise SystemExit(1)` for a clean CLI failure surface.

---

_Reviewed: 2026-07-13T13:04:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
