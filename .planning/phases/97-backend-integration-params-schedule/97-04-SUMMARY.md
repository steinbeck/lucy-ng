---
phase: 97-backend-integration-params-schedule
plan: 04
subsystem: infra
tags: [nmrpipe, smile, nus, backend-detection, subprocess, protocol]

# Dependency graph
requires:
  - phase: 97-01
    provides: "src/lucy_ng/nus/backends/__init__.py package marker (docstring-only)"
provides:
  - "NmrPipeSmileBackend: research-corrected external-binary detection (nmrPipe/bruk2pipe/nusExpand.tcl via shutil.which) + SMILE-plugin capability probe (nmrPipe -fn SMILE -help)"
  - "diagnose() distinguishing not_installed / installed_not_sourced / smile_plugin_missing / available with actionable install/source hints"
  - "NusBackend runtime_checkable Protocol + get_backend()/list_available_backends() registry over backend classes"
affects: [97-05, 98-reconstruction-processing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "External-binary detection via classmethods (shutil.which + fixed-arg subprocess.run), mirroring LSDRunner"
    - "Capability-probe detection for plugin-dispatched functionality that shutil.which cannot see (nmrPipe -fn SMILE)"
    - "typing.Protocol + runtime_checkable as the repo's first generic backend-registry shape"

key-files:
  created:
    - src/lucy_ng/nus/backends/nmrpipe_smile.py
    - tests/test_nus_backends.py
  modified:
    - src/lucy_ng/nus/backends/__init__.py

key-decisions:
  - "REQUIRED_TOOLS = [nmrPipe, bruk2pipe, nusExpand.tcl] only -- 'smileNus' deliberately excluded (not a real binary; verified against SMILE User's Manual). Even comments/docstrings avoid the literal substring 'smileNus' to satisfy the plan's grep-based acceptance guard."
  - "SMILE plugin availability is a subprocess capability probe (nmrPipe -fn SMILE -help), never shutil.which(), because SMILE is dispatched internally by nmrPipe's own plugin mechanism"
  - "diagnose() has four distinct states (available, smile_plugin_missing, installed_not_sourced, not_installed) so a user with all tools on PATH but a broken/uninstalled SMILE plugin gets a different message than someone with nothing installed at all"
  - "_REGISTRY typed as dict[str, type[NusBackend]] (not bare dict[str, type]) so mypy can verify list_available_backends()'s cls.is_available() call against the Protocol"

requirements-completed: [NUS-01]

# Metrics
duration: 6min
completed: 2026-07-12
---

# Phase 97 Plan 04: NUS Backend Detection Summary

**NmrPipeSmileBackend detects the real nmrPipe/bruk2pipe/nusExpand.tcl toolchain via shutil.which and probes the SMILE plugin via a fixed-arg `nmrPipe -fn SMILE -help` subprocess call (never `shutil.which("smileNus")`, which does not exist); a NusBackend Protocol + registry expose it generically, both correctly reporting unavailable on this NMRPipe-less dev machine.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-12T14:22:44Z
- **Completed:** 2026-07-12T14:29:12Z
- **Tasks:** 2 completed
- **Files modified:** 3 (2 created, 1 upgraded from plan-01 marker)

## Accomplishments
- `NmrPipeSmileBackend` implements the RESEARCH.md-corrected detection design: three real `which()`-able tools plus a distinct SMILE-plugin capability probe, exactly matching the SMILE manual's own recommended verification command
- `diagnose()` gives four unambiguous diagnostic states with actionable install/source hints (install URL always present), closing D-01's "installed but not sourced" requirement
- `NusBackend` (the repo's first `typing.Protocol`) + `get_backend()`/`list_available_backends()` registry let future callers (Phase 97-05's `lucy nus check` CLI, Phase 98's reconstruction pipeline) address backends generically without importing concrete classes
- 20 new unit tests (all green), including a source-behavior test asserting the SMILE probe uses a fixed arg list with no `shell=True`

## Task Commits

Each task was committed atomically:

1. **Task 1: NmrPipeSmileBackend detection + SMILE capability probe** - `3985673` (feat)
2. **Task 2: NusBackend protocol + registry** - `a29b7ca` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `src/lucy_ng/nus/backends/nmrpipe_smile.py` - `NmrPipeSmileBackend`: `REQUIRED_TOOLS`, `missing_tools()`, `smile_plugin_available()`, `is_available()`, `diagnose()`
- `src/lucy_ng/nus/backends/__init__.py` - Upgraded from the plan-01 docstring-only marker to define `NusBackend` (Protocol), `_REGISTRY`, `get_backend()`, `list_available_backends()`
- `tests/test_nus_backends.py` - `TestNusBackendAvailability`, `TestNusBackendDiagnose`, `TestNusBackendSubprocessSafety`, `TestNusBackendRegistry` (20 tests total)

## Decisions Made
- See `key-decisions` in frontmatter. Most notable: the plan's own acceptance guard (`grep -n "smileNus" ... MUST return no matches`) applies even to comments/docstrings, so the module docstring's explanation of *why* `smileNus` isn't real was rephrased to avoid the literal substring while keeping the explanation intact.
- `_REGISTRY` type annotation tightened to `dict[str, type[NusBackend]]` (rather than bare `dict[str, type]`) to keep mypy clean on the new files — a Rule 1 (bug) class fix caught during verification, not a plan deviation in behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed literal "smileNus" substring from nmrpipe_smile.py comments/docstrings**
- **Found during:** Task 1, acceptance-criteria verification
- **Issue:** The initial docstring/comment explaining *why* `smileNus` is not a real binary name literally contained the substring `smileNus`, which would fail the plan's own acceptance guard (`grep -n "smileNus" src/lucy_ng/nus/backends/nmrpipe_smile.py` MUST return no matches) even though the *code* (REQUIRED_TOOLS) never referenced it.
- **Fix:** Rephrased both occurrences (module docstring, `REQUIRED_TOOLS` comment) to describe the non-existent binary without using the literal substring.
- **Files modified:** `src/lucy_ng/nus/backends/nmrpipe_smile.py`
- **Verification:** `grep -n 'smileNus' src/lucy_ng/nus/backends/nmrpipe_smile.py` returns nothing; `pytest tests/test_nus_backends.py -x` still green (15/15 at that point).
- **Committed in:** `3985673` (Task 1 commit)

**2. [Rule 1 - Bug] Tightened `_REGISTRY` type annotation for mypy**
- **Found during:** Task 2, post-task mypy check
- **Issue:** `_REGISTRY: dict[str, type]` caused `mypy` to report `"type" has no attribute "is_available"` at the `list_available_backends()` call site (`src/lucy_ng/nus/backends/__init__.py:87`).
- **Fix:** Changed the annotation to `dict[str, type[NusBackend]]`, letting mypy verify the classmethod call against the Protocol.
- **Files modified:** `src/lucy_ng/nus/backends/__init__.py`
- **Verification:** `mypy src/lucy_ng/nus/backends/` reports zero errors in the new files (all remaining mypy errors are pre-existing, in unrelated modules).
- **Committed in:** `a29b7ca` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs caught by the plan's own verification gates, not scope changes)
**Impact on plan:** Both fixes are cosmetic/type-safety corrections with zero behavior change. No scope creep.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required. NMRPipe/SMILE installation itself remains a Phase 98 prerequisite (manual-only verification per 97-VALIDATION.md); Phase 97's job is only to correctly *detect* its absence, which it does.

## Next Phase Readiness
- `lucy nus check` (Phase 97-05) can now be built directly on top of `get_backend("nmrpipe_smile")`/`NmrPipeSmileBackend.diagnose()` — no further backend-detection work needed.
- `src/lucy_ng/nus/backends/` diff stays isolated: `params.py`, `schedule.py`, `models/nus.py` were untouched by this plan, matching the wave boundary.
- Full test suite green: 1289 passed, 7 skipped, 1 xfailed (up from 1269 passed at Plan 03 close; +20 new NUS backend tests).

---
*Phase: 97-backend-integration-params-schedule*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created files verified present on disk; both task commits (`3985673`, `a29b7ca`) verified present in git log.
