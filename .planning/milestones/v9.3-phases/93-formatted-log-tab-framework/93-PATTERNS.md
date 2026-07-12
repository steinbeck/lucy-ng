# Phase 93: Formatted Log + Tab Framework - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 4 (2 modified, 1 new, 1 test file extended)
**Analogs found:** 4 / 4 (all exact — this phase extends existing files directly; there is no "new domain" to find an external analog for)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `src/lucy_ng/webview/app.py` (MODIFIED — add `GET /webview.js`) | route/config | request-response (static file serving) | itself — existing `GET /` route in the same file | exact (self-analog, extend in place) |
| `src/lucy_ng/webview/static/webview.js` (NEW — extracted) | component (client-side script) | event-driven (poll loop) + transform (markdown→DOM) | the inline `<script>` block currently in `static/index.html` (lines 199-425) | exact (direct extraction, not a fresh design) |
| `src/lucy_ng/webview/static/index.html` (MODIFIED — tab bar + `<script src>` + `<div>` panels) | component (markup/CSS) | request-response | itself — existing `#main` two-column layout + `#log-panel-wrapper` block | exact (self-analog, extend in place) |
| `tests/test_webview_api.py` (MODIFIED — new test classes) | test | request-response / static-scan | `TestFrontend` (route smoke test) and `TestPackaging` (artifact-glob check) in the same file | exact |

No file in this phase has "no analog" — it is a pure in-place extension of four already-existing artifacts. There is no dereplication/prediction/CLI-style file to search elsewhere in the repo; all four analogs live in the same files being modified.

## Pattern Assignments

### `src/lucy_ng/webview/app.py` (route/config, request-response) — add `GET /webview.js`

**Analog:** the existing `GET /` route, same file, lines 56-63.

**Current exact code to mirror** (`src/lucy_ng/webview/app.py:56-65`):
```python
    # Serve the single-page frontend at GET /
    from fastapi.responses import FileResponse  # noqa: PLC0415

    _static_file = Path(__file__).parent / "static" / "index.html"

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(_static_file), media_type="text/html")

    return app
```

**Important deviation from RESEARCH.md's suggested snippet:** RESEARCH.md's Pattern 1 / Code Examples invent a `_static_dir` variable and a module-level `@app.get` decorator style that does not match the real file. The **actual** codebase pattern is: a single `_static_file` Path built inline right before the route, inside `create_app()`, with the `FileResponse` import lazily deferred via `# noqa: PLC0415` (WV-08 rule — no fastapi import at module scope outside this one function body). The new route MUST follow the real pattern, not the research sketch:

```python
    # Serve the single-page frontend at GET / and its extracted script at GET /webview.js
    from fastapi.responses import FileResponse  # noqa: PLC0415

    _static_file = Path(__file__).parent / "static" / "index.html"
    _webview_js = Path(__file__).parent / "static" / "webview.js"

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(_static_file), media_type="text/html")

    @app.get("/webview.js")
    def webview_js() -> FileResponse:
        return FileResponse(str(_webview_js), media_type="application/javascript")

    return app
```

**Docstring pattern** (`app.py:18-38`): the `create_app()` docstring enumerates every route as a bullet under "Returns:". Add a `- GET /webview.js → extracted dashboard script (WV-0x, Phase 93)` bullet in the same style, and update the trailing paragraph about lazy imports if it references route count.

**WV-08 lazy-import discipline** (`app.py:1-9`, `35-38`, `46-48`): this module is the *only* place fastapi may be imported at module level; router modules and the new route's `FileResponse` import must stay inside `create_app()`'s body. No change needed to this discipline — just add the new route inside the existing `FileResponse` import block (do not add a second `from fastapi.responses import FileResponse` line — reuse the one already imported for `/`).

---

### `src/lucy_ng/webview/static/webview.js` (NEW — extracted client script)

**Analog:** the inline `<script>` block in `static/index.html`, lines 199-425 (verbatim source to extract).

