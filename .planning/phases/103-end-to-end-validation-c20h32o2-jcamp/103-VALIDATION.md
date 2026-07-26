---
phase: 103
slug: end-to-end-validation-c20h32o2-jcamp
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-26
---

# Phase 103 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `103-RESEARCH.md` § Validation Architecture.
> **Note:** this is a *proof* phase — two of its five requirement rows are
> MANUAL-ONLY by nature (real 55 MB dataset outside the repo; interactive CASE
> run). Those are satisfied by recorded evidence in this file, exactly as
> Phase 100's VAL-01/VAL-02 rows were.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Quick run command** | `pytest tests/readers/test_jcamp.py tests/test_jcamp_1d_bridge.py tests/test_cli_jcamp.py tests/test_skill_files_unchanged.py -q` |
| **Full suite command** | `pytest -q` (1408 passing at Phase-102 close) |
| **Estimated runtime** | quick ~10 s · full ~3–4 min |

Static gates (CLAUDE.md, run alongside the suite): `mypy src/lucy_ng` (strict),
`ruff check src tests`.

**Byte-freeze drift gate (D-09):** `case.md` + the five `lucy-*.md` agent files
must stay byte-identical (`tests/test_skill_files_unchanged.py`). `nus/qc.py`,
`PeakPicker2D` and the 1D picker must also stay byte-identical this phase — only
`readers/jcamp.py` and `cli/jcamp.py` are this phase's own touched source files.

---

## Sampling Rate

- **After every task commit:** Run the quick run command above
- **After every plan wave:** Run the full suite + `mypy src/lucy_ng` + the byte-freeze drift gate
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds (quick), ~240 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD — filled by gsd-planner | | | JVAL-01 / JVAL-02 | — | N/A | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → evidence level (from RESEARCH.md)

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| JVAL-01 (CLI knob wiring, D-01/D-04) | `--threshold`/`--snr-floor` accept both bare and `key=value` forms; plain `--snr-floor 5.0` stays backwards-compatible | unit + CLI-surface | `pytest tests/test_cli_jcamp.py -q` |
| JVAL-01 (D-09 reader fix) | Widened 13C ppm plausibility bound lets the real HMBC read without weakening the guard against genuinely-wrong axes | unit | `pytest tests/readers/test_jcamp.py -q` |
| JVAL-01 (real-data run) | Real `C20H32O2-jcamp`, tuned per-experiment knobs, QC PASS or soft-only PARTIAL | **MANUAL-ONLY** | N/A — dataset (~55 MB) lives outside the repo |
| JVAL-01 (positive fixture, D-11.4) | Accepted real peak lists committed as a **known-good** fixture, distinct from the known-bad QC-02 floor | automated once committed | new regression test mirroring `tests/nus/test_qc_regression.py` |
| JVAL-02 (CASE convergence) | Fresh `/lucy-ng:case C20H32O2` converges (LSD terminates, finite rankable set) | **MANUAL-ONLY** | N/A — interactive, human-started agentic run (D-14) |

---

## Wave 0 Requirements

- [ ] Boundary test near the widened `_PPM_PLAUSIBILITY_BOUNDS["13C"]` — an axis at ~235 ppm passes, a genuinely-wrong axis (e.g. computed from SFO instead of SF) still fails — covers the D-09 reader fix
- [ ] `tests/test_cli_jcamp.py` extension for the new `key=value` option parsing (keyed form, bare form, unrecognised-key error)
- [ ] Known-good peak fixture directory + regression test mirroring `tests/nus/test_qc_regression.py` (name/location = planner discretion per D-11)

*Existing infrastructure otherwise covers this phase: `tests/readers/test_jcamp.py`,
`tests/test_jcamp_1d_bridge.py`, `tests/test_cli_jcamp.py`,
`tests/test_skill_files_unchanged.py` (Phase 101/102, unaffected except where
explicitly extended above).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-dataset ingestion reaches §8 quality + QC PASS / soft-only PARTIAL | JVAL-01 | The six real `.dx` files (~55 MB) live outside the repo and cannot be committed; §8/§10 grading needs the external ground-truth guide | Run `lucy jcamp` with the per-experiment knobs recorded in this file; record every D-03 matrix cell's outcome, the §10 cross-check table, and the QC verdict |
| Soft-PARTIAL chemist confirmation | JVAL-01 | Requires a human chemist's judgement (D-07) | Executor stops, presents violated soft checks + §10 table + COSY/HMBC connectivity summary; the user's verdict **and reasoning** are recorded verbatim below |
| CASE convergence on JCAMP-derived peaks | JVAL-02 | Interactive, human-started, multi-hour agentic run in a fresh session (D-14) | User starts `/lucy-ng:case` in the jcamp directory in a fresh session and reports back; result + model actually used recorded below |

---

## Evidence (filled during execution)

### Per-experiment knob values (D-02/D-03)
*TBD — every matrix cell logged, not just the winner*

### §10 ground-truth cross-check table (D-05)
*TBD — picked 1D-¹³C shifts vs. §10, per-signal deviation; HSQC correlation count vs. §8's ~17 protonated carbons*

### QC verdict (D-06)
*TBD — verdict + violated checks + full `qc_report.json` reference*

### Chemist verdict (D-07)
*TBD — verbatim, with reasoning*

### CASE outcome (D-15) + model actually used (D-13.4)
*TBD*

### Deviations logged under D-09
*TBD — every reader/bridge/CLI fix, so a proof phase does not silently become a development phase*

---

## Proof-Level Ledger

Extends Phase 102's. Phase 103's job is to move the four
**NOT PROVEN — Phase 103 / JVAL** rows of `102-VALIDATION.md` into a real-data level.

| Level | Claim |
|-------|-------|
| REAL-DATA | *TBD during execution* |
| FIXTURE-COVERED | *TBD* |
| NOT PROVEN | *TBD — anything the D-03 budget did not reach, per the D-10 honest-partial-close rule, with a named tracked next step* |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a Wave 0 dependency, or are listed under Manual-Only above
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 240 s
- [ ] Byte-freeze drift gate green (`tests/test_skill_files_unchanged.py`)
- [ ] Known-bad QC-02 fixtures under `.../C20H32O2/analysis/nmr_peaks/` untouched (D-11)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
