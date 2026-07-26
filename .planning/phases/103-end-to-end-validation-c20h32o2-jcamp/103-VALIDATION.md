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

### Step A — baseline / source-tree proof (Task 3)

`PYTHONPATH="$(pwd)/src" python -c "import lucy_ng.cli.jcamp as m; print(m.__file__)"` printed
`/Users/steinbeck/Dropbox/develop/lucy-ng/src/lucy_ng/cli/jcamp.py` (the worktree's own
source, not a stale editable install elsewhere). Base commit for this plan's work:
`08ad99a` (Phase-102 close) plus this plan's own Task 1/2 commits on top.

### Per-experiment knob values (D-02/D-03)

All 31 cells were computed via direct `bridge_peak_pick`/`bridge_peak_pick_1d` calls
against an in-memory `Spectrum2D`/`Spectrum1D` read once per experiment (RESEARCH.md
Pattern 2 — the bridge, not `PeakPicker2D.pick_peaks` directly, so `detect_negative` is
derived exactly as the governed CLI run derives it).

| Experiment | Mode | Value | Peak count | In target zone? | Note |
|---|---|---|---|---|---|
| HSQC | snr_floor | 1000 | 51 | no | above 17-40 zone |
| HSQC | snr_floor | 2000 | 50 | no | above 17-40 zone |
| HSQC | snr_floor | 3000 | 39 | yes | in zone, but see below: quaternary hit at both 36.23 AND 37.9 |
| HSQC | snr_floor | 4000 | 23 | yes | in zone, closest to §8's ~17-27 expectation; quaternary hit at 37.9 only |
| HSQC | snr_floor | 5000 | 11 | no | below zone, coverage collapses (6/16) |
| HSQC | threshold | 0.01 | 62 | no | above zone; quaternary hits at 36.23, 37.9, AND 79.29 |
| HSQC | threshold | 0.02 | 51 | no | above zone |
| HSQC | threshold | 0.05 | 46 | no | above zone |
| COSY | snr_floor | 800 | 364 | no | above 20-200 zone |
| COSY | snr_floor | 1500 | 346 | no | above zone |
| COSY | snr_floor | 3000 | 285 | no | above zone |
| COSY | snr_floor | 5000 | 185 | yes | in zone |
| COSY | snr_floor | 8000 | 77 | yes | in zone, plausible real aliphatic network size |
| COSY | threshold | 0.02 | 348 | no | above zone |
| COSY | threshold | 0.05 | 219 | no | just above zone |
| COSY | threshold | 0.10 | 64 | yes | in zone |
| HMBC | snr_floor | 500 | 138 | yes | in zone |
| HMBC | snr_floor | 1000 | 88 | yes | in zone |
| HMBC | snr_floor | 2000 | 59 | yes | in zone, plausible 2-3 bond correlation count over 20 carbons |
| HMBC | snr_floor | 3000 | 29 | no | just below 30-200 zone |
| HMBC | snr_floor | 5000 | 15 | no | below zone |
| HMBC | threshold | 0.01 | 106 | yes | in zone |
| HMBC | threshold | 0.02 | 78 | yes | in zone |
| HMBC | threshold | 0.05 | 22 | no | below zone |
| 13C | snr_floor | 5 | 45 | no | above 18-26 zone; includes real 79.35 but also ~25 extra baseline/solvent peaks |
| 13C | snr_floor | 10 | 35 | no | above zone; still includes real 79.35 |
| 13C | snr_floor | 20 | 24 | yes | in zone; still includes 79.35 but multiple CDCl3-triplet duplicates |
| 13C | snr_floor | 40 | 20 | yes | in zone, EXACT match to §10's 20-carbon count; 79.35 drops out at this floor (see note below) |
| 1H | snr_floor | 5 | 265 | n/a — no hard target | shipped default; plausible given real multiplet splitting |
| 1H | snr_floor | 10 | 209 | n/a | thinner |
| 1H | snr_floor | 20 | 165 | n/a | thinner still |

**31/31 cells logged** (5+3 HSQC, 5+3 COSY, 5+3 HMBC, 4 for 13C, 3 for 1H = 8+8+8+4+3 = 31).

**Chosen `(mode, value)` per experiment and reason:**

