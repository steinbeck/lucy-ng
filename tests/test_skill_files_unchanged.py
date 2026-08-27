"""Byte-unchanged guard for `case.md` and the 5-agent CASE team (Phase 102,
Plan 04, JCLI-02 / ROADMAP Phase-102 success criterion 4).

WHY THIS EXISTS: Phase 102's whole design is "reuse the Phase-99 bridge and
QC gate UNCHANGED" -- and the same invariant extends to the autonomous CASE
orchestrator itself. `case.md` and the five `lucy-*.md` agent files are the
highest-value tamper target in this repo: they are the instructions an
autonomous agent team executes (see this plan's `<threat_model>`, T-102-10).
Before this file, that guarantee was verifiable only by trust -- a full
search of the whole `tests/` tree (grep for the alternation of "sha256",
"hashlib" and "git diff" across every test file) found NO prior committed
pytest test that asserts `case.md` or any
`.claude/agents/lucy-*.md` file is byte-unchanged. `tests/test_case_md_wv07.py`
is a different kind of test entirely -- a substring CONTENT-CONTRACT check
(asserts specific phrases are present/absent), not a byte-equality check.
This is the repo's FIRST committed byte-unchanged test.

WHY A HASH TABLE, NOT `git diff --exit-code <ref>`: content hashing needs no
git subprocess call and is immune to shallow-clone / history-rewrite
concerns (a `git diff` against a ref that has been squashed, rebased, or is
missing from a shallow CI checkout would fail confusingly for reasons
unrelated to the files' actual content). A frozen SHA-256 table is simpler
and self-contained -- exactly the same call `102-RESEARCH.md` Pitfall 5
recommends and computed the baseline for.

UPDATING THE BASELINE (deliberate, reviewed decision only): if a future
phase LEGITIMATELY changes `case.md` or an agent file (in-scope, reviewed,
documented in that phase's SUMMARY), recompute the new hash with
``shasum -a 256 <path>`` for every changed file and update
`EXPECTED_SHA256` below in the SAME commit that changes the source file.
This is NOT a bug to silently work around by deleting or loosening this
test -- a failure here means the file changed, and the fix is either (a)
revert the unintended edit, or (b) update the baseline as an explicit part
of a phase whose scope includes changing the CASE orchestrator, recorded in
that phase's SUMMARY.

WHAT IS DELIBERATELY *NOT* FROZEN HERE: `src/lucy_ng/nus/qc.py`,
`nus/bridge.py`, `cli/pick.py`, and the two pickers
(`processing/peak_picker.py`, `processing/peak_picker_2d.py`) are
byte-unchanged for THIS PHASE ONLY, already verified by the
`git diff --exit-code 22f2b52 -- ...` acceptance gates baked into every
plan of Phase 102 (102-01/02/03/04) -- they are legitimately expected to
change in some FUTURE phase (e.g. a new peak-pick algorithm), and freezing
them by a committed hash table here would make that future, in-scope edit
fail this test confusingly. `case.md` and the 5-agent team are different:
they are not expected to change as a SIDE EFFECT of routine feature work at
all, which is exactly why a hard, committed freeze is appropriate for them
specifically.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

# Resolved from this test file's own location, NOT the process cwd -- unlike
# tests/test_case_md_wv07.py's bare `Path(".claude/...")` (which silently
# depends on pytest being launched from the repo root), this makes the test
# pass regardless of the invoking working directory.
REPO_ROOT = Path(__file__).resolve().parents[1]

CASE_MD_PATH = ".claude/commands/lucy-ng/case.md"

#: Frozen baseline, verified 2026-07-25 at commit `22f2b52` (Phase-101 close,
#: clean working tree) via `shasum -a 256 <path>` -- reproduced verbatim
#: from 102-RESEARCH.md Pitfall 5 / this plan's `<interfaces>` block, and
#: RE-VERIFIED live against this worktree's checkout before writing this
#: test (identical).
#: BASELINE UPDATED 2026-08-07: the five agent files lost their
#: `model: claude-opus-4-8` frontmatter pin. The pin bit on any machine
#: without `CLAUDE_CODE_SUBAGENT_MODEL=inherit` in settings.json -- Sheldon
#: has none, so a benchmark orchestrator on Opus 5 was spawning the whole
#: specialist team on 4.8. Omitting `model:` makes each agent inherit the
#: parent session's model, which is the same on every host. `case.md` is
#: unchanged; only the five agent hashes move.
#: BASELINE UPDATED 2026-08-27 (retroactive): `d62d833` (2026-08-09,
#: "docs(skill): heteroatom protons need their own HSQC line or LSD aborts")
#: added the HETEROATOM-PROTON rule to `lucy-lsd-engineer.md` and
#: `lucy-devils-advocate.md` (+28/-1 lines) but did NOT refresh this table in
#: the same commit, as the procedure above requires. This guard therefore
#: failed for those two files for 18 days. The edit itself was deliberate and
#: is substantively correct -- any proton used as the H-side of an HMBC line
#: needs its own `HSQC X X` declaration or LSD aborts, verified against the
#: solver's own `hestvalide` check (CASE96, 2026-08-09) -- so the resolution
#: is (b) update the baseline, not (a) revert. Approved by the user on
#: 2026-08-27. `case.md` and the other three agent files still match the
#: 2026-08-07 baseline exactly, so the drift is fully accounted for by
#: `d62d833` and nothing else.
#:
#: NOTE FOR THE BENCHMARK: `d62d833` landed mid-campaign, so the blind CASE
#: runs in `case-uat-results-opus5-rest/` span two skill states. That mixed
#: provenance was accepted deliberately (see `.planning/STATE.md`
#: "Key Decisions (2026-08)"); this red guard was its earliest machine-readable
#: trace and went unnoticed.
EXPECTED_SHA256: dict[str, str] = {
    CASE_MD_PATH: "8299791ead74294fa31424bae990de62d7bf73260d5dbdbe1e776539e7148d8b",
    ".claude/agents/lucy-nmr-chemist.md": (
        "c643b44d3e49bcd7eb0de0125fca051f9c59cf9b1ceff1906143d39d9bdca19e"
    ),
    ".claude/agents/lucy-lsd-engineer.md": (
        "d482f7b4618f1f50a8febdfa09384a2160231a6a3e1bc743039bc42220d0a401"
    ),
    ".claude/agents/lucy-solution-analyst.md": (
        "8fd09a57e0826b3f0dcb574094491d60c1e3997fd44d09509eb7fa91fc5e96c8"
    ),
    ".claude/agents/lucy-devils-advocate.md": (
        "1745718828c147dd7d28a2c7c9f1c0a6d18f65f1adf06b98568daf09eaa86247"
    ),
    ".claude/agents/lucy-diagnostic.md": (
        "41cf15d781dde1a8daaf828ba6d296e61bd4eb0a663f42d4572278b8f49a07cb"
    ),
}

#: Exactly the five `lucy-*.md` agent files that make up "the 5-agent CASE
#: team" per CLAUDE.md's own "CASE skill location" section
#: (`lucy-nmr-chemist`, `lucy-lsd-engineer`, `lucy-solution-analyst`,
#: `lucy-devils-advocate` spawned by `case.md`, plus `lucy-diagnostic` on
#: escalation only). `.claude/agents/supervisor.md` ALSO exists in this
#: repo but is DELIBERATELY EXCLUDED here: it is not named as part of "the
#: 5-agent team" by CLAUDE.md's roster or by 102-CONTEXT.md's own list
#: (102-RESEARCH.md Assumption A2) -- the `lucy-*.md` glob pattern below is
#: what makes that exclusion explicit and structural rather than an
#: accidental omission from a hand-maintained list.
EXPECTED_AGENT_FILES: tuple[str, ...] = (
    "lucy-devils-advocate.md",
    "lucy-diagnostic.md",
    "lucy-lsd-engineer.md",
    "lucy-nmr-chemist.md",
    "lucy-solution-analyst.md",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("relative_path,expected_hash", sorted(EXPECTED_SHA256.items()))
def test_skill_files_are_byte_unchanged(relative_path: str, expected_hash: str) -> None:
    """`case.md` and the five agent files must be byte-identical to the
    frozen Phase-101-close baseline.

    A failure here means one of these files changed. This is NOT
    automatically a bug: either (a) the edit was unintended -- revert it,
    or (b) a later phase DELIBERATELY changed the CASE orchestrator as part
    of its own reviewed scope -- in which case recompute the new hash with
    `shasum -a 256 <path>` and update `EXPECTED_SHA256` above in the SAME
    commit, and record the deliberate change in that phase's SUMMARY.md.
    Never "fix" this test by deleting the assertion or loosening the hash
    comparison.
    """
    path = REPO_ROOT / relative_path
    assert path.exists(), f"missing skill file: {relative_path}"
    actual_hash = _sha256(path)
    assert actual_hash == expected_hash, (
        f"{relative_path} has changed since the Phase-101-close baseline "
        f"(expected sha256={expected_hash}, got {actual_hash}). "
        "If this edit was unintended, revert it. If a later phase "
        "deliberately changed the CASE orchestrator/agent files as part of "
        "its own reviewed scope, update EXPECTED_SHA256 in this test file "
        "(shasum -a 256 <path>) in the same commit and record the decision "
        "in that phase's SUMMARY.md -- do not silently loosen this check."
    )


def test_agent_roster_is_complete() -> None:
    """Catches a NEWLY ADDED agent file that a pure hash table over known
    paths cannot detect on its own.

    Globs `.claude/agents/lucy-*.md` and asserts the sorted result equals
    exactly `EXPECTED_AGENT_FILES` -- five files. `.claude/agents/supervisor.md`
    exists in this repo but is deliberately excluded from the 5-agent team
    (it is not named by CLAUDE.md's roster or CONTEXT.md's list,
    102-RESEARCH.md Assumption A2); the `lucy-*.md` glob pattern itself is
    what makes that exclusion explicit and structural, not an accidental
    gap in a hand-maintained filename list.
    """
    agents_dir = REPO_ROOT / ".claude" / "agents"
    found = sorted(p.name for p in agents_dir.glob("lucy-*.md"))
    assert found == list(EXPECTED_AGENT_FILES), (
        f"the lucy-*.md agent roster changed: expected "
        f"{list(EXPECTED_AGENT_FILES)}, found {found}. A new agent file was "
        "either added or removed -- if added deliberately, decide whether "
        "it belongs to 'the 5-agent team' (CLAUDE.md roster) and, if so, "
        "add its frozen hash to EXPECTED_SHA256 and its name to "
        "EXPECTED_AGENT_FILES in the same commit."
    )
    # supervisor.md is expected to exist but never match the lucy-*.md glob
    # (documents the exclusion rather than leaving it silent).
    assert (agents_dir / "supervisor.md").exists(), (
        "supervisor.md is expected to exist in .claude/agents/ but is "
        "deliberately excluded from the 5-agent-team byte-unchanged guard"
    )
    assert "supervisor.md" not in found


def test_case_md_is_a_regular_readable_file() -> None:
    """A broken symlink or an empty file must fail loudly and clearly here,
    rather than surfacing as a confusing hash mismatch in the parametrized
    test above.
    """
    path = REPO_ROOT / CASE_MD_PATH
    assert path.exists(), f"missing: {CASE_MD_PATH}"
    assert path.is_file(), f"not a regular file: {CASE_MD_PATH}"
    content = path.read_bytes()
    assert content, f"{CASE_MD_PATH} is empty"
