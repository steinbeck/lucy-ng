# Phase 93: Formatted Log + Tab Framework - Research

**Researched:** 2026-07-07
**Domain:** Vanilla-JS frontend extension of an existing FastAPI dashboard (no new backend logic, no new dependencies)
**Confidence:** HIGH

## Summary

Phase 93 is a pure-frontend change to the v9.2 webview. The existing dashboard
(`src/lucy_ng/webview/static/index.html`) is a single file: inline `<style>`, a two-column
flex layout (`#structure-panel` left, `#log-panel-wrapper` right), and an inline `<script>`
implementing a 3-second poll loop (`tick()` → `refreshStatus` / `refreshStructures` /
`refreshLog`). The log panel is a `<pre>` element whose content is set via
`logEl.textContent = content` — raw `CASE-PROGRESS.md` text, no markdown rendering
(`D-12` in the v9.2 design). This phase must (1) extract all inline JS into
`static/webview.js`, served via an explicit `GET /webview.js` route in `app.py`
mirroring the existing `GET /` `FileResponse` pattern; (2) add a tab bar that shows/hides
panels via plain `display` toggling (no router, no framework); (3) replace the `<pre>` log
panel with a hand-rolled markdown-to-DOM renderer that covers exactly the subset the
coordinator actually writes to `CASE-PROGRESS.md` (verified against
`.claude/commands/lucy-ng/references/progress-format.md`): `#`/`##`/`###` headings,
`**bold**` field-label spans, inline `` `code` `` spans, `---` horizontal rules, and pipe
tables (used once, in the `## Timing Summary` block). Fenced code blocks are not present in
any real `CASE-PROGRESS.md` example found in this repo, but the locked design decision
requires supporting them defensively.

The single hard constraint carried over from v9.2 (`D-12`/`T-91-09`) is that server content
must reach the DOM only via `textContent` / `createElement`, never `innerHTML`. This is
not a performance nicety — CASE-PROGRESS.md can contain SMILES/CXSMILES strings
inside `**field:**` values, and those can legally contain `<` and `>` characters, so an
`innerHTML` assignment on run-derived text is a real injection vector, not a theoretical one.

**Primary recommendation:** Build a small (~60-80 line) line-based block parser plus a
~20-line inline-span tokenizer, both operating purely through DOM node construction
(`document.createElement`, `document.createTextNode`) — never string concatenation into
`innerHTML`. Keep the existing 3-second `tick()` polling every panel regardless of which
tab is visible (cheap JSON/text fetches); do not gate fetches behind tab visibility in this
phase.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tab switching (show/hide panels) | Browser / Client | — | Pure DOM/CSS state, no server round-trip |
| Markdown → DOM rendering of log content | Browser / Client | — | Server intentionally stays "dumb" (D-12); all formatting logic is client-side |
| `CASE-PROGRESS.md` raw text delivery | API / Backend (existing `routers/log.py`) | — | Already implemented in v9.2; Phase 93 does not touch this endpoint |
| `/webview.js` static file serving | Frontend Server (FastAPI `create_app`) | — | New explicit route, same pattern as the existing `GET /` `FileResponse` |
| Packaging of `static/webview.js` into the wheel | Build / Static | — | `hatch` artifact glob (already covers flat files under `static/`) |

**Why this matters here:** every capability in this phase lives in the Browser/Client tier
except the one-line `/webview.js` route addition, which belongs in the existing Frontend
Server tier (`app.py`). There is no API/Backend logic change and no Database/Storage
change in this phase — this confirms the roadmap's claim that Phase 93 carries "zero
backend risk."

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOG-01 | User sees the run log (`CASE-PROGRESS.md`) rendered with markdown formatting — headings, agent sections, bold, tables, monospace code — instead of raw text, updated live on the existing ~3 s refresh. | See "Code Examples" (markdown-to-DOM renderer) and "Common Pitfalls" (scroll-preserve regression risk, table false-positive detection). Markdown subset verified against real coordinator-writing rules in `progress-format.md`, not assumed. |
| TAB-01 | User navigates the dashboard via tabs (per REQUIREMENTS.md: Overview/Structures/Spectra/Tables/Log; per ROADMAP.md Phase 93 criterion: Run Log/1D Spectra/2D Spectra/Tables) without a page reload; existing v9.2 widgets remain reachable. | See "Open Questions" #1 — the two source documents name the tabs differently; recommended resolution is documented there. See "Code Examples" for the tab-switch pattern. |

</phase_requirements>

## Standard Stack

### Core

No new libraries. This phase adds zero entries to `pyproject.toml`.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | `>=0.100` (already declared in `[webview]` extra) `[VERIFIED: codebase — pyproject.toml line 58]` | Serves the new `GET /webview.js` route via `FileResponse`, identical pattern to the existing `GET /` route | Already the project's only backend framework for this dashboard; no alternative considered |
| Vanilla JS (ES5-style, matches existing `index.html` script) | n/a | Tab switching + markdown-to-DOM renderer | Locked project constraint: no CDN, no bundler, no framework (`CLAUDE.md`, `D-12`, v9.2 design spec) |

