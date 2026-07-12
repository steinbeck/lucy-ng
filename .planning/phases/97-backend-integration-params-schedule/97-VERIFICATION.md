---
phase: 97-backend-integration-params-schedule
verified: 2026-07-12T15:10:34Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 97: Backend Integration + Params/Schedule Verification Report

**Phase Goal:** Lucy-ng can detect the NUS reconstruction backend (NMRPipe+SMILE) on the local machine and correctly parse any NUS experiment's Bruker acquisition parameters and sampling schedule into validated Pydantic models, ready to drive reconstruction in Phase 98.
**Verified:** 2026-07-12T15:10:34Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `lucy nus check` reports NMRPipe+SMILE availability, fails loud (exit 1) when missing, with install guidance; backend not a core dependency | VERIFIED | Ran `lucy nus check` on this machine (no NMRPipe): printed `NMRPipe+SMILE: not available (not_installed)`, listed missing tools (`nmrPipe, bruk2pipe, nusExpand.tcl`), printed install URL, exited 1 (`check_exit=1`). `pyproject.toml` core `dependencies` list has no NMRPipe/SMILE entry; `[nus]` extra is empty. |
| 2 | `lucy nus params <expdir> --format json` extracts a validated `NusAcquisitionParams` per-experiment (SFO1, SW_h, TD/dim, FnMODE, GRPDLY/DECIM, byte order/dtype) verified against real exp2/exp3/exp4 fixtures | VERIFIED | Ran `lucy nus params tests/fixtures/nus/exp3_hsqc --format json` — output matches RESEARCH-verified values exactly (fnmode_f1=6, f1_td=100, nus_td=400, f1_nucleus=13C, f1_sfo1≈125.7157, grpdly=67.9851531982422 unrounded, nus_amount_pct=25, f1_sf/f1_offset populated from procs/proc2s). `pytest tests/test_nus_params.py` 24/24 passed covering all 3 fixtures. |
| 3 | `lucy nus schedule <expdir> --format json` builds schedule from nuslist with 0-based acquisition-order-preserved indexing (never sorted) + hard `n_sampled == len(nuslist)` assertion derived from FnMODE, passing for all 3 experiments (COSY 188==188; HSQC 50==100/2; HMBC 116==232/2) | VERIFIED | Ran `lucy nus schedule` on all three fixtures: exp2_cosy n_sampled=188 len=188 fnmode=1 td=188; exp3_hsqc n_sampled=50 len=50 fnmode=6 td=100; exp4_hmbc n_sampled=116 len=116 fnmode=6 td=232 — exact match to spec. `nuslist[:8]` = `[0,124,431,670,369,53,211,120]`, confirmed `sorted? False` (acquisition order preserved, never sorted). `grep "sorted("` in schedule.py returns no matches against the parsed nuslist. `pytest tests/test_nus_schedule.py` 26/26 passed including dedicated acquisition-order regression test. |
| 4 | A clean core `pip install lucy-ng` still imports the CLI without error; NUS pieces behind optional `[nus]` extra with lazy imports | VERIFIED | `python -c "from lucy_ng.cli import cli"` exits 0. `grep -n "^from lucy_ng.nus\|^import lucy_ng.nus" src/lucy_ng/cli/nus.py` empty (all imports deferred inside command bodies). `pyproject.toml` `nus = []` extra present (empty, reserved for Phase 98/99); core `dependencies` list unchanged (click, jsonschema, nmrglue, numpy, pydantic, requests, rdkit, scipy, tqdm — no NMRPipe/SMILE). |

**Score:** 4/4 ROADMAP success criteria verified.

### Additional Plan-Level Must-Haves

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 5 | `NusAcquisitionParams`/`NusSchedule` Pydantic v2 models exist, validated, reject unknown nucleus/FnMODE, round-trip via to_dict/from_dict | VERIFIED | `src/lucy_ng/models/nus.py` defines both models exactly per the 97-01 interface contract; `pytest tests/test_nus_models.py` 11/11 passed (validator rejection tests, round-trip test, unsorted-order-preservation test all present and green). |
| 6 | `NmrPipeSmileBackend` detects real which()-able tools + probes SMILE plugin via `nmrPipe -fn SMILE -help` (never `shutil.which('smileNus')`); `diagnose()` distinguishes not_installed vs installed_not_sourced | VERIFIED | `grep -n smileNus src/lucy_ng/nus/backends/nmrpipe_smile.py` → no matches. Source inspection confirms `REQUIRED_TOOLS = ["nmrPipe","bruk2pipe","nusExpand.tcl"]` and `smile_plugin_available()` uses fixed-arg subprocess probe. `diagnose()` returns distinct `not_installed`/`installed_not_sourced`/`smile_plugin_missing`/`available` states with actionable hint text. `grep shell=True` → no matches. `pytest tests/test_nus_backends.py` 20/20 passed. |
| 7 | `NusBackend` protocol + registry (`get_backend`/`list_available_backends`) exposes backends generically | VERIFIED | `src/lucy_ng/nus/backends/__init__.py` defines `NusBackend` Protocol + `_REGISTRY` + both functions exactly per plan 04 interface. `list_available_backends()` returns `[]` on this machine (no NMRPipe) without raising. |
| 8 | `lucy nus` group registers only implemented subcommands (check/params/schedule), no dead reconstruct/pipeline stubs (D-02) | VERIFIED | `lucy nus --help` lists exactly `check`, `params`, `schedule` — no `reconstruct`/`pipeline`. `grep add_command(nus)` in `cli/main.py` present. |
| 9 | Real C20H32O2 metadata fixtures (exp2/3/4) present as self-contained text-only fixtures (D-03), no binary `ser` | VERIFIED | `find tests/fixtures/nus -type f` lists 15 text files (acqus/acqu2s/nuslist/pdata/1/{procs,proc2s} × 3 experiments), no `ser` file present. |

