# Phase 95: 1D Real Spectra + Peak Overlay - Research

**Researched:** 2026-07-09
**Domain:** FastAPI webview extension — Bruker/nmrglue raw-data reading + matplotlib-Agg PNG rendering
**Confidence:** HIGH

## Summary

This phase is a narrow, well-bounded extension of the existing Phase 94 `tables.py` router
pattern. All the load-bearing pieces already exist in the codebase and were read/executed
directly during this research session: `BrukerReader.read_1d()` (confirmed working, executed
against the real CASE1/ibuprofen dataset), the `make_router(analysis_dir) -> APIRouter(prefix="/api")`
+ never-500 idiom (`tables.py`, `log.py`), the lazy-import docking pattern in `app.py`, and the
`carbon_signals.json` schema (confirmed against the Phase 94 hand-authored test fixture — no
on-disk analysis/ currently exists with real Phase-95-shaped data, same caveat already recorded
in STATE.md for Phase 94).

Two verified findings materially sharpen the plan beyond what CONTEXT.md assumed:

1. **`Spectrum1D.ppm_scale` from nmrglue is ALREADY in descending order** (high ppm first,
   confirmed by executing `read_1d` against `CASE1/2`: `ppm_scale[0]=231.29`,
   `ppm_scale[-1]=-12.00`). The "reversed axis" requirement is satisfied by
   `ax.set_xlim(ppm_scale[0], ppm_scale[-1])` alone — **no `ax.invert_xaxis()` call and no
   manual array reversal is needed or wanted.** Calling `invert_xaxis()` on an axis whose xlim
   was set from an already-descending scale would silently re-reverse it back to ascending —
   a real footgun for the planner to avoid.
2. **A naive "scan acqus $NUC1" experiment-selection strategy is unsafe** — it will silently
   misclassify both 2D experiments and DEPT-edited 1D experiments as candidates unless two
   additional, verified discriminators are applied (see Common Pitfalls #1 and #2). Both were
   confirmed by inspecting real acqus files across CASE1 and CASE6.

**Primary recommendation:** Mirror `tables.py`'s `make_router(analysis_dir)` shape exactly; add
`spectra.py` with one `_read_manifest()` helper, one `_select_experiment(bruker_data_dir, nucleus)`
helper (filters out 2D dirs via `acqu2s` presence and DEPT pulse programs via `metadata.pulse_program`,
then picks lowest experiment number), one `_render_1d_png(spectrum, peaks)` helper (matplotlib OO
API, `Figure`+`FigureCanvasAgg`, `_apply_nmr_axes()` shared helper), and PNG routes that **always
return valid PNG bytes, HTTP 200** — a real chart when data is available, or a lightweight
"unavailable / waiting for data" placeholder chart when not — exactly mirroring the
`structures.py` SVG-endpoint precedent (`placeholder_svg()` on failure, never a JSON-vs-binary
content-type mismatch).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Raw Bruker FID/processed-data reading | API/Backend (`BrukerReader`, already exists) | — | nmrglue is a server-side-only dependency; no client access to raw binary Bruker files |
| Experiment (nucleus/dimensionality) selection | API/Backend (new `spectra.py`) | — | Requires filesystem + acqus parsing; not exposable to browser |
| Matplotlib rendering (Figure → PNG bytes) | API/Backend (new `spectra.py`, lazy import) | — | CPU-bound; must stay off the event loop (sync `def`, threadpool) per D-04 |
| Peak overlay (position/label placement) | API/Backend (same render function) | — | Peaks are read from `analysis/peaks/carbon_signals.json` server-side; overlay drawn into the same Figure before PNG encode |
| PNG delivery to browser | API/Backend → Browser | — | `Response(content=png_bytes, media_type="image/png")`; browser just paints an `<img>` |
| ~3s poll / cache-busted re-fetch | Browser (vanilla JS, `webview.js`) | — | Existing `tick()` polling loop; no server push (SSE explicitly deferred to v9.4) |
| `.run_manifest.json` write | API/Backend (CASE orchestrator, `case.md`, Bash) | — | Trusted local process; not a network-facing write |

## User Constraints (from CONTEXT.md)

### Locked Decisions

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
- **D-02 (Auto-detect by nucleus; ¹³C always + ¹H when present):** `bruker_data_dir` is a
  Bruker **dataset root** containing numbered experiment sub-directories (10/, 11/, …),
  each with `acqus`. The router scans them, reads the nucleus (`acqus $NUC1`, e.g. `13C`
  / `1H`), renders the **¹³C 1D always**, and renders a **¹H 1D only when a ¹H experiment
  is found** (SP1-01 "¹H if present"). No hard-coded experiment numbers. If multiple
  candidate experiments share a nucleus, selection heuristic (e.g. lowest experiment
  number, or the one whose ppm range best matches the peaks) is Claude's discretion —
  document whatever is chosen.
- **D-03 (Vertical markers + ppm labels, assignment when available):** Overlay each
  picked peak from `carbon_signals.json` as a thin **vertical marker/tick at its ppm** on
  the line trace, labelled with its **ppm value**; add the **assignment** label (e.g.
  `C=O`, `ArCH₃`) when the signal carries one. Subtle colour that respects the existing
  v9.2/9.3 visual language. The trace is a continuous **line plot** with the ppm axis
  **reversed** (high ppm on the left) — `ax.get_xlim()[0] > ax.get_xlim()[1]` must hold.
  Reversed-axis handling goes through a **shared `_apply_nmr_axes()` helper** (locked
  v9.3-roadmap decision, STATE.md) so Phase 96's 2D axes reuse it and no axis is left
  un-reversed by omission.
- **D-04 (matplotlib `>=3.7` in `[webview]` extra, OO-API only, lazy imports, PNG image
  endpoint):** Add `matplotlib>=3.7` to the `[webview]` optional-dependency extra only
  (NOT base). Use the **matplotlib object-oriented API exclusively — `Figure` +
  `FigureCanvasAgg`; NEVER `matplotlib.pyplot`** in any webview module. Every matplotlib
  import is lazy, inside `make_router()` / the request handler — never at module top or in
  `webview/__init__`/`server`/`state` (WV-08). `from lucy_ng.cli import cli` on a base
  install (no `[webview]`) must not raise ImportError. Served as a **PNG image endpoint**
  (forced by the no-build/no-CDN constraint). Close figures after each render (`try/finally`)
  to avoid Figure leaks. Route handlers may be sync `def` (FastAPI dispatches them to a
  threadpool, so the CPU-bound render never blocks the event loop).
- **D-06 (No render caching in Phase 95):** 1D rendering is cheap; do not build a cache
  here. Phase 96 introduces the mtime-keyed PNG cache for the expensive 2D contours; if
  the planner wants a trivial 1D cache it is discretionary, but the phase does not require
  it and the ~3 s poll re-rendering a cheap 1D PNG is acceptable.
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

### Deferred Ideas (OUT OF SCOPE)

- **Render caching for 1D** — deferred to Phase 96's mtime-keyed PNG cache pattern (1D is
  cheap; uncached here per D-06).
