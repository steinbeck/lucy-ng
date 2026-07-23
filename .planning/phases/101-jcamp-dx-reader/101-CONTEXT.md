# Phase 101: JCAMP-DX Reader - Context

**Gathered:** 2026-07-23
**Status:** Ready for planning

<domain>
## Phase Boundary

A pure-Python JCAMP-DX reader that decodes both 1D (`Spectrum1D`) and 2D
(`Spectrum2D`) NTUPLES spectra into lucy-ng's **existing** spectrum models —
**no external binary** — closing the exact gap where nmrglue returns
`data=None` for 2D NTUPLES assembly. The 2D path decodes the DIFDUP-compressed
per-F1-row `##DATA TABLE=` pages into a full `(n_f1, n_f2)` matrix, and ppm
axes are **proven correct against ground truth, not eyeballed** (the milestone's
one real technical risk, WR-04 class).

Delivers requirements **JC-01, JC-02, JC-03, JC-04**.

**In scope:** `readers/jcamp.py` (+ a small vendored decode module), ppm-axis
derivation + verification, 1D/2D reader, one CI-runnable fixture test.

**Out of scope (belongs to later phases / other milestones):** the `lucy jcamp`
CLI, the `PeakPicker2D` bridge, and the QC gate (all Phase 102, reused
byte-unchanged); CASE convergence (Phase 103); NOESY *consumption* by the CASE
constraint model (deferred JC-F1 — NOESY is still *read* fine here); JCAMP
*writing* (JC-F3); non-JCAMP vendor formats (JC-F2).
</domain>

<decisions>
## Implementation Decisions

### ppm-axis derivation & verification (JC-02 — the crux risk)
- **D-01: Frequency source = in-file Bruker `##$` fields.** Both spectrometer
  frequencies are present in the `.dx` itself — F2 (¹H) from `##$SFO1` (`499.9216`,
  `##$BF1= 499.92`) and **F1 (¹³C) from `##$SFO2` (`125.7157`, `##$BF2= 125.705`)**.
  The reader is therefore **self-contained** — no gamma-ratio estimate, no
  dependency on the sibling 1D file. (The standard NTUPLES `##.OBSERVE FREQUENCY`
  carries only the direct-dimension ¹H frequency, so the indirect ¹³C frequency
  **must** come from `##$SFO2`/`##$BF2`.)
- **D-02: Axes are stored in Hz (`##UNITS= HZ`) → must be converted to ppm.**
  Worked evidence on the HSQC fixture: F2 `FIRST=3748.17 Hz / 499.92 ≈ 7.50 ppm`,
  `LAST=0 → 0 ppm` (plausible ¹H window); F1 `21997.14 / 125.71 ≈ 175 ppm …
  −616 / 125.71 ≈ −4.9 ppm` (plausible ¹³C window). Both axes reversed
  (descending ppm).
- **D-03: JC-02 verification = automatic cross-check vs 1D reference peaks.**
  Project the 2D onto each axis and match peak positions against the 1D ¹H and
  1D ¹³C `.dx` reference peaks (within tolerance) — proves calibration, not just
  gross Hz-vs-ppm errors.
- **D-04: The check lives in BOTH places.** The reader carries a **hard
  fail-loud range assertion** (rejects an absurd/ non-reversed / Hz-looking axis
  immediately, following the `nus/` fail-loud pattern); the **finer peak-match
  cross-check lives in the CI/validation test**.
- **⚠ Research flag (not a locked decision):** `SFO` (transmitter) vs the
  *referenced* `##$SF`/`SR` (processing reference) for the Hz→ppm divisor. The
  `##.SHIFT REFERENCE= INTERNAL, CDCl3` line implies a reference offset may
  apply. The researcher should confirm whether `FIRST/LAST` Hz are already
  referenced offsets (⇒ divide by `SF`) or raw transmitter offsets (⇒ `SFO`);
  the D-03 auto cross-check is the safety net that catches any residual SR shift.

### Decoder strategy (JC-04 — no dependency on nmrglue's private API)
- **D-05: Vendor the DIFDUP/SQZ/DUP/PAC line decoder** (~60 lines: `_parse_data`
  + `_parse_affn_pac` + the `_DIF_DIGITS`/`_DUP_DIGITS`/`_SQZ_DIGITS` tables)
  into a lucy-ng module (e.g. `readers/_jcampdx_decode.py`) **with BSD
  attribution** (nmrglue is New-BSD). Self-contained, CI-safe, satisfies JC-04
  literally. Chosen over wrapping the private funcs (violates JC-04 wording;
  nmrglue is `0.12-dev`) and over a from-scratch reimplementation (needless risk
  on a solved problem).
