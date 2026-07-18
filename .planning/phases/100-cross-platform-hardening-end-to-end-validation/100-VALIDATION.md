---
phase: 100
slug: cross-platform-hardening-end-to-end-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-18
---

# Phase 100 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing suite, 1373 passing as of Phase 99) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/nus -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~60–120 seconds (full); backend-gated integration tests skip without NMRPipe on PATH |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/nus -q`
- **After every plan wave:** Run `pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 100-01-01 | 01 | 1 | PORT-01 | — | preflight blocks reconstruct/pipeline on missing backend binary before any external stage runs | unit (mocked platform/subprocess) | `pytest tests/nus/test_preflight.py -q` | ❌ W0 | ⬜ pending |
| 100-01-02 | 01 | 1 | PORT-01 | — | soft Rosetta/x86 condition warns, does not block | unit (mocked `sysctl.proc_translated`/`platform.machine`) | `pytest tests/nus/test_preflight.py -q` | ❌ W0 | ⬜ pending |
| 100-02-01 | 02 | 1 | PORT-02 | — | `docs/NUS-PORTABILITY.md` exists with all three platform rows + WSL2 marked untested | doc-existence assertion | `pytest tests/nus/test_portability_doc.py -q` | ❌ W0 | ⬜ pending |
| 100-03-01 | 03 | 2 | VAL-01 | — | real exp2/3/4 reconstruction clears §8 via QC PASS or soft-only PARTIAL | manual / backend-gated | `lucy nus pipeline <expdir>` + `lucy nus qc` | N/A | ⬜ pending |
| 100-03-02 | 03 | 2 | VAL-02 | — | fresh `/lucy-ng:case C20H32O2` terminates with a finite rankable set | manual / agentic | `/lucy-ng:case C20H32O2` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. Task IDs are indicative — the planner finalizes them.*

---

## Wave 0 Requirements

- [ ] `tests/nus/test_preflight.py` — PORT-01 preflight logic with mocked `platform.machine()`, `sysctl.proc_translated`, `shutil.which`, `csh` presence (native arm64 / x86-under-Rosetta / missing-binary / missing-csh matrix)
- [ ] `tests/nus/test_portability_doc.py` — assert `docs/NUS-PORTABILITY.md` exists and contains the three platform rows + the "documented, untested" WSL2 marker
- [ ] Existing `tests/nus/conftest.py` fixtures (known-bad QC-02 regression dir is already repo-committed at `tests/fixtures/nus/known_bad_peaks/` — VAL-01 overwriting the external C20H32O2 files does NOT break these)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Native NMRPipe+SMILE reconstruction of real exp2/3/4 clears §8 | VAL-01 | Backend (NMRPipe+SMILE) is not in CI; requires the real Bruker `ser` data + a local install | Install native NMRPipe+SMILE on this Mac → `lucy nus check` green → `lucy nus pipeline` on exp2/3/4 → `lucy nus qc` → PASS or soft-only PARTIAL + brief chemist confirm; record verdict in `100-VALIDATION` / a VALIDATION artifact |
| Fresh `/lucy-ng:case C20H32O2` converges | VAL-02 | Full agentic CASE run; not a unit test; `case.md` runs unmodified | Run `/lucy-ng:case C20H32O2` on the newly reconstructed peak lists; success = LSD terminates (no ~10⁶ timeout) + finite rankable set (correct structure top = bonus) |

---

## Validation Sign-Off

- [ ] All CI-testable tasks (PORT-01 preflight, PORT-02 doc) have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (VAL tasks are inherently manual/backend-gated — flagged explicitly, not silently skipped)
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
