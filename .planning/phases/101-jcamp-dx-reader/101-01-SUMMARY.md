---
phase: 101-jcamp-dx-reader
plan: 01
subsystem: testing
tags: [jcamp-dx, nmrglue, pytest, fixtures, ntuples, difdup, red-tests]

# Dependency graph
requires: []
provides:
  - "Committed real CI fixture: tests/fixtures/jcamp/C20H32O2_HSQC_trimmed.dx (16 real F1 pages, pruned header, 152 KB) + whole 1D 1H/13C references"
  - "Reproducible fixture generator tests/fixtures/jcamp/_generate_fixture.py (re-runnable against the external source dataset)"
  - "RED test scaffolding: tests/readers/test_jcampdx_decode.py (D-08 layer 1, hand-oracle, no nmrglue dependency) + tests/readers/test_jcamp.py (D-08 layer 2, integration on the real fixture)"
  - "Structural proof that COSY/NOESY (homonuclear) 2D files decode with the same NTUPLES/PAGE/DATATABLE structure as HSQC (RESEARCH.md Open Question 1 resolved)"
affects: [101-02, 101-03, 101-04, 102-jcamp-cli-bridge]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave-0 RED scaffolding: fixtures + failing tests committed before any reader implementation exists, per D-08's two-layer independent-oracle strategy"
    - "Import-inside-test-body (WV-08) so pytest collection succeeds while lucy_ng.readers.jcamp / _jcampdx_decode remain unimplemented"

key-files:
  created:
    - tests/fixtures/jcamp/_generate_fixture.py
    - tests/fixtures/jcamp/C20H32O2_HSQC_trimmed.dx
    - tests/fixtures/jcamp/C20H32O2_1H.dx
    - tests/fixtures/jcamp/C20H32O2_13C.dx
    - tests/readers/__init__.py
    - tests/readers/test_jcampdx_decode.py
    - tests/readers/test_jcamp.py
  modified: []

key-decisions:
  - "Header pruning matched literal key prefixes as they appear in the real Bruker JCAMP-DX export (##TITLE=, ##$SF=, ##.PULSE SEQUENCE=, etc.) rather than nmrglue's normalized _getkey() form, keeping the generator simple and deterministic"
  - "F1 page window fixed at [1735:1751] (16 pages) per RESEARCH.md's verified oracle coordinates -- contains 2 of the 3 known real gem-dimethyl/methyl cross-peaks"
  - "test_jcamp.py's Y-FACTOR scaling test (Pitfall 2) targets a reader-level helper (_apply_yfactor) directly with a synthetic Y_FACTOR=2.5, since the real fixture's own Y_FACTOR happens to be 1 and would not catch a missing multiplication"
  - "test_jcamp.py's ppm-axis-assertion test targets a reader-level helper (_assert_plausible_ppm_axis) directly, matching RESEARCH.md's ready-to-implement fail-loud function"

patterns-established:
  - "Vendored-decoder hand-oracle test pattern: expected integers derived independently from the JCAMP-DX pseudo-digit spec by hand-tracing the actual nmrglue _parse_pseudo/_finish_value/_append_value algorithm, then cross-checked once against the reference decoder during authoring (never imported by the committed test itself)"

requirements-completed: []  # JC-01..04 land fully only once Plans 02-04 turn these RED tests GREEN; this plan ships fixtures + scaffolding only.

# Metrics
duration: 20min
completed: 2026-07-23
---

# Phase 101 Plan 01: JCAMP-DX Reader Wave-0 Scaffolding Summary

**Committed a real, trimmed 2D HSQC JCAMP-DX fixture (16 genuine DIFDUP pages with verified gem-dimethyl cross-peaks) plus two RED test modules that every downstream reader-implementation plan must turn GREEN — the correctness oracle is real data, not a mock.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-23T12:44:40Z
- **Completed:** 2026-07-23T12:57:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 7 created (0 modified)

