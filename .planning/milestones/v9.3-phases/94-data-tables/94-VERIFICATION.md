---
phase: 94-data-tables
verified: 2026-07-09T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 94: Data Tables Verification Report

**Phase Goal:** Users can inspect raw peak data (¹³C signals, HSQC/HMBC/COSY correlations) and the LSD constraint inventory as formatted tables in the Tables tab.
**Verified:** 2026-07-09
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 (SC1) | User sees ¹³C signal table (ppm, mult, nC, assignment) from `analysis/peaks/carbon_signals.json` | VERIFIED | `tables.py::_read_carbon` reads the file, returns `rows`/`counts`/`note`; `webview.js::renderCarbon` builds a `['δC (ppm)','Mult','nC','Assignment','Confidence']` table via `buildTable`. `test_carbon_returns_rows` asserts `ppm/mult/nC/assignment/confidence` present in the row. |
| 2 (SC2) | User sees HSQC/HMBC/COSY correlation tables with shift columns and HMBC flag colouring | VERIFIED | `_read_hsqc`/`_read_hmbc`/`_read_cosy` in `tables.py`; `renderHsqc`/`renderHmbc`/`renderCosy` in `webview.js` render shift + intensity columns. HMBC: `HMBC_FLAG_CLASS` maps `ok`/`potential_4J`/`1J_artifact` → `row-ok`/`row-potential-4j`/`row-1j-artifact`, applied via post-process `querySelectorAll('tbody tr')` (no row hidden). `test_hsqc_cosy_return_ok` and `test_hmbc_preserves_flag_verbatim` (asserts all 3 flag values present, unmodified) both pass. CSS classes `.row-ok/.row-potential-4j/.row-1j-artifact` exist in `index.html`. |
| 3 (SC3) | User sees LSD constraint inventory table (type, atom indices, note) parsed from the latest `iteration_NN/compound.lsd` header JSON | VERIFIED | `_newest_compound_lsd` selects by `re.match(r"iteration_(\d+)", name)` (no `$` anchor — matches family-suffixed dirs) with mtime tiebreak; `_extract_inventory_block` strips `; ` prefix between the v2 delimiters and `json.loads`. `webview.js::renderConstraints` builds 3 subsections (Applied Constraints / Constraint Summary / Deferred-Pending) per D-01. `test_constraints_selects_highest_iteration` confirms `iteration_02_anchor_recovery` (numeric 2) wins over bare `iteration_01`. |
| 4 (SC4) | Absent/partial peak JSON or `compound.lsd` → "waiting for data" state, HTTP 200, never 500 | VERIFIED | All 5 `_read_*` functions in `tables.py` wrap file/JSON access in broad `except _JSON_READ_ERRORS` / explicit malformed-block checks, returning `state="waiting"` — no `raise`/`HTTPException` anywhere in the module. 10 dedicated tests cover absent+malformed for all 5 panels (`test_carbon_waiting_when_absent`, `test_malformed_json_returns_waiting` [carbon], `test_hsqc_waiting_when_absent/_malformed`, `test_hmbc_waiting_when_absent/_malformed`, `test_cosy_waiting_when_absent/_malformed`, `test_constraints_waiting_when_absent/_malformed`), all asserting `status_code == 200` and `state == "waiting"`. Frontend: every `render*` function checks `data.state !== 'ok'` and calls `showTableWaiting(...)` per-panel, independent of the other 4. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lucy_ng/webview/routers/tables.py` | 5 GET routes, never-500 reader helpers | VERIFIED | 262 lines; `make_router()` registers `/api/tables/{carbon,hsqc,hmbc,cosy,constraints}`; all 5 `_read_*` functions catch a broad error tuple and degrade to `waiting`; no `raise`/`HTTPException` present. |
| `src/lucy_ng/webview/app.py` | Router docked via lazy import + `include_router` | VERIFIED | `from lucy_ng.webview.routers import tables as _tables` + `app.include_router(_tables.make_router(analysis_dir))`, unconditional, alongside the existing 3 routers. |
| `src/lucy_ng/webview/static/webview.js` | 5 fetch/render pairs, HMBC colouring, TBL-03 structured view, no innerHTML | VERIFIED | `refreshCarbon/Hsqc/Hmbc/Cosy/Constraints` all present and registered in `tick()` (lines 756-760); `formatIntensity`/`formatBool`/`cellText`/`setCaption`/`showTableWaiting` shared helpers present and match claimed behaviour (verified `formatIntensity(5559614)` logic → `5.6M`). `grep innerHTML` on the file returns zero matches. |
| `src/lucy_ng/webview/static/index.html` | 5 Tables-tab sections + CSS tokens | VERIFIED | `#table-carbon/-hsqc/-hmbc/-cosy/-constraints` sections present with caption/body containers; `.row-ok/.row-potential-4j/.row-1j-artifact/.table-waiting/.data-table` CSS classes present. |
| `tests/test_webview_api.py::TestTablesEndpoint` | 14 test methods, RED-by-skip → GREEN | VERIFIED | 14 methods confirmed by name (carbon/hsqc/cosy/hmbc/constraints × ok+absent+malformed permutations); all pass in the full run. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `webview.js` fetch calls | `/api/tables/*` routes | `fetch(URL).then(json).then(render).catch(warn)` | WIRED | 5 URL consts (`CARBON_URL`...`CONSTRAINTS_URL`) match the 5 router paths exactly; `.catch` present on every fetch chain. |
| `tables.py` routes | `analysis_dir` peaks JSON files | direct file read, no CLI coupling | WIRED | `_extract_inventory_block` is a local reimplementation, not an import of `cli.lsd` (confirmed via `grep "^import\|^from"` — no `cli.lsd`/`cli import lsd` present; only literal string in a docstring). |
| `app.py::create_app()` | `tables.make_router()` | `include_router` | WIRED | Confirmed unconditional registration, line 62. |
| `webview.js::renderHmbc` | HMBC row DOM | `table.querySelectorAll('tbody tr')[i].className = HMBC_FLAG_CLASS[flag]` | WIRED | Iterates in fetch-row order (`rows[i].flag`), matches `trs[i]` 1:1; no row filtered/hidden. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `renderCarbon`/`Hsqc`/`Hmbc`/`Cosy`/`Constraints` | `data.rows` / `data.inventory` | `tables.py` reads real files under `analysis_dir/peaks/*.json` and `analysis_dir/iteration_*/compound.lsd` via `json.loads(p.read_text(...))` — no static/hardcoded return values in any success path | Yes | FLOWING |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| TBL-01 | 94-01/02/03 | ¹³C signal table from carbon_signals.json | SATISFIED | `_read_carbon` + `renderCarbon` + `test_carbon_returns_rows` |
| TBL-02 | 94-01/02/03 | HSQC/HMBC/COSY correlation tables with shifts/flags | SATISFIED | `_read_hsqc/_read_hmbc/_read_cosy` + `renderHsqc/Hmbc/Cosy` + flag-colour tests |
| TBL-03 | 94-01/02/03 | LSD constraint inventory parsed from latest iteration | SATISFIED | `_newest_compound_lsd` + `_extract_inventory_block` + `renderConstraints` (3-subsection) + `test_constraints_selects_highest_iteration` |

