---
gsd_state_version: 1.0
milestone: v9.3
milestone_name: CASE Web-View Stage 2
status: executing
stopped_at: Phase 96 context gathered
last_updated: "2026-07-11T12:03:46.468Z"
last_activity: 2026-07-11 -- Phase 96 planning complete
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 16
  completed_plans: 12
  percent: 75
---

# lucy-ng State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-07)

**Core value:** AI agent autonomously determines compound structures from NMR, with a multi-agent team that uses the intended solver pipeline — not a manual bypass
**Current focus:** Phase 96 — 2d real spectra + peak overlay

## Current Position

Phase: 96
Plan: Not started
Next: Phase 95 (1D Real Spectra + Peak Overlay) — introduces Bruker-path wiring + matplotlib Agg
Status: Ready to execute
Last activity: 2026-07-11 -- Phase 96 planning complete

```
Progress: [██████████░░░░░░░░░░] 50% (2/4 phases)
```

## Milestone v9.3 Phases

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 93. Formatted Log + Tab Framework | Tab navigation bar + hand-rolled markdown renderer; pure frontend | LOG-01, TAB-01 | — |
| 94. Data Tables | `tables.py` router reading `analysis/peaks/*.json` + `compound.lsd`; ¹³C signals, correlations, LSD constraints | TBL-01, TBL-02, TBL-03 | 93 |
| 95. 1D Real Spectra + Peak Overlay | `spectra.py` router; real Bruker 1D traces + peak overlay; matplotlib in `[webview]` extra; `.run_manifest.json` path wiring | SP1-01, SP-02 | 93, 94 |
| 96. 2D Real Spectra + Peak Overlay | Extends `spectra.py` with HSQC/HMBC/COSY contour + cross-peak overlay; decimation + cache | SP2-01 | 95 |

**Sequencing:** Phase 93 (tab framework + markdown log) ships first as a pure frontend change — it establishes the tab dock-in that all later phases populate and carries zero backend risk. Phase 94 (data tables) comes next, establishing the `analysis/`-only router pattern without matplotlib. Phase 95 (1D spectra) introduces the Bruker-path wiring (`.run_manifest.json` written by `case.md`) and the matplotlib Agg pipeline — two cross-cutting concerns that Phase 96 inherits. Phase 96 (2D spectra) is purely additive to Phase 95: same router, same manifest, same matplotlib backend, only adds 2D contour logic + caching.

## Deferred Items

Items acknowledged and deferred at **v9.2 CASE Web-View milestone close on 2026-07-07** (carried into v9.3 or later):

| Category | Item | Status | Note |
|----------|------|--------|------|
| stage-2 | Formatted run log (render CASE-PROGRESS.md markdown: headings/bold/tables) | ACTIVE → Phase 93 | Deferred in Phase 91 with an explicit "revisit if the raw log proves hard to read" trigger — trigger met on the live CASE1 run. Reverses D-13. |
| stage-2 | Rendered spectra tabs + data tables (1D ¹³C/¹H, 2D HSQC/HMBC/COSY; peak lists, constraint inventory) | ACTIVE → Phases 94-96 | Explicit Stage 2 per design spec. Architecture built to accommodate. |
| defer-v9.4 | DEPT sub-tab (CH/CH2/CH3 signed bar chart) | deferred → v9.4 | Conditional on `multiplicity_edited` field in hsqc.json; P2 deliverable |
| defer-v9.4 | Interactive spectrum zoom/pan | deferred | Would require a JS charting library; conflicts with no-build/no-CDN constraint |
| defer-v9.4 | SSE/WebSocket live push replacing 3 s polling | deferred | Optional optimization; no functional gain |
| todo | 2026-06-30-ranking-tests-hardfail-without-hosegen | deferred | Test-infra todo from v9.1; unrelated to webview |
| todo | 2026-06-25-case4-azulene-regiochemistry-enumeration-gap | carried (from v9.1) | Still open; unrelated to webview |

Items acknowledged and deferred at **v9.1 milestone close on 2026-06-29**:

