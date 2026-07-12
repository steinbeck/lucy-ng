---
phase: 95
slug: 1d-real-spectra-peak-overlay
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 95 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/test_webview_api.py -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~90 seconds (full suite); ~5 s (webview only) |

Notes:
- `spectra.py` router + matplotlib render are covered by a new `TestSpectraEndpoint`
  in `tests/test_webview_api.py`, mirroring the Phase 94 `TestTablesEndpoint` WV-08
  import-safety pattern (fastapi/matplotlib imports inside test bodies; `try/except
  ImportError: pytest.skip`).
- The reversed-axis contract (SC2) is an assertion-level test: render against the CASE1
  ibuprofen dataset (or a synthetic descending-ppm fixture) and assert
  `ax.get_xlim()[0] > ax.get_xlim()[1]`.
- `from lucy_ng.cli import cli` import-without-matplotlib (SC3) is a base-install
  guard test.

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_webview_api.py -q`
- **After every plan wave:** Run `pytest`
- **Before `/gsd:verify-work`:** Full suite must be green + `mypy src/lucy_ng` + `ruff check src tests`
- **Max feedback latency:** ~5 seconds (webview slice)

---

## Per-Task Verification Map

*Derived from the 4 finalized plans. Each implementation task carries an
`<automated>` verify command; Wave 0 (95-01) ships the RED-by-skip scaffold.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 95-01-01 | 01 | 0 | SP1-01 | — | matplotlib confined to `[webview]` extra (base install imports without it) | unit | `python -c "import tomllib,sys;d=tomllib.load(open('pyproject.toml','rb'))" && pytest tests/test_webview_api.py -q` | ✅ | ⬜ pending |
| 95-01-02 | 01 | 0 | SP1-01, SP-02 | T-95-02-01 | RED-by-skip scaffold: reversed-axis assertion + never-500 + base-import guard | unit | `pytest tests/test_webview_api.py::TestSpectraEndpoint -q` | ✅ | ⬜ pending |
| 95-02-01 | 02 | 1 | SP1-01, SP-02 | — | `_apply_nmr_axes` set_xlim-only (no invert_xaxis); `_select_experiment` excludes 2D/DEPT | unit (tdd) | `pytest tests/test_webview_api.py::TestSpectraEndpoint -q` | ✅ W0 | ⬜ pending |
| 95-02-02 | 02 | 1 | SP1-01, SP-02 | T-95-02-01 | never-500 PNG routes; placeholder image bytes, no JSON on image route | unit (tdd) | `pytest tests/test_webview_api.py::TestSpectraEndpoint -q` | ✅ W0 | ⬜ pending |
| 95-03-01..03 | 03 | 2 | SP1-01, SP-02 | — | 1D Spectra tab `<img>` + poll; `case.md` `.run_manifest.json` write | unit | `pytest tests/test_webview_api.py -q` | ✅ W0 | ⬜ pending |
| 95-04-01 | 04 | 3 | SP1-01, SP-02 | — | manual browser QC: real trace, carbonyl-left, overlay alignment, unavailable states | manual | (checkpoint:human-verify) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. "File Exists" = the test file the
verify command targets already exists (✅) or is created in Wave 0 (✅ W0).*

---

## Wave 0 Requirements

- [ ] `tests/test_webview_api.py::TestSpectraEndpoint` — RED-by-skip stubs for SP1-01, SP-02
      (mirror Phase 94 `TestTablesEndpoint`; hand-authored fixtures for
      `analysis/.run_manifest.json`, `carbon_signals.json`, and a Bruker experiment tree
      or a synthetic descending-ppm `Spectrum1D`)

*Existing pytest infrastructure otherwise covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 1D Spectra tab renders the real ¹³C trace + peak overlay in a browser, visually matching the raw signal | SP1-01 | Visual QC of the rendered PNG (peak positions vs real signal, reversed axis, marker/label legibility) cannot be fully asserted headlessly | Run a live/replayed CASE1 run, open the webview, select the 1D Spectra tab, confirm carbonyl (~181 ppm) on far left, CH₃ on right, markers aligned to peaks (Phase 93 D-04 manual browser checkpoint) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (95-01 ships `TestSpectraEndpoint` scaffold)
- [x] No watch-mode flags
- [x] Feedback latency < 5s (webview slice)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-09 (plans finalized; per-task map derived from 95-01..95-04)
