"""NUS reconstruction stage orchestration primitives.

This module is the NUS analog of `lucy_ng.lsd.runner.LSDRunner`: it owns the
one shared, fail-loud subprocess wrapper every external-tool stage
(bruk2pipe, nusExpand.tcl, SMILE, post-processing) must call, plus the
FnMODE-driven stage-order recipe table (Critical Finding 1 of
98-RESEARCH.md: the bruk2pipe <-> nusExpand.tcl invocation order is
FnMODE-dependent, not fixed).

Wave 1 (Plan 02) ships only these two foundation primitives -- `run_stage()`
and the FnMODE recipe/`_ordering_for_fnmode()` helper. No orchestration
(`NusRunner.reconstruct()`) or backend invocation lives here yet; those are
built in Plans 03/05 on top of these primitives.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import nmrglue as ng

from lucy_ng.models.nus import COMPLEX_FNMODES, REAL_FNMODES

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
            for existence, non-emptiness, and (for `.fid`/`.ft2` outputs)
            non-all-zero parsed data.
        timeout: Maximum seconds to allow the subprocess to run.

    Raises:
        RuntimeError: On non-zero exit code, on a missing/empty
            `expected_output`, or on an `.fid`/`.ft2` output that is
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
    if expected_output.suffix in {".fid", ".ft2"}:
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