| Category | Item | Status | Note |
|----------|------|--------|------|
| todo | 2026-06-25-case4-azulene-regiochemistry-enumeration-gap | deferred | NEW 4th defect class from v9.1 UAT-01; di-methyl-ethyl class now searched, exact chamazulene regiochemistry still unreachable. Carried-seed. |

## Completed Milestones

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Core CASE Pipeline | 1-10 | 2026-01-12 |
| v1.1 Database-Backed Dereplication | 11-15 | 2026-01-15 |
| v1.2 HOSE Database Prediction | 16-19 | 2026-01-18 |
| v2.0 Robust Multi-Agent CASE | 20-26 | 2026-02-08 |
| v2.1 Working Multi-Agent CASE | 27-33 | 2026-02-09 |
| v3.0 Statistical Detection | 34-40 | 2026-02-16 |
| v4.0 Team-Based CASE | 41-48 | 2026-02-18 |
| v5.0 Fragment Library | 49-54 | 2026-02-21 |
| v6.0 Skill Quality Overhaul | 55-58 | 2026-03-10 |
| v7.0 Statistical 4J Detection | 59-64 | ABANDONED 2026-03-12 |
| v8.0 pyLSD Integration | 65-71 | Superseded by v9.0 (UAT failed as mechanism validation) |
| v9.0 CASE Reliability & Skill Consolidation | 72-85 | 2026-06-17 |
| v9.1 CASE Final-Answer Correctness & Verification Gates | 86-89 | 2026-06-29 |
| v9.2 CASE Web-View | 90-92 | 2026-07-07 |

## Performance Metrics

**Velocity:**

- Total plans completed: 188 across 12 milestones (11 shipped + 1 abandoned) at v9.2 close
  - v9.2: 3 phases (90-92), 10 plans, shipped 2026-07-07; tests: 1174 passing at close
  - v9.1: 4 phases (86-89), 9 plans, shipped 2026-06-29; tests: 1131 passing at close
- v9.3: 4 phases planned (93-96); 5 plans complete (Phase 93: 3/3, Phase 94: 2/4)
  - Phase 94 Plan 01 (Wave-0 test scaffold): 4 min, 2 tasks, 1 file (`tests/test_webview_api.py`, +542 lines)
  - Phase 94 Plan 02 (tables.py router): 25 min, 2 tasks, 2 files (`webview/routers/tables.py` NEW, `webview/app.py` modified)

## Accumulated Context

### Roadmap Evolution

- v9.3 roadmap created (2026-07-07): phases 93-96. Derived from 8 requirements (LOG-01, TAB-01, TBL-01..03, SP1-01, SP2-01, SP-02) with authoritative override: spectra = **real Bruker traces + peak overlay** (not peak-only sticks). Research HIGH confidence across all phases; no research gate needed for any phase.

### Key Design Decisions for v9.3

