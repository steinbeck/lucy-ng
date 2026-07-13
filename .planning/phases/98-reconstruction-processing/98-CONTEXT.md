# Phase 98: Reconstruction + Processing - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

lucy-ng runs the **full external reconstruction + processing pipeline** for any NUS 2D experiment, fully automatically and headless — from Bruker `ser`+`nuslist` through `bruk2pipe` → `nusExpand.tcl` → SMILE (indirect-dimension reconstruction) → FT/apodization/phase/baseline → a processed 2D spectrum on reversed, 1D-calibrated ppm axes. Delivers `nus/runner.py` (orchestration, mirroring `LSDRunner`), the `NmrPipeSmileBackend.reconstruct()` body, and `nus/postprocess.py` (FT/phase/baseline). Backend = **NMRPipe + SMILE** (locked in Phase 97 / research — not re-litigated here).

**In scope (RECON-01..05):** the `lucy nus reconstruct <expdir>` command body; per-stage subprocess orchestration with a fail-loud wrapper (exit code + output-file non-emptiness); FnMODE-aware processing from one entrypoint (echo-antiecho phase-sensitive HSQC/HMBC vs QF magnitude COSY) at 25 % and 33 % densities; hard direct-dimension-first (F2 before F1) ordering gate; reversed ppm axes calibrated to the reliable 1D reference; CLI flags for iteration count / threshold / virtual-echo with convergence-/residual-based stopping.

