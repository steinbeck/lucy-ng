# Phase 100: Cross-Platform Hardening + End-to-End Validation - Research

**Researched:** 2026-07-18
**Domain:** (a) platform preflight for an external-binary NMR reconstruction pipeline (Apple-Silicon/Rosetta detection, csh/tcsh availability, portability documentation); (b) real, backend-gated empirical validation of the NUS reconstruction pipeline against a live QC gate and the existing CASE orchestrator
**Confidence:** HIGH for code integration points and current-environment facts (directly inspected/probed); MEDIUM for NMRPipe/SMILE install specifics (official docs fetched but install itself not executed in this research pass); LOW-MEDIUM for anything about actual reconstruction quality on real data (that is precisely what VAL-01/02 exist to discover — this research cannot pre-answer it)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — VAL runs locally on this Apple-Silicon Mac.** NMRPipe+SMILE is a native macOS Apple-Silicon target per the locked v10.0 backend decision — it is simply not installed on this dev machine yet (verified 2026-07-18: `arm64`, macOS 26.5, `csh`/`tcsh` present, `nmrPipe`/`bruk2pipe`/`nusExpand.tcl` absent from PATH). This is an install gap, not a platform blocker. Install path: native NMRPipe macOS Apple-Silicon build + SMILE plugin, `bin/` on PATH — documented as a local prerequisite in CLAUDE.md, exactly like the existing LSD-solver prerequisite. The install itself is a manual step, not a code deliverable. The PORT-01 preflight (`lucy nus check`) is the tool that confirms the local install is ready before the VAL run starts. Evidence: commit the real reconstructed peak JSONs + QC report + a `VALIDATION.md` (§8 verdict per experiment + case-convergence result).

**D-02 — VAL-01 §8 pass = QC PASS, or PARTIAL only when soft-only + chemist confirm.** PASS → passed. PARTIAL → accepted only if the violated checks are all soft (edited-sign self-consistency, COSY diagonal symmetry) and a brief chemist visual confirms the connectivity is usable for CASE. Any critical violation (quaternary-C 1-bond correlation, ppm calibration, signal-to-ridge dominance, HSQC coverage) = FAIL = not passed.

**D-03 — VAL-02 bar = LSD terminates + finite rankable set.** Success = LSD runs to completion (no ~10⁶ timeout/explosion) and produces a finite, 13C-prediction-rankable candidate set. The correct C20H32O2 structure ranking top-N is a bonus, not a condition. VAL-01 is necessary but VAL-02 is the real bar.

**D-04 — Bounded tuning budget, then honest stop.** If the real reconstruction does not clear the §8/QC gate critically: apply a bounded, pre-defined tuning budget (SMILE `-maxIter`/`-thresh`/virtual-echo, apodization, phase defaults, try 33% sampling density). After the budget: persistent FAIL is recorded as a documented limitation in `VALIDATION.md` + ROADMAP, with RECON-F1 (hmsIST/mddnmr fallback) named as the tracked next step. hmsIST NOT pulled in even on FAIL. No indefinite hard block. PORT ships independently of the VAL outcome.

**D-05 — PORT-01 preflight: critical = fail-loud block, soft = warn.** Critical gaps (missing backend binary, no csh) make `reconstruct`/`pipeline` abort fail-loud (exit≠0) before any stage runs. Soft conditions (running under Rosetta/x86 emulation but tools present) are logged loudly but do not block. `lucy nus check` reports both granularly per-check. Extend the existing `NusBackend.diagnose()` in `src/lucy_ng/nus/backends/` — do not rewrite.

**D-06 — PORT-02 matrix lives in a dedicated `docs/NUS-PORTABILITY.md`.** Rows: macOS-arm64-native / Linux-native / Windows-WSL2-gap. WSL2 workaround documented step-by-step but explicitly marked documented, untested. Linked from CLAUDE.md/README.

### Claude's Discretion
- Exact preflight check API surface and how the platform section extends `NusBackend.diagnose()` / `lucy nus check` output shape (D-05).
- Exact `docs/NUS-PORTABILITY.md` layout, and whether the install-prerequisite doc block sits in CLAUDE.md, README, or both (D-01/D-06).
- The precise contents/format of `VALIDATION.md` and where the committed real peak lists live vs the known-bad QC-02 fixtures (D-01) — must not overwrite the known-bad regression fixtures.
- The exact numeric tuning-budget bounds (how many knob combinations / iterations before honest-stop) (D-04).

### Deferred Ideas (OUT OF SCOPE)
- hmsIST/mddnmr fallback backend (RECON-F1) — NOT pulled into this phase even on a SMILE FAIL; tracked as the next step if the tuning budget is exhausted.
- Real WSL2/native-Windows verification — PORT-02 documents the WSL2 path but marks it untested; actual verification / NMRFx pivot (RECON-F2) is deferred.
- Webview rendering of reconstructed 2D + QC report (RECONUX-F2) and per-peak recon-confidence → LSD constraint weighting (RECONUX-F1) — deferred (v1.x).
- Re-litigating Phase-97/98/99 internals — this phase runs and validates them, does not change them.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PORT-01 | `lucy nus check` performs a platform preflight (Apple-Silicon `arch`/Rosetta, `csh`/`tcsh`, backend binaries) and reports readiness clearly before a run starts | See "PORT-01: Platform Preflight" below — exact detection code, extension point in `NmrPipeSmileBackend.diagnose()`, and the missing pre-stage gate in `NusRunner.reconstruct()` this phase must add |
| PORT-02 | A documented portability matrix (macOS-arm64-native / Linux-native / Windows-WSL2-gap) exists, every gap investigated and written down | See "PORT-02: Portability Matrix" below — verified facts for macOS-arm64 (own machine + official docs), documented pitfalls for Linux (32-bit libs) and Windows (no csh/tcsh, no native build since v8.9) from milestone-level PITFALLS.md |
| VAL-01 | C20H32O2 exp2/3/4 reconstructed end-to-end via `lucy nus pipeline`, passing the guide's §8 quality gate | See "VAL-01: Operationalizing §8 on Real Data" below — exact §8 text, how it maps onto the six `nus/qc.py` checks, chemist-confirm procedure for PARTIAL, known-bad-fixture non-collision requirement |
| VAL-02 | Fresh `/lucy-ng:case C20H32O2` run on the new peak lists converges on a finite, rankable solution set | See "VAL-02: CASE Convergence" below — what "converges" means operationally against `case.md`/`LSDRunner`/ranking, and why the original run exploded |
</phase_requirements>

## Summary

This phase closes milestone v10.0 with two independent, non-blocking bodies of work. PORT-01/02 are pure software-engineering additions to already-existing, already-tested code: `NmrPipeSmileBackend.diagnose()` (Phase 97) already distinguishes "not installed" from "installed but not sourced" for the three required tools plus the SMILE plugin capability probe; PORT-01 extends that same dict with a `platform` sub-object (arch, Rosetta-translation status, csh/tcsh presence) using only Python stdlib (`platform`, `subprocess`, `shutil.which`) — no new dependency, nothing for the Package Legitimacy Gate to check. The one real code gap this research surfaced: `NusRunner.reconstruct()` currently reads params/schedule and dispatches stages with **no preflight gate at all** — `lucy nus check` reports diagnostics but nothing calls it before `reconstruct`/`pipeline` run. PORT-01's fail-loud requirement (D-05) is therefore not just "add checks," it is "add checks AND wire them as a hard precondition into `NusRunner.reconstruct()` (or the `cli/nus.py` command bodies)," mirroring the F2-before-F1 ordering gate already added in Phase 98 (RECON-02) and the fail-loud philosophy of RECON-04.