- [v9.3-roadmap]: **Spectra source = real Bruker data** — BrukerReader/nmrglue renders the actual processed spectrum; picked peaks from `analysis/peaks/*.json` are overlaid on top. This is the QC value: user sees whether peaks were placed correctly relative to the real signals.
- [v9.3-roadmap]: **Bruker-path wiring via `.run_manifest.json`** — `case.md` writes `{"bruker_data_dir": "<abs>", "formula": "<formula>"}` into `analysis/.run_manifest.json` at run-start. The spectra router reads this file. If absent (manual `lucy webview serve`, pre-v9.3 run), spectra tab shows "unavailable" gracefully. No CLI signature change; no `.webview.json` model change.
- [v9.3-roadmap]: **matplotlib OO API only** — `Figure` + `FigureCanvasAgg`; never `matplotlib.pyplot` in any webview module. All matplotlib imports lazy inside `make_router()` per WV-08. `matplotlib>=3.7` added to `[webview]` extra.
- [v9.3-roadmap]: **Reversed ppm axes everywhere** — `ax.set_xlim(ppm_scale[0], ppm_scale[-1])` where `ppm_scale[0]` is the highest ppm (Bruker convention). Both F1 and F2 axes reversed on 2D plots. Shared `_apply_nmr_axes()` helper prevents omission.
- [v9.3-roadmap]: **2D performance** — decimate to ≤512×512 before contouring; threshold-based contour levels (MAD noise floor); mtime-keyed per-router PNG cache; sync `def` route handlers (FastAPI dispatches to thread-pool, never blocks event loop).
- [v9.3-roadmap]: **Markdown log = hand-rolled DOM renderer** — createElement + textContent throughout; never `innerHTML` of server content. Covers the exact CASE-PROGRESS.md subset (## headings, **bold**, `code`, pipe-tables, code fences, --- hr). No CDN, no bundled JS library.
- [v9.3-roadmap]: **SP-02 graceful degradation** — assigned to Phase 95 (first spectra phase, where the "unavailable" pattern for missing raw data is established); carried as a hard acceptance criterion to Phase 96 and recommended acceptance concern for Phase 94 tables.

### Decisions (inherited from v9.2)

Decisions are logged in PROJECT.md Key Decisions table.

- [v9.2-roadmap]: FastAPI + uvicorn shipped as `lucy-ng[webview]` optional extra; core `lucy` CLI stays dependency-free. Frontend is static HTML + vanilla JS — no build toolchain. Server is "dumb" (reads files only, no agent-team coupling).
- [Phase 91]: All fastapi/webview imports in test files are inside test function bodies (WV-08 collect-safety).
- [Phase 91]: Epoch values in timing.jsonl test fixtures are JSON strings matching case.md shell printf %s output.
- [Phase 94 Plan 01]: `tables_analysis_dir`/`tables_iterations_dir` fixtures in `tests/test_webview_api.py` are hand-authored to CONTEXT.md's LOCKED peaks-JSON schema — no on-disk `analysis/` run on this machine currently matches those exact field names (RESEARCH.md Assumptions A1-A5), so no existing file could be used as a template.
- [Phase 94 Plan 01]: TBL-01/02/03 remain Pending in REQUIREMENTS.md — Plan 01 only ships the Wave-0 RED-by-skip test scaffold (`TestTablesEndpoint`, 14 methods); requirements complete only once Plan 02's `tables.py` router makes all 14 pass.
- [Phase 94 Plan 02]: `tables.py` router ships all 5 GET routes (carbon/hsqc/hmbc/cosy/constraints), never-500, docked in `app.py`; `TestTablesEndpoint` (14/14) now GREEN — TBL-01/02/03 complete. Constraints route selects highest numeric `iteration_(\d+)` across family-suffixed dirs (mtime tiebreak, D-02); inventory parser reimplemented webview-local (never imports `cli/lsd.py`, whose validator raises SystemExit).

### Pending Todos

- **[2026-06-25] CASE4 azulene-regiochemistry-enumeration gap** — carried seed; not in v9.3 scope. See `.planning/todos/pending/2026-06-25-case4-azulene-regiochemistry-enumeration-gap.md`.

### Blockers/Concerns

None. Phase 93 may begin immediately (`/gsd-plan-phase 93`).

### Strategic Reference

See `background/sherlock-analysis.md` for full Sherlock vs lucy-ng comparison. v9.0 closed the end-to-end mechanism gap; v9.1 closed the three "clean-but-wrong" defect classes. v9.2 adds live observability. v9.3 deepens the inspector with spectra and data tables.

Key v9.0 constraint (still in force): SYME and DEFF NOT are lucy-ng abstractions. Native LSD-3.4.9 commands are: MULT, LIST, PROP, BOND, COSY, HMBC, ELIM, DEFF, FEXP, HSQC, ELEM.

## Session Continuity

Last session: 2026-07-10T12:40:09.515Z
Stopped at: Phase 96 context gathered
Resume with: `/gsd-execute-phase 94` (continue with Plan 94-03 — frontend Tables tab)

---
*Last updated: 2026-07-07 — v9.3 roadmap created (4 phases, 8 requirements mapped)*