- **2D contour spectra (HSQC/HMBC/COSY)** → Phase 96 (already scoped).
- **Interactive zoom/pan, DEPT sub-tab, SSE live push** → v9.4 per STATE.md.
- **Stick-spectrum fallback from peak JSON when raw data absent** — considered and
  rejected (D-01, no validation value); not revisited.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SP1-01 | User sees the real 1D spectrum (¹³C, plus ¹H if present) rendered as a line plot with a reversed ppm axis, with the picked peaks overlaid | Verified `BrukerReader.read_1d` execution against CASE1 confirms `data`/`ppm_scale`/`nucleus`/`metadata.pulse_program` fields exist and that `ppm_scale` is already descending; verified `carbon_signals.json` schema (`signals[].ppm/mult/nC/assignment/confidence`) from Phase 94 fixture; verified matplotlib OO-API PNG render recipe executes correctly with the installed matplotlib 3.10.7 |
| SP-02 | When a spectrum/peak data is missing, partial, or raw data cannot be located, tab shows "unavailable/waiting" (HTTP 200, never 500) | Verified `tables.py`/`structures.py` never-500 idiom (broad except tuples, `{"state": "waiting", ...}` and `placeholder_svg()` patterns) to mirror for the PNG endpoint |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| matplotlib | >=3.7 (installed: 3.10.7; PyPI latest: 3.11.0) | Agg-backend PNG rendering of the 1D trace + peak overlay | Locked user decision (D-04); the de facto standard Python plotting library, already listed in CONTEXT.md canonical_refs; `Figure`+`FigureCanvasAgg` OO-API confirmed executable in this environment (produced a valid 14 KB PNG, reversed-xlim assertion passed) `[VERIFIED: PyPI + local execution]` |
| nmrglue | already a base dep (`git+https://github.com/jjhelmus/nmrglue.git`, tracks master; installed 2.2.1) | Bruker pdata reading + ppm-scale generation, wrapped by `BrukerReader` | Already in use by `BrukerReader.read_1d`/`read_2d`; no new dependency work needed `[VERIFIED: pyproject.toml + executed import]` |
| numpy | already a base dep (>=1.24; installed via nmrglue's numpy 2.2.1) | Array backing for `Spectrum1D.data`/`ppm_scale` | Already in use `[VERIFIED: pyproject.toml]` |
| fastapi | already a `[webview]` dep (>=0.100) | `APIRouter`, `Response` | Already in use by every existing router `[VERIFIED: pyproject.toml]` |

### Supporting

None — no new supporting libraries needed. Peak overlay data comes from an existing JSON file
(`carbon_signals.json`), read with the stdlib `json` module exactly as `tables.py` does.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Figure`+`FigureCanvasAgg` | `matplotlib.pyplot` | Rejected by locked decision D-04 — pyplot's global figure-stack state is unsafe under FastAPI's threaded/threadpool request dispatch (concurrent requests could interleave writes to the same global current-figure) |
| PNG (`canvas.print_png`) | SVG (matplotlib's `FigureCanvasSVG`) | SVG would be more consistent with the existing RDKit `structures.py` SVG endpoint and produces crisper vector text, but CONTEXT.md D-04 explicitly locks "PNG image endpoint" — not revisited here |
| Server-rendered PNG | Client-side charting (Plotly.js/D3/Chart.js via CDN) | Explicitly rejected by REQUIREMENTS.md "Out of Scope" (no build tooling, no CDN) |

**Installation:**
```bash
# Add to pyproject.toml [project.optional-dependencies].webview only:
# matplotlib>=3.7
pip install "lucy-ng[webview]"
```

**Version verification:** `pip index versions matplotlib` → latest 3.11.0, installed 3.10.7 in
this dev environment, both satisfy `>=3.7`. `nmrglue`/`numpy` confirmed already importable as
base deps (no `[webview]` extra needed for either).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|--------------|-----------|-------------|
| matplotlib | PyPI | ~20 years (first release 2003) | >100M/month (industry-standard scientific-Python plotting library) | github.com/matplotlib/matplotlib | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

`slopcheck install matplotlib` ran successfully in this environment and returned `[OK]`. This
package's identity was not discovered via WebSearch/training — it is an explicit locked decision
already named in CONTEXT.md D-04 (user-supplied), and its registry existence, current version,
and functional behavior (Figure/FigureCanvasAgg/PNG round-trip) were all directly executed and
confirmed in this session, so it is tagged `[VERIFIED: PyPI + local execution]` rather than
`[ASSUMED]` above.

## Architecture Patterns

### System Architecture Diagram

```
Browser (webview.js tick(), ~3s poll)
  │
  ├─ GET /api/spectra/1d/carbon  ──┐
  └─ GET /api/spectra/1d/proton  ──┤
                                    │
                          spectra.py router (make_router(analysis_dir))
                                    │
              ┌─────────────────────┼─────────────────────────┐
              │                     │                         │
     read .run_manifest.json   locate/select              read analysis/peaks/
     (bruker_data_dir, formula)  Bruker experiment dir      carbon_signals.json
              │                (scan numbered dirs,               │
              │                 skip acqu2s [2D],                 │
              │                 skip dept* PULPROG,                │
              │                 lowest number wins)                │
              │                     │                         │
              │              BrukerReader.read_1d()                │
              │              (nmrglue: read_pdata,                 │
              │               guess_udic, uc.ppm_scale())           │
              │                     │                         │
              │                     ▼                         ▼
              │           Spectrum1D(data, ppm_scale,   peak overlay rows
              │              nucleus, metadata)          (ppm/assignment)
              │                     │                         │
              │                     └───────────┬─────────────┘
              │                                 ▼
              │                    _render_1d_png() — matplotlib OO API
              │                    Figure + FigureCanvasAgg
              │                    _apply_nmr_axes() (shared, reversed ppm)
              │                    line trace + vertical peak markers/labels
              │                                 │
              │                    canvas.print_png(buf) in try/finally
              │                                 │
              └──── any failure at any step ─────┤
                    (missing manifest, bad path,  │
                     no matching experiment,      ▼
                     malformed peak JSON) ──> placeholder "unavailable" PNG
                                                 │
                                                 ▼
                                  Response(png_bytes, media_type="image/png")
                                  HTTP 200 always
```

### Recommended Project Structure
```
src/lucy_ng/webview/
├── routers/
│   ├── tables.py       # existing (Phase 94) — pattern to mirror
│   ├── log.py           # existing — minimal make_router template
│   └── spectra.py       # NEW — this phase
└── static/
    ├── index.html        # MODIFY — replace the spectra-1d placeholder div with <img> targets
    └── webview.js         # MODIFY — add refreshSpectra1D() to tick(), cache-busted <img> src
```

### Pattern 1: Never-500 PNG endpoint (binary analog of tables.py's JSON never-500 idiom)
**What:** The route handler always returns a `Response(content=<png bytes>, media_type="image/png")`
with HTTP 200 — never a 500, and never a JSON body on this route (JSON and PNG cannot coexist on
one content-type). All failure modes (absent manifest, unlocatable/stale `bruker_data_dir`, no
matching experiment for the requested nucleus, corrupt pdata, malformed peak JSON) render a
small placeholder PNG with the text "unavailable / waiting for data" instead of raising.
**When to use:** Any binary (image) endpoint that must satisfy SP-02's "HTTP 200, never 500"
contract — this is the same shape already proven in `structures.py`'s `/api/structure/{i}.svg`
(`placeholder_svg()` on malformed SMILES, HTTP 200, D-11).
**Example (verified executable in this session):**
```python
# Source: executed directly in this research session against matplotlib 3.10.7
import io
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

def _render_placeholder_png(message: str, width_in: float = 8.0, height_in: float = 2.0) -> bytes:
    fig = Figure(figsize=(width_in, height_in), dpi=100)
    try:
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color="#6c757d")
        ax.axis("off")
        buf = io.BytesIO()
        canvas.print_png(buf)
        return buf.getvalue()
    finally:
        import matplotlib.pyplot as _plt  # only for .close(fig); NEVER used for drawing
        _plt.close(fig)
