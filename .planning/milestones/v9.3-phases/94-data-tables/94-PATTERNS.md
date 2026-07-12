# Phase 94: Data Tables - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 6 (2 new, 3 modified, 1 test file to extend)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lucy_ng/webview/routers/tables.py` (NEW) | route (FastAPI router) | request-response / file-I/O (read-only) | `src/lucy_ng/webview/routers/log.py` (ok/waiting shape) + `structures.py` (JSON-parse tiering + "newest iteration" selection) | exact (role) / role-match (data-flow nuance: JSON parsing needs `structures.py`'s broader except tuple, not `log.py`'s narrow one) |
| `src/lucy_ng/webview/app.py` (MODIFY) | config / app-factory (router docking) | request-response (wiring only) | itself — the existing 3 `include_router` lines for status/structures/log | exact |
| `src/lucy_ng/webview/static/webview.js` (MODIFY) | component (frontend render + poll) | request-response (fetch → render) | itself — `refreshStructures`/`renderStructures` pair (fetch→render→DOM) + `buildTable(headerCells, rows)` (~line 270) | exact |
| `src/lucy_ng/webview/static/index.html` (MODIFY) | component (static markup + CSS tokens) | n/a (static) | itself — Tables tab placeholder `<div class="placeholder" data-panel="tables">` + the `#log-panel table` CSS token block | exact |
| `tests/test_webview_api.py` (MODIFY — new `TestTablesEndpoint` class) | test | request-response (TestClient integration) | itself — `TestStatusEndpoint` / `TestLogEndpoint` / `TestStructuresEndpoint` classes | exact |
| TBL-03 JSON-block parsing helper (inside `tables.py`) | utility (parser) | transform (text → dict) | `src/lucy_ng/cli/lsd.py::_extract_inventory_block()` | exact (logic to mirror, NOT to import — see Shared Patterns) |

## Pattern Assignments

### `src/lucy_ng/webview/routers/tables.py` (NEW — route, request-response/file-I/O)

**Analog 1 — the ok/waiting shape:** `src/lucy_ng/webview/routers/log.py` (full file, 62 lines)

**Imports pattern** (lines 16-21):
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
```
Add `import json` and `import re` at module level (matching `status.py` lines 17-18 — module-level is fine here, no RDKit/heavy dep involved, per RESEARCH.md Pattern 3).

**Router factory pattern** (lines 24-40):
```python
def make_router(analysis_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/log")
    def get_log() -> dict[str, Any]:
        return _read_log(analysis_dir)

    return router
```
Mirror this exactly, one `@router.get(...)` per table source (5 routes recommended per CONTEXT.md SC4 + RESEARCH.md: `/tables/carbon`, `/tables/hsqc`, `/tables/hmbc`, `/tables/cosy`, `/tables/constraints`).

**Never-500 degradation pattern** (lines 48-61):
```python
def _read_log(analysis_dir: Path) -> dict[str, Any]:
    progress_md = analysis_dir / "CASE-PROGRESS.md"
    try:
        content = progress_md.read_text(encoding="utf-8")
        return {"state": "ok", "content": content}
    except (FileNotFoundError, OSError):
        return {"state": "waiting", "content": ""}
```
For the 4 peaks-JSON readers, this narrow `except` clause is INSUFFICIENT — they must parse JSON, so use the broader analog below.

**Analog 2 — the JSON-parsing except tuple + tiered fallback:** `src/lucy_ng/webview/routers/structures.py` (`_load_all_structures`, lines 89-160)

```python
# Source: src/lucy_ng/webview/routers/structures.py, lines 104-132 (excerpt)
ranking_json = analysis_dir / "ranking_results.json"
if ranking_json.exists():
    try:
        data = json.loads(ranking_json.read_text(encoding="utf-8"))
        solutions = data.get("solutions", [])
        total = int(data.get("total_solutions", len(solutions)))
        ...
        return ("ranked", entries, total)
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        pass  # fall through to unranked
```
Copy this `except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError): pass` tuple verbatim for each of `_read_carbon`, `_read_hsqc`, `_read_hmbc`, `_read_cosy` in `tables.py` — this is the exact broader tuple RESEARCH.md Pitfall 1 calls out as required (not `log.py`'s narrower one). Each reader should look like:
```python
def _read_carbon(analysis_dir: Path) -> dict[str, Any]:
    p = analysis_dir / "peaks" / "carbon_signals.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"state": "ok", "note": data.get("note"), "counts": {...}, "rows": data.get("signals", [])}
    except (FileNotFoundError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        return {"state": "waiting", "note": None, "counts": {}, "rows": []}
```

**Analog 3 — "newest iteration_NN" selection, WITH the family-suffix fix required by D-02:** `src/lucy_ng/webview/routers/structures.py::_newest_solutions_smi` (lines 163-175)

```python
# Source: src/lucy_ng/webview/routers/structures.py, lines 163-175 — DO NOT copy the regex verbatim
def _newest_solutions_smi(analysis_dir: Path) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    for p in analysis_dir.glob("iteration_*/solutions.smi"):
        m = re.match(r"iteration_(\d+)$", p.parent.name)  # <-- `$` anchor: WRONG for tables.py
        if m:
            candidates.append((int(m.group(1)), p))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]
