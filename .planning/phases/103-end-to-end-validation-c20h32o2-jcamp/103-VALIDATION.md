---
phase: 103
slug: end-to-end-validation-c20h32o2-jcamp
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-26
updated: 2026-07-26
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
| 103-01-T1 | 103-01 | 1 | JVAL-01 | T-103-03 | Widened `13C` ppm bound still rejects a >250 ppm axis AND a raw-Hz axis, so the fail-loud guard is narrowed, not removed; frozen-file drift gate green | unit | `PYTHONPATH="$(pwd)/src" pytest tests/readers/test_jcamp.py -q && mypy src/lucy_ng && ruff check src tests` | ⚠️ extends `tests/readers/test_jcamp.py` | ⬜ pending |
| 103-01-T2 | 103-01 | 1 | JVAL-01 | T-103-01, T-103-03 | Unrecognized experiment key / non-float value / same-experiment threshold+snr_floor all exit non-zero (never silently ignored); `run_qc_checks` still called exactly once; CR-01 clearing not regressed | unit + CLI-surface (`CliRunner(mix_stderr=False)`) | `PYTHONPATH="$(pwd)/src" pytest tests/test_cli_jcamp.py -q && test "$(grep -c 'run_qc_checks(staged_dir)' src/lucy_ng/cli/jcamp.py)" = "1"` | ⚠️ extends `tests/test_cli_jcamp.py` | ⬜ pending |
| 103-01-T3 | 103-01 | 1 | JVAL-01 | T-103-02, T-103-06 | Nothing written into the sibling Bruker tree or `tests/fixtures/nus/`; external known-bad lists checksummed pre/post; single governed CLI invocation | **MANUAL-ONLY** real-data run + artefact assertion | `test "$(grep -cE '^\| (HSQC\|COSY\|HMBC\|13C\|1H) \| (snr_floor\|threshold) \|' .planning/phases/103-end-to-end-validation-c20h32o2-jcamp/103-VALIDATION.md)" -ge 31 && test -z "$(git status --porcelain tests/fixtures/nus/)"` | ⚠️ writes this file's Evidence sections | ⬜ pending |
| 103-01-T4 | 103-01 | 1 | JVAL-01 | T-103-06 | No peak list hand-edited toward §10 (mtime listing recorded); `nus/qc.py` byte-unchanged; a FAIL/exhausted budget recorded as NOT achieved with a named next step | **MANUAL-ONLY** (blocking chemist checkpoint, D-07) | N/A — `<human-check>`; `git diff --exit-code 08ad99a -- src/lucy_ng/nus/qc.py` | N/A | ⬜ pending |
| 103-01-T5 | 103-01 | 1 | JVAL-01 | T-103-02 | New known-good fixture is physically distinct from the known-bad floors and never overwrites them; test asserts PASS-or-PARTIAL **and** zero critical violations, so it cannot silently degrade | integration (real committed peaks) | `PYTHONPATH="$(pwd)/src" pytest tests/test_jcamp_qc_regression.py tests/nus/test_qc_regression.py -q && test -z "$(git status --porcelain tests/fixtures/nus/)"` | ❌ new `tests/test_jcamp_qc_regression.py` + `tests/fixtures/jcamp/known_good_peaks/` | ⬜ pending |
| 103-01-T6 | 103-01 | 1 | JVAL-02 | T-103-03, T-103-04 | All four D-13 blind safeguards recorded as performed; `case.md` + 5 agent files byte-unchanged; `README.md` restored unconditionally | **MANUAL-ONLY** (blocking handoff checkpoint, D-14) | N/A — `<human-check>`; `git diff --exit-code 08ad99a -- .claude/ && pytest tests/test_skill_files_unchanged.py -q` | N/A | ⬜ pending |

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

There is no separate RED-stub wave (`tdd_mode` is off). Every code-producing task in
`103-01-PLAN.md` creates or extends the test its own `<automated>` command runs, so
Nyquist coverage holds task-by-task. The three RESEARCH.md Wave-0 gaps map as follows:

- [x] Boundary test near the widened `_PPM_PLAUSIBILITY_BOUNDS["13C"]` → **103-01-T1**.
      **Planner correction:** RESEARCH.md's suggested negative control ("an axis computed
      from SFO instead of SF still fails") is NOT achievable — `_assert_plausible_ppm_axis`'s
      own docstring records that the SFO-divisor error is only ~0.447 ppm and stays inside
      these bounds by design; that bug is the JC-02 1D cross-check's job. The negative
      controls that genuinely hold are a >250 ppm axis and a raw-**Hz** axis (the real HMBC
      `FIRST`/`LAST` values 29516.31/-574.76 — the "forgot to divide by SF" class). The test
      must not overclaim.
- [x] `tests/test_cli_jcamp.py` extension for the new `KEY=value` option parsing (keyed,
      bare, keyed-beats-bare, case-insensitive key, unrecognised-key error, non-float value,
      same-experiment threshold+snr_floor ambiguity, `run_qc_checks` call-count 1) → **103-01-T2**
- [x] Known-good peak fixture + regression test mirroring `tests/nus/test_qc_regression.py`
      → **103-01-T5**, at `tests/fixtures/jcamp/known_good_peaks/` +
      `tests/test_jcamp_qc_regression.py` (module-level fixture, no new conftest — only one
      test file needs it). Asserts PASS-**or**-PARTIAL plus zero critical violations, since
      D-06/D-07 make a soft-only PARTIAL a valid positive outcome.

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