**IIFE + strict-mode wrapper pattern** (`index.html:199-201, 424`):
```javascript
(function () {
  'use strict';
  ...
}());
```
Preserve this wrapper exactly in the extracted `webview.js` — do not change to ES6 modules/`const`/`let` (the existing style is deliberately `var`-based ES5, per RESEARCH.md Standard Stack — "Vanilla JS (ES5-style, matches existing index.html script)").

**Fetch + render + catch pattern** (`index.html:213-219`, repeated 3x for status/structures/log):
```javascript
function refreshStatus() {
  fetch(STATUS_URL)
    .then(function (r) { return r.json(); })
    .then(function (data) { renderStatus(data); })
    .catch(function (e) { console.warn('status fetch failed:', e); });
}
```
The new `refreshLog()` must keep this exact shape (fetch → `.then(json)` → `.then(render)` → `.catch(console.warn)`), only replacing the render step's body.

**XSS-safe DOM-construction pattern already in use** (`index.html:288-296`, `349-366` — `renderStructures`): every existing render function already builds nodes via `document.createElement` + `.textContent`/`createTextNode`, never `innerHTML`, and clears via reassigning `.textContent = ''` (safe for clearing, not building). This is the established in-file precedent the new `renderLog()` / `appendInline()` / `buildTable()` functions (see RESEARCH.md Pattern 3, already fully drafted there) must follow — it is not a new discipline being introduced, it's already the file's only convention. Concrete existing precedent to imitate for "safe label building":
```javascript
// index.html:349-366 (renderStructures) — exact reference for "build DOM via
// createElement/textContent, filter+join arrays, never touch innerHTML"
labelDiv.textContent = '';
if (parts.length > 0) {
  var rankSpan = document.createElement('span');
  rankSpan.className = 'tile-rank';
  rankSpan.textContent = rankText || ('Index ' + idx);
  labelDiv.appendChild(rankSpan);
  ...
}
```

**Scroll-preserve pattern to keep unchanged (D-13)** (`index.html:382-399`, current `refreshLog`):
```javascript
function refreshLog() {
  var logEl = document.getElementById('log-panel');
  var atBottom = (logEl.scrollHeight - logEl.scrollTop) <= (logEl.clientHeight + 5);

  fetch(LOG_URL)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var content = data.content || '';
      logEl.textContent = content || 'Waiting for log data...';
      if (atBottom) { logEl.scrollTop = logEl.scrollHeight; }
    })
    .catch(function (e) { console.warn('log fetch failed:', e); });
}
```
The `atBottom`-before / `scrollTop`-restore-after structure is the exact contract to preserve; only the middle assignment (`logEl.textContent = ...`) is replaced by a call to the new `renderLog(content, logEl)` (RESEARCH.md's updated `refreshLog()` snippet already reflects this correctly — use it verbatim as the target implementation, it is the one part of RESEARCH.md's Code Examples that matches file reality exactly, unlike the `app.py` snippet above).

**Bootstrap/polling loop to preserve unchanged** (`index.html:411-422`):
```javascript
function tick() {
  refreshStatus();
  refreshStructures();
  refreshLog();
  flashDot();
}

tick();
setInterval(tick, REFRESH_MS);
```
Add `initTabs()` as a one-time call near `tick()` bootstrap (not inside the interval — tabs are click-driven, not polled), e.g. immediately before or after the `tick();` bootstrap line.

**New content this phase adds to webview.js with no direct in-file precedent** (write fresh, per RESEARCH.md Pattern 2/3 — already vetted code, use as-is):
- `initTabs()` / `activate(tabName)` — tab click-handler + `display` toggle (RESEARCH.md Architecture Patterns, Pattern 2, lines 192-217 of 93-RESEARCH.md)
- `renderLog(rawText, container)`, `buildTable(headerCells, rows)`, `appendInline(parent, text)` — markdown block/inline parser (RESEARCH.md Pattern 3, lines 236-367 of 93-RESEARCH.md)