```
**Critical difference (D-02 / RESEARCH.md Pitfall 3):** the `$`-anchored regex above will NOT match `iteration_07_anchor_recovery` (a real, on-disk family-suffixed directory name). `tables.py` needs a **prefix-only** match plus an **mtime tiebreak**:
```python
def _newest_compound_lsd(analysis_dir: Path) -> Path | None:
    candidates: list[tuple[int, float, Path]] = []
    for p in analysis_dir.glob("iteration_*/compound.lsd"):
        m = re.match(r"iteration_(\d+)", p.parent.name)  # prefix match, no `$`
        if m:
            candidates.append((int(m.group(1)), p.stat().st_mtime, p))
    if not candidates:
        return None
    return max(candidates, key=lambda t: (t[0], t[1]))[2]
```
(Quoted from RESEARCH.md Pattern 2, itself verified against real CASE4 on-disk directories — no existing file has this exact function; it is new code following the established shape.)

**TBL-03 comment-strip + JSON parse:** see "Shared Patterns → LSD constraint-inventory parsing" below — reimplement locally in `tables.py`, do NOT import from `cli/lsd.py`.

---

### `src/lucy_ng/webview/app.py` (MODIFY — config/wiring)

**Analog:** itself, current `create_app()` (full file, 72 lines)

**Docking pattern to extend** (lines 47-55):
```python
# Phase 91: lazy imports — these modules import fastapi/RDKit and must only
# be reached via create_app(), never at package import time (WV-08).
from lucy_ng.webview.routers import log as _log  # noqa: PLC0415
from lucy_ng.webview.routers import status as _status  # noqa: PLC0415
from lucy_ng.webview.routers import structures as _structures  # noqa: PLC0415

