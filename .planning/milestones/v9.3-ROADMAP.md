# lucy-ng Roadmap

## Milestones

- [v1.0 Core CASE Pipeline](milestones/v1.0-ROADMAP.md) - Phases 1-10 (shipped 2026-01-12)
- [v1.1 Database-Backed Dereplication](milestones/v1.1-ROADMAP.md) - Phases 11-15 (shipped 2026-01-15)
- [v1.2 HOSE Database Prediction](milestones/v1.2-ROADMAP.md) - Phases 16-19 (shipped 2026-01-18)
- **v2.0 Robust Multi-Agent CASE** - Phases 20-26 (shipped 2026-02-08)
- **v2.1 Working Multi-Agent CASE** - Phases 27-33 (shipped 2026-02-09)
- [v3.0 Statistical Detection](milestones/v3.0-ROADMAP.md) - Phases 34-40 (shipped 2026-02-16)
- [v4.0 Team-Based CASE](milestones/v4.0-ROADMAP.md) - Phases 41-48 (shipped 2026-02-18)
- [v5.0 Fragment Library](milestones/v5.0-ROADMAP.md) - Phases 49-54 (shipped 2026-02-21)
- [v6.0 Skill Quality Overhaul](milestones/v6.0-ROADMAP.md) - Phases 55-58 (shipped 2026-03-10)
- [v7.0 Statistical 4J Detection](milestones/v7.0-ROADMAP.md) - Phases 59-64 (ABANDONED 2026-03-12)
- **v8.0 pyLSD Integration** - Phases 65-71 (superseded by v9.0 before UAT passed)
- ✅ [v9.0 CASE Reliability & Skill Consolidation](milestones/v9.0-ROADMAP.md) - Phases 72-85 (shipped 2026-06-17)
- ✅ [v9.1 CASE Final-Answer Correctness & Verification Gates](milestones/v9.1-ROADMAP.md) - Phases 86-89 (shipped 2026-06-29)
- ✅ [v9.2 CASE Web-View](milestones/v9.2-ROADMAP.md) - Phases 90-92 (shipped 2026-07-07)
- **v9.3 CASE Web-View Stage 2** - Phases 93-96 (in progress)

---

**v9.2 outcome:** A read-only web dashboard makes a CASE run observable live and after the fact —
`lucy webview serve/stop/status`, four JSON/SVG endpoints with graceful degradation, RDKit SVG
depictions, single-file vanilla-JS dashboard, auto-launched by `case.md`. Live-validated on CASE1
(ibuprofen, Rank 1 MAE 0.25). Full archive: [`milestones/v9.2-ROADMAP.md`](milestones/v9.2-ROADMAP.md).

---

## v9.3 CASE Web-View Stage 2

**Goal:** Grow the read-only CASE webview from a status monitor into a full run inspector — a
formatted run log plus **real rendered spectra with the picked peaks overlaid** (so the user can
immediately judge peak-picking quality against the actual data) and peak/constraint data tables,
all organized in tabs. Builds on the v9.2 architecture where "tabs dock in without a rewrite."

### Phases

- [x] **Phase 93: Formatted Log + Tab Framework** — tab navigation bar + hand-rolled markdown renderer for the run log; pure frontend, no new backend (completed 2026-07-08)
- [x] **Phase 94: Data Tables** — new `tables.py` router reading `analysis/peaks/*.json` + `iteration_NN/compound.lsd`; ¹³C signals, correlations, and LSD constraint inventory tables (completed 2026-07-09)
- [x] **Phase 95: 1D Real Spectra + Peak Overlay** — new `spectra.py` router; real Bruker 1D traces via BrukerReader/nmrglue with picked peaks overlaid; matplotlib added to `[webview]` extra; Bruker-path wiring via `.run_manifest.json` (completed 2026-07-09)
- [x] **Phase 96: 2D Real Spectra + Peak Overlay** — extends `spectra.py` with HSQC/HMBC/COSY contour plots + cross-peak overlay; decimation + threshold levels + mtime PNG cache (completed 2026-07-12)

