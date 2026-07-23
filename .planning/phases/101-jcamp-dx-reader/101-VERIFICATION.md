---
phase: 101-jcamp-dx-reader
verified: 2026-07-23T16:45:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 101: JCAMP-DX Reader Verification Report

**Phase Goal:** Lucy-ng can decode both 1D and 2D JCAMP-DX spectra — including the DIFDUP-compressed NTUPLES pages nmrglue itself cannot assemble — into the existing Spectrum1D/Spectrum2D models, with no external binary and with ppm axes proven correct rather than assumed.
**Verified:** 2026-07-23T16:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A 2D JCAMP NTUPLES file decodes into a full `(n_f1, n_f2)` matrix loaded into `Spectrum2D`, with DIFDUP pages assembled by lucy-ng's own layer (closing nmrglue's `None` gap) | ✓ VERIFIED | `JcampReader.read_2d` in `src/lucy_ng/readers/jcamp.py:355-520` assembles pages via `parse_data` (own vendored decoder, `_jcampdx_decode.py`), never calls `nmrglue`'s public 2D data API. `pytest tests/readers/test_jcamp.py::TestJcampReader2D::test_read_2d_shape` PASSES; live run confirms `data.shape == (16, 2048)` on the committed real fixture. |
| 2 | `Spectrum2D` ppm axes are reversed + correct on both dims, derived from NTUPLES metadata AND cross-checked against the trusted 1D reference (not eyeballed) | ✓ VERIFIED | `_ppm_scale` uses the verified `OFFSET_ppm - (FIRST_hz - hz[i])/SF` formula (jcamp.py:110-137), not the naive `Hz/SFO` divisor. `_assert_plausible_ppm_axis` gates both axes (reversed + bounds, D-04). The load-bearing cross-check `test_read_2d_ppm_axes_match_1d_reference` (tests/readers/test_jcamp.py:68-95) projects the 2D peak onto both axes and matches the real 1D ¹H/¹³C reference peaks within tolerance (¹H ≤0.05, ¹³C ≤0.10 ppm) — PASSES live. SUMMARY-101-04 documents a real bug this exact cross-check caught and fixed (F1-anchor re-basing for the trimmed-window `$OFFSET`), proving the check is load-bearing, not decorative. |
| 3 | A 1D JCAMP file decodes through the same reader module into `Spectrum1D` | ✓ VERIFIED | `JcampReader.read_1d` (jcamp.py:278-353) in the same module as `read_2d`. `pytest tests/readers/test_jcamp.py::TestJcampReader1D::test_read_1d` PASSES — ¹H → nucleus `"1H"`, ¹³C → nucleus `"13C"`, live-verified on both committed real fixtures. |
| 4 | A committed, CI-runnable test decodes a small real fixture via the vendored decoder with NO external binary and NO nmrglue-private-API dependency — passes in CI | ✓ VERIFIED | `tests/fixtures/jcamp/C20H32O2_HSQC_trimmed.dx` (156 KB, real Bruker HSQC data, 16 genuine DIFDUP pages, verified header content) committed. `tests/readers/test_jcampdx_decode.py` hand-oracle tests decode via the vendored `parse_data` and assert against hand-computed integers — AST-parse of `_jcampdx_decode.py` confirms its only imports are `re`, `typing.Any`, `warnings.warn`, `numpy`, `numpy.typing.NDArray` (zero nmrglue import; the two textual "nmrglue" hits are attribution-comment prose, not import statements). Both tests PASS with no external binary, no network. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/fixtures/jcamp/C20H32O2_HSQC_trimmed.dx` | Real, trimmed 2D HSQC NTUPLES fixture, <200 KB, 16 pages | ✓ VERIFIED | 156 KB on disk; header inspected directly — real Bruker HSQC metadata (`##.PULSE SEQUENCE= hsqcedetgpsp.3`, `##VAR_DIM= 16, 2048, 2048`, real `$OFFSET`/`$SF` values); not synthetic/mocked. |
| `tests/fixtures/jcamp/C20H32O2_1H.dx`, `C20H32O2_13C.dx` | Real 1D references for JC-02 cross-check / JC-03 | ✓ VERIFIED | 692 KB / 2.7 MB on disk, whole real files, committed. |
| `tests/readers/test_jcampdx_decode.py` | D-08 layer-1 hand-oracle unit test, no nmrglue dependency | ✓ VERIFIED | 2 tests, both PASS; AST-confirmed zero nmrglue import. |
| `tests/readers/test_jcamp.py` | D-08 layer-2 integration tests | ✓ VERIFIED | 7 tests (2D shape/ppm-assertion/yfactor, ppm cross-check, 1D read ×1 covering both nuclei, error handling ×2), all PASS. |
| `src/lucy_ng/readers/_jcampdx_decode.py` | Vendored DIFDUP/SQZ/DUP/PAC decoder, `parse_data`, ≥200 lines, New-BSD attribution | ✓ VERIFIED | 323 lines; `parse_data` present; full 4-clause New-BSD license + "Jonathan J. Helmus" verbatim in docstring; zero actual nmrglue import (AST-confirmed). |
| `src/lucy_ng/readers/jcamp.py` | `JcampReader` module: helpers + `read_1d`/`read_2d`/`read` | ✓ VERIFIED | 557 lines; contains `def read_1d`, `def read_2d`, `def read`; all shared helpers (`_read_metadata`, `_strip_caret`, `_clean_nucleus_label`, `_ppm_scale`, `_assert_plausible_ppm_axis`, `_resolve_dim`, `_apply_yfactor`, `_page_hz`) present and exercised by passing tests. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/readers/test_jcampdx_decode.py` | `lucy_ng.readers._jcampdx_decode` | `from ... import parse_data` inside test body | ✓ WIRED | Import present, tests pass. |
| `tests/readers/test_jcamp.py` | `lucy_ng.readers.jcamp` | `from ... import JcampReader` inside test body | ✓ WIRED | Import present, tests pass. |
| `jcamp.py::read_2d` | `_jcampdx_decode.parse_data` | per-page DIFDUP decode | ✓ WIRED | `jcamp.py:427` calls `parse_data(str(table))` inside the page-assembly loop; live-verified with real fixture data producing correct `(16, 2048)` matrix. |
| `jcamp.py::read_2d` | `_detect_experiment_type` (bruker.py) | `.PULSE SEQUENCE` → `experiment_type` | ✓ WIRED | `jcamp.py:39` imports it, `jcamp.py:500` calls it; live-verified `experiment_type == "HSQC"`. |
| `jcamp.py::read_2d` F2 axis | 1D ¹H reference peaks | cross-check test | ✓ WIRED | `test_read_2d_ppm_axes_match_1d_reference` PASSES with real tolerance assertions, not stubbed. |
| `jcamp.py::_ppm_scale` | OFFSET+SF formula | linspace | ✓ WIRED | Formula body (`np.linspace(offset_ppm, offset_ppm - sw_hz/sf, n, ...)`) matches RESEARCH's verified Pattern-2 formula exactly; numerically reproduces the RESEARCH worked example to <0.001 ppm (per SUMMARY-03, independently confirmed by the cross-check test passing). |
| `jcamp.py::_resolve_dim` | homonuclear degeneracy guard | `len(matches) > 1` → raise | ✓ WIRED | jcamp.py:219-225 raises `ValueError` naming the ambiguous nucleus and deferring to Phase 103; code present and readable, matches must-have wording exactly. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase-101 test suite green | `pytest tests/readers/test_jcamp.py tests/readers/test_jcampdx_decode.py -v` | 9/9 PASSED | ✓ PASS |
| No nmrglue import in vendored decoder | AST parse of `_jcampdx_decode.py` imports | Only `re`, `typing.Any`, `warnings.warn`, `numpy`, `numpy.typing.NDArray` | ✓ PASS |
| `mypy`/`ruff` clean on phase files | `mypy`/`ruff check` on `jcamp.py` + `_jcampdx_decode.py` | ruff: all checks passed; mypy: only the pre-existing, project-wide "nmrglue missing library stubs" note (same as `bruker.py`), zero new type errors attributable to phase code | ✓ PASS |
| COSY/NOESY spot-check (Open Question 1) still reproducible | `python tests/fixtures/jcamp/_generate_fixture.py` | Prints `COSY/NOESY SPOTCHECK PASS`, exit 0 | ✓ PASS |
| Full project suite regression-free | `pytest -q` (full suite) | 1408 passed, 8 skipped, 1 xfailed, 427s | ✓ PASS |
| No lingering RED / anti-pattern markers in phase files | `grep -iE "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER\|not yet implemented"` on `jcamp.py`/`_jcampdx_decode.py` | No matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| JC-01 | 101-04 (also declared 101-01 scaffolding) | 2D NTUPLES → `Spectrum2D`, no external binary | ✓ SATISFIED | `read_2d` implemented, tested, shape `(16, 2048)` confirmed live. REQUIREMENTS.md marks Complete. |
| JC-02 | 101-03 (formula) + 101-04 (cross-check) | Reversed, correct, cross-checked ppm axes | ✓ SATISFIED | `_ppm_scale`/`_assert_plausible_ppm_axis`/`_resolve_dim` + load-bearing cross-check test all pass live. REQUIREMENTS.md marks Complete. |
| JC-03 | 101-03 | 1D → `Spectrum1D` via same reader module | ✓ SATISFIED | `read_1d` implemented in `jcamp.py`, both nuclei tested live. REQUIREMENTS.md marks Complete. |
| JC-04 | 101-02 | Vendored decoder, no nmrglue private-API dependency, CI-runnable oracle test | ✓ SATISFIED | `_jcampdx_decode.py` vendored, AST-confirmed zero nmrglue import, hand-oracle tests pass live with no external binary. REQUIREMENTS.md marks Complete. |

No orphaned requirements — REQUIREMENTS.md maps exactly JC-01..04 to Phase 101, and all four are claimed (across the 4 plans' frontmatter) and satisfied.

### Anti-Patterns Found

None. Scan of `src/lucy_ng/readers/jcamp.py` and `src/lucy_ng/readers/_jcampdx_decode.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|placeholder|coming soon|not yet implemented|not available` returned zero matches. No hardcoded empty returns, no stub handlers — every code path was exercised by a passing, non-trivial assertion (shape, nucleus, ppm-axis value, cross-check tolerance).

### Human Verification Required

None. All four ROADMAP success criteria are mechanically verifiable (shape assertions, numeric ppm tolerances, AST-confirmed import absence, live pytest runs) and were verified directly against the codebase and a live test run — no visual, UX, or external-service-dependent behavior is in scope for this phase.

### Gaps Summary

No gaps. All four ROADMAP success criteria are independently verified against the actual codebase (not SUMMARY claims): the vendored decoder has zero nmrglue import, the 2D page-assembly path produces the correct shape from real DIFDUP data, both ppm axes use the verified formula and are cross-checked against real 1D references (with a genuine bug — the trimmed-fixture F1 anchor — caught and fixed by that exact cross-check, per 101-04-SUMMARY's Deviations section), and the 1D path shares the same reader module. Full project test suite (1408 passed / 8 skipped / 1 xfailed) shows zero regressions, and all 8 skips + 1 xfail are pre-existing external-tool/network conditions unrelated to Phase 101.

---

*Verified: 2026-07-23T16:45:00Z*
*Verifier: Claude (gsd-verifier)*
