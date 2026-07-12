# Phase 95: 1D Real Spectra + Peak Overlay - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Populate the **1D Spectra** tab (2nd tab of the webview right panel, docked-in as a
placeholder in Phase 93) with a **real 1D spectrum trace rendered from the raw Bruker
processed data** and the picked peaks overlaid — so a chemist can visually validate
peak-picking quality against the actual signal.

New `spectra.py` router (mirrors the Phase 94 `tables.py` "dumb server" pattern but
reaches beyond `analysis/`): it reads `analysis/.run_manifest.json` to locate the raw
Bruker dataset, uses `BrukerReader.read_1d` (nmrglue-backed, already a base dep) to get
the continuous trace + ppm scale, renders a **matplotlib (Agg) PNG** with a **reversed
ppm axis**, overlays the picked peaks from `analysis/peaks/carbon_signals.json`, and
serves it as an image endpoint. `matplotlib` is added to the `[webview]` extra; all
matplotlib imports are **lazy inside `make_router()`** (WV-08). Degrades to a
well-formed "unavailable / waiting for data" state (HTTP 200, never 500) whenever the
manifest, the raw data, or the peak JSON is missing/unlocatable.

**Also in scope (cross-cutting, established here, inherited by Phase 96):**
- `case.md` writes `analysis/.run_manifest.json` at run-start (`{"bruker_data_dir": "<abs>",
  "formula": "<formula>"}`) — the path-wiring that makes raw-data access possible.
- The matplotlib-Agg render pipeline + the `[webview]` matplotlib extra + lazy-import
  discipline.

**Not in scope:** 2D contour spectra (Phase 96), any peak *editing*, interactive
zoom/pan (v9.4), a JS charting library (violates the no-build/no-CDN constraint),
render caching (Phase 96 introduces the mtime cache; 1D render is cheap and stays
uncached here — see D-06).

</domain>

<decisions>
## Implementation Decisions

### No-manifest / degradation behaviour
- **D-01 (Strict "unavailable" — no stick fallback):** When `.run_manifest.json` is
  absent (e.g. manual `lucy webview serve <analysis_dir>`, pre-v9.3 run), the 1D Spectra
  tab shows the well-formed "unavailable / waiting for data" state — HTTP 200, never 500.
  **Do NOT** synthesise a stick spectrum from `carbon_signals.json` as a fallback: it
  would be circular (replotting the peaks that came from that JSON) and carries no
  validation value against the real signal, which is the entire point of the phase.
  Locked by SP-02 + ROADMAP SC4.
- **D-05 (Stale/unlocatable raw path → "unavailable"):** When the manifest exists but
  `bruker_data_dir` is missing, moved, or not a readable Bruker experiment tree, treat it
  exactly like an absent manifest → "unavailable". SP-02 explicitly covers "the raw
  experiment data cannot be located". The router must never 500 on a bad path.

### Experiment selection & ¹H scope
- **D-02 (Auto-detect by nucleus; ¹³C always + ¹H when present):** `bruker_data_dir` is a
  Bruker **dataset root** containing numbered experiment sub-directories (10/, 11/, …),
  each with `acqus`. The router scans them, reads the nucleus (`acqus $NUC1`, e.g. `13C`
  / `1H`), renders the **¹³C 1D always**, and renders a **¹H 1D only when a ¹H experiment
  is found** (SP1-01 "¹H if present"). No hard-coded experiment numbers. If multiple
  candidate experiments share a nucleus, selection heuristic (e.g. lowest experiment
  number, or the one whose ppm range best matches the peaks) is Claude's discretion —
  document whatever is chosen.

### Peak overlay visual style
- **D-03 (Vertical markers + ppm labels, assignment when available):** Overlay each
  picked peak from `carbon_signals.json` as a thin **vertical marker/tick at its ppm** on
  the line trace, labelled with its **ppm value**; add the **assignment** label (e.g.
  `C=O`, `ArCH₃`) when the signal carries one. Subtle colour that respects the existing
  v9.2/9.3 visual language. The trace is a continuous **line plot** with the ppm axis
  **reversed** (high ppm on the left) — `ax.get_xlim()[0] > ax.get_xlim()[1]` must hold.
  Reversed-axis handling goes through a **shared `_apply_nmr_axes()` helper** (locked
  v9.3-roadmap decision, STATE.md) so Phase 96's 2D axes reuse it and no axis is left
  un-reversed by omission.

