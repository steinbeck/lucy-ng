# Phase 105: Documentation and outside face - Research

**Researched:** 2026-10-06
**Domain:** Documentation rename + accuracy audit (README, CLAUDE.md, docs/, infographic deck, figshare record, peripheral public-repo docs)
**Confidence:** HIGH for inventory/CLI-truth/figshare findings (all directly verified against the live repo and tool output). MEDIUM for the figshare versioning behaviour (official docs cross-verified but the two pages hedge slightly differently). LOW for nothing material — the one open item (MCP/architecture staleness) is a verified fact, not a guess, but the *decision* on how far to fix it is a scope question, not a research gap.

## Summary

This phase is smaller than it looks for the renaming part and bigger than it looks for the
accuracy part. The rename itself is mechanical: every occurrence of `lucy-ng` / `lucy_ng` /
`Lucy` / `/lucy-ng:` / `lucy-<agent>` / bare `lucy ` commands in the nine in-scope files is
inventoried below with file-level grouping so work can be split without overlap, and the
`ailsa` CLI (installed, version 0.1.0) was run directly to get ground truth for every command
name, subcommand, and flag the rewritten docs must match.

Two things turned up that are **not** about the name and will trip up a naive find-and-replace:

1. **`docs/USER_GUIDE.md` and `docs/ARCHITECTURE.md` both describe a three-interface
   architecture (CLI + Python API + MCP server/FastMCP) that no longer exists.** The MCP
   server was removed in v2.0 (CLI-only pivot, confirmed by this repo's own project memory and
   independently re-confirmed here: no `mcp` extra in `pyproject.toml`, no `mcp` module under
   `src/ailsa/`). `docs/INSTALLATION.md` still tells readers to `pip install "ailsa[mcp]..."`
   and run `lucy-mcp --help` — neither exists. This is pre-existing rot, not something the
   rename created, but a rename pass that doesn't touch it ships the "fresh start" docs with a
   fabricated feature. Flagged as an Open Question below — it is adjacent to but not strictly
   inside DOC-02's wording.
