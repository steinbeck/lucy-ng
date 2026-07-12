# Phase 94: Data Tables - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 94-data-tables
**Areas discussed:** LSD inventory layout, compound.lsd selection, HMBC flags, columns & metadata

---

## LSD constraint inventory layout (TBL-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Strukturiert + Reasoning | Applied-constraints table (type/atoms/note) for BOND/HMBC/COSY-equiv + count rows for MULT/HSQC + a Deferred/pending section from the narrative | ✓ |
| Flach, nur applied | Exactly the ROADMAP columns type/atoms/note, applied only, no pending/reasoning | |
| Roh-JSON pretty | Parsed JSON pretty-printed in a monospace block | |

**User's choice:** Strukturiert + Reasoning
**Notes:** JSON header exposes per-atom indices only for BOND / HMBC-correlations / COSY-equiv; MULT/HSQC are counts. The pending/deferred reasoning is a primary QC value of the inspector.

---

## Which compound.lsd

| Option | Description | Selected |
|--------|-------------|----------|
| Höchstes iteration_NN | Regex iteration_(\d+), highest numeric prefix across all families, mtime tiebreak | ✓ |
| Neueste per mtime | Last-written compound.lsd by mtime | |
| Alle Families (Auswahl) | Family dropdown / multiple inventories | |

**User's choice:** Höchstes iteration_NN
**Notes:** Iteration dirs carry family suffixes (iteration_06_ethyl33_anchor, iteration_07_anchor_recovery) with parallel families. Deterministic prefix-max matches ROADMAP "latest iteration_NN". Family selector deferred to v9.4.

---

## HMBC flag treatment (TBL-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Alle zeigen, farbcodiert | Show all kept rows; colour per flag (ok/potential_4J/1J_artifact) | ✓ |
| Nur flag=ok | Show only genuine long-range correlations, hide artefacts | |
| Alle + Filter-Toggle | All colour-coded plus an "only ok" toggle | |

**User's choice:** Alle zeigen, farbcodiert
**Notes:** Seeing what the detection layer flagged as artefact is the QC value. Filter toggle deferred.

---

## Columns & metadata

| Option | Description | Selected |
|--------|-------------|----------|
| QC-relevante Extras | 13C + confidence; correlations show observed/matched shifts, one_bond, compact intensity | ✓ |
| Nur Roadmap-Minimum | Only the columns named in ROADMAP/REQUIREMENTS | |
| Alles aus dem JSON | Every field incl. raw intensities | |

**User's choice:** QC-relevante Extras
**Notes:** Surface the fields a chemist judges peak quality on; intensities formatted compactly (5.6M not 5559614).

| Option | Description | Selected |
|--------|-------------|----------|
| Als Caption zeigen | note + counts as a small caption above each table | ✓ |
| Weglassen | Plain tables only, no metadata | |

**User's choice:** Als Caption zeigen
**Notes:** Curation narrative (why peaks removed, solvent exclusions, overcount alarms) is high-value QC context.

---

## Claude's Discretion

- Endpoint shape (combined `/api/tables` vs one route per source), subject to SC4 per-table waiting granularity.
- CSS palette for HMBC flag colours, caption styling, table density (respect v9.2/9.3 visual language).
- Whether to reuse `buildTable()` directly or wrap it for per-row flag classes + compact-intensity formatter.
- Internal parsing helpers, function names, module organisation.

## Deferred Ideas

- Family selector / multiple LSD inventories side-by-side → v9.4.
- HMBC "only ok" filter toggle → out of scope for this read-only phase.
- Real spectra traces + peak overlay → Phases 95/96.
- Interactive zoom/pan, DEPT sub-tab, SSE live push → v9.4.
