---
phase: 97
slug: backend-integration-params-schedule
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-12
---

# Phase 97 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (per `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing, no new config needed) |
| **Quick run command** | `pytest tests/test_nus_params.py tests/test_nus_schedule.py tests/test_nus_backends.py tests/test_cli_nus.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~5–15 seconds (NUS subset); full suite per existing baseline |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_nus_*.py tests/test_cli_nus.py -x`
- **After every plan wave:** Run `pytest` (full suite)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds (NUS subset)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| W0 fixtures | 00 | 0 | NUS-02/03/04 | — | N/A | fixture | `test -d tests/fixtures/nus/exp2_cosy` | ❌ W0 | ⬜ pending |
| NUS-01 detect | backends | 1 | NUS-01 | T-97-02 | probe uses fixed arg list, no shell=True | unit | `pytest tests/test_nus_backends.py -x` | ❌ W0 | ⬜ pending |
| NUS-01 check CLI | cli | 2 | NUS-01 | T-97-01 | `click.Path`/resolve on expdir | CLI | `pytest tests/test_cli_nus.py -k check -x` | ❌ W0 | ⬜ pending |
| NUS-02 params | params | 1 | NUS-02 | T-97-01 | Pydantic v2 field validation | unit | `pytest tests/test_nus_params.py -x` | ❌ W0 | ⬜ pending |
| NUS-03 schedule | schedule | 1 | NUS-03 | — | FnMODE-derived hard assertion | unit | `pytest tests/test_nus_schedule.py -x` | ❌ W0 | ⬜ pending |
| NUS-03 order | schedule | 1 | NUS-03 | — | never sort nuslist | unit | `pytest tests/test_nus_schedule.py -k acquisition_order -x` | ❌ W0 | ⬜ pending |
| NUS-04 json | cli | 2 | NUS-04 | T-97-01 | schema-valid JSON | CLI | `pytest tests/test_cli_nus.py -k "params or schedule" -x` | ❌ W0 | ⬜ pending |
| NUS-05 import-safe | cli | 2 | NUS-05 | — | lazy imports, core dep-free | unit | `pytest tests/test_cli_main.py -k nus_import_safe -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/nus/exp2_cosy/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}` — copy from real C20H32O2 exp2 (D-03 + research SF/OFFSET correction)
- [ ] `tests/fixtures/nus/exp3_hsqc/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}` — copy from real C20H32O2 exp3
- [ ] `tests/fixtures/nus/exp4_hmbc/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s}` — copy from real C20H32O2 exp4
- [ ] `tests/test_nus_params.py` — stubs for NUS-02
- [ ] `tests/test_nus_schedule.py` — stubs for NUS-03
- [ ] `tests/test_nus_backends.py` — stubs for NUS-01
- [ ] `tests/test_cli_nus.py` — stubs for NUS-01, NUS-04, NUS-05
- [ ] Framework install: none — pytest already configured project-wide

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `lucy nus check` reports "installed but not sourced" vs "not installed" on a *real* NMRPipe install | NUS-01 | No NMRPipe on this dev machine or CI; the positive-detection path can only be exercised on a machine with the toolchain | On a machine with NMRPipe sourced: `lucy nus check` → exit 0 + available; with NMRPipe installed but env not sourced: → distinct diagnostic. Deferred live-install verification (research Assumption A2). |

*Negative-detection (not-installed) path IS automated; only the positive/sourced path is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
