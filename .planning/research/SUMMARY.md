# Project Research Summary

**Project:** lucy-ng — v10.0 Automatic NUS 2D Reconstruction
**Domain:** Non-uniform-sampling (NUS) 2D NMR reconstruction backend integration, embedded in an existing autonomous CASE (Computer-Assisted Structure Elucidation) pipeline
**Researched:** 2026-07-12
**Confidence:** MEDIUM-HIGH (core backend/architecture recommendation HIGH; a few platform/library details MEDIUM-LOW, flagged below)

## Executive Summary

lucy-ng needs to replace an ad-hoc, hand-rolled per-column IST reconstruction (the root cause of the 2026-07-09 CASE failure — t1-ridge artifacts that defeated LSD's constraint pruning on a ~10⁶-candidate tetracyclic diterpene search space) with a real, validated compressed-sensing/IST reconstruction of NUS 2D Bruker data (COSY/HSQC/HMBC), driven entirely headlessly with no GUI step. All four research passes converge on the same core strategy: do not write a reconstruction algorithm from scratch — no mature pip-installable CS/IST-for-NMR package exists, and re-deriving the quadrature-aware sparse-recovery math correctly is a multi-week, high-correctness-risk undertaking that would just reproduce the same class of bug this milestone exists to fix. Instead, delegate reconstruction to an established external binary (subprocess-driven, exactly the pattern lucy-ng already uses for LSD), keep everything else — Bruker metadata parsing, schedule/FnMODE bookkeeping, the peak-pick bridge, and a mandatory automated quality gate — as pure, testable, backend-agnostic lucy-ng code.

The recommended primary backend is NMRPipe + SMILE: it is free, actively maintained, has native builds for macOS Apple Silicon (the primary dev/test platform) and Linux (Intel + ARM), is 100% CLI/pipeline-driven with no GUI dependency, and is the most literature-validated reconstruction algorithm of the candidates investigated. Its one real gap is Windows: no maintained native build since v8.9, requiring a WSL2 or VM workaround. A second candidate, NMRFx (pure Java, genuinely native on macOS/Linux/Windows, Python-scriptable, headless, built-in IST/NESTA), was surfaced by the features research as architecturally the strongest fit for the "broad cross-platform" constraint, but it received far less depth of verification in this research pass (docs site TLS issues blocked direct fetch; reconstruction fidelity for small-molecule natural-product 2D spectra specifically is not independently benchmarked the way SMILE's is). Given the milestone explicitly allows documented platform gaps and prioritizes getting a correct reconstruction validated end-to-end on the real C20H32O2 dataset over maximal day-one portability, NMRPipe+SMILE is the recommendation for v10.0, with Windows treated as an accepted, documented gap (WSL2 workaround) rather than a blocker — see the Backend Decision section below for the full reasoning and the conditions under which NMRFx should be revisited.

The single biggest risk is not "does reconstruction run" but "does it produce fabricated cross-peaks that look clean but are wrong" — over- or under-converged IST/CS reconstruction is a documented failure mode (peer-reviewed) that can sparsify pure noise into plausible-looking peaks, and because lsd-engineer treats HMBC/COSY/HSQC correlations as hard generation constraints, a single fabricated correlation can silently prune the correct structure out of LSD's candidate space — a "clean but wrong" answer with no obvious symptom, one pipeline stage earlier than the exact failure class the v9.1 milestone (RANK/IDENT/MULT) was built to catch. This milestone must therefore ship a mandatory, structured QC gate between reconstruction and CASE handoff that cross-checks every reconstructed correlation against the trusted, already-validated 1D shift data (the guide's own §8/§10 ground truth) — the CASE orchestrator must refuse to start a run when this gate reports FAIL, exactly as it already fails loud on other precondition problems (e.g. outlsd).

## Key Findings

### Recommended Stack

Core technology: NMRPipe (v13.0, native macOS Apple Silicon + Linux Intel/ARM) + the bundled SMILE plugin (`nmrPipe -fn SMILE`), driven entirely via `subprocess` from a new `lucy nus` CLI group — no Python bindings exist for any of these tools, which matches lucy-ng's existing thin-CLI-wrapper pattern (nmrglue/LSD/RDKit). Supporting pieces: `bruk2pipe` (Bruker→NMRPipe conversion, scriptable non-interactively since lucy-ng already parses `acqus`/`acqu2s`), `nusExpand.tcl` (sparse→full-grid NUS expansion), and `nmrglue` 0.11 (already a dependency) for reading NMRPipe-format output back into Python for peak picking. Windows has no maintained native NMRPipe build (last one was v8.9); the accepted workaround is WSL2 Ubuntu (unverified, needs a spike) or IBBR's own prebuilt Ubuntu VM image.

Fallback ladder (in order):
1. NMRPipe + SMILE — primary, most literature-validated, native macOS/Linux.
2. hmsIST (Wagner lab) / mddnmr CLI scripts — both legitimate published fallbacks for artefact-heavy data, both layer on top of an already-required NMRPipe install, both effectively unmaintained (2016-2020) and Linux-only in practice. Reserve for cases where SMILE demonstrably leaves ridges at this project's 25-33% sampling densities.
3. TopSpin CS/MDD reconstruction — manual escape hatch for a human only. No source confirms a true zero-display headless automation mode; do not build it into the automated `lucy` CLI path.
4. Explicitly rejected: a from-scratch Python CS/IST implementation. High correctness risk (subtle quadrature/phase bugs), no existing pip package does this correctly for NMR today, and it is precisely the class of mistake (hand-rolled per-column IST) that caused the milestone's founding failure.

NMRFx (pure Java, native macOS/Linux/Windows, Python-scriptable `process.py`, built-in IST/NESTA, headless by design) is the strongest portability candidate identified but was not deeply vetted for reconstruction fidelity on small-molecule natural-product 2D data — see Backend Decision below.

### Backend Decision — NMRPipe+SMILE vs NMRFx (must be surfaced explicitly, not buried)

This is a genuine cross-cutting tradeoff the research did not fully resolve and the roadmap must decide on explicitly:

| | NMRPipe + SMILE | NMRFx (IST/NESTA) |
|---|---|---|
| Reconstruction fidelity | Most literature-validated, de-facto standard (NIH/Bax lab); the algorithm every other backend investigated is built as an add-on to | In-house IST/NESTA, actively maintained (2025 paper), less independently published/benchmarked than SMILE |
| Cross-platform | Native macOS (Intel+ARM) + Linux (Intel+ARM); no native Windows build since v8.9 (WSL2/VM workaround) | Pure Java — genuinely native on macOS, Linux, and Windows |
| Headless/scriptable | 100% CLI/pipeline (csh/Tcl scripts + C binaries), no GUI at all | Python-scripted (`process.py`), explicitly designed for headless/batch execution |
| Verification depth in this research pass | HIGH — official install docs, SMILE manual, direct grounding against this project's own acqus/acqu2s/nuslist files | MEDIUM — surfaced by FEATURES.md only; docs subdomain had a TLS cert mismatch blocking direct fetch; not independently source-verified for NMR-specific (Bruker nuslist/FnMODE) correctness the way SMILE was |
| Ecosystem maturity | Every other real backend (hmsIST, mddnmr) is layered on top of it — effectively a forced dependency regardless of primary choice | Self-contained, no NMRPipe dependency |

Recommendation: NMRPipe + SMILE as the v10.0 primary backend. Rationale: (1) the milestone's own primary dev/test platform is macOS Apple Silicon, where NMRPipe is native and best-documented; (2) SMILE is the most rigorously validated reconstruction algorithm of the candidates, and reconstruction correctness (not fabricating cross-peaks) is the crux risk this milestone exists to eliminate — a less-benchmarked backend raises exactly that risk; (3) the milestone explicitly allows documented platform gaps, and Windows-via-WSL2 is a reasonable, containable gap to document rather than a blocker; (4) NMRPipe is a forced dependency anyway if the hmsIST/mddnmr fallback ladder is ever needed, so standing it up first is not wasted effort. NMRFx warrants a short, explicit spike-comparison (reconstruct one of the three real C20H32O2 experiments with both backends, compare against the §8/§10 ground truth) if/when native Windows support becomes a hard requirement rather than a documented gap — do not silently drop it from consideration, and do not commit to it as primary without that verification, since its NMR-specific correctness was not independently confirmed in this research pass the way SMILE's was.

### Expected Features

Pipeline chain (backbone), tagged [US] = our code (backend-agnostic) vs [BE] = backend-delegated:

1. [US] Read Bruker raw data (`ser`, `nuslist`, `acqus`/`acqu2s`) — extends the existing `BrukerReader`.
2. [US] Parse acquisition parameters needed for conversion (SFO1, SW_h, TD per dim, FnMODE, GRPDLY/DECIM, byte order, hypercomplex-component count) — lucy-ng must derive these itself; no GUI wizard does it for an unattended pipeline.
3. [BE] Bruker → backend format conversion (`bruk2pipe`).
4. [BE] NUS expansion (zero-fill sparse FID onto full t1 grid per schedule, `nusExpand.tcl`).
5. [BE] Indirect-dimension reconstruction (SMILE) — the algorithmic core, explicitly not reimplemented.
6. [BE, ordering enforced US] Direct-dimension (F2) processing before indirect reconstruction — SMILE-mandated ordering; a pure orchestration/sequencing risk if not enforced as a hard pipeline gate.
7. [BE] Indirect-dimension (F1) processing after reconstruction.
8. [US or BE] Baseline correction.
9. [US] Peak picking → JSON, reusing lucy-ng's existing nmrglue-based 2D picker code (DEPT-guided HSQC, HMBC-guided, COSY) unmodified against reconstructed spectra — NMRPipe's `.ft2` output is natively `nmrglue.fileio.pipe`-readable, making this stage genuinely backend-agnostic.
10. [US] Reconstruction quality auto-assessment — no human in the loop; see Critical Pitfalls.

Must have (table stakes): real backend-delegated reconstruction (not hand-rolled); correct 0-based/hypercomplex-aware schedule conversion; FnMODE-aware processing (echo-antiecho HSQC/HMBC vs QF COSY); enforced direct-dimension-first ordering; full apod/ZF/FT/phase/baseline chain; peak picking into the existing, unchanged `analysis/nmr_peaks/*.json` schema; edited-sign/multiplicity fidelity preserved (feeds v9.1's `multiplicity_edited`); handles both 25% and 33% sampling densities from one pipeline; reusable `lucy` CLI step, not a C20H32O2-only script; documented cross-platform behavior.

Should have (differentiators): fully automatic, no-GUI quality auto-assessment with concrete computable metrics (not "looks clean"); backend chosen for headless+cross-platform scriptability, not raw fidelity alone; reconstruction-quality metadata embedded in peak JSON (replacing the current blanket `"confidence": "low"`); magnitude-mode-aware COSY handling (QF ≠ phase-sensitive); configurable reconstruction knobs (iteration count, threshold, virtual-echo toggle) exposed via CLI flags; a documented portability matrix.

Defer (v1.x/v2+): a second backend as fallback (only if the primary fails the §8-derived gate); full Linux/Windows portability validation beyond macOS; a generalized schedule/FnMODE abstraction for experiment types beyond COSY/HSQC/HMBC (TOCSY, NOESY-NUS); 3D/4D NUS support (no current consumer); per-peak confidence scoring feeding LSD constraint weighting directly; deep-learning-based reconstruction (GPU dependency, poor portability, unmature for small-molecule 2D validation); MaxEnt as a fourth backend paradigm; non-Bruker vendor support (already out of scope generally).

### Architecture Approach

New top-level `nus/` package (sibling of `lsd/`, `webview/`, `readers/`) — not nested under `processing/`, because reconstruction is external-tool integration (subprocess orchestration, multi-stage on-disk artefacts) that happens before a `Spectrum2D` object exists, matching the shape of `lsd/` and `webview/` rather than the pure-Python signal-processing shape of `processing/`. The backend is a runtime-detected external binary, exactly the LSD precedent (`LSDRunner`'s `SEARCH_PATHS` + `shutil.which()` + fail-loud `lucy nus check`) — never a required core `pyproject.toml` dependency, since none of NMRPipe/hmsIST/mddnmr/TopSpin are pip packages. An optional `[nus]` pip extra exists only for genuinely pip-installable pieces (e.g. QC-plotting deps), following the `[webview]` extra's `_require_*_extra()` lazy-import pattern — core `lucy` CLI stays dependency-free.

Major components:
1. `nus/params.py` + `nus/schedule.py` — Bruker metadata + `nuslist` parsing into `NusAcquisitionParams`/`NusSchedule` Pydantic models; pure Python, zero external deps, fully unit-testable against the real C20H32O2 fixtures from day one.
2. `nus/backends/*.py` — one module per backend (`nmrpipe_smile.py` primary; `hmsist.py`/`mddnmr.py` fallback stubs) behind a shared `NusBackend` protocol; `nus/runner.py` orchestrates params → schedule → `backend.reconstruct()` → postprocess, mirroring `LSDRunner`.
3. `nus/postprocess.py` — FT/apodization/phase/baseline, backend-delegated where possible.
4. `nus/bridge.py` — the only module touching the existing pipeline surface: builds a `Spectrum2D` in memory, calls the existing `processing.PeakPicker2D` as a direct Python function call (not a subprocess to `lucy pick`, following the `_perform_ranking()` precedent in `cli/lsd.py`), and writes `analysis/nmr_peaks/*.json` byte-for-byte schema-identical to today's output.
5. `cli/nus.py` — `lucy nus` command group (`check`/`params`/`schedule`/`reconstruct`/`pipeline`), import-safe like `cli/webview.py`.

Integration philosophy — pre-CASE "dumb tool": reconstruction is a deterministic, mechanical signal-processing pipeline with zero domain judgment; it must run as a pre-CASE step (`lucy nus pipeline <expdir>`), producing clean `analysis/nmr_peaks/*.json` before `/lucy-ng:case` starts. `case.md` and the 5-agent team need zero changes — no new `[BEGIN]` directive, no 6th agent, no CASE-PROGRESS.md section. This keeps the milestone's "CASE pipeline unchanged" constraint enforceable by inspection: the diff to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` should be empty.

### Critical Pitfalls

1. Fabricated cross-peaks from over/under-converged reconstruction become hard LSD constraints (the crux risk). Both under-iteration (residual t1-ridges — the exact 2026-07-09 failure) and over-iteration (IST progressively sparsifies pure noise into plausible fake peaks — documented in peer-reviewed CS literature) are dangerous, but over-iteration is worse: `lsd-engineer` treats HMBC/COSY/HSQC correlations as hard generation constraints, so a fabricated correlation can actively prune the correct structure out of LSD's candidate space, producing a confident, wrong, "clean" answer with no obvious symptom. Avoid by: a residual/convergence-based stopping rule (not a fixed iteration count as the sole criterion), held-out cross-validation on actually-sampled points, and — non-negotiably — a dedicated, structured QC gate between reconstruction and CASE handoff that cross-checks every reconstructed correlation against the trusted 1D shift data (§8/§10 ground truth: protonated-carbon coverage, edited-sign self-consistency, COSY diagonal symmetry, ppm calibration, signal-to-ridge ratio). The CASE orchestrator must refuse to start when this gate reports FAIL — extending the existing v9.0 constraint-hardness guard (FIX-10) to reconstruction-derived peaks.

2. The FnMODE/nuslist bookkeeping trap — this milestone's own data exercises both failure modes simultaneously. `nuslist` length equals `acqu2s TD` for QF/real modes (verified: COSY, FnMODE=1, 188==188) but equals `TD/2` for complex/hypercomplex modes like echo-antiecho (verified: HSQC 50==100/2, HMBC 116==232/2). A single hard-coded divisor passes for two of the three real experiments and silently corrupts the third. Avoid by: deriving `n_sampled` from `FnMODE` explicitly per experiment, with a hard-fail assertion `n_sampled == len(nuslist)` before any conversion step runs — never a warning.

3. `nuslist` must never be sorted or regenerated. Rows correspond to consecutively acquired FID blocks in acquisition order (verified: exp2's `nuslist` is `0, 124, 431, 670, 369, …`, not ascending), not sorted index order; sorting silently breaks the block↔grid-index correspondence and produces a plausible-looking but wrong reconstruction — degrading gracefully into artifacts rather than crashing, the most dangerous class of bug in this domain. TopSpin's own GUI has a documented version of this trap (clicking "Calculate" regenerates and overwrites an already-acquired schedule).

4. Silent low-level data-integrity bugs that "complete" without crashing: non-integer `GRPDLY` digital-filter removal (verified: 67.985…, requires interpolation, not integer truncation) must happen before any F2 processing; byte order/dtype (`BYTORDA`/`DTYPA`) must be read per-experiment, never hard-coded from this dataset's values; `csh`-piped NMRPipe stage chains don't reliably propagate exit codes, so every external-tool invocation needs a fail-loud wrapper checking both exit code and output-file size/non-emptiness (a truncated/empty intermediate silently "succeeds" through the rest of the chain).

5. Cross-platform gaps that surface only at runtime. Apple Silicon: some NMRPipe binaries may need Rosetta 2, and `csh` pipe semantics can mask an architecture failure as a "completed" pipeline with garbage output — needs an explicit preflight (`arch -x86_64 nmrPipe -help`). Windows: no `csh`/`tcsh` natively and no maintained native NMRPipe build — must be a documented portability-matrix gap (WSL2/Docker/Python-native fallback), caught by a `lucy nus check`-style preflight, never discovered mid-run.

## Implications for Roadmap

Based on combined research (the four researchers largely converged on the same four-phase shape independently; this is the merged, single ordering):

### Phase 1: Backend integration + params/schedule
Rationale: Riskiest external-binary integration work (backend availability, install friction) should happen early to fail fast; pure-Python params/schedule parsing has zero external-binary dependency and can be built/unit-tested against the real C20H32O2 `acqus`/`acqu2s`/`nuslist` fixtures from day one, in parallel with backend detection.
Delivers: `nus/backends/__init__.py` (`NusBackend` protocol), `nus/backends/nmrpipe_smile.py`, `lucy nus check`; `nus/params.py` + `nus/schedule.py` with `NusAcquisitionParams`/`NusSchedule` models.
Addresses: correct Bruker→backend schedule conversion (table stakes), FnMODE-aware metadata derivation.
Avoids: Pitfall 2 (FnMODE/TD-length assumption), Pitfall 3 (nuslist sorting), Pitfall 5 (platform preflight groundwork).
Exit criterion: `lucy nus check` correctly reports backend availability; `lucy nus params`/`lucy nus schedule` produce correct, schema-validated JSON, with the hard `n_sampled == len(nuslist)` assertion passing for all three real C20H32O2 experiments (FnMODE 1, 6, 6).

### Phase 2: Reconstruction + processing
Rationale: Needs the real external binary installed; expect this to be the highest-uncertainty phase — reconstruction quality, not plumbing, is the open question the whole milestone exists to answer.
Delivers: `nus/runner.py` orchestration; the backend's `reconstruct()` implementation (conversion → NUS expansion → SMILE call); `nus/postprocess.py` (FT/phase/baseline), with direct-dimension-first ordering enforced as a hard pipeline gate.
Uses: NMRPipe + SMILE via subprocess; `bruk2pipe`/`nusExpand.tcl`.
Implements: the [BE] half of the pipeline chain; GRPDLY/byte-order-correct conversion (Pitfall 4); fail-loud subprocess wrapper (Pitfall 5) applied to every invocation.
Exit criterion: `lucy nus reconstruct <expdir>` produces a processed 2D spectrum for all three C20H32O2 experiments passing the guide's §8 qualitative checks (manual/visual gate at this phase; automated in Phase 3).

### Phase 3: Peak-pick bridge + QC gate + CLI
Rationale: Can be scaffolded in parallel with Phase 2 once Phase 1's models are stable (only the `reconstruct` subcommand body hard-depends on Phase 2); this is also where the crux risk (fabricated cross-peaks, Pitfall 1) gets its mandatory automated defense.
Delivers: `nus/bridge.py` (Spectrum2D → existing `PeakPicker2D` → JSON, schema-identical to today's manual/GUI path); the §8/§10-derived automated QC gate (protonated-carbon coverage, edited-sign consistency, COSY diagonal symmetry, held-out cross-validation, ppm calibration cross-check, signal-to-ridge regression vs. the known-bad baseline) as a PASS/FAIL/PARTIAL machine-readable report; full `cli/nus.py` group registered in `cli/main.py`.
Addresses: peak picking into existing JSON schema (table stakes), reconstruction-quality metadata in peak JSON (differentiator).
Avoids: Pitfall 1 (the crux risk) — the QC gate is this pitfall's mandatory mitigation, not optional polish.
Exit criterion: `lucy nus pipeline <expdir>` end-to-end produces `analysis/nmr_peaks/*.json` schema-identical to a known-good fixture; QC gate correctly reports FAIL on the existing (known-bad) t1-ridge-laden peak lists and is wired so the CASE orchestrator refuses to proceed on a FAIL report.

### Phase 4: Cross-platform hardening + C20H32O2 end-to-end CASE-convergence validation
Rationale: Milestone-closing phase — portability documentation and the actual success criterion (CASE convergence) both depend on everything upstream being stable.
Delivers: portability matrix (macOS/Linux native support confirmed; Windows WSL2/VM gap documented with workaround steps); path/line-ending robustness in generated scripts; final validation reconstructing C20H32O2 exp2/exp3/exp4, confirming the §8 quality gate, then running `/lucy-ng:case C20H32O2` to confirm convergence on a small rankable solution set.
Addresses: the milestone's explicit "documented portability" and "end-to-end validation" target features.
Exit criterion: all v10.0 target features met; this is the milestone's actual success bar.

### Phase Ordering Rationale

- Nothing downstream is meaningfully testable until the thing upstream exists (params/schedule → conversion → reconstruction → peak-pick → QC → CASE), so the phase order follows the pipeline's own dependency chain.
- The riskiest, least-controllable work (external-binary availability and reconstruction quality) is front-loaded into Phases 1-2 so failures surface early rather than at milestone close.
- Pure-Python, fixture-testable work (params/schedule parsing, the CLI surface, the QC gate's comparison logic) is deliberately decoupled from the real-binary dependency so it can proceed in parallel and isn't blocked by backend install friction.
- The QC gate is placed as its own explicit phase-3 deliverable, not folded into "peak picking" as an afterthought — this directly reflects the core lesson that a pipeline with no QC gate has no place where a human would have caught a subtly-wrong reconstruction.

### Research Flags

Needs deeper research during phase planning:
- Phase 2 (Reconstruction + processing): exact `nmrPipe -fn SMILE` flag syntax, iteration/threshold defaults, and virtual-echo invocation were not independently verified from a parseable manual in this research pass (PDF fetch issues) — re-fetch/verify at implementation time. Also the WSL2 Windows workaround is unverified end-to-end (LOW-MEDIUM confidence, inferred).
- Phase 3 (QC gate): the ridge-detection metric (scanning F1 columns for anomalous peak density) needs its own design spike — this is genuinely new code, not adapted from an existing pattern.
- Phase 4 (Cross-platform hardening): if native Windows ever becomes a hard requirement rather than a documented gap, the NMRFx spike-comparison (see Backend Decision) belongs here or in a follow-up milestone.

Phases with well-documented, standard patterns (safe to skip deep research-phase):
- Phase 1 (Backend detection, params/schedule parsing): directly mirrors the existing `LSDRunner`/`lucy lsd check` pattern and lucy-ng's own already-verified `acqus`/`acqu2s` parsing conventions.
- Phase 3 (Peak-pick bridge, CLI surface): directly mirrors the existing `_perform_ranking()` direct-call pattern (`cli/lsd.py`) and the `[webview]` optional-extra/import-safe-CLI pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | NMRPipe+SMILE core recommendation HIGH (official install docs, SMILE manual, direct grounding against this project's own acqus/acqu2s/nuslist files); TopSpin-headless and mddnmr/hmsIST platform specifics MEDIUM/LOW (site TLS issues, ambiguous licensing text, no independent re-run) |
| Features | MEDIUM-HIGH | Pipeline chain and FnMODE/schedule mechanics are well-established NMR methodology, HIGH confidence via multiple independent official sources; exact backend behavior for these specific experiments is MEDIUM (verified via docs/search, not hands-on tested) |
| Architecture | HIGH | Module layout, CLI shape, and dependency-isolation decisions derived directly from inspecting the live codebase (`lsd/`, `webview/`, `readers/bruker.py`, `cli/*.py`, `pyproject.toml`); MEDIUM on exact intermediate-artefact names (depends on final backend choice); LOW on the exact Windows story pending a real WSL2/Docker spike |
| Pitfalls | HIGH for schedule/parameter facts (verified directly against this project's own real data files); MEDIUM for reconstruction-algorithm behavior (peer-reviewed literature); MEDIUM-LOW for backend-specific CLI/install quirks (official docs + community wikis, not independently re-run) |

Overall confidence: MEDIUM-HIGH — the backend/architecture recommendation and the domain mechanics (FnMODE, schedule indexing, digital-filter removal) are solidly grounded, including direct verification against this project's own real C20H32O2 data. The main open uncertainty is empirical: whether SMILE at 25-33% sampling actually clears the §8/§10 quality bar on this compound's crowded, information-dense HMBC/HSQC data, which only Phase 2's real reconstruction run can answer.

### Gaps to Address

- NMRFx as a genuine primary alternative was not deeply vetted (docs TLS issues blocked direct verification; no independent confirmation of NMR-specific correctness for Bruker nuslist/FnMODE data). Handle by: proceeding with NMRPipe+SMILE as primary per the Backend Decision above, and treating an NMRFx spike-comparison as an explicit, named follow-up if native Windows support later becomes a hard requirement.
- Exact SMILE CLI flag/parameter syntax (iteration count, threshold, `-EA`/virtual-echo flags) not independently source-verified in this pass. Handle by: a short spike at the start of Phase 2 re-fetching the current SMILE manual/example scripts before writing the `nmrpipe_smile.py` backend module.
- WSL2 as the Windows workaround is inferred, not independently tested. Handle by: treating it as an explicit spike item in Phase 4, not asserting it as supported in requirements until validated.
- Whether SMILE alone (vs. needing an hmsIST/mddnmr fallback) clears the quality bar on this compound's specific 25-33% sampling is fundamentally an empirical question no amount of further desk research resolves. Handle by: Phase 2's exit criterion is exactly this test, with the fallback ladder pre-designed (Phase 1's `NusBackend` protocol) so adding a second backend later is additive, not a rewrite.
- Exact hypercomplex-component-count handling inside `bruk2pipe`/`nusExpand.tcl` for echo-antiecho experiments was described at the mechanism level but not verified against actual tool output. Handle by: the hard-fail assertion in Phase 1 (`n_sampled == len(nuslist)` derived from `FnMODE`) is the concrete safeguard; confirm the conversion tool's own convention empirically during Phase 1/2 implementation.

## Sources

### Primary (HIGH confidence)
- Direct inspection of `C20H32O2/{2,3,4}/{ser,nuslist,acqus,acqu2s}` (this project's real NUS data) — schedule/FnMODE/GRPDLY/byte-order facts grounded, not assumed
- Direct inspection of installed `nmrglue` 0.11 (`nmrglue.process.proc_base`, `nmrglue.fileio.pipe`) — confirms I/O-only capability, no CS/IST/SMILE function
- `analysis/NUS-RECONSTRUCTION-GUIDE.md` (this repo's authoritative task brief) — §2 failure root cause, §5 recommended pipeline, §6 TopSpin alternative, §7 fallback backends, §8 verification criteria, §10 ground-truth shift list
- `.planning/PROJECT.md` — v10.0 milestone definition and constraints
- Live codebase inspection: `src/lucy_ng/lsd/runner.py`, `cli/lsd.py`, `cli/webview.py`, `readers/bruker.py`, `pyproject.toml`, `cli/main.py` — architectural precedents
- https://www.ibbr.umd.edu/nmrpipe/install — NMRPipe platform matrix, version, csh requirement
- https://spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf, https://spin.niddk.nih.gov/bax/software/SMILE/ — SMILE manual and overview
- Kazimierczuk et al., "Pitfalls in compressed sensing reconstruction and how to avoid them," J. Biomol. NMR (https://pmc.ncbi.nlm.nih.gov/articles/PMC5504175/) — peer-reviewed, source for fabricated-noise-peak/virtual-echo/peak-splitting pitfalls
- NUScon (https://mr.copernicus.org/articles/2/843/2021/) — peer-reviewed, source for QC-gate metric design

### Secondary (MEDIUM confidence)
- https://github.com/eburakova/hmsIST and hmsIST primary literature (2012, 2017 papers) — distribution/licensing ambiguous, effectively unmaintained
- http://mddnmr.spektrino.com/man (v2.7 manual, Sept 2020) — live site has a TLS certificate mismatch, a currency/trust flag
- NMRFx: https://link.springer.com/article/10.1007/s10858-016-0049-6, 2025 biorxiv preprint, docs.nmrfx.org (TLS cert error blocked direct fetch, content via search snippet only)
- https://www.bruker.com/.../topspin-faqs.html, topspin-python-interface.html — official but does not confirm true headless/no-display automation
- Powers Wiki (bionmr.unl.edu) — community wiki, source of the "never click Calculate/Show table" TopSpin schedule-corruption warning
- `tlinnet/docker_relax` Dockerfile — working reference for containerized NMRPipe+mddnmr, not independently rebuilt/tested

### Tertiary (LOW confidence)
- WSL2-as-Windows-workaround for NMRPipe — inferred from IBBR's "Linux VM" guidance, not independently verified
- nmrPype (PyPI, PhiMykah/nmrPype) — pure-Python NMRPipe processing-verb reimplementation, reconstruction (SMILE/IST) support unverified, not part of the primary recommendation

---
*Research completed: 2026-07-12*
*Ready for roadmap: yes*
