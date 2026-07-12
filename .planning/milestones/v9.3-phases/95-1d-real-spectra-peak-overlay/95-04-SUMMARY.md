---
plan: 95-04
phase: 95-1d-real-spectra-peak-overlay
status: checkpoint-defect-captured
completed: 2026-07-09
tasks_total: 1
tasks_done: 1
---

# Plan 95-04 Summary — Human Browser Verification (1D Spectra Tab)

## Outcome

Human-verify checkpoint executed by the orchestrator via live browser automation
(claude-in-chrome) against the **real CASE1 / ibuprofen** dataset. A manifest-backed
`analysis/` dir was built pointing `bruker_data_dir` at the real CASE1 Bruker tree with
an ibuprofen-literature `carbon_signals.json` overlay; `lucy webview serve` was launched
and the 1D Spectra tab was opened, screenshotted, and inspected. Degradation paths
(empty dir, stale raw path) were exercised on separate server instances.

**User verdict:** NOT approved as-is — routed to gap closure for one cosmetic defect
(see below). All correctness criteria passed.

## Verified PASS (real evidence, screenshots inspected)

| Criterion | Result |
|-----------|--------|
| SC1 — real continuous ¹³C trace (not sticks), noise floor visible | ✅ |
| SC1 — peak overlay: vertical accent markers + ppm + assignment labels | ✅ |
| SC2 — reversed ppm axis (200 left → 0 right) | ✅ |
| SC2 — carbonyl (180.9) far LEFT, aliphatic CH₃ (22.4/18.1) right | ✅ |
| DEPT sanity — carbonyl present in trace → standard ¹³C (`zgpg30`), not DEPT | ✅ |
| Real data — CDCl₃ solvent (~77 ppm) in trace, correctly NOT overlaid | ✅ |
| ¹H — real ¹H trace rendered (ibuprofen pattern, isopropyl doublet ~0.9) | ✅ |
| SC3 — base `from lucy_ng.cli import cli` w/o matplotlib; no top-level imports | ✅ |
| SC4/SP-02 — empty dir → "Waiting for a live CASE run…" placeholder PNG, HTTP 200 | ✅ |
| SP-02/D-05 — stale raw path → "Raw Bruker data not found at the recorded path.", HTTP 200 | ✅ |
| Frontend — both `<img>` load live in the tab; tab switching; no console errors | ✅ |

## Defect captured (verbatim → gap closure)

**Assignment-label collision in dense-peak regions.** The picked-peak **ppm number
labels** are rotated 90° and stack legibly, but the **assignment text labels** are drawn
horizontally (`va="bottom"`, no rotation) at the top of the axes. Where peaks are close
in ppm (aromatic ~127–141: "ArC/ArCH" overlap; methyls ~18–22: "2xCH3/CH3" overlap), the
horizontal assignment labels collide and become unreadable. The ppm numbers remain
readable and the trace/axis/overlay are all correct — this is a legibility-only issue,
consistent with the non-blocking UI-checker Dimension 2/5 FLAGs.

**Routing:** Addressed by gap-closure plan **95-05** (`_render_1d_png` — combine ppm +
assignment into a single rotated per-peak label to eliminate horizontal collision).
Phase 95 completion is gated on 95-05 + re-verification.

## Self-Check: PASSED (checkpoint executed, defect recorded, no code changed here)
