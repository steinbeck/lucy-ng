"""PICK-01: the peak-pick bridge (Phase 99 Plan 03).

`nus/bridge.py` builds a `Spectrum2D` in memory from a processed `.ft2`
(mirrors `readers/bruker.py::read_2d()`'s `ng.pipe.guess_udic`/
`uc_from_udic` idiom) and calls the existing `PeakPicker2D.pick_peaks()`
directly (mirrors `cli/lsd.py::_perform_ranking()`'s direct-call pattern)
-- no new picker, no subprocess.

Note on Wave 0 (Plan 01) provenance: the original RED-by-skip stubs called
`build_spectrum2d(tmp_path / "processed.ft2", params=None, ...)` /
`bridge_peak_pick(tmp_path / "processed.ft2", experiment_type=...)` against
a `.ft2` path that was never actually written to disk -- placeholders that
could never pass as literally written (build_spectrum2d must genuinely
parse an NMRPipe header; there is no real reconstruction fixture until
Phase 100). This file replaces those placeholders with a real,
nmrglue-readable synthetic `.ft2` fixture (`make_valid_ft2`, conftest.py)
matching `nus/bridge.py`'s actual implemented signature
(`build_spectrum2d(processed_ft2, params, experiment_type)`) -- the same
class of Wave-0-stub-vs-real-signature correction Phase 98 Plans 03/05
made. `bridge_peak_pick()`'s schema tests are added in Task 2 of this plan.
"""

from __future__ import annotations

import pytest

from lucy_ng.models import Spectrum2D
from lucy_ng.models.nus import NusAcquisitionParams


def _make_params(**overrides: object) -> NusAcquisitionParams:
    """Minimal valid `NusAcquisitionParams` -- `build_spectrum2d()` only
    reads `f1_nucleus`/`f2_nucleus`/`f2_sfo1` from it, but the model
    requires the full acquisition field set to validate."""
    defaults: dict[str, object] = dict(
        pulse_program="hsqcedetgpsisp2.3",
        f2_nucleus="1H",
        f2_sfo1=500.13,
        f2_sw_h=8000.0,
        f2_td=2048,
        byte_order=0,
        dtype_code=0,
        decim=32.0,
        dspfvs=20,
        grpdly=67.98,
        nus_amount_pct=25,
        nus_seed=1,
        f1_nucleus="13C",
        f1_sfo1=125.77,
        f1_sw_h=25000.0,
        f1_o1=10000.0,
        f1_td=256,
        fnmode_f1=6,
        nus_td=256,
    )
    defaults.update(overrides)
    return NusAcquisitionParams(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_spectrum2d() -- .ft2 -> Spectrum2D construction.
# ---------------------------------------------------------------------------


def test_build_spectrum2d_from_ft2(make_valid_ft2) -> None:
    """`build_spectrum2d()` constructs a `Spectrum2D` from a processed
    `.ft2` (F1=13C indirect, F2=1H direct)."""
    from lucy_ng.nus.bridge import build_spectrum2d

    ft2_path = make_valid_ft2()
    spectrum = build_spectrum2d(ft2_path, params=_make_params(), experiment_type="HSQC")

    assert isinstance(spectrum, Spectrum2D)
    assert spectrum.f1_nucleus == "13C"
    assert spectrum.f2_nucleus == "1H"
    assert spectrum.experiment_type == "HSQC"
    assert spectrum.data.shape == (8, 16)
    assert len(spectrum.f1_ppm_scale) == 8
    assert len(spectrum.f2_ppm_scale) == 16


def test_build_spectrum2d_prefers_sidecar_f1_axis(make_valid_ft2) -> None:
    """When `processed_ppm_axis.json` exists next to the `.ft2`, its
    `calibrated_ppm_axis` is used for F1 -- not the raw NMRPipe-header axis
    (99-PATTERNS.md Pattern 1, the F1-axis-override note)."""
    from lucy_ng.nus.bridge import build_spectrum2d

    calibrated_axis = [200.0, 195.0, 190.0, 185.0, 180.0, 175.0, 170.0, 165.0]
    ft2_path = make_valid_ft2(calibrated_f1_ppm_axis=calibrated_axis)
    spectrum = build_spectrum2d(ft2_path, params=_make_params(), experiment_type="HSQC")

    assert list(spectrum.f1_ppm_scale) == calibrated_axis


def test_build_spectrum2d_without_sidecar_uses_raw_header_axis(make_valid_ft2) -> None:
    """No sidecar present -> falls back to the raw NMRPipe-header F1 axis
    (not the same values a sidecar-driven test would assert)."""
    from lucy_ng.nus.bridge import build_spectrum2d

    ft2_path = make_valid_ft2()
    assert not (ft2_path.parent / "processed_ppm_axis.json").exists()
    spectrum = build_spectrum2d(ft2_path, params=_make_params(), experiment_type="HSQC")

    assert len(spectrum.f1_ppm_scale) == 8


def test_build_spectrum2d_fails_loud_on_missing_file(tmp_path) -> None:
    """A missing/unreadable `.ft2` raises a typed `RuntimeError`, not a bare
    traceback (fail-loud convention, mirroring `nus/runner.py::run_stage()`)."""
    from lucy_ng.nus.bridge import build_spectrum2d

    with pytest.raises(RuntimeError):
        build_spectrum2d(
            tmp_path / "does_not_exist.ft2", params=_make_params(), experiment_type="HSQC"
        )