- **HSQC: `snr_floor=4000` (23 cross-peaks).** Closest in-zone cell to §8's ~17-27
  expected protonated-carbon count. **Important finding, recorded here in full because
  it drives the Task-4 D-07/D-10 decision below:** ALL EIGHT HSQC matrix cells — every
  `snr_floor` value (1000/2000/3000/4000/5000) and every `threshold` value
  (0.01/0.02/0.05) — show at least one HSQC correlation within ±0.5 ppm of the
  `quaternary_exclusion` check's compiled-in shift `37.86` ppm (observed nearest pick
  ≈37.90 ppm at every single cell). This is NOT a knob-tuning artifact of one cell; it is
  a persistent, knob-independent correlation. At `snr_floor=4000` the correlating proton
  is `h1_ppm≈1.571` ppm with a positive (`CH_or_CH3`) edited sign — i.e. it looks like a
  genuine protonated-carbon signal, not noise. §10 itself flags 37.86 as "possibly one
  angular C (**MEDIUM confidence**)" among the five compiled-in quaternaries — this real,
  reproducible cross-peak is independent evidence pointing the same direction as that
  MEDIUM-confidence caveat. The **D-03 knob matrix is exhausted for HSQC's
  `quaternary_exclusion` criterion specifically**: no cell in the pre-defined 8-cell row
  clears it, and per D-03/D-08 no new cell was invented and no peak was hand-edited to
  make it disappear.
- **COSY: `snr_floor=8000` (77 cross-peaks).** In-zone; a plausible real aliphatic
  network size (§8: "not just the OH ridge"), and this mode/value keeps COSY consistent
  with HSQC's `snr_floor` mode.
- **HMBC: `snr_floor=2000` (59 cross-peaks).** In-zone, plausible order-of-magnitude for
  2-3 bond correlations over 20 carbons.
- **13C: `snr_floor=40` (20 peaks) — EXACT count match to §10's 20-carbon list.** See the
  §10 cross-check table below: 17/20 matched within tolerance, with the 3 unmatched
  entries explained by real, verified acquisition-window/solvent facts (not a knob
  failure) — described under that table.
- **1H: bare default `snr_floor=5.0` (265 peaks).** No hard target zone is defined for 1H
  (RESEARCH.md); 265 peaks is plausible given genuine 1H multiplet splitting on a
  32-proton molecule and 1H is not itself graded by any critical QC check.

### Step C — the ONE governed `lucy jcamp` invocation (D-04)

Exact command, run once over the whole real dataset:

```
PYTHONPATH="$(pwd)/src" lucy jcamp ~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp \
  --snr-floor hsqc=4000 --snr-floor cosy=8000 --snr-floor hmbc=2000 --snr-floor 13c=40 --snr-floor 5.0 \
  --format json
```

Result: **exit code 1** (QC verdict FAIL). `failed: []` — **all six real `.dx` files were
read without a single read failure**, HMBC included (the Task-1 fix proven on the real
file, not just a probe). `skipped`: exactly one entry,
`{"file": "C20H32O2_NOESY.dx", "reason": "NOESY is not supported by the peak-pick bridge
(D-06: read, not picked)"}` — the D-06 skip working as designed. Nothing was written to
`analysis/nmr_peaks/`; the verdict-annotated payloads plus `qc_report.json` were
quarantined to `analysis/jcamp_ingest/qc_failed/` (D-07 write boundary held).

### QC verdict (D-06)

**Verdict: FAIL.**

| Check | Critical? | Passed? | Detail |
|---|---|---|---|
| `quaternary_exclusion` | yes | **NO** | `1 HSQC correlation(s) at quaternary shifts: [37.9]` |
| `ppm_calibration` | yes | yes | well-calibrated against `GUIDE_S10_C13` |
| `hsqc_coverage` | yes | **NO** | `11/16 protonated carbons covered (69%)` (floor 80%) |
| `signal_to_ridge` | yes | yes | no dominant ridge detected (value 0.186, floor 0.5) |
| `edited_sign_consistency` | no (soft) | yes | all carbons self-consistent |
| `cosy_diagonal_symmetry` | no (soft) | yes | 97% of COSY cross-peaks have a diagonal mirror |

`classification_source` = `"override"` (no DEPT file present — inherited, byte-frozen
behaviour per D-05, not a choice this phase made). `thresholds_used`: `c13_tol=0.5`,
`h1_tol=0.05`, `ridge_fraction_fail=0.5`, `hsqc_coverage_floor=0.8`,
`edited_sign_tol=0.5`, `cosy_symmetry_floor=0.5`.

