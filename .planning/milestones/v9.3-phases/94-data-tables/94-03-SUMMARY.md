---
phase: 94-data-tables
plan: 03
subsystem: webview
tags: [vanilla-js, webview, tables, frontend, xss-discipline]

# Dependency graph
requires:
  - phase: 94-02
    provides: "tables.py 5-route FastAPI router (/api/tables/{carbon,hsqc,hmbc,cosy,constraints}), all never-500, degrading to state=waiting"
provides:
  - "Tables tab populated with 5 stacked sections (13C Signals, HSQC, HMBC, COSY, LSD Constraint Inventory), each independently fetch/render/catch on the existing ~3s tick() poll"
  - "formatIntensity/formatBool/cellText/setCaption/showTableWaiting shared render helpers in webview.js"
  - "HMBC row flag-colouring via post-process querySelectorAll('tbody tr').className (row-ok/row-potential-4j/row-1j-artifact)"
  - "TBL-03 structured 3-subsection render (Applied Constraints / Constraint Summary / Deferred-Pending)"
  - ".data-table/.tables-section/.tables-subsection/.table-waiting CSS tokens in index.html"
affects: ["94-04-PLAN.md (phase close / verification)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "fetch(URL).then(json).then(render).catch(warn) per-panel independence (SC4), mirrored 5x from refreshStructures/renderStructures"
    - "buildTable(headers, rows) reused verbatim; per-row CSS class applied by post-process querySelectorAll('tbody tr') walk, never forking buildTable"
    - "table.className = 'data-table' set on buildTable's return value (not a buildTable fork) to pick up shared density CSS"
    - "Compact-intensity + Yes/No boolean formatting as pure client-side display helpers, no backend change"

key-files:
  created: []
  modified:
    - src/lucy_ng/webview/static/index.html
    - src/lucy_ng/webview/static/webview.js

key-decisions:
  - "Applied Constraints 'Note' column: the LSD inventory schema's applied_from_detection is a flat narrative list with no per-row index back to a specific BOND/HMBC/COSY-equiv constraint, so every generated row renders a genuinely empty Note cell (per the plan's explicit 'otherwise empty cell' fallback) rather than a heuristic/guessed mapping."
  - "Extended the Yes/No (never raw true/false) convention beyond the TBL-03-mandated ring_exclusion_enabled to the HSQC matched_real_carbon/one_bond boolean columns too, for QC-readability consistency across all 5 tables."
  - "table.className = 'data-table' is set on buildTable's return value after the call (not inside buildTable), keeping buildTable itself untouched per PATTERNS.md guidance while still picking up the shared density CSS block."

requirements-completed: [TBL-01, TBL-02, TBL-03]

# Metrics
duration: 20min
completed: 2026-07-09
---

# Phase 94 Plan 03: Tables Tab Frontend Rendering Summary

**Tables tab now renders all 5 backend `/api/tables/*` sources as live, QC-grade DOM tables — compact intensity formatting, HMBC per-row flag colouring via CSS-class post-processing, and the LSD constraint inventory as a 3-subsection structured view — entirely via `createElement`/`textContent`, preserving the D-02/v9.2 no-`innerHTML` XSS discipline.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-09T08:34:41Z
- **Tasks:** 3 completed
- **Files modified:** 2 (`index.html`, `webview.js`)

## Accomplishments

- Replaced the Phase-93 `Tables — coming in Phase 94` placeholder with 5 real `<section>` containers (`#table-carbon`, `#table-hsqc`, `#table-hmbc`, `#table-cosy`, `#table-constraints`), each with its own heading, caption element, and body container — giving SC4's per-table waiting-state independence for free at the DOM level.
- Added the shared `.data-table` density class (matching the shipped `#log-panel table` tokens exactly), the HMBC flag triad (`.row-ok` / `.row-potential-4j` / `.row-1j-artifact`, exact UI-SPEC hex values), `.table-waiting`, and the `.tables-section`/`.tables-subsection`/`.tables-heading`/`.tables-display-heading`/`.tables-subheading`/`.tables-caption` layout tokens (16px/24px gaps per spec) — no new colours/fonts/sizes introduced beyond the UI-SPEC-enumerated set.
- Added `formatIntensity(v)` (exact `M`/`K`/raw algorithm), `formatBool(v)` (Yes/No, never raw true/false), `cellText(v)` (defensive null-safe stringification), `setCaption(el, note, counts)` (D-05 `{note} — {counts}` format, dangling-em-dash-safe), and `showTableWaiting(bodyEl, captionEl, message)` shared helpers.
- Added 4 independent `refreshCarbon/Hsqc/Hmbc/Cosy` + `renderCarbon/Hsqc/Hmbc/Cosy` pairs mirroring the existing `refreshStructures`/`renderStructures` fetch→render→catch shape, each reusing `buildTable`/`appendInline` verbatim; all 4 registered inside `tick()`.
- HMBC rows show **all** kept rows (never filtered), coloured per `flag` value by post-processing `table.querySelectorAll('tbody tr')` and assigning `.className` by index — `buildTable` itself is untouched.
- Added `refreshConstraints`/`renderConstraints` rendering TBL-03 as 3 subsections: **Applied Constraints** (`BOND`/`HMBC`/`COSY-equiv` rows from `bond_constraints`/`hmbc_batches[].correlations`/`cosy_equiv_pairs`, with the "No applied constraints recorded" spanning-row fallback when all three arrays are empty), **Constraint Summary** (fixed row order, `ring_exclusion_enabled` rendered `Yes`/`No`, `deff_fexp.status` `.get()`-defensive), **Deferred / Pending** (`<ul>`/`<li>` from `pending_from_detection`, with the "Nothing deferred this iteration." empty-state fallback).
- All 5 panels registered in the existing ~3s `tick()` poll; each fetch/render/catch independently, so one malformed source cannot blank the other four (SC4).

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the Tables panel structure + CSS tokens in index.html** - `4ef5623` (feat)
2. **Task 2: Render the 4 peaks tables (carbon/hsqc/hmbc/cosy) in webview.js** - `34d99cf` (feat)
3. **Task 3: Render TBL-03 structured LSD constraint inventory (3 subsections)** - `f9ce9d3` (feat)

## Files Created/Modified

- `src/lucy_ng/webview/static/index.html` — Tables-tab placeholder replaced with 5 sections + CSS tokens (`.data-table`, HMBC flag triad, `.table-waiting`, layout/typography tokens)
- `src/lucy_ng/webview/static/webview.js` — 5 URL consts, 5 shared helpers, 5 refresh/render pairs (4 peaks tables + TBL-03 structured render), all registered in `tick()`

## Decisions Made

- Applied Constraints "Note" column intentionally renders empty for every row — the LSD inventory schema provides no per-row mapping from `applied_from_detection` narrative strings back to a specific `BOND`/`HMBC`/`COSY-equiv` constraint instance, so guessing a mapping would misattribute QC narrative. This satisfies the plan's own "otherwise empty cell" fallback for the (currently: all) unmapped case.
- Extended the "never raw true/false" Yes/No convention (mandated by TBL-03's `ring_exclusion_enabled`) to the HSQC `matched_real_carbon`/`one_bond` boolean columns for consistent QC readability across all 5 tables — a same-family, non-scope-expanding extension.
- `table.className = 'data-table'` is assigned on `buildTable`'s return value at each call site (not inside `buildTable`), keeping the shared helper untouched per PATTERNS.md guidance while still picking up the shared density CSS.

## Deviations from Plan

None — plan executed as written, with the two Claude's-discretion decisions above (Note-column empty-fallback, boolean Yes/No extension) both explicitly permitted by the plan's own defensive-fallback language and CONTEXT.md's "Claude's discretion" scope.

## Issues Encountered

- First implementation of the render-helper doc comments used the literal substring `innerHTML` inside code comments (explaining what was *not* done), which tripped the whole-file `test_no_innerhtml_in_source` regression scan (it does a raw substring match, not markup-aware parsing). Reworded the two comments to avoid the literal substring while preserving the same explanatory intent — no functional change, verified green afterward.

## Verification Output

```
$ pytest tests/test_webview_api.py::TestFrontend -x -q
2 passed, 26 warnings in 0.24s

$ pytest tests/test_webview_api.py::TestMarkdownRendererSafety::test_no_innerhtml_in_source -x -q
1 passed, 26 warnings in 0.01s

$ pytest tests/test_webview_api.py -q
35 passed, 26 warnings in 0.30s

$ node --check src/lucy_ng/webview/static/webview.js
(no output — syntactically valid)

$ ruff check src/lucy_ng/webview
All checks passed!
(ruff check src tests reports 282 pre-existing errors across the whole tree,
none attributable to this plan's two changed files — both are non-Python;
confirmed via `ruff check src/lucy_ng/webview` scoped to the touched package.)

$ node -e "... formatIntensity(5559614), formatIntensity(5559), formatIntensity(42) ..."
5.6M 5.6K 42
```

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 5 Tables-tab sections render live from the Phase 94-02 backend routes; SC4 per-table independence verified by construction (5 separate fetch/catch pairs).
- XSS discipline preserved: `test_no_innerhtml_in_source` (whole-file scan) green; no `innerHTML` anywhere in `webview.js`.
- Plan 94-04 (phase close / verification) can proceed — no blockers.

---
*Phase: 94-data-tables*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: src/lucy_ng/webview/static/index.html
- FOUND: src/lucy_ng/webview/static/webview.js
- FOUND: .planning/phases/94-data-tables/94-03-SUMMARY.md
- FOUND: 4ef5623 (commit exists in git log)
- FOUND: 34d99cf (commit exists in git log)
- FOUND: f9ce9d3 (commit exists in git log)
