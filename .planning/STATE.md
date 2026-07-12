---
gsd_state_version: 1.0
milestone: v10.0
milestone_name: Automatic NUS 2D Reconstruction
status: executing
stopped_at: Phase 97 Plan 02 complete
last_updated: "2026-07-12T14:07:02.737Z"
last_activity: 2026-07-12
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 5
  completed_plans: 2
  percent: 0
---

# lucy-ng State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-12)

**Core value:** AI agent autonomously determines compound structures from NMR, with a multi-agent team that uses the intended solver pipeline — not a manual bypass
**Current focus:** Phase 97 — backend-integration-params-schedule

## Current Position

Phase: 97 (backend-integration-params-schedule) — EXECUTING
Plan: 3 of 5
Status: Plan 02 complete (nus/params.py, NUS-02); ready to execute Plan 03
Last activity: 2026-07-12 -- Plan 97-02 complete (read_nus_params, all 3 real fixtures verified)

Progress: [████░░░░░░] 40%

## Milestone v10.0 Phases

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 97. Backend Integration + Params/Schedule | `lucy nus check` backend detection (LSD precedent) + `nus/params.py`/`nus/schedule.py` Bruker parsing, fixture-tested against real C20H32O2 data | NUS-01..05 | — |
| 98. Reconstruction + Processing | Real NMRPipe+SMILE subprocess chain (bruk2pipe → nusExpand.tcl → SMILE → FT/phase/baseline), FnMODE-aware, fail-loud wrapper | RECON-01..05 | 97 |
| 99. Peak-Pick Bridge + QC Gate + CLI | `nus/bridge.py` → existing `PeakPicker2D`; mandatory automated QC gate (PASS/PARTIAL/FAIL) blocking CASE handoff on FAIL; full `lucy nus` CLI group | PICK-01..03, QC-01..03 | 98 |
| 100. Cross-Platform Hardening + End-to-End Validation | Portability matrix (macOS/Linux native, Windows WSL2 gap documented); C20H32O2 exp2/3/4 reconstruction passing §8 gate; `/lucy-ng:case C20H32O2` convergence | PORT-01..02, VAL-01..02 | 99 |

**Sequencing:** Phase 97 (backend detection + pure-Python params/schedule parsing) ships first — zero external-binary dependency, fixture-testable from day one, and front-loads the FnMODE/nuslist bookkeeping correctness (a single hard-coded divisor would silently corrupt one of the three real C20H32O2 experiments). Phase 98 (reconstruction + processing) is the highest-uncertainty phase — needs the real NMRPipe+SMILE binary and answers the milestone's open empirical question (does SMILE clear the quality bar at 25-33% sampling). Phase 99 (peak-pick bridge + QC gate + CLI) is where the crux risk (fabricated cross-peaks becoming hard LSD constraints) gets its mandatory automated defense — the QC gate is its own deliverable, not folded into peak-picking. Phase 100 (cross-platform hardening + validation) is milestone-closing: portability documentation and the actual success criterion (`/lucy-ng:case C20H32O2` convergence) both depend on everything upstream being stable.

## Deferred Items

Items acknowledged and deferred at **v9.3 CASE Web-View Stage 2 milestone close on 2026-07-12**:

| Category | Item | Status | Note |
|----------|------|--------|------|
| todo | 2026-06-25-case4-azulene-regiochemistry-enumeration-gap | deferred (re-confirmed) | CASE-solver backlog; unrelated to the v9.3 webview scope. Still open. |
| todo | 2026-06-30-ranking-tests-hardfail-without-hosegen | deferred (re-confirmed) | v9.1 test-infra backlog; unrelated to the v9.3 webview scope. |

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
| v9.3 CASE Web-View Stage 2 | 93-96 | 2026-07-12 |

## Performance Metrics

**Velocity:**

- Total plans completed: 192 across 12 milestones (11 shipped + 1 abandoned) at v9.2 close
  - v9.2: 3 phases (90-92), 10 plans, shipped 2026-07-07; tests: 1174 passing at close
  - v9.1: 4 phases (86-89), 9 plans, shipped 2026-06-29; tests: 1131 passing at close
- v9.3: 4 phases (93-96), 16 plans, shipped 2026-07-12 (~107 commits, +16,988/-287 lines)
- v10.0: 4 phases planned (97-100); 2 plans complete — Phase 97 Plan 01 (fixtures + NUS models), 4 min, 2 tasks, 18 files, tests 1219 passing at close; Phase 97 Plan 02 (nus/params.py, NUS-02), 14 min, 1 task, 2 files, tests 1243 passing at close

