"""Tests for the thin 1D JCAMP peak-pick bridge (Phase 102, D-03/D-04).

Honest proof level: `TestJcamp1dBridgeSchema` and
`TestJcamp1dBridgeQcDiscovery.test_qc_gate_discovers_bridge_output_as_trusted_reference`
/ `test_glob_does_not_cross_match_1d_filenames` run against the two REAL,
committed, whole 1D reference files (`tests/fixtures/jcamp/C20H32O2_1H.dx`,
`C20H32O2_13C.dx`) -- not trimmed, not synthetic -- so 1D bridge behaviour on
real data is genuinely fixture-covered. Only the negative-detection and
threshold-branch tests use a synthetic `Spectrum1D`, and only because no
committed 1D fixture happens to exercise those specific branches (a strong
negative lobe, an explicit `threshold=`/`snr_floor=` override). Nothing here
is stand-in-covered: `TestJcamp1dBridgeQcDiscovery` calls the real
`QcReferenceData.resolve()` and `_glob_by_keyword()` directly, with no
test-double substitution of any kind.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from lucy_ng.models import Spectrum1D

REF_1H = Path(__file__).parent / "fixtures" / "jcamp" / "C20H32O2_1H.dx"
REF_13C = Path(__file__).parent / "fixtures" / "jcamp" / "C20H32O2_13C.dx"


def _idx(scale: NDArray[np.float64], ppm: float) -> int:
    return int(np.argmin(np.abs(scale - ppm)))


def _build_synthetic_1d_spectrum(
    nucleus: str,
    positive_peaks: list[float],
    negative_peaks: list[float] | None = None,
) -> Spectrum1D:
    """Build a small deterministic Spectrum1D with explicit peak positions.

    Mirrors tests/nus/test_bridge.py::_build_synthetic_spectrum's pattern
    (a low-amplitude gaussian noise floor plus explicit single-point maxima
    placed at known ppm positions, well above the noise floor so
    AdaptivePeakPicker's default SNR mode picks them deterministically).
    """
    rng = np.random.default_rng(7)
    n = 200
    data = rng.normal(0.0, 10.0, size=n)
    ppm_scale = np.linspace(200.0, 0.0, n, dtype=np.float64)

    for ppm in positive_peaks:
        data[_idx(ppm_scale, ppm)] = 1.0e6
    for ppm in negative_peaks or []:
        data[_idx(ppm_scale, ppm)] = -1.0e6

    return Spectrum1D(
        data=data,
        ppm_scale=ppm_scale,
        nucleus=nucleus,
        frequency=125.77,
    )


class TestJcamp1dBridgeSchema:
    """Pitfall-2 guard: schema shape must match cli/pick.py::pick_1d exactly."""

    def test_payload_has_pick_1d_top_level_keys(self) -> None:
        from lucy_ng.processing.jcamp_1d_bridge import bridge_peak_pick_1d
        from lucy_ng.readers.jcamp import JcampReader

        spectrum = JcampReader.read_1d(REF_13C)
        payload = bridge_peak_pick_1d(spectrum)

        expected_keys = {
            "count",
            "noise_sigma",
            "negative_detected",
            "snr_floor_used",
            "peaks",
            "nucleus",
        }
        assert expected_keys <= set(payload)
        assert "cross_peaks" not in payload
        assert "c13_ppm" not in payload
        assert "h1_ppm" not in payload

    def test_peak_entries_have_ppm_intensity_snr(self) -> None:
        from lucy_ng.processing.jcamp_1d_bridge import bridge_peak_pick_1d
        from lucy_ng.readers.jcamp import JcampReader

        spectrum = JcampReader.read_1d(REF_13C)
        payload = bridge_peak_pick_1d(spectrum)

        assert payload["count"] == len(payload["peaks"])
        assert payload["peaks"], "expected at least one peak from the real 13C fixture"
        for peak in payload["peaks"]:
            assert set(peak) == {"ppm", "intensity", "snr"}
            assert isinstance(peak["ppm"], float)

    def test_negative_detection_matches_pick_1d_heuristic(self) -> None:
        from lucy_ng.processing.jcamp_1d_bridge import bridge_peak_pick_1d

        with_negative = _build_synthetic_1d_spectrum(
            "13C", positive_peaks=[150.0, 100.0], negative_peaks=[40.0]
        )
        without_negative = _build_synthetic_1d_spectrum(
            "13C", positive_peaks=[150.0, 100.0]
        )

        payload_with = bridge_peak_pick_1d(with_negative)
        payload_without = bridge_peak_pick_1d(without_negative)

        assert payload_with["negative_detected"] is True
        assert payload_without["negative_detected"] is False

    def test_snr_floor_used_reporting(self) -> None:
        from lucy_ng.processing.jcamp_1d_bridge import bridge_peak_pick_1d

        spectrum = _build_synthetic_1d_spectrum("13C", positive_peaks=[150.0, 100.0])

        default_payload = bridge_peak_pick_1d(spectrum)
        assert default_payload["snr_floor_used"] == 5.0

        custom_floor_payload = bridge_peak_pick_1d(spectrum, snr_floor=3.0)
        assert custom_floor_payload["snr_floor_used"] == 3.0

        threshold_payload = bridge_peak_pick_1d(spectrum, threshold=0.05)
        assert threshold_payload["snr_floor_used"] is None

    def test_unknown_nucleus_filename_raises(self) -> None:
        import pytest

        from lucy_ng.processing.jcamp_1d_bridge import peak_json_filename

        with pytest.raises(ValueError):
            peak_json_filename("19F")


class TestJcamp1dBridgeQcDiscovery:
    """The load-bearing proof (D-04): the unchanged QC gate discovers the
    bridge's output as trusted 1D reference, via a real, un-mocked
    QcReferenceData.resolve() run."""

    def test_qc_gate_discovers_bridge_output_as_trusted_reference(self, tmp_path: Path) -> None:
        from lucy_ng.nus.bridge import write_peak_json
        from lucy_ng.nus.qc import QcReferenceData
        from lucy_ng.processing.jcamp_1d_bridge import bridge_peak_pick_1d
        from lucy_ng.readers.jcamp import JcampReader

        for ref_path in (REF_1H, REF_13C):
            spectrum = JcampReader.read_1d(ref_path)
            payload = bridge_peak_pick_1d(spectrum)
            write_peak_json(tmp_path, payload["nucleus"], payload)

        ref = QcReferenceData.resolve(tmp_path)

        assert len(ref.trusted_c13) > 0
        assert len(ref.trusted_h1) > 0
        assert ref.classification_source != "insufficient_reference_data"

    def test_glob_does_not_cross_match_1d_filenames(self, tmp_path: Path) -> None:
        from lucy_ng.nus.bridge import write_peak_json
        from lucy_ng.nus.qc import _glob_by_keyword
        from lucy_ng.processing.jcamp_1d_bridge import bridge_peak_pick_1d
        from lucy_ng.readers.jcamp import JcampReader

        for ref_path in (REF_1H, REF_13C):
            spectrum = JcampReader.read_1d(ref_path)
            payload = bridge_peak_pick_1d(spectrum)
            write_peak_json(tmp_path, payload["nucleus"], payload)

        c13_matches = _glob_by_keyword(tmp_path, "13c")
        h1_matches = _glob_by_keyword(tmp_path, "1h")

        assert [p.name for p in c13_matches] == ["13C.json"]
        assert [p.name for p in h1_matches] == ["1H.json"]

    def test_wrong_2d_schema_would_be_silently_dropped(self, tmp_path: Path) -> None:
        """Negative control pinning 102-RESEARCH.md Pitfall 2's silent-failure
        mode: a hand-built 2D-shaped payload named '13C.json' is discovered
        by keyword-glob but its shift list is silently empty -- no exception,
        no loud error -- because _load_1d_shifts() reads peaks[].ppm, not
        cross_peaks[].c13_ppm."""
        import json

        from lucy_ng.nus.qc import QcReferenceData

        wrong_schema_dir = tmp_path / "wrong_schema"
        wrong_schema_dir.mkdir()
        wrong_payload = {
            "experiment": "HSQC",
            "n_cross_peaks": 1,
            "cross_peaks": [{"c13_ppm": 42.0, "h1_ppm": 1.2}],
        }
        (wrong_schema_dir / "13C.json").write_text(json.dumps(wrong_payload))

        ref = QcReferenceData.resolve(wrong_schema_dir)

        assert ref.trusted_c13 == []
