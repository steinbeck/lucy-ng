---
phase: 95-1d-real-spectra-peak-overlay
plan: 05
subsystem: ui
tags: [matplotlib, fastapi, webview, spectra-overlay, gap-closure]

# Dependency graph
requires:
  - phase: 95-1d-real-spectra-peak-overlay
    provides: "95-02 _render_1d_png real trace + peak overlay; 95-04 human-verify checkpoint that captured the label-collision defect"
provides:
  - "Single combined rotated (ppm + assignment) per-peak label in _render_1d_png, eliminating the horizontal assignment-label collision in dense-peak regions"
affects: [95-1d-real-spectra-peak-overlay-completion, webview-spectra-tab]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Single rotated ax.text per peak (ppm + assignment folded into one f-string label) instead of a rotated ppm label plus a separate horizontal assignment label"]

key-files:
  created: []
  modified:
    - src/lucy_ng/webview/routers/spectra.py
    - tests/test_webview_api.py

key-decisions:
  - "Folded ppm + assignment into one f-string label (\"{ppm:.1f}  {assignment}\") drawn at marker_top with rotation=90, rather than keeping two separate ax.text calls, per the 95-05 plan's exact fix."
  - "New test asserts exactly one ax.text(...) call per peak in the _render_1d_png source (via inspect.getsource) plus a live two-peak dense-region render, rather than trying to parse rendered pixel positions -- keeps the assertion resilient to matplotlib internals as the plan recommended."

patterns-established:
  - "Peak-overlay labels: one rotated label per data point combining all per-point metadata, to avoid horizontal-collision failure modes in dense chart regions."

requirements-completed: [SP1-01]

# Metrics
duration: 15min
completed: 2026-07-09
---

# Phase 95 Plan 05: Combine ppm + assignment into one rotated per-peak label Summary

**Fixed the Wave-3 checkpoint defect by folding the separate horizontal assignment label into the existing rotated ppm label in `_render_1d_png`, eliminating dense-region text collisions (aromatic ~127-141, methyls ~18-22) while keeping both values visible per peak.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-09T14:26:00Z (approx, worktree checkout)
- **Completed:** 2026-07-09T14:40:34Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- `_render_1d_png`'s peak loop now draws exactly one `ax.text(...)` call per peak: a single rotated (90°) label combining ppm and, when present, the assignment (`f"{ppm:.1f}  {assignment}"`), replacing the prior pattern of a rotated ppm label plus a separate horizontal assignment label at `y_max`.
- Added `test_single_combined_rotated_label_per_peak` to `TestSpectraEndpoint`: a source-level assertion (exactly one `ax.text(` call inside the peak loop, no `, y_max,`-anchored call, combined f-string present) plus a live render of two near-collinear peaks (22.4 ppm "2xCH3", 18.1 ppm "CH3" — the exact methyl-region collision case from the defect) confirming HTTP 200 image/png with non-empty bytes.
- All prior behaviour (trace rendering, reversed axis, marker vertical lines, degradation paths) left untouched — verified all 47 `tests/test_webview_api.py` tests still pass, including the 12 in `TestSpectraEndpoint`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Combine ppm + assignment into one rotated per-peak label in `_render_1d_png`** - `8f4a1a0` (fix)

**Plan metadata:** (this commit, docs — created by orchestrator per plan instructions, not by this executor)

## Files Created/Modified
- `src/lucy_ng/webview/routers/spectra.py` - `_render_1d_png` peak loop: removed the separate horizontal `ax.text(ppm, y_max, str(assignment), ...)` block; the rotated ppm-label call now uses a combined `label` string built from `f"{ppm:.1f}  {assignment}"` (or just `f"{ppm:.1f}"` when no assignment); docstring updated to describe the single combined label.
- `tests/test_webview_api.py` - Added `test_single_combined_rotated_label_per_peak` to `TestSpectraEndpoint`, asserting the source no longer contains a separate assignment-only `ax.text` call and exercising a live dense-region two-peak render.

## Decisions Made
- Combined-label format is `f"{ppm:.1f}  {assignment}"` (two spaces as a visual separator) drawn with the same `rotation=90, ha="center", va="bottom", fontsize=7, color=_ACCENT_COLOR` styling the ppm-only label already used, so orientation/placement/appearance is otherwise unchanged.
- The new test uses `inspect.getsource(spectra._render_1d_png)` plus substring/count assertions rather than parsing rendered PNG pixels — this was the plan's own recommended approach ("grep-style source assertion... resilient to matplotlib internals") and avoids brittleness against matplotlib version differences in text-layout internals.

## Deviations from Plan

None - plan executed exactly as written. The single task's `<action>` and `<acceptance_criteria>` were followed directly: the horizontal assignment block was removed, the combined f-string label was built, the vertical marker line was left untouched, and a focused test was added to `TestSpectraEndpoint`.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 95's Wave-3 human-verify gap closure defect is resolved; the orchestrator's remaining verification step is a visual re-render of the CASE1 ¹³C overlay to confirm no residual collision in the aromatic/methyl regions (per this plan's `<verification>` section) before marking Phase 95 complete.
- No blockers. `mypy src/lucy_ng/webview/routers/spectra.py` and `ruff check src/lucy_ng/webview/routers/spectra.py tests/test_webview_api.py` both clean on the touched files (mypy's whole-package run surfaces 66 pre-existing unrelated errors in other modules, none in `spectra.py` — out of scope per the deviation-rules scope boundary).

---
*Phase: 95-1d-real-spectra-peak-overlay*
*Completed: 2026-07-09*

## Self-Check: PASSED
- FOUND: .planning/phases/95-1d-real-spectra-peak-overlay/95-05-SUMMARY.md
- FOUND commit: 8f4a1a0
