# Phase 100 — VAL Evidence (C20H32O2 end-to-end validation)

**Run date:** 2026-07-18 / 2026-07-19
**Host:** dev Mac, Apple Silicon (arm64), macOS 26.5, 24 GB RAM
**Backend:** NMRPipe (native `mac_arm64`) + SMILE plugin, installed at `~/NMRPipe` via the
official `install.com`; `lucy nus check` → `status: available`, `smile_available: true`,
`platform.critical_platform_issues: []`
**Data:** `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/`
(exp2 COSY `/2`, exp3 HSQC `/3`, exp4 HMBC `/4`)

---

## Outcome summary

| Requirement | Verdict |
|---|---|
| **VAL-01** — exp2/3/4 reconstructed and passing the §8 gate | ❌ **NOT ACHIEVED** — documented limitation (see below) |
| **VAL-02** — fresh `/lucy-ng:case C20H32O2` converges on a finite rankable set | ❌ **NOT REACHED** — blocked by VAL-01 (no reconstructed peaks to consume) |
| PORT-01 / PORT-02 (Plans 100-01 / 100-02) | ✅ **DELIVERED** — independent of the VAL outcome, per D-04 |

This is the **honest-stop outcome explicitly provided for by CONTEXT decision D-04**: the
bounded tuning budget was exhausted, the limitation is documented rather than papered over,
and **RECON-F1** is named as the tracked next step. No fabricated or partial peak lists were
written to the consumable location; the CASE pipeline was never fed reconstruction output.

---

## What the run DID establish (positive results)

The reconstruction chain was executed against the real binaries for the first time in the
milestone's history, and runs correctly through every stage up to and including the SMILE
invocation:

| Stage | Result |
|---|---|
| `nusExpand.tcl` (NUS expansion) | ✅ produces full-grid `ser_full` (sparse 100 → 200 increments) |
| `bruk2pipe` (Bruker → NMRPipe) | ✅ produces `converted.fid` (1024 × 400) |
| `process_direct` (F2: SP→ZF→FT→PS→POLY→TP) | ✅ produces `f2_processed.fid`, header verified `2DMODE: States Transposed`, `DOMAIN: Time Freq` — exactly SMILE's required input |
| SMILE (`nusPipe`) | ⚠️ **starts and computes** (100% CPU, full direct-dimension scan) but aborts on memory (below) |
| `process_indirect` → peak-pick → QC | not reached |

Three real defects were found and fixed on the way (all committed, all test-covered) — see
`100-03-VAL-EXECUTION-LOG.md` for full detail:

- **D-BUG-1** — `nusExpand.tcl` could not locate `acqus`/`acqu2s` (looked up relative to cwd,
  not `expdir`). Fixed by passing explicit `-acqus`/`-acqu2s` paths.
- **D-BUG-2** — `process_direct`/`process_indirect` chained multiple `-fn` verbs in **one**
  `nmrPipe` process. NMRPipe honours only the first verb and silently drops the rest, so F2
  was never Fourier-transformed or transposed. Fixed by a new `run_pipeline_stage()` that
  pipes one `nmrPipe` process per verb and checks **every** process's exit code
  (strengthening RECON-04 / Pitfall 14).
- **D-BUG-3** — the blocking one (below).

Both fixes were invisible to the Phase-98 test suite because it recorded argv against mocks
and never executed a real `nmrPipe`.

---

## VAL-01: why it could not complete (D-BUG-3)

The SMILE step aborts with:

```
OMP: Error #34: System unable to allocate necessary resources for OMP thread
OMP: System error #35: Resource temporarily unavailable
NMRPipe System Message: Cannot allocate memory
NMRPipe Signal Message: Abort trap
```

The message names OMP threads, but the underlying failure is plain memory exhaustion.
`nusPipe` reaches a **~5–7 GB resident working set** and dies when the host cannot grow it.

**Bounded tuning budget (D-04), executed and exhausted.** The allocation proved
**independent of every knob available to the caller**:

| Varied | Values tested | Peak RSS |
|---|---|---|
| Direct-dimension size | 2048 / 1024 / 256 | ~5.7 / ~6.3 / ~5.0 GB |
| `OMP_NUM_THREADS` | 8 / 4 / 2 / 1 | ~4.4 / — / ~6.0 / ~6.3 GB |
| `-maxIter` | 5 / 50 / 500 | 6.45 / 6.86 / ~5.7 GB |

Additional controls: the sampling schedule was verified consistent (nuslist = 50 entries,
indices 0–199 → 200-point indirect grid, matching the data); a full reboot cleared swap
(3.8 GB → 0) and the compressor, and SMILE still aborted; accumulated orphaned `nusPipe`
processes from earlier timeout-killed attempts were identified and reaped as a compounding
factor.

Since the raw experiment data is only a few MB, a fixed ~6.5 GB working set is
disproportionate by roughly three orders of magnitude and does not respond to any documented
SMILE parameter. This is characterised as a property (possibly a defect) of **this
macOS-arm64 `nusPipe` build**, not of lucy-ng code, and not something tunable from the
caller side. On this host (24 GB total, ~17 GB consumed by a normal desktop workload) the
required headroom was not available.

**Non-fatal observation deferred:** this SMILE build reports
`Warning from nusPipe: Argument 19 may be unknown or unused: '-EA'` — lucy-ng passes `-EA`
for echo-antiecho but this build does not recognise it. Harmless as a warning, but
echo-antiecho handling must be re-verified whenever SMILE is next run to completion.

---

## VAL-02: not reached

`/lucy-ng:case C20H32O2` was **not** run: VAL-01 produced no accepted reconstructed peak
lists, so there was nothing new for the orchestrator to consume, and running CASE against the
old known-bad home-IST lists would have re-tested the very failure this milestone exists to
fix. The D-07 write boundary behaved correctly throughout — no reconstruction-derived peaks
ever reached `analysis/nmr_peaks/`.

---

## Data integrity (verified)

- `tests/fixtures/nus/known_bad_peaks/` — **byte-unchanged** (the QC-02 regression floor is
  intact).
- External root known-bad lists (`COSY_exp2`, `HSQC_exp3`, `HMBC_exp4`) were **archive-copied**
  to `analysis/nmr_peaks/known_bad_home_ist_archive/` before any run, and were never
  overwritten (no reconstruction reached the consolidation step).
- Trusted 1D reference lists (`13C_exp*`, `1H_exp1`, `NOESY_exp5`) — untouched.
- `.claude/commands/lucy-ng/` and `.claude/agents/` — **byte-unchanged** (CASE-skill invariant
  held; the orchestrator was never modified).

---

## Tracked next step

**RECON-F1** — the deferred hmsIST / mddnmr fallback backend, wired behind the existing
`NusBackend` protocol — is the named path forward for NUS reconstruction on hosts where
SMILE cannot run. Recorded in `.planning/ROADMAP.md` § Phase 100 and
`.planning/REQUIREMENTS.md` § Future Requirements.

Secondary options if SMILE is revisited: run the reconstruction on a host with ≥ 8 GB free
RAM (the chain is now known-good up to SMILE, so this is a pure resource question), and raise
the hard-coded 600 s `run_stage` timeout / expose it as a CLI flag, since a successful SMILE
run on this data plausibly exceeds it.
