# Phase 94: Data Tables - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Populate the **Tables** tab of the v9.2/9.3 webview dashboard — the empty
placeholder docked in during Phase 93 — with five formatted, read-only tables:

1. **¹³C signal table** — from `analysis/peaks/carbon_signals.json` (TBL-01)
2. **HSQC** correlations — from `analysis/peaks/hsqc.json` (TBL-02)
3. **HMBC** correlations — from `analysis/peaks/hmbc.json` (TBL-02)
4. **COSY** correlations — from `analysis/peaks/cosy.json` (TBL-02)
5. **LSD constraint inventory** — from the JSON block in the header of the
   latest `iteration_NN/compound.lsd` (TBL-03)

Backend follows the established "dumb server" pattern: a new `tables.py` router
that only reads files, one endpoint per data source, degrading to a
"waiting for data" payload (HTTP 200, never 500) when a file is absent or
partially written during a live run (SC4). Frontend renders into the Tables
tab using the existing DOM/table primitives — no new design system, no backend
markdown rendering, no build toolchain.

**Not in scope:** real spectra traces (Phase 95/96), any peak *editing*, any
change to the CASE agent team or the JSON producers, live SSE push.

</domain>

<decisions>
## Implementation Decisions

### TBL-03 — LSD constraint inventory
- **D-01 (Layout — structured view with reasoning):** Render TBL-03 as a
  **structured multi-section view**, NOT a single flat table:
  - An **"Applied constraints"** table with columns `type | atom-indices | note`
    for the constraints that carry per-atom indices in the JSON: `BOND`
    (`bond_constraints`, e.g. `"1 14"`), `HMBC` (per-batch `correlations`, e.g.
    `"1 9"`), and `COSY-equiv` (`cosy_equiv_pairs`). The `note` column draws from
    `applied_from_detection` narrative where a constraint maps to one.
  - **Count/summary rows** for constraints the JSON only exposes as totals:
    `MULT` (`mult_count`), `HSQC` (`hsqc_count`), `hmbc_total`, `elim_budget`,
    `ring_exclusion_enabled`, `deff_fexp.status`.
  - A secondary **"Deferred / pending"** section rendered from
    `pending_from_detection` (and optionally `detection_results`), presented as
    the reasoning narrative — this QC "why was X deferred" context is a primary
    reason the inspector exists.
  - The JSON lives inside `; `-prefixed comment lines between
    `; === CONSTRAINT INVENTORY v2 ===` and `; === END CONSTRAINT INVENTORY ===`.
    The router must strip the leading `; ` from each line, join, and `json.loads`.
    Parse must be defensive: malformed / missing block → "waiting for data",
    never a 500.

- **D-02 (Which compound.lsd — highest numeric `iteration_NN`):** Iteration
  directories carry family suffixes (`iteration_06_ethyl33_anchor`,
  `iteration_07_anchor_recovery`) and multiple families may run in parallel.
  Select the file by the **highest numeric prefix** extracted via
  `iteration_(\d+)`, across all families, with **mtime as tiebreak** when two
  dirs share the same number. Deterministic and matches the ROADMAP wording
  "latest `iteration_NN`". Showing all families side-by-side is deferred (see
  Deferred Ideas).

### TBL-02 — correlation tables
- **D-03 (HMBC flags — show all, colour-coded):** Show **all kept rows**;
  colour each row by its `flag` value (`ok` / `potential_4J` / `1J_artifact`).
  Suggested treatment: `ok` = normal/green accent, `potential_4J` = amber,
  `1J_artifact` = dimmed/grey (exact palette = Claude's discretion, respect the
  existing v9.2/9.3 visual language). Do NOT hide artefact rows — seeing what
  the detection layer flagged as artefact is the QC value. Colouring is applied
  per-row via CSS classes on DOM `<tr>` elements (no `innerHTML` of server
  content — preserve the D-02/v9.2 XSS discipline).

### Columns & metadata (all tables)
- **D-04 (Columns — QC-relevant extras):** Surface the fields a chemist judges
  peak quality on, beyond the ROADMAP minimum:
  - ¹³C: `ppm | mult | nC | assignment` **+ `confidence`**.
  - HSQC: carbon/proton shifts, `matched_real_carbon`, `one_bond` marker,
    `intensity`.
  - HMBC: `carbon_ppm` / `carbon_ppm_observed`, `proton_ppm`, `flag`,
    `intensity`.
  - COSY: `proton_a_ppm`, `proton_b_ppm`, `intensity`.
  - **Intensity is formatted compactly** (e.g. `5.6M`, `1.5M`) rather than raw
    (`5559614`) — raw values are unreadable in a table cell.
- **D-05 (Caption per table — show note + counts):** Render each source JSON's
  top-level `note` plus the salient counts (e.g. HMBC "29 kept of 913",
  `experiment`, `formula`/`dbe`/`solvent` for ¹³C) as a small **caption above
  each table**. This curation narrative (why peaks were removed, solvent
  exclusions, overcount alarms) is high-value QC context.

### Claude's Discretion
- Exact endpoint shape (`/api/tables` combined vs one route per source) — but
  SC4 requires **per-table** waiting granularity, so each table panel must be
  able to independently show "waiting for data".
- CSS palette for HMBC flag colours, caption styling, table density — respect
  the existing v9.2/9.3 visual language; introduce no new design system.
- Whether the frontend reuses the existing `buildTable(headerCells, rows)`
  helper directly or a thin wrapper that adds per-row flag classes and the
  compact-intensity formatter.
- Internal parsing helpers, function names, module organisation within
  `tables.py` and the frontend table code.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing webview implementation (the base to extend — do NOT redesign)
