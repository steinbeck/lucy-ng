---
phase: 101-jcamp-dx-reader
reviewed: 2026-07-23T14:18:30Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - src/lucy_ng/readers/jcamp.py
  - src/lucy_ng/readers/_jcampdx_decode.py
  - tests/readers/test_jcamp.py
  - tests/readers/test_jcampdx_decode.py
  - tests/fixtures/jcamp/_generate_fixture.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 101: Code Review Report

**Reviewed:** 2026-07-23T14:18:30Z
**Depth:** deep
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the two new source modules (`readers/jcamp.py`, `readers/_jcampdx_decode.py`) and their
tests/fixture-generator. The review focused adversarially on the phase's stated crux risk — the
ppm-axis formula (JC-02) — and on fail-loud discipline for malformed NTUPLES structure (JC-01).

**Core correctness verdict: no blocker found.** I independently re-derived the OFFSET+SF ppm
formula by hand and traced it against the real committed fixture's metadata (`$OFFSET`, `$SF`,
`FIRST`/`LAST`, `PAGE`), including the local-anchor re-basing algebra the 101-04 executor added for
the trimmed-window case (`f1_local_offset = f1_offset - (f1_global_first_hz - page_hz[0]) / f1_sf`).
The re-basing is algebraically equivalent to applying the global formula directly to the window's
own first point — confirmed by substitution, not just by the fixture's tests passing. I also
independently exercised (outside the committed suite, via monkeypatching) several of `read_2d`'s
fail-loud branches (`PAGE`/`DATATABLE` count mismatch, `_resolve_dim`'s homonuclear degeneracy
guard) and confirmed they raise `ValueError` correctly with the metadata this project's real files
actually produce.

What I found instead is a cluster of **robustness and test-coverage gaps**: an unguarded shape
assumption in `read_1d` that would crash with a confusing low-level exception (not silently
corrupt data) on a plausible-but-uncommon file shape; a complete absence of negative-path test
coverage for `read_2d`'s ~10 fail-loud branches, `_resolve_dim`'s degeneracy guard, and the new
`read()` dispatcher (none of which are exercised by any committed test, only by my own ad hoc
verification during this review); and one pre-existing (not introduced by vendoring) nmrglue defect
in the vendored decoder that is now first-party code and whose `# type: ignore[index]` marks the
exact line mypy flagged instead of guarding it.

## Warnings

### WR-01: `read_1d` assumes `jc.read()` always returns a `[real, imaginary]` list; a plausible real-world shape crashes with a confusing exception instead of a clear error

**File:** `src/lucy_ng/readers/jcamp.py:303-310`
**Issue:** `_dic, data = jc.read(str(path))` then `real = np.asarray(data[0], ...)`. This is only
correct when nmrglue's `getdataarray()` returns a 2-element `[real_array, imag_array]` list (the
NTUPLES path with both channels present — true for both committed 1D fixtures, verified directly).
But `getdataarray()` has two other reachable return shapes: (1) the XYDATA (non-NTUPLES) path
returns a single flat `ndarray`, not a list — `data[0]` then silently becomes the *first scalar data
point*, not the real channel; (2) the NTUPLES path with only a real channel and no imaginary
channel also collapses to a bare `rdatalist[0]` array (see nmrglue's `getdataarray`, the
`if rdatalist: ... else: data = rdatalist[0]` branch — no `else` wrapping in a list). In both cases
`data[0]` returns a numpy scalar; `np.asarray(scalar)` is 0-dimensional and the following
`n = len(real)` then raises `TypeError: len() of unsized object` — a confusing crash rather than the
module's own clear, path-including `ValueError` messages used everywhere else in this file. I
verified this exact `TypeError` reproduces with a plain scalar via direct execution.
**Fix:**
```python
_dic, data = jc.read(str(path))
if data is None:
    raise ValueError(f"JCAMP-DX file has no data payload: {path}")
if not (isinstance(data, list) and len(data) == 2 and data[0] is not None):
    raise ValueError(
        f"Unexpected JCAMP-DX 1D data shape for {path}: expected "
        f"[real, imaginary] NTUPLES channels, got {type(data)!r}"
    )
real = np.asarray(data[0], dtype=np.float64)
```

