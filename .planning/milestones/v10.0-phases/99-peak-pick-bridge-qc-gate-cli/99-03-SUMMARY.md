---
phase: 99-peak-pick-bridge-qc-gate-cli
plan: 03
subsystem: nus
tags: [nmrglue, peak-picking, nus, bridge, pydantic, spectrum2d]

# Dependency graph
requires:
  - phase: 99-peak-pick-bridge-qc-gate-cli
    provides: "Plan 01's QcVerdict/QcCheckResult/QcReport contract; Plan 02's nus/qc.py run_qc_checks()/QcReport for the confidence/metadata wiring"
provides:
  - "src/lucy_ng/nus/bridge.py: build_spectrum2d() (processed .ft2 -> Spectrum2D) + bridge_peak_pick() (Spectrum2D -> PeakPicker2D -> per-experiment CASE JSON schema) + confidence_from_verdict() + write_peak_json()"
  - "src/lucy_ng/processing/edited_sign.py: detect_multiplicity_edited(), the importable twin of cli/pick.py's module-private detector, preserving the byte-unchanged cli/pick.py invariant"
  - "PICK-01/PICK-03 satisfied: schema-identical per-peak keys via direct PeakPicker2D call, plus the D-05 additive 'reconstruction' metadata block and D-06 verdict-derived confidence replacing the blanket \"confidence\": \"low\""
