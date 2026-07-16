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
from pathlib import Path

import nmrglue as ng
import numpy as np

from lucy_ng.models import Spectrum2D
from lucy_ng.models.nus import NusAcquisitionParams


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
