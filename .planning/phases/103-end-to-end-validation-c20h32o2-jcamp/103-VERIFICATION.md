---
phase: 103-end-to-end-validation-c20h32o2-jcamp
verified: 2026-07-28T00:00:00Z
status: passed
score: 9/9 must-haves verified (2 of the 9 correctly documented as not-achieved by an
  approved D-10 honest-partial-close; the 1 additional CR-01 finding from the prior
  verification pass is now confirmed fixed, tested, and regression-pinned)
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 8/9
  gaps_closed:
    - "Per-experiment picker knobs: a bare --threshold silently shadowing a keyed --snr-floor (CR-01) is now rejected fail-loud instead of silently discarded, and is pinned by a new regression test that is confirmed (by mutation) to fail if the old bug is reintroduced."
  gaps_remaining: []
  regressions: []
deferred: []
---

# Phase 103: End-to-End Validation (C20H32O2-jcamp) Verification Report

**Phase Goal:** The `C20H32O2-jcamp` dataset proves the JCAMP ingestion path is not just
mechanically correct but usable for real CASE structure elucidation.
**Verified:** 2026-07-28
**Status:** passed
**Re-verification:** Yes — after gap closure (CR-01)

## Framing (read this before the table)

This phase closed as a **deliberate, coordinator-approved honest PARTIAL** (the plan's
own D-10 branch) for JVAL-01/JVAL-02. That is not, by itself, a verification failure —
the plan's must-haves explicitly anticipate and require exactly this branch when the QC
verdict is a critical FAIL. Those PARTIAL verdicts and the JVAL-F2/JVAL-F3 tracked
follow-ups **stand unchanged from the prior verification pass** — they are not
re-litigated here, per the scope of this re-verification.

The one thing this pass re-verifies is **CR-01**, a code-review-identified precedence
defect in this phase's own Task 2 deliverable (the `--threshold`/`--snr-floor` CLI knob
wiring) that the prior verification pass flagged as unresolved, untested, and untracked.
Four commits since then (`0eaca92`, `fd40c1f`, `7351e8b`, `663416f`) claim to close it.
This pass verified those claims directly against code, git history, and live execution
— see "Gap Closure" below. The finding is now closed; overall status is `passed`.

## Gap Closure — CR-01 (verified 2026-07-28)

**Claim under test:** commits `0eaca92` (fix), `fd40c1f` (tests), `7351e8b` (docs-only),
`663416f` (docs-only, CR-02/CR-03 filing) close the CR-01 gap recorded in the prior
`103-VERIFICATION.md`.

**1. Guard fix read and exercised live.** `src/lucy_ng/cli/jcamp.py` STEP 0 (lines
230–269) now resolves the *effective* threshold/snr-floor per experiment
(`_resolved_threshold`/`_resolved_snr_floor`) before the ambiguity checks, not just the
two keyed dicts. Exercised live with `CliRunner` against a real copied fixture directory
(not a nonexistent path) for all five combinations named in scope:

