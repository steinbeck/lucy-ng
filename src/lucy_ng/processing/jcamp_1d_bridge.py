"""Thin 1D peak-pick bridge for JCAMP-DX ingestion (Phase 102, D-03).

This module is the 1D counterpart of `nus/bridge.py`'s 2D
`bridge_peak_pick()`: a direct, in-memory call to the existing 1D picker
(`AdaptivePeakPicker.pick_peaks()`, `processing/peak_picker.py`) -- no new
picker, no child-process shell-out to `cli/pick.py`.

It lives under `processing/` rather than beside `nus/bridge.py` because it
has ZERO `nus.*` coupling (unlike the 2D path, which reuses the Phase-99
QC-metadata/verdict machinery) -- resolving 102-RESEARCH.md Open Question 3.

Schema contract (load-bearing, 102-RESEARCH.md Pitfall 2): the returned
payload MUST stay schema-identical to `cli/pick.py::pick_1d`'s JSON output
(`count`/`noise_sigma`/`negative_detected`/`snr_floor_used`/`peaks[].{ppm,
intensity,snr}`) because `nus/qc.py::_load_1d_shifts()` parses that exact
shape and fails SILENTLY -- `data.get("peaks", [])` defaults to an empty
list rather than raising -- on any mismatch (e.g. the 2D per-experiment
correlation shape, keyed by carbon/proton ppm pairs rather than a flat
`peaks` list). `cli/pick.py` is byte-protected this phase and is
duplicated-by-contract here, exactly as `processing/edited_sign.py`
duplicates `cli/pick.py`'s private `_detect_multiplicity_edited()` detector
for the same "reuse without editing the frozen file" reason.

The only additive (non-`pick_1d`) top-level key this module emits is
`"nucleus"` -- harmless to `_load_1d_shifts()` (which only reads
`peaks[].ppm`), carried so a caller can derive the correct output filename
(`peak_json_filename()`) without re-inspecting the source `Spectrum1D`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from lucy_ng.models import Spectrum1D
from lucy_ng.processing.peak_picker import AdaptivePeakPicker

#: Nuclei this bridge is allowed to serialize a QC-discoverable filename for
#: (D-06: an unexpected 1D nucleus must never quietly land a file in the
#: QC-graded directory).
_VALID_1D_NUCLEI = {"1H", "13C"}


def bridge_peak_pick_1d(
    spectrum: Spectrum1D,
    *,
    threshold: float | None = None,
    snr_floor: float | None = None,
) -> dict[str, Any]:
    """Peak-pick `spectrum` and serialize into `cli/pick.py::pick_1d`'s exact JSON shape.

    Mirrors `cli/pick.py::pick_1d` lines 93-148 verbatim (auto-detected
    negative-peak heuristic, threshold/snr_floor three-way branching,
    `snr_floor_used` reporting), with one deliberate divergence: when
    `spectrum.data` is all-zero (`max_abs == 0.0`), `has_significant_negative`
    is forced to `False` instead of evaluating `-effective_threshold *
    max_abs` (which `pick_1d` does not guard) -- so a degenerate all-zero 1D
    file returns a valid, empty-peak payload instead of a divide-adjacent
    edge case propagating into a directory run (T-102-04).

    Args:
        spectrum: The in-memory `Spectrum1D` (e.g. from
            `JcampReader.read_1d()`).
        threshold: Passed through to `AdaptivePeakPicker.pick_peaks()`. If
            not `None`, disables SNR mode (legacy threshold*max behaviour),
            matching `pick_1d`'s own semantics.
        snr_floor: Passed through to `AdaptivePeakPicker.pick_peaks()` when
            `threshold` is `None` (SNR mode).

    Returns:
        A dict with top-level keys, in this order: `count`, `noise_sigma`,
        `negative_detected`, `snr_floor_used`, `peaks`, `nucleus`. `peaks`
        elements are `{"ppm": ..., "intensity": ..., "snr": ...}`. `nucleus`
        is `spectrum.nucleus` -- an ADDITIVE top-level key beyond
        `pick_1d`'s shape, harmless to `_load_1d_shifts()`.
    """
    effective_threshold = threshold if threshold is not None else 0.05
    max_abs = float(np.max(np.abs(spectrum.data)))
    if max_abs == 0.0:
        # Deliberate divergence from pick_1d (which has no such guard): an
        # all-zero spectrum must not crash a directory run (T-102-04).
        has_significant_negative = False
    else:
        has_significant_negative = bool(
            np.min(spectrum.data) < -effective_threshold * max_abs
        )

    use_snr = threshold is None
    if threshold is not None:
        peaks = AdaptivePeakPicker.pick_peaks(
            spectrum,
            threshold=threshold,
            detect_negative=has_significant_negative,
            use_snr=use_snr,
        )
    elif snr_floor is not None:
        peaks = AdaptivePeakPicker.pick_peaks(
            spectrum,
            detect_negative=has_significant_negative,
            snr_floor=snr_floor,
            use_snr=True,
        )
    else:
        peaks = AdaptivePeakPicker.pick_peaks(
            spectrum,
            detect_negative=has_significant_negative,
            use_snr=use_snr,
        )

    if not use_snr:
        snr_floor_used: float | None = None
    elif snr_floor is not None:
        snr_floor_used = snr_floor
    else:
        snr_floor_used = 5.0

    return {
        "count": len(peaks.peaks),
        "noise_sigma": peaks.noise_sigma,
        "negative_detected": has_significant_negative,
        "snr_floor_used": snr_floor_used,
        "peaks": [
            {"ppm": p.position, "intensity": p.intensity, "snr": p.snr}
            for p in peaks.peaks
        ],
        "nucleus": spectrum.nucleus,
    }


def peak_json_filename(nucleus: str) -> str:
    """Return the QC-discoverable output filename for a 1D `nucleus`.

    `f"{nucleus}.json"` -- so `"13C"` -> `"13C.json"`, `"1H"` -> `"1H.json"`.

    Pitfall-3 constraint (102-RESEARCH.md): `nus/qc.py::_glob_by_keyword()`
    is a case-insensitive SUBSTRING match over `peaks_dir.glob("*.json")`.
    Verified: `"13C.json"` is discovered by keyword `"13c"` only, and
    `"1H.json"` is discovered by keyword `"1h"` only -- neither name matches
    the other's keyword, nor `"hsqc"`/`"hmbc"`/`"cosy"`/`"dept"`.

    Args:
        nucleus: The 1D nucleus, must be one of `{"1H", "13C"}`.

    Returns:
        The filename to write this payload to.

    Raises:
        ValueError: If `nucleus` is outside `{"1H", "13C"}` -- an unexpected
            1D nucleus must never quietly land a file in the QC-graded
            directory (D-06 routes such files to the skip path instead).
    """
    if nucleus not in _VALID_1D_NUCLEI:
        raise ValueError(
            f"peak_json_filename: unsupported 1D nucleus {nucleus!r}, "
            f"expected one of {sorted(_VALID_1D_NUCLEI)}"
        )
    return f"{nucleus}.json"
