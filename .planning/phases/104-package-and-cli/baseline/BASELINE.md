# Phase 104 Pre-Rename Baseline

Captured 2026-10-03, before any rename edit (PKG-01..05). This directory is the diffable
reference every later 104-* plan compares against to prove "same pass count as before" and
"no new findings" (PKG-04), and "byte-identical `--format json` stdout" (D-04 cross-reference
in the plan context).

## Headline facts

```
PHASE_START_SHA: 9b1091ddb228fa2c51f8d8bb8daa7a6c6f0486e8
UV_LOCK_DISPOSITION: committed 9b1091ddb228fa2c51f8d8bb8daa7a6c6f0486e8
SLOW_TEST: passed
```

`PHASE_START_SHA` is the commit created by Task 1 of this plan (the standalone `build(lock)`
commit) — it is the first commit where `uv.lock` is clean and `uv lock --check` passes, and
the true starting point for every rename edit in Plans 02-05.

## Task 1 — uv.lock disposition

Per D-06, the pre-existing dirty `uv.lock` (558 insertions / 1 deletion, working tree at plan
start) was verified to be pure catch-up for the `dev`/`webview`/`nus` extras already declared
in `pyproject.toml`, not an unrelated or suspicious change:

- `git show HEAD:uv.lock` (the committed version at phase start) followed by `uv lock --check`
  exited **1** (stale) — confirming the committed lock did not match the committed
  `pyproject.toml`.
- Restoring the working-tree (dirty) `uv.lock` and running `uv lock --check` exited **0**
  (consistent).
- `git diff uv.lock | grep '^-' | grep -v '^---'` showed exactly one removed line:
  `provides-extras = ["dev", "prediction", "webview"]` — a metadata line, not a removed
  `[[package]]` block.

All three expectations held, so `uv.lock` was committed alone:
`build(lock): sync uv.lock with the dev/webview/nus extras already declared in pyproject.toml`
(commit `9b1091d`). `git show --stat` for that commit lists exactly one file, `uv.lock`.

## Task 2 — pytest (quick suite)

Command: `uv run --extra dev pytest -q -p no:cacheprovider -k "not test_import_coconut_real" -rfE`

```
= 74 failed, 1344 passed, 86 skipped, 1 deselected, 1 xfailed, 12 warnings in 76.79s (0:01:16) =
```

Matches the research/validation baseline exactly (74 failed / 1344 passed / 86 skipped / 1
deselected / 1 xfailed). `baseline/pytest-failed.txt` holds the 74 sorted, deduplicated
failing node IDs (no " - <reason>" suffix) for the `comm -13` regression check in Plans 02-05.

`wc -l < baseline/pytest-failed.txt` = 74, matching the "74 failed" count in
`baseline/pytest-summary.txt` exactly.

## Task 2 — slow real-data test

**Plan correction (Rule 1 — blocking bug):** The plan names the test class
`TestDatabaseImporter::test_import_coconut_real`. That class/method pairing does not exist —
`test_import_coconut_real` is defined on `TestDatabaseImporterIntegration`
(`tests/test_database_importer.py` line 288), a different class in the same file. Running the
plan's literal node ID collects 0 tests (pytest exit 4, "ERROR: not found"). Corrected to
`tests/test_database_importer.py::TestDatabaseImporterIntegration::test_import_coconut_real`
and re-run; the real `data/reference/predicted_coconut.sdf` (4.74 GB) is present on this
machine, so the test ran for real (not skipped). Result: `1 passed in 307.88s (0:05:07)`.

```
SLOW_TEST: passed
```

## Task 2 — mypy

Command: `uv run --extra dev mypy src/lucy_ng 2>&1 | grep ' error: ' | sort`

33 errors, matching the expected baseline exactly. Stored at `baseline/mypy.txt`.

## Task 2 — ruff

Command: `uv run --extra dev ruff check src tests --output-format concise 2>&1 | grep -E '^[a-z].*:[0-9]+:[0-9]+: ' | sort`

282 errors, matching the expected baseline exactly. Stored at `baseline/ruff.txt`.

## Task 2 — golden stdout (D-04 cross-reference)

Two database-backed commands, run from the repo root, stdout captured with stderr discarded:

- `uv run lucy detect hhb C10H14O2 --format json` → `baseline/golden-detect-hhb-C10H14O2.json`
- `uv run lucy identify --smiles CCO --format json` → `baseline/golden-identify-CCO.json`