## Accomplishments
- Trimmed real 2D HSQC fixture (152 KB, 16 F1 pages, pruned header, `VAR_DIM` updated, parseable by nmrglue's `_readrawdic`) committed alongside whole copies of the two real 1D `.dx` references needed for the JC-02 cross-check
- Reproducible generator script that prunes the real source header to only the ~17 keys the reader will consume, and that runs a COSY/NOESY one-page structural spot-check as part of its own execution
- COSY/NOESY spot-check confirmed both homonuclear 2D files decode via nmrglue's own `_parse_data` with the same NTUPLES/PAGE/DATATABLE structure as the heteronuclear HSQC file, resolving RESEARCH.md's Open Question 1 before Plan 04 commits to a single 2D code path
- Two RED test modules (9 tests total) that collect cleanly under pytest while failing individually (`ModuleNotFoundError`) since `lucy_ng.readers.jcamp` / `_jcampdx_decode` do not exist yet — the exact Wave-0 target Plans 02-04 must satisfy
- Hand-oracle unit test proven independent of nmrglue (`grep -q "import nmrglue" tests/readers/test_jcampdx_decode.py` exits non-zero) — a vendoring bug in Plan 02 will be caught even if nmrglue itself is absent or broken

## Task Commits

1. **Task 1: Build and commit the trimmed HSQC fixture + 1D references + COSY/NOESY spot-check** - `c852715` (feat)
2. **Task 2: Author the RED test scaffolding (hand-oracle unit test + integration test)** - `59ade7d` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `tests/fixtures/jcamp/_generate_fixture.py` - Reproducible generator: prunes the real source HSQC header, trims to F1 page window [1735:1751], updates VAR_DIM, copies the 1D references, and runs the COSY/NOESY spot-check (prints `COSY/NOESY SPOTCHECK PASS`)
- `tests/fixtures/jcamp/C20H32O2_HSQC_trimmed.dx` - Trimmed real 2D HSQC fixture, 152 KB, 16 pages
- `tests/fixtures/jcamp/C20H32O2_1H.dx` - Real 1D 1H reference (whole copy)
- `tests/fixtures/jcamp/C20H32O2_13C.dx` - Real 1D 13C reference (whole copy)
- `tests/readers/__init__.py` - Empty package marker
- `tests/readers/test_jcampdx_decode.py` - D-08 layer-1 hand-oracle unit tests (2 tests, no nmrglue dependency)
- `tests/readers/test_jcamp.py` - D-08 layer-2 integration tests (7 tests: 2D shape/ppm-assertion/yfactor, ppm cross-check, 1D read, error handling)

## Decisions Made
- Header-pruning implemented via literal key-prefix matching against the real file's actual `##KEY=` text (not nmrglue's normalized key form) — simpler, deterministic, and verified directly against the real source file's line structure
- `VAR_DIM`'s F1 entry updated from 2048 to 16 in the trimmed fixture so a future `len(PAGE) == VAR_DIM[F1]` consistency assertion holds
- Placed the Pitfall-2 Y-FACTOR scaling test and the D-04 ppm-axis-assertion test in `test_jcamp.py` (not `test_jcampdx_decode.py`), targeting reader-level helpers (`_apply_yfactor`, `_assert_plausible_ppm_axis`) per RESEARCH.md's own recommended function names — gives Plans 03/04 a concrete, unambiguous implementation target

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's Task 1 acceptance-criteria verify command references a nonexistent dict key**
- **Found during:** Task 1 verification
- **Issue:** The plan's literal verify command reads `inner['VAR_DIM'][0]`, but nmrglue's `_readrawdic`/`_getkey` normalizes JCAMP keys by stripping underscores/spaces/dashes, so the actual dict key is `VARDIM`, not `VAR_DIM`. Running the plan's exact one-liner raises `KeyError: 'VAR_DIM'`.
- **Fix:** Verified the same substantive claim (16 pages, VAR_DIM's F1 entry updated to 16) using the correct key name `inner['VARDIM'][0]`; confirmed output `pages 16 vardim 16, 2048, 2048`. No production/fixture code changed — this was purely a typo in the plan's own inspection command, not a defect in the fixture or generator.
- **Files modified:** None (verification-only correction)
- **Verification:** `python -c "...; print('pages', len(inner['PAGE']), 'vardim', inner['VARDIM'][0])"` → `pages 16 vardim 16, 2048, 2048`
- **Committed in:** N/A (no code change; documented here for the record)

---

**Total deviations:** 1 auto-fixed (1 bug, in a verification command only)
**Impact on plan:** None on shipped artifacts. The fixture and generator are correct as committed; only my own ad-hoc verification command needed the corrected key name.

## Issues Encountered
- None beyond the deviation above.

## User Setup Required
None - no external service configuration required. The generator script depends on the external `C20H32O2-jcamp` source dataset at `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/` only for regeneration; the committed fixture files under `tests/fixtures/jcamp/` are self-contained and require no external data to run the test suite.

## Next Phase Readiness
- Plan 02 (vendor the DIFDUP/SQZ/DUP/PAC decoder into `readers/_jcampdx_decode.py`) has a concrete, hand-verified RED target: `tests/readers/test_jcampdx_decode.py::test_hand_authored_mini_vector` and `test_hand_authored_dif_dup_heavy_line`.
- Plans 03/04 (`readers/jcamp.py` — `JcampReader.read_1d`/`read_2d`, `_assert_plausible_ppm_axis`, `_apply_yfactor`) have concrete RED targets in `tests/readers/test_jcamp.py`, including the JC-02 load-bearing ppm cross-check against the committed 1D references.
- No blockers. The committed fixture is self-contained (no external binary, no external data needed to run `pytest tests/readers/`).

---
*Phase: 101-jcamp-dx-reader*
*Completed: 2026-07-23*

## Self-Check: PASSED

All 7 created files verified present on disk; all 3 task/plan commits (`c852715`, `59ade7d`, `9e76f2c`) verified present in git log.
