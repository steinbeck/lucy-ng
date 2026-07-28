# Requirements: lucy-ng — v10.1 JCAMP-DX 2D Ingestion

**Defined:** 2026-07-21
**Core Value:** An AI agent can autonomously determine the structure of an unknown organic compound from its NMR spectra. v10.1 adds a **binary-free ingestion path**: lucy-ng reads already-reconstructed 1D/2D spectra from **JCAMP-DX** and produces the same consumable CASE peak lists, so CASE can run on NUS (or any) data reconstructed anywhere — decoupling CASE from the v10.0 SMILE self-reconstruction blocker.

**Relationship to v10.0 (locked):** JCAMP ingestion is a **complementary input path, not a replacement** for v10.0's NUS self-reconstruction (which remains PARTIAL — PORT shipped, VAL blocked by SMILE's memory abort, RECON-F1 tracked). It reuses the entire downstream Phase-99 pipeline (`Spectrum2D` → `PeakPicker2D` → `analysis/nmr_peaks/*.json` → QC gate → CASE) unchanged. Motivating dataset: `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/` (6 `.dx` files, 2D grids 2048×2048), reconstructed in TopSpin via `mddnmr` compressed sensing (IRLS).

## Milestone v10.1 Requirements

### JCAMP-DX reader (JC)

- [x] **JC-01**: `lucy` reads a 2D JCAMP-DX NTUPLES file (HSQC/HMBC/COSY) into the existing `Spectrum2D` model — decoding the DIFDUP-compressed per-F1-row `##DATA TABLE=` pages into a full `(n_f1, n_f2)` intensity matrix — with **no external binary**.
- [x] **JC-02**: The 2D `Spectrum2D` carries correct **reversed ppm axes** on both dimensions, derived from the NTUPLES metadata (`VAR_DIM`, `FIRST`/`LAST`/`FACTOR`, `.NUCLEUS`, `.OBSERVE FREQUENCY`) and **cross-checked against the trusted 1D reference / §10 ground-truth shifts** — explicitly guarding the WR-04-class Hz-vs-ppm axis error.
- [x] **JC-03**: `lucy` reads a 1D JCAMP-DX file (¹H, ¹³C) into the existing `Spectrum1D` model through the same reader module.
- [x] **JC-04**: A JCAMP-DX line decoder (DIFDUP/SQZ/PAC) is available to the reader **without depending on nmrglue's private API** (vendored or wrapped behind a stable internal interface), and is covered by a committed, **CI-runnable** unit test on a small real JCAMP fixture — no external binary, so "verified" means verified (addresses the Phase-100 mock-only-verification learning).

### CLI & peak-pick bridge (JCLI)

- [x] **JCLI-01**: `lucy jcamp <dir-or-files>` runs the full chain (read JCAMP → `Spectrum2D`/`Spectrum1D` → existing `PeakPicker2D` → `analysis/nmr_peaks/*.json` in the existing per-peak schema), reusing the Phase-99 bridge pattern (`build_spectrum2d`-style direct call, **not** a new picker); every subcommand supports `--format json`.
- [x] **JCLI-02**: JCAMP-derived peak lists pass through the **unchanged Phase-99 QC gate** (PASS/PARTIAL/FAIL), the edited-HSQC sign (+/−) is preserved so multiplicity derivation still works, and `case.md` + the 5-agent team stay byte-unchanged.

### End-to-end validation (JVAL)

- [ ] **JVAL-01**: The `C20H32O2-jcamp` dataset is read, peak-picked, and QC-graded to §8-quality peak lists (QC PASS, or soft-only PARTIAL + a brief chemist confirmation) — the first real spectra to clear the gate in this project.
- [ ] **JVAL-02**: A fresh `/lucy-ng:case C20H32O2` on the JCAMP-derived peak lists converges on a finite, rankable solution set — the milestone's actual success bar (proving the connectivity from externally-reconstructed spectra is usable for CASE).

## Future Requirements

Acknowledged but deferred — not in this milestone's roadmap.

- **JC-F1**: JCAMP-DX for additional experiment types beyond HSQC/HMBC/COSY/1D (e.g. NOESY-driven constraints, DEPT). The `C20H32O2-jcamp` NOESY `.dx` is present but not consumed by the current CASE constraint model.
- **JC-F2**: Generalized vendor-format ingestion (Varian/JEOL native, nmrML) behind the same reader abstraction.
- **JC-F3**: JCAMP-DX **writing** / round-trip export of lucy-ng spectra.
- **RECON-F1** (carried from v10.0): hmsIST / mddnmr CLI fallback backend for in-lucy-ng NUS self-reconstruction — the tracked path to close v10.0's VAL. Note the v10.1 JCAMP data was itself produced by `mddnmr`, so this remains the natural next reconstruction step.
- **JVAL-F2** (tracked, Phase 103 honest partial close): real-data recalibration of the 2D
  noise/threshold model and/or the QC gate's quaternary-override mechanism for
  CS-reconstructed matrices. On the real `C20H32O2-jcamp` HSQC file, every cell of the
  pre-defined D-03 knob matrix (all 5 `snr_floor` and all 3 `threshold` values) shows a
  persistent, knob-independent HSQC correlation at ~37.9 ppm within tolerance of the QC
  gate's compiled-in quaternary shift 37.86 ppm — a shift §10 itself flags as only
  MEDIUM-confidence — so `quaternary_exclusion` cannot be cleared by any value in the
  matrix. Closing this needs either (a) a genuinely different picker/noise-model
  calibration for real CS/IRLS-reconstructed matrices (the `_compute_2d_noise_sigma`
  ~15x dynamic-range gap already flagged in 103-RESEARCH.md), or (b) a mechanism for the
  QC gate's `known_quaternary_shifts` override to express confidence tiers instead of a
  hard boolean list — both require edits to files byte-frozen in Phase 103
  (`nus/qc.py`, `PeakPicker2D`). Evidence: `phases/103-.../103-VALIDATION.md`.
