---
phase: 100-cross-platform-hardening-end-to-end-validation
plan: 02
subsystem: docs
tags: [portability, documentation, nus, cross-platform, wsl2, smile]

# Dependency graph
requires:
  - phase: 99-peak-pick-bridge-qc-gate-cli
    provides: "lucy nus check/reconstruct/pipeline CLI group (the tool the doc tells users to verify with)"
  - phase: 100-01
    provides: "diagnose() status values (available/smile_plugin_missing/installed_not_sourced/not_installed) the doc's Verify-with-lucy-nus-check text names"
provides:
  - "docs/NUS-PORTABILITY.md PORT-02 portability matrix (macOS-arm64-native / Linux-native / Windows-WSL2-gap)"
  - "CLAUDE.md + README.md NMRPipe+SMILE local prerequisite entries linking the matrix"
  - "tests/nus/test_portability_doc.py doc-existence/required-content guard"
affects: [100-03, VAL-01, VAL-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prerequisite-bullet + verify-with-CLI-command + doc-link (mirrors existing LSD-solver / reference-database CLAUDE.md and README blocks)"

key-files:
  created:
    - docs/NUS-PORTABILITY.md
    - tests/nus/test_portability_doc.py
  modified:
    - CLAUDE.md
    - README.md

key-decisions:
  - "WSL2 workaround is written out step-by-step but explicitly marked 'documented, untested' (D-06) -- no Windows host was available to verify it during this milestone"
  - "No Windows-specific detection code is added anywhere (matches Phase 100-01's platform_check.py, which stays generic stdlib-only) -- the doc explains why the existing generic checks already degrade correctly on Windows"
  - "SMILE-is-a-separate-download gotcha called out explicitly in its own section (not buried in the install walkthrough) since it is the single most likely install mistake (RESEARCH Pitfall 2)"

requirements-completed: [PORT-02]

# Metrics
duration: 12min
completed: 2026-07-18
---

# Phase 100 Plan 02: Cross-Platform Portability Documentation Summary

**New `docs/NUS-PORTABILITY.md` PORT-02 matrix (macOS Apple-Silicon native / Linux native / Windows WSL2 gap) with a step-by-step, explicitly-untested WSL2 workaround and the SMILE-separate-download gotcha, linked from CLAUDE.md's Local prerequisites and README, guarded by a new doc-existence/content pytest.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 1 completed
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `docs/NUS-PORTABILITY.md` documents all three platform rows (macOS Apple Silicon
  native, Linux native, Windows WSL2 gap), the SMILE-is-a-separate-download gotcha
  (`plugin.smile.tZ`), a macOS-arm64 install walkthrough, a step-by-step WSL2 workaround
  explicitly marked **"documented, untested"**, a note that Apple-Silicon Rosetta status
  is a soft warning only, and a design note on why no Windows-specific detection code
  exists in `platform_check.py`
- `CLAUDE.md` § Local prerequisites gained a third bullet (NMRPipe + SMILE) in the exact
  shape of the existing LSD-solver/reference-database bullets, linking
  `docs/NUS-PORTABILITY.md`
- `README.md` gained a `### NMRPipe + SMILE (NUS reconstruction)` block alongside the
  existing LSD-solver/reference-database prerequisite blocks, linking the same doc
- `tests/nus/test_portability_doc.py` (7 tests) asserts the doc exists, has the minimum
  40-line length, names all three platforms, marks WSL2 "documented, untested", calls out
  the separate SMILE download, and that both CLAUDE.md and README.md link the doc

## Task Commits

Each task was committed atomically:

1. **Task 1: Write docs/NUS-PORTABILITY.md, add CLAUDE.md prerequisite + README link, add doc test** - `9fe2a1f` (docs)

## Files Created/Modified

- `docs/NUS-PORTABILITY.md` - New: the PORT-02 portability matrix (79 lines)
- `CLAUDE.md` - Additive: NMRPipe+SMILE bullet under § Local prerequisites
- `README.md` - Additive: `### NMRPipe + SMILE (NUS reconstruction)` block near the
  existing LSD-solver / reference-database blocks
- `tests/nus/test_portability_doc.py` - New: 7 tests guarding the doc's existence and
  required content

## Decisions Made

- WSL2 is documented step-by-step but explicitly marked untested per D-06 -- no
  fabricated verification claims
- No Windows-specific code path was added anywhere; the doc explains and defends this
  design choice rather than treating it as a gap that needs code
- The SMILE-separate-download gotcha got its own dedicated section rather than being
  folded into the general install walkthrough, since RESEARCH flagged it as the single
  most likely real-world install mistake

## Deviations from Plan

None — plan executed exactly as written. This plan is pure documentation + a
doc-existence test; no source code changes to `nus/`, `cli/`, or any `.claude/` skill
files were made or needed.

## Issues Encountered

None.

## User Setup Required

None for this plan. The NMRPipe+SMILE install itself remains a separate, already-tracked
manual prerequisite (D-01), out of this plan's scope — it is the subject of Plan 03's
VAL-01/02 empirical work, not this documentation plan.

## Next Phase Readiness

- PORT-02 fully satisfied: every known platform gap (macOS native, Linux native, Windows
  WSL2 gap) investigated and written down; CLAUDE.md/README link the matrix; doc test
  guards required content
- PORT-01 (Plan 01) + PORT-02 (this plan) together close all PORT requirements for the
  phase — VAL-01/02 (Plan 03) can proceed independently, per D-04's "PORT ships
  independently of the VAL outcome"
- No blockers for Plan 03

---
*Phase: 100-cross-platform-hardening-end-to-end-validation*
*Completed: 2026-07-18*

## Self-Check: PASSED

All created files verified present on disk; task commit (9fe2a1f) and summary commit
(b8966c1) verified present in git log.
