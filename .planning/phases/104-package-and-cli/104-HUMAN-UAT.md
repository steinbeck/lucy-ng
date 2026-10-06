---
status: partial
phase: 104-package-and-cli
source: [104-VERIFICATION.md]
started: 2026-10-03T13:35:41Z
updated: 2026-10-03T13:35:41Z
---

## Current Test

[awaiting PyPI upload after Phase 107 — moved 2026-10-06, see 105-CONTEXT.md D-05]

## Tests

### 1. ailsa published on PyPI after the README rewrite (PKG-01, PyPI half)
expected: After Phase 107 (repo renamed; README rewritten in 105), rebuild (`rm -rf dist && uv build`), re-present the manifest for approval, upload with explicit filenames, then in a fresh venv `pip install ailsa==<version>` gives a working `ailsa`, `lucy` warns once on stderr, `import ailsa` reports the version and `import lucy_ng` fails (104-06-PLAN.md Task 3, "upload" branch).
result: [pending — deferred by user decision 2026-10-03; proceeding to Phase 105 with this item open was the user's explicit choice]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
