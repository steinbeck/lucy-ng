---
phase: 99
slug: peak-pick-bridge-qc-gate-cli
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 99 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Detailed Validation Architecture lives in `99-RESEARCH.md`; the planner fills the
> Per-Task Verification Map from the finalized PLAN.md task IDs.

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
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

*Populated by the planner from finalized PLAN.md task IDs. Every QC-check task and the bridge task must map to a unit test; the QC-02 discrimination test (known-bad ⇒ FAIL, clean-synthetic ⇒ PASS) is the regression floor.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 99-01-01 | 01 | 1 | QC-01/QC-02 | — | Fabricated cross-peak never written as consumable peak | unit | `pytest tests/nus/test_qc.py -q` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/nus/test_bridge.py` — stubs for PICK-01/PICK-02/PICK-03
- [ ] `tests/nus/test_qc.py` — stubs for QC-01/QC-02/QC-03 (one per check + the discrimination test)
- [ ] `tests/nus/conftest.py` — shared fixtures: pointer to the real known-bad home-IST peak lists (QC-02 FAIL side) + a **hand-authored synthetic clean peak-list set** (QC-02 PASS side — no real clean C20H32O2 reconstruction exists until Phase 100, so this synthetic fixture is load-bearing)
- [ ] trusted-1D reference fixtures (13C/1H lists) for the QC checks that cross-check against 1D

*pytest infrastructure already exists (tests/nus/ from Phase 97/98) — no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real clean-reconstruction PASS on C20H32O2 exp2/3/4 | QC-02 (PASS side) | No clean reconstruction exists until Phase 100 runs the real backend; unit tests use a synthetic clean fixture | Deferred to Phase 100 / VAL — run `lucy nus pipeline` on real exp3 and confirm PASS |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (known-bad + synthetic-clean fixtures)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
