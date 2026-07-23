---
phase: 101-jcamp-dx-reader
plan: 04
subsystem: readers
tags: [jcamp-dx, nmrglue, ntuples, difdup, ppm-axis, spectrum2d]

# Dependency graph
requires:
  - phase: 101-02
    provides: "Vendored DIFDUP/SQZ/DUP/PAC decoder (readers/_jcampdx_decode.py::parse_data)"
  - phase: 101-03
    provides: "Shared, contract-defining helpers in readers/jcamp.py (_read_metadata, _ppm_scale, _assert_plausible_ppm_axis, _resolve_dim, _clean_nucleus_label) plus JcampReader.read_1d"
provides:
  - "JcampReader.read_2d(path) -> Spectrum2D: assembles DIFDUP-compressed NTUPLES pages into a full (n_f1, n_f2) intensity matrix, Y-FACTOR-scaled, with reversed and plausibility-checked ppm axes on both dimensions"
  - "JcampReader.read(path) -> Spectrum1D | Spectrum2D: dispatcher on ##NUM DIM= (absent -> 1D)"
  - "_apply_yfactor / _page_hz: small new reader-internal helpers"
  - "The JC-02 load-bearing cross-check (2D axes vs 1D reference peaks) proven GREEN on real, committed fixture data"
affects: ["102"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NTUPLES page assembly: SYMBOL string parsed once into a generic F1/F2/Y column-index map (never hardcoded), used to index FACTOR/FIRST/LAST/VAR_DIM consistently"
    - "Fail-loud NTUPLES structural consistency: len(PAGE)==len(DATATABLE)==VAR_DIM[F1] and decoded-row-length==VAR_DIM[F2] asserted before any data is trusted (T-101-04)"
    - "Local-window ppm re-anchoring: when a page window is a TRIMMED SLICE of a much larger original NTUPLES axis, the file's global $OFFSET anchors the ORIGINAL axis's first point, not the slice's own first page -- the local anchor must be recomputed from the slice's actual position before reusing the shared linspace-based _ppm_scale helper"

key-files:
  created: []
  modified:
    - src/lucy_ng/readers/jcamp.py

key-decisions:
  - "F1 (indirect) axis point count and endpoints come from the per-page ##PAGE= Hz values (not the global FIRST/LAST triple, which only reflects the file's original untrimmed page count) -- but the axis's ppm ANCHOR still comes from the file's global $OFFSET+FIRST, re-based onto the window's own first page's Hz value before calling _ppm_scale. This is a refinement of 101-RESEARCH.md Pitfall 3's stated formula, discovered via the JC-02 cross-check itself (see Deviations)."
  - "F2 (direct) axis uses the global FIRST[0]/LAST[0] triple directly with n_f2 read points, since F2 is never trimmed by fixture generation (only the F1/page dimension was sliced)."
  - ".NUCLEUS's comma-split order gives f1_nucleus/f2_nucleus (guaranteed SYMBOL-matching order per 101-RESEARCH.md Pitfall 4); $NUC1 (co-indexed with $SF/$OFFSET) is used separately via _resolve_dim to look up each nucleus's own offset/sf pair."
  - "read()'s ##NUM DIM= dispatch treats an ABSENT NUM DIM key as NUM DIM=1, since real 1D JCAMP-DX files carry no ##NUM DIM= line at all (verified directly against both committed 1D fixtures) -- only 2D files declare it explicitly."

patterns-established:
  - "SYMBOL-driven generic dimension-index resolution (dims.index('F1')/('F2')/('Y')) rather than hardcoded tuple-position assumptions, extending Plan 03's _resolve_dim degeneracy-guard philosophy to the NTUPLES column-order question"

requirements-completed: ["JC-01", "JC-02"]

# Metrics
duration: 45min
completed: 2026-07-23
---

# Phase 101 Plan 04: 2D NTUPLES Page Assembly + read() Dispatcher Summary

**`JcampReader.read_2d` assembles DIFDUP-compressed NTUPLES pages into a Y-FACTOR-scaled `(16, 2048)` `Spectrum2D` with reversed, cross-check-verified ppm axes on both dimensions -- closing JC-01/JC-02, the milestone's one real technical risk.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-07-23T15:35:00Z (approx)
- **Completed:** 2026-07-23T16:20:00Z (approx)
- **Tasks:** 2/2 completed
- **Files modified:** 1 (`src/lucy_ng/readers/jcamp.py`)

## Accomplishments
- Implemented `JcampReader.read_2d`: parses `SYMBOL` ("F1,F2,Y") into a generic column-index map, fail-loud asserts `len(PAGE)==len(DATATABLE)==VAR_DIM[F1]` and decoded-row-length `==VAR_DIM[F2]` (T-101-04), locates the SYMBOL-indexed `Y_FACTOR` and scales every decoded row via a new `_apply_yfactor` helper, and stacks 16 real DIFDUP-decoded pages into a `(16, 2048)` float64 matrix
- Derived both ppm axes via the shared `_ppm_scale`/`_resolve_dim`/`_assert_plausible_ppm_axis` helpers from Plan 03: F2 (¹H, direct) from the global `FIRST[0]`/`LAST[0]` triple; F1 (¹³C, indirect) from the per-page `##PAGE= F1=<hz>` values, re-anchored to the file's global `$OFFSET` (see Deviations -- this re-anchoring was the one real bug this plan's own JC-02 cross-check caught and fixed)
- Implemented `JcampReader.read()`: dispatches on `##NUM DIM=` (absent -> 1D, `2` -> 2D), raising `ValueError` for any other value
- **JC-02's load-bearing cross-check is GREEN**: `test_read_2d_ppm_axes_match_1d_reference` projects the 2D onto both axes and matches against the real 1D `¹H`/`¹³C` reference spectra within tolerance (¹H ≤0.05 ppm, ¹³C ≤0.10 ppm) -- proving the axes are calibrated, not merely plausible
- All three previously-RED tests now GREEN (`test_read_2d_shape`, `test_read_2d_yfactor_scaling`, `test_read_2d_ppm_axes_match_1d_reference`); full `tests/readers/` suite (9 tests) green; `mypy --strict`/`ruff` clean on `jcamp.py` (only the pre-existing, already-accepted "nmrglue missing stubs" note remains, matching Plan 03's precedent)
- Full project suite: **1408 passed, 8 skipped, 1 xfailed** (up from Plan 03's 1405 passed -- exactly the 3 newly-GREEN tests, zero regressions)

## Task Commits

1. **Task 1: read_2d -- page assembly + Y-FACTOR + reversed ppm axes + fail-loud (JC-01, JC-02 reader-internal)** - `a89c0de` (feat)
2. **Task 2: read() dispatcher + JC-02 load-bearing 1D cross-check** - `731814d` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `src/lucy_ng/readers/jcamp.py` - Added `_apply_yfactor`, `_page_hz` helpers, `JcampReader.read_2d`, `JcampReader.read`; updated imports (`Spectrum2D`, `parse_data`)

## Decisions Made
- F1 axis anchor re-basing (see Deviations) -- the single substantive technical decision this plan made beyond the plan's literal wording, required because the committed trimmed fixture's `$OFFSET` anchors the file's ORIGINAL (untrimmed) NTUPLES axis, not the trimmed window's own first page.
- `read()` treats a missing `##NUM DIM=` key as `NUM DIM=1` rather than raising, since real 1D JCAMP-DX files never declare that key at all (confirmed by direct inspection of both committed 1D fixtures) -- this is the only dimensionality-absent case the real data exhibits, so treating absence as an error would break `read()` on every real 1D file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] F1 ppm-axis formula anchored at the wrong Hz reference point for a trimmed fixture window**
- **Found during:** Task 2, running the JC-02 load-bearing cross-check test (`test_read_2d_ppm_axes_match_1d_reference`)
- **Issue:** The plan's literal action text calls for `_ppm_scale(page_hz[0], page_hz[-1], offset_F1, sf_F1, n_f1)` -- treating the trimmed window's own first page Hz value as the axis's anchor point matching `$OFFSET`. On the real committed fixture this produced an F1 axis of `~174.99 ppm` down to `~173.67 ppm` (implausible for the real 13C gem-dimethyl signal, which should read `~21-23 ppm`) -- passing the coarse `_assert_plausible_ppm_axis` bounds check (still inside `[-15, 230]` and still descending) but failing the JC-02 cross-check by 64 ppm. Root cause: `tests/fixtures/jcamp/_generate_fixture.py` preserves the NTUPLES header (including `$OFFSET`/global `FIRST`/`LAST`) verbatim during trimming, slicing ONLY the `PAGE`/`DATATABLE` window -- so `$OFFSET` still anchors the file's ORIGINAL, untrimmed F1 axis's first point (Hz ~21997.14), not the trimmed window's own first page (Hz ~2830.44).
- **Fix:** Compute the local anchor at `page_hz[0]` by re-basing the global offset through the verified `OFFSET+SF` formula (`f1_local_offset = f1_offset - (f1_global_first_hz - page_hz[0]) / f1_sf`, using the global NTUPLES header's `FIRST[0]` F1 component as `f1_global_first_hz`), then pass that corrected local offset into the unmodified shared `_ppm_scale(page_hz[0], page_hz[-1], f1_local_offset, f1_sf, n_f1)` call. This still reuses the shared helper exactly as instructed, only correcting what value is passed as its anchor.
- **Files modified:** `src/lucy_ng/readers/jcamp.py`
- **Verification:** `test_read_2d_ppm_axes_match_1d_reference` GREEN (F1 peak within 0.10 ppm of the real 13C reference, F2 peak within 0.05 ppm of the real 1H reference); full `tests/readers/` suite green; full project suite 1408 passed / 8 skipped / 1 xfailed, zero regressions.
- **Committed in:** `a89c0de` (Task 1 commit -- the fix belongs to `read_2d`'s own formula, per the plan's own instruction that "the bug is in the Task-1 formula/dimension mapping, not the test")

---

**Total deviations:** 1 auto-fixed (1 bug fix, caught by the plan's own designed JC-02 cross-check test working exactly as intended)
**Impact on plan:** No scope creep -- this is the plan's own stated failure mode ("if the cross-check reveals an axis error, the bug is in the Task-1 formula... fix the reader, never loosen the tolerance") being exercised and resolved as designed. JC-02's tolerance was never touched.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 101 (JCAMP-DX Reader) is now fully complete: JC-01, JC-02, JC-03, JC-04 all satisfied and CI-verified against committed real fixture data (no external binary, no mocks for the crux path).
- `JcampReader.read()`/`read_1d()`/`read_2d()` are the stable, complete public surface Phase 102's `lucy jcamp` CLI will wrap directly.
- Full suite: 1408 passed, 8 skipped, 1 xfailed -- no regressions, no known stubs, no deferred items from this plan.
- No blockers.

---
*Phase: 101-jcamp-dx-reader*
*Completed: 2026-07-23*

## Self-Check: PASSED

`src/lucy_ng/readers/jcamp.py` and `.planning/phases/101-jcamp-dx-reader/101-04-SUMMARY.md` verified present on disk; commits `a89c0de` and `731814d` verified present in `git log --oneline --all`.
