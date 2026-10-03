---
phase: 104-package-and-cli
verified: 2026-10-03T00:00:00Z
status: human_needed
score: 4/5 must-haves verified (PKG-01 pyproject half verified; PyPI-upload half deferred by recorded user decision)
overrides_applied: 0
deferred:
  - truth: "A user can `pip install ailsa` from PyPI and get the real package (PKG-01, PyPI-upload half)"
    addressed_in: "Phase 105 (then a follow-up upload action, not a numbered phase)"
    evidence: "104-06-SUMMARY.md: 'PyPI upload deferred by user decision on 2026-10-03. Reason: the PyPI long description is README.md, which still presents the project as lucy-ng with `lucy` commands; README is rewritten in Phase 105 (docs), and the first public version number can never be reused. Upload after Phase 105.' ROADMAP.md Phase 105 goal: 'README, docs/, CLAUDE.md ... present the project as AILSA.' REQUIREMENTS.md PKG-01 annotation confirms the same deferral explicitly, dated 2026-10-03."
human_verification:
  - test: "Decide whether to proceed to Phase 105 with PKG-01's PyPI-upload half still open, or treat it as a phase-104 blocker requiring immediate upload."
    expected: "A deliberate decision, not a default. The pyproject.toml/package-identity half of PKG-01 is done and verified; only the `pip install ailsa` live-PyPI half is pending, by the user's own 2026-10-03 decision to wait for the Phase 105 README rewrite (the PyPI long description is the README, and the first published version number cannot be reused, so uploading now would publish a page that still says lucy-ng)."
    why_human: "This is a scheduling/release decision already made by the user in-session, not a code defect discoverable by grep. The verifier cannot upload to PyPI (and must not), so it can only confirm the artifacts are built and twine-verified, and surface the pending decision for the record."
---

# Phase 104: Package and CLI Verification Report

