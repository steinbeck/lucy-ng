# Phase 97: Backend Integration + Params/Schedule - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 97-backend-integration-params-schedule
**Areas discussed:** `lucy nus check` depth, CLI surface in Phase 97, Test-fixture strategy, NusAcquisitionParams scope

---

## `lucy nus check` depth

| Option | Description | Selected |
|--------|-------------|----------|
| Backend detection + sourced hint | SMILE tools on PATH (LSD style); distinguishes "installed but env not sourced" from "not installed"; platform preflight stays Phase 100 | ✓ |
| Backend detection only | Minimal PATH check; all hints + preflight to Phase 100 | |
| Full preflight in 97 | Also Apple-Silicon arch/Rosetta + csh checks; pulls PORT-01 forward | |

**User's choice:** Backend detection + sourced hint.
**Notes:** Keeps the PORT-01 portability boundary in Phase 100 clean while giving high-value UX (the "sourced vs not installed" distinction is cheap).

---

## CLI surface in Phase 97

| Option | Description | Selected |
|--------|-------------|----------|
| Only implemented commands | `lucy nus check/params/schedule`; reconstruct/pipeline added when they work; no dead command | ✓ |
| Full group with stubs | reconstruct/pipeline registered but exit "coming in Phase 98/99" | |

**User's choice:** Only implemented commands.
**Notes:** No misleading "not implemented" commands in intermediate state; Click groups extend trivially.

---

## Test-fixture strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata into tests/fixtures/nus/ | Copy acqus/acqu2s/nuslist of the 3 experiments (small text files); self-contained CI; ser not needed | ✓ |
| Reference external data dir | Tests read from ~/Dropbox/.../C20H32O2; not CI-portable, skip without data | |

**User's choice:** Metadata into tests/fixtures/nus/.
**Notes:** Params/schedule parsing reads only text metadata; large `ser` stays out (matters only for Phase 98 reconstruction fixtures). No compound identity in these files.

---

## NusAcquisitionParams scope

| Option | Description | Selected |
|--------|-------------|----------|
| Superset incl. ppm calibration | Also SF/OFFSET/SW/nucleus per dim that Phase-98 processing needs; parse once | ✓ |
| Minimal (NUS-02 only) | Only conversion params; Phase 98 adds ppm calibration itself | |

**User's choice:** Superset incl. ppm calibration.
**Notes:** Cheap now, avoids a second parse pass in Phase 98 (RECON-02 reversed ppm axis).

---

## Claude's Discretion

- Param-helper reuse mechanism (underscore-import vs promote to shared module) — reuse, don't duplicate.
- `NusBackend` protocol shape (Protocol vs ABC), registry API names, `models/nus.py` field naming/validators.
- Whether `[nus]` extra is created empty-but-present now or when the first pip dep appears (core CLI dependency-free is the invariant).

## Deferred Ideas

- Full platform preflight (arch/Rosetta, csh matrix) → Phase 100 / PORT-01.
- `lucy nus reconstruct` / `pipeline` bodies → Phases 98/99.
- `ser`-based reconstruction fixtures → Phase 98.
- Pending todos CASE4-azulene-regiochemistry (0.6) + ranking-tests-hosegen (0.2) reviewed, not folded (unrelated to NUS param/schedule).
