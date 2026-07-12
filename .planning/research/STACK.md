# Stack Research: Automatic NUS 2D NMR Reconstruction

**Domain:** Non-uniform-sampling (NUS) 2D NMR reconstruction backend for a fully-automated (no-GUI) CASE pipeline
**Milestone:** v10.0 Automatic NUS 2D Reconstruction
**Researched:** 2026-07-12
**Confidence:** MEDIUM-HIGH (core recommendation HIGH; TopSpin-headless and mddnmr/hmsIST platform details MEDIUM/LOW — flagged per-claim below)

## Recommendation (one paragraph)

**Use NMRPipe + SMILE as the sole reconstruction backend, driven entirely by subprocess from a new `lucy nus` CLI group.** NMRPipe is free, actively maintained (current: v13.0 Rev 2026.072.12.03), has *native* Apple-Silicon and Intel macOS builds plus native Linux Intel/ARM builds, is 100% command-line/scriptable (no GUI), and ships the SMILE plugin automatically — `nmrPipe -fn SMILE` is literally a shell pipeline stage. It is also the *only* one of the four heavyweight backends investigated that does not have unresolved automation or platform question marks. hmsIST and mddnmr are legitimate fallbacks for artefact-heavy cases, but both are unmaintained (last confirmed releases 2016–2020), Linux-only in practice, and both *use NMRPipe internally anyway* — so NMRPipe has to be installed regardless of whether SMILE alone proves sufficient. TopSpin's CS/MDD reconstruction is free even in the academic "for Processing" license and is cross-platform, but no source (official Bruker docs, community write-ups) confirms a true zero-display headless mode for triggering reconstruction unattended — it is not safe to build the hard "no GUI" automation requirement on top of it; reserve it as a manual fallback for a human, exactly as the task brief itself already frames it. No mature pip-installable pure-Python CS/IST-for-NMR package exists; nmrglue itself provides only the NUS *unscrambling* utility (`expand_nus`), not a reconstruction algorithm — confirmed by direct inspection of the installed nmrglue 0.11 — which is exactly why the prior ad-hoc per-column IST left t1 ridges. Do not re-implement CS/IST from scratch; drive the validated NMRPipe/SMILE binary instead.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| NMRPipe | 13.0 Rev 2026.072.12.03 (current as of research date) | NUS expansion, FT, apodization, phasing, baseline — the whole processing chain | De-facto standard NMR processing engine; free; native macOS (Intel + Apple Silicon) and Linux (Intel + ARM) builds; 100% CLI/pipeline-driven; every other backend investigated (hmsIST, mddnmr) is built as an *add-on* to it, so it's a hard dependency either way. HIGH confidence — verified on official IBBR install page. |
| SMILE plugin (Ying/Delaglio/Torchia/Bax, NIH) | bundled with NMRPipe ≥ March 2018 releases (current release includes it) | The actual CS/IST-family NUS reconstruction algorithm, run as `nmrPipe -fn SMILE` | De-facto standard NUS reconstruction for NMRPipe pipelines; explicitly documented to run on both Linux and macOS from the command line; installs automatically alongside NMRPipe (`plugin.smile.tZ`), no separate registration. HIGH confidence — official SMILE manual + IBBR docs. |
| `bruk2pipe` (NMRPipe utility) | bundled with NMRPipe | Bruker `ser`/`fid` → NMRPipe binary format, with explicit flags (no interactive prompts) | Core NMRPipe conversion binary; scriptable non-interactively once F1/F2 acquisition parameters are known. **lucy-ng already parses these parameters** (`acqus`/`acqu2s` via the existing `BrukerReader`/nmrglue path) — so the `fid.com` conversion script can be *generated programmatically* from data already read by lucy-ng, avoiding NMRPipe's interactive `bruker` GUI template tool entirely. MEDIUM-HIGH confidence (mechanism verified from official docs + the project's own confirmed acqus/acqu2s parsing capability; exact bruk2pipe flag set needs a Phase-1 spike). |
| `nusExpand.tcl` (NMRPipe utility) | bundled with NMRPipe | Expands the sparse NUS `ser` onto the full sampling grid using the `nuslist` schedule before SMILE | Standard companion tool referenced directly by the SMILE manual; command-line/Tcl, no GUI. Note: nmrglue's own `expand_nus()` (Python, already available in this repo's dependency tree) performs the equivalent unscrambling and could be used as an alternative/cross-check inside `lucy`, but the canonical pipeline documented by NIH uses `nusExpand.tcl`. MEDIUM confidence. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| nmrglue | 0.11 (already installed/used in this repo) | Bruker parameter parsing (acqus/acqu2s/nuslist), post-reconstruction peak picking, verification plots | Already the project's I/O layer; confirmed (by direct inspection) to expose `expand_nus()` for NUS grid expansion and generic FT/apodization primitives in `nmrglue.process.proc_base`, but **no CS/IST/SMILE-equivalent reconstruction function** — do not attempt to extend it into a reconstruction algorithm. |
| Python `subprocess` (stdlib) | — | Drive `nmrPipe`, `bruk2pipe`, `nusExpand.tcl`, `smileNus`/`nmrPipe -fn SMILE` as external processes | All NMRPipe-family tools are csh/Tcl scripts and C binaries with no Python bindings — subprocess is the only integration path, matching lucy-ng's existing thin-CLI-wrapper architecture. |
| nmrPype (`PhiMykah/nmrPype` on GitHub, PyPI) | 0.8.0 (BSD-licensed, Python 3.10+) | Optional: pure-Python reimplementation of NMRPipe's core processing verbs (FT/ZF/SP/PS/transpose) | Interesting as a potential pip-only fallback for the *processing* stage (post-reconstruction FT/apodization/phasing) if a real NMRPipe install proves impossible on a target machine. **Not verified to implement SMILE/IST/CS reconstruction itself** — treat as unproven/LOW confidence for the reconstruction step specifically; would need direct source inspection before relying on it. Not part of the primary recommendation. |

