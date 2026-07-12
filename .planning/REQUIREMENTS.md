# Requirements: lucy-ng v9.3 — CASE Web-View Stage 2

**Milestone goal:** Grow the read-only CASE webview from a status monitor into a full run inspector — a formatted run log plus **real rendered spectra with the picked peaks overlaid** and data tables, organized in tabs. The overlay lets the user immediately judge whether the peak-picking makes sense against the actual spectrum.

**Builds on:** v9.2 (WV-01..08) — FastAPI `create_app(analysis_dir)` + `make_router` routers, single-file vanilla-JS frontend, RDKit depictions, graceful degradation, `[webview]` optional extra, WV-08 import-safety. Research: `.planning/research/SUMMARY.md` (+ STACK/FEATURES/ARCHITECTURE/PITFALLS).

---

## v9.3 Requirements

### Formatted Log & Tabs

- [ ] **LOG-01**: User sees the run log (`CASE-PROGRESS.md`) rendered with markdown formatting — headings, agent sections, **bold**, tables, monospace code — instead of raw text, updated live on the existing ~3 s refresh.
- [ ] **TAB-01**: User navigates the dashboard via tabs (Overview / Structures / Spectra / Tables / Log) without a page reload; the existing v9.2 widgets remain reachable.

### Data Tables

- [x] **TBL-01**: User sees the ¹³C signal table (ppm, multiplicity, nC, assignment) from the curated `analysis/peaks/carbon_signals.json`.
- [x] **TBL-02**: User sees the correlation tables — HSQC (one-bond), HMBC (long-range), COSY — from `analysis/peaks/{hsqc,hmbc,cosy}.json`, with shifts and flags.
- [x] **TBL-03**: User sees the LSD constraint inventory (the constraints fed to the solver — MULT/HSQC/HMBC/BOND/etc.) parsed from the latest `iteration_NN/compound.lsd`.

### Spectra (real trace + peak overlay)

- [x] **SP1-01**: User sees the real 1D spectrum (¹³C, plus ¹H if present) rendered as a line plot with a **reversed ppm axis**, with the picked peaks overlaid (markers/labels at their positions from the peak JSON) so the peak-picking can be visually validated against the data.
- [x] **SP2-01**: User sees the real 2D spectra (HSQC, HMBC, COSY) rendered as contour plots with **reversed ppm axes on both dimensions**, with the picked cross-peaks overlaid.
- [x] **SP-02**: When a spectrum or its peak data is missing, partial, or the raw experiment data cannot be located, the corresponding tab shows a well-formed "unavailable / waiting for data" state (HTTP 200, never 500) — consistent with v9.2 graceful degradation.

---

## Future Requirements (deferred)

- DEPT sub-tab / DEPT-135 phase display (P2 — needs a `multiplicity_edited` test case).
- Interactive spectrum zoom / pan (would need a client plotting lib — conflicts with the no-build/no-CDN constraint).
- SSE/WebSocket live push to replace 3 s polling (optional optimization; no functional gain).
- Re-processing raw FIDs from scratch in the dashboard (the server renders already-processed spectra; it is not an NMR processing tool).

## Out of Scope

- Editing or re-picking peaks from the dashboard — the webview stays strictly read-only.
- Any control over the CASE run (the dashboard is observability only).
- New heavy frontend frameworks, build tooling, or external CDNs — the frontend stays self-contained vanilla JS.

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| LOG-01 | Phase 93 | Pending |
| TAB-01 | Phase 93 | Pending |
| TBL-01 | Phase 94 | Complete |
| TBL-02 | Phase 94 | Complete |
| TBL-03 | Phase 94 | Complete |
| SP1-01 | Phase 95 | Complete |
| SP-02  | Phase 95 | Complete |
| SP2-01 | Phase 96 | Complete |
