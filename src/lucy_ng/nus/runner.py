"""NUS reconstruction stage orchestration primitives.

This module is the NUS analog of `lucy_ng.lsd.runner.LSDRunner`: it owns the
one shared, fail-loud subprocess wrapper every external-tool stage
(bruk2pipe, nusExpand.tcl, SMILE, post-processing) must call, plus the
FnMODE-driven stage-order recipe table (Critical Finding 1 of
98-RESEARCH.md: the bruk2pipe <-> nusExpand.tcl invocation order is
FnMODE-dependent, not fixed).

Plan 02 shipped the two foundation primitives (`run_stage()` and the FnMODE
recipe/`_ordering_for_fnmode()` helper). Plan 05 (this addition) adds
`NusRunner` -- the whole-pipeline orchestrator: `reconstruct(expdir)` reads
Phase 97's `NusAcquisitionParams`/`NusSchedule` exactly once, owns the
`analysis/nus_recon/<expN>/` stage-dir lifecycle (D-03: persistent, kept --
no `rmtree`), enforces the F2-before-F1 hard ordering gate as an explicit
precondition that raises BEFORE any subprocess is dispatched (RECON-02), and
dispatches the four physically-ordered stages (SMILE manual Sec.4/Sec.6.1):
`backend.convert()` -> `postprocess.process_direct()` (F2 + transpose,
SMILE's actual input) -> `backend.reconstruct_indirect()` (SMILE) ->
`postprocess.process_indirect()` (post-SMILE F1 + transpose + ppm
calibration).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import nmrglue as ng

from lucy_ng.models.nus import (
    COMPLEX_FNMODES,
    REAL_FNMODES,
    NusAcquisitionParams,
    NusReconstructionResult,
)
from lucy_ng.nus.backends import get_backend
from lucy_ng.nus.params import read_nus_params
from lucy_ng.nus.postprocess import process_direct, process_indirect
from lucy_ng.nus.schedule import read_nus_schedule

#: The two stage-order branches this project has verified against the
#: official SMILE manual (98-RESEARCH.md Critical Finding 1). Any FnMODE
#: outside REAL_FNMODES/COMPLEX_FNMODES has no known recipe -- refuse to
#: guess (mirrors nus/schedule.py's expected_sample_count() convention).
StageOrder = Literal["expand_first", "convert_first"]


def run_stage(
    name: str,
    argv: list[str],
    cwd: Path,
    expected_output: Path,
    timeout: int = 600,
) -> None:
    """Run one external-tool subprocess stage with a fail-loud output check.

    The single correctness anchor for RECON-04: every external call in this
    phase (bruk2pipe, nusExpand.tcl, SMILE, post-processing) must go through
    this helper rather than trusting a subprocess's own exit code alone
    (Pitfall 14 -- csh-piped NMRPipe stages can silently pass through
    truncated data).

    Args:
        name: Human-readable stage name, used in raised error messages
            (e.g. "bruk2pipe", "nusExpand.tcl", "SMILE").
        argv: Fixed argument list for `subprocess.run` -- never a shell
            string, never a shell-invocation flag.
        cwd: Working directory for the subprocess.
        expected_output: Path to the file this stage must produce. Checked
            for existence, non-emptiness, and (for `.fid`/`.ft1`/`.ft2`
            outputs) non-all-zero parsed data. `.ft1` is the SMILE
            reconstruction output (`reconstruct_indirect()`), the stage
            most prone to producing plausible-but-empty/all-zero data --
            it MUST receive the all-zero parse check, not just exists/size.
        timeout: Maximum seconds to allow the subprocess to run.

    Raises:
        RuntimeError: On non-zero exit code, on a missing/empty
            `expected_output`, or on an `.fid`/`.ft1`/`.ft2` output that is
            all-zero/truncated data.
    """
    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, cwd=cwd
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"NUS stage '{name}' failed (exit {proc.returncode}): "
            f"{proc.stderr[:500]!r}"
        )
    if not expected_output.exists() or expected_output.stat().st_size == 0:
        raise RuntimeError(
            f"NUS stage '{name}' reported success but output file "
            f"{expected_output} is missing or empty -- refusing to "
            "continue (csh-piped NMRPipe stages can silently pass through "
            "truncated data, Pitfall 14)."
        )
    if expected_output.suffix in {".fid", ".ft1", ".ft2"}:
        try:
            _dic, data = ng.fileio.pipe.read(str(expected_output))
            all_zero = data.size == 0 or not data.any()
        except Exception:
            # Not a well-formed NMRPipe file (e.g. too short a header to
            # parse at all) -- fall back to a raw byte-level all-zero
            # check so a genuinely truncated/corrupt intermediate is still
            # caught, without treating every parse failure as fatal (a
            # non-NMRPipe-format-but-non-empty file is out of scope for
            # this check; the exists()/size check above already ran).
            raw = expected_output.read_bytes()
            all_zero = len(raw) == 0 or raw == b"\x00" * len(raw)
        if all_zero:
            raise RuntimeError(
                f"NUS stage '{name}' output {expected_output} parses but "
                "is all-zero/empty data -- treat as a hard failure, not a "
                "legitimate empty result."
            )


def _ordering_for_fnmode(fnmode: int) -> StageOrder:
    """Resolve the bruk2pipe<->nusExpand.tcl stage order for a given FnMODE.

    Per the official SMILE manual (98-RESEARCH.md Critical Finding 1):
    running `nusExpand.tcl` *before* `bruk2pipe` is the recommended,
    fully-worked path for phase-sensitive (echo-antiecho/complex-pair)
    experiments, but the manual explicitly states this order "does not
    work" for magnitude-mode (QF) Bruker data -- which must instead run
    `bruk2pipe` first.

    Args:
        fnmode: `acqu2s FnMODE` (F1/indirect dimension).

    Returns:
        `"expand_first"` for `fnmode in COMPLEX_FNMODES` (4, 5, 6),
        `"convert_first"` for `fnmode in REAL_FNMODES` (1, 2).

    Raises:
        NotImplementedError: If `fnmode` is not a recognized real/complex
            mode -- refuses to guess (mirrors
            `nus/schedule.py::expected_sample_count()`).
    """
    if fnmode in COMPLEX_FNMODES:
        return "expand_first"
    if fnmode in REAL_FNMODES:
        return "convert_first"
    raise NotImplementedError(f"FnMODE={fnmode} has no known stage-order recipe")


@dataclass(frozen=True)
class FnModeRecipe:
    """Per-FnMODE reconstruction recipe (RECON-03's one auditable table).

    Captures the four things that differ by FnMODE per 98-RESEARCH.md
    Pattern 3: stage order, the `bruk2pipe -yMODE` value, whether F1 phase
    correction applies at all, and whether SMILE's `-EA` flag is passed.

    Attributes:
        stage_order: `"expand_first"` or `"convert_first"` -- see
            `_ordering_for_fnmode`.
        bruk2pipe_ymode: The literal string passed to `bruk2pipe -yMODE`.
        phase_sensitive: True for COMPLEX_FNMODES (echo-antiecho/States/
            States-TPPI); False for REAL_FNMODES (QF/QSEQ magnitude mode,
            e.g. COSY -- processed without phase correction).
        smile_ea: True if SMILE's `-EA` flag applies for this FnMODE
            (Echo-AntiEcho only, FnMODE=6).
    """

    stage_order: StageOrder
    bruk2pipe_ymode: str
    phase_sensitive: bool
    smile_ea: bool


# Per-FnMODE recipe table -- the single auditable place FnMODE-driven
# reconstruction behavior lives (RECON-03). `bruk2pipe -yMODE` string
# values for FnMODE 4/5/6 are directly confirmed against the SMILE
# manual's own worked scripts (98-RESEARCH.md Standard Stack /
# Critical Finding 1). The FnMODE 1/2 (QF/QSEQ magnitude) `-yMODE` value
# is PROVISIONAL per 98-RESEARCH.md Assumptions Log A3: only
# "Echo-AntiEcho"/"Complex"/"States" were directly confirmed via the
# manual's own worked scripts; a secondary source's mode-value list for
# magnitude mode was ambiguous/garbled. "QF" is bruk2pipe's own
# documented flag name for the Bruker QF acquisition mode, but has NOT
# been independently verified against a primary SMILE-manual example --
# flagged here, not asserted as confirmed. Verify via
# `bruk2pipe -yMODE -help` at implementation time before trusting this
# value unattended for the exp2 COSY branch.
_FNMODE_RECIPES: dict[int, FnModeRecipe] = {
    6: FnModeRecipe(
        stage_order="expand_first",
        bruk2pipe_ymode="Echo-AntiEcho",
        phase_sensitive=True,
        smile_ea=True,
    ),
    5: FnModeRecipe(
        stage_order="expand_first",
        bruk2pipe_ymode="States-TPPI",
        phase_sensitive=True,
        smile_ea=False,
    ),
    4: FnModeRecipe(
        stage_order="expand_first",
        bruk2pipe_ymode="States",
        phase_sensitive=True,
        smile_ea=False,
    ),
    2: FnModeRecipe(
        stage_order="convert_first",
        bruk2pipe_ymode="QSEQ",  # PROVISIONAL -- see Assumptions Log A3 above
        phase_sensitive=False,
        smile_ea=False,
    ),
    1: FnModeRecipe(
        stage_order="convert_first",
        bruk2pipe_ymode="QF",  # PROVISIONAL -- see Assumptions Log A3 above
        phase_sensitive=False,
        smile_ea=False,
    ),
}


def recipe_for_fnmode(fnmode: int) -> FnModeRecipe:
    """Return the `FnModeRecipe` for a given FnMODE.

    Args:
        fnmode: `acqu2s FnMODE` (F1/indirect dimension).

    Returns:
        The `FnModeRecipe` capturing stage order, `bruk2pipe -yMODE` value,
        phase-sensitivity, and SMILE `-EA` applicability for this FnMODE.

    Raises:
        NotImplementedError: If `fnmode` is not a recognized real/complex
            mode -- refuses to guess (mirrors `_ordering_for_fnmode`).
    """
    try:
        return _FNMODE_RECIPES[fnmode]
    except KeyError:
        # Delegate to _ordering_for_fnmode purely for its consistent
        # refuse-to-guess NotImplementedError message/behavior; it will
        # always raise here since _FNMODE_RECIPES and
        # REAL_FNMODES/COMPLEX_FNMODES cover the identical fnmode set.
        _ordering_for_fnmode(fnmode)
        raise AssertionError("unreachable")  # pragma: no cover


@dataclass(frozen=True)
class F2Plan:
    """Resolved direct-dimension (F2) processing plan (RECON-02 hard gate).

    `NusRunner._resolve_f2_plan()` returns this (or `None` if the plan
    cannot be resolved) BEFORE any subprocess is dispatched -- the explicit
    precondition that makes the F2-before-F1 ordering gate raise up front
    rather than fail partway through the pipeline.

    Attributes:
        magnitude: True when this FnMODE's recipe is magnitude-mode
            (`not recipe.phase_sensitive`, e.g. QF/QSEQ COSY) -- threaded
            into `postprocess.process_direct()`/`process_indirect()`'s own
            `magnitude` flag, which skips the `PS` phase-correction verb
            entirely for magnitude-mode data.
    """

    magnitude: bool


class NusRunner:
    """Whole-pipeline NUS reconstruction orchestrator (RECON-01/RECON-02).

    The NUS analog of `lucy_ng.lsd.runner.LSDRunner`: owns the
    `analysis/nus_recon/<expN>/` stage-dir lifecycle (D-03: persistent,
    kept -- never `shutil.rmtree`'d) and dispatches the four physically
    ordered reconstruction stages from one `reconstruct(expdir)` entrypoint.

    Does not implement its own binary detection/`SEARCH_PATHS` -- that
    already exists on the resolved backend (`NmrPipeSmileBackend`,
    Phase 97); `__init__` resolves a backend via `get_backend()` rather than
    re-implementing discovery.
    """

    def __init__(self, backend: Any | None = None) -> None:
        """Resolve the reconstruction backend.

        Args:
            backend: An object/class exposing `convert()` and
                `reconstruct_indirect()` (matching `NmrPipeSmileBackend`'s
                classmethod surface). Defaults to
                `get_backend()` (the registered `"nmrpipe_smile"` backend,
                Phase 97) when not supplied -- test doubles may pass their
                own fake backend here. Typed `Any` rather than a narrower
                Protocol/class type because both a classmethod-based
                backend *class* (the production default) and a plain
                instance test double (unit tests, this plan's own
                `_RecordingBackend`) are legitimate callers -- the real
                contract (`convert()`/`reconstruct_indirect()` signature
                compatibility) is enforced by the `NusBackend` Protocol at
                the registry boundary (`nus/backends/__init__.py`), not
                here.
        """
        self.backend: Any = backend if backend is not None else get_backend()

    def _stage_dir(self, expdir: Path) -> Path:
        """Return (and create) this experiment's persistent stage dir.

        D-03: `analysis/nus_recon/<expN>/` under the *resolved* experiment
        directory, `mkdir(parents=True, exist_ok=True)`'d -- KEPT, never
        `shutil.rmtree`'d by this method or any caller in this phase.

        Args:
            expdir: The (already-resolved) Bruker NUS experiment directory.

        Returns:
            The created stage directory
            (`expdir / "analysis" / "nus_recon" / expdir.name`).
        """
        expdir = Path(expdir).resolve()
        stage_dir = expdir / "analysis" / "nus_recon" / expdir.name
        stage_dir.mkdir(parents=True, exist_ok=True)
        return stage_dir

    def _resolve_f2_plan(self, params: NusAcquisitionParams) -> F2Plan | None:
        """Resolve the direct-dimension (F2) processing plan, or `None`.

        Consults `recipe_for_fnmode(params.fnmode_f1)` for the
        phase-sensitivity/magnitude split (RECON-03's single auditable
        FnMODE recipe table) -- returns `None` (never raises) when the
        FnMODE has no known recipe, so `reconstruct()`'s hard gate can
        raise its own, more specific `RuntimeError` before any subprocess
        is dispatched (RECON-02), rather than propagating a bare
        `NotImplementedError` from deep inside the pipeline.

        Args:
            params: Already-parsed `NusAcquisitionParams` (Phase 97).

        Returns:
            An `F2Plan` if `params.fnmode_f1` has a known recipe, else
            `None`.
        """
        try:
            recipe = recipe_for_fnmode(params.fnmode_f1)
        except NotImplementedError:
            return None
        return F2Plan(magnitude=not recipe.phase_sensitive)

    def reconstruct(
        self,
        expdir: str | Path,
        *,
        max_iter: int = 500,
        threshold: float = 0.8,
        n_sigma: int = 5,
        virtual_echo: bool = True,
        f1_p0: float = 90.0,
        f1_p1: float = 0.0,
        f2_p0: float = 0.0,
        f2_p1: float = 0.0,
        timeout: int = 600,
    ) -> NusReconstructionResult:
        """Run the whole NUS reconstruction + processing pipeline.

        Reads `NusAcquisitionParams`/`NusSchedule` exactly once (Phase 97's
        `read_nus_params`/`read_nus_schedule` -- never re-parsed), resolves
        this experiment's persistent stage dir (D-03), enforces the
        F2-before-F1 hard ordering gate as an explicit precondition BEFORE
        any subprocess is dispatched (RECON-02), then dispatches the four
        physically ordered stages (SMILE manual Sec.4/Sec.6.1):

        1. `self.backend.convert()` -- FnMODE-branched Bruker -> NMRPipe
           conversion (`converted.fid`).
        2. `postprocess.process_direct()` -- DIRECT (F2) processing +
           transpose (`f2_processed.fid`) -- SMILE's actual input.
        3. `self.backend.reconstruct_indirect()` -- SMILE, consuming
           `process_direct()`'s output, NEVER `convert()`'s raw output
           (`reconstructed.ft1`).
        4. `postprocess.process_indirect()` -- post-SMILE INDIRECT (F1)
           processing + transpose + ppm calibration (`processed.ft2`).

        Args:
            expdir: Bruker NUS experiment directory (contains `ser`,
                `nuslist`, `acqus`, `acqu2s`).
            max_iter: SMILE `-maxIter` upper bound (RECON-05), forwarded to
                `backend.reconstruct_indirect()`.
            threshold: SMILE `-thresh` value (RECON-05).
            n_sigma: SMILE `-nSigma` noise-threshold convergence value
                (RECON-05).
            virtual_echo: Whether to request virtual-echo/`-EA`
                reconstruction when the FnMODE recipe allows it (RECON-05).
            f1_p0: F1 zero-order phase (D-02 CLI-overridable constant),
                threaded into both `reconstruct_indirect()`'s `-xP0` and
                `process_indirect()`'s post-SMILE phase correction.
            f1_p1: F1 first-order phase. Same contract as `f1_p0`.
            f2_p0: F2 zero-order phase (D-02 CLI-overridable constant),
                threaded into `process_direct()`'s phase correction.
                PROVISIONAL default (0.0) -- no universal value exists
                across pulse sequences; a later plan exposes this as a CLI
                override once the correct empirical value is known for this
                project's own data.
            f2_p1: F2 first-order phase. Same contract as `f2_p0`.
            timeout: Per-stage subprocess timeout in seconds, forwarded to
                every stage.

        Returns:
            A `NusReconstructionResult` with `success=True`, `stage_dir` set
            to `analysis/nus_recon/<expN>/`, `stage_outputs` populated with
            all four stage paths, and `processed_spectrum` set to
            `process_indirect()`'s output.

        Raises:
            RuntimeError: If the F2 processing plan cannot be resolved
                (raised BEFORE any subprocess dispatch -- RECON-02 hard
                gate), or propagated from any stage's `run_stage()` failure.
            FileNotFoundError: Propagated from `read_nus_params`/
                `read_nus_schedule` if `expdir` does not exist.
            NotImplementedError: Propagated if `params.fnmode_f1` has no
                known stage-order/reconstruction recipe.
        """
        expdir = Path(expdir).resolve()
        params = read_nus_params(expdir)
        schedule = read_nus_schedule(expdir)
        stage_dir = self._stage_dir(expdir)

        # Hard gate (RECON-02): the F2 plan must be resolved BEFORE any
        # subprocess is dispatched -- checked first, raises immediately.
        f2_plan = self._resolve_f2_plan(params)
        if f2_plan is None:
            raise RuntimeError(
                "F2 (direct-dimension) processing plan not resolved -- "
                "refusing to start F1/SMILE reconstruction out of order "
                "(RECON-02 hard gate)."
            )

        converted = self.backend.convert(
            expdir, params, schedule, stage_dir, timeout=timeout
        )
        f2_processed = process_direct(
            converted,
            stage_dir,
            params,
            f2_p0=f2_p0,
            f2_p1=f2_p1,
            magnitude=f2_plan.magnitude,
            timeout=timeout,
        )
        reconstructed = self.backend.reconstruct_indirect(
            f2_processed,
            nuslist_path=expdir / "nuslist",
            stage_dir=stage_dir,
            fnmode=params.fnmode_f1,
            max_iter=max_iter,
            threshold=threshold,
            n_sigma=n_sigma,
            virtual_echo=virtual_echo,
            f1_p0=f1_p0,
            f1_p1=f1_p1,
            timeout=timeout,
        )
        processed = process_indirect(
            reconstructed,
            stage_dir,
            params,
            f1_p0=f1_p0,
            f1_p1=f1_p1,
            magnitude=f2_plan.magnitude,
            timeout=timeout,
        )

        return NusReconstructionResult(
            success=True,
            backend=getattr(self.backend, "__name__", type(self.backend).__name__),
            fnmode_f1=params.fnmode_f1,
            stage_dir=str(stage_dir),
            stage_outputs={
                "convert": str(converted),
                "process_direct": str(f2_processed),
                "smile": str(reconstructed),
                "process_indirect": str(processed),
            },
            processed_spectrum=str(processed),
            smile_iterations=None,
        )