**Two critical violations, both traced to the same root cause.** `hsqc_coverage`'s 16-carbon
denominator itself includes ONE spurious "protonated candidate" that can never be
covered: the picked 1D-13C list at `snr_floor=40` contains a CDCl3 solvent triplet
(76.78/77.03/77.28 ppm) that `_dedupe_shifts` collapses to a single candidate
representative (76.78) — this candidate is real solvent, not a compound carbon, so no
HSQC correlation will ever "cover" it. Combined with the 5 known-quaternary
exclusions (2 of which, 142.00/135.86, are not even physically present in this 1D-13C
file's acquisition window — see the §10 table below), the achievable coverage ceiling is
15/16 (93.75%) at best; the observed 11/16 (69%) is genuinely short of the 80% floor
regardless. `quaternary_exclusion`'s failure is the persistent 37.9 ppm hit described
above under "Chosen knobs" — present at every one of the 8 HSQC matrix cells.

**The full `qc_report.json`, in the verdict-derived quarantine location** (external, not
committed): `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/analysis/jcamp_ingest/qc_failed/qc_report.json`.
Per Task 5's own explicit anticipation of this exact scenario ("If Task 3's run ended in a
FAIL verdict and therefore wrote no consumable peaks, do not fabricate a fixture"), this
report is **not** copied into `tests/fixtures/jcamp/known_good_peaks/` — that path is
reserved for a genuine PASS/PARTIAL positive fixture, and copying a FAIL report there
would mislabel the directory. This is logged as an explicit, honest resolution of a
plan-literal contradiction (Task 3's acceptance criteria assume the file exists at that
path unconditionally; Task 5's action text explicitly overrides this for the FAIL case) —
see "Plan-literal note" at the end of this section.

### §10 ground-truth cross-check table (D-05)

Picked 1D-¹³C list (`13C.json`, `snr_floor=40`, 20 peaks), tolerance = the gate's own
`c13_tol = 0.5` ppm (taken from `thresholds_used`, not invented separately):

| §10 ppm | nearest picked 13C ppm | Δ ppm | matched? |
|---|---|---|---|
| 142.00 | 77.28 | -64.72 | no |
| 135.86 | 77.28 | -58.58 | no |
| 79.35 | 77.28 | -2.07 | no |
| 69.06 | 69.06 | +0.00 | yes |
| 67.06 | 67.06 | -0.00 | yes |
| 51.63 | 51.63 | -0.00 | yes |
| 37.86 | 37.86 | -0.00 | yes |
| 37.19 | 37.19 | -0.00 | yes |
| 36.23 | 36.23 | +0.00 | yes |
| 35.23 | 35.23 | +0.00 | yes |
| 34.21 | 34.21 | -0.00 | yes |
| 33.67 | 33.67 | -0.00 | yes |
| 30.66 | 30.66 | +0.00 | yes |
| 29.77 | 29.77 | +0.00 | yes |
| 27.93 | 27.93 | +0.00 | yes |
| 27.15 | 27.16 | +0.01 | yes |
| 25.96 | 25.96 | +0.00 | yes |
| 23.43 | 23.43 | -0.00 | yes |
| 22.63 | 22.64 | +0.01 | yes |
| 21.78 | 21.78 | +0.00 | yes |

**matched 17/20 within ±0.5 ppm.**

**The 3 unmatched entries are explained, not hand-waved:**
- **142.00 and 135.86 ppm (the two olefinic quaternaries) are NOT PRESENT in this real
  1D-13C JCAMP file at any swept `snr_floor` (5/10/20/40) — verified directly: this
  file's own ppm axis only spans `[-10.14, 110.14]` ppm** (checked via
  `JcampReader.read(...).ppm_scale.min()/.max()`), i.e. the acquisition window physically
  does not cover the olefinic region at all. This is a genuine acquisition-coverage fact
  about the real `C20H32O2_13C.dx` file, not a peak-picking knob failure — no `snr_floor`
  or `threshold` value could ever recover these two shifts from this file.
- **79.35 ppm (the Cq-O quaternary) IS present in the raw spectrum at low `snr_floor`
  (verified present at 5/10/20) but drops below the `snr_floor=40` cutoff** chosen for its
  exact 20-peak count match to §10. This is a genuine, documented D-03 tuning trade-off,
  not an error.
- The **residual "no §10 counterpart" picks are exactly the CDCl3 solvent triplet**
  (76.7763, 77.0305, 77.2847 ppm — the classic CDCl3 residual-solvent multiplet centred
  ≈77.16 ppm) — a real, expected chromatographic/solvent artifact, not a compound carbon.
  `PeakPicker2D`/the 1D picker have no solvent-exclusion logic (out of scope, D-01 rejects
  a post-pick filter), so this artifact survives at every swept `snr_floor` (5 through
  100, verified) and is documented here rather than filtered.

### §8 HSQC-correlation count (D-05b)

From `HSQC.json` (`snr_floor=4000`, chosen cell):
- **Total HSQC cross-peaks: 23.**
- **Distinct `c13_ppm` values (rounded to 0.1 ppm): 17** — matching §8's "~17 protonated
  carbons" expectation almost exactly. (One of the 17 distinct rounded values is a
  near-zero artifact at `c13_ppm≈0.02`, `h1_ppm≈0.02` ppm — a baseline/DC-offset pick, not
  a real carbon; recorded here, not silently dropped from the count.)
