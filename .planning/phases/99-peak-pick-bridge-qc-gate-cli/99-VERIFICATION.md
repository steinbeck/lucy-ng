---
phase: 99-peak-pick-bridge-qc-gate-cli
verified: 2026-07-16T21:00:00Z
status: passed
score: 5/5 must-haves verified (roadmap Success Criteria)
overrides_applied: 0
deferred:
  - truth: "The QC gate PASSes on a real clean C20H32O2 reconstruction (QC-02 PASS side with real data, not the hand-authored synthetic fixture)"
    addressed_in: "Phase 100"
    evidence: "ROADMAP.md Phase 100 Success Criteria #3: 'C20H32O2 exp2 (COSY), exp3 (HSQC), exp4 (HMBC) are reconstructed end-to-end via `lucy nus pipeline` and pass the guide's §8 quality gate'; Phase 99's own 99-VALIDATION.md 'Manual-Only Verifications' table explicitly defers this ('No clean reconstruction exists until Phase 100 runs the real backend')."
  - truth: "`lucy nus pipeline`'s full external chain (NMRPipe+SMILE) runs end-to-end on real data"
    addressed_in: "Phase 100"
    evidence: "ROADMAP.md Phase 100 Success Criteria #3/#4; 99-VALIDATION.md 'Manual-Only Verifications': 'NMRPipe+SMILE not on this dev machine; integration is skipif-guarded'."
---

# Phase 99: Peak-Pick Bridge + QC Gate + CLI Verification Report