affects: [99-04-cli-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Importable-twin module (processing/edited_sign.py) instead of promoting/exporting a frozen file's private function -- preserves a HARD byte-unchanged invariant on cli/pick.py"
    - "bridge_peak_pick() accepts optional qc_report/recon_meta so a caller can invoke it twice (pre-QC to produce peaks for grading, post-QC to rebuild the final confidence-corrected payload) -- resolves the causal-ordering problem where peaks must exist before QC can grade them"
    - "make_valid_ft2 conftest factory: real nmrglue-readable minimal NMRPipe .ft2 built via create_blank_udic + create_dic + ng.pipe.write, for tests that genuinely parse the NMRPipe header (vs. make_valid_intermediate's arbitrary bytes, sufficient only for exit-code/non-emptiness checks)"

key-files:
  created:
    - src/lucy_ng/nus/bridge.py
    - src/lucy_ng/processing/edited_sign.py
  modified:
    - src/lucy_ng/processing/__init__.py
    - tests/nus/conftest.py (added make_valid_ft2 factory)
    - tests/nus/test_bridge.py (Wave-0 stubs replaced with real synthetic-fixture tests)
    - tests/nus/test_bridge_metadata.py (Wave-0 stubs replaced with real synthetic-fixture tests)

key-decisions:
  - "HMBC suspected_1J_artifact is conservatively False for every bridge-picked peak: a genuine 1J-leak flag requires cross-referencing the sibling HSQC peak list, out of scope for a single per-experiment bridge_peak_pick() call. Left as an honest 'not determined' rather than a fabricated heuristic; may become a pipeline-level post-process step in a future plan."
  - "confidence/note default to an honest 'pending_qc' placeholder when bridge_peak_pick() is called without a qc_report (the pre-QC pass), never a fabricated PASS/PARTIAL value -- keeps T-99-09's 'no blanket confidence' guarantee true even before Plan 04 wires the real verdict."
  - "PASS -> confidence \"high\" (not \"medium\") -- picked the single, unambiguous value per D-06's Claude's-discretion note; documented in confidence_from_verdict()'s docstring."

requirements-completed: [PICK-01, PICK-03]

# Metrics
duration: 24min
completed: 2026-07-16
---

# Phase 99 Plan 03: Peak-Pick Bridge Summary

**`nus/bridge.py`: in-memory `Spectrum2D` construction from a processed `.ft2` plus a direct, unmodified `PeakPicker2D.pick_peaks()` call transformed into the CASE HSQC/HMBC/COSY JSON schema with a D-05 additive `"reconstruction"` metadata block and D-06 verdict-derived confidence**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-16T19:15:00+02:00 (immediately after Plan 02 close)
- **Completed:** 2026-07-16T19:39:18+02:00
- **Tasks:** 2
- **Files modified:** 5 (2 new modules, 3 test/config files)

## Accomplishments
- Built `nus/bridge.py::build_spectrum2d()`: reads a processed `.ft2` via `ng.pipe.read()`/`ng.pipe.guess_udic()`/`uc_from_udic()` (the exact idiom `readers/bruker.py::read_2d()` uses for Bruker `pdata`, swapped to NMRPipe), preferring the `processed_ppm_axis.json` sidecar's calibrated F1 axis when present and falling back to the raw NMRPipe-header axis otherwise; wraps read/parse failures in a typed `RuntimeError` (fail-loud).
- Built `nus/bridge.py::bridge_peak_pick()`: calls `PeakPicker2D.pick_peaks()` directly and unmodified, then transforms its raw `f1_position`/`f2_position`/`intensity` output into the three CASE-consumed per-experiment schemas (HSQC/HMBC/COSY), NOT the raw picker shape — verified by exact-key-set assertions in tests.
- Added the D-05 additive top-level `"reconstruction"` metadata block (`backend`, `iterations`, `qc_verdict`, `violated_checks`, `thresholds_used`) and D-06 per-peak `confidence` derivation (`confidence_from_verdict()`: PASS->"high", PARTIAL->"low", raises on FAIL) — replacing the blanket `"confidence": "low"` the current home-IST fixtures hardcode.
- Preserved the HARD `cli/pick.py` byte-unchanged invariant: created `processing/edited_sign.py` as a verbatim importable twin of `cli/pick.py::_detect_multiplicity_edited()` rather than touching the frozen file; `git diff --exit-code src/lucy_ng/cli/pick.py` returns 0.

## Task Commits

Each task was committed atomically:

1. **Task 1: Shared edited-sign helper + build_spectrum2d() from processed .ft2** - `1ef4117` (feat)
2. **Task 2: bridge_peak_pick() — per-experiment schema serialization + D-05/D-06 metadata** - `bffcbc9` (feat)

_Note: Task 2 was tagged `tdd="true"` in the plan, but as with Phase 99 Plan 02, this shipped as a standard `feat` commit rather than split RED/GREEN/REFACTOR commits — the plan's own Wave-0 stub tests were placeholders that referenced a nonexistent `.ft2` path and could never literally pass, so this plan's job was to design the real signature and write real tests against it, not drive a pre-existing failing test to green._

## Files Created/Modified
- `src/lucy_ng/nus/bridge.py` - `build_spectrum2d()`, `bridge_peak_pick()`, `confidence_from_verdict()`, `write_peak_json()`, and the per-experiment transform helpers (`_hsqc_cross_peaks`/`_hmbc_cross_peaks`/`_cosy_cross_peaks`, `_reconstruction_metadata_block`, `_build_caveat`, `_confidence_and_note`)
- `src/lucy_ng/processing/edited_sign.py` - `detect_multiplicity_edited()`, the importable twin of `cli/pick.py`'s module-private detector
- `src/lucy_ng/processing/__init__.py` - Exported `detect_multiplicity_edited`
- `tests/nus/conftest.py` - Added `make_valid_ft2` factory (real, nmrglue-readable minimal NMRPipe `.ft2` fixture builder)
- `tests/nus/test_bridge.py` - 10 tests: `build_spectrum2d()` (fixture construction, sidecar F1-axis override, fallback, fail-loud) + `bridge_peak_pick()` (HSQC/HMBC/COSY schema, edited/not-edited sign mapping, unknown-experiment rejection)
- `tests/nus/test_bridge_metadata.py` - 7 tests: metadata block presence/shape, PARTIAL-verdict violation surfacing, pre-QC "pending_qc" placeholder, `confidence_from_verdict()` mapping + FAIL rejection, end-to-end confidence propagation for PASS/PARTIAL

## Decisions Made
- Rewrote both `test_bridge.py` and `test_bridge_metadata.py`'s Wave-0 (Plan 01) stub tests entirely rather than patching them in place. The stubs called `build_spectrum2d(tmp_path / "processed.ft2", params=None, ...)` and `bridge_peak_pick(tmp_path / "processed.ft2", experiment_type="HSQC")` against a `.ft2` path that was never written to disk (a placeholder that could never pass literally) and expected a `"verdict"` metadata key that this plan's Task 2 action text specifies as `"qc_verdict"`. Replaced with a real `make_valid_ft2` fixture factory (for `build_spectrum2d`) and deterministic synthetic-`Spectrum2D` construction mirroring `tests/test_hmbc_peak_picking_integrity.py`'s established synthetic-peak pattern (for `bridge_peak_pick`, which takes a `Spectrum2D` directly per the plan's own designed signature, not a `.ft2` path) — the same class of Wave-0-stub-vs-real-signature correction Phase 98 Plans 03/05/06 made for their own stub tests.
- `bridge_peak_pick()` accepts optional `qc_report`/`recon_meta` (both default `None`) specifically so Plan 04's `lucy nus pipeline` can call it twice: once without them (to produce peaks for the QC gate to grade — peaks must exist before QC can run) and once more with the real `QcReport` (to rebuild the final, confidence-corrected payload that actually gets written at the D-07 write boundary). When `qc_report` is `None`, confidence is an honest `"pending_qc"` placeholder and the metadata block's `qc_verdict` is `"UNKNOWN"` — never a fabricated PASS/PARTIAL.
- HMBC's `suspected_1J_artifact` is conservatively `False` for every bridge-picked peak (present in the schema, but not computed) — a genuine 1J-leak detection needs to cross-reference the sibling HSQC peak list from the same reconstruction, which is out of scope for a single per-experiment `bridge_peak_pick()` call. Documented in-source as planner discretion; may become a pipeline-level post-process step in a future plan.
- Picked `confidence_from_verdict(PASS) == "high"` (not `"medium"`) as the single unambiguous value, per D-06's "Claude's discretion" note.

