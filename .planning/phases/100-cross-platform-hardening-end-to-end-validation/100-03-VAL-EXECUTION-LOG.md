# Phase 100 · Plan 100-03 (VAL) — Real-Data Execution Log

> Running log of the milestone-closing VAL run on the real C20H32O2 data.
> Feeds `100-03-SUMMARY.md` + `VALIDATION.md` at close. Each entry = a real
> issue the first-ever execution against the real NMRPipe+SMILE binaries
> surfaced, plus its resolution. Started 2026-07-18/19.

## Context / meta-finding

**Phase 98 (Reconstruction + Processing) and Phase 99 shipped "COMPLETE & verified" on mock-only tests** — the reconstruction chain was never run against the real `nmrPipe`/`bruk2pipe`/`nusExpand.tcl`/SMILE binaries (no backend in CI; explicitly flagged PROVISIONAL, "real-data spike deferred to Phase 100"). Phase 100 VAL is that spike. It has surfaced a chain of real-binary integration defects invisible to argv-recording mocks. These are being fixed inline (disciplined: each fix = test + atomic commit), and this class of gap is a **learning** worth recording at milestone close (mock-only "verification" of an external-binary pipeline gives false confidence).

## Environment setup (VAL prerequisites — one-time, this machine)

| Item | Resolution |
|------|-----------|
| NMRPipe base (native arm64) | User downloaded free `NMRPipeX.tZ`; installed properly via official `install.com +nounpack +nopost +nocshrc` at `~/NMRPipe` (generates `com/nmrInit.mac_arm64.com` with correct `NMRBASE`/`NMRBIN`). |
| SMILE plugin | `nusPipe` absent from base archive (PORT-01 preflight correctly reported `smile_plugin_missing`); user downloaded free `plugin.smile.tZ`; merged into `~/NMRPipe/nmrbin.mac_arm64/` (native arm64 `nusPipe` + `lib/smile` dylibs). |
| Gatekeeper quarantine | Cleared (`xattr -c`) on the arm64 bin + dylibs — "code signature not valid / library load disallowed by system policy" until cleared. |
| X11 / XQuartz | `nusExpand.tcl` runs via `nmrWish.exe` which hard-links `/opt/X11/lib/libX11.6.dylib` → **XQuartz is a HARD runtime dependency of the reconstruction path** (not just optional for nmrDraw). User installed via `brew install --cask xquartz` (needs admin). |
| Runtime env | Derived from the official `nmrInit.mac_arm64.com` (via `csh … ; env` capture) + SMILE plugin vars + `DYLD_FALLBACK_LIBRARY_PATH → lib/smile`. `lucy nus check` → `status: available, smile_available: true, arch arm64`. |

**Doc follow-up (PORT-02):** `docs/NUS-PORTABILITY.md` must be updated — SMILE is a separate download AND XQuartz is a hard dependency. (Deferred to end of VAL.)

## Real-data defects found & fixed

### D-BUG-1 — nusExpand.tcl cannot find `acqus`/`acqu2s` (FIXED)
- **Symptom:** `nusExpand.tcl … NUS Expand Error Extracting Input Sizes from acqus and acqu2s` (exit 1) on exp3.
- **Root cause:** `-mode bruker` nusExpand re-derives input X/Y sizes from Bruker `acqus`/`acqu2s`, looked up by **bare name relative to its cwd** (`stage_dir`), not `expdir`. `convert()` (`nmrpipe_smile.py`, expand_first branch) passed neither explicit `-acqus`/`-acqu2s` nor a cwd where those files live.
- **Fix:** pass explicit `-acqus <expdir>/acqus -acqu2s <expdir>/acqu2s` in the expand_first `expand_argv`. Verified: nusExpand then produces the full-grid `ser_full` (Output Y-Size 200 from sparse 100).
- **Test:** `tests/nus/test_reconstruct_chain.py::test_echo_antiecho_expand_argv_passes_acqus_paths`.
- **Commit:** (this commit)

