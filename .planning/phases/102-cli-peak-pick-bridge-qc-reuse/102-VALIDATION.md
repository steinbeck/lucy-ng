---
phase: 102
slug: cli-peak-pick-bridge-qc-reuse
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-25
updated: 2026-07-25
---

# Phase 102 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Quick run command** | `pytest tests/readers/test_jcamp.py tests/test_jcamp_1d_bridge.py tests/test_cli_jcamp.py tests/test_skill_files_unchanged.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~15 s quick · ~180 s full suite (1408 tests at Phase-101 close) |

Static gates (CLAUDE.md, run alongside the suite):
- `mypy src/lucy_ng` (strict mode — every new module must pass)
- `ruff check src tests`

Reused-module drift gate (run at the end of every plan; `22f2b52` is the
Phase-101-close code baseline, verified identical to current HEAD for these
paths):
```
git diff --exit-code 22f2b52 -- \
  .claude/ src/lucy_ng/nus/ src/lucy_ng/cli/pick.py \
  src/lucy_ng/processing/peak_picker.py src/lucy_ng/processing/peak_picker_2d.py
```

---

## Sampling Rate

- **After every task commit:** run the quick command above
- **After every plan wave:** `pytest -q` plus `mypy src/lucy_ng` plus the drift gate
- **Before `/gsd-verify-work`:** full suite green, zero regressions vs. the
  1408-test Phase-101 baseline
- **Max feedback latency:** 15 seconds (quick), 180 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 102-01-T1 | 102-01 | 1 | JCLI-01 | T-102-01, T-102-03 | Header-consistency assertions (`VAR_DIM` vs page/row counts, `$NUC1`/`$SF`/`$OFFSET` lengths) stay intact; fixture generator fails loud on a missing source file | integration (fixture generation + reader) | `python tests/fixtures/jcamp/_generate_fixture.py && git diff --exit-code -- tests/fixtures/jcamp/C20H32O2_HSQC_trimmed.dx && pytest tests/readers/test_jcamp.py -q` | ❌ 3 new `.dx` fixtures | ⬜ pending |
| 102-01-T2 | 102-01 | 1 | JCLI-01 | T-102-01, T-102-02 | Ambiguity `ValueError` remains the default; the positional path is reachable only via an explicit caller hint and is proven on the heteronuclear fixture | unit | `pytest tests/readers/test_jcamp.py -q && mypy src/lucy_ng && ruff check src tests` | ✅ extends `tests/readers/test_jcamp.py` | ⬜ pending |
| 102-02-T1 | 102-02 | 1 | JCLI-01, JCLI-02 | T-102-04, T-102-12 | Zero-magnitude guard prevents a degenerate 1D file from raising/NaN-poisoning; `peak_json_filename` allow-lists `{1H, 13C}` so no unexpected nucleus lands in the QC-graded directory | unit (source + smoke) | `mypy src/lucy_ng && ruff check src tests && python -c "from lucy_ng.processing import bridge_peak_pick_1d, peak_json_filename"` | ❌ `src/lucy_ng/processing/jcamp_1d_bridge.py` | ⬜ pending |
| 102-02-T2 | 102-02 | 1 | JCLI-01, JCLI-02 | T-102-05, T-102-12 | Un-mocked `QcReferenceData.resolve()` proves real discovery; a negative-control test pins the silent-failure mode of the wrong (2D) schema | unit + integration | `pytest tests/test_jcamp_1d_bridge.py -q` | ❌ new file | ⬜ pending |
| 102-03-T1 | 102-03 | 2 | JCLI-01, JCLI-02 | T-102-06, T-102-07, T-102-08, T-102-12, T-102-13 | `Path(...).resolve()` on every user path; per-file try/except so one bad file never aborts the batch nor passes as clean; `out_root` not created before the verdict; work root outside `out_root` | static + import-safety smoke | `mypy src/lucy_ng && ruff check src tests && python -c "import sys, lucy_ng.cli.jcamp; assert 'lucy_ng.nus.qc' not in sys.modules"` | ❌ `src/lucy_ng/cli/jcamp.py` | ⬜ pending |
| 102-03-T2 | 102-03 | 2 | JCLI-01 | T-102-06 | Argument validation rejects nonexistent paths, an empty directory, and a directory mixed with explicit files — each with a non-zero exit and no `analysis/` side effects | integration (CLI, `CliRunner`) | `pytest tests/test_cli_jcamp.py tests/test_cli_main.py -q` | ❌ new file | ⬜ pending |
| 102-04-T1 | 102-04 | 3 | JCLI-01, JCLI-02 | T-102-07, T-102-08, T-102-14 | FAIL verdict never writes consumable peaks (quarantine + non-zero exit); a malformed `.dx` forces a non-zero exit even under a forced PASS; each test class states its proof level | integration (CLI over committed fixtures; verdict monkeypatched only in the discrimination class) | `pytest tests/test_cli_jcamp.py -q && test -z "$(git status --porcelain tests/fixtures/jcamp/)"` | ⚠️ extends the 102-03 file | ⬜ pending |
| 102-04-T2 | 102-04 | 3 | JCLI-02 | T-102-10, T-102-11 | SHA-256 freeze of `case.md` + the five `lucy-*.md` agent files, plus a roster-completeness glob that also catches a newly added agent file | unit (golden-hash, cwd-independent) | `pytest tests/test_skill_files_unchanged.py -q && git diff --exit-code 22f2b52 -- .claude/` | ❌ new file | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