---

### `src/lucy_ng/webview/static/index.html` (MODIFIED — tab bar markup + panel divs + external script tag)

**Analog:** itself — the existing `#main` / `#structure-panel` / `#log-panel-wrapper` block, lines 179-197, plus the `<style>` block, lines 7-165.

**Structure to keep unchanged** (`index.html:179-189`, left column):
```html
<div id="main">
  <div id="structure-panel">
    <h2>Candidate Structures</h2>
    <div id="structure-grid">
      <div id="structure-waiting">Waiting for candidates...</div>
    </div>
    <div id="structure-hint"></div>
  </div>
  ...
```
Per D-01/UI-SPEC, this left column is untouched by Phase 93 — do not add tab machinery here.

**Structure to replace** (`index.html:191-195`, right column — becomes the tab dock):
```html
  <!-- Log panel (right) -->
  <div id="log-panel-wrapper">
    <h2>Run Log</h2>
    <pre id="log-panel">Waiting for log data...</pre>
  </div>
```
Replace the static `<h2>Run Log</h2>` with the `#tab-bar` (4 buttons, `data-tab` attrs, per UI-SPEC Component Specifications table), and replace the single `<pre id="log-panel">` with four `[data-panel]` divs (`log`, `spectra-1d`, `spectra-2d`, `tables`) — the existing `log-panel` div becomes `<div id="log-panel" data-panel="log">` (a `<div>` now, not `<pre>`, per UI-SPEC "Markdown-rendered Run Log panel" section and RESEARCH.md Recommended Project Structure).

**Script tag to replace** (`index.html:199` open tag / `425` close tag): delete the entire inline `<script>...</script>` block (lines 199-425) and replace with:
```html
<script src="/webview.js"></script>
```

**CSS tokens to extend, not invent** (`index.html:127-158`, `#log-panel-wrapper` / `#log-panel` rules): the existing `#log-panel` rule sets `font-family: monospace; white-space: pre-wrap; ...` at the container level — per UI-SPEC this must be REMOVED from the container (the new `<div>` does not set page-wide monospace/pre-wrap; each rendered child node — `h1`/`h2`/`h3`/`p`/`code`/`pre code`/`table` — controls its own typography per the UI-SPEC "Markdown-rendered Run Log panel" table). Keep the box model (`background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 10px 12px; overflow-y: scroll; min-height: 200px;`) and only adjust `max-height` per UI-SPEC (`calc(100vh - 156px)`, +36px vs current `calc(100vh - 120px)` to make room for the new tab-bar row).

**Existing color/spacing tokens already in the stylesheet to reuse verbatim for the new tab-bar/markdown rules** (no new hex values — see UI-SPEC Color table, all sourced from these exact lines):
- `#dee2e6` border color — `index.html:24` (`#status-bar` border-bottom), reused for tab-bar bottom border, table cell borders, `hr`
- `#6c757d` muted text — `index.html:118` (`#structure-hint`), reused for inactive tab labels, placeholder copy
- `#495057` — `index.html:34` (`.label`), reused for inactive-tab hover + `h3` headings
- `#212529` — `index.html:15` (`body` color), reused as the tab active-accent + rendered heading/bold text
- `#f8f9fa` — `index.html:14` (`body` background), reused for inline-code background + table header background

---

### `tests/test_webview_api.py` (MODIFIED — new test classes/cases)

