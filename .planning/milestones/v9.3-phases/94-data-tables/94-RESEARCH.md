# Phase 94: Data Tables - Research

**Researched:** 2026-07-09
**Domain:** FastAPI router extension + vanilla-JS table rendering for an existing read-only CASE webview dashboard (internal codebase extension, not a new library integration)
**Confidence:** HIGH for router/frontend patterns and LSD constraint-inventory format (all directly quoted from real source and real production `analysis/` artefacts); MEDIUM for the exact `analysis/peaks/{carbon_signals,hsqc,hmbc,cosy}.json` field names (no file with those exact names exists on this machine today — see Open Questions).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### TBL-03 — LSD constraint inventory
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

#### TBL-02 — correlation tables
- **D-03 (HMBC flags — show all, colour-coded):** Show **all kept rows**;
  colour each row by its `flag` value (`ok` / `potential_4J` / `1J_artifact`).
  Suggested treatment: `ok` = normal/green accent, `potential_4J` = amber,
  `1J_artifact` = dimmed/grey (exact palette = Claude's discretion, respect the
  existing v9.2/9.3 visual language). Do NOT hide artefact rows — seeing what
  the detection layer flagged as artefact is the QC value. Colouring is applied
  per-row via CSS classes on DOM `<tr>` elements (no `innerHTML` of server
  content — preserve the D-02/v9.2 XSS discipline).

#### Columns & metadata (all tables)
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

### Deferred Ideas (OUT OF SCOPE)
- **Family selector / multiple LSD inventories side-by-side** — showing all
  parallel families (not just the highest `iteration_NN`) — deferred; likely v9.4.
- **HMBC "only ok" filter toggle** — interactive client-side filtering of
  flagged rows — deferred; out of scope for this read-only phase.
- Real spectra traces + peak overlay (1D/2D) → Phases 95/96 (already scoped).
- Interactive zoom/pan, DEPT sub-tab, SSE live push → v9.4 per STATE.md.

None of the above expand Phase 94 scope — captured so they are not lost.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TBL-01 | User sees the ¹³C signal table (ppm, multiplicity, nC, assignment) from the curated `analysis/peaks/carbon_signals.json`. | Router pattern to mirror (`log.py`/`structures.py` ok/waiting shape), `buildTable` frontend reuse, and the exact peaks-JSON field-name caveat are documented in Standard Stack / Architecture Patterns / Common Pitfalls #4 / Assumptions Log A1. |
| TBL-02 | User sees the correlation tables — HSQC (one-bond), HMBC (long-range), COSY — from `analysis/peaks/{hsqc,hmbc,cosy}.json`, with shifts and flags. | Same router pattern (one route per source, per SC4); D-03 HMBC flag-colouring approach documented in Architecture Patterns Pattern 4 and Anti-Patterns; field-name caveats in Assumptions Log A2-A4. |
| TBL-03 | User sees the LSD constraint inventory (MULT/HSQC/HMBC/BOND/etc.) parsed from the latest `iteration_NN/compound.lsd`. | Fully verified against real, current, on-disk data (CASE4 `iteration_07_anchor_recovery`); parsing precedent (`_extract_inventory_block` in `cli/lsd.py`), JSON Schema (`schemas/constraint_inventory_v2.json`), and the D-02 "latest iteration" selection logic (with family-suffix + mtime tiebreak fix) are documented in Architecture Patterns Pattern 2 and Code Examples. |
</phase_requirements>

## Summary

Phase 94 is a pure "read one more file, render one more panel" extension of a pattern that already exists three times in this codebase (`routers/log.py`, `routers/status.py`, `routers/structures.py`). There is nothing to discover about FastAPI or vanilla-JS DOM rendering here — the correct approach is to copy the existing `make_router(analysis_dir) -> APIRouter(prefix="/api")` shape verbatim, add one `include_router` line to `create_app()`, and add rendering functions to `webview.js` that reuse the existing `buildTable(headerCells, rows)` helper and the `fetch → render` ~3s poll loop.

The one genuinely research-worthy finding is that **no file on this machine matches the exact canonical filenames `analysis/peaks/carbon_signals.json`, `analysis/peaks/hsqc.json`, `analysis/peaks/hmbc.json`, `analysis/peaks/cosy.json`** that CONTEXT.md, REQUIREMENTS.md, ROADMAP.md and the prior v9.3 research (SUMMARY.md/FEATURES.md) all cite as "confirmed from a real CASE1 run." All ten local `active-lucy-ng-testprojects/CASE*` directories and the `case-benchmark/results/CASE1/run-01` directory were inspected directly; none currently contains a `peaks/` subdirectory with those four filenames. Older runs use ad hoc, inconsistent naming (`peaks.json`, `13c_peaks.json`, `hmbc_curated.json`, `cosy_raw.json`, etc.) with **different field names** than the CONTEXT.md schema. The LSD constraint-inventory side of this phase (TBL-03), by contrast, is fully verified: `src/lucy_ng/cli/lsd.py` already contains a working `_extract_inventory_block()` parser for this exact format, the JSON Schema lives at `schemas/constraint_inventory_v2.json`, and a real, currently-on-disk `compound.lsd` file (CASE4, `iteration_07_anchor_recovery`) was read and quoted in full below.

