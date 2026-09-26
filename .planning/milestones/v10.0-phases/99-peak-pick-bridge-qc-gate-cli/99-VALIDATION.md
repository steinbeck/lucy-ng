---
phase: 99
slug: peak-pick-bridge-qc-gate-cli
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-16
---

# Phase 99 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Detailed Validation Architecture lives in `99-RESEARCH.md`; the Per-Task
> Verification Map below is populated from the finalized PLAN.md task IDs.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `pytest tests/nus/ -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~90 seconds (full suite ~1329 tests as of Phase 98) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/nus/ -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 99-01-01 | 01 | 1 | QC-01/PICK-03 | T-99-02 | Verdict serializes as plain string; models round-trip | unit | `pytest tests/nus/test_bridge_metadata.py -q` (+ model round-trip inline) | ❌ W0 | ⬜ pending |
| 99-01-02 | 01 | 1 | QC-02 | T-99-01/T-99-03 | Known-bad fixture trips quaternary/ridge; clean fixture clean | fixture | fixture-structure assertions (inline python) | ❌ W0 | ⬜ pending |
| 99-01-03 | 01 | 1 | QC-01/QC-02/QC-03/PICK-01/PICK-02/PICK-03 | — | RED-by-skip stubs collectable backend-less | scaffold | `pytest tests/nus/ --collect-only -q` | ❌ W0 | ⬜ pending |
| 99-02-01 | 02 | 2 | QC-01 | T-99-03 | 6 checks peak-list-only; no silent PASS on missing reference | unit | `pytest tests/nus/test_qc_checks.py -q` | ❌ W0 | ⬜ pending |
| 99-02-02 | 02 | 2 | QC-01/QC-02 | T-99-01 | aggregate_verdict + run_qc_checks; known-bad⇒FAIL, clean⇒PASS | unit/regression | `pytest tests/nus/test_qc_regression.py -q` | ❌ W0 | ⬜ pending |
| 99-03-01 | 03 | 2 | PICK-01 | T-99-10/T-99-11 | build_spectrum2d fail-loud; cli/pick.py byte-unchanged | unit | `pytest tests/nus/test_bridge.py -q` (+ `git diff --exit-code cli/pick.py`) | ❌ W0 | ⬜ pending |
| 99-03-02 | 03 | 2 | PICK-01/PICK-03 | T-99-08/T-99-09 | Per-experiment schema + small metadata block + verdict confidence | unit | `pytest tests/nus/test_bridge.py tests/nus/test_bridge_metadata.py -q` | ❌ W0 | ⬜ pending |
| 99-04-01 | 04 | 3 | PICK-02/QC-02 | T-99-06 | `lucy nus qc` FAIL⇒exit≠0, PASS⇒exit 0, --format json | integration | `pytest tests/nus/test_cli_pipeline.py -q -k qc` | ❌ W0 | ⬜ pending |
| 99-04-02 | 04 | 3 | PICK-02/QC-03 | T-99-12/T-99-13 | FAIL quarantines + exits≠0; PASS/PARTIAL write consumable; case.md untouched | unit/integration | `pytest tests/nus/test_write_boundary.py tests/nus/test_cli_pipeline.py -q` | ❌ W0 | ⬜ pending |

*Regression floor:* the QC-02 discrimination test (`test_qc_regression.py`: known-bad ⇒ FAIL, synthetic-clean ⇒ PASS) is the load-bearing gate. No 3 consecutive tasks lack an automated verify.

---

## Wave 0 Requirements

- [ ] `tests/nus/test_qc_checks.py` — RED-by-skip stubs, one class per QC check (QC-01)
- [ ] `tests/nus/test_qc_regression.py` — known-bad⇒FAIL, clean-synthetic⇒PASS discrimination (QC-02)
- [ ] `tests/nus/test_bridge.py` — Spectrum2D construction + schema-identical peaks (PICK-01)
- [ ] `tests/nus/test_bridge_metadata.py` — metadata block + verdict-derived confidence (PICK-03)
- [ ] `tests/nus/test_write_boundary.py` — PASS/PARTIAL write vs FAIL quarantine+exit (QC-03/D-07)
- [ ] `tests/nus/test_cli_pipeline.py` — qc/pipeline commands + --format json everywhere (PICK-02/D-08)
- [ ] `src/lucy_ng/models/nus.py` — QcVerdict/QcCheckResult/QcReport contract (interface for Plans 02-04)
- [ ] `tests/fixtures/nus/known_bad_peaks/` — real home-IST lists (QC-02 FAIL side) + trusted-1D reference lists
- [ ] `tests/fixtures/nus/clean_peaks_synthetic/` — **hand-authored synthetic clean set** (QC-02 PASS side — load-bearing; no real clean C20H32O2 reconstruction until Phase 100)
- [ ] `tests/nus/conftest.py` — `known_bad_peaks_dir`/`clean_peaks_dir` fixtures + KNOWN_QUATERNARY_SHIFTS

*pytest infrastructure already exists (tests/nus/ from Phase 97/98) — no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real clean-reconstruction PASS on C20H32O2 exp2/3/4 | QC-02 (PASS side, real data) | No clean reconstruction exists until Phase 100 runs the real backend; unit tests use the synthetic clean fixture | Deferred to Phase 100 / VAL — run `lucy nus pipeline` on real exp3 and confirm PASS |
| `lucy nus pipeline` full external chain end-to-end | PICK-02 (real backend) | NMRPipe+SMILE not on this dev machine; integration is `skipif`-guarded | Phase 100 on a backend-equipped host |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (known-bad + synthetic-clean fixtures + QC models contract)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned
