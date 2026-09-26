---
phase: 102
phase_name: "cli-peak-pick-bridge-qc-reuse"
project: "lucy-ng"
generated: "2026-07-25"
counts:
  decisions: 9
  lessons: 7
  patterns: 8
  surprises: 7
missing_artifacts:
  - "102-UAT.md"
---

# Phase 102 Learnings: CLI + Peak-Pick Bridge + QC Reuse

## Decisions

### Fix the homonuclear `_resolve_dim` defect inside Phase 102 rather than reopening Phase 101
`readers/jcamp.py::_resolve_dim` raised `ValueError` for every homonuclear 2D experiment, which blocked COSY. The fix was pulled into Phase 102 as its first, highest-risk task instead of being deferred or routed around via the D-06 skip path.

**Rationale:** `readers/jcamp.py` is not on CONTEXT.md's byte-protected list (that list is `PeakPicker2D`, the 1D picker, `nus/qc.py`, `case.md`, the 5 agent files), and D-06's non-fatal skip is scoped to NOESY-and-unrecognized types — not to COSY, which Phase 102's own success criterion 1 requires working. Skipping COSY would have satisfied the letter of D-06 while violating the phase goal.
**Source:** 102-RESEARCH.md (Pitfall 1), 102-01-PLAN.md, 102-01-SUMMARY.md

### `procs_index` is a hint, never an override — the unique-match path is untouched
`_resolve_dim(inner, target_nucleus, *, procs_index=None)`; the hint is consulted only inside the `len(matches) > 1` branch. With no hint, the fail-loud `ValueError` still fires.

**Rationale:** Keeps the already-correct heteronuclear (HSQC/HMBC) resolution path completely unchanged, and narrows the ambiguity guard rather than removing it — silently guessing an axis assignment would produce plausible-but-wrong ppm axes, the exact defect class this milestone exists to prevent.
**Source:** 102-01-SUMMARY.md (Decisions Made), 102-REVIEW.md (confirmed correct)

### The 1D bridge lives under `processing/`, not `nus/`
`bridge_peak_pick_1d` was placed in `src/lucy_ng/processing/jcamp_1d_bridge.py` rather than beside the 2D bridge in `nus/`.

**Rationale:** It has zero `nus.*` coupling, unlike the 2D bridge. The `nus/` package name is NUS-flavoured but the function is generic — CONTEXT.md left the location explicitly to planner discretion.
**Source:** 102-02-SUMMARY.md (key-decisions)

### Work root sits *beside* `out_root`, never inside it
`work_root = out_root.parent / "jcamp_ingest"`, with `staged/` and `qc_failed/` beneath it.

**Rationale:** A later `lucy nus qc <out_root>` run can then never accidentally glob staged or quarantined JSON (the keyword-glob is case-insensitive substring matching), and a FAIL run leaves `analysis/nmr_peaks/` genuinely absent rather than half-populated.
**Source:** 102-03-SUMMARY.md (Decisions Made), 102-RESEARCH.md (Pitfall 3)

### Two distinct exit-code rules: a skip is not a failure
`SystemExit(1)` on a FAIL verdict, **and** `SystemExit(1)` whenever the `failed` list is non-empty even on PASS/PARTIAL. A non-empty `skipped` list alone (D-06) stays non-fatal and exits 0.

**Rationale:** A file that could not be read must never be reported as a clean run, but a deliberately unsupported experiment (NOESY) must not kill the batch. Conflating the two would either mask malformed input or make the expected NOESY file fatal.
**Source:** 102-03-SUMMARY.md (key-decisions)

### `RECON_BACKEND = "jcamp"` — short by design, provenance goes elsewhere
The unchanged bridge interpolates this string into every per-peak note, so a long provenance string would multiply across hundreds of peaks. Full provenance lives in an additive top-level `source` block instead.

**Rationale:** Respects the byte-unchanged bridge's own formatting behaviour without editing it; `nus/qc.py::_load_peaks` only requires `cross_peaks` and `_load_1d_shifts` only reads `peaks`, so extra top-level keys are safely ignored.
**Source:** 102-03-SUMMARY.md (key-decisions, Decisions Made)

### `QcConfig.default()`'s quaternary override is documented, not fixed
`classification_source` reads `"override"` using the five compiled-in §8 shifts whenever no DEPT file is present. No CLI flag was added to change this.

**Rationale:** Fixing it would require editing `nus/qc.py`, which is byte-protected this phase. Adding an escape-hatch flag would expand scope beyond JCLI-01/02. Recorded as inherited behaviour in the command docstring and both summaries instead of silently absorbed.
**Source:** 102-RESEARCH.md (Pitfall 4), 102-03-SUMMARY.md, 102-02-SUMMARY.md

### CR-01 clearing is asymmetric: `rmtree` the owned dir, `unlink` inside the user's dir
`work_root` (the fixed `jcamp_ingest/` subdirectory) is fully `rmtree`'d; `out_root` — user-specified via `--out` — is never removed wholesale, only the closed set of filenames this command can ever write there is unlinked, and the directory itself removed only if that empties it.

**Rationale:** Fixing a correctness bug must not introduce a worse one. A recursive delete on an arbitrary user-supplied path would trade a stale-state defect for data loss.
**Source:** commit `f6de196`, 102-REVIEW.md (CR-01), 102-VERIFICATION.md

### `supervisor.md` is excluded from the skill-file freeze — explicitly, not silently
The SHA-256 guard covers `case.md` plus the five `lucy-*.md` agent files. `.claude/agents/supervisor.md` exists in the repo but is asserted-and-documented as out of roster.

**Rationale:** Neither CLAUDE.md's description nor CONTEXT.md names it as part of "the 5-agent team". An unexplained omission in a byte-freeze guard reads as an oversight; an asserted one reads as a decision.
**Source:** 102-RESEARCH.md (Pitfall 5), 102-04-SUMMARY.md

---

## Lessons

### A phase closed as "complete & verified" can still hide a defect that blocks the next phase's success criteria
Phase 101 shipped with `VERIFICATION.md status: passed`, yet its reader could not read COSY at all. The deferral was documented in `101-03-SUMMARY.md` as out-of-scope with a forward reference to "Phase 103" — but Phase 103's actual ROADMAP scope is end-to-end *validation*, not reader fixes, so the deferral had no real owner.

**Context:** Found by the phase researcher `grep`-ing the real external `.dx` files for `$NUC1`, not by reading lucy-ng's code or trusting the prior phase's summary. A green verification means the phase met *its own* must-haves; it says nothing about whether a documented deferral points at a phase that will actually absorb it.
**Source:** 102-RESEARCH.md (Pitfall 1), 102-01-SUMMARY.md

### A schema contract that degrades silently needs a negative-control test, not just a positive one
`nus/qc.py::_load_1d_shifts` does `data.get("peaks", [])`. If the 1D bridge had emitted the 2D `cross_peaks` shape, nothing would raise — the gate would return an empty reference list and `check_hsqc_coverage` would fall back to a hardcoded reference, producing a plausible-looking but wrong QC run.

**Context:** The 1D and 2D schemas share superficial vocabulary ("ppm", "peaks") but differ in top-level and per-peak key names, so reusing the wrong helper by analogy to the just-built 2D bridge is an easy mistake. The mitigation was a test that hand-builds a 2D-shaped payload named `13C.json` and pins the silent-failure mode explicitly.
**Source:** 102-RESEARCH.md (Pitfall 2), 102-02-SUMMARY.md

### The worktree base assertion is load-bearing, not ceremony
Two of the three worktree-isolated executor agents started on a stale, unrelated commit (`dfac9bb`, a v9.3-milestone-archive point) rather than the expected wave-merged base. Both were corrected by the mandatory `<worktree_branch_check>` `git reset --hard` before any file was read or written.