**Primary recommendation:** Build `tables.py` by copying `routers/log.py`'s ok/waiting shape exactly (one function per source, each independently degradable per SC4), reuse `_extract_inventory_block`-style parsing logic for TBL-03 (do not re-derive it — `src/lucy_ng/cli/lsd.py` already solved the "; -strip → json.loads, tolerate missing END" problem), and treat the CONTEXT.md peaks-JSON field names as the authoritative target schema (locked decision) while building Wave-0 test fixtures by hand rather than copying any file found on disk today, because no on-disk file matches that schema exactly.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Read `analysis/peaks/*.json` + `compound.lsd` from disk | API/Backend (FastAPI router, `tables.py`) | — | Same tier as the three existing routers; the "dumb server" reads `analysis_dir` only, no agent/business logic |
| Parse `; `-commented CONSTRAINT INVENTORY JSON block | API/Backend | — | Pure string/JSON parsing, no I/O beyond the one file; belongs next to `_extract_inventory_block` precedent in `cli/lsd.py`, reimplemented (not imported — see Don't Hand-Roll) inside `tables.py` to keep the CLI and webview independently deployable |
| Select "latest" `iteration_NN[_family]` directory | API/Backend | — | Same responsibility already implemented for structures (`structures.py::_newest_solutions_smi`) — mirror the pattern, don't invent a new one |
| Compact intensity formatting (`5559614` → `5.6M`) | Browser/Client | — | Pure display formatting of already-fetched JSON; no reason to push this into the backend response, keeps `tables.py` a thin file-reader |
| HMBC flag → CSS class colouring | Browser/Client | — | DOM-side per-`<tr>` class assignment (D-03); the backend returns the raw `flag` string unchanged |
| Table DOM construction | Browser/Client | — | Reuses existing `buildTable(headerCells, rows)` in `webview.js`; no new rendering tier needed |
| Tab panel wiring / independent "waiting" state per table | Browser/Client + API/Backend | — | Each of the 5 tables issues its own `fetch()` and renders independently (SC4 requires per-table granularity, not one combined endpoint) |

## Standard Stack

This phase adds **zero new dependencies**. It reuses the already-declared `[webview]` extra (`fastapi>=0.100`, `uvicorn>=0.20`) and the already-installed `fastapi==0.128.2` `[VERIFIED: pip show fastapi, this environment]`. No `matplotlib`, no charting library, no template engine, no markdown library — the entire phase is `json.loads` + DOM table construction.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | ≥0.100 (0.128.2 installed) `[VERIFIED: pip show fastapi]` | `APIRouter` factory for the new `/api/tables/*` (or per-source) routes | Already the sole web framework in this codebase; adding a fifth router is zero-cost |
| stdlib `json`, `re`, `pathlib` | builtin | Parse peaks JSON + strip/parse the `; `-commented LSD inventory block | No parsing library is warranted for this format — see Don't Hand-Roll |

### Supporting
None. This phase does not need `pydantic` response models beyond what FastAPI's plain-`dict[str, Any]` returns already used by `log.py`/`status.py` provide — mirror those, don't add typed response models unless the planner independently decides the extra rigor is worth the churn.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled `; `-strip + `json.loads` parser (mirrors `cli/lsd.py`) | Import `_extract_inventory_block` directly from `lucy_ng.cli.lsd` | Tempting for DRY, but `cli/lsd.py` is part of the dependency-free core CLI; importing it from `webview/routers/tables.py` is fine (no fastapi/RDKit leakage risk — `cli/lsd.py` has no heavy deps) but couples the webview's read-only display logic to the CLI's exit-code-raising validator (`_validate_and_parse_inventory` calls `raise SystemExit(1)` and `click.echo(err=True)` on malformed input — exactly the opposite of the "never 500, always degrade to waiting" contract this phase requires). **Recommendation: re-implement a small, purely-returns-`None`-on-failure variant inside `tables.py`, structurally similar to `_extract_inventory_block` but without any `SystemExit`/`click` dependency.** Do not import the CLI's SystemExit-raising validator into the router.
| Per-table individual routes (`GET /api/tables/carbon`, `/hsqc`, `/hmbc`, `/cosy`, `/constraints`) | One combined `GET /api/tables` endpoint returning all 5 in one payload | CONTEXT.md D-05/Claude's Discretion explicitly leaves this open, but SC4 ("the corresponding table panel shows a waiting state") requires **per-table** independence — a combined endpoint where one file is malformed must not degrade the other four tables. Recommend **5 separate routes** (mirrors `log.py`'s one-route-per-concern precedent) unless the planner has a strong reason for one endpoint with 5 independently-flagged sub-payloads. |

**Installation:** None — no new packages.

## Package Legitimacy Audit

Not applicable — this phase installs no external packages. Skipping the slopcheck/registry-verification gate per protocol (no packages to audit).

## Architecture Patterns

### System Architecture Diagram

```
Browser (webview.js, ~3s poll, one fetch per table)
   │
   ├─ GET /api/tables/carbon ──┐
   ├─ GET /api/tables/hsqc  ───┤
   ├─ GET /api/tables/hmbc  ───┼──> tables.py router (FastAPI, mirrors log.py)
   ├─ GET /api/tables/cosy  ───┤        │
   └─ GET /api/tables/constraints ┘     │
                                          ▼
                          analysis_dir (already-resolved Path, closed over
                          by make_router() — same as log.py/status.py/structures.py)
                                          │
              ┌───────────────────────────┼────────────────────────────┐
              ▼                           ▼                            ▼
   analysis/peaks/carbon_signals.json   analysis/peaks/{hsqc,hmbc,cosy}.json   newest iteration_NN[_family]/compound.lsd
              │                           │                            │
        json.loads, tolerant       json.loads, tolerant        1. glob iteration_*/compound.lsd
        of missing file/keys       of missing file/keys        2. regex iteration_(\d+), max number, mtime tiebreak
              │                           │                     3. strip "; " lines between the two delimiter
              │                           │                        comments, json.loads (defensive — never raises)
              ▼                           ▼                            ▼
   {"state":"ok"|"waiting", "note":…, "counts":…, "rows":[...]}  (per-table, never 500)
              │
              ▼
   Browser: buildTable(headerCells, rows) + per-row <tr> CSS class (HMBC flag colouring)
   + caption element above each table (note + counts, D-05)
   + compact-intensity formatter applied to intensity cells before rendering
```

A reader can trace TBL-01/02 end-to-end: browser polls one of 4 peaks endpoints → router reads one JSON file under `analysis/peaks/` → returns ok/waiting → browser renders a table + caption. TBL-03 is the one branch that fans out into 3 steps (file selection, comment-strip, JSON parse) before reaching the same ok/waiting/render endpoint.

### Recommended Project Structure
```
src/lucy_ng/webview/
├── routers/
│   ├── log.py            # existing — pattern to mirror
│   ├── status.py         # existing
│   ├── structures.py     # existing (also has the "newest iteration_NN" precedent, see below)
│   └── tables.py         # NEW — this phase
├── static/
│   ├── index.html         # MODIFIED — Tables tab placeholder → real table containers
│   └── webview.js         # MODIFIED — 5 new render fns + fetch URLs + buildTable reuse
└── app.py                 # MODIFIED — one new lazy import + include_router line
```

### Pattern 1: The `make_router(analysis_dir)` factory (mirror exactly)

