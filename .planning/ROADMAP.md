# lucy-ng Roadmap

## Milestones

- [v1.0 Core CASE Pipeline](milestones/v1.0-ROADMAP.md) - Phases 1-10 (shipped 2026-01-12)
- [v1.1 Database-Backed Dereplication](milestones/v1.1-ROADMAP.md) - Phases 11-15 (shipped 2026-01-15)
- [v1.2 HOSE Database Prediction](milestones/v1.2-ROADMAP.md) - Phases 16-19 (shipped 2026-01-18)
- **v2.0 Robust Multi-Agent CASE** - Phases 20-26 (shipped 2026-02-08)
- **v2.1 Working Multi-Agent CASE** - Phases 27-33 (shipped 2026-02-09)
- [v3.0 Statistical Detection](milestones/v3.0-ROADMAP.md) - Phases 34-40 (shipped 2026-02-16)
- [v4.0 Team-Based CASE](milestones/v4.0-ROADMAP.md) - Phases 41-48 (shipped 2026-02-18)
- [v5.0 Fragment Library](milestones/v5.0-ROADMAP.md) - Phases 49-54 (shipped 2026-02-21)
- [v6.0 Skill Quality Overhaul](milestones/v6.0-ROADMAP.md) - Phases 55-58 (shipped 2026-03-10)
- [v7.0 Statistical 4J Detection](milestones/v7.0-ROADMAP.md) - Phases 59-64 (ABANDONED 2026-03-12)
- **v8.0 pyLSD Integration** - Phases 65-71 (superseded by v9.0 before UAT passed)
- ✅ [v9.0 CASE Reliability & Skill Consolidation](milestones/v9.0-ROADMAP.md) - Phases 72-85 (shipped 2026-06-17)
- ✅ [v9.1 CASE Final-Answer Correctness & Verification Gates](milestones/v9.1-ROADMAP.md) - Phases 86-89 (shipped 2026-06-29)
- ✅ [v9.2 CASE Web-View](milestones/v9.2-ROADMAP.md) - Phases 90-92 (shipped 2026-07-07)
- ✅ [v9.3 CASE Web-View Stage 2](milestones/v9.3-ROADMAP.md) - Phases 93-96 (shipped 2026-07-12)

---

**v9.2 outcome:** A read-only web dashboard makes a CASE run observable live and after the fact —
`lucy webview serve/stop/status`, four JSON/SVG endpoints with graceful degradation, RDKit SVG
depictions, single-file vanilla-JS dashboard, auto-launched by `case.md`. Live-validated on CASE1
(ibuprofen, Rank 1 MAE 0.25). Full archive: [`milestones/v9.2-ROADMAP.md`](milestones/v9.2-ROADMAP.md).

---

**v9.3 outcome:** The read-only CASE web-view grew from a status monitor into a full
spectral-inspection suite — a persistent 4-tab bar (Run Log / 1D / 2D Spectra / Tables) over a
markdown-rendered run log, data tables (¹³C signals, HSQC/HMBC/COSY correlations, LSD constraint
inventory), and **real rendered 1D + 2D NMR spectra with the picked peaks overlaid** for visual
peak-picking QC. New `tables.py` + `spectra.py` routers; `.run_manifest.json` raw-Bruker-path
wiring; matplotlib in the `[webview]` extra (OO-API/lazy/WV-08); block-max decimation + MAD
contour levels + mtime PNG cache for 2D. Full archive:
[`milestones/v9.3-ROADMAP.md`](milestones/v9.3-ROADMAP.md).