### Supporting

None. No supporting packages are introduced by this phase.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled ~80-line markdown subset parser | `marked.js` / `markdown-it` (CDN or bundled) | Explicitly forbidden by the locked v9.3 design decision and the project's no-CDN/no-build constraint; also would need a `dangerouslySetInnerHTML`-equivalent step to inject parsed HTML, reopening the exact XSS vector the v9.2 `D-12` decision closed |
| Plain CSS `display:none/block` tab switching | Client-side router / URL-hash routing | Unnecessary complexity for 4 static panels in one page; no deep-linking requirement stated in REQUIREMENTS.md or ROADMAP.md |
| `FileResponse` for `/webview.js` | Inline `<script>` (current v9.2 state) | Explicit route is what success criterion 4 requires (extraction + packaging test); inline script cannot satisfy "present in the installed wheel" verification independently |

**Installation:** None required — this phase adds no dependencies.

**Version verification:** N/A — no new packages.

## Package Legitimacy Audit

**Not applicable.** Phase 93 installs zero new external packages (no new Python
dependency, no npm package, no CDN script tag — confirmed against `pyproject.toml`
`[project.optional-dependencies].webview` which lists only `fastapi>=0.100` and
`uvicorn>=0.20`, both already present and already used by shipped v9.2 code). The
slopcheck/registry-verification gate is skipped because there is nothing to verify.

## Architecture Patterns

### System Architecture Diagram

```
Browser                                    FastAPI (app.py / create_app)
--------                                   -----------------------------
GET /            ────────────────────────► FileResponse(index.html)
                 ◄──────────────────────── text/html (tab shell + panel divs)

GET /webview.js  ────────────────────────► FileResponse(webview.js)   [NEW - this phase]
                 ◄──────────────────────── application/javascript

  tick() every 3000ms:
    fetch /api/status      ─────────────► routers/status.py   (unchanged)
    fetch /api/structures  ─────────────► routers/structures.py (unchanged)
    fetch /api/log         ─────────────► routers/log.py      (unchanged: raw text passthrough)
                 ◄──────────────────────── {"state": "ok", "content": "<raw markdown>"}

  [renderLog(content)]                              (NEW - this phase, client-only)
    │
    ├─ blockParse(content) → list of block tokens (heading/hr/table/para/list/code-fence)
    ├─ for each block: createElement(tag) + inlineParse(text) → strong/code/text nodes
    └─ replace #log-panel children (never innerHTML) while preserving D-13 scroll behaviour

  [Tab bar click handler]                           (NEW - this phase, client-only)
    │
    └─ toggle .active class + display on #tab-log / #tab-spectra-1d /
       #tab-spectra-2d / #tab-tables  (no fetch triggered by tab switch itself)
```

Data flow for the primary use case (user reads a formatted log): the browser's existing
3-second timer fetches raw markdown text from the unchanged `GET /api/log` endpoint; the
NEW client-side `renderLog()` function converts that text into a DOM subtree using only
`createElement`/`textContent`; the NEW tab bar independently controls which top-level
panel is visible, orthogonal to the polling loop (polling continues for all panels
regardless of active tab, matching the existing v9.2 "always refresh" behaviour).

### Recommended Project Structure

```
src/lucy_ng/webview/
├── app.py                  # MODIFIED: add GET /webview.js FileResponse route
├── static/
│   ├── index.html          # MODIFIED: tab bar markup + 4 panel <div>s;
│   │                       #   <script src="/webview.js"></script> replaces inline <script>;
│   │                       #   #log-panel becomes a <div> (was <pre>)
│   └── webview.js          # NEW: all JS extracted from index.html, plus:
│                           #   - tab switch handler
│                           #   - markdown block parser + inline tokenizer
│                           #   - renderLog() replacing the old textContent assignment
```

No new directories. `static/webview.js` sits at the same flat level as `index.html`, so
the existing hatch glob `"src/lucy_ng/webview/static/*"` covers it without any
`pyproject.toml` change (verified — see "Common Pitfalls" #2 for the one thing to still
test).

### Pattern 1: Explicit static-file route with correct MIME type

**What:** Serve `webview.js` the same way `index.html` is served today — `FileResponse`
with an explicit `media_type`.
**When to use:** Any time a static asset must be reachable at a stable, predictable path
independent of the FastAPI static-files mount machinery (project has none configured; the
existing pattern is per-file explicit routes).
**Example:**
```python
# Source: existing pattern in src/lucy_ng/webview/app.py (GET / route), extended
from fastapi.responses import FileResponse  # noqa: PLC0415

_static_dir = Path(__file__).parent / "static"

@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(_static_dir / "index.html"), media_type="text/html")

@app.get("/webview.js")
def webview_js() -> FileResponse:
    return FileResponse(str(_static_dir / "webview.js"), media_type="application/javascript")
```
Explicit `media_type` avoids relying on `mimetypes.guess_type()` for `.js`, which is
inconsistent across host OS mimetypes databases and can fall back to
`application/octet-stream` (some browsers refuse to execute a `<script src>` with that
Content-Type under strict MIME-sniffing policies).