### What is explicitly NOT recommended as the reconstruction algorithm

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| Hand-rolled per-column 1D IST on top of `nmrglue.expand_nus()` (the prior approach) | Confirmed root cause of the t1-ridge artefacts that stalled the last CASE run — nmrglue has no validated multidimensional CS/IST algorithm; a naive per-column threshold loop is not equivalent to SMILE/hmsIST-class reconstruction | NMRPipe + SMILE (`nmrPipe -fn SMILE`) |
| A from-scratch pure-Python CS/IST implementation (e.g., built on `sigpy`, `PySAP`/`pysap-mri`, or `mripy`) | These are general MRI/compressed-sensing toolkits, not NMR-FID-aware; none understands Bruker `nuslist`/FnMODE quadrature layout out of the box; re-deriving the Hyberts/Sun/Wagner IST algorithm correctly (and getting the phase/quadrature handling right for echo-antiecho HSQC/HMBC and QF COSY) is a multi-week research-grade effort with high correctness risk, essentially re-implementing hmsIST/SMILE from the papers | NMRPipe + SMILE (mature, peer-reviewed, widely validated implementation) |

## Installation

### macOS (Apple Silicon, primary dev machine) — WORKS NATIVELY

```bash
# tcsh is macOS's default install already (per environment check in NUS-RECONSTRUCTION-GUIDE.md);
# NMRPipe REQUIRES csh/tcsh as the invoking shell for its install + wrapper scripts.
mkdir -p ~/nmrpipe_install && cd ~/nmrpipe_install

# Exact filenames/URLs change per release — check https://www.ibbr.umd.edu/nmrpipe/install
# for the current tarball list before running. As of this research, download is a direct
# curl/wget with no visible registration wall on the IBBR-hosted install page (older
# NMRPipe documentation from spin.niddk.nih.gov historically referenced an email-registration
# step to bax@nih.gov for *redistribution* rights — re-verify this distinction at install time).
curl -O https://www.ibbr.umd.edu/api/nmrpipe/download?fileName=install.com
curl -O https://www.ibbr.umd.edu/api/nmrpipe/download?fileName=binval.com
# ... plus the platform-specific .tZ bundle for mac11_arm64 (Apple Silicon) —
# select mac11_arm64 explicitly, NOT mac11_64 (Intel) or the Linux ARM VM build.

csh install.com          # runs interactively but is fully scriptable with default answers
csh binval.com           # validates the install
source ~/.cshrc          # or wherever install.com wrote the env additions

nmrPipe -help            # verify
smileNus -help            # verify SMILE plugin installed
nusExpand.tcl -help      # verify
```