- `src/lucy_ng/webview/app.py` — `create_app()`; dock the new router via
  `app.include_router(_tables.make_router(analysis_dir))` next to log/status/structures
- `src/lucy_ng/webview/routers/log.py` — canonical router pattern to mirror:
  `make_router(analysis_dir)` + `APIRouter(prefix='/api')` + `{"state":"ok"|"waiting", ...}`
  graceful-degradation payload, never raises 500 (SC4 model)
- `src/lucy_ng/webview/routers/status.py`, `.../structures.py` — additional router examples
- `src/lucy_ng/webview/static/webview.js` — existing frontend; `buildTable(headerCells, rows)`
  DOM table builder (~line 270) is reusable; `fetch → render` polling pattern (~3 s)
- `src/lucy_ng/webview/static/index.html` — Tables tab placeholder to populate
- `tests/test_webview_api.py` — WV-08 import-safety pattern (fastapi imports inside
  test bodies; skip when fastapi absent)

### Data shapes (the files the tables read)
- `analysis/peaks/carbon_signals.json` — top-level `formula`/`dbe`/`solvent`/`note`
  + `signals[]` (`atom`, `ppm`, `mult`, `nC`, `assignment`, `confidence`)
- `analysis/peaks/hsqc.json` — `experiment`/`count`/`note` + `peaks[]`
  (`carbon_ppm`, `proton_ppm`, `intensity`, `matched_real_carbon`, `one_bond`)
- `analysis/peaks/hmbc.json` — `experiment`/`raw_count`/`kept_count`/`flag_rules`/`note`
  + `peaks[]` (`carbon_ppm`, `carbon_ppm_observed`, `proton_ppm`, `intensity`, `flag`)
- `analysis/peaks/cosy.json` — `experiment`/`count`/`note` + `peaks[]`
  (`proton_a_ppm`, `proton_b_ppm`, `intensity`)
- `analysis/iteration_NN[/_family]/compound.lsd` — `; `-commented JSON block between
  `; === CONSTRAINT INVENTORY v2 ===` and `; === END CONSTRAINT INVENTORY ===`
  (`mult_count`, `hsqc_count`, `hmbc_batches[].correlations`, `hmbc_total`,
  `bond_constraints`, `cosy_equiv_pairs`, `applied_from_detection`,
  `pending_from_detection`, `detection_results`, `deff_fexp`, `elim_budget`,
  `ring_exclusion_enabled`)

### Prior-phase decisions carried forward
- `.planning/phases/93-formatted-log-tab-framework/93-CONTEXT.md` — D-01 (tab layout:
  Tables is the 4th tab of the right panel; Overview/Structures are the persistent left
  column), D-02 (XSS discipline: createElement + textContent, never innerHTML of server
  content), D-04 (two-layer test: pytest static-scan + optional manual browser checkpoint)
- `.planning/ROADMAP.md` §"Phase 94: Data Tables" — goal, 4 success criteria, requirements
- `.planning/REQUIREMENTS.md` — TBL-01, TBL-02, TBL-03

### Specs / conventions
- `CLAUDE.md` (repo) — dev commands (pytest, mypy strict, ruff), package structure
- WV-08 convention (from Phase 91, see STATE.md) — fastapi/webview imports inside
  function/test bodies only; router modules never imported from
  `webview/__init__.py` / `server.py` / `state.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `buildTable(headerCells, rows)` in `webview.js` — DOM `<table>` builder using
  `createElement`/`textContent`; reuse directly, or wrap to add per-row flag
  CSS classes (HMBC) and the compact-intensity formatter.
- `routers/log.py` `_read_log()` — the exact "read file → ok/waiting, never 500"
  shape TBL-01…03 endpoints should copy.
- `create_app()` lazy-import + `include_router` docking pattern.

### Established Patterns
- One router module per data area, `make_router(analysis_dir)` returning an
  `APIRouter(prefix='/api')`.
- Frontend `fetch(URL).then(json).then(render).catch(warn)` on the shared ~3 s
  poll; each panel renders independently.
- XSS discipline is satisfied by construction (no `innerHTML` of server content).

### Integration Points
- New `src/lucy_ng/webview/routers/tables.py`; one `include_router` line in `app.py`.
- New frontend render functions + URLs in `webview.js`, targeting the Tables tab
  container in `index.html`.
- New `tests/` coverage following `tests/test_webview_api.py` import-safety pattern.

</code_context>

<specifics>
## Specific Ideas

- Compact intensity formatting is a hard requirement (raw `5559614` → `5.6M`).
- LSD JSON parse strips the `; ` comment prefix before `json.loads`; malformed
  block degrades to "waiting", never 500.
- "Latest" file = max `iteration_(\d+)` across families, mtime tiebreak.
- HMBC artefact rows stay visible, colour-coded — never filtered out.
- Per-table caption carries the curation `note` + counts.

</specifics>

<deferred>
## Deferred Ideas

- **Family selector / multiple LSD inventories side-by-side** — showing all
  parallel families (not just the highest `iteration_NN`) — deferred; likely v9.4.
- **HMBC "only ok" filter toggle** — interactive client-side filtering of
  flagged rows — deferred; out of scope for this read-only phase.
- Real spectra traces + peak overlay (1D/2D) → Phases 95/96 (already scoped).
- Interactive zoom/pan, DEPT sub-tab, SSE live push → v9.4 per STATE.md.

None of the above expand Phase 94 scope — captured so they are not lost.

</deferred>

---

*Phase: 94-data-tables*
*Context gathered: 2026-07-09*
