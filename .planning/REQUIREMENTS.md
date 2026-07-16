# Requirements: lucy-ng — v10.0 Automatic NUS 2D Reconstruction

**Defined:** 2026-07-12
**Core Value:** An AI agent can autonomously determine the structure of an unknown organic compound from its NMR spectra — which requires reliable 2D connectivity, so NUS (non-uniformly-sampled) 2D data must be reconstructed with a real, validated method, fully automatically.

**Backend decision (locked):** NMRPipe + SMILE as the primary reconstruction backend (native macOS Apple Silicon + Linux, 100% CLI/headless, best literature-validated). Windows is an accepted, documented portability gap (WSL2/VM workaround). The `NusBackend` protocol keeps the architecture backend-agnostic so hmsIST/mddnmr fallbacks or a later NMRFx pivot are additive, not a rewrite. See `.planning/research/SUMMARY.md` § Backend Decision.

## Milestone v10.0 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase (see Traceability).

### Backend & Bruker conversion (NUS)

- [x] **NUS-01**: `lucy nus check` detects the reconstruction backend (NMRPipe + SMILE) on PATH and fails loud with install guidance when it is missing — mirroring `lucy lsd check`; the backend is a runtime-detected external tool, never a core `pyproject.toml` dependency.
- [x] **NUS-02**: Bruker acquisition parameters needed for conversion (SFO1, SW_h, TD per dimension, FnMODE, GRPDLY/DECIM, byte order/dtype) are extracted from `acqus`/`acqu2s` into a validated Pydantic model, read per-experiment and never hard-coded.
- [x] **NUS-03**: The reconstruction sampling schedule is built from the Bruker `nuslist` with correct 0-based indexing and acquisition-order preservation (never sorted/regenerated); a hard-fail assertion `n_sampled == len(nuslist)` is derived from FnMODE (QF == TD vs echo-antiecho == TD/2) before any conversion runs.
- [x] **NUS-04**: `lucy nus params` and `lucy nus schedule` expose the parsed parameters and schedule as JSON (`--format json`), validated against the real C20H32O2 exp2/exp3/exp4 fixtures.
- [x] **NUS-05**: Core `lucy` CLI stays dependency-free; any genuinely pip-installable pieces (e.g. QC-plot deps) live behind an optional `[nus]` extra with lazy imports, following the `[webview]` precedent.

### Reconstruction & processing (RECON)

- [x] **RECON-01**: `lucy nus reconstruct <expdir>` runs the full backend chain fully automatically with no GUI step — Bruker→NMRPipe conversion (`bruk2pipe`), NUS expansion (`nusExpand.tcl`), SMILE reconstruction of the indirect (t1) dimension.
- [x] **RECON-02**: Post-reconstruction processing (apodization, zero-fill, FT, phase correction, baseline) runs with direct-dimension-first (F2 before F1) ordering enforced as a hard pipeline gate, on reversed ppm axes calibrated to match the reliable 1D reference.
- [x] **RECON-03**: Reconstruction/processing is FnMODE-aware, correctly handling both echo-antiecho phase-sensitive (HSQC/HMBC) and QF magnitude-mode (COSY) experiments from one pipeline, at both 25% and 33% sampling densities.
- [x] **RECON-04**: Every external-tool invocation runs through a fail-loud subprocess wrapper that checks both exit code and output-file non-emptiness — csh-piped NMRPipe stages do not reliably propagate failures, so a truncated/empty intermediate must never pass silently.
- [x] **RECON-05**: Reconstruction knobs (iteration count, threshold, virtual-echo toggle) are exposed via CLI flags with sane defaults; the stopping criterion is convergence/residual-based, not a fixed iteration count alone.

### Quality gate (QC)

- [x] **QC-01**: An automated QC gate cross-checks every reconstructed correlation against the trusted 1D shift data (protonated-carbon HSQC coverage, quaternary-carbon exclusion, edited-sign self-consistency, COSY diagonal symmetry, ppm calibration, signal-to-ridge ratio) and emits a machine-readable PASS/PARTIAL/FAIL report — no human in the loop.
- [x] **QC-02**: The QC gate reports FAIL on the existing known-bad t1-ridge home-IST peak lists (regression floor) and PASS on a clean reconstruction — proving it discriminates.
- [x] **QC-03**: The CASE handoff refuses to start when the QC gate reports FAIL, extending the v9.0 constraint-hardness guard (FIX-10) to reconstruction-derived peaks so a fabricated cross-peak can never silently become a hard LSD constraint.

