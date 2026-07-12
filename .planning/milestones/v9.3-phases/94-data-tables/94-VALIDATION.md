---
phase: 94
slug: data-tables
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-09
---

# Phase 94 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 94-RESEARCH.md "## Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥7.0 + `fastapi.testclient.TestClient` (httpx-backed) — same as existing webview tests |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| **Quick run command** | `pytest tests/test_webview_api.py -x -q` |
| **Full suite command** | `pytest --cov=lucy_ng` |
| **Estimated runtime** | ~20 seconds (quick), ~2–3 min (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_webview_api.py -x -q`
- **After every plan wave:** Run `pytest --cov=lucy_ng`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 94-00-01 | 00 | 0 | TBL-01/02/03 | — | fixtures scoped under temp `analysis_dir` | fixture | `pytest tests/test_webview_api.py -x -q` | ❌ W0 | ⬜ pending |
| 94-tables-carbon | — | ≥1 | TBL-01 | — | JSON parsed defensively, read scoped to `analysis_dir` | integration | `pytest tests/test_webview_api.py::TestTablesEndpoint -x` | ❌ W0 | ⬜ pending |
| 94-tables-corr | — | ≥1 | TBL-02 | — | HMBC `flag` preserved unmodified; waiting on malformed | integration | `pytest tests/test_webview_api.py::TestTablesEndpoint -x` | ❌ W0 | ⬜ pending |
| 94-tables-constraints | — | ≥1 | TBL-03 | — | highest `iteration_(\d+)` + mtime tiebreak; `; `-strip → json.loads | integration | `pytest tests/test_webview_api.py::TestTablesEndpoint::test_constraints_selects_highest_iteration -x` | ❌ W0 | ⬜ pending |
| 94-tables-degrade | — | ≥1 | TBL-01/02/03 (SC4) | — | absent/partial file → `state:"waiting"`, HTTP 200, never 500 | integration | `pytest tests/test_webview_api.py::TestTablesEndpoint::test_malformed_json_returns_waiting -x` | ❌ W0 | ⬜ pending |
| 94-frontend-xss | — | ≥2 | (carried) | XSS | no `innerHTML` of server content | static-scan | `pytest tests/test_webview_api.py::TestMarkdownRendererSafety::test_no_innerhtml_in_source -x` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Test fixture(s) in `tests/test_webview_api.py` (or `tests/conftest.py`, matching the existing `live_analysis_dir` / `final_analysis_dir` structure): a temp `analysis_dir` containing hand-authored `peaks/carbon_signals.json`, `peaks/hsqc.json`, `peaks/hmbc.json`, `peaks/cosy.json` matching the CONTEXT.md schema — **do NOT copy any existing on-disk file; none matches the canonical schema (RESEARCH Assumptions A1–A5)**.
- [ ] Multi-iteration `iteration_NN[_family]/compound.lsd` fixture set: at least one family-suffixed dir (e.g. `iteration_02_foo`) higher-numbered than a bare `iteration_01`, each with a real-shaped CONSTRAINT INVENTORY v2 block (adaptable from the CASE4 example quoted in RESEARCH), to exercise D-02 selection.
- [ ] `tests/test_webview_api.py::TestTablesEndpoint` — new test class following `TestStatusEndpoint`/`TestLogEndpoint`/`TestStructuresEndpoint`, with the WV-08 `try/except ImportError: pytest.skip(...)` import-safety pattern.
- [ ] No new framework install needed — `fastapi` / `httpx` / `pytest` already declared and installed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HMBC row colouring, per-table captions (note + counts), compact-intensity `M`/`K` suffixes render correctly in the Tables tab | TBL-02/D-03/D-04/D-05 | Visual rendering + CSS-class colouring cannot be asserted from Python; follows 93-CONTEXT.md D-04 two-layer precedent | Serve `lucy webview serve <analysis_dir>`, open Tables tab, confirm colour classes on HMBC rows, captions above each table, intensity shown as `5.6M`/`1.5M` not raw |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
