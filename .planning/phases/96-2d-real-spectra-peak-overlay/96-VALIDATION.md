---
phase: 96
slug: 2d-real-spectra-peak-overlay
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-11
---

# Phase 96 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 96-RESEARCH.md §Validation Architecture (empirically verified against real CASE1 + repo 2D datasets).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`[tool.pytest.ini_options]` in `pyproject.toml`) |
| **Config file** | `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| **Quick run command** | `pytest tests/test_webview_api.py -k spectra_2d -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30–60 s (webview subset ~5 s; 2D real-data render ~0.1 s/plot) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_webview_api.py -k spectra_2d`
- **After every plan wave:** Run `pytest tests/test_webview_api.py`
- **Before `/gsd:verify-work`:** Full suite (`pytest`) must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner (step 8). Each row below maps a phase requirement /
> success criterion to its automated proof; the planner MUST attach these to the concrete
> task IDs it creates. `❌ W0` = test file/scaffold created in Wave 0.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {96-0X-XX} | 0X | 0 | SP2-01 | — | N/A | scaffold | `pytest tests/test_webview_api.py -k spectra_2d --collect-only` | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | SP2-01 | — | N/A | integration | `pytest tests/test_webview_api.py -k "spectra_2d and real"` | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | SP2-01 | — | N/A | unit | `pytest tests/test_webview_api.py -k "apply_nmr_axes_2d"` (xlim[0]>xlim[1] AND ylim[0]>ylim[1]) | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | SP2-01 | — | N/A | unit | `pytest tests/test_webview_api.py -k "hmbc_flag_color"` (source-palette assertion, `inspect.getsource`) | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | SC3 (perf) | — | N/A | perf | `pytest tests/test_webview_api.py -k "render_under_budget"` (assert < 1 s) | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | SC3 (cache) | — | N/A | unit | `pytest tests/test_webview_api.py -k "cache_hit_no_rerender"` (monkeypatch render, assert not called on 2nd unchanged-mtime request) | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | SC4 | — | N/A | unit | `pytest tests/test_webview_api.py -k "cache_bounded"` (assert cache len ≤ 3 after N requests) | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | SP-02 | — | N/A | integration | `pytest tests/test_webview_api.py -k "spectra_2d and placeholder"` (absent manifest / stale path / no match → placeholder PNG, never 500) | ❌ W0 | ⬜ pending |
| {96-0X-XX} | 0X | 1+ | WV-08 | — | N/A | unit | existing `try/except ImportError: pytest.skip` guard applied to new test methods | ✅ (pattern exists) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New `TestSpectraEndpoint2D` class (or extend `TestSpectraEndpoint`) in
      `tests/test_webview_api.py` — RED-by-skip scaffold mirroring the Phase 95 pattern
      (WV-08 import guard; `CASE1_ROOT.is_dir()` skip guard for real-data tests).
- [ ] Hand-authored `analysis/peaks/{hsqc,hmbc,cosy}.json` fixtures (to the locked Phase 94
      schema) for overlay-marker position + HMBC flag-colour assertions — mirrors the
      existing `tables_analysis_dir` hand-authored-to-locked-schema fixture pattern.
- [ ] Reuse existing `CASE1_ROOT` fixture (confirmed to contain real HSQC `/6`, HMBC `/7`,
      COSY `/5` 2D experiments — no new dataset needed).

*Note (from research): do NOT hand-author a fake 2D `pdata/1/2rr`. The acqu2s-inclusion
selector needs a readable real `2rr` to reach `BrukerReader.read_2d()` and match
`experiment_type`; test that logic against the real CASE1/repo datasets with a skip-guard.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Contour + overlay visually reads correctly in the browser 2D-Spectra tab (aromatic region top-left, open-circle markers on real signal, HMBC flag colours, COSY diagonal) | SP2-01 / SC1 / SC2 | Pixel-level visual quality can't be fully asserted in pytest; mirrors the Phase 95 manual browser checkpoint plan | Serve `lucy webview serve <CASE1 analysis dir>`, open 2D Spectra tab, confirm HSQC/HMBC/COSY render with reversed axes, cross-peaks on signal, HMBC colour-coding, COSY diagonal |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (new 2D test class + peak-JSON fixtures)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
