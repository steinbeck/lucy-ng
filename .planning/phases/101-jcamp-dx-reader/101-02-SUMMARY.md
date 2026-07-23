---
phase: 101-jcamp-dx-reader
plan: 02
subsystem: readers
tags: [jcamp-dx, nmrglue, difdup, decoder, vendoring, mypy-strict]

# Dependency graph
requires: ["101-01"]
provides:
  - "Self-contained DIFDUP/SQZ/DUP/PAC decoder: src/lucy_ng/readers/_jcampdx_decode.py::parse_data(datastring) -> (NDArray[float64], 'R'|'I') | None"
  - "JC-04 GREEN: tests/readers/test_jcampdx_decode.py (both hand-oracle tests) now pass, independent of nmrglue"
affects: ["101-03", "101-04", "102-jcamp-cli-bridge"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vendoring-with-typing pattern: copy an external New-BSD algorithm's logic byte-identical, then add type annotations (function signatures, NDArray[np.float64] returns, targeted `# type: ignore[code]`/`assert`) as a typing-only layer so the project's mypy --strict gate passes without altering runtime behavior"

key-files:
  created:
    - src/lucy_ng/readers/_jcampdx_decode.py
  modified: []

key-decisions:
  - "Renamed the vendored entry point from _parse_data to public parse_data (Claude's Discretion per PATTERNS.md), since both the reader (Plan 03/04) and the Wave-0 hand-oracle test import it as a public symbol"
  - "Added type annotations + numpy typing (function signatures, NDArray[np.float64], a couple of targeted `assert`/`# type: ignore[index]` on lines where mypy cannot statically prove non-None state that the vendored algorithm guarantees at runtime) to satisfy CLAUDE.md's mypy --strict requirement -- this is the one deviation from a purely byte-identical copy, and it changes zero decode behavior (verified by the unchanged hand-oracle test results)"
  - "Added stacklevel=2 to all 5 vendored warn() calls to satisfy ruff's B028 (flake8-bugbear) rule -- cosmetic-only (affects where the warning appears to originate), no behavior change"

patterns-established:
  - "Vendored-decoder hand-oracle test pattern (established by Plan 01, now proven GREEN against a real vendored copy, not against nmrglue itself)"

requirements-completed: ["JC-04"]

# Metrics
duration: 25min
completed: 2026-07-23
---

# Phase 101 Plan 02: Vendor JCAMP-DX DIFDUP/SQZ/DUP/PAC Decoder Summary

**Vendored nmrglue's 9-object DIFDUP/SQZ/DUP/PAC decoder dependency closure into `src/lucy_ng/readers/_jcampdx_decode.py` with full New-BSD attribution, zero nmrglue import, and mypy-strict/ruff-clean type annotations added as a non-behavioral layer -- the Wave-0 hand-oracle test now passes independently of nmrglue.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-23T14:20:00Z (approx)
- **Completed:** 2026-07-23T14:45:00Z (approx)
- **Tasks:** 1/1 completed
- **Files modified:** 1 created (0 modified)

## Accomplishments
- Vendored the full 9-object dependency closure of nmrglue's `_parse_data` (`_DIGITS`, `_SQZ_DIGITS`, `_DIF_DIGITS`, `_DUP_DIGITS`, `_detect_format`, `_parse_affn_pac`, `_append_value`, `_finish_value`, `_parse_pseudo`, entry point renamed `_parse_data` -> `parse_data`) into a new self-contained module, with the full 4-clause New-BSD license text (Jonathan J. Helmus, 2010-2015) reproduced verbatim in the module docstring plus a one-line provenance note
- Confirmed zero `import nmrglue`/`from nmrglue import ...` statement anywhere in the module (verified via `grep -nE '^\s*(import|from)\s+nmrglue'`, no matches) -- satisfies JC-04's literal "without depending on nmrglue's private API"
- Both D-08 layer-1 hand-oracle tests (`test_hand_authored_mini_vector`, `test_hand_authored_dif_dup_heavy_line`) in `tests/readers/test_jcampdx_decode.py` now PASS, proving the vendored copy decodes DIF/SQZ/DUP/PAC correctly against integers hand-derived independently of nmrglue
- Added type annotations across all 6 internal functions plus the public `parse_data` entry point (return type `tuple[NDArray[np.float64], str] | None`) to satisfy the project's `mypy --strict` gate (CLAUDE.md hard requirement) -- `mypy src/lucy_ng/readers/_jcampdx_decode.py` reports zero errors for this module
- `ruff check` clean (fixed 5 `B028` "no explicit stacklevel" warnings on the vendored `warn()` calls)
- Full test suite: 1401 passed, 7 failed (pre-existing RED scaffolding in `tests/readers/test_jcamp.py` targeting `lucy_ng.readers.jcamp`, which Plans 03/04 build -- not this plan's scope), 8 skipped, 1 xfailed -- no regressions introduced by this change

## Task Commits

1. **Task 1: Vendor the 9-object decoder closure with New-BSD attribution** - `0c1a387` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `src/lucy_ng/readers/_jcampdx_decode.py` - Self-contained, mypy-strict-clean, ruff-clean vendored DIFDUP/SQZ/DUP/PAC decoder (`parse_data` entry point + its 8-object dependency closure), New-BSD license reproduced verbatim, no nmrglue import

## Decisions Made
- Renamed `_parse_data` to public `parse_data` per PATTERNS.md's "Claude's Discretion" note, since both `test_jcampdx_decode.py` (already committed in Wave 0) and the future `jcamp.py` reader import it as a public symbol
- Chose typing-only additions (function signatures, `NDArray[np.float64]` return type, two `assert`/one `# type: ignore[index]`/one `Any`-typed dual-purpose local variable) over restructuring the vendored algorithm, to satisfy `mypy --strict` while keeping the decode logic itself byte-identical to upstream -- verified non-behavioral by re-running both hand-oracle tests after every typing edit, with no change in outcome
- Added `stacklevel=2` to the vendored module's 5 `warn()` calls to satisfy ruff's `B028` bugbear rule; purely cosmetic (changes only where the warning is reported as originating from), no behavior change to the decode algorithm

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's own literal acceptance-criteria grep contradicts its own action instructions**
- **Found during:** Task 1 acceptance-criteria verification
- **Issue:** The plan's acceptance criteria requires `grep -c nmrglue src/lucy_ng/readers/_jcampdx_decode.py` to return `0`, but the plan's own action text (and 101-PATTERNS.md) explicitly requires a provenance note and full license block that names "nmrglue" (e.g. `# Vendored from nmrglue.fileio.jcampdx (0.12-dev), lines 208-453.` and "Copyright Notice and Statement for the nmrglue Project"). A module satisfying the action's own attribution requirement cannot also satisfy a literal zero-occurrence grep on the word "nmrglue".
- **Fix:** Kept the required license/provenance text (5 occurrences of the word "nmrglue", all in the module docstring/comments) and verified the *substantive* JC-04 requirement instead -- no actual `import nmrglue` / `from nmrglue import ...` statement anywhere in the file (`grep -nE '^\s*(import|from)\s+nmrglue' src/lucy_ng/readers/_jcampdx_decode.py` returns no matches). This is what JC-04 and the plan's own objective text ("without depending on nmrglue's private API") actually require.
- **Files modified:** None beyond the module itself (already covered by Task 1)
- **Verification:** `grep -c nmrglue ...` = 5 (docstring/comments only); `grep -nE '^\s*(import|from)\s+nmrglue' ...` = no matches (exit 1); both hand-oracle tests pass
- **Committed in:** `0c1a387`

**2. [Rule 2 - Missing critical functionality per CLAUDE.md] Vendored module had zero type annotations, failing the project's mypy --strict gate**
- **Found during:** Task 1, running `mypy src/lucy_ng/readers/_jcampdx_decode.py` per CLAUDE.md's `mypy src/lucy_ng # type checking (strict mode)` project command
- **Issue:** A byte-identical, unmodified copy of nmrglue's untyped-Python decoder produced ~25 mypy --strict errors in the new module alone (missing function annotations, untyped calls, a `Match[str] | None` union-attr issue, a dual-typed local variable, unindexable `None`).
- **Fix:** Added full type annotations to all function signatures and the module-level entry point, plus two `assert`/one targeted `# type: ignore[index]`/one `Any`-typed local variable at the specific spots where mypy cannot statically prove properties the vendored algorithm's own control flow already guarantees at runtime. Re-ran both hand-oracle tests after each edit to confirm zero behavior change.
- **Files modified:** `src/lucy_ng/readers/_jcampdx_decode.py`
- **Verification:** `mypy src/lucy_ng/readers/_jcampdx_decode.py` reports zero errors for this file; `ruff check` clean; both hand-oracle tests still pass; full suite shows no new failures
- **Committed in:** `0c1a387`

---

**Total deviations:** 2 auto-fixed (1 plan-bug documentation correction, 1 CLAUDE.md-driven addition)
**Impact on plan:** None on the shipped artifact's substantive correctness or JC-04 compliance. The module is self-contained, imports no nmrglue symbol, carries full license attribution, and is now also mypy-strict/ruff clean per project convention -- a stricter bar than the plan's own acceptance criteria required.

## Issues Encountered
None beyond the deviations above.

## User Setup Required
None.

## Next Phase Readiness
- Plan 03/04 (`readers/jcamp.py` -- `JcampReader.read_1d`/`read_2d`) can now `from lucy_ng.readers._jcampdx_decode import parse_data` and rely on its documented return contract: raw decoded `(NDArray[float64], "R"|"I")`, Y-FACTOR scaling NOT applied (must be done by the reader per Pitfall 2).
- The 7 still-failing tests in `tests/readers/test_jcamp.py` are the exact Wave-0 RED targets Plans 03/04 must turn GREEN (`ModuleNotFoundError: lucy_ng.readers.jcamp` -- that module does not exist yet, out of this plan's scope).
- No blockers.

---
*Phase: 101-jcamp-dx-reader*
*Completed: 2026-07-23*

## Self-Check: PASSED

`src/lucy_ng/readers/_jcampdx_decode.py` verified present on disk; commit `0c1a387` verified present in `git log --oneline`.