- **Per-quaternary 1-bond-correlation check** (tolerance ±0.5 ppm):
  - 142.00 ppm: **0** correlations — clean (no leak).
  - 135.86 ppm: **0** correlations — clean (no leak).
  - 79.35 ppm: **0** correlations — clean (no leak).
  - 36.23 ppm: **0** correlations — clean (no leak).
  - 37.86 ppm: **1** correlation (13C≈37.90, 1H≈1.571 ppm, positive/`CH_or_CH3` sign) —
    **the persistent hit driving the `quaternary_exclusion` FAIL**, discussed above. Four
    of the five compiled-in quaternaries show a genuinely clean absence of correlation;
    only the one §10 itself calls MEDIUM-confidence shows a hit.

### Connectivity summary (for the D-07 chemist gate)

From `COSY.json` (`snr_floor=8000`, 77 total cross-peaks):
- Off-diagonal H-H pairs: **50**.
- Off-diagonal pairs excluding the 5.32 ppm OH ridge (±0.1 ppm on either proton): **50**
  (identical — none of the 50 off-diagonal pairs involve the OH ridge at this knob
  setting) — a real aliphatic coupling network, not merely the OH ridge (§8's explicit
  criterion).

From `HMBC.json` (`snr_floor=2000`, 59 total cross-peaks):
- Correlations originating from the gem-dimethyl methyl protons (~0.964/0.990 ppm,
  ±0.03 ppm): **7**, reaching 13C shifts 135.83, 69.14, 51.59, 35.21, 34.27, 29.83, 27.95
  ppm. **None of the 7 reach 36.23 ppm** (the quaternary the gem-dimethyl pair is
  attached to) — plausible chemically as a weak/absent 2-bond correlation with visible
  3-bond correlations to neighbouring ring carbons instead, but recorded as observed
  fact, not interpreted further (that judgement belongs to the Task-4 chemist gate).
- Ridge indicator (largest number of HMBC cross-peaks sharing one F1/13C value, rounded
  to 0.1 ppm): **135.8 ppm with 8 F2 partners** — a reasonable number of long-range
  correlations from an olefinic quaternary carbon, not the "hundreds sharing one F1
  value" signature of a true t1-ridge artifact.

### External known-bad list checksums (D-11 proof of non-modification)

Pre- and post-run `shasum` of `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/analysis/nmr_peaks/*.json` are IDENTICAL:

```
3c8fafb92c0fe98c7cec5b0a503aa70d99de874e  13C_exp6_narrow.json
0b5a9eef3d157fcac8e8681f0a939ddc5226e128  13C_exp7_wide.json
26d640fc0f5fb83841962d4577f30fcc7ccf9453  1H_exp1.json
5a34d930be15ece94f8327ff1f1952b2b8fdb4c8  COSY_exp2.json
0ced28311c4f456cdde1d0cc645a175e7325f3fd  HMBC_exp4.json
7d6b9c40d7af942d7c8fd3d40bd14cbfcbdde2c7  HSQC_exp3.json
d18c91ffbe9cf446ded359c0f6ca3e6ae32cfa51  NOESY_exp5.json
```

`git status --porcelain tests/fixtures/nus/` is empty (verified before and after the
governed run).

### Plan-literal note (deviation, T-103-hazard "literal acceptance criteria vs. prose")

