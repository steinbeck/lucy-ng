# Phase 102: CLI + Peak-Pick Bridge + QC Reuse - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

One command — `lucy jcamp <dir-or-files>` — turns a JCAMP-DX directory (or an
explicit file list) into CASE-consumable, QC-graded peak lists by **reusing**
the Phase-99 bridge and the **byte-unchanged** Phase-99 QC gate. It reads each
`.dx` via the Phase-101 `JcampReader` into `Spectrum1D`/`Spectrum2D`, feeds the
2D spectra through the existing `nus/bridge.py::bridge_peak_pick(spectrum, …)`
seam (which takes a `Spectrum2D` directly, NMRPipe-independent) and the 1D
spectra through a thin 1D bridge over the existing 1D picker, writes the
existing `analysis/nmr_peaks/*.json` per-peak schema, and runs the unchanged QC
gate. Delivers requirements **JCLI-01, JCLI-02**.

**In scope:**
- Top-level `lucy jcamp` command (full chain: read → pick → QC → write; dir +
  explicit files; `--format json`).
- 2D peak-pick via the reused Phase-99 bridge (`bridge_peak_pick`); 1D peak-pick
  via a new thin 1D bridge (direct call to `processing/peak_picker.py`, no new
  picker, no shell-out).
- Wiring the **unchanged** QC gate over the JCAMP-derived peak lists; 1D outputs
  named so the gate's keyword-glob (`13c`/`1h`) discovers them as trusted
  reference.
- Edited-HSQC sign (+/−) preserved through the JCAMP round-trip (JCLI-02).

**Out of scope (later phases / other milestones):**
- Full green-on-real-data QC validation of `C20H32O2-jcamp` (QC PASS / §8) →
  **Phase 103 / JVAL** (D-05 boundary).
- CASE convergence on JCAMP peaks → **Phase 103 / JVAL-02**.
- NOESY *consumption* by the CASE constraint model (NOESY is still *read* fine;
  it is just not peak-picked here) → deferred **JC-F1**.
- Any change to `PeakPicker2D`, the 1D picker, `nus/qc.py`, `case.md`, or the
  5-agent team files — **reuse unchanged** (JCLI-02 / success criterion 4).
- Reconstruction / NUS internals (v10.0, PARTIAL) — this milestone consumes
  already-reconstructed JCAMP, it does not reconstruct.

</domain>

<decisions>
## Implementation Decisions

### CLI form & inputs (JCLI-01)
- **D-01 — Single top-level `lucy jcamp <dir-or-files>` command, full-chain.**
  Runs read → pick → QC → write in one invocation. Accepts a **directory**
  (auto-discover `*.dx`) *and* an **explicit file list**. `--format json` on the
  command. Chosen over a `lucy nus`-style subcommand group because JCAMP has no
  separable reconstruction stages — it is essentially one read+pick step + QC.
  Standalone QC needs **no new subcommand**: the output lands in the same
  `nmr_peaks` schema, so the existing `lucy nus qc <peaks-dir>` already covers
  it (no duplicate `lucy jcamp qc`).
- **D-02 — Output default `<input-dir>/analysis/nmr_peaks/`, with `--out <dir>`
  override.** Mirrors the NUS pattern (`<expdir>/analysis/…`) and matches the
  directory layout CASE expects in the data tree.

### 1D peak-picking in scope (JCLI-01)
- **D-03 — `lucy jcamp` peak-picks the 1D JCAMP files itself.** 1H/13C `.dx` →
  1D peak lists via a **new thin 1D bridge** — a direct in-memory call to the
  existing `processing/peak_picker.py` (the 1D `PeakPicker`), mirroring the
  Phase-99 `bridge_peak_pick` direct-call pattern (no new picker, no shell-out
  to `cli/pick.py`). 1D outputs are named so the QC gate's keyword-glob finds
  them (`13c_*` / `1h_*`). This makes the all-JCAMP dataset self-sufficient: the
  1D lists serve **both** as CASE input **and** as the QC gate's trusted 1D
  reference. (Phase 99 shipped a 2D-only bridge — the 1D bridge is the one
  genuinely new piece of picking glue here.)

### QC gate reuse & reference wiring (JCLI-02)
- **D-04 — prot/quaternary classification uses the QC gate's existing
  `detection/` fallback** (Phase-99 D-03), fed from the picked 1D-13C list.
  `C20H32O2-jcamp` has **no DEPT**, so the DEPT branch does not apply; the
  built-in multiplicity/hybridisation fallback is used. This is **non-circular**
  (it does NOT use the HSQC-under-test — Phase-99 D-03 forbids that) and requires
  **zero change to the byte-unchanged `qc.py`**. A config/CLI **known-quaternary
  override** (the 5 §8 shifts 142.0/135.86/79.35/36.23/37.86) is kept only as an
  escape-hatch, never the default.
