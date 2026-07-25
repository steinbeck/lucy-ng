---
phase: 102-cli-peak-pick-bridge-qc-reuse
verified: 2026-07-25T13:35:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 102: CLI + Peak-Pick Bridge + QC Reuse Verification Report

**Phase Goal:** A JCAMP-DX file or directory can be turned into CASE-consumable, QC-graded peak lists via one command, reusing the Phase-99 bridge and QC gate exactly as they are — zero changes to `case.md` or the 5-agent team.

**Verified:** 2026-07-25T13:35:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `lucy jcamp <dir-or-files>` runs read→pick→QC→write via the reused Phase-99 bridge, not a new picker; `--format json` supported | ✓ VERIFIED | Live-ran `lucy jcamp <copied-fixture-dir> --format json` — produced correct JSON with `verdict/out_dir/written/skipped/failed/quarantine/report` keys. Read `src/lucy_ng/cli/jcamp.py` in full: 2D dispatch calls `bridge_peak_pick(...)` (imported from `lucy_ng.nus.bridge`, never reimplemented); 1D dispatch calls `bridge_peak_pick_1d(...)` (`processing/jcamp_1d_bridge.py`, itself a direct call to `AdaptivePeakPicker.pick_peaks`, verified `grep -n "AdaptivePeakPicker.pick_peaks(" src/lucy_ng/processing/jcamp_1d_bridge.py` hits). `grep -c "run_qc_checks(" src/lucy_ng/cli/jcamp.py` = 1 (QC called once, not per-file). |
| 2 | JCAMP-derived peaks pass through the unchanged Phase-99 QC gate and receive PASS/PARTIAL/FAIL exactly like NUS peaks | ✓ VERIFIED | Live run over the 6 committed fixtures produced verdict `FAIL` with the exact 6 named checks (`quaternary_exclusion` PASS; `ppm_calibration`, `hsqc_coverage`, `signal_to_ridge` FAIL-critical; `edited_sign_consistency`, `cosy_diagonal_symmetry` FAIL-soft) — matches 102-04-SUMMARY.md's recorded observation verbatim. `TestJcampQcDiscrimination` (4 tests, `tests/test_cli_jcamp.py`) independently proves PASS/PARTIAL/FAIL each drive distinct write behavior via a synthetic `QcReport` test-double (verdict only; peaks are real). `git diff --exit-code 22f2b52 -- src/lucy_ng/nus/` exits 0 — `qc.py`/`bridge.py` byte-unchanged. |
| 3 | Edited-HSQC sign (+/-) survives the JCAMP round-trip; multiplicity derivation still works | ✓ VERIFIED | Independently re-ran the live CLI and inspected the quarantined `HSQC.json`: `n_cross_peaks=115`, multiplicity_hint distribution `{"CH_or_CH3": 70, "CH2": 45}`, zero `"CH_or_CH2_or_CH3"` ambiguous hints — exact match to the claimed values in 102-04-PLAN.md's `<interfaces>` and 102-04-SUMMARY.md's "Observed results". Reproduced on real (trimmed) committed data, not asserted from prose. |
| 4 | `case.md` and the 5-agent-team files are byte-unchanged, verifiable by diff | ✓ VERIFIED | Ran `git diff --exit-code 22f2b52 -- .claude/ src/lucy_ng/nus/ src/lucy_ng/cli/pick.py src/lucy_ng/processing/peak_picker.py src/lucy_ng/processing/peak_picker_2d.py` myself — exit code 0, no diff. `tests/test_skill_files_unchanged.py` (8 tests) hashes real file bytes (`hashlib.sha256(path.read_bytes())`) against a frozen baseline table and globs `.claude/agents/lucy-*.md` for roster completeness — cannot pass vacuously (verified by reading the full test source; it is not a self-referential tautology). Ran it: 8 passed. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lucy_ng/cli/jcamp.py` | `lucy jcamp` command, import-safe, deferred domain imports | ✓ VERIFIED | 400 lines; single `@click.command("jcamp")` (not a group); no `lucy_ng.*` import at module level (`python -c "import lucy_ng.cli.jcamp; assert 'lucy_ng.nus.qc' not in sys.modules"` — verified in CI test); CR-01 fix present (STEP 2.5 clears `work_root`/`out_root` stale state each run — read and live-reproduced) |
| `src/lucy_ng/processing/jcamp_1d_bridge.py` | 1D bridge, direct-call to `AdaptivePeakPicker`, schema-identical to `pick_1d` | ✓ VERIFIED | Exports `bridge_peak_pick_1d`, `peak_json_filename`; live payload check on real `13C.dx` fixture confirmed keys `count/noise_sigma/negative_detected/snr_floor_used/peaks/nucleus`, no `cross_peaks` key |
| `src/lucy_ng/readers/jcamp.py` (`_resolve_dim` homonuclear fix) | Positional fallback so COSY/NOESY read without raising | ✓ VERIFIED | `procs_index` param present at both call sites; live `JcampReader.read()` on COSY/NOESY/HMBC/HSQC all succeeded in the end-to-end run (`failed: []`) |
| `tests/test_cli_jcamp.py` | Fixture-backed E2E + discrimination + CLI-surface suite | ✓ VERIFIED | 27+ tests collected across `TestJcampCliSurface`, `TestJcampUnexpectedReadResultType`, `TestJcampImportSafety`, `TestJcampEndToEnd`, `TestJcampStaleStateCleared` (added post-review, CR-01 regression), `TestJcampQcDiscrimination`; all pass |
| `tests/test_skill_files_unchanged.py` | SHA-256 golden-hash guard, ≥8 tests | ✓ VERIFIED | 8 tests, all pass; cwd-independent (`Path(__file__).resolve().parents[1]`); not vacuous |
| `tests/fixtures/jcamp/C20H32O2_{COSY,HMBC,NOESY}_trimmed.dx` | Committed real (trimmed) 2D fixtures | ✓ VERIFIED | Present, tracked, 16 pages each; used directly in the live CLI reproduction above |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `cli/jcamp.py` | `nus/bridge.py::bridge_peak_pick` | direct call, deferred import | ✓ WIRED | Read source; live-exercised; not reimplemented |
| `cli/jcamp.py` | `processing/jcamp_1d_bridge.py::bridge_peak_pick_1d` | direct call | ✓ WIRED | Read source; live-exercised (`13C.json`/`1H.json` written into quarantine) |
| `cli/jcamp.py` | `nus/qc.py::run_qc_checks` | single deferred call over staged dir | ✓ WIRED | `grep -c "run_qc_checks("` = 1; live run produced a real `QcReport` with 6 checks |
| `cli/main.py` | `cli/jcamp.py::jcamp` | `cli.add_command(jcamp)` | ✓ WIRED | `lucy jcamp --help` works via the installed `lucy` entrypoint (verified live) |

### Data-Flow Trace (Level 4)

Not applicable in the UI-rendering sense (this is a CLI, not a web component), but the equivalent trace was performed by directly executing `lucy jcamp` against real (trimmed) fixture files copied to a scratch directory and inspecting the emitted JSON on disk — this is the strongest available proof for a CLI artifact and was done independently of the SUMMARY's claims, with identical results (verdict FAIL, 115 cross-peaks, 70/45 split, quarantine populated, no `nmr_peaks/` created). A second live run after deleting the COSY input file confirmed the CR-01 stale-state fix: the prior run's `COSY.json` no longer appears in the quarantine directory on re-run.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| JCLI-01 | 102-01, 102-02, 102-03, 102-04 | `lucy jcamp` full chain, reused bridge, `--format json` | ✓ SATISFIED | Live CLI run + code inspection, see Truth 1 |
| JCLI-02 | 102-02, 102-03, 102-04 | Unchanged QC gate, edited-sign preserved, `case.md`/agents byte-unchanged | ✓ SATISFIED | Live CLI run + `git diff --exit-code`, see Truths 2-4 |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s traceability table lists only JCLI-01/JCLI-02 for Phase 102, both accounted for above. Note: the REQUIREMENTS.md checkboxes and traceability table still read "Pending" / unchecked for JCLI-01/JCLI-02 — this is a documentation-sync gap (the doc was not updated after phase completion), not a code gap; flagged as informational only, does not affect the phase's goal-achievement status.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER found in any Phase-102 file | — | None found via targeted grep across `cli/jcamp.py`, `processing/jcamp_1d_bridge.py`, `readers/jcamp.py` (diff region), test files |

The one real defect found during the phase (CR-01, stale staging/quarantine/consumable state across re-runs) was caught by the code reviewer, is fixed in commit `f6de196` with two regression tests (`TestJcampStaleStateCleared`), and was independently reproduced live in this verification (see Data-Flow Trace) — confirmed genuinely fixed, not just claimed fixed. WR-01 (bare `assert` for control flow) and WR-02 (hand-duplicated supported-experiment sets with no drift guard) are both fixed in `c4d8f06`/`fd0181f` with regression tests. IN-01 (misleading docstring) fixed in `0693914`.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `lucy jcamp <dir>` on 6 real committed fixtures | `lucy jcamp <copied-fixtures> --format json` | Exit 1, verdict FAIL, NOESY skipped, quarantine populated with `HSQC.json` (115 cross-peaks, 70/45 multiplicity split) | ✓ PASS |
| CR-01 fix (stale-state clearing) | Re-ran after deleting `COSY_trimmed.dx` from the input dir | Stale `COSY.json` no longer present in quarantine on 2nd run | ✓ PASS |
| Byte-unchanged drift gate (criterion 4) | `git diff --exit-code 22f2b52 -- .claude/ src/lucy_ng/nus/ src/lucy_ng/cli/pick.py src/lucy_ng/processing/peak_picker.py src/lucy_ng/processing/peak_picker_2d.py` | Exit 0, no diff | ✓ PASS |
| Full test suite | `pytest -q` (full repo) | 1457 passed, 8 skipped, 1 xfailed — matches the documented baseline exactly, zero regressions | ✓ PASS |
| Targeted phase test suite | `pytest tests/readers/test_jcamp.py tests/test_jcamp_1d_bridge.py tests/test_cli_jcamp.py -q` | 48 passed | ✓ PASS |
| Static gates | `mypy src/lucy_ng` / `ruff check src tests` | 119 / 282 errors — identical to the documented pre-existing baseline (confirmed by diffing against the Phase-101-close baseline checkout); zero errors in any Phase-102 file (`jcamp.py`, `jcamp_1d_bridge.py`) | ✓ PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` convention; its equivalent "probe" is the fixture-backed CLI run, executed live above (see Behavioral Spot-Checks).

