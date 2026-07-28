# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v7.0 — Statistical 4J Detection (ABANDONED)

**Abandoned:** 2026-03-12
**Phases:** 6 planned, 5 executed | **Plans:** 9 executed, all reverted

### What Was Built
- Schema v7 migration with coupling_path_stats table (3.78M entries from 895K compounds)
- CouplingPathStatsGenerator with checkpoint/resume pattern
- StatisticalDetector.detect_4j_coupling with three-tier classification
- detect_4j_batch with HOSE code pre-loading optimization
- CLI commands: `lucy detect 4j` and `lucy detect 4j-batch`
- Agent skill updates for statistical 4J detection across 3 agents
- **All reverted** — net code change: 0 lines

### What Worked
- **Rapid prototyping**: 5 phases (9 plans) executed in 2 days — fast enough to fail cheaply
- **Calibration before UAT**: Phase 63 calibration caught the fundamental flaw before wasting time on agent integration testing
- **Clean revert**: Single `git revert` cleanly removed all v7.0 code, 860 tests pass

### What Was Inefficient
- **Late calibration**: Should have run calibration on a small sample (1K compounds) BEFORE building the full pipeline (phases 59-62). The fundamental distribution problem would have been visible with 10K entries, not 3.78M
- **Full generation run**: 3.78M entries generated over hours, only to discover the metric is useless. A proof-of-concept with 1% sample would have saved significant compute time

### Patterns Established
- **Calibrate early**: For statistical approaches, validate the metric on a small sample before building full infrastructure
- **Fail fast, fail cheap**: When an approach has a theoretical risk, test the theory before building the tooling

### Key Lessons
1. **Aggregate pair distance statistics don't discriminate 4J**: Most atom pairs in any molecule are 5+ bonds apart, making "long-range path probability" meaningless as a discriminator
2. **The 4J problem needs solver-level exploration**: Statistical pre-filtering can't work because the question isn't "are these atoms far apart in general" but "are they far apart in THIS molecule" — which requires the solver
3. **Abandoned milestones are still valuable**: The post-mortem and calibration data prevent re-attempting the same failed approach

### Cost Observations
- Model mix: ~40% opus (orchestration, calibration analysis), ~60% sonnet (execution)
- Sessions: ~4
- Notable: 3 days of work with zero net code change — but the learning was essential

---

## Milestone: v6.0 — Skill Quality Overhaul

**Shipped:** 2026-03-10
**Phases:** 4 | **Plans:** 7 | **Sessions:** 3

### What Was Built
- Factored case.md orchestrator with 3 extracted reference files (progress-format, loop-patterns, advisory-templates)
- 4J HMBC coupling awareness pipeline: nmr-chemist flags → lsd-engineer defers → solution-analyst verifies
- Orchestrator message validation with RESEND-REQUIRED protocol
- Natural-language trigger phrases in all 5 skill descriptions + routing decision tree
- Error recovery in predict (HOSE miss) and dereplicate (0-match), dry-run gate in sanitise
- Version compatibility check in status, smoke test mode (--smoke-test) in CASE orchestrator

### What Worked
- **Auto-advance pipeline**: /gsd:plan-phase --auto executed 4 phases (plan → verify → execute → verify → complete) in a single session with minimal human interaction
- **Parallel execution**: Plans 57-01 and 57-02 ran in parallel (Wave 1) with non-overlapping file sections, completing in ~6 minutes combined
- **No Python changes**: Pure .md skill editing meant zero test failures, zero regressions, zero build issues — fastest milestone to ship
- **Integration checker**: Caught 2 genuine wiring gaps (aromatic expectation relay, 4J status validation) that individual phase verifiers missed

### What Was Inefficient
- **gsd-tools init can't find milestone-scoped phases**: Phases 55-58 exist in v6.0-ROADMAP.md but init returns phase_found=false. Required manual directory creation and variable setup each time
- **SUMMARY frontmatter inconsistency**: No `requirements-completed` field in SUMMARYs, making 3-source cross-reference incomplete in audit. The verification + traceability table was sufficient but the third source was weak