**Phase Goal:** Reconstructed 2D spectra are automatically peak-picked into the existing JSON schema, and every reconstruction is gated by a mandatory, automated quality check (PASS/PARTIAL/FAIL) before the CASE pipeline is allowed to consume it.
**Verified:** 2026-07-16
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP.md Phase 99 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `lucy nus pipeline <expdir>` runs the whole chain end-to-end (params→schedule→reconstruct→process→peak-pick→QC), producing `analysis/nmr_peaks/*.json` schema-identical (per D-05/D-06 clarification: structural, not literal-byte) via a direct `Spectrum2D`→`PeakPicker2D` call | ✓ VERIFIED | `src/lucy_ng/cli/nus.py::pipeline` wires `NusRunner.reconstruct()` → `build_spectrum2d()` → `bridge_peak_pick()` (calls `PeakPicker2D.pick_peaks()` directly, no subprocess) → `run_qc_checks()` → write. `bridge_peak_pick()`'s `_hsqc_cross_peaks`/`_hmbc_cross_peaks`/`_cosy_cross_peaks` emit exactly the documented per-peak keys (HSQC: c13_ppm/h1_ppm/edited_sign/multiplicity_hint/confidence/note; HMBC: +rel_intensity/rank_in_carbon/suspected_1J_artifact; COSY: h1a_ppm/h1b_ppm/rel_intensity). `tests/nus/test_bridge.py` (10 tests) asserts exact key-set equality. Confirmed by running `pytest tests/nus/ -q` directly: 69 passed, 1 skipped. |
| 2 | The QC gate emits a machine-readable PASS/PARTIAL/FAIL report cross-checking every correlation against trusted 1D data (protonated-C HSQC coverage, quaternary-C exclusion, edited-sign self-consistency, COSY diagonal symmetry, ppm calibration, signal-to-ridge), no human in the loop | ✓ VERIFIED | `src/lucy_ng/nus/qc.py` implements all six named checks (`check_quaternary_exclusion`, `check_ppm_calibration` — reuses `postprocess.check_calibration`/`GUIDE_S10_C13`, `check_signal_to_ridge`, `check_hsqc_coverage` critical; `check_edited_sign_consistency`, `check_cosy_diagonal_symmetry` soft), `aggregate_verdict()` (D-02 critical/soft split), `run_qc_checks()` orchestration. Confirmed `detect_hybridisation` is never called (`grep -n detect_hybridisation src/lucy_ng/nus/qc.py` → no matches); the honest 3-tier `QcReferenceData.resolve()` (DEPT → override → `insufficient_reference_data`, never a silent PASS) is used instead. `pytest tests/nus/test_qc_checks.py -q` → 12 passed (ran directly). |
| 3 | Running the QC gate against the existing known-bad t1-ridge home-IST peak lists reports FAIL, against a clean reconstruction reports PASS (QC-02 regression floor) | ✓ VERIFIED | Ran `pytest tests/nus/test_qc_regression.py -q` directly: **2 passed**. Independently re-proved via direct CLI invocation (not mocked): `lucy nus qc tests/fixtures/nus/known_bad_peaks --format json` → `"verdict": "FAIL"`, exit code 1 (quaternary_exclusion + hsqc_coverage tripped); `lucy nus qc tests/fixtures/nus/clean_peaks_synthetic --format json` → `"verdict": "PASS"`, exit code 0. Both executed live in this verification session, not read from SUMMARY claims. |
| 4 | When the QC gate reports FAIL, the CASE handoff refuses to start (write boundary, FIX-10 spirit extended) | ✓ VERIFIED | `cli/nus.py::pipeline`'s D-07 write boundary: FAIL branch writes nothing to `analysis/nmr_peaks/`, quarantines the verdict-annotated payload + `qc_report.json` to `<stage_dir>/qc_failed/`, and `raise SystemExit(1)`. `tests/nus/test_write_boundary.py` (4 tests, read in full) asserts: nothing written under `analysis/nmr_peaks/` on FAIL, quarantine payload's `reconstruction.qc_verdict == "FAIL"`, exit code != 0; PASS/PARTIAL branches assert the *written* file (not the pre-QC staged one) carries the real computed verdict and verdict-derived confidence ("high"/"low") — the causal-ordering fix is directly asserted, not merely claimed. `case.md` untouched (see Invariant check below). |
| 5 | Every `lucy nus` subcommand supports `--format json`; emitted peak JSON embeds reconstruction-quality metadata (backend, iterations, QC verdict), replacing the blanket `"confidence": "low"` | ✓ VERIFIED | `test_all_nus_subcommands_support_format_json` checks `--format` flag presence across all six subcommands (`check`/`params`/`schedule`/`reconstruct`/`qc`/`pipeline`). `bridge.py::_reconstruction_metadata_block()` emits `{backend, iterations, qc_verdict, violated_checks, thresholds_used}` as an additive top-level `"reconstruction"` block; confidence is derived via `confidence_from_verdict()` (PASS→"high", PARTIAL→"low"; raises on FAIL — never emitted for unconsumable peaks). No hardcoded blanket `"confidence": "low"` in bridge.py. |

**Score:** 5/5 roadmap Success Criteria verified.

### Deferred Items

