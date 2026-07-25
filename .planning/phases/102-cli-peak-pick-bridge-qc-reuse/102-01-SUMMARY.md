---
phase: 102-cli-peak-pick-bridge-qc-reuse
plan: 01
subsystem: nmr-readers
tags: [jcamp-dx, nmrglue, ppm-axis, homonuclear, fixtures]

# Dependency graph
requires:
  - phase: 101-jcamp-dx-reader
    provides: JcampReader.read/read_1d/read_2d, _resolve_dim, _ppm_scale, the trimmed HSQC fixture + 1D references
provides:
  - "Trimmed committed 2D JCAMP-DX fixtures for COSY, HMBC, NOESY (16 F1 pages each), mirroring the real 6-file C20H32O2-jcamp dataset in miniature"
  - "_resolve_dim positional homonuclear fallback (procs_index=0=F2/direct, procs_index=1=F1/indirect), proven against committed ground truth"
  - "JcampReader.read_2d() now succeeds for COSY and NOESY (previously raised ValueError for any homonuclear experiment), unblocking Phase 102's CLI wiring"
affects: [102-02, 102-03, 102-04, 103-jcamp-e2e-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "build_trimmed_2d(source, dest, page_window, label) generic fixture-trim helper, parameterized over build_trimmed_hsqc/cosy/hmbc/noesy thin wrappers"
    - "_resolve_dim(inner, target_nucleus, *, procs_index=None) positional-fallback pattern -- unique nucleus match stays authoritative, procs_index is only consulted when ambiguous, no hint == fail loud unchanged"

key-files:
  created:
    - tests/fixtures/jcamp/C20H32O2_COSY_trimmed.dx
    - tests/fixtures/jcamp/C20H32O2_HMBC_trimmed.dx
    - tests/fixtures/jcamp/C20H32O2_NOESY_trimmed.dx
  modified:
    - tests/fixtures/jcamp/_generate_fixture.py
    - src/lucy_ng/readers/jcamp.py
    - tests/readers/test_jcamp.py

key-decisions:
  - "Page windows chosen per-experiment: COSY slice(1512,1528) (F1 ppm 1.5122..1.4572, diagonal peak at F1=1.4792/F2=1.4796), HMBC slice(840,856) (page 848, F1~36.4 ppm 13C), NOESY slice(824,840) (pages 824/832, F1~0.96 ppm 1H) -- each independently probed against the real external dataset, not reused from HSQC's own window."
  - "The homonuclear positional convention (index 0=F2/direct, index 1=F1/indirect) is proven on the HETEROnuclear HSQC fixture (where nucleus matching independently disambiguates), not on COSY/NOESY data itself -- the 0.000938 ppm homonuclear $OFFSET delta (7.050608 vs 7.051546 ppm, ~0.47 Hz) is numerically indistinguishable and could not itself discriminate a swapped axis."

requirements-completed: [JCLI-01]

# Metrics
duration: 22min
completed: 2026-07-25
---

# Phase 102 Plan 01: Fixture Generator Parameterization + Homonuclear `_resolve_dim` Fix Summary

**Extended the JCAMP fixture generator to commit trimmed COSY/HMBC/NOESY fixtures, then fixed a real, verified `_resolve_dim` defect that raised `ValueError` for every homonuclear 2D experiment (blocking COSY, a required Phase-102 experiment) with a positional fallback proven on the heteronuclear HSQC fixture.**

## Performance

- **Duration:** 22 min (11:45:37 to 11:57:13 CEST between the two task commits; plan read + verification either side)
- **Started:** 2026-07-25T09:38:00Z (approx, first Read call)
- **Completed:** 2026-07-25T09:57:39Z
- **Tasks:** 2 completed
- **Files modified:** 4 (1 new fixture-gen edit, 3 new committed `.dx` fixtures) + 2 (reader fix + test extension)

## Accomplishments

- `JcampReader.read_2d()` now succeeds for COSY and NOESY (previously raised `ValueError: Ambiguous nucleus '1H' appears 2 times ...` for both) -- unblocking Phase 102's own success criterion 1, which explicitly requires COSY output.
- The homonuclear positional convention is **proven**, not assumed: `test_heteronuclear_positional_convention_holds` shows `_resolve_dim(inner, "1H", procs_index=0)` and `_resolve_dim(inner, "13C", procs_index=1)` reproduce the HSQC fixture's own unique-nucleus-match values exactly ((7.050608, 499.92) and (174.9902, 125.704983984) respectively) -- data where the answer is independently knowable, not merely assumed by analogy.
- Three new trimmed 2D fixtures committed (COSY, HMBC, NOESY, 16 F1 pages each), extending the existing HSQC-only fixture set to mirror the real 6-file `C20H32O2-jcamp` dataset in miniature. Regenerating leaves the pre-existing HSQC fixture byte-identical.
- COSY axis correctness cross-checked twice against committed ground truth: internal diagonal self-consistency (measured F1=1.4792 ppm, F2=1.4796 ppm, a real diagonal cross-peak, within 0.05 ppm) and an absolute cross-check against the committed 1D `1H` reference (both COSY axes independently match).
- The fail-loud ambiguity error is preserved as the default when no `procs_index` hint is supplied (`test_ambiguous_without_hint_still_raises`), satisfying T-102-02.

## Task Commits

Each task was committed atomically:

1. **Task 1: Parameterize the fixture generator and commit trimmed COSY/HMBC/NOESY fixtures** - `22f4758` (feat)
2. **Task 2: Positional homonuclear fallback in `_resolve_dim`, proven against committed ground truth** - `fd2bdb4` (fix)

## Files Created/Modified

- `tests/fixtures/jcamp/_generate_fixture.py` - `build_trimmed_hsqc()` refactored into generic `build_trimmed_2d(source, dest, page_window, label)`; added `COSY_PAGE_WINDOW`/`HMBC_PAGE_WINDOW`/`NOESY_PAGE_WINDOW` constants and `build_trimmed_cosy()`/`build_trimmed_hmbc()`/`build_trimmed_noesy()` wrappers, all called from `main()`.
- `tests/fixtures/jcamp/C20H32O2_COSY_trimmed.dx` - New committed fixture, 16 F1 pages, contains the diagonal peak used by the new cross-check tests.
- `tests/fixtures/jcamp/C20H32O2_HMBC_trimmed.dx` - New committed fixture, 16 F1 pages (heteronuclear, unaffected by the `_resolve_dim` bug -- read successfully even before Task 2's fix).
- `tests/fixtures/jcamp/C20H32O2_NOESY_trimmed.dx` - New committed fixture, 16 F1 pages, for the D-06 unsupported-experiment-read (not pick) path.
- `src/lucy_ng/readers/jcamp.py` - `_resolve_dim` gained an optional `procs_index: int | None = None` keyword; the ambiguous-match branch now resolves positionally when a hint is supplied instead of always raising; `read_2d()`'s two call sites pass `procs_index=0` (F2/`f2_nucleus`) and `procs_index=1` (F1/`f1_nucleus`).
- `tests/readers/test_jcamp.py` - New `TestJcampReaderHomonuclear` class (6 tests): convention proof, COSY read-without-raising, diagonal self-consistency, 1D-reference cross-check, NOESY read, and the no-hint-still-raises negative test.

## Decisions Made

- **Page windows are experiment-specific, independently verified.** The plan's `<interfaces>` block already supplied the exact windows (COSY `slice(1512,1528)`, HMBC `slice(840,856)`, NOESY `slice(824,840)`) from prior real-data probing; these were used as specified rather than re-derived, since re-deriving them would have required re-probing the (large, external, uncommitted) real files again for no benefit.
- **The homonuclear ordering itself is honestly documented as unprovable from COSY data alone.** Per the plan's explicit critical-context warning, no test claims to derive "index 0 = F2" from COSY/NOESY data -- the two real `$OFFSET` values there differ by only 0.000938 ppm (~0.47 Hz), well below any ppm cross-check's resolution. The load-bearing proof is `test_heteronuclear_positional_convention_holds` on the HSQC fixture; the COSY tests only confirm the *result* is self-consistent and matches ground truth, not that the convention itself is independently derivable from homonuclear data.
- **`_resolve_dim`'s unique-match path is never overridden by `procs_index`.** Even when a `procs_index` hint is passed, it is only consulted inside the `len(matches) > 1` branch -- this keeps the heteronuclear (HSQC/HMBC) path's existing, already-correct behavior completely unchanged.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' acceptance criteria were met verbatim: `build_trimmed_2d`/window constants/wrapper functions exist as specified; the three fixture files are tracked with 16 `##PAGE=` blocks each; the HSQC fixture regenerates byte-identical; the HMBC fixture reads successfully with the exact shape/experiment_type asserted; the commit message documents the observed pre-fix `ValueError` behavior on COSY/NOESY; `procs_index` appears in the signature and at both call sites with the exact 0/1 assignment specified; `"deferred to Phase 103"` no longer appears anywhere in the file; the new test class is collected with 6 new tests (exceeding the "at least 6" bar); the docstring documents the 0.000938 ppm homonuclear `$OFFSET` delta explicitly as an honest limitation.

One process note worth recording (not a plan deviation, an environment hazard for any future worktree-isolated executor on this repo): this worktree's global `lucy-ng` editable pip install (and a system `.pth` file) resolve to the **main repo checkout**, not the worktree, so bare `python`/`pytest`/`mypy` invocations silently import/analyze the wrong tree unless `PYTHONPATH` is explicitly prepended with the worktree's own `src/` directory. All verification commands in this plan were re-run with that explicit `PYTHONPATH` override once this was discovered; the very first `python -c` sanity check (before the override was found) transparently showed stale/wrong (pre-fix) behavior, which is what surfaced the issue.

## Issues Encountered

- **mypy/ruff baseline is not currently zero-error on this repo, unrelated to this plan.** `mypy src/lucy_ng` reports 119 pre-existing errors across 34 files (lsd/, prediction/, dereplication/, cli/lsd.py, cli/database.py, etc. -- untyped RDKit calls, missing nmrglue/requests/jsonschema stubs, generic-dict-without-type-args, and a few real logic-typing mismatches). `ruff check src tests` reports 282 pre-existing errors, similarly scattered across unrelated files. Both counts were diffed line-for-line against an unmodified checkout of the main repo (same commit before this plan's changes) and found **identical** (mypy) / **identical count** (ruff) -- confirming these are pre-existing, out-of-scope conditions per the SCOPE BOUNDARY rule, not regressions introduced by this plan. `mypy src/lucy_ng/readers/jcamp.py` and `ruff check src/lucy_ng/readers/jcamp.py tests/readers/test_jcamp.py tests/fixtures/jcamp/_generate_fixture.py` (the files this plan touches) are both fully clean. This is logged here rather than fixed, since fixing 119/282 pre-existing errors across dozens of unrelated files is out of this plan's scope.
- **Full-suite skip-count delta vs the 1408-passed/8-skipped baseline is environmental, not a regression.** This worktree checkout: `1407 passed, 15 skipped, 1 xfailed, 0 failures`. The 7 additional skips (dereplication/database tests needing the ~2.8 GB reference SQLite DB or NMRShiftDB/COCONUT source files, which are not present in this fresh worktree) plus a net -1 in "passed" (6 new jcamp tests added, offset by those 7 newly-skipped tests) account for the full delta. Zero test failures, zero errors, in either count.

## Proof-Level Honesty (per 102-RESEARCH.md Pitfall 6 / this plan's `<verification>` section)

Everything claimed above is proven on **committed, real (trimmed) fixture data** -- 16 F1 rows per 2D file. This is sufficient to prove the reader/`_resolve_dim` fix is structurally and axially correct at the schema/ppm level. It does **not** prove peak-count plausibility or noise-statistic behavior on the full real 2048x2048 matrices (that generalization belongs to Phase 103 / JVAL, per D-05's phase boundary -- explicitly out of scope here).

## Next Phase Readiness

- `JcampReader.read_2d()` now succeeds for HSQC, HMBC, COSY, and NOESY -- the reader-level blocker for Phase 102's CLI wiring (bridge_peak_pick over HSQC/HMBC/COSY, D-06 read-but-skip-pick for NOESY) is fully resolved.
- Three new trimmed fixtures are committed and available for 102-02/102-03/102-04's CLI integration tests (directory-mode discovery, D-06 skip-path testing, byte-unchanged guard test fixtures) -- no further fixture generation work should be needed for those plans.
- No blockers for 102-02.

## Self-Check: PASSED
