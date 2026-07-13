---
phase: 98-reconstruction-processing
verified: 2026-07-13T13:14:54Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 98: Reconstruction + Processing Verification Report

**Phase Goal:** Lucy-ng runs the full external reconstruction pipeline — Bruker→NMRPipe conversion, NUS expansion, SMILE reconstruction, and post-processing — fully automatically with no GUI step, for any NUS 2D experiment.
**Verified:** 2026-07-13T13:14:54Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | RECON-01: `lucy nus reconstruct <expdir>` runs the full chain (convert → process_direct F2+TP → SMILE reconstruct_indirect → process_indirect F1) headlessly, no GUI | ✓ VERIFIED | `NusRunner.reconstruct()` (`src/lucy_ng/nus/runner.py:346-503`) calls the four stages in exactly that order; `reconstruct` subcommand registered in `src/lucy_ng/cli/nus.py:146-253` calling `NusRunner().reconstruct(...)`. All subprocess calls use fixed argv lists (never `shell=True`). |
| 2 | RECON-02: direct-dimension-first (F2 before F1) enforced as a hard gate + reversed, 1D-calibrated ppm axes | ✓ VERIFIED | Two gates in `runner.py`: (a) up-front `_resolve_f2_plan()` precondition (`runner.py:432-438`, defense-in-depth, monkeypatch-testable only per WR-02 finding — documented as such, not misrepresented); (b) the WR-02 **fix**, a genuinely reachable guard at `runner.py:460-465` asserting SMILE's input is `process_direct()`'s F2-processed output, never the raw converted FID. `postprocess.ppm_scale()` (`postprocess.py:368-397`) produces a reversed axis (`scale[0] > scale[-1]`); `calibrate_against_1d_reference()` cross-checks against `GUIDE_S10_C13`. WR-04 (OFFSET-as-Hz bug) fixed at `postprocess.py:396-397` (ppm value used directly, only spacing divided by SF) with an explicit regression test pinning `axis[0] == 200.0` (`tests/nus/test_processing_order.py:99`). WR-03 (axis sized from raw grid vs processed F1 size) fixed via `_read_processed_f1_size()` reading the actual `.ft2` header (`postprocess.py:274-303`). |
| 3 | RECON-03: FnMODE-aware from one entrypoint (echo-antiecho HSQC/HMBC vs QF magnitude COSY), QF/COSY branch intentionally provisional | ✓ VERIFIED | `_FNMODE_RECIPES` table (`runner.py:189-220`) and `recipe_for_fnmode()`/`_ordering_for_fnmode()` are the single auditable dispatch point; `NmrPipeSmileBackend.convert()` branches on `recipe.stage_order` (`nmrpipe_smile.py` `expand_first` vs `convert_first`). The QF/magnitude branch (`convert_first`, FnMODE 1/2) is explicitly commented `PROVISIONAL` with a reference to Assumptions Log A1/A3 and a note that it requires an implementation-time spike against real exp2 COSY data (deferred to Phase 100) — present and annotated, not silently omitted or asserted as trustworthy. |
| 4 | RECON-04: fail-loud `run_stage()` checks exit code AND output-file non-emptiness/non-all-zero, covering `.fid`/`.ft1`/`.ft2` | ✓ VERIFIED | `run_stage()` (`runner.py:51-118`): raises on non-zero exit, raises on missing/zero-byte output, and (WR-01 fix) the all-zero/truncated-data parse check now covers `suffix in {".fid", ".ft1", ".ft2"}` — `.ft1` (SMILE's own output) included after the review fix. `tests/nus/test_runner_faillloud.py` (4 tests, all passing) exercises exit-code, empty-output, and truncated-all-zero paths against a `.fid` fixture; the `.ft1` inclusion is a suffix-set membership check exercised by the same code path (no dedicated `.ft1`-suffixed regression test exists — INFO-level gap only, not blocking, since the logic is generic and already covered for `.fid`). |
| 5 | RECON-05: CLI flags `--iterations`/`--threshold`/`--virtual-echo`/`--no-virtual-echo` with convergence-based stopping | ✓ VERIFIED | `cli/nus.py:146-212` defines all four flags (`--iterations` default 500, `--threshold` default 0.8, `--virtual-echo/--no-virtual-echo` default True, plus `--f1-p0`/`--f1-p1`/`--f2-p0`/`--f2-p1`); threaded through to `NusRunner.reconstruct()` → `backend.reconstruct_indirect(max_iter=..., threshold=..., n_sigma=..., virtual_echo=...)`. Docstrings and code comments explicitly state `-maxIter` is an upper bound only, real stopping is `-nSigma`/`-thresh` convergence (`nmrpipe_smile.py:456-460`, `cli/nus.py:153-157`). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lucy_ng/nus/runner.py` | `run_stage()`, FnMODE recipe table, `NusRunner.reconstruct()` orchestrator | ✓ VERIFIED | All present, substantive (not stubs), wired into CLI and postprocess/backend modules. |
| `src/lucy_ng/nus/postprocess.py` | `process_direct()`, `process_indirect()`, ppm axis + calibration helpers | ✓ VERIFIED | All present, substantive, wired (imported by `runner.py`, used in `reconstruct()`). Both WR-03/WR-04 fixes present with regression test coverage. |
| `src/lucy_ng/nus/backends/nmrpipe_smile.py` | `convert()` FnMODE-branched, `reconstruct_indirect()` SMILE call | ✓ VERIFIED | Both methods substantive; `convert()` branches correctly on `recipe.stage_order`; `reconstruct_indirect()` builds the SMILE argv with `-maxIter`/`-thresh`/`-nSigma`/`-EA`/`-xP0`/`-xP1`, routes through `run_stage()`. |
| `src/lucy_ng/cli/nus.py` | `reconstruct` subcommand with RECON-05 flags | ✓ VERIFIED | Present, import-safe (deferred `lucy_ng.nus.*` imports), registered on the `nus` Click group, wired to `NusRunner().reconstruct()`. |
| `src/lucy_ng/models/nus.py` | `NusReconstructionResult` | ✓ VERIFIED | Present with `to_dict()`/`from_dict()`/`summary()`, used as `reconstruct()`'s return type. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `cli/nus.py::reconstruct` | `nus/runner.py::NusRunner.reconstruct` | direct call, result rendered via `--format json`/text | ✓ WIRED | `cli/nus.py:236-253` |
| `NusRunner.reconstruct()` | `backend.convert()` → `process_direct()` → `backend.reconstruct_indirect()` → `process_indirect()` | sequential calls, F2-processed output threaded as SMILE input | ✓ WIRED | `runner.py:440-488`; reachable guard at `runner.py:460-465` enforces the SMILE input is never the raw converted FID |
| `process_indirect()` | ppm calibration sidecar | `_write_ppm_calibration_sidecar()` call at end of `process_indirect()` | ✓ WIRED | `postprocess.py:269` |
| `recipe_for_fnmode()` | `convert()` / `_resolve_f2_plan()` | single source of FnMODE dispatch truth | ✓ WIRED | consumed in both `nmrpipe_smile.py::convert()` and `runner.py::_resolve_f2_plan()` |

### Behavioral Spot-Checks / Test Execution

Scoped run per critical_runtime_rule (no full unbounded suite):

```
pytest tests/nus/ tests/test_cli_nus.py -q
38 passed, 1 skipped in 1.61s
```

The 1 skip is `tests/nus/test_reconstruct_integration.py::test_reconstruct_exp3_hsqc_end_to_end` — a `skipif`-guarded real end-to-end test against external C20H32O2 data / real NMRPipe+SMILE binaries (D-04). Correctly absent from this environment (no NMRPipe/SMILE installed, no external data path) — this is Phase 100's scope (§8-gate validation), not a Phase 98 gap.

### Anti-Patterns Found

Scanned all 5 phase-modified core files (`runner.py`, `postprocess.py`, `nmrpipe_smile.py`, `cli/nus.py`, `models/nus.py`) for `TBD`/`FIXME`/`XXX` (debt-marker gate) and `TODO`/`HACK`/`PLACEHOLDER` — none found. The intentionally-provisional QF/COSY branch and F1 phase default are documented in-line as `PROVISIONAL` with explicit cross-references to the research Assumptions Log, not left as bare TODOs — acceptable per phase context (deferred to Phase 100 spike, not omitted).

No blockers or warnings found in anti-pattern scan.

### "CASE Pipeline Unchanged" Invariant

```
git diff --stat 0b7ec80^..HEAD -- src/lucy_ng/detection/ src/lucy_ng/fragments/ \
  src/lucy_ng/lsd/ src/lucy_ng/ranking/ src/lucy_ng/cli/pick.py .claude/
```
Empty diff — confirmed no touch to any CASE-pipeline path across the whole phase 98 commit range.

### Code Review Findings Disposition

`98-REVIEW.md` (0 critical / 4 warning / 3 info, `status: issues_found`) findings and their resolution, verified against current source:

| Finding | Status | Verified fix |
|---------|--------|--------------|
| WR-01 (`.ft1` missing from all-zero guard) | ✓ FIXED | `runner.py:100` now includes `.ft1` in the suffix set (commit `a79883f`) |
| WR-02 (F2-before-F1 gate structurally unreachable) | ✓ FIXED | Reachable guard added at `runner.py:460-465` asserting SMILE's input path (commit `cfd60a2`); original defense-in-depth gate kept and now honestly documented as monkeypatch-only |
| WR-03 (ppm sidecar sized from raw grid, not processed F1 size) | ✓ FIXED | `_read_processed_f1_size()` reads back the actual `.ft2` header (commit `e22e87c`); intended vs. observed size both recorded in the sidecar JSON |
| WR-04 (OFFSET treated as Hz, collapsing the ppm axis) | ✓ FIXED | `ppm_scale()` uses OFFSET directly as ppm (commit `cda55e1`); regression test pins `axis[0] == 200.0` |
| IN-01 (`TimeoutExpired` vs documented `RuntimeError`) | Not fixed (Info, non-blocking) | Docstring inaccuracy only; fail-loud behavior unaffected |
| IN-02 (`smile_iterations` never populated) | Not fixed (Info, non-blocking) | Field remains `None`; dead but harmless, no consumer depends on it yet |
| IN-03 (CLI surfaces raw tracebacks) | Not fixed (Info, non-blocking, pre-existing convention shared with `check`/`params`/`schedule`) | Consistent with existing project convention, not a regression |

All 4 warnings were fixed in commits `a79883f`/`cda55e1`/`e22e87c`/`cfd60a2` after the review (`7af3812`). The 3 Info items remain open but are explicitly non-blocking per the review's own severity classification and this phase's context brief.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| RECON-01 | 98-01, 98-03, 98-05 | `lucy nus reconstruct` full automatic chain, no GUI | ✓ SATISFIED | `runner.py::NusRunner.reconstruct()`, `cli/nus.py::reconstruct` |
| RECON-02 | 98-01, 98-04, 98-05 | F2-before-F1 hard gate, reversed 1D-calibrated ppm axes | ✓ SATISFIED | `runner.py` guards + `postprocess.py` ppm helpers (WR-02/03/04 fixed) |
| RECON-03 | 98-01, 98-02, 98-03 | FnMODE-aware, echo-antiecho + QF from one entrypoint | ✓ SATISFIED | `_FNMODE_RECIPES` table, `convert()` branching |
| RECON-04 | 98-01, 98-02 | fail-loud wrapper, exit code + non-emptiness | ✓ SATISFIED | `run_stage()` (WR-01 fixed) |
| RECON-05 | 98-01, 98-06 | CLI flags, convergence-based stopping | ✓ SATISFIED | `cli/nus.py` flags → `reconstruct_indirect()` |

No orphaned requirements — `.planning/REQUIREMENTS.md` maps only RECON-01..05 to Phase 98, and all five are claimed across the six plans' `requirements:` frontmatter.

Note: `.planning/REQUIREMENTS.md`'s traceability table (line 85) still shows `RECON-01..05 | Phase 98 | Pending` — a stale status label not updated post-completion. The requirement checkboxes themselves (lines 22-26) are marked `[x]`. This is a documentation-hygiene nit, not a phase-98 code gap; recommend updating the traceability table's Status column to "Done" in a follow-up docs commit.

### Human Verification Required

None required to close this phase — the phase-98 scope is explicitly headless-orchestration-only. WR-03's residual concern (ppm axis sizing correctness against *real* Phase-100 NMRPipe output) is real-data-dependent and is already correctly scoped to Phase 100 validation per the review and this phase's context brief; it is not an unresolved phase-98 truth (the code is correct given the data the phase can access in CI — it reads back the actual processed size rather than assuming one).

### Gaps Summary

No blocking gaps. All five RECON-01..05 truths are verified against actual source code (not SUMMARY claims): the four-stage headless orchestration exists and is correctly sequenced, the F2-before-F1 gate is genuinely enforced (not just symbolically), FnMODE branching is table-driven, the fail-loud wrapper covers all three real intermediate suffixes, and all RECON-05 CLI flags thread through to a convergence-based (not iteration-count-only) SMILE stopping rule. All 4 code-review warnings were fixed in follow-up commits and are re-verified here as actually present in source, with regression tests added where testable without a real backend (WR-04's `axis[0] == 200.0` pin). The QF/COSY branch is intentionally provisional and clearly annotated as such, per phase scope — not a gap. The one true end-to-end integration test is correctly `skipif`-guarded and skips cleanly in this environment; real-data validation is Phase 100's explicit scope. Test suite: 38 passed, 1 skipped (0 failed). "CASE pipeline unchanged" invariant confirmed via empty git diff.

---

_Verified: 2026-07-13T13:14:54Z_
_Verifier: Claude (gsd-verifier)_