**Context:** Without that assertion, both agents would have written correct-looking code against a months-old tree and their merges would have silently reverted wave-1 and wave-2 work. This is an agent-harness environment hazard, not a plan defect — but it fired on a majority of dispatches, so it should be treated as expected, not exceptional.
**Source:** 102-03-SUMMARY.md, 102-04-SUMMARY.md (Issues Encountered)

### In this repo, bare `python`/`pytest` inside a worktree verifies the wrong source tree
The global `lucy-ng` editable install and a system `.pth` file resolve to the **main repo checkout**, so import-based verification inside a worktree silently analyses code the agent did not write. All four plans hit this.

**Context:** Plan 01 discovered it when its very first `python -c` sanity check transparently showed stale, pre-fix behaviour. The convention that emerged — prepend `PYTHONPATH="$(pwd)/src"` to every runtime verification command inside a worktree — was then carried forward in each subsequent plan's prompt. `mypy`/`ruff` are unaffected because they operate on file paths, not the import system.
**Source:** 102-01-SUMMARY.md, 102-02-SUMMARY.md, 102-03-SUMMARY.md, 102-04-SUMMARY.md

### Literal `grep -c … == 0` acceptance criteria recurrently contradict the plan's own action text
Twice this phase (102-02, 102-03) a plan required a substring count of zero (or exactly one) while its own action text asked for a comment or docstring naming that very substring — e.g. "explain that there is no subprocess" against `grep -c "subprocess" == 0`, and "comment that the anti-pattern is calling `run_qc_checks()` per file" against `grep -c "run_qc_checks(" == 1`.

**Context:** Both were resolved by rephrasing prose to preserve meaning without the flagged literal, and both were logged as Rule-1 deviations. The same class was already documented in 101-02. Substring-count criteria should target code constructs (an import statement, a call site), not prose that legitimately discusses them.
**Source:** 102-02-SUMMARY.md, 102-03-SUMMARY.md (Deviations from Plan)

### A write boundary needs run-to-run state hygiene, not just correct per-run branching
`cli/jcamp.py` branched correctly on the verdict — a FAIL genuinely refused to write new consumable peaks — yet the boundary was still defeated, because a prior PASS run's output was never removed. The consumable directory kept advertising `"qc_verdict": "PASS"` after a failed run.

**Context:** Fixed, idempotent paths plus "write only on success" is not sufficient when the previous run's artifacts persist. The guarantee users actually depend on is about the *state of the directory*, not the *behaviour of the invocation*.
**Source:** 102-REVIEW.md (CR-01), commit `f6de196`