**What:** Every router in this codebase is a single function `make_router(analysis_dir: Path) -> APIRouter` that closes over `analysis_dir`, defines its routes as nested functions, and returns the router. `create_app()` calls it once per router and does the `include_router`.

**When to use:** For every one of the (recommended 5) new routes in `tables.py`.

**Example (quoted verbatim from `src/lucy_ng/webview/routers/log.py`, the canonical single-file-read router):**
```python
# Source: src/lucy_ng/webview/routers/log.py (this repo)
def make_router(analysis_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/log")
    def get_log() -> dict[str, Any]:
        return _read_log(analysis_dir)

    return router


def _read_log(analysis_dir: Path) -> dict[str, Any]:
    progress_md = analysis_dir / "CASE-PROGRESS.md"
    try:
        content = progress_md.read_text(encoding="utf-8")
        return {"state": "ok", "content": content}
    except (FileNotFoundError, OSError):
        return {"state": "waiting", "content": ""}
```

The `tables.py` equivalent for each JSON source is the same shape, with `json.loads()` added and a broader `except` clause (see Common Pitfalls #1).

### Pattern 2: "Newest iteration_NN" file selection (mirror `structures.py`, extend for family suffixes)

**What:** `structures.py` already solves "find the latest iteration directory" for `solutions.smi`:

```python
# Source: src/lucy_ng/webview/routers/structures.py (this repo)
def _newest_solutions_smi(analysis_dir: Path) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    for p in analysis_dir.glob("iteration_*/solutions.smi"):
        m = re.match(r"iteration_(\d+)$", p.parent.name)
        if m:
            candidates.append((int(m.group(1)), p))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]
```

**Difference required by D-02 (CONTEXT.md):** this existing regex `r"iteration_(\d+)$"` requires the directory name to end immediately after the digits — it will **not** match `iteration_07_anchor_recovery` (real, currently-on-disk directory name in CASE4). TBL-03 needs a **prefix-only** match plus an **mtime tiebreak**:

```python
# NEW pattern needed in tables.py — not present verbatim anywhere yet
def _newest_compound_lsd(analysis_dir: Path) -> Path | None:
    candidates: list[tuple[int, float, Path]] = []
    for p in analysis_dir.glob("iteration_*/compound.lsd"):
        m = re.match(r"iteration_(\d+)", p.parent.name)  # prefix match, no `$`
        if m:
            candidates.append((int(m.group(1)), p.stat().st_mtime, p))
    if not candidates:
        return None
    # highest iteration number wins; mtime breaks ties per D-02
    return max(candidates, key=lambda t: (t[0], t[1]))[2]
```

Verified against real directory names in `CASE4/analysis/`: `iteration_01`, `iteration_01_ethyl33`, `iteration_02_ethyl33`, ..., `iteration_07_anchor_recovery` — the highest numeric prefix (7) is the last-created directory (mtime `Jun 25 18:24`), confirming both the regex and the tiebreak logic are exercised by real historical data `[VERIFIED: direct filesystem inspection]`.

### Pattern 3: `create_app()` docking (mirror exactly)

**What:** Every router is docked with a lazy import + one `include_router` call inside `create_app()`. Quoted in full from `src/lucy_ng/webview/app.py`:

```python
# Source: src/lucy_ng/webview/app.py (this repo), lines 47-55
from lucy_ng.webview.routers import log as _log  # noqa: PLC0415
from lucy_ng.webview.routers import status as _status  # noqa: PLC0415
from lucy_ng.webview.routers import structures as _structures  # noqa: PLC0415

app.include_router(_status.make_router(analysis_dir))
app.include_router(_structures.make_router(analysis_dir))
app.include_router(_log.make_router(analysis_dir))
```

**Action for this phase:** add a fourth line, in the same style:
```python
from lucy_ng.webview.routers import tables as _tables  # noqa: PLC0415
...
app.include_router(_tables.make_router(analysis_dir))
```
`tables.py` needs no RDKit/matplotlib import, so unlike `structures.py` it does not need a lazy import *inside* `make_router()` — a module-level `import json`/`import re` is fine, matching `log.py`'s and `status.py`'s style (only `fastapi` itself is the module-level import that WV-08 cares about, and every router module already does that).

### Pattern 4: Frontend `buildTable` reuse (mirror exactly, extend for row classes)

**What:** `webview.js` already has a generic DOM table builder used by the markdown-log's pipe-table renderer:

```javascript
// Source: src/lucy_ng/webview/static/webview.js, lines 270-294 (this repo)
function buildTable(headerCells, rows) {
  var table = document.createElement('table');
  var thead = document.createElement('thead');
  var headRow = document.createElement('tr');
  headerCells.forEach(function (cell) {
    var th = document.createElement('th');
    appendInline(th, cell);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  var tbody = document.createElement('tbody');
  rows.forEach(function (rowCells) {
    var tr = document.createElement('tr');
    rowCells.forEach(function (cell) {
      var td = document.createElement('td');
      appendInline(td, cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  return table;
}
```

**Constraint for D-03 (HMBC row colouring):** `buildTable(headerCells, rows)` takes `rows: string[][]` and has no per-row metadata channel — it cannot express "this row's flag is `potential_4J`, give it a CSS class." Two viable options, both within Claude's Discretion (CONTEXT.md explicitly leaves this open):
1. **Thin wrapper** `buildTableWithRowClasses(headerCells, rows, rowClasses)` that calls `buildTable` internals but sets `tr.className = rowClasses[i]` after construction (requires either duplicating `buildTable`'s body or refactoring it to accept an optional per-row class callback).
2. **Post-process**: call `buildTable`, then walk `table.querySelectorAll('tbody tr')` and set `.className` on each by index, matching the fetched HMBC row order.

Recommend option 2 — zero changes to the existing, log-tab-tested `buildTable`, and the HMBC render function already controls the row order it requested from the fetch, so index-matching is safe as long as the backend returns rows already sorted/filtered the same way every poll (it does — deterministic `json.loads` of a static file).

`appendInline` is also reused as-is for header/cell text — it already does the safe `textContent`/`createElement` construction (no `innerHTML`), satisfying the 93-CONTEXT.md D-02/XSS-discipline carry-forward automatically for any text that flows through `buildTable`.

### Anti-Patterns to Avoid
- **Importing `cli.lsd._validate_and_parse_inventory` directly into the router:** that function is designed to `raise SystemExit(1)` and `click.echo(err=True)` on malformed input for CLI use — the exact opposite of "never 500, always degrade to waiting" (SC4). Write a webview-local variant that returns `None` on any failure instead.
- **One combined `/api/tables` response for all 5 sources:** breaks SC4's per-table waiting-state independence — one malformed JSON file must not blank out the other four tables.
- **`innerHTML` anywhere in the new render functions:** the existing `test_no_innerhtml_in_source` regression test (`tests/test_webview_api.py::TestMarkdownRendererSafety`) scans the whole `webview.js` file for the literal substring `innerHTML` — any use in the new Tables code breaks that test file-wide, not just for the Tables feature.
- **Assuming the CONSTRAINT INVENTORY JSON block has exactly the fields listed in `schemas/constraint_inventory_v2.json`:** the schema sets `"additionalProperties": true`, and the real CASE4 file (quoted below) contains extra fields not in the required/documented list (`family`, `hmbc_active`, `list_prop_constraints`, `ring_size_filter`, `ring_size_escalation`, `dropped_correlations`). Parse with `.get(key, default)` throughout — never assume a fixed key set, and never let an unexpected extra key break the parse.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Extracting the `; `-commented JSON block from an LSD file | A new regex-based multi-line JSON extractor from scratch | Mirror `_extract_inventory_block()` in `src/lucy_ng/cli/lsd.py` (lines ~175-200) — it already handles the exact delimiter pair (`=== CONSTRAINT INVENTORY v2 ===` / `=== END CONSTRAINT INVENTORY ===`), the `"; "`-prefix strip (`line[2:]` — exactly 2 chars), blank-comment-line (`;` alone) handling, and the "START without END = malformed, not absent" distinction | Getting the delimiter/strip logic subtly wrong (e.g. `.lstrip("; ")` instead of a fixed 2-char slice) silently corrupts JSON that contains leading semicolons or spaces in string values |
| Finding the "latest" iteration directory | A bespoke `sorted(glob(...))[-1]` (string sort) | Mirror `structures.py::_newest_solutions_smi`'s integer-extraction + `max()` pattern (adapted per Pattern 2 above for family suffixes + mtime tiebreak) | String-sorting `iteration_2` vs `iteration_10` puts `iteration_10` before `iteration_2` — this exact bug class is called out as "Pitfall 5" in `status.py`'s own docstring precedent |
| Rendering a table in the DOM | A new table-building function, or a client-side templating string | Reuse `buildTable(headerCells, rows)` verbatim (see Pattern 4) | Already exists, already tested (implicitly, via the log-tab pipe-table path), already satisfies the XSS-discipline test |
| Compact number formatting (`5559614` → `5.6M`) | A general-purpose number-formatting library (`numeral.js`, `d3-format`, etc. via CDN) | A ~10-line hand-rolled formatter (divide by 1e6/1e3, one decimal, `M`/`K` suffix) | REQUIREMENTS.md/CONTEXT.md explicitly forbid new CDN dependencies; this is a 1-purpose, ~5-branch function, not a hand-rolled "solved problem" — no library is proportionate |

**Key insight:** every piece of backend logic this phase needs (file-degradation shape, iteration-directory selection, comment-stripped JSON extraction) already has a working precedent somewhere in this exact codebase. The research task was to *find* those precedents, not to evaluate external libraries — there is no external-library dimension to this phase at all.

## Common Pitfalls

### Pitfall 1: Narrow `except` clauses swallow fewer failure modes than the peaks JSON actually needs
**What goes wrong:** `log.py`'s `_read_log` only catches `(FileNotFoundError, OSError)` because it never parses the content. `structures.py`'s loader additionally catches `(json.JSONDecodeError, OSError, KeyError, TypeError, ValueError)` because it parses JSON and does `.get()`/sort/index operations on it. `tables.py`'s 4 peaks-JSON readers must use the **broader** `structures.py`-style except tuple, not the narrower `log.py`-style one, because they parse JSON.
**Why it happens:** copy-pasting the simplest router (`log.py`) instead of the JSON-parsing one (`structures.py`) as the template.
**How to avoid:** template each of the 4 peaks-JSON readers on `structures.py::_load_all_structures`'s try/except shape, not `log.py`'s.
**Warning signs:** a malformed/partially-written JSON file (likely during a live run — SC4's explicit "partially written" scenario) throws `json.JSONDecodeError` uncaught → 500, violating the phase's core acceptance criterion.

### Pitfall 2: The "$$; -strip" must be exactly 2 characters, not a general strip
**What goes wrong:** Using `line.lstrip("; ")` instead of `line[2:]` after checking `line.startswith("; ")` will over-strip if the JSON content itself starts with a literal `;` or space character (e.g., inside a string value that happens to start with those chars after JSON re-serialization edge cases), or under-strip if there are exactly-one-space comment lines.
**Why it happens:** `str.lstrip(chars)` strips *any* combination of the given characters from the left, repeatedly — not a fixed prefix.
**How to avoid:** mirror the real code precedent exactly: `if line.startswith("; "): json_lines.append(line[2:])` (quoted from `cli/lsd.py` above).
**Warning signs:** intermittent JSON parse failures only on lines with unusual leading content.

### Pitfall 3: Assuming the "latest iteration" regex needs a `$` anchor
**What goes wrong:** copying `structures.py`'s `r"iteration_(\d+)$"` verbatim (with the end-anchor) will silently fail to match any family-suffixed directory (`iteration_07_anchor_recovery`), which — per D-02 and per the real CASE4 data on disk — is exactly the common case this phase must handle (`_newest_solutions_smi` matches suffix-less dirs only, which happens to be correct for its own purpose since `solutions.smi` files only ever live in bare `iteration_NN` dirs in this dataset, but `compound.lsd` files live in **both** bare and family-suffixed dirs).
**Why it happens:** reflexively copying the nearest existing "find latest iteration" helper without checking whether its anchor assumption holds for the new use case.
**How to avoid:** use `re.match(r"iteration_(\d+)", name)` (prefix match) for `compound.lsd` discovery, per Pattern 2 above — verified against real on-disk directory names.
**Warning signs:** TBL-03 shows "waiting for data" even though `iteration_07_anchor_recovery/compound.lsd` clearly exists — silently picks an earlier, wrong iteration or none at all.

### Pitfall 4: Trusting CONTEXT.md's exact peaks-JSON field names as independently re-verified
**What goes wrong:** treating `carbon_ppm`/`proton_ppm`/`flag`/`nC`/`assignment` etc. as `[VERIFIED]` ground truth for writing acceptance tests, when in fact no file with those exact names/fields exists anywhere on this machine today (see Open Questions/Assumptions Log).
**Why it happens:** the schema is quoted consistently and confidently across REQUIREMENTS.md, ROADMAP.md, CONTEXT.md, and the prior v9.3 research docs (SUMMARY.md/FEATURES.md, which claim direct inspection of a "real CASE1 run") — high repetition creates false confidence.
**How to avoid:** the planner should still build Wave-0 fixtures using the CONTEXT.md schema (it is the **locked decision** and the correct target to build against), but should NOT assume any existing CASE run's `analysis/` tree can be pointed at directly as a golden fixture. Fixtures must be authored by hand to match CONTEXT.md's documented field names.
**Warning signs:** a manual browser checkpoint against a real (but older, pre-schema) CASE run's `analysis/peaks/` directory shows empty/"waiting" tables even though peak files exist, because the real files use the older ad hoc names (`13c_curated.json`, `hmbc_curated.json`, etc., confirmed present in `C13H9OBr/analysis/peaks/` and `CASE6/analysis/peaks.json`) rather than the new canonical names this router reads.

### Pitfall 5: Confusing "file absent" with "file present but LSD-block malformed" for TBL-03
**What goes wrong:** treating every parse failure the same way loses the useful distinction CONTEXT.md D-01 requires ("Parse must be defensive... never a 500") — but `cli/lsd.py`'s own validator (`_validate_and_parse_inventory`) deliberately treats "no block at all" (returns `None`, not an error) differently from "START delimiter present but END missing" (a hard `SystemExit(1)` error in the CLI). The webview router should collapse **both** cases to "waiting" (never 500), but should not accidentally treat a malformed/truncated block as if data were simply absent when logging/debugging — a `note`/reason string in the "waiting" payload is cheap insurance and mirrors nothing existing (new, small addition) but aids debugging without violating SC4.
**Why it happens:** copying the CLI's error/success dichotomy without re-deriving what "graceful" means for a passive display endpoint.
**How to avoid:** the router's version of `_extract_inventory_block`/parse should always return either a parsed dict or `None`; the route handler maps `None` → `{"state": "waiting", ...}` uniformly, regardless of *why* extraction failed.
**Warning signs:** none externally visible (both cases correctly show "waiting"), but debugging a live run becomes harder without an internal reason captured somewhere (log line, or optional non-contractual `reason` field).

## Code Examples

### Real, on-disk CONSTRAINT INVENTORY v2 block (verified — CASE4, `iteration_07_anchor_recovery/compound.lsd`)

```
; === CONSTRAINT INVENTORY v2 ===
; {
;   "version": 2, "iteration": 7, "formula": "C14H16", "timestamp": "2026-06-25T19:30:00Z",
;   "family": "ethyl33 (RESOLVED: ethyl = CH3 17.38 / CH2 33.86; 12.89 + 24.12 = two ArCH3)",
;   "mult_count": 14, "hsqc_count": 9,
;   "hmbc_batches": [
;     {"batch": 1, "count": 5, "correlations": ["6 7", "3 6", "12 9", "6 8", "5 8"]},
;     {"batch": 2, "count": 4, "correlations": ["6 5", "5 9", "1 2", "12 6"]},
;     {"batch": 3, "count": 1, "correlations": ["5 1"]}
;   ],
;   "hmbc_active": ["5 1", "6 7", "6 5", "3 6"],
;   "hmbc_total": 4, "grouped_hmbc": [],
;   "bond_constraints": ["2 4"],
;   "cosy_equiv_pairs": [],
;   "list_prop_constraints": ["LIST L1 8 9 10 11 13 14 ; 135-137 ppm congested Cq/CH set (documentation grouping)"],
;   "elim_budget": 0,
;   "deff_not_patterns": [],
;   "ring_exclusion_enabled": true,
;   "ring_size_filter": { "status": "applied", "filter_index": "F3", "filename": "ring57", ... },
;   "deff_fexp": { "status": "none", "fragment_smiles": null, ..., "conflict_reason": "fragment database not available" },
;   "detection_results": { "hybridisation_queries": [...], "neighbours_queries": [...], "hhb_result": "...", "grouping_detected": [...] },
;   "applied_from_detection": [ "no heteroatom constraints (pure-carbon formula)", "AZULENE [5,7] ring SIZE forced via DEFF F3 ring57 goodlist filter ...", ... ],
;   "pending_from_detection": [ "deferred 4J pair STILL HELD OUT", "second fusion-Cq identity, exact ipso carbons of 24.12-Me and ethyl, ... LEFT OPEN. ..." ],
;   "ring_size_escalation": "DOCUMENTED ESCALATION ...",
;   "dropped_correlations": { "1 2": "geometrically impossible ...", "5 8": "...", ... }
; }
; === END CONSTRAINT INVENTORY ===
;
; --- MULT: atom definitions (family ethyl33) ---
MULT 1 C 3 3    ; CH3 12.89 (ArCH3 on 5-ring)
```
Source: `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/CASE4/analysis/iteration_07_anchor_recovery/compound.lsd` — quoted verbatim, `[VERIFIED: direct filesystem read]`.

This confirms every field CONTEXT.md's canonical_refs names for TBL-03 (`mult_count`, `hsqc_count`, `hmbc_batches[].correlations`, `hmbc_total`, `bond_constraints`, `cosy_equiv_pairs` (here empty — must render as "none"), `applied_from_detection`, `pending_from_detection`, `deff_fexp`, `elim_budget`, `ring_exclusion_enabled`) is real and populated as documented, **plus** several extra fields (`family`, `hmbc_active`, `list_prop_constraints`, `ring_size_filter`, `ring_size_escalation`, `dropped_correlations`) not mentioned in CONTEXT.md — confirming the schema's `additionalProperties: true` and the need for `.get()`-defensive parsing (Anti-Pattern above).

### Extraction/parsing precedent (existing, quoted from `src/lucy_ng/cli/lsd.py`)
```python
# Source: src/lucy_ng/cli/lsd.py (this repo), lines ~175-200
def _extract_inventory_block(content: str) -> str | None:
    """Extract JSON from between v2 inventory delimiters, stripping '; ' prefix.

    Returns the extracted JSON string, or None if no v2 inventory block is found
    or if the block is malformed (START delimiter present but END delimiter missing).
    """
    lines = content.splitlines()
    in_block = False
    found_end = False
    json_lines: list[str] = []
    for line in lines:
        if "=== CONSTRAINT INVENTORY v2 ===" in line:
            in_block = True
            continue
        if "=== END CONSTRAINT INVENTORY ===" in line and in_block:
            found_end = True
            break
        if in_block:
            if line.startswith("; "):
                json_lines.append(line[2:])  # strip "; " prefix (exactly 2 chars)
    # ... (malformed-vs-absent distinction continues below this excerpt)
```
`tables.py` should implement a webview-local sibling of this function that never raises — collapse both "no block" and "malformed block" to a single `None` return, then map `None` → `{"state": "waiting"}` at the route level (see Pitfall 5).

### CONSTRAINT INVENTORY v2 JSON Schema (existing, for field reference)
Location: `schemas/constraint_inventory_v2.json` (also mirrored at `src/lucy_ng/data/schemas/constraint_inventory_v2.json` for the installed package). `additionalProperties: true` at the top level — confirmed above. Required fields: `version`, `iteration`, `formula`, `timestamp`, `mult_count`, `hsqc_count`, `hmbc_batches`, `hmbc_total`. All other fields referenced in CONTEXT.md's canonical_refs (`bond_constraints`, `cosy_equiv_pairs`, `elim_budget`, `deff_fexp`, `ring_exclusion_enabled`, `applied_from_detection`, `pending_from_detection`, `detection_results`) are optional/typed but not required — the router must tolerate their absence (`.get(key, default)`), not just their presence.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| ARCHITECTURE.md's early sketch: `GET /api/tables` (discovery) + `GET /api/tables/{name}` with `name ∈ {peaks_13c, peaks_1h, constraints, hmbc_usage}`, sourced from `analysis/peaks_13c.json` (flat, no `peaks/` subdir) and parsing "HMBC usage" out of `CASE-PROGRESS.md` prose | SUMMARY.md's later reconciliation (same research session, after user override) and CONTEXT.md (locked): `analysis/peaks/carbon_signals.json`, `analysis/peaks/{hsqc,hmbc,cosy}.json` (a `peaks/` subdirectory, 4 separate files, no `hmbc_usage`/`peaks_1h` concept) | Same 2026-07-07 research session — ARCHITECTURE.md's sketch was superseded before SUMMARY.md was finalized | `ARCHITECTURE.md` (in `.planning/research/`) is a **stale draft** for this phase; do not use its endpoint/filename sketch. CONTEXT.md and SUMMARY.md's later sections are authoritative. |

**Deprecated/outdated:**
- `ARCHITECTURE.md`'s `peaks_13c.json`/`peaks_1h.json`/`hmbc_usage`-parsed-from-markdown design (lines ~249-272 of that file) — superseded within the same research pass, before CONTEXT.md was written. Flagging explicitly so the planner does not accidentally follow the older sketch if skimming `.planning/research/ARCHITECTURE.md` directly.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `analysis/peaks/carbon_signals.json` exists with fields `formula`/`dbe`/`solvent`/`note` + `signals[]` (`atom`,`ppm`,`mult`,`nC`,`assignment`,`confidence`) exactly as CONTEXT.md states | Summary, Common Pitfalls #4 | If the actual nmr-chemist-produced file differs (as every locally-inspected historical run does, under different filenames/field names), TBL-01 renders empty/"waiting" against a real run despite peak data being present. The router code itself is safe either way (never 500) — but the *acceptance criteria* and manual browser checkpoint could give a false "it works" signal if only tested against hand-built fixtures that exactly match the assumed schema, never against a real CASE run's actual output. |
| A2 | `analysis/peaks/hsqc.json` has `experiment`/`count`/`note` + `peaks[]` (`carbon_ppm`,`proton_ppm`,`intensity`,`matched_real_carbon`,`one_bond`) | Common Pitfalls #4 | Same as A1 — no on-disk file under this exact name/shape was found to cross-check. |
| A3 | `analysis/peaks/hmbc.json` has `experiment`/`raw_count`/`kept_count`/`flag_rules`/`note` + `peaks[]` (`carbon_ppm`,`carbon_ppm_observed`,`proton_ppm`,`intensity`,`flag` ∈ `{ok,potential_4J,1J_artifact}`) | Common Pitfalls #4, D-03 | Same as A1. Note the closest real analogue found (`hmbc_curated.json` in `C13H9OBr/analysis/peaks/`) uses `c_ppm`/`h_ppm`/`snr`/`potential_4J` (boolean, not a 3-way `flag` enum) — a materially different shape, suggesting the 3-way `flag` field described in CONTEXT.md may be a planned addition to the nmr-chemist skill that has not shipped in any run captured on this machine yet. |
| A4 | `analysis/peaks/cosy.json` has `experiment`/`count`/`note` + `peaks[]` (`proton_a_ppm`,`proton_b_ppm`,`intensity`) | Common Pitfalls #4 | The closest real analogue (`cosy_raw.json`, `C13H9OBr`) uses `experiment_type`/`f1_position`/`f2_position`/`intensity` — again a different key naming convention (`f1_position` vs `proton_a_ppm`). |
| A5 | These 4 filenames/schemas were "confirmed from a real CASE1 run" per `.planning/research/FEATURES.md`/`SUMMARY.md` (2026-07-07) | Summary | That verification, if it happened, was evidently against a CASE1 `analysis/` tree that either (a) lived only on the remote Sheldon host and was never copied locally, or (b) has since been cleaned/archived from this machine — the local `CASE1` test-project dir and the `case-benchmark/results/CASE1/run-01` dir both currently lack any `peaks/` subdirectory. Cannot independently re-verify in this session. Tagged `[CITED: .planning/research/FEATURES.md]`, not `[VERIFIED]`. |

**If this table is empty:** N/A — see entries above. The TBL-03 (LSD constraint inventory) side of this phase has **no** assumptions log entries — it was independently re-verified against a real, currently-on-disk file (CASE4) in this session.

## Open Questions (RESOLVED)

1. **Does the exact `analysis/peaks/{carbon_signals,hsqc,hmbc,cosy}.json` schema in CONTEXT.md actually match what the current nmr-chemist agent writes today?**
   - **RESOLVED (adopted in planning):** CONTEXT.md's schema is the authoritative locked build target; Wave-0 fixtures in plan 94-01 are hand-authored to that schema (never copied from any on-disk `analysis/` dir), per the recommendation below. Re-verify against a real current-schema CASE run at the 94-04 manual checkpoint if one becomes available.
   - What we know: CONTEXT.md (locked decision from discuss-phase) and prior v9.3 research both state this schema with high confidence and cite a real CASE1 run. The LSD-side schema (TBL-03) was independently re-verified in this session against real, current data and matches exactly.
   - What's unclear: No locally-accessible file matches the peaks-JSON schema's exact filenames or field names. The closest real analogues on this machine use different names (`13c_curated.json`, `hmbc_curated.json` with `c_ppm`/`h_ppm`/`snr`, `cosy_raw.json` with `f1_position`/`f2_position`) that appear to be an earlier/parallel convention, not the target schema.
   - Recommendation: Treat CONTEXT.md's schema as the authoritative build target (it is a locked decision — the planner should not re-litigate it), but the planner MUST build Wave-0 test fixtures by hand to match that exact schema rather than pointing tests at any existing `analysis/` directory on this machine. If a real CASE run using the exact new schema becomes available before/during execution (e.g. from Sheldon, or a fresh local run under the current nmr-chemist skill version), re-verify the manual browser checkpoint against it — this is the single highest-value verification step available for this phase.

2. **RESOLVED (adopted in planning):** Is `cosy_equiv_pairs` guaranteed to exist in every `compound.lsd`'s inventory block, or only sometimes (as an optional/newer field)? Plans parse defensively with `.get("cosy_equiv_pairs", [])` (94-02), so presence is never assumed regardless.
   - What we know: it appears (empty) in the one real file inspected (CASE4, iteration 7, `"cosy_equiv_pairs": []`). It is not in the schema's `required` list and not explicitly typed in `schemas/constraint_inventory_v2.json`'s `properties` (falls under `additionalProperties: true`).
   - What's unclear: whether older `compound.lsd` files (e.g. CASE1-3, pre-dating this field's introduction) omit it entirely.
   - Recommendation: parse with `.get("cosy_equiv_pairs", [])` — never assume presence.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fastapi | `tables.py` router (mirrors existing 3 routers) | ✓ | 0.128.2 `[VERIFIED: pip show fastapi]` | — |
| httpx | `fastapi.testclient.TestClient` (test-only) | ✓ | ≥0.27 declared in `dev` extra (pyproject.toml) | — |
| pytest | test runner | ✓ (project standard) | ≥7.0 declared | — |

**Missing dependencies with no fallback:** None — this phase adds no new dependency.

**Missing dependencies with fallback:** None applicable.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest ≥7.0, `fastapi.testclient.TestClient` (httpx-backed) — same as all existing webview tests |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["src"]` |
| Quick run command | `pytest tests/test_webview_api.py -x -q` |
| Full suite command | `pytest --cov=lucy_ng` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TBL-01 | `GET /api/tables/carbon` returns `state:"ok"` + rows with `ppm`/`mult`/`nC`/`assignment`/`confidence` when `analysis/peaks/carbon_signals.json` present; `state:"waiting"` when absent | integration (TestClient) | `pytest tests/test_webview_api.py::TestTablesEndpoint -x` | ❌ Wave 0 — new fixture + new test class needed |
| TBL-02 | `GET /api/tables/{hsqc,hmbc,cosy}` return `state:"ok"` with correct field sets; HMBC rows retain `flag` value unmodified (colouring is a frontend concern) | integration (TestClient) | `pytest tests/test_webview_api.py::TestTablesEndpoint -x` | ❌ Wave 0 |
| TBL-02 (SC4 partial-write) | Malformed/partial JSON in any of the 4 peaks files → `state:"waiting"`, HTTP 200, never 500 | integration (TestClient, hand-corrupted fixture) | `pytest tests/test_webview_api.py::TestTablesEndpoint::test_malformed_json_returns_waiting -x` | ❌ Wave 0 |
| TBL-03 | `GET /api/tables/constraints` selects highest-numeric `iteration_(\d+)` dir (with mtime tiebreak across family-suffixed dirs), strips `; ` prefix, parses JSON, returns structured payload | integration (TestClient, multi-iteration-dir fixture incl. a family-suffixed name) | `pytest tests/test_webview_api.py::TestTablesEndpoint::test_constraints_selects_highest_iteration -x` | ❌ Wave 0 |
| TBL-03 (SC4) | Missing `compound.lsd`, or START-without-END malformed block → `state:"waiting"`, never 500 | integration (TestClient) | `pytest tests/test_webview_api.py::TestTablesEndpoint::test_constraints_waiting_when_malformed -x` | ❌ Wave 0 |
| (carried) frontend XSS discipline | New render functions in `webview.js` must not introduce `innerHTML` | static-source-scan (existing test, no new test needed — it already scans the whole file) | `pytest tests/test_webview_api.py::TestMarkdownRendererSafety::test_no_innerhtml_in_source -x` | ✅ already exists, automatically covers new code added to the same file |
| (recommended, not in REQUIREMENTS) manual browser checkpoint | HMBC row colouring renders correctly, captions show note+counts, compact intensity formatting displays `M`/`K` suffixes correctly | manual (`checkpoint:human-verify`), following the 93-CONTEXT.md D-04 two-layer precedent | N/A — human browser check | ❌ Wave 0 (task, not a file) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_webview_api.py -x -q`
- **Per wave merge:** `pytest --cov=lucy_ng`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] New fixture(s) in `tests/conftest.py` (or a local fixture in `test_webview_api.py`, matching how `live_analysis_dir`/`final_analysis_dir` are already structured): an `analysis_dir` with `peaks/carbon_signals.json`, `peaks/hsqc.json`, `peaks/hmbc.json`, `peaks/cosy.json` (all matching the CONTEXT.md schema by hand, per Assumption A1-A5 — do not copy any existing on-disk file, since none matches), plus a multi-iteration `iteration_NN[_family]/compound.lsd` set (at least one family-suffixed name, e.g. `iteration_02_foo`, higher-numbered than a bare `iteration_01`, to exercise the D-02 selection logic) with a real-shaped CONSTRAINT INVENTORY v2 block (can be adapted from the CASE4 example quoted above).
- [ ] `tests/test_webview_api.py::TestTablesEndpoint` — new test class, following the existing `TestStatusEndpoint`/`TestLogEndpoint`/`TestStructuresEndpoint` structure (import-safety `try/except ImportError: pytest.skip(...)` pattern, WV-08).
- [ ] No new framework install needed — `fastapi`/`httpx`/`pytest` are already declared and installed.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Local-only dev tool, no auth in v9.2/9.3 design (unchanged by this phase) |
| V3 Session Management | No | No sessions anywhere in the webview |
| V4 Access Control | No | Single-user localhost tool |
| V5 Input Validation | Yes | All 5 new endpoints are `GET`-only with no user-supplied input parameters (no path params, no query params) — the only "input" is the content of files under `analysis_dir`, which is controlled by the CASE run itself, not by an HTTP client. Validation here means defensive JSON/comment-block parsing (never trust file *shape*, only trust that reads are scoped to `analysis_dir`) — see Common Pitfalls #1/#5. |
| V6 Cryptography | No | N/A — no crypto surface introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reflected XSS via server-controlled content rendered into the DOM (e.g. a malicious `assignment`/`note` string in a peaks JSON file containing `<img onerror=...>`) | Tampering/Information Disclosure | Already mitigated by construction: `buildTable`/`appendInline` use `textContent`/`createElement` exclusively, never `innerHTML` — confirmed by the existing regression test `test_no_innerhtml_in_source`, which scans the entire `webview.js` file (new code inherits this guarantee automatically as long as no new function introduces `innerHTML`). |
| Path traversal via a crafted `analysis_dir` | Tampering | Not attacker-controlled in this phase — `analysis_dir` is a server-startup argument (`lucy webview serve <dir>`), not a per-request parameter; all 5 new routes read fixed relative paths (`peaks/*.json`, `iteration_*/compound.lsd`) under that already-resolved root. No new traversal surface introduced (same as existing 3 routers). |
| Denial of service via a very large or deeply nested peaks/LSD file | Denial of Service | Out of scope for this phase (matches existing routers' threat model — no size/depth limits imposed anywhere in the webview today); note only if the planner wants to add a defensive cap, this would be a new, un-precedented control, not carried forward from existing code. |

## Sources

### Primary (HIGH confidence — direct codebase/filesystem inspection this session)
- `src/lucy_ng/webview/routers/log.py`, `status.py`, `structures.py`, `app.py` — full read, router pattern quoted verbatim
- `src/lucy_ng/webview/static/webview.js`, `index.html` — full read, `buildTable`/`appendInline`/tab-wiring quoted verbatim
- `tests/test_webview_api.py`, `tests/conftest.py` (fixture section) — full read, WV-08 import-safety pattern and fixture shapes confirmed
- `src/lucy_ng/cli/lsd.py` (`_extract_inventory_block`, `_validate_and_parse_inventory`) — read in context, parsing precedent quoted verbatim
- `schemas/constraint_inventory_v2.json` — full read
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/CASE4/analysis/iteration_07_anchor_recovery/compound.lsd` — full CONSTRAINT INVENTORY v2 block read and quoted verbatim (real, current, on-disk production data)
- `pyproject.toml` — `[project.optional-dependencies].webview`, `[tool.pytest.ini_options]`, hatch artifacts glob
- `pip show fastapi` — installed version 0.128.2

### Secondary (MEDIUM confidence — prior in-repo research, not independently re-verified this session)
- `.planning/research/SUMMARY.md`, `FEATURES.md` (2026-07-07) — cite the exact peaks-JSON schema as "confirmed from a real CASE1 run"; could not be independently re-verified in this session (see Assumptions Log A5)
- `.claude/agents/lucy-lsd-engineer.md` — CONSTRAINT INVENTORY v2 writer instructions (LLM-agent-driven, not code-generated), confirms the on-disk format and the write/update procedure

### Tertiary (LOW confidence / superseded — flagged, not to be followed)
- `.planning/research/ARCHITECTURE.md` (lines ~249-272) — an earlier, superseded sketch of `tables.py` using different filenames/endpoints (`peaks_13c.json`, `hmbc_usage` parsed from markdown); superseded within the same 2026-07-07 research session, before CONTEXT.md was written. Do not use.
- Ad hoc historical peak files inspected for directional shape only, NOT as schema ground truth: `data/nmrdata/active-lucy-ng-testprojects/C13H9OBr/analysis/peaks/{13c_curated,hsqc_curated,hmbc_curated,cosy_raw}.json`, `CASE6/analysis/peaks.json` — different field names than CONTEXT.md's target schema; useful only to confirm the general "top-level note/formula + array-of-records" shape is a stable convention across CASE run history.

## Metadata

**Confidence breakdown:**
- Standard stack / architecture (router pattern, app docking, frontend reuse): HIGH — every pattern quoted verbatim from this exact codebase, zero external-library research needed
- TBL-03 (LSD constraint inventory) data shape and parsing: HIGH — independently re-verified against real, current, on-disk production data (CASE4) plus existing working parser code and JSON Schema
- TBL-01/TBL-02 (peaks JSON) exact field names: MEDIUM — consistently documented across CONTEXT.md/REQUIREMENTS.md/ROADMAP.md/prior research, but not independently re-verifiable against any file present on this machine; treat as the correct locked target schema, but build fixtures by hand (see Assumptions Log, Open Question 1)
- Pitfalls: HIGH — all five pitfalls are derived from directly-observed discrepancies between existing code patterns and this phase's exact requirements (e.g. the `$`-anchor regex mismatch was caught by comparing `structures.py`'s regex against real on-disk family-suffixed directory names)

**Research date:** 2026-07-09
**Valid until:** 30 days (stable internal codebase pattern; re-check sooner if a fresh CASE run becomes available locally with the new peaks/ schema, to resolve Open Question 1)
