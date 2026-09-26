# Phase 100: Cross-Platform Hardening + End-to-End Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-18
**Phase:** 100-cross-platform-hardening-end-to-end-validation
**Areas discussed:** VAL environment & evidence, VAL pass thresholds, VAL-fail contingency, PORT-01/02 semantics

---

## VAL environment & evidence

Opening framing was corrected mid-discussion: Claude initially stated "the dev Mac can't run the backend". The user challenged ("if the Mac can't run it, no point continuing — what's the problem?"). A live check (`uname -m` → arm64, macOS 26.5; `csh`/`tcsh` present; `nmrPipe`/`bruk2pipe`/`nusExpand.tcl` absent) proved it is an **uninstalled tool, not a platform blocker** — macOS Apple Silicon is a first-class native target per the locked backend decision.

| Option | Description | Selected |
|--------|-------------|----------|
| Lokal installieren + hier laufen | Install native NMRPipe+SMILE on this Mac, get `lucy nus check` green, run the full VAL chain locally | ✓ |
| Doch Sheldon nutzen | Run on the Linux backend host, commit artifacts back (remote/manual snapshot) | |
| Erst Install prüfen, dann entscheiden | Research install effort first, decide local vs Sheldon with facts | |

**User's choice:** Lokal installieren + hier laufen.
**Notes:** Install documented as a CLAUDE.md prerequisite (like LSD solver), not a code deliverable. Evidence form = committed real peak JSONs + QC report + VALIDATION.md (Claude default, user did not object). PORT-01 preflight is the tool that confirms the local install green before VAL.

---

## VAL pass thresholds

### VAL-01 (§8 gate acceptance)

| Option | Description | Selected |
|--------|-------------|----------|
| QC PASS, sonst blockiert | Only PASS counts; PARTIAL = not passed | |
| PASS oder PARTIAL + Chemist-Sichtprüfung | PASS passes; PARTIAL accepted if soft-only + chemist visual; critical = FAIL | (Claude rec) |
| QC-Verdict rein maschinell | Machine gate is truth, no human eyeball | |

**User's choice:** "Deine Empfehlung" → Claude recommended **Option 2** (PASS, or PARTIAL when soft-only + brief chemist confirm; any critical violation = FAIL), coupled to VAL-02 as the real bar.
**Notes:** Rationale — QC gate calibrated only against synthetic anchors; real C20H32O2 is its first true test, so a one-off milestone-close run warrants a human eyeball on PARTIAL.

### VAL-02 (convergence bar)

| Option | Description | Selected |
|--------|-------------|----------|
| LSD terminiert + rankbares Set | LSD completes (no ~10⁶ timeout) + finite rankable set; correct structure top = bonus | ✓ |
| Struktur in Top-N | Additionally requires correct structure in top-N after ranking | |
| Konkrete Kandidaten-Obergrenze | Hard number ceiling (e.g. < 10⁴) | |

**User's choice:** LSD terminiert + rankbares Set.
**Notes:** Most honest bar, maps directly onto the original 2026-07-09 timeout failure mode.

---

## VAL-fail contingency

| Option | Description | Selected |
|--------|-------------|----------|
| Tuning-Budget, dann ehrlich stoppen | Bounded knob-tuning budget, then documented limitation + RECON-F1 pointer | (Claude rec) |
| hmsIST-Fallback ziehen (RECON-F1) | Activate the deferred second backend in this phase on hard SMILE fail | |
| Hart blockieren | No tuning beyond defaults; FAIL = milestone not through, phase stays open | |

**User's choice:** "Deine Entscheidung" → Claude decided **Option 1** (bounded, pre-defined tuning budget: SMILE knobs, apodization, phase defaults, 33% density; then honest stop → documented limitation in VALIDATION.md + ROADMAP + RECON-F1 as tracked next step).
**Notes:** hmsIST rejected as scope-sprengung (deferred future-req, own phase). Hard-block rejected — SMILE is third-party; a sampling limit isn't our code. PORT ships independently of the VAL outcome, so the phase never fully fails.

---

## PORT-01/02 semantics

### PORT-01 (preflight behavior)

| Option | Description | Selected |
|--------|-------------|----------|
| Kritisch = block, Rest = warn | Critical gaps fail-loud block pre-stage (exit≠0); soft (Rosetta/x86) warn-not-block; granular report | ✓ |
| Nur berichten, nie blockieren | check reports readiness but run proceeds, fails at real stage error | |
| Du entscheidest | — | |

**User's choice:** Kritisch = block, Rest = warn.
**Notes:** Consistent with RECON-04 fail-loud + D-07 write boundary.

### PORT-02 (portability matrix location + depth)

| Option | Description | Selected |
|--------|-------------|----------|
| docs/-Datei, WSL2 dokumentiert-theoretisch | Dedicated docs/NUS-PORTABILITY.md; WSL2 step-by-step but marked documented-untested | ✓ |
| README-Abschnitt, WSL2 real getestet | README section + WSL2 verified on a real Windows host | |
| Du entscheidest | — | |

**User's choice:** docs/-Datei, WSL2 dokumentiert-theoretisch.
**Notes:** No Windows host confirmed available — don't hang the phase on acquiring one; honest "documented, untested" marking satisfies PORT-02's "written down, not silently accepted".

---

## Claude's Discretion

- VAL-01 §8 acceptance semantics (user said "Deine Empfehlung" → Claude recommended, user accepted).
- VAL-fail contingency (user said "Deine Entscheidung" → Claude decided).
- Preflight check API surface / `diagnose()` extension shape.
- `docs/NUS-PORTABILITY.md` layout + where the install-prerequisite block lives (CLAUDE.md/README).
- `VALIDATION.md` contents/format + real-peak-list location (must not overwrite known-bad QC-02 fixtures).
- Concrete numeric bounds of the D-04 tuning budget.

## Deferred Ideas

- hmsIST/mddnmr fallback (RECON-F1) — the documented next step if tuning budget exhausted; own future phase.
- Real WSL2/native-Windows verification; NMRFx pivot (RECON-F2).
- Webview rendering of reconstructed 2D + QC (RECONUX-F2); per-peak recon-confidence → LSD weighting (RECONUX-F1).
- Reviewed-not-folded todos: `2026-06-25-case4-azulene-regiochemistry-enumeration-gap`, `2026-06-30-ranking-tests-hardfail-without-hosegen` (unrelated to PORT/VAL, same call as Phases 97/98/99).