Both inputs are intentionally neutral (a bare formula; ethanol) — no benchmark compound
appears in either file (D-05). Both parse as valid JSON (`python3 -m json.tool` exit 0 for
both). Both commands were run a second time and `cmp`'d byte-for-byte against the stored
file — both are deterministic (`DETECT_DETERMINISTIC`, `IDENTIFY_DETERMINISTIC`), so later
plans can gate on exact byte identity, not just JSON-equivalence.

## Global install (to be reinstalled in Plan 05)

`/opt/miniconda3/bin/pip show lucy-ng | head -12`:

```
Name: lucy-ng
Version: 0.1.0
Summary: AI-agent powered Computer-Assisted Structure Elucidation for organic natural products
Home-page:
Author: Christoph Steinbeck
Author-email:
License:
Location: /opt/miniconda3/lib/python3.12/site-packages
Editable project location: /Users/steinbeck/Dropbox/develop/lucy-ng
Requires: click, jsonschema, nmrglue, numpy, pydantic, rdkit, requests, scipy, tqdm
Required-by:
```

`head -6 /opt/miniconda3/bin/lucy`:

```
#!/opt/miniconda3/bin/python
# -*- coding: utf-8 -*-
import re
import sys
from lucy_ng.cli import cli
if __name__ == '__main__':
```

This global editable install points at `lucy_ng` and will break the moment `src/lucy_ng` is
renamed to `src/ailsa` — expected, and explicitly Plan 05's job to reinstall under the new
name.

## Identity leak check (D-05, acceptance criterion)

Name list built at runtime from the gitignored `.planning/CASE-DATASET-IDENTITIES.md` (never
written into a tracked file):

```
grep -oE '\*\*[^*]+\*\*' .planning/CASE-DATASET-IDENTITIES.md | tr -d '*' | sort -u > SCRATCH/identity-names.txt
grep -ciF -f SCRATCH/identity-names.txt baseline/*
```

Result: `pytest-failed.txt` matched **6** lines; every other baseline file matched 0.

**Reviewed, not a leak.** The 6 matches are all `ibuprofen`/`pulegone`, from
`tests/test_ranking.py`'s own pre-existing parametrize IDs (`ibuprofen_db`, `pulegone_db` —
see lines 1299-1401 of that file, committed since Phase 86 / v9.1). `pytest-failed.txt`
reproduces failing test node IDs verbatim; it does not introduce these strings, they are
already literal, tracked, public source in this repository. Both names are also already
public throughout many other tracked files (`PROJECT.md`, `README.md`,
`docs/infographics/*`, `.planning/milestones/*`) — ibuprofen is CASE1 and pulegone is CASE3,
both long-validated, non-blind members of the original CASE1-9 test set (distinct from the
blind benchmark dataset that `CASE-DATASET-IDENTITIES.md` otherwise protects). No redaction
applied — redacting would break the exact node-ID fidelity the `comm -13` comparison in
Plans 02-05 depends on, for strings that carry zero incremental disclosure risk.

## Comparison recipe (for Plans 02-05)

**pytest:** regenerate `<new-failed>` the same way (`grep -E '^(FAILED|ERROR) ' <log> | sed
-E 's/^(FAILED|ERROR) //' | sed -E 's/ - .*$//' | sort -u`), then:

```
comm -13 baseline/pytest-failed.txt <new-failed>
```

must be empty — no node ID may fail after the rename that did not already fail before it.

**mypy / ruff:** raw line-for-line baseline/new diffs will never match because every path and
module name literally changes (`src/lucy_ng` → `src/ailsa`, `lucy_ng` → `ailsa`). Normalise
both sides with the same transform before comparing:

```
sed -e 's#src/lucy_ng#src/ailsa#g' -e 's/lucy_ng/ailsa/g' -E -e 's/:[0-9]+:([0-9]+:)? /: /' <file>
```

Apply to **both** the baseline file and the new tool output, then:

```
comm -13 <mapped-baseline> <mapped-new>
```

must be empty — no new finding line beyond what the baseline already had, once path/module
renaming and line-number drift are normalised away.

**Golden JSON:** the dual-filename DB resolver change (PKG-05) and the module rename must not
change these two commands' stdout at all. Re-run both exact commands after each relevant plan
and `cmp` the fresh output against `baseline/golden-detect-hhb-C10H14O2.json` /
`baseline/golden-identify-CCO.json` — any difference is a regression, not an improvement, and
must be explained before proceeding.
