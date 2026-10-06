# Phase 105: Documentation and outside face - Context

**Gathered:** 2026-10-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Everything a reader sees from outside the code presents the project as **AILSA** (*AI + LSD +
Agents*), with LSD and Jean-Marc Nuzillard credited up front: README, `docs/`, `CLAUDE.md`,
the figshare record text of the reference database, the infographic deck, and the peripheral
documents still tracked in the public repo. Code, the skill files under `.claude/`, scripts that
drive the live benchmark (runner, watchdog, LaunchAgent), the GitHub repo name and the planning
history are **not** this phase (code = done in 104; skill = 106; repo/hosts/planning docs = 107).

**Overriding intent (user, 2026-10-06):** publication is a fresh start. Very few people know
lucy-ng; the name lucy-ng should **disappear as far as possible** from everything outside-facing.

</domain>

<decisions>
## Implementation Decisions

### The old name
- **D-01:** **No "formerly lucy-ng" note anywhere.** The DOC-01 clause "a short note that the
  project was formerly called lucy-ng" is struck (REQUIREMENTS.md DOC-01 and ROADMAP.md Phase
  105 success criterion 1 amended in the same commit as this file). DOC-01 now reads: README
  presents AILSA with the expansion and credits LSD/Nuzillard up front — nothing more.
- **D-02:** **Lucy lineage removed entirely.** Delete README lines 21–22 ("lucy-ng is a reference
  to the original *Lucy* CASE program… LSD made Lucy obsolete"), the README credit "original Lucy
  concept by Christoph Steinbeck" (≈ line 444), and the deck's "Lineage" box on slide 7 (Lucy,
  "later acquired by Bruker"). Neither Lucy nor Bruker-as-acquirer appears in any outside-facing
  text. Reason: the name alludes to the author's old LSD competitor; the project is built on LSD
  and must not stir that again.
- **D-03:** **Legacy compatibility is silent.** Docs never mention the deprecated `lucy` alias or
  the legacy DB filename `lucy-ng-derep.db`. They show only `ailsa …` and `ailsa-derep.db`
  (`DatabaseFinder.NEW_DB_NAME`). Both legacy paths keep working in code (Phase 104); they are
  just undocumented. Applies to CLAUDE.md too.

### Names for things not yet renamed
- **D-04:** **Docs use the final names now**, even though they only become true in Phases 106/107:
  slash commands `/ailsa:case`, `/ailsa:dereplicate`, `/ailsa:predict`, `/ailsa:sanitise`,
  `/ailsa:status`; agents `ailsa-nmr-chemist`, `ailsa-lsd-engineer`, `ailsa-solution-analyst`,
  `ailsa-devils-advocate`, `ailsa-diagnostic`; paths `.claude/commands/ailsa/`,
  `.claude/agents/ailsa-*.md`; repo `https://github.com/steinbeck/ailsa`, clone dir `ailsa`.
  Accepted: a few days of mismatch on the public repo until 106/107 land. Each doc file is
  touched once; 106/107 must not need to re-edit these docs.
- **D-05:** **PyPI upload moves to the end of the milestone** — after Phase 107 (repo renamed),
  not right after 105. The 0.1.0 upload freezes its README on PyPI, so it must only happen when
  every command and link in it works. Update `104-HUMAN-UAT.md`'s pending item and the
  PKG-01 note in REQUIREMENTS.md accordingly ("deferred until after Phase 107").

### Infographic deck
- **D-06:** **New benchmark slide.** How the blind benchmark works (agent team gets only a
  directory of spectra; external, independent grading), whole-benchmark result on the current
  model (rank 1 177/256 = 69.1 %, top 10 73.8 %), paired comparison with the previous model
  (102 datasets, rank 1 67 vs 40, McNemar p = 1.4·10⁻⁶), and — honestly — the limit: large
  molecules (≥ 26 heavy atoms) fail more often. **Source of truth for every figure:
  `docs/BENCHMARK.md`** (and STATE.md § 9) — copy, don't recompute. **No compound identities**
  from the benchmark on the slide (public repo).
- **D-07:** **CASE1–9 slide stays as illustrative examples**, retitled from "test set" to
  examples so it does not compete with the benchmark. Structures/identities there are already
  public (nmrXiv) — keep. Update its solved status only if CASE-DATASET-IDENTITIES.md changed.
- **D-08:** "By the numbers" slide: refresh to current facts (test count from the Phase-104
  baseline, DB/HOSE/fragment counts unchanged unless sources say otherwise); the "8/9 CASE set
  solved" tile gives way to the benchmark figure.

### figshare record
- **D-09:** **Claude drafts, user edits in the browser.** No figshare API token exists anywhere
  (searched 2026-10-06, see memory `reference_figshare_token`); a one-off text change does not
  justify minting a write token. Deliverable: final title + description text (AILSA name,
  LSD/Nuzillard credit, `ailsa database download` usage, link to github.com/steinbeck/ailsa) as a
  file the user copies in, plus a short click-path. This is a **human checkpoint** in the plan;
  verification = user confirms, then check the public record shows the new title and the DOI
  10.6084/m9.figshare.31073554 still resolves to the same file (ID 61078393).
- **D-10:** The figshare *file name* (`lucy-ng-derep.db.gz`): rename it only if figshare allows
  that without a new upload/new file ID; otherwise leave it (new upload is out of scope).
  Research must answer this. `ailsa database download` fetches by file ID, so code is
  unaffected either way.