**Overall Score:** 9/9 must-haves verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lucy_ng/models/nus.py` | `NusAcquisitionParams` + `NusSchedule` Pydantic v2 models | VERIFIED | Both classes present, all D-04 superset fields, validators, to_dict/from_dict; re-exported via `models/__init__.py`. |
| `src/lucy_ng/nus/params.py` | `read_nus_params(expdir) -> NusAcquisitionParams` | VERIFIED | Present, documented, correct acqu2s-not-acqus FnMODE read, correct procs/proc2s SF/OFFSET read, no `read_pdata()` call. |
| `src/lucy_ng/nus/schedule.py` | `read_nus_schedule`, `expected_sample_count`, `validate_schedule` | VERIFIED | Present, `expected_sample_count` uses shared `REAL_FNMODES`/`COMPLEX_FNMODES` from models.nus, `validate_schedule` raises `ValueError`/`NotImplementedError` (never warns), never sorts nuslist. |
| `src/lucy_ng/nus/backends/nmrpipe_smile.py` | `NmrPipeSmileBackend` detection class | VERIFIED | `REQUIRED_TOOLS`, `missing_tools`, `smile_plugin_available`, `is_available`, `diagnose` all present and match spec. |
| `src/lucy_ng/nus/backends/__init__.py` | `NusBackend` protocol + registry | VERIFIED | Present, `get_backend`/`list_available_backends` implemented. |
| `src/lucy_ng/cli/nus.py` | `lucy nus` group: check/params/schedule, import-safe, `--format json` | VERIFIED | All three commands present, deferred imports only, `--format json` on all three. |
| `pyproject.toml` `[nus]` extra | Empty-but-present optional extra | VERIFIED | `nus = [...]` (empty list, explanatory comment) present under `[project.optional-dependencies]`. |
| `tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc}/*` | Real text-metadata fixtures | VERIFIED | 15 files present, values match RESEARCH-documented ground truth exactly (FnMODE, NusTD, nuslist lengths). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `models/__init__.py` | `models/nus.py` | re-export | WIRED | `from lucy_ng.models import NusAcquisitionParams, NusSchedule` succeeds. |
| `nus/params.py` | `readers/bruker.py` | `_get_param_2d` reuse | WIRED | `from lucy_ng.readers.bruker import _get_param_2d` present and used for procs/proc2s SF/OFFSET extraction. |
| `nus/schedule.py` | `models/nus.py` | `REAL_FNMODES`/`COMPLEX_FNMODES` shared constants | WIRED | `from lucy_ng.models.nus import COMPLEX_FNMODES, REAL_FNMODES, NusSchedule` — validator and hard assertion cannot diverge. |
| `nus/schedule.py` | `nus/params.py` | `read_nus_params` reuse for FnMODE/TD/NusTD | WIRED | `from lucy_ng.nus.params import read_nus_params`, called inside `read_nus_schedule`. |
| `cli/main.py` | `cli/nus.py` | `add_command(nus)` | WIRED | Both the import line and `add_command(nus)` confirmed present; `lucy nus --help` functions end-to-end. |
| `cli/nus.py` | `nus/params.py` / `nus/schedule.py` / `nus/backends` | deferred imports in command bodies | WIRED | No top-level `lucy_ng.nus` import in `cli/nus.py`; commands function correctly when invoked (verified via live CLI runs). |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Core CLI import-safe | `python -c "from lucy_ng.cli import cli"` | exit 0 | PASS |
| Backend check fails loud, no NMRPipe on this machine | `lucy nus check; echo exit=$?` | `NMRPipe+SMILE: not available (not_installed)` + missing-tools list + install URL, `check_exit=1` | PASS |
| Params extraction on real fixture | `lucy nus params tests/fixtures/nus/exp3_hsqc --format json` | valid JSON, all fields match RESEARCH ground truth (fnmode_f1=6, nus_td=400, grpdly=67.9851531982422, f1_sf/f1_offset populated) | PASS |
| Schedule extraction + hard assertion, all 3 fixtures | `lucy nus schedule <exp> --format json` for exp2/exp3/exp4 | n_sampled==len(nuslist) for all three: 188/188, 50/50, 116/116; correct fnmode/td per experiment | PASS |
| Acquisition order preserved | schedule JSON `nuslist[:8]` for exp2_cosy | `[0,124,431,670,369,53,211,120]`, `sorted? False` | PASS |
| `lucy nus --help` shows only implemented subcommands | `lucy nus --help` | Lists `check`, `params`, `schedule` only (no `reconstruct`/`pipeline`) | PASS |
| `[nus]` extra + core deps clean | `grep -A5 "optional-dependencies"` / `grep dependencies` in pyproject.toml | `nus = []` present; core deps list has no NMRPipe/SMILE | PASS |
| No `smileNus`/`shell=True` misuse | `grep -n smileNus\|shell=True src/lucy_ng/nus/backends/nmrpipe_smile.py` | no matches | PASS |
| No `sorted(` on nuslist | `grep -n "sorted(" src/lucy_ng/nus/schedule.py` | no matches | PASS |
| Full unit test suite for phase-97 modules | `pytest tests/test_nus_params.py tests/test_nus_schedule.py tests/test_nus_backends.py tests/test_cli_nus.py tests/test_nus_models.py -q` | 94 passed | PASS |
| Full project test suite (regression check) | `pytest -q` | 1304 passed, 7 skipped, 1 xfailed, 0 failed | PASS |
| Lint clean | `ruff check src/lucy_ng/nus src/lucy_ng/models/nus.py src/lucy_ng/cli/nus.py` | All checks passed | PASS |
| CASE-pipeline-unchanged invariant | `git diff --stat` since phase start for `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py` | empty diff | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| NUS-01 | 97-04, 97-05 | Backend detection (NMRPipe+SMILE), fails loud, install guidance, never a core dependency | SATISFIED | `lucy nus check` behavior confirmed live; `NmrPipeSmileBackend` correct tool list + SMILE probe. |
| NUS-02 | 97-01, 97-02 | Bruker acquisition params extracted per-experiment into validated Pydantic model | SATISFIED | `read_nus_params` verified against all 3 fixtures, exact value match. |
| NUS-03 | 97-01, 97-03 | Sampling schedule from nuslist, 0-based acquisition-order-preserved, hard FnMODE-derived assertion | SATISFIED | `read_nus_schedule` verified against all 3 fixtures, order-preservation confirmed. |
| NUS-04 | 97-05 | `lucy nus params`/`lucy nus schedule` JSON output validated against real fixtures | SATISFIED | Live CLI runs on all 3 fixtures produce correct JSON. |
| NUS-05 | 97-05 | Core CLI dependency-free; `[nus]` optional extra with lazy imports | SATISFIED | `pip install -e .`-equivalent import check passes; `[nus]` extra present empty; no top-level `lucy_ng.nus` imports in `cli/nus.py`. |

No orphaned requirements — REQUIREMENTS.md lists exactly NUS-01..05 for Phase 97, and all 5 are claimed and satisfied across the 5 plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers found in any phase-97 file | — | None |

A code review (`97-REVIEW.md`, standard depth) found 0 critical issues and 7 warnings + 5 info items — all latent robustness gaps (e.g. `NusSchedule`'s invariant not re-enforced by a `model_validator` on direct construction/`from_dict`, `nuslist` row-shape not asserted, `nus_amount_pct` typed `int` instead of `float`, `smile_plugin_available()`'s "never raises" docstring not fully honored against `UnicodeDecodeError`, implicit `pdata` folder fallback in calibration read). None of these affect the phase's stated goal or ROADMAP success criteria as verified against the real fixtures and this machine's environment — they are candidate hardening items for Phase 98/99 rather than blockers to Phase 97's own goal. The one CI-breaking lint failure identified in review (E501 in `cli/nus.py`) was already fixed in a follow-up commit (`e0e126e`), confirmed via live `ruff check` (all checks passed).

### Human Verification Required

None. All observable truths for this phase are verifiable programmatically (parsing, detection, CLI behavior, import-safety) — no visual, real-time, or external-service behavior is in scope for Phase 97.

### Gaps Summary

No gaps. All 4 ROADMAP success criteria and all 5 requirement IDs (NUS-01..05) are independently verified against the actual codebase and the real C20H32O2 fixtures, not merely SUMMARY.md self-reports. The full project test suite (1304 tests) passes with zero regressions, and the CASE-pipeline-unchanged invariant (no diff to `detection/`, `fragments/`, `lsd/`, `ranking/`, `cli/pick.py`) holds. The 7 warning-level code-review findings are legitimate robustness improvements to consider before/during Phase 98 (particularly WR-01: enforce the `n_sampled`/`nuslist` invariant at the model level, not just procedurally in `schedule.py`), but do not block this phase's goal achievement since every documented construction path in current use (`read_nus_schedule` → `cli/nus.py schedule`) already enforces the assertion correctly and is proven correct against all three real fixtures.

---

_Verified: 2026-07-12T15:10:34Z_
_Verifier: Claude (gsd-verifier)_
