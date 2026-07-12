---
phase: 96-2d-real-spectra-peak-overlay
reviewed: 2026-07-12T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/lucy_ng/webview/routers/spectra.py
  - src/lucy_ng/webview/app.py
  - src/lucy_ng/webview/static/index.html
  - src/lucy_ng/webview/static/webview.js
  - tests/test_webview_api.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
resolution:
  cr-01: fixed
  wr-01: fixed
  wr-02: accepted-followup
  wr-03: accepted-followup
  in-01: accepted-followup
  in-02: accepted-followup
status: resolved
---

# Phase 96: Code Review Report

**Reviewed:** 2026-07-12
**Depth:** standard
**Files Reviewed:** 5
**Status:** resolved (CR-01 + WR-01 fixed in commit `fix(96): 2D placeholder figsize + analysis_dir-scoped cache`; WR-02/WR-03/IN-01/IN-02 accepted as non-blocking follow-ups)

## Resolution (post-review)

- **CR-01 (Critical) — FIXED:** `_render_placeholder_png` now takes a `figsize`
  parameter; the 2D routes pass `_FIGSIZE_2D` so the "unavailable" placeholder is
  900×600 like the real 2D render (no layout jump). Regression-guarded by a
  900×600 PNG-IHDR assertion on `test_spectra_2d_missing_manifest_placeholder`.
- **WR-01 (Warning) — FIXED:** the `_png_cache` key is now scoped by `analysis_dir`
  (`f"{analysis_dir}:{kind}"`), eliminating cross-instance aliasing when source
  mtimes coincide.
- **WR-02 (double directory scan / TOCTOU) — ACCEPTED FOLLOW-UP:** a perf/robustness
  refactor (dedup `_select_experiment_2d` + `_selected_2d_pdata_path`); no
  correctness bug in the single-process, static-filesystem webview use. Noted for a
  future cleanup.
- **WR-03 (all-rows-malformed peak JSON → no "unavailable" note) — ACCEPTED FOLLOW-UP:**
  edge case that does not occur with real detector output (which emits well-formed
  rows or an absent file); fixing requires threading plotted-count back from the
  overlay plotters. Deferred.
- **IN-01 (sub-ppm axis-tail clip) / IN-02 (nested ternary readability) — ACCEPTED:**
  cosmetic; no action.

## Summary

Phase 96 extends `spectra.py` with three new `/api/spectra/2d/{hsqc,hmbc,cosy}` PNG
routes, block-max decimation, MAD-derived geometric contour levels, an mtime-keyed PNG
cache, and per-experiment-type overlay/legend rendering. The core domain logic checks
out: `ax.contour(f2s, f1s, decimated, ...)` correctly matches the verified
`data.shape == (len(f1), len(f2))` orientation with no transpose; `_apply_nmr_axes_2d`'s
x/y reversal logic is correct (confirmed by a live unit-test run — `xlim[0] > xlim[1]`,
`ylim[1] > ylim[0]` with the high F1 endpoint at the top); the never-500 guard, WV-08
lazy-import discipline, and `try/finally` figure release are all intact; `ruff` and
`mypy` report zero new issues in this module; all 60 webview tests (13 of them
Phase‑96‑specific, run live against the real CASE1 dataset) pass.