- **D-05 — Phase-102 QC depth = wired + mechanically discriminating; full green
  is Phase 103.** Phase 102 must show the unchanged QC gate **runs** over the
  JCAMP peaks and **discriminates** (PASS/PARTIAL/FAIL reachable; verdict + soft
  violations surfaced in the peak-JSON metadata block). Driving the real
  `C20H32O2-jcamp` dataset to QC PASS / §8 quality is **Phase 103 / JVAL** — the
  phase boundary. Do not pull JVAL validation into 102.

### Unsupported experiments (directory run)
- **D-06 — NOESY & any non-{HSQC/HMBC/COSY/1H/13C} file: read but do not pick,
  skip with a visible warning, non-fatal.** The Phase-101 reader decodes NOESY
  fine, but `bridge_peak_pick` supports only HSQC/HMBC/COSY (raises otherwise);
  the command must catch/route around that, log **which files were skipped and
  why**, and still produce the consumable lists for the supported experiments.
  The expected NOESY `.dx` in the dataset (JC-F1 deferred) must not kill the run.

### Claude's Discretion
- Provenance semantics in the reused `reconstruction` metadata block for the
  JCAMP path (e.g. `backend="jcamp"` / external-mddnmr-TopSpin origin) and the
  `caveat` text — planner discretion within the stable per-peak schema.
- Exact location/name of the new 1D-bridge helper (whether it lives beside
  `nus/bridge.py`, in a new module, or under `readers/`) — note the function is
  generic, only the `nus/` package name is NUS-flavoured.
- Where the `lucy jcamp` command module lives and how it is registered on the
  `lucy` group (mirror the import-safe `cli/nus.py` registration pattern).
- The `case.md` + 5-agent-team **byte-unchanged** guarantee (JCLI-02 / criterion
  4) should be asserted by a diff-based test — planner picks the mechanism.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone planning
- `.planning/REQUIREMENTS.md` — JCLI-01, JCLI-02 (the two requirements this
  phase closes); Out-of-Scope table (no changes to PeakPicker2D / QC gate /
  `case.md`); JC-F1 (NOESY consumption) deferred.
- `.planning/ROADMAP.md` § "Phase 102: CLI + Peak-Pick Bridge + QC Reuse" — goal
  + 4 success criteria; § "Phase 103" for the JVAL boundary (D-05).

### Prior-phase context (decisions this phase builds on)
- `.planning/phases/101-jcamp-dx-reader/101-CONTEXT.md` — the `JcampReader` API
  (`read`/`read_1d`/`read_2d`, D-09), `_detect_experiment_type` reuse (D-10),
  ppm-axis + edited-sign correctness the bridge relies on.
