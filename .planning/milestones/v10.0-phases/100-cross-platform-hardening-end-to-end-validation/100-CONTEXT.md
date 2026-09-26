# Phase 100: Cross-Platform Hardening + End-to-End Validation - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The milestone-closing phase of v10.0. Two independent bodies of work:

- **PORT (cross-platform hardening):** `lucy nus check` gains a platform preflight (Apple-Silicon `arch`/Rosetta, `csh`/`tcsh`, backend binaries) that reports readiness *before* a run and hard-blocks on critical gaps; plus a documented portability matrix (macOS-arm64-native / Linux-native / Windows-WSL2-gap). Extends the existing backend detection, does not replace it.
- **VAL (end-to-end validation):** the real empirical proof the whole milestone has deferred — reconstruct the actual C20H32O2 exp2 (COSY) / exp3 (HSQC) / exp4 (HMBC) via `lucy nus pipeline`, clear the guide's §8 quality gate, and prove a fresh `/lucy-ng:case C20H32O2` converges on a finite, rankable solution set instead of exploding to ~10⁶ candidates.

**In scope (PORT-01..02, VAL-01..02):**
- PORT-01: platform preflight in `lucy nus check` — critical checks (missing backend binary, no `csh`) fail-loud before any stage; soft checks (running under Rosetta/x86 emulation with tools present) warn but do not block; granular per-check readiness report.
- PORT-02: `docs/NUS-PORTABILITY.md` matrix; Windows/WSL2 workaround documented step-by-step but explicitly marked **documented-but-untested** (no Windows host confirmed); linked from CLAUDE.md/README.
- VAL-01: real reconstruction of exp2/3/4 passing the §8 gate (via the Phase-99 QC gate as the machine judge + a brief chemist visual confirm on PARTIAL).
- VAL-02: fresh `/lucy-ng:case C20H32O2` converges (LSD terminates, finite rankable set) on the newly reconstructed peak lists.

**Out of scope (later / other milestones):**
- hmsIST/mddnmr fallback backend (RECON-F1) — explicitly NOT pulled into this phase even on SMILE FAIL (see D-04).
- NMRFx / native-Windows backend pivot (RECON-F2); webview rendering of reconstructed 2D + QC (RECONUX-F2); per-peak recon-confidence → LSD weighting (RECONUX-F1).
- Re-litigating Phase-97/98/99 internals (params/schedule, reconstruction chain, QC gate, peak-pick bridge) — this phase *runs* and *validates* them, it does not change them.

**Invariant carried forward (Phases 98/99):** `case.md` stays **untouched** — the "CASE pipeline unchanged" invariant holds through milestone close. VAL-02 runs the real orchestrator unmodified.
</domain>

<decisions>
## Implementation Decisions

### VAL execution environment & evidence (D-01)
- **D-01 — VAL runs locally on this Apple-Silicon Mac.** NMRPipe+SMILE is a *native macOS Apple-Silicon target* per the locked v10.0 backend decision — it is simply **not installed on this dev machine yet** (verified 2026-07-18: `arm64`, macOS 26.5, `csh`/`tcsh` present, `nmrPipe`/`bruk2pipe`/`nusExpand.tcl` absent from PATH). This is an install gap, **not a platform blocker**, so there is no reason to route VAL to Sheldon.
  - **Install path:** native NMRPipe macOS Apple-Silicon build + SMILE plugin, `bin/` on PATH — documented as a local prerequisite in CLAUDE.md, exactly like the existing LSD-solver prerequisite. The install itself is a manual step (user/Claude), **not a code deliverable** — the phase only documents it.
  - **Green gate before VAL:** the PORT-01 preflight (`lucy nus check`) is the tool that confirms the local install is ready before the VAL run starts — PORT and VAL interlock, they do not run side-by-side.
  - **Evidence form:** commit the real reconstructed peak JSONs + QC report + a `VALIDATION.md` (§8 verdict per experiment + case-convergence result) as the phase's durable, reproducible-by-hand evidence. Validation runs on the platform the milestone claims as "native supported", not a frozen remote snapshot.