### Peak-pick bridge & CLI (PICK)

- [x] **PICK-01**: A peak-pick bridge builds a `Spectrum2D` in memory and reuses the existing `PeakPicker2D` via a direct Python call (mirroring `_perform_ranking()`), writing `analysis/nmr_peaks/*.json` byte-for-byte in the existing schema (HSQC edited-sign, HMBC, COSY) so the downstream CASE pipeline is unchanged.
- [x] **PICK-02**: `lucy nus pipeline <expdir>` runs the whole chain end-to-end (params → schedule → reconstruct → process → peak-pick → QC) as one reusable command usable for any NUS CASE run, not a C20H32O2-only script; all `lucy nus` subcommands support `--format json`.
- [x] **PICK-03**: Reconstruction-quality metadata (backend, iterations, QC verdict) is embedded in the emitted peak JSON, replacing the current blanket `"confidence": "low"`.

### Cross-platform portability (PORT)

- [ ] **PORT-01**: `lucy nus check` performs a platform preflight (Apple Silicon `arch`/Rosetta check, `csh`/`tcsh` availability, backend binaries) and reports readiness clearly, so a platform gap is caught before a run rather than mid-pipeline.
- [ ] **PORT-02**: A portability matrix is documented (macOS Apple Silicon native, Linux native, Windows WSL2/VM gap with concrete workaround steps) — every gap is investigated and written down, not silently accepted.

### End-to-end validation (VAL)

- [ ] **VAL-01**: C20H32O2 exp2 (COSY), exp3 (HSQC), exp4 (HMBC) are reconstructed end-to-end and pass the guide's §8 quality gate (clean 1-bond HSQC with correct edited signs, ridge-free HMBC, a real aliphatic COSY network).
- [ ] **VAL-02**: A fresh `/lucy-ng:case C20H32O2` run on the new peak lists converges on a small, rankable solution set (the milestone's actual success bar) — proving the reconstruction fixed the connectivity gap that timed out the first run at ~10⁶ candidates.

## Future Requirements

Acknowledged but deferred — not in this milestone's roadmap.

### Reconstruction backends (RECON+)

- **RECON-F1**: hmsIST / mddnmr CLI fallback backend, wired behind the `NusBackend` protocol, for cases where SMILE demonstrably leaves ridges at low sampling.
- **RECON-F2**: NMRFx (pure Java, native Windows) spike-comparison and optional primary-backend pivot, if native Windows becomes a hard requirement rather than a documented gap.
- **RECON-F3**: Generalized schedule/FnMODE abstraction for NUS experiment types beyond COSY/HSQC/HMBC (TOCSY, NOESY-NUS); 3D/4D NUS support.

### Reconstruction UX (RECONUX)

- **RECONUX-F1**: Per-peak reconstruction-confidence scoring feeding LSD constraint weighting directly.
- **RECONUX-F2**: Webview integration — render reconstructed 2D spectra + QC report in the existing dashboard tabs.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| From-scratch Python CS/IST reconstruction algorithm | High correctness risk; re-derives the exact class of bug (hand-rolled per-column IST) this milestone exists to fix. No mature pip package does it for NMR. |
| TopSpin headless reconstruction in the automated path | No source confirms a true zero-display headless mode; both AU-program and TopSpin Python Interface paths need a running GUI instance. Manual human escape hatch only. |
| Native Windows NMRPipe support | No maintained native build since v8.9. Accepted, documented gap (WSL2/VM). Not a blocker per milestone scope. |
| Deep-learning-based reconstruction | GPU dependency, poor portability, immature for small-molecule 2D validation. |
| Non-Bruker vendor NUS formats (Varian/JEOL) | Bruker-only remains the project-wide scope. |
| Reprocessing the uniformly-sampled experiments (exp5 NOESY, exp1/6/7 1D) | Not NUS — no reconstruction needed. |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| NUS-01..05 | Phase 97 | Pending |
| RECON-01..05 | Phase 98 | Pending |
| QC-01..03 | Phase 99 | Pending |
| PICK-01..03 | Phase 99 | Pending |
| PORT-01..02 | Phase 100 | Pending |
| VAL-01..02 | Phase 100 | Pending |

**Coverage:**
- v10.0 requirements: 20 total
- Mapped to phases: 20/20 ✓
- Unmapped: 0

---
*Requirements defined: 2026-07-12*
*Last updated: 2026-07-12 after roadmap creation — mapped to Phases 97-100 (100% coverage, no orphans).*