## Honesty-Gate Assessment (per verification_emphasis)

1. **Proof-level honesty is itself a deliverable — VERIFIED.** No artifact anywhere (SUMMARY.md, VALIDATION.md, docstrings, test names) presents the 16-row fixture result as "verified on real data." Grepped all Phase-102 planning artifacts for the phrase; every hit is a statement that the claim is explicitly NOT made (a negation), or a plan/threat-model instruction to avoid making it. The FAIL verdict is recorded as an *observed* value with an honest, mechanically-correct reason (16 F1 rows cannot reach the 0.8 `hsqc_coverage` floor against the whole-file 1D reference) — independently reproduced live, not merely asserted.
2. **D-05 boundary — respected.** No artifact claims the real, uncommitted `C20H32O2-jcamp` dataset was driven to a green §8 verdict; every SUMMARY explicitly assigns that to Phase 103/JVAL. No Phase-103 work (JVAL-01/02, CASE convergence) was found pulled forward.
3. **Criterion 4 — verified by actually running the diff**, not by reading a claim: `git diff --exit-code 22f2b52 -- .claude/ src/lucy_ng/nus/ src/lucy_ng/cli/pick.py src/lucy_ng/processing/peak_picker.py src/lucy_ng/processing/peak_picker_2d.py` → exit 0. `tests/test_skill_files_unchanged.py` read in full and confirmed non-vacuous (hashes real file bytes, globs a real directory).
4. **Criterion 3 — independently reproduced**, not accepted on report: live CLI run on the real committed fixtures reproduced 115 cross-peaks / 70 `CH_or_CH3` / 45 `CH2` / 0 ambiguous exactly.
5. **Criterion 1's "not a new picker" — confirmed** by reading `cli/jcamp.py` in full: it imports and directly calls `bridge_peak_pick`/`bridge_peak_pick_1d`, both of which delegate to the pre-existing `PeakPicker2D`/`AdaptivePeakPicker`. No new picking algorithm exists anywhere in the diff.

## Human Verification Required

None. All four ROADMAP success criteria are independently, mechanically verifiable and were verified above, either by live command execution or by reading and cross-checking source/test code — no visual, real-time, or subjective judgement call is needed for this phase's goal.

## Gaps Summary

No gaps found blocking phase-goal achievement. One informational item: `.planning/REQUIREMENTS.md`'s Phase-102 checkboxes and traceability table were not updated to reflect completion (still show "Pending"/unchecked) — this is a documentation-sync task, not a code or goal-achievement gap, and does not block phase closure. Recommend updating REQUIREMENTS.md's JCLI-01/JCLI-02 rows to "Complete" as part of phase close-out.

---

*Verified: 2026-07-25T13:35:00Z*
*Verifier: Claude (gsd-verifier)*
</content>
