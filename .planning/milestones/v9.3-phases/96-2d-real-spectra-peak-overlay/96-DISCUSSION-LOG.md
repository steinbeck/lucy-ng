# Phase 96: 2D Real Spectra + Peak Overlay - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 96-2d-real-spectra-peak-overlay
**Areas discussed:** Contour-Darstellung, Decimation-Methode, Cross-Peak-Marker, 2D-Tab-Layout

---

## Contour-Darstellung

### Contour levels above MAD noise floor

| Option | Description | Selected |
|--------|-------------|----------|
| Geometrisch, ~8 Levels | Levels grow geometrically (~1.4) from the noise floor; ~8 levels show weak + strong peaks without smearing. NMR-software standard. | ✓ |
| Linear, ~10 Levels | Even spacing; emphasises strong peaks, weak long-range HMBC cross-peaks vanish. Less usual for 2D NMR. | |
| Du entscheidest | Claude picks per NMR convention. | |

### Contour line colouring

| Option | Description | Selected |
|--------|-------------|----------|
| Einfarbig dezent | All contour lines one muted grey/blue-grey (~1D trace #495057); calm background so coloured markers stand out. | ✓ |
| Colormap nach Intensität | Contour lines coloured by height (viridis); shows intensity but competes with overlay markers, new colours. | |

### Positive vs negative contours

| Option | Description | Selected |
|--------|-------------|----------|
| Nur positive | Magnitude-mode assumption; positive contours only. Sufficient for QC. | ✓ |
| Positive + negative | Adds negative contours (phase-sensitive edited-HSQC CH2 / artefacts); more info, more complexity. | |

**Notes:** Positive-only, single muted colour, geometric ~8 levels — a calm QC background under coloured overlay markers.

---

## Decimation-Methode

| Option | Description | Selected |
|--------|-------------|----------|
| Block-Maximum | Max-pool per block; preserves peak apices — narrow HMBC cross-peak between grid points survives. | |
| Striding | data[::step]; fastest/simplest but can lose narrow peak apices → chemist misses a real peak. | |
| Du entscheidest | Claude picks pragmatically (block-max for fidelity, striding as perf fallback), documents. | ✓ |

**Notes:** Deferred to Claude with a strong lean recorded in CONTEXT.md D-04: block-maximum preferred for peak fidelity; striding only if block-max can't meet the <1 s budget (SC3).

---

## Cross-Peak-Marker

### Marker shape

| Option | Description | Selected |
|--------|-------------|----------|
| Offene Kreise | Ring around each peak; contour underneath stays visible, shows whether marker hits real signal. | ✓ |
| Kreuze (× / +) | Thin cross marks exact coordinate; precise but harder to read as a group in dense regions. | |
| Du entscheidest | Claude picks form/size. | |

### HSQC marker differentiation

| Option | Description | Selected |
|--------|-------------|----------|
| Alle gleich | Uniform HSQC marker style; HSQC peaks are one-bond by definition, distinction adds noise. (Only HMBC flag-coded, locked.) | ✓ |
| one_bond hervorheben | matched_real_carbon / one_bond styled differently; shows detection quality, more complexity. | |

### COSY diagonal

| Option | Description | Selected |
|--------|-------------|----------|
| Diagonale einzeichnen | Thin grey diagonal (F1=F2) as orientation; usual COSY look. proton_a on x, proton_b on y, both reversed. | ✓ |
| Keine Diagonale | Contours + markers only; cleaner but less familiar. | |

**Notes:** Open circles, uniform HSQC, COSY diagonal drawn. HMBC flag-colour coding is a locked ROADMAP SC2 requirement (not re-discussed).

---

## 2D-Tab-Layout

### Plot arrangement

| Option | Description | Selected |
|--------|-------------|----------|
| Gestapelt, alle sichtbar | Three `<img>` stacked, all rendered (mirrors 1D carbon+proton); each polls/renders independently, per-plot 'unavailable'. | ✓ |
| Sub-Tabs im 2D-Tab | HSQC\|HMBC\|COSY selector, only active plot rendered; saves requests but new pattern, no side-by-side compare. | |

### Endpoint shape

| Option | Description | Selected |
|--------|-------------|----------|
| Drei PNG-Routen | /api/spectra/2d/{hsqc,hmbc,cosy}; mirrors 1D carbon/proton split, per-plot independent degradation. | ✓ |
| Du entscheidest | Claude picks route form as long as each plot can be independently 'unavailable'. | |

**Notes:** Stacked all-visible + three independent PNG routes — consistent with the Phase 95 pattern.

---

## Claude's Discretion

- Exact geometric growth factor + final level count within "geometric, ~8" (D-01).
- Decimation method: block-max vs striding fallback, block size, per-axis step (D-04).
- 2D experiment-selection tiebreak (multiple same-type experiments) — mirror the 1D
  `_select_experiment` (scan `acqu2s` dirs, use `Spectrum2D.experiment_type`, lowest-number
  tiebreak).
- Figure sizing/DPI, marker/circle/diagonal/contour line weights — v9.2/9.3 look, no new
  design system.
- mtime-cache internal structure and eviction policy.
- Endpoint internals, helper/function names, module organisation within `spectra.py`.

## Deferred Ideas

- Negative / phase-sensitive edited-HSQC contours (CH2 down-peaks) — rejected D-03; v9.4.
- HSQC one_bond / matched_real_carbon marker distinction — rejected D-05.
- Sub-tabs / plot selector inside the 2D tab — rejected D-09.
- Interactive zoom/pan, DEPT sub-tab, SSE live push — v9.4 per STATE.md.
- Colormap-by-intensity contours — rejected D-02.
- Reviewed todo not folded: `CASE4 azulene regiochemistry enumeration gap` — CASE-solver
  concern, off-topic for 2D rendering (same disposition as Phase 95).
