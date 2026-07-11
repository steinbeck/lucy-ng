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
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter
from fastapi.responses import Response
from numpy.typing import NDArray

from lucy_ng.models import Spectrum1D, Spectrum2D
from lucy_ng.processing.peak_picker_2d import _compute_2d_noise_sigma
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

# 2D chart styling (96-UI-SPEC.md) -- taller figure to give the F1/y-axis
# room; same width as the 1D charts for visual column alignment (D-09).
_FIGSIZE_2D = (9.0, 6.0)

# Locked copy strings (96-UI-SPEC.md Copywriting Contract) -- do not reword.
_MSG_NO_HSQC = "No HSQC experiment found in this dataset."
_MSG_NO_HMBC = "No HMBC experiment found in this dataset."
_MSG_NO_COSY = "No COSY experiment found in this dataset."

# LOCKED HMBC flag palette (96-CONTEXT.md D-06) -- reused verbatim from the
# Phase 94 Tables-tab HMBC flag-colour palette for visual consistency between
# the Tables tab and the 2D plot. Do NOT introduce new hues.
_HMBC_FLAG_COLORS = {
    "ok": "#28a745",
    "potential_4J": "#ffc107",
    "1J_artifact": "#adb5bd",
}
_DEFAULT_FLAG_COLOR = "#495057"  # unrecognised/missing flag -- same as trace/contour colour


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


def _select_experiment_2d(bruker_data_dir: Path, experiment_type: str) -> Spectrum2D | None:
    """Scan numbered Bruker experiment dirs, return the best Spectrum2D for `experiment_type`.

    Mirror of `_select_experiment` with an INVERTED filter: only dirs WITH
    `acqu2s` are candidates (the 1D selector explicitly excludes these --
    Pitfall 1 checked BEFORE any `read_2d()` call, so an unreadable 1D dir is
    never even opened as 2D). Among the remaining candidates matching
    `experiment_type`, the lowest experiment number wins (same tiebreak as
    the 1D selector, per 96-CONTEXT.md's discretion note).

    Returns:
        The selected Spectrum2D, or None when no candidate matches or
        `bruker_data_dir` is not a readable directory -- never raises.
    """
    if not bruker_data_dir.is_dir():
        return None

    candidates: list[tuple[int, Spectrum2D]] = []
    try:
        entries = sorted(bruker_data_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return None

    for exp_dir in entries:
        if not exp_dir.is_dir() or not re.match(r"^\d+$", exp_dir.name):
            continue
        if not (exp_dir / "acqu2s").exists():
            continue  # 1D experiment -- not a 2D candidate
        try:
            spectrum = BrukerReader.read_2d(exp_dir)
        except (FileNotFoundError, ValueError, OSError):
            continue  # unreadable / not a 2D experiment
        if spectrum.experiment_type != experiment_type:
            continue
        candidates.append((int(exp_dir.name), spectrum))

    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]  # lowest experiment number wins


