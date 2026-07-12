---
phase: 93-formatted-log-tab-framework
plan: 02
subsystem: ui
tags: [vanilla-js, dom, xss-safety, webview, markdown]

# Dependency graph
requires:
  - phase: 93-01
    provides: Extracted static/webview.js + GET /webview.js route + index.html loading it externally
provides:
  - "Persistent 4-tab bar (#tab-bar) over the right panel: Run Log / 1D Spectra / 2D Spectra / Tables, Run Log default-active"
  - "3 docked-in placeholder panels (1D Spectra/2D Spectra/Tables) carrying Phase 94-96 copy, no content yet"
  - "renderLog/buildTable/appendInline markdown-to-DOM block+inline parser (headings, bold, inline code, pipe tables, hr, bullets, fenced code)"
  - "refreshLog() rewired onto renderLog() while preserving the D-13 scroll-preserve contract"
  - "Static-source innerHTML XSS-guard test (TestMarkdownRendererSafety) establishing the automated regression guard for LOG-01/D-02"
affects: [93-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tab switching via plain data-tab/data-panel attribute + display:flex/none toggle, no fetch triggered by activate() (existing tick() polling loop keeps all 4 panels current regardless of visibility)"
    - "Line-based markdown block parser (closed 6-construct subset) building DOM nodes exclusively via createElement/textContent/createTextNode — container cleared via removeChild loop, never innerHTML"

key-files:
  created: []
  modified:
    - src/lucy_ng/webview/static/index.html
    - src/lucy_ng/webview/static/webview.js
    - tests/test_webview_api.py

key-decisions:
  - "Split the CSS edit into two commits (tab-bar/panel box-model CSS in Task 1, markdown-child typography CSS in Task 2) to keep each task's commit scoped to its own acceptance criteria, even though both touch index.html's <style> block"
  - "Fixed a bug in the RESEARCH.md-vetted Pattern 3 pipe-table separator regex (Rule 1): the original /^\\|[\\s:-]+\\|\\s*$/ excludes the pipe character from its own character class, so it only matches by accident on a 2-column separator (|---|---|) and silently fails on the real 3+ column Timing Summary format (|-------|-------|----------|) that progress-format.md actually specifies — widened to /^\\|[\\s:|-]+\\|\\s*$/, verified against a Node harness with both a 3-column table and the XSS payload"

patterns-established:
  - "Every function touching /api/log-derived content builds DOM via createElement/textContent/createTextNode only; verified both by a static-source pytest scan and a Node-based DOM-mock simulation of the actual payload"

requirements-completed: [LOG-01, TAB-01]

# Metrics
duration: 21min
completed: 2026-07-07
---

# Phase 93 Plan 02: Formatted Log + Tab Framework Summary

Persistent 4-tab bar (Run Log/1D Spectra/2D Spectra/Tables) docked over the right panel with 3 Phase-94/95/96 placeholders, plus a hand-rolled 6-construct markdown-to-DOM renderer (`renderLog`/`buildTable`/`appendInline`) that converts `CASE-PROGRESS.md` into headings/bold/code/tables/hr/bullets using `textContent`/`createElement` exclusively — closing the XSS vector by construction and verified both by a static-source pytest scan and a hand-written Node DOM-mock exercising the actual `# <img src=x onerror=alert(1)>` payload.

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-07T20:13:00Z (continuing from wave-1 base)
- **Completed:** 2026-07-07T20:34:26Z
- **Tasks:** 2/2 completed
- **Files modified:** 3

## Accomplishments
- `#tab-bar` (4 buttons, `data-tab` attrs) replaces the static `<h2>Run Log</h2>`; 4 sibling `[data-panel]` divs replace the single `<pre id="log-panel">` — `log-panel` is now a `<div>`, 3 placeholders carry the exact "coming in Phase 9x" copy from UI-SPEC
- `initTabs()`/`activate(tabName)` in webview.js: click-driven `display: flex/none` + `.active` class toggle, no fetch triggered, called once at bootstrap next to `tick()`
- `renderLog(rawText, container)` + `buildTable(headerCells, rows)` + `appendInline(parent, text)`: closed-subset block/inline markdown parser — every leaf via `textContent`/`createTextNode`, container cleared via `removeChild` loop, never `innerHTML`
- `refreshLog()` rewired to call `renderLog(content, logEl)`, keeping the `atBottom`-before / `scrollTop`-restore-after D-13 contract exactly as before
- Markdown-child CSS added to `#log-panel` (h1/h2/h3/p/strong/code/pre/hr/table/ul) using only pre-existing hex tokens
- `TestMarkdownRendererSafety::test_no_innerhtml_in_source` — pure static-source scan, no fastapi import, asserts the literal substring `innerHTML` never appears in `webview.js`
- Found and fixed a real bug in the RESEARCH.md-vetted pipe-table separator regex (see Deviations) — without the fix, the actual `## Timing Summary` table format from `progress-format.md` would silently degrade to paragraphs instead of rendering as a `<table>`

## Task Commits

Each task was committed atomically:

1. **Task 1: Tab bar markup, placeholder panels, CSS, and tab-switching JS** - `fdd80df` (feat)
2. **Task 2: Markdown-to-DOM renderer, refreshLog rewire, and innerHTML XSS-guard test** - `0c1a8b8` (feat)
3. **Rule 1 auto-fix: pipe-table separator regex** - `8748c94` (fix)

**Plan metadata:** (this commit, added by orchestrator after merge)

## Files Created/Modified
- `src/lucy_ng/webview/static/index.html` - Tab bar + 4 panel divs replacing the old `<h2>`/`<pre>` pair; tab-bar/panel-box-model CSS (Task 1); markdown-child typography CSS for `#log-panel` h1/h2/h3/p/strong/code/pre/hr/table/ul (Task 2); removed page-wide `white-space: pre-wrap` + monospace from the `#log-panel` container rule
- `src/lucy_ng/webview/static/webview.js` - Added `initTabs()`/`activate()` (Task 1); added `renderLog()`/`buildTable()`/`appendInline()` and rewired `refreshLog()` onto the new renderer (Task 2); fixed the pipe-table separator regex (Rule 1 fix commit)
- `tests/test_webview_api.py` - Added `class TestMarkdownRendererSafety` with `test_no_innerhtml_in_source`

## Decisions Made
- Split the markdown-CSS addition strictly into Task 2's commit (even though both tasks touch the same `<style>` block) to keep each task's commit matching its own acceptance criteria exactly, per the atomic-commit-per-task requirement.
- Kept `display: flex` for panel visibility toggling (per RESEARCH.md Pattern 2's vetted code) even though panel content is simple block/text flow — a flex container with anonymous block-boxed text content renders identically to a plain block container for this content shape, and matching the vetted pattern verbatim avoids introducing an untested deviation.
- Wrote a throwaway Node.js DOM-mock harness (in the scratchpad, not committed) to empirically verify the renderer's actual DOM output against the XSS payload and a realistic 3-column Timing Summary table before considering the plan done — this is what surfaced the pipe-table regex bug described below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pipe-table separator regex rejects the real multi-column Timing Summary format**
- **Found during:** Task 2 verification (Node DOM-mock harness simulating `renderLog()` against a 3-column table matching `progress-format.md`'s actual `## Timing Summary` shape)
- **Issue:** The RESEARCH.md Pattern 3 code (transcribed verbatim per the plan's `<interfaces>` block) uses `/^\|[\s:-]+\|\s*$/` to detect a pipe-table separator row. This character class excludes the pipe character `|` itself, so it only matches a 2-column separator like `|---|---|` by coincidence (the middle `|` happens to sit exactly at the boundary between the `[\s:-]+` match and the trailing `\|`). For the real 3+ column format `progress-format.md` specifies (`| Phase | Agent | Start (UTC) | End (UTC) | Duration |` with separator `|-------|-------|-------------|-----------|----------|`), the regex fails to match because internal `|` characters aren't in the allowed class, so the parser falls through to the default paragraph branch instead of rendering a `<table>` — exactly the Timing Summary block this phase is meant to render.
- **Fix:** Widened the character class to `/^\|[\s:|-]+\|\s*$/`, allowing internal pipe delimiters between dash runs while still correctly rejecting body rows (which contain letters, so still fail the class match).
- **Files modified:** `src/lucy_ng/webview/static/webview.js`
- **Verification:** Wrote a Node.js harness with a minimal DOM mock (createElement/createTextNode/appendChild/removeChild/textContent) to run the actual `renderLog()`/`appendInline()` functions extracted from the real source file against (a) the XSS payload `# <img src=x onerror=alert(1)>` — confirmed it renders as a single literal text node inside `<h1>`, never parsed as an element — and (b) a realistic 3-column pipe table — confirmed it now builds a `<table>` with correct `<th>`/`<td>` counts, hr, and a 2-item bullet list. Also re-ran `pytest tests/test_webview_api.py -q` (7 passed, 14 skipped) and `grep -c 'innerHTML' src/lucy_ng/webview/static/webview.js` (0) after the fix.
- **Committed in:** `8748c94` (separate fix commit, since Task 2's commit had already landed before the bug was found during post-commit verification)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary correctness fix for a construct explicitly in this phase's scope (the pipe-table renderer is one of the plan's 6 must-support markdown constructs, and the Timing Summary table is the one real pipe-table `CASE-PROGRESS.md` ever contains). No scope creep — confined to the one regex the plan's own interfaces block specified.

## Issues Encountered
- No local Python venv had `fastapi` installed in this worktree (same as noted in 93-01-SUMMARY.md's Environment Notes) — the 14 fastapi-dependent test methods in `tests/test_webview_api.py` skip cleanly rather than run live; all 7 fastapi-independent tests (including the new `TestMarkdownRendererSafety`) run and pass. This matches the plan's verification requirement ("pytest green, or gracefully skips when fastapi absent").
- `python`/`python3` were not directly usable from the shell PATH inside the worktree; used the repo's existing `.venv` at `/mnt/raid_drive/chris/lucy-ng/.venv/bin/python` (shared venv, same one 93-01 used) — no new environment setup needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The 4-tab bar, 3 placeholders, and markdown renderer are all in place and unit/static-test verified; Plan 03 (manual browser checkpoint) can now confirm the visual/interaction contract (tab switching, typography hierarchy, and the live XSS-payload browser check) that only a real browser can validate.
- Phases 94-96 have a stable dock-in point: `[data-panel="tables"]`, `[data-panel="spectra-1d"]`, `[data-panel="spectra-2d"]` are the exact attribute selectors those phases will populate with real content, replacing the placeholder `<div class="placeholder">` text.
- No blockers. The one open item Plan 03 should specifically verify in-browser (per UI-SPEC's own "Manual hierarchy check" note) is whether the 13px `h3` vs 12px body/bold 1px size difference reads as a distinguishable visual hierarchy level for agent-name sub-headings — this is a genuine judgment call UI-SPEC flagged as needing human eyes, not a defect.

## Self-Check: PASSED

- FOUND: src/lucy_ng/webview/static/index.html
- FOUND: src/lucy_ng/webview/static/webview.js
- FOUND: tests/test_webview_api.py
- FOUND: .planning/phases/93-formatted-log-tab-framework/93-02-SUMMARY.md
- FOUND commit fdd80df (Task 1)
- FOUND commit 0c1a8b8 (Task 2)
- FOUND commit 8748c94 (Rule 1 fix)
- FOUND commit d9cd025 (this SUMMARY)

---
*Phase: 93-formatted-log-tab-framework*
*Completed: 2026-07-07*
