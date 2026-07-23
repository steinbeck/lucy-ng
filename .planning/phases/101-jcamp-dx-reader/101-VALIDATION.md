---
phase: 101
slug: jcamp-dx-reader
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 101 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 101-RESEARCH.md § Validation Architecture (HIGH confidence).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing project standard) |
| **Config file** | existing `pyproject.toml` (unchanged by this phase) |
| **Quick run command** | `pytest tests/readers/test_jcamp.py tests/readers/test_jcampdx_decode.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~5 s quick / full suite ~3 min |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/readers/test_jcamp.py tests/readers/test_jcampdx_decode.py -x`
- **After every plan wave:** Run `pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds (quick), ~180 seconds (full)

---

## Per-Task Verification Map

*(Seed map — task IDs are assigned by the planner; each PLAN.md task must carry an `<automated>` verify command drawn from the requirement rows below, or declare a Wave-0 dependency.)*

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| JC-04 | Hand-authored DIF/SQZ/DUP/PAC mini-vector decodes to expected integers (`"0A00N%Sl"` → `[100,105,105,102]`), independent of our own decoder | unit (independent oracle) | `pytest tests/readers/test_jcampdx_decode.py::test_hand_authored_mini_vector -x` | ❌ W0 | ⬜ pending |
| JC-01 | 2D NTUPLES (HSQC/HMBC/COSY) DIFDUP pages assemble into `Spectrum2D` with correct `(n_f1, n_f2)` shape, no external binary | integration | `pytest tests/readers/test_jcamp.py::test_read_2d_shape -x` | ❌ W0 | ⬜ pending |
| JC-02 | Reader-internal fail-loud range/reversed assertion rejects Hz-looking / non-descending axes | unit (reader assertion) | `pytest tests/readers/test_jcamp.py::test_read_2d_ppm_axis_assertion -x` | ❌ W0 | ⬜ pending |
| JC-02 | ppm axes cross-checked against 1D reference peaks within tolerance (¹H ≤0.05 ppm, ¹³C ≤0.10 ppm) — catches the 0.447 ppm naive-divisor bug class | integration (load-bearing) | `pytest tests/readers/test_jcamp.py::test_read_2d_ppm_axes_match_1d_reference -x` | ❌ W0 | ⬜ pending |
| JC-03 | 1D JCAMP (¹H, ¹³C) reads into `Spectrum1D` via the same reader module | integration | `pytest tests/readers/test_jcamp.py::test_read_1d -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/readers/test_jcampdx_decode.py` — D-08 layer 1: hand-authored decode oracle (JC-04)
- [ ] `tests/readers/test_jcamp.py` — D-08 layer 2: integration tests on trimmed fixture (JC-01, JC-02, JC-03, JC-04)
- [ ] `tests/fixtures/jcamp/` — trimmed real 2D `.dx` fixture (~8-16 real signal pages, header pruned to consumed keys) + copies of the two real 1D reference `.dx` files (JC-02 cross-check needs the 1D references per D-03)
- [ ] Wave-0 spot-check: decode one real page of COSY and NOESY (RESEARCH Open Question 1 / Assumption A3) before committing to "one 2D code path for all experiment types"

*Framework itself — pytest — already exists; no new test-infrastructure install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | All Phase-101 behaviors have automated verification (the fixture + hand-oracle make the correctness claim CI-checkable — the load-bearing point of JC-04). |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (decode oracle, integration test, fixture)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (quick)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