### Pattern 2: Tab switching via plain class/display toggling

**What:** Four (or five — see Open Questions) top-level panel `<div>`s, one "active" at a
time, toggled by a click handler on sibling `<button>`/`<div data-tab="...">` elements.
**When to use:** Static, small, fixed set of panels with no deep-linking requirement.
**Example:**
```javascript
// Source: hand-written pattern consistent with existing index.html JS style (IIFE, 'use strict')
function initTabs() {
  var buttons = document.querySelectorAll('#tab-bar [data-tab]');
  var panels = document.querySelectorAll('[data-panel]');

  function activate(tabName) {
    for (var i = 0; i < panels.length; i++) {
      panels[i].style.display = (panels[i].getAttribute('data-panel') === tabName)
        ? 'flex' : 'none';
    }
    for (var j = 0; j < buttons.length; j++) {
      var isActive = buttons[j].getAttribute('data-tab') === tabName;
      buttons[j].classList.toggle('active', isActive);
    }
  }

  for (var k = 0; k < buttons.length; k++) {
    buttons[k].addEventListener('click', function (evt) {
      activate(evt.currentTarget.getAttribute('data-tab'));
    });
  }

  activate('log');  // default tab on load
}
```
No `fetch` call is triggered by `activate()` itself — the existing `tick()` loop already
refreshes every panel's data every 3 s regardless of visibility, so switching tabs simply
reveals already-current DOM content.

### Pattern 3: Line-based markdown block parser (textContent-only)

**What:** Convert the exact `CASE-PROGRESS.md` subset into DOM nodes without ever
building an HTML string.
**When to use:** Exactly this phase's log renderer; the subset is closed (verified against
`.claude/commands/lucy-ng/references/progress-format.md`, the authoritative writer spec):
`#`/`##`/`###` headings, `**bold**` spans (used almost exclusively as `**Field:** value`
labels), inline `` `code` `` spans (filenames/constraint expressions,
e.g. `` `fragment_abc123.lsd` ``), `---` horizontal rules (section separators), one pipe
table (`## Timing Summary`), and — per the locked design decision — fenced code blocks
defensively, even though none appear in current real output.
**Example:**
```javascript
// Source: hand-written; block-level dispatcher.
function renderLog(rawText, container) {
  // Clear existing children WITHOUT innerHTML (preserves D-13 scroll-restore contract
  // at the call site — see refreshLog() below).
  while (container.firstChild) { container.removeChild(container.firstChild); }

  var lines = rawText.split('\n');
  var i = 0;
  while (i < lines.length) {
    var line = lines[i];

    // Fenced code block: ```...```
    if (/^```/.test(line)) {
      var codeLines = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { codeLines.push(lines[i]); i++; }
      i++; // skip closing fence
      var pre = document.createElement('pre');
      var codeEl = document.createElement('code');
      codeEl.textContent = codeLines.join('\n');
      pre.appendChild(codeEl);
      container.appendChild(pre);
      continue;
    }

    // Heading: #, ##, ### (only levels used by the coordinator's writer)
    var headingMatch = /^(#{1,3})\s+(.*)$/.exec(line);
    if (headingMatch) {
      var tag = 'h' + headingMatch[1].length;
      var hEl = document.createElement(tag);
      appendInline(hEl, headingMatch[2]);
      container.appendChild(hEl);
      i++;
      continue;
    }

    // Horizontal rule
    if (/^---+\s*$/.test(line)) {
      container.appendChild(document.createElement('hr'));
      i++;
      continue;
    }

    // Pipe table: header row + separator row (e.g. |---|---|) required before treating
    // as a table — avoids false positives on stray '|' characters in body text.
    if (/^\|.*\|\s*$/.test(line) && i + 1 < lines.length
        && /^\|[\s:-]+\|\s*$/.test(lines[i + 1])) {
      var headerCells = line.split('|').slice(1, -1).map(function (s) { return s.trim(); });
      i += 2; // skip header + separator
      var rows = [];
      while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) {
        rows.push(lines[i].split('|').slice(1, -1).map(function (s) { return s.trim(); }));
        i++;
      }
      container.appendChild(buildTable(headerCells, rows));
      continue;
    }

    // Bullet list item: - text  (used in ### Team Models)
    if (/^-\s+/.test(line)) {
      var ul = document.createElement('ul');
      while (i < lines.length && /^-\s+/.test(lines[i])) {
        var li = document.createElement('li');
        appendInline(li, lines[i].replace(/^-\s+/, ''));
        ul.appendChild(li);
        i++;
      }
      container.appendChild(ul);
      continue;
    }

    // Blank line: skip
    if (line.trim() === '') { i++; continue; }

    // Default: paragraph line (covers **Field:** value lines)
    var p = document.createElement('p');
    appendInline(p, line);
    container.appendChild(p);
    i++;
  }
}

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