However, one concrete, live-reproduced defect directly violates a LOCKED, explicitly
documented acceptance criterion (96-UI-SPEC.md: figure sizing "applies to both the
real-contour and placeholder-chart render paths for all three routes, so layout never
jumps between states") — the shared placeholder renderer was never updated to use the
2D figure size, so every 2D "unavailable" placeholder (the state shown for the first
several seconds/minutes of every CASE run, before an HSQC/HMBC/COSY experiment is
found) renders at half the height of the real chart, and the panel visibly jumps
taller the moment real data appears. Three further Warning/Info-level issues (a
module-global PNG cache that is not scoped to `analysis_dir`, duplicated/duplicated-effort
2D experiment-selection scanning, and per-peak silent-degradation gaps) are also
documented below.

## Critical Issues

### CR-01: 2D placeholder PNG uses the 1D figsize — violates the locked "no layout jump" requirement

**File:** `src/lucy_ng/webview/routers/spectra.py:663-691` (`_render_placeholder_png`), called from `_render_2d` at `:792-822`

**Issue:** `96-UI-SPEC.md` (lines 276-283) locks the 2D figure size at `figsize=(9.0, 6.0)`
and explicitly states this "applies to both the real-contour and placeholder-chart
render paths for all three routes, so layout never jumps between states." The
implementation never gave `_render_placeholder_png` a figsize parameter — it hard-codes
`figure_cls(figsize=_FIGSIZE, dpi=_DPI)` where `_FIGSIZE = (9.0, 3.0)` (the 1D size), and
every one of the three 2D routes (`_render_2d`'s `_MSG_NO_MANIFEST` / `_MSG_STALE_PATH`
/ `_MSG_NO_HSQC` / `_MSG_NO_HMBC` / `_MSG_NO_COSY` branches, plus the outer
`except Exception` never-500 fallback) calls this same unparameterized helper.

Live-rendered proof (both PNGs produced by the actual shipped functions):
```
placeholder size (used for every 2D "unavailable" state): (900, 300)
real 2D render size (_FIGSIZE_2D @ 100 dpi):               (900, 600)
```
Since `.spectrum-img { width: 100%; height: auto; }` (index.html:372-378) scales purely
by the image's native aspect ratio, the HSQC/HMBC/COSY panels render at half height
during "No HSQC experiment found in this dataset." / "Waiting for a live CASE run…" /
any other placeholder state, then visibly double in height the instant a real
experiment is found and the first real contour renders — precisely the layout jump the
locked spec says must not happen. Untestable-by-omission: none of the 13 new
`TestSpectraEndpoint2D` tests assert placeholder PNG dimensions, so this regressed
silently past the test suite.

**Fix:** Give `_render_placeholder_png` a `figsize` parameter (default `_FIGSIZE` for the
1D callers) and pass `_FIGSIZE_2D` from the three 2D placeholder call sites:

```python
def _render_placeholder_png(
    figure_cls: Any, canvas_cls: Any, message: str, *, figsize: tuple[float, float] = _FIGSIZE
) -> bytes:
    fig = figure_cls(figsize=figsize, dpi=_DPI)
    ...

# in _render_2d's every _render_placeholder_png(...) call site:
return _render_placeholder_png(Figure, FigureCanvasAgg, _MSG_NO_MANIFEST, figsize=_FIGSIZE_2D)
```
Add a regression test asserting `Image.open(io.BytesIO(png)).size == (900, 600)` for a
2D-route placeholder PNG (mirroring the existing `len(r.content) > 0` checks, which are
too weak to catch this class of bug).

## Warnings

### WR-01: `_png_cache` is a bare module-level global, not scoped per `analysis_dir` — contradicts its own docstring

**File:** `src/lucy_ng/webview/routers/spectra.py:365-370, 383-388`

**Issue:** The cache comment claims it is "closed over by `make_router()`" and
96-RESEARCH.md's Security Domain explicitly asserts "the module-level `_png_cache` dict
is closed over per-router-instance inside `make_router()`, not shared across
`analysis_dir`s." Neither claim matches the code: `_png_cache` is declared at module
scope (outside `make_router()`), so it is one dict shared by **every** `make_router()`
call in the process, keyed only on `(kind, source_mtime)` — never on `analysis_dir`.
Verified live:
```python
_png_cache.clear()
_cached_or_render("hsqc", 100.0, lambda: b"AAA")   # -> b"AAA"
_cached_or_render("hsqc", 200.0, lambda: b"BBB")   # -> b"BBB" (different mtime, re-renders)
_cached_or_render("hsqc", 200.0, lambda: b"CCC")   # -> b"BBB" -- cache hit from a
                                                    #    DIFFERENT analysis_dir/request
                                                    #    that coincidentally shares mtime 200.0
```
In production this is low-risk today (`lucy webview serve` launches one process per
`analysis_dir`, confirmed via `cli/webview.py`'s per-`ANALYSIS_DIR` `start`/`stop`
subprocess model), but it is still a real defect: (1) it directly contradicts the
module's and the research doc's own stated invariant, (2) it creates test-order-dependent
pollution in this exact test file — several `TestSpectraEndpoint2D` tests must manually
call `spectra._png_cache.clear()` to get a deterministic result, while others
(`test_spectra_2d_hsqc_returns_png_on_case1_real`, `..._hmbc_...`, `..._cosy_...`) do
not, and silently rely on whichever test ran first to have already populated the shared
cache with the real CASE1 mtime, and (3) any future change toward a
multi-analysis-dir-per-process server (e.g. an admin dashboard) would silently leak
cached PNGs across unrelated runs.

**Fix:** Either move `_png_cache` inside `make_router()` (a real per-router-instance
closure, matching the docstring's claim) or key cache entries on
`(str(analysis_dir), kind, source_mtime)` if a module-level dict is intentionally kept
for simplicity.

### WR-02: 2D experiment selection is scanned twice per request via duplicated logic

**File:** `src/lucy_ng/webview/routers/spectra.py:165-247, 792-808`

**Issue:** `_select_experiment_2d` (used to obtain the `Spectrum2D` to render) and
`_selected_2d_pdata_path` (used only to compute the cache-key mtime) are two
independent, byte-for-byte-duplicated implementations of the same directory scan +
`BrukerReader.read_2d()` + lowest-experiment-number tiebreak. `_render_2d` calls both,
one after the other, on every request that isn't served by the render cache (and even
on cache hits it still calls `_select_experiment_2d` first to check `spectrum is None`).
This means `read_2d()` — which reads and parses the entire `pdata/1/2rr` binary via
nmrglue — is invoked twice per render. Beyond the (out-of-scope) performance cost, the
duplication is a maintainability/consistency risk: the two scans run against a
filesystem that may be actively written by a live CASE run, so if a new matching
experiment directory (e.g. from a re-run) appears between the two independent scans, the
`Spectrum2D` actually rendered and the mtime the cache is keyed on can end up describing
two *different* experiment directories with no way to detect the mismatch.

**Fix:** Have `_select_experiment_2d` return the selected `exp_dir: Path` alongside the
`Spectrum2D` (e.g. a small `tuple[Path, Spectrum2D]` or a dataclass), and derive both the
render input and the cache-key path from that single scan. If the existing frozen test
`test_spectra_2d_select_experiment_2d_keeps_only_acqu2s` truly pins the current
`Spectrum2D | None` return signature, introduce a new combined helper
(`_select_experiment_2d_with_path`) that both call sites in `_render_2d` use instead of
either of the two current ones.

### WR-03: Peaks JSON present but every row malformed silently renders with no markers and no "unavailable" note

**File:** `src/lucy_ng/webview/routers/spectra.py:631-653` (mirrors the same gap already
present in `_render_1d_png`, `:549-561`)

**Issue:** `_render_2d_png`'s peaks branch is keyed purely on `if peaks:` (i.e., is the
list non-empty), not on whether any row actually produced a plotted marker. If
`analysis/peaks/hsqc.json` (etc.) exists with a non-empty `peaks` list but every row is
missing/mistyped `carbon_ppm`/`proton_ppm` (e.g. a schema drift or partial-write from a
concurrently-running CASE process), `_plot_uniform_overlay`/`_plot_hmbc_overlay` skip
every row via their per-peak `try/except`, so zero markers are drawn — but the
mutually-exclusive `_MSG_PEAKS_UNAVAILABLE` annotation is also never drawn, because that
branch only fires when `peaks` (the raw list) is empty. The chart silently looks like
"no cross-peaks exist" when the real state is "the peaks file could not be parsed",
which is exactly the ambiguity SP-02's degradation contract is meant to avoid.