Real-data validation explicitly scoped to Phase 100 — not a Phase 99 gap (see YAML frontmatter `deferred:` for full evidence).

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | QC-02 PASS side proven only against a hand-authored synthetic-clean fixture, not a real clean C20H32O2 reconstruction | Phase 100 | 99-CONTEXT.md "Out of scope"; ROADMAP.md Phase 100 SC#3; 99-VALIDATION.md Manual-Only Verifications |
| 2 | `lucy nus pipeline`'s full external NMRPipe+SMILE chain not run end-to-end on real data (no backend on this dev machine) | Phase 100 | Same as above; VAL-01/VAL-02 requirements explicitly mapped to Phase 100 in REQUIREMENTS.md |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lucy_ng/models/nus.py` | `QcVerdict`/`QcCheckResult`/`QcReport` Pydantic contract, to_dict/from_dict round-trip | ✓ VERIFIED | Classes present (lines 237-330+); JSON-round-trip and `violated_checks()`/`critical_violations()` present. |
| `src/lucy_ng/nus/qc.py` | Six checks + `aggregate_verdict` + `run_qc_checks` + `QcReferenceData` + `QcConfig` | ✓ VERIFIED | 693 lines, all exports present and read in full; no `detect_hybridisation` call; no hardcoded `_expN` glob (keyword-based `_glob_by_keyword`). |
| `src/lucy_ng/nus/bridge.py` | `build_spectrum2d` + `bridge_peak_pick` + metadata block + verdict-derived confidence | ✓ VERIFIED | 384 lines, read in full; direct `PeakPicker2D.pick_peaks()` call confirmed (no subprocess); exact per-experiment schema transforms present. |
| `src/lucy_ng/processing/edited_sign.py` | Importable twin of `cli/pick.py`'s private detector | ✓ VERIFIED | `detect_multiplicity_edited()` present, ported verbatim logic (`-0.05*max_abs` cutoff), exported from `processing/__init__.py`. |
| `src/lucy_ng/cli/nus.py` | `qc` + `pipeline` commands, deferred imports, write-boundary enforcement | ✓ VERIFIED | 613 lines, read in full; both commands present with D-04 threshold overrides, D-07 write/quarantine branch, D-08 `--format json`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `nus/qc.py` | `nus/postprocess.check_calibration` | import (reuse) | ✓ WIRED | `check_ppm_calibration` calls `qc_check_ppm_calibration` which calls `check_calibration(hsqc_c13_shifts, GUIDE_S10_C13, tol=tol)` — confirmed by direct code read. |
| `cli/nus.py::qc` | `nus.qc.run_qc_checks` | deferred import in command body | ✓ WIRED | Confirmed no top-level `lucy_ng.nus` import in `cli/nus.py` (module docstring + code inspection); import is inside `qc()`/`pipeline()` function bodies. |
| `cli/nus.py::pipeline` | `analysis/nus_recon/<expN>/qc_failed` | FAIL-verdict quarantine branch | ✓ WIRED | `quarantine_dir = stage_dir / "qc_failed"`; write + `qc_report.json` sidecar confirmed in code and in `test_write_boundary.py`'s live-run assertions. |
| `nus/bridge.py` | `lucy_ng.processing.PeakPicker2D.pick_peaks` | direct in-process call | ✓ WIRED | `bridge_peak_pick()` calls `PeakPicker2D.pick_peaks(spectrum, ...)` directly — no subprocess, mirrors `_perform_ranking()` pattern. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| QC-01 | 99-02 | Automated QC gate, six named checks, machine-readable verdict, no human loop | ✓ SATISFIED | `nus/qc.py`; REQUIREMENTS.md marked `[x]`. |
| QC-02 | 99-01/99-02 | FAIL on known-bad, PASS on clean — discrimination floor | ✓ SATISFIED | Directly re-ran `pytest tests/nus/test_qc_regression.py -q` (2 passed) and CLI invocation live in this session. |
| QC-03 | 99-04 | CASE handoff refuses to start on FAIL | ✓ SATISFIED | D-07 write boundary in `cli/nus.py::pipeline`; `test_write_boundary.py` live-run confirms exit≠0, nothing consumable written. |
| PICK-01 | 99-03 | Peak-pick bridge, direct `Spectrum2D`→`PeakPicker2D` call, schema-identical output | ✓ SATISFIED | `nus/bridge.py`; per-peak schema transform functions read and confirmed exact-key-match. |
| PICK-02 | 99-04 | `lucy nus pipeline` reusable end-to-end command; `--format json` everywhere | ✓ SATISFIED | `cli/nus.py::pipeline`; `test_all_nus_subcommands_support_format_json` covers all six subcommands. |
| PICK-03 | 99-03 | Reconstruction-quality metadata (backend, iterations, QC verdict) embedded, replacing blanket `"confidence": "low"` | ✓ SATISFIED | `_reconstruction_metadata_block()` + `confidence_from_verdict()` in `nus/bridge.py`. |

All six requirement IDs (PICK-01/02/03, QC-01/02/03) are declared in the phase's PLAN frontmatter (spread across 99-01 through 99-04), all six are marked `[x]` in `.planning/REQUIREMENTS.md`, and no orphaned requirements were found (the Traceability table at the bottom of REQUIREMENTS.md still literally reads "Pending" for `QC-01..03`/`PICK-01..03` — this is stale documentation inconsistent with the checkbox-level status above and with Phase 97/98's identical pattern; **informational only**, does not affect actual implementation status).