### WR-02: No negative-path test coverage for any of `read_2d`'s fail-loud branches, `_resolve_dim`'s degeneracy guard, or the new `read()` dispatcher

**File:** `tests/readers/test_jcamp.py` (absence), affecting `src/lucy_ng/readers/jcamp.py`
**Issue:** Fail-loud discipline against malformed NTUPLES structure is this phase's own explicit
design goal (101-RESEARCH.md "Security Domain" table, the plan's T-101-04 task, and the WR-04-class
degeneracy guard called out by name in 101-03-SUMMARY.md). The implementation of all of these checks
is logically correct (I confirmed two of them — `PAGE`/`DATATABLE` count mismatch and the homonuclear
`_resolve_dim` ambiguity guard — fire correctly via ad hoc monkeypatched calls during this review),
but **none of the ~10 `raise ValueError(...)` branches in `read_2d`** (missing/malformed `SYMBOL`,
`PAGE`/`DATATABLE` count mismatch, `VAR_DIM` F1/F2 mismatch, missing `FACTOR`, a `parse_data`
decode failure, inconsistent decoded-row lengths, missing/malformed `.NUCLEUS`, missing
`FIRST`/`LAST`, missing pulse sequence), **`_resolve_dim`'s** ambiguous/absent-nucleus paths, nor
**`JcampReader.read()`'s** dispatcher (`NUM DIM` = 1 / 2 / other-value error path) has a single line
of committed pytest coverage. `test_jcamp.py` only tests the happy path plus `read_1d`'s
`FileNotFoundError`. A future refactor could invert one of these conditions (e.g. `!=` to `==`) and
the full suite would stay green.
**Fix:** Add at minimum one test per `read_2d` fail-loud branch (construct a minimal malformed
metadata dict and monkeypatch `_read_metadata`, as this review did ad hoc) plus a direct test of
`_resolve_dim`'s ambiguous-nucleus `ValueError` and a `JcampReader.read()` dispatcher test (NUM DIM
absent → 1D, `="2"` → 2D, other value → `ValueError`).

### WR-03: Vendored decoder can dereference `None` when two DUP-mode pseudo-digits occur back-to-back — pre-existing upstream defect, now first-party code

