# NUS Reconstruction: Cross-Platform Portability

This document is the PORT-02 portability matrix for the `lucy nus` NUS (Non-Uniform
Sampling) 2D reconstruction pipeline (`lucy nus check` / `reconstruct` / `pipeline`).
It records every known platform gap for the locked v10.0 backend decision — **NMRPipe +
SMILE** — so that gaps are investigated and written down, not silently accepted.

`lucy nus check` is the single source of truth for whether your machine is ready to run
the pipeline. It reports both backend-tool availability (`nmrPipe`, `bruk2pipe`,
`nusExpand.tcl`, the SMILE plugin) and a `platform` section (architecture, Rosetta
translation status, `csh`/`tcsh` presence). Critical gaps (missing backend binaries, no
`csh`/`tcsh` interpreter) hard-block `reconstruct`/`pipeline` before any stage runs
(PORT-01); soft gaps (running under Rosetta 2 / x86 emulation with the tools present)
only warn.

## Platform Matrix

| Platform | Native NMRPipe build | csh/tcsh | `lucy nus check` readiness signal | Status |
|----------|----------------------|----------|-------------------------------------|--------|
| **macOS Apple Silicon (native)** | Yes — `mac_arm64` | Present by default (`/bin/csh`, `/bin/tcsh`) | `status: available`, `platform.rosetta_translated: false`, no critical or soft issues | **Supported, install verified locally** (this dev machine: arm64, macOS 26.5, `sysctl.proc_translated=0`). Reconstruction blocked here only by SMILE's RAM appetite — see *Memory requirement* |
| **Linux (native)** | Yes — native Linux builds distributed on the same install page | Present on essentially every distro (install via package manager if missing) | `status: available`, `platform.os: Linux`, no critical issues | **Supported** (historical 32-bit-library caveat on some older distros — see Pitfalls below) |
| **Windows (WSL2 gap)** | **No** — no native NMRPipe build has been distributed since v8.9 | **No** native `csh`/`tcsh` on Windows | `status: not_installed` (no binaries on PATH) AND a critical `csh`/`tcsh`-missing platform issue — both fire and hard-block `reconstruct`/`pipeline` with no Windows-specific code required | **Gap — documented workaround only, see below** |

**Applies to every supported row:** the reconstruction additionally requires **XQuartz/X11**
(`nusExpand.tcl` runs under an X11-linked `nmrWish.exe`) and **≥ 8 GB free RAM** for the
SMILE step. Neither is covered by `lucy nus check`'s current probes — see the dedicated
sections below.

The Windows row is not silently accepted: the generic PORT-01 checks (missing backend
binary, missing `csh`) already fail correctly on a native Windows host with **no
Windows-specific detection branch** in the code (`platform_check.py` uses only
`platform.machine()`/`platform.system()`/`shutil.which()` — see *Design note* below).
This is deliberate: Windows genuinely lacks both a native NMRPipe build and a `csh`/`tcsh`
interpreter, so the same critical-check logic that protects macOS/Linux from a broken
install degrades correctly on Windows without any extra branching.

## SMILE is a separate download from base NMRPipe

**Important gotcha, all platforms:** the SMILE reconstruction plugin
(`plugin.smile.tZ`, "Companion Files from the Ad Bax Group at the NIH") is **NOT**
bundled with the base NMRPipe distribution. It is listed as its own, separate download on
the install page. If you install only the base `install.com`/`NMRPipeX.tZ`/`binval.com`
tarballs and skip `plugin.smile.tZ`:

- `nmrPipe -fn SMILE -help` reports `"unknown function"`.
- `lucy nus check` correctly reports `status: "smile_plugin_missing"` — distinct from
  `"not_installed"` (no NMRPipe at all) and from `"installed_not_sourced"` (NMRPipe
  present but its environment script was never sourced).

Always download and install `plugin.smile.tZ` as its own explicit step alongside the base
NMRPipe tarballs — do not assume it is bundled.

## macOS Apple Silicon: install walkthrough

> **Verified end-to-end on macOS 26.5 / Apple Silicon (arm64) during the Phase-100
> validation run.** The steps below replace earlier documentation-derived guesses with
> what actually works; deviations from the upstream install page are called out.

1. Download the NMRPipe distribution (`NMRPipeX.tZ`) **and** the separate SMILE companion
   plugin (`plugin.smile.tZ`) from <https://www.ibbr.umd.edu/nmrpipe/install>. Both are
   available without a licence click-through from the site's archive area.
2. Create an install directory (e.g. `~/NMRPipe`) and extract `NMRPipeX.tZ` into it, then
   extract `plugin.smile.tZ` **into the same tree** so `nusPipe` and `lib/smile/*.dylib`
   land in `nmrbin.mac_arm64/` alongside `nmrPipe`.