**Phase Goal:** PyPI package `ailsa`, module `ailsa` replacing `lucy_ng`, CLI `ailsa` with `lucy` kept as a deprecated alias for one release; full suite/mypy/ruff green on the renamed tree (green = no regression against the recorded pre-rename baseline in baseline/BASELINE.md).
**Verified:** 2026-10-03
**Status:** human_needed (all automated truths verified live against the codebase; one item — the PyPI upload itself — is a recorded, intentional deferral, not a gap, but still needs to be on the record as an open action before milestone close)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pyproject.toml` names the project `ailsa`; module `ailsa` exists and is importable; no `lucy_ng` module/import remains in `src/`, `tests/`, `scripts/` (PKG-01 pyproject half + PKG-02) | ✓ VERIFIED | `pyproject.toml` line 6: `name = "ailsa"`. `src/ailsa/` exists (confirmed via `ls`), `src/lucy_ng` does not exist. `python3 -c "import ailsa"` resolves to `src/ailsa/__init__.py` (both via `uv run` and the global miniconda interpreter). `grep -rn "lucy_ng" src/ tests/ scripts/ pyproject.toml` → 0 matches (run live, not from SUMMARY). `pip show ailsa` reports version 0.1.0, editable at this repo; `pip show lucy-ng` reports "not found". |
| 2 | `pip install ailsa` from PyPI gives the real package (PKG-01 PyPI-upload half) | ⚠ DEFERRED (recorded user decision, not a code gap) | `104-06-SUMMARY.md`: wheel + sdist built (`ailsa-0.1.0-py3-none-any.whl`, `ailsa-0.1.0.tar.gz`), both `twine check` PASSED, contents scoped correctly (confirmed consistent with `pyproject.toml`'s sdist include list and wheel `packages = ["src/ailsa"]`). Nothing was uploaded — PyPI still reports only `0.0.1` (unverified independently here since checking PyPI is a network call the verifier does not need to make to confirm the deferral; the SUMMARY's own stated pending state is corroborated by REQUIREMENTS.md's PKG-01 checkbox annotation and ROADMAP's Phase 105 scope, both dated 2026-10-03). This is the single knowingly-incomplete item in the phase, by explicit user instruction, not an executor gap. |
| 3 | Every subcommand runs as `ailsa …`; `lucy …` still works for one release and prints a one-line deprecation hint pointing at `ailsa`, stderr-only, stdout byte-identical (PKG-03) | ✓ VERIFIED | Live run: `ailsa --help` lists all subcommands. `lucy detect hhb C10H14O2 --format json` and `ailsa detect hhb C10H14O2 --format json` produce byte-identical stdout (`cmp` exit 0) and both match the Plan 01 pre-rename golden file (`diff` empty). `lucy`'s stderr (and only stderr) carries exactly: "Warning: \`lucy\` is deprecated and will be removed in the next release; use \`ailsa\` instead." `pyproject.toml` `[project.scripts]`: `ailsa = "ailsa.cli:cli"`, `lucy = "ailsa.cli:lucy_deprecated"`. |
| 4 | The full test suite passes on the renamed tree with the same pass count as before the rename, and `mypy --strict`/`ruff` report no new findings beyond the recorded pre-rename baseline (PKG-04) | ✓ VERIFIED | Live re-run (not trusted from SUMMARY): quick pytest suite → `74 failed, 1372 passed, 86 skipped, 1 deselected, 1 xfailed` (baseline was `74 failed / 1344 passed / 86 skipped` — the +28 passed are new tests added by Plans 03/04, not baseline tests going green). `comm -13 baseline/pytest-failed.txt <live-failed-list>` → **empty** (zero new failures) and `comm -23` also empty (zero pre-existing failures silently disappeared/skipped). `mypy src/ailsa` → 33 errors, exact count match, normalised `comm -13` against baseline → **empty**. `ruff check src tests` → 278 findings (baseline 282); normalised `comm -13` → 4 lines, all in `tests/test_inventory_schema.py`/`tests/test_lsd_orchestrator.py`, confirmed via `git diff 9b1091d` to be E501 line-length findings that merely shifted length because `lucy_ng.*` (8 chars) shortened to `ailsa.*` (5 chars) on the same already-over-limit lines — not a new code-quality regression, matches the documented and independently re-derived explanation in 104-02-SUMMARY.md. |
| 5 | A user with the existing `data/reference/lucy-ng-derep.db` file keeps working; `ailsa database download`/`info` (and the fragments DB) accept the old filename as well as the new default (PKG-05) | ✓ VERIFIED | Live run against the real ~4 GB legacy file on this machine (no mocks): `ailsa database info` (no args) → "Database: data/reference/lucy-ng-derep.db", 928,443 compounds, correct source breakdown. `ailsa database download` → "Database already exists: data/reference/lucy-ng-derep.db" with zero network access. `ailsa fragment info` → "Fragment database: data/reference/lucy-ng-fragments.db", correct SSC count. `src/ailsa/database/finder.py` has `NEW_DB_NAME`/`LEGACY_DB_NAME` and a `resolve_default_derep_path()` tried-new-then-legacy resolver across all 5 search tiers. |

**Score:** 4/5 truths fully verified live; 1/5 (PyPI-upload half of PKG-01) is a recorded, deliberate, in-scope deferral — not a silent gap, but not yet closed either.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ailsa/` | Renamed package tree, 126 files | ✓ VERIFIED | `git mv` confirmed via `git log` (`2ffb0cf refactor(104-02)`); directory exists, `src/lucy_ng` absent |
| `pyproject.toml` | `name = "ailsa"`, scripts, sdist/wheel targets | ✓ VERIFIED | `name = "ailsa"`; `[project.scripts]` has both entries; `[tool.hatch.build.targets.wheel] packages = ["src/ailsa"]`; `[tool.mypy] packages = ["ailsa"]` |
| `src/ailsa/cli/main.py` (`lucy_deprecated`) | Deprecated alias function | ✓ VERIFIED | `def lucy_deprecated` at line 81; stderr-only warning, delegates to `cli.main(prog_name="lucy")` |
| `src/ailsa/webview/server.py` (`_build_launcher`) | Launcher prefers `ailsa`, never falls back to stale `lucy` | ✓ VERIFIED | Function present, 2-tier (ailsa on PATH → `python -m ailsa.cli`), documented deviation from research's 3-tier proposal (deliberate, explained in 104-03-SUMMARY.md) |
| `src/ailsa/database/finder.py` | Dual-filename resolver for derep DB | ✓ VERIFIED | `NEW_DB_NAME`/`LEGACY_DB_NAME`/`resolve_default_derep_path()` present and exercised live against the real file |
| `src/ailsa/cli/fragment.py` | Dual-filename resolver for fragments DB | ✓ VERIFIED (narrower scope — see WARNING below) | `resolve_default_fragments_db()` present, works live against the real file, but only checks `data/reference/`, not the other 4 tiers `DatabaseFinder` checks for the derep DB |
| `src/ailsa/identity.py` | Import-fallback candidate list widened | ✓ VERIFIED (precedence defect in an untested, `pragma: no cover` branch — see WARNING below) | Fallback present; Dropbox-tier loop nesting inverted relative to `DatabaseFinder`'s own tier 5 |
| `baseline/BASELINE.md` + 6 sibling files | Diffable pre-rename baseline | ✓ VERIFIED | All 7 files present, non-empty, `PHASE_START_SHA`/`UV_LOCK_DISPOSITION`/`SLOW_TEST` lines present; golden JSON files still byte-match live output |
| `dist/ailsa-0.1.0-py3-none-any.whl`, `dist/ailsa-0.1.0.tar.gz` | Release artifacts (gitignored) | ✓ VERIFIED (per 104-06-SUMMARY.md; `dist/` is gitignored so not independently re-checked on disk — not required, since the artifacts are reproducible via `uv build` and the metadata/content claims were cross-checked against `pyproject.toml`) | twine check PASSED per SUMMARY; sdist/wheel content list consistent with the `pyproject.toml` include/packages config verified above |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `ailsa`/`lucy` console scripts | `src/ailsa/cli/main.py` | `[project.scripts]` entry points | ✓ WIRED | Both scripts on PATH, both resolve to `ailsa.cli` functions, confirmed by reading the installed `/opt/miniconda3/bin/{ailsa,lucy}` wrapper scripts live |
| `ailsa database {info,download}` | `DatabaseFinder.resolve_default_derep_path()` | Click `ParameterSource.DEFAULT` check | ✓ WIRED | Live run against real ~4 GB file resolves correctly with zero args |
| `ailsa fragment {info,search,build}` | `resolve_default_fragments_db()` (fragment.py-local, not `DatabaseFinder`) | Same `ParameterSource.DEFAULT` pattern | ⚠️ PARTIAL | `info` is tested and live-verified; `search`/`build` share the identical code path but have no test coverage (104-REVIEW.md IN-02, confirmed still present) — functionally wired, not test-proven for 2 of 3 commands |
| `webview.server._build_launcher` | `ailsa` console script | `shutil.which("ailsa")` | ✓ WIRED | Function + tests present (`tests/test_webview_launcher.py`) |