VAL-01/02 are empirical, not implementation-heavy: this exact machine (verified 2026-07-18, confirmed again during this research pass) is `arm64`/macOS 26.5, native (not Rosetta-translated — `sysctl -n sysctl.proc_translated` returns `0`), with `csh`/`tcsh` present and `nmrPipe`/`bruk2pipe`/`nusExpand.tcl` absent from PATH. Official NMRPipe docs confirm a native `mac11_arm64` build exists (no Rosetta/VM needed for command-line use — only `nmrDraw`, the GUI viewer, is documented as macOS-problematic), and that SMILE is a **separately downloaded companion file** (`plugin.smile.tZ`), not bundled with the base NMRPipe distribution. The `lucy nus pipeline` command (Phase 99) already implements the full params→schedule→reconstruct→peak-pick→QC→write/quarantine chain end-to-end; VAL-01 is "install the tool, then run this existing command three times (exp2/3/4) and grade the output," not new code. VAL-02 is "run the existing, untouched `/lucy-ng:case C20H32O2` orchestrator against the new peak lists and observe whether LSD terminates," also not new code. The only genuinely new artifact both VAL items need is `VALIDATION.md` plus committed evidence files.

**Primary recommendation:** Treat PORT-01/02 as a small, fully CI-testable coding task (mock `platform`/`subprocess`/`shutil.which`, wire the preflight into `NusRunner.reconstruct()`/`cli/nus.py`, write `docs/NUS-PORTABILITY.md`), sequenced to land FIRST and independently of VAL — then use the now-green `lucy nus check` as the literal gate that tells the human/agent when to proceed to the manual NMRPipe+SMILE install and the VAL run. Do not attempt to script or automate the NMRPipe install itself (official docs confirm it is an interactive, registration-adjacent, shell-config-editing process not suited to unattended execution).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Platform/architecture detection (arch, Rosetta, csh/tcsh) | CLI / Backend detection (`nus/backends/nmrpipe_smile.py`) | — | Pure local-machine introspection, no external service; belongs next to the existing tool-detection code it extends |
| Pre-stage fail-loud gate (block `reconstruct`/`pipeline` on critical gaps) | Orchestration (`nus/runner.py::NusRunner.reconstruct()`) + CLI (`cli/nus.py`) | Backend (`diagnose()` is the data source) | Mirrors the existing RECON-02/RECON-04 pattern: preconditions are checked before any subprocess dispatch, in the orchestrator, not buried in a single stage |
| Portability documentation | Docs (`docs/NUS-PORTABILITY.md`) | CLAUDE.md/README (links) | Pure documentation artifact, no runtime component |
| NMRPipe+SMILE installation | Human/manual (outside the codebase) | CLAUDE.md (documented prerequisite) | Third-party, registration-adjacent, shell-config-editing install — explicitly out of scope for automation per the milestone's own Out-of-Scope table ("TopSpin headless reconstruction... no source confirms a true zero-display headless mode") and D-01 ("not a code deliverable") |
| Real reconstruction execution (exp2/3/4) | CLI (`lucy nus pipeline`, existing, Phase 99) | Backend (NMRPipe+SMILE subprocess chain) | No new code; this phase exercises the already-built pipeline |
| §8 quality judgement | QC gate (`nus/qc.py::run_qc_checks()`, existing, Phase 99) | Human (chemist confirm on PARTIAL, D-02) | Machine judge is already built; the only new "logic" is the human sign-off procedure for the PARTIAL/soft-only case, which is a documented manual step, not code |
| CASE convergence proof | CASE orchestrator (`case.md`, existing, untouched) + `lsd/runner.py::LSDRunner` | `ranking/` | Runs the real, unmodified orchestrator; "convergence" is observed (does LSD terminate + does `analysis/final_results.md` get written with a finite candidate count), not implemented |
| Evidence/documentation of validation | New `VALIDATION.md` + committed peak JSONs/QC reports | ROADMAP.md (limitation note if FAIL) | Durable, reproducible-by-hand record per D-01 |

## Standard Stack

### Core

No new libraries. This phase adds Python-stdlib-only detection code (`platform`, `subprocess`, `shutil`) to existing modules, and one external, non-pip, manually-installed tool (NMRPipe+SMILE) that is already the locked v10.0 backend (Phase 97-99 decision, not re-litigated here).

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| NMRPipe | `mac11_arm64` (native Apple Silicon build) [CITED: ibbr.umd.edu/nmrpipe/install] | Reconstruction backend already integrated (Phase 97-99) | Locked milestone decision; native arm64 build confirmed to exist |
| SMILE plugin (`plugin.smile.tZ`) | bundled with the "Companion Files from the Ad Bax Group at the NIH" download set [CITED: ibbr.umd.edu/nmrpipe/install] | Sparse-sampling reconstruction plugin (`nmrPipe -fn SMILE`) | Same locked decision; ships as a **separate** download from base NMRPipe — install checklist must include it explicitly, it will NOT appear after installing only the base NMRPipe/binval/companion tarballs |
| Python stdlib: `platform`, `subprocess`, `shutil` | 3.10+ (project floor) [VERIFIED: local interpreter] | Arch/Rosetta/csh detection for PORT-01 | No package needed; `pyproject.toml` stays untouched, matching NUS-05's dependency-free-core invariant |

**Version verification:**
```bash
python3 -c "import sys; print(sys.version)"   # 3.10+ already the project floor (pyproject.toml)
```
No `npm view`/`pip index versions` check applies — no new pip/npm packages are introduced by this phase.

### Supporting

