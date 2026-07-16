# Phase 99: Peak-Pick Bridge + QC Gate + CLI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-14
**Phase:** 99-peak-pick-bridge-qc-gate-cli
**Areas discussed:** PARTIAL-Semantik, QC-Schwellen & 1D-Quelle, Schema & Metadaten, QC-Verdrahtung & CLI

---

## PARTIAL-Semantik — CASE-Handoff bei PARTIAL

| Option | Description | Selected |
|--------|-------------|----------|
| PARTIAL geht durch + Warnung | Nur FAIL blockiert; PARTIAL schreibt Peaks + Verdikt in Metadaten/Log | ✓ |
| PARTIAL blockiert auch | Nur PASS lässt CASE starten | |
| PARTIAL degradiert Constraints | PARTIAL geht durch, betroffene Peaks als "weich" markiert | |

**User's choice:** PARTIAL geht durch + Warnung.
**Notes:** Milestone-Ziel ist CASE-Konvergenz; harte PARTIAL-Blockade würde reale Rekonstruktionen stoppen. Warnung erreicht Agenten über den Metadaten-Block im JSON — kein case.md-Eingriff.

## PARTIAL-Semantik — Verdikt-Aggregation

| Option | Description | Selected |
|--------|-------------|----------|
| Kritische vs weiche Checks | Kritische Checks ⇒ FAIL, weiche ⇒ PARTIAL, alle sauber ⇒ PASS | ✓ |
| Reine Zählung | 0 fail=PASS, 1-2=PARTIAL, ≥3=FAIL | |
| Pro-Check Sub-Verdikt + Worst-of | Jeder Check PASS/PARTIAL/FAIL, Gesamt = worst-of | |

**User's choice:** Kritische vs weiche Checks.

## PARTIAL-Semantik — welche Checks sind kritisch (⇒FAIL)

| Option | Description | Selected |
|--------|-------------|----------|
| Quaternär-Ausschluss | Quaternäre mit 1-Bindungs-HSQC = fabriziert | ✓ |
| ppm-Kalibrierung | Achsen grob daneben = alle Korrelationen fehlplatziert | ✓ |
| Signal/Ridge-Verhältnis | t1-Ridges dominieren = home-IST-Fehlermodus | ✓ |
| HSQC-Abdeckung | Anteil protonierter C mit genau einer Korrelation | ✓ |

**User's choice:** Alle vier kritisch. Weiche (PARTIAL-)Checks bleiben damit: edited-sign-Konsistenz, COSY-Diagonal-Symmetrie.
**Notes:** HSQC-Abdeckung als kritisch gewählt ⇒ braucht einen FAIL-Floor, der eine unvollständige-aber-saubere Rekonstruktion nicht hart blockiert (Threshold-Kalibrierung, siehe Schwellen-Bereich).

---

## QC-Schwellen & 1D-Quelle — Referenzquelle

| Option | Description | Selected |
|--------|-------------|----------|
| Bestehende 1D-Peaklisten | Aus vorhandenen 13C/1H nmr_peaks JSON lesen | ✓ |
| Frisch aus 1D-Spektren picken | Zweiter Picker-Lauf, autark | |
| Explizit übergebene Referenz | CLI-Argument | |

**User's choice:** Bestehende 1D-Peaklisten.

## QC-Schwellen & 1D-Quelle — prot/quaternär-Klassifikation

| Option | Description | Selected |
|--------|-------------|----------|
| DEPT/edited, sonst detection | DEPT falls vorhanden, sonst detection/-Multiplizität | ✓ |
| Nur 13C-Shift-Heuristik | Aus Shift-Region + DBE | |
| Toleranz-basiert, keine harte Liste | Nur ppm-Nähe zu bekannten Quaternären | |

**User's choice:** DEPT/edited, sonst detection.
**Notes:** Muss unabhängig von der zu prüfenden HSQC sein (sonst zirkulär).

## QC-Schwellen & 1D-Quelle — Festlegung der Schwellen

