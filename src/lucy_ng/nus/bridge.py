"""Peak-pick bridge: processed `.ft2` -> `Spectrum2D` -> `PeakPicker2D` -> CASE JSON schema.

Phase 99, PICK-01/PICK-03. Builds an in-memory `Spectrum2D` from Phase-98's
processed `.ft2` output (mirrors `readers/bruker.py::read_2d()`'s
`guess_udic`/`uc_from_udic` idiom, swapping `ng.bruker.*` for `ng.pipe.*`),
calls the existing `PeakPicker2D.pick_peaks()` directly (mirrors
`cli/lsd.py::_perform_ranking()`'s direct-call pattern -- no subprocess, no
new picker), and transforms the raw picker output into the per-experiment
CASE schema (`analysis/nmr_peaks/*.json`) with a D-05 additive top-level
"reconstruction" metadata block and D-06 verdict-derived per-peak
confidence.

HARD invariant: `cli/pick.py` stays byte-unchanged. The multiplicity-edited
detector is shared via `lucy_ng.processing.edited_sign.detect_multiplicity_edited`
(a verbatim importable twin of `cli/pick.py`'s module-private copy), never
by editing `cli/pick.py` itself.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import nmrglue as ng
import numpy as np

from lucy_ng.models import Peak2D, Spectrum2D
from lucy_ng.models.nus import NusAcquisitionParams, QcReport, QcVerdict
from lucy_ng.processing import PeakPicker2D, detect_multiplicity_edited

_VALID_BRIDGE_EXPERIMENTS = {"HSQC", "HMBC", "COSY"}


def build_spectrum2d(
    processed_ft2: Path | str,
    params: NusAcquisitionParams,
    experiment_type: str,
) -> Spectrum2D:
    """Build a `Spectrum2D` from a Phase-98 processed `.ft2` file.

    Mirrors `readers/bruker.py::read_2d()`'s `ng.bruker.guess_udic`/
    `uc_from_udic` idiom with `ng.pipe.*` substituted for the NMRPipe-format
    processed output. Prefers the `processed_ppm_axis.json` sidecar's
    calibrated F1 axis (written by `nus/postprocess.py::process_indirect()`,
    Phase 98) over the raw NMRPipe-header F1 axis when the sidecar exists
    next to `processed_ft2` -- the sidecar already carries the §10
    1D-cross-check calibration offset a NUS-reconstructed indirect
    dimension needs and the raw header does not.

    Args:
        processed_ft2: Path to the processed `.ft2` NMRPipe file.
        params: Acquisition params supplying `f1_nucleus`/`f2_nucleus`/`f2_sfo1`
            (not recoverable from the NMRPipe header alone).
        experiment_type: One of `Spectrum2D`'s valid experiment types
            (HSQC/HMBC/COSY/TOCSY/NOESY/ROESY).

    Returns:
        An in-memory `Spectrum2D` ready for `PeakPicker2D.pick_peaks()`.

    Raises:
        RuntimeError: If the `.ft2` file or its F1-calibration sidecar
            cannot be read/parsed -- fail-loud, mirroring
            `nus/runner.py::run_stage()`'s typed-error convention rather
            than propagating a bare exception.
    """
    processed_ft2 = Path(processed_ft2)
    try:
        dic, data = ng.pipe.read(str(processed_ft2))
        udic = ng.pipe.guess_udic(dic, data)
    except Exception as exc:
        raise RuntimeError(
            f"build_spectrum2d: failed to read processed NMRPipe file "
            f"{processed_ft2}: {exc!r}"
        ) from exc

    uc_f2 = ng.fileiobase.uc_from_udic(udic, dim=1)
    f2_ppm_scale = np.array(uc_f2.ppm_scale(), dtype=np.float64)

    sidecar = processed_ft2.parent / "processed_ppm_axis.json"
    if sidecar.exists():
        try:
            sidecar_data = json.loads(sidecar.read_text())
            f1_ppm_scale = np.array(sidecar_data["calibrated_ppm_axis"], dtype=np.float64)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"build_spectrum2d: failed to read F1 ppm-calibration sidecar "
                f"{sidecar}: {exc!r}"
            ) from exc
    else:
        uc_f1 = ng.fileiobase.uc_from_udic(udic, dim=0)
        f1_ppm_scale = np.array(uc_f1.ppm_scale(), dtype=np.float64)

    return Spectrum2D(
        data=np.array(data, dtype=np.float64),
        f1_ppm_scale=f1_ppm_scale,
        f2_ppm_scale=f2_ppm_scale,
        f1_nucleus=params.f1_nucleus,
        f2_nucleus=params.f2_nucleus,
        experiment_type=experiment_type,
        frequency=params.f2_sfo1,
    )


def confidence_from_verdict(verdict: QcVerdict) -> str:
    """D-06: per-peak `confidence` derived from the QC verdict.

    PASS -> "high", PARTIAL -> "low". FAIL peaks must never reach this
    function: D-07 quarantines a FAIL reconstruction before any write, so
    there is no honest confidence value to emit for it.

    Raises:
        ValueError: If called with `QcVerdict.FAIL` -- a programming error
            in the caller (the pipeline must quarantine before calling this).
    """
    if verdict == QcVerdict.PASS:
        return "high"
    if verdict == QcVerdict.PARTIAL:
        return "low"
    raise ValueError(
        f"confidence_from_verdict: FAIL peaks are never consumable (D-07 "
        f"quarantines before write); got {verdict!r}"
    )


def _confidence_and_note(qc_report: QcReport | None, backend: str) -> tuple[str, str]:
    """Derive per-peak (confidence, note) from an optional QC report.

    When `qc_report` is `None` (the bridge is being called standalone,
    before Plan 04's `pipeline` has computed the real verdict -- the
    causal-ordering fix: peaks must exist before QC can grade them), an
    honest "pending_qc" placeholder is emitted rather than a fabricated
    verdict-derived value. `pipeline` re-calls `bridge_peak_pick()` with the
    real `qc_report` once QC has run, replacing this placeholder before
    anything reaches `analysis/nmr_peaks/`.
    """
    if qc_report is None:
        return "pending_qc", f"reconstructed via {backend}; QC verdict not yet available"
    confidence = confidence_from_verdict(qc_report.verdict)
    violated = qc_report.violated_checks()
    if qc_report.verdict == QcVerdict.PASS:
        note = f"reconstructed via {backend}; QC verdict PASS"
    else:
        note = f"reconstructed via {backend}; QC verdict PARTIAL (violated: {', '.join(violated)})"
    return confidence, note


def _build_caveat(backend: str, qc_report: QcReport | None) -> str:
    """Regenerate the top-level `caveat` to reflect the real backend/QC state.

    Replaces the current home-IST caveat (CONTEXT.md "byte-for-byte"
    clarification: the per-peak *keys* stay schema-identical, but `caveat`
    and per-peak `confidence` necessarily change).
    """
    if qc_report is None:
        return f"Reconstructed via {backend}. QC verdict not yet available."
    violated = qc_report.violated_checks()
    caveat = f"Reconstructed via {backend}. QC verdict: {qc_report.verdict.value}."
    if violated:
        caveat += f" Violated checks: {', '.join(violated)}."
    return caveat


def _reconstruction_metadata_block(
    *, backend: str, iterations: int | None, qc_report: QcReport | None
) -> dict[str, Any]:
    """D-05: small, additive top-level metadata block.

    Kept small and focused (backend, iterations, verdict, violated-check
    names, thresholds used) -- not full per-check numeric traces (T-99-08,
    99-RESEARCH.md Pitfall 6: the only consumer is an LLM agent, an
    oversized block burns its attention budget for no benefit).
    """
    if qc_report is not None:
        qc_verdict = qc_report.verdict.value
        violated_checks = qc_report.violated_checks()
        thresholds_used = dict(qc_report.thresholds_used)
    else:
        qc_verdict = "UNKNOWN"
        violated_checks = []
        thresholds_used = {}
    return {
        "backend": backend,
        "iterations": iterations,
        "qc_verdict": qc_verdict,
        "violated_checks": violated_checks,
        "thresholds_used": thresholds_used,
    }


def _hsqc_cross_peaks(
    peaks: list[Peak2D], spectrum: Spectrum2D, confidence: str, note: str
) -> list[dict[str, Any]]:
    """Transform raw HSQC Peak2D output into the CASE per-peak schema.

    Sign->multiplicity mapping is gated by whether the whole spectrum is
    multiplicity-edited (`detect_multiplicity_edited`, shared with
    `cli/pick.py` via `processing/edited_sign.py`): edited -> positive
    peaks are CH/CH3, negative peaks are CH2; not edited -> every peak is
    sign-ambiguous (CH_or_CH2_or_CH3).
    """
    multiplicity_edited, _ = detect_multiplicity_edited(spectrum.data)
    cross_peaks: list[dict[str, Any]] = []
    for peak in peaks:
        if multiplicity_edited:
            sign, hint = ("positive", "CH_or_CH3") if peak.intensity >= 0 else ("negative", "CH2")
        else:
            sign, hint = "ambiguous", "CH_or_CH2_or_CH3"
        cross_peaks.append(
            {
                "c13_ppm": peak.f1_position,
                "h1_ppm": peak.f2_position,
                "edited_sign": f"{sign}({hint})",
                "multiplicity_hint": hint,
                "confidence": confidence,
                "note": note,
            }
        )
    return cross_peaks


def _hmbc_cross_peaks(
    peaks: list[Peak2D], confidence: str, note: str, tol: float = 0.5
) -> list[dict[str, Any]]:
    """Transform raw HMBC Peak2D output into the CASE per-peak schema.

    `rel_intensity` is normalized against the max |intensity| across the
    whole HMBC list (zero-guarded). `rank_in_carbon` ranks peaks sharing a
    carbon (grouped within `tol` ppm) by descending |intensity|.
    `suspected_1J_artifact` is conservatively `False` for every bridge-picked
    peak: flagging a genuine 1J leak requires cross-referencing the sibling
    HSQC list, which is out of scope for a single per-experiment
    `bridge_peak_pick()` call (planner discretion; may be added as a
    pipeline-level post-process step in a future plan).
    """
    if not peaks:
        return []
    max_abs = max((abs(p.intensity) for p in peaks), default=0.0) or 1.0

    groups: dict[float, list[Peak2D]] = defaultdict(list)
    for peak in peaks:
        groups[round(peak.f1_position / tol) * tol].append(peak)
    rank_by_id: dict[int, int] = {}
    for group in groups.values():
        for rank, peak in enumerate(sorted(group, key=lambda p: -abs(p.intensity)), start=1):
            rank_by_id[id(peak)] = rank

    return [
        {
            "c13_ppm": peak.f1_position,
            "h1_ppm": peak.f2_position,
            "rel_intensity": abs(peak.intensity) / max_abs,
            "rank_in_carbon": rank_by_id[id(peak)],
            "suspected_1J_artifact": False,
            "confidence": confidence,
            "note": note,
        }
        for peak in peaks
    ]


def _cosy_cross_peaks(peaks: list[Peak2D], confidence: str, note: str) -> list[dict[str, Any]]:
    """Transform raw COSY Peak2D output into the CASE per-peak schema.

    Both COSY dimensions are 1H (F1 = F2 = 1H), so `h1a_ppm`/`h1b_ppm` map
    directly from `f1_position`/`f2_position`.
    """
    if not peaks:
        return []
    max_abs = max((abs(p.intensity) for p in peaks), default=0.0) or 1.0
    return [
        {
            "h1a_ppm": peak.f1_position,
            "h1b_ppm": peak.f2_position,
            "rel_intensity": abs(peak.intensity) / max_abs,
            "confidence": confidence,
            "note": note,
        }
        for peak in peaks
    ]


def bridge_peak_pick(
    spectrum: Spectrum2D,
    *,
    experiment: str,
    qc_report: QcReport | None = None,
    recon_meta: dict[str, Any] | None = None,
    threshold: float | None = None,
    snr_floor: float = 5.0,
) -> dict[str, Any]:
    """Peak-pick `spectrum` and serialize into the CASE per-experiment JSON schema.

    Calls `PeakPicker2D.pick_peaks()` directly (unmodified, no subprocess --
    PICK-01) and transforms its raw `f1_position`/`f2_position`/`intensity`
    output into the schema `analysis/nmr_peaks/*.json` files carry: HSQC
    `{c13_ppm, h1_ppm, edited_sign, multiplicity_hint, confidence, note}`,
    HMBC `{c13_ppm, h1_ppm, rel_intensity, rank_in_carbon,
    suspected_1J_artifact, confidence, note}`, COSY `{h1a_ppm, h1b_ppm,
    rel_intensity, confidence, note}`.

    Accepts an *optional* `qc_report`/`recon_meta` so a caller (Plan 04's
    `lucy nus pipeline`) can call this twice: once without them to produce
    peaks for the QC gate to grade, and once more with the real `QcReport`
    to build the final, confidence-corrected payload that actually gets
    written (D-07's write boundary). When omitted, confidence is the
    honest "pending_qc" placeholder (`_confidence_and_note`), never a
    fabricated verdict-derived value.

    Args:
        spectrum: The in-memory `Spectrum2D` (e.g. from `build_spectrum2d()`).
        experiment: One of "HSQC", "HMBC", "COSY".
        qc_report: The QC gate's verdict for this reconstruction, if already
            computed (D-06 confidence derivation).
        recon_meta: `{"backend": str, "iterations": int | None}` sourced
            from `NusReconstructionResult` (D-05 metadata block).
        threshold: Passed through to `PeakPicker2D.pick_peaks()`.
        snr_floor: Passed through to `PeakPicker2D.pick_peaks()`.

    Returns:
        A dict with top-level keys `{experiment, caveat, n_cross_peaks,
        cross_peaks, reconstruction}` -- schema-identical per-peak keys to
        the existing `analysis/nmr_peaks/*.json` files, plus the D-05
        additive `reconstruction` metadata block.

    Raises:
        ValueError: If `experiment` is not one of HSQC/HMBC/COSY.
    """
    if experiment not in _VALID_BRIDGE_EXPERIMENTS:
        raise ValueError(
            f"bridge_peak_pick: unsupported experiment {experiment!r}, "
            f"expected one of {sorted(_VALID_BRIDGE_EXPERIMENTS)}"
        )

    multiplicity_edited = False
    if experiment == "HSQC":
        multiplicity_edited, _ = detect_multiplicity_edited(spectrum.data)

    peak_list = PeakPicker2D.pick_peaks(
        spectrum,
        threshold=threshold,
        use_snr=threshold is None,
        snr_floor=snr_floor,
        detect_negative=multiplicity_edited,
    )

    recon_meta = recon_meta or {}
    backend = recon_meta.get("backend", "unknown")
    iterations = recon_meta.get("iterations")
    confidence, note = _confidence_and_note(qc_report, backend)

    if experiment == "HSQC":
        cross_peaks = _hsqc_cross_peaks(peak_list.peaks, spectrum, confidence, note)
    elif experiment == "HMBC":
        cross_peaks = _hmbc_cross_peaks(peak_list.peaks, confidence, note)
    else:
        cross_peaks = _cosy_cross_peaks(peak_list.peaks, confidence, note)

    return {
        "experiment": experiment,
        "caveat": _build_caveat(backend, qc_report),
        "n_cross_peaks": len(cross_peaks),
        "cross_peaks": cross_peaks,
        "reconstruction": _reconstruction_metadata_block(
            backend=backend, iterations=iterations, qc_report=qc_report
        ),
    }


def write_peak_json(out_dir: Path | str, experiment: str, payload: dict[str, Any]) -> Path:
    """Write a `bridge_peak_pick()` payload to `out_dir/{experiment}.json`.

    Bridge-level convenience only: the PASS/PARTIAL-vs-FAIL write/quarantine
    branch (D-07) is Plan 04's responsibility (`cli/nus.py::pipeline`) --
    this helper serializes+writes unconditionally once the caller has
    already decided to write.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{experiment}.json"
    out_path.write_text(json.dumps(payload, indent=2))
    return out_path