```
*(Note: `plt.close(fig)` is the one pyplot call that is acceptable even under the "never
matplotlib.pyplot" rule, IF the planner prefers to avoid it entirely: `Figure` objects created
via the constructor (not `plt.figure()`) are NOT tracked by pyplot's global figure registry, so
simply letting `fig` go out of scope / `del fig` is sufficient — no `plt.close()` call, and no
`pyplot` import at all, is actually required. Recommend the planner use `del canvas, fig` in the
`finally` block instead, to keep the "NEVER matplotlib.pyplot" rule (D-04) unambiguous with zero
exceptions.)*

### Pattern 2: 1D-vs-2D and DEPT-vs-standard experiment discrimination (verified against real data)
**What:** Bruker experiment roots for a single compound often contain a proton-decoupled ¹³C
(the one to render), one or more DEPT-edited ¹³C experiments (same nucleus, must be excluded from
"the ¹³C spectrum"), a ¹H spectrum, and several 2D experiments whose acqus `$NUC1` field reports
the **direct (F2) detected nucleus** — which for inverse-detected HSQC/HMBC/COSY is `1H`, exactly
the same value as the real 1D proton spectrum. A naive "scan every numbered dir's acqus $NUC1"
loop will therefore misclassify 2D experiments as extra ¹H candidates.
**When to use:** Always, in `_select_experiment()` — this is not an edge case, it is the normal
shape of a CASE compound directory (confirmed present in every multi-experiment dataset checked).
**Verified against real data (executed in this session):**
```
CASE1/ (7 numbered experiment dirs directly under the compound root):
  1/ NUC1=1H  PULPROG=zg30           1D (no acqu2s)  <- the real 1H spectrum
  2/ NUC1=13C PULPROG=zgpg30         1D (no acqu2s)  <- the real 13C spectrum (want this one)
  3/ NUC1=13C PULPROG=dept135        1D (no acqu2s)  <- DEPT, must be excluded
  4/ NUC1=13C PULPROG=dept90         1D (no acqu2s)  <- DEPT, must be excluded
  5/ NUC1=1H  PULPROG=cosygpqf       2D (acqu2s present) <- must be excluded from 1H candidates
  6/ NUC1=1H  PULPROG=inv4gpqf       2D (acqu2s present) <- must be excluded (HSQC-family)
  7/ NUC1=1H  PULPROG=inv4gplplrndqf 2D (acqu2s present) <- must be excluded (HMBC-family)

CASE6/ (same pattern, two full experiment sets numbered 1-8 and 17-24):
  1(or 17)/  1H  zg30      1D
  2(or 18)/  13C udeft     1D  <- standard 13C
  3(or 19)/  13C deptsp135 1D  <- DEPT, exclude
  4(or 20)/  13C deptsp90  1D  <- DEPT, exclude
  5-8 (or 21-24)/ 2D experiments (hsqc/hmbc/cosy/noesy), all acqu2s present, all NUC1=1H
