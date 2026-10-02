---
phase: 104
slug: package-and-cli
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-02
---

# Phase 104 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`[tool.pytest.ini_options]` in `pyproject.toml`, `testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --extra dev pytest -q -p no:cacheprovider -k "not test_import_coconut_real"` |
| **Full suite command** | `uv run --extra dev pytest -q -p no:cacheprovider` |
| **Estimated runtime** | ~79 seconds (quick); 10+ minutes (full, with the real-data import test) |

---

## Baseline (measured 2026-10-02, before any rename edit)

| Check | Baseline |
|-------|----------|
| pytest (quick) | 1345 passed / 74 failed / 86 skipped / 1 xfailed — all 74 failures are pre-existing environment gaps |
| `mypy --strict` | 33 errors |
| `ruff check src tests` | 282 errors |

"Same as before" in PKG-04 means these counts, not a clean report. Wave 0 re-measures and records them before the first rename edit.

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Quick run command plus the `lucy_ng` grep gate (`grep -rn "lucy_ng" src/ tests/ scripts/ --include="*.py"` returns empty once the module rename has landed)
- **Before `/gsd-verify-work`:** Full suite, `mypy --strict`, and `ruff` counts match the baseline
- **Max feedback latency:** ~80 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| PKG-01 | `pyproject.toml` names the project `ailsa`; package builds, passes twine check, has no direct-URL dependency; installs from PyPI | smoke | 104-02 T1 (`name = "ailsa"`, `import ailsa`); 104-05 T1 (`uv build` + METADATA/sdist/twine gate); 104-06 T3 (fresh-venv `pip install ailsa==0.1.0`, after human approval) | N/A | ⬜ pending |
| PKG-02 | No `lucy_ng` module or import in `src/`, `tests/`, `scripts/` | grep gate | 104-02 T1 and 104-05 T2: `grep -rn --exclude-dir=__pycache__ "lucy_ng" src tests scripts pyproject.toml` → empty; `test ! -e src/lucy_ng` | N/A | ⬜ pending |
| PKG-03 | `ailsa …` works; `lucy …` works and prints the deprecation hint on stderr only, stdout JSON untouched | unit + CLI | 104-03 T1 `tests/test_cli_deprecated_alias.py` (capsys + real-subprocess byte comparison, golden cmp); 104-03 T2 `tests/test_webview_launcher.py`; 104-05 T3 PATH-level `lucy`/`ailsa` shasum equality | created in 104-03 (RED first) | ⬜ pending |
| PKG-04 | No failing node ID beyond the baseline; mypy/ruff no new normalised finding line | regression | 104-01 T2 records baseline files; every later plan runs the `comm -13` comparison; 104-05 T2 full gate incl. slow test | N/A | ⬜ pending |
| PKG-05 | `DatabaseFinder` and `database download`/`info` accept `lucy-ng-derep.db` as well as the new default | unit | 104-04 T1 `tests/test_database_finder.py` (isolated HOME/cwd/mdfind); 104-04 T2 new classes in `tests/test_cli_database.py`; real-file checks on this machine | created in 104-04 (RED first) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Re-measure and record the baseline counts (pytest, mypy, ruff) as the phase's first task output
- [ ] Test for the `lucy` deprecated alias: hint on stderr, stdout unchanged (PKG-03)
- [ ] Tests for dual-filename database resolution (PKG-05)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Upload of the real package to PyPI | PKG-01 | Public and irreversible; requires explicit user approval | After approval: `uv build && twine upload dist/*`; then in a fresh venv `pip install ailsa==<version>` and run `ailsa --help` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
