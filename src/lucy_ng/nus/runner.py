"""NUS reconstruction stage orchestration primitives.

This module is the NUS analog of `lucy_ng.lsd.runner.LSDRunner`: it owns the
one shared, fail-loud subprocess wrapper every external-tool stage
(bruk2pipe, nusExpand.tcl, SMILE, post-processing) must call.

Wave 1 (Plan 02) ships only the foundation primitives -- `run_stage()` here,
with the FnMODE-driven stage-order recipe table added alongside it in this
same plan. No orchestration (`NusRunner.reconstruct()`) or backend
invocation lives here yet; those are built in Plans 03/05 on top of these
primitives.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import nmrglue as ng


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