### Patterns Established
- **"Use when:" trigger phrase pattern**: Skill frontmatter descriptions with explicit trigger phrases for intent routing
- **Dry-run gate pattern**: READ-ONLY scan → manifest report → exact "proceed" confirmation before writes
- **Reference extraction pattern**: Large static content in references/ subdirectory, loaded on-demand via "Read file:" directives
- **Smoke test mode**: --smoke-test flag for 1-iteration pipeline validation with structured checkpoint table

### Key Lessons
1. **Skill-only milestones are fast**: 4 phases in 1 day with auto-advance. No test suite to run, no build to break — focus on content quality and integration wiring
2. **Integration checking matters most for .md changes**: Individual file verification passes easily but cross-file wiring (who relays what field to whom) is where gaps hide
3. **Milestone-scoped roadmaps need better tool support**: The init tool's inability to find phases in milestone-specific roadmaps added friction to every phase

### Cost Observations
- Model mix: ~30% opus (orchestration), ~70% sonnet (planning, execution, verification)
- Sessions: 3 (phases 55-56, phases 57-58, audit + complete)
- Notable: Auto-advance eliminated context switches between plan/execute/verify — single session handled phases 57 and 58 end-to-end

---

## Milestone: v9.0 — CASE Reliability & Skill Consolidation

**Shipped:** 2026-06-17
**Phases:** 14 (72–85) | **Plans:** 34

### What Was Built
- Solution plumbing: `lucy lsd run`/outlsd produces real ranked SMILES + fails loud; deterministic cross-ring COSY derivation (`lucy detect aromatic-cosy`).
- Native-only constraint translation (SYME→BOND/COSY, DEFF NOT→DEFF F/FEXP) across all paths + permutation constraint preservation; devils-advocate G5–G8 gates.
- Peak-picking integrity: SNR-floor for 13C (FIX-08) and HMBC (FIX-12) + overcount guard.
- Constraint-hardness guard (FIX-10); blind-UAT skill decontamination (FIX-09); Kekulé-aromatize-before-predict (FIX-11).
- Validation: CASE9 solved (UAT-04) + CASE1 clean emergent pass (UAT-03).

### What Worked
- **Goal-backward blind UAT as the gate**: repeatedly failing the blind UAT (Phases 76/78/79/80) surfaced the *real* upstream defects (peak-picking) instead of letting a green unit suite mask them.
- **Independent RDKit verification by a tainted bookkeeper**: kept "found ibuprofen" claims honest (caught the ortho-vs-para distinction and the rank-vs-predict MAE discrepancy).
- **Fix the model, not just the skill**: the single highest-leverage fix was `CLAUDE_CODE_SUBAGENT_MODEL=inherit` — many "skill" failures were Sonnet-4.6-driven.

### What Was Inefficient
- **Long chain of failed gates (76→78→79→80→81)**: each blind UAT exposed one more upstream layer (LSD mechanism → carbonyl masking → 4J trap → peak-picking flood). Earlier raw-spectrum inspection would have found the snr_floor=3 noise flood sooner.
- **Auto-memory contaminated the "blind" UAT**: per-data-dir auto-memory leaked the answer into supposedly-blind runs; required quarantine + `autoMemoryEnabled:false` + workspace-trust to make blind runs repeatable.

### Patterns Established
- **Blind-UAT hygiene**: quarantine per-data-dir memory + `autoMemoryEnabled:false` before each blind run; orchestrating instance is bookkeeper only.
- **SNR-floor over fraction-of-max**: noise-relative thresholds for both 1D and 2D pickers so weak-but-real signals survive.
- **Constraint-hardness discipline**: statistical/uncertain inferences stay advisory; never hard PROP/BOND that can exclude the truth.

### Key Lessons
1. A green unit suite is not validation — only the end-to-end blind UAT against real spectra caught the upstream peak-picking defects.
2. Confirm the runtime model before blaming the skill — a silent subagent-model override caused failures no skill edit could fix.
3. Auto-memory and repeatable blind testing conflict; isolate test fixtures from persistent memory.