```
**Recommended discriminator (both confirmed reliable across both datasets checked):**
1. **2D exclusion:** `(experiment_dir / "acqu2s").exists()` → skip (this is a 2D experiment; its
   acqus `$NUC1` reflects the detected/F2 nucleus, not a standalone 1D spectrum).
2. **DEPT exclusion (for ¹³C only):** after calling `BrukerReader.read_1d(dir)`, check
   `spectrum.metadata.get("pulse_program", "").lower()` — if it contains `"dept"`, skip this
   candidate; keep scanning. (`zgpg30`/`zg30`/`udeft` are all standard non-edited pulse programs
   and do NOT match this filter.)
3. **Tiebreak:** among remaining candidates for a given nucleus, pick the **lowest experiment
   number** (matches CONTEXT.md D-02's suggested heuristic and was independently confirmed
   correct for both CASE1 and CASE6 — the standard ¹³C experiment is always numbered lower than
   its DEPT siblings in both datasets checked).

### Pattern 3: `.run_manifest.json` contract + case.md write site
**What:** `case.md`'s `spawn_case_team` Step 5 already does `mkdir -p <compound_path>/analysis`
as a prefix on its very first timing stamp (`run_start`, case.md lines 236, 345-346), BEFORE the
webview server launch (line 248) and BEFORE the CASE-PROGRESS.md header write (line 266). The
`.run_manifest.json` write belongs in this same window: after the `mkdir -p .../analysis` (so the
directory exists) and before or alongside the webview launch (so the dashboard can read it from
the very first poll tick).
**Where exactly:** Insert a new Bash step immediately after the `run_start` timing stamp
(case.md ~line 236-246, before the `WEBVIEW_OUTPUT=$(lucy webview serve ...)` call) that writes:
```bash
cat > "<compound_path>/analysis/.run_manifest.json" <<JSON
{"bruker_data_dir": "<compound_path (absolute)>", "formula": "<formula>"}
JSON
```
Both `<compound_path>` and `<formula>` are already known at this point in `spawn_case_team`
(they are the same values interpolated into the `SendMessage` prompts a few lines below at 274).
No CLI signature change, no `.webview.json` schema change — confirmed by reading `app.py`
(`create_app(analysis_dir: Path)` takes only the analysis dir; the manifest is read by the new
`spectra.py` router from inside that same analysis dir).

### Anti-Patterns to Avoid
- **Calling `ax.invert_xaxis()` after `ax.set_xlim(ppm_scale[0], ppm_scale[-1])`:** since
  `ppm_scale` from nmrglue is already descending, `set_xlim` with those two values already
  produces a reversed (high-ppm-left) axis. An additional `invert_xaxis()` call flips it back to
  ascending — the opposite of SP1-01's requirement. Verified empirically in this session.
- **Scanning acqus `$NUC1` without excluding `acqu2s`-bearing directories:** will silently offer
  2D experiments as fake "extra ¹H 1D" candidates (verified against real CASE1/CASE6 data).
- **Treating any `13C`-nucleus experiment as "the" ¹³C spectrum:** DEPT-edited experiments share
  the nucleus but are not the spectrum a chemist expects on this tab (verified: CASE1 exp 3/4,
  CASE6 exp 3/4/19/20 are all DEPT variants sharing the 13C nucleus with the standard experiment).
- **Using `matplotlib.pyplot.close(fig)` in the cleanup path:** technically harmless (closing a
  non-pyplot-tracked Figure is a no-op on the global stack) but importing `pyplot` at all
  re-introduces the exact module the locked decision (D-04) forbids; prefer `del fig, canvas`
  or simply letting local variables go out of scope at function return.
- **Returning JSON `{"state": "waiting"}` from the PNG route on failure:** breaks the
  `<img src="...">` contract in the browser (an `<img>` tag showed a JSON blob does not decode as
  an image and renders a broken-image icon) — always return valid PNG bytes, varying only the
  *content* of the image (real chart vs. placeholder text), never the content-type.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ppm-scale generation from raw Bruker data | Manual SW/O1/SFO1 arithmetic to compute a ppm axis | `nmrglue`'s `ng.bruker.guess_udic()` + `ng.fileiobase.uc_from_udic(udic, dim=0).ppm_scale()` — already fully wrapped by `BrukerReader.read_1d()` | This is exactly what `BrukerReader` already does; re-deriving it in `spectra.py` would duplicate logic and risk subtle referencing bugs (e.g. `SFO1` vs `BF1`, digital-filter group-delay offsets) that nmrglue already handles correctly |
| Nucleus/dimensionality detection | Hand-rolled acqus text parsing (regex over `##$NUC1=<...>`) | `BrukerReader.read_1d()`'s existing `_get_param()`/`nucleus` extraction (call `read_1d` per candidate dir inside a `try/except (FileNotFoundError, ValueError)`, bucket by `.nucleus`) | `_get_param()` already handles the `<...>` bracket-stripping Bruker parameter-string convention; a fresh regex would have to reinvent this correctly |
| PNG encoding | Manual `PIL.Image` buffer construction from a matplotlib RGBA array | `FigureCanvasAgg.print_png(buf)` (or `.buffer_rgba()` only if a raw-pixel-format cache key is needed, which Phase 95 does not need per D-06) | `print_png` is matplotlib's own, tested Agg PNG encoder — no need for an extra PIL dependency (PIL is already a transitive matplotlib dep anyway, but the encode path should stay inside matplotlib) |
| Never-500 failure handling | Bespoke try/except sprinkled ad hoc through the router | The exact `_JSON_READ_ERRORS` broad-except-tuple idiom from `tables.py`, adapted to the analogous binary-endpoint pattern from `structures.py`'s `placeholder_svg()` fallback | Both idioms are already proven correct and tested (14/14 `TestTablesEndpoint` methods pass); reusing them keeps the never-500 guarantee auditable across the whole webview package |

**Key insight:** every piece of "new" logic this phase needs (ppm-scale generation, acqus
parameter parsing, never-500 degradation) already has a working, tested implementation elsewhere
in this codebase. The actual net-new code is: (1) the experiment-selection filter (2D/DEPT
exclusion — genuinely new, verified necessary above), (2) the matplotlib render function, and
(3) the router glue + manifest read.

## Common Pitfalls

### Pitfall 1: 2D experiments masquerading as 1H 1D candidates
**What goes wrong:** The router finds a `1H`-nucleus acqus entry in a directory that is actually
a 2D HSQC/HMBC/COSY experiment (inverse-detected, so F2/`acqus $NUC1` = `1H`) and tries to render
it as if it were a 1D proton spectrum.
**Why it happens:** `BrukerReader.read_1d()` reads `pdata/1` unconditionally; for a 2D experiment
this directory contains `2rr` (2D real-real data) rather than `1r`, and depending on nmrglue's
`guess_udic`/`uc_from_udic(dim=0)` behavior this can either raise an unexpected exception deep in
nmrglue (least likely, since dim=0 exists in both) or — worse — silently produce a nonsensical
1D "spectrum" that is actually a slice/misread of 2D data.
**How to avoid:** Check `(experiment_dir / "acqu2s").exists()` BEFORE calling `read_1d()` on any
candidate directory, and skip it if true. Verified: every 2D experiment in both CASE1 and CASE6
has `acqu2s` present; every 1D experiment (proton or carbon, edited or not) lacks it.
**Warning signs:** A "1H spectrum" panel that looks like noise, is empty, or throws deep inside
nmrglue's `uc_from_udic` — always check whether the selected directory has `acqu2s` first.

