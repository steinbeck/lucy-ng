"""PORT-01 platform preflight detection: arch, Rosetta translation, csh/tcsh.

Stdlib-only (``platform``, ``shutil``, ``subprocess``) -- never a new
``pyproject.toml`` dependency, mirroring
``lucy_ng.nus.backends.nmrpipe_smile``'s own runtime-detection convention
(``shutil.which`` first, fixed-arg-list ``subprocess.run``, never
``shell=True``).

This module answers three independent questions, none of which
``NmrPipeSmileBackend.diagnose()`` currently reports:

1. What CPU architecture / OS is this process actually running on
   (``platform.machine()``/``platform.system()``)?
2. Is this process a genuinely-native Apple-Silicon process, or is it
   running under Rosetta 2 x86_64 translation (macOS-only; ``None`` when
   not applicable -- Linux, genuine Intel, or an errored probe)?
3. Are the ``csh``/``tcsh`` shell interpreters present on PATH? NMRPipe
   utility scripts (``bruk2pipe``, ``nusExpand.tcl``) are themselves
   csh/tcsh-shebanged scripts -- even though lucy-ng invokes them via a
   direct ``subprocess.run(["bruk2pipe", ...])`` call (never a piped csh
   chain), the OS still needs a csh/tcsh interpreter on PATH to execute the
   script via its shebang line (RESEARCH.md Pitfall 4).

Per D-05: a missing csh AND missing tcsh interpreter is a CRITICAL issue;
running under Rosetta translation (tools otherwise present) is a SOFT
warning only. No Windows-specific branch is added -- the generic csh/tcsh
+ missing-tools checks already degrade correctly there (RESEARCH.md
Anti-Patterns).
"""

import platform
import shutil
import subprocess
from typing import Any


def _rosetta_translated() -> bool | None:
    """Detect whether THIS process is running under Rosetta 2 translation.

    Only meaningful on macOS (Apple-Silicon-capable) -- the
    ``sysctl.proc_translated`` OID does not exist elsewhere. Any non-"0"/
    "1" output (including a genuine Intel Mac, a non-Apple-Silicon-capable
    macOS version, a missing ``sysctl`` binary, or a subprocess
    error/timeout) resolves to ``None`` ("not applicable") -- NEVER
    coerced to ``False`` (RESEARCH.md Pitfall 3: never call ``int()``
    unconditionally on the probe's output).

    Returns:
        True if translated, False if native, None if not applicable/
        indeterminate. Never raises.
    """
    if platform.system() != "Darwin":
        return None
    try:
        proc = subprocess.run(
            ["sysctl", "-n", "sysctl.proc_translated"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = proc.stdout.strip()
    if output == "1":
        return True
    if output == "0":
        return False
    return None


def detect_platform() -> dict[str, Any]:
    """Detect this process's architecture/OS/Rosetta/csh-tcsh status.

    Returns:
        A dict with keys:
          - arch: `platform.machine()` (e.g. "arm64", "x86_64").
          - os: `platform.system()` (e.g. "Darwin", "Linux", "Windows").
          - rosetta_translated: True/False/None (None = not applicable/
            indeterminate -- never a false negative on non-Darwin/genuine
            Intel systems).
          - csh_available: True if `shutil.which("csh")` is not None.
          - tcsh_available: True if `shutil.which("tcsh")` is not None.
          - critical_platform_issues: list[str] -- D-05 critical gaps
            (missing csh AND tcsh) that must fail-loud block reconstruct/
            pipeline.
          - soft_platform_warnings: list[str] -- D-05 soft conditions
            (running under Rosetta translation) that warn but never block.
    """
    csh_available = shutil.which("csh") is not None
    tcsh_available = shutil.which("tcsh") is not None
    rosetta_translated = _rosetta_translated()

    critical_platform_issues: list[str] = []
    if not csh_available and not tcsh_available:
        critical_platform_issues.append(
            "no csh/tcsh interpreter found on PATH -- NMRPipe utility "
            "scripts (bruk2pipe, nusExpand.tcl) are csh/tcsh-shebanged and "
            "require one of these interpreters to execute, even though "
            "lucy-ng invokes them via a direct subprocess call."
        )

    soft_platform_warnings: list[str] = []
    if rosetta_translated is True:
        soft_platform_warnings.append(
            "running under Rosetta 2 x86_64 translation -- a native "
            "Apple-Silicon (arm64) NMRPipe build is recommended; this is a "
            "soft warning only and does not block reconstruction."
        )

    return {
        "arch": platform.machine(),
        "os": platform.system(),
        "rosetta_translated": rosetta_translated,
        "csh_available": csh_available,
        "tcsh_available": tcsh_available,
        "critical_platform_issues": critical_platform_issues,
        "soft_platform_warnings": soft_platform_warnings,
    }