### Cost Observations
- Model mix: Opus 4.8 for CASE runs + orchestration (the model upgrade was itself the decisive fix)
- Notable: the winning run needed 0 coordinator bypass interventions — the mechanism finally carried the result

---

## Milestone: v9.1 — CASE Final-Answer Correctness & Verification Gates

**Shipped:** 2026-06-29
**Phases:** 4 (86–89) | **Plans:** 9 | **Timeline:** 6 days (2026-06-23 → 06-29) | **Tests:** 1131 passing

### What Was Built
Three "clean-but-wrong" CASE failure classes closed with verification gates: RANK (ranker↔predict unified onto one DB-first predictor), IDENT (installed `lucy identify` + post-solution `G-IDENT` gate stop naming hallucination), MULT (per-family multiplicity search + MAE-independent `coverage_gate` + binding `G-MULT` flag). A blind-UAT gate (89) validated all three end-to-end on independent blind instances.

### What Worked
- **Blind UATs as the real acceptance test.** Each fix was a skill-prompt edit not unit-testable in-session; the fresh-blind-instance runs (RDKit-verified by InChIKey) were the only honest validation — and caught what static checks couldn't.
- **The gap-closure loop inside a phase.** Phase 87's first blind UAT exposed GAP-87-A (`verify_case_solution.py` unreachable from a CASE data dir); a same-phase `--gaps` closure (move core into installed `lucy identify`) fixed it and the re-run passed. Defects found by the UAT became immediate, scoped closures.
- **Code review on the small Python seams paid off** (WR-01 dot-suffix accession, CR-01 corrupt-DB crash, WR NaN/inf detector) — each a real correctness fix on the load-bearing deterministic pieces.

### What Was Inefficient
- **CASE runs stalled ~5.5 h** (lsd-engineer went idle after the solver without signalling) before the anti-stall + coordinator filesystem-recovery hardening — a message-driven-orchestration footgun only visible in a real long run.
- The `lucy identify` reachability gap should have been caught at plan time (the deferred `lucy identify` CLI was the actual delivery mechanism all along) — the blind UAT, not planning, surfaced it.

### Patterns Established
- **Verification gate triad:** binding deterministic tool (`lucy identify` / `coverage_gate`) + independent LLM advisory (`G-IDENT` / `G-MULT`) + blind-UAT acceptance. SEARCHED-not-RANKED and MAE-independent guardrails as a pattern for "wrong-class" defects.
- **Orchestrator-as-bookkeeper for blind UATs:** contaminated session verifies (RDKit) + records, never runs the CASE.

### Key Lessons
- For skill-prompt fixes, **a fixture that exercises the live agent (blind UAT) is the acceptance test** — in-repo unit tests only cover the Python seams.
- A passing in-repo verification can still hide a **delivery/reachability** gap (repo-only script vs installed CLI). Ask "can the runtime actually reach this?" at plan time.
- New defect classes surface from real runs (CASE4 azulene regiochemistry) — budget for a "surface, don't necessarily fix" UAT lane (UAT-03 spirit).

### Cost Observations
- Model mix: Opus for planning + blind CASE runs; Sonnet for executor/checker/verifier subagents.
- Notable: the milestone was driven phase-by-phase with `--chain` (plan→execute), with the human running the blind UATs out-of-session.

---

## Milestone: v9.2 — CASE Web-View

**Shipped:** 2026-07-07
**Phases:** 3 (90–92) | **Plans:** 10 | **Tasks:** 17

### What Was Built
A read-only web dashboard for CASE runs: `lucy webview serve/stop/status` (FastAPI, optional `lucy-ng[webview]` extra), four JSON/SVG endpoints with graceful degradation, RDKit SVG depictions, a single-file vanilla-JS auto-refresh frontend (no build step), and orchestrator auto-launch from `case.md`. Live-validated on a CASE1 run (ibuprofen, Rank 1 MAE 0.25).