3. Run the official installer from the install root. It needs `install.com` **and**
   `binval.com` in the *current working directory* (it looks for `./binval.com`, not
   `com/binval.com`):

   ```bash
   cd ~/NMRPipe
   cp com/binval.com com/install.com .
   csh ./install.com +nounpack +nopost +nocshrc
   ```

   This generates `com/nmrInit.mac_arm64.com` with the correct `NMRBASE`/`NMRBIN`.
   Note the binary type is **`mac_arm64`**, not `mac11_arm64`.
4. **Clear the Gatekeeper quarantine** on the binaries and their libraries — otherwise
   macOS refuses to load them with *"code signature not valid for use in process: library
   load disallowed by system policy"*:

   ```bash
   find ~/NMRPipe/nmrbin.mac_arm64 -print0 | xargs -0 xattr -c
   ```

5. Source the generated init script (`~/NMRPipe/com/nmrInit.mac_arm64.com`) — it is a
   **csh** script, so `csh`/`tcsh` must be present (they ship with macOS). It sets
   `NMRBASE`, `NMRBIN`, `NMRTXT` and prepends the binary and `com/` directories to `PATH`.
   For a non-csh shell, capture its environment once
   (`csh -c 'source …; env'`) and export the `NMR*`/`PATH` values.
   You may also need `DYLD_FALLBACK_LIBRARY_PATH` pointing at
   `nmrbin.mac_arm64/lib/smile` so `nusPipe` resolves its `@rpath` dylibs.
6. **Install XQuartz** — see the hard-dependency section below. This is *not* optional.
7. Verify with:

   ```bash
   lucy nus check     # must report backend "available" and the platform
                       # section clear of any critical issues
   ```

   If `lucy nus check` reports `smile_plugin_missing`, revisit step 1/2 — the SMILE
   plugin was not installed (see the gotcha above).

`nmrPipe`, `bruk2pipe` and `nusPipe` are native arm64 Mach-O binaries and run with no
Rosetta or virtualization.

## XQuartz (X11) is a HARD dependency of the reconstruction path

> **Correction to the upstream framing.** Upstream docs discuss X11/XQuartz mainly in the
> context of the `nmrDraw` GUI, which lucy-ng never invokes — so earlier revisions of this
> document treated XQuartz as an optional, try-it-if-something-fails mitigation. **That is
> wrong.** The Phase-100 run showed:

`nusExpand.tcl` — a mandatory step of the NUS reconstruction chain — is executed by
NMRPipe's Tcl/Tk interpreter `nmrWish.exe`, which is **link-time bound to
`/opt/X11/lib/libX11.6.dylib`**. Without XQuartz, `nmrWish.exe` cannot start at all and
the reconstruction fails at the expansion stage with a `dyld: Library not loaded` error —
even though no GUI is ever displayed.

```bash
brew install --cask xquartz     # requires admin rights
```

Install it on **any** host that runs the reconstruction, headless or not.

## Memory requirement: SMILE needs several GB of FREE RAM

Measured during the Phase-100 validation run on real Bruker NUS data (2D HSQC, 200-point
indirect grid): the SMILE step (`nusPipe`) allocated a **~5–7 GB resident working set** and
aborted when the machine could not satisfy it, with a misleading message:

```
OMP: Error #34: System unable to allocate necessary resources for OMP thread
OMP: System error #35: Resource temporarily unavailable
NMRPipe System Message: Cannot allocate memory
```

The underlying failure is plain memory exhaustion, *not* a thread-count problem. Measured
systematically, this allocation was **independent of** the direct-dimension size
(2048/1024/256 points), of `OMP_NUM_THREADS` (8/4/2/1), and of `-maxIter` (5/50/500) —
i.e. it is not tunable from the caller side. Since the raw data is only a few MB, this is
disproportionate and may be specific to this macOS-arm64 `nusPipe` build.

**Practical guidance:**

- Budget **≥ 8 GB genuinely free RAM** for the SMILE step; a 24 GB machine with a typical
  desktop workload (browser, Dropbox, editors) may not have enough headroom.