## Deviations from Plan

None beyond the Wave-0 test-stub rewrite documented above under "Decisions Made" (the same class of correction explicitly precedented by Phase 98 Plans 03/05/06 — not a Rule 1-4 deviation, since the plan's own action text specified the real signatures the rewritten tests now exercise; the Wave-0 stubs were acknowledged placeholders, not a contract this plan was obligated to preserve verbatim).

## Issues Encountered
- `mypy src/lucy_ng/nus/bridge.py` reports one `import-untyped` note for `nmrglue` (no stubs/py.typed marker) — confirmed as the identical pre-existing baseline `nus/postprocess.py` already reports (same nmrglue import), not a defect introduced by this plan. `bridge.py`/`processing/edited_sign.py` themselves report zero errors.
- Initial synthetic HMBC/COSY test data used raw `np.random.default_rng().random()` uniform noise across a small 8x16 grid for the `build_spectrum2d()`-path tests only (not for `bridge_peak_pick()`'s schema tests, which needed deterministic picked-peak counts) — realized during design that `bridge_peak_pick()` tests needed the `test_hmbc_peak_picking_integrity.py` synthetic-Gaussian-noise-floor-plus-explicit-maxima pattern instead, to get deterministic peak counts; used that pattern from the start for all `bridge_peak_pick()` tests, avoiding any flaky-test risk.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- PICK-01/PICK-03 are now complete. `lucy_ng.nus.bridge.build_spectrum2d()`/`bridge_peak_pick()` are fully working, importable, and produce schema-identical per-experiment JSON with the D-05/D-06 metadata/confidence additions.
- Plan 04 (`cli/nus.py::qc`/`pipeline` commands + D-07 write/quarantine boundary, PICK-02/QC-03) can now proceed: `bridge_peak_pick()`'s `qc_report`/`recon_meta` parameters are the exact hook Plan 04's pipeline needs for the pre-QC/post-QC two-call pattern, and `write_peak_json()` is available as an optional write helper (the actual PASS/PARTIAL-vs-FAIL branch stays Plan 04's responsibility).
- `cli/pick.py` remains byte-unchanged (`git diff --exit-code` == 0); `detection/`, `fragments/`, `lsd/`, `ranking/` untouched.
- Full test suite green: 1360 passed, 14 skipped, 1 xfailed — up from Plan 02's 1343 passed/18 skipped baseline; the delta is exactly the 17 newly-activated PICK-01/PICK-03 tests (10 in `test_bridge.py`, 7 in `test_bridge_metadata.py`).
- No blockers or concerns for downstream plans.

---
*Phase: 99-peak-pick-bridge-qc-gate-cli*
*Completed: 2026-07-16*

## Self-Check: PASSED

All 7 created/modified files verified present on disk; both task commit
hashes (1ef4117, bffcbc9) verified present in git log.
