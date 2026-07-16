"""Shared multiplicity-edited-sign detector (Phase 99, PICK-01).

This module exists solely so `nus/bridge.py` can import a
`detect_multiplicity_edited()` function without importing (or modifying)
`cli/pick.py`, which is a HARD invariant for this phase (verified by a
`git diff --exit-code src/lucy_ng/cli/pick.py` acceptance gate in the phase
plan). `cli/pick.py::_detect_multiplicity_edited()` is module-private and
was never designed to be imported from outside that file; rather than
promote/export it there (which would touch the frozen file), this module is
an intentionally duplicated, byte-for-byte-equivalent importable twin.

A future refactor may fold `cli/pick.py`'s private copy into this module
once the byte-unchanged invariant is relaxed (see 99-RESEARCH.md
Assumptions Log A5) -- until then the two copies are kept in sync manually
and cross-checked by a parity test (`tests/nus/test_bridge.py`).
"""

from __future__ import annotations

from typing import Any

import numpy as np


def detect_multiplicity_edited(data: np.ndarray[Any, Any]) -> tuple[bool, int]:
    """Detect whether an HSQC is multiplicity-edited (deterministic, no LLM).

    Ported verbatim from the proven ``lucy pick 1d`` ``negative_detected``
    detector (np.min(data) < -0.05 * max_abs), itself ported verbatim into
    ``cli/pick.py::_detect_multiplicity_edited()``. A multiplicity-edited
    HSQC phases CH2 cross-peaks with opposite sign, producing genuine
    negative intensity well below the noise floor; no negatives => NOT
    edited => sign-ambiguous.

    Args:
        data: The 2D HSQC intensity matrix (``Spectrum2D.data``).

    Returns:
        Tuple of (multiplicity_edited, negative_crosspeak_count). Degrades to
        the safe default ``(False, 0)`` on empty / all-zero / all-non-finite
        data without raising. NaN/inf pixels are excluded so a single non-finite
        value can neither mask real negative cross-peaks nor poison the
        magnitude scale; the boolean is derived from the count so the two can
        never disagree (T-88-01; code-review WR-01).
    """
    if data.size == 0:
        return False, 0
    # Only finite pixels contribute to the scale and the negative test — a NaN
    # or inf must not change the verdict.
    finite = np.isfinite(data)
    if not bool(finite.any()):
        return False, 0
    max_abs = float(np.max(np.abs(data[finite])))
    if max_abs == 0.0:
        return False, 0
    cutoff = -0.05 * max_abs
    negative_crosspeak_count = int(np.count_nonzero(finite & (data < cutoff)))
    multiplicity_edited = negative_crosspeak_count > 0
    return multiplicity_edited, negative_crosspeak_count