**Out of scope (later phases):** peak-pick bridge → `analysis/nmr_peaks/*.json` and the mandatory QC gate (Phase 99, `nus/bridge.py` + `lucy nus pipeline`); full platform preflight matrix / Rosetta / csh availability probe (Phase 100 / PORT); the end-to-end §8-gate validation on C20H32O2 and CASE convergence (Phase 100). No changes to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py`, or `case.md` — the "CASE pipeline unchanged" invariant; that diff must stay empty.
</domain>

<decisions>
## Implementation Decisions

### Pipeline orchestration & subprocess strategy (D-01)
- **D-01:** Drive the NMRPipe/SMILE chain **Python-orchestrated, one external subprocess per stage** (`bruk2pipe` → `nusExpand.tcl` → SMILE → FT/PS/baseline), each writing an intermediate file that the next stage reads — **not** as a single csh pipe chain. Rationale: csh-piped NMRPipe stages do not reliably propagate per-stage exit codes (Pitfall 14), which is exactly what RECON-04 must guard against; running each stage as its own subprocess makes the fail-loud check (exit code **and** output-file non-emptiness) native and per-stage. Command strings stay logged/auditable. This also reduces the hard csh dependency (relevant to the Windows gap, Pitfall 12, though full portability is Phase 100).
- Follow the `LSDRunner` subprocess/`is_available()` precedent for the wrapper shape (`lsd/runner.py`).

### Phasing & ppm calibration (D-02)
- **D-02:** **Deterministic known-phase, no blind auto-phase**, with an **optional CLI override**. F2 phase from the reliable 1D reference (P0/P1); F1 default for echo-antiecho HSQC/HMBC (standard 0/0); COSY processed in **magnitude mode** (no phase). Rationale: auto-phase failure is silent with no human in the loop (Pitfall 10) and would only be caught — if at all — by the Phase-99 QC gate. CLI flags allow manual override when a dataset needs it.
- ppm axes are **reversed and calibrated against the §10 ground-truth 1D shifts** (RECON-02, Pitfall 6) — calibration cross-check is the trusted 1D data, not the reconstruction itself.

### Intermediate-file location & retention (D-03)
- **D-03:** Reconstruction intermediates (`test.fid`/converted FID, `nusExpand` output, `.ft2`, etc.) are written to a **persistent per-experiment subfolder under `analysis/` (e.g. `analysis/nus_recon/<expN>/`)** and **kept** (Guide `analysis/` convention). Rationale: the fail-loud wrapper must be able to inspect each stage's output, and retaining intermediates makes a suspicious/artefact-heavy reconstruction forensically debuggable — the core-risk stage of the whole milestone. A cleanup flag may be offered, default **keep**.

### Test strategy (D-04)
- **D-04:** **Mocks in CI + a backend-gated integration test against the external data path.** CI-safe unit tests cover the orchestration logic with the subprocess boundary mocked: the hard F2-before-F1 ordering gate (an out-of-order attempt must raise before any reconstruction runs), the fail-loud wrapper (a deliberately truncated/empty intermediate must abort), and the FnMODE branching (echo-antiecho vs QF). A real end-to-end integration test drives the actual `bruk2pipe`→SMILE chain but points at the **external** C20H32O2 data path and is `skipif`-guarded when the backend or data is absent. **Do not copy the large `ser` binaries into the repo** — this closes the Phase-97 D-03-deferred `ser`-fixture decision: reconstruction is validated via external-path integration, not repo-committed binaries.

### Claude's Discretion
- **RECON-05 knob defaults** — the user explicitly delegated the default values for iteration-count upper bound, threshold, and the virtual-echo toggle to research/planner. **Research assignment:** read the SMILE manual/tutorials and set sane defaults (virtual echo is likely default-ON for echo-antiecho / causal-signal construction, Pitfall 8; iteration count as a conservative upper bound alongside a real convergence/residual stopping rule, never as the sole stopping criterion — Technical Debt table). Expose all three as CLI flags (RECON-05).
- GRPDLY/DECIM digital-filter removal method (via `bruk2pipe` built-in vs an `nmrPipe` stage) — planner/executor discretion, informed by Pitfall 3; must be correct, not necessarily a user choice.
- Exact `nus/runner.py` API surface, how the F2-before-F1 ordering gate is mechanically enforced (state machine vs explicit precondition assertion), and the split of responsibilities between `runner.py` and `postprocess.py` — planner discretion within the LSDRunner-mirroring pattern.
- Apodization/ZF parameter choices (SP window etc.) — standard NMRPipe processing defaults, planner discretion.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone planning
- `.planning/REQUIREMENTS.md` — RECON-01..05 (the five requirements this phase closes)
- `.planning/ROADMAP.md` § Phase 98 — goal + 5 success criteria; § Phase 99/100 for the scope boundary (peak-pick/QC and platform/validation are NOT this phase)
- `.planning/research/SUMMARY.md` — backend decision (NMRPipe+SMILE), pipeline chain steps 3–6 ([BE] tags, ordering enforced [US]), the crux fabricated-cross-peak risk, four-phase shape (Phase 2 = this phase, highest-uncertainty)

### Architecture & pitfalls (code-grounded, authoritative for this phase)
- `.planning/research/ARCHITECTURE.md` — `nus/runner.py` orchestration (mirrors `LSDRunner`), `nus/postprocess.py`, `nus/backends/nmrpipe_smile.py` `reconstruct()` boundary; "CASE pipeline unchanged" invariant (empty diff to `detection/`/`fragments/`/`lsd/`/`ranking/`/`cli/pick.py`)
- `.planning/research/PITFALLS.md` — Pitfall 3 (GRPDLY removal), Pitfall 6 (ppm axis vs 1D reference), Pitfall 7 (over/under-converged fabricated peaks — residual/convergence stopping), Pitfall 8 (virtual echo / causal signal), Pitfall 10 (silent auto-phase failure → D-02), Pitfall 14 (silent subprocess failures in csh pipe chains → D-01), Technical-Debt table (fixed-iteration-count anti-pattern)

### Task brief + data
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` §5 (recommended automatable NMRPipe+SMILE pipeline: bruk2pipe → nusExpand.tcl → SMILE → apod/ZF/FT/PS → baseline), §8 (verification / what a good reconstruction looks like — Phase 99/100 gate criteria), §10 (ground-truth 1D shifts for ppm calibration)
- Real integration-test data (external, not copied): `.../C20H32O2/{2,3,4}/` (exp2 COSY FnMODE 1; exp3 HSQC, exp4 HMBC FnMODE 6) — `ser` + `acqus`/`acqu2s`/`nuslist`