### Peripheral documents in the public repo
- **D-11:** **Maintain or remove — nothing stays with the old name.** Still-needed documents get
  the new name (`rdmo-project-description.txt`, `scripts/faulon-bridge/README.md`, metadata text
  in `scripts/figshare_upload.py` and `scripts/zenodo_upload.py`). Ballast is removed from the
  tree with `git rm` (stays in git history) — candidates: `analysis_ibuprofen/` (old example
  run), the two dated specs under `docs/superpowers/specs/`, `background/sherlock-analysis.md`
  (and evaluate the rest of `background/`). **The deletion list is presented to the user for
  approval before any `git rm`** (human checkpoint).
- **D-12:** Not this phase even though they say lucy: `.claude/` skill files (106),
  `scripts/uat_*`, `scripts/launchd/*`, `scripts/bootstrap_case_host.sh` (106/107 — they drive
  live hosts), `.planning/` (107), `pyproject.toml`/`src/` (done in 104). `data/reference/*`
  and `background/wenk-thesis.txt` match "lucy" as data/third-party text — do not edit content.

### Claude's Discretion
- Replace the deck's Lineage box with a "Get it" box (repo github.com/steinbeck/ailsa, PyPI
  `ailsa`, database DOI).
- Replace the "12 milestones shipped · v1.0 → v9.2" tile (lucy-ng history) with a current fact.
- Generated PDF renamed `ailsa-infographics.pdf`; old `lucy-ng-infographics.pdf` git-rm'd.
- Exact README structure/wording, as long as LSD + Nuzillard stay up front and the DOC-01/02
  bar holds. Rewrite the README as AILSA rather than search-and-replace where prose reads
  awkwardly.
- Verification grep: outside-facing files (README, CLAUDE.md, docs/**, deck sources, remaining
  peripheral docs) contain no `lucy-ng`, `lucy_ng`, `Lucy`, or a `lucy ` command — except where
  a decision above explicitly keeps it (figshare file name if unrenameable).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/REQUIREMENTS.md` — DOC-01..04 (DOC-01 amended per D-01), Out of Scope list
- `.planning/ROADMAP.md` § Phase 105 — goal and success criteria (criterion 1 amended per D-01)
- `.planning/phases/104-package-and-cli/104-HUMAN-UAT.md` — pending PyPI upload (moves per D-05)
- `.planning/phases/104-package-and-cli/104-VERIFICATION.md` — what 104 actually renamed

### Facts the docs must reflect
- `docs/BENCHMARK.md` — every benchmark figure (D-06)
- `.planning/STATE.md` § 9 — benchmark close-out figures
- `.planning/CASE-DATASET-IDENTITIES.md` — CASE1–9 solved status (D-07; orchestrator-only file, gitignored — read, never copy identities beyond what the deck already shows)
- `src/ailsa/database/finder.py` — `NEW_DB_NAME = "ailsa-derep.db"` (D-03)
- `src/ailsa/cli/database.py` — DOI, file ID 61078393 (D-09/D-10)

### Files to change
- `README.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/BENCHMARK.md`, `docs/INSTALLATION.md`,
  `docs/NUS-PORTABILITY.md`, `docs/SERVER_BOOTSTRAP.md`, `docs/USER_GUIDE.md`
- `docs/infographics/build.py`, `docs/infographics/README.md`, `docs/infographics/gen_structures.py` (if needed) — **edit build.py, never deck.html**
- `rdmo-project-description.txt`, `scripts/faulon-bridge/README.md`, `scripts/figshare_upload.py`, `scripts/zenodo_upload.py`
- Removal candidates (D-11, after approval): `analysis_ibuprofen/`, `docs/superpowers/specs/*.md`, `background/sherlock-analysis.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docs/infographics/build.py` assembles `deck.html` from inline HTML + `structures.json`;
  README there documents rebuild + PDF export.
- `scripts/figshare_upload.py` holds the current record title/description — starting point for
  the D-09 draft text.

### Established Patterns
- CLI help text and command names already say `ailsa` (Phase 104) — docs should match `ailsa --help` output exactly; use it as the source for the command table.
- Old-name counts at discussion time: README 35× `lucy-ng` + 31 `lucy ` commands; INSTALLATION 35/14; USER_GUIDE 25 `lucy_ng` + 46 `lucy `; SERVER_BOOTSTRAP 18/11; NUS-PORTABILITY 13 `lucy `.

### Integration Points
- README is the PyPI long description (pyproject `readme`) — relevant for the deferred upload (D-05).
- `SERVER_BOOTSTRAP.md` describes the compute-host setup, whose scripts are renamed only in 106/107 — write final names per D-04.

</code_context>

<specifics>
## Specific Ideas

- User's words: "Ich möchte mit der Veröffentlichung einen Neuanfang. Der Name lucy-ng soll
  möglichst weitgehend verschwinden."
- Benchmark slide must be honest about the large-molecule limit, not only the headline.

</specifics>

<deferred>
## Deferred Ideas

- `src/ailsa/database/finder.py` still uses a home directory `~/.lucy` (`HOME_DB_PATH`, `HOME_TABLE_PATH`) — a
  code leftover of the old name; candidate for 106/107 or a quick task (not docs).
- Phase 107's changelog entry "explaining the rename" (REPO-04) conflicts with D-01's spirit —
  revisit when 107 is discussed (perhaps a neutral release note without the old name).

### Reviewed Todos (not folded)
- CASE4 azulene regiochemistry enumeration gap — chemistry defect, matched only on keywords.
- PROV-01 (agent hypothesis compiled into QC gate as ground truth) — behaviour decision, unrelated to renaming.

</deferred>

---

*Phase: 105-documentation-and-outside-face*
*Context gathered: 2026-10-06*
