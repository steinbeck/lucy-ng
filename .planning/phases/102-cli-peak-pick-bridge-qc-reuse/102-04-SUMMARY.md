---
phase: 102-cli-peak-pick-bridge-qc-reuse
plan: 04
subsystem: testing
tags: [jcamp-dx, pytest, integration-tests, qc-gate, byte-unchanged, honesty-gate]

# Dependency graph
requires:
  - phase: 102-cli-peak-pick-bridge-qc-reuse (wave 1, plan 01)
    provides: "Committed trimmed HSQC/HMBC/COSY/NOESY JCAMP fixtures + the homonuclear _resolve_dim fix"
  - phase: 102-cli-peak-pick-bridge-qc-reuse (wave 1, plan 02)
    provides: "bridge_peak_pick_1d()/peak_json_filename() 1D peak-pick bridge"
  - phase: 102-cli-peak-pick-bridge-qc-reuse (wave 2, plan 03)
    provides: "lucy jcamp CLI command (read -> pick -> QC -> write, D-07 write boundary)"
provides:
  - "Fixture-backed, un-mocked end-to-end proof that lucy jcamp works over the six committed real JCAMP fixtures (TestJcampEndToEnd)"
  - "Mechanical proof that PASS/PARTIAL/FAIL are all reachable with distinct, asserted write behaviour (TestJcampQcDiscrimination, mock-covered verdict only)"
  - "The repo's first committed byte-unchanged test for case.md + the 5-agent CASE team (tests/test_skill_files_unchanged.py)"
affects: [103-end-to-end-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CliRunner(mix_stderr=False) for any lucy jcamp test that parses --format json output -- avoids an ordering-dependent flake where nmrglue's UserWarning('$RELAX' key without value) leaks into stdout on the FIRST time that exact source line fires in a pytest session (Python's default once-per-call-site warning filter), which would otherwise only manifest when tests/test_cli_jcamp.py is run in isolation rather than as part of the full suite"
    - "_find_json() helper excludes any path containing a 'staged' path component, since the CLI's staged (verdict-less, qc_verdict=UNKNOWN) directory carries a same-named HSQC.json alongside the real consumable/quarantine one"
    - "SHA-256 golden-hash table resolved via Path(__file__).resolve().parents[1], not bare cwd-relative strings (unlike the pre-existing tests/test_case_md_wv07.py) -- verified cwd-independent by running from /tmp against the absolute test path"

key-files:
  created:
    - tests/test_skill_files_unchanged.py
  modified:
    - tests/test_cli_jcamp.py

key-decisions:
  - "CliRunner(mix_stderr=False) used throughout the new fixture-backed tests (departure from the plain CliRunner() the plan 03 surface tests use) -- discovered empirically that the default mix_stderr=True interleaves warnings.warn output into result.output, which is fine for text-format assertions but breaks json.loads(result.output) the first time a given nmrglue warning fires in a session; this is a test-robustness fix, not a production-code change."
  - "_six_checks() test helper in TestJcampQcDiscrimination takes a `failing` dict naming which of the six checks should report passed=False; every check not named there always passes -- simpler and less error-prone than parameterizing a boolean per check."
  - "test_out_override branches its own assertion on the observed verdict (FAIL vs PASS/PARTIAL) rather than assuming one, since --out's effect on quarantine-vs-consumable placement is verdict-dependent and this plan does not force a verdict in that particular test."

requirements-completed: [JCLI-01, JCLI-02]

# Metrics
duration: 55min
completed: 2026-07-25
---

# Phase 102 Plan 04: Fixture-Backed End-to-End Proof + Skill-File Freeze Summary

**Proved `lucy jcamp` actually works end-to-end on the six committed real JCAMP fixtures (observed verdict: FAIL, for an honest and explained reason), proved all three QC verdicts drive distinct write behaviour via a verdict test-double, and shipped the repo's first committed SHA-256 byte-unchanged guard for `case.md` and the 5-agent CASE team.**

## Performance

