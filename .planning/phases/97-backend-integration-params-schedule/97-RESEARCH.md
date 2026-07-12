# Phase 97: Backend Integration + Params/Schedule - Research

**Researched:** 2026-07-12
**Domain:** External-binary backend detection (NMRPipe+SMILE) + pure-Python Bruker NUS acquisition-parameter/sampling-schedule parsing into Pydantic v2 models
**Confidence:** HIGH — every claim below that matters for correctness (FnMODE→schedule-length rule, exact param field names, byte layout) is grounded in direct inspection of the real C20H32O2 fixture files and the installed `nmrglue` library, not training-data recall. One important correction to the milestone's prior architecture research is reported explicitly (see "Critical correction" below).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**`lucy nus check` depth (D-01):** `lucy nus check` in Phase 97 does **backend detection only** — checks the SMILE toolchain (`nmrPipe`, `smileNus`, `nusExpand.tcl`, `bruk2pipe`) on PATH via the LSD precedent (`shutil.which` + `SEARCH_PATHS`, mirroring `LSDRunner.is_available()`) — **plus** a distinct diagnostic state separating "installed but the NMRPipe env is not sourced / tools not on PATH" from "not installed at all", with actionable install/source guidance (URL + `.cshrc` source hint). It fails loud (exit 1) when unusable, like `lucy lsd check`.
**NOT in Phase 97:** the full platform preflight (Apple-Silicon `arch`/Rosetta probe, `csh`/`tcsh` presence matrix) — that is PORT-01, deliberately kept in Phase 100 so the portability boundary stays clean. Phase 97 `check` may lay the groundwork but must not pull PORT-01 work forward.

> **Research correction to this decision's tool list — read before implementing:** `smileNus` is **not a real, independently-detectable binary**. See "Critical correction" section below. The detection *logic* (SEARCH_PATHS + shutil.which + fail-loud, installed-vs-not-sourced diagnostic) is unaffected and should be implemented exactly as decided; only the *tool name list* and the SMILE-specific check need to change from the CONTEXT.md wording.

**CLI surface in Phase 97 (D-02):** Register only the **implemented** subcommands now — `lucy nus check`, `lucy nus params`, `lucy nus schedule` — in a new `lucy nus` Click group added to `cli/main.py` via `add_command`. `reconstruct` and `pipeline` are added in Phases 98/99 when they actually work. **No dead/"not implemented" stub commands.** `cli/nus.py` stays import-safe (deferred imports inside command bodies, same convention as `cli/webview.py`).

**Test-fixture strategy (D-03):** Copy the real C20H32O2 **metadata text files** — `acqus`, `acqu2s`, `nuslist` for exp2 (COSY), exp3 (HSQC), exp4 (HMBC) — into `tests/fixtures/nus/` (e.g. `tests/fixtures/nus/exp2_cosy/`, `exp3_hsqc/`, `exp4_hmbc/`) so params/schedule tests are self-contained and CI-portable. The large binary `ser` files are **NOT** copied — params/schedule parsing reads only the text metadata, so `ser` is unnecessary weight here (it will matter for reconstruction fixtures in Phase 98, decided separately). These are acquisition-parameter files with no compound identity, so no blind-UAT contamination concern.

**NusAcquisitionParams scope (D-04):** `NusAcquisitionParams` captures a **superset** — the NUS-02 conversion parameters (SFO1, SW_h, TD per dimension, FnMODE, GRPDLY/DECIM, byte order/dtype, NusAMOUNT, NusSEED) **plus** the ppm-calibration parameters Phase-98 processing will need anyway (SF, OFFSET/O1, SW per dimension, F1/F2 nucleus). Parse once in Phase 97 rather than forcing a second parse pass in Phase 98 (RECON-02 reversed ppm axis). Cheap now, avoids duplication.

> **Research note on D-04:** `SF`/`OFFSET` do **not** live in `acqus`/`acqu2s` — they live in the *processing* parameter files `pdata/1/procs` (F2) and `pdata/1/proc2s` (F1), a different file pair entirely. See "SF/OFFSET live in procs, not acqus" finding below — this changes which files `nus/params.py` must open, not just which keys it reads.

### Claude's Discretion

- Whether to reuse `readers/bruker.py`'s `_get_param`/`_get_param_2d`/`_strip_brackets` via a direct underscore-import from within the `nus` package, or promote them to a small shared internal module both import — a one-line structural choice for the planner (ARCHITECTURE.md § Internal Boundaries flags it as non-blocking). Reuse, do not duplicate.
- Exact `NusBackend` protocol shape (Protocol vs ABC), registry API names (`get_backend`, `list_available_backends`), and the `models/nus.py` field naming/validators — planner/executor discretion within the models above.
- Whether the `[nus]` extra is created empty-but-present now or added when the first pip dep appears — planner discretion; core CLI dependency-free is the invariant.

### Deferred Ideas (OUT OF SCOPE)

- Full platform preflight (Apple-Silicon arch/Rosetta, csh/tcsh matrix) → Phase 100 / PORT-01 (kept out of Phase 97 `check` per D-01).
- `lucy nus reconstruct` / `lucy nus pipeline` command bodies → Phases 98/99 (per D-02, not stubbed now).
- `ser`-based reconstruction fixtures (large binaries) → Phase 98 fixture decision (D-03 copies only text metadata).
- Reviewed todos not folded: `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` (unrelated), `2026-06-30-ranking-tests-hardfail-without-hosegen` (unrelated).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NUS-01 | `lucy nus check` detects NMRPipe+SMILE on PATH, fails loud with install guidance; backend never a core `pyproject.toml` dependency | Pattern 1 (below) + the corrected tool list + `nmrPipe -fn SMILE -help` capability-probe pattern; "installed but not sourced" diagnostic design |
| NUS-02 | Bruker acquisition parameters (SFO1, SW_h, TD per dim, FnMODE, GRPDLY/DECIM, byte order/dtype) extracted from `acqus`/`acqu2s` into a validated Pydantic model, per-experiment, never hard-coded | "Exact field names" table + real fixture values below; `_get_param_2d` reuse pattern |
| NUS-03 | Sampling schedule built from `nuslist`, 0-based, acquisition-order-preserved, hard-fail `n_sampled == len(nuslist)` derived from FnMODE | FnMODE→length derivation table with real fixture values; `nmrglue`'s built-in `nuslist` parsing (verified, order-preserving) |
| NUS-04 | `lucy nus params`/`lucy nus schedule` expose JSON, validated against real C20H32O2 exp2/exp3/exp4 fixtures | Exact verified values for all three experiments in the tables below |
| NUS-05 | Core `lucy` CLI stays dependency-free; genuinely pip-installable pieces behind `[nus]` extra with lazy imports | Pattern 2 (below); this phase needs **zero** new pip dependencies (see Package Legitimacy Audit) |
</phase_requirements>

## Summary