**Fix:** Track whether at least one peak was actually plotted (e.g. have the
`_plot_*_overlay` helpers return a plotted-count) and show the "peak positions
unavailable" annotation whenever that count is zero, regardless of whether the raw list
was empty or fully-malformed.

## Info

### IN-01: Decimated ppm scale can clip up to `step-1` samples off the axis's low-ppm tail

**File:** `src/lucy_ng/webview/routers/spectra.py:317-346` (`_block_max_decimate`)

**Issue:** `dec_a = scale_a[::step_y][: decimated.shape[0]]` strides the *original*
(un-padded) scale array. For any dataset that actually needs decimation (e.g. 1024→512,
step 2), the last retained scale sample is `scale_a[::step_y][-1]`, not `scale_a[-1]`
unless `(len(scale_a) - 1)` happens to be an exact multiple of `step_y`. `_apply_nmr_axes_2d`
then sets `xlim`/`ylim` from these decimated-scale endpoints, so the displayed axis range
is very slightly narrower than the spectrum's true acquisition window (a fraction of one
ppm-per-point, e.g. ~0.01 ppm for the verified CASE1 HSQC/HMBC shapes) — in the
extremely unlikely case a picked cross-peak sits inside that clipped margin, it would be
silently cut off by the axis limit rather than appearing at the plot edge. Effect is
negligible in practice given real spectral windows, but worth a one-line fix for
correctness.

**Fix:** Compute axis limits from the *original* (un-decimated) `f1_ppm_scale[-1]`/
`f2_ppm_scale[-1]` rather than the decimated tail sample, since the true axis extent is
independent of the decimation stride.

### IN-02: Cramped nested ternary in `_plot_hmbc_overlay` hurts readability

**File:** `src/lucy_ng/webview/routers/spectra.py:474-477`

**Issue:**
```python
color = _HMBC_FLAG_COLORS.get(flag, _DEFAULT_FLAG_COLOR) if isinstance(flag, str) else (
    _DEFAULT_FLAG_COLOR
)
```
The parenthesized single-value else-branch reads as if it were doing more than it is; a
plain if/else or an early-return reads more clearly.

**Fix:**
```python
color = _HMBC_FLAG_COLORS.get(flag, _DEFAULT_FLAG_COLOR) if isinstance(flag, str) else _DEFAULT_FLAG_COLOR
```
or split into an explicit `if isinstance(flag, str): color = ... else: color = ...` block.

---

_Reviewed: 2026-07-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