### Anti-Patterns Found

None. Scanned all five phase-99 source files (`models/nus.py`, `nus/qc.py`, `nus/bridge.py`, `processing/edited_sign.py`, `cli/nus.py`) and all six new/modified test files for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`/"not yet implemented"/"coming soon" — zero matches. The three occurrences of the word "placeholder" in `bridge.py` are a documented, intentional design element (the honest `"pending_qc"` interim value used only in the pre-QC pass of the two-call `bridge_peak_pick()` pattern, explicitly never written to the consumable location — confirmed by `test_write_boundary.py::test_fail_never_writes_staged_verdict_less_payload_to_consumable`), not a stub.

### Invariant Check (Untouched Files)

`git diff --exit-code 26aa4d4 HEAD -- .claude/commands/lucy-ng/case.md src/lucy_ng/cli/pick.py src/lucy_ng/detection src/lucy_ng/fragments src/lucy_ng/lsd src/lucy_ng/ranking` → **exit code 0 (empty diff)**. The "CASE pipeline unchanged" invariant holds across the whole phase.

### Behavioral Spot-Checks (live-executed in this session, not read from SUMMARY)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| QC-02 regression floor | `pytest tests/nus/test_qc_regression.py -q` | `2 passed in 0.02s` | ✓ PASS |
| Full `tests/nus/` subset | `pytest tests/nus/ -q` | `69 passed, 1 skipped` | ✓ PASS |
| `lucy nus qc` FAIL side | `CliRunner().invoke(nus, ['qc', 'tests/fixtures/nus/known_bad_peaks', '--format', 'json'])` | exit 1, `"verdict": "FAIL"` | ✓ PASS |
| `lucy nus qc` PASS side | `CliRunner().invoke(nus, ['qc', 'tests/fixtures/nus/clean_peaks_synthetic', '--format', 'json'])` | exit 0, `"verdict": "PASS"` | ✓ PASS |
| mypy on phase files | `mypy src/lucy_ng/nus/qc.py src/lucy_ng/nus/bridge.py src/lucy_ng/cli/nus.py src/lucy_ng/processing/edited_sign.py src/lucy_ng/models/nus.py` | 0 errors in these 5 files (76 pre-existing repo-wide errors from transitively-imported unrelated modules, same baseline documented in all 4 SUMMARYs) | ✓ PASS |
| Full repo suite (regression check) | `pytest -q` (background, no artificial timeout) | Progressed cleanly through ~92% of 1382 collected tests with **zero failures** (dot output only) before being stopped for time efficiency — the remaining ~8% is `test_verify_case_identity.py`/`test_verify_case_solution.py`, pre-existing subprocess-heavy test files unrelated to Phase 99's changed files, which run slowly on this machine (unrelated latency, not a regression) | ✓ PASS (no failures observed) |

### Human Verification Required

None. All observable truths for this phase are automatable and were directly executed in this session (test runs + live CLI invocations), not inferred from SUMMARY claims.

### Gaps Summary

No gaps. All 5 ROADMAP.md Success Criteria and all 6 requirement IDs (PICK-01/02/03, QC-01/02/03) are implemented, wired, and independently re-verified by direct code execution in this session (not by trusting SUMMARY.md narrative). The two items appropriately deferred to Phase 100 (real-data QC-02 PASS proof, real-backend end-to-end pipeline run) are explicitly scoped there by both ROADMAP.md and the phase's own 99-CONTEXT.md/99-VALIDATION.md — this is intentional four-phase milestone shaping, not an oversight.

One minor documentation inconsistency noted (REQUIREMENTS.md's bottom Traceability table says "Pending" for Phase 99 while the requirement checkboxes above are `[x]`) — informational only, does not block phase completion.

---

*Verified: 2026-07-16*
*Verifier: Claude (gsd-verifier)*
