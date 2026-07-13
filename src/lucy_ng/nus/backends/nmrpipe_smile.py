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
``subprocess.run`` (never a shell-invocation flag, never user input
interpolated).

Phase 98 (Plan 03) adds two more methods to this same class, split around
the F2 (direct-dimension) processing step SMILE requires to run first
(SMILE manual Sec.4/Sec.6.1):

* ``convert()`` -- FnMODE-branched Bruker-to-NMRPipe conversion
  (``bruk2pipe``/``nusExpand.tcl``), producing a converted, still
  time-domain FID. It does **not** call SMILE -- the direct dimension must
  still be apodized/zero-filled/Fourier-transformed/phased and transposed
  (``lucy_ng.nus.postprocess.process_direct()``, Plan 04) before
  reconstruction can run.
* ``reconstruct_indirect()`` -- runs SMILE on that already
  F2-processed, transposed FID (never the raw ``convert()`` output).

Both route every external call through
``lucy_ng.nus.runner.run_stage()`` (RECON-04's fail-loud wrapper),
imported with a deferred import inside each method body -- this avoids a
runner<->backend import cycle now that ``nus/runner.py`` is expected to
grow a ``get_backend()``-based orchestrator (Plan 05) that itself imports
from ``nus/backends/``.
"""

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lucy_ng.models.nus import NusAcquisitionParams, NusSchedule
    from lucy_ng.nus.runner import FnModeRecipe

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

    @staticmethod
    def _bruk2pipe_argv(
        *,
        input_path: Path,
        output_path: Path,
        params: "NusAcquisitionParams",
        f1_grid_size: int,
        recipe: "FnModeRecipe",
        aq2d: str,
    ) -> list[str]:
        """Build the `bruk2pipe` argument list shared by both convert() branches.

        `f1_grid_size` is the F1 (indirect) dimension point count to pass as
        `-yN`/`-yT` -- the caller decides whether that is the full expanded
        grid (`NusSchedule.nus_td`, echo-antiecho/expand_first branch, per
        98-RESEARCH.md Critical Finding 2) or the still-sparse acquisition
        count (`NusAcquisitionParams.f1_td`, QF/magnitude/convert_first
        branch, since expansion has not run yet in that branch).

        `-xCAR`/`-yCAR` (ppm carrier calibration) and Bruker byte-swap flags
        (`-aswap`/`-noaswap`) are intentionally omitted here: `F2`'s carrier
        (O1) is not part of `NusAcquisitionParams` (only F1's `f1_o1` is,
        see `models/nus.py`), and ppm calibration itself is
        `postprocess.py`'s job (Plan 04, cross-checked against the 1D
        reference per RECON-02/D-02) -- omitting them here does not
        silently produce a wrong *conversion*, only an uncalibrated one that
        Plan 04 calibrates afterward.
        """
        return [
            "bruk2pipe",
            "-in",
            str(input_path),
            "-grpdly",
            str(params.grpdly),
            "-decim",
            str(params.decim),
            "-dspfvs",
            str(params.dspfvs),
            "-xN",
            str(params.f2_td),
            "-yN",
            str(f1_grid_size),
            "-xT",
            str(params.f2_td // 2),
            "-yT",
            str(f1_grid_size // 2),
            "-xMODE",
            "DQD",
            "-yMODE",
            recipe.bruk2pipe_ymode,
            "-xSW",
            str(params.f2_sw_h),
            "-ySW",
            str(params.f1_sw_h),
            "-xOBS",
            str(params.f2_sfo1),
            "-yOBS",
            str(params.f1_sfo1),
            "-xLAB",
            params.f2_nucleus,
            "-yLAB",
            params.f1_nucleus,
            "-ndim",
            "2",
            "-aq2D",
            aq2d,
            "-out",
            str(output_path),
            "-verb",
            "-ov",
        ]

    @classmethod
    def convert(
        cls,
        expdir: Path,
        params: "NusAcquisitionParams",
        schedule: "NusSchedule",
        stage_dir: Path,
        *,
        timeout: int = 600,
    ) -> Path:
        """FnMODE-branched Bruker -> NMRPipe conversion (RECON-01/RECON-03).

        Dispatches `bruk2pipe`/`nusExpand.tcl` fully automatically, in the
        FnMODE-dependent order the official SMILE manual documents
        (98-RESEARCH.md Critical Finding 1):

        * `recipe.stage_order == "expand_first"` (echo-antiecho HSQC/HMBC,
          FnMODE 4/5/6): `nusExpand.tcl` runs on the sparse Bruker `ser`
          BEFORE `bruk2pipe`, so bruk2pipe converts the already-expanded,
          sorted `ser_full` and handles the Echo-AntiEcho N/P reshuffling
          natively during conversion -- the manual's own fully-worked path.
        * `recipe.stage_order == "convert_first"` (QF/magnitude COSY,
          FnMODE 1/2): reversed order -- `bruk2pipe` runs first on the raw
          sparse `ser`, `nusExpand.tcl` expands the resulting `.fid`
          afterward. **PROVISIONAL** per 98-RESEARCH.md Assumptions Log
          A1/A3: the SMILE manual does not fully work this branch through
          (only states "the other approach can be used too") -- requires
          an implementation-time spike against real C20H32O2 exp2 COSY
          data, cross-checked against the COSY diagonal-symmetry pitfall
          check, before this branch is trusted unattended.

        `bruk2pipe`'s `-yN`/`-yT` F1 grid-size flags always use
        `NusSchedule.nus_td` for the *post-expansion* conversion
        (`expand_first`) -- never the sparse `NusAcquisitionParams.f1_td`
        and never a re-derived `max(nuslist)+1` (Critical Finding 2).

        IMPORTANT: this method does NOT call SMILE. Its output
        (`converted.fid`) is a TIME-DOMAIN FID that must still be
        F2-processed (apodized/zero-filled/Fourier-transformed/phased) and
        transposed by `lucy_ng.nus.postprocess.process_direct()` (Plan 04)
        BEFORE `reconstruct_indirect()` can run (SMILE manual Sec.4).

        Args:
            expdir: Bruker NUS experiment directory (contains `ser`,
                `nuslist`, `acqus`, `acqu2s`).
            params: Already-parsed `NusAcquisitionParams` (Phase 97) --
                never re-parsed here.
            schedule: Already-parsed `NusSchedule` (Phase 97) -- never
                re-parsed here.
            stage_dir: Directory intermediates are written to (D-03:
                persistent, kept by default -- `mkdir(parents=True,
                exist_ok=True)`, never `shutil.rmtree`'d by this method).
            timeout: Per-stage subprocess timeout in seconds, forwarded to
                `run_stage()`.

        Returns:
            Path to the converted FID (`stage_dir/converted.fid`).

        Raises:
            NotImplementedError: If `params.fnmode_f1` has no known
                stage-order recipe (propagated from `recipe_for_fnmode`).
            RuntimeError: Propagated from `run_stage()` on any stage
                failure (non-zero exit, missing/empty/all-zero output).
        """
        from lucy_ng.nus.runner import recipe_for_fnmode, run_stage

        expdir = Path(expdir).resolve()
        stage_dir = Path(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)

        recipe = recipe_for_fnmode(params.fnmode_f1)
        converted_fid = stage_dir / "converted.fid"
        aq2d = "States" if recipe.phase_sensitive else "Magnitude"

        if recipe.stage_order == "expand_first":
            # Echo-AntiEcho/States/States-TPPI (FnMODE 4/5/6): fully worked
            # path per SMILE manual Sec.4/Sec.6.1 -- expand the sparse
            # Bruker `ser` to the full grid BEFORE conversion so bruk2pipe
            # handles the Echo-AntiEcho N/P reshuffling natively.
            ser_full = stage_dir / "ser_full"
            expand_argv = [
                "nusExpand.tcl",
                "-mode",
                "bruker",
                "-sampleCount",
                str(schedule.n_sampled),
                "-in",
                str(expdir / "ser"),
                "-out",
                str(ser_full),
                "-sample",
                str(expdir / "nuslist"),
            ]
            run_stage(
                "nusExpand.tcl",
                expand_argv,
                cwd=stage_dir,
                expected_output=ser_full,
                timeout=timeout,
            )

            bruk2pipe_argv = cls._bruk2pipe_argv(
                input_path=ser_full,
                output_path=converted_fid,
                params=params,
                f1_grid_size=schedule.nus_td,
                recipe=recipe,
                aq2d=aq2d,
            )
            run_stage(
                "bruk2pipe",
                bruk2pipe_argv,
                cwd=stage_dir,
                expected_output=converted_fid,
                timeout=timeout,
            )
        elif recipe.stage_order == "convert_first":
            # QF/magnitude COSY (FnMODE 1/2) -- implemented in Task 2 of
            # this plan (98-03), PROVISIONAL per 98-RESEARCH.md Assumptions
            # Log A1/A3. Not yet implemented at this commit.
            raise NotImplementedError(
                "convert_first (QF/magnitude) stage order not yet implemented "
                "-- see Task 2 of 98-03-PLAN.md"
            )
        else:  # pragma: no cover -- recipe_for_fnmode only returns the two
            # branches handled above; defensive, mirrors the "unreachable"
            # convention in nus/runner.py::recipe_for_fnmode.
            raise NotImplementedError(
                f"convert() has no recipe for stage_order={recipe.stage_order!r}"
            )

        return converted_fid

    @classmethod
    def reconstruct_indirect(
        cls,
        f2_processed_fid: Path,
        *,
        nuslist_path: Path,
        stage_dir: Path,
        fnmode: int = 6,
        max_iter: int = 500,
        threshold: float = 0.8,
        n_sigma: int = 5,
        virtual_echo: bool = True,
        f1_p0: float = 90.0,
        f1_p1: float = 0.0,
        timeout: int = 600,
    ) -> Path:
        """Run SMILE on the F2-processed, transposed FID (RECON-01/RECON-02).

        The input is `f2_processed_fid` -- the transposed, direct-dimension
        -processed FID produced by `lucy_ng.nus.postprocess.process_direct()`
        (Plan 04) -- NEVER the raw, still-time-domain FID `convert()`
        returns. SMILE manual Sec.4: "the direct dimension must be first
        apodized, zero filled, Fourier transformed, and phased... before...
        the SMILE function can be called." The parameter name makes this
        contract explicit so a caller cannot accidentally wire in
        `convert()`'s own output here.

        `-maxIter` is an upper bound only (RECON-05 rationale,
        98-RESEARCH.md Pitfall "`-maxIter` treated as the primary stopping
        criterion") -- the real stopping rule is the noise-threshold
        convergence check (`-nSigma`/`-thresh`), never a fixed iteration
        count alone.

        `-EA` (virtual echo / Echo-AntiEcho reconstruction) is only passed
        when `fnmode`'s recipe marks it applicable (echo-antiecho only,
        `FnModeRecipe.smile_ea`) AND `virtual_echo` is True -- QF/magnitude
        FnMODEs (1/2) never receive `-EA`.

        Args:
            f2_processed_fid: The transposed, F2-processed FID (Plan 04's
                `process_direct()` output) -- SMILE's actual input.
            nuslist_path: Path to the (unmodified) Bruker `nuslist` file,
                passed to SMILE's `-sample` flag.
            stage_dir: Directory intermediates are written to (D-03:
                persistent, kept by default).
            fnmode: `acqu2s FnMODE` (F1/indirect dimension) -- determines
                whether `-EA` applies via `recipe_for_fnmode`. Defaults to
                6 (echo-antiecho, the common HSQC/HMBC case).
            max_iter: SMILE `-maxIter` upper bound (default 500, per the
                SMILE manual's own high-iteration-count recommendation for
                final reconstructions).
            threshold: SMILE `-thresh` value (default 0.8).
            n_sigma: SMILE `-nSigma` noise-threshold convergence value
                (default 5).
            virtual_echo: Whether to request virtual-echo/Echo-AntiEcho
                reconstruction (`-EA`) when the FnMODE recipe allows it.
                Default True (virtual echo is default-on for
                echo-antiecho/causal-signal construction).
            f1_p0: SMILE's `-xP0` zero-order F1 phase (default 90.0 --
                PROVISIONAL per 98-RESEARCH.md Assumptions Log A2: verified
                only against the manual's own unrelated TROSY example, not
                this project's `hsqcedetgpsp.3`/`hmbcetgpl3nd` pulse
                sequences; CLI-overridable per D-02).
            f1_p1: SMILE's `-xP1` first-order F1 phase (default 0.0).
            timeout: Per-stage subprocess timeout in seconds, forwarded to
                `run_stage()`.

        Returns:
            Path to the reconstructed file (`stage_dir/reconstructed.ft1`).

        Raises:
            NotImplementedError: If `fnmode` has no known recipe
                (propagated from `recipe_for_fnmode`).
            RuntimeError: Propagated from `run_stage()` on any stage
                failure (non-zero exit, missing/empty/all-zero output).
        """
        from lucy_ng.nus.runner import recipe_for_fnmode, run_stage

        f2_processed_fid = Path(f2_processed_fid)
        nuslist_path = Path(nuslist_path)
        stage_dir = Path(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)

        recipe = recipe_for_fnmode(fnmode)
        reconstructed = stage_dir / "reconstructed.ft1"

        argv = [
            "nmrPipe",
            "-in",
            str(f2_processed_fid),
            "-fn",
            "SMILE",
            "-nDim",
            "2",
            "-sample",
            str(nuslist_path),
            "-maxIter",
            str(max_iter),
            "-nSigma",
            str(n_sigma),
            "-thresh",
            str(threshold),
            "-xP0",
            str(f1_p0),
            "-xP1",
            str(f1_p1),
        ]
        if recipe.smile_ea and virtual_echo:
            argv.append("-EA")
        argv.extend(["-out", str(reconstructed), "-verb", "-ov"])

        run_stage(
            "SMILE",
            argv,
            cwd=stage_dir,
            expected_output=reconstructed,
            timeout=timeout,
        )
        return reconstructed
