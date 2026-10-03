---
phase: 104-package-and-cli
plan: 06
subsystem: infra
tags: [packaging, pypi, twine, release]

requires:
  - phase: 104-05
    provides: "PyPI-uploadable pyproject.toml and a full-phase regression gate with no regression"
provides:
  - "Verified release artifacts dist/ailsa-0.1.0-py3-none-any.whl and dist/ailsa-0.1.0.tar.gz (gitignored, not committed)"
  - "A recorded user decision: PyPI upload deferred until after the documentation phase"
affects: [105]

key-files:
  created: []
  modified:
    - .planning/REQUIREMENTS.md

key-decisions:
  - "PyPI upload deferred by user decision on 2026-10-03. Reason: the PyPI long description is README.md, which still presents the project as lucy-ng with `lucy` commands; README is rewritten in Phase 105 (docs), and the first public version number can never be reused. Upload after Phase 105."
  - "PKG-01 checkbox reverted to open: the pyproject half (project named `ailsa`) is done; the PyPI half (`pip install ailsa` gives the real package) is pending the deferred upload."

requirements-completed: []

duration: ~10 min
completed: 2026-10-03
---

# Phase 104 Plan 06: Release artifacts built, PyPI upload deferred

**ailsa 0.1.0 wheel and sdist built and twine-verified; publishing deferred by the user until the README rewrite in Phase 105. Nothing was uploaded.**

## Task Outcomes

| Task | Outcome |
|------|---------|
| 1. Build release artifacts + manifest | Done. `uv build` produced exactly the two artifacts below. |
| 2. Approval checkpoint | User answered **defer** (2026-10-03). |
| 3. Upload / verify | Not run (defer branch). PyPI release list unchanged: `['0.0.1']`, `info.version` 0.0.1. |

## Release Manifest (as presented to the user)

- **Name / version:** `ailsa` 0.1.0, License-Expression MIT, Requires-Python >=3.10
- **Summary:** AILSA (AI + LSD + Agents): agentic Computer-Assisted Structure Elucidation of natural products from NMR data
- **Requires-Dist:** click>=8.0, jsonschema>=4.18.0, nmrglue>=0.12, numpy>=1.24, pydantic>=2.0, rdkit>=2023.0, requests>=2.28, scipy>=1.10, tqdm>=4.0; extras `dev` (httpx, mypy, pytest-cov, pytest, ruff) and `webview` (fastapi, matplotlib, uvicorn). No ` @ ` direct-URL dependency.
- **Files:**
  - `ailsa-0.1.0-py3-none-any.whl` — 371351 bytes — sha256 `6258fe8cac5849986b66af668dfe7bfb0560a8a386205c20e166d85fd71f91aa` — 131 files
  - `ailsa-0.1.0.tar.gz` — 305456 bytes — sha256 `600c80a3c3c7c201cac6646bde463663b5512a6ff6fe4135231692712e7672a3` — 126 files under `src/ailsa/` plus `.gitignore`, `LICENSE`, `README.md`, `pyproject.toml`, `PKG-INFO`
- **twine check:** PASSED (wheel), PASSED (sdist)
- **PyPI state at decision time:** `info.version` 0.0.1, releases `['0.0.1']`
- **README head (PyPI page):** `# lucy-ng` / "AI-Agent Powered Computer-Assisted Structure Elucidation for Organic Natural Products"
- **Identity scan of both archives:** the only real compound-name hits are the long-public example dataset name used in README/docstring examples and one docstring example word in `identity.py`; both are already on the public GitHub master. All other hits were generic words from the scan list. No new disclosure.

## Pending

- PKG-01 PyPI half: after Phase 105 rewrites README.md, rebuild (`rm -rf dist && uv build`), re-present the manifest, upload with explicit filenames on approval, then verify in a fresh venv per this plan's Task 3 "upload" branch.

## Self-Check: PASSED