Apple-Silicon-specific note: NMRPipe publishes a **native** `mac11_arm64` build (Mac OS 13.3.1 M1 baseline) — no Rosetta 2 translation needed, unlike many older scientific tools. `nmrDraw` (the interactive GUI) is documented as **not** working directly on macOS — irrelevant here since the pipeline is headless anyway (peak picking will go through nmrglue/lucy-ng, not nmrDraw).

### Linux (Intel or ARM) — WORKS NATIVELY, easiest platform

```bash
# csh/tcsh required; on Ubuntu:
sudo apt-get install csh tcsh
# Then the same install.com/binval.com flow, selecting the matching platform build:
# linux239_64 (Ubuntu 24), linux235_64 (Ubuntu 22), linux231_64 (Ubuntu 20),
# linux212_64 (legacy CentOS 6.5), or linux235_arm64 (Ubuntu 22 ARM, e.g. Apple-Silicon VM/cloud ARM).
```

Native Linux ARM build exists (`linux235_arm64`) — relevant if the pipeline is later containerized/deployed to ARM cloud instances or run inside a Linux VM on an Apple-Silicon Mac.

### Windows — NO NATIVE BUILD; documented platform gap, workaround required

NMRPipe has **not shipped a maintained native Windows build since v8.9** (the legacy `winxp` build is explicitly marked as no longer updated). The IBBR install page's own recommended path for Windows users is a **Linux virtual machine** (VMware image with NMRPipe 13.0 preinstalled is offered directly by IBBR for both Windows/Intel and macOS/ARM hosts).

- **Recommended workaround (not officially documented by IBBR, but the standard community practice and consistent with the "Linux VM" guidance):** WSL2 with an Ubuntu distribution, then install the matching Linux Intel build inside WSL2. This should work because WSL2 is a real Linux kernel (unlike WSL1), and NMRPipe's Linux binaries have no unusual kernel/driver dependencies — but this has **not been independently verified in this research pass** and should be spiked/validated before being written into requirements as fact. Confidence: LOW-MEDIUM (inferred, not sourced).
- **Officially supported workaround:** the IBBR-provided pre-built Ubuntu VM image (VMware). Higher confidence since it's IBBR's own recommendation, but adds a VM-management dependency to the automation story (the `lucy` CLI would need to shell out across a VM boundary, e.g. via `vmrun`/SSH — materially more complex than a native/WSL2 subprocess call).
- **Document this as an accepted platform gap** per the milestone's own "documented limitations allowed" clause — full native Windows support for the reconstruction backend is not realistically achievable without Bruker TopSpin (see below), which has its own unresolved headless-automation gap.

## Platform Support Matrix