2. **Several README/USER_GUIDE command examples are already broken against the current CLI**,
   independent of naming: `ailsa pick hsqc` has no `--dept135` flag any more (DEPT-guided
   filtering moved to agent-side skill knowledge), and **`ailsa lsd generate` does not exist at
   all** (README's `lucy lsd generate data/Ibuprofen C13H18O2 -o ibuprofen.lsd` and
   `USER_GUIDE.md`'s `#### Generate LSD Input` section both document a dead command). The LSD
   subgroup today is `analyze | check | rank | run | validate-inventory` — no `generate`. The
   planner must verify every retained code example against `ailsa <group> <cmd> --help`
   individually, not trust the old prose; a few will need rewriting for accuracy, not just
   renaming.

The figshare question (D-09/D-10) has a definite answer: the "Manage files" action set on a
published item is edit / delete / **replace** / reorder — there is no in-place rename, so
changing the file's name requires a re-upload (new file, likely new ID), which is explicitly
out of scope. **D-10 resolves to: leave the file name exactly as it is** —
`lucy-ng-derep.db.zip` (not `.db.gz` as assumed in CONTEXT.md; verified live via the public API).
Editing the title **will** create a new version (title changes trigger versioning; description-only
edits do not); the base DOI `10.6084/m9.figshare.31073554` stays constant and keeps resolving to
the newest version, but the versioned DOI will tick from `.v2` to `.v3`. The current live record
(fetched, no token needed) shows title `"COCONUT rereplication database for use in lucy-ng"` and
a description that links `github.com/steinbeck/lucy-ng` — both need the D-09 draft text.

**Primary recommendation:** Treat this as two passes per file — a mechanical renaming pass
(the inventory below) and a short accuracy spot-check pass (verify every retained command/flag
against `ailsa --help`) — rather than one search-and-replace pass, because at least two files
(`INSTALLATION.md`, `ARCHITECTURE.md`) are stale in ways that predate the rename and a third
(`USER_GUIDE.md`) has a dead command example.

## Architectural Responsibility Map

Not applicable in the usual sense (no browser/server/API tiers here). Mapped instead to
documentation surfaces, since that is the unit of ownership the planner needs:

| Capability | Primary Owner | Secondary | Rationale |
|------------|---------------|-----------|-----------|
| Project identity / pitch | `README.md` | infographic deck slide 1 | README is read first (GitHub, PyPI long description); deck restates it visually |
| Agent-pipeline developer memory | `CLAUDE.md` | — | Loaded as Claude Code project memory inside the repo only |
| Technical architecture | `docs/ARCHITECTURE.md` | — | Needs rewrite beyond renaming (MCP-era content, see Summary) |
| Install/setup instructions | `docs/INSTALLATION.md`, `docs/SERVER_BOOTSTRAP.md` | `docs/NUS-PORTABILITY.md` | Split by audience: local dev vs. headless compute host vs. one optional backend |
| CLI/API reference | `docs/USER_GUIDE.md` | README's `lucy`-CLI table | USER_GUIDE is the detailed one; README's table must stay a summary, not drift from it |
| Evaluation claims | `docs/BENCHMARK.md` | README "Evaluation" section, deck benchmark slide (new, D-06) | BENCHMARK.md is explicitly the source of truth per D-06 — copy figures, never recompute |
| External data citation | figshare record (D-09/D-10), `scripts/figshare_upload.py`, `scripts/zenodo_upload.py` | — | Live record != script metadata (see Code Examples); don't assume they match today |
| Visual one-pager | `docs/infographics/build.py` → `deck.html` → PDF | — | Edit build.py only, per repo CLAUDE.md; never hand-edit deck.html |
| Non-core domain description | `scripts/faulon-bridge/README.md`, `rdmo-project-description.txt` | — | Small, self-contained, low risk |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** No "formerly lucy-ng" note anywhere. DOC-01 struck of that clause; now reads:
  README presents AILSA with the expansion and credits LSD/Nuzillard up front — nothing more.
- **D-02:** Lucy lineage removed entirely — delete README lines 21-22, the "original Lucy
  concept by Christoph Steinbeck" credit (~line 444), and the deck's slide-7 "Lineage" box
  (Lucy, "later acquired by Bruker"). Neither Lucy nor Bruker-as-acquirer appears anywhere
  outside-facing.
- **D-03:** Legacy compatibility is silent. Docs never mention the deprecated `lucy` alias or
  the legacy DB filename `lucy-ng-derep.db`. Show only `ailsa …` and `ailsa-derep.db`. Both
  legacy paths keep working in code; just undocumented. Applies to CLAUDE.md too.
- **D-04:** Docs use the final names now (pre-106/107): `/ailsa:case`, `/ailsa:dereplicate`,
  `/ailsa:predict`, `/ailsa:sanitise`, `/ailsa:status`; agents `ailsa-nmr-chemist`,
  `ailsa-lsd-engineer`, `ailsa-solution-analyst`, `ailsa-devils-advocate`, `ailsa-diagnostic`;
  paths `.claude/commands/ailsa/`, `.claude/agents/ailsa-*.md`; repo
  `https://github.com/steinbeck/ailsa`, clone dir `ailsa`. A few days of public mismatch is
  accepted. Each doc file touched once — 106/107 must not need to re-edit these docs.
- **D-05:** PyPI upload moves to after Phase 107, not right after 105. Update
  `104-HUMAN-UAT.md`'s pending item and the PKG-01 note in REQUIREMENTS.md.
- **D-06:** New benchmark slide in the deck: how the blind benchmark works, whole-benchmark
  rank-1 177/256 = 69.1%, top-10 189/256 = 73.8%, paired comparison 67 vs 40 (p = 1.4e-6 over
  102 shared datasets), and the large-molecule limit (≥26 heavy atoms fail more). Source of
  truth for every figure: `docs/BENCHMARK.md` and STATE.md §9 — copy, don't recompute. No
  compound identities on the slide.
- **D-07:** CASE1-9 slide stays, retitled from "test set" to "examples" (public nmrXiv
  identities, not a secret). Update solved status only if CASE-DATASET-IDENTITIES.md changed.
- **D-08:** "By the numbers" slide refreshed: current test count (from Phase-104 baseline),
  unchanged DB/HOSE/fragment counts unless sources disagree, "8/9 CASE set solved" tile gives
  way to the benchmark figure.
- **D-09:** Claude drafts figshare title+description text; user edits in the browser (human
  checkpoint). No API token exists; not worth minting one for a text-only change.
- **D-10:** Rename the figshare file only if figshare allows it without a new upload/file ID;
  research must answer this (see Summary — it does not allow it; leave the name as-is).
- **D-11:** Peripheral docs — maintain-and-rename or remove (`git rm`, stays in history).
  Candidates to remove: `analysis_ibuprofen/`, `docs/superpowers/specs/*.md` (2 files),
  `background/sherlock-analysis.md` (and evaluate the rest of `background/`). Deletion list
  goes to the user for approval before any `git rm` (human checkpoint).
- **D-12:** Not this phase: `.claude/` skill files (106); `scripts/uat_*`, `scripts/launchd/*`,
  `scripts/bootstrap_case_host.sh` (106/107, drive live hosts); `.planning/` (107);
  `pyproject.toml`/`src/` (done in 104). `data/reference/*` and `background/wenk-thesis.txt`
  are third-party/data text — do not edit content.
- **D-13:** Describe the method as hub-and-spoke (headless `claude -p` runs spawn/resume one
  specialist at a time via the coordinator; zero `TeamCreate` calls in 169 Opus-5 runs, 7
  specialist-initiated `SendMessage` calls total vs. ~1125 specialist spawns). README's "The
  CASE Agent Team" section + its ASCII diagram, `docs/ARCHITECTURE.md`, `docs/BENCHMARK.md`'s
  method section, and the deck's agent-team slide must all describe hub-and-spoke, not peer
  messaging. Peer-messaging/teams may be mentioned only as an interactive mode the benchmark
  did not measure.

### Claude's Discretion

- Replace the deck's Lineage box with a "Get it" box (repo, PyPI `ailsa`, database DOI).
- Replace the "12 milestones shipped" tile with a current fact.
- Generated PDF renamed `ailsa-infographics.pdf`; old `lucy-ng-infographics.pdf` git-rm'd.
- Exact README structure/wording — rewrite as AILSA rather than search-and-replace where prose
  reads awkwardly, as long as LSD + Nuzillard stay up front and DOC-01/02 hold.
- Verification grep: outside-facing files contain no `lucy-ng`, `lucy_ng`, `Lucy`, or a `lucy `
  command — except where a decision explicitly keeps it (the figshare file name).

### Deferred Ideas (OUT OF SCOPE)

- `src/ailsa/database/finder.py`'s `~/.lucy` home paths (`HOME_DB_PATH`, `HOME_TABLE_PATH`) —
  code leftover, not docs; candidate for 106/107 or a quick task.
- Phase 107's changelog "explaining the rename" (REPO-04) possibly conflicts with D-01's
  spirit — revisit when 107 is discussed.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| DOC-01 | README presents AILSA, expansion "AI + LSD + Agents", LSD/Nuzillard credited up front, no "formerly lucy-ng" note (D-01) | Exact README line map in Inventory §1 below; built-on-LSD section (lines 42-65) already has the right shape, just needs the name swap + D-02 lineage deletion |
| DOC-02 | `docs/` + CLAUDE.md refer to project/package/CLI/commands by new names; no living doc instructs `lucy` | Full per-file inventory below (Inventory §2); CLI-truth findings flag which retained examples are *already* broken and need more than renaming |
| DOC-03 | figshare record carries new name in title+description; DOI/file unchanged | figshare behaviour verified: title edit → new version (DOI suffix bumps, base DOI unchanged); file rename unsupported without re-upload → D-10 resolved to "leave file name" |
| DOC-04 | infographic deck rebuilt under new name with current headline numbers | `build.py` structure mapped (7 slides → 8 with D-06's new benchmark slide); current baseline numbers sourced from `docs/BENCHMARK.md` + Phase-104 baseline (1372 passed, not the deck's stale 1174) |

## Project Constraints (from CLAUDE.md)

- **Deck:** "Edit `build.py`, never `deck.html`." The HTML is fully generated; hand-editing it
  is explicitly forbidden and would be overwritten on the next `python build.py` run anyway.
- **Infographic maintenance trigger:** milestone close or a CASE test result flip is when the
  deck is supposed to be refreshed — this phase is exactly that trigger (D-04/D-08).
- **Rebuild sequence documented in `docs/infographics/README.md`:** (1) `python
  gen_structures.py` only if a molecule/SMILES changed (not needed this phase — no CASE
  identities change), (2) `python build.py` to regenerate `deck.html`, (3) optional Chrome
  headless PDF export.
- **CASE skill location pointer in CLAUDE.md** — `.claude/commands/ailsa/` /
  `.claude/agents/ailsa-*.md` are mentioned by path in CLAUDE.md's "CASE skill location"
  section (per D-04, write the *target* names now) but the actual skill files are **not**
  edited this phase (106).
- No other project-specific lint/test/security directives apply to a docs-only phase.

## Standard Stack

Not applicable — this phase installs no packages and writes no application code. No Package
Legitimacy Audit is required (no `npm install` / `pip install` of new dependencies).

## Architecture Patterns

### Recommended work split (by file, no overlap)

```
README.md                    — full rewrite pass (D-02 lineage removal, D-13 method,
                                D-04 names, CLI example verification)
CLAUDE.md                    — rename pass only (small, 4+4 occurrences, no stale-content issue)
docs/ARCHITECTURE.md         — rename pass + MCP-era content removal/rewrite (flagged below)
docs/BENCHMARK.md            — rename pass only (2 occurrences; figures already correct —
                                this file is the D-06 source of truth, don't touch numbers)
docs/INSTALLATION.md         — rename pass + MCP section removal/rewrite (flagged below)
docs/NUS-PORTABILITY.md      — rename pass only
docs/SERVER_BOOTSTRAP.md     — rename pass only (compute-host script paths named per D-04,
                                scripts themselves NOT touched — D-12)
docs/USER_GUIDE.md           — rename pass + fix/remove the dead `lucy lsd generate` example
                                + reconcile the "three interfaces incl. MCP" framing
docs/infographics/build.py   — content pass: D-06 new slide, D-07 retitle, D-08 refresh,
                                D-02 Lineage box replacement, renumber 0N/07 → 0N/08 everywhere
docs/infographics/README.md  — rename pass + PDF filename (ailsa-infographics.pdf)
rdmo-project-description.txt — rename pass (small, 4 occurrences, self-contained)
scripts/faulon-bridge/README.md — rename pass (small, self-contained)
scripts/figshare_upload.py   — rename pass in METADATA dict (note: already inconsistent with
                                the live figshare record — see Code Examples; don't assume
                                these strings match what's actually published)
scripts/zenodo_upload.py     — rename pass, same caveat
(removal candidates)         — human checkpoint before any git rm (D-11)
figshare record itself       — separate human checkpoint (D-09): draft text, user pastes in browser
```

Each file in the top block can be a separate task/wave with no file-overlap risk. The
infographics file is the only one requiring both a rename pass and net-new content (the
benchmark slide), so budget it as a bigger task than the others.

### Pattern: grep-based rename inventory with an allow-list

The verification grep from CONTEXT.md's Claude's Discretion section should run as:

```bash
# Outside-facing files only — exclude everything deferred (D-12) and the figshare
# file name (D-10) explicitly
rg -n --no-heading -i '\blucy-ng\b|\blucy_ng\b|\bLucy\b|/lucy-ng:|\blucy-[a-z]+(-advocate|-engineer|-chemist|-analyst)?\b|\blucy [a-z]+' \
   README.md CLAUDE.md docs/ARCHITECTURE.md docs/BENCHMARK.md docs/INSTALLATION.md \
   docs/NUS-PORTABILITY.md docs/SERVER_BOOTSTRAP.md docs/USER_GUIDE.md \
   docs/infographics/build.py docs/infographics/README.md \
   rdmo-project-description.txt scripts/faulon-bridge/README.md \
   scripts/figshare_upload.py scripts/zenodo_upload.py \
   | grep -v 'lucy-ng-derep.db.zip'   # the one allow-listed exception (D-10)
```

A clean run (empty output except the allow-listed filename, which the pattern above doesn't
even match since it looks for `lucy-ng` as a whole-word-ish token embedded in a longer
filename — verify with a literal `lucy-ng-derep.db.zip` string match separately so it isn't
silently caught or silently missed) is the pass condition.

### Anti-Patterns to Avoid

- **Blind sed/replace across all docs:** will "fix" the MCP-server and dead-command passages
  into `ailsa`-flavored versions of the same wrong information (e.g. `ailsa lsd generate` or
  `pip install "ailsa[mcp]..."`). Every retained code example must be re-verified against
  `ailsa <group> <cmd> --help`, not just renamed.
- **Touching `.claude/`, `scripts/uat_*`, `scripts/launchd/*`, `scripts/bootstrap_case_host.sh`,
  or `.planning/`:** explicitly deferred per D-12 — these are correctly excluded from this
  phase's file list above.
- **Hand-editing `deck.html`:** always edit `build.py` and regenerate.
- **Recomputing benchmark numbers:** `docs/BENCHMARK.md` is the single source of truth per
  D-06; every other file (README, deck) must copy its figures verbatim, not re-derive them.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Checking no old name remains | A one-off manual visual scan | The `rg`/`grep` allow-list command above, run as the last task in every file-touching plan step | Deterministic, scriptable, catches what eyeballing misses (41 `lucy-` agent-prefix lines in README alone) |
| Verifying CLI examples are current | Trusting the old prose | `ailsa <group> --help` / `ailsa <group> <cmd> --help` run live for every retained example | Already found two broken examples (`--dept135`, `lsd generate`) this way — training-data/prose knowledge is stale |
| Checking figshare rename feasibility | Guessing from the UI label names | The two Figshare help-center pages fetched in this research (How versioning works; How to edit or delete your item) | Definitive, official, dated guidance beats assumption |

**Key insight:** every "obviously mechanical" renaming file in this phase has at least one spot
where mechanical renaming alone propagates wrong information forward. The grep allow-list check
and the `--help` cross-check are cheap and catch both.

## Common Pitfalls

### Pitfall 1: Renaming dead content instead of fixing it
**What goes wrong:** `docs/INSTALLATION.md`'s `pip install "lucy-ng[mcp] @ ..."` becomes
`pip install "ailsa[mcp] @ ..."` — syntactically renamed, still describes a package extra that
doesn't exist (confirmed: no `mcp` key anywhere in `pyproject.toml`).
**Why it happens:** Search-and-replace operates on strings, not on whether the sentence is true.
**How to avoid:** For `docs/INSTALLATION.md` and `docs/ARCHITECTURE.md` specifically, treat the
MCP-server content as a known pre-existing defect (not caused by this phase) and decide
explicitly whether to strip it now (recommended, since the file is being touched anyway and the
"fresh start" framing is undercut by shipping a fabricated feature) or leave a tracked follow-up.
See Open Questions.
**Warning signs:** Any doc sentence mentioning `mcp`, `FastMCP`, `lucy-mcp`, or "three
interfaces."

### Pitfall 2: Trusting README/USER_GUIDE code examples at face value
**What goes wrong:** `ailsa lsd generate data/Ibuprofen C13H18O2 -o ibuprofen.lsd` gets renamed
in place (it's already `ailsa`-prefixed hypothetically) and ships as a documented command that
`ailsa lsd --help` proves doesn't exist (`analyze | check | rank | run | validate-inventory`
only).
**Why it happens:** The CLI evolved (LSD-file construction moved to agent skill knowledge) but
the docs didn't track it.
**How to avoid:** Run every retained example's command group through `--help` before finalizing
that section. Confirmed this phase: `ailsa pick hsqc`/`ailsa pick hmbc` have no `--dept135`
flag (now agent-side); `ailsa lsd rank` takes a `SMILES_FILE` positional + `-s/--spectrum` or
`--shifts`, not README's `lucy lsd rank output/ data/Ibuprofen/2 --top 10` two-positional form
(though `-n/--top` itself is real).
**Warning signs:** Any `lucy <verb> <verb2>` three-token invocation — these are the ones most
likely to have drifted.

### Pitfall 3: Deck slide-footer renumbering
**What goes wrong:** Adding the D-06 benchmark slide as an 8th slide but leaving some
`0N / 07` footer counters unchanged, or renumbering some slides but not the ones after the
insertion point.
**Why it happens:** The counters are hand-written literal strings in each `<section
class="slide">` block in `build.py` (7 occurrences today: `01/07` … `07/07`), not derived from
a loop variable.
**How to avoid:** After inserting the new slide, grep `build.py` for `/ 07` and confirm zero
matches remain, then confirm `/ 08` appears exactly 8 times (one per `<div class="foot">`).
**Warning signs:** `python build.py` succeeds (it doesn't validate counter consistency) but
`deck.html` visually shows a repeated or skipped number.

### Pitfall 4: figshare title edit creates a new version readers may not expect
**What goes wrong:** Editing the title to remove "lucy-ng" bumps the record to version 3; if
the human-checkpoint instructions don't mention this, the user may think something broke when
the versioned DOI changes from `.v2` to `.v3`.
**Why it happens:** Figshare's documented behaviour: title changes trigger versioning,
description-only changes do not (confirmed via Figshare's own "How versioning works" guide).
**How to avoid:** The D-09 human-checkpoint instructions handed to the user should say
explicitly: "this will create version 3; the base DOI `10.6084/m9.figshare.31073554` keeps
resolving to it automatically, no action needed on citations that use the base DOI."
**Warning signs:** None at execution time — this is a "tell the user in advance" pitfall, not a
detectable bug.

## Code Examples

### Verified current `ailsa` CLI surface (run live, version 0.1.0)

```
$ ailsa --version
ailsa, version 0.1.0

$ ailsa --help
  Commands:
    read  pick  analyze  dereplicate  identify  predict  detect  lsd
    visualize  fetch  database  fragment  webview  nus  jcamp  pylsd

$ ailsa lsd --help
  Commands:
    analyze  check  rank  run  validate-inventory
    # NOTE: no "generate" — README/USER_GUIDE document a dead command, see Pitfall 2

$ ailsa pick hsqc --help
  Options:
    -t, --threshold FLOAT  Peak threshold (default: 0.05).
    --format [text|json]
    # NOTE: no --dept135 — "The AI agent applies DEPT-guided filtering logic
    # using skill knowledge" (moved out of the CLI)

$ ailsa lsd rank --help
  Usage: ailsa lsd rank [OPTIONS] SMILES_FILE
  Options: -s/--spectrum PATH | --shifts TEXT | -n/--top INTEGER |
            -t/--tolerance FLOAT | --db PATH | --table PATH | --max-radius INTEGER

$ ailsa database download --help
  # Confirms legacy-filename handling already documents itself correctly
  # in --help text (D-03 territory, code side, already done in Phase 104):
  "an existing data/reference/lucy-ng-derep.db (PKG-05, pre-rename installs)
   is used in place instead" — this --help text itself still says the legacy
   name, which is correct and intentional (it's describing legacy-file
   detection, not instructing a new user to create that name) — do NOT "fix"
   this in Phase 105, it's in src/ailsa/cli (104, done, not in scope).
```

### figshare record — live state vs. upload-script state (these two do NOT match today)

```
# Live public record (fetched 2026-10-06, no token, https://api.figshare.com/v2/articles/31073554):
title: "COCONUT rereplication database for use in lucy-ng"
description: "...for use with the lucy-ng structure elucidation system.
               See https://github.com/steinbeck/lucy-ng for more."
file: {"id": 61078393, "name": "lucy-ng-derep.db.zip", "size": 828954592}
version: 2
doi: "10.6084/m9.figshare.31073554.v2"   (base DOI: 10.6084/m9.figshare.31073554)

# scripts/figshare_upload.py METADATA dict (stale, doesn't match the above):
title: "lucy-ng Compound Database: NMR Chemical Shifts for Natural Products"
description: mentions "compounds.db.gz" (not the actual filename) and different
              compound/size figures than the live record
```
Treat these as two independent texts needing two independent edits: the live record (via the
D-09 human checkpoint) and the script's dict (via normal file editing, D-11's "still-needed
documents" list). Don't assume fixing one fixes the other.

### Deck slide inventory (`docs/infographics/build.py`, 7 slides today)

```
01/07  Title/overview        — repo line, combination-thesis framing
02/07  The idea              — spectra in / structure out, emergent rings
03/07  The pipeline          — Bruker data → pick → detect → build → LSD → rank → identity
04/07  The agent team        — orchestrator + 4 specialists (+ diagnostic) — D-13 applies here too
05/07  nmrXiv data source    — ailsa fetch nmrxiv <DOI>
06/07  Test set CASE1–9      — RDKit structures; D-07: retitle to "examples"
07/07  By the numbers        — stats tiles (928K/7.9M/2.4M/111K/1174-tests/12-milestones/
                               8-9-solved/5-agents) + credits + Lineage box (D-02: remove)
```
D-06 inserts a new benchmark slide. Recommended position: between 05 (nmrXiv/data source) and
06 (CASE examples), so the narrative order becomes idea → pipeline → team → data source →
**benchmark result** → illustrative examples → numbers. Renumber all 7 existing `0N / 07`
footers to `0N / 08` and insert the new one as `06 / 08`, shifting the old 06/07 to 07/08 and
08/08. (This is a recommendation, not a locked decision — the user did not specify slide order,
only that the slide must exist per D-06.)

**Current stats tile values needing refresh (D-08):**
- `1174` automated tests → stale. Phase-104 baseline shows `1344 passed` pre-rename,
  `1372 passed` after Phase 104's own test additions (confirmed in `.planning/phases/
  104-package-and-cli/104-VERIFICATION.md`: "74 failed, 1372 passed, 86 skipped"). Use the
  current post-104 number, not the deck's `1174`, and not the raw `1372` without the caveat
  that 74 are environment-dependent failures (missing LSD binary / NMRPipe on the deck-building
  machine) rather than code defects — phrase the tile as "tests" with a footnote style
  consistent with how the deck already handles the "1 partial" caveat on the CASE tile.
- `12 / milestones shipped / v1.0 → v9.2` tile → Claude's Discretion item: replace with a
  current fact (e.g., current milestone number/name, or drop in favor of something that won't
  immediately go stale again).
- `8/9 CASE set solved` tile → D-08 says this "gives way to the benchmark figure" — i.e. this
  tile's slot gets repurposed to show the new 69.1%/73.8% headline instead, since the full
  story now lives on the new D-06 slide; keep the detail there, not duplicated on both.
- `928K` / `7.9M` / `2.4M` / `111K` (DB/HOSE/fragment/formula counts) — per D-08, unchanged
  "unless sources say otherwise." These were not independently re-verified against the live DB
  in this research pass (that would require downloading the ~2.8GB database); flag as
  `[ASSUMED]` — the planner/executor should run `ailsa database info <path>` against the actual
  installed DB if one is available locally, or treat these four figures as carried forward
  unchanged since no contradicting source was found.

### Benchmark figures to copy into the new slide (verbatim from `docs/BENCHMARK.md`)

```
Whole benchmark (256 datasets, current model):
  Rank 1:  177 / 256 = 69.1%   (76.6% of the 231 that produced a report)
  Top 10:  189 / 256 = 73.8%   (81.8% of the 231 that produced a report)

By size (rank 1, timeouts counted as failures):
  <=15 heavy atoms:  40/40  = 100%
  16-20:             28/32  = 88%
  21-25:             49/70  = 70%
  >=26:              60/114 = 53%   <- the "large molecules are the limit" slide content

Paired comparison (102 datasets run on both model generations):
  Current model: 67/102 (65.7%) rank 1   vs   Previous model: 40/102 (39.2%)
  Won only by current model: 30   Won only by previous model: 3
  Exact two-sided McNemar: p = 1.4e-6
```
No compound identities appear anywhere in this table — safe for the public repo as-is.

## State of the Art

Not applicable in the usual "library version" sense. The one relevant "what changed" fact:

| Old description | Current reality | When changed | Impact on docs |
|---|---|---|---|
| "Lucy-ng provides three interfaces: CLI, Python API, MCP Server" (USER_GUIDE.md, ARCHITECTURE.md) | MCP server removed; CLI-only (confirmed: no `mcp` extra, no `mcp` module) | v2.0 (per this repo's own project memory) | Both files need more than renaming — the architecture description itself is wrong |
| Peer-messaging agent team (`TeamCreate`, `SendMessage` between specialists) as the described method | Headless `-p` runs (which produced every published benchmark number) use hub-and-spoke: 0 `TeamCreate` in 169 runs, coordinator spawns/resumes one specialist at a time | Discovered 2026-10-06, documented in D-13 | README's "CASE Agent Team" section + diagram, ARCHITECTURE.md, BENCHMARK.md method section, deck agent-team slide all need the corrected framing |
| `lucy lsd generate` as a documented command | No `generate` subcommand exists; LSD-file construction is agent-side skill knowledge now | Unknown exact version (not dated in docs) | README + USER_GUIDE examples need rewriting, not renaming |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `928K`/`7.9M`/`2.4M`/`111K` DB/HOSE/fragment/formula counts on the deck's numbers slide are still accurate and need no update per D-08 | Code Examples (deck stats) | Low — D-08 explicitly says "unchanged unless sources say otherwise" and no contradicting source was found; worst case the numbers are off by a small margin until the next milestone-close refresh |
| A2 | Recommended slide position for the new D-06 benchmark slide (between data-source and CASE-examples slides) is a sensible narrative order | Code Examples (deck slide inventory) | Low — purely cosmetic; D-06 only requires the slide to exist, not where |
| A3 | Stripping the MCP-server content from `INSTALLATION.md`/`ARCHITECTURE.md` now (rather than deferring) is the right call given the "fresh start" framing | Common Pitfalls / Open Questions | Medium — if the planner defers instead, the rewritten AILSA docs ship with a reference to a non-existent `ailsa[mcp]` extra and `lucy-mcp`/`ailsa-mcp` command; low technical risk (nobody will successfully follow a broken instruction) but undercuts the stated goal of a credible fresh start |

## Open Questions

1. **How far should the accuracy fix go on `docs/INSTALLATION.md` and `docs/ARCHITECTURE.md`?**
   - What we know: both files describe an MCP server that was removed in v2.0; this is
     unrelated to the rename but both files are being touched anyway for DOC-02.
   - What's unclear: whether removing/rewriting the MCP sections is "in scope" for a phase
     whose success criteria are about naming, or whether it should be filed as a separate
     follow-up (the user has not been asked this specific question).
   - Recommendation: fix it now while the file is open — D-04's own rule ("each doc file is
     touched once; 106/107 must not need to re-edit these docs") argues for doing it in the
     same pass rather than creating a reason to touch `ARCHITECTURE.md` a third time later.
     Surface this explicitly to the user/discuss-phase step rather than deciding silently,
     since it technically broadens the diff beyond pure renaming.

2. **Does the `ailsa lsd generate`-shaped workflow still exist anywhere (just under a different
   command), or was it fully subsumed into agent skill knowledge with no CLI equivalent?**
   - What we know: `ailsa lsd --help` has no `generate`; `ailsa fragment to-lsd` generates an
     LSD *fragment* file from SMILES (different purpose — fragment library, not per-run
     constraints).
   - What's unclear: whether the per-run LSD constraint file (the thing README's example
     produces as `ibuprofen.lsd`) is now built entirely by agent prompt logic with no CLI
     equivalent at all, or whether it moved under a name not checked here (e.g. something under
     `ailsa detect` or `ailsa analyze`).
   - Recommendation: the planner/executor should grep `src/ailsa/cli/` for any command that
     writes a `.lsd` file before rewriting this example, to confirm there truly is no CLI
     equivalent and the correct fix is "describe this as agent behaviour, not a CLI command."

3. **Should `background/wenk-thesis.txt` and `background/Dissertation Michael Wenk.pdf` (8.2MB)
   be evaluated for removal alongside `sherlock-analysis.md`, per D-11's "evaluate the rest of
   background/"?**
   - What we know: neither is referenced by path from any code, doc, or test — the only "Wenk"
     references in code (`tests/test_lsd_grouping_syntax.py`, `src/ailsa/fragments/searcher.py`,
     `src/ailsa/fragments/extractor.py`) are citation comments ("following the Wenk thesis
     convention"), not file-path references, so removing the background files would not break
     anything.
   - What's unclear: whether these are third-party copyrighted material (a PhD thesis PDF) that
     shouldn't be in a public repo regardless of the rename, or legitimate scholarly background
     the user wants kept.
   - Recommendation: present as part of the same D-11 deletion-list human checkpoint; flag the
     PDF specifically as a potential copyright/size concern independent of the renaming
     question.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `ailsa` CLI | CLI-truth verification | Yes | 0.1.0 | — |
| `python3` (system) | `docs/infographics/build.py` | Yes | 3.x (system) | — |
| `rdkit` | `docs/infographics/gen_structures.py` | **No** (system python) | — | Not needed this phase — no SMILES/molecule changes planned (D-07 only changes title/status, not structures); only invoke if a CASE identity actually changed |
| Google Chrome (headless) | Optional PDF export of the deck | Yes | — (binary present at the documented path) | PDF export is optional per the deck README; HTML regeneration alone satisfies DOC-04 |
| `rg`/`ripgrep` or `grep` | Verification grep | Yes (both) | — | — |
| figshare API token | Direct automated edit of the figshare record | **No** (confirmed absent, per CONTEXT.md D-09 and re-confirmed: public GET worked with no auth, but no write credential exists) | — | Human checkpoint: Claude drafts text, user edits via figshare's web UI |

**Missing dependencies with no fallback:** none — the only "missing" item (figshare write
token) already has its fallback built into the locked decision (D-09 human checkpoint).

**Missing dependencies with fallback:** `rdkit` (not needed this phase, see above).

## Validation Architecture

> `workflow.nyquist_validation` is absent from `.planning/config.json` → treated as enabled.
> This is a documentation-only phase with no test framework in the usual sense; the "tests"
> below are deterministic shell/Python checks, not pytest.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None (docs-only phase) — checks are shell/grep + `python build.py` exit status |
| Config file | none |
| Quick run command | `rg` allow-list command (see Architecture Patterns) |
| Full suite command | the 5 checks below, run in sequence |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|-------------|
| DOC-01 | README has no old-name mentions except allow-listed; mentions AILSA + LSD/Nuzillard up front | grep/smoke | `rg -i '\blucy' README.md \| grep -v 'lucy-ng-derep.db.zip'` → empty; `grep -c 'Nuzillard' README.md` → >=1 in first 50 lines | ❌ Wave 0 — write as a one-off script, not a persisted test |
| DOC-02 | No living doc instructs `lucy <cmd>`; CLAUDE.md/docs/* renamed | grep | Same `rg` pattern across all 9 doc files (Architecture Patterns block) → empty except allow-list | ❌ Wave 0 |
| DOC-02 (accuracy) | Every retained CLI example matches current `ailsa --help` output | manual + semi-automated | For each `ailsa X Y ...` line found by `rg '\bailsa [a-z]' docs/USER_GUIDE.md README.md'`, run `ailsa X Y --help` and confirm the flags used appear in the help text | ❌ Wave 0 — no existing script; this phase should add one or do it by hand once |
| DOC-03 | figshare record shows new title; DOI/file unchanged | manual (human checkpoint) | `curl -s https://api.figshare.com/v2/articles/31073554 \| python3 -m json.tool` after the user's edit → check `title`, `doi` (expect `.v3`), `files[0].id == 61078393` | ❌ N/A — verification command exists (used in this research), not a persisted test file |
| DOC-04 | Deck rebuilds under new name with current numbers; slide count/footers consistent | smoke | `cd docs/infographics && python build.py` → exit 0; `grep -c 'ailsa' deck.html` > 0; `grep -c 'lucy-ng' deck.html` == 0; `grep -o '/ 0[0-9]' deck.html \| sort -u` shows exactly one denominator (e.g. all `/ 08`) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** run the `rg` allow-list check against just the file(s) touched in that task.
- **Per wave merge:** run the full allow-list check across all 14 in-scope files (9 docs/code
  files + deck.html + the two scripts + the two text files), plus `python build.py` and the
  figshare live-record check if D-09's checkpoint has completed by then.
- **Phase gate:** all five checks in the Phase Requirements → Test Map green, plus a manual
  read-through confirming D-02 (Lucy lineage), D-13 (hub-and-spoke framing), and D-06/07/08
  (deck content) by eye — these are prose-correctness checks a grep cannot fully verify.

### Wave 0 Gaps

- [ ] A small verification script (shell or Python, lives under `scripts/` or is a one-off run
  from the terminal — planner's call whether it's worth persisting) implementing the `rg`
  allow-list command from Architecture Patterns, run against the final file list.
- [ ] A positive-control check: before trusting the grep, temporarily plant a `lucy-ng` string
  in a scratch copy of one file and confirm the grep catches it (proves the pattern isn't
  silently broken, e.g. by an anchoring or escaping mistake) — do this once during Wave 0, not
  per-task.
- [ ] A relative-link check for README/docs: extract `[text](path)` markdown links with a
  short `grep -oE '\]\([^)]+\)'` pass and confirm each non-URL target exists on disk
  (`#anchor`-only links can be skipped or checked against the file's own `##` headings).
  No existing tool/script does this in the repo; `npx markdown-link-check` is available via the
  system `npx` but was not used in this research because it would fetch a package over the
  network at check time — prefer the filesystem-only grep approach for a sandboxed/offline-safe
  check.
- [ ] `ailsa --help` / per-group `--help` outputs captured once as a reference (e.g. redirected
  to a scratch file) so every doc-writing task in the same wave compares against the same
  snapshot rather than re-running `--help` inconsistently.

## Security Domain

> `security_enforcement` is absent from `.planning/config.json` → treated as enabled. This
> phase touches no authentication, session, access-control, input-validation, or cryptography
> code or configuration — it edits prose files and a static HTML-generating script. All ASVS
> categories below are "not applicable."

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | N/A — no auth code touched |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | No | N/A — `build.py` has no untrusted input; it reads its own hardcoded Python strings |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Accidentally committing a figshare/zenodo API credential while editing `scripts/figshare_upload.py`/`scripts/zenodo_upload.py` | Information Disclosure | Neither script currently contains a live token (confirmed: this phase does not add API-driven automation — D-09 is a human-browser checkpoint specifically to avoid minting a token); if the planner is tempted to add token-based automation anyway, don't — stay inside the locked decision |
| Leaking an unpublished CASE dataset's compound identity while editing the benchmark slide or BENCHMARK.md | Information Disclosure | D-06 explicitly forbids compound identities on the new slide; this research's Code Examples section above lists only aggregate figures, no identities, by design |

## Sources

### Primary (HIGH confidence)
- `ailsa --help`, `ailsa lsd --help`, `ailsa pick hsqc --help`, `ailsa pick hmbc --help`,
  `ailsa lsd rank --help`, `ailsa lsd run --help`, `ailsa database download --help`,
  `ailsa database --help` — run live against the installed CLI, 2026-10-06
- `https://api.figshare.com/v2/articles/31073554` — public API, fetched live, no token, 2026-10-06
- Live repo inspection: `pyproject.toml`, `src/ailsa/` directory listing, `grep`/`rg` counts
  across all 15 in-scope files, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`,
  `.planning/phases/104-package-and-cli/104-VERIFICATION.md`,
  `.planning/phases/104-package-and-cli/baseline/BASELINE.md`,
  `docs/BENCHMARK.md` (full Results section), `docs/infographics/build.py` (full slide
  structure), `docs/infographics/README.md`

### Secondary (MEDIUM confidence)
- [How versioning works — Figshare](https://info.figshare.com/user-guide/how-versioning-works/) —
  title-edit-triggers-version / description-edit-does-not / base-DOI-stable claims
- [How to edit or delete your item — Figshare](https://info.figshare.com/user-guide/how-to-edit-or-delete-your-item/) —
  "Manage files" action set (edit/delete/replace/reorder), no rename-in-place action listed
- [Article endpoints — Figshare API docs](https://docs.figshare.com/old_docs/api/articles/) —
  cross-check on publish/versioning semantics (slightly more conservative phrasing than the
  user-guide page; both agree title changes propagate via a new version)

### Tertiary (LOW confidence)
- None used as the basis for any claim in this document — where WebSearch surfaced a claim
  (e.g. file-rename-via-"Manage files"), it was cross-checked against an official Figshare
  help-center page before being stated as fact; where it couldn't be (exact mechanism of file
  rename), the document says so explicitly rather than asserting it.

## Metadata

**Confidence breakdown:**
- Renaming inventory / CLI-truth: HIGH — every count and every `--help` output was run live
  against this repo and the installed `ailsa`, not recalled from training data.
- figshare behaviour: MEDIUM-HIGH — two independent official Figshare pages agree on the
  title-triggers-version / no-in-place-rename findings; file-rename specifically is an inference
  from the documented action list (edit/delete/replace/reorder) rather than an explicit "you
  cannot rename" statement, so treat D-10's resolution as "no supported path found" rather than
  "Figshare explicitly prohibits this."
- Deck/benchmark figures: HIGH — copied verbatim from `docs/BENCHMARK.md`, the designated
  source of truth; test-count figure HIGH (read from Phase-104's own verification doc); DB/HOSE/
  fragment/formula counts MEDIUM (not independently re-verified against a live database this
  session — flagged as A1 in Assumptions Log).
- Pre-existing staleness findings (MCP, dead `lsd generate` command): HIGH — independently
  confirmed via `pyproject.toml`, `src/ailsa/` listing, and live `--help` output, not just
  "the docs look old."

**Research date:** 2026-10-06
**Valid until:** This research is tied to a specific commit state and a specific live figshare
record; re-verify the figshare live-record snippet and the `ailsa --help` outputs if execution
is delayed more than a few days, since both could change independently of this phase (e.g. a
Phase-104 follow-up fix, or the user editing the figshare record before Claude drafts text).
