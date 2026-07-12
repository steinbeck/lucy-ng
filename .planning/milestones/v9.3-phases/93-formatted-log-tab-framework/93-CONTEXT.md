# Phase 93: Formatted Log + Tab Framework - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning
**Source:** plan-phase --chain (no discuss-phase; decisions below resolved during planning)

<domain>
## Phase Boundary

Pure-frontend enhancement to the existing v9.2 webview dashboard. Adds (1) a persistent tab bar over the right panel and (2) a hand-rolled markdown renderer for the run log. Ships first in v9.3 because it establishes the tab dock-in that Phases 94–96 populate; carries zero backend risk. The only server-side change is extracting `static/webview.js` from `index.html` and serving it via an explicit `/webview.js` route.

</domain>

<decisions>
## Implementation Decisions

### D-01 Tab layout (RESOLVED — resolves REQUIREMENTS-vs-ROADMAP conflict)
Tabbed **right panel** with exactly four tabs, in order: **Run Log / 1D Spectra / 2D Spectra / Tables**. The 1D and 2D spectra tabs are split (not a single combined "Spectra" tab) to match the downstream phase boundaries — Phase 95 populates 1D, Phase 96 populates 2D. The existing v9.2 **Overview** and **Structures** widgets remain a **persistent always-visible left column** (they are NOT tabs). This resolves the conflict between REQUIREMENTS.md TAB-01 (which listed 5 tabs incl. Overview/Structures and a single Spectra) and ROADMAP.md Phase 93 (4 tabs); ROADMAP wins as the authoritative phase-scope source, confirmed by the user.
- In Phase 93, the 1D Spectra / 2D Spectra / Tables tabs are docked-in **placeholders** ("coming in Phase 9x" / empty panel). Only Run Log is populated with real content this phase.
- Clicking a tab shows that panel and hides the others with no page reload. TAB-01's "existing v9.2 widgets remain reachable" is satisfied by the persistent left column.

### D-02 Markdown renderer (LOCKED from v9.3 roadmap)
Hand-rolled DOM renderer: `createElement` + `textContent` / `createTextNode` throughout. **Never** `innerHTML` of server content. Covers exactly this CASE-PROGRESS.md subset: `#`/`##`/`###` headings, `**bold**` (incl. `**Field:** value` labels), `` `code` ``, pipe-tables, code fences, `---` horizontal rules, bullet lists. No CDN, no bundled JS library, no build toolchain. The XSS discipline is satisfied by construction — the `# <img src=x onerror=alert(1)>` payload must render as literal escaped text.

### D-03 JS extraction + route (LOCKED from roadmap success criteria)
Extract `static/webview.js` from `index.html`; serve via an explicit `GET /webview.js` route in `app.py` (mirror the existing `GET /` FileResponse route). Must be present in the installed wheel — the existing `src/lucy_ng/webview/static/*` hatch artifact glob covers it; verify the glob includes `.js`.

### D-04 Test approach (from RESEARCH — no JS runtime exists)
Two-layer verification: (a) automatable pytest static-source-scan asserting `webview.js` has no `innerHTML` assignment of server content + a `/webview.js` route smoke test, and (b) a manual `checkpoint:human-verify` task for the browser-rendered-escaping and tab-switching behaviors. All fastapi/webview imports in test files go INSIDE test function bodies (WV-08 collect-safety).

### Claude's Discretion
- Exact CSS for tab bar styling, active-tab indicator, and left-column/right-panel split (respect existing v9.2 visual language — no new design system).
- Internal structure of the markdown parser (block parser + inline tokenizer), function names, and file organization within `webview.js`.
- Placeholder copy for the not-yet-populated tabs.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing webview implementation (the base to extend — do NOT redesign)
- `src/lucy_ng/webview/app.py` — FastAPI app, existing routes incl. `GET /` FileResponse; add `/webview.js` here
- `src/lucy_ng/webview/static/index.html` — current dashboard; extract inline JS to `webview.js`, add tab bar
- `src/lucy_ng/webview/` routers + `.webview.json` state model — how CASE-PROGRESS.md is currently read and polled (~3 s)
- `tests/test_webview_api.py` — WV-08 import-safety pattern (imports inside test bodies; skips when fastapi absent)

### Specs
- `.claude/commands/lucy-ng/references/progress-format.md` — authoritative spec of the markdown subset the CASE coordinator writes to CASE-PROGRESS.md
- `.planning/phases/93-formatted-log-tab-framework/93-RESEARCH.md` — full research incl. verified renderer code pattern and pitfalls

</canonical_refs>

<specifics>
## Specific Ideas

- Tab order is fixed: Run Log, 1D Spectra, 2D Spectra, Tables.
- Run Log is the default active tab on load.
- Packaging check: `hatch build` wheel must contain `webview/static/webview.js`.

</specifics>

<deferred>
## Deferred Ideas

- 1D/2D Spectra tab content → Phases 95/96. Tables tab content → Phase 94. This phase only docks in the empty tabs.
- DEPT sub-tab, interactive zoom/pan, SSE live push → deferred to v9.4 per STATE.md.

</deferred>

---

*Phase: 93-formatted-log-tab-framework*
*Context resolved: 2026-07-07 during plan-phase --chain*