Phase 97 is two largely independent, low-risk pieces of work glued together by one shared invariant (core CLI stays import-safe / dependency-free). The params/schedule half is pure-Python, needs zero new dependencies, and can be built and fully unit-tested today against the real C20H32O2 `acqus`/`acqu2s`/`nuslist` files — all of which were re-inspected directly in this research pass (not recalled from training data). The backend-detection half mirrors `LSDRunner`/`lucy lsd check` almost verbatim, with one important correction to the milestone-level architecture research: **`smileNus` is not a real, independently-invokable binary.** SMILE is an NMRPipe *plugin function* (`nmrPipe -fn SMILE`), and its underlying executable (`nusPipe`) is an internal implementation detail wired up via NMRPipe's own plugin-dispatch environment variables — it is not meant to be called or `which`'d directly. `lucy nus check`'s SMILE-availability check must therefore run `nmrPipe -fn SMILE -help` (or equivalent) as a capability probe, not `shutil.which("smileNus")`. This was verified directly against the primary source (the SMILE User's Manual PDF, section 2 "How to obtain the program"), which existing milestone research had flagged as unverified ("PDF fetch issues... re-fetch/verify at implementation time" — SUMMARY.md Research Flags, Phase 2). This research pass resolved that flag.

A second concrete correction/refinement to the milestone architecture: the ppm-calibration fields D-04 asks for (`SF`, `OFFSET`) are **not** in `acqus`/`acqu2s` at all — Bruker splits acquisition parameters (`acqus`/`acqu2s`, what the pulse program used) from processing parameters (`pdata/1/procs`/`pdata/1/proc2s`, what the last processing run calibrated). `nus/params.py` must therefore read from *four* files per experiment (`acqus`, `acqu2s`, `pdata/1/procs`, `pdata/1/proc2s`), and `NusAcquisitionParams` needs to represent that provenance split (or accept the fields may be `None` if `pdata/1/` doesn't exist yet, which is normal for freshly-acquired-but-not-yet-processed NUS data — the real fixture directories confirm `pdata/1/` contains only `procs`/`proc2s`/thumbnails, no processed binary, because NUS data isn't processable until Phase 98 reconstructs it).

Every FnMODE/nuslist-length/byte-order/NusTD fact needed to make NUS-02/03/04 concrete and testable was independently re-verified against the live fixture files in `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/{2,3,4}/` during this research session (not merely copied from the milestone PITFALLS.md, though the values agree). The `nmrglue.bruker.read()` function (already an installed dependency) turns out to parse `nuslist` automatically into an acquisition-ordered list of tuples and to read the raw `ser` file at its *true* physical shape (`TD(F1)` blocks, not the full NUS grid) — a mechanism worth understanding even though Phase 97 only needs the metadata files, because it explains *why* `nuslist` length relates to `acqu2s TD` the way it does (each nuslist row = 1 real block for QF, 2 real blocks for Echo-AntiEcho).