### Pitfall 2: DEPT experiments rendered as "the" ¹³C spectrum
**What goes wrong:** DEPT-135/DEPT-90 (edited ¹³C, phase-inverted for CH/CH₂, weak/absent
quaternary carbons) gets selected instead of the standard proton-decoupled ¹³C acquisition,
producing a spectrum where the carbonyl (quaternary, invisible in DEPT) appears to be missing —
directly undermining SC2's carbonyl-at-181ppm visual-validation check.
**Why it happens:** DEPT experiments share the same `$NUC1=13C` value as the standard experiment;
a bare nucleus-match scan cannot tell them apart.
**How to avoid:** After nucleus-matching, additionally check `metadata["pulse_program"]` (already
returned by `read_1d`) for the substring `"dept"` (case-insensitive) and exclude matches.
**Warning signs:** SC2's ibuprofen carbonyl check (`~181 ppm` peak) fails or is unusually weak
relative to CH/CH₃ peaks — check which pulse program was actually selected.

### Pitfall 3: Double-reversing the ppm axis
**What goes wrong:** Code calls both `ax.set_xlim(ppm_scale[0], ppm_scale[-1])` AND
`ax.invert_xaxis()`, or reverses the `ppm_scale`/`data` numpy arrays before plotting AND also sets
`xlim` from the (now ascending) reversed arrays — either combination cancels out the intended
reversal and produces an ascending (low-ppm-left) axis, silently failing SC2's
`ax.get_xlim()[0] > ax.get_xlim()[1]` test.
**Why it happens:** `ppm_scale` from `Spectrum1D`/nmrglue is ALREADY descending (Bruker
convention) — verified by direct execution against CASE1 (`ppm_scale[0]=231.29`,
`ppm_scale[-1]=-12.00`). Code written from the assumption "ppm scales are usually ascending, I
need to reverse them" will over-correct.
**How to avoid:** Never call `invert_xaxis()`. Never manually reverse the `ppm_scale`/`data`
arrays. Simply `ax.plot(spectrum.ppm_scale, spectrum.data)` then
`ax.set_xlim(spectrum.ppm_scale[0], spectrum.ppm_scale[-1])` — the shared `_apply_nmr_axes()`
helper should encode exactly this and nothing more.
**Warning signs:** SC2's `ax.get_xlim()[0] > ax.get_xlim()[1]` assertion fails, or the chart
visually shows the carbonyl on the right instead of the left.

### Pitfall 4: matplotlib.pyplot import creeping in via `plt.close(fig)`
**What goes wrong:** A developer adds `import matplotlib.pyplot as plt` purely to call
`plt.close(fig)` in a `finally` block "to be safe," reintroducing the exact global-state module
D-04 forbids, and — because this import sits at module level or inside `make_router()` alongside
other lazy imports — it may not be caught by a simple grep for `pyplot` if written as
`from matplotlib import pyplot`.
**Why it happens:** `plt.close()` is the idiomatic matplotlib-tutorial way to release a Figure;
muscle memory reaches for it even in `Figure()`-constructor (non-pyplot) code.
**How to avoid:** `Figure()` objects created via direct construction (not `plt.figure()`) are
never registered in pyplot's global figure manager, so there is nothing to "close" from pyplot's
perspective — just let the local `fig`/`canvas` variables go out of scope (or `del` them
explicitly in a `finally` block) at the end of the render function.
**Warning signs:** `grep -rn "pyplot" src/lucy_ng/webview/` returns any hit outside a code
comment.

### Pitfall 5: PNG route returning JSON on the "waiting" path
**What goes wrong:** The failure branch returns `JSONResponse({"state": "waiting"})` instead of
PNG bytes, matching the `tables.py` idiom literally instead of adapting it to a binary endpoint —
this breaks `<img src="/api/spectra/1d/carbon">` in the browser (renders a broken-image icon,
not a graceful "waiting" message).
**Why it happens:** Over-generalizing the very well-established `{"state": "ok"|"waiting"}` JSON
idiom from `tables.py`/`log.py` without noticing this route's content-type is fixed to
`image/png`.
**How to avoid:** Always return `Response(content=<png bytes>, media_type="image/png")` from
every code path in the route handler — vary only whether the bytes are a real chart or a
placeholder message rendered as its own tiny matplotlib figure (mirrors `structures.py`'s
`placeholder_svg()` precedent exactly).
**Warning signs:** A frontend manual browser check shows a broken-image icon instead of an
"unavailable" message text.

## Code Examples

### Manifest read (never-500, mirrors tables.py's `_JSON_READ_ERRORS` idiom)
```python
# Source: pattern adapted from src/lucy_ng/webview/routers/tables.py (_read_carbon)
import json
from pathlib import Path
from typing import Any

_JSON_READ_ERRORS = (FileNotFoundError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError)

def _read_manifest(analysis_dir: Path) -> dict[str, Any] | None:
    """Read analysis/.run_manifest.json. Returns None on any failure (D-01/D-05) — never raises."""
    p = analysis_dir / ".run_manifest.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data.get("bruker_data_dir"), str):
            return None
        return data
    except _JSON_READ_ERRORS:
        return None
```

### Experiment selection (verified logic — see Pattern 2 above for the empirical basis)
```python
# Source: derived from BrukerReader.read_1d (src/lucy_ng/readers/bruker.py) + verified
# acqus/acqu2s inspection of CASE1 and CASE6 real datasets (this research session)
import re
from pathlib import Path

from lucy_ng.models import Spectrum1D
from lucy_ng.readers.bruker import BrukerReader


def _select_experiment(bruker_data_dir: Path, nucleus: str) -> Spectrum1D | None:
    """Scan numbered experiment dirs, return the best Spectrum1D for `nucleus`, or None."""
    candidates: list[tuple[int, Spectrum1D]] = []
    for exp_dir in sorted(bruker_data_dir.iterdir(), key=lambda p: p.name):
        if not exp_dir.is_dir() or not re.match(r"^\d+$", exp_dir.name):
            continue
        if (exp_dir / "acqu2s").exists():
            continue  # 2D experiment — Pitfall 1
        try:
            spectrum = BrukerReader.read_1d(exp_dir)
        except (FileNotFoundError, ValueError, OSError):
            continue  # unreadable / not a 1D experiment
        if spectrum.nucleus != nucleus:
            continue
        pulse_program = str(spectrum.metadata.get("pulse_program", "")).lower()
        if "dept" in pulse_program:
            continue  # DEPT-edited — Pitfall 2
        candidates.append((int(exp_dir.name), spectrum))
    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]  # lowest experiment number wins
```