| Combination | Args | Result | Judgement |
|---|---|---|---|
| bare `--threshold` + keyed `--snr-floor` | `--threshold 0.02 --snr-floor cosy=7` | exit 2, `click.BadParameter` naming COSY explicitly | ✓ now rejected, was the actual CR-01 hole |
| bare `--threshold` + bare `--snr-floor` | `--threshold 0.02 --snr-floor 5.0` | exit 2, clear message | ✓ new fail-loud guard (deliberate behavior change, see below) |
| keyed `--threshold` + bare `--snr-floor` | `--threshold hsqc=0.02 --snr-floor 5.0` | exit 1 (real dataset's unrelated QC FAIL verdict, NOT a usage error) | ✓ still legal, exactly as the original guard's message promised |
| bare `--snr-floor` alone | `--snr-floor 5.0` | exit 1 (same unrelated QC FAIL) | ✓ unchanged |
| bare `--threshold` alone | `--threshold 0.02` | exit 1 (same unrelated QC FAIL) | ✓ unchanged |

(The exit-1 outcomes above are the real `C20H32O2-jcamp` fixture set's own QC critical
FAIL verdict — `ppm_calibration`/`hsqc_coverage`/`signal_to_ridge` — identical to the one
already recorded in `103-VALIDATION.md`; they are unrelated to CR-01 and confirm no
usage-error (`exit 2`) was raised for either legal combination.)

**Judgement on the new bare+bare rejection:** rejecting bare `--threshold` + bare
`--snr-floor` is a deliberate behavior change from silent-ignore to fail-loud. This is
defensible against the plan's must-have text ("the plain `--snr-floor 5.0` form still
behaves exactly as before") because that promise is about `--snr-floor` used *alone*
(confirmed unchanged above, row 4) — not about a combination that was never legal in a
meaningful sense to begin with (the bare `--snr-floor` was always dead in that combo,
silently, before the fix; now it fails loud with a clear message instead). No regression
against the literal must-have text.

**2. Three previously-vacuous tests confirmed genuinely repaired, by mutation, not just
by reading the diff:**

- `test_keyed_form_routes_per_experiment_and_reaches_staging_and_rebuild_identically`
  (the "collapsing calls into a set" fix): reverted the FAIL-branch rebuild call site
  (the branch actually exercised by these real, always-QC-FAIL fixtures) to a stub
  payload with no `bridge_peak_pick` call. Test **failed** as expected
  (`assert 1 == 2 ... a deleted rebuild call site must fail this test`). Restored;
  `git status` clean afterward.
- The `"unrecognized key"` stdout→stderr fix: reproduced the exact prior bug live —
  under `mix_stderr=False`, a real `click.BadParameter` rejection's message lands
  entirely on `result.stderr`; `result.output` (stdout) is empty (`''`) regardless of
  whether the rejection occurred. This proves the **old** assertion
  (`"unrecognized key" not in result.output`) was unfalsifiable — it would pass whether
  or not a typo'd key was correctly rejected. The **new** assertion
  (`not in result.stderr`) is checked against the correct channel and would catch a
  regression that silently accepted an invalid key.
- `test_keyed_threshold_with_bare_snr_floor_is_legal`: now asserts `exit_code in (0, 1)`
  (excluding usage-error `2`) plus the actual resolved per-experiment knob values via the
  bridge spy, replacing the old `exception is None or isinstance(..., SystemExit)`
  tautology (true on every possible outcome). Confirmed by reading the diff and by the
  live 5-combination run above (row 3), which is exactly this scenario and correctly
  returns `exit_code == 1`, never `2`.

**3. New CR-01 regression test genuinely pins the behavior, not just exercises it.**
`test_bare_threshold_with_keyed_snr_floor_is_rejected` was run against a temporary
revert of the guard to the old keyed-vs-keyed-only comparison
(`shadowed = sorted(set(threshold_by_exp) & set(snr_by_exp))`, restoring the exact
pre-fix logic). The test **failed** against the reintroduced bug
(`assert 1 == 2 ... exit_code == SystemExit(1)` instead of the expected `2`), confirming
it is a real regression pin, not a test that would pass regardless. Source file restored
immediately after; `git status` clean.

**4. CR-02/CR-03 confirmed filed, not fixed.** `.planning/REQUIREMENTS.md` (commit
`663416f`) has two new entries attributing both defects to **Phase 102** (`f6de196`),
found by Phase 103's code review, explicitly marked "NOT fixed by Phase 103." Confirmed
`git show 0eaca92 -- src/lucy_ng/cli/jcamp.py` touches only the STEP-0 knob-resolution
block (lines 222–269) — the STEP 2.5 purge logic CR-02/CR-03 describe (lines ~293–333)
is untouched by any of the four commits.

**5. Reader comment change confirmed comment-only.**
`git diff 7351e8b^ 7351e8b -- src/lucy_ng/readers/jcamp.py` shows only a docstring/comment
rewrite around `_PPM_PLAUSIBILITY_BOUNDS`; the bound values themselves
(`"13C": (-15.0, 250.0)`, `"1H": (-3.0, 15.0)`) are byte-identical before and after. The
230→250 widening from Phase 103's Task-2 work stands, validated.

**6. Byte-freeze re-confirmed.**
`git diff --exit-code 08ad99a -- src/lucy_ng/nus/qc.py src/lucy_ng/cli/pick.py src/lucy_ng/processing/ .claude/`
→ exit 0 (clean). `git diff --exit-code 08ad99a -- tests/fixtures/nus/known_bad_peaks/`
→ exit 0 (clean).

**7. Scoped tests (not the full suite, per instructions).**
`pytest tests/test_cli_jcamp.py tests/readers/test_jcamp.py -q` → **52 passed**, 0
failures (up from the 38 tests present before `fd40c1f`; +1 new CR-01 regression test,
+ repairs to 3 existing tests that changed assertions but not test count net). `mypy`
and `ruff` on both touched source files are clean (mypy's only output for these two
files is the pre-existing, unrelated `nmrglue` missing-stubs note; ruff: "All checks
passed!"). Per instructions, the full `pytest -q` suite was **not** re-run in this pass
— the orchestrator's post-commit run (1469 passed, 8 skipped, 1 xfailed, 0 failures,
baseline 1468) is accepted as recorded, not independently reproduced here.

**Conclusion:** CR-01 is genuinely fixed, tested with a regression pin confirmed by
mutation (not merely exercised), and does not introduce any new gap. The mirror-image
legal case (keyed-threshold + bare-snr-floor) remains legal exactly as promised — no
regression there. CR-02/CR-03 are correctly filed as tracked, unfixed Phase-102 defects,
not silently dropped and not conflated with this phase's own work. Gap closed.

## Goal Achievement

### Observable Truths (from 103-01-PLAN.md must_haves.truths)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All six `.dx` files READ by one `lucy jcamp` invocation, zero `failed`, HMBC included, NOESY in `skipped` with a reason | ✓ VERIFIED | `103-VALIDATION.md` § Step C quotes `failed: []` and the NOESY skip entry verbatim; corroborated by the on-disk `jcamp_ingest/{staged,qc_failed}/` directory listing (no NOESY.json anywhere, all 5 other experiments present) and the captured `qc_report.json` at the quarantine path, read directly and matching `103-VALIDATION.md`'s QC table byte-for-byte |
| 2 | Per-experiment `KEY=value` knobs settable on one invocation; bare `--snr-floor 5.0` unchanged; unrecognized key exits non-zero; a recognized, explicit knob is never silently ignored | ✓ VERIFIED | Prior pass's CR-01 finding (a bare `--threshold` silently shadowing a keyed `--snr-floor`) is now fixed, live-exercised across all 5 relevant combinations, and pinned by a mutation-confirmed regression test — see "Gap Closure" above. `_parse_keyed_option` allow-lists and fails loud on unknown keys; `tests/test_cli_jcamp.py` 52/52 passing |
| 3 | Every cell of the pre-defined 31-cell D-03 knob matrix has a recorded outcome, not just the winner | ✓ VERIFIED | `grep -cE '^\| (HSQC\|COSY\|HMBC\|13C\|1H) \| (snr_floor\|threshold) \|' 103-VALIDATION.md` = 31 (confirmed live) |
| 4 | QC gate ran EXACTLY ONCE over the fully-staged set (one `run_qc_checks(staged_dir)` call site); verdict + full report recorded | ✓ VERIFIED (report "committed" sub-clause honestly not met — see below) | `grep -c 'run_qc_checks(staged_dir)' src/lucy_ng/cli/jcamp.py` = 1 (confirmed live); verdict + full 6-check table recorded in `103-VALIDATION.md` and independently matches the real `qc_report.json` on disk at the quarantine path, read directly. The "committed" half of this truth is the same expected exception as Truth 7 below (FAIL run → no known-good fixture directory → nothing to commit into the repo) — documented honestly, not silently dropped |
| 5 | Independent 20-row §10 cross-check table + §8 HSQC-correlation count | ✓ VERIFIED | Read `103-VALIDATION.md` directly: 20 rows present, `matched 17/20` summary line, tolerance `c13_tol=0.5` cited from `thresholds_used` (matches the real `qc_report.json`'s `thresholds_used`); §8 section reports total/distinct HSQC counts and a per-quaternary statement for all five compiled-in shifts |
| 6 | Soft-only PARTIAL → chemist verdict verbatim; critical FAIL after exhausted matrix → recorded as NOT achieved with a named tracked next step | ✓ VERIFIED | Verdict is critical FAIL (confirmed against real `qc_report.json`); `103-VALIDATION.md` § "Chemist verdict (D-07)" explicitly states Branch 3 applies, records achieved/NOT-achieved per item, and names **JVAL-F2** (and JVAL-F3) as the tracked next step, filed in `REQUIREMENTS.md` |
| 7 | Accepted peaks committed as a regenerable known-good fixture + test; known-bad QC-02 fixtures byte-unchanged | ⚠️ DOCUMENTED EXCEPTION (not a gap) | Fixture correctly and explicitly NOT created (`tests/fixtures/jcamp/known_good_peaks/` and `tests/test_jcamp_qc_regression.py` both confirmed absent by `ls`) — this is the expected, honestly-documented consequence of the FAIL verdict (D-07 write boundary: no consumable peaks exist to fixture). Known-bad floors re-confirmed byte-unchanged this pass: `git diff --exit-code 08ad99a -- tests/fixtures/nus/known_bad_peaks/` clean |
| 8 | Fresh `/lucy-ng:case C20H32O2` outcome recorded as observation, OR an honest limitation naming the failure mode + tracked next step | ✓ VERIFIED (recorded as NOT ATTEMPTED, correctly) | `103-VALIDATION.md` § "CASE outcome" states Task 6 was formally skipped because the FAIL verdict wrote no `analysis/nmr_peaks/*.json` (confirmed live: the directory does not exist). Recorded as **not attempted**, not as achieved and not as a bare "failed" — matches the required framing exactly |
| 9 | `nus/qc.py`, `PeakPicker2D`, the 1D picker, `cli/pick.py`, `case.md`, the five agent files byte-unchanged vs. `08ad99a` | ✓ VERIFIED | `git diff --exit-code 08ad99a -- .claude/ src/lucy_ng/nus/ src/lucy_ng/processing/peak_picker.py src/lucy_ng/processing/peak_picker_2d.py src/lucy_ng/cli/pick.py` → exit 0 (clean), re-run live this pass |

**Score:** 9/9 truths cleanly verified as documented (including the two D-10-anticipated
exceptions counted as passes on their own honest-documentation terms). Truth #2, downgraded
to PARTIAL in the prior pass for the CR-01 finding, is now fully VERIFIED.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/phases/103-.../103-VALIDATION.md` | Primary evidence: matrix, QC verdict, §10 table, chemist verdict, CASE outcome, ledger | ✓ VERIFIED | Unchanged since prior pass; not re-litigated |
| `tests/fixtures/jcamp/known_good_peaks/HSQC.json` | Positive QC regression fixture | ✗ MISSING (expected, documented) | Correctly absent — FAIL run wrote no consumable peaks; explicitly logged in `103-VALIDATION.md` |
| `tests/test_jcamp_qc_regression.py` | Regression test for the fixture | ✗ MISSING (expected, documented) | Same reason as above |
| `src/lucy_ng/cli/jcamp.py` | `--threshold`/`--snr-floor` KEY=value wiring at all 4 bridge call sites, with a correct ambiguity guard | ✓ VERIFIED | `grep -c 'threshold=' src/lucy_ng/cli/jcamp.py` = 4 (confirmed); CR-01 precedence hole fixed and live-verified across all 5 relevant combinations |
| `tests/test_cli_jcamp.py` | Knob test suite, no vacuous assertions | ✓ VERIFIED | 3 previously-vacuous assertions repaired and confirmed falsifiable by mutation; 1 new CR-01 regression test confirmed to fail against the reintroduced bug; 52/52 passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `cli/jcamp.py` per-experiment knob dicts | `bridge_peak_pick`/`bridge_peak_pick_1d` | `threshold=`/`snr_floor=` at 4 call sites | ✓ WIRED | Confirmed at lines 366-367, 404-405, 446-447, 482-483 |
| `test_jcamp_qc_regression.py` | `tests/fixtures/jcamp/known_good_peaks/` | `run_qc_checks()` | N/A — neither side exists | Consistent with the documented D-10 skip (Truth 7) |
| `103-VALIDATION.md` §10 table | picked 1D `13C.json` shifts | per-signal Δppm rows | ✓ WIRED | All 20 §10 shifts present as rows; the `142.00` row correctly shows "no" match (not silently omitted) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 fix: bare-threshold + keyed-snr-floor rejected | live `CliRunner` against real fixture dir | exit 2, `click.BadParameter` naming COSY | ✓ PASS |
| CR-01 fix: bare-threshold + bare-snr-floor rejected (new, deliberate) | live `CliRunner` | exit 2, clear message | ✓ PASS |
| CR-01 fix: keyed-threshold + bare-snr-floor still legal | live `CliRunner` | exit 1 (real QC FAIL, not usage error) | ✓ PASS |
| CR-01 fix: bare-snr-floor alone unchanged | live `CliRunner` | exit 1 (real QC FAIL, not usage error) | ✓ PASS |
| CR-01 fix: bare-threshold alone unchanged | live `CliRunner` | exit 1 (real QC FAIL, not usage error) | ✓ PASS |
| Regression test genuinely pins the bug (mutation) | reverted guard to old keyed-vs-keyed-only logic, re-ran `test_bare_threshold_with_keyed_snr_floor_is_rejected` | test FAILED against the reintroduced bug; file restored, `git status` clean | ✓ PASS |
| Counter-based call-site test genuinely catches deletion (mutation) | stubbed out the FAIL-branch rebuild call, re-ran `test_keyed_form_routes_per_experiment...` | test FAILED (`1 == 2`); file restored, `git status` clean | ✓ PASS |
| stdout→stderr assertion fix confirmed necessary | reproduced real rejection live, compared `result.output` (empty) vs `result.stderr` (contains message) | confirms old assertion was unfalsifiable, new one is correct | ✓ PASS |
| Scoped test files | `pytest tests/test_cli_jcamp.py tests/readers/test_jcamp.py -q` | 52 passed | ✓ PASS |
| mypy/ruff on touched files | `mypy src/lucy_ng/cli/jcamp.py src/lucy_ng/readers/jcamp.py`; `ruff check` (both files + both test files) | mypy: only pre-existing unrelated nmrglue-stub note; ruff: "All checks passed!" | ✓ PASS |
| Byte-freeze drift gate (re-confirmed) | `git diff --exit-code 08ad99a -- .claude/ src/lucy_ng/nus/ src/lucy_ng/processing/ src/lucy_ng/cli/pick.py` | exit 0 | ✓ PASS |
| Known-bad fixtures unchanged (re-confirmed) | `git diff --exit-code 08ad99a -- tests/fixtures/nus/known_bad_peaks/` | exit 0 | ✓ PASS |
| Reader comment-only change | `git diff 7351e8b^ 7351e8b -- src/lucy_ng/readers/jcamp.py` | comment/docstring only; bound values byte-identical | ✓ PASS |
| CR-02/CR-03 filed not fixed | `git show 663416f -- .planning/REQUIREMENTS.md`; `git show 0eaca92 -- src/lucy_ng/cli/jcamp.py` | REQUIREMENTS.md has both entries, attributed to Phase 102 (f6de196); the fix commit touches only STEP 0, not the STEP 2.5 purge logic CR-02/CR-03 describe | ✓ PASS |
| Full suite (per instructions, NOT re-run this pass) | orchestrator's post-commit run (accepted as recorded) | 1469 passed, 8 skipped, 1 xfailed, 0 failures (baseline 1468) | ? ACCEPTED (not independently reproduced, per explicit scope instruction) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| JVAL-01 | 103-01-PLAN.md | Real dataset read+picked+QC-graded to §8 quality | ✓ SATISFIED-AS-PARTIAL | Unchanged from prior pass; `REQUIREMENTS.md` line 109 correctly reads "Partial ... honest partial close — see JVAL-F2/JVAL-F3" |
| JVAL-02 | 103-01-PLAN.md | Fresh CASE convergence on JCAMP-derived peaks | ✓ SATISFIED-AS-PARTIAL | Unchanged from prior pass; `REQUIREMENTS.md` line 110 correctly reads "Partial ... not attempted — no consumable peaks" |
| JVAL-F2 | Filed by this phase | Real-data 2D noise/quaternary-override recalibration | ✓ FILED | Unchanged from prior pass |
| JVAL-F3 | Filed by this phase | Re-export exp7/wide as JCAMP-DX | ✓ FILED | Unchanged from prior pass |

No orphaned requirements (unchanged from prior pass).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/lucy_ng/cli/jcamp.py` | 299-306 | CR-02/CR-03 (pre-existing from Phase 102): `--out` purge deletes prior consumable output before any input is read; `work_root` collision `rmtree`s the whole user directory | ℹ️ Info — now tracked | Not attributable to Phase 103's delivered work; now correctly filed in `REQUIREMENTS.md` as tracked, unfixed Phase-102 defects (confirmed this pass) |

CR-01 (the prior pass's 🛑 Blocker-class finding) is resolved — fix confirmed live and
by mutation-tested regression test; no longer listed as an anti-pattern.
WR-09/WR-10 (the two previously-vacuous test assertions) are resolved — both repairs
confirmed genuinely falsifiable by mutation, not just by reading the diff.
WR-07 (the reader comment's inverted rationale) is resolved — the comment now correctly
states the floor, not the ceiling, exercises the computed-Hz half of the guard.

No `TBD`/`FIXME`/`XXX` unreferenced debt markers found in the two touched source files
(re-confirmed this pass).

### Human Verification Required

None. Unchanged from the prior pass — the two checkpoint gates this plan defines were
already exercised with recorded human/coordinator confirmation, and this re-verification
pass's scope (CR-01 code-level closure) required no new human judgment calls.

### Gaps Summary

No open gaps. The single gap recorded in the prior `103-VERIFICATION.md` pass — CR-01, a
silent-ignore precedence defect in the per-experiment `--threshold`/`--snr-floor` CLI
wiring — is confirmed closed: fixed in `0eaca92`, pinned by a mutation-confirmed
regression test in `fd40c1f` (plus three previously-vacuous tests independently
confirmed repaired, also by mutation), with no new gap introduced. CR-02/CR-03,
discovered incidentally by this phase's code review but attributable to Phase 102, are
correctly filed as tracked follow-ups rather than silently fixed or silently dropped.
The `7351e8b` comment-only change to `readers/jcamp.py` does not touch validated bounds
or logic. Byte-freeze and known-bad fixtures remain untouched.

The phase's D-10 honest-partial-close for JVAL-01/JVAL-02 stands unchanged from the
prior verification pass and is not re-litigated here.

---

_Verified: 2026-07-28_
_Verifier: Claude (gsd-verifier)_