**Primary recommendation:** Build `nus/params.py`/`nus/schedule.py` as pure-Python readers over `ng.bruker.read(expdir)` (reusing `_get_param`/`_get_param_2d`/`_strip_brackets` from `readers/bruker.py` via direct import — acceptable per ARCHITECTURE.md's Internal Boundaries note), deriving `n_sampled` from `acqu2s FnMODE` (1 or other real-only modes → `TD`; 4/5/6 → `TD // 2`) and asserting it equals `len(nuslist)` before any model is considered valid. Build `nus/backends/nmrpipe_smile.py`'s detection as: `shutil.which()` for `nmrPipe`, `bruk2pipe`, `nusExpand.tcl` (three real, independently-callable binaries/scripts), plus a distinct `nmrPipe -fn SMILE -help` subprocess capability-probe for the SMILE plugin itself (not a fourth `which()` target).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backend (NMRPipe+SMILE) detection | External-tool integration (`nus/backends/`) | — | Runtime-detected external binary, never a Python dependency — same tier as `lsd/` (LSDRunner) |
| Bruker acquisition-parameter parsing | Pure-Python data layer (`nus/params.py` → `models/nus.py`) | Readers (`readers/bruker.py`, reused helpers) | Mirrors the existing `readers/bruker.py` param-dict extraction pattern exactly; no external process involved |
| Sampling-schedule parsing (`nuslist`) | Pure-Python data layer (`nus/schedule.py` → `models/nus.py`) | — | File-format parsing + FnMODE-derived validation logic; zero I/O beyond reading a text file |
| CLI surface (`lucy nus check/params/schedule`) | CLI (`cli/nus.py`) | — | Thin Click wrapper over the two tiers above, import-safe per the `[webview]` precedent |
| Optional `[nus]` pip extra | Packaging (`pyproject.toml`) | — | Governs pip-installable pieces only; the backend binary itself is never represented here (Anti-Pattern 1 in ARCHITECTURE.md) |

## Standard Stack

### Core

No new runtime dependencies are required for this phase. `nus/params.py` and `nus/schedule.py` are pure Python built on top of the already-declared `nmrglue` and `pydantic` dependencies.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `nmrglue` | git master (already pinned in `pyproject.toml`, NumPy-2-compatible fork) | Reads `acqus`/`acqu2s`/`nuslist`/`procs`/`proc2s` via `ng.bruker.read()`; already the project's sole Bruker I/O library | Already a core dependency (`readers/bruker.py`); avoids a second Bruker parser |
| `pydantic` | `>=2.0` (already pinned) | `NusAcquisitionParams`/`NusSchedule` models, same convention as `Spectrum1D`/`Spectrum2D`/`Peak1D` | Already the project's sole data-model library |
| `click` | `>=8.0` (already pinned) | `lucy nus` command group | Already the project's sole CLI library |

**Version verification:**
```bash
$ pip show nmrglue pydantic click 2>&1 | grep -E "^(Name|Version):"
```
`nmrglue` is installed from `git+https://github.com/jjhelmus/nmrglue.git` (no PyPI release used, per the existing `pyproject.toml` comment explaining the NumPy-2 `np.dtype('a8')` incompatibility of the last PyPI release). This phase adds no new dependency, so no new version-verification is needed beyond confirming the already-pinned versions still resolve (`pip install -e .` succeeding is sufficient evidence).

### Supporting

None. This phase's only I/O is reading local text files (`acqus`, `acqu2s`, `nuslist`, `procs`, `proc2s`) and calling `shutil.which`/`subprocess.run` for backend detection — both stdlib.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `nmrglue.bruker.read()` for acqus/acqu2s/nuslist parsing | Hand-rolled text parser (regex over `##$KEY= value` lines) | `nmrglue` already handles bracket-stripping, numeric coercion, and automatic `nuslist` parsing (verified: returns an acquisition-ordered `list[tuple[int, ...]]`) correctly; hand-rolling reintroduces exactly the class of bug (ad-hoc Bruker parsing) this milestone exists to move away from. Existing `readers/bruker.py` already made this choice — Phase 97 should not diverge. |
| `shutil.which("smileNus")` for SMILE detection | `subprocess.run(["nmrPipe", "-fn", "SMILE", "-help"])` capability probe | `shutil.which` cannot detect a plugin function baked into another binary's dispatch table — see Critical correction below. This is not a stylistic choice, it is a correctness requirement. |

**Installation:** No installation step — no new packages.

## Package Legitimacy Audit

**No new external packages are introduced by this phase.** `nmrglue`, `pydantic`, and `click` are pre-existing, already-audited core dependencies (see `pyproject.toml` `dependencies` list); the `nus/` package and `models/nus.py` are pure additions written in-repo. No `pip install` step is part of this phase's plan.

If the planner elects to create the `[nus]` pyproject extra now (per Claude's Discretion, "empty-but-present"), it should contain **zero packages** in Phase 97 — an empty `nus = []` list mirroring the empty `prediction = []` extra already present in `pyproject.toml` (see file, lines 56-60) — since D-04's superset is entirely pure-Python and NUS-05 only requires the extra to *exist* as a scaffold, not to hold a dependency yet.

*Package Legitimacy Gate: N/A — no packages to check.*

## Architecture Patterns

### System Architecture Diagram

```
Bruker NUS experiment dir (e.g. <compound>/3/)
  ├── acqus, acqu2s        (acquisition parameters — SFO1, SW_h, TD, FnMODE, GRPDLY, DECIM, BYTORDA, DTYPA, NusAMOUNT, NusSEED, NusTD)
  ├── nuslist               (sampling schedule — 0-based t1-grid indices, ACQUISITION order, not sorted)
  └── pdata/1/procs, proc2s (processing/calibration parameters — SF, OFFSET; present even before reconstruction)
        │
        ▼
┌─────────────────────────────┐        ┌──────────────────────────────┐
│ nus/params.py                │        │ nus/schedule.py               │
│  ng.bruker.read(expdir)      │        │  ng.bruker.read(expdir)       │
│  + pdata procs/proc2s read   │        │  (or direct nuslist text read)│
│  -> NusAcquisitionParams     │        │  n_sampled = f(FnMODE, TD)    │
│     (validated Pydantic v2)  │        │  assert n_sampled==len(nuslist)│
│                               │        │  -> NusSchedule (validated)   │
└──────────────┬───────────────┘        └───────────────┬───────────────┘
               │                                          │
               ▼                                          ▼
        cli/nus.py: `lucy nus params <expdir> --format json`
        cli/nus.py: `lucy nus schedule <expdir> --format json`
               (both write/echo JSON; Phase 98 consumes both models)

Independent, parallel path — backend availability (no data dependency):

  PATH / filesystem
        │
        ▼
┌───────────────────────────────────┐
│ nus/backends/nmrpipe_smile.py      │
│  shutil.which("nmrPipe")           │
│  shutil.which("bruk2pipe")         │
│  shutil.which("nusExpand.tcl")     │
│  subprocess: nmrPipe -fn SMILE -help│  <- capability probe, NOT which()
│  -> is_available() / missing_tools()│
└──────────────┬─────────────────────┘
               ▼
        cli/nus.py: `lucy nus check` (exit 1 + install guidance if unusable)
```

### Recommended Project Structure

```
src/lucy_ng/
├── nus/                          # NEW top-level package (sibling of lsd/, webview/, readers/)
│   ├── __init__.py                # re-exports for cli/nus.py
│   ├── params.py                  # acqus/acqu2s/procs/proc2s -> NusAcquisitionParams
│   ├── schedule.py                # nuslist -> NusSchedule (FnMODE-derived length assertion)
│   └── backends/
│       ├── __init__.py            # NusBackend Protocol, get_backend(), list_available_backends()
│       └── nmrpipe_smile.py       # is_available(), missing_tools(), SMILE-plugin capability probe
├── models/
│   └── nus.py                     # NEW: NusAcquisitionParams, NusSchedule (Pydantic v2)
├── readers/
│   └── bruker.py                  # UNCHANGED (nus/params.py imports _get_param/_get_param_2d directly)
├── cli/
│   └── nus.py                     # NEW: `lucy nus` group — check/params/schedule only (D-02)
└── ...                            # everything else unchanged
tests/
├── fixtures/
│   └── nus/
│       ├── exp2_cosy/{acqus,acqu2s,nuslist}
│       ├── exp3_hsqc/{acqus,acqu2s,nuslist}
│       └── exp4_hmbc/{acqus,acqu2s,nuslist}
├── test_nus_params.py             # NEW
├── test_nus_schedule.py           # NEW
├── test_nus_backends.py           # NEW
└── test_cli_nus.py                # NEW
```

### Pattern 1: External-binary detection — corrected for SMILE's plugin architecture

**What:** Two-tier detection. Tier 1 (real, independent binaries): `shutil.which()` over `["nmrPipe", "bruk2pipe", "nusExpand.tcl"]`, exactly the `LSDRunner.SEARCH_PATHS` + `shutil.which` pattern. Tier 2 (SMILE plugin capability): run `nmrPipe -fn SMILE -help` as a subprocess and check for success — this is how the SMILE manual itself instructs users to verify the plugin is installed ("To test if SMILE is properly installed on a computer, one can enter `nmrPipe -fn SMILE -help` on a terminal").

**When to use:** Any time a tool is delivered as a *function inside* another CLI (NMRPipe's `-fn` plugin dispatch), `shutil.which()` alone cannot detect it — the plugin executable (`nusPipe`) is looked up internally by NMRPipe via its own `$NMRBASE`/environment-variable mechanism (`NMR_PLUGIN_EXE=nusPipe`), not via the shell `PATH` in a way a user or `which` would normally probe.

**Critical correction (why this matters — read before implementing D-01):**
The milestone-level architecture research (`.planning/research/ARCHITECTURE.md` Pattern 1 example) and this phase's own CONTEXT.md both list `REQUIRED_TOOLS = ["nmrPipe", "smileNus", "nusExpand.tcl", "bruk2pipe"]`. **`smileNus` is not a real binary name.** This was flagged as an open research gap in SUMMARY.md ("exact `nmrPipe -fn SMILE` flag syntax... not independently verified... re-fetch/verify at implementation time") and has now been resolved by fetching the primary source directly:

> "The SMILE processing function is available as a plug-in for the NMRPipe package... File 4 (`plugin.smile.tZ`) must be downloaded... This plug-in file includes the actual executable program (`nusPipe`)... the following... environment variables are set... `setenv NMR_PLUGIN_FN SMILE` / `setenv NMR_PLUGIN_EXE nusPipe`... To test if SMILE is properly installed... enter `nmrPipe -fn SMILE -help`."
> — SMILE User's Manual, §1–2 [CITED: spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf]

So: `nusPipe` is the real underlying executable, but it is an NMRPipe-internal implementation detail invoked via plugin dispatch, not a user-facing command — checking `shutil.which("nusPipe")` is unreliable (its location is inside `$NMRBASE/nmrbin.*/`, which may or may not be separately on `PATH`) and checking `shutil.which("smileNus")` will always fail (no such binary exists under that name, on any platform, per this primary source). The correct, manual-endorsed detection is the subprocess capability probe.

**Example:**
```python
# nus/backends/nmrpipe_smile.py
import shutil
import subprocess


class NmrPipeSmileBackend:
    """NMRPipe + SMILE reconstruction backend (external, runtime-detected)."""

    # Real, independently-`which`-able binaries/scripts.
    REQUIRED_TOOLS = ["nmrPipe", "bruk2pipe", "nusExpand.tcl"]

    @classmethod
    def missing_tools(cls) -> list[str]:
        """Tools from REQUIRED_TOOLS not found on PATH."""
        return [t for t in cls.REQUIRED_TOOLS if shutil.which(t) is None]

    @classmethod
    def smile_plugin_available(cls) -> bool:
        """SMILE is an nmrPipe plugin function, not a standalone binary.

        Detected via capability probe (per the SMILE manual's own
        recommended verification command), not shutil.which().
        """
        if shutil.which("nmrPipe") is None:
            return False
        try:
            proc = subprocess.run(
                ["nmrPipe", "-fn", "SMILE", "-help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        # SMILE's -help prints its own usage block ("SMILE: Sparse
        # Multidimensional Iterative Lineshape Enhanced.") on success;
        # a missing plugin causes nmrPipe to report an unknown function.
        combined = (proc.stdout + proc.stderr).lower()
        return "smile" in combined and "unknown function" not in combined

    @classmethod
    def is_available(cls) -> bool:
        return not cls.missing_tools() and cls.smile_plugin_available()
```

**Trade-offs:** The capability probe adds a ~subprocess-launch cost (~10-50ms) to `lucy nus check` versus a pure `shutil.which()` check, and requires parsing `-help` output text rather than a boolean file-exists check — inherently less robust to upstream text changes than a binary-presence check, but this is the only mechanism the tool itself exposes and is exactly what the manual instructs users to run.

### Pattern 2: `[nus]` pyproject extra — empty scaffold, following `[prediction]` precedent

**What:** `pyproject.toml` already contains a precedent for an *empty* optional-dependencies entry with an explanatory comment (`prediction = []`, lines 56-60) — not just the non-empty `[webview]` extra. Phase 97's `[nus]` extra should follow the empty-scaffold precedent, since D-04's params/schedule superset needs zero new pip packages.

**When to use:** When NUS-05's invariant ("core CLI dependency-free") must be documented and structurally enforced even though no dependency exists yet.

**Example:**
```toml
[project.optional-dependencies]
# ... existing entries ...
nus = [
    # No dependencies yet — NUS-01..05 (Phase 97) use only nmrglue/pydantic/click,
    # already core dependencies. Reserved for Phase 98/99 pip-installable pieces
    # (e.g. QC-plotting deps), following the [webview] extra's lazy-import pattern.
]
```

**Trade-offs:** An empty list has no functional effect (`pip install lucy-ng[nus]` installs nothing extra) but documents intent and gives Phase 98/99 a place to add dependencies without a `pyproject.toml` restructure.

### Anti-Patterns to Avoid

- **Treating `smileNus` as a real binary to `which()`:** See Pattern 1 correction above — this will make `lucy nus check` report "not found" even on a correctly-installed NMRPipe+SMILE system, an outright false negative.
- **Reading SF/OFFSET from `acqus`/`acqu2s`:** These keys do not exist there (verified: `grep -E '\$(SF|OFFSET)=' acqus acqu2s` returns nothing for all three real experiments). They live in `pdata/1/procs`/`pdata/1/proc2s`. Silently defaulting to `None` without reading the correct file is a data-completeness bug, not a "field genuinely absent" case.
- **Deriving `n_sampled` from `max(nuslist) + 1`** instead of reading `acqu2s NusTD` directly. `NusTD` is a real, authoritative Bruker parameter giving the exact full-grid size (verified: 750/400/700 for exp2/3/4, matching the guide's table exactly) — inferring it from the sampled-index maximum is a fragile heuristic that happens to work on this dataset (because the last grid point was sampled) but is not guaranteed in general.
- **Assuming `read_pdata()` works on a NUS experiment directory:** It raises `OSError: No Bruker binary file could be found` — verified directly (`3/pdata/1/` contains only `procs`/`proc2s`/`clevels`/`thumb.png`, no `1r`/`2rr`). NUS data cannot be processed until Phase 98 reconstructs it; `nus/params.py` must use `ng.bruker.read(expdir)` (reads raw `acqus`/`acqu2s`/`nuslist`/`ser`), never `ng.bruker.read_pdata()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bruker `acqus`/`acqu2s`/`nuslist` text parsing | A regex-based `##$KEY= value` parser | `ng.bruker.read(expdir)` (already installed) — parses all of `acqus`, `acqu2s`, `nuslist`, `procs`, `proc2s` into a single `dic` in one call, auto-strips `<angle brackets>`, auto-parses `nuslist` into an ordered `list[tuple[int, ...]]` | Verified directly: `ng.bruker.read()` already returns `dic['nuslist']` correctly acquisition-ordered (not sorted) — re-implementing this risks reintroducing the sorting bug PITFALLS.md Pitfall 3 warns about |
| SMILE backend availability check | A `shutil.which("smileNus")`-style check | The `nmrPipe -fn SMILE -help` capability probe (Pattern 1) | No standalone `smileNus` binary exists; the manual's own recommended verification command is the capability probe |

**Key insight:** Both "don't hand-roll" items above are really the same lesson: this domain (Bruker parameter files, NMRPipe plugin architecture) already has a canonical, already-installed way to introspect itself (`nmrglue` for data files, `nmrPipe -fn X -help` for plugin functions) — every hand-rolled shortcut around either one has already been shown, in this research pass, to diverge from ground truth in a way that would silently misreport availability or misparse a parameter.

## Exact Bruker Field Names — Verified Against Real C20H32O2 Fixtures

All values below were read directly from `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/{2,3,4}/{acqus,acqu2s,pdata/1/procs,pdata/1/proc2s,nuslist}` on 2026-07-12 — `[VERIFIED: direct fixture inspection]` for every cell in these three tables.

### Acquisition parameters (`acqus` = F2/direct, `acqu2s` = F1/indirect)

| Field | File | exp2 (COSY) | exp3 (HSQC) | exp4 (HMBC) | Notes |
|-------|------|-------------|-------------|-------------|-------|
| `PULPROG` | acqus | `cosygpmfppqf` | `hsqcedetgpsp.3` | `hmbcetgpl3nd` | angle-bracketed string, strip via `_strip_brackets` |
| `NUC1` (F2) | acqus | `1H` | `1H` | `1H` | |
| `SFO1` (F2) | acqus | 499.92164974 | 499.92164974 | 499.92164974 | MHz |
| `SW_h` (F2) | acqus | 3750 | 3750 | 3750 | Hz |
| `TD` (F2) | acqus | 2048 | 2048 | 2048 | real+imag interleaved points, direct dim |
| `BYTORDA` | acqus | 0 (little-endian) | 0 | 0 | read per-experiment, never hard-code |
| `DTYPA` | acqus | 0 (int32) | 0 | 0 | |
| `DIGTYP` | acqus | 12 | 12 | 12 | |
| `DECIM` | acqus | 5333.33333333333 | 5333.33333333333 | 5333.33333333333 | |
| `DSPFVS` | acqus | 20 | 20 | 20 | |
| `GRPDLY` | acqus | 67.9851531982422 | 67.9851531982422 | 67.9851531982422 | **non-integer** — see PITFALLS.md Pitfall 3 |
| `NusAMOUNT` | acqus | 25 | 25 | 33 | percent |
| `NusSEED` | acqus | 54321 | 54321 | 54321 | |
| `NUC1` (F1) | acqu2s | `1H` | `13C` | `13C` | **differs by experiment — never hard-code the nucleus** |
| `SFO1` (F1) | acqu2s | 499.92164974 | 125.715668907639 | 125.719440057158 | MHz — note exp3≠exp4 despite both being ¹³C (slightly different reference/shim between acquisitions) |
| `SW_h` (F1) | acqu2s | 3750.93773443361 | 22624.4343891403 | 30120.4819277108 | Hz |
| `O1` (F1) | acqu2s | 1649.74000000484 | 10684.9236386353 | 14456.0731581578 | Hz, carrier offset |
| `TD` (F1) | acqu2s | 188 | 100 | 232 | **this is the field the FnMODE-length rule below operates on** |
| `FnMODE` | acqu2s | 1 (QF) | 6 (Echo-AntiEcho) | 6 (Echo-AntiEcho) | **the F1-dimension FnMODE — `acqus FnMODE` is always 0 for all three experiments and is NOT the value to branch on; only `acqu2s FnMODE` matters** |
| `NusTD` | acqu2s | 750 | 400 | 700 | **full NUS grid size — authoritative, do not infer from `max(nuslist)+1`** |

> **Trap already present in the real data, worth flagging explicitly for the planner:** `acqus` (F2, direct dimension) *also* has a key literally named `FnMODE`, and its value is `0` for all three experiments — this is a vestigial/irrelevant field for a 1D-context acquisition parameter file. Code that reads "the FnMODE" without specifying `acqu2s` (not `acqus`) will silently read `0` for every experiment and derive `n_sampled = TD` unconditionally (the QF branch), which happens to be correct for exp2 but silently wrong for exp3/exp4. This is a sharper, more concrete version of PITFALLS.md Pitfall 1 — the bug is not just "assuming one relationship for all experiments," it is "reading the wrong file's namesake key entirely." `NusAcquisitionParams` field naming should make the F1/F2 distinction unambiguous (e.g. `fnmode_f1: int` not `fnmode: int`).

### Processing/calibration parameters — separate files, present even pre-reconstruction

| Field | File | exp2 F2 | exp2 F1 | exp3 F2 | exp3 F1 | exp4 F2 | exp4 F1 |
|-------|------|---------|---------|---------|---------|---------|---------|
| `SF` | `pdata/1/procs` (F2) / `pdata/1/proc2s` (F1) | 499.92 | 499.92 | 499.92 | 125.704983984 | 499.92 | 125.704983984 |
| `OFFSET` | same | 7.050608 | 7.051546 | 7.050608 | 174.9902 | 7.050608 | 234.8062 |

`[VERIFIED: direct fixture inspection]` — `pdata/1/` exists and contains `procs`/`proc2s` for all three NUS experiment directories even though no processed binary (`1r`/`2rr`) exists yet (NUS data is not processable until Phase 98's reconstruction). `nus/params.py` must open these two additional files per experiment; `readers/bruker.py`'s existing `_get_param_2d(dic, param_dict, key)` helper signature already generalizes to this (call with `param_dict="procs"`/`"proc2s"` instead of `"acqus"`/`"acqu2s"`) provided `ng.bruker.read()`'s returned `dic` is used (it already includes `procs`/`proc2s` keys — verified: `sorted(dic.keys())` includes `'proc2s'`, `'procs'` alongside `'acqus'`, `'acqu2s'`, `'nuslist'`, `'pprog'`).

### FnMODE → sampled-count derivation rule (the correctness crux — NUS-03)

| Exp | Type | `acqu2s FnMODE` | `acqu2s TD` | Rule | Computed `n_sampled` | `len(nuslist)` | Assert passes? |
|-----|------|------------------|-------------|------|----------------------|-----------------|-----------------|
| 2 | COSY | 1 (QF) | 188 | `n_sampled = TD` | 188 | 188 | ✓ `188 == 188` |
| 3 | HSQC | 6 (Echo-AntiEcho) | 100 | `n_sampled = TD // 2` | 50 | 50 | ✓ `50 == 100 // 2` |
| 4 | HMBC | 6 (Echo-AntiEcho) | 232 | `n_sampled = TD // 2` | 116 | 116 | ✓ `116 == 232 // 2` |

`[VERIFIED: direct fixture inspection]` — `wc -l nuslist` and `grep '\$TD=' acqu2s` re-confirmed independently of PITFALLS.md's own numbers (they agree). Derivation rule, restated precisely for implementation: `FnMODE` values 1 (QF) and 2 (QSEQ) are real-only → `n_sampled = TD`; `FnMODE` values 4 (States), 5 (States-TPPI), 6 (Echo-AntiEcho) are complex-pair → `n_sampled = TD // 2`. This dataset only exercises FnMODE 1 and 6, so the assertion logic should raise `NotImplementedError` (not silently guess) for any `FnMODE` not in `{1, 2, 4, 5, 6}` rather than defaulting either way — a genuinely new FnMODE in a future NUS CASE compound must fail loud, not silently misparse.

### `nuslist` acquisition-order verification

`[VERIFIED: direct fixture inspection]` — first 8 rows of each file, confirming non-ascending (acquisition) order, per PITFALLS.md Pitfall 2/3:

```
exp2 (COSY):  0, 124, 431, 670, 369, 53, 211, 120, ...   (max index: 748, grid size NusTD=750)
exp3 (HSQC):  0, 33, 115, 178, 98, 14, 199, 56, ...       (max index: 199, grid size NusTD=400... )
exp4 (HMBC):  0, 58, 201, 312, 172, 24, 348, 98, ...      (max index: 349, grid size NusTD=700)
```

Note the apparent mismatch for exp3: `max(nuslist)=199` but `NusTD=400`. This is expected and *not* a bug: `NusTD` counts the full grid in the same real-point units as `acqu2s TD` (i.e. `NusTD` is on the same "real points" scale as `TD`, so for a complex/Echo-AntiEcho experiment the *complex-pair* grid size is `NusTD // 2 = 200`, and `nuslist` values (which index complex pairs, 0-based) correctly range `0..199` for a grid of 200 slots). This is the same real-vs-complex distinction as the `TD`→`n_sampled` rule above, applied one level up to the grid size — reinforcing that every `TD`/`NusTD`-derived count in this domain must be run through the same FnMODE-aware real/complex conversion, not just the sampled-count assertion. Flag this explicitly in `NusSchedule`'s docstring/field documentation so a future maintainer doesn't "fix" the apparent off-by-half mismatch incorrectly.

`ng.bruker.read()` independently confirms acquisition-order (not sorted) parsing — verified via direct call: `dic['nuslist'][:10]` for exp2 returns `[(0,), (124,), (431,), (670,), (369,), (53,), (211,), (120,), (101,), (37,)]`, matching the raw file's row order exactly, as a list of 1-tuples (nmrglue's `nuslist` representation is one tuple per row, ready to generalize to multi-dimensional NUS schedules even though this project's schedules are single-column).

### `ser` block-count sanity check (context, not required for Phase 97 but explains *why* the TD/nuslist relationship exists)

`[VERIFIED: direct fixture inspection]` — `ser` file sizes divided by the per-block byte size (`TD(F2) × 4 bytes` for int32, from `DTYPA=0`) equal exactly `acqu2s TD`, not `NusTD`:

| Exp | `ser` bytes | Block bytes (`2048 × 4`) | Blocks in `ser` | `acqu2s TD` |
|-----|-------------|----------------------------|-------------------|--------------|
| 2 | 1,540,096 | 8,192 | 188 | 188 ✓ |
| 3 | 819,200 | 8,192 | 100 | 100 ✓ |
| 4 | 1,900,544 | 8,192 | 232 | 232 ✓ |

This confirms the raw `ser` file on disk already contains *only the actually-acquired* blocks (sparse), sized to `acqu2s TD`, not the full `NusTD` grid — `ng.bruker.read()` reading `ser` at this "sparse" shape (verified: `data.shape == (100, 1024)` for exp3, i.e. `(TD, TD(F2)//2)` complex points) is therefore correct as-is; the *expansion* to the full `NusTD` grid (zero-filling unsampled positions per the schedule) is Phase 98's job (`nusExpand.tcl`), not Phase 97's. Phase 97 only needs to parse and validate the schedule, not apply it.

## Code Examples

### `nus/params.py` — reading acqus/acqu2s/procs/proc2s in one call

```python
# Source: verified against installed nmrglue 0.11 (git master) + real C20H32O2 fixtures
import nmrglue as ng
from lucy_ng.readers.bruker import _get_param_2d, _strip_brackets  # reuse, don't duplicate

def read_nus_params(expdir: str) -> dict:
    dic, data = ng.bruker.read(expdir)  # NOT read_pdata() — no processed binary exists yet
    return {
        "pulse_program": _strip_brackets(dic["acqus"]["PULPROG"]),
        "f2_nucleus": _strip_brackets(dic["acqus"]["NUC1"]),
        "f2_sfo1": dic["acqus"]["SFO1"],
        "f2_sw_h": dic["acqus"]["SW_h"],
        "f2_td": dic["acqus"]["TD"],
        "byte_order": dic["acqus"]["BYTORDA"],
        "dtype_code": dic["acqus"]["DTYPA"],
        "decim": dic["acqus"]["DECIM"],
        "dspfvs": dic["acqus"]["DSPFVS"],
        "grpdly": dic["acqus"]["GRPDLY"],  # non-integer — store as float, do not round
        "nus_amount_pct": dic["acqus"]["NusAMOUNT"],
        "nus_seed": dic["acqus"]["NusSEED"],
        "f1_nucleus": _strip_brackets(dic["acqu2s"]["NUC1"]),
        "f1_sfo1": dic["acqu2s"]["SFO1"],
        "f1_sw_h": dic["acqu2s"]["SW_h"],
        "f1_o1": dic["acqu2s"]["O1"],
        "f1_td": dic["acqu2s"]["TD"],
        "fnmode_f1": dic["acqu2s"]["FnMODE"],  # acqu2s, NOT acqus — see trap note above
        "nus_td": dic["acqu2s"]["NusTD"],
        # Calibration — separate files (procs/proc2s), present pre-reconstruction:
        "f2_sf": dic["procs"]["SF"],
        "f2_offset": dic["procs"]["OFFSET"],
        "f1_sf": dic["proc2s"]["SF"],
        "f1_offset": dic["proc2s"]["OFFSET"],
    }
```

### `nus/schedule.py` — FnMODE-derived hard-fail assertion

```python
# Source: derived from PITFALLS.md Pitfall 1 + this research's direct fixture verification
REAL_FNMODES = {1, 2}       # QF, QSEQ
COMPLEX_FNMODES = {4, 5, 6}  # States, States-TPPI, Echo-AntiEcho

def expected_sample_count(fnmode: int, td_f1: int) -> int:
    if fnmode in REAL_FNMODES:
        return td_f1
    if fnmode in COMPLEX_FNMODES:
        return td_f1 // 2
    raise NotImplementedError(
        f"FnMODE={fnmode} is not a recognized real/complex mode; "
        "refusing to guess a sample-count relationship."
    )

def validate_schedule(fnmode: int, td_f1: int, nuslist: list[int]) -> None:
    n_sampled = expected_sample_count(fnmode, td_f1)
    if n_sampled != len(nuslist):
        raise ValueError(
            f"NUS schedule length mismatch: FnMODE={fnmode} implies "
            f"n_sampled={n_sampled} (from TD={td_f1}), but nuslist has "
            f"{len(nuslist)} entries. Refusing to proceed — never sort, "
            "regenerate, or silently truncate/pad the schedule."
        )
```

### `nus/backends/nmrpipe_smile.py` — `lucy nus check` diagnostic states (D-01)

```python
# Source: LSDRunner precedent (src/lucy_ng/lsd/runner.py) + SMILE manual capability-probe pattern
import shutil

def diagnose() -> dict:
    """Distinguish 'not installed' from 'installed but not on PATH / env not sourced'."""
    missing = NmrPipeSmileBackend.missing_tools()
    if not missing:
        smile_ok = NmrPipeSmileBackend.smile_plugin_available()
        return {"status": "available" if smile_ok else "smile_plugin_missing",
                "missing_tools": [], "smile_available": smile_ok}
    # Distinct diagnostic: is nmrPipe present anywhere common but not on PATH?
    # (mirrors LSDRunner.SEARCH_PATHS fallback, adapted to NMRPipe's $NMRBASE convention)
    common_nmrbase = ["~/.nmrpipe", "~/nmrpipe", "/opt/nmrpipe"]
    hint_found = any(__import__("pathlib").Path(p).expanduser().exists() for p in common_nmrbase)
    return {
        "status": "installed_not_sourced" if hint_found else "not_installed",
        "missing_tools": missing,
        "smile_available": False,
        "hint": (
            "NMRPipe appears installed but its tools are not on PATH — "
            "did you source its environment? Typically: `source ~/.nmrpipe/com/nmrInit.<platform>.com` "
            "or the equivalent line added to `.cshrc` by NMRPipe's own install.com. "
            "Install docs: https://www.ibbr.umd.edu/nmrpipe/install"
            if hint_found else
            "NMRPipe not found. Install (free registration required): "
            "https://www.ibbr.umd.edu/nmrpipe/install"
        ),
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Ad-hoc per-column IST in `nmrglue` (this project's own prior approach, root cause of the 2026-07-09 CASE failure) | Delegated to a real, validated backend (NMRPipe+SMILE, external subprocess) | This milestone (v10.0) | Phase 97 lays the pure-Python groundwork (params/schedule); the actual reconstruction delegation happens in Phase 98 |
| Assuming `nmrPipe -fn SMILE` flag syntax and plugin architecture (SUMMARY.md flagged this as unverified) | Confirmed: SMILE is an NMRPipe plugin (`plugin.smile.tZ`), invoked via `-fn SMILE`, underlying binary `nusPipe` is internal | Verified in this research pass (2026-07-12), via the primary SMILE manual PDF | Corrects Phase 97's `lucy nus check` design (Pattern 1 above) and pre-empts a Phase 98 backend-invocation mistake before it happens |

**Deprecated/outdated:** The `REQUIRED_TOOLS` list containing `"smileNus"` in `.planning/research/ARCHITECTURE.md` (Pattern 1 code example) and `97-CONTEXT.md` (D-01 wording) — both predate this research pass's primary-source verification and should be treated as superseded by this document for implementation purposes. The *decision* (backend detection, fail-loud, installed-vs-not-sourced diagnostic) is unaffected; only the tool-name list changes.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `nusExpand.tcl` is directly `shutil.which()`-discoverable on PATH after a standard NMRPipe install (i.e. it is installed as an executable script in a PATH-included directory, not requiring `tclsh nusExpand.tcl` invocation) | Pattern 1, Standard Stack | If wrong, `lucy nus check` would report a false "missing tool" for a correctly-installed system; low severity (a install-time diagnostic wording issue, not a data-correctness issue) — mitigate by having Phase 98's first real integration test (which needs a live NMRPipe install) confirm this empirically, and adjusting the check if `nusExpand.tcl` turns out to need a `tclsh` wrapper invocation instead |
| A2 | The `nmrPipe -fn SMILE -help` capability-probe's stdout/stderr reliably contains the substring "smile" (case-insensitive) on success across NMRPipe versions, and an "unknown function"-style message on failure | Pattern 1 | If the exact wording differs across NMRPipe releases, the probe could false-positive or false-negative; mitigate by making the probe's exact success/failure string matching a config-adjustable constant reviewed against the actual installed version the first time a real system is available (this project's own dev Mac does not yet have NMRPipe installed per the task brief §4) |
| A3 | `FnMODE` values 1 and 2 (QSEQ) both map to the real/`n_sampled=TD` branch identically (this dataset only exercises FnMODE=1, never verified FnMODE=2 directly) | FnMODE derivation table | Low risk — QSEQ is a documented real-mode variant of QF in the Bruker parameter reference; if wrong, a future QSEQ-acquired NUS experiment would need its own row, caught immediately by the hard-fail assertion (fails loud, not silently) |

## Open Questions

1. **Does `nusExpand.tcl` require a `tclsh` wrapper, or is it directly executable?**
   - What we know: The SMILE manual references it as a script name (`nusExpand.tcl`) alongside `nusZF.com`, implying a Tcl-scripted tool typically invoked as `nusExpand.tcl <args>` directly (has a `#!/usr/bin/env tclsh`-style shebang, common for NMRPipe's Tcl utilities).
   - What's unclear: Exact PATH/shebang behavior across the Linux vs Mac NMRPipe distributions was not independently confirmed (no live NMRPipe install exists on this project's dev machine per the task brief §4).
   - Recommendation: Treat as A1 above — low-risk, self-correcting at Phase 98's first live integration test; do not block Phase 97 on this.

2. **Exact wording of `nmrPipe`'s "unknown function" error for a missing SMILE plugin.**
   - What we know: NMRPipe's `-fn` dispatch presumably errors distinctly when a requested function isn't registered (SMILE isn't compiled in without the plugin).
   - What's unclear: The exact error string was not observed directly (no test system available).
   - Recommendation: A2 above — implement the probe now with a best-effort string match, and treat this as a "verify at Phase 98/first real install" item, since Phase 97's `lucy nus check` failing loud with *some* diagnostic message (even an imperfect one) is still strictly better than the current state (no check exists at all).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `nmrglue` (Python) | `nus/params.py`, `nus/schedule.py` | ✓ | installed from git master, confirmed importable and functional against real fixtures in this research session | — |
| `pydantic` | `models/nus.py` | ✓ (already core dep) | `>=2.0` per `pyproject.toml` | — |
| `nmrPipe` (external binary) | `lucy nus check` (NUS-01) — **detection only in Phase 97, no invocation** | ✗ (per task brief §4: "NICHT installiert: nmrPipe, bruk2pipe, topspin, mddnmr" on the dev Mac) | — | None needed for Phase 97 — `lucy nus check` is *expected* to correctly report "not available" on this machine right now; that correct-negative-report is itself a validatable Phase 97 acceptance criterion. Real installation is a Phase 98 prerequisite, not Phase 97's. |
| `bruk2pipe`, `nusExpand.tcl` (external) | `lucy nus check` | ✗ | — | Same as above |
| `csh`/`tcsh` | NMRPipe's own install/invocation model (not directly used by Phase 97 code) | ✓ (per task brief §4: already present on the dev Mac) | — | Not exercised by Phase 97; relevant starting Phase 98 |

**Missing dependencies with no fallback:** None — Phase 97 does not require the NMRPipe backend to be installed; `lucy nus check` reporting "not available" on this machine is the *correct*, testable behavior for this phase.

**Missing dependencies with fallback:** N/A.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (per `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing, no new config needed) |
| Quick run command | `pytest tests/test_nus_params.py tests/test_nus_schedule.py tests/test_nus_backends.py tests/test_cli_nus.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| NUS-01 | `lucy nus check` reports unavailable + diagnostic on this machine (no NMRPipe installed) | unit + CLI | `pytest tests/test_nus_backends.py tests/test_cli_nus.py -k check -x` | ❌ Wave 0 |
| NUS-01 | `lucy nus check` exits 1 when unusable | CLI | `pytest tests/test_cli_nus.py -k check_exit_code -x` | ❌ Wave 0 |
| NUS-02 | `NusAcquisitionParams` extracts correct SFO1/SW_h/TD/FnMODE/GRPDLY/byte-order for all three fixtures | unit | `pytest tests/test_nus_params.py -x` | ❌ Wave 0 |
| NUS-03 | `n_sampled == len(nuslist)` assertion passes for FnMODE 1 (exp2) and FnMODE 6 (exp3, exp4); raises for an unrecognized FnMODE | unit | `pytest tests/test_nus_schedule.py -x` | ❌ Wave 0 |
| NUS-03 | `nuslist` parsed in acquisition order, never sorted (regression fixture using exp2's known unsorted order) | unit | `pytest tests/test_nus_schedule.py -k acquisition_order -x` | ❌ Wave 0 |
| NUS-04 | `lucy nus params`/`lucy nus schedule --format json` produce schema-valid JSON for all three fixtures | CLI | `pytest tests/test_cli_nus.py -k "params or schedule" -x` | ❌ Wave 0 |
| NUS-05 | `pip install lucy-ng` (core only) still imports `lucy_ng.cli` without error (import-safety of `cli/nus.py`) | unit | `pytest tests/test_cli_main.py -k nus_import_safe -x` (new test to add to the existing collect-safety pattern) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_nus_*.py tests/test_cli_nus.py -x`
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/fixtures/nus/exp2_cosy/{acqus,acqu2s,nuslist}` — copy from real C20H32O2 exp2 (D-03)
- [ ] `tests/fixtures/nus/exp3_hsqc/{acqus,acqu2s,nuslist}` — copy from real C20H32O2 exp3 (D-03)
- [ ] `tests/fixtures/nus/exp4_hmbc/{acqus,acqu2s,nuslist}` — copy from real C20H32O2 exp4 (D-03)
- [ ] `tests/test_nus_params.py` — covers NUS-02
- [ ] `tests/test_nus_schedule.py` — covers NUS-03
- [ ] `tests/test_nus_backends.py` — covers NUS-01
- [ ] `tests/test_cli_nus.py` — covers NUS-01, NUS-04, NUS-05
- [ ] Framework install: none — pytest already configured project-wide

**Note on D-03 fixture copying:** copy only `acqus`, `acqu2s`, `nuslist` — do NOT copy `pdata/1/procs`/`pdata/1/proc2s`, unless the planner decides `NusAcquisitionParams`'s SF/OFFSET fields need fixture coverage too (recommended: also copy these two small text files per experiment, since D-04 explicitly requires SF/OFFSET in the model and this research found they live in a different directory than D-03's stated file list anticipated — `pdata/1/procs`/`pdata/1/proc2s` are themselves small text files, not binaries, so copying them does not violate D-03's "no large binary `ser` files" constraint).

## Security Domain

No `security_enforcement` key is set in `.planning/config.json`; per the default-enabled rule, a lightweight domain check is included. This phase has no network surface, no authentication, and no user-facing input beyond local filesystem paths supplied via CLI arguments — the applicable ASVS surface is narrow.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | No auth surface in this phase |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes | Pydantic v2 `NusAcquisitionParams`/`NusSchedule` validate all parsed Bruker fields (types, the FnMODE-derived hard-fail assertion); CLI path arguments use Click's `type=click.Path(exists=True)` pattern already used elsewhere in the codebase (e.g. `cli/lsd.py` `lsd_run`) |
| V6 Cryptography | No | N/A — no crypto operations in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Path traversal via a malicious `<expdir>` CLI argument | Tampering | `click.Path(exists=True)` + `Path(expdir).resolve()` before any file access, matching the existing `BrukerReader.read_1d/read_2d` pattern (`Path(experiment_dir)` + `.exists()` check) |
| Subprocess argument injection via `nmrPipe -fn SMILE -help` capability probe | Tampering | The probe uses a fixed, hard-coded argument list (`["nmrPipe", "-fn", "SMILE", "-help"]`, no `shell=True`, no user input interpolated into the command) — matches `LSDRunner`'s existing `subprocess.run([...], ...)` list-argument convention, never string-interpolated shell commands |

## Sources

### Primary (HIGH confidence)
- Direct inspection of `C20H32O2/{2,3,4}/{acqus,acqu2s,nuslist,pdata/1/procs,pdata/1/proc2s,ser}` — 2026-07-12, this research session
- Direct Python invocation of installed `nmrglue.bruker.read()`/`read_pdata()`/`rm_dig_filter()` — 2026-07-12, this research session, against the real fixtures
- SMILE User's Manual PDF, §1–2 — https://spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf (fetched and read directly in this session; resolves the milestone SUMMARY.md's open "re-fetch/verify at implementation time" flag)
- `src/lucy_ng/lsd/runner.py` — `LSDRunner.SEARCH_PATHS`/`shutil.which`/`is_available()` (Pattern 1 base)
- `src/lucy_ng/cli/webview.py` — import-safe CLI + `_require_webview()` (Pattern 2 base, D-02)
- `src/lucy_ng/readers/bruker.py` — `_get_param`, `_get_param_2d`, `_strip_brackets` (reuse target, D-04)
- `src/lucy_ng/models/spectrum.py` — Pydantic v2 model conventions (`ConfigDict(arbitrary_types_allowed=True)`, `field_validator`, `to_dict`/`from_dict`)
- `pyproject.toml` — existing `[project.optional-dependencies]` structure, including the empty `prediction = []` precedent for Pattern 2

### Secondary (MEDIUM confidence)
- WebSearch results confirming `nusExpand.tcl`/`bruk2pipe` as real, documented NMRPipe NUS tools (cross-checked against the SMILE manual, which independently corroborates both names)
- `.planning/research/{SUMMARY,ARCHITECTURE,PITFALLS}.md` — milestone-level research, largely confirmed by this phase's direct verification; the one identified discrepancy (`smileNus`) is called out explicitly above rather than silently propagated

### Tertiary (LOW confidence)
- IBBR NMRPipe install page (`ibbr.umd.edu/nmrpipe/install.html`) — WebFetch returned a summarized tool list without explicit NUS-specific binary names; treated as supporting context only, not the basis for any claim above

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies, all reused libraries already installed and directly exercised against real data in this session
- Architecture: HIGH — module layout is a direct precedent match (`lsd/`, `webview/`); the one architectural correction (SMILE detection mechanism) is primary-source-verified, not speculative
- Pitfalls: HIGH for all data-parsing facts (verified against real fixtures independently of the milestone's own PITFALLS.md, values agree); MEDIUM for the exact capability-probe string-matching robustness across NMRPipe versions (Assumption A2, no live install available to test against)

**Research date:** 2026-07-12
**Valid until:** 30 days (stable domain — Bruker parameter file format and this project's own fixture data do not change; NMRPipe/SMILE tool architecture is a mature, slow-moving external dependency)
