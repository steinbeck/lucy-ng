# Phase 102: CLI + Peak-Pick Bridge + QC Reuse - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-25
**Phase:** 102-cli-peak-pick-bridge-qc-reuse
**Areas discussed:** CLI form & inputs, 1D peak-picking scope, QC reference wiring, QC validation depth, unsupported-experiment handling

---

## CLI form

| Option | Description | Selected |
|--------|-------------|----------|
| Single command (full-chain) | One `lucy jcamp <dir-or-files>` runs read→pick→QC→write; dir + explicit files; standalone QC via existing `lucy nus qc` | ✓ |
| `lucy jcamp` group | Group with subcommands (pick/qc) analogous to `lucy nus`; duplicates existing QC | |

**User's choice:** Single command (full-chain).
**Notes:** JCAMP has no separable reconstruction stages; output schema identical to NUS path, so `lucy nus qc` already covers standalone QC — no `lucy jcamp qc` duplicate.

## Output location

| Option | Description | Selected |
|--------|-------------|----------|
| `<input-dir>/analysis/nmr_peaks/` | Default beside the .dx files, `--out` override; mirrors NUS `<expdir>/analysis/…` and CASE layout | ✓ |
| cwd / forced `--out` | No implicit location | |

**User's choice:** `<input-dir>/analysis/nmr_peaks/` with `--out` override.

## 1D scope

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — pick 1D via thin bridge | 1H/13C .dx → 13c_/1h_ lists via existing 1D picker (direct call, no new picker/shell-out); serves CASE input AND QC reference | ✓ |
| No — 2D only | Requires pre-existing 1D lists; QC would report insufficient_reference_data on pure JCAMP | |

**User's choice:** Yes — pick 1D via thin bridge.
**Notes:** Phase 99 shipped a 2D-only bridge; the 1D bridge is the one genuinely new picking helper. 1D output names must match the QC gate's keyword-glob (13c/1h).

## prot/quaternary source (QC)

| Option | Description | Selected |
|--------|-------------|----------|
| `detection/` fallback (1D 13C) | Existing non-circular fallback in the unchanged qc.py; no DEPT in dataset; no qc.py edit | ✓ |
| config/CLI override | Pass the 5 §8 quaternary shifts by hand; kept as escape-hatch only | |
| Use edited HSQC | Circular (classifies the spectrum it grades) — forbidden by Phase-99 D-03 | |

**User's choice:** `detection/` fallback (1D 13C).

## QC validation depth

| Option | Description | Selected |
|--------|-------------|----------|
| Wire + mechanical, green in 103 | Phase 102 shows QC runs and discriminates (verdict in JSON); full green-on-real-data is Phase 103 / JVAL | ✓ |
| Full green already in 102 | Drive real dataset to QC PASS now — pulls JVAL work forward | |

**User's choice:** Wire + mechanical; full green is Phase 103.

## Unsupported experiments

| Option | Description | Selected |
|--------|-------------|----------|
| Skip + warning | NOESY & non-{HSQC/HMBC/COSY/1H/13C}: read but not picked, visible warning, non-fatal | ✓ |
| Silent skip | Drop without notice | |
| Error/abort | Hard-fail on unsupported — too strict; expected NOESY would kill the run | |

**User's choice:** Skip + warning.

---

## Claude's Discretion

- Provenance semantics in the reused `reconstruction` metadata block for the JCAMP path (`backend="jcamp"` / external-mddnmr origin) + `caveat` text.
- Exact location/name of the new 1D-bridge helper module.
- `lucy jcamp` command module location + registration on the `lucy` group (mirror import-safe `cli/nus.py`).
- Mechanism for the `case.md` + 5-agent-team byte-unchanged diff test.

## Deferred Ideas

- NOESY consumption by the CASE constraint model (JC-F1) — future milestone.
- Full C20H32O2-jcamp green QC + CASE convergence — Phase 103 / JVAL.
- JCAMP writing / other vendor formats (JC-F3 / JC-F2) — out of scope.
- RECON-F1 (hmsIST/mddnmr NUS fallback) — carried from v10.0, unrelated here.
