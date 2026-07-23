"""JCAMP-DX NMR file reader.

Reads binary-free, already-reconstructed JCAMP-DX (``.dx``) spectra into
lucy-ng's existing ``Spectrum1D``/``Spectrum2D`` models. Mirrors the
``BrukerReader`` shape (readers/bruker.py) so downstream consumers (CLI,
``PeakPicker2D`` bridge) can target either reader interchangeably.

This module owns two kinds of logic:

1. Shared, contract-defining helpers (metadata access, ``.NUCLEUS``/``$NUC1``
   based dimension mapping, the verified ppm-axis formula, the fail-loud
   plausibility assertion). These are consumed by BOTH ``read_1d`` (this
   module) and ``read_2d`` (a later plan) -- defining them once, correctly,
   here is the interface-first ordering this phase follows.
2. The 1D read path (``JcampReader.read_1d``), which is this plan's own
   deliverable (JC-03).

ppm-axis formula (the JC-02 crux, 101-RESEARCH.md "Pattern 2", verified to
<0.0004 ppm against the project's own trusted ``BrukerReader`` ground truth):

    ppm[i] = OFFSET_ppm - (FIRST_hz - hz[i]) / SF

``OFFSET_ppm`` (``$OFFSET``, procs/proc2s) is already in ppm and anchors the
FIRST point of the axis; the Hz-to-ppm divisor is ``$SF`` (the spectrometer
*reference* frequency), NOT ``$SFO1``/``$SFO2`` (the transmitter frequency).
Dividing by SFO from a zero anchor is a real, measured ~0.447 ppm systematic
error on this project's own fixture data -- do not "simplify" this formula.
"""

from pathlib import Path
from typing import Any

import nmrglue.fileio.jcampdx as jc
import numpy as np
from numpy.typing import NDArray

from lucy_ng.readers.bruker import (
    _detect_experiment_type,  # noqa: F401  (D-10, re-exported for Plan 04)
)

# ppm-axis plausibility bounds per nucleus (101-RESEARCH.md "JC-02 concrete
# assertion bounds"). Deliberately generous -- this is the coarse, fail-loud
# safety net (D-04); the finer JC-02 cross-check against 1D reference peaks
# lives in the test layer (D-03).
_PPM_PLAUSIBILITY_BOUNDS: dict[str, tuple[float, float]] = {
    "1H": (-3.0, 15.0),
    "13C": (-15.0, 230.0),
    "15N": (-50.0, 900.0),
    "31P": (-200.0, 250.0),
}
_PPM_PLAUSIBILITY_FALLBACK: tuple[float, float] = (-1e6, 1e6)


def _read_metadata(path: str | Path) -> dict[str, Any]:
    """Read a JCAMP-DX file's metadata dict via nmrglue's raw-dict helper.

    ``ng.jcampdx.read()``'s top-level ``DATATYPE`` dispatch only recognizes
    three buckets (``_datatype_NMRSPECTRUM``, ``_datatype_NMRFID``,
    ``_datatype_NA``) and never promotes a 2D file's metadata to the top
    level (101-RESEARCH.md "Pattern 1"). Calling ``_readrawdic`` directly and
    searching for whichever ``_datatype_*`` bucket is present avoids coupling
    this reader to that incomplete dispatch table -- 1D files in this
    project's fixtures use ``_datatype_NMRSPECTRUM``; 2D files use
    ``_datatype_NDNMRSPECTRUM``.

    Args:
        path: Path to the ``.dx`` file.

    Returns:
        The inner metadata dict (the single element of the matched
        ``_datatype_*`` bucket's list).

    Raises:
        ValueError: If no ``_datatype_*`` bucket is present in the raw dict.
    """
    raw = jc._readrawdic(str(path))
    for key, value in raw.items():
        if key.startswith("_datatype_"):
            inner: dict[str, Any] = value[0]
            return inner
    raise ValueError(
        f"No '_datatype_*' bucket found in JCAMP-DX metadata for {path} "
        f"(found top-level keys: {sorted(raw.keys())}) -- malformed or "
        "unsupported JCAMP-DX file"
    )


def _strip_caret(value: str) -> str:
    """Strip a leading caret from JCAMP-DX nucleus values ('^1H' -> '1H')."""
    return value.lstrip("^")


def _clean_nucleus_label(value: str) -> str:
    """Normalize a JCAMP-DX nucleus label to lucy-ng's plain form.

    JCAMP-DX nucleus fields arrive in more than one wrapping convention
    depending on which key they come from: ``.OBSERVE NUCLEUS`` uses a
    leading caret (``^1H``), while ``$NUC1`` uses Bruker's angle-bracket
    convention (``<1H>``, matching ``readers/bruker.py::_strip_brackets``).
    Strip whichever wrapping is present so callers always get a plain
    nucleus string ('1H', '13C', ...).
    """
    value = value.strip()
    value = _strip_caret(value)
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    return value


