---
phase: 98
slug: reconstruction-processing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-13
---

# Phase 98 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/nus/ -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~60–120 seconds (full suite; nus/ subset ~a few seconds — CI path is fully mocked) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/nus/ -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

> Every RECON requirement is verified via a CI-safe (mocked subprocess boundary) test — the D-04 decision. The real end-to-end chain is a separate `@pytest.mark.skipif` integration test gated on backend + external-data availability; it is NOT part of the CI feedback loop and is documented under Manual-Only Verifications.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 98-01-01 | 01 | 1 | RECON-04 | — | Fail-loud wrapper aborts on non-zero exit OR empty output file | unit | `pytest tests/nus/test_runner_faillloud.py -q` | ❌ W0 | ⬜ pending |
| 98-02-01 | 02 | 2 | RECON-01 | — | Full stage chain dispatched in correct FnMODE-branched order (mocked binaries) | unit | `pytest tests/nus/test_reconstruct_chain.py -q` | ❌ W0 | ⬜ pending |
| 98-02-02 | 02 | 2 | RECON-02 | — | F2-before-F1 processing enforced; out-of-order raises before any recon runs; ppm axes reversed+calibrated | unit | `pytest tests/nus/test_processing_order.py -q` | ❌ W0 | ⬜ pending |
| 98-03-01 | 03 | 2 | RECON-03 | — | FnMODE 6 (echo-antiecho) vs FnMODE 1 (QF) select correct stage order + phase mode; both 25%/33% densities | unit | `pytest tests/nus/test_fnmode_branching.py -q` | ❌ W0 | ⬜ pending |
| 98-04-01 | 04 | 3 | RECON-05 | — | CLI flags iteration/threshold/virtual-echo present with defaults; convergence/residual stopping wired to SMILE | unit | `pytest tests/nus/test_cli_reconstruct.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Exact task IDs/plan split are planner-owned — this map is the coverage contract, not the final task numbering.*

---

## Wave 0 Requirements

- [ ] `tests/nus/conftest.py` — shared fixtures: subprocess-boundary mock (a single `run_stage()` seam), fake NMRPipe intermediate files (valid + deliberately-truncated/empty), reuse of the Phase-97 `tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc}/` metadata
- [ ] `tests/nus/test_runner_faillloud.py` — stubs for RECON-04 (exit-code + output-non-emptiness)
- [ ] `tests/nus/test_reconstruct_chain.py` — stubs for RECON-01
- [ ] `tests/nus/test_processing_order.py` — stubs for RECON-02
- [ ] `tests/nus/test_fnmode_branching.py` — stubs for RECON-03
- [ ] `tests/nus/test_cli_reconstruct.py` — stubs for RECON-05

*pytest infrastructure already exists — Wave 0 adds fixtures + test stubs only, no framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real end-to-end reconstruction of C20H32O2 exp2/3/4 produces a processed 2D spectrum | RECON-01/02/03 | Requires NMRPipe+SMILE on PATH and the large external `ser` binaries (not in CI, not in repo — D-04) | `pytest tests/nus/test_reconstruct_integration.py -q` on a dev machine with the backend installed; the test is `skipif`-guarded (backend + `$LUCY_NUS_TEST_DATA` external path present). Actual reconstruction-quality (fabricated-peak / ridge) judgement is the Phase-99 QC gate + Phase-100 §8 validation, NOT this phase. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