### What Worked
- **Nyquist test-first (Wave 0) throughout.** Every phase opened with a RED grep/contract or API-contract test scaffold, so the implementation waves had an executable target and the plan-checker could verify coverage before execution.
- **`--chain` plan→execute pipeline** ran each phase end-to-end with sub-agents (research→plan→verify→execute→verify), the human validating live in-browser at the phase checkpoints.
- **Design-spec discipline:** the milestone's Stage-1/Stage-2 split was fixed in the design spec up front, so "what's missing" at close (formatted log, spectra tabs) was already a documented deferral, not a surprise gap.
- **Live human-verify caught real issues** the automated gates could not: the empty-log-at-t=0 finding (fixed `f782ea8`) came only from watching a real run.

### What Was Inefficient
- **The decision-coverage gate false-negatived** on Phase 91 because plans cited `D-NN` in task bodies (stripped code fences / non-designated sections) rather than in `must_haves`/`truths`; needed a manual truths-citation pass. Worth teaching the planner to cite decisions in designated sections.
- **`case.md` edits can only be verified in a fresh session**, so Phase 92's live behavior was a manual gate — one round-trip of "edit → user runs fresh CASE → feedback" per finding.
- **Post-code-review blockers on Phase 91** (null-rank tier drop, kekulize-500, empty-SMILES refetch) were real and only surfaced by the adversarial code-review agent after execution — earlier review in-wave might have caught them cheaper.

### Patterns Established
- **Grep-contract tests over markdown skill files** (`test_case_md_wv07.py`) as the automatable half of verifying `case.md` edits, paired with an explicit manual fresh-session verify item.
- **Server survival by OS, not orchestration:** `subprocess.Popen(start_new_session=True)` lets a launched server outlive the agent team with zero keep-alive logic.
- **Import-safety invariant** (`[webview]` optional extra kept out of the core import path; fastapi/RDKit imported lazily inside `create_app()`), verified by a `sys.modules` assertion test.

### Key Lessons
- A dev-tool dashboard's design contract can live in CONTEXT.md + the design spec; a separate UI-SPEC added little for a single-file monitor. Skipping it was correct.
- When a phase edits a sensitive shared skill file, budget for a fresh-session manual verify loop and lean on grep-contract tests for the rest.

### Cost Observations
- Model mix: opus for planning, sonnet for research/executors/verifiers/checker.
- Notable: the whole milestone ran as three `--chain` pipelines (one per phase) plus an interactive live-verify + fix loop; the largest single cost was executor waves, not planning.

---

## Milestone: v9.3 — CASE Web-View Stage 2

**Shipped:** 2026-07-12
**Phases:** 4 (93–96) | **Plans:** 16 | **Tasks:** 23

### What Was Built
Formatted markdown run log + 4-tab framework (93); data tables — ¹³C/HSQC/HMBC/COSY + LSD constraint inventory (94); 1D real Bruker spectra + peak overlay with `.run_manifest.json` path wiring + matplotlib `[webview]` pipeline (95); 2D HSQC/HMBC/COSY contour plots + cross-peak overlay with block-max decimation, MAD levels, mtime cache (96).

### What Worked
- **The manual browser checkpoint earned its keep.** Phase 96's `autonomous:false` checkpoint — driven by rendering the real CASE1 PNGs and viewing them — caught a 2D F1/y-axis inversion that the headless test *asserted in the wrong direction* and so happily passed. Visual verification against real data found what the test couldn't.
- **Adversarial gates each caught a real, distinct defect:** plan-checker (2 blockers: a `-k` selector matching zero tests; a frozen-signature contract break), UI-checker (typography 4-size cap), code-review (CR-01 placeholder layout-jump). None were rubber-stamps.
- **Purely-additive phase design** (extend `spectra.py` in place, mirror the 1D→2D pattern) kept the diff analog-driven and low-risk; PATTERNS.md made the 1D→2D mapping explicit.

### What Was Inefficient
- The headless axis test encoded the *wrong* expected direction and passed green — a reminder that a passing test proves consistency with its own assertion, not correctness. Spatial/visual contracts (axis direction, aromatic-top-left) need either a golden-image check or a human look.
- `mypy`/`ruff` over the whole repo surfaces large pre-existing debt unrelated to the phase; scoping checks to the changed files avoided false alarms but the debt remains.