### Existing code precedents to follow
- `src/lucy_ng/lsd/runner.py` — `LSDRunner` subprocess orchestration, `SEARCH_PATHS`, `is_available()`, fail-loud pattern (D-01 wrapper precedent)
- `src/lucy_ng/nus/params.py` + `src/lucy_ng/models/nus.py` — `NusAcquisitionParams` already parses SFO1/SW/TD/FnMODE/GRPDLY/DECIM/byte-order **plus** SF/OFFSET/O1 ppm-calibration params (Phase 97 D-04 superset) — reconstruction consumes these, does NOT re-parse
- `src/lucy_ng/nus/schedule.py` — `NusSchedule` (0-based, acquisition-order `nuslist`, `n_sampled == len(nuslist)` FnMODE assertion) feeds `nusExpand`/SMILE `-sample`
- `src/lucy_ng/nus/backends/nmrpipe_smile.py` — Phase-97 detection stub; this phase adds the `reconstruct()` body
- `src/lucy_ng/cli/nus.py` — import-safe `lucy nus` group; add the `reconstruct` command here (Phase 97 D-02 deferred it to now)
- `src/lucy_ng/cli/webview.py` — import-safe CLI + `_require_*_extra()` pattern for any new optional dep
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nus/params.py` / `models/nus.py::NusAcquisitionParams` — the full conversion + calibration parameter set is already parsed (Phase 97 D-04 superset). Reconstruction/processing reads these; no second parse pass.
- `nus/schedule.py::NusSchedule` — validated 0-based acquisition-order schedule; feeds `nusExpand.tcl` / SMILE `-sample`.
- `lsd/runner.py::LSDRunner` — subprocess orchestration + `is_available()` + `SEARCH_PATHS`; the fail-loud/per-stage wrapper (D-01) mirrors this.
- `nus/backends/nmrpipe_smile.py` — detection already implemented in Phase 97; this phase fills in `reconstruct()`.

### Established Patterns
- CLI groups in `cli/main.py` via `add_command`; each subcommand supports `--format json`. `reconstruct` joins the existing `lucy nus` group (import-safe deferred imports, webview convention).
- Optional heavy deps behind `[nus]` extra + `_require_*` guard (webview precedent) — apply if any new pip dep appears (e.g. for processing/IO).
- Pydantic v2 models in `models/`; any processed-spectrum/recon-result model joins `models/nus.py`.

### Integration Points
- `reconstruct()` in `nus/backends/nmrpipe_smile.py`; `nus/runner.py` orchestrates params → schedule → `backend.reconstruct()` → `postprocess`.
- New `reconstruct` command in `cli/nus.py` (additive).
- Intermediates written under `analysis/nus_recon/<expN>/` in the target experiment dir (D-03).
- **No touch** to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py`, `case.md` — invariant; that diff stays empty (peak-pick bridge is Phase 99).
</code_context>

<specifics>
## Specific Ideas

- The **fail-loud wrapper is the correctness anchor of this phase**: every external call checks exit code AND output-file non-emptiness; a deliberately truncated/empty intermediate must abort with a clear error (RECON-04, Pitfall 14). This is why D-01 chose per-stage subprocesses over a csh pipe.
- **F2 before F1 is a hard gate, not a convention**: an out-of-order attempt must raise *before* any reconstruction runs (RECON-02, SMILE-mandated ordering) — this is directly testable with mocks (D-04) with no backend present.
- **Deterministic phase, never blind auto-phase** (D-02): F2 from the 1D P0/P1, F1 default echo-antiecho, COSY magnitude — because a wrong auto-phase is silent (Pitfall 10) and only the Phase-99 QC gate might catch it.
- **The reconstruction quality itself is the milestone's open question** (research: Phase 2 is the highest-uncertainty phase). Under-iteration → residual t1-ridges (the 2026-07-09 failure); over-iteration → fabricated noise-peaks. Convergence/residual-based stopping, not a fixed iteration count as the sole rule.
</specifics>

<deferred>
## Deferred Ideas

- Peak-pick bridge → `analysis/nmr_peaks/*.json` (byte-for-byte schema-identical via `Spectrum2D` → existing `PeakPicker2D`) and the mandatory automated QC gate (PASS/PARTIAL/FAIL) → **Phase 99**.
- Full platform preflight (Apple-Silicon `arch`/Rosetta probe, `csh`/`tcsh` matrix) and the documented portability matrix → **Phase 100 / PORT**.
- End-to-end §8-gate validation on C20H32O2 exp2/3/4 and `/lucy-ng:case C20H32O2` convergence → **Phase 100 / VAL**.
- hmsIST/mddnmr fallback backends (only if SMILE leaves ridges at 25 % on this data) → deferred (v1.x); primary is NMRPipe+SMILE.

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` (score 0.6, generic keyword match) — CASE-solver / azulene regiochemistry defect, unrelated to NUS reconstruction/processing. **Not folded** (same call as Phase 97).
- `2026-06-30-ranking-tests-hardfail-without-hosegen` (score 0.6, keyword match) — hosegen ranking-test-infra todo, unrelated to this phase. **Not folded.**

</deferred>

---

*Phase: 98-reconstruction-processing*
*Context gathered: 2026-07-13*