// Inline tokenizer: splits on **bold** and `code` spans, appends child nodes
// via textContent / createElement ONLY — never innerHTML.
function appendInline(parent, text) {
  var tokenRe = /\*\*(.+?)\*\*|`(.+?)`/g;
  var lastIndex = 0;
  var match;
  while ((match = tokenRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
    }
    if (match[1] !== undefined) {
      var strong = document.createElement('strong');
      strong.textContent = match[1];
      parent.appendChild(strong);
    } else {
      var code = document.createElement('code');
      code.textContent = match[2];
      parent.appendChild(code);
    }
    lastIndex = tokenRe.lastIndex;
  }
  if (lastIndex < text.length) {
    parent.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
}
```

This satisfies the phase's mandatory XSS acceptance criterion by construction: even if
`text` contains `<img src=x onerror=alert(1)>`, `document.createTextNode(text)` /
`el.textContent = text` always renders it as literal characters — there is no code path
in this renderer that ever assigns to `.innerHTML` or uses template-string HTML
concatenation.

### Anti-Patterns to Avoid

- **`innerHTML = convertedHtml`:** Reintroduces the exact XSS vector v9.2's `D-12`
  decision closed. Never acceptable for server-derived content in this codebase.
- **Regex-based "markdown to HTML string" conversion** (e.g.
  `text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')` followed by
  `el.innerHTML = converted`): produces the same vector as above even though it looks like
  "just regex" — the resulting string still gets parsed as HTML on assignment.
- **Rebuilding `#log-panel` from `innerHTML = ''`, then rebuilding via `createElement`:**
  Clearing via `innerHTML = ''` is safe (it does not interpret markup on read), but writing
  the habit into muscle memory next to unsafe patterns increases the chance of an accidental
  regression in a later phase. Use `while (el.firstChild) el.removeChild(el.firstChild)`
  instead, for consistency with the "never touch innerHTML" rule everywhere in this file.
- **Full markdown-spec parsers (CommonMark) on the client:** Unneeded complexity for a
  closed, verified 6-construct subset; also typically ship as a bundled library, violating
  the no-build/no-CDN constraint.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Full CommonMark/GFM markdown parsing (nested lists, links, images, blockquotes, tables with alignment markers, etc.) | A general-purpose markdown engine from scratch | The closed 6-construct subset parser in "Code Examples" | `CASE-PROGRESS.md` is written by exactly one program (`case.md` coordinator) against a documented, stable format (`progress-format.md`) — it will never contain arbitrary user markdown. Building for the full spec is wasted surface area and wasted testing effort. |
| HTML sanitization / escaping library (e.g. DOMPurify) | A sanitizer to "clean" content before `innerHTML` | `textContent`/`createElement` throughout (no sanitization needed because no HTML parsing ever happens) | Sanitizer libraries are a second line of defense for when you must use `innerHTML`. This project's actual defense is architectural: never call `innerHTML` on server content at all. Adding a sanitizer here would be solving a self-inflicted problem while also violating the no-CDN/no-bundle constraint. |
| Client-side router (hash routing / History API) for tabs | A URL-routing micro-library | Plain `data-tab` attribute + `display` toggle (Pattern 2) | Four static panels with no deep-link requirement in REQUIREMENTS.md/ROADMAP.md; a router adds indirection with zero product benefit here. |

**Key insight:** The entire security story for this phase reduces to one invariant: *no
function in `webview.js` ever assigns a string derived from server content to
`.innerHTML`*. Everything else (markdown parsing, tab switching) is ordinary DOM
manipulation. The "don't hand-roll" table above is short because there is genuinely very
little to reach for off-the-shelf here — the constraint set (no CDN, no build step, closed
markdown subset) makes hand-rolling the *correct* choice, not a shortcut.

## Common Pitfalls

### Pitfall 1: `innerHTML` regression via a "helper" utility function

**What goes wrong:** A future edit adds a convenience function like
`function setHtml(el, html) { el.innerHTML = html; }` and something upstream feeds it
markdown-converted HTML "just this once," silently reopening the XSS vector this phase
exists partly to guard against.
**Why it happens:** `innerHTML` is one keystroke away from `textContent` and often "just
works" in casual testing (test payloads without `<script>`/`onerror` render fine visually
either way).
**How to avoid:** Add a pytest-level static-source-scan test asserting the string
`innerHTML` does not appear anywhere in `static/webview.js` (or, if a legitimate future use
ever appears, that it's confined to an explicit allow-listed line with a code comment
justifying it). This is fully automatable without a browser/JS runtime.
**Warning signs:** Code review introduces `.innerHTML =` anywhere a variable (not a
literal string) is the right-hand side.

### Pitfall 2: `hatch` artifact glob is non-recursive — verify, don't assume

**What goes wrong:** `artifacts = ["src/lucy_ng/webview/static/*"]` is a flat glob. Since
`webview.js` sits directly in `static/` (not a subdirectory), it IS covered — confirmed by
reading `pyproject.toml` directly. But this is exactly the kind of assumption that silently
breaks if a later phase (94/95/96) adds a `static/css/` or `static/vendor/` subdirectory.
**Why it happens:** Non-recursive globs look correct in dev (files are read straight off
disk, not from the built wheel) and only fail once someone does `hatch build` + install
from wheel.
**How to avoid:** Extend the existing `TestPackaging.test_hatch_artifacts_include_static`
in `tests/test_webview_api.py` (already asserts the glob string is present) with a second
assertion that actually builds a wheel manifest (or, cheaper: asserts
`(static_dir / "webview.js").exists()` combined with the existing glob-string check) — the
existing test already validates the mechanism is a flat, single-level glob; this phase
should add nothing new to `pyproject.toml`, only confirm `webview.js` lands at the flat
level.
**Warning signs:** 404 on `/webview.js` in a `pip install lucy-ng[webview]` deployment that
does not reproduce when running from a source checkout (`hatch run` / editable install).

