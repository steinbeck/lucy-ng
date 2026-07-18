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
| **macOS Apple Silicon (native)** | Yes — `mac11_arm64` | Present by default (`/bin/csh`, `/bin/tcsh`) | `status: available`, `platform.rosetta_translated: false`, no critical or soft issues | **Supported, verified locally** (this dev machine: arm64, macOS 26.5, `sysctl.proc_translated=0`) |
| **Linux (native)** | Yes — native Linux builds distributed on the same install page | Present on essentially every distro (install via package manager if missing) | `status: available`, `platform.os: Linux`, no critical issues | **Supported** (historical 32-bit-library caveat on some older distros — see Pitfalls below) |
| **Windows (WSL2 gap)** | **No** — no native NMRPipe build has been distributed since v8.9 | **No** native `csh`/`tcsh` on Windows | `status: not_installed` (no binaries on PATH) AND a critical `csh`/`tcsh`-missing platform issue — both fire and hard-block `reconstruct`/`pipeline` with no Windows-specific code required | **Gap — documented workaround only, see below** |

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

1. Download the native `mac11_arm64` NMRPipe build **and** the separate SMILE companion
   plugin (`plugin.smile.tZ`) from <https://www.ibbr.umd.edu/nmrpipe/install>.
2. Extract both into the same NMRPipe installation tree.
3. Source the architecture-specific environment script,
   `nmrInit.mac11_arm64.com` (a manual, registration-adjacent step that edits your shell
   startup file — not automatable, and not attempted by this codebase; a fresh
   login/shell may be required for the sourced environment to take effect).
4. Add the NMRPipe `bin/` directory to `PATH`.
5. Verify with:

   ```bash
   lucy nus check     # must report backend "available" and the platform
                       # section clear of any critical issues
   ```

   If `lucy nus check` reports `smile_plugin_missing`, revisit step 1 — the SMILE
   plugin was not installed (see the gotcha above).

Only `nmrDraw` (the GUI spectrum viewer) is documented as macOS-problematic upstream, and
lucy-ng never invokes it — only the CLI/scriptable tools `nmrPipe`, `bruk2pipe`, and
`nusExpand.tcl` are used by the reconstruction pipeline, all of which run natively on
Apple Silicon with no Rosetta or virtualization required.

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
- **X11/XQuartz:** upstream install docs mention X11/XQuartz setup in the context of
  `nmrDraw` (the GUI viewer), which lucy-ng never invokes. If any CLI-only tool
  (`nmrPipe`, `bruk2pipe`, `nusExpand.tcl`) unexpectedly fails to launch with an
  X11-library-linkage error, installing XQuartz anyway is a cheap mitigation to try
  before treating it as a genuine platform blocker.
