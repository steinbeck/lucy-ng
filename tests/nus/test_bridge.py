"""PICK-01 stubs: the peak-pick bridge.

RED-by-skip (Wave 0, Phase 99 Plan 01): `lucy_ng.nus.bridge` does not exist
yet -- ships in Plan 03. `nus/bridge.py` builds a `Spectrum2D` in memory
from a processed `.ft2` (mirrors `readers/bruker.py::read_2d()`'s
`ng.pipe.guess_udic`/`uc_from_udic` idiom) and calls the existing
`PeakPicker2D.pick_peaks()` directly (mirrors `cli/lsd.py::_perform_ranking()`'s
direct-call pattern) -- no new picker, no subprocess.

Implementing plan: Plan 03 (`lucy_ng.nus.bridge.build_spectrum2d` +
`lucy_ng.nus.bridge.bridge_peak_pick`).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 03")
def test_build_spectrum2d_from_ft2(tmp_path) -> None:
    """`build_spectrum2d()` must construct a `Spectrum2D` from a processed
    `.ft2` file (F1=13C indirect, F2=1H direct), preferring the
    `processed_ppm_axis.json` sidecar's calibrated F1 axis when present
    (99-PATTERNS.md Pattern 1) and falling back to the raw NMRPipe-header
    F1 axis otherwise.

    Implementing plan: Plan 03 (`lucy_ng.nus.bridge.build_spectrum2d`).
    """
    from lucy_ng.models import Spectrum2D
    from lucy_ng.nus.bridge import build_spectrum2d

    spectrum = build_spectrum2d(tmp_path / "processed.ft2", params=None, experiment_type="HSQC")
    assert isinstance(spectrum, Spectrum2D)


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 03")
def test_bridge_peak_pick_emits_schema(tmp_path) -> None:
    """`bridge_peak_pick()` must call `PeakPicker2D.pick_peaks()` unmodified
    and transform its raw `f1_position`/`f2_position`/`intensity`/`snr`
    output into the CASE-consumed per-peak schema -- for HSQC specifically
    the exact key set {c13_ppm, h1_ppm, edited_sign, multiplicity_hint,
    confidence, note} (99-PATTERNS.md's schema table, NOT the raw picker
    shape).

    Implementing plan: Plan 03 (`lucy_ng.nus.bridge.bridge_peak_pick`).
    """
    from lucy_ng.nus.bridge import bridge_peak_pick

    result = bridge_peak_pick(tmp_path / "processed.ft2", experiment_type="HSQC")
    expected_keys = {
        "c13_ppm", "h1_ppm", "edited_sign", "multiplicity_hint", "confidence", "note",
    }
    assert set(result["cross_peaks"][0].keys()) == expected_keys
