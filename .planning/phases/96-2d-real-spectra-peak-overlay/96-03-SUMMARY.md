---
phase: 96-2d-real-spectra-peak-overlay
plan: 03
subsystem: ui
tags: [vanilla-js, static-html, webview, spectra, frontend]

# Dependency graph
requires:
  - phase: 96-02
    provides: "/api/spectra/2d/{hsqc,hmbc,cosy} PNG routes with never-500 degradation"
provides:
  - "2D Spectra tab UI: three stacked HSQC/HMBC/COSY <img> sections replacing the Phase-96 placeholder"
  - "refreshSpectra2D() cache-busting all three 2D img src attributes on the existing ~3s tick() poll"
affects: [96-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "2D spectra <img> sections mirror the 1D spectra markup exactly (tables-section/tables-heading/spectrum-img, no new CSS)"
    - "refreshSpectra2D mirrors refreshSpectra1D: Date.now() cache-buster + per-img getElementById/if-guard/src update"

key-files:
  created: []
  modified:
    - src/lucy_ng/webview/static/index.html
    - src/lucy_ng/webview/static/webview.js

key-decisions:
  - "Reused .tables-section/.tables-heading/.spectrum-img verbatim per D-09 — no new CSS class or style token introduced"
  - "refreshSpectra2D() placed immediately after refreshSpectra1D() in tick() (order-independent, fire-and-forget, matches plan instruction)"

patterns-established: []

requirements-completed: [SP2-01, SP-02]

# Metrics
duration: 3min
completed: 2026-07-11
---

# Phase 96 Plan 03: 2D Spectra Tab Frontend Wiring Summary

**Three stacked HSQC/HMBC/COSY `<img>` sections replace the "coming in Phase 96" placeholder, cache-busted every ~3s poll via a new `refreshSpectra2D()` mirroring the existing `refreshSpectra1D()` pattern.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-11T14:20:52+02:00 (base commit)
- **Completed:** 2026-07-11T14:23:03+02:00
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- `data-panel="spectra-2d"` placeholder in `index.html` replaced with three stacked `<section class="tables-section">` blocks (HSQC/HMBC/COSY), each containing an `<img class="spectrum-img">` sourced from `/api/spectra/2d/{hsqc,hmbc,cosy}` respectively — no new CSS class introduced (D-09).
- `refreshSpectra2D()` added to `webview.js`, mirroring `refreshSpectra1D()` exactly: one `Date.now()` cache-buster, three guarded `getElementById`/`if (img)`/`img.src = ...?t=<timestamp>` updates.
- `refreshSpectra2D();` wired into `tick()` immediately after the existing `refreshSpectra1D();` call, so all three 2D plots refresh on the existing ~3s poll alongside the rest of the dashboard.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace the spectra-2d placeholder with three stacked HSQC/HMBC/COSY img sections** - `a18d7a1` (feat)
2. **Task 2: Add refreshSpectra2D and call it from tick()** - `fcc288f` (feat)

**Plan metadata:** committed alongside this SUMMARY (see final commit)

## Files Created/Modified
- `src/lucy_ng/webview/static/index.html` - `data-panel="spectra-2d"` placeholder div replaced with three `<section id="spectrum-{hsqc,hmbc,cosy}">` blocks, each `<h2 class="tables-heading">` + `<img id="img-spectrum-{hsqc,hmbc,cosy}" class="spectrum-img">` sourced from the Plan 02 routes
- `src/lucy_ng/webview/static/webview.js` - new `refreshSpectra2D()` function (cache-busts the three 2D `<img>` src attributes) + one-line call added to `tick()`

## Decisions Made
- Followed the plan and UI-SPEC.md markup exactly — no deviation from the locked DOM structure, ids, alt text, or `refreshSpectra2D` reference implementation.
- `initTabs()` left untouched, as instructed — it already toggles `data-panel="spectra-2d"` generically via `[data-panel]` selectors, so no tab-bar change was needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Both structural guard scripts (`python -c "..."` from the plan's `<verify>` blocks) passed on first attempt. `ruff check src tests` was run per the critical invariants; it surfaced 281 pre-existing errors in unrelated Python files (out of this plan's scope — this plan touches only `index.html`/`webview.js`, no Python files), none of which reference either file modified by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The 2D Spectra tab now has real markup and polling wiring in place, ready for Plan 04 (visual verification / checkpoint against a live or fixture-backed webview server).
- No blockers. The three `<img>` elements will render the Plan 02 placeholder PNGs ("no HSQC/HMBC/COSY experiment found" or similar) until pointed at a real `analysis/` run with 2D Bruker data.

---
*Phase: 96-2d-real-spectra-peak-overlay*
*Completed: 2026-07-11*

## Self-Check: PASSED

- FOUND: src/lucy_ng/webview/static/index.html
- FOUND: src/lucy_ng/webview/static/webview.js
- FOUND: .planning/phases/96-2d-real-spectra-peak-overlay/96-03-SUMMARY.md
- FOUND: a18d7a1 (Task 1 commit)
- FOUND: fcc288f (Task 2 commit)
- FOUND: 5d06f7a (SUMMARY commit)