| Backend | macOS Apple Silicon | macOS Intel | Linux (Intel) | Linux (ARM) | Windows | Headless/scriptable? | Python binding? |
|---|---|---|---|---|---|---|---|
| **NMRPipe + SMILE** | **Works** (native `mac11_arm64`) | Works (native `mac11_64`) | **Works** (native, multiple distro builds) | Works (native `linux235_arm64`) | No native build (v8.9 was last); Linux VM or WSL2 (unverified) workaround | Yes — pure CLI/pipe, no GUI at all | No — subprocess only |
| **hmsIST** (Wagner lab) | Not documented / unverified | Not documented / unverified | Likely (built for NMRPipe-Linux workflows; exact binary architectures not confirmed) | Unverified | Unverified, likely no | Yes, in principle (csh + NMRPipe pipeline scripts) — but distribution/platform details too thin to commit to a specific OS | No — subprocess/script only |
| **mddnmr / qMDD** | No (no macOS build found) | No (no macOS build found) | Works — "statically linked executables for several Linux platforms" (v2.7 manual, Sept 2020) | Unverified | No | The **qMDD GUI is a GUI** (Python 2 + PySide — obsolete stack, hard to even install in 2026); but mddnmr also ships **command-line-only shell scripts** that bypass the GUI and are scriptable | No modern binding (qMDD's Python layer is Python 2/PySide, effectively unusable/unmaintained in 2026); CLI scripts are subprocess-only |
| **TopSpin headless (CS/MDD)** | Runs (M1-compatible per Bruker; native-ARM status not explicitly confirmed) | Runs | Runs (AlmaLinux stated) | Unverified | Runs | **Unverified** — TopSpin's own Python interface (4.3+) connects to a *running* TopSpin instance over a network/web service, and legacy Jython AU-program automation runs *inside* a running TopSpin process; no source found confirming TopSpin can run fully headless (zero display, no interactive session) to trigger NUS/CS reconstruction unattended | Yes — network/web-service Python API (Python 3.9+) exists in TopSpin ≥4.3, but only for driving an already-running TopSpin instance |
| **Pure-Python CS/IST (pip)** | N/A — no such package exists (see below) | N/A | N/A | N/A | N/A | N/A | N/A |

## Per-Candidate Detail

### 1. NMRPipe + SMILE — RECOMMENDED PRIMARY

- **License:** Free for academic/non-commercial use, provided "as-is and without warranties." Site terms note the *software* itself "is not to be redistributed without permission from the authors" — this governs redistribution, not local use. No blocking registration wall observed on the current (2026) IBBR-hosted install page (direct `wget`/`curl`), though older documentation referenced an email-based registration step (`bax@nih.gov`) — worth a 5-minute re-check at install time since this detail has visibly changed over the tool's history. Confidence: MEDIUM (current mechanism), HIGH (that it's free/no-cost).
- **Install:** Native binaries for macOS (Intel + Apple Silicon) and Linux (Intel + ARM, multiple distro-targeted builds). No Windows native build since v8.9; VM/WSL2 workaround required (see above).
- **csh dependency:** Hard requirement — install scripts and the runtime environment setup are csh/tcsh. Already satisfied on the dev machine per the task brief's own environment check.
- **Python binding:** None — pure CLI/pipeline tool (`nmrPipe -fn SMILE ...`), invoked via `subprocess`, exactly matching lucy-ng's existing thin-CLI-wrapper architectural pattern (nmrglue/LSD/RDKit are all wrapped the same way).
- **Version/maintenance:** Actively maintained — current version 13.0 Rev 2026.072.12.03 (script update dated 2026-05-20), i.e. maintained as of this research date. HIGH confidence (official install page).
- **Unattended end-to-end feasibility:** YES. Every step (bruk2pipe conversion → nusExpand.tcl → `nmrPipe -fn SMILE` → apodization/ZF/FT/PS/baseline via standard `.com` pipe scripts → peak picking) is a shell/Tcl invocation with no interactive prompts once parameters are supplied — this is precisely the pattern NIH's own SMILE manual documents for multi-job/multicore batch reconstruction.
- **Source:** https://www.ibbr.umd.edu/nmrpipe/install , https://spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf , https://spin.niddk.nih.gov/bax/software/SMILE/

### 2. hmsIST (Wagner lab, Harvard) — VIABLE FALLBACK, LOW-CONFIDENCE ON DISTRIBUTION/PLATFORM