### D-BUG-2 — process_direct/process_indirect chain multiple `-fn` in ONE nmrPipe call (FIXED)
- **Symptom:** SMILE stage fails `SMILE Error: the direct dim must be in freq domain.` The `f2_processed.fid` header shows `DOMAIN: Time Time, Not Transposed` — F2 was never FT'd/transposed.
- **Root cause:** `process_direct()`/`process_indirect()` (`postprocess.py`) build ONE `nmrPipe -in … -fn SP -fn ZF -fn FT -fn PS -fn POLY -fn TP -out …` invocation. **NMRPipe does not chain multiple `-fn` in one process** — it applies only the first verb (`SP`) and warns "Arguments N..M may be unknown or unused" for the rest. The canonical idiom is a **shell pipeline of one `nmrPipe` process per verb** (`nmrPipe -fn SP | nmrPipe -fn ZF | nmrPipe -fn FT | … | nmrPipe -fn TP -out …`). Mock-only Phase-98 tests recorded the argv and never executed real nmrPipe, so this was invisible.
- **Verified correct form:** the piped chain produces `2DMODE: States Transposed, DOMAIN: Time Freq` (F2 FT'd + transposed) — exactly SMILE's required input.
- **Fix (done):** added `runner.py::run_pipeline_stage()` — chains one `nmrPipe` process per verb via `subprocess.Popen` (stdin→stdout), and checks the return code of EVERY process (strengthens RECON-04/Pitfall-14: a mid-pipe failure no longer passes silently). Rewrote `process_direct`/`process_indirect` (`postprocess.py`) to emit per-verb stage lists. Extended `conftest.py::mock_run_stage` to also patch `run_pipeline_stage` (flattened argv into the same `calls` list + raw stages in `captured["pipelines"]`); strengthened `test_processing_order.py` to assert the per-verb pipeline structure (`fn_verbs == [SP, ZF, FT, PS, POLY, TP]`, TP last); added two `run_pipeline_stage` executor tests (success wiring + mid-pipe fail-loud) to `test_runner_faillloud.py`.
- **Verified:** full nus suite 95 passed / 1 skipped; ruff/mypy clean for the changed code (one pre-existing B904 in `recipe_for_fnmode`, untouched).
- **Commit:** (this commit)

<!-- Append further D-BUG-N entries as the real run surfaces them (process_indirect, post-SMILE stages, peak-pick, QC on real data). -->

### D-BUG-3 — SMILE aborts under memory pressure (ENVIRONMENTAL — awaiting RAM headroom)
- **Symptom:** SMILE stage runs (`nusPipe` at ~100% CPU, all 2048/1024 direct columns scanned), then aborts:
  `OMP: Error #34: System unable to allocate necessary resources for OMP thread ... Resource temporarily unavailable ... NMRPipe System Message: Cannot allocate memory ... Abort trap`.
- **Root cause:** NOT thread count. Verified: OMP=8/4/2/**1** all abort at ~6.0–6.3 GB RSS; halving the F2 direct dimension (ZF 2048→1024) did **not** reduce the ~6 GB. SMILE's working set here is ~6.3 GB and largely fixed. The dev Mac has **24 GB total but ~18 GB baseline-used** (other apps + macOS wired 6.3 GB + compressor ~3 GB), leaving only ~5.5 GB free with swap already ~3.8/5 GB used. SMILE's 6.3 GB exceeds free RAM → the abort. The "OMP thread" wording is misleading — the underlying failure is `Cannot allocate memory`.
- **Compounding hazard found & handled:** each SMILE run killed by a foreground per-command timeout left an **orphaned `nusPipe`** child holding 0.5–4.4 GB; several accumulated and starved memory. Mitigation: SMILE MUST run as a to-completion background job (never a timeout-killed foreground), and orphans must be reaped (`pkill -9 -f nusPipe`).
- **Also found (non-fatal, deferred):** this SMILE build reports `Warning from nusPipe: Argument 19 may be unknown or unused: '-EA'` — lucy passes `-EA` (echo-antiecho) but this version does not recognise it. Non-fatal (warning), but echo-antiecho handling should be re-checked once SMILE runs to completion.
- **Legit code fix to bake in (independent of RAM):** lucy's reconstruction should export `OMP_NUM_THREADS`/`OPENBLAS_NUM_THREADS`/`MKL_NUM_THREADS` caps so `nusPipe`'s nested OMP×BLAS threading cannot blow up on multi-core hosts. (Deferred until SMILE runs end-to-end so the fix is verified live.)
- **Resolution (needs user):** free RAM headroom — cleanest is a **reboot** (clears ~3.8 GB swap + ~3 GB compressor + baseline creep → fresh baseline ~6–8 GB used → ~16 GB free, SMILE's 6.3 GB fits comfortably), then re-run. Alternatively quit heavy apps. This is the last real blocker; all code/env issues upstream are fixed.
- **Status:** blocked on RAM headroom (environmental).

#### D-BUG-3 follow-up: parameter isolation (post-reboot, swap=0)

A reboot cleared swap/compressor but SMILE still aborts. Systematic isolation shows the ~5–6.9 GB
allocation is **independent of every knob available to us**:

| Varied | Values tested | Peak RSS |
|---|---|---|
| Direct-dim size | 2048 / 1024 / **256** | ~5.7 / ~6.3 / ~5.0 GB |
| `OMP_NUM_THREADS` | 8 / 4 / 2 / **1** | ~4.4 / — / ~6.0 / ~6.3 GB |
| `-maxIter` | **5** / 50 / 500 | 6.45 / 6.86 / ~5.7 GB |

Sampling schedule verified consistent (nuslist = 50 entries, indices 0–199 → 200-point indirect
grid, matching the data's 200 indirect points; `nus_td` 400 = 200 complex × 2 real). Raw data is
only ~6 MB, so a ~6.5 GB fixed working set is **disproportionate by ~1000×** — this looks like a
pathological/fixed allocation in this macOS-arm64 `nusPipe` build, not a tunable.

**Bounded tuning budget is therefore considered EXHAUSTED for SMILE-on-this-host (D-04).**
Remaining options: (a) free ~3–4 GB more RAM on this Mac and retry (cheapest real shot);
(b) run the VAL reconstruction on a larger-RAM host (reverses D-01 for the VAL run only);
(c) honest stop per D-04 — document the limitation, PORT (Plans 01/02) still ships, and name
RECON-F1 (hmsIST/mddnmr fallback) as the tracked next step.

**Note:** all upstream code/env defects (D-BUG-1, D-BUG-2, install, XQuartz, quarantine) are FIXED
and committed — the pipeline runs correctly all the way into SMILE. This blocker is the external
backend's memory behaviour, not lucy-ng code.