app.include_router(_status.make_router(analysis_dir))
app.include_router(_structures.make_router(analysis_dir))
app.include_router(_log.make_router(analysis_dir))
```
**Action:** add a fourth lazy import + include_router line, same style:
```python
from lucy_ng.webview.routers import tables as _tables  # noqa: PLC0415
...
app.include_router(_tables.make_router(analysis_dir))
```
Also update the module docstring's route list (lines 26-33) to add the 5 new `GET /api/tables/*` routes, matching the existing doc-comment convention (`- GET /api/log → raw CASE-PROGRESS.md content (WV-05)`).

---

### `src/lucy_ng/webview/static/webview.js` (MODIFY — component, request-response)

**Analog 1 — the reusable table builder** (lines 270-294, quote in full — reuse verbatim, do not modify):
```javascript
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
`rows` is `string[][]`; it has NO per-row metadata channel, so D-03's HMBC flag-colouring must be applied by a **post-process** step (RESEARCH.md recommends this over forking `buildTable`): call `buildTable(headerCells, rows)`, then `table.querySelectorAll('tbody tr')` and set `.className` per index to match the fetched row order (deterministic — same JSON, same order, every poll).

`appendInline` (lines 298-320) is reused as-is for every table cell — it already guarantees `textContent`/`createElement`-only construction (no `innerHTML`), which is what makes `test_no_innerhtml_in_source` (see test analog below) pass automatically for new code appended to this file.

**Analog 2 — the fetch → render → poll skeleton** (lines 74-79 + 385-390, quote both):
```javascript
// fetch → render pair (mirror this shape per new table: refreshCarbon/refreshHsqc/... )
function refreshStructures() {
  fetch(STRUCTURES_URL)
    .then(function (r) { return r.json(); })
    .then(function (data) { renderStructures(data); })
    .catch(function (e) { console.warn('structures fetch failed:', e); });
}
```
```javascript
// tick() — the single ~3s poll driver; register new refresh*() calls here
function tick() {
  refreshStatus();
  refreshStructures();
  refreshLog();
  flashDot();
}
...
setInterval(tick, REFRESH_MS);  // D-15: ~3 s polling
```
**Action:** add `var CARBON_URL = '/api/tables/carbon';` (+ HSQC/HMBC/COSY/CONSTRAINTS) near the top alongside `STATUS_URL`/`STRUCTURES_URL`/`LOG_URL` (lines 4-7), add 5 `refreshX()`/`renderX()` pairs following the `refreshStructures`/`renderStructures` shape, and add each `refreshX()` call inside `tick()`. Each panel must render+catch **independently** (SC4: one malformed source must not blank the other four) — this independence falls out naturally from copying the existing per-source fetch/catch pattern rather than combining fetches.

**Caption pattern (D-05):** no direct analog exists (this is new UI), but the closest structural precedent is `renderStructures`'s `hint` element (lines 82-83, 171-177 — a small text element updated alongside the main render, built via `textContent` only):
```javascript
// Source: webview.js lines 171-177 (hint-text precedent for the new per-table caption)
if (total > structures.length) {
  hint.textContent = '+' + (total - structures.length) + ' more candidate'
    + (total - structures.length !== 1 ? 's' : '') + ' not shown';
} else {
  hint.textContent = total + ' candidate' + (total !== 1 ? 's' : '');
}
```
Mirror this `textContent`-only caption-building style for each table's note/counts caption.

---

### `src/lucy_ng/webview/static/index.html` (MODIFY — static markup/CSS)

**Analog 1 — the Tables tab placeholder to replace** (line 323):
```html
<div class="placeholder" data-panel="tables">Tables — coming in Phase 94</div>
```
This whole `<div>` becomes the real Tables panel container — keep `data-panel="tables"` (tab-switch wiring in `initTabs()`, lines 351-373, keys off this attribute and needs no changes), drop the `placeholder` class, and nest 5 sub-containers inside it (e.g. `<div id="table-carbon">`, `<div id="table-hsqc">`, ... `<div id="table-constraints">`), each independently replaced/filled by its `renderX()` function — this gives SC4's per-table waiting-state independence for free at the DOM level.

**Analog 2 — the existing inline `<style>` token block for tables** (lines 253-271, quote in full — reuse these tokens, do not invent new ones per RESEARCH.md "no new design system"):
```css
#log-panel table {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
  margin: 8px 0;
}
#log-panel th {
  background: #f8f9fa;
  color: #495057;
  font-weight: 600;
  text-align: left;
  padding: 4px 8px;
  border: 1px solid #dee2e6;
}
#log-panel td {
  padding: 4px 8px;
  border: 1px solid #dee2e6;
  color: #212529;
}
```
**Action:** either scope these same rules under a new `#tables-panel` / `[data-panel="tables"]` selector (since `buildTable()` output is a generic `<table>` with no `#log-panel`-specific styling hook), or generalize the existing selectors to a shared class (e.g. `.data-table`) applied by both the log-tab table renderer and the new Tables-tab renderer. Also add new CSS classes for D-03 HMBC row colouring, following the existing badge-colour token style (lines 43-46):
```css
.badge-waiting   { background: #e9ecef; color: #6c757d; }
.badge-running   { background: #d1ecf1; color: #0c5460; }
.badge-complete  { background: #d4edda; color: #155724; }
.badge-error     { background: #f8d7da; color: #721c24; }
```
Mirror this same "3-4 named state classes, background+color pair" token shape for `.flag-ok` / `.flag-potential_4j` / `.flag-1j_artifact` row classes (colour choice is Claude's discretion per CONTEXT.md, but the *shape* — flat background/foreground colour pairs — must match this existing convention, not introduce gradients/shadows/a new palette system).

---

### `tests/test_webview_api.py` (MODIFY — new `TestTablesEndpoint` class)

**Analog:** `TestLogEndpoint` (lines 106-151, quoted in full — the simplest of the three existing classes, good template for the ok/waiting-only routes; `TestStructuresEndpoint`, lines 159-330, is the better template for the JSON-parsing/tiered routes since it also exercises `tmp_path`-built custom fixtures per-test, as TBL-03's multi-iteration-dir test will need):

```python
class TestLogEndpoint:
    """WV-05 / WV-06: GET /api/log returns CASE-PROGRESS.md content or waiting."""

    def test_log_returns_content(self, live_analysis_dir: Path) -> None:
        """Live dir with CASE-PROGRESS.md → state=='ok', content contains 'Iteration 1'."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import log  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or log router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(log.make_router(live_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/log")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("state") == "ok", f"Expected state=ok: {data}"
        assert "Iteration 1" in data.get("content", ""), (
            f"Expected 'Iteration 1' in log content: {data}"
        )

    def test_log_waiting_when_empty(self, empty_analysis_dir: Path) -> None:
        """Empty dir → state=='waiting', HTTP 200."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.routers import log  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or log router not yet available")

        from fastapi import FastAPI  # pyright: ignore[reportMissingModuleSource]

        app = FastAPI()
        app.include_router(log.make_router(empty_analysis_dir))

        with TestClient(app) as client:
            r = client.get("/api/log")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["state"] == "waiting", f"Expected state=waiting: {r.json()}"
```

**Import-safety pattern (WV-08) — non-negotiable, copy verbatim into every new test method:**
```python
try:
    from fastapi.testclient import TestClient
    from lucy_ng.webview.routers import tables  # new module
except ImportError:
    pytest.skip("webview extra or tables router not yet available")

from fastapi import FastAPI
```
This ensures the test file collects cleanly even before `tables.py` exists (Wave 0 RED pattern, per the file's own module docstring lines 1-13).

**Fixture-building analog for the multi-iteration TBL-03 test** (mirrors `TestStructuresEndpoint::test_ranked_with_null_rank_does_not_drop_tier`, lines 215-250 — builds a bespoke `tmp_path`-scoped fixture inline rather than using a shared conftest fixture, exactly what TBL-03's family-suffix + mtime-tiebreak test needs):
```python
# Source: tests/test_webview_api.py lines 226-241 (excerpt) — pattern for hand-built fixtures
import json as _json

(tmp_path / "ranking_results.json").write_text(
    _json.dumps({"solutions": solutions, "total_solutions": 3}),
    encoding="utf-8",
)

app = FastAPI()
app.include_router(structures.make_router(tmp_path))

with TestClient(app) as client:
    r = client.get("/api/structures")
```
For TBL-03, build `tmp_path / "iteration_01" / "compound.lsd"` and `tmp_path / "iteration_02_anchor_recovery" / "compound.lsd"` by hand (the second with a later mtime or higher numeric prefix) with a CONSTRAINT INVENTORY v2 block adapted from the real CASE4 excerpt in RESEARCH.md, then assert `/api/tables/constraints` selects the iteration_02 one.

**Existing regression test that automatically covers new `webview.js` code — no new test needed:**
```python
# Source: tests/test_webview_api.py lines 523-535
class TestMarkdownRendererSafety:
    def test_no_innerhtml_in_source(self) -> None:
        js_path = (
            Path(__file__).parent.parent
            / "src" / "lucy_ng" / "webview" / "static" / "webview.js"
        )
        if not js_path.exists():
            pytest.skip("webview.js not yet extracted")
        source = js_path.read_text(encoding="utf-8")
        assert "innerHTML" not in source, (
            "webview.js must never use innerHTML (XSS guard, D-02) — "
            "found the literal substring 'innerHTML' in the source"
        )
```
This test scans the **whole file** — any `innerHTML` use added anywhere in the new Tables render code breaks this test file-wide (RESEARCH.md Anti-Patterns). No new test file/class is needed for this guarantee; it is inherited automatically.

**Fixture precedent for hand-built peaks JSON (`tests/conftest.py`)** — `live_analysis_dir` (lines 271-322) shows the existing convention for building a synthetic `analysis/` tree inside a fixture using plain `Path.mkdir()`/`write_text(json.dumps(...))` calls; a new `tables_analysis_dir` (or extending `live_analysis_dir`) fixture for `peaks/carbon_signals.json`/`hsqc.json`/`hmbc.json`/`cosy.json` + a multi-iteration `compound.lsd` set should follow this exact same construction style (mkdir → write_text(json.dumps(...))), per RESEARCH.md Wave-0 Gaps (build fixtures by hand — no on-disk file matches CONTEXT.md's exact peaks-JSON schema today).

---

## Shared Patterns

### 1. Ok/waiting-never-500 payload shape
**Source:** `src/lucy_ng/webview/routers/log.py::_read_log` (lines 48-61)
**Apply to:** all 5 new `tables.py` route handlers.
```python
try:
    content = progress_md.read_text(encoding="utf-8")
    return {"state": "ok", "content": content}
except (FileNotFoundError, OSError):
    return {"state": "waiting", "content": ""}
```
For JSON-parsing routes, widen the except tuple per `structures.py`'s precedent: `(FileNotFoundError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError)`.

### 2. `make_router(analysis_dir) -> APIRouter(prefix="/api")` factory
**Source:** all three existing routers (`log.py` lines 24-40, `status.py` lines 26-42, `structures.py` lines 36-81)
**Apply to:** `tables.py` as a whole — one function, closes over `analysis_dir`, returns the router; `app.py` calls it once.

### 3. "Newest iteration_NN" directory selection (with the family-suffix fix)
**Source:** `structures.py::_newest_solutions_smi` (lines 163-175) — needs the `$`-anchor removed and mtime-tiebreak added for `tables.py`'s `_newest_compound_lsd` (see full corrected version above, quoted from RESEARCH.md Pattern 2, independently verified against real CASE4 on-disk directories: `iteration_01`, `iteration_02_ethyl33`, ..., `iteration_07_anchor_recovery`).
**Apply to:** TBL-03's `compound.lsd` discovery only (not TBL-01/02, which read fixed `peaks/*.json` paths with no iteration concept).

### 4. `create_app()` lazy-import + `include_router` docking
**Source:** `src/lucy_ng/webview/app.py` lines 47-55
**Apply to:** the one new line needed in `app.py` for `tables.py`.

### 5. LSD constraint-inventory comment-strip + JSON parse (TBL-03 only)
**Source:** `src/lucy_ng/cli/lsd.py::_extract_inventory_block()` (lines 175-205, quoted in full):
```python
def _extract_inventory_block(content: str) -> str | None:
    """Extract JSON from between v2 inventory delimiters, stripping '; ' prefix.

    Returns the extracted JSON string, or None if no v2 inventory block is found
    or if the block is malformed (START delimiter present but END delimiter missing).

    Lines that are exactly ';' (blank comment lines) are mapped to empty strings.
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
            elif line == ";":
                json_lines.append("")
    if not json_lines:
        return None
    if not found_end:
        # START delimiter was present but END was never found — malformed block.
        return None
    return "\n".join(json_lines)
```
**Apply to:** a **reimplemented, webview-local sibling** of this exact function inside `tables.py`. **Do NOT import this function (or `_validate_and_parse_inventory`, `cli/lsd.py` lines 349+) directly** — `cli/lsd.py`'s validator deliberately `raise SystemExit(1)`/`click.echo(err=True)` on malformed input for CLI use, the exact opposite of the router's "never 500, always degrade to waiting" contract (RESEARCH.md Anti-Patterns, Pitfall 5). Copy the logic, keep the CLI and webview independently deployable, and after calling this local copy, wrap the result: `json.loads(result)` inside a `try/except (json.JSONDecodeError, TypeError): return None` before mapping `None` → `{"state": "waiting"}` at the route level. Parse every field with `.get(key, default)` — the schema's `additionalProperties: true` and the real CASE4 file contain extra undocumented keys (`family`, `hmbc_active`, `ring_size_filter`, etc.) that must not break the parse.

### 6. XSS discipline via `textContent`/`createElement` only (no `innerHTML`)
**Source:** `appendInline()` (webview.js lines 298-320) + the whole-file regression test `TestMarkdownRendererSafety::test_no_innerhtml_in_source` (test_webview_api.py lines 520-535)
**Apply to:** every new render function in `webview.js` — reuse `buildTable`/`appendInline` for all cell content; use `.className` assignment (not markup strings) for D-03 row colouring.

## No Analog Found

None — every file in scope has a strong (exact or role-match) analog already in the codebase; this phase is a pure "fifth router + fifth frontend panel" extension of an established pattern (per RESEARCH.md Summary). The one piece of genuinely new logic (`_newest_compound_lsd`'s family-suffix+mtime handling) is a small, well-specified correction to an existing near-analog, not a from-scratch design.

## Metadata

**Analog search scope:** `src/lucy_ng/webview/` (routers/, static/, app.py), `src/lucy_ng/cli/lsd.py`, `tests/test_webview_api.py`, `tests/conftest.py`
**Files scanned:** 8 (log.py, status.py, structures.py, app.py, webview.js, index.html, test_webview_api.py, conftest.py) + 1 targeted excerpt (cli/lsd.py `_extract_inventory_block`)
**Pattern extraction date:** 2026-07-09
