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
and deterministic synthetic Spectrum2D data (mirroring
`tests/test_hmbc_peak_picking_integrity.py`'s established synthetic-peak
pattern), matching `nus/bridge.py`'s actual implemented signatures
(`build_spectrum2d(processed_ft2, params, experiment_type)` /
`bridge_peak_pick(spectrum, *, experiment=...)`) -- the same class of
Wave-0-stub-vs-real-signature correction Phase 98 Plans 03/05 made.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

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


def _idx(scale: NDArray[np.float64], ppm: float) -> int:
    return int(np.argmin(np.abs(scale - ppm)))


def _build_synthetic_spectrum(
    experiment_type: str,
    positive_peaks: list[tuple[float, float]],
    negative_peaks: list[tuple[float, float]] | None = None,
    f1_label: str = "13C",
    f2_label: str = "1H",
) -> Spectrum2D:
    """Build a small deterministic Spectrum2D with explicit peak positions.

    Mirrors tests/test_hmbc_peak_picking_integrity.py's synthetic-peak
    pattern: a low-amplitude gaussian noise floor plus explicit single-pixel
    maxima placed at known ppm positions, well above the noise floor so
    PeakPicker2D's default SNR mode picks them deterministically.
    """
    rng = np.random.default_rng(7)
    n1, n2 = 32, 48
    data = rng.normal(0.0, 50.0, size=(n1, n2))

    f1_scale = np.linspace(200.0, 0.0, n1, dtype=np.float64)
    f2_scale = np.linspace(10.0, 0.0, n2, dtype=np.float64)

    for f1_ppm, f2_ppm in positive_peaks:
        data[_idx(f1_scale, f1_ppm), _idx(f2_scale, f2_ppm)] = 1.0e6
    for f1_ppm, f2_ppm in negative_peaks or []:
        data[_idx(f1_scale, f1_ppm), _idx(f2_scale, f2_ppm)] = -1.0e6

    return Spectrum2D(
        data=data,
        f1_ppm_scale=f1_scale,
        f2_ppm_scale=f2_scale,
        f1_nucleus=f1_label,
        f2_nucleus=f2_label,
        experiment_type=experiment_type,
        frequency=500.13,
    )


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


# ---------------------------------------------------------------------------
# bridge_peak_pick() -- per-experiment CASE schema serialization (PICK-01).
# ---------------------------------------------------------------------------


def test_bridge_peak_pick_emits_hsqc_schema() -> None:
    """HSQC cross-peaks have exactly {c13_ppm, h1_ppm, edited_sign,
    multiplicity_hint, confidence, note} -- NOT the raw picker shape
    (f1_position/f2_position/intensity/snr)."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _build_synthetic_spectrum(
        "HSQC", positive_peaks=[(69.06, 0.99)], negative_peaks=[(38.5, 1.9)]
    )
    result = bridge_peak_pick(spectrum, experiment="HSQC", threshold=0.05)

    expected_keys = {
        "c13_ppm", "h1_ppm", "edited_sign", "multiplicity_hint", "confidence", "note",
    }
    assert result["experiment"] == "HSQC"
    assert result["n_cross_peaks"] == len(result["cross_peaks"]) == 2
    for cross_peak in result["cross_peaks"]:
        assert set(cross_peak.keys()) == expected_keys


def test_bridge_peak_pick_hsqc_multiplicity_edited_sign_mapping() -> None:
    """Multiplicity-edited HSQC: positive -> CH_or_CH3, negative -> CH2."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _build_synthetic_spectrum(
        "HSQC", positive_peaks=[(69.06, 0.99)], negative_peaks=[(38.5, 1.9)]
    )
    result = bridge_peak_pick(spectrum, experiment="HSQC", threshold=0.05)

    by_hint = {p["multiplicity_hint"] for p in result["cross_peaks"]}
    assert by_hint == {"CH_or_CH3", "CH2"}
    for peak in result["cross_peaks"]:
        if peak["multiplicity_hint"] == "CH_or_CH3":
            assert peak["edited_sign"] == "positive(CH_or_CH3)"
        else:
            assert peak["edited_sign"] == "negative(CH2)"


def test_bridge_peak_pick_hsqc_not_edited_is_ambiguous() -> None:
    """A non-multiplicity-edited HSQC (no negative cross-peaks) reports
    every peak as sign-ambiguous (CH_or_CH2_or_CH3)."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _build_synthetic_spectrum("HSQC", positive_peaks=[(69.06, 0.99), (30.2, 1.4)])
    result = bridge_peak_pick(spectrum, experiment="HSQC", threshold=0.05)

    for peak in result["cross_peaks"]:
        assert peak["multiplicity_hint"] == "CH_or_CH2_or_CH3"
        assert peak["edited_sign"] == "ambiguous(CH_or_CH2_or_CH3)"


def test_bridge_peak_pick_emits_hmbc_schema() -> None:
    """HMBC cross-peaks have exactly {c13_ppm, h1_ppm, rel_intensity,
    rank_in_carbon, suspected_1J_artifact, confidence, note}."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _build_synthetic_spectrum(
        "HMBC", positive_peaks=[(142.0, 1.57), (142.0, 2.3), (79.35, 1.05)]
    )
    result = bridge_peak_pick(spectrum, experiment="HMBC", threshold=0.05)

    expected_keys = {
        "c13_ppm", "h1_ppm", "rel_intensity", "rank_in_carbon",
        "suspected_1J_artifact", "confidence", "note",
    }
    assert result["cross_peaks"]
    for cross_peak in result["cross_peaks"]:
        assert set(cross_peak.keys()) == expected_keys
    ranks_at_142 = sorted(
        p["rank_in_carbon"] for p in result["cross_peaks"] if abs(p["c13_ppm"] - 142.0) < 1.0
    )
    assert ranks_at_142 == [1, 2]


def test_bridge_peak_pick_emits_cosy_schema() -> None:
    """COSY cross-peaks have exactly {h1a_ppm, h1b_ppm, rel_intensity,
    confidence, note}; both dims map from f1/f2_position (both 1H)."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _build_synthetic_spectrum(
        "COSY", positive_peaks=[(5.32, 1.57)], f1_label="1H"
    )
    result = bridge_peak_pick(spectrum, experiment="COSY", threshold=0.05)

    expected_keys = {"h1a_ppm", "h1b_ppm", "rel_intensity", "confidence", "note"}
    assert result["cross_peaks"]
    for cross_peak in result["cross_peaks"]:
        assert set(cross_peak.keys()) == expected_keys


def test_bridge_peak_pick_rejects_unknown_experiment() -> None:
    """An unsupported experiment type raises ValueError (refuse-to-guess)."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _build_synthetic_spectrum("HSQC", positive_peaks=[(69.06, 0.99)])
    with pytest.raises(ValueError):
        bridge_peak_pick(spectrum, experiment="NOESY", threshold=0.05)