### Click's default `CliRunner()` makes JSON-output assertions order-dependent
`CliRunner()` defaults to `mix_stderr=True`, so a `warnings.warn` message (here nmrglue's `JCAMP-DX key without value: $RELAX`) lands in `result.output` and breaks `json.loads()`. Python's once-per-call-site warning filter means it only fires the *first* time in a session — so the failure appears or disappears depending on test ordering.

**Context:** Discovered empirically during manual pre-verification, before any test was written against the wrong assumption. `CliRunner(mix_stderr=False)` makes JSON-parsing assertions robust regardless of run order.
**Source:** 102-04-SUMMARY.md (Decisions Made)

---

## Patterns

### Staged/final two-call QC wiring
Stage every file (1D and 2D) with `qc_report=None` into a staging directory, run the QC gate **exactly once** over the fully-staged directory, then rebuild the payloads with the real verdict before writing consumables.

**When to use:** Whenever a quality gate must grade artifacts that do not exist until they are produced, but the artifacts' own metadata wants the gate's verdict. Critically, the gate must see the whole set at once — a per-file call is subtly wrong here because the 1D files are the trusted reference for grading the 2D ones.
**Source:** 102-RESEARCH.md (Pattern 2, from `cli/nus.py::pipeline`), 102-03-SUMMARY.md

### Narrowed ambiguity guard with an opt-in positional hint
Keep the unique-match path authoritative and unchanged; consult a caller-supplied positional hint *only* in the ambiguous branch; keep fail-loud as the default when no hint is given.

**When to use:** Extending a fail-loud resolver to handle a previously-unsupported case, without weakening it for the cases it already handled correctly. The shape makes "we guessed" impossible to reach accidentally.
**Source:** 102-01-SUMMARY.md

### Prove a convention where the answer is independently knowable, then apply it where it is not
The positional axis convention (`$NUC1` index 0 = F2/direct) was proven on the **heteronuclear** HSQC fixture, where nucleus matching independently disambiguates — then applied to homonuclear files, where it cannot be derived from the data at all.

**When to use:** Any time a convention must be applied to degenerate data. Just as important as the proof is stating plainly, in the artifact, that the degenerate case does not itself prove the convention.
**Source:** 102-01-SUMMARY.md (Decisions Made)

### Un-mocked integration proof paired with a negative control
For a contract that fails silently, ship two tests: one that runs the *real* consumer (`QcReferenceData.resolve()`, zero test-doubles) against only the new producer's output and asserts the good state, and one that feeds a deliberately wrong-shaped payload and pins the silent-failure mode.

**When to use:** Whenever the consumer swallows a schema mismatch instead of raising. The positive test alone cannot distinguish "correct" from "correct by accident".
**Source:** 102-02-SUMMARY.md

### Proof-level ledger as a first-class artifact
Every claim is filed under FIXTURE-COVERED / SYNTHETIC / MOCK-COVERED / NOT-PROVEN, in VALIDATION.md and repeated in test-class docstrings, with the not-proven items routed to a named later phase.

**When to use:** Any phase whose CI data is a reduced stand-in for the real thing. It is what stops a green suite on 16 trimmed rows from being reported as "verified on real data" — the Phase-100 failure mode this whole milestone was designed around.
**Source:** 102-VALIDATION.md, 102-04-SUMMARY.md, 102-VERIFICATION.md (Honesty-Gate Assessment)

### Assert the branch-agnostic invariant first, then observe, then pin
Write the test so it holds for whichever branch the code takes, run the command, observe the real outcome, and only then record the observed value with a comment saying it was observed.

**When to use:** When the expected result genuinely is not knowable in advance. It prevents an executor from inventing an expectation and then bending the implementation to meet it — and it makes a legitimate FAIL recordable as a result rather than a problem.
**Source:** 102-04-PLAN.md, 102-04-SUMMARY.md

### Golden-hash freeze plus roster-completeness glob
A SHA-256 baseline table pins the *content* of each protected file; a separate glob over the directory pins the *roster*, so a newly added file is caught, not only a modified one. Paths are repo-relative so the test is cwd-independent, and deliberate exclusions are asserted rather than omitted.

**When to use:** Enforcing a byte-unchanged invariant that spans multiple phases. Without the roster check the guard passes vacuously the moment someone adds a file.
**Source:** 102-RESEARCH.md (Pitfall 5), 102-04-SUMMARY.md

### Generic fixture-trim helper with thin per-artifact wrappers
`build_trimmed_2d(source, dest, page_window, label)` parameterized over `build_trimmed_hsqc/cosy/hmbc/noesy`, with per-experiment page windows chosen by probing the real data — and regeneration leaving already-committed fixtures byte-identical.

**When to use:** Growing a committed fixture set from one artifact to several. The byte-identical-regeneration property is what makes the generator trustworthy enough to re-run.
**Source:** 102-01-SUMMARY.md

---

## Surprises

### The blocked experiment was COSY, not just NOESY
D-06 anticipated skipping NOESY as unsupported. The verified reality was that `$NUC1` lists `['<1H>', '<1H>']` for *both* homonuclear files, so `read_2d()` raised before the bridge was ever reached — taking down COSY, which the phase's own success criterion 1 requires.

**Impact:** Turned a "glue only, no new algorithms" phase into one carrying a real reader fix as its first and highest-risk task, and pushed the fix ahead of all CLI wiring in the wave plan.
**Source:** 102-RESEARCH.md (Pitfall 1)

### The prior phase's deferral pointed at a phase that does not own it
`101-03-SUMMARY.md` deferred homonuclear axis resolution "to Phase 103" — but Phase 103's ROADMAP scope is end-to-end validation, not reader work. The forward reference was stale, so the deferred item had no real owner in the roadmap.

**Impact:** Had the researcher not cross-checked the deferral target against ROADMAP.md, the gap could have survived into Phase 103 and surfaced as an inexplicable validation failure there.
**Source:** 102-RESEARCH.md (Pitfall 1)

### The positional convention suggested by pattern mapping was almost inverted
`SYMBOL` declares `F1,F2,Y`, which suggests threading `dims.index("F1")` — that is `0`. The heteronuclear HSQC file proves `$NUC1` index 0 is the **F2/direct** dimension.

**Impact:** Caught during planning, before implementation. Had the suggested indexing been used, both axes would have been swapped on every homonuclear spectrum — producing a plausible, self-consistent, and entirely wrong ppm assignment.
**Source:** 102-01-PLAN.md, planner's verification notes

### The homonuclear ordering cannot be discriminated from the homonuclear data itself
Both COSY dimensions share `$SF = 499.92` and their `$OFFSET` values differ by 0.000938 ppm (~0.47 Hz) — far below any ppm cross-check's resolution.

**Impact:** Forced an honest split between what the fixtures prove (the *result* is self-consistent and matches the committed 1D reference) and what only the heteronuclear proof establishes (the convention itself). Recorded in VALIDATION.md's Manual-Only table rather than dressed up as an automated proof.
**Source:** 102-01-SUMMARY.md (Decisions Made)

### The QC gate's "escape hatch" is already the unconditional default
CONTEXT.md's D-04 describes the known-quaternary override as an escape hatch "never the default" — but `QcConfig`'s dataclass default *is* the five compound-specific §8 shifts, applied whenever no DEPT file exists, which is exactly the `C20H32O2-jcamp` case.

**Impact:** The intent expressed in discussion did not match the shipped byte-protected code. Since `qc.py` could not be edited, the gap was documented as inherited behaviour in three places rather than silently absorbed — and the observed `classification_source == "override"` was recorded as fact, not as a choice this phase made.
**Source:** 102-RESEARCH.md (Pitfall 4), 102-02-SUMMARY.md, 102-03-SUMMARY.md

### No committed test enforced the byte-unchanged invariant that three prior phases claimed
Phases 97–99 all asserted `case.md` / `cli/pick.py` byte-unchanged, but the repo contained only a substring content-contract test (`test_case_md_wv07.py`) and `git diff --exit-code` strings living inside plan verify-commands — never a committed pytest test.

**Impact:** The invariant had been re-verified manually each phase and never regression-guarded. Phase 102 shipped the repo's first committed guard for it.
**Source:** 102-RESEARCH.md (Pitfall 5), 102-04-SUMMARY.md

### A Critical defect survived planning, plan-checking, and four executor self-checks
CR-01 (stale staging and consumable state persisting across runs) passed the plan-checker's dedicated causal-ordering and write-boundary review, and all four executors' self-checks, and was found only by the code-review pass — which reproduced it live rather than inferring it.

**Impact:** Confirms the advisory code-review gate earns its place even on a phase that was heavily front-loaded with verification. Each earlier gate checked whether the *invocation* behaved correctly; none checked what the *directory* looked like after two invocations.
**Source:** 102-REVIEW.md, 102-VERIFICATION.md (Anti-Patterns Found)