### Pitfall 3: Losing the D-13 scroll-preserve behaviour when switching from `textContent` to DOM nodes

**What goes wrong:** The current `refreshLog()` captures `atBottom` before the update and
restores `scrollTop` after, working because `logEl.textContent = content` is a single
atomic replace. Once `renderLog()` builds a tree of child nodes instead, it is easy to
introduce a rebuild strategy that resets scroll position on every 3-second tick (annoying
for a user reading history mid-run) or, conversely, one that never rescinds `scrollTop`
correctly at the boundary case (log freshly reaches bottom for the first time).
**Why it happens:** DOM-node rebuilds are more surface area than a single string
assignment; it's easy to move the `atBottom` capture to the wrong side of the
clear-and-rebuild step.
**How to avoid:** Keep the existing call-site contract from `index.html`'s `refreshLog()`
exactly as-is — capture `atBottom` BEFORE calling `renderLog()`, call
`renderLog(content, logEl)` (which internally clears via
`removeChild` loop, not `innerHTML = ''`, then appends new block nodes), then restore
`scrollTop` after, exactly mirroring the current code's before/after structure. Add a test
asserting scroll restoration behaviour is unchanged (can be tested at the JS-logic level
only if a JS test runtime is introduced — see "Validation Architecture" below for the
recommended lower-effort alternative).
**Warning signs:** Manual testing shows the log jumps to the top or bottom unexpectedly
every ~3 seconds while the user is scrolled mid-history.

### Pitfall 4: Table/heading false positives on stray characters in body text