- `.planning/phases/99-peak-pick-bridge-qc-gate-cli/99-CONTEXT.md` — the bridge +
  QC-gate decisions being reused: D-01/D-02 verdict semantics (PARTIAL passes,
  FAIL blocks; critical-vs-soft), **D-03 trusted-1D reference + non-circular
  prot/quaternary classification** (→ this phase's D-04), D-05 additive metadata
  block, D-07 write boundary.

### Existing code to reuse (verified present) — unchanged
- `src/lucy_ng/nus/bridge.py` — `bridge_peak_pick(spectrum: Spectrum2D, *,
  experiment, qc_report, recon_meta, threshold, snr_floor)` (the 2D reuse seam —
  takes a `Spectrum2D` directly, NMRPipe-independent), `write_peak_json`,
  `confidence_from_verdict`, the HSQC/HMBC/COSY serializers, and the
  `_VALID_BRIDGE_EXPERIMENTS = {HSQC, HMBC, COSY}` guard behind D-06.
- `src/lucy_ng/nus/qc.py` — the **byte-unchanged** QC gate: keyword-glob 1D
  reference discovery (`_glob_by_keyword` on `13c`/`1h`/`dept`), `_load_1d_shifts`,
  `detection/`-based prot/quaternary fallback, critical-vs-soft aggregation.
- `src/lucy_ng/readers/jcamp.py` — `JcampReader.read/read_1d/read_2d` (Phase 101).
- `src/lucy_ng/processing/peak_picker.py` — the existing **1D** `PeakPicker`
  (D-03 direct-call target); `src/lucy_ng/processing/peak_picker_2d.py` —
  `PeakPicker2D.pick_peaks()` (called via the bridge).
- `src/lucy_ng/cli/pick.py` — `pick 1d` (canonical 1D peak-list JSON shape the 1D
  bridge must match) and `_detect_multiplicity_edited`; **not** to be edited —
  the shared twin lives in `processing/edited_sign.py`.
- `src/lucy_ng/cli/nus.py` — import-safe `lucy nus` group + `lucy nus qc`
  (reused for standalone QC per D-01); registration pattern for the new
  `lucy jcamp` command.
- `src/lucy_ng/models/spectrum.py` — `Spectrum1D`/`Spectrum2D` produced by the
  reader and consumed by the bridge.

### Task brief + data (real, external — not committed; source for JVAL in 103)
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/` —
  6 `.dx` (1H, 13C, HSQC, HMBC, COSY, NOESY; 2D 2048×2048) + `README.md`.
- `.../C20H32O2/analysis/NUS-RECONSTRUCTION-GUIDE.md` **§8** (QC check
  definitions: ~17 protonated C, the 5 named quaternaries, clean edited signs,
  ridge-free HMBC, real aliphatic COSY) + **§10** (ground-truth 1D shifts) —
  the same authoritative source the unchanged QC gate encodes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`nus/bridge.py::bridge_peak_pick`** — the 2D reuse seam. Accepts a
  `Spectrum2D` directly, so the JCAMP `Spectrum2D` from `JcampReader.read_2d`
  plugs straight in; returns the full per-experiment payload (per-peak schema +
  additive `reconstruction` block). No new 2D picker (JCLI-01).
- **`nus/qc.py` (unchanged)** — discovers its trusted 1D reference by
  keyword-glob (`13c`/`1h`) in the peaks dir and classifies prot/quaternary via a
  `detection/` fallback when no DEPT exists — exactly the `C20H32O2-jcamp` case
  (D-04). No `qc.py` edit needed.
- **`processing/peak_picker.py` (1D)** — direct-call target for the new thin 1D
  bridge (D-03), mirroring the 2D bridge's direct-call idiom.
- **`JcampReader` (Phase 101)** — `read()` dispatches 1D/2D on `##NUM DIM`;
  edited-sign and ppm axes already correct, so the bridge inherits them.

### Established Patterns
- **Bridge = build model in memory → direct Python call to existing subsystem**
  (Phase-99 `bridge_peak_pick`; `_perform_ranking()` lineage) — extended to 1D
  here, never a subprocess/new picker.
- **Import-safe CLI registration** (`cli/nus.py`, `cli/webview.py`
  `_require_*_extra`) — the new `lucy jcamp` command follows it; nmrglue is
  already a core dep (no new extra, per Phase-101 D-11).
- **Fail-loud / non-fatal-skip split** — supported experiments picked, NOESY &
  unsupported skipped with a visible warning (D-06).
- **`case.md` untouched invariant** (Phase 98/99) — enforcement stays at the
  CLI/write boundary; no orchestrator-side change (JCLI-02 / criterion 4).

### Integration Points
- `JcampReader.read()` → `Spectrum2D` → `bridge_peak_pick` → `write_peak_json`
  → `<out>/analysis/nmr_peaks/{HSQC,HMBC,COSY}.json`.
- `JcampReader.read()` → `Spectrum1D` → 1D bridge → `<out>/analysis/nmr_peaks/`
  `13c_*`/`1h_*` (QC trusted reference **and** CASE 1D input).
- QC gate reads those peak lists (unchanged) → PASS/PARTIAL/FAIL → verdict +
  violations embedded in the peak JSON; standalone re-run via `lucy nus qc`.

</code_context>

<specifics>
## Specific Ideas

- The command is deliberately *thin*: all the hard work (2D DIFDUP assembly, ppm
  axes, edited sign, peak picking, QC checks) already exists — Phase 102 is
  glue + one 1D bridge, no new algorithms.
- Standalone QC intentionally rides the existing `lucy nus qc <peaks-dir>`
  rather than a duplicated `lucy jcamp qc`, because the output schema is
  identical across the NUS and JCAMP paths — one QC surface for both.
- The 1D lists are the linchpin of the whole QC-reuse story: without them the
  unchanged gate would report `insufficient_reference_data` on a pure-JCAMP
  dataset — hence D-03 makes 1D picking non-optional.

</specifics>

<deferred>
## Deferred Ideas

- **NOESY consumption by the CASE constraint model** (JC-F1) — NOESY reads and
  could be picked, but CASE has no NOESY constraint path yet; not this milestone.
- **Full C20H32O2-jcamp green QC + CASE convergence** — Phase 103 / JVAL-01/02
  (D-05 boundary), not 102.
- **JCAMP writing / other vendor formats** (JC-F3 / JC-F2) — out of scope this
  milestone.
- **RECON-F1** (hmsIST/mddnmr in-lucy-ng NUS fallback) — carried from v10.0;
  unrelated to reading already-reconstructed JCAMP here.

None — discussion stayed within phase scope (no todos surfaced for folding).

</deferred>

---

*Phase: 102-cli-peak-pick-bridge-qc-reuse*
*Context gathered: 2026-07-25*