| Item | Purpose | When to Use |
|------|---------|-------------|
| `sysctl -n sysctl.proc_translated` (macOS-only sysctl OID) | The Apple-documented mechanism to detect whether the CURRENT process is running under Rosetta 2 translation | Only inside a `platform.system() == "Darwin"` branch; errors/absent on Linux and on Intel Macs without Rosetta — must be treated as "not applicable" (`None`), never as "translated=False" by default-catching an exception incorrectly |
| `shutil.which("csh")` / `shutil.which("tcsh")` | Detect C-shell interpreter availability (many NMRPipe utility scripts, e.g. `nusExpand.tcl`/`bruk2pipe`, are csh/tcsh scripts invoked via their shebang even when lucy-ng calls them as a direct subprocess, not a piped csh chain) | Critical check per D-05 — absence blocks, regardless of platform |
| `platform.machine()` / `platform.system()` | Cross-platform arch/OS identification (works identically on Linux, no Rosetta concept there) | Primary arch signal on Linux/Windows; on macOS, cross-check with the Rosetta sysctl since a translated x86_64 Python interpreter reports `platform.machine() == "x86_64"` even on arm64 hardware |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sysctl -n sysctl.proc_translated` | `subprocess.run(["arch"])` and parse output, or `os.uname()` | `arch`/`uname -m` report the architecture of the process being *executed*, not whether the *calling* process is under Rosetta translation — does not distinguish "genuine arm64 native" from "the Python interpreter itself was invoked as x86_64 under Rosetta." The sysctl OID is the one Apple-documented mechanism that answers the actual question (is THIS process translated); prefer it, but treat `arch -x86_64 nmrPipe -help` (as PITFALLS.md Pitfall 11 suggests) as a *secondary* smoke-test that nmrPipe itself launches successfully in the requested architecture, not as the Rosetta-status source of truth |
| Extending `NmrPipeSmileBackend.diagnose()` in place | A new standalone `nus/platform.py` module with its own `PlatformDiagnosis` model, composed into `diagnose()`'s output | D-05 explicitly says "extend... do not rewrite," but a small pure-function helper module (e.g. `nus/platform_check.py` exporting `detect_platform() -> dict`) that `diagnose()` calls and merges in is fully consistent with that instruction — it is additive composition, not a rewrite, and keeps the arch/Rosetta/csh logic unit-testable in isolation from the backend-specific tool-detection logic |

**Installation:**
```bash
# No pip install needed for PORT-01/02 code (stdlib only).
# NMRPipe+SMILE is a manual, non-pip install — see "VAL: NMRPipe+SMILE Install" below.
```

## Package Legitimacy Audit

Not applicable. This phase introduces no new pip/npm/cargo packages — PORT-01/02 use only Python stdlib (`platform`, `subprocess`, `shutil`), and VAL-01/02 install an external, non-pip binary tool (NMRPipe+SMILE) that is a manually downloaded tarball from `ibbr.umd.edu`, never `pip install`-able, exactly like the existing LSD-solver prerequisite. No `slopcheck`/registry verification applies.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PORT-01/02 (software, CI-testable)                                     │
│                                                                           │
│  platform.machine()/system() ─┐                                         │
│  sysctl proc_translated (macOS)├─► detect_platform() ──┐                │
│  shutil.which("csh"/"tcsh")   ─┘        (new helper)     │              │
│                                                            ▼              │
│  NmrPipeSmileBackend.diagnose()  ◄── merges platform dict into existing │
│         │                              status/missing_tools/hint dict   │
│         ▼                                                                │
│  `lucy nus check` (existing CLI, extended text/json output)             │
│         │                                                                │
│         ▼                                                                │
│  NusRunner.reconstruct() / cli/nus.py::pipeline                         │
│  ── NEW: pre-stage precondition check ──                                │
│     critical issue present? ──yes──► raise/exit≠0 BEFORE any subprocess │
│     soft issue present?     ──yes──► log warning, proceed               │
│         │ no critical issue                                              │
│         ▼                                                                │
│  (existing Phase 98/99 stage chain: convert→process_direct→SMILE→        │
│   process_indirect→bridge→qc→write/quarantine)                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  VAL-01/02 (empirical, manual/backend-gated — NOT CI)                   │
│                                                                           │
│  Human: install NMRPipe (mac11_arm64) + SMILE plugin, source             │
│         nmrInit.mac11_arm64.com, add bin/ to PATH                       │
│         │                                                                │
│         ▼                                                                │
│  `lucy nus check` ──green──► `lucy nus pipeline <expdir>` × 3            │
│         (exp2 COSY / exp3 HSQC / exp4 HMBC)                             │
│         │                                                                │
│         ▼                                                                │
│  existing `nus/qc.py::run_qc_checks()` verdict (PASS/PARTIAL/FAIL)      │
│         │                                                                │
│    PASS/soft-PARTIAL+chemist-confirm ──► write VALIDATION.md §8 result  │
│    critical FAIL ──► bounded tuning-budget sweep (D-04) ──► re-run       │
│         │ (after budget exhausted, still FAIL)                          │
│         ▼                                                                │
│    document limitation in VALIDATION.md + ROADMAP, name RECON-F1         │
│                                                                           │
│  Peaks written to analysis/nmr_peaks/*.json (real experiment dir,       │
│  NOT overwriting the known-bad QC-02 regression fixtures)               │
│         │                                                                │
│         ▼                                                                │
│  `/lucy-ng:case C20H32O2` (existing orchestrator, untouched)             │
│         │                                                                │
│         ▼                                                                │
│  LSDRunner terminates (no ~10⁶ explosion) ──► analysis/final_results.md │
│  with a finite, ranking-produced candidate set ──► VAL-02 bar met       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/lucy_ng/nus/
├── platform_check.py       # NEW (planner discretion on name) — pure
│                            #   detect_platform() -> dict (arch, rosetta,
│                            #   csh/tcsh), no backend-specific logic
├── backends/
│   └── nmrpipe_smile.py    # MODIFIED (additive) — diagnose() merges in
│                            #   detect_platform()'s output under a
│                            #   "platform" key; new critical/soft
│                            #   classification surfaced alongside the
│                            #   existing status/missing_tools/hint keys
├── runner.py                # MODIFIED (additive) — NusRunner.reconstruct()
│                            #   gains a precondition check (mirrors the
│                            #   existing F2-before-F1 RECON-02 gate
│                            #   pattern) that raises before any
│                            #   run_stage() call on a critical platform/
│                            #   tool gap
└── cli/nus.py                # MODIFIED (additive) — check output gains a
                              #   platform section (text+json); reconstruct/
                              #   pipeline surface the new precondition
                              #   failure as a clean exit≠0 message

docs/
└── NUS-PORTABILITY.md       # NEW — the PORT-02 matrix

CLAUDE.md                    # MODIFIED (additive) — "Local prerequisites"
                              #   section gains the NMRPipe+SMILE entry,
                              #   alongside the existing LSD-solver and
                              #   reference-DB entries; links to
                              #   docs/NUS-PORTABILITY.md

.planning/phases/100-.../
└── VALIDATION.md             # NEW (this phase's deliverable) — §8 verdict
                              #   per experiment + case-convergence result
                              #   + (if applicable) documented FAIL/RECON-F1
                              #   pointer
```

### Pattern 1: Extend a diagnose()-style dict, don't create a parallel reporting path

**What:** `NmrPipeSmileBackend.diagnose()` already returns a structured dict (`status`, `missing_tools`, `smile_available`, `hint`). PORT-01 adds a `platform` key to that same dict (e.g. `{"arch": "arm64", "rosetta_translated": false, "csh_available": true, "tcsh_available": true, "critical_platform_issues": [], "soft_platform_warnings": []}`), and a top-level `overall_status` (or extends `status`) that folds platform criticality into the existing available/not-available signal.

**When to use:** Whenever a new class of precondition needs to be surfaced through an already-established, already-tested diagnostic entry point — avoids `lucy nus check`'s text/json output growing two independent reporting shapes that the planner/tests then have to keep in sync.

**Example:**
```python
# Source: existing src/lucy_ng/nus/backends/nmrpipe_smile.py (read in full during research)
@classmethod
def diagnose(cls) -> dict[str, Any]:
    missing = cls.missing_tools()
    platform_info = detect_platform()  # NEW: from nus/platform_check.py
    # ... existing status/hint logic unchanged ...
    result["platform"] = platform_info
    return result
```