- **D-06: Header/metadata via nmrglue's *public* `ng.jcampdx.read()`.** It
  returns the full metadata dict (VAR_DIM, FIRST/LAST/FACTOR, `##$SFO*`, nucleus,
  pulse sequence) — it works, it just returns `data=None` for 2D. Only the
  **page-stacking + DIFDUP decode is lucy-ng's own**. Public API for the boring
  header parse; vendored kernel for the novel 2D assembly.

### CI fixture & correctness oracle (JC-04 — "verified means verified")
- **D-07: Fixture = a real 2D `.dx` trimmed to a few F1 pages** (~8–16 rows,
  full F2 width, NTUPLES/`VAR_DIM` header adjusted to match), committed at
  ~50–100 KB. Real Bruker DIFDUP pages, realistic assembly, no external binary.
- **D-08: Independent oracle, not circular.** Two-layer test:
  1. **Unit test with a hand-authored DIF/SQZ/DUP/PAC mini-vector** whose
     expected integers are computed **by hand from the JCAMP spec** — an oracle
     independent of our own decoder (catches an initial decode bug, which a
     frozen-golden-from-our-decoder would not).
  2. **Integration test on the trimmed real 2D** — asserts shape `(n_f1, n_f2)`,
     reversed ppm axes, and a few known peak coordinates.
  This directly applies the Phase-100 meta-lesson (mock-only "verified" gave
  false confidence).

### Reader API & experiment detection
- **D-09: `JcampReader` class with static `read_1d`/`read_2d` + a `read()`
  dispatcher** that branches on `##NUM DIM`. Mirrors the existing `BrukerReader`
  shape (readers/bruker.py) so Phase-102 CLI wiring is trivial and can target
  1D/2D explicitly.
- **D-10: Experiment type from `##.PULSE SEQUENCE` via the existing
  `_detect_experiment_type`** (bruker.py) — e.g. `hsqcedetgpsp.3 → HSQC`; it
  already handles hsqc/hmbc/cosy/noesy. Single source of truth, no new detection
  logic; not `##TITLE` (free-form) and not the filename (convention, not content).