Task 3's acceptance criteria include `test -f tests/fixtures/jcamp/known_good_peaks/qc_report.json`
unconditionally. Task 5's own action text explicitly anticipates a FAIL outcome ("If Task
3's run ended in a FAIL verdict... do not fabricate a fixture... leave this task's
artifacts uncreated"). Since the governed run's verdict IS FAIL, writing the FAIL
`qc_report.json` into a directory literally named `known_good_peaks` would mislabel it as
a positive fixture. Resolution: the full report is captured and quoted verbatim above
(and remains on disk at the external quarantine path); `tests/fixtures/jcamp/known_good_peaks/`
is left uncreated per Task 5's explicit, more specific instruction, which takes
precedence over Task 3's generic literal path check. This is exactly the plan's own
carried-forward hazard ("Literal `grep -c … == N` acceptance criteria recurrently
contradict a plan's own prose").

### Chemist verdict (D-07)
*TBD — verbatim, with reasoning*

### CASE outcome (D-15) + model actually used (D-13.4)
*TBD*

### Deviations logged under D-09

**1. `src/lucy_ng/readers/jcamp.py` — widened `_PPM_PLAUSIBILITY_BOUNDS["13C"]` upper bound `230.0` → `250.0` (Task 1).**
- **Genuine defect blocking JVAL-01/02:** `JcampReader.read_2d()` on the real
  `C20H32O2_HMBC.dx` raised `ValueError: Implausible 13C ppm axis: [-4.57, 234.81]
  outside expected [-15.0, 230.0]` — the real HMBC file could not be read AT ALL
  without this fix, blocking every downstream step (D-03 matrix, QC gate, §10
  table, CASE handoff).
- **Root cause:** the real HMBC acquisition uses a legitimately wider 13C sweep
  than HSQC (`$OFFSET=234.8062` ppm, SW ≈ 30091 Hz at `SF=125.705` MHz) — a real,
  physically sensible window, not a units/divisor bug. The old `230.0` ceiling was
  simply too tight for this real experiment's parameter choice.
- **Fix:** changed exactly one literal, `_PPM_PLAUSIBILITY_BOUNDS["13C"]` from
  `(-15.0, 230.0)` to `(-15.0, 250.0)`. Nothing else in `_assert_plausible_ppm_axis`,
  `_ppm_scale`, or `_resolve_dim` was touched.
- **Measured axis endpoints (proof the fix is correct, not just "stops raising"):**
  read `C20H32O2_HMBC.dx` with `PYTHONPATH="$(pwd)/src"` — shape `(1024, 2048)`,
  F1 (13C) `234.80619999997373` → `-4.572275227432982` ppm, F2 (1H)
  `7.050608` → `-0.4469294966244597` ppm. This F1 axis brackets the full §10 13C
  range (21.78–142.00 ppm) with wide margin on both sides (per RESEARCH.md Open
  Question #3).
- **The guard remains meaningful, not "raised until it stops complaining":** still
  rejects a >250 ppm axis (`[260.0, 0.0]`) and a raw-Hz axis (the real HMBC
  `FIRST`/`LAST` values `29516.31`/`-574.76` left undivided by SF — the "forgot to
  divide by SF" bug class this guard exists to catch). Both negative controls are
  now pinned in `tests/readers/test_jcamp.py::test_read_2d_ppm_axis_assertion`.
- **Explicitly NOT covered by this guard** (per its own docstring, unchanged):
  the ~0.447 ppm SFO-vs-SF divisor error stays inside these bounds by design —
  that remains the JC-02 1D cross-check's job (Task 3 Step E's §10 table), not
  this coarse net's.
- **Files:** `src/lucy_ng/readers/jcamp.py` (1 constant + comment), `tests/readers/test_jcamp.py`
  (4 new assertions in the existing test).

**2. `src/lucy_ng/cli/jcamp.py` — additive per-experiment `--threshold`/`--snr-floor` `KEY=value` CLI wiring (D-01/D-04, Task 2).**
- **No new picking logic added** — `bridge_peak_pick` (2D) and `bridge_peak_pick_1d`
  (1D) already accepted both `threshold` and `snr_floor`; only `--snr-floor`
  (bare, single global value) was reachable from the CLI. This wiring exposes the
  already-existing tuning surface so the D-03 knob matrix (Task 3) can be run
  through the real governed CLI invocation, not just direct bridge calls.
- **Additive/backwards-compatible:** the plain `--snr-floor 5.0` form is unchanged;
  omitting the option still yields the shipped default (5.0) for every experiment.
- **Files:** `src/lucy_ng/cli/jcamp.py` (new `_parse_keyed_option` helper, option
  block, four bridge call sites), `tests/test_cli_jcamp.py` (new test class).

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
