---
phase: 95-1d-real-spectra-peak-overlay
plan: 03
subsystem: ui
tags: [webview, vanilla-js, static-html, case-orchestrator, matplotlib-png, fastapi]

# Dependency graph
requires:
  - phase: 95-1d-real-spectra-peak-overlay (Plan 02)
    provides: "/api/spectra/1d/carbon and /api/spectra/1d/proton PNG endpoints (never-500, spectra.py router)"
provides:
  - "1D Spectra tab populated with img-spectrum-carbon/img-spectrum-proton mounts targeting the PNG endpoints"
  - "refreshSpectra1D() cache-busting poll registered in tick() (~3s)"
  - "case.md writes analysis/.run_manifest.json at run-start (bruker_data_dir + formula)"
affects: [96-2d-contour-spectra]

# Tech tracking
tech-stack:
  added: []
  patterns: ["<img src> cache-bust idiom (reused from renderStructures) applied to a never-500 PNG endpoint with no fetch/catch needed"]

key-files:
  created: []
  modified:
    - src/lucy_ng/webview/static/index.html
    - src/lucy_ng/webview/static/webview.js
    - .claude/commands/lucy-ng/case.md

key-decisions:
  - "refreshSpectra1D() has no .catch()/error branch — the PNG endpoint is contractually never-500 (placeholder state is baked into the returned pixels per SP-02), matching the plan's explicit instruction"
  - "No SMILES-diff dedupe on the two <img> tags (D-06) — unconditional cache-bust every tick since 1D rendering is cheap and uncached this phase"
  - "case.md manifest write kept to a single added Bash heredoc block between the run_start timing stamp and the webview launch, with zero CLI signature or .webview.json changes (D-07)"

patterns-established:
  - "spectra.py PNG endpoints are consumed purely via native <img> GET, never JSON fetch — this is the frontend half of Phase 96's contour-endpoint contract too"

requirements-completed: [SP1-01, SP-02]

# Metrics
duration: 12min
completed: 2026-07-09
---

# Phase 95 Plan 03: 1D Spectra Tab Frontend Wiring + case.md Manifest Write Summary

**Wired the 1D Spectra tab to the Plan-02 PNG endpoints with a cache-busting poll, and gave case.md a single new run-start write so the router can locate the raw Bruker dataset.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-09T15:40:00+02:00 (approx, first commit 15:41:09+02:00)
- **Completed:** 2026-07-09T15:42:04+02:00
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `index.html`'s `spectra-1d` placeholder replaced with two always-present `<section class="tables-section">` blocks (`#spectrum-carbon`, `#spectrum-proton`), each containing an `<img>` sourced at its `/api/spectra/1d/{carbon,proton}` route; `.spectrum-img` CSS added reusing existing `#dee2e6`/`6px` tokens
- `webview.js` gained `refreshSpectra1D()` — cache-busts both `<img>` sources every ~3s tick with no fetch/catch (native `<img>` GET, never-500 contract) — registered in `tick()`
- `case.md`'s `spawn_case_team` Step 5 gained one new Bash heredoc block writing `analysis/.run_manifest.json` (`bruker_data_dir` + `formula`) immediately after the `run_start` timing stamp and before the webview launch

## Task Commits

Each task was committed atomically:

1. **Task 1: index.html — replace spectra-1d placeholder with img-spectrum-carbon/proton + .spectrum-img CSS** - `5e65bbe` (feat)
2. **Task 2: webview.js — refreshSpectra1D() cache-bust + tick() registration** - `52fb15e` (feat)
3. **Task 3: case.md — write analysis/.run_manifest.json at run-start** - `38210d6` (feat)

_No TDD tasks in this plan (frontend markup/script + skill-script edits, no behavior-adding source code with new logic branches requiring RED/GREEN)._

## Files Created/Modified
- `src/lucy_ng/webview/static/index.html` - `spectra-1d` panel now holds `#spectrum-carbon`/`#spectrum-proton` sections with `img-spectrum-carbon`/`img-spectrum-proton`; `.spectrum-img` CSS rule added; `spectra-2d` placeholder left untouched
- `src/lucy_ng/webview/static/webview.js` - new `refreshSpectra1D()` function + call site inside `tick()`
- `.claude/commands/lucy-ng/case.md` - one new Bash write block for `analysis/.run_manifest.json` in `spawn_case_team` Step 5

## Decisions Made
- Placed `refreshSpectra1D()` immediately before the `initTabs()` section (rather than adjacent to `refreshConstraints`) to keep it visually distinct as the one panel with no fetch/render/catch triplet — matches the plan's "any position" discretion for the `tick()` call site.
- Kept both `<section>` blocks unconditionally present in the DOM (never hidden), per the UI-SPEC contract — absence of a ¹H experiment is communicated by the placeholder PNG rendered server-side, not by DOM hiding.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The frontend now targets the exact endpoint shape Plan 02 built; manual browser verification of the full end-to-end flow (live CASE run → manifest → PNG → tab) is deferred to Plan 95-04 (checkpoint), as stated in this plan's `<verification>` section.
- Phase 96 (2D contour spectra) can reuse the same `<img>`-cache-bust idiom and the `_apply_nmr_axes()` helper referenced in 95-PATTERNS.md; no blockers.
- `pytest tests/test_webview_api.py -q` passes (46 passed) — no regressions introduced by the frontend/skill-script edits (they do not touch the router).
- No Python files were modified in this plan (frontend HTML/JS + a Markdown skill script only), so `ruff check`/`mypy` are not applicable to this plan's diff.

---
*Phase: 95-1d-real-spectra-peak-overlay*
*Completed: 2026-07-09*

## Self-Check: PASSED

All created/modified files found on disk; all three task commit hashes (5e65bbe, 52fb15e, 38210d6) found in git log.