### Phase Details

#### Phase 93: Formatted Log + Tab Framework

**Goal**: Users can navigate the dashboard via a persistent tab bar and see the run log rendered as formatted markdown — headings, bold, tables, monospace — instead of raw text.
**Depends on**: Phase 92 (v9.2 shipped — existing server, endpoints, and frontend are the base)
**Requirements**: LOG-01, TAB-01
**Success Criteria** (what must be TRUE):
  1. User sees a tab bar (Run Log / 1D Spectra / 2D Spectra / Tables) and clicking a tab shows that panel while hiding the others, with no page reload.
  2. The run log displays CASE-PROGRESS.md with formatted headings (`## Iteration N`, `### Agent`), bold agent names, pipe-tables, and monospace code blocks instead of raw text; content updates on the existing ~3 s refresh.
  3. Injecting `# <img src=x onerror=alert(1)>` into a mock CASE-PROGRESS.md renders as literal escaped text in the browser, not as an HTML element — the v9.2 XSS discipline (textContent throughout, never innerHTML of server content) is preserved.
  4. `static/webview.js` is extracted from `index.html`, served via an explicit `/webview.js` route in `app.py`, and present in the installed wheel (existing `src/lucy_ng/webview/static/*` hatch artifact glob covers it).

**Plans**: 3 plans
- [x] 93-01-PLAN.md — Extract webview.js + `/webview.js` route + Wave 0 route/packaging tests
- [x] 93-02-PLAN.md — Tab bar (4 tabs) + hand-rolled markdown-to-DOM renderer + innerHTML XSS-guard test
- [x] 93-03-PLAN.md — Manual browser checkpoint: XSS escaping + tab switching + typography hierarchy

**UI hint**: yes

---

#### Phase 94: Data Tables

**Goal**: Users can inspect raw peak data (¹³C signals, HSQC/HMBC/COSY correlations) and the LSD constraint inventory as formatted tables in the Tables tab.
**Depends on**: Phase 93
**Requirements**: TBL-01, TBL-02, TBL-03
**Success Criteria** (what must be TRUE):
  1. User sees the ¹³C signal table (columns: ppm, multiplicity, nC, assignment) populated from `analysis/peaks/carbon_signals.json`.
  2. User sees HSQC, HMBC, and COSY correlation tables from `analysis/peaks/{hsqc,hmbc,cosy}.json`, with shift columns and flag colouring on HMBC rows.
  3. User sees the LSD constraint inventory table (constraint type, atom indices, note) parsed from the JSON block in the latest `iteration_NN/compound.lsd` header.
  4. When any peak JSON file or `compound.lsd` is absent or partially written during a live run, the corresponding table panel shows a "waiting for data" state — HTTP 200 response, never a 500 error.

**Plans**: 4 plans
- [x] 94-01-PLAN.md — Wave 0: hand-authored peaks/compound.lsd fixtures + TestTablesEndpoint (RED-by-skip)
- [x] 94-02-PLAN.md — Backend: tables.py router (5 /api/tables routes, never-500) + app.py docking
- [x] 94-03-PLAN.md — Frontend: 5 Tables-tab sections, HMBC flag colouring, compact intensity, TBL-03 structured view
- [x] 94-04-PLAN.md — Manual browser checkpoint: HMBC colours + captions + intensity + TBL-03 layout

**UI hint**: yes

---

#### Phase 95: 1D Real Spectra + Peak Overlay