def _ppm_scale(
    first_hz: float, last_hz: float, offset_ppm: float, sf: float, n: int
) -> NDArray[np.float64]:
    """Derive a ppm axis from Hz-domain JCAMP-DX fields (the JC-02 crux math).

    Verified formula (101-RESEARCH.md "Pattern 2", <0.0004 ppm residual
    against BrukerReader ground truth on the sibling raw Bruker dataset):

        ppm[i] = OFFSET_ppm - (FIRST_hz - hz[i]) / SF

    ``offset_ppm`` (``$OFFSET``) is already in ppm and anchors the axis'
    first point; the divisor is ``$SF`` (spectrometer reference frequency),
    NOT ``$SFO1``/``$SFO2`` (transmitter frequency) -- the naive
    Hz-divided-by-SFO-from-zero approach silently produces a plausible but
    wrong axis (measured ~0.447 ppm error on this project's own fixture).

    Args:
        first_hz: The axis's ``##FIRST=`` Hz value (global anchor point).
        last_hz: The axis's ``##LAST=`` Hz value.
        offset_ppm: ``$OFFSET`` -- already in ppm.
        sf: ``$SF`` -- spectrometer reference frequency (MHz).
        n: Number of points on the axis.

    Returns:
        A descending (reversed, Bruker-convention) ppm axis of length ``n``.
    """
    sw_hz = first_hz - last_hz
    return np.linspace(offset_ppm, offset_ppm - sw_hz / sf, n, dtype=np.float64)


def _assert_plausible_ppm_axis(scale: NDArray[np.float64], nucleus: str) -> None:
    """Fail-loud check that a computed ppm axis is plausible and reversed (D-04).

    This is deliberately a coarse safety net -- it would NOT by itself catch
    the naive SFO-divisor bug (that axis is still inside these bounds and
    still descending on this project's own fixture). The finer, load-bearing
    check is the JC-02 cross-check against 1D reference peaks, which lives
    in the test layer (D-03), not here.

    Args:
        scale: The computed ppm axis.
        nucleus: The nucleus the axis belongs to (e.g. '1H', '13C').

    Raises:
        ValueError: If the axis is out of the expected plausibility range,
            or is not reversed (descending), per Bruker convention.
    """
    lo, hi = _PPM_PLAUSIBILITY_BOUNDS.get(nucleus, _PPM_PLAUSIBILITY_FALLBACK)
    if not (lo <= scale.min() and scale.max() <= hi):
        raise ValueError(
            f"Implausible {nucleus} ppm axis: [{scale.min():.2f}, {scale.max():.2f}] "
            f"outside expected [{lo}, {hi}] -- likely wrong Hz/frequency divisor"
        )
    if not (scale[0] > scale[-1]):
        raise ValueError(
            f"{nucleus} ppm axis not reversed (descending) -- Bruker convention violated"
        )


def _resolve_dim(inner: dict[str, Any], target_nucleus: str) -> tuple[float, float]:
    """Resolve the (``$OFFSET``, ``$SF``) pair for a target nucleus in a 2D file.

    ``$SF``/``$OFFSET``/``$NUC1`` are parallel lists (one entry per
    dimension), but their list-position order is a parse-order artifact, NOT
    a JCAMP-DX spec guarantee (101-RESEARCH.md Pitfall 4) -- never hardcode
    "index 0 = F1". Instead, find the (unique) index in ``$NUC1`` whose
    caret/bracket-stripped value equals ``target_nucleus``, and use that same
    index into ``$SF``/``$OFFSET`` (all three are co-indexed by construction,
    since nmrglue accumulates them together from the same procs/proc2s
    parse pass).

    Degeneracy guard (WR-04 class, homonuclear experiments): if
    ``target_nucleus`` appears MORE THAN ONCE in ``$NUC1`` (e.g. COSY/NOESY,
    both dims '1H'), first-matching would silently resolve a
    plausible-but-wrong axis. Fail loud instead -- homonuclear axis
    resolution by position is deferred to Phase 103.

    Args:
        inner: The metadata dict (as returned by ``_read_metadata``, or an
            equivalent mapping with ``$NUC1``/``$SF``/``$OFFSET`` keys).
        target_nucleus: The nucleus to resolve (e.g. '1H', '13C').

    Returns:
        A tuple of ``(offset_ppm, sf)`` for the resolved dimension.

    Raises:
        ValueError: If ``$NUC1``/``$SF``/``$OFFSET`` lengths mismatch, if
            ``target_nucleus`` is not present, or if it is ambiguous
            (present more than once -- homonuclear).
    """
    nuc1_raw = inner["$NUC1"]
    sf_raw = inner["$SF"]
    offset_raw = inner["$OFFSET"]

    if not (len(nuc1_raw) == len(sf_raw) == len(offset_raw)):
        raise ValueError(
            f"Dimension-list length mismatch: len($NUC1)={len(nuc1_raw)}, "
            f"len($SF)={len(sf_raw)}, len($OFFSET)={len(offset_raw)} -- "
            "malformed JCAMP-DX 2D metadata"
        )

    nuclei = [_clean_nucleus_label(str(n)) for n in nuc1_raw]
    matches = [i for i, n in enumerate(nuclei) if n == target_nucleus]

    if len(matches) == 0:
        raise ValueError(
            f"Nucleus '{target_nucleus}' not found in $NUC1={nuclei} -- "
            "cannot resolve dimension"
        )
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous nucleus '{target_nucleus}' appears {len(matches)} times in "
            f"$NUC1={nuclei} -- homonuclear axis resolution (e.g. COSY/NOESY) is "
            "out of scope for this phase (deferred to Phase 103, which resolves by "
            "positional SYMBOL order); refusing to silently first-match"
        )

    index = matches[0]
    return float(offset_raw[index]), float(sf_raw[index])