- **License:** Ambiguous — the GitHub mirror (`eburakova/hmsIST`) states the tools "can be distributed freely but are not publicly accessible," which is self-contradictory given the repo is in fact a public GitHub repo; a separate Wagner-lab copyright PDF is referenced. Treat as "usable, terms unclear" and re-verify with the lab/PDF before shipping this into an automated pipeline. Confidence: LOW.
- **Install:** No documented macOS or Windows build; presumably Linux binaries built to plug into an existing NMRPipe pipeline (it explicitly "works in conjunction with NMR Pipe," reusing NMRPipe's csh/Tcl scripting conventions). Platform matrix for this tool specifically could not be confirmed from available sources.
- **Python binding:** None — csh/Tcl scripts + compiled reconstruction binary, subprocess-only, same integration pattern as NMRPipe.
- **Version/maintenance:** Effectively unmaintained — the GitHub repo is explicitly described as "stored for archiving purposes," last substantive publications are from 2012–2017 (the seminal IST-HMS paper is 2012; the tmax-optimization follow-up is 2017). No 2020s activity found.
- **Unattended feasibility:** Plausible in principle (same csh-pipeline pattern as NMRPipe/SMILE) but unverified in practice given the platform/distribution uncertainty above.
- **Recommendation:** Keep as a documented fallback for artefact-heavy datasets if SMILE underperforms on this project's 25%/33% sampling densities, but do not build it into the v10.0 requirements as a guaranteed path — needs its own platform spike before being relied upon.
- **Source:** https://github.com/eburakova/hmsIST , https://link.springer.com/article/10.1007/s10858-012-9611-z , https://link.springer.com/article/10.1007/s10858-017-0103-z

### 3. mddnmr / qMDD (Orekhov group) — VIABLE FALLBACK, LINUX-ONLY

- **License:** Free for academic use (stated in the user manual); the distribution site (`mddnmr.spektrino.com`) currently returns a **TLS certificate mismatch** (cert issued for `home.pl`/`*.home.pl`, not the mddnmr domain) — a signal of site/infrastructure rot that should raise caution about currency and trustworthiness of the download itself. Confidence: MEDIUM on licensing text, LOW on current site health.
- **Install:** Distributed as **statically-linked executables for several Linux platforms** (per the v2.7/Sept-2020 manual and v2.5 release notes) — no macOS or Windows build found in any source consulted. The MDD/CS/IST computational core runs from Linux command-line shell scripts; the **qMDD GUI wrapper is Python 2 + PySide** — Python 2 has been EOL since January 2020, making the GUI path essentially unusable/unreasonable to stand up fresh in 2026 without a legacy environment. However, mddnmr also ships command-line-only scripts that drive the same reconstruction without the GUI.
- **Python binding:** None current/modern — qMDD's Python layer is Python-2-only and should not be relied on; the CLI-script path is subprocess-only, same pattern as the other backends.
- **Version/maintenance:** Last confirmed version is 2.5–2.7 (manual dated September 2020); no evidence of activity since. Effectively unmaintained. Confidence: MEDIUM (based on available manual/groups.io evidence; could not access the live download page directly due to the TLS issue above).
- **Unattended feasibility:** Yes for the CLI-script path on Linux (calls into NMRPipe for the FT stage, same subprocess pattern) — but platform-limited to Linux only, and the qMDD convenience GUI must be avoided entirely.
- **Recommendation:** Linux-only fallback; do not target macOS/Windows for this backend. Given hmsIST and mddnmr are both Linux-only, unmaintained, and layer on top of NMRPipe anyway, prioritize getting SMILE working well before investing in either.
- **Source:** http://mddnmr.spektrino.com/man (v2.7 manual, Sept 2020), Google Groups "Mddnmr 2.5 – out now!" (https://groups.google.com/g/mddnmr/c/VekBfc7gYXE)

### 4. TopSpin headless (CS/MDD reconstruction) — NOT RECOMMENDED for the automated pipeline

- **License:** Free "TopSpin for Processing — Academic/Government/Non-Profit" license, valid 3 years, renewable; explicitly includes 2D NUS/CS processing at no extra cost ("NUS processing for 2D spectra... is also available in the academic version"). Full 3D-6D NUS and the Structure-Elucidation CMC-se module are separately licensed/paid. Confidence: HIGH (Bruker's own FAQ).
- **Install:** Cross-platform — Windows, macOS (M1-compatible per Bruker marketing copy, though "native Apple-Silicon" vs. Rosetta was not explicitly stated and should be verified), and Linux (AlmaLinux). No registration-wall beyond the academic-license application process (institutional email, org verification).
- **Python binding:** Two generations exist — (a) legacy **Jython** (Python 2.7) automation that runs *inside* a live TopSpin process via AU programs / `edpy`, and (b) a newer **TopSpin Python Interface** (TopSpin ≥ 4.3) that lets an *external* Python 3.9+ process talk to a running TopSpin instance over an embedded network/web service. Both require **TopSpin itself to already be running** as a process — neither source consulted describes a way to launch TopSpin, run a reconstruction, and exit with zero display/session, i.e. a true unattended headless mode (à la a systemd/cron job with no X server or virtual desktop at all). This is the critical unresolved gap for this project's hard "no GUI" requirement. Confidence: LOW that full headless automation is achievable without dedicated, possibly platform-specific, engineering (e.g. Xvfb tricks that Bruker does not document or support).
- **Version/maintenance:** Actively maintained, current TopSpin generation is 4.x (4.3+ for the modern Python interface); this is the best-maintained software of the five candidates by a wide margin, since it's Bruker's flagship commercial product.
- **Recommendation:** Do not build v10.0 automation on TopSpin. It remains valid as the **manual fallback for a human operator** (Chris) exactly as the task brief itself already frames it (§6 "Alternative A... eher der Weg für den Menschen selbst") — keep it out of the `lucy` CLI's automated critical path. If a future milestone wants to revisit this, the concrete open question to resolve first is: *can `TopSpin` be started in a genuinely displayless mode (no X11/Aqua/RDP session at all) on Linux and still accept commands over the Python-interface network API?* — this needs a dedicated spike, not assumed from marketing docs.
- **Source:** https://www.bruker.com/en/products-and-solutions/mr/nmr-software/topspin-faqs.html , https://www.bruker.com/en/products-and-solutions/mr/nmr-software/topspin/topspin-python-interface.html , https://ekwan.github.io/2020/01/topspin-automation

### 5. Pure-Python / pip-installable CS/IST — DOES NOT EXIST AS A MATURE OPTION; DO NOT BUILD ONE FROM SCRATCH

- **nmrglue (already a lucy-ng dependency, v0.11):** direct inspection of the installed package (`nmrglue.process.proc_base`) confirms it provides `expand_nus()` (schedule-based NUS-grid expansion/unscrambling — the same conceptual step as `nusExpand.tcl`) plus generic FT/apodization/phase-correction primitives (`fft`, `zf`, `sp`, `em`, `ps`, `tp`, etc.), but **no CS, IST, SMILE, or any other multidimensional sparse-reconstruction algorithm**. This is a directly-verified, HIGH-confidence negative finding, and it explains the prior failure: the "ad-hoc per-column IST" mentioned in the task brief was necessarily a hand-written addition on top of these primitives, not a library feature — and a naive per-column 1D threshold loop is not equivalent to a validated multidimensional CS/IST algorithm (which must jointly threshold across the full indirect-dimension spectrum, not column-by-column), which plausibly explains the residual t1 ridges.
- **General-purpose Python CS/MRI toolkits** (`sigpy`, `PySAP`/`pysap-mri`, `mripy`/`peng-cao/mripy`): all exist and are pip-installable/GitHub-installable, but are built around **MRI k-space** conventions (Cartesian/non-Cartesian k-space trajectories, coil sensitivities), not NMR FID/quadrature-detection conventions (States-TPPI, echo-antiecho, QF). None was found to have NMR-specific examples, Bruker-format awareness, or NMRPipe-format I/O. Adapting one correctly for this project's echo-antiecho HSQC/HMBC and QF COSY data would itself be a from-scratch signal-processing implementation project. LOW confidence that this is a shorter path than driving NMRPipe/SMILE.
- **`nmrPype` (PyPI, `PhiMykah/nmrPype`, v0.8.0, BSD, Python 3.10+):** a genuine, actively-tagged pure-Python reimplementation of NMRPipe's *processing* verbs (FT/ZF/SP/PS/transpose) — pip-installable, no NMRPipe binary required for those steps. Interesting as a potential pip-only fallback for the **post-reconstruction processing** stage specifically. Its PyPI/GitHub description does not claim SMILE/IST/CS reconstruction support, and this was not independently verified by reading its source — treat any use of it for the *reconstruction* step (as opposed to plain FT/ZF/apodization) as unverified/LOW confidence.
- **Recommendation:** Do not attempt to implement CS/IST/SMILE from the published algorithm papers as the v10.0 solution. The correctness risk (subtle quadrature/phase bugs are exactly the kind of thing that silently produces "plausible-looking but wrong" reconstructions, which is the CASE failure mode this milestone exists to eliminate) outweighs any packaging convenience. Use the validated NMRPipe+SMILE binary via subprocess instead.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| NMRPipe + SMILE | hmsIST | If SMILE reconstructions on this project's 25–33% sampling densities still show visible t1-ridge artefacts after tuning (SMILE iteration count, threshold), and you're on Linux — hmsIST is a robust, well-cited fallback algorithm, but budget time for its platform/distribution uncertainty. |
| NMRPipe + SMILE | mddnmr CLI scripts (not qMDD GUI) | Same artefact-quality trigger as above, Linux-only, and only via the command-line scripts (never the Python-2/PySide GUI). |
| NMRPipe + SMILE (fully automated) | TopSpin GUI CS/MDD | If full automation genuinely turns out infeasible on a given machine (e.g., NMRPipe truly cannot be stood up, no VM/WSL2 permitted) — accept a manual, human-driven reconstruction step for that one machine, documented as an explicit exception to the "no GUI" constraint, not as a scripted `lucy` pathway. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| Hand-rolled per-column IST on `nmrglue.expand_nus()` | Proven root cause of the prior CASE-run failure (t1-ridge artefacts, LSD unable to prune the candidate space) | NMRPipe + SMILE |
| qMDD GUI (Python 2 + PySide) | Python 2 is EOL (Jan 2020); GUI-driven; unmaintained since ~2020 | mddnmr's own command-line-only scripts (Linux only), or better, skip mddnmr entirely and use SMILE |
| TopSpin as the automated reconstruction path in the `lucy` CLI | No documented/verified true-headless (zero-display) automation mode for CS/MDD reconstruction; would make the pipeline silently depend on an interactive session existing somewhere | NMRPipe + SMILE, subprocess-driven |
| From-scratch pure-Python CS/IST implementation | High correctness risk reproducing published algorithms exactly (quadrature/phase handling for echo-antiecho and QF data is easy to get subtly wrong); no existing pip package implements it correctly for NMR today | NMRPipe + SMILE (mature, peer-reviewed, widely validated) |
| Native Windows NMRPipe install | Not maintained since v8.9 (legacy XP-only build) | WSL2 Ubuntu (needs validation) or IBBR's own prebuilt Ubuntu VM image, documented as an accepted platform gap |

## Stack Patterns by Variant

**If running on macOS Apple Silicon (primary dev machine) or any native Linux (Intel/ARM):**
- Install NMRPipe + SMILE natively; drive the full pipeline (bruk2pipe → nusExpand.tcl → SMILE → standard processing) via `subprocess` from a new `lucy nus` command group.
- Generate the `fid.com`/conversion parameters programmatically from lucy-ng's existing Bruker `acqus`/`acqu2s` parsing rather than using NMRPipe's interactive `bruker` GUI template tool.

**If running on Windows:**
- Document as a platform gap. Recommend WSL2 Ubuntu as the primary workaround (needs a validation spike before being asserted as supported) or the IBBR-provided Ubuntu VM image as the officially-sanctioned fallback. Do not attempt a native Windows NMRPipe install.

**If SMILE reconstructions fail the quality gate (t1 ridges still present after tuning) on this project's 25%/33%-sampled data:**
- Fall back to hmsIST or mddnmr's CLI-only path, both Linux-only, both layered on the same already-required NMRPipe install. Treat both as experimental/spike-first, not drop-in replacements.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| NMRPipe 13.0 (mac11_arm64) | SMILE plugin bundled with the same release | SMILE requires "NMRPipe posted March 15 2018 or later" — any current download already satisfies this; do not mix an old NMRPipe core with a separately-obtained SMILE plugin. |
| nmrglue 0.11 (already installed) | Any NMRPipe version | nmrglue's `nmrglue.fileio.pipe` module reads/writes NMRPipe-format files, giving lucy-ng a native Python bridge to hand processed NMRPipe spectra back into the existing peak-picking code without needing NMRPipe's own text-peaklist tools. |
| WSL2 + Ubuntu Linux NMRPipe build | Should match one of `linux231_64`/`linux235_64`/`linux239_64` (Ubuntu 20/22/24) | Pick the build matching the WSL2 distro's Ubuntu version; unverified end-to-end in this research pass. |

## Grounding: real data checked against this recommendation

Direct inspection of `/Users/steinbeck/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/2/` (exp2, COSY) confirms the task brief's data-inventory table: `nuslist` contains 188 zero-based t1 indices (0, 124, 431, …, matching `NusAMOUNT=25`, `NusSEED=54321` in `acqus`), `acqus` shows `PULPROG=<cosygpmfppqf>`, `AQ_mod=3`, `TD=2048`, `SW_h=3750`, and `acqu2s` shows `FnMODE=1` (QF) with indirect `TD=188` — exactly matching the guide's "COSY / QF / 188 points" row. This confirms the sampling-schedule and FnMODE facts this STACK research (and the downstream conversion-script design) are built on are accurate, not assumed.

## Sources

- https://www.ibbr.umd.edu/nmrpipe/install — NMRPipe platform matrix, version, csh requirement, download mechanism (HIGH confidence, official/current)
- https://spin.niddk.nih.gov/bax/software/smile/smile_manual.pdf — SMILE manual, install/bundling with NMRPipe, macOS+Linux CLI usage (HIGH confidence, official)
- https://spin.niddk.nih.gov/bax/software/SMILE/ — SMILE overview, example scripts (HIGH confidence, official)
- https://github.com/eburakova/hmsIST — hmsIST distribution, ambiguous license notice, "archived" status (MEDIUM confidence — public repo but self-described as an archive mirror)
- https://link.springer.com/article/10.1007/s10858-012-9611-z , https://link.springer.com/article/10.1007/s10858-017-0103-z — hmsIST/IST-HMS primary literature, dates the last known active development (2012, 2017) (HIGH confidence for dates, MEDIUM for currency inference)
- http://mddnmr.spektrino.com/man — mddnmr v2.7 manual (Sept 2020), Linux-only statically-linked executables (MEDIUM confidence — manual content retrieved, but the live site currently fails TLS certificate validation, a currency/trust red flag)
- https://groups.google.com/g/mddnmr/c/VekBfc7gYXE — mddnmr 2.5 release notes, Linux platform confirmation (MEDIUM confidence)
- https://www.bruker.com/en/products-and-solutions/mr/nmr-software/topspin-faqs.html — TopSpin academic/free licensing, 2D NUS included free (HIGH confidence, official vendor)
- https://www.bruker.com/en/products-and-solutions/mr/nmr-software/topspin/topspin-python-interface.html — TopSpin Python Interface (4.3+), network/web-service architecture, Python 3.9+ requirement (HIGH confidence, official vendor; LOW confidence on headless/no-display capability, which the page does not address)
- https://ekwan.github.io/2020/01/topspin-automation — community write-up confirming legacy Jython/AU-program automation runs inside a live TopSpin process, no headless mode described (MEDIUM confidence, single community source)
- Direct inspection of installed `nmrglue` 0.11 (`nmrglue.process.proc_base`) in this repo's environment — confirms `expand_nus()` exists, confirms no CS/IST/SMILE function exists (HIGH confidence — first-party verification, not a web source)
- Direct inspection of `C20H32O2/2/{nuslist,acqus,acqu2s}` — grounds the FnMODE/nuslist/NusAMOUNT facts used throughout this document (HIGH confidence — first-party verification)
- https://pypi.org/project/nmrPype/ — pure-Python NMRPipe-processing-verb reimplementation, BSD/Python 3.10+ (MEDIUM confidence — PyPI listing read via search snippet, not independently source-verified for SMILE/IST support)

---
*Stack research for: NUS 2D NMR reconstruction backend (lucy-ng v10.0)*
*Researched: 2026-07-12*
