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

from lucy_ng.models import Spectrum1D, Spectrum2D
from lucy_ng.readers._jcampdx_decode import parse_data
from lucy_ng.readers.bruker import _detect_experiment_type

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


def _resolve_dim(
    inner: dict[str, Any], target_nucleus: str, *, procs_index: int | None = None
) -> tuple[float, float]:
    """Resolve the (``$OFFSET``, ``$SF``) pair for a target nucleus in a 2D file.

    ``$SF``/``$OFFSET``/``$NUC1`` are parallel lists (one entry per
    dimension), but their list-position order is a parse-order artifact, NOT
    a JCAMP-DX spec guarantee (101-RESEARCH.md Pitfall 4) -- never hardcode
    "index 0 = F1". Instead, find the (unique) index in ``$NUC1`` whose
    caret/bracket-stripped value equals ``target_nucleus``, and use that same
    index into ``$SF``/``$OFFSET`` (all three are co-indexed by construction,
    since nmrglue accumulates them together from the same procs/proc2s
    parse pass).

    Positional fallback (homonuclear experiments, e.g. COSY/NOESY): when
    ``target_nucleus`` appears more than once in ``$NUC1`` (both dims share
    the same nucleus), nucleus matching alone cannot disambiguate. This is
    resolved by ``procs_index`` -- an explicit caller-supplied hint using the
    verified "procs-then-proc2s" parse-order convention where index 0 is
    ALWAYS the DIRECT dimension (F2) and index 1 is ALWAYS the INDIRECT
    dimension (F1), regardless of SYMBOL's declared F1,F2 order. This
    convention is proven -- not assumed -- on the committed heteronuclear
    HSQC fixture, where nucleus matching independently disambiguates: its
    ``$NUC1 = ['<1H>', '<13C>']`` against ``.NUCLEUS = "13C, 1H"`` shows 1H
    (index 0) IS the F2/direct dimension even though SYMBOL declares F1
    first (see ``tests/readers/test_jcamp.py::TestJcampReaderHomonuclear::
    test_heteronuclear_positional_convention_holds``).

    Honest limitation: for a genuinely homonuclear file, both dimensions
    necessarily share the same ``$SF``, and on this project's real COSY data
    the two ``$OFFSET`` values differ by only 0.000938 ppm (7.050608 vs
    7.051546, ~0.47 Hz) -- so a positional swap would be numerically
    negligible and is NOT discriminable by any downstream ppm-based
    cross-check. The discriminating evidence for this convention is the
    heteronuclear proof above, not the homonuclear data itself.

    The unique-match path (``len(matches) == 1``) is never overridden by
    ``procs_index`` -- it stays authoritative whenever nucleus matching alone
    can disambiguate. If ``procs_index`` is not supplied and the match is
    ambiguous, the original fail-loud ``ValueError`` is raised unchanged, so
    a caller that forgets the hint still fails loud rather than silently
    first-matching (T-102-02).

    Args:
        inner: The metadata dict (as returned by ``_read_metadata``, or an
            equivalent mapping with ``$NUC1``/``$SF``/``$OFFSET`` keys).
        target_nucleus: The nucleus to resolve (e.g. '1H', '13C').
        procs_index: Optional positional hint (0 = F2/direct, 1 = F1/indirect)
            used ONLY when nucleus matching is ambiguous (homonuclear).

    Returns:
        A tuple of ``(offset_ppm, sf)`` for the resolved dimension.

    Raises:
        ValueError: If ``$NUC1``/``$SF``/``$OFFSET`` lengths mismatch, if
            ``target_nucleus`` is not present, if it is ambiguous and no
            ``procs_index`` hint is supplied, or if ``procs_index`` is out
            of range for the matched indices.
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
        if procs_index is None:
            raise ValueError(
                f"Ambiguous nucleus '{target_nucleus}' appears {len(matches)} times in "
                f"$NUC1={nuclei} -- homonuclear axis resolution requires an explicit "
                "procs_index hint (0=F2/direct, 1=F1/indirect); refusing to silently "
                "first-match"
            )
        if not (0 <= procs_index < len(matches)):
            raise ValueError(
                f"procs_index={procs_index} out of range for {len(matches)} matches "
                f"of nucleus '{target_nucleus}' in $NUC1={nuclei}"
            )
        index = matches[procs_index]
        return float(offset_raw[index]), float(sf_raw[index])

    index = matches[0]
    return float(offset_raw[index]), float(sf_raw[index])


def _apply_yfactor(
    raw: "list[float] | NDArray[np.float64]", y_factor: float
) -> NDArray[np.float64]:
    """Scale raw decoded NTUPLES row intensities by the SYMBOL-indexed Y-FACTOR.

    ``parse_data`` (the vendored decoder) returns raw, un-scaled integers --
    nmrglue's own ``getdataarray()`` applies this multiplication as a
    separate step, and it is easy to forget when hand-rolling 2D assembly
    (101-RESEARCH.md Pitfall 2). The real committed HSQC fixture's own
    ``Y_FACTOR`` happens to be exactly ``1``, so this must be unit-tested
    directly with a non-trivial factor rather than relying on the fixture
    alone to catch a missing multiplication.

    Args:
        raw: Raw decoded row intensities (un-scaled).
        y_factor: The ``FACTOR`` entry at SYMBOL's ``Y`` index.

    Returns:
        The scaled intensities as a float64 numpy array.
    """
    return (np.asarray(raw, dtype=np.float64) * y_factor).astype(np.float64)


def _page_hz(page: str) -> float:
    """Extract the Hz value from a NTUPLES ``##PAGE= F1=<hz>`` entry.

    Args:
        page: A single ``inner["PAGE"]`` entry (e.g. ``"F1=2830.444647689"``).

    Returns:
        The parsed Hz value.

    Raises:
        ValueError: If the entry is not in the expected ``F1=<hz>`` shape.
    """
    parts = page.split("=", 1)
    if len(parts) != 2:
        raise ValueError(f"Malformed NTUPLES PAGE entry: {page!r} -- expected 'F1=<hz>'")
    try:
        return float(parts[1])
    except ValueError as exc:
        raise ValueError(f"Malformed NTUPLES PAGE entry: {page!r} -- expected 'F1=<hz>'") from exc


class JcampReader:
    """Reader for JCAMP-DX NMR data files (binary-free, already-reconstructed)."""

    @staticmethod
    def read_1d(path: str | Path) -> Spectrum1D:
        """Read a 1D JCAMP-DX file and return a Spectrum1D.

        Per D-11, the intensity array comes from nmrglue's public decoded
        output (``ng.jcampdx.read()`` already returns real data for 1D
        files) -- the vendored decoder covers only the 2D NTUPLES-assembly
        gap. Metadata comes from this module's own ``_read_metadata``.

        Args:
            path: Path to the 1D ``.dx`` file.

        Returns:
            Spectrum1D with the processed real-channel data and ppm axis.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            ValueError: If required metadata is missing, no data payload is
                present, or the derived ppm axis is implausible/non-reversed.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"JCAMP-DX file not found: {path}")

        inner = _read_metadata(path)
        _dic, data = jc.read(str(path))
        if data is None:
            raise ValueError(f"JCAMP-DX file has no data payload: {path}")

        # SYMBOL for a 1D file is "X, R, I" (Hz axis, real channel, imaginary
        # channel); data[0] is the real channel -- the processed spectrum.
        real = np.asarray(data[0], dtype=np.float64)
        n = len(real)

        nucleus_raw = inner.get(".OBSERVENUCLEUS")
        if not nucleus_raw:
            raise ValueError(f"'.OBSERVE NUCLEUS' not found in JCAMP-DX metadata: {path}")
        nucleus = _clean_nucleus_label(str(nucleus_raw[0]))

        offset_raw = inner.get("$OFFSET")
        sf_raw = inner.get("$SF")
        first_raw = inner.get("FIRST")
        last_raw = inner.get("LAST")
        if not offset_raw or not sf_raw or not first_raw or not last_raw:
            raise ValueError(
                f"Required ppm-axis fields ($OFFSET/$SF/FIRST/LAST) missing "
                f"from JCAMP-DX metadata: {path}"
            )

        offset_ppm = float(offset_raw[0])
        sf = float(sf_raw[0])
        # FIRST/LAST for a 1D file are single comma-joined "X, R, I" triples;
        # the axis (X) value is the first component (101-RESEARCH.md Pitfall 3).
        first_hz = float(str(first_raw[0]).split(",")[0])
        last_hz = float(str(last_raw[0]).split(",")[0])

        ppm_scale = _ppm_scale(first_hz, last_hz, offset_ppm, sf, n)
        _assert_plausible_ppm_axis(ppm_scale, nucleus)

        solvent_raw = inner.get(".SOLVENTNAME")
        solvent = str(solvent_raw[0]) if solvent_raw else None
        pulse_program_raw = inner.get(".PULSESEQUENCE")
        pulse_program = str(pulse_program_raw[0]) if pulse_program_raw else None

        metadata: dict[str, Any] = {"frequency_source": "SF"}
        if pulse_program:
            metadata["pulse_program"] = pulse_program

        return Spectrum1D(
            data=real,
            ppm_scale=ppm_scale,
            nucleus=nucleus,
            frequency=sf,
            solvent=solvent,
            metadata=metadata,
        )

    @staticmethod
    def read_2d(path: str | Path) -> Spectrum2D:
        """Read a 2D JCAMP-DX NTUPLES file and return a Spectrum2D.

        Assembles the DIFDUP-compressed per-F1-row NTUPLES pages into a full
        ``(n_f1, n_f2)`` intensity matrix -- the exact gap where nmrglue's
        public API returns ``data=None`` for 2D files (101-RESEARCH.md
        Pattern 1). Both ppm axes are derived via the verified ``OFFSET+SF``
        formula (JC-02) and fail-loud plausibility-checked (D-04).

        Args:
            path: Path to the 2D ``.dx`` file.

        Returns:
            Spectrum2D with the assembled, Y-FACTOR-scaled data matrix and
            reversed ppm axes.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            ValueError: If required NTUPLES metadata is missing/inconsistent
                (page/datatable count mismatch, missing Y-FACTOR, malformed
                PAGE entries), a row fails to decode, or a derived ppm axis
                is implausible/non-reversed.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"JCAMP-DX file not found: {path}")

        inner = _read_metadata(path)

        symbol_raw = inner.get("SYMBOL")
        if not symbol_raw:
            raise ValueError(f"'SYMBOL' not found in JCAMP-DX metadata: {path}")
        dims = [s.strip() for s in str(symbol_raw[0]).split(",")]
        if "F1" not in dims or "F2" not in dims or "Y" not in dims:
            raise ValueError(
                f"SYMBOL does not declare the expected F1/F2/Y dimensions: {dims} ({path})"
            )
        y_index = dims.index("Y")
        f2_index = dims.index("F2")

        pages = inner.get("PAGE")
        tables = inner.get("DATATABLE")
        if not pages or not tables:
            raise ValueError(
                f"'PAGE'/'DATA TABLE' NTUPLES blocks not found in JCAMP-DX metadata: {path}"
            )
        if len(pages) != len(tables):
            raise ValueError(
                f"NTUPLES page/datatable count mismatch: len(PAGE)={len(pages)}, "
                f"len(DATATABLE)={len(tables)} -- malformed or truncated 2D file: {path}"
            )
        n_f1 = len(pages)

        vardim_raw = inner.get("VARDIM")
        if not vardim_raw:
            raise ValueError(f"'VAR_DIM' not found in JCAMP-DX metadata: {path}")
        var_dims = [int(float(v)) for v in str(vardim_raw[0]).split(",")]
        if var_dims[dims.index("F1")] != n_f1:
            raise ValueError(
                f"VAR_DIM F1 count ({var_dims[dims.index('F1')]}) does not match "
                f"len(PAGE) ({n_f1}) -- malformed or truncated 2D file: {path}"
            )

        factor_raw = inner.get("FACTOR")
        if not factor_raw:
            raise ValueError(f"'FACTOR' not found in JCAMP-DX metadata: {path}")
        factor_parts = str(factor_raw[0]).split(",")
        y_factor = float(factor_parts[y_index])

        rows: list[NDArray[np.float64]] = []
        for table in tables:
            decoded = parse_data(str(table))
            if decoded is None:
                raise ValueError(f"Failed to decode DIFDUP DATA TABLE row in {path}")
            raw_row, _channel = decoded
            rows.append(_apply_yfactor(raw_row, y_factor))

        row_lengths = {len(row) for row in rows}
        if len(row_lengths) != 1:
            raise ValueError(
                f"Decoded NTUPLES rows have inconsistent lengths {sorted(row_lengths)} "
                f"-- malformed 2D file: {path}"
            )
        n_f2 = row_lengths.pop()
        if var_dims[f2_index] != n_f2:
            raise ValueError(
                f"VAR_DIM F2 count ({var_dims[f2_index]}) does not match the decoded "
                f"row length ({n_f2}) -- malformed 2D file: {path}"
            )

        data = np.vstack(rows).astype(np.float64)

        nucleus_raw = inner.get(".NUCLEUS")
        if not nucleus_raw:
            raise ValueError(f"'.NUCLEUS' not found in JCAMP-DX metadata: {path}")
        nuclei = [_clean_nucleus_label(n) for n in str(nucleus_raw[0]).split(",")]
        if len(nuclei) != 2:
            raise ValueError(
                f"'.NUCLEUS' does not declare exactly two dimensions: {nuclei} ({path})"
            )
        # .NUCLEUS's comma-split order is guaranteed to match SYMBOL's declared
        # F1,F2 dimension order (101-RESEARCH.md Pitfall 4).
        f1_nucleus, f2_nucleus = nuclei[0], nuclei[1]

        first_raw = inner.get("FIRST")
        last_raw = inner.get("LAST")
        if not first_raw or not last_raw:
            raise ValueError(f"'FIRST'/'LAST' not found in JCAMP-DX metadata: {path}")
        # FIRST[0]/LAST[0] are the NTUPLES-global F1,F2,Y triples (not a
        # per-page value -- 101-RESEARCH.md Pitfall 3); only F2 (the direct
        # dimension, constant across pages) is read from them.
        first_global = [float(v) for v in str(first_raw[0]).split(",")]
        last_global = [float(v) for v in str(last_raw[0]).split(",")]
        f2_first_hz = first_global[f2_index]
        f2_last_hz = last_global[f2_index]

        # procs_index=0: $NUC1/$SF/$OFFSET are co-indexed in nmrglue's
        # procs-then-proc2s parse order, where index 0 is ALWAYS the DIRECT
        # dimension (F2) -- proven on the heteronuclear HSQC fixture, see
        # _resolve_dim's docstring. Only used when nucleus matching is
        # ambiguous (homonuclear); the unique-match path is unaffected.
        f2_offset, f2_sf = _resolve_dim(inner, f2_nucleus, procs_index=0)
        f2_ppm_scale = _ppm_scale(f2_first_hz, f2_last_hz, f2_offset, f2_sf, n_f2)
        _assert_plausible_ppm_axis(f2_ppm_scale, f2_nucleus)

        # F1 (indirect) axis: point COUNT and endpoints come from the
        # per-page ##PAGE= Hz values, NOT the global FIRST/LAST triple, so a
        # trimmed fixture's axis has the correct length (Pitfall 3). But
        # $OFFSET still anchors the ORIGINAL, un-trimmed spectrum's global
        # FIRST hz (fixture generation preserves the NTUPLES header/OFFSET
        # verbatim, only slicing the PAGE/DATATABLE window -- see
        # tests/fixtures/jcamp/_generate_fixture.py) -- so passing
        # page_hz[0] straight into _ppm_scale's offset-anchored FIRST slot
        # silently anchors the axis at the wrong point for any trimmed
        # window that doesn't start at the file's original page 0 (verified
        # empirically: this produced ppm~174 instead of the true ~21-23ppm
        # cross-peak). Rebase the anchor to page_hz[0] first, then reuse the
        # shared helper for the local window.
        page_hz = [_page_hz(str(page)) for page in pages]
        # procs_index=1: index 1 is ALWAYS the INDIRECT dimension (F1) --
        # the other half of the proven procs-then-proc2s convention.
        f1_offset, f1_sf = _resolve_dim(inner, f1_nucleus, procs_index=1)
        f1_global_first_hz = first_global[dims.index("F1")]
        f1_local_offset = f1_offset - (f1_global_first_hz - page_hz[0]) / f1_sf
        f1_ppm_scale = _ppm_scale(page_hz[0], page_hz[-1], f1_local_offset, f1_sf, n_f1)
        _assert_plausible_ppm_axis(f1_ppm_scale, f1_nucleus)

        pulse_program_raw = inner.get(".PULSESEQUENCE")
        if not pulse_program_raw:
            raise ValueError(f"'.PULSE SEQUENCE' not found in JCAMP-DX metadata: {path}")
        pulse_program = str(pulse_program_raw[0])
        experiment_type = _detect_experiment_type(pulse_program, f1_nucleus, f2_nucleus)

        solvent_raw = inner.get(".SOLVENTNAME")
        solvent = str(solvent_raw[0]) if solvent_raw else None

        metadata: dict[str, Any] = {"frequency_source": "SF", "pulse_program": pulse_program}
        if solvent:
            metadata["solvent"] = solvent
        metadata["f1_frequency"] = f1_sf
        metadata["f2_frequency"] = f2_sf

        return Spectrum2D(
            data=data,
            f1_ppm_scale=f1_ppm_scale,
            f2_ppm_scale=f2_ppm_scale,
            f1_nucleus=f1_nucleus,
            f2_nucleus=f2_nucleus,
            experiment_type=experiment_type,
            frequency=float(f2_sf),
            metadata=metadata,
        )

    @staticmethod
    def read(path: str | Path) -> Spectrum1D | Spectrum2D:
        """Read a JCAMP-DX file, dispatching to ``read_1d``/``read_2d`` on ``##NUM DIM=`` (D-09).

        1D JCAMP-DX files carry no ``##NUM DIM=`` line at all (verified
        directly against this project's own committed 1D fixtures) -- its
        absence is treated as ``NUM DIM=1``, consistent with 2D files being
        the only ones that declare it explicitly (``##NUM DIM= 2``).

        Args:
            path: Path to the ``.dx`` file.

        Returns:
            Spectrum1D (NUM DIM==1, or the key is absent) or Spectrum2D
            (NUM DIM==2).

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            ValueError: If the file declares an unsupported dimensionality.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"JCAMP-DX file not found: {path}")

        inner = _read_metadata(path)
        num_dim_raw = inner.get("NUMDIM")
        num_dim = int(float(str(num_dim_raw[0]))) if num_dim_raw else 1

        if num_dim == 1:
            return JcampReader.read_1d(path)
        if num_dim == 2:
            return JcampReader.read_2d(path)
        raise ValueError(
            f"Unsupported JCAMP-DX dimensionality '##NUM DIM= {num_dim}': {path}"
        )
