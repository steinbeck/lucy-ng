---
phase: 93-formatted-log-tab-framework
plan: 01
subsystem: ui
tags: [fastapi, static-assets, vanilla-js, webview]

# Dependency graph
requires:
  - phase: 90-92 (v9.2 CASE Web-View)
    provides: FastAPI webview app (app.py), single-file dashboard (index.html), test scaffold (test_webview_api.py)
provides:
  - "Extracted, independently-packaged static/webview.js client script"
  - "GET /webview.js FastAPI route serving it with correct JS media type"
  - "index.html loading the dashboard script externally instead of inline"
  - "Route smoke test + packaging existence assertion establishing the extraction discipline for Plan 02 (tabs + markdown renderer)"
affects: [93-02, 93-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "External static JS asset served via a dedicated FastAPI FileResponse route with explicit media_type (never mimetypes.guess_type fallback)"
    - "Reuse a single lazily-imported FileResponse binding across multiple static-file routes in create_app() (WV-08 discipline)"

key-files:
  created:
    - src/lucy_ng/webview/static/webview.js
  modified:
    - src/lucy_ng/webview/app.py
    - src/lucy_ng/webview/static/index.html
    - tests/test_webview_api.py

key-decisions:
  - "Extracted the inline IIFE verbatim (ES5 var-style, no const/let/module conversion) to keep this plan strictly behavior-preserving"
  - "No pyproject.toml change needed — the existing flat src/lucy_ng/webview/static/* hatch glob already covers webview.js"

patterns-established:
  - "Static webview JS assets live at the flat static/ level and get an explicit FileResponse route with an explicit media_type"

requirements-completed: [TAB-01]

# Metrics
duration: 12min
completed: 2026-07-07
---

# Phase 93 Plan 01: Extract webview.js + /webview.js route Summary

Extracted the inline dashboard `<script>` block into `static/webview.js`, added an explicit `GET /webview.js` FastAPI route with `media_type="application/javascript"`, and wired `index.html` to load it externally — a behavior-preserving refactor with zero UI/functional change, establishing the extraction+route+packaging discipline required before Plan 02 adds tabs and the markdown renderer.

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-07T20:13:00Z
- **Completed:** 2026-07-07T20:25:13Z
- **Tasks:** 2/2 completed
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `src/lucy_ng/webview/static/webview.js` created — verbatim extraction of the 227-line inline IIFE (refreshStatus/renderStatus/refreshStructures/renderStructures/refreshLog/flashDot/tick), no behavior changes
- `GET /webview.js` route added to `app.py`, reusing the existing `FileResponse` import (only one `from fastapi.responses import FileResponse` line in the file) and explicit `media_type="application/javascript"` per Pitfall 5 (never rely on MIME sniffing)
- `index.html` reduced from a 227-line inline script to a single `<script src="/webview.js"></script>` tag
- Route smoke test (`TestFrontend.test_webview_js_served`) and packaging existence assertion (`TestPackaging.test_webview_js_present_in_static`) added; both green, `pyproject.toml` untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract webview.js, add /webview.js route, wire external script tag** - `0a5c411` (feat)
2. **Task 2: Wave 0 tests — /webview.js route smoke test + packaging existence assertion** - `df22c13` (test)

**Plan metadata:** (this commit, added by orchestrator after merge)

## Files Created/Modified
- `src/lucy_ng/webview/static/webview.js` - New file; verbatim extraction of the dashboard client script (IIFE, ES5 style)
- `src/lucy_ng/webview/app.py` - Added `_webview_js` path constant + `GET /webview.js` route + docstring bullet
- `src/lucy_ng/webview/static/index.html` - Replaced 227-line inline `<script>` block with `<script src="/webview.js"></script>`
- `tests/test_webview_api.py` - Added `TestFrontend.test_webview_js_served` and `TestPackaging.test_webview_js_present_in_static`

## Decisions Made
- Followed 93-PATTERNS.md's REAL `app.py` route shape (inline `_static_file`/`_webview_js` Path built inside `create_app()`, lazy `FileResponse` import with `# noqa: PLC0415`) rather than 93-RESEARCH.md's `_static_dir`/module-level-decorator sketch, per the plan's explicit interface note.
- No new test class for markdown-renderer XSS-safety (`TestMarkdownRendererSafety` from PATTERNS.md) — that belongs to Plan 02 where the markdown renderer itself is introduced; out of scope for this behavior-preserving extraction plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] Line-length fix in new packaging assertion**
- **Found during:** Task 2
- **Issue:** The new `test_webview_js_present_in_static` assertion message was 101 characters, exceeding the project's ruff `E501` 100-char limit (introduced by this task's own code, in scope per the deviation rules' scope boundary).
- **Fix:** Wrapped the assertion message string across two lines.
- **Files modified:** `tests/test_webview_api.py`
- **Verification:** `ruff check tests/test_webview_api.py` reports zero new errors (one pre-existing E501 at line 293 from Plan 03's territory, unrelated to this change, left untouched per scope boundary).
- **Committed in:** `df22c13` (part of Task 2 commit)

Note: a pre-existing `E501` at `tests/test_webview_api.py:293` (in `TestStructuresEndpoint`, unrelated to this plan's files) and pre-existing `mypy` `import-not-found` errors for `fastapi`/`nmrglue`/`tqdm`/`scipy`/`hosegen` stubs (environment lacks the `[webview]` extra and several optional type-stub packages) were observed but are out of scope — logged here for visibility, not fixed (Scope Boundary rule).

## Environment Notes

- `fastapi` is not installed in this worktree's active venv (`/mnt/raid_drive/chris/lucy-ng/.venv`), so the 14 fastapi-dependent tests in `tests/test_webview_api.py` skip cleanly rather than run live. All fastapi-independent tests (5 `TestPackaging` cases including the 2 in this plan) pass. This matches the plan's `<done>` criterion: "existing suite still green (or gracefully skips when fastapi absent)."

## Known Stubs

None — no stubs introduced. This plan is a pure extraction with no new data-fetching or rendering surface.

## Threat Flags

None — no new surface beyond what `93-PLAN.md`'s `<threat_model>` (T-93-02, T-93-03, T-93-SC) already covers; `/webview.js` uses a fixed constant path (not user-derived) and an explicit media_type, matching the plan's mitigation exactly.

## Self-Check: PASSED

- FOUND: src/lucy_ng/webview/static/webview.js
- FOUND: src/lucy_ng/webview/app.py (GET /webview.js route present)
- FOUND: src/lucy_ng/webview/static/index.html (external script tag present, inline script removed)
- FOUND: tests/test_webview_api.py (test_webview_js_served, test_webview_js_present_in_static present)
- FOUND commit 0a5c411
- FOUND commit df22c13
