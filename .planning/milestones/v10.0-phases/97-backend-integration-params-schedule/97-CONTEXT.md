# Phase 97: Backend Integration + Params/Schedule - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

lucy-ng can (a) detect the NUS reconstruction backend (NMRPipe + SMILE) on the local machine and (b) correctly parse any NUS experiment's Bruker acquisition parameters and sampling schedule into validated Pydantic models — ready to drive reconstruction in Phase 98. Pure-Python params/schedule work, fixture-tested against the real C20H32O2 data; no reconstruction, no processing, no peak-picking (those are Phases 98–99).

**In scope (NUS-01..05):** new `src/lucy_ng/nus/` package skeleton; `nus/backends/` with the `NusBackend` protocol + `nmrpipe_smile.py` detection; `lucy nus check`; `nus/params.py` → `NusAcquisitionParams`; `nus/schedule.py` → `NusSchedule`; `models/nus.py`; `lucy nus params` / `lucy nus schedule` (both `--format json`); optional `[nus]` pyproject extra scaffold; core `lucy` CLI stays dependency-free.

**Out of scope (later phases):** actual reconstruction / SMILE invocation (98), FT/phase/baseline processing (98), peak-pick bridge + QC gate (99), full platform preflight matrix (100 / PORT), `lucy nus reconstruct` + `lucy nus pipeline` bodies (98/99).
</domain>

<decisions>
## Implementation Decisions

### `lucy nus check` depth (D-01)
- **D-01:** `lucy nus check` in Phase 97 does **backend detection only** — checks the SMILE toolchain (`nmrPipe`, `smileNus`, `nusExpand.tcl`, `bruk2pipe`) on PATH via the LSD precedent (`shutil.which` + `SEARCH_PATHS`, mirroring `LSDRunner.is_available()`) — **plus** a distinct diagnostic state separating "installed but the NMRPipe env is not sourced / tools not on PATH" from "not installed at all", with actionable install/source guidance (URL + `.cshrc` source hint). It fails loud (exit 1) when unusable, like `lucy lsd check`.
- **NOT in Phase 97:** the full platform preflight (Apple-Silicon `arch`/Rosetta probe, `csh`/`tcsh` presence matrix) — that is PORT-01, deliberately kept in Phase 100 so the portability boundary stays clean. Phase 97 `check` may lay the groundwork but must not pull PORT-01 work forward.

### CLI surface in Phase 97 (D-02)
- **D-02:** Register only the **implemented** subcommands now — `lucy nus check`, `lucy nus params`, `lucy nus schedule` — in a new `lucy nus` Click group added to `cli/main.py` via `add_command`. `reconstruct` and `pipeline` are added in Phases 98/99 when they actually work. **No dead/"not implemented" stub commands.** `cli/nus.py` stays import-safe (deferred imports inside command bodies, same convention as `cli/webview.py`).

### Test-fixture strategy (D-03)
- **D-03:** Copy the real C20H32O2 **metadata text files** — `acqus`, `acqu2s`, `nuslist` for exp2 (COSY), exp3 (HSQC), exp4 (HMBC) — into `tests/fixtures/nus/` (e.g. `tests/fixtures/nus/exp2_cosy/`, `exp3_hsqc/`, `exp4_hmbc/`) so params/schedule tests are self-contained and CI-portable. The large binary `ser` files are **NOT** copied — params/schedule parsing reads only the text metadata, so `ser` is unnecessary weight here (it will matter for reconstruction fixtures in Phase 98, decided separately). These are acquisition-parameter files with no compound identity, so no blind-UAT contamination concern.

### NusAcquisitionParams scope (D-04)
- **D-04:** `NusAcquisitionParams` captures a **superset** — the NUS-02 conversion parameters (SFO1, SW_h, TD per dimension, FnMODE, GRPDLY/DECIM, byte order/dtype, NusAMOUNT, NusSEED) **plus** the ppm-calibration parameters Phase-98 processing will need anyway (SF, OFFSET/O1, SW per dimension, F1/F2 nucleus). Parse once in Phase 97 rather than forcing a second parse pass in Phase 98 (RECON-02 reversed ppm axis). Cheap now, avoids duplication.