**Analog 1 — route smoke test:** `TestFrontend.test_index_html_served` (`tests/test_webview_api.py:403-422`):
```python
class TestFrontend:
    """WV-06: GET / serves index.html with Content-Type text/html."""

    def test_index_html_served(self, live_analysis_dir: Path) -> None:
        """GET / → HTTP 200, Content-Type starts with 'text/html'."""
        try:
            from fastapi.testclient import TestClient  # pyright: ignore[reportMissingModuleSource]

            from lucy_ng.webview.app import create_app  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            pytest.skip("webview extra or create_app not yet available")

        with TestClient(create_app(live_analysis_dir)) as client:
            r = client.get("/")

        assert r.status_code == 200, f"Expected 200 for GET /, got {r.status_code}: {r.text[:200]}"
        content_type = r.headers.get("content-type", "")
        assert content_type.startswith("text/html"), (
            f"Expected content-type to start with text/html: {content_type!r}"
        )
```
Add `test_webview_js_served` as a new method in this exact class, same try/except-skip / `create_app` / `TestClient` shape, asserting `r.status_code == 200` and `content_type.startswith("application/javascript")` (or also accept `"text/javascript"` per RESEARCH.md A3) for `client.get("/webview.js")`.

**Analog 2 — hatch-artifact static scan:** `TestPackaging.test_hatch_artifacts_include_static` (`tests/test_webview_api.py:463-484`):
```python
class TestPackaging:
    """WV-08: pyproject.toml hatch artifacts include src/lucy_ng/webview/static/*."""

    def test_hatch_artifacts_include_static(self) -> None:
        """[tool.hatch.build.targets.wheel].artifacts contains 'src/lucy_ng/webview/static/*'."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as fh:
            pyproject = tomllib.load(fh)

        artifacts: list[str] = (
            pyproject.get("tool", {})
            .get("hatch", {})
            .get("build", {})
            .get("targets", {})
            .get("wheel", {})
            .get("artifacts", [])
        )

        assert "src/lucy_ng/webview/static/*" in artifacts, (
            f"'src/lucy_ng/webview/static/*' not found in hatch wheel artifacts.\n"
            f"Current artifacts: {artifacts}"
        )
```
Verified: this glob string is present verbatim today (`pyproject.toml:70`, inside `[tool.hatch.build.targets.wheel].artifacts`, lines 65-71 — flat single-level glob, no subdirectory, confirmed non-recursive as RESEARCH.md Pitfall 2 describes). Extend this test with a second assertion in the SAME method or a new method in the same class:
```python
static_dir = Path(__file__).parent.parent / "src" / "lucy_ng" / "webview" / "static"
assert (static_dir / "webview.js").exists(), (
    "webview.js must exist at the flat static/ level for the existing hatch glob to cover it"
)
```
No `pyproject.toml` change is required this phase — only add the existence assertion (Pitfall 2's recommended regression guard).

**New test class — static-source XSS-guard scan (no existing analog in this file; write following the same import-inside-body / skip pattern used by every other class in this file):**
```python
class TestMarkdownRendererSafety:
    """LOG-01 / D-02: static/webview.js must never assign server content via innerHTML."""

    def test_no_innerhtml_in_source(self) -> None:
        """'innerHTML' must not appear anywhere in static/webview.js (regression guard)."""
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
This is a pure string-scan test (no fastapi import needed at all), so it does not need the try/except-skip-on-ImportError pattern used by the fastapi-dependent classes — only the `if not js_path.exists(): pytest.skip(...)` guard for Wave-0 (file not yet created) ordering, consistent with how `TestPackaging` has no fastapi dependency either.

**Module-level import discipline to preserve** (`tests/test_webview_api.py:1-20`): keep `from __future__ import annotations`, `pathlib.Path`, `pytest`, `tomllib` as the only module-level imports; every `fastapi` / `lucy_ng.webview.*` import stays inside each test method body per the file's own header docstring (WV-08 rule, lines 10-13).

---

## Shared Patterns

### Lazy fastapi import discipline (WV-08)
**Source:** `src/lucy_ng/webview/app.py` lines 1-9, 35-38, 46-48, 56-57; `tests/test_webview_api.py` lines 10-13 (module docstring) and every test method (`try: from fastapi... except ImportError: pytest.skip(...)`).
**Apply to:** `app.py`'s new `/webview.js` route (reuse the already-imported `FileResponse`, do not import at module scope) and every new test method in `test_webview_api.py` that touches fastapi/TestClient/create_app.

### DOM-safety via textContent/createElement only (D-02/D-12/T-91-09)
**Source:** `src/lucy_ng/webview/static/index.html` lines 288-296, 349-366 (`renderStructures`), 391 (`refreshLog`, current single-line version); RESEARCH.md Pattern 3 (full block/inline parser).
**Apply to:** every new function in `webview.js` that touches DOM content derived from `/api/log`, `/api/status`, `/api/structures` — never `innerHTML`, clear via `while (el.firstChild) el.removeChild(el.firstChild)` (new) or plain reassignment of `.textContent = ''` (existing precedent, both acceptable per RESEARCH.md Anti-Patterns note — the removeChild loop is the *stricter* habit RESEARCH.md recommends going forward to avoid muscle-memory drift toward `innerHTML`).

### Explicit `media_type` on every `FileResponse` (Pitfall 5)
**Source:** `src/lucy_ng/webview/app.py` line 63 (`media_type="text/html"` for `/`).
**Apply to:** the new `/webview.js` route — `media_type="application/javascript"`, never rely on `mimetypes.guess_type()` fallback.

### Fetch/then/catch shape for all polled endpoints
**Source:** `index.html` lines 214-219 (`refreshStatus`), 273-278 (`refreshStructures`), 382-399 (`refreshLog`).
**Apply to:** no new fetch is added this phase (tab switching triggers no fetch per RESEARCH.md Pattern 2/UI-SPEC), but `refreshLog`'s existing shape is the template for how `renderLog()` is invoked inside the `.then(data => ...)` callback.

## No Analog Found

None. All four touched files already exist in the repository and are being extended in place; there is no file in this phase whose closest match lives outside the files it is directly extracted from/into.

## Metadata

**Analog search scope:** `src/lucy_ng/webview/` (app.py, static/index.html, routers/log.py), `tests/test_webview_api.py`, `pyproject.toml` (`[tool.hatch.build.targets.wheel]`)
**Files scanned:** 5 (app.py, index.html, log.py, test_webview_api.py, pyproject.toml)
**Pattern extraction date:** 2026-07-07

## PATTERN MAPPING COMPLETE

**Phase:** 93 - Formatted Log + Tab Framework
**Files classified:** 4 (app.py modified, webview.js new/extracted, index.html modified, test_webview_api.py extended)
**Analogs found:** 4 / 4

### Coverage
- Files with exact analog: 4
- Files with role-match analog: 0
- Files with no analog: 0

### Key Patterns Identified
- `app.py`'s real `/` route pattern is a `_static_file = Path(...)` variable built inline inside `create_app()`, with `FileResponse` imported lazily via `# noqa: PLC0415` (WV-08) — RESEARCH.md's own code snippet uses a slightly different `_static_dir` shape that does NOT match the actual file; planner/executor must follow the real `app.py` shape (documented above), not the research sketch, for this one detail.
- `index.html`'s existing inline `<script>` (lines 199-425) already follows every DOM-safety convention (`createElement`/`textContent`, never `innerHTML`) that D-02 requires for the new markdown renderer — this is a direct, in-file precedent, not a new discipline being introduced.
- `tests/test_webview_api.py` has two directly reusable class templates: `TestFrontend` (route smoke test, extend for `/webview.js`) and `TestPackaging` (hatch-artifact glob check, extend with an existence assertion) — both need only additive test methods, no new import-discipline pattern to invent. The new `TestMarkdownRendererSafety` class is genuinely new but trivially follows the same file's conventions (pathlib-based, skip-if-not-ready).
- `pyproject.toml`'s `src/lucy_ng/webview/static/*` glob (line 70) is confirmed flat/non-recursive and already covers `webview.js` with zero `pyproject.toml` changes needed this phase.

### File Created
`.planning/phases/93-formatted-log-tab-framework/93-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files.
