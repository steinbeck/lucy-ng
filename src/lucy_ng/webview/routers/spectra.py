"""GET /api/spectra/1d/{carbon,proton} router (SP1-01/SP-02).

Two independent, read-only GET routes serving the 1D Spectra tab:
  - /api/spectra/1d/carbon -> real 13C 1D trace + peak overlay (always attempted)
  - /api/spectra/1d/proton -> real 1H 1D trace (rendered only when a 1H
    experiment is found in the dataset; D-02)

Both routes read `analysis/.run_manifest.json` (written by the trusted local
`case.md` process, D-07) to locate the raw Bruker dataset root, select the
correct experiment directory via `_select_experiment()` (excluding 2D and
DEPT-edited experiments), render it with `BrukerReader.read_1d()` +
matplotlib (Agg), and overlay the picked peaks from
`analysis/peaks/carbon_signals.json`.

Every route ALWAYS returns valid PNG bytes at HTTP 200 -- a real chart when
data is available, or a well-formed "unavailable" placeholder chart on any
failure (absent manifest, stale/unreadable raw path, no matching
experiment, malformed peak JSON). Never a 500, never a JSON body (SP-02,
mirrors structures.py's placeholder_svg() precedent).

WV-08 import-safety: this module imports fastapi at module level, which is
permitted because it is ONLY ever imported from inside create_app() and
from test bodies. matplotlib is imported ONLY inside make_router() -- never
at module level or in webview/__init__.py, webview/server.py, or
webview/state.py (D-04).
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter
from fastapi.responses import Response
from numpy.typing import NDArray

from lucy_ng.models import Spectrum1D
from lucy_ng.readers.bruker import BrukerReader

# Broad except tuple for JSON-parsing readers (mirrors tables.py's
# _JSON_READ_ERRORS -- the narrower (FileNotFoundError, OSError) idiom used
# by log.py is insufficient once json.loads()/.get()/indexing are involved).
_JSON_READ_ERRORS = (
    FileNotFoundError,
    json.JSONDecodeError,
    OSError,
    KeyError,
    TypeError,
    ValueError,
)

# Locked copy strings (95-UI-SPEC.md Copywriting Contract) -- do not reword.
_MSG_NO_MANIFEST = (
    "Waiting for a live CASE run — spectra will appear once analysis starts."
)
_MSG_STALE_PATH = "Raw Bruker data not found at the recorded path."
_MSG_NO_CARBON = "No ¹³C experiment found in this dataset."
_MSG_NO_PROTON = "No ¹H experiment in this dataset."
_MSG_PEAKS_UNAVAILABLE = "peak positions unavailable"

# Chart styling (95-UI-SPEC.md Layout & Interaction Contract) -- shared by
# both the real-trace and placeholder render paths so the layout never jumps
# between states.
_FIGSIZE = (9.0, 3.0)
_DPI = 100
_TRACE_COLOR = "#495057"
_ACCENT_COLOR = "#0c5460"
_PLACEHOLDER_COLOR = "#6c757d"


# ---------------------------------------------------------------------------
# Internal helpers -- manifest / experiment selection / peak reading
# (matplotlib-free; safe to import and unit-test without the [webview] extra
# providing matplotlib, though fastapi itself is still required, WV-08).
# ---------------------------------------------------------------------------


def _read_manifest(analysis_dir: Path) -> dict[str, Any] | None:
    """Read analysis/.run_manifest.json.

    Returns:
        The parsed dict when `.run_manifest.json` is valid JSON with a
        string `bruker_data_dir` field. Returns None on ANY failure
        (missing file, bad JSON, wrong type) -- never raises (D-01/D-05).
    """
    p = analysis_dir / ".run_manifest.json"
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data.get("bruker_data_dir"), str):
            return None
        return data
    except _JSON_READ_ERRORS:
        return None


def _select_experiment(bruker_data_dir: Path, nucleus: str) -> Spectrum1D | None:
    """Scan numbered Bruker experiment dirs, return the best Spectrum1D for `nucleus`.

    Excludes 2D experiments (`acqu2s` present, checked BEFORE any read_1d()
    call -- Pitfall 1) and DEPT-edited 13C experiments (`pulse_program`
    contains "dept", checked after reading -- Pitfall 2). Among the
    remaining candidates for `nucleus`, the lowest experiment number wins
    (secondary tiebreak; the DEPT filter is the numbering-independent
    primary discriminator).

    Returns:
        The selected Spectrum1D, or None when no candidate matches or
        `bruker_data_dir` is not a readable directory -- never raises.
    """
    if not bruker_data_dir.is_dir():
        return None

    candidates: list[tuple[int, Spectrum1D]] = []
    try:
        entries = sorted(bruker_data_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return None

    for exp_dir in entries:
        if not exp_dir.is_dir() or not re.match(r"^\d+$", exp_dir.name):
            continue
        if (exp_dir / "acqu2s").exists():
            continue  # 2D experiment -- Pitfall 1
        try:
            spectrum = BrukerReader.read_1d(exp_dir)
        except (FileNotFoundError, ValueError, OSError):
            continue  # unreadable / not a 1D experiment
        if spectrum.nucleus != nucleus:
            continue
        pulse_program = str(spectrum.metadata.get("pulse_program", "")).lower()
        if "dept" in pulse_program:
            continue  # DEPT-edited -- Pitfall 2
        candidates.append((int(exp_dir.name), spectrum))

    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]  # lowest experiment number wins


def _read_peaks(analysis_dir: Path) -> list[dict[str, Any]]:
    """Read analysis/peaks/carbon_signals.json's `signals` list.

    Returns:
        The `signals` list, or an empty list on any failure (absent file,
        malformed JSON, wrong shape) -- NEVER raises, so a missing/malformed
        peaks file degrades to a bare trace per SP-02.
    """
    p = analysis_dir / "peaks" / "carbon_signals.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        signals = data.get("signals", [])
        if not isinstance(signals, list):
            return []
        return signals
    except _JSON_READ_ERRORS:
        return []


# ---------------------------------------------------------------------------
# Internal helpers -- matplotlib rendering.
#
# Figure/FigureCanvasAgg are taken as INJECTED parameters (typed Any) rather
# than imported here, so this module never imports matplotlib outside
# make_router() (WV-08/D-04). Both helpers release the Figure via `del` in a
# `finally` block (T-95-02-03) -- no matplotlib.pyplot import anywhere,
# since Figure() objects built via direct construction are never registered
# in pyplot's global figure manager (nothing to "close").
# ---------------------------------------------------------------------------


def _apply_nmr_axes(ax: Any, ppm_scale: NDArray[np.float64]) -> None:
    """Set xlim from an already-descending Bruker ppm_scale.

    Do NOT call any axis-flip/inversion method and do NOT reverse the array
    -- `ppm_scale` from BrukerReader.read_1d is ALREADY descending
    (Pitfall 3). set_xlim alone with the descending endpoints already
    produces the reversed (high-ppm-left) axis.
    """
    ax.set_xlim(float(ppm_scale[0]), float(ppm_scale[-1]))
    ax.set_xlabel("δ (ppm)")


def _render_1d_png(
    figure_cls: Any,
    canvas_cls: Any,
    spectrum: Spectrum1D,
    peaks: list[dict[str, Any]],
) -> bytes:
    """Render a real 1D trace + peak overlay to PNG bytes (D-03).

    Draws a continuous line trace on a reversed ppm axis, with each peak in
    `peaks` overlaid as a thin vertical marker at its ppm (~70% axis
    height), labelled with its ppm value and, when present, its
    `assignment`. When `peaks` is empty, a small "peak positions
    unavailable" note is drawn top-right (SP-02 partial degradation --
    95-UI-SPEC.md).
    """
    fig = figure_cls(figsize=_FIGSIZE, dpi=_DPI)
    canvas = canvas_cls(fig)
    try:
        ax = fig.add_subplot(111)
        ax.plot(spectrum.ppm_scale, spectrum.data, color=_TRACE_COLOR, linewidth=1.0)
        _apply_nmr_axes(ax, spectrum.ppm_scale)

        y_min, y_max = ax.get_ylim()
        marker_top = y_min + 0.7 * (y_max - y_min)

        if not peaks:
            ax.text(
                0.98,
                0.95,
                _MSG_PEAKS_UNAVAILABLE,
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=7,
                style="italic",
                color=_PLACEHOLDER_COLOR,
            )

        for peak in peaks:
            if not isinstance(peak, dict):
                continue
            try:
                ppm = float(peak["ppm"])
            except (KeyError, TypeError, ValueError):
                continue
            ax.plot(
                [ppm, ppm],
                [y_min, marker_top],
                color=_ACCENT_COLOR,
                linewidth=0.75,
            )
            ax.text(
                ppm,
                marker_top,
                f"{ppm:.1f}",
                color=_ACCENT_COLOR,
                fontsize=7,
                rotation=90,
                ha="center",
                va="bottom",
            )
            assignment = peak.get("assignment")
            if assignment:
                ax.text(
                    ppm,
                    y_max,
                    str(assignment),
                    color=_ACCENT_COLOR,
                    fontsize=7,
                    ha="center",
                    va="bottom",
                )

        buf = io.BytesIO()
        canvas.print_png(buf)
        return buf.getvalue()
    finally:
        del canvas
        del fig


def _render_placeholder_png(figure_cls: Any, canvas_cls: Any, message: str) -> bytes:
    """Render a well-formed "unavailable" placeholder chart to PNG bytes.

    Axis-off, centered message text -- the PNG analog of
    structures.py/depiction.py's `placeholder_svg()` precedent (never a
    JSON body on this route, Pitfall 5).
    """
    fig = figure_cls(figsize=_FIGSIZE, dpi=_DPI)
    canvas = canvas_cls(fig)
    try:
        ax = fig.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            fontsize=11,
            color=_PLACEHOLDER_COLOR,
            wrap=True,
            transform=ax.transAxes,
        )
        ax.axis("off")
        buf = io.BytesIO()
        canvas.print_png(buf)
        return buf.getvalue()
    finally:
        del canvas
        del fig