**Goal**: Users see real ¹³C (and ¹H if present) spectrum traces rendered from the raw Bruker data with the picked peaks overlaid as markers, enabling visual validation of peak-picking quality against the actual signal.
**Depends on**: Phase 93, Phase 94
**Requirements**: SP1-01, SP-02
**Success Criteria** (what must be TRUE):
  1. User sees the ¹³C spectrum as a real continuous trace (BrukerReader + nmrglue from the raw Bruker processed data) with a reversed ppm axis (high ppm on the left) and the picked peaks overlaid as vertical markers from `analysis/peaks/carbon_signals.json`.
  2. On CASE1 (ibuprofen), the carbonyl peak (~181 ppm) appears on the far left of the ¹³C chart and the aliphatic CH3 groups appear on the right; `ax.get_xlim()[0] > ax.get_xlim()[1]` holds in tests (NMR axis direction correct).
  3. A clean `pip install lucy-ng[webview]` can serve the 1D Spectra tab (matplotlib declared in the `[webview]` extra); `from lucy_ng.cli import cli` on a base install without the extra does not raise ImportError; all matplotlib imports are lazy inside `make_router()` per WV-08.
  4. When `.run_manifest.json` is absent (no live CASE run) or the peak JSON is missing, the 1D Spectra tab shows a "unavailable / waiting for data" message — HTTP 200, never a 500 error.

**Plans**: 4 plans
- [x] 95-01-PLAN.md — Wave 0: matplotlib in [webview] extra + TestSpectraEndpoint (RED-by-skip)
- [x] 95-02-PLAN.md — Backend: spectra.py router (real ¹³C/¹H trace + overlay, reversed axis, never-500 PNG) + app.py docking
- [x] 95-03-PLAN.md — Frontend: 1D Spectra tab img mounts + refreshSpectra1D + case.md .run_manifest.json write
- [x] 95-04-PLAN.md — Manual browser checkpoint: real trace, reversed axis, peak overlay, unavailable states

**UI hint**: yes

---

#### Phase 96: 2D Real Spectra + Peak Overlay

**Goal**: Users see real HSQC, HMBC, and COSY contour plots rendered from the raw Bruker 2D data with the picked cross-peaks overlaid, completing the full spectral inspection suite.
**Depends on**: Phase 95
**Requirements**: SP2-01
**Success Criteria** (what must be TRUE):
  1. User sees the HSQC contour plot with reversed ppm axes on both dimensions (aromatic region at top-left: F2 ~7 ppm, F1 ~130 ppm) and the HSQC cross-peaks from `analysis/peaks/hsqc.json` overlaid as scatter markers.
  2. User sees HMBC and COSY contour plots with cross-peaks overlaid; HMBC cross-peak markers are colour-coded by flag value from `analysis/peaks/hmbc.json`.
  3. Render time is under 1 s per request: 2D data is decimated to at most 512×512 before contouring, contour levels are threshold-based (MAD-derived noise floor), and rendered PNGs are cached keyed by source file mtime — the 3 s browser polling loop does not trigger re-renders on a cache hit.
  4. Repeated browser polling does not cause memory growth — figures are closed after each render (`try/finally`) and the mtime cache prevents unbounded Figure allocation.

**Plans**: 4 plans
- [x] 96-01-PLAN.md — Wave 0: hand-authored 2D peak fixtures + TestSpectraEndpoint2D (RED-by-skip)
- [x] 96-02-PLAN.md — Backend: spectra.py 2D routes (HSQC/HMBC/COSY contour + overlay, reversed axes, mtime cache, never-500) + app.py docstring
- [x] 96-03-PLAN.md — Frontend: three stacked 2D img sections + refreshSpectra2D wired into tick()
- [x] 96-04-PLAN.md — Manual browser checkpoint: real contours, reversed axes, HMBC flag colours, COSY diagonal, unavailable states

**UI hint**: yes

---

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 93. Formatted Log + Tab Framework | 3/3 | Complete   | 2026-07-08 |
| 94. Data Tables | 4/4 | Complete   | 2026-07-09 |
| 95. 1D Real Spectra + Peak Overlay | 5/5 | Complete    | 2026-07-09 |
| 96. 2D Real Spectra + Peak Overlay | 4/4 | Complete    | 2026-07-12 |
