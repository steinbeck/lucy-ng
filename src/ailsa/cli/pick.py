"""CLI commands for peak picking from NMR spectra."""

import json
from typing import Any

import click
import numpy as np

from ailsa.processing import (
    AdaptivePeakPicker,
    PeakPicker2D,
)
from ailsa.readers import BrukerReader


@click.group()
def pick() -> None:
    """Peak picking from spectra."""
    pass


def _detect_multiplicity_edited(data: "np.ndarray[Any, Any]") -> tuple[bool, int]:
    """Detect whether an HSQC is multiplicity-edited (deterministic, no LLM).

    Ported verbatim from the proven ``ailsa pick 1d`` ``negative_detected``
    detector (np.min(data) < -0.05 * max_abs). A multiplicity-edited HSQC
    phases CH2 cross-peaks with opposite sign, producing genuine negative
    intensity well below the noise floor; no negatives => NOT edited =>
    sign-ambiguous.

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


@pick.command("1d")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=None,
    help="Peak threshold (auto if not set).",
)
@click.option(
    "--snr-floor",
    "-s",
    type=float,
    default=None,
    help="SNR floor multiplier k (default: 5.0 signal/noise; use 3.0 for exploratory re-pick).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def pick_1d(
    path: str, threshold: float | None, snr_floor: float | None, output_format: str
) -> None:
    """Pick peaks from a 1D spectrum.

    PATH is the path to the Bruker experiment directory.

    Automatically detects negative peaks in spectra that contain them
    (e.g., DEPT-135 where CH2 peaks are negative).
    """
    spectrum = BrukerReader.read_1d(path)

    # Auto-detect negative peaks: if spectrum has significant negative values
    # (e.g., DEPT-135 CH2 peaks), enable negative peak detection automatically.
    effective_threshold = threshold if threshold is not None else 0.05
    max_abs = float(np.max(np.abs(spectrum.data)))
    has_significant_negative = bool(np.min(spectrum.data) < -effective_threshold * max_abs)

    # When an explicit threshold is given, disable SNR mode to preserve legacy behaviour.
    # When threshold is None (default), use SNR mode (MAD/CDCl3-aware threshold).
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

    # Compute the effective snr_floor for JSON output.
    # When use_snr=False (threshold mode): None.
    # When use_snr=True and snr_floor kwarg provided: that value.
    # When use_snr=True and no snr_floor kwarg: the method default (5.0).
    if not use_snr:
        snr_floor_used: float | None = None
    elif snr_floor is not None:
        snr_floor_used = snr_floor
    else:
        snr_floor_used = 5.0

    if output_format == "json":
        data = {
            "count": len(peaks.peaks),
            "noise_sigma": peaks.noise_sigma,  # None for legacy/explicit-threshold callers
            "negative_detected": has_significant_negative,
            "snr_floor_used": snr_floor_used,
            "peaks": [
                {
                    "ppm": p.position,
                    "intensity": p.intensity,
                    "snr": p.snr,  # None for explicit-threshold callers
                }
                for p in peaks.peaks
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        if has_significant_negative:
            click.echo(
                f"Found {len(peaks.peaks)} peaks (negative peak detection enabled):"
            )
        else:
            click.echo(f"Found {len(peaks.peaks)} peaks:")
        for p in sorted(peaks.peaks, key=lambda x: -x.position):
            click.echo(f"  {p.position:8.2f} ppm  (intensity: {p.intensity:.2e})")


@pick.command("2d")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=0.05,
    help="Peak threshold (default: 0.05).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def pick_2d(path: str, threshold: float, output_format: str) -> None:
    """Pick peaks from a 2D spectrum.

    PATH is the path to the Bruker experiment directory.
    """
    spectrum = BrukerReader.read_2d(path)
    peaks = PeakPicker2D.pick_peaks(spectrum, threshold=threshold)

    if output_format == "json":
        data = {
            "experiment_type": spectrum.experiment_type,
            "count": len(peaks.peaks),
            "peaks": [
                {
                    "f1_position": p.f1_position,
                    "f2_position": p.f2_position,
                    "intensity": p.intensity,
                }
                for p in peaks.peaks
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Found {len(peaks.peaks)} peaks in {spectrum.experiment_type}:")
        for p in sorted(peaks.peaks, key=lambda x: (-x.f1_position, x.f2_position)):
            click.echo(f"  F1: {p.f1_position:7.2f}  F2: {p.f2_position:6.2f}  (int: {p.intensity:.2e})")


@pick.command("hsqc")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=0.05,
    help="Peak threshold (default: 0.05).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def pick_hsqc(path: str, threshold: float, output_format: str) -> None:
    """Pick raw HSQC peaks above threshold.

    PATH is the path to the HSQC Bruker experiment directory.

    Returns raw cross-peaks without DEPT-guided filtering. The AI agent
    applies DEPT-guided filtering logic using skill knowledge.
    """
    spectrum = BrukerReader.read_2d(path)
    peaks = PeakPicker2D.pick_peaks(spectrum, threshold=threshold)

    # Deterministic multiplicity-editing detector (MULT-04 / D-05), ported
    # from the proven pick_1d negative_detected path. Independent of the
    # peak-picking --threshold (uses the fixed 0.05 fraction).
    multiplicity_edited, negative_crosspeak_count = _detect_multiplicity_edited(
        spectrum.data
    )

    if output_format == "json":
        data = {
            "experiment_type": spectrum.experiment_type,
            "count": len(peaks.peaks),
            "multiplicity_edited": multiplicity_edited,
            "negative_crosspeak_count": negative_crosspeak_count,
            "peaks": [
                {
                    "f1_position": p.f1_position,
                    "f2_position": p.f2_position,
                    "intensity": p.intensity,
                }
                for p in peaks.peaks
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        edit_note = (
            "multiplicity-edited" if multiplicity_edited else "not multiplicity-edited"
        )
        click.echo(
            f"Found {len(peaks.peaks)} peaks in {spectrum.experiment_type} "
            f"({edit_note}):"
        )
        for p in sorted(peaks.peaks, key=lambda x: (-x.f1_position, x.f2_position)):
            click.echo(f"  F1: {p.f1_position:7.2f}  F2: {p.f2_position:6.2f}  (int: {p.intensity:.2e})")


@pick.command("hmbc")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=None,
    help="Fraction-of-max peak threshold (legacy mode; SNR mode if not set).",
)
@click.option(
    "--snr-floor",
    "-s",
    type=float,
    default=None,
    help="SNR floor multiplier k (default: 5.0). Recovers weak long-range "
    "cross-peaks the fraction-of-max threshold drops (FIX-12).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def pick_hmbc(
    path: str, threshold: float | None, snr_floor: float | None, output_format: str
) -> None:
    """Pick raw HMBC peaks.

    PATH is the path to the HMBC Bruker experiment directory.

    By default uses a MAD-based SNR floor (the 2D analog of FIX-08): weak but
    real long-range cross-peaks that sit far below the fraction-of-max threshold
    are kept when they are SNR>=floor over local 2D noise. An explicit
    ``-t/--threshold`` falls back to the legacy fraction-of-max path.

    Returns raw cross-peaks without cross-validation filtering. The AI agent
    applies HMBC filtering logic using skill knowledge.
    """
    spectrum = BrukerReader.read_2d(path)

    # Explicit -t disables SNR mode (legacy fraction-of-max); otherwise SNR mode.
    use_snr = threshold is None
    if threshold is not None:
        peaks = PeakPicker2D.pick_peaks(spectrum, threshold=threshold, use_snr=False)
    elif snr_floor is not None:
        peaks = PeakPicker2D.pick_peaks(spectrum, snr_floor=snr_floor, use_snr=True)
    else:
        peaks = PeakPicker2D.pick_peaks(spectrum, use_snr=True)

    # Effective snr_floor for JSON: None in legacy mode, else the value (method
    # default 5.0 when -s not given).
    if not use_snr:
        snr_floor_used: float | None = None
    elif snr_floor is not None:
        snr_floor_used = snr_floor
    else:
        snr_floor_used = 5.0

    if output_format == "json":
        data = {
            "experiment_type": spectrum.experiment_type,
            "count": len(peaks.peaks),
            "snr_floor_used": snr_floor_used,
            "peaks": [
                {
                    "f1_position": p.f1_position,
                    "f2_position": p.f2_position,
                    "intensity": p.intensity,
                    "snr": p.snr,  # None for legacy/explicit-threshold callers
                }
                for p in peaks.peaks
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        mode = f"SNR floor k={snr_floor_used}" if use_snr else "fraction-of-max"
        click.echo(
            f"Found {len(peaks.peaks)} peaks in {spectrum.experiment_type} ({mode}):"
        )
        for p in sorted(peaks.peaks, key=lambda x: (-x.f1_position, x.f2_position)):
            click.echo(
                f"  F1: {p.f1_position:7.2f}  F2: {p.f2_position:6.2f}  "
                f"(int: {p.intensity:.2e})"
            )