### Pattern 2: Precondition-check-before-dispatch (mirrors the existing RECON-02 gate)

**What:** `NusRunner.reconstruct()` already has a precedent for "raise BEFORE any subprocess is dispatched" — the F2-before-F1 ordering gate (`_resolve_f2_plan()` returning `None` raises a `RuntimeError` before `run_stage()` is ever called, per Phase 98's RECON-02). PORT-01's fail-loud requirement is the same shape: call `backend.diagnose()`, and if any `critical_platform_issues`/`missing_tools` are non-empty, raise (or in the CLI, `raise SystemExit(1)` with a clear message) before `params`/`schedule` reads even happen, let alone stage dispatch.

**When to use:** Any new "must be true before we spend real time/resources" precondition in this pipeline.

**Example:**
```python
# Illustrative — mirrors the existing pattern already in nus/runner.py
def reconstruct(self, expdir, ...):
    diagnosis = self.backend.diagnose()
    if diagnosis.get("platform", {}).get("critical_platform_issues"):
        raise RuntimeError(
            f"Critical platform issue(s), aborting before any stage runs: "
            f"{diagnosis['platform']['critical_platform_issues']}"
        )
    # ... existing params/schedule/F2-F1 gate logic unchanged ...
```

**Important finding for the planner:** as of this research, `NusRunner.reconstruct()` has **no backend-availability check at all** — it goes straight from `expdir` to `read_nus_params`/`read_nus_schedule` to stage dispatch. `lucy nus check` exists as a *separate* command a human/agent is expected to run first, but nothing enforces that sequencing programmatically. PORT-01 is the first requirement that makes this a hard, code-enforced precondition rather than a documentation convention — plan a task for this explicitly, it is not "just add fields to diagnose()."

### Pattern 3: Skipif-guarded backend-gated integration test (existing precedent, reuse for VAL)

**What:** `tests/nus/test_reconstruct_integration.py` already implements the exact pattern VAL-01's automated (non-manual) surface should reuse: a single `@pytest.mark.skipif`-guarded test keyed off `NmrPipeSmileBackend.is_available()` AND an external-data-path existence check, with the data path overridable via `LUCY_NUS_TEST_DATA`. It is expected to SKIP (not fail) on any machine without the real backend installed.

**When to use:** For any new automated test that needs the real NMRPipe+SMILE binaries — do not invent a second skip-condition convention.

**Example:**
```python
# Source: tests/nus/test_reconstruct_integration.py (verbatim pattern, read in full)
@pytest.mark.skipif(
    not _backend_available() or not _EXTERNAL_DATA.exists(),
    reason="NMRPipe+SMILE backend or external C20H32O2 data not available...",
)
def test_...(): ...
```

### Anti-Patterns to Avoid

- **Scripting/automating the NMRPipe install itself:** official docs confirm the install is registration-adjacent (download requires navigating `ibbr.umd.edu`), edits `.cshrc` manually per the user's own instructions, and requires a logout/login cycle for the sourced environment to take effect. This is not automatable inside an agent session and is explicitly out of scope (D-01: "not a code deliverable"). Do not write an `install_nmrpipe.sh` script as part of this phase's plans.
- **Treating `arch -x86_64 nmrPipe -help` succeeding/failing as the sole Rosetta signal:** it tests whether Rosetta CAN translate and run a given binary, not whether the CURRENT process/interpreter already is one. Use `sysctl -n sysctl.proc_translated` for the actual Rosetta-translation status of the running process; keep the `arch -x86_64` smoke-test (if used at all) as a secondary "can we even launch nmrPipe under emulation" check, not conflated with it.
- **Special-casing Windows detection with new logic:** the existing critical checks (missing backend binary, missing csh) already fail correctly on a hypothetical Windows run without any extra `platform.system() == "Windows"` branch — Windows genuinely has neither csh/tcsh nor a native NMRPipe build, so the generic checks degrade correctly. Do not add Windows-specific detection code; just make sure `docs/NUS-PORTABILITY.md` explains *why* the generic checks already cover it.
- **Overwriting the known-bad QC-02 regression fixtures:** `.../C20H32O2/analysis/nmr_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2}.json` are the FAIL regression floor from Phase 99 (their `caveat` field documents "home-grown per-column IST... residual t1 ridges"). VAL-01's real reconstruction must write its output somewhere else (a new subdirectory, or overwrite only after those three files are first copied/renamed to an explicit `_known_bad_home_ist` archive path) — never silently replace them, or QC-02's discrimination proof becomes unverifiable in the future.
- **Grading VAL-01 by inventing new criteria beyond §8:** the guide's §8 text is short and specific (5 named quaternaries, ~17 protonated carbons with 1/2 correlations, clean edited signs, ridge-free HMBC with sharp gem-dimethyl correlations, a real COSY network beyond the OH ridge at 5.32, signal-to-ridge better than the existing home-IST lists) — the existing `nus/qc.py` checks already encode these; do not add a seventh ad hoc criterion during VAL that the QC gate does not already check.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| §8 quality judgement | A new one-off "is this reconstruction good" script for VAL-01 | The existing `nus/qc.py::run_qc_checks()` (six checks, PASS/PARTIAL/FAIL, D-02 critical/soft split), invoked via the existing `lucy nus qc`/`lucy nus pipeline` | It is already the calibrated D-02 machine judge; VAL-01 is the first REAL-data test of it, not an occasion to build a parallel grader |
| Rosetta-translation detection | A heuristic guess from `platform.machine()` alone | `sysctl -n sysctl.proc_translated` (macOS-specific, Apple-documented) combined with `platform.machine()`/`platform.system()` for the cross-platform baseline | `platform.machine()` alone cannot distinguish "arm64 native" from "x86_64 genuinely Intel" from "x86_64 because the interpreter itself is Rosetta-translated" — a documented, project-level pitfall (PITFALLS.md Pitfall 11) |
| CASE-run convergence proof | A custom timeout/candidate-count harness around LSD for this phase only | The existing `/lucy-ng:case` orchestrator + `lsd/runner.py::LSDRunner` (already has a `timeout` parameter and raises `subprocess.TimeoutExpired` cleanly) + `analysis/final_results.md`/ranking output as already produced by the unmodified pipeline | The milestone's own invariant is "case.md stays untouched" — VAL-02 must observe the existing machinery, not add instrumentation to it |

**Key insight:** Every piece of "judgement" logic this phase needs (quality gate, convergence definition, backend detection dict) already exists in the codebase from Phases 97-99. The work in Phase 100 is (a) a small, additive extension to one existing dict (`diagnose()`) plus one new precondition call site, and (b) exercising already-built commands against real external data and honestly recording the result — resisting the temptation to build new judgement machinery is itself the main risk to avoid.

## Common Pitfalls

### Pitfall 1: `NusRunner.reconstruct()` has no preflight gate today — PORT-01 must add the call site, not just the data

**What goes wrong:** A plan that only adds platform/csh detection fields to `diagnose()` without also wiring a call to it inside `NusRunner.reconstruct()` (or `cli/nus.py`'s command bodies) satisfies "reports readiness" but not "hard-blocks reconstruct/pipeline on critical gaps" (ROADMAP success criterion 1, D-05).
**Why it happens:** `lucy nus check` already exists as a separate, human-run command; it is easy to assume "checking exists" already covers the requirement.
**How to avoid:** Explicitly plan a task that adds a precondition check at the top of `NusRunner.reconstruct()` (mirroring the existing F2-before-F1 `RuntimeError`-before-`run_stage()` pattern) and/or in `cli/nus.py::reconstruct`/`pipeline` command bodies, verified by a unit test with `diagnose()` mocked to return a critical issue and asserting `run_stage`/subprocess is never invoked.
**Warning signs:** A plan whose only diff is inside `nus/backends/nmrpipe_smile.py` and `cli/nus.py`'s `check` command — no touch to `nus/runner.py::reconstruct()` — is very likely to satisfy PORT-01's "readiness reporting" half but miss the "hard-blocks" half.

### Pitfall 2: SMILE is a separate download from base NMRPipe

**What goes wrong:** Following only the base `install.com`/`NMRPipeX.tZ`/`binval.com` install steps leaves `nmrPipe -fn SMILE -help` reporting "unknown function" (the existing `smile_plugin_available()` probe correctly detects this as `smile_plugin_missing`, distinct from `not_installed`) — but a human following generic NMRPipe install tutorials may not realize a second, separate file is needed.
**Why it happens:** `plugin.smile.tZ` is listed under "Companion Files from the Ad Bax Group at the NIH" on the install page, not the primary "Download NMRPipe" section.
**How to avoid:** The CLAUDE.md prerequisite entry and `docs/NUS-PORTABILITY.md` must explicitly call out downloading and installing `plugin.smile.tZ` as its own step, not assume it is bundled.
**Warning signs:** `lucy nus check` reporting `status: "smile_plugin_missing"` after the base install appears "complete" — this is the existing code's own diagnostic for exactly this gap; trust it over assuming a fresh install is broken.

### Pitfall 3: Rosetta detection false-negatives/positives on macOS

**What goes wrong:** `sysctl -n sysctl.proc_translated` returns a non-numeric error string (not `0`/`1`) on genuine Intel Macs and on non-Apple-Silicon-capable macOS versions — code that does `int(output)` unconditionally will raise `ValueError` instead of correctly reporting "not applicable."
**Why it happens:** The OID only exists on Apple-Silicon-capable macOS; querying it elsewhere errors rather than returning `0`.
**How to avoid:** Wrap the sysctl call and treat any non-`0`/`1` output (including a subprocess error) as `rosetta_translated: None` ("not applicable"), never coerce it to `False`.
**Warning signs:** A crash or a silently-wrong `False` when run on CI (Linux) or on an Intel Mac.

### Pitfall 4: Confusing "csh/tcsh interpreter present" with "lucy-ng pipes commands through csh"

**What goes wrong:** Because Phase 98 (D-01) deliberately chose per-stage `subprocess.run()` calls over a single csh pipe chain (to make the fail-loud wrapper reliable — Pitfall 14 from milestone PITFALLS.md), a planner might reason "we don't use csh, so why check for it?" and skip/deprioritize the csh/tcsh check.
**Why it happens:** The reasons for the two decisions (per-stage subprocess vs. csh-pipe-chain; csh/tcsh presence check) are easy to conflate but are actually orthogonal — `bruk2pipe` and `nusExpand.tcl` are themselves csh/tcsh-shebanged scripts; lucy-ng invoking them via `subprocess.run(["bruk2pipe", ...])` still requires a csh/tcsh interpreter to be installed on the system for the OS to execute that script via its shebang line, regardless of whether lucy-ng itself constructs a shell pipe.
**How to avoid:** Keep the csh/tcsh presence check as a genuine, independent critical check (per D-05, explicitly named alongside "missing backend binary").
**Warning signs:** A plan that treats the csh/tcsh check as redundant with `missing_tools()` — they answer different questions (interpreter present vs. named binaries on PATH).

### Pitfall 5: The known-bad QC-02 fixtures sit in the exact same directory VAL-01 will write real output to — but the repo's own tests already use a SAFE copy

**What goes wrong:** `.../C20H32O2/analysis/nmr_peaks/{HSQC_exp3,HMBC_exp4,COSY_exp2}.json` (the EXTERNAL data path) is both (a) the default write target of `lucy nus pipeline <expdir>` (which writes to `<expdir>/analysis/nmr_peaks/`) and (b) the original source of the Phase-99 QC-02 regression-floor FAIL fixtures. Running `lucy nus pipeline` on the real `C20H32O2` experiment directories without care would overwrite those external files in place.
**Why it happens:** `<expdir>/analysis/nmr_peaks/` is the one, single, unparameterized consumable-peaks location by design (D-07 write boundary, Phase 99) — there is no separate "test fixtures" vs. "real run output" directory distinction built into the pipeline itself.
**Resolved by research (good news):** the automated QC-02 regression tests do **NOT** read the external path directly — `tests/nus/conftest.py::known_bad_peaks_dir` resolves to a repo-committed copy at `tests/fixtures/nus/known_bad_peaks/{13C_exp6_narrow,13C_exp7_wide,1H_exp1,COSY_exp2,HMBC_exp4}.json` [VERIFIED: read `tests/nus/conftest.py`/`ls tests/fixtures/nus/known_bad_peaks/` in this research pass]. `tests/nus/test_qc_regression.py`, `test_cli_pipeline.py`, and `test_qc_checks.py` all consume this fixture directory, never the external `.../C20H32O2/analysis/nmr_peaks/` path. This means: **the automated regression floor (QC-02) is already safe** — overwriting the external files does not touch `tests/fixtures/nus/known_bad_peaks/`. The only remaining risk is losing the external files themselves as a piece of *project history/evidence* (they document the original 2026-07-09 failure mode on disk, outside git).
**How to avoid:** Before running VAL-01 for real, copy the three external known-bad files to an explicit archive path (e.g. `analysis/nmr_peaks/known_bad_home_ist_archive/` under the external `C20H32O2` tree, or simply confirm they already match `tests/fixtures/nus/known_bad_peaks/` byte-for-byte and treat the repo copy as the durable record) before `lucy nus pipeline` overwrites them. Do not touch `tests/fixtures/nus/known_bad_peaks/` at all — that fixture directory must keep the ORIGINAL known-bad content for QC-02 to keep proving discrimination.
**Warning signs:** `git status` inside `tests/fixtures/nus/known_bad_peaks/` showing any change — that would be the real regression-floor break; a `git status`/diff on the EXTERNAL (non-repo) files is expected and not a problem for the automated suite, only for hand-preserved project history.

### Pitfall 6: PARTIAL-with-chemist-confirm has no existing "confirm" mechanism — this phase must define one

**What goes wrong:** D-02 requires "a brief chemist visual confirms the connectivity is usable for CASE" on soft-only PARTIAL — but nothing in the codebase currently implements or records a human confirmation step (QC verdicts are fully machine, by QC-01's own design: "no human in the loop").
**Why it happens:** The QC gate was deliberately built headless (QC-01); D-02's chemist-confirm is a *milestone-close-only*, one-off exception to that, not a new permanent code path.
**How to avoid:** Treat this as a `VALIDATION.md` documentation step, not new code: if VAL-01 lands PARTIAL with only soft violations, the plan should include a concrete manual review action (e.g., "read the reconstructed HSQC/HMBC/COSY peak lists and the §8 checklist side by side, note agreement/disagreement per item") whose outcome (confirmed / not confirmed) is recorded as a line in `VALIDATION.md`, not as a new `QcVerdict` enum value or CLI flag.
**Warning signs:** A plan that adds a new `--chemist-confirmed` CLI flag or a `HUMAN_CONFIRMED` verdict state to `nus/qc.py` — this over-engineers a one-off milestone-close judgement call into permanent pipeline code, contradicting QC-01's "no human in the loop" design and D-07's single-pipeline-boundary invariant.

### Pitfall 7: `-nSigma` is a reconstruction knob already exposed in `NusRunner.reconstruct()`/`NmrPipeSmileBackend.reconstruct_indirect()` but NOT yet a `lucy nus reconstruct`/`pipeline` CLI flag

**What goes wrong:** D-04's bounded tuning budget calls out `-maxIter`/`-thresh`/virtual-echo explicitly (already CLI flags: `--iterations`, `--threshold`, `--virtual-echo`) but `-nSigma` (also a real SMILE convergence knob, already a `NusRunner.reconstruct(n_sigma=5, ...)` parameter) has no CLI flag today — a tuning sweep that needs to vary it would have to call the Python API directly, not the CLI, unless a plan adds the flag.
**Why it happens:** `n_sigma` was added to `NusRunner`/`NmrPipeSmileBackend` in Phase 98 but Phase 98/99's CLI work only surfaced `--iterations`/`--threshold`/`--virtual-echo`/phase flags in `cli/nus.py`.
**How to avoid:** Decide explicitly (planner discretion) whether the D-04 tuning-budget sweep is driven via direct Python calls to `NusRunner().reconstruct(n_sigma=...)` (no CLI change needed) or whether `--n-sigma` should be added to `lucy nus reconstruct`/`pipeline` as part of this phase — either is valid, but the plan must state which, since as of this research the CLI cannot vary `n_sigma` without a code change.
**Warning signs:** A tuning-budget plan step that says `lucy nus pipeline --n-sigma 3 ...` will fail with "no such option" against the current CLI.

## Code Examples

### Current `diagnose()` output shape (verified by reading the file in full)

```python
# Source: src/lucy_ng/nus/backends/nmrpipe_smile.py (as of Phase 99, read in full)
{
    "status": "available" | "smile_plugin_missing" | "installed_not_sourced" | "not_installed",
    "missing_tools": [...],       # subset of ["nmrPipe", "bruk2pipe", "nusExpand.tcl"]
    "smile_available": bool,
    "hint": "...",                 # actionable, contains the install URL
}
```
PORT-01 adds a `"platform"` key here (see Pattern 1 above) — this is the concrete extension point.

### Current environment probe (verified live during this research pass, 2026-07-18)

```bash
$ uname -m                                    # arm64
$ sw_vers                                     # ProductVersion: 26.5
$ sysctl -n sysctl.proc_translated            # 0  (native, not Rosetta-translated)
$ which csh tcsh                              # /bin/csh /bin/tcsh (both present)
$ which nmrPipe bruk2pipe nusExpand.tcl       # (none found — install gap, confirms D-01's framing)
```
[VERIFIED: local shell, this session] — matches the CONTEXT.md-stated 2026-07-18 verification exactly; re-confirmed independently in this research pass.

### `lucy nus pipeline` existing invocation VAL-01 will run three times, unmodified

```bash
# Source: src/lucy_ng/cli/nus.py::pipeline (existing, Phase 99, read in full)
lucy nus pipeline /path/to/C20H32O2/2 --format json   # exp2, COSY
lucy nus pipeline /path/to/C20H32O2/3 --format json   # exp3, HSQC
lucy nus pipeline /path/to/C20H32O2/4 --format json   # exp4, HMBC
```
Each call writes to `analysis/nmr_peaks/*.json` on PASS/PARTIAL, or quarantines to `analysis/nus_recon/<expN>/qc_failed/` and exits non-zero on FAIL (D-07, already implemented — see `cli/nus.py` lines ~457-613, read in full during this research pass).

### Existing skipif backend-gated test pattern to extend/reuse for VAL automation

```python
# Source: tests/nus/test_reconstruct_integration.py (read in full)
_EXTERNAL_DATA = Path(os.environ.get("LUCY_NUS_TEST_DATA", str(_DEFAULT_EXTERNAL_DATA)))

@pytest.mark.skipif(
    not _backend_available() or not _EXTERNAL_DATA.exists(),
    reason="NMRPipe+SMILE backend or external C20H32O2 data not available...",
)
def test_...(): ...
```
Note: this existing test only exercises `NusRunner.reconstruct()` on exp3 (HSQC) — it does NOT exercise `lucy nus pipeline` (the QC-gated, write-boundary-enforced full chain) or exp2/exp4. If Wave 0 wants an automated (skip-in-CI) test analog of VAL-01, a new test following this same pattern but calling `pipeline` on all three experiments would be additive, not a modification of this file.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Ad hoc, hand-rolled per-column IST reconstruction (nmrglue-based, the 2026-07-09 failure) | Real, literature-validated NMRPipe+SMILE reconstruction with a mandatory QC gate | Phases 97-99 (2026-07-12 to 2026-07-16), this phase validates it on real data | This is precisely the milestone's core value proposition; VAL-01/02 is the proof, not new capability |
| Assumed "dev Mac can't run the backend" (implicit earlier framing) | Confirmed (CONTEXT.md D-01, re-verified this research pass) the Mac is a first-class native target — it is an *install gap*, not a *platform limit* | 2026-07-18 (context-gathering + this research) | Removes any temptation to route VAL to a remote host; the local machine IS the reference platform the milestone claims |

**Deprecated/outdated:**
- Any assumption that NMRPipe requires Rosetta on Apple Silicon — false; a native `mac11_arm64` build exists and is the one to install [CITED: ibbr.umd.edu/nmrpipe/install].
- Any assumption that SMILE ships bundled with base NMRPipe — false; it is a separate companion download (`plugin.smile.tZ`) [CITED: ibbr.umd.edu/nmrpipe/install].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `mac11_arm64` NMRPipe download and the `plugin.smile.tZ` companion file, once installed and sourced, will actually run `-fn SMILE` correctly on macOS 26.5 arm64 — this was confirmed only via the install *documentation*, not by actually completing the install in this research pass (D-01 makes the install itself a manual step outside this research session's scope) | Standard Stack, Common Pitfall 2 | If the real install surfaces an incompatibility (e.g. a newer macOS ABI issue with an older native binary), VAL-01 could be blocked on an install-level problem the D-04 tuning budget cannot fix — this would need to be surfaced as a new, not-yet-anticipated blocker, distinct from D-04's reconstruction-quality tuning scope |
| A2 | The `sysctl -n sysctl.proc_translated` OID behaves identically on macOS 26.5 as documented for earlier macOS versions (this exact OID's stability across macOS major versions was not independently re-verified against Apple's current developer docs in this pass, only exercised live on this machine returning `0`) | Standard Stack, Alternatives Considered | If Apple has changed this OID's semantics/availability in a later macOS release, the Rosetta soft-check could silently misreport; low risk since it was exercised live and returned a sane, expected value (`0`, matching "native, not translated") |
| A3 | No pip-installable Python package is needed anywhere in this phase (stdlib `platform`/`subprocess`/`shutil` suffice for PORT-01) | Package Legitimacy Audit | If the planner decides a richer platform-detection library is desirable (unlikely, low value for this small a check surface), the Package Legitimacy Gate would need to be re-run at planning/execution time |

**If this table is empty:** N/A — see above; three low-to-medium-risk assumptions logged, none blocking.

## Open Questions

1. **What exact CLI surface does the D-04 tuning-budget sweep use?**
   - What we know: `--iterations`/`--threshold`/`--virtual-echo`/phase flags already exist on `lucy nus reconstruct`/`pipeline`; `-nSigma` does not have a CLI flag yet (Pitfall 7).
   - What's unclear: whether the planner wants to add a `--n-sigma` flag as part of this phase, or drive the sweep via direct Python calls to `NusRunner().reconstruct(n_sigma=...)` in a one-off script/notebook that is not committed as permanent CLI surface.
   - Recommendation: Add `--n-sigma` as a CLI flag (small, consistent extension mirroring the existing flag pattern) so the entire D-04 sweep is drivable via the same `lucy nus pipeline` command a human would naturally reach for — avoids a separate, undocumented "tuning script" needing its own maintenance.

2. **RESOLVED during this research pass:** Do the automated QC-02 regression tests read the external `C20H32O2` path directly (requiring careful relocation before VAL-01 overwrites it), or a repo-local copy?
   - What we know: `tests/nus/conftest.py::known_bad_peaks_dir` resolves to `tests/fixtures/nus/known_bad_peaks/` — a repo-committed copy, confirmed present via `ls` in this research pass (`13C_exp6_narrow.json`, `13C_exp7_wide.json`, `1H_exp1.json`, `COSY_exp2.json`, `HMBC_exp4.json`, `HSQC_exp3.json`). `test_qc_regression.py`, `test_cli_pipeline.py`, `test_qc_checks.py` all consume this fixture directory.
   - What's unclear: nothing operationally blocking — the automated suite is safe. The only open item is whether the planner wants a symbolic "preserve the external originals" step (e.g. an explicit archive copy under the external `C20H32O2/analysis/` tree) as part of the VAL-01 plan, purely for human-auditable project history outside git.
   - Recommendation: No test-fixture changes needed. Add a one-line plan step to archive-copy (not move) the external known-bad files before running `lucy nus pipeline` for real, purely as a courtesy/history-preservation step — not a blocking requirement.

3. **Does the local NMRPipe install actually work headlessly (no X11/XQuartz needed) for the CLI-only stages lucy-ng invokes?**
   - What we know: official docs mention XQuartz/X11 setup as part of the general install walkthrough, but this is documented in the context of `nmrDraw` (the GUI viewer), which lucy-ng never invokes — only `nmrPipe`, `bruk2pipe`, `nusExpand.tcl` (all CLI/scriptable tools) are used.
   - What's unclear: whether the base `install.com` script itself has a hard X11-library-linkage dependency even for the non-GUI binaries (some older NMRPipe utility binaries historically linked X11 libraries even when not displaying anything), which would need X11 present in some minimal form even in a "no GUI use" scenario.
   - Recommendation: During the actual install (D-01's manual step), if any binary fails to launch with an X11-library-not-found error, install XQuartz anyway even though `nmrDraw` itself is out of scope — cheap mitigation, do not treat a linkage error as a genuine platform blocker before trying it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `csh`/`tcsh` | PORT-01 critical check; NMRPipe utility scripts' shebang interpreter | ✓ | `/bin/csh`, `/bin/tcsh` present | — |
| `arm64` native (not Rosetta) | PORT-01 soft check | ✓ | `sysctl.proc_translated=0` (native) | — (this machine has no fallback need; documents the "clean" soft-check case) |
| `nmrPipe` | VAL-01/02 (backend for reconstruction) | ✗ | — | Manual install per D-01 (native `mac11_arm64` build); no code fallback — VAL cannot proceed without it |
| `bruk2pipe` | VAL-01/02 | ✗ | — | Same manual install (bundled with base NMRPipe download) |
| `nusExpand.tcl` | VAL-01/02 | ✗ | — | Same manual install (bundled with base NMRPipe download) |
| SMILE plugin (`nmrPipe -fn SMILE -help`) | VAL-01/02 | ✗ | — | Manual install of the SEPARATE `plugin.smile.tZ` companion file (Common Pitfall 2) |
| `python3` (3.10+) | PORT-01 code | ✓ | project floor already satisfied | — |
| Docker | Not used by this phase (no containerization introduced) | n/a | — | — |

**Missing dependencies with no fallback:**
- `nmrPipe`/`bruk2pipe`/`nusExpand.tcl`/SMILE plugin — VAL-01/02 cannot run until these are manually installed (D-01's explicit, accepted, non-blocking-for-PORT gap). PORT-01/02 ship independently regardless (D-04's "PORT ships independently of the VAL outcome").

**Missing dependencies with fallback:**
- None applicable — there is no alternate backend fallback path for VAL within this phase's scope (RECON-F1/hmsIST is explicitly deferred, D-04).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ [VERIFIED: pyproject.toml `pytest>=7.0`] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]` |
| Quick run command | `pytest tests/nus/ -x` |
| Full suite command | `pytest` (full repo suite; 1373+ passed as of Phase 99 completion per STATE.md) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| PORT-01 | `detect_platform()`/`diagnose()` correctly classifies arch/Rosetta/csh as critical vs soft, with `platform`/`subprocess`/`shutil.which` mocked for all branches (native arm64, Rosetta-translated, genuine Intel, Linux, Windows-simulated, missing csh) | unit | `pytest tests/nus/test_platform_check.py -x` | ❌ Wave 0 |
| PORT-01 | `NusRunner.reconstruct()` raises (never calls `run_stage()`/dispatches a subprocess) when `diagnose()` reports a critical platform/tool issue, mocked | unit | `pytest tests/nus/test_platform_preflight_gate.py -x` | ❌ Wave 0 |
| PORT-01 | `lucy nus check --format json` includes the new `platform` key and reports the correct exit code (0 on all-clear, 1 on any critical issue) | unit/CLI | `pytest tests/nus/test_cli_check.py -x` | ❌ Wave 0 (no existing `test_cli_check.py` found in `tests/nus/`) |
| PORT-02 | `docs/NUS-PORTABILITY.md` exists and contains the three required rows (macOS-arm64-native, Linux-native, Windows-WSL2-gap) | smoke/lint | A simple existence + grep-for-headers assertion, e.g. `pytest tests/test_docs.py::test_nus_portability_matrix_exists -x` (or a shell-level CI doc-lint step, planner discretion) | ❌ Wave 0 (no doc-lint precedent found in `tests/`; planner may choose a non-pytest doc-existence check instead) |
| VAL-01 | C20H32O2 exp2/3/4 pass §8 via the QC gate | **manual/backend-gated**, NOT CI | `lucy nus pipeline <expdir> --format json` × 3, real NMRPipe+SMILE install required | manual-only — justification: requires a manually-installed, non-pip, third-party binary tool not present in CI; this is the documented, accepted shape of "Manual-Only" per the existing `test_reconstruct_integration.py` precedent |
| VAL-02 | `/lucy-ng:case C20H32O2` converges (LSD terminates, finite rankable set) | **manual/backend-gated**, NOT CI | `/lucy-ng:case C20H32O2` run via Claude Code, real LSD solver + real reconstructed peaks required | manual-only — justification: exercises the full multi-agent CASE orchestrator against a real, multi-hour NMR structure-elucidation run; not a unit-testable behavior, and `case.md` is explicitly untouched/unexercised by any automated harness in this repo |

### Sampling Rate
- **Per task commit:** `pytest tests/nus/ -x` (PORT-01/02 unit tests only — VAL is not part of the automated per-commit loop)
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`, PLUS the manual VAL-01/02 evidence (`VALIDATION.md` + committed peak JSONs/QC reports) reviewed as the phase's actual milestone-closing proof — the automated suite alone does not certify this phase complete, per D-01/D-02/D-03's explicit manual/empirical framing.

### Wave 0 Gaps
- [ ] `tests/nus/test_platform_check.py` — covers PORT-01's arch/Rosetta/csh detection logic (mocked `platform`/`subprocess.run`/`shutil.which` across native-arm64, Rosetta-translated, genuine-Intel, Linux, Windows-simulated branches)
- [ ] `tests/nus/test_platform_preflight_gate.py` — covers the new precondition-check-before-dispatch in `NusRunner.reconstruct()` (mocked `diagnose()` returning a critical issue → assert no `run_stage()`/subprocess call happens)
- [ ] `tests/nus/test_cli_check.py` — covers `lucy nus check`'s extended text/json output and exit-code semantics (no existing file found under this name in `tests/nus/`; verify at plan time whether platform-check assertions should instead be folded into an existing `test_cli_*` file rather than a new one)
- [ ] Doc-existence check for `docs/NUS-PORTABILITY.md` (PORT-02) — no existing doc-lint precedent in this repo's test suite; planner discretion on whether this is a pytest test or a simple CI/manual checklist item

*(VAL-01/02 have no Wave 0 test gaps in the traditional sense — they are backend-gated manual runs, not unit-testable behaviors; their "test" is the real `lucy nus pipeline`/`/lucy-ng:case` invocation itself, already fully implemented by Phases 97-99.)*

## Security Domain

`security_enforcement` is absent from `.planning/config.json` → treated as enabled, but this phase has essentially no attack surface: it is local CLI tooling (no network service, no authentication, no user-facing web input) operating on a single developer's own machine against the developer's own NMR data.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Not applicable — no auth surface introduced |
| V3 Session Management | No | Not applicable |
| V4 Access Control | No | Not applicable — single-user local CLI |
| V5 Input Validation | Marginal | `expdir`/paths passed to `subprocess.run()` with fixed argument lists (never `shell=True`, never string-interpolated into a shell command) — already the established pattern in `nmrpipe_smile.py`/`runner.py`; PORT-01's new platform-detection subprocess calls (`sysctl`, `shutil.which`) must follow the same fixed-arg-list convention, never pass user/CLI-supplied strings into a shell-interpreted command |
| V6 Cryptography | No | Not applicable — no secrets/crypto introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Command injection via subprocess argument construction | Tampering | Every subprocess call in this codebase already uses a fixed `list[str]` argv (never `shell=True`, never f-string-built shell commands) — PORT-01's new `detect_platform()` helper (invoking `sysctl`, `shutil.which`) must preserve this convention exactly; no expdir/user-supplied string should ever reach a shell-interpreted context |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/100-cross-platform-hardening-end-to-end-validation/100-CONTEXT.md` — locked decisions D-01..D-06, canonical refs
- `.planning/REQUIREMENTS.md` — PORT-01/02, VAL-01/02 exact wording; backend decision; RECON-F1
- `.planning/ROADMAP.md` § Phase 100 — goal + 4 success criteria
- `.planning/STATE.md` — milestone/phase history, Phase 97-99 completion summaries
- `src/lucy_ng/nus/backends/nmrpipe_smile.py`, `src/lucy_ng/nus/backends/__init__.py`, `src/lucy_ng/cli/nus.py`, `src/lucy_ng/nus/qc.py`, `src/lucy_ng/nus/runner.py`, `tests/nus/test_reconstruct_integration.py` — read in full during this research pass
- Live shell probes on the actual dev machine (`uname -m`, `sw_vers`, `sysctl -n sysctl.proc_translated`, `which csh tcsh`, `which nmrPipe bruk2pipe nusExpand.tcl smileNus`) — executed 2026-07-18 during this research session

### Secondary (MEDIUM confidence)
- https://www.ibbr.umd.edu/nmrpipe/install [CITED — fetched via WebFetch during this research pass] — `mac11_arm64` native build existence, `plugin.smile.tZ` as a separate companion download, csh/tcsh shell requirement, `nmrInit.<platform>.com` manual-sourcing step, X11/XQuartz relevance (nmrDraw-only), no registration mentioned in the fetched content (contradicts this repo's own `smile_plugin_available()` docstring's phrasing "free registration required" — flagged as a discrepancy, not resolved in this pass; the actual install step will clarify)
- `.planning/research/SUMMARY.md`, `.planning/research/PITFALLS.md`, `.planning/research/ARCHITECTURE.md` — milestone-level research (backend decision rationale, Pitfalls 11-14 on Apple-Silicon/Rosetta/csh/Windows/silent-subprocess-failure, `nus/` package architecture) — dated 2026-07-12, itself flagged MEDIUM-LOW confidence on exact backend CLI/install specifics pending re-verification (which this research pass partially did via the WebFetch above)

### Tertiary (LOW confidence)
- WebSearch snippet summary of https://www.ibbr.umd.edu/nmrpipe/install (used only to identify the correct URL before WebFetch) — superseded by the direct WebFetch above
- groups.io Apple-Silicon NMRPipe discussion thread — fetch blocked by a paywall (HTTP 402) in this research pass; not used as a source, flagged only so the planner knows this avenue was attempted and failed, not silently skipped

## Metadata

**Confidence breakdown:**
- Standard stack / architecture (PORT-01/02 code integration): HIGH — all integration points read directly from the live codebase in this session
- NMRPipe/SMILE install specifics: MEDIUM — official docs fetched and cross-checked, but the install itself was not executed in this research pass (deliberately out of scope per D-01, a manual step for the actual planning/execution phase)
- VAL-01/02 reconstruction-quality outcome: LOW (necessarily) — this is exactly what VAL-01/02 exist to discover; no research pass can pre-determine whether the real C20H32O2 reconstruction will pass §8 or how CASE will actually behave on the new peaks

**Research date:** 2026-07-18
**Valid until:** 14 days (fast-moving milestone-closing phase; the local environment state — install gap — is the single most time-sensitive fact here and could change as soon as the manual install happens)