- **JVAL-F3** (tracked, Phase 103 honest partial close, additional to JVAL-F2 not instead
  of it): re-export **exp7 (wide, `$SW=160.372937567397` ppm, `$OFFSET=160.1929` ppm)**
  from the raw Bruker tree as JCAMP-DX into the `C20H32O2-jcamp` dataset, alongside the
  existing exp6 ("narrow") 1D-13C file. A read-only diagnostic (103-VALIDATION.md §10
  table) confirmed the real `C20H32O2_13C.dx` file included in this dataset is exp6
  ("narrow", `$SW=120.283311386233` ppm, `$OFFSET=110.1447` ppm), whose window
  (`[-10.14, 110.14]` ppm) physically cannot cover the two olefinic quaternaries
  (142.00/135.86 ppm) — those exist in the raw Bruker tree's exp7 ("wide"), which was
  never converted to JCAMP-DX for this dataset. **Honest limit of this step:**
  re-exporting exp7 would complete the §10 1D-13C coverage but would **NOT** fix
  `quaternary_exclusion`'s FAIL — the persistent, knob-independent HSQC correlation at
  ~37.9 ppm (tracked by JVAL-F2) sits well inside exp6's own narrow window and is
  entirely independent of which 1D-13C reference file is present. A PASS verdict is
  therefore NOT guaranteed by this step alone. Evidence: `phases/103-.../103-VALIDATION.md`.
- **CR-02** (Phase-102 defect, rediscovered by Phase 103's code review; NOT fixed by
  Phase 103): `lucy jcamp`'s STEP 2.5 (`src/lucy_ng/cli/jcamp.py:299-306`) purges the
  `--out` target's closed set of peak-list filenames (`HSQC.json`/`HMBC.json`/
  `COSY.json`/`1H.json`/`13C.json`) *before* STEP 3 reads a single input file. A run
  that fails on malformed input (or discovers nothing supported) exits non-zero,
  writes nothing to `--out`, and still destroys any pre-existing peak lists at that
  path -- including a prior `lucy nus pipeline` PASS-graded result, since the two
  commands write the identical filenames/schema. Fix: move the `out_root` half of the
  purge to after the "nothing staged" bail-out (STEP 4), so it only runs once a verdict
  is about to be produced. Introduced in Phase 102 (commit `f6de196`), not Phase 103;
  filed here because Phase 103's review (`103-REVIEW.md` CR-02) is where it was found.
  Evidence: `phases/103-.../103-REVIEW.md`.
- **CR-03** (Phase-102 defect, rediscovered by Phase 103's code review; NOT fixed by
  Phase 103): `lucy jcamp`'s derived `work_root = out_root.parent / "jcamp_ingest"`
  (`src/lucy_ng/cli/jcamp.py:273`) is unvalidated against the caller-supplied `--out`.
  If `--out` is itself named (or ends in) `jcamp_ingest`, `work_root == out_root`, and
  STEP 2.5's `shutil.rmtree(work_root, ignore_errors=True)`
  (`src/lucy_ng/cli/jcamp.py:299`) deletes the entire user-specified output directory,
  including files this command never wrote. Fix: fail loud (`click.BadParameter`) on
  the collision before any deletion, per `103-REVIEW.md`'s suggested fix. Introduced in
  Phase 102 (commit `f6de196`), not Phase 103; filed here because Phase 103's review
  (`103-REVIEW.md` CR-03) is where it was found. Evidence: `phases/103-.../103-REVIEW.md`.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| NUS self-reconstruction inside lucy-ng | That is v10.0 (PARTIAL) / RECON-F1. v10.1 consumes spectra reconstructed elsewhere; it does not reconstruct. |
| JCAMP-DX writing / export | Read-only ingestion this milestone (see JC-F3). |
| 3D / nD JCAMP | 2D + 1D only; the CASE model consumes 2D correlations + 1D shifts. |
| Non-JCAMP vendor formats (Varian/JEOL native, nmrML) | JCAMP-DX is the one interchange format in scope now (see JC-F2). |
| Changes to `PeakPicker2D`, the QC gate, or `case.md` | Reuse the unchanged Phase-99 downstream; v10.1 only adds a new front-end reader + bridge. |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| JC-01 | Phase 101 | Complete |
| JC-02 | Phase 101 | Complete |
| JC-03 | Phase 101 | Complete |
| JC-04 | Phase 101 | Complete |
| JCLI-01 | Phase 102 | Complete |
| JCLI-02 | Phase 102 | Complete |
| JVAL-01 | Phase 103 | Partial (closed 2026-07-28, honest partial close — see JVAL-F2/JVAL-F3) |
| JVAL-02 | Phase 103 | Partial (closed 2026-07-28, not attempted — no consumable peaks) |

**Coverage:**
- v10.1 requirements: 8 total
- Mapped to phases: 8/8 ✓ (roadmap created 2026-07-21)
</content>