- **D-11: 1D data path reuses nmrglue's public output.** For 1D,
  `ng.jcampdx.read()` already returns decoded data — use it directly; the
  vendored decoder covers **only** the 2D page assembly (nmrglue's actual gap).
  Minimal code, each path uses the strongest available tool. (JC-03's "same
  reader module" = same module/API, not necessarily the same decode path.)

### Claude's Discretion
- Stripping the caret nucleus prefix (`^1H`/`^13C` → `1H`/`13C`) to satisfy the
  `Spectrum2D`/`Spectrum1D` nucleus validators; solvent/metadata mapping into the
  existing `metadata` dict; exact module/file names; where the trimmed fixture is
  stored under `tests/`.
- No new optional extra is needed: **nmrglue is already a core dependency**
  (imported by `readers/bruker.py`), so the JCAMP reader adds no packaging surface.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — JC-01..04 definitions + Out-of-Scope table + JC-F1/F2/F3 deferred.
- `.planning/ROADMAP.md` § "Phase 101: JCAMP-DX Reader" — goal + 4 success criteria.

### Existing code to mirror / reuse (verified present)
- `src/lucy_ng/readers/bruker.py` — `BrukerReader` class shape (static `read_1d`/`read_2d`), `_detect_experiment_type()` (reuse for D-10), `_strip_brackets`/param helpers.
- `src/lucy_ng/models/spectrum.py` — `Spectrum1D` / `Spectrum2D` target models: fields, nucleus validator set `{1H,13C,15N,31P,19F,2H}`, experiment-type validator set `{HSQC,HMBC,COSY,TOCSY,NOESY,ROESY}`, `f1/f2_ppm_scale`, `to_dict`.
- `src/lucy_ng/nus/bridge.py` + `nus/qc.py` — the **Phase-99 downstream** the reader feeds (context only; reused unchanged in Phase 102).

### Vendored-decoder source (New-BSD, attribute)
- nmrglue `nmrglue.fileio.jcampdx` — `_parse_data`, `_parse_affn_pac`, `_DIF_DIGITS`, `_DUP_DIGITS`, `_SQZ_DIGITS` (installed at `/opt/miniconda3/lib/python3.12/site-packages/nmrglue/fileio/jcampdx.py`, nmrglue `0.12-dev`). Public entry `ng.jcampdx.read()` for the metadata dict (D-06).

### Test data (real, external — NOT committed; source for the trimmed fixture + JVAL)
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/` — 6 `.dx` (1H, 13C, HSQC, HMBC, COSY, NOESY; 2D grids 2048×2048) + `README.md` (decode-feasibility notes, provenance, mddnmr/IRLS audit trail).
- The HSQC NTUPLES block (verified): `VAR_DIM= 2048,2048,2048`, `UNITS= HZ,HZ,ARBITRARY UNITS`, `FACTOR= 11.047,1.831,1`, `FIRST= 21997.14,3748.17,-3615`, `LAST= -616.25,0,2771`, `.NUCLEUS= 13C,1H`, plus `##$SFO1/2`, `##$BF1/2`.

### Prior-milestone lessons (why these decisions)
- Memory `[[project_v100_nus_reconstruction]]` + `phases/100-.../VALIDATION.md` — the mock-only-verification lesson (→ D-08) and the WR-04 Hz-vs-ppm axis-error class (→ D-01..04).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`BrukerReader` (readers/bruker.py)** — API template for `JcampReader` (D-09); `_detect_experiment_type()` reused verbatim for D-10; `_strip_brackets` pattern for cleaning param strings.
- **`Spectrum1D`/`Spectrum2D` (models/spectrum.py)** — the exact target models; already carry `f1/f2_ppm_scale`, nucleus + experiment validators, `metadata`. Reader must emit stripped nuclei (`^1H`→`1H`) and a validator-accepted `experiment_type`.
- **nmrglue public `ng.jcampdx.read()`** — returns the metadata dict for 1D & 2D and full data for 1D; only 2D `data` is `None` (the gap this phase fills).
- **nmrglue private DIFDUP kernel** — ~60 lines, to be vendored (D-05).

### Established Patterns
- **Reader = thin wrapper over nmrglue** (project architecture: "thin tools around nmrglue/LSD/RDKit"). Keep the reader thin; only the 2D assembly is genuinely new.
- **Fail-loud** (`nus/run_stage`, constraint-hardness guard FIX-10) — informs the D-04 hard range assertion.
- **Real fixtures committed & CI-runnable** — the deliberate contrast to v10.0's uncommittable external SMILE binary.

### Integration Points
- Output `Spectrum2D`/`Spectrum1D` → (Phase 102) existing `PeakPicker2D` via the Phase-99 `build_spectrum2d`-style bridge → `analysis/nmr_peaks/*.json` → unchanged QC gate. This phase stops at producing correct spectrum models; it does not touch the bridge, picker, QC gate, or `case.md`.
</code_context>

<specifics>
## Specific Ideas

- The motivating file's HSQC header was read directly during discussion; the
  exact NTUPLES values above are the concrete anchor for the ppm math (D-01/D-02)
  and for constructing the trimmed fixture (D-07).
- `##DATA TABLE= (F2++(Y..Y)), PROFILE` with one `##PAGE= F1=<Hz>` per F1 row —
  2048 pages in the real HSQC; the fixture keeps only the first ~8–16.
- Per-page `##FIRST=` third value is the row's starting Y (DIF seed / check),
  not an axis field — do not confuse it with the axis `FIRST`.
</specifics>

<deferred>
## Deferred Ideas

- **NOESY consumption by the CASE constraint model** — the NOESY `.dx` reads
  fine here, but CASE does not yet use NOESY constraints (JC-F1, future milestone).
- **JCAMP writing / round-trip export** (JC-F3) and **other vendor formats**
  (Varian/JEOL native, nmrML — JC-F2) — explicitly out of scope this milestone.
- **RECON-F1** (hmsIST/mddnmr fallback for in-lucy-ng NUS self-reconstruction) —
  carried from v10.0; unrelated to reading already-reconstructed JCAMP here.

None of these belong in Phase 101 — discussion stayed within the reader scope.
</deferred>

---

*Phase: 101-jcamp-dx-reader*
*Context gathered: 2026-07-23*