### Shared `_apply_nmr_axes()` helper (reversed ppm axis — Pitfall 3)
```python
# Source: derived from STATE.md "[v9.3-roadmap] Reversed ppm axes everywhere" +
# verified via direct execution in this research session (ax.get_xlim()[0] > ax.get_xlim()[1] == True)
from numpy.typing import NDArray
import numpy as np


def _apply_nmr_axes(ax: "matplotlib.axes.Axes", ppm_scale: NDArray[np.float64]) -> None:  # noqa: F821
    """Set xlim from an already-descending Bruker ppm_scale. Do NOT call invert_xaxis()."""
    ax.set_xlim(float(ppm_scale[0]), float(ppm_scale[-1]))
    ax.set_xlabel("δ (ppm)")
```

### PNG route (never-500 binary endpoint — Pitfall 5)
```python
# Source: pattern adapted from structures.py's placeholder_svg() precedent
from fastapi import APIRouter
from fastapi.responses import Response


def make_router(analysis_dir):  # -> APIRouter, matplotlib import lazy inside (WV-08/D-04)
    from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: PLC0415
    from matplotlib.figure import Figure  # noqa: PLC0415

    router = APIRouter(prefix="/api")

    @router.get("/spectra/1d/carbon")
    def get_carbon_1d() -> Response:
        png_bytes = _render_or_placeholder(analysis_dir, "13C", Figure, FigureCanvasAgg)
        return Response(content=png_bytes, media_type="image/png")

    return router
```

## State of the Art

| Old Approach (pre-roadmap sketch) | Current (locked) Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `research/SUMMARY.md` stick-spectra sketch (synthesize a spectrum shape from peak JSON) | Real Bruker trace via `BrukerReader.read_1d` + nmrglue | v9.3 roadmap (2026-07-07), reaffirmed in CONTEXT.md D-01 | The whole QC value of the phase (visually validating peak-picking against the real signal) only exists with a real trace; a stick-plot-from-peaks is circular |

**Deprecated/outdated:** None specific to this phase — matplotlib's pyplot-vs-OO-API distinction
is not a version-deprecation issue, it is a concurrency-safety choice already locked by D-04.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Lowest experiment number wins" tiebreak generalizes beyond CASE1/CASE6 to other CASE datasets not directly inspected in this session (CASE2-5, CASE7-9, C13H9OBr, C20H32O2) | Pattern 2 / Architecture Patterns | If some future dataset numbers its DEPT experiment lower than its standard ¹³C experiment, the router would pick the DEPT spectrum instead — verified only for CASE1 and CASE6 in this session, not the full dataset population |
| A2 | No live `analysis/` directory anywhere on this machine currently contains a real, phase-95-shaped `.run_manifest.json` or a real `carbon_signals.json` matching the locked schema for CASE1 — testing must use hand-authored fixtures (same caveat already recorded for Phase 94 in STATE.md) | Phase Requirements / Package Legitimacy Audit | Tests built against a hand-authored fixture could pass while missing a real-world schema drift that would only surface once `case.md`'s actual peak-picking output is inspected against this exact schema |

