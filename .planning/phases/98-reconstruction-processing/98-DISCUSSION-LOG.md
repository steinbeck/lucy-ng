# Phase 98: Reconstruction + Processing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-13
**Phase:** 98-reconstruction-processing
**Areas discussed:** Skript-Strategie, Phasierung/Kalibrierung, Intermediate-Files, Test-Strategie

---

## Skript-Strategie (pipeline orchestration)

| Option | Description | Selected |
|--------|-------------|----------|
| Python-orchestriert, pro Stufe | Each nmrPipe stage as its own Python subprocess with an intermediate file; no csh pipe. Per-stage exit-code + output-non-emptiness check → RECON-04 native, avoids Pitfall 14. | ✓ |
| Generierte .com-Skripte (GUI-Template-Stil) | Full csh pipe chains on disk (bruker-GUI fid.com style). Closer to SMILE tutorials, but fail-loud through the pipe is harder and csh-dependent. | |
| Du entscheidest | Planner picks the form as long as RECON-04 is hard-met. | |

**User's choice:** Python-orchestriert, pro Stufe (recommended)
**Notes:** Core rationale = csh pipes don't reliably propagate exit codes (Pitfall 14), the exact thing RECON-04 must catch; per-stage subprocesses make the fail-loud check native. Follows the LSDRunner precedent.

---

## Phasierung/Kalibrierung (phasing & ppm calibration)

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministisch + optionaler CLI-Override | Fixed known phase (F2 from 1D P0/P1; F1 default 0/0 echo-antiecho; COSY magnitude). No blind auto-phase. CLI override available. ppm reversed + calibrated to §10 1D shifts. | ✓ |
| Auto-Phase-Algorithmus | Automatic per-dimension phase correction. More convenient, but Pitfall 10 (silent wrong phase). | |
| Du entscheidest | Planner picks the method; invariant = reproducible, headless, 1D-calibrated. | |

**User's choice:** Deterministisch + optionaler CLI-Override (recommended)
**Notes:** Auto-phase failure is silent with no human in the loop (Pitfall 10); only the Phase-99 QC gate might catch it. Calibration cross-checks the trusted 1D data, not the reconstruction (Pitfall 6).

---

## Intermediate-Files (intermediate location & retention)

| Option | Description | Selected |
|--------|-------------|----------|
| Persistenter analysis/nus_recon/-Unterordner, behalten | Per-experiment subfolder under analysis/ (Guide convention); intermediates retained so the fail-loud wrapper can inspect them and artefact-heavy runs stay forensically debuggable. Optional cleanup flag. | ✓ |
| Temp-Dir, nach Erfolg aufräumen | Intermediates in a temp dir, deleted after success. Cleaner, but nothing to inspect on artefact suspicion. | |
| Du entscheidest | Planner picks location/retention; invariant = wrapper must inspect output files. | |

**User's choice:** Persistenter analysis/nus_recon/-Unterordner, behalten (recommended)
**Notes:** Debuggability of the milestone's core-risk stage (reconstruction quality) outweighs tidiness.

---

## Test-Strategie (Phase 98 test approach)

| Option | Description | Selected |
|--------|-------------|----------|
| Mocks in CI + backend-gated Integrationstest gegen externen Datenpfad | CI: ordering gate, fail-loud wrapper, FnMODE branching with mocked subprocess boundary. Plus a real end-to-end integration test pointing at the external C20H32O2 path (skipif backend/data absent). No large ser in the repo. | ✓ |
| Echte ser-Fixtures ins Repo kopieren + skipif Backend | Copy exp2/3/4 ser into tests/fixtures/nus/. Self-contained, but blows up repo size (tens of MB binaries). | |
| Nur Mocks | Only orchestration logic with mocks; real chain never exercised in tests until Phase 100. | |

**User's choice:** Mocks in CI + backend-gated Integrationstest gegen externen Datenpfad (recommended)
**Notes:** Closes the Phase-97 D-03-deferred `ser`-fixture decision: validate reconstruction via external-path integration, not repo-committed binaries.

---

## Claude's Discretion

- **RECON-05 knob defaults** — user delegated iteration-count upper bound, threshold, and virtual-echo toggle to research/planner. Research assignment: read SMILE manual/tutorials, set sane defaults (virtual echo likely default-ON for echo-antiecho, Pitfall 8; iteration count as conservative upper bound alongside a real convergence/residual stopping rule, never sole criterion). Expose all three as CLI flags.
- GRPDLY/DECIM digital-filter removal method — planner discretion, informed by Pitfall 3.
- `nus/runner.py` API surface, mechanical enforcement of the F2-before-F1 ordering gate, runner/postprocess responsibility split — planner discretion within the LSDRunner-mirroring pattern.
- Apodization/ZF parameter choices — standard NMRPipe defaults, planner discretion.

## Deferred Ideas

- Peak-pick bridge + mandatory QC gate → Phase 99.
- Platform preflight (Rosetta/csh matrix) + portability matrix → Phase 100 / PORT.
- End-to-end §8-gate validation on C20H32O2 + CASE convergence → Phase 100 / VAL.
- hmsIST/mddnmr fallback backends → deferred (v1.x); primary = NMRPipe+SMILE.
- Reviewed-not-folded todos: `2026-06-25-case4-azulene-regiochemistry-enumeration-gap`, `2026-06-30-ranking-tests-hardfail-without-hosegen` — both unrelated keyword matches.