### VAL acceptance thresholds (D-02, D-03)
- **D-02 — VAL-01 §8 pass = QC PASS, or PARTIAL only when soft-only + chemist confirm.** The Phase-99 QC gate is the machine judge (it already encodes §8 as PASS/PARTIAL/FAIL).
  - **PASS** → passed.
  - **PARTIAL** → accepted **only if** the violated checks are all *soft* (edited-sign self-consistency, COSY diagonal symmetry) **and** a brief chemist visual confirms the connectivity is usable for CASE.
  - Any **critical** violation (quaternary-C 1-bond correlation, ppm calibration, signal-to-ridge dominance) = FAIL = not passed — these are exactly the fabricated-cross-peak modes that poison LSD.
  - Rationale: the QC gate was calibrated only against *synthetic* anchors (Phase 99 QC-02); real C20H32O2 is its first true test, so a milestone-closing one-off local run warrants a human eyeball on PARTIAL — cheap here, not a CI burden. Pure-machine acceptance is too blind for milestone close; pure-PASS-on-all-three risks blocking on a soft nitpick.
- **D-03 — VAL-02 bar = LSD terminates + finite rankable set.** Success = LSD runs to completion (no ~10⁶ timeout/explosion, the original 2026-07-09 failure mode) and produces a finite, 13C-prediction-rankable candidate set. **The correct C20H32O2 structure ranking top-N is a bonus, not a condition** — that would depend on ranking quality + regiochemistry resolution beyond "reconstruction fixed the connectivity gap". This is the most honest bar, mapped directly onto the original timeout.
- **VAL-01/VAL-02 coupling:** VAL-01 is necessary but **VAL-02 is the real bar.** A soft-PARTIAL reconstruction that still lets CASE converge to a rankable set is a genuine milestone pass.

### VAL-fail contingency (D-04)
- **D-04 — Bounded tuning budget, then honest stop.** If the real reconstruction does not clear the §8/QC gate critically:
  - **Bounded, pre-defined tuning budget:** SMILE knobs (`-maxIter`, `-thresh`, virtual-echo toggle), apodization, phase defaults, and trying the higher 33% sampling density. The budget must be defined up front so it stays "did we drive it correctly", not endless drift.
  - **After the budget:** persistent FAIL is recorded as a **documented limitation** in `VALIDATION.md` + ROADMAP, with **RECON-F1 (hmsIST/mddnmr fallback)** named as the tracked next step.
  - **hmsIST NOT pulled into this phase** even on FAIL — it is a deferred future-requirement with a whole new backend path; grafting it here would blow the milestone-closing phase open (rejected Option 2).
  - **No indefinite hard block** — SMILE is a third-party tool; if 25% sampling on this sample is simply too sparse, no code of ours fixes it, and blocking forever mis-attributes a backend limit to our code (rejected Option 3).
  - **PORT ships independently of the VAL outcome.** PORT-01/02 deliver regardless of whether SMILE clears the bar, so the phase never fully fails — worst case is "PORT delivered + VAL honestly documents a backend limitation with RECON-F1 as the path".

### PORT semantics (D-05, D-06)
- **D-05 — PORT-01 preflight: critical = fail-loud block, soft = warn.** Critical gaps (missing backend binary, no `csh`) make `reconstruct`/`pipeline` abort fail-loud (exit≠0) **before any stage runs** — consistent with the RECON-04 fail-loud wrapper and the D-07 write boundary. Soft conditions (running under Rosetta/x86 emulation but tools present) are logged loudly but do **not** block. `lucy nus check` reports both granularly per-check.
- **D-06 — PORT-02 matrix lives in a dedicated `docs/NUS-PORTABILITY.md`.** Rows: macOS-arm64-native / Linux-native / Windows-WSL2-gap. The WSL2 workaround is documented step-by-step but explicitly marked **documented, untested** (no Windows host confirmed available — do not hang the phase on acquiring one). Linked from CLAUDE.md/README. Satisfies PORT-02's "every gap investigated and written down, not silently accepted".