### Claude's Discretion
- Whether to reuse `readers/bruker.py`'s `_get_param`/`_get_param_2d`/`_strip_brackets` via a direct underscore-import from within the `nus` package, or promote them to a small shared internal module both import — a one-line structural choice for the planner (ARCHITECTURE.md § Internal Boundaries flags it as non-blocking). Reuse, do not duplicate.
- Exact `NusBackend` protocol shape (Protocol vs ABC), registry API names (`get_backend`, `list_available_backends`), and the `models/nus.py` field naming/validators — planner/executor discretion within the models above.
- Whether the `[nus]` extra is created empty-but-present now or added when the first pip dep appears — planner discretion; core CLI dependency-free is the invariant.

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` (score 0.6, generic keyword match) — CASE-solver / azulene regiochemistry defect, unrelated to NUS param/schedule parsing. **Not folded.**
- `2026-06-30-ranking-tests-hardfail-without-hosegen` (score 0.2) — hosegen test-infra todo, unrelated. **Not folded.**
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone planning
- `.planning/REQUIREMENTS.md` — NUS-01..05 (the five requirements this phase closes) + backend-decision block
- `.planning/ROADMAP.md` § Phase 97 — goal + 3 success criteria
- `.planning/research/SUMMARY.md` — backend decision, pipeline chain (US vs BE tags), FnMODE trap, per-phase exit criteria

### Architecture (code-grounded, authoritative for this phase)
- `.planning/research/ARCHITECTURE.md` — module layout (`nus/` package, `models/nus.py`), Pattern 1 (external-binary detection, LSD precedent), Pattern 2 (`[nus]` extra), Internal Boundaries table (param-helper reuse)
- `.planning/research/PITFALLS.md` — Pitfall 2 (FnMODE: `nuslist` length == TD for QF vs TD/2 for echo-antiecho — this dataset hits both), Pitfall 3 (never sort/regenerate `nuslist`), Pitfall 4 (byte order per-experiment, non-integer GRPDLY)

### Task brief + data
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` §3 (data inventory: per-exp FnMODE/NUS%/nuslist sizes), §5 (pipeline), §10 (ground-truth shifts)
- Real fixtures source: `.../C20H32O2/{2,3,4}/{acqus,acqu2s,nuslist}` — copy into `tests/fixtures/nus/` per D-03

### Existing code precedents to follow
- `src/lucy_ng/lsd/runner.py` — `SEARCH_PATHS` + `shutil.which` + `is_available()` (D-01 detection precedent)
- `src/lucy_ng/cli/lsd.py` — `lucy lsd check` command shape
- `src/lucy_ng/cli/webview.py` — import-safe CLI + `_require_*_extra()` pattern (D-02)
- `src/lucy_ng/readers/bruker.py` — `_get_param`/`_get_param_2d`/`_strip_brackets` + `_read_2d_metadata` (reuse for D-04)
- `src/lucy_ng/cli/main.py` — `add_command` group registration
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `readers/bruker.py::_get_param`, `_get_param_2d`, `_strip_brackets` — acqus/acqu2s param extraction; already read NUC1/SFO1/SW_h/PULPROG/SOLVENT/NS per dimension. `nus/params.py` reuses these; adds FnMODE, GRPDLY/DECIM, BYTORDA/DTYPA, NusAMOUNT, NusSEED, SF/OFFSET (currently unread).
- `lsd/runner.py::LSDRunner` — `SEARCH_PATHS`, `OUTLSD_SEARCH_PATHS`, `is_available()`, `shutil.which` — the exact detection shape `nus/backends/nmrpipe_smile.py` should mirror.
- `tests/fixtures/` — established fixtures dir; add `nus/` subtree of copied metadata.

### Established Patterns
- CLI groups registered in `cli/main.py` via `cli.add_command(<group>)`; each group in its own `cli/<name>.py`, every subcommand supports `--format json`.
- Import-safe CLI modules (webview) keep heavy/optional imports inside command bodies; `[webview]` optional extra + `_require_webview()` guard is the template for `[nus]`.
- Pydantic v2 models live in `models/` (Spectrum1D/2D, Peak1D) — `models/nus.py` joins them.

### Integration Points
- New `lucy nus` group → `cli/main.py` (additive only).
- `nus/params.py` → imports from `readers/bruker.py` (helpers) — the only touch to existing modules; `readers/bruker.py` change is additive/none.
- No touch to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` — the "CASE pipeline unchanged" invariant; the diff there must stay empty.
</code_context>

<specifics>
## Specific Ideas

- FnMODE→sampled-count rule is the correctness crux of this phase: QF (COSY, FnMODE=1) → `n_sampled == TD`; echo-antiecho (HSQC/HMBC, FnMODE=6) → `n_sampled == TD/2`. Verified in the data: COSY 188==188, HSQC 50==100/2, HMBC 116==232/2. The hard assertion `n_sampled == len(nuslist)` must fire per-experiment before any downstream step, and must be a raise, never a warning (PITFALLS Pitfall 2).
- `nuslist` is in acquisition order (e.g. exp2: `0, 124, 431, 670, 369, …`), NOT sorted — preserve order exactly; never sort or regenerate (PITFALLS Pitfall 3).
- `lucy nus check` must give the "installed but env not sourced" hint — NMRPipe needs `.cshrc`/env sourcing before its tools appear on PATH (D-01).
</specifics>

<deferred>
## Deferred Ideas

- Full platform preflight (Apple-Silicon arch/Rosetta, csh/tcsh matrix) → Phase 100 / PORT-01 (kept out of Phase 97 `check` per D-01).
- `lucy nus reconstruct` / `lucy nus pipeline` command bodies → Phases 98/99 (per D-02, not stubbed now).
- `ser`-based reconstruction fixtures (large binaries) → Phase 98 fixture decision (D-03 copies only text metadata).

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` — CASE-solver regiochemistry defect; unrelated to NUS param/schedule. Considered, deferred (stays in pending/).
- `2026-06-30-ranking-tests-hardfail-without-hosegen` — hosegen test-infra; unrelated. Considered, deferred.
</deferred>

---

*Phase: 97-backend-integration-params-schedule*
*Context gathered: 2026-07-12*
