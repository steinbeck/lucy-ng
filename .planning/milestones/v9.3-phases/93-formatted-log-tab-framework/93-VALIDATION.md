---
phase: 93
slug: formatted-log-tab-framework
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-07
---

# Phase 93 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/test_webview_api.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_webview_api.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 93-01/T1 | 01 | 1 | TAB-01 | T-93-03 (MIME) | `/webview.js` served with explicit `media_type` | unit | `pytest tests/test_webview_api.py -q` | ✅ | ⬜ pending |
| 93-01/T2 | 01 | 1 | TAB-01 | — | `webview.js` present in wheel artifact glob | unit | `pytest tests/test_webview_api.py -q` | ✅ | ⬜ pending |
| 93-02/T1 | 02 | 2 | TAB-01 | — | Tab switch shows one panel, no reload; left column persists | unit | `pytest tests/test_webview_api.py -q` | ✅ | ⬜ pending |
| 93-02/T2 | 02 | 2 | LOG-01 | T-93-01 (XSS) | Markdown renders as literal escaped text; static scan finds no `innerHTML` of server content | unit | `pytest tests/test_webview_api.py -q` | ✅ | ⬜ pending |
| 93-03/T1 | 03 | 3 | LOG-01 / TAB-01 | T-93-01 (XSS) | Browser: XSS payload escapes, tab switching works, h3-vs-body hierarchy readable | manual | `checkpoint:human-verify` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. Rows verified against the 3 finished plans by gsd-plan-checker.*

---

## Wave 0 Requirements

- [ ] Static-source-scan test asserting `webview.js` contains no `innerHTML` assignment of server content (automatable XSS-discipline guard)
- [ ] `/webview.js` route smoke test (200 + JS content-type) added to `tests/test_webview_api.py` under WV-08 import-safety

*Existing pytest infrastructure covers the automatable phase requirements; no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `# <img src=x onerror=alert(1)>` in a mock CASE-PROGRESS.md renders as literal escaped text in the browser (not an element) | LOG-01 | No JS test runtime exists (no package.json / jsdom / Playwright) | Serve dashboard with a mock CASE-PROGRESS.md containing the payload; open in browser; confirm text appears literally and no alert fires |
| Clicking each tab shows its panel and hides others with no page reload | TAB-01 | Requires a real browser DOM interaction | Open dashboard; click each of Run Log / 1D Spectra / 2D Spectra / Tables; confirm only the active panel is visible; confirm Overview + Structures left column stays visible |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing pytest infra covers all automatable checks)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-07 (validated by gsd-plan-checker against the 3 finished plans)
