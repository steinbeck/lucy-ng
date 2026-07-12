# Plan 94-04 Summary — Manual Browser Checkpoint

**Plan:** 94-04 (checkpoint:human-verify, blocking)
**Status:** APPROVED
**Date:** 2026-07-09
**Requirements:** TBL-01, TBL-02, TBL-03

## Outcome

Human browser verification of the Phase 94 Tables tab: **APPROVED** by the user.

Verified against a schema-conformant fixture-backed `analysis_dir` (hand-authored to the
locked CONTEXT.md peaks/*.json schema + a multi-iteration `compound.lsd` set including a
family-suffixed `iteration_02_anchor_recovery`), served via
`lucy webview serve <dir> --open`. All 5 `/api/tables/*` endpoints independently
smoke-tested green (HTTP 200, `state="ok"`) before the browser check; HMBC payload
carried all three flag values (`ok`/`potential_4J`/`1J_artifact`); `/constraints`
selected the highest numeric iteration.

## Verified behaviours (the visual/CSS surface Python cannot assert)

- [x] Five sections present in order: ¹³C Signals · HSQC · HMBC · COSY · LSD Constraint Inventory
- [x] HMBC rows colour-coded by flag (ok = normal/green accent, potential_4J = amber
      `#fff3cd`, 1J_artifact = dimmed/grey); no rows hidden
- [x] Per-table captions (note + counts) above each of the 4 peaks tables
- [x] Compact intensity rendering (`5.6M` / `1.5M` / `445.2K`, not raw integers)
- [x] TBL-03 three-subsection structured layout (Applied Constraints / Constraint Summary
      with Ring exclusion Yes/No / Deferred-Pending reasoning)

## Defects

None reported — approved as-is.

## Known, intentional (not a defect)

- TBL-03 "Applied Constraints" **Note column is intentionally empty**: the LSD inventory
  schema's `applied_from_detection` is a flat narrative list with no per-row index back to
  a specific BOND/HMBC/COSY-equiv constraint, so no heuristic mapping was guessed
  (documented in 94-03-SUMMARY under Decisions Made). Acknowledged by the user.

## Self-Check: PASSED