No orphaned requirements found for Phase 94 in REQUIREMENTS.md (all three map to plans that claim them).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_webview_api.py:293` | pre-existing E501 (line too long) | Info | Introduced in Phase 93 (`0c1a8b8`), unrelated to Phase 94's changes; logged in `deferred-items.md`. Not a Phase 94 debt marker (no TBD/FIXME/XXX found in any Phase 94-touched file). |

No TBD/FIXME/XXX/HACK/PLACEHOLDER markers found in `tables.py`, `app.py`, `webview.js`, or `index.html`. The two `placeholder`-class references in `index.html` (lines 411-412) are the intentional Phase 95/96 stubs for 1D/2D Spectra tabs — explicitly out of scope for Phase 94 (confirmed against ROADMAP.md phase boundaries).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full webview test suite green | `pytest tests/test_webview_api.py -q` | `35 passed` | PASS |
| `TestTablesEndpoint` (14 methods) green | `pytest tests/test_webview_api.py::TestTablesEndpoint -q` | `14 passed` (part of the 35) | PASS |
| No `innerHTML` in `webview.js` | `grep -n innerHTML webview.js` | 0 matches | PASS |
| No `cli.lsd` import coupling | `grep "^import\|^from" tables.py` | only `json`, `re`, `pathlib`, `typing`, `fastapi` | PASS |
| No `raise`/`HTTPException` in `tables.py` | `grep raise\|HTTPException tables.py` | 0 matches (only docstring mentions of "never raises") | PASS |
| ruff clean on touched webview files | `ruff check src/lucy_ng/webview` | `All checks passed!` | PASS |
| mypy clean on `tables.py`/`app.py` | `mypy src/lucy_ng/webview 2>&1` (66 errors, all in unrelated pre-existing files: stats_generator.py, generator.py, predictor.py, runner.py, orchestrator.py, ranker.py) | 0 errors attributable to `webview/routers/tables.py` or `webview/app.py` | PASS |
| JS syntax valid | `node --check webview.js` | no output (valid) | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` found in the repository and Phase 94 is not a migration/CLI-tooling phase; PLAN/SUMMARY files make no probe references.

### Human Verification Required

None outstanding. The visual-only success criteria (HMBC row colour rendering, per-table captions, compact-intensity display, TBL-03 3-subsection layout) were verified via a blocking `checkpoint:human-verify` manual browser check in Plan 94-04, executed against a schema-conformant fixture `analysis_dir` served via `lucy webview serve`, and explicitly **APPROVED by the user** on 2026-07-09 (`.planning/phases/94-data-tables/94-04-SUMMARY.md`). Per the verification method's explicit instruction, this documented human approval is treated as satisfying evidence for the visual/pixel-level criteria — no new human verification item is raised.

### Gaps Summary

None. All 4 ROADMAP success criteria (SC1-SC4) are backed by both static code evidence (real file reads, never-500 error handling, correct regex/parsing logic, no innerHTML) and passing automated tests (35/35, including the phase-specific 14-method `TestTablesEndpoint`), plus an already-completed and approved manual browser checkpoint for the visual-only aspects. No stubs, no orphaned wiring, no debt markers introduced by this phase.

---

_Verified: 2026-07-09_
_Verifier: Claude (gsd-verifier)_