### Patterns Established
- **Render-and-look verification for image outputs:** for server-rendered chart PNGs, render against a real dataset and inspect the actual pixels (headless + browser) rather than trusting `ylim[0] > ylim[1]`-style proxies.
- **figsize parity across real + placeholder render paths** (CR-01) so a panel never changes height when it flips between "unavailable" and real data.

### Key Lessons
- A green test is only as good as its assertion — for direction/orientation/layout, assert the *spatial* outcome or verify visually.
- Advisory gates (UI-check, code-review) are worth running even in an auto-chain: three of them each found a distinct real defect here.

### Cost Observations
- Model mix: orchestration on Opus; researcher/planner-checker/executor/verifier/reviewer subagents on Sonnet.
- Notable: ran as a single `--chain` discuss→plan→execute→verify→complete pipeline with one interactive manual-checkpoint + inline fix loop (axis fix + code-review fixes). Verification/review caught 4 real defects post-plan.

---

## Milestone: v10.1 — JCAMP-DX 2D Ingestion (CLOSED PARTIAL)

**Closed:** 2026-07-28 (not shipped-complete)
**Phases:** 3 (101–103) | **Plans:** 9 | **Commits:** 77 | **Span:** 2026-07-23 → 2026-07-28

### What Was Built
- Pure-Python `readers/jcamp.py`: 1D `.dx` → `Spectrum1D`, 2D NTUPLES DIFDUP pages → `Spectrum2D`, closing the gap where nmrglue returns `None` for 2D NTUPLES assembly
- Vendored New-BSD DIFDUP/SQZ/DUP/PAC line decoder (`_jcampdx_decode.py`) — zero nmrglue private-API, mypy-strict, CI-runnable on a committed real fixture
- `lucy jcamp` — one command from JCAMP directory to QC-graded peak lists, reusing the Phase-99 bridge and the byte-unchanged QC gate
- Thin 1D bridge whose payload matches `cli/pick.py::pick_1d` exactly, so the unchanged gate discovers it as trusted 1D reference (proven un-mocked)
- The repo's first committed SHA-256 byte-unchanged guard for `case.md` + the 5-agent team

### What Was NOT Achieved
The milestone's actual success bar. JVAL-01's real-data QC verdict is a critical FAIL, and JVAL-02 (CASE convergence) was never attempted because the FAIL correctly produced no consumable peaks. The plumbing works; the proof that it is *usable* does not exist yet. Closed via the plan's D-10 honest-partial-close on an explicit user decision — the second consecutive milestone (after v10.0) to stop honestly rather than inflate a result.

### What Worked
- **Real fixtures as the correctness oracle, not mocks.** Phase 101 opened by committing a real trimmed DIFDUP fixture plus RED tests that every later plan had to turn GREEN. This was a direct correction of the Phase-100 mock-only-verification learning, and it held.
- **Citing raw headers instead of trusting the reader's own output.** When the §10 cross-check missed 3 of 20 carbons, the tempting story was "our ppm axis is broken" — the highest-risk failure class of this milestone. Reading the raw JCAMP header *and* the untouched sibling Bruker `acqus`/`procs` settled it in minutes with code-external evidence: `exp6`/narrow was exported, `exp7`/wide was not.
- **Independent verification catching a self-reported "clean".** Phase 103's code review found a silent-ignore defect (CR-01) in code the phase itself had shipped and described as clean — in exactly the behaviour class the plan's must-haves ruled out.
- **Mutation testing to confirm a gap was really closed.** Reverting the guard made the new regression test fail; stubbing the rebuild call site made the call-site test fail. Diff-reading would not have proven either.

