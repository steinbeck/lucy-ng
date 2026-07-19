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