### Claude's Discretion
- Exact preflight check API surface and how the platform section extends the existing `NusBackend.diagnose()` / `lucy nus check` output shape (D-05) — planner discretion within the fail-loud/D-07 pattern.
- Exact `docs/NUS-PORTABILITY.md` layout, and whether the install-prerequisite doc block sits in CLAUDE.md, README, or both (D-01/D-06).
- The precise contents/format of `VALIDATION.md` and where the committed real peak lists live vs the known-bad QC-02 fixtures (D-01) — planner discretion, but must not overwrite the known-bad regression fixtures.
- The exact numeric tuning-budget bounds (how many knob combinations / iterations before honest-stop) (D-04) — planner sets a concrete, finite budget.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone planning
- `.planning/REQUIREMENTS.md` — PORT-01..02, VAL-01..02 (the four requirements this phase closes); the locked backend decision (native macOS Apple-Silicon + Linux, Windows = documented WSL2/VM gap); RECON-F1 (deferred hmsIST fallback, the D-04 tracked next step).
- `.planning/ROADMAP.md` § Phase 100 — goal + 4 success criteria (preflight, portability matrix, §8-gate reconstruction, case convergence).
- `.planning/research/SUMMARY.md` § Backend Decision — why NMRPipe+SMILE, native platforms, the Windows gap rationale.

### Architecture & pitfalls
- `.planning/research/ARCHITECTURE.md` — `nus/` package layout, `NusBackend` protocol (keeps hmsIST/NMRFx additive), the "CASE pipeline unchanged" invariant.
- `.planning/research/PITFALLS.md` — csh-piped NMRPipe stages silently passing failures (the RECON-04 lineage PORT-01 blocking extends); ridge/over-under-converged reconstruction (what VAL-01 §8 actually tests on real data).
- `.planning/phases/99-peak-pick-bridge-qc-gate-cli/99-CONTEXT.md` — the QC gate that judges VAL-01 §8 (D-01/D-02 verdict semantics, critical-vs-soft tiers, D-07 write/quarantine boundary PORT-01 blocking is consistent with).
- `.planning/phases/98-reconstruction-processing/98-CONTEXT.md` — the `NusRunner.reconstruct()` chain + knob defaults (SMILE `-maxIter`/`-thresh`/virtual-echo, apodization, phase) that the D-04 tuning budget adjusts; QF/COSY branch + F1 phase defaults flagged PROVISIONAL → this phase is the real-data spike that confirms or tunes them.

### Task brief + data (the authoritative §8 gate + ground truth)
- `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` **§8** (the literal "what a good reconstruction looks like" definitions VAL-01 checks: ~17 protonated C each with one/CH2-two HSQC correlation, the 5 quaternaries 142.0/135.86/79.35/36.23/37.86 with NO 1-bond correlation, clean edited signs, ridge-free HMBC, a real aliphatic COSY network not just the OH-ridge at 5.32) and **§10** (ground-truth 1D shifts).
- `.../C20H32O2/analysis/nmr_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2}.json` — the existing **known-bad home-IST** peak lists (QC-02 FAIL regression floor). **Must NOT be overwritten** by the VAL run — the real reconstructed lists are the new evidence, the known-bad ones stay as the regression fixture.
- `.../C20H32O2/analysis/nmr_peaks/{13C_exp7_wide,13C_exp6_narrow,1H_exp1}.json` — the trusted 1D reference the QC gate cross-checks against.
- The raw Bruker experiment dirs for exp2/exp3/exp4 under the same C20H32O2 tree — the `lucy nus pipeline` input.