**Note:** matplotlib's package identity is NOT listed here — it was a locked user decision from
CONTEXT.md D-04 (not sourced from this research session's training/websearch), and its version,
registry presence, and functional behavior were all independently verified via `pip index
versions`, `slopcheck`, and direct code execution in this session — see Standard Stack.

## Open Questions

1. **Does the "lowest experiment number" tiebreak hold for the other 7 CASE datasets?**
   - What we know: Confirmed correct for CASE1 and CASE6 (both have the standard ¹³C experiment
     numbered lower than its DEPT siblings).
   - What's unclear: CASE2-5, CASE7-9 were not individually inspected in this research session
     (time-boxed to the phase's primary dataset, CASE1, per the SC2 acceptance criterion).
   - Recommendation: The planner should keep the DEPT-substring filter (Pattern 2, step 2) as the
     PRIMARY discriminator (verified robust — it does not depend on numbering order at all) and
     treat "lowest number" as only a secondary tiebreak among non-DEPT candidates of the same
     nucleus. This makes the numbering-order assumption (A1) low-risk even if unverified for the
     other datasets, since DEPT filtering alone already resolves the CASE1/CASE6 cases correctly
     without relying on numbering at all.

2. **Should the ¹H "always render when present" rule (D-02) also apply the acqu2s/DEPT-style
   filtering, or is a bare nucleus-match sufficient once 2D dirs are excluded?**
   - What we know: CASE1/CASE6's ¹H 1D experiment (`zg30`) is unambiguous once 2D dirs
     (`acqu2s` present) are excluded — no "DEPT-equivalent" edited ¹H experiment variant exists
     in either dataset.
   - What's unclear: Whether some other dataset has more than one non-2D ¹H experiment (e.g. a
     presaturation or WET-solvent-suppression variant) that would need the same
     lowest-number-wins tiebreak.
   - Recommendation: Apply the same `_select_experiment()` helper uniformly for both nuclei
     (it already generalizes — the DEPT filter is a no-op for ¹H candidates since `"dept"` never
     appears in a proton pulse-program name); no nucleus-specific branching needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| matplotlib | Rendering (D-04) | ✓ | 3.10.7 (installed), 3.11.0 (latest on PyPI) | — |
| nmrglue | `BrukerReader.read_1d`/`read_2d` | ✓ (already base dep) | 2.2.1 | — |
| fastapi | Router/Response | ✓ (already `[webview]` dep) | installed, satisfies >=0.100 | — |
| CASE1 raw Bruker dataset (for manual/SC2 verification) | SC2 carbonyl-at-181ppm check | ✓ | — (`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/CASE1`, 7 numbered experiment dirs) | — |
| Live `analysis/.run_manifest.json` on this machine | End-to-end manual verification | ✗ | — | Hand-authored `tmp_path` fixtures for pytest (same as Phase 94); a manual `lucy webview serve` smoke test against a synthetic manifest pointing at CASE1 is a reasonable Wave-N checkpoint |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:** No live `.run_manifest.json` exists yet on this machine
(A2 above) — use hand-authored pytest fixtures; a manual checkpoint task can construct a
synthetic manifest pointing at the real CASE1 directory to exercise the full path against real
Bruker data.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (>=7.0, already a dev dep) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| Quick run command | `pytest tests/test_webview_api.py -k Spectra -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SP1-01 | `/api/spectra/1d/carbon` returns a PNG with reversed xlim when manifest+data+peaks all present | integration | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_carbon_reversed_axis -x` | ❌ Wave 0 (new test class, mirrors `TestTablesEndpoint`) |
| SP1-01 | `/api/spectra/1d/proton` renders when a ¹H experiment is present; is independently "unavailable" when only ¹³C is found | integration | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_proton_present_and_absent -x` | ❌ Wave 0 |
| SP1-01 | Peak overlay markers appear at the ppm positions from `carbon_signals.json` (assert on rendered PNG byte-count delta vs. no-overlay baseline, or assert the overlay-drawing helper is called with the expected ppm list — unit-level, not pixel-diff) | unit | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_peak_overlay_positions -x` | ❌ Wave 0 |
| SP-02 | Absent `.run_manifest.json` → HTTP 200, placeholder PNG (never 500) | integration | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_missing_manifest_returns_placeholder -x` | ❌ Wave 0 |
| SP-02 | Manifest present but `bruker_data_dir` stale/unreadable → HTTP 200, placeholder PNG | integration | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_stale_bruker_path_returns_placeholder -x` | ❌ Wave 0 |
| SP-02 | `carbon_signals.json` absent/malformed but raw data present → chart renders WITHOUT peak overlay, still HTTP 200 (never 500) | integration | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_missing_peaks_json_renders_bare_trace -x` | ❌ Wave 0 |
| SC2 (ROADMAP) | Against the REAL CASE1 dataset, `ax.get_xlim()[0] > ax.get_xlim()[1]` holds and the rendered carbonyl-region peak (~181 ppm) is positioned left of the aliphatic CH3 region | integration (uses real CASE1 fixture path, not a synthetic tmp_path) | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_case1_carbonyl_left_of_aliphatic -x` (skip if CASE1 data dir absent on CI) | ❌ Wave 0 |
| WV-08 | `from lucy_ng.cli import cli` and `from lucy_ng.webview import server` do not raise ImportError without `[webview]`; `spectra.py` module-level code contains no `matplotlib` import outside `make_router()` | static/structural | `pytest tests/test_webview_api.py::TestSpectraEndpoint::test_no_module_level_matplotlib_import -x` (source-grep style, mirrors existing WV-08 discipline) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_webview_api.py -k Spectra -x`
- **Per wave merge:** `pytest` (full suite; 1174+ tests passing at last count per STATE.md)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_webview_api.py::TestSpectraEndpoint` — new test class (mirrors
      `TestTablesEndpoint`'s shape: `try/except ImportError: pytest.skip` on
      `from lucy_ng.webview.routers import spectra`), covering the 8 rows in the map above.
- [ ] `spectra_manifest_dir` fixture (or reuse/extend `tables_analysis_dir`) — a `tmp_path`-based
      analysis dir containing a hand-authored `.run_manifest.json` pointing at the REAL CASE1
      directory (`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/CASE1`) for the
      SC2 real-data test, plus a synthetic Bruker-dir-shaped `tmp_path` fixture (fake acqus files)
      for the pure-unit-level 2D/DEPT-exclusion tests so those don't depend on the external
      Dropbox path being present in CI.
- [ ] Framework install: none needed — matplotlib will be present in any environment running
      `pytest tests/test_webview_api.py -k Spectra` since it must be added to `[webview]`, and the
      dev extra already pulls in `httpx`/`fastapi` needed for `TestClient`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user localhost tool, no auth surface (existing project-wide decision, unchanged by this phase) |
| V3 Session Management | no | No sessions introduced |
| V4 Access Control | no | No access-control surface introduced |
| V5 Input Validation | yes (narrow) | The only external input this phase parses is `analysis/.run_manifest.json` (trusted-writer, D-07) and `carbon_signals.json` (already-audited schema from Phase 94) — both parsed via `json.loads` inside the existing broad-except never-500 idiom, never `eval`/`exec`/`pickle` |
| V6 Cryptography | no | No cryptographic operations introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via a maliciously-crafted `bruker_data_dir` value in `.run_manifest.json` | Tampering / Information Disclosure | Explicitly accepted risk per locked decision D-07 ("Trust the manifest's absolute path — localhost single-user tool... no path whitelist/sandboxing beyond 'if it is not a readable Bruker experiment tree, show unavailable'"). This is consistent with the existing routers' threat model (e.g. `structures.py` already reads arbitrary SMILES/paths from `analysis/` without sandboxing) — not a new risk introduced by this phase, and out of scope to harden per the locked decision. |
| Denial of service via a very large/malformed Bruker `fid`/`1r` file causing nmrglue to allocate excessive memory | Denial of Service | Not mitigated in this phase (matches the existing threat model — no size/resource limits exist anywhere else in the webview package either); acceptable given the single-user localhost deployment target. Flagged here for visibility, not as a blocking requirement. |
| Malformed `carbon_signals.json` causing a rendering exception mid-Figure-construction | Denial of Service (partial — would 500 without the never-500 guard) | Wrap the peak-overlay-drawing step in the same broad except tuple as the rest of the router (`_JSON_READ_ERRORS`-style), falling back to rendering the bare trace without peaks rather than failing the whole request (see Common Pitfalls / SP-02 test map row "Missing peaks JSON renders bare trace") |

## Sources

### Primary (HIGH confidence — directly read/executed in this session)
- `src/lucy_ng/readers/bruker.py` — `BrukerReader.read_1d`/`read_2d`, `_get_param`, `_detect_experiment_type` (full read)
- `src/lucy_ng/models/spectrum.py` — `Spectrum1D`/`Spectrum2D` Pydantic models (full read)
- `src/lucy_ng/models/peaks.py` — `Peak1D`/`Peak2D`/`PeakList1D`/`PeakList2D` (full read)
- `src/lucy_ng/webview/routers/tables.py` — never-500 JSON idiom, `make_router` shape (full read)
- `src/lucy_ng/webview/routers/log.py` — minimal `make_router` template (full read)
- `src/lucy_ng/webview/routers/structures.py` — PNG/SVG-analog binary endpoint pattern,
  `placeholder_svg()` precedent (full read)
- `src/lucy_ng/webview/app.py` — `create_app()`, lazy-import docking pattern (full read)
- `src/lucy_ng/webview/static/webview.js` — `tick()` polling loop, `refreshCarbon`/`renderCarbon`
  fetch pattern, tab-panel dispatch (targeted read)
- `src/lucy_ng/webview/static/index.html` — spectra-1d tab placeholder location, CSS colour
  tokens (targeted read)
- `pyproject.toml` — `[project.optional-dependencies].webview`, base deps, pytest config (full read)
- `tests/test_webview_api.py` — WV-08 `try/except ImportError: pytest.skip` idiom,
  `tables_analysis_dir` hand-authored fixture, `TestTablesEndpoint` test bodies (targeted read)
- `.claude/commands/lucy-ng/case.md` — `spawn_case_team` Step 5 (`run_start` timing stamp +
  `mkdir -p analysis` + webview launch + CASE-PROGRESS.md header ordering), timing step's
  `run_start`/`mkdir -p` mechanism (targeted read, two sections)
- Direct code execution in this session: `BrukerReader.read_1d()` against the real
  `CASE1/2` (¹³C, `zgpg30`) experiment directory — confirmed `nucleus="13C"`,
  `frequency=125.706...`, `solvent="CDCl3"`, `metadata={"pulse_program": "zgpg30", "num_scans":
  1024, "temperature": 298}`, `data.shape=(65536,)`, `ppm_scale[0]=231.29`, `ppm_scale[-1]=-12.00`
  (already descending)
- Direct code execution in this session: matplotlib `Figure`+`FigureCanvasAgg` OO-API round-trip
  (plot → `set_xlim` reversed → `canvas.print_png` → 14346-byte PNG, `ax.get_xlim()[0] >
  ax.get_xlim()[1]` == `True`)
- Direct filesystem inspection in this session: `acqus`/`acqu2s`/`pdata/1` contents for all 7
  CASE1 experiment dirs and all 8+8 CASE6 experiment dirs (two independent datasets, confirming
  the 2D/`acqu2s` and DEPT/`pulse_program` discriminators)
- `slopcheck install matplotlib` — executed in this session, returned `[OK]` (PyPI)
- `pip index versions matplotlib` — executed in this session, confirmed 3.11.0 latest / 3.10.7 installed

### Secondary (MEDIUM confidence)
- None — all findings in this phase were directly verifiable against the local codebase and
  local Bruker datasets; no external/web sources were needed.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — matplotlib version/behavior verified by direct execution; nmrglue/numpy/fastapi already-installed base/extra deps confirmed via pyproject.toml
- Architecture: HIGH — router/lazy-import/never-500 patterns copied verbatim from working, tested Phase 94/91 code; PNG-endpoint-never-500 pattern is a direct structural analog of the already-shipped `structures.py` SVG endpoint
- Pitfalls: HIGH — all 5 pitfalls were empirically confirmed against real CASE1/CASE6 Bruker data or by direct code execution in this session, not inferred from training data

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (30 days — stable, no fast-moving external dependencies; matplotlib/nmrglue/fastapi versions pinned as ranges, not exact pins)

## RESEARCH COMPLETE

**Phase:** 95 - 1D Real Spectra + Peak Overlay
**Confidence:** HIGH

### Key Findings
- `Spectrum1D.ppm_scale` from `BrukerReader.read_1d` is ALREADY descending (verified by executing it against real CASE1 data) — the reversed-axis requirement is `ax.set_xlim(ppm_scale[0], ppm_scale[-1])` alone; calling `invert_xaxis()` in addition would silently undo it. This directly refines the STATE.md/CONTEXT.md description of `_apply_nmr_axes()`.
- A naive "scan acqus $NUC1" experiment-selection loop is unsafe: verified against real CASE1 and CASE6 datasets that (1) 2D experiments (HSQC/HMBC/COSY) report `$NUC1=1H` for their F2 dimension and must be excluded via `acqu2s` presence, and (2) DEPT-edited ¹³C experiments share the `13C` nucleus with the standard decoupled spectrum and must be excluded via a `metadata["pulse_program"]` substring check — both are new, concrete discriminators the planner should encode in `_select_experiment()`.
- The PNG endpoint's "never-500" contract should follow the already-shipped `structures.py` SVG precedent exactly: always return valid image bytes (real chart or placeholder-text chart), never a JSON body — a mixed JSON/binary contract on one route would break `<img src>` in the browser.
- matplotlib is confirmed [OK] via slopcheck, is already installed (3.10.7) and importable in this environment, and the exact `Figure`+`FigureCanvasAgg`+reversed-xlim+`print_png` recipe was executed end-to-end successfully in this session.
- The `.run_manifest.json` write site in `case.md` is precisely located: immediately after the `run_start` timing stamp's `mkdir -p <compound_path>/analysis` prefix (line ~236-246) and before the webview-launch call — `<compound_path>` and `<formula>` are already in scope there.

### File Created
`/Users/steinbeck/Dropbox/develop/lucy-ng/.planning/phases/95-1d-real-spectra-peak-overlay/95-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | matplotlib version/behavior directly executed; all other deps already installed/confirmed |
| Architecture | HIGH | Router/never-500/lazy-import patterns copied from working, tested Phase 91/94 code |
| Pitfalls | HIGH | Empirically confirmed against real Bruker data (CASE1, CASE6), not inferred |

### Open Questions
1. Whether "lowest experiment number wins" as a tiebreak generalizes to CASE2-5/CASE7-9 (not individually inspected) — mitigated by recommending the DEPT-substring filter as the primary (numbering-independent) discriminator, with numbering only as a secondary tiebreak.
2. Whether any dataset has more than one non-2D, non-DEPT ¹H experiment variant requiring the same tiebreak — the recommended `_select_experiment()` helper already generalizes to this case without special-casing.

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