def _selected_2d_pdata_path(bruker_data_dir: Path, experiment_type: str) -> Path | None:
    """Re-resolve the SAME experiment dir `_select_experiment_2d` would pick, as a path.

    `_select_experiment_2d(...) -> Spectrum2D | None` keeps its Wave-0-frozen
    public signature (no tuple/path return -- would break the frozen
    `test_spectra_2d_select_experiment_2d_keeps_only_acqu2s` test). This
    helper independently re-does the identical scan + tiebreak so the mtime
    cache can key on the real source file (`pdata/1/2rr`) without touching
    that contract.

    Returns:
        The selected experiment's `pdata/1/2rr` path (or the experiment dir
        itself if `2rr` is absent -- Pitfall 5), or None when no candidate
        matches / the root is unreadable -- never raises.
    """
    if not bruker_data_dir.is_dir():
        return None

    candidates: list[tuple[int, Path]] = []
    try:
        entries = sorted(bruker_data_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return None

    for exp_dir in entries:
        if not exp_dir.is_dir() or not re.match(r"^\d+$", exp_dir.name):
            continue
        if not (exp_dir / "acqu2s").exists():
            continue
        try:
            spectrum = BrukerReader.read_2d(exp_dir)
        except (FileNotFoundError, ValueError, OSError):
            continue
        if spectrum.experiment_type != experiment_type:
            continue
        candidates.append((int(exp_dir.name), exp_dir))

    if not candidates:
        return None
    exp_dir = min(candidates, key=lambda t: t[0])[1]
    data_file = exp_dir / "pdata" / "1" / "2rr"
    return data_file if data_file.exists() else exp_dir


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


def _read_peaks_2d(analysis_dir: Path, kind: str) -> list[dict[str, Any]]:
    """Read analysis/peaks/{hsqc,hmbc,cosy}.json's `peaks` list.

    Args:
        analysis_dir: The CASE analysis directory.
        kind: One of "hsqc", "hmbc", "cosy" -- selects the peaks JSON file.

    Returns:
        The `peaks` list, or an empty list on any failure (absent file,
        malformed JSON, wrong shape) -- NEVER raises, so a missing/malformed
        peaks file degrades to a bare contour per SP-02.
    """
    p = analysis_dir / "peaks" / f"{kind}.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        peaks = data.get("peaks", [])
        if not isinstance(peaks, list):
            return []
        return peaks
    except _JSON_READ_ERRORS:
        return []


def _source_mtime(exp_dir: Path, peaks_path: Path) -> float:
    """Combined source mtime for the 2D PNG cache key (96-RESEARCH.md Pattern 5).

    `exp_dir` is expected to be the value returned by
    `_selected_2d_pdata_path` (either a `pdata/1/2rr` file or, as a fallback,
    the experiment directory itself). Each stat is independently guarded
    (Pitfall 5) so an unusual processing configuration never escapes as a
    raised exception -- this function itself never raises.

    Returns:
        `max(data_mtime, peaks_mtime)` -- either file changing invalidates
        the cache; neither changing reproduces the identical float, hitting
        the cache. Falls back to 0.0 for either half on any OSError.
    """
    try:
        data_mtime = exp_dir.stat().st_mtime
    except OSError:
        data_mtime = 0.0
    try:
        peaks_mtime = peaks_path.stat().st_mtime if peaks_path.exists() else 0.0
    except OSError:
        peaks_mtime = 0.0
    return max(data_mtime, peaks_mtime)


def _block_max_decimate(
    data: NDArray[np.float64],
    scale_a: NDArray[np.float64],
    scale_b: NDArray[np.float64],
    max_dim: int = 512,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Block-maximum decimate a 2D array to <= max_dim in each axis (D-04).

    Partitions `data` into (step_a, step_b) blocks and takes each block's
    max -- so a narrow cross-peak apex falling between grid points survives
    downsampling (chosen over plain striding per D-04's discretion: the
    entire QC value of the overlay depends on real peaks not silently
    vanishing; verified at 7ms for a 1024x2048 array, 96-RESEARCH.md
    Pattern 3). The matching scales are decimated consistently by striding
    + truncation to the decimated shape in this SAME call, so data and
    scales can never drift apart (96-RESEARCH.md Pitfall 1).
    """
    ny, nx = data.shape
    step_y = max(1, -(-ny // max_dim))  # ceil division
    step_x = max(1, -(-nx // max_dim))
    if step_y == 1 and step_x == 1:
        return data, scale_a, scale_b  # already small enough -- no-op
    pad_y = (-ny) % step_y
    pad_x = (-nx) % step_x
    padded = np.pad(data, ((0, pad_y), (0, pad_x)), mode="edge")
    ny2, nx2 = padded.shape
    decimated = padded.reshape(ny2 // step_y, step_y, nx2 // step_x, step_x).max(axis=(1, 3))
    dec_a = scale_a[::step_y][: decimated.shape[0]]
    dec_b = scale_b[::step_x][: decimated.shape[1]]
    return decimated, dec_a, dec_b


def _geometric_levels(
    floor: float, factor: float = 1.4, count: int = 8
) -> NDArray[np.float64]:
    """Geometric contour levels starting at `floor`, growing by `factor` each step (D-01).

    `factor=1.4, count=8` are the chosen constants (96-RESEARCH.md Pattern 4 /
    96-UI-SPEC.md Contour level construction, verified to produce a
    visually-graduated ladder for HSQC/HMBC/COSY): weak long-range HMBC
    cross-peaks near the floor remain visible while strong HSQC one-bond
    peaks do not smear the plot shut. `floor` is always positive-only
    (D-03), computed by the caller as `5.0 * sigma`.
    """
    levels: NDArray[np.float64] = (floor * (factor ** np.arange(count))).astype(np.float64)
    return levels


# Module-level mtime-keyed PNG cache -- closed over by make_router(),
# persists for the life of the server process. One entry per route (3
# routes total under the "keep only the latest mtime per plot" eviction
# policy, 96-RESEARCH.md Pattern 5) -- a NEWER mtime simply overwrites the
# OLD entry, so no explicit eviction list is needed (SC3/SC4).
_png_cache: dict[str, tuple[float, bytes]] = {}


def _cached_or_render(
    cache_key: str, source_mtime: float, render_fn: Callable[[], bytes]
) -> bytes:
    """Return the cached PNG if source_mtime matches; otherwise render + store.

    `render_fn` is a zero-arg closure so it is only invoked on a cache miss
    (avoids paying the render cost merely to compute a key comparison).
    Cache key is strictly `(cache_key, source_mtime)` -- never the request
    object, query params, or the frontend's `?t=` cache-buster (Pitfall 4).
    """
    cached = _png_cache.get(cache_key)
    if cached is not None and cached[0] == source_mtime:
        return cached[1]
    png_bytes = render_fn()
    _png_cache[cache_key] = (source_mtime, png_bytes)
    return png_bytes


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


def _apply_nmr_axes_2d(
    ax: Any, f1_ppm_scale: NDArray[np.float64], f2_ppm_scale: NDArray[np.float64]
) -> None:
    """Set xlim/ylim from already-descending Bruker F1/F2 ppm scales (D-08).

    F2 (direct dimension, always 1H) is the x-axis; F1 (indirect dimension,
    13C for HSQC/HMBC or 1H for COSY) is the y-axis -- this positional
    mapping holds regardless of nucleus (96-RESEARCH.md Pitfall 3). Do NOT
    call any axis-flip/inversion method and do NOT reverse either array --
    both scales are ALREADY descending (mirrors the 1D helper's Pitfall 3);
    set_xlim/set_ylim alone with the descending endpoints already produce
    the reversed (high-ppm-left / high-ppm-top) axes. xlabel is always
    "δH (ppm)"; the caller sets the per-plot-type ylabel.
    """
    ax.set_xlim(float(f2_ppm_scale[0]), float(f2_ppm_scale[-1]))
    ax.set_ylim(float(f1_ppm_scale[0]), float(f1_ppm_scale[-1]))
    ax.set_xlabel("δH (ppm)")


def _plot_uniform_overlay(
    ax: Any, peaks: list[dict[str, Any]], xkey: str, ykey: str, color: str
) -> None:
    """Draw each peak as an open circle at (peak[xkey], peak[ykey]) in `color` (D-05/D-07).

    Used for HSQC (uniform accent-coloured markers, no flag distinction) and
    the COSY scatter overlay. Malformed peak rows (missing/non-numeric
    x/y) are skipped, never raise (96-RESEARCH.md Security Domain V5).
    """
    for peak in peaks:
        if not isinstance(peak, dict):
            continue
        try:
            x = float(peak[xkey])
            y = float(peak[ykey])
        except (KeyError, TypeError, ValueError):
            continue
        ax.scatter([x], [y], s=30, facecolors="none", edgecolors=color, linewidths=1.0)


def _plot_hmbc_overlay(ax: Any, peaks: list[dict[str, Any]]) -> None:
    """Draw each HMBC peak as an open circle colour-coded by its `flag` (D-06, LOCKED).

    `x=proton_ppm, y=carbon_ppm`; colour looked up from `_HMBC_FLAG_COLORS`
    (falling back to `_DEFAULT_FLAG_COLOR` for an unknown/missing flag).
    Malformed peak rows are skipped, never raise.
    """
    for peak in peaks:
        if not isinstance(peak, dict):
            continue
        try:
            x = float(peak["proton_ppm"])
            y = float(peak["carbon_ppm"])
        except (KeyError, TypeError, ValueError):
            continue
        flag = peak.get("flag")
        color = _HMBC_FLAG_COLORS.get(flag, _DEFAULT_FLAG_COLOR) if isinstance(flag, str) else (
            _DEFAULT_FLAG_COLOR
        )
        ax.scatter([x], [y], s=30, facecolors="none", edgecolors=color, linewidths=1.0)


def _plot_hmbc_legend(ax: Any) -> None:
    """Draw the compact 3-line HMBC flag legend, top-right corner (96-UI-SPEC.md).

    One line per flag, 7pt, coloured in that flag's hex, right-aligned,
    stacked -- drawn ONLY in the non-empty-peaks branch, never alongside the
    "peaks unavailable" annotation (96-UI-SPEC.md Layout & Interaction
    Contract's HMBC in-chart flag legend).
    """
    lines = ("ok", "potential_4J", "1J_artifact")
    for i, flag in enumerate(lines):
        ax.text(
            0.98,
            0.98 - i * 0.05,
            flag,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            color=_HMBC_FLAG_COLORS[flag],
        )


def _plot_cosy_diagonal(
    ax: Any, f1_scale: NDArray[np.float64], f2_scale: NDArray[np.float64]
) -> None:
    """Draw a thin grey F1=F2 diagonal line as a COSY orientation aid (D-07).

    Drawn using the overlapping ppm range of the two (nearly but not always
    bit-identical) axes -- 96-RESEARCH.md Pattern 6.
    """
    lo = max(float(f1_scale[-1]), float(f2_scale[-1]))
    hi = min(float(f1_scale[0]), float(f2_scale[0]))
    ax.plot([lo, hi], [lo, hi], color="#adb5bd", linewidth=0.5, linestyle="-")


def _render_1d_png(
    figure_cls: Any,
    canvas_cls: Any,
    spectrum: Spectrum1D,
    peaks: list[dict[str, Any]],
    *,
    annotate_missing_peaks: bool = True,
) -> bytes:
    """Render a real 1D trace + peak overlay to PNG bytes (D-03).

    Draws a continuous line trace on a reversed ppm axis, with each peak in
    `peaks` overlaid as a thin vertical marker at its ppm (~70% axis
    height), labelled with a SINGLE combined rotated label carrying its ppm
    value and, when present, its `assignment` (95-05 gap closure -- a
    separate horizontal assignment label collided in dense-peak regions;
    folding both into one rotated label eliminates that collision while
    keeping both values visible). When `peaks` is empty AND
    `annotate_missing_peaks` is True, a small "peak positions unavailable"
    note is drawn top-right (SP-02 partial degradation -- 95-UI-SPEC.md);
    the caller passes False for nuclei with no peak-JSON source (e.g. the
    1H route), where an empty overlay is expected rather than a degraded
    state.
    """
    fig = figure_cls(figsize=_FIGSIZE, dpi=_DPI)
    canvas = canvas_cls(fig)
    try:
        ax = fig.add_subplot(111)
        ax.plot(spectrum.ppm_scale, spectrum.data, color=_TRACE_COLOR, linewidth=1.0)
        _apply_nmr_axes(ax, spectrum.ppm_scale)

        y_min, y_max = ax.get_ylim()
        marker_top = y_min + 0.7 * (y_max - y_min)

        if not peaks and annotate_missing_peaks:
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
            assignment = peak.get("assignment")
            label = f"{ppm:.1f}  {assignment}" if assignment else f"{ppm:.1f}"
            ax.text(
                ppm,
                marker_top,
                label,
                color=_ACCENT_COLOR,
                fontsize=7,
                rotation=90,
                ha="center",
                va="bottom",
            )

        buf = io.BytesIO()
        canvas.print_png(buf)
        return buf.getvalue()
    finally:
        del canvas
        del fig


def _render_2d_png(
    figure_cls: Any,
    canvas_cls: Any,
    spectrum: Spectrum2D,
    peaks: list[dict[str, Any]],
    experiment_type: str,
) -> bytes:
    """Render a real 2D contour + cross-peak overlay to PNG bytes (SP2-01).

    Mirrors `_render_1d_png`'s try/finally figure-release shape. Contour
    levels are geometric (D-01), single muted colour (D-02), positive-only
    (D-03), computed from a noise floor derived on the FULL-RESOLUTION data
    BEFORE decimation (96-RESEARCH.md Pitfall 2 -- block-max decimation
    inflates retained values and would bias the MAD upward if computed
    after). Decimation is block-maximum to <=512x512 (D-04). The overlay is
    dispatched by `experiment_type` with explicit mutual exclusivity
    (mirrors the 1D peaks-vs-annotation branch): a non-empty `peaks` list
    draws the type-specific markers (+ the HMBC flag legend for HMBC) and
    never the "peaks unavailable" note; an empty `peaks` list draws ONLY
    that note.
    """
    sigma = _compute_2d_noise_sigma(spectrum.data)  # full-res, BEFORE decimation
    decimated, f1s, f2s = _block_max_decimate(
        spectrum.data, spectrum.f1_ppm_scale, spectrum.f2_ppm_scale
    )
    levels = _geometric_levels(5.0 * sigma)

    fig = figure_cls(figsize=_FIGSIZE_2D, dpi=_DPI)
    canvas = canvas_cls(fig)
    try:
        ax = fig.add_subplot(111)
        ax.contour(f2s, f1s, decimated, levels=levels, colors=_TRACE_COLOR, linewidths=0.5)
        _apply_nmr_axes_2d(ax, f1s, f2s)
        ax.set_ylabel("δC (ppm)" if experiment_type != "COSY" else "δH (ppm)")

        if peaks:
            if experiment_type == "HMBC":
                _plot_hmbc_overlay(ax, peaks)
                _plot_hmbc_legend(ax)
            elif experiment_type == "COSY":
                _plot_cosy_diagonal(ax, f1s, f2s)
                _plot_uniform_overlay(
                    ax, peaks, "proton_a_ppm", "proton_b_ppm", _ACCENT_COLOR
                )
            else:  # HSQC
                _plot_uniform_overlay(ax, peaks, "proton_ppm", "carbon_ppm", _ACCENT_COLOR)
        else:
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


# ---------------------------------------------------------------------------
# Router factory -- matplotlib is imported ONLY here (WV-08/D-04).
# ---------------------------------------------------------------------------


def make_router(analysis_dir: Path) -> APIRouter:
    """Return an APIRouter(prefix='/api') with the 1D and 2D spectra routes.

    Imports matplotlib's Figure/FigureCanvasAgg inside this factory so
    matplotlib is never pulled in at webview package import time (WV-08).

    Args:
        analysis_dir: Path to the CASE analysis directory (already resolved
            by create_app; do NOT call .resolve() here again).

    Returns:
        An APIRouter with:
        - GET /spectra/1d/carbon -> real 13C trace + peak overlay, or a
          placeholder PNG on any failure (never 500, SP-02).
        - GET /spectra/1d/proton -> real 1H trace (no peak overlay -- this
          schema has no 1H peak-JSON source), or an independent placeholder
          PNG when no 1H experiment is found.
        - GET /spectra/2d/hsqc -> real HSQC contour + cross-peak overlay
          (uniform accent markers, D-05), or a placeholder PNG on any
          failure (never 500, SP-02, Phase 96).
        - GET /spectra/2d/hmbc -> real HMBC contour + cross-peak overlay
          colour-coded by flag (D-06) + a top-right flag legend, or an
          independent placeholder PNG (Phase 96).
        - GET /spectra/2d/cosy -> real COSY contour + diagonal + cross-peak
          overlay (D-07), or an independent placeholder PNG (Phase 96).
        Each 2D route's rendered PNG is cached in the module-level
        `_png_cache`, keyed on the selected experiment's source mtime, so
        repeated polls with an unchanged mtime return the cached bytes
        without re-rendering (SC3/SC4).
    """
    # Lazy matplotlib import -- only reached via create_app() (WV-08/D-04)
    from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: PLC0415
    from matplotlib.figure import Figure  # noqa: PLC0415

    router = APIRouter(prefix="/api")

    def _render_nucleus(nucleus: str, no_experiment_message: str) -> bytes:
        """Render one nucleus's route body; degrade to a placeholder on ANY failure.

        Wraps the whole body in the broad never-500 guard (T-95-02-01):
        absent manifest, stale/unreadable bruker path, no matching
        experiment, or any unexpected rendering error all collapse to the
        same `no_experiment_message` placeholder -- HTTP 200, never a raise
        that would surface as a 500 at the route level.
        """
        try:
            manifest = _read_manifest(analysis_dir)
            if manifest is None:
                return _render_placeholder_png(Figure, FigureCanvasAgg, _MSG_NO_MANIFEST)

            bruker_dir = Path(manifest["bruker_data_dir"])
            if not bruker_dir.is_dir():
                return _render_placeholder_png(Figure, FigureCanvasAgg, _MSG_STALE_PATH)

            spectrum = _select_experiment(bruker_dir, nucleus)
            if spectrum is None:
                return _render_placeholder_png(Figure, FigureCanvasAgg, no_experiment_message)

            if nucleus == "13C":
                peaks = _read_peaks(analysis_dir)
                return _render_1d_png(Figure, FigureCanvasAgg, spectrum, peaks)

            # 1H route: no peak-JSON source in this schema -- render a bare
            # trace, no "peak positions unavailable" annotation (discretion,
            # documented in make_router's docstring).
            return _render_1d_png(
                Figure, FigureCanvasAgg, spectrum, [], annotate_missing_peaks=False
            )
        except Exception:  # noqa: BLE001 -- never-500 guard (SP-02/T-95-02-01)
            return _render_placeholder_png(Figure, FigureCanvasAgg, no_experiment_message)

    @router.get("/spectra/1d/carbon")
    def get_carbon_1d() -> Response:
        png_bytes = _render_nucleus("13C", _MSG_NO_CARBON)
        return Response(content=png_bytes, media_type="image/png")

    @router.get("/spectra/1d/proton")
    def get_proton_1d() -> Response:
        png_bytes = _render_nucleus("1H", _MSG_NO_PROTON)
        return Response(content=png_bytes, media_type="image/png")

    def _render_2d(experiment_type: str, no_experiment_message: str) -> bytes:
        """Render one 2D route's body; degrade to a placeholder on ANY failure.

        Same broad never-500 guard shape as `_render_nucleus` (T-95-02-01):
        absent manifest, stale/unreadable bruker path, no matching 2D
        experiment, or any unexpected rendering/mtime-lookup error all
        collapse to the same `no_experiment_message` placeholder -- HTTP
        200, never a raise that would surface as a 500 (SP-02). The
        `_source_mtime` lookup sits INSIDE this guard (96-RESEARCH.md
        Pitfall 5). Cache key is independent of the frontend's `?t=`
        cache-buster -- keyed on `(kind, source_mtime)` only (Pitfall 4).
        """
        try:
            manifest = _read_manifest(analysis_dir)
            if manifest is None:
                return _render_placeholder_png(Figure, FigureCanvasAgg, _MSG_NO_MANIFEST)

            bruker_dir = Path(manifest["bruker_data_dir"])
            if not bruker_dir.is_dir():
                return _render_placeholder_png(Figure, FigureCanvasAgg, _MSG_STALE_PATH)

            spectrum = _select_experiment_2d(bruker_dir, experiment_type)
            if spectrum is None:
                return _render_placeholder_png(Figure, FigureCanvasAgg, no_experiment_message)

            kind = experiment_type.lower()
            peaks_path = analysis_dir / "peaks" / f"{kind}.json"
            pdata_path = _selected_2d_pdata_path(bruker_dir, experiment_type)
            source_mtime = _source_mtime(pdata_path or bruker_dir, peaks_path)

            return _cached_or_render(
                kind,
                source_mtime,
                lambda: _render_2d_png(
                    Figure,
                    FigureCanvasAgg,
                    spectrum,
                    _read_peaks_2d(analysis_dir, kind),
                    experiment_type,
                ),
            )
        except Exception:  # noqa: BLE001 -- never-500 guard (SP-02/T-95-02-01)
            return _render_placeholder_png(Figure, FigureCanvasAgg, no_experiment_message)

    @router.get("/spectra/2d/hsqc")
    def get_hsqc_2d() -> Response:
        png_bytes = _render_2d("HSQC", _MSG_NO_HSQC)
        return Response(content=png_bytes, media_type="image/png")

    @router.get("/spectra/2d/hmbc")
    def get_hmbc_2d() -> Response:
        png_bytes = _render_2d("HMBC", _MSG_NO_HMBC)
        return Response(content=png_bytes, media_type="image/png")

    @router.get("/spectra/2d/cosy")
    def get_cosy_2d() -> Response:
        png_bytes = _render_2d("COSY", _MSG_NO_COSY)
        return Response(content=png_bytes, media_type="image/png")

    return router