**File:** `src/lucy_ng/readers/_jcampdx_decode.py:255`
**Issue:** `elif currentmode == 3 and value_to_append[1]:  # type: ignore[index]`. Tracing the state
machine: after `_finish_value` processes a DUP-mode number, it sets `value_to_append = None`
(line 183-184). If the *very next* pseudo-digit character is itself a single-character DUP code with
no intervening plain digit (three consecutive single-char DUP codes in a row, e.g. an encoded
plateau of identical values), this line executes with `currentmode == 3` and `value_to_append is
None`, raising an unhandled `TypeError: 'NoneType' object is not subscriptable` — bypassing this
same function's own `warn(...); return None` fail-loud contract used for every other malformed-input
case in this module. I confirmed this line is byte-identical to upstream nmrglue's `_parse_pseudo`
(not a vendoring-introduced regression — it is 101-02's own attribution: "self-contained,
byte-identical copy"), but it is now vendored into first-party `src/` rather than a third-party
dependency, and the `# type: ignore[index]` on this exact line is documentary evidence that mypy
flagged the same `None`-indexing risk during Plan 02 and it was suppressed rather than guarded.
**Fix:**
```python
elif currentmode == 3:
    if value_to_append is None:
        warn(f"DUP entry with no preceding value at line: {dataline}", stacklevel=2)
        return None
    if value_to_append[1]:
        previous_is_dif = True
```

### WR-04: `_read_metadata` raises an unguarded `IndexError` instead of a clear `ValueError` when a matched `_datatype_*` bucket is an empty list

**File:** `src/lucy_ng/readers/jcamp.py:76-85`
**Issue:** `inner: dict[str, Any] = value[0]` assumes the matched bucket's list is non-empty. Every
other missing/malformed-metadata case in this module raises a path-including `ValueError` with a
clear message; this one spot would instead surface a bare `IndexError: list index out of range`
with no file-path context if nmrglue ever returns an empty list for a matched `_datatype_*` key
(e.g. a `DATATYPE` line present with no actual data section following it).
**Fix:**
```python
for key, value in raw.items():
    if key.startswith("_datatype_"):
        if not value:
            raise ValueError(f"Empty '{key}' bucket in JCAMP-DX metadata for {path}")
        inner: dict[str, Any] = value[0]
        return inner
```

## Info

### IN-01: Redundant re-parsing of the same file / redundant index lookups

**File:** `src/lucy_ng/readers/jcamp.py`
**Issue:** `JcampReader.read()` calls `_read_metadata(path)` once to inspect `NUM DIM`, then
dispatches to `read_1d`/`read_2d`, each of which calls `_read_metadata(path)` again — parsing the
same file twice per `read()` call. Separately, `read_1d` calls `_read_metadata(path)` (→
`jc._readrawdic`) *and* `jc.read(str(path))` (which internally calls `_readrawdic` again) — the same
file is read from disk and re-parsed twice within a single `read_1d` call. Also, `dims.index("F1")`
is computed independently at both line 413 and line 491 in `read_2d` rather than being cached once
like `f2_index`/`y_index` are.
**Fix:** Not urgent (explicitly out of v1 scope per performance exclusion), but low-effort to
thread a single parsed `inner`/`dims` through the call chain if this is ever revisited.

### IN-02: `Any`-typed dual-purpose local variable weakens the mypy-strict guarantee it was added to satisfy

**File:** `src/lucy_ng/readers/_jcampdx_decode.py:203`
**Issue:** `valuestr: Any = []` is intentionally untyped because the vendored algorithm reuses the
same name for both a `list[str]` (accumulating characters) and a `str` (the joined, finished
number) — a legitimate but type-safety-defeating pattern. Documented as a deliberate trade-off in
101-02-SUMMARY.md ("added ... one `Any`-typed dual-purpose local variable"). No action required;
noted so a future reader doesn't mistake this for full type coverage of the decode loop.

### IN-03: COSY/NOESY (homonuclear) 2D assembly remains unverified through the actual `read_2d` code path

**File:** `src/lucy_ng/readers/jcamp.py` (read_2d), `tests/fixtures/jcamp/_generate_fixture.py`
**Issue:** The only homonuclear verification is a one-page spot-check in the fixture generator
script, calling nmrglue's own `_readrawdic`/`_parse_data` directly (dev tooling, not the reader).
`JcampReader.read_2d` has never actually been run against a real COSY/NOESY file — `_resolve_dim`'s
degeneracy guard is designed to fail loud rather than silently mis-resolve, so this is a documented,
deliberate deferral (RESEARCH.md Assumption A3, explicitly pushed to Phase 103), not a phase-101
defect. Flagging only so it isn't forgotten if Phase 102's CLI is wired to COSY/NOESY files before
Phase 103 lands.

### IN-04: `read()`'s `NUM DIM` parsing can raise a raw, context-free `ValueError`/`TypeError` for non-numeric values

**File:** `src/lucy_ng/readers/jcamp.py:548`
**Issue:** `num_dim = int(float(str(num_dim_raw[0]))) if num_dim_raw else 1` — if `##NUM DIM=` were
ever present but non-numeric (malformed file), `float(...)` raises an uncaught `ValueError` with no
file-path context, unlike the module's other validation errors.
**Fix:** Wrap in a `try/except` and re-raise with the file path, consistent with the module's other
error messages.

---

_Reviewed: 2026-07-23T14:18:30Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