| Option | Description | Selected |
|--------|-------------|----------|
| Defaults aus §8 + optional überschreibbar | Konstanten aus Guide + CLI/Config-Override | ✓ |
| Fest verdrahtet, nicht überschreibbar | Feste Konstanten, keine Knobs | |
| Forschung soll Werte bestimmen | Werte an Researcher delegieren | (ergänzend) |

**User's choice:** Defaults aus §8 + optional überschreibbar.
**Notes:** Exakte Signal/Ridge- und Abdeckungs-Floor-Werte werden gegen QC-02 kalibriert (known-bad ⇒ FAIL, sauber ⇒ PASS) — als Research-Auftrag festgehalten.

---

## Schema & Metadaten — Platzierung der Metadaten

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level additiver Block | Neuer top-level Key, per-Peak-Schema stabil | ✓ (Claude entschied) |
| Pro Cross-Peak | backend/iterations je Peak | |
| Separates Sidecar-File | Eigene .qc.json-Datei | |

**User's choice:** "Du entscheidest" → Claude wählte den top-level additiven Block (löst PICK-01/PICK-03-Spannung, per-Peak-Schema bleibt stabil).

## Schema & Metadaten — confidence-Ersatz

| Option | Description | Selected |
|--------|-------------|----------|
| Aus QC-Verdikt abgeleitet | PASS→high/medium, PARTIAL→low, FAIL→gar nicht an CASE | ✓ |
| Aus Peak-SNR abgeleitet | Pro-Peak-SNR | |
| Kombiniert QC + SNR | Basis QC, pro-Peak korrigiert | |

**User's choice:** Aus QC-Verdikt abgeleitet.

---

## QC-Verdrahtung & CLI — CLI-Oberfläche

| Option | Description | Selected |
|--------|-------------|----------|
| Eigenständiges qc + pipeline | `lucy nus qc` standalone (QC-02 testbar) + `lucy nus pipeline` volle Kette | ✓ |
| Nur pipeline, qc intern | Kein separater qc-Command | |
| Du entscheidest | Aufteilung dem Planner überlassen | |

**User's choice:** Eigenständiges qc + pipeline.

## QC-Verdrahtung & CLI — Enforcement-Ort

| Option | Description | Selected |
|--------|-------------|----------|
| Pipeline schreibt Peaks nur bei PASS/PARTIAL | Fail-loud am Entstehungsort, case.md unangetastet | ✓ |
| case.md liest QC-Verdikt & bricht ab | Peaks immer geschrieben, Orchestrator gated | |
| Beides: Pipeline-Barriere + case.md-Gate | Defense-in-depth | |

**User's choice:** Pipeline schreibt Peaks nur bei PASS/PARTIAL.
**Notes:** Bei FAIL → Quarantäne-/Diagnose-Pfad + Exit non-zero. case.md bleibt unangetastet (Phase-98-Invariant); Defense-in-depth bewusst verworfen.

---

## Claude's Discretion
- Exakter Name/Shape des top-level Metadaten-Blocks (`reconstruction` vs `nus_metadata`); `caveat`-Regeneration/Entfernung.
- Ob `lucy nus peak-pick` eigener Subcommand oder nur interne Stufe.
- Confidence-Mapping (PASS→high vs medium); Quarantäne-Verzeichnisname.
- Exakte Signal/Ridge- und HSQC-Abdeckungs-Floor-Werte (datenkalibriert gegen QC-02).
- `nus/bridge.py` API-Surface + Split vom QC-Modul.

## Deferred Ideas
- Platform preflight / Portabilitätsmatrix → Phase 100 / PORT.
- End-to-end §8-Validierung + CASE-Konvergenz → Phase 100 / VAL.
- Per-Peak-Confidence → LSD-Constraint-Weighting (RECONUX-F1); Webview-QC-Rendering (RECONUX-F2) → v1.x.
- Defense-in-depth zweites QC-Gate in case.md → explizit verworfen (Invariant).
- Kombiniertes QC+SNR per-Peak-Confidence → verworfen zugunsten QC-Verdikt-abgeleitet.