### Data-Flow Trace (Level 4)

Not applicable in the dynamic-rendering sense (no UI component); the equivalent check here is "does the renamed CLI actually talk to the real, unmoved ~4 GB database file end-to-end" — confirmed live above (database info/download/fragment info all produced real, non-stub, non-empty output from the actual file on disk).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `ailsa` module imports | `uv run python3 -c "import ailsa; print(ailsa.__file__)"` | `/Users/steinbeck/Dropbox/develop/lucy-ng/src/ailsa/__init__.py` | ✓ PASS |
| `ailsa`/`lucy` stdout byte-identity | `cmp` of `ailsa detect hhb ...` vs `lucy detect hhb ...` vs Plan 01 golden file | All three identical | ✓ PASS |
| `lucy` deprecation hint is stderr-only | `lucy detect hhb C10H14O2 --format json 2>&1 1>/dev/null` | Exactly one warning line | ✓ PASS |
| No `lucy_ng` string remains in `src/`, `tests/`, `scripts/` | `grep -rn "lucy_ng" src/ tests/ scripts/ pyproject.toml` | 0 matches | ✓ PASS |
| `database info`/`download`/`fragment info` resolve the real legacy-named files with zero args | Direct CLI run from repo root | All three correct, real data | ✓ PASS |
| Full quick pytest suite matches baseline exactly (no new failures, no new passes-that-were-failures) | `uv run --extra dev pytest -q ... -rfE` + `comm -13`/`comm -23` against `baseline/pytest-failed.txt` | 74/1372/86, both `comm` diffs empty | ✓ PASS |
| `mypy src/ailsa` matches baseline count and normalised finding set | `uv run --extra dev mypy src/ailsa` + `comm -13` | 33 errors, empty diff | ✓ PASS |
| `ruff check src tests` matches baseline (±4 explained shrinking-line false positives) | `uv run --extra dev ruff check src tests` + `comm -13` | 278 findings, 4-line diff explained by rename-induced line-length shift, confirmed via `git diff` | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention in this repo and no probe files declared in the 104-0*-PLAN.md files. Step 7c: SKIPPED (no runnable probe scripts for this phase; the regression gate above fills the equivalent role and was run live, not taken from SUMMARY).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PKG-01 | 104-02, 104-05, 104-06 | `pip install ailsa` gives the real package; `pyproject.toml` names the project `ailsa` | ⚠ PARTIAL (pyproject half SATISFIED, PyPI-upload half DEFERRED by recorded user decision) | See Truth #1/#2 above |
| PKG-02 | 104-02 | No `lucy_ng` module/import in `src/`, `tests/`, `scripts/` | ✓ SATISFIED | Live grep, 0 matches; `src/lucy_ng` absent. (Note: REQUIREMENTS.md's checkbox for PKG-02 is still `[ ]` — a stale tracking artifact, not a code gap; see Gaps Summary.) |
| PKG-03 | 104-03, 104-05 | `ailsa …` works; `lucy …` works + stderr-only deprecation hint | ✓ SATISFIED | Live byte-identity + stderr-only check |
| PKG-04 | 104-01, 104-02, 104-05 | Same pass count as before; no new mypy/ruff findings | ✓ SATISFIED | Live re-run, exact `comm -13`/`comm -23` match |
| PKG-05 | 104-04 | Legacy DB filename keeps working | ✓ SATISFIED | Live run against the real ~4 GB file |

All 5 requirement IDs declared for Phase 104 in REQUIREMENTS.md's traceability table (PKG-01..05) appear in at least one plan's `requirements:` frontmatter (104-01: PKG-04; 104-02: PKG-01/02/04; 104-03: PKG-03; 104-04: PKG-05; 104-05: PKG-01/03/04; 104-06: PKG-01). No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/ailsa/cli/nus.py` | 1 | Module docstring still reads `"""Lucy NUS ...` (capitalized leftover, mechanical rename regex missed capitalized prose form) | ℹ️ Info | Cosmetic only; confirmed still present live (104-REVIEW.md IN-01, independently re-confirmed) |
| `src/ailsa/cli/webview.py` | 1 | Module docstring still reads `"""Lucy webview ...` | ℹ️ Info | Cosmetic only; same as above |
| `src/ailsa/identity.py` | 62-74 | Dual-filename precedence loop nesting inverted relative to `DatabaseFinder`'s own tier 5, inside an untested `# pragma: no cover` import-failure fallback branch | ⚠ Warning | Confirmed present live (104-REVIEW.md WR-01, independently re-confirmed by reading the code). Only reachable if `ailsa.database.finder` itself fails to import; does not affect the verified real-machine behavior (Truth #5) |
| `src/ailsa/cli/fragment.py` | 16-36 | Hand-rolled dual-filename resolver narrower than `DatabaseFinder` (only checks `data/reference/`, not the other 4 search tiers) | ⚠ Warning | Confirmed present live (104-REVIEW.md WR-02, independently re-confirmed). Works correctly for the real file on this machine (the common case) but would miss a legacy fragments DB stored in `~/.lucy/` or similar, unlike the derep-DB path |
| `tests/test_cli_database.py` | 296-320 | `fragment search`/`fragment build` dual-filename branches share code with `fragment info` but have no dedicated test | ℹ️ Info | Confirmed still true (104-REVIEW.md IN-02) |
| No TBD/FIXME/XXX debt markers found | — | — | — | `grep -nE "TBD\|FIXME\|XXX"` across all phase-104-modified files returned only false-positive matches inside pre-existing test fixture strings (`"not_a_real_smiles_XXXX"`), not actual debt markers |

None of these anti-patterns are classified as Blocker: the code review (104-REVIEW.md) itself rated them Warning/Info, and live re-verification confirms the primary, documented, common-case behavior (real ~4 GB database file resolution) works correctly end-to-end. They are carried forward here as Warnings for the record, not re-litigated as new Blockers.

### Human Verification Required

### 1. PKG-01 PyPI-upload decision is on the record, not yet closed

**Test:** Confirm with the user whether Phase 104 should be considered "done enough" to proceed to Phase 105 with the PyPI upload still pending, or whether the upload should happen now before moving on.
**Expected:** A deliberate choice already made in-session on 2026-10-03 (defer until after the Phase 105 README rewrite, because the PyPI long description is the README and the first published version number can never be reused) — this verification surfaces it so the choice is visible in the phase's audit trail rather than silently carried forward.
**Why human:** This is a release-sequencing decision, not a code defect. The verifier must not upload to PyPI and cannot grep for "has the user decided this is OK" — the decision itself is the artifact needing acknowledgement.

## Gaps Summary

No code-level gaps were found. Every must-have truth derived from the phase goal and from ROADMAP.md's 5 success criteria was independently re-verified against the live codebase (not trusted from SUMMARY.md): the module rename is complete and clean, the deprecated `lucy` alias is byte-identical on stdout and warns only on stderr, the full regression gate (pytest/mypy/ruff) matches the recorded pre-rename baseline exactly with zero new findings, and the legacy database filename keeps working end-to-end against the real multi-gigabyte file on this machine.

The one open item — the PyPI-upload half of PKG-01 — is not a gap in the adversarial sense: artifacts are built, `twine check` PASSED, and the non-upload is an explicit, dated, reasoned user decision recorded in `104-06-SUMMARY.md` and mirrored in `REQUIREMENTS.md`'s PKG-01 annotation. It is correctly modeled here as `deferred` + a human-verification acknowledgement rather than a `gaps_found` item, because closing it is a scheduling action (upload after Phase 105), not an engineering task.

One documentation-tracking inconsistency worth flagging for cleanup (not blocking): `REQUIREMENTS.md`'s checkbox for **PKG-02** is still `[ ]` even though the underlying requirement ("no `lucy_ng` module or import remains in `src/`, `tests/`, `scripts/`") is fully satisfied and was independently re-verified live in this report. This looks like a bookkeeping gap in the requirements-tracking file, not a code gap — the next phase or a quick doc fix should flip that checkbox to `[x]`.

The two code-review Warnings (WR-01 identity.py fallback precedence inversion in an untested pragma-no-cover branch; WR-02 fragment.py's narrower hand-rolled dual-filename resolver) remain open and are carried forward here for visibility, matching 104-REVIEW.md's own non-Blocker classification.

---

_Verified: 2026-10-03_
_Verifier: Claude (gsd-verifier)_