- Lowering `OMP_NUM_THREADS` does **not** avoid it, but capping thread counts
  (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`) is still sensible hygiene
  on multi-core hosts, since `nusPipe` links both OpenMP and OpenBLAS.
- Never abort a running SMILE job with a short per-command timeout: the killed wrapper
  leaves an **orphaned `nusPipe`** process holding multiple GB. Reap strays with
  `pkill -9 -f nusPipe` before retrying.

## Windows / WSL2 workaround

**This section is documented, untested.** No Windows host has been confirmed available
during this milestone's development, so the steps below are the expected, standard path
based on WSL2 behaving like a Linux userspace — they have not been run end-to-end on
real Windows hardware. Treat this as a starting point, not a verified recipe.

1. Install WSL2 with an Ubuntu (or other mainstream) Linux distribution:
   `wsl --install` from an elevated PowerShell prompt, then reboot if prompted.
2. Inside the WSL2 Linux userspace, install `csh`/`tcsh` via the distro's package
   manager (e.g. `sudo apt install csh tcsh` on Ubuntu/Debian) — these are not installed
   by default on a minimal WSL2 image.
3. Download and install the **native Linux** NMRPipe build (not a Windows build — none
   exists) plus the separate SMILE companion plugin, following the Linux install steps
   from <https://www.ibbr.umd.edu/nmrpipe/install>, entirely inside the WSL2 Linux
   filesystem.
4. Source the Linux `nmrInit.<platform>.com` environment script and add `bin/` to
   `PATH` inside the WSL2 shell profile (e.g. `~/.bashrc` or `~/.cshrc`, matching
   whichever login shell you use inside WSL2).
5. Install `lucy-ng` itself inside the WSL2 Linux environment (not on native Windows
   Python) so that `subprocess.run()` calls to `nmrPipe`/`bruk2pipe`/`nusExpand.tcl`
   resolve against the WSL2 `PATH`, not the Windows one.
6. Verify with `lucy nus check` **run from inside the WSL2 shell** — this is the same
   Linux-native check path described in the Platform Matrix above, just executing inside
   the WSL2 userspace rather than a standalone Linux machine.

Because this workaround is untested, do not treat a clean `lucy nus check` pass inside
WSL2 as a guarantee that the full `reconstruct`/`pipeline` chain behaves identically to a
native Linux or macOS run — file/path translation quirks between the Windows host
filesystem and the WSL2 Linux filesystem (e.g. mounting Bruker experiment directories
from a Windows drive under `/mnt/c/...`) are a plausible, unverified source of
divergence and are explicitly out of scope for this phase (see `RECON-F2` / NMRFx
native-Windows backend pivot as the deferred, longer-term alternative).

## Apple Silicon Rosetta status: soft warning only

If `lucy nus check` reports `platform.rosetta_translated: true` (i.e. the Python
interpreter itself, and therefore the tools it shells out to, are running under Rosetta 2
x86_64 emulation rather than natively), this is a **soft warning, not a block**. The
native `mac11_arm64` build is strongly preferred (faster, no emulation overhead), but an
x86_64 build under Rosetta is tolerated and the pipeline proceeds if the tools are
otherwise present and working. Only a genuinely missing backend binary or missing
`csh`/`tcsh` interpreter is treated as critical (PORT-01 / D-05).

## Design note: no Windows-specific detection code

`lucy nus check`'s platform preflight (`src/lucy_ng/nus/platform_check.py`) is built from
generic, cross-platform stdlib primitives only: `platform.machine()`,
`platform.system()`, and `shutil.which("csh")`/`shutil.which("tcsh")`. There is
deliberately no `if platform.system() == "Windows"` branch anywhere in this code. The
existing generic checks already fail correctly on Windows (no `csh`/`tcsh`, no NMRPipe
binaries on `PATH`) without needing Windows-specific logic — adding such a branch would
only duplicate behavior the generic checks already provide correctly.

## Pitfalls carried forward from the milestone-level research

- **Linux 32-bit library caveat:** some older Linux distributions historically required
  32-bit compatibility libraries for certain NMRPipe binaries. If `lucy nus check`
  reports a binary present on `PATH` but the binary fails to execute, check your distro's
  32-bit compatibility package availability.
- **X11/XQuartz — SUPERSEDED, see the hard-dependency section above.** This entry
  previously described XQuartz as an optional mitigation relevant only to the `nmrDraw`
  GUI. The Phase-100 real-data run disproved that: `nusExpand.tcl` runs under
  `nmrWish.exe`, which is link-time bound to `libX11`, so **XQuartz is required on the
  reconstruction path** even for fully headless use.
- **SMILE memory footprint — see the memory-requirement section above.** Budget ≥ 8 GB
  free RAM; the failure mode is an `OMP`/`Cannot allocate memory` abort that reads like a
  thread-count problem but is not.
- **Gatekeeper quarantine:** freshly downloaded NMRPipe binaries/dylibs carry
  `com.apple.quarantine` and are refused at load time with a *"code signature not valid"*
  error until cleared (`xattr -c`). See the install walkthrough.