### What Was Inefficient
- **Three tests were vacuous and shipped that way.** `assert exception is None or isinstance(exception, SystemExit)` is true on every outcome; an assertion read stdout where the message lands on stderr; a `set()` collapse passed even with the call site deleted. All three were written *by* the phase whose must-haves they were supposed to pin, and all three were only caught by an outside reviewer that executed them rather than read them.
- **A knob matrix was defined before knowing whether the failure was knob-shaped.** All 8 HSQC cells produced the same quaternary hit. Testing one cell for knob-sensitivity first would have reached "this is not tunable" far sooner.
- **The `gsd-code-fixer` agent wrote its changes but neither committed nor verified them**, returning an empty report. The orchestrator had to re-derive the diff, re-run the behaviour, and run the suite before committing.

### Patterns Established
- **Header-citation diagnosis:** when a reader's output looks wrong, quote the raw file and the vendor's own parameter files before touching the reader. Code-external evidence beats a code-internal argument.
- **`[~]` for partial requirements:** a checkbox that says `[x]` while the traceability table says "Partial" is a lie that outlives the milestone in the archive.
- **Write-boundary honesty compounds:** because the D-07 boundary refused to write peaks on FAIL, JVAL-02 could be recorded as *not attempted* rather than fabricated or half-run.

### Key Lessons
1. **A test that cannot fail is worse than no test** — it converts an unknown into a false assurance. Prove a new test fails against the unfixed code before trusting it.
2. **"Knob-independent" is a finding, not a dead end** — reproducing a failure across the whole parameter matrix is what converts "we didn't tune enough" into "this needs a different fix", and it is what made the honest close defensible.
3. **Ask which artefact is missing before blaming the code.** Two milestones in a row (v10.0 SMILE memory, v10.1 narrow exp6) were limited by the environment or the input, not by lucy-ng.
4. **Verify agent self-reports.** Executor, fixer and verifier each made at least one claim this milestone that did not survive an independent check — one full-suite claim, one silent no-op, one "clean" that a reviewer disproved.

### Cost Observations
- Model mix: orchestration on Opus, executors/verifier/reviewer on Sonnet
- Notable: the highest-value spend was the *unplanned* read-only ppm-axis diagnostic — ~25 minutes that converted a suspected reader bug into a ruled-out risk class, and it only happened because the close was paused to ask.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v10.1 | ~6 | 3 | Real fixtures as the correctness oracle (not mocks); raw-header citation to rule out a suspected reader defect; second consecutive honest PARTIAL close |
| v9.0 | many | 14 | Blind UAT as the real gate; fix the runtime model, not just the skill; blind-UAT memory hygiene |
| v7.0 | ~4 | 6 | ABANDONED — calibrate statistical metrics early before building infrastructure |
| v6.0 | 3 | 4 | Auto-advance pipeline; pure .md editing; integration checker for wiring |

### Cumulative Quality

| Milestone | Tests | Coverage | Skill Lines |
|-----------|-------|----------|-------------|
| v10.1 | 1469 passing (8 skipped, 1 xfailed) | — | 5-agent team + orchestrator, byte-frozen and SHA-256-guarded |
| v9.0 | 1081 passing | — | 4-agent team + orchestrator (repo/.claude, symlinked) |
| v7.0 | 860 (7 skipped) | — | ~4,200 (unchanged — all code reverted) |
| v6.0 | 867 (unchanged) | — | ~4,200 (skills + agents, factored with references) |

### Top Lessons (Verified Across Milestones)

1. Integration wiring is the highest-risk area for multi-agent skill architectures — individual files pass verification but cross-file field relay is where gaps hide
2. Calibrate statistical approaches on small samples before building full infrastructure — the distribution problem in v7.0 was visible at any scale
3. A green unit suite ≠ validation — the end-to-end blind UAT against real data is the only gate that catches upstream (peak-picking) defects (v9.0)
4. Verify the runtime model/config before attributing failures to the skill — a silent subagent-model override drove much of the v9.0 failure chain
5. A test that cannot fail is worse than no test — prove a new test fails against the unfixed code before trusting it (v10.1: three vacuous tests shipped by the phase whose must-haves they were meant to pin)
6. Verify agent self-reports rather than relaying them — executor, fixer and verifier each made a claim in v10.1 that did not survive an independent check
