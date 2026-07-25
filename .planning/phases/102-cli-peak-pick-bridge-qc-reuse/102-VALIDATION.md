---
phase: 102
slug: cli-peak-pick-bridge-qc-reuse
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-25
---

# Phase 102 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/test_jcamp_cli.py tests/test_jcamp_bridge_1d.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5 s quick · ~180 s full suite (1408 tests at Phase-101 close) |

Static gates (CLAUDE.md, run alongside the suite):
- `mypy src/lucy_ng` (strict mode — every new module must pass)
- `ruff check src tests`

---

## Sampling Rate

- **After every task commit:** Run the quick command above
- **After every plan wave:** Run `pytest -q` plus `mypy src/lucy_ng`
- **Before `/gsd-verify-work`:** Full suite must be green, zero regressions vs. the 1408-test Phase-101 baseline
- **Max feedback latency:** 10 seconds (quick), 180 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| *(filled by gsd-planner during planning)* | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_jcamp_bridge_1d.py` — RED stubs for the new 1D bridge (JCLI-01, D-03)
- [ ] `tests/test_jcamp_cli.py` — RED stubs for `lucy jcamp` (JCLI-01: dir + explicit files, `--format json`, D-06 non-fatal skip)
- [ ] `tests/test_skill_files_unchanged.py` — RED stub for the byte-unchanged assertion on `case.md` + `.claude/agents/lucy-*.md` (JCLI-02 / success criterion 4)
- [ ] Homonuclear-2D fixture coverage — a committed COSY-shaped JCAMP fixture (or a `$NUC1 = ['<1H>','<1H>']` header variant of the existing trimmed fixture) so the `_resolve_dim` fix is proven on data, not on a mock

*Existing infrastructure otherwise covers the phase: `tests/test_jcamp.py` (Phase-101 real committed fixtures), `tests/test_bridge.py` / `tests/test_bridge_metadata.py` (Phase-99 2D bridge), `tests/test_qc*.py` (unchanged QC gate).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `lucy jcamp` end-to-end on the real 6-file `C20H32O2-jcamp` dataset | JCLI-01 | The dataset lives outside the repo (`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/`, ~2048×2048 spectra) and is deliberately not committed | Run `lucy jcamp <that dir> --format json`; confirm HSQC/HMBC/COSY + `13c_*`/`1h_*` peak JSONs are written, NOESY is skipped with a visible warning, and a QC verdict is embedded. **Grading the verdict green (§8 quality) is Phase 103 / JVAL — out of scope here (D-05).** |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