- **Duration:** ~55 min (worktree-base correction + full context read + manual pre-verification of every claim + two task commits)
- **Started:** 2026-07-25T09:41:00Z (approx, first Read call after worktree-base fix)
- **Completed:** 2026-07-25T10:41:28Z
- **Tasks:** 2 completed
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `TestJcampEndToEnd` (10 tests, FIXTURE-COVERED, zero test-doubles) proves, on the real six committed JCAMP fixtures: the D-07 write-boundary invariant holds regardless of which verdict the 16-row trimmed fixtures produce; NOESY is skipped non-fatally with a named reason and `failed` stays empty (D-06); all six fixtures read without a read failure (including the two homonuclear ones Plan 01 fixed); the edited-HSQC sign survives the round-trip (`CH2` and `CH_or_CH3` both present, zero `CH_or_CH2_or_CH3`); the QC verdict is embedded in the peak JSON with `backend == "jcamp"`; the picked 1D lists are discovered by the real, un-mocked `QcReferenceData.resolve()` as trusted reference with the inherited `classification_source == "override"` (Pitfall 4); explicit-file-list mode (D-01) and `--out` (D-02) both work; `--format json` carries exactly the seven documented top-level keys with 6 checks.
- `TestJcampQcDiscrimination` (4 tests, MOCK-COVERED verdict only, real peaks) proves PASS writes consumable peaks with `confidence: "high"`, PARTIAL writes with `confidence: "low"` and surfaces the violated check by name, FAIL quarantines and exits non-zero (mirroring `tests/nus/test_write_boundary.py`'s exact assertion shape) without ever calling `confidence_from_verdict()` for FAIL peaks, and a malformed `.dx` file forces a non-zero exit even under a forced PASS verdict (T-102-07).
- `tests/test_skill_files_unchanged.py` (8 tests): SHA-256 golden-hash freeze of `case.md` and the five `lucy-*.md` agent files, re-verified live against this worktree before writing the test (all six hashes matched the Phase-101-close baseline exactly, zero drift); a roster-completeness glob (`lucy-*.md`) catches a newly added agent file, not just a modified one; `supervisor.md`'s exclusion from the 5-agent-team guard is documented and asserted explicitly, not silent.
- Full suite: **1446 passed, 15 skipped, 1 xfailed** (1424 at Plan 03 close + 14 Task-1 tests + 8 Task-2 tests = 1446, exact arithmetic match, zero regressions). `mypy src/lucy_ng` = 119 errors, `ruff check src tests` = 282 errors -- both **identical** to the documented pre-existing baseline, zero new errors attributable to this plan's two files (both individually clean under `mypy`/`ruff`).
- `git diff --exit-code 22f2b52 -- .claude/ src/lucy_ng/nus/ src/lucy_ng/cli/pick.py src/lucy_ng/processing/peak_picker.py src/lucy_ng/processing/peak_picker_2d.py` exits 0 -- every reused/byte-protected module and the whole `.claude/` tree remain provably untouched.
- `git status --porcelain tests/fixtures/jcamp/` is empty after every test run -- the tracked fixture tree was never polluted with `analysis/`/`jcamp_ingest/` side effects.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fixture-backed end-to-end suite for `lucy jcamp`** - `074ba21` (test)
2. **Task 2: SHA-256 byte-unchanged guard for `case.md` and the 5-agent team** - `be77e2d` (test)

## Files Created/Modified

- `tests/test_cli_jcamp.py` - Extended (9 -> 23 tests) with `_copy_fixtures()`/`_find_json()` helpers, `TestJcampEndToEnd` (10 fixture-covered tests), and `TestJcampQcDiscrimination` (4 mock-covered-verdict tests).
- `tests/test_skill_files_unchanged.py` - New. `EXPECTED_SHA256` (6-file baseline table), `EXPECTED_AGENT_FILES` (5-file roster tuple), 8 tests (6 parametrized hash checks + roster-completeness + readable-file check).

## Decisions Made

- **`CliRunner(mix_stderr=False)`** for every new test that parses `--format json` output, rather than the plain `CliRunner()` the Plan-03 surface tests use. Discovered empirically while manually pre-verifying the CLI's real behaviour: nmrglue emits `UserWarning: JCAMP-DX key without value: $RELAX` via `warnings.warn` (not `click.echo`), and Python's default "once per call-site" warning filter only shows it the FIRST time that exact source line fires in a given interpreter session. With the default `mix_stderr=True`, that warning text lands in `result.output` and breaks `json.loads()` -- but only non-deterministically, depending on test ordering/isolation (confirmed live: a second invocation in the same session never re-triggers the warning). `mix_stderr=False` makes every JSON-parsing assertion robust regardless of run order. This is a test-only robustness decision, not a production-code change.
- **`_find_json()` excludes any path containing a `"staged"` component.** The CLI's staged (verdict-less) directory under `jcamp_ingest/staged/` also writes a same-named `HSQC.json` (with `qc_verdict: "UNKNOWN"`) before the QC gate runs -- without this exclusion, tests locating "the" HSQC.json anywhere under `analysis/` non-deterministically matched two files.
- **`test_out_override` branches on the observed verdict** rather than assuming FAIL or PASS/PARTIAL, since it does not force a verdict and `--out`'s effect on where consumables vs. quarantine land is verdict-dependent.
- **Every claim, per this plan's honesty mandate, is filed under its actual proof level** in code comments and docstrings: `TestJcampEndToEnd` is FIXTURE-COVERED (zero test-doubles, real committed data); `TestJcampQcDiscrimination` is explicitly labelled MOCK-COVERED for the verdict only (the peaks staged into it are still real, fixture-derived cross-peaks); nothing in either class is worded as "verified on real data" beyond what the 16-row trimmed fixtures can actually prove.

## Deviations from Plan

None — plan executed as written. Every acceptance criterion in both tasks was verified to hold exactly as literally specified:
- `pytest tests/test_cli_jcamp.py -q` collects 23 tests (9 + 14) and passes.
- `grep -c "class TestJcampEndToEnd\|class TestJcampQcDiscrimination" tests/test_cli_jcamp.py` -> `2`.
- `grep -c "monkeypatch" tests/test_cli_jcamp.py` -> `0` inside `TestJcampEndToEnd`, `9` inside `TestJcampQcDiscrimination`.
- `pytest tests/test_skill_files_unchanged.py -q` collects 8 tests and passes; `grep -c "supervisor"` -> 6; `grep -c "shasum -a 256"` -> 4.
- The skill-file test passes when invoked from `/tmp` against the absolute test path (cwd-independence verified live).
- Full suite green, `mypy`/`ruff` at the exact documented pre-existing baseline counts, both reused-module and `.claude/` drift gates exit 0.

One test-robustness adjustment was made during implementation (not a deviation from any plan instruction, since the plan did not specify a `CliRunner` construction mode): `CliRunner(mix_stderr=False)` was chosen over the plain `CliRunner()` after empirically discovering the nmrglue-warning JSON-parse flake described above under "Decisions Made". This was caught and fixed during manual pre-verification, before any test was written against the wrong assumption.

## Issues Encountered

- **Worktree base drift at agent startup (same class as every prior plan in this phase):** this worktree's HEAD was found on a stale commit (`dfac9bb`, a v9.3-milestone-archive point) rather than the expected wave-2-merged base (`11ad5ab`, "docs(phase-102): update tracking after wave 2"). Corrected via `git reset --hard 11ad5ab26da5a68a6ae2ccbbcbf464b550cef7c9` per the mandatory `<worktree_branch_check>` protocol before any file was read or written -- not a plan deviation, an agent-harness environment hazard.
- **`PYTHONPATH` shadowing (same as every prior plan's own summary in this phase):** this worktree's ambient editable install resolves to the main repo checkout by default. Every verification command in this plan was run with `PYTHONPATH="$(pwd)/src"` explicitly prepended, matching the documented convention from Plans 01-03.
- **Full-suite skip count (15, not 8):** matches the exact environmental delta already documented in every prior plan of this phase (missing ~2.8 GB reference SQLite DB / NMRShiftDB source files in this fresh worktree) -- confirmed zero test failures, zero errors, at this or any prior gate.

## Proof-Level Honesty (per 102-RESEARCH.md Pitfall 6 / this plan's `<verification>` section)

Filed exactly as the plan's `<verification>` block requires, stated verbatim here:

- **FIXTURE-COVERED on real committed data** (16 F1 rows per 2D file, whole real 1D files): file discovery, 1D/2D routing, homonuclear COSY/NOESY reading, the D-06 NOESY skip, the edited-HSQC sign round-trip, QC-gate execution and verdict embedding, 1D reference discoverability, both output formats.
- **MOCK-COVERED** (real peaks, injected verdict): the PASS and PARTIAL write branches, and the malformed-file exit rule under a forced PASS.
- **NOT PROVEN HERE**: peak-count plausibility, SNR-floor behaviour on a full 2048x2048 matrix, and any claim that the QC verdict is chemically correct. Those require the real, external, uncommitted `C20H32O2-jcamp` dataset and are Phase 103 / JVAL's job (D-05). This green suite is on 16-row trimmed fixtures and is never described as "verified on real data".

**Observed results for the committed six-fixture directory run** (this is the load-bearing, measured data this SUMMARY records, per the plan's `<output>` requirement):

- **Verdict: FAIL.** All six 2D/1D fixtures read without a read failure; NOESY skipped (D-06, non-fatal); nothing written to `analysis/nmr_peaks/`; quarantine at `analysis/jcamp_ingest/qc_failed/` holding `qc_report.json` + all five payloads.
- **Per-check results:** `quaternary_exclusion` PASSED (no HSQC correlations at the known-quaternary shifts); `ppm_calibration` FAILED ("systematic offset exceeds tolerance"); `hsqc_coverage` FAILED ("2/21 protonated carbons covered (10%)"); `signal_to_ridge` FAILED ("max ridge_fraction=0.73 at COSY.h1a_ppm"); `edited_sign_consistency` FAILED (soft, "mixed multiplicity_hint at [21.0, 21.5, 22.0, 22.5]"); `cosy_diagonal_symmetry` FAILED (soft, "1% of COSY cross-peaks have a diagonal mirror").
- **Why FAIL is the honest, expected outcome, not a defect:** the trimmed HSQC fixture covers only 16 F1 rows (~1.3 ppm of 13C) against the whole-file 1D 13C reference's 45 real picked shifts -- nowhere near the `hsqc_coverage_floor` of 0.8. Driving the REAL 2048x2048 `C20H32O2-jcamp` dataset to a green Sec.8 verdict is explicitly Phase 103 / JVAL's job (D-05), not this phase's bar.
- **Observed `classification_source`: `"override"`**, using the five compiled-in Sec.8 quaternary shifts (142.00, 135.86, 79.35, 36.23, 37.86), `trusted_c13` (45 shifts) and `trusted_h1` (265 shifts) both non-empty -- exactly the inherited `QcConfig.default()` behaviour 102-RESEARCH.md Pitfall 4 predicted, recorded here as observed fact, not a choice this phase makes.
- **Observed HSQC cross-peak count: 115**, with `multiplicity_hint` distribution `{"CH_or_CH3": 70, "CH2": 45}` and zero `"CH_or_CH2_or_CH3"` (ambiguous) entries -- the edited-HSQC sign (ROADMAP criterion 3) survives the JCAMP round-trip on real data, matching this plan's pre-recorded `<interfaces>` baseline exactly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All four Phase-102 ROADMAP success criteria are now verifiable by running a committed test suite, not by trust: criterion 1 (`lucy jcamp` end-to-end on committed fixtures) and criterion 2 (QC gate wired + discriminating) are proven by `TestJcampEndToEnd`/`TestJcampQcDiscrimination`; criterion 3 (edited-HSQC sign survives) is proven on real data; criterion 4 (`case.md` + 5-agent team byte-unchanged) is now a committed, cwd-independent SHA-256 test.
- Phase 103 / JVAL's job is precisely scoped by this plan's honesty gate: drive the real, external, uncommitted `C20H32O2-jcamp` 2048x2048 dataset to a green Sec.8 QC verdict and a convergent `/lucy-ng:case C20H32O2` run. The FAIL verdict observed here on the 16-row trimmed fixtures is expected and does not indicate any defect for Phase 103 to inherit.
- No blockers for Phase 103 from this plan's scope.

## Self-Check: PASSED

- FOUND: `tests/test_cli_jcamp.py` (23 tests collected, extended)
- FOUND: `tests/test_skill_files_unchanged.py` (8 tests collected, new)
- FOUND commit: `074ba21` (Task 1)
- FOUND commit: `be77e2d` (Task 2)

---
*Phase: 102-cli-peak-pick-bridge-qc-reuse*
*Completed: 2026-07-25*
