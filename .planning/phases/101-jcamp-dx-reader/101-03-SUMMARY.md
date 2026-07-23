---
phase: 101-jcamp-dx-reader
plan: 03
subsystem: readers
tags: [jcamp-dx, nmrglue, ppm-axis, spectrum1d, mypy-strict]

# Dependency graph
requires:
  - phase: 101-01
    provides: "RED test scaffolding (tests/readers/test_jcamp.py) + real committed fixtures (tests/fixtures/jcamp/*.dx)"
  - phase: 101-02
    provides: "Vendored DIFDUP/SQZ/DUP/PAC decoder (readers/_jcampdx_decode.py::parse_data) -- not directly imported by this plan, but the sibling module read_2d (Plan 04) will consume"
provides:
  - "src/lucy_ng/readers/jcamp.py: shared, contract-defining helpers (_read_metadata, _strip_caret, _clean_nucleus_label, _ppm_scale, _assert_plausible_ppm_axis, _resolve_dim) consumed by both read_1d (this plan) and read_2d (Plan 04)"
  - "JcampReader.read_1d(path) -> Spectrum1D: JC-03 GREEN for both 1H and 13C JCAMP-DX references"
  - "The verified OFFSET+SF ppm-axis formula (JC-02 crux) implemented and numerically proven against 101-RESEARCH.md's worked example"
  - "_resolve_dim's fail-loud homonuclear-degeneracy guard (WR-04 class), ready for Plan 04's 2D dimension resolution"
