"""NMRPipe + SMILE NUS reconstruction backend detection.

SMILE (Sparse Multidimensional Iterative Lineshape Enhanced) is delivered as
an *nmrPipe plugin function* (``nmrPipe -fn SMILE``), not a standalone
binary. Its underlying executable (``nusPipe``) is an NMRPipe-internal
implementation detail invoked via NMRPipe's own plugin-dispatch environment
variables (``NMR_PLUGIN_FN``/``NMR_PLUGIN_EXE``) -- it is not meant to be
``shutil.which()``'d directly, and there is no plugin-named binary combining
"smile" and "nus" in that order on any platform (verified against the SMILE
User's Manual, Sections 1-2).

Detection therefore uses two tiers:

1. Real, independently-``which()``-able tools: ``nmrPipe``, ``bruk2pipe``,
   ``nusExpand.tcl`` (``REQUIRED_TOOLS``, ``missing_tools()``).
2. A capability probe for the SMILE plugin itself: ``nmrPipe -fn SMILE
   -help`` (``smile_plugin_available()``) -- this is the exact verification
   command the SMILE manual instructs users to run.

Mirrors the ``lucy_ng.lsd.runner.LSDRunner`` external-binary detection
pattern: classmethods, ``shutil.which`` first, fixed-arg-list
``subprocess.run`` (never ``shell=True``, never user input interpolated).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

#: Real, independently-`which()`-able binaries/scripts required by the
#: NMRPipe+SMILE reconstruction pipeline. Deliberately does NOT include a
#: standalone "SMILE" binary name -- see module docstring.
REQUIRED_TOOLS = ["nmrPipe", "bruk2pipe", "nusExpand.tcl"]

#: Common NMRPipe installation base directories, used only to distinguish
#: "not installed" from "installed but not sourced" in diagnose().
COMMON_NMRBASE_DIRS = ["~/.nmrpipe", "~/nmrpipe", "/opt/nmrpipe"]

_INSTALL_URL = "https://www.ibbr.umd.edu/nmrpipe/install"


class NmrPipeSmileBackend:
    """NMRPipe + SMILE reconstruction backend (external, runtime-detected).

    Never a core `pyproject.toml` dependency -- availability is probed at
    runtime via `shutil.which`/subprocess, exactly like `LSDRunner`.
    """

    # Real, independently-`which()`-able binaries/scripts.
    REQUIRED_TOOLS = REQUIRED_TOOLS

    @classmethod
    def missing_tools(cls) -> list[str]:
        """Return the subset of REQUIRED_TOOLS not found on PATH.

        Returns:
            List of tool names missing from PATH (empty if all present).
        """
        return [t for t in cls.REQUIRED_TOOLS if shutil.which(t) is None]

    @classmethod
    def smile_plugin_available(cls) -> bool:
        """Probe whether nmrPipe's SMILE plugin function is available.

        SMILE is an nmrPipe plugin function, not a standalone binary --
        detected via capability probe (per the SMILE manual's own
        recommended verification command), never `shutil.which()`.

        Short-circuits to False without launching a subprocess when
        `nmrPipe` itself is not on PATH.

        Returns:
            True if the probe succeeds, False otherwise (never raises).
        """
        if shutil.which("nmrPipe") is None:
            return False
        try:
            proc = subprocess.run(
                ["nmrPipe", "-fn", "SMILE", "-help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        # SMILE's -help prints its own usage block ("SMILE: Sparse
        # Multidimensional Iterative Lineshape Enhanced.") on success; a
        # missing plugin causes nmrPipe to report an unknown function.
        combined = (proc.stdout + proc.stderr).lower()
        return "smile" in combined and "unknown function" not in combined

    @classmethod
    def is_available(cls) -> bool:
        """Check if the full NMRPipe+SMILE backend is usable.

        Returns:
            True only if all REQUIRED_TOOLS are on PATH AND the SMILE
            plugin capability probe succeeds. Never raises.
        """
        return not cls.missing_tools() and cls.smile_plugin_available()

    @classmethod
    def diagnose(cls) -> dict[str, Any]:
        """Distinguish 'not installed' from 'installed but not sourced'.

        Returns:
            A dict with keys:
              - status: one of "available", "smile_plugin_missing",
                "installed_not_sourced", "not_installed"
              - missing_tools: list of REQUIRED_TOOLS not found on PATH
              - smile_available: bool
              - hint: actionable install/source guidance (non-empty,
                contains an install URL)
        """
        missing = cls.missing_tools()
        if not missing:
            smile_ok = cls.smile_plugin_available()
            return {
                "status": "available" if smile_ok else "smile_plugin_missing",
                "missing_tools": [],
                "smile_available": smile_ok,
                "hint": (
                    "NMRPipe+SMILE backend fully available."
                    if smile_ok
                    else (
                        "nmrPipe, bruk2pipe, and nusExpand.tcl are all on "
                        "PATH, but the SMILE plugin capability probe "
                        "(`nmrPipe -fn SMILE -help`) failed. The SMILE "
                        "plugin may not be installed for this NMRPipe "
                        f"installation. Install docs: {_INSTALL_URL}"
                    )
                ),
            }
        # Distinct diagnostic: is nmrPipe present anywhere common but not
        # on PATH? (mirrors LSDRunner.SEARCH_PATHS fallback, adapted to
        # NMRPipe's $NMRBASE convention.)
        hint_found = any(
            Path(p).expanduser().exists() for p in COMMON_NMRBASE_DIRS
        )
        return {
            "status": "installed_not_sourced" if hint_found else "not_installed",
            "missing_tools": missing,
            "smile_available": False,
            "hint": (
                "NMRPipe appears installed but its tools are not on PATH — "
                "did you source its environment? Typically: "
                "`source ~/.nmrpipe/com/nmrInit.<platform>.com` or the "
                "equivalent line added to `.cshrc` by NMRPipe's own "
                f"install.com. Install docs: {_INSTALL_URL}"
                if hint_found
                else f"NMRPipe not found. Install (free registration required): {_INSTALL_URL}"
            ),
        }
