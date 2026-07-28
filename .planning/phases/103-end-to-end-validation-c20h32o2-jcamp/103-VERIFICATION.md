---
phase: 103-end-to-end-validation-c20h32o2-jcamp
verified: 2026-07-28T00:00:00Z
status: gaps_found
score: 8/9 must-haves verified (2 of the 9 correctly documented as not-achieved by an
  approved D-10 honest-partial-close; 1 additional finding — CR-01 — flagged as an
  unresolved defect in this phase's own Task-2 deliverable)
overrides_applied: 0
gaps:
  - truth: "Per-experiment picker knobs are settable on ONE `lucy jcamp` invocation as repeatable KEY=value options, the plain `--snr-floor 5.0` form still behaves exactly as before, and an unrecognized experiment key exits non-zero instead of being silently ignored"
    status: partial
    reason: >
      The literal claim (unrecognized keys exit non-zero; bare --snr-floor 5.0 is
      unchanged; keyed-vs-keyed ambiguity is rejected) is independently verified true
      by direct code reading and test execution. However, code review 103-REVIEW.md
      CR-01 (confirmed by direct inspection of src/lucy_ng/cli/jcamp.py:217-241, commit
      426926e, this phase's own Task 2) found a silent-ignore precedence hole the plan's
      own <behavior> section never specified: a BARE --threshold combined with a KEYED
      --snr-floor for the same experiment is accepted (exit 0/1), forwarded to the
      bridge, and then silently discarded because `use_snr = threshold is None` in
      nus/bridge.py (byte-frozen) makes threshold mode win unconditionally once
      threshold is non-None for that call. The ambiguity guard added in this phase only
      compares `set(threshold_by_exp) & set(snr_by_exp)` (keyed vs. keyed), never the
      *resolved* effective threshold. This is exactly the "recognized key silently
      ignored" anti-pattern the phase's own must-have text says must not happen, just
      for a combination the plan never enumerated. Confirmed independently (not just
      trusting REVIEW.md): read cli/jcamp.py STEP 0 block directly; the guard logic at
      lines 227-234 provably does not cover this case. No test in
      TestJcampKnobOptions exercises it (WR-11 in the review, confirmed by reading
      tests/test_cli_jcamp.py:680-943 — the mirror-image case is tested, this one is
      not). Does NOT corrupt the JVAL-01 evidence already gathered: the one governed
      `lucy jcamp` invocation in 103-VALIDATION.md § Step C used only `--snr-floor`
      (bare and keyed), never `--threshold`, so CR-01 was never triggered in the
      recorded run.
    artifacts:
      - path: "src/lucy_ng/cli/jcamp.py"
        issue: "Ambiguity guard at lines ~227-234 tests keyed-vs-keyed sets only, not the resolved effective threshold/snr_floor per experiment; a bare --threshold silently shadows every keyed --snr-floor with no diagnostic."
      - path: "tests/test_cli_jcamp.py"
        issue: "TestJcampKnobOptions has no test for bare-threshold + keyed-snr-floor (the actually-broken combination); the mirror case (keyed-threshold + bare-snr-floor) is tested (test_keyed_threshold_with_bare_snr_floor_is_legal), and that test's own assertion is provably vacuous (`result.exception is None or isinstance(result.exception, SystemExit)` — true in both the accept and the reject case)."
    missing:
      - "Either fix the guard to compare resolved (not just keyed) modes per experiment and add the negative test tests/test_cli_jcamp.py::test_bare_threshold_with_keyed_snr_floor_is_rejected (per 103-REVIEW.md's suggested fix), or file this explicitly as a tracked Future Requirement (e.g. JVAL-F4) in .planning/REQUIREMENTS.md so it is not silently lost — right now it exists only in 103-REVIEW.md, which is not cross-referenced from REQUIREMENTS.md or ROADMAP.md."
deferred: []
---

# Phase 103: End-to-End Validation (C20H32O2-jcamp) Verification Report

**Phase Goal:** The `C20H32O2-jcamp` dataset proves the JCAMP ingestion path is not just
mechanically correct but usable for real CASE structure elucidation.
**Verified:** 2026-07-28
**Status:** gaps_found
**Re-verification:** No — initial verification

## Framing (read this before the table)

This phase closed as a **deliberate, coordinator-approved honest PARTIAL** (the plan's
own D-10 branch). That is not, by itself, a verification failure — the plan's must-haves
explicitly anticipate and require exactly this branch when the QC verdict is a critical
FAIL. The bulk of this verification therefore checks whether the PARTIAL close is
**honest and complete**, not whether JVAL-01/JVAL-02 were literally achieved (they were
not, and are correctly recorded as not achieved).

One new, separate finding falls outside that framing: **CR-01**, a code-review-identified
critical defect in this phase's own Task 2 deliverable (the `--threshold`/`--snr-floor`
CLI knob wiring), confirmed independently by direct code inspection. It does not
retroactively corrupt the JVAL-01 evidence already gathered (the governed run never used
`--threshold`), but it is an unresolved, untested, untracked defect in code this phase
shipped and claimed was "shipped cleanly" (SUMMARY.md). That is why overall status is
`gaps_found` rather than `passed`.

## Goal Achievement

### Observable Truths (from 103-01-PLAN.md must_haves.truths)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All six `.dx` files READ by one `lucy jcamp` invocation, zero `failed`, HMBC included, NOESY in `skipped` with a reason | ✓ VERIFIED | `103-VALIDATION.md` § Step C quotes `failed: []` and the NOESY skip entry verbatim; corroborated by the on-disk `jcamp_ingest/{staged,qc_failed}/` directory listing (no NOESY.json anywhere, all 5 other experiments present) and the captured `qc_report.json` at the quarantine path, read directly and matching `103-VALIDATION.md`'s QC table byte-for-byte |
| 2 | Per-experiment `KEY=value` knobs settable on one invocation; bare `--snr-floor 5.0` unchanged; unrecognized key exits non-zero | ⚠️ PARTIAL (see gap) | The literal sub-claims verified true (tests pass, `_parse_keyed_option` allow-lists and fails loud on unknown keys, verified by reading `cli/jcamp.py:74-97` and running `tests/test_cli_jcamp.py` — 38 passed). BUT: CR-01 (bare `--threshold` silently shadows a keyed `--snr-floor`) is a real, reproduced, untested gap in the general knob-settability claim — see Gaps |
| 3 | Every cell of the pre-defined 31-cell D-03 knob matrix has a recorded outcome, not just the winner | ✓ VERIFIED | `grep -cE '^\| (HSQC\|COSY\|HMBC\|13C\|1H) \| (snr_floor\|threshold) \|' 103-VALIDATION.md` = 31 (confirmed live) |
| 4 | QC gate ran EXACTLY ONCE over the fully-staged set (one `run_qc_checks(staged_dir)` call site); verdict + full report recorded | ✓ VERIFIED (report "committed" sub-clause honestly not met — see below) | `grep -c 'run_qc_checks(staged_dir)' src/lucy_ng/cli/jcamp.py` = 1 (confirmed live); verdict + full 6-check table recorded in `103-VALIDATION.md` and independently matches the real `qc_report.json` on disk at the quarantine path, read directly. The "committed" half of this truth is the same expected exception as Truth 7 below (FAIL run → no known-good fixture directory → nothing to commit into the repo) — documented honestly, not silently dropped |
| 5 | Independent 20-row §10 cross-check table + §8 HSQC-correlation count | ✓ VERIFIED | Read `103-VALIDATION.md` directly: 20 rows present, `matched 17/20` summary line, tolerance `c13_tol=0.5` cited from `thresholds_used` (matches the real `qc_report.json`'s `thresholds_used`); §8 section reports total/distinct HSQC counts and a per-quaternary statement for all five compiled-in shifts |
| 6 | Soft-only PARTIAL → chemist verdict verbatim; critical FAIL after exhausted matrix → recorded as NOT achieved with a named tracked next step | ✓ VERIFIED | Verdict is critical FAIL (confirmed against real `qc_report.json`); `103-VALIDATION.md` § "Chemist verdict (D-07)" explicitly states Branch 3 applies, records achieved/NOT-achieved per item, and names **JVAL-F2** (and JVAL-F3) as the tracked next step, filed in `REQUIREMENTS.md` |
| 7 | Accepted peaks committed as a regenerable known-good fixture + test; known-bad QC-02 fixtures byte-unchanged | ⚠️ DOCUMENTED EXCEPTION (not a gap) | Fixture correctly and explicitly NOT created (`tests/fixtures/jcamp/known_good_peaks/` and `tests/test_jcamp_qc_regression.py` both confirmed absent by `ls`) — this is the expected, honestly-documented consequence of the FAIL verdict (D-07 write boundary: no consumable peaks exist to fixture). Known-bad floors confirmed byte-unchanged: `git diff --exit-code 08ad99a -- tests/fixtures/nus/known_bad_peaks/` clean, AND the external `~/.../C20H32O2/analysis/nmr_peaks/*.json` `shasum` values (re-run live) match `103-VALIDATION.md`'s recorded checksums exactly, all 7 files |
| 8 | Fresh `/lucy-ng:case C20H32O2` outcome recorded as observation, OR an honest limitation naming the failure mode + tracked next step | ✓ VERIFIED (recorded as NOT ATTEMPTED, correctly) | `103-VALIDATION.md` § "CASE outcome" states Task 6 was formally skipped because the FAIL verdict wrote no `analysis/nmr_peaks/*.json` (confirmed live: the directory does not exist). Recorded as **not attempted**, not as achieved and not as a bare "failed" — matches the required framing exactly. Correctly does NOT file a new JVAL-F1 (no evidence was gathered either way, and the plan's own Task 6 branch only requires filing JVAL-F1 on the BAD-integration-outcome branch, which was never reached) |
| 9 | `nus/qc.py`, `PeakPicker2D`, the 1D picker, `cli/pick.py`, `case.md`, the five agent files byte-unchanged vs. `08ad99a` | ✓ VERIFIED | `git diff --exit-code 08ad99a -- .claude/ src/lucy_ng/nus/ src/lucy_ng/processing/peak_picker.py src/lucy_ng/processing/peak_picker_2d.py src/lucy_ng/cli/pick.py` → exit 0 (clean), run live. `pytest tests/test_skill_files_unchanged.py -q` → 8 passed, run live |

**Score:** 8/9 truths cleanly verified as documented (including the two D-10-anticipated
exceptions counted as passes on their own honest-documentation terms); 1 truth (#2)
downgraded to PARTIAL for the CR-01 finding.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/phases/103-.../103-VALIDATION.md` | Primary evidence: matrix, QC verdict, §10 table, chemist verdict, CASE outcome, ledger | ✓ VERIFIED | Exists, 613 lines, every required section present and cross-checked live against on-disk artifacts (qc_report.json, checksums) — not just narration |
| `tests/fixtures/jcamp/known_good_peaks/HSQC.json` | Positive QC regression fixture | ✗ MISSING (expected, documented) | Correctly absent — FAIL run wrote no consumable peaks; explicitly logged in `103-VALIDATION.md` as "SKIPPED" with reason, matching the plan's own Task 5 contingency text |
| `tests/test_jcamp_qc_regression.py` | Regression test for the fixture | ✗ MISSING (expected, documented) | Same reason as above; confirmed absent via `ls` |
| `src/lucy_ng/cli/jcamp.py` | `--threshold`/`--snr-floor` KEY=value wiring at all 4 bridge call sites | ⚠️ VERIFIED-WITH-DEFECT | `grep -c 'threshold=' src/lucy_ng/cli/jcamp.py` = 4 (confirmed); contains `--threshold`; CR-01 precedence hole confirmed live in the same file |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `cli/jcamp.py` per-experiment knob dicts | `bridge_peak_pick`/`bridge_peak_pick_1d` | `threshold=`/`snr_floor=` at 4 call sites | ✓ WIRED | Confirmed at lines 339, 377, 419, 455 — 1D staging, 2D staging, FAIL rebuild, PASS/PARTIAL rebuild, matching the plan's documented call-site map |
| `test_jcamp_qc_regression.py` | `tests/fixtures/jcamp/known_good_peaks/` | `run_qc_checks()` | N/A — neither side exists | Consistent with the documented D-10 skip (Truth 7) |
| `103-VALIDATION.md` §10 table | picked 1D `13C.json` shifts | per-signal Δppm rows | ✓ WIRED | All 20 §10 shifts present as rows; the `142.00` row correctly shows "no" match (not silently omitted) |

### Data-Flow Trace (Level 4)

Not applicable in the usual sense (no UI component rendering dynamic data). The
equivalent check here — does `103-VALIDATION.md`'s narrated evidence trace back to real,
unmodified on-disk data rather than fabricated numbers — was performed and passed:
the quoted `qc_report.json` verdict/checks/`thresholds_used` were independently re-read
from the external quarantine file and match the VALIDATION.md transcription exactly
(verdict, all 6 check names/critical flags/details/values, all 6 threshold values);
the external known-bad `shasum` values were independently recomputed and match.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Byte-freeze drift gate | `git diff --exit-code 08ad99a -- .claude/ src/lucy_ng/nus/ src/lucy_ng/processing/peak_picker*.py src/lucy_ng/cli/pick.py` | exit 0 | ✓ PASS |
| Single QC call-site invariant | `grep -c 'run_qc_checks(staged_dir)' src/lucy_ng/cli/jcamp.py` | 1 | ✓ PASS |
| Four bridge call sites | `grep -c 'threshold=' src/lucy_ng/cli/jcamp.py` | 4 | ✓ PASS |
| Skill-files unchanged | `pytest tests/test_skill_files_unchanged.py -q` | 8 passed | ✓ PASS |
| Scoped phase test files | `pytest tests/test_cli_jcamp.py tests/readers/test_jcamp.py tests/test_jcamp_1d_bridge.py -q` | 59 passed | ✓ PASS |
| mypy/ruff on touched files | `mypy src/lucy_ng/cli/jcamp.py src/lucy_ng/readers/jcamp.py`; `ruff check src/lucy_ng/cli/jcamp.py src/lucy_ng/readers/jcamp.py tests/test_cli_jcamp.py tests/readers/test_jcamp.py` | mypy: only pre-existing unrelated nmrglue-stub notes, zero errors in these two files; ruff: "All checks passed!" | ✓ PASS |
| External known-bad checksums unchanged | `shasum ~/.../C20H32O2/analysis/nmr_peaks/*.json` | Matches `103-VALIDATION.md`'s recorded values exactly (all 7 files) | ✓ PASS |
| CR-01 reproduction | Direct read of `cli/jcamp.py` STEP 0 (lines 217-241) | Ambiguity guard only compares `set(threshold_by_exp) & set(snr_by_exp)`; `_resolved_threshold`/`_resolved_snr_floor` resolve independently with no cross-check | ✗ CONFIRMS the gap |
| Full suite (`pytest -q`, 1477 tests collected) | background run | Did not complete within available verification time — an unrelated, apparently slow/stalled module (`test_database_importer.py`, likely large reference-DB-adjacent I/O) stopped progressing past 24% after several minutes; killed to avoid open-ended resource use | ? SKIPPED (see note) |

**Note on the full-suite check:** the SUMMARY's "1468 passed vs. 1408-test Phase-102
baseline, zero regressions" claim could not be independently reproduced end-to-end in
the time available for this verification — the run stalled (not failed) partway through
an unrelated test module. All *scoped* checks relevant to this phase's own changed files
(readers/jcamp.py, cli/jcamp.py, and their test files) passed cleanly, and mypy/ruff are
clean on those files specifically. This is recorded as a limitation of this
verification pass, not as a finding against the phase — there is no evidence of a
regression, only incomplete confirmation of "zero regressions across the whole suite."

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| JVAL-01 | 103-01-PLAN.md | Real dataset read+picked+QC-graded to §8 quality | ✓ SATISFIED-AS-PARTIAL | `REQUIREMENTS.md` line 87 correctly reads "Partial ... honest partial close — see JVAL-F2/JVAL-F3"; matches `103-VALIDATION.md`'s own close narrative and the real `qc_report.json` FAIL verdict |
| JVAL-02 | 103-01-PLAN.md | Fresh CASE convergence on JCAMP-derived peaks | ✓ SATISFIED-AS-PARTIAL | `REQUIREMENTS.md` line 88 correctly reads "Partial ... not attempted — no consumable peaks"; matches the confirmed absence of `analysis/nmr_peaks/` |
| JVAL-F2 | Filed by this phase | Real-data 2D noise/quaternary-override recalibration | ✓ FILED | `REQUIREMENTS.md` § Future Requirements, full detail present (root cause, both possible fix directions, byte-frozen-file caveat) |
| JVAL-F3 | Filed by this phase | Re-export exp7/wide as JCAMP-DX | ✓ FILED | `REQUIREMENTS.md` § Future Requirements, includes the explicit "would NOT by itself fix quaternary_exclusion" honesty caveat |

No orphaned requirements: `grep -n "Phase 103" .planning/REQUIREMENTS.md` and the
Traceability table both map JVAL-01/JVAL-02 to Phase 103 exclusively, and both IDs
appear in the plan's own `requirements:` frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/lucy_ng/cli/jcamp.py` | ~217-234 | CR-01: ambiguity guard tests keyed-vs-keyed only, not resolved mode | 🛑 Blocker-class (silent-ignore of a recognized, explicit user option) | Confirmed live by direct code reading; reproduced by 103-REVIEW.md; no test covers it; not tracked as a Future Requirement anywhere in REQUIREMENTS.md/ROADMAP.md |
| `src/lucy_ng/cli/jcamp.py` | 299-306 | CR-02/CR-03 (pre-existing from Phase 102, rediscovered by this phase's review): `--out` purge deletes prior consumable output before any input is read; `--out .../jcamp_ingest` collision `rmtree`s the whole user directory | ℹ️ Info for THIS phase (not introduced here; STEP 2.5 predates Phase 103's Task 2 changes, confirmed by reading the surrounding comment referencing Phase 102's own "CR-01") | Not attributable to Phase 103's delivered work; flagged for completeness since `cli/jcamp.py` is a file this phase touched and re-shipped without addressing it |
| `tests/test_cli_jcamp.py` | 895-905, 838 | WR-09/WR-10: two assertions in the Phase-103 knob test suite are provably vacuous (`result.exception is None or isinstance(..., SystemExit)`; a stdout-only substring check against a stderr-only message) | ⚠️ Warning | Confirmed by direct reading; reduces actual coverage below what the test names claim, and is precisely why CR-01 shipped uncaught |
| `src/lucy_ng/readers/jcamp.py` | 46-53 (comment) | WR-07: the widened-bound comment's stated rationale is factually inverted (claims the *ceiling* defends against the SFO/SF divisor bug; the guard's own docstring says the opposite, and it's actually the floor, per WR-06) | ℹ️ Info | Not independently re-derived line-by-line here, but the underlying claim (`_ppm_scale`'s `scale[0]` is always the raw file's `$OFFSET`) is consistent with `readers/jcamp.py`'s own code structure read during this verification; taken on the code review's authority as a documentation-accuracy issue, not a behavior gap |

No `TBD`/`FIXME`/`XXX` unreferenced debt markers found in the two touched source files
(`grep -n -E "TBD|FIXME|XXX" src/lucy_ng/cli/jcamp.py src/lucy_ng/readers/jcamp.py` →
no matches).

### Human Verification Required

None. The two checkpoint gates this plan defines (Task 4's D-07/D-10 chemist gate, Task
6's D-14 CASE handoff) were both already exercised with recorded human/coordinator
confirmation (`103-VALIDATION.md` § "Chemist verdict (D-07)" and the "Approval:
Coordinator-approved D-10 honest partial close, 2026-07-28" line at the file's end).
Re-litigating an already-approved checkpoint decision is out of scope for this
verification; this report instead checked that what was approved is what is actually
on disk and in git, which it is.

### Gaps Summary

One real gap, structured in the frontmatter above: **CR-01**, a silent-ignore precedence
defect in the per-experiment `--threshold`/`--snr-floor` CLI wiring shipped by this
phase's own Task 2 (commit `426926e`). It is independently confirmed by direct code
reading (not merely trusting `103-REVIEW.md`'s narrative): the phase's own ambiguity
guard checks only `set(threshold_by_exp) & set(snr_by_exp)`, never the *resolved*
effective mode per experiment, so a bare `--threshold` silently shadows any keyed
`--snr-floor` with no error and no message. This directly matches the failure class the
phase's own must-have text explicitly rules out ("never be silently ignored") — just for
a combination the plan's `<behavior>` section never enumerated, and which the
implementation's own test suite (confirmed by direct reading) does not cover.

This finding does **not** invalidate the phase's D-10 honest-partial-close for
JVAL-01/JVAL-02, which is independently verified as accurate, evidence-backed, and
properly approved. It also does not touch any byte-frozen file. It is reported because
(a) it is a genuine, reproducible defect in code this phase shipped and described as
"shipped cleanly" / "zero regressions" in SUMMARY.md, and (b) it currently has **no
tracked follow-up anywhere** — it exists only inside `103-REVIEW.md`, which is not
cross-referenced from `REQUIREMENTS.md` or `ROADMAP.md`, so it would be easy to lose
before milestone close.

**This looks like an oversight rather than an intentional deviation** (the plan's
`<behavior>` section addresses the mirror-image case explicitly and gets it right; this
combination was simply never enumerated). Recommended resolution — either of:
1. A small follow-up fix to `cli/jcamp.py`'s ambiguity guard (103-REVIEW.md's suggested
   fix is directly applicable) plus the missing negative test, or
2. File it explicitly in `.planning/REQUIREMENTS.md` § Future Requirements (e.g.
   `JVAL-F4`) so it survives past this session, if the team decides the fix can wait.

If the team judges this an acceptable, already-understood risk (e.g. because the
governed real-data run never combines a bare `--threshold` with a keyed `--snr-floor`),
add an override to this file's frontmatter recording that decision, and it will be
counted as resolved on re-verification.

---

_Verified: 2026-07-28_
_Verifier: Claude (gsd-verifier)_