### Existing code precedents to follow
- `src/lucy_ng/nus/backends/__init__.py` + `nus/backends/nmrpipe_smile.py` — `NusBackend.is_available()/missing_tools()/diagnose()`, `shutil.which` + SMILE plugin probe. PORT-01's platform preflight extends `diagnose()` (add `arch`/Rosetta/`csh` checks), does not rewrite it.
- `src/lucy_ng/cli/nus.py` — the `lucy nus check` command (currently backend-only) + `reconstruct`/`pipeline`/`qc`; PORT-01 blocking hooks in here at the pre-stage gate; all subcommands `--format json`.
- `src/lucy_ng/cli/lsd.py` — `lucy lsd check` is the precedent pattern for the preflight readiness report (NUS-01 already mirrored it).
- `src/lucy_ng/nus/runner.py` + `nus/postprocess.py` — the `NusRunner.reconstruct()` chain + processing knobs the D-04 tuning budget adjusts; RECON-04 fail-loud `run_stage()` wrapper the PORT-01 blocking is consistent with.
- `src/lucy_ng/nus/qc.py` — `run_qc_checks()` → PASS/PARTIAL/FAIL, the D-02 machine judge for VAL-01.
- `CLAUDE.md` § "Local prerequisites" — where the NMRPipe+SMILE install prerequisite is documented (alongside the existing LSD-solver + reference-DB entries).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NusBackend.diagnose()` (`nus/backends/`) — existing backend readiness dict; PORT-01 extends it with platform checks (`uname -m`/arch, Rosetta detection, `csh`/`tcsh` presence) rather than a new mechanism.
- `lucy nus check` / `lucy lsd check` — the established "preflight readiness, fail-loud on missing tool" CLI pattern PORT-01 follows.
- `NusRunner.reconstruct()` + `postprocess.py` — the chain VAL runs on real data; its SMILE/apodization/phase knobs are the D-04 tuning surface.
- `nus/qc.py::run_qc_checks()` — the §8→PASS/PARTIAL/FAIL judge for VAL-01.
- `lucy nus pipeline` (Phase 99) — the single end-to-end command VAL-01 invokes on exp2/3/4.

### Established Patterns
- CLI groups in `cli/main.py` via `add_command`; each subcommand `--format json`; import-safe `lucy nus` group.
- RECON-04 fail-loud subprocess wrapper (exit-code + non-empty output check) — PORT-01 critical-block extends the same fail-loud philosophy to the *pre-run* boundary.
- D-07 write/quarantine boundary (Phase 99) — enforcement lives at the pipeline boundary, `case.md` untouched; PORT-01 blocking sits at the same layer.

### Integration Points
- PORT-01: `lucy nus check` platform section → same `diagnose()` extension consumed by `reconstruct`/`pipeline` as a pre-stage gate (critical → exit≠0).
- VAL: local NMRPipe+SMILE install → `lucy nus check` green → `lucy nus pipeline` exp2/3/4 → real peak JSONs + QC report → `/lucy-ng:case C20H32O2` (orchestrator unchanged).
- PORT-02: `docs/NUS-PORTABILITY.md` (new) linked from CLAUDE.md/README; install prerequisite added to CLAUDE.md § Local prerequisites.

</code_context>

<specifics>
## Specific Ideas

- **The Mac is a first-class native target, not a fallback.** The earlier "dev Mac can't run the backend" framing was wrong — it's an uninstalled tool, not a platform limit. VAL therefore runs on exactly the reference platform the milestone claims (macOS Apple Silicon), which is stronger evidence than a remote Linux snapshot.
- **VAL-02 is the milestone's actual success bar, VAL-01 is the gate that makes it trustworthy.** Frame verification around "did CASE converge on a rankable set" (D-03), with VAL-01's §8 pass (D-02) as the necessary precondition that guarantees the peaks feeding it are not fabricated.
- **The §8 guide is authoritative for VAL-01** — the 5 named quaternaries, ~17 protonated carbons, the OH-ridge-at-5.32 COSY smell test, "signal-to-ridge better than the current home-IST lists". Validate against §8, not invented criteria.
- **Do not overwrite the known-bad QC-02 fixtures** — they are the regression floor proving the gate discriminates; the real reconstructed lists are new evidence alongside them.
- **PORT is decoupled from VAL** — it ships whether or not SMILE clears the bar, so the phase always delivers something even in the worst empirical case.

</specifics>

<deferred>
## Deferred Ideas

- **hmsIST/mddnmr fallback backend (RECON-F1)** — explicitly NOT pulled into this phase even on a SMILE FAIL (D-04); it is the *documented next step* if the tuning budget is exhausted, tracked in ROADMAP/`VALIDATION.md`, its own future phase.
- **Real WSL2/native-Windows verification** — PORT-02 documents the WSL2 path but marks it untested (no Windows host confirmed); actual verification / NMRFx pivot (RECON-F2) is deferred.
- **Webview rendering of reconstructed 2D + QC report (RECONUX-F2)** and **per-peak recon-confidence → LSD constraint weighting (RECONUX-F1)** — deferred (v1.x).

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap` (score 0.6, generic keyword match) — CASE-solver / azulene regiochemistry defect, unrelated to PORT/VAL. **Not folded** (same determination as Phases 97/98/99).
- `2026-06-30-ranking-tests-hardfail-without-hosegen` (score 0.4, keyword match) — hosegen ranking-test-infra todo, unrelated to this phase. **Not folded.**

</deferred>

---

*Phase: 100-cross-platform-hardening-end-to-end-validation*
*Context gathered: 2026-07-18*