## Accumulated Context

### Roadmap Evolution

- v9.3 roadmap created (2026-07-07): phases 93-96. Derived from 8 requirements (LOG-01, TAB-01, TBL-01..03, SP1-01, SP2-01, SP-02) with authoritative override: spectra = **real Bruker traces + peak overlay** (not peak-only sticks). Research HIGH confidence across all phases; no research gate needed for any phase.
- v10.0 roadmap created (2026-07-12): phases 97-100, continuing numbering from the last shipped phase (96). Derived from 20 requirements (NUS-01..05, RECON-01..05, QC-01..03, PICK-01..03, PORT-01..02, VAL-01..02), following the research-converged build order (SUMMARY.md § Implications for Roadmap): backend+params/schedule → reconstruction+processing (highest-uncertainty) → peak-pick bridge+QC gate+CLI (crux-risk mitigation as its own deliverable) → cross-platform hardening+end-to-end validation. 20/20 requirements mapped, no orphans.

### Key Design Decisions for v10.0

- [v10.0-roadmap]: **Backend = NMRPipe+SMILE, runtime-detected external binary** — never a core `pyproject.toml` dependency, mirrors the `LSDRunner`/`lucy lsd check` precedent exactly. Windows is an accepted, documented WSL2/VM gap (Phase 100), not a blocker.
- [v10.0-roadmap]: **New `nus/` package, sibling of `lsd/`/`webview/`** — pre-CASE "dumb tool"; zero changes to `case.md` or the 5-agent team; the diff to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` must stay empty (enforceable-by-inspection constraint carried into Phase 97's success criteria).
- [v10.0-roadmap]: **QC gate is its own phase deliverable (Phase 99), not folded into peak-picking** — it is the mandatory automated defense against fabricated cross-peaks silently becoming hard LSD constraints (the milestone's crux risk per research).
- [Phase 97 Plan 01]: `NusAcquisitionParams.fnmode_f1` validator shares the `REAL_FNMODES`/`COMPLEX_FNMODES`/`VALID_FNMODES` module constants with `nus/schedule.py` (plan 03) so the two never maintain divergent FnMODE allowlists.
- [Phase 97 Plan 01]: Fixture set expanded beyond D-03's original acqus/acqu2s/nuslist trio to also copy `pdata/1/procs`+`pdata/1/proc2s` per RESEARCH.md's SF/OFFSET-live-in-procs correction — otherwise SF/OFFSET fields would have zero fixture coverage.
- [Phase 97 Plan 02]: `read_nus_params` uses nmrglue's low-level `read_acqus_file()`/`read_procs_file()` instead of the monolithic `ng.bruker.read()` — the latter unconditionally requires a `fid`/`ser` binary to determine data shape, which the D-03 test fixtures deliberately omit (metadata-only). The low-level readers parse the identical `acqus`/`acqu2s`/`procs`/`proc2s` files with zero binary dependency, correct for both the fixtures and real not-yet-reconstructed NUS directories.

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

- **[2026-06-25] CASE4 azulene-regiochemistry-enumeration gap** — carried seed; not in v10.0 scope. See `.planning/todos/pending/2026-06-25-case4-azulene-regiochemistry-enumeration-gap.md`.

### Blockers/Concerns

None. Phase 97 may begin planning immediately (`/gsd-plan-phase 97`).

### Strategic Reference

See `background/sherlock-analysis.md` for full Sherlock vs lucy-ng comparison. v9.0 closed the end-to-end mechanism gap; v9.1 closed the three "clean-but-wrong" defect classes. v9.2 adds live observability; v9.3 deepens the inspector with spectra and data tables. v10.0 closes the NUS 2D reconstruction gap that timed out the first C20H32O2 CASE run.

Key v9.0 constraint (still in force): SYME and DEFF NOT are lucy-ng abstractions. Native LSD-3.4.9 commands are: MULT, LIST, PROP, BOND, COSY, HMBC, ELIM, DEFF, FEXP, HSQC, ELEM.

## Session Continuity

Last session: 2026-07-12T14:07:02.737Z
Stopped at: Phase 97 Plan 02 complete
Resume with: `/gsd-execute-phase 97` (continues with Plan 03 — nus/schedule.py, NUS-03)

---
*Last updated: 2026-07-12 — Phase 97 Plan 02 complete (read_nus_params, NUS-02)*

## Operator Next Steps

- Continue Phase 97 with Plan 03 (`nus/schedule.py`) via `/gsd-execute-phase 97`