affects: ["101-04"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared-helpers-first module structure: contract-defining functions (ppm math, metadata access, dimension resolution) committed and verified in their own task before the first consumer (read_1d) is built on top of them, so Plan 04's read_2d has a stable, already-tested foundation"
    - "Dual nucleus-label unwrapping (_clean_nucleus_label): JCAMP-DX nucleus fields arrive in more than one wrapping convention depending on source key (caret-prefixed '.OBSERVE NUCLEUS' vs angle-bracket-wrapped '$NUC1') -- one helper strips both, rather than assuming a single convention"

key-files:
  created: []
  modified:
    - src/lucy_ng/readers/jcamp.py

key-decisions:
  - "_resolve_dim indexes into $SF/$OFFSET via $NUC1's own list position (not .NUCLEUS's), since $NUC1/$SF/$OFFSET are co-indexed by nmrglue's parse order while .NUCLEUS is a separately-ordered NTUPLES-standard field (101-RESEARCH.md Pitfall 4) -- verified against real fixture data where $NUC1=['<1H>','<13C>'] but .NUCLEUS='13C, 1H' (reversed order)"
  - "_clean_nucleus_label strips BOTH caret ('^1H') and angle-bracket ('<1H>') wrapping, not just caret as the plan's literal wording suggested, since real fixture data shows '.OBSERVE NUCLEUS' uses caret while '$NUC1' uses angle brackets -- see Deviations"
  - "read_1d's nucleus source is '.OBSERVE NUCLEUS' (normalized key '.OBSERVENUCLEUS'), not a literal '.NUCLEUS' key, since 1D JCAMP-DX files carry no dimension-list '.NUCLEUS' field (that field only exists on 2D NTUPLES files) -- verified directly against both committed 1D fixtures"
  - "frequency field populated from $SF (not $SFO1/.OBSERVE FREQUENCY), per 101-RESEARCH.md Open Question 2's recommendation, for consistency with the ppm-axis math"

patterns-established:
  - "Contract-first shared helpers: _ppm_scale/_assert_plausible_ppm_axis/_resolve_dim are pure functions with no I/O, independently unit-verifiable (as done in Task 1's automated verify script) before any reader path consumes them"

requirements-completed: ["JC-02", "JC-03"]

# Metrics
duration: 30min
completed: 2026-07-23
---

# Phase 101 Plan 03: JCAMP-DX Shared Helpers + 1D Read Path Summary

**Implemented the verified OFFSET+SF ppm-axis formula (not the naive SFO divisor) plus a fail-loud homonuclear-degeneracy guard in `readers/jcamp.py`, then built `JcampReader.read_1d` on top of it -- both 1H and 13C JCAMP-DX references now decode into `Spectrum1D` with correctly reversed, plausibility-checked ppm axes.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-07-23T15:03:00Z (approx)
- **Completed:** 2026-07-23T15:33:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 1 (created then extended: src/lucy_ng/readers/jcamp.py)

## Accomplishments
- Implemented the JC-02 crux math (`_ppm_scale`) exactly per 101-RESEARCH.md's verified `OFFSET + SF` formula, numerically confirmed to reproduce the research's worked ¹H example (`7.0506 ... -0.4469`) to <0.001 ppm
- Implemented `_assert_plausible_ppm_axis` (D-04 fail-loud safety net: plausibility bounds per nucleus + reversed-axis check)
- Implemented `_resolve_dim` with the WR-04-class degeneracy guard: resolves heteronuclear dimensions (e.g. HSQC's distinct ¹³C/¹H) by unique `$NUC1` match, and raises `ValueError` (rather than silently first-matching) when the target nucleus is ambiguous (homonuclear, e.g. COSY/NOESY `1H`/`1H`) -- deferred to Phase 103 per plan scope
- Implemented `_read_metadata` (raw-dict access via `jcampdx._readrawdic`, searching for whichever `_datatype_*` bucket is present) so the reader is not coupled to `ng.jcampdx.read()`'s incomplete 2D dispatch table
- Built `JcampReader.read_1d` on top of these helpers: both `C20H32O2_1H.dx` (nucleus `1H`, ppm max ≈7.051) and `C20H32O2_13C.dx` (nucleus `13C`, ppm range ≈[-10.14, 110.15]) now decode into valid `Spectrum1D` objects with reversed, plausibility-checked axes
- `tests/readers/test_jcamp.py::TestJcampReader1D::test_read_1d` GREEN (JC-03); `TestJcampReaderErrors` (both tests) GREEN; the two hand-oracle decoder tests remain GREEN (untouched); full suite shows **1405 passed, 8 skipped, 1 xfailed**, with the exact 3 expected RED failures remaining for Plan 04 (`test_read_2d_shape`, `test_read_2d_yfactor_scaling`, `test_read_2d_ppm_axes_match_1d_reference` -- all require `read_2d`/`_apply_yfactor`, out of this plan's scope)
- `mypy src/lucy_ng/readers/jcamp.py` clean beyond the pre-existing, project-wide "nmrglue missing library stubs" warning already accepted for `readers/bruker.py`; `ruff check` clean

## Task Commits

1. **Task 1: Module skeleton + shared helpers (metadata access, dimension mapping, ppm formula, fail-loud assertion)** - `41796a7` (feat)
2. **Task 2: read_1d path (JC-03)** - `9619476` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `src/lucy_ng/readers/jcamp.py` - New module: shared helpers (`_read_metadata`, `_strip_caret`, `_clean_nucleus_label`, `_ppm_scale`, `_assert_plausible_ppm_axis`, `_resolve_dim`) plus `JcampReader.read_1d`; imports and re-exports `_detect_experiment_type` from `readers/bruker.py` (D-10) for Plan 04's future use

## Decisions Made
- `_resolve_dim` indexes `$SF`/`$OFFSET` via `$NUC1`'s own list position rather than `.NUCLEUS`'s, since direct inspection of the real trimmed HSQC fixture showed `$NUC1 = ['<1H>', '<13C>']` (co-indexed with `$SF`/`$OFFSET`, both in "procs-then-proc2s" parse order) while `.NUCLEUS = '13C, 1H'` is in the reversed SYMBOL-declared "F1,F2" order -- using `.NUCLEUS`'s order to index `$SF`/`$OFFSET` would silently swap the two dimensions
- `read_1d` sources `nucleus` from `.OBSERVE NUCLEUS` (normalized key `.OBSERVENUCLEUS`), confirmed present and caret-wrapped (`^1H`/`^13C`) on both committed 1D fixtures via direct inspection; `.NUCLEUS` (the comma-joined dimension list) is a 2D-NTUPLES-only field and does not exist in 1D files
- `frequency` set from `$SF` (matching the ppm-axis math), per 101-RESEARCH.md Open Question 2's low-risk recommendation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_strip_caret` alone is insufficient for real `$NUC1` values -- they are angle-bracket-wrapped, not caret-prefixed**
- **Found during:** Task 1, while inspecting the real committed fixtures to confirm `_resolve_dim`'s intended real-world usage (in preparation for Plan 04)
- **Issue:** The plan's action text says to "strip a leading caret from JCAMP `.NUCLEUS`/`$NUC1` values" and names a single `_strip_caret` helper. Direct inspection of the real trimmed HSQC fixture's raw metadata dict showed `$NUC1 = ['<1H>', '<13C>']` (Bruker angle-bracket convention, matching `readers/bruker.py::_strip_brackets`) -- NOT caret-prefixed. Only `.OBSERVE NUCLEUS` (a different key, used by 1D files) is caret-prefixed (`^1H`). A `_resolve_dim` that only strips carets would silently fail to match any real 2D `$NUC1` entry (raising a "nucleus not found" `ValueError` on every real 2D file), since Plan 04 depends on this shared helper being correct for real data, not just the plan's own synthetic caret-formatted test dict.
- **Fix:** Kept `_strip_caret` exactly as specified (strips a leading caret only) but added a second helper, `_clean_nucleus_label`, that strips a leading caret AND surrounding angle brackets, and used it inside `_resolve_dim` for matching `$NUC1` entries. This keeps the plan's literal synthetic verify-script passing (its caret-formatted `$NUC1` test values still match) while making the shared helper correct for the real angle-bracket-wrapped `$NUC1` values Plan 04's `read_2d` will actually pass in.
- **Files modified:** `src/lucy_ng/readers/jcamp.py`
- **Verification:** Task 1's automated verify script (heteronuclear + homonuclear synthetic cases) still passes unchanged; additionally confirmed by direct inspection that `_clean_nucleus_label('<1H>') == '1H'` and `_clean_nucleus_label('^1H') == '1H'`
- **Committed in:** `41796a7` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug-class robustness fix, verified against real fixture data not covered by the plan's own synthetic test)
**Impact on plan:** No scope creep -- this strengthens the exact shared contract the plan states Plan 04 will consume, using real data inspected during this plan's own execution rather than deferring the discovery to Plan 04.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 04 (`read_2d`) has a stable, already-verified foundation: `_read_metadata`, `_ppm_scale`, `_assert_plausible_ppm_axis`, and `_resolve_dim` (including its degeneracy guard and its `$NUC1`-based, angle-bracket-and-caret-robust indexing) are ready to consume as-is.
- The three remaining RED tests in `tests/readers/test_jcamp.py` (`test_read_2d_shape`, `test_read_2d_yfactor_scaling`, `test_read_2d_ppm_axes_match_1d_reference`) are Plan 04's exact target; `_apply_yfactor` still needs to be implemented (Pitfall 2 -- Y-FACTOR scaling of decoded row intensities).
- `_detect_experiment_type` is already imported and re-exported from `readers/bruker.py` (D-10) for Plan 04's direct use.
- No blockers.

---
*Phase: 101-jcamp-dx-reader*
*Completed: 2026-07-23*

## Self-Check: PASSED

`src/lucy_ng/readers/jcamp.py` and `.planning/phases/101-jcamp-dx-reader/101-03-SUMMARY.md` verified present on disk; commits `41796a7` and `9619476` verified present in `git log --oneline --all`.