### Packaging & rendering
- **D-04 (matplotlib `>=3.7` in `[webview]` extra, OO-API only, lazy imports, PNG image
  endpoint):** Add `matplotlib>=3.7` to the `[webview]` optional-dependency extra only
  (NOT base). Use the **matplotlib object-oriented API exclusively — `Figure` +
  `FigureCanvasAgg`; NEVER `matplotlib.pyplot`** in any webview module (locked v9.3-roadmap
  decision, STATE.md — pyplot's global state is unsafe under the threaded FastAPI server).
  Every matplotlib import is lazy, inside `make_router()` / the request handler — never at
  module top or in `webview/__init__`/`server`/`state` (WV-08). `from lucy_ng.cli import
  cli` on a base install (no `[webview]`) must not raise ImportError. Served as a **PNG
  image endpoint** (forced by the no-build/no-CDN constraint — no client-side charting).
  Close figures after each render (`try/finally`) to avoid Figure leaks. Route handlers may
  be sync `def` (FastAPI dispatches them to a threadpool, so the CPU-bound render never
  blocks the event loop).
- **D-06 (No render caching in Phase 95):** 1D rendering is cheap; do not build a cache
  here. Phase 96 introduces the mtime-keyed PNG cache for the expensive 2D contours; if
  the planner wants a trivial 1D cache it is discretionary, but the phase does not require
  it and the ~3 s poll re-rendering a cheap 1D PNG is acceptable.

### Manifest trust
- **D-07 (Trust the manifest's absolute path — localhost single-user tool):** The
  absolute `bruker_data_dir` comes from `analysis/.run_manifest.json`, written by the
  trusted local `case.md` process. Reading it directly is acceptable for this
  single-user localhost dev tool; no path whitelist/sandboxing beyond "if it is not a
  readable Bruker experiment tree, show unavailable" (D-05). Consistent with the existing
  routers' threat model.

### Claude's Discretion
- Exact endpoint shape (e.g. `/api/spectra/1d/carbon` + `/api/spectra/1d/proton` PNG
  routes vs one route with a `?nucleus=` param) — but per-nucleus "unavailable" must be
  independently expressible.
- Multi-candidate experiment tiebreak heuristic (D-02).
- matplotlib figure sizing/DPI, marker/label typography, exact colours — respect the
  v9.2/9.3 look; introduce no new design system.
- Whether the ¹H panel is a separate `<img>` below the ¹³C one or a stacked figure.
- Internal helper/function names and module organisation within `spectra.py`.

### Reviewed Todos (not folded — off-topic for this phase)
- `hosegen-dependent ranking tests hard-fail instead of skipif` (tests) — unrelated to
  the webview; belongs to the v9.1 test-infra backlog.
- `CASE4 chamazulene regiochemistry enumeration gap` (skill) — CASE solver concern,
  nothing to do with 1D spectra rendering.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing webview implementation (the base to extend — do NOT redesign)
- `src/lucy_ng/webview/app.py` — `create_app()`; dock the new router via
  `app.include_router(_spectra.make_router(analysis_dir))` with the existing lazy-import
  pattern (see the Phase 94 `_tables` docking at ~line 57-62)
- `src/lucy_ng/webview/routers/tables.py` — the Phase 94 router to mirror:
  `make_router(analysis_dir)` + `APIRouter(prefix="/api")` + `{"state":"ok"|"waiting"}`
  never-500 degradation; also its multi-file defensive reading
- `src/lucy_ng/webview/routers/log.py` — the minimal canonical `make_router` template
- `src/lucy_ng/webview/static/webview.js` — existing frontend; the ~3 s `tick()` poll +
  independent `fetch→render→catch` per-panel pattern; the 1D Spectra tab render target
- `src/lucy_ng/webview/static/index.html` — the **1D Spectra tab placeholder** to populate;
  inline `<style>` token block (reuse; no new design system)
- `tests/test_webview_api.py` — WV-08 import-safety pattern (fastapi/webview imports inside
  test bodies; `try/except ImportError: pytest.skip`); the Phase 94 `TestTablesEndpoint`
  fixture style to mirror for a `TestSpectraEndpoint`

### Raw Bruker data access
- `src/lucy_ng/readers/bruker.py` — `BrukerReader.read_1d(experiment_dir) -> Spectrum1D`;
  reads `pdata/1/`, uses `nmrglue` (`ng.bruker.read_pdata`, `guess_udic`, `uc.ppm_scale()`)
  to produce the trace + `ppm_scale`. Also `acqus` reading for nucleus detection ($NUC1)
- `src/lucy_ng/models/` — the `Spectrum1D` model (fields: processed `data`, `ppm_scale`,
  parameters/nucleus) returned by `read_1d`
- Local Bruker test datasets: `data/` (repo) and
  `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/` (CASE1 = ibuprofen, for
  the SC2 carbonyl-at-181ppm axis-direction check)

### Path wiring (NEW this phase)
- `.planning/STATE.md` §"[v9.3-roadmap] Bruker-path wiring" — the `.run_manifest.json`
  contract: `case.md` writes `{"bruker_data_dir": "<abs>", "formula": "<formula>"}` into
  `analysis/.run_manifest.json` at run-start; absent → graceful "unavailable"
- `.claude/commands/lucy-ng/case.md` — the CASE orchestrator; **MODIFIED this phase** to
  write `analysis/.run_manifest.json` at run-start (one added write; no CLI signature or
  `.webview.json` model change)

### Packaging
- `pyproject.toml` — `[project.optional-dependencies].webview` (ADD `matplotlib` here);
  `nmrglue`/`numpy` are already base deps (confirmed); `[tool.pytest.ini_options]`

### Prior-phase decisions carried forward
- `.planning/phases/93-formatted-log-tab-framework/93-CONTEXT.md` — D-01 (4-tab right
  panel; 1D Spectra is tab 2; Overview/Structures persistent left column), D-02 (XSS
  discipline), D-04 (two-layer test: pytest static/integration + manual browser checkpoint)
- `.planning/phases/94-data-tables/94-CONTEXT.md` + `94-PATTERNS.md` — the `analysis/`
  router + hand-authored-fixture + `TestTablesEndpoint` patterns to reuse
- `.planning/ROADMAP.md` §"Phase 95" — goal, SC1–SC4, requirements
- `.planning/REQUIREMENTS.md` — SP1-01 (real 1D ¹³C+¹H line plot, reversed axis, peak
  overlay markers/labels), SP-02 (graceful "unavailable" when spectrum/peak/raw data
  missing or unlocatable)

### Conventions
- `CLAUDE.md` (repo) — dev commands (pytest, `mypy src/lucy_ng` strict, `ruff check src tests`)
- WV-08 (from Phase 91, see STATE.md) — fastapi/webview/heavy imports inside function/test
  bodies only

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BrukerReader.read_1d(experiment_dir)` → `Spectrum1D` (trace `data` + `ppm_scale`) — the
  raw-data reader; nmrglue already handles pdata + ppm-scale generation.
- Phase 94 `routers/tables.py` — the never-500 `make_router(analysis_dir)` shape + the
  hand-authored-fixture test class to copy for `spectra.py` / `TestSpectraEndpoint`.
- `carbon_signals.json` schema (from Phase 94 CONTEXT) — `signals[]` with `ppm`, `mult`,
  `nC`, `assignment`, `confidence`: the peak positions/labels to overlay.

### Established Patterns
- One router module per data area; `make_router(analysis_dir) -> APIRouter(prefix="/api")`;
  frontend `fetch→render→catch` on the shared ~3 s poll; each panel renders independently.
- WV-08 lazy imports; "dumb server reads files, degrades to waiting, never 500".

### Integration Points
- New `src/lucy_ng/webview/routers/spectra.py`; one `include_router` line in `app.py`.
- New frontend render (an `<img>` fed by a PNG endpoint) + URL in `webview.js`, targeting
  the 1D Spectra tab container in `index.html`.
- New `pyproject.toml` `[webview]` matplotlib dependency.
- `.claude/commands/lucy-ng/case.md` — add the run-start `.run_manifest.json` write.
- New `tests/test_webview_api.py::TestSpectraEndpoint` (WV-08 import-safety; skips when
  matplotlib/fastapi absent).

</code_context>

<specifics>
## Specific Ideas

- Real **continuous line trace** from raw Bruker processed data — NOT a stick plot from
  peak JSON (supersedes the pre-roadmap `research/SUMMARY.md` stick-spectra sketch).
- **Reversed ppm axis** is a hard requirement; the CASE1/ibuprofen carbonyl (~181 ppm) on
  the far left is the concrete axis-direction test (`ax.get_xlim()[0] > ax.get_xlim()[1]`).
- Peaks overlaid as **vertical markers + ppm labels** (+ assignment when present).
- **matplotlib only in `[webview]` extra, lazy-imported**; base `lucy` install must import
  without it.
- `.run_manifest.json` is the sole raw-data path source; absent/stale → "unavailable".

</specifics>

<deferred>
## Deferred Ideas

- **Render caching for 1D** — deferred to Phase 96's mtime-keyed PNG cache pattern (1D is
  cheap; uncached here per D-06).
- **2D contour spectra (HSQC/HMBC/COSY)** → Phase 96 (already scoped).
- **Interactive zoom/pan, DEPT sub-tab, SSE live push** → v9.4 per STATE.md.
- **Stick-spectrum fallback from peak JSON when raw data absent** — considered and
  rejected (D-01, no validation value); not revisited.

None of the above expand Phase 95 scope — captured so they are not lost.

</deferred>

---

*Phase: 95-1d-real-spectra-peak-overlay*
*Context gathered: 2026-07-09*
