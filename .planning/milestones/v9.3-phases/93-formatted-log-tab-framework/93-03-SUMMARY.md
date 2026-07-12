---
phase: 93-formatted-log-tab-framework
plan: 03
subsystem: ui
tags: [checkpoint, human-verify, xss, tabs, browser, webview, defect-fix]

# Dependency graph
requires:
  - phase: 93-02
    provides: 4-tab bar + markdown-to-DOM renderer + refreshLog rewire + innerHTML XSS-guard test
provides:
  - "Human sign-off (real browser) on the three browser-observable behaviors: XSS escaping, tab switching + persistent left column, h3-vs-body typography hierarchy"
  - "Defect fix: run-log panel renders markdown blocks vertically (block flow), not as horizontal flex-row items"
affects: [94, 95, 96]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Active tab-panel visibility toggled to display:block (not flex) — markdown block flow stacks vertically; flex sizing comes from the panel being a flex:1 *item* of the column wrapper, not from the panel itself being a flex container"

key-files:
  created:
    - .planning/phases/93-formatted-log-tab-framework/93-03-SUMMARY.md
  modified:
    - src/lucy_ng/webview/static/index.html
    - src/lucy_ng/webview/static/webview.js

key-decisions:
  - "Fixed a layout defect surfaced only in a real browser (the automated innerHTML static-source scan and DOM-mock could not see it): #log-panel resolved to display:flex/row from two places — the CSS rule [data-panel=\"log\"]{display:flex} (initial paint) and activate() in webview.js setting style.display='flex' on the active panel (inline style won on every tab switch). Both changed to block. Confirms D-04 two-layer strategy: the manual browser half caught a defect the automated half structurally could not."

patterns-established:
  - "Tab-panel activation uses display:block for the active panel; height fill comes from flex:1 as a column-wrapper flex item, not from making the panel a flex container"

requirements-completed: [LOG-01, TAB-01]

# Sign-off
verification: human-verify (blocking checkpoint) — APPROVED
verified_by: user (Christoph Steinbeck), real Chrome browser, 2026-07-08
---

# 93-03 — Browser Verification Checkpoint: SUMMARY

## Outcome

**APPROVED** by the user after a real-browser session (Claude-in-Chrome, "Browser 1", macOS).
One defect was found and fixed during the checkpoint; all five acceptance criteria then
re-verified green.

## Defect found & fixed

**Symptom:** The Run Log rendered every markdown block (h1, p, hr, h2, h3, table, ul) laid out
**horizontally side-by-side** in narrow columns instead of flowing vertically — unreadable.

**Root cause:** `#log-panel` resolved to `display: flex` with the default `flex-direction: row`,
so renderLog's block children became horizontal flex items. Two sources both forced flex:
1. `index.html` — CSS rule `[data-panel="log"] { display: flex; }` (governs the initial paint)
2. `webview.js` — `activate()` set `panels[i].style.display = 'flex'` for the active panel; the
   inline style won over CSS on every tab switch.

**Fix:** Both changed to `block` (commit `3f38091`). The panel still fills height because it is a
`flex: 1` *item* of the `flex-direction: column` `#log-panel-wrapper`; `overflow-y: scroll` is
unaffected; placeholder panels stay horizontally centred via `text-align: center`.

## Acceptance criteria — all verified in a real browser (post-fix)

| # | Criterion | Result |
|---|-----------|--------|
| 1 | XSS: `# <img src=x onerror=alert(1)>` renders as literal escaped text; no alert, no `<img>` | ✅ text node only, no img element anywhere in panel |
| 2 | 4 tabs switch with no page reload; only active panel visible | ✅ no-reload sentinel survived all switches; only active panel `display:block` |
| 3 | Left Candidate-Structures/Overview column stays visible across tab clicks | ✅ present on every tab |
| 4 | Placeholder copy exact | ✅ "1D Spectra — coming in Phase 95" / "2D Spectra — coming in Phase 96" / "Tables — coming in Phase 94" |
| 5 | h3 agent-name headings distinguishable above body text | ✅ h3 13px/600/#495057 vs body 12px/400 — size + weight + colour delta |
| 6 | D-13: log panel does not jump scroll on the ~3 s refresh | ✅ scrolled mid-history (scrollTop 2792 of 6207), 7 s / 2+ refresh ticks, delta 0, no jump |

## Verification notes

- The automated half of the D-04 strategy (innerHTML static-source scan + Node DOM-mock) had
  passed in Plans 01–02 and again here for the XSS path — but it structurally could not see the
  flex-row layout defect. The **manual browser half caught it**, validating the two-layer design.
- `pytest tests/test_webview_api.py` → **21 passed** after the fix.
- Mock analysis dir served via `lucy webview serve` with a CASE-PROGRESS.md exercising every
  supported construct (H1/H2/H3, bold labels, inline code, hr, bullet list, pipe table) plus the
  XSS payload; enlarged to ~417 lines to force scroll overflow for the D-13 check.
