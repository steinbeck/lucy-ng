# Plan 100-03 — Summary (VAL end-to-end)

**Status:** Stopped honestly per CONTEXT decision D-04 — VAL-01/VAL-02 NOT achieved,
limitation documented, RECON-F1 named as tracked next step.
**Executed:** 2026-07-18 / 2026-07-19 (interactive, `autonomous: false`)
**Evidence artifacts:** `VALIDATION.md` (durable outcome) · `100-03-VAL-EXECUTION-LOG.md`
(running defect log)

## What was done

| Task | Outcome |
|---|---|
| **T1 — install backend, `lucy nus check` green** | ✅ **Done.** Native NMRPipe (`mac_arm64`) + separate SMILE plugin installed at `~/NMRPipe` via the official `install.com`; Gatekeeper quarantine cleared; XQuartz installed; environment derived from the generated `nmrInit.mac_arm64.com`. `lucy nus check` → `status: available`, `smile_available: true`, `platform.critical_platform_issues: []`. |
| **T2 — reconstruct exp2/3/4, §8/QC grade** | ❌ **Not achieved.** Chain fixed and verified through `nusExpand.tcl` → `bruk2pipe` → `process_direct` (F2 correctly FT'd + transposed), but the SMILE step aborts on memory. D-04 tuning budget executed and exhausted. |
| **T3 — fresh `/lucy-ng:case C20H32O2`, VAL-02** | ❌ **Not reached** — no accepted reconstructed peaks to consume; CASE deliberately not run against the old known-bad lists. |

## Deviations from plan

The plan specified "no new code — this exercises the already-built Phase 97-99 pipeline".
That held for T1/T3, but T2 surfaced **genuine defects in the Phase-98 reconstruction code**
that blocked the goal outright. Fixing them was necessary and in-scope for a validation phase
whose stated purpose is the deferred real-data spike. Each fix was test-covered and committed
atomically:

- **`08f66fb` — D-BUG-1:** `convert()` now passes explicit `-acqus`/`-acqu2s` expdir paths to
  `nusExpand.tcl`, which otherwise resolves them relative to its cwd (`stage_dir`) and fails
  with *"Error Extracting Input Sizes"*. Test:
  `test_echo_antiecho_expand_argv_passes_acqus_paths`.
- **`01a7ec4` — D-BUG-2:** `process_direct`/`process_indirect` built ONE `nmrPipe` call with
  multiple `-fn` verbs; NMRPipe honours only the first and drops the rest, so F2 was never
  Fourier-transformed or transposed and SMILE rejected the input. Added
  `runner.run_pipeline_stage()` (one `nmrPipe` process per verb, piped, checking **every**
  process's exit code — strengthens RECON-04/Pitfall-14) and rewrote both functions to
  per-verb stages. Tests: per-verb pipeline structure assertion in `test_processing_order.py`
  + two executor fail-loud tests.
- Documentation deviation: `docs/NUS-PORTABILITY.md` (PORT-02, Plan 100-02) was **corrected**
  with real findings that contradicted its research-derived assumptions — XQuartz is a HARD
  dependency of the reconstruction path (not optional/`nmrDraw`-only), the build is
  `mac_arm64` (not `mac11_arm64`), Gatekeeper quarantine must be cleared, and SMILE needs
  ≥ 8 GB free RAM.

## Meta-finding (worth carrying to milestone close)

Phases 98 and 99 shipped "COMPLETE & verified" on **mock-only tests** that recorded subprocess
argv and never executed the real external binaries. Both defects above were structurally
invisible to that test style — the argv "looked right". For a pipeline whose whole job is
orchestrating external tools, argv-recording mocks give false confidence; at least one
backend-gated smoke test against real binaries is needed to make "verified" meaningful.
Candidate for `/gsd-extract-learnings` at milestone close.

## Requirement status

- **VAL-01** — not met (documented limitation).
- **VAL-02** — not reached (blocked by VAL-01).
- PORT-01 / PORT-02 — delivered by Plans 100-01 / 100-02, independent of this outcome (D-04).

## Invariants held

- `tests/fixtures/nus/known_bad_peaks/` byte-unchanged (QC-02 regression floor intact).
- External known-bad lists archive-copied before any run; trusted 1D lists untouched.
- `.claude/commands/lucy-ng/` + `.claude/agents/` byte-unchanged (CASE-skill invariant).
- D-07 write boundary correct: no reconstruction-derived peaks ever reached
  `analysis/nmr_peaks/`.
- Full test suite green throughout (nus suite 95 passed / 1 skipped after the fixes).
