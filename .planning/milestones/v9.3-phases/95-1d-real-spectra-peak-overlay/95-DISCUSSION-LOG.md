# Phase 95: 1D Real Spectra + Peak Overlay - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 95-1d-real-spectra-peak-overlay
**Areas discussed:** No-manifest empty-state, Experiment selection & ¹H scope, Peak-overlay style, Manifest-path & trust

---

## Pre-discussion clarification (resolved without a question)

A conflict was surfaced and settled from the docs, not asked of the user:
- **ROADMAP/STATE (locked v9.3):** real continuous Bruker traces via BrukerReader/nmrglue
  from raw processed data, wired via `.run_manifest.json`.
- **`research/SUMMARY.md` (2026-07-07, pre-roadmap):** claimed spectra should be sticks
  from peak JSON, "no nmrglue, no run_manifest."
- **Resolution:** ROADMAP SC1 + STATE §Bruker-path-wiring win (research SUMMARY is
  superseded). Real traces + `.run_manifest.json` treated as locked.

Also confirmed from code: `nmrglue`/`numpy` are already **base** deps — only `matplotlib`
needs the `[webview]` extra.

---

## No-manifest empty-state

| Option | Description | Selected |
|--------|-------------|----------|
| Strict "unavailable" (SP-02/SC4) | Simplest, requirement-aligned; a stick plot from the same peak JSON is circular / no validation value | ✓ |
| Stick-fallback from carbon_signals.json | Tab useful without a live run, but 2nd render path + low validation value | |

**User's choice:** Strict "unavailable" → **D-01**
**Notes:** The phase's purpose is validating peak-picking against the *real* signal; a
JSON-derived stick replot adds nothing.

---

## Experiment selection & ¹H scope

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-detect by nucleus; ¹³C always + ¹H when present | Scan Bruker subdirs, read acqus $NUC1; no hard-coded experiment numbers; matches SP1-01 "¹H if present" | ✓ |
| ¹³C-only now, ¹H → v9.4 | Tighter phase, drops SP1-01's ¹H clause | |

**User's choice:** Auto-detect by nucleus → **D-02**
**Notes:** ¹H rendered only when a ¹H 1D experiment is found.

---

## Peak-overlay style

| Option | Description | Selected |
|--------|-------------|----------|
| Vertical markers + ppm labels (+ assignment when present) | Thin vertical tick at each peak ppm on the line trace, ppm-value label, assignment label if available | ✓ |
| Marker + assignment (no ppm label) | Chemist-oriented, less numeric clutter | |
| Markers only, no labels | Cleanest, least informative | |

**User's choice:** Vertical markers + ppm labels → **D-03**
**Notes:** Continuous line plot, reversed ppm axis (`ax.get_xlim()[0] > ax.get_xlim()[1]`).

---

## Manifest-path & trust

| Option | Description | Selected |
|--------|-------------|----------|
| Stale → "unavailable", trust the absolute path | SP-02 "cannot be located" → treat like absent; trust the case.md-written manifest path; no sandboxing | ✓ |
| Additional path validation | More defensive, unneeded overhead for a localhost single-user tool | |

**User's choice:** Stale → "unavailable", trust absolute path → **D-05 / D-07**
**Notes:** Never 500 on a bad path.

---

## Claude's Discretion

- Endpoint shape (per-nucleus routes vs `?nucleus=`), multi-candidate experiment tiebreak,
  matplotlib figure sizing/DPI/typography/colours, ¹H panel layout (separate `<img>` vs
  stacked figure), internal helper/module organisation. (See CONTEXT.md D-04/D-06 + Discretion.)

## Deferred Ideas

- 1D render caching → Phase 96 mtime cache pattern (D-06).
- 2D contour spectra → Phase 96.
- Interactive zoom/pan, DEPT sub-tab, SSE push → v9.4.
- Stick-spectrum fallback → rejected (D-01), not revisited.
