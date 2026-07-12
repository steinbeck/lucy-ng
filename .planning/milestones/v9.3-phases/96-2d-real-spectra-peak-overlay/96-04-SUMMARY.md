# 96-04 SUMMARY — Manual Browser Checkpoint (2D Spectra tab)

**Plan:** 96-04 (type: execute, autonomous: false — human verification)
**Requirements:** SP2-01, SP-02
**Status:** PASSED (with one defect found and fixed during verification)
**Date:** 2026-07-12

## What was verified

Live browser verification of the Phase 96 2D Spectra tab via `lucy webview serve`
against a real analysis dir whose `.run_manifest.json` points at the real CASE1
Bruker dataset (HSQC exp /6, HMBC exp /7, COSY exp /5), with hand-authored overlay
peak JSON (illustrative cross-peaks to exercise the overlay/flag/diagonal paths).
Rendered both headlessly (FastAPI TestClient → PNG bytes, inspected as images) and
live in Chrome (2D Spectra tab, scrolled through all three stacked plots).

## must_haves — all confirmed

1. **Three real contour plots (HSQC, HMBC, COSY), not empty axes or sticks** — ✓
   Real contours from raw Bruker 2D data; ~99–230 KB PNGs; stacked all-visible.
2. **Both ppm axes reversed, aromatic top-left (F2 ~7 / F1 ~130)** — ✓ AFTER FIX
   (see Defect below). HSQC/HMBC now show δC 175 at top → 0 at bottom, aromatic
   (~125–140) in the upper region; δH 7 left → 1 right.
3. **Open-circle cross-peaks on real signal; HMBC flag-coloured; COSY diagonal** — ✓
   Open-circle markers; HMBC legend (ok=green / potential_4J=amber / 1J_artifact=grey)
   with matching coloured markers; COSY diagonal runs top-left → bottom-right.
4. **No flicker/memory growth (mtime cache + figure release)** — ✓
   Covered by `test_spectra_2d_cache_hit_no_rerender` + `test_spectra_2d_cache_bounded`
   (cache len ≤ 3) + `try/finally` figure release; live ~3 s poll shows no churn.
5. **Per-plot "unavailable" placeholder, never 500** — ✓
   Covered by the 3 passing `spectra_2d and placeholder` tests (absent manifest /
   stale path / no matching experiment → placeholder PNG, HTTP 200).

## Defect found during verification (and fixed)

**SC1 F1/y-axis inversion.** `_apply_nmr_axes_2d` mirrored the 1D x-axis recipe onto
the y-axis (`set_ylim(f1[0], f1[-1])` = high→low), placing high ppm at the BOTTOM.
Aromatic carbons (F1 ~130) rendered at the bottom instead of top-left — violating SC1.
The headless test asserted the wrong direction (`ylim[0] > ylim[1]`), so it passed while
the display was upside-down. Fixed: `set_ylim(f1[-1], f1[0])` (downfield at the top);
test updated to require high-ppm-at-top (`ylim[1] > ylim[0]`, downfield endpoint at top).
Re-verified by re-rendering HSQC/HMBC/COSY against real CASE1 data (aromatic top-left;
COSY diagonal top-left → bottom-right) and live in the browser.

Fix commit: `fix(96): correct 2D F1 (y) axis direction — downfield at top (SC1)`.

## Verification commands

- `pytest tests/test_webview_api.py` → 60 passed, 12→0 skipped-become-real for 2D.
- `ruff check src/lucy_ng/webview/routers/spectra.py tests/test_webview_api.py` → clean.
- Live: `lucy webview serve <analysis_dir>` → 2D Spectra tab, all three plots correct.

No further defects. Phase 96 acceptance criteria SC1–SC4 satisfied.