**What goes wrong:** A `**Field:** value` line's value could theoretically contain a `#`
at line-start (unlikely but not impossible — e.g., a SMILES fragment beginning with an
isotope label) or a `|` character, causing the heading/table detector to misfire.
**Why it happens:** Line-based markdown detection is inherently pattern-based, not
semantic.
**How to avoid:** The block parser in "Code Examples" already requires a valid
`|---|---|`-style separator line immediately after a `|...|` line before committing to
table-mode (matches CommonMark's own pipe-table disambiguation rule), which eliminates the
most likely false-positive source. Headings are anchored to `^#{1,3}\s+` (require a space
after the hashes), which will not match inline `#` characters embedded mid-value.
**Warning signs:** A field value renders as a heading or gets swallowed into an unintended
table.

### Pitfall 5: `.js` served with the wrong MIME type

**What goes wrong:** `FileResponse` without an explicit `media_type` relies on
`mimetypes.guess_type()`, which is dependent on the host's system mimetypes database and
can return `None` (falling back to `application/octet-stream`) for `.js` on some minimal
Docker base images / Python builds. Browsers with strict MIME-sniffing (`X-Content-Type-
Options: nosniff`, which some deployments set globally) will refuse to execute a `<script
src="/webview.js">` served as `application/octet-stream`.
**Why it happens:** It "just works" in most local dev environments where the mimetypes DB
already knows `.js`, masking the issue until a different host environment is used.
**How to avoid:** Pass `media_type="application/javascript"` explicitly to `FileResponse`,
matching the project's own existing pattern of always passing `media_type` explicitly for
`index.html` (`text/html`).
**Warning signs:** Blank page / no dashboard behaviour in one deployment environment that
works fine in another; browser console shows a MIME-type-refused-to-execute error.

## Code Examples

Verified patterns synthesized from direct codebase inspection (no Context7/official-docs
lookup needed — this phase touches no third-party API surface beyond FastAPI's
`FileResponse`, which is already used identically elsewhere in this file):

### `app.py` — new `/webview.js` route (extends existing pattern)
```python
# Source: src/lucy_ng/webview/app.py — extends the existing `/` FileResponse route
from fastapi.responses import FileResponse  # noqa: PLC0415

_static_dir = Path(__file__).parent / "static"

@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(_static_dir / "index.html"), media_type="text/html")

@app.get("/webview.js")
def webview_js() -> FileResponse:
    return FileResponse(str(_static_dir / "webview.js"), media_type="application/javascript")
```

### `refreshLog()` call site — preserving D-13 scroll behaviour with the new renderer
```javascript
// Source: adapted from existing index.html refreshLog(), extended to call renderLog()
function refreshLog() {
  var logEl = document.getElementById('log-panel'); // now a <div>, was <pre>
  var atBottom = (logEl.scrollHeight - logEl.scrollTop) <= (logEl.clientHeight + 5);

  fetch(LOG_URL)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var content = data.content || '';
      if (!content) {
        while (logEl.firstChild) { logEl.removeChild(logEl.firstChild); }
        logEl.appendChild(document.createTextNode('Waiting for log data...'));
      } else {
        renderLog(content, logEl); // block parser from "Architecture Patterns" Pattern 3
      }
      if (atBottom) { logEl.scrollTop = logEl.scrollHeight; }
    })
    .catch(function (e) { console.warn('log fetch failed:', e); });
}
```

## State of the Art

| Old Approach (v9.2) | Current Approach (Phase 93) | When Changed | Impact |
|--------------------|------------------------------|---------------|--------|
| `<pre id="log-panel">` + `logEl.textContent = rawMarkdown` | `<div id="log-panel">` + `renderLog()` block/inline DOM builder | This phase | Log becomes visually structured (headings, bold labels, tables) while keeping the exact same XSS-safety guarantee (`textContent` at every leaf) |
| Inline `<script>` in `index.html` | `static/webview.js` served via explicit route | This phase | Enables independent packaging verification (success criterion 4) and general maintainability |
| Single always-visible two-column layout | Persistent left column (Structures) + tabbed right column (Log/1D/2D/Tables) — see Open Questions #1 for the recommended interpretation | This phase | Establishes the dock-in point Phases 94-96 populate |

**Deprecated/outdated:** None — this is the first phase touching the log rendering since
v9.2 shipped it as raw-text-only by explicit design (`D-12`, deferred with a "revisit if
the raw log proves hard to read" trigger that STATE.md records as now met).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The tab set for this phase is exactly the 4 panels named in ROADMAP.md's Phase 93 success criterion (Run Log / 1D Spectra / 2D Spectra / Tables), with the existing Structures grid remaining a persistent, non-tabbed left column rather than becoming a 5th tab. | Open Questions #1 | If wrong, the planner under-scopes the tab bar (misses a Structures tab) or the phase inadvertently moves/hides the structure grid that users currently rely on in v9.2, degrading an existing working feature. |
| A2 | No real `CASE-PROGRESS.md` from a completed run exists in this repo/data tree to inspect directly; the markdown subset used in this research is derived entirely from `.claude/commands/lucy-ng/references/progress-format.md` (the authoritative writer spec) plus the `conftest.py` test fixture snippet, both of which are first-party project sources, not external/training-data guesses. | Summary, Architecture Pattern 3 | If the coordinator's actual runtime output drifts from the documented spec (e.g., a field value that legitimately starts with `#` or contains a raw `|`), the block parser's heuristics (Pitfall 4) should still degrade gracefully to a paragraph rather than crash, but visual formatting could look wrong for that one line. |
| A3 | `FileResponse(..., media_type="application/javascript")` is accepted by browsers as a valid classic-script MIME type. This is standard/uncontroversial browser behavior, not a project-specific claim, but is not independently verified against a live browser in this research session. | Common Pitfalls #5, Code Examples | Extremely low risk — this is one of the two IANA-registered/commonly-accepted MIME types for JavaScript; if a stricter policy is ever encountered, `text/javascript` (the WHATWG-recommended modern alternative) is the fallback. |

## Open Questions (RESOLVED)

> Both questions were resolved during plan-phase and carried into the plans. See CONTEXT.md.

1. **Tab naming/scope discrepancy between REQUIREMENTS.md and ROADMAP.md.**
   **RESOLVED — see CONTEXT.md D-01 (user-confirmed 2026-07-07):** ROADMAP's 4-tab set is authoritative for this phase (Run Log / 1D Spectra / 2D Spectra / Tables); Overview + Structures stay as the persistent left column, not tabs.
   - What we know: `REQUIREMENTS.md` TAB-01 names 5 tabs — "Overview / Structures /
     Spectra / Tables / Log". `ROADMAP.md`'s Phase 93 success criterion #1 names 4 tabs —
     "Run Log / 1D Spectra / 2D Spectra / Tables" — and does not mention a
     Structures/Overview tab at all. The existing v9.2 layout has Structures as a
     permanently-visible left column, separate from the log panel.
   - What's unclear: Whether Structures should become a 5th tab in this phase, or whether
     it stays as the existing persistent left column while only the right-hand panel
     becomes tabbed (Log/1D-Spectra/2D-Spectra/Tables).
   - Recommendation: Treat ROADMAP.md's Phase 93 success criteria as authoritative for
     THIS phase (it is the more specific, phase-scoped instruction) and keep the Structures
     grid as the persistent left column, untouched by this phase's tab bar. This matches
     the existing two-column flex layout exactly (`#structure-panel` stays; `#log-panel-
     wrapper` becomes the tab dock) and requires zero changes to already-working v9.2
     structure-rendering code. Flag this interpretation explicitly for user confirmation
     during planning/discuss-phase, since REQUIREMENTS.md's milestone-level wording
     technically implies a 5th tab.

2. **Automated verification of the browser-rendered-escaping acceptance criterion (#3).**
   **RESOLVED — see CONTEXT.md D-04:** two-layer approach adopted — automatable pytest static-source-scan (no `innerHTML` of server content) + a manual `checkpoint:human-verify` task (plan 93-03). No Node/jsdom dependency introduced.
   - What we know: The project has no JS test runtime/browser-automation tool in its
     dependency stack (no `package.json`, no Playwright/Selenium/jsdom in `pyproject.toml`
     `dev` extras). `node` (v19.9.0) happens to be present on this development machine but
     is not a declared or required project tool.
   - What's unclear: How the planner should schedule an executable check for "renders as
     literal escaped text in the browser" — this is fundamentally a browser/DOM-execution
     behavior (`textContent` API contract), not something `pytest` alone can execute.
   - Recommendation: Use a two-layer verification strategy: (a) an automatable pytest
     static-source-scan asserting `"innerHTML"` never appears in `static/webview.js`
     (cheap, deterministic, catches the actual regression vector — see Pitfall 1), plus
     (b) a manual verification step (documented as a `checkpoint:human-verify` task) where
     a human injects the literal payload from the acceptance criterion into a mock
     `CASE-PROGRESS.md`, loads the dashboard in a real browser, and confirms no alert
     fires. Do not introduce Node/jsdom as a new project testing dependency for this one
     criterion — it would be disproportionate tooling for a single, easily-manually-
     verified behavior.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI | `/webview.js` route, all existing routers | ✗ (not installed in `.venv`) | `>=0.100` declared, not installed locally | `pip install -e ".[webview]"` before running webview-dependent tests; all webview tests already `pytest.skip()` gracefully when absent (verified: `pytest tests/test_webview_api.py` → 5 passed, 13 skipped) |
| uvicorn | Manual serving (`lucy webview serve`) for exploratory/manual verification of Pitfall/Open-Question #2 | ✗ (not installed in `.venv`) | `>=0.20` declared, not installed locally | Same as above |
| Node.js | Not required by this phase | ✓ (v19.9.0, incidental to this dev machine) | v19.9.0 | Not used — see Open Question #2; do not add as a project dependency |
| A real, non-synthetic `CASE-PROGRESS.md` from a completed run | Ground-truth validation of the markdown subset | ✗ (none found under this repo or its data tree — CASE run outputs live outside this repo per `CLAUDE.md` scope note) | — | Use `.claude/commands/lucy-ng/references/progress-format.md` (authoritative writer spec, first-party) plus the `conftest.py` `live_analysis_dir` fixture snippet as the ground truth for the parser subset (already done in this research) |

**Missing dependencies with no fallback:** None — all gaps above have a documented,
low-risk fallback.

**Missing dependencies with fallback:** FastAPI/uvicorn (install via `[webview]` extra
before running the full non-skipped test suite for this phase).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 `[VERIFIED: pytest --version in project .venv]`, config in `pyproject.toml` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["src"]` |
| Quick run command | `pytest tests/test_webview_api.py -q` |
| Full suite command | `pytest -q` (or `pytest --cov=lucy_ng` for coverage) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TAB-01 | `GET /webview.js` returns 200, `content-type` starts with `application/javascript` (or `text/javascript`) | integration (FastAPI `TestClient`) | `pytest tests/test_webview_api.py::TestFrontend -x` (extend with a new `test_webview_js_served` case) | ❌ Wave 0 — new test class needed |
| TAB-01 | `pyproject.toml` hatch artifacts glob still covers `webview.js` (regression guard for Pitfall 2) | unit | `pytest tests/test_webview_api.py::TestPackaging -x` (existing test already covers the glob string; extend to also assert `(static_dir / "webview.js").exists()` once the file is created) | ✅ (existing test), extend for the new file |
| LOG-01 | `GET /api/log` still returns raw, unmodified markdown text (server-side behavior must NOT change — rendering is 100% client-side per `D-12`) | integration | `pytest tests/test_webview_api.py::TestLogEndpoint -x` (existing, unchanged) | ✅ existing |
| LOG-01 | `static/webview.js` never contains the literal substring `innerHTML` (automated regression guard for the XSS discipline — see Pitfall 1 / Open Question #2) | static source scan | New test: `pytest tests/test_webview_api.py::TestMarkdownRendererSafety -x` | ❌ Wave 0 — new test needed |
| LOG-01 (acceptance criterion #3 — literal-escape rendering in a real browser) | manual-only | n/a — DOM-execution behavior cannot be asserted from pytest without a browser/jsdom runtime not present in this project's stack | manual `checkpoint:human-verify` | ❌ Wave 0 — document as a manual verification step, not an automated test |

### Sampling Rate
- **Per task commit:** `pytest tests/test_webview_api.py -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`; plus the one documented
  manual browser-verification checkpoint for the XSS acceptance criterion.

### Wave 0 Gaps
- [ ] `tests/test_webview_api.py::TestFrontend::test_webview_js_served` — covers TAB-01
  (route existence + content-type)
- [ ] `tests/test_webview_api.py::TestPackaging` — extend existing test to also assert
  `webview.js` exists on disk at the flat `static/` level (covers TAB-01 packaging
  regression guard)
- [ ] `tests/test_webview_api.py::TestMarkdownRendererSafety::test_no_innerhtml_in_source`
  — static string-scan of `static/webview.js` (covers LOG-01 XSS-discipline regression
  guard)
- [ ] A documented manual verification checklist item (not a pytest test) for the literal
  browser-rendered-escaping acceptance criterion — recommend the planner add this as an
  explicit `checkpoint:human-verify` task at the end of the phase's plan, not skip it
  silently.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Dashboard is loopback-only, read-only, no auth surface (unchanged from v9.2) |
| V3 Session Management | No | No sessions/cookies introduced |
| V4 Access Control | No | No access-control surface change |
| V5 Input Validation / Output Encoding | Yes | Client-side output encoding via `textContent`/`createElement` exclusively (this phase's core security control); no server-side input validation change (log content already passes through unmodified, as in v9.2) |
| V6 Cryptography | No | Not applicable to this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Stored/reflected XSS via run-derived content (SMILES/CXSMILES strings, agent-reported free text) rendered into the DOM | Tampering / Elevation of Privilege (in a browser context) | `textContent`/`createElement` exclusively for all server-derived strings; never `innerHTML`, never template-string HTML concatenation, never a regex-based markdown-to-HTML-string converter (see "Common Pitfalls" #1 and "Architecture Patterns" Anti-Patterns) |
| MIME-type confusion serving `.js` as `application/octet-stream`, causing silent script-execution failure (an availability issue, not directly a security one, but worth flagging alongside the route addition) | Denial of Service (soft) | Explicit `media_type="application/javascript"` on the new `FileResponse` route (see Pitfall 5) |

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `src/lucy_ng/webview/app.py`, `routers/log.py`,
  `routers/status.py`, `state.py`, `static/index.html` — v9.2 architecture, existing
  `FileResponse` pattern, existing polling/scroll-preserve/XSS-guard code, all confirmed
  by reading the actual files in this session.
- Direct codebase inspection: `tests/test_webview_api.py` — confirmed existing test
  conventions (import-inside-function-body per WV-08, `pytest.skip()` on missing extra,
  `TestPackaging` hatch-artifact assertion pattern). Ran `pytest tests/test_webview_api.py
  -q` in this session: 5 passed, 13 skipped (fastapi/uvicorn absent in local `.venv`,
  confirming graceful degradation works as documented).
- Direct codebase inspection: `.claude/commands/lucy-ng/references/progress-format.md` —
  the authoritative, first-party specification of exactly what markdown constructs the
  coordinator writes into `CASE-PROGRESS.md` (headings, `**Field:** value` bold-label
  lines, bullet lists, `---` separators, one pipe table in `## Timing Summary`). This is
  the ground truth for the markdown subset, not a training-data guess.
- Direct codebase inspection: `tests/conftest.py` `live_analysis_dir` fixture — confirms
  the actual minimal `CASE-PROGRESS.md` content used in existing tests
  (`## Iteration 1: ...` / `### LSD-Engineer`).
- Direct codebase inspection: `pyproject.toml` — confirmed `[project.optional-
  dependencies].webview` (fastapi + uvicorn only, no matplotlib needed for this phase),
  and `[tool.hatch.build.targets.wheel].artifacts` (flat, non-recursive glob covering
  `static/*`).
- `.planning/research/SUMMARY.md` (existing v9.3 milestone-level research, HIGH
  confidence, produced 2026-07-07) — cross-checked against direct codebase inspection in
  this session; all claims relevant to Phase 93 confirmed consistent.
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` — locked
  scope, requirements, and design decisions for v9.3 and Phase 93 specifically.

### Secondary (MEDIUM confidence)
- General browser behavior: `element.textContent = <string>` never parses its argument as
  markup (this is a foundational, stable DOM API guarantee, not a fast-moving area) —
  used as the basis for the XSS-safety claim throughout this document.
- `FileResponse` / MIME-type-for-`.js` behavior — standard FastAPI/Starlette behavior
  (`FileResponse` uses `mimetypes.guess_type()` unless `media_type` is passed explicitly);
  not independently re-verified against Starlette's current source in this session, but
  consistent with the project's own existing explicit-`media_type` pattern for
  `index.html`.

### Tertiary (LOW confidence)
- None used for this phase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing patterns directly inspected
- Architecture: HIGH — all patterns derived from direct inspection of the actual v9.2
  codebase, not assumed
- Pitfalls: HIGH — every pitfall traces to either a concrete codebase artifact (the
  hatch glob, the D-13 scroll-preserve code, the existing MIME pattern) or a documented
  locked decision (D-12 XSS discipline)
- Tab-naming discrepancy (Open Question #1): MEDIUM — real ambiguity between two project
  documents, flagged rather than silently resolved
- Automated-verification gap for the browser-escaping criterion (Open Question #2): HIGH
  confidence that the gap exists (no JS runtime in the stack), MEDIUM confidence in the
  specific two-layer mitigation recommended

**Research date:** 2026-07-07
**Valid until:** No external expiry — this phase depends on zero external
packages/services whose behavior could drift; re-research only if the phase scope changes
materially (e.g., if REQUIREMENTS.md's 5-tab wording is adopted over ROADMAP.md's 4-tab
wording, revisit Open Question #1's structural recommendation).