There is no separate RED-stub wave in this phase (`tdd_mode` is off). Every task
creates the test file its own `<automated>` command runs, so Nyquist coverage
holds task-by-task. The Wave-0 gaps identified in 102-RESEARCH.md map to plans
as follows:

- [x] Homonuclear-2D fixture coverage → **102-01-T1** commits real trimmed COSY,
      HMBC and NOESY `.dx` fixtures (16 F1 pages each), so the `_resolve_dim` fix
      and the D-06 skip path are proven on data, not on mocks
- [x] `tests/readers/test_jcamp.py` homonuclear extension → **102-01-T2**
- [x] 1D-bridge schema + QC-discovery tests → **102-02-T2**
      (`tests/test_jcamp_1d_bridge.py`)
- [x] `lucy jcamp` CLI tests → **102-03-T2** (surface/import safety) and
      **102-04-T1** (fixture-backed end-to-end), both in `tests/test_cli_jcamp.py`
- [x] Byte-unchanged skill-file guard → **102-04-T2**
      (`tests/test_skill_files_unchanged.py`)

*Existing infrastructure otherwise covers the phase: `tests/readers/test_jcamp.py`
(Phase-101 real committed fixtures), `tests/nus/test_bridge.py` /
`test_bridge_metadata.py` (Phase-99 2D bridge), `tests/nus/test_qc_checks.py` /
`test_qc_regression.py` (unchanged QC gate), `tests/nus/test_write_boundary.py`
(the D-07 assertion shape).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `lucy jcamp` end-to-end on the real 6-file `C20H32O2-jcamp` dataset | JCLI-01 | The dataset lives outside the repo (`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/`, four 2D files at 1024–2048 F1 rows, ~55 MB total) and is deliberately not committed | Run `lucy jcamp <that dir> --format json`; confirm HSQC/HMBC/COSY + `13C.json`/`1H.json` are written (or quarantined), NOESY appears in `skipped` with a reason, `failed` is empty, and a QC verdict is embedded in each 2D payload's `reconstruction` block. **Grading that verdict green (§8 quality) is Phase 103 / JVAL — out of scope here (D-05).** |
| Peak-count plausibility and SNR-floor behaviour on a full 2048×2048 matrix | JCLI-01 | `_compute_2d_noise_sigma`'s global MAD is computed over a 16-row sample in the committed fixtures, which is not representative of the real matrix (102-RESEARCH.md Pitfall 6) | Compare picked cross-peak counts from the real dataset against §8's expectations (~17 protonated carbons, ridge-free HMBC, a real aliphatic COSY network). **Phase 103 / JVAL-01.** |
| Discriminating a homonuclear F1/F2 positional swap on real data | JCLI-01 | Physically impossible with this dataset: both homonuclear dimensions share `$SF = 499.92` and their `$OFFSET` values differ by only 0.000938 ppm (~0.47 Hz), so a swap is numerically negligible and cannot be detected downstream | The discriminating evidence is instead the heteronuclear convention proof on the committed HSQC fixture (102-01-T2, `test_heteronuclear_positional_convention_holds`). Record this limitation verbatim in `102-01-SUMMARY.md`; do not claim the COSY cross-checks prove the ordering. |
| Chemical correctness of the QC verdict on JCAMP-derived peaks | JVAL-01 | Requires a chemist's judgement on a soft-PARTIAL result against §8/§10 ground truth | **Phase 103 / JVAL-01** — explicitly out of scope for Phase 102, whose bar (D-05) is only that the gate runs and discriminates. |

---

## Proof-Level Ledger (honesty gate)

Every phase claim must be filed under exactly one of these. `/gsd-verify-phase`
and the SUMMARYs must use the same wording.

| Level | What it covers in Phase 102 |
|-------|------------------------------|
| **FIXTURE-COVERED (real committed data)** | Homonuclear COSY/NOESY reading; the heteronuclear positional-convention proof; the COSY diagonal and 1H-reference cross-checks; 1D bridge schema and un-mocked QC discovery; file discovery and 1D/2D routing; the D-06 NOESY skip; QC-gate execution and verdict embedding; the edited-HSQC sign round-trip (both `CH2` and `CH_or_CH3` hints, zero ambiguous) |
| **SYNTHETIC** | 1D negative-lobe detection and the threshold/`snr_floor` reporting branches (no committed 1D fixture exercises them) |
| **MOCK-COVERED (real peaks, injected verdict)** | The PASS and PARTIAL write branches, and the malformed-file non-zero-exit rule under a forced PASS |
| **NOT PROVEN — Phase 103 / JVAL** | Peak-count plausibility, full-matrix SNR behaviour, §8-quality green verdict, CASE convergence, and any claim that a verdict is chemically correct |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (mapped to plans above)
- [x] No watch-mode flags
- [x] Feedback latency < 180s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned 2026-07-25 by gsd-planner
</content>
