"""PICK-03: reconstruction-quality metadata embedding (Phase 99 Plan 03).

D-05 adds a new top-level additive metadata block (`"reconstruction"`)
alongside `experiment`/`cross_peaks`; existing per-peak keys stay
structurally unchanged. D-06 derives per-peak `confidence` from the QC
verdict (PASS -> high/medium, PARTIAL -> low), replacing the blanket
`"confidence": "low"`.

Note on Wave 0 (Plan 01) provenance: the original RED-by-skip stub called
`bridge_peak_pick(tmp_path / "processed.ft2", experiment_type="HSQC")` (a
`.ft2` path never written to disk) and expected `result["reconstruction"]`
to carry `{"backend", "iterations", "verdict"}`. This file replaces that
placeholder with `bridge_peak_pick()`'s actual implemented signature
(`bridge_peak_pick(spectrum, *, experiment=..., qc_report=..., recon_meta=...)`)
and the Task 2 action text's actual metadata-block key names (`qc_verdict`,
not `verdict`) -- the same class of Wave-0-stub-vs-real-signature
correction Phase 98 Plans 03/05 made.
"""

from __future__ import annotations

import numpy as np
import pytest

from lucy_ng.models import Spectrum2D
from lucy_ng.models.nus import QcCheckResult, QcReport, QcVerdict


def _hsqc_spectrum_with_one_peak() -> Spectrum2D:
    rng = np.random.default_rng(3)
    n1, n2 = 16, 24
    data = rng.normal(0.0, 50.0, size=(n1, n2))
    f1_scale = np.linspace(200.0, 0.0, n1, dtype=np.float64)
    f2_scale = np.linspace(10.0, 0.0, n2, dtype=np.float64)
    f1_idx = int(np.argmin(np.abs(f1_scale - 69.06)))
    f2_idx = int(np.argmin(np.abs(f2_scale - 0.99)))
    data[f1_idx, f2_idx] = 1.0e6
    return Spectrum2D(
        data=data,
        f1_ppm_scale=f1_scale,
        f2_ppm_scale=f2_scale,
        f1_nucleus="13C",
        f2_nucleus="1H",
        experiment_type="HSQC",
        frequency=500.13,
    )


def _pass_report() -> QcReport:
    return QcReport(
        verdict=QcVerdict.PASS,
        checks=[
            QcCheckResult(name="quaternary_exclusion", passed=True, critical=True),
            QcCheckResult(name="ppm_calibration", passed=True, critical=True),
        ],
        thresholds_used={"c13_tol": 0.5},
    )


def _partial_report() -> QcReport:
    return QcReport(
        verdict=QcVerdict.PARTIAL,
        checks=[
            QcCheckResult(name="quaternary_exclusion", passed=True, critical=True),
            QcCheckResult(
                name="edited_sign_consistency", passed=False, critical=False,
                details="mixed multiplicity_hint at [67.06]",
            ),
        ],
        thresholds_used={"c13_tol": 0.5},
    )


def test_metadata_block_present() -> None:
    """Emitted peak JSON carries a top-level "reconstruction" block with
    backend/iterations/qc_verdict/violated_checks/thresholds_used (D-05) --
    the existing per-peak keys remain structurally unchanged."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _hsqc_spectrum_with_one_peak()
    result = bridge_peak_pick(
        spectrum,
        experiment="HSQC",
        threshold=0.05,
        qc_report=_pass_report(),
        recon_meta={"backend": "nmrpipe_smile", "iterations": 400},
    )

    metadata_block = result["reconstruction"]
    assert {"backend", "iterations", "qc_verdict", "violated_checks", "thresholds_used"} <= set(
        metadata_block.keys()
    )
    assert metadata_block["backend"] == "nmrpipe_smile"
    assert metadata_block["iterations"] == 400
    assert metadata_block["qc_verdict"] == "PASS"
    assert metadata_block["violated_checks"] == []
    assert metadata_block["thresholds_used"] == {"c13_tol": 0.5}

    # PICK-01's "byte-for-byte" clarification: per-peak keys stay
    # structurally unchanged even though the metadata block is new.
    expected_peak_keys = {
        "c13_ppm", "h1_ppm", "edited_sign", "multiplicity_hint", "confidence", "note",
    }
    assert set(result["cross_peaks"][0].keys()) == expected_peak_keys


def test_metadata_block_reflects_partial_verdict_violations() -> None:
    """A PARTIAL verdict's violated soft checks are surfaced in the metadata
    block (D-01: PARTIAL writes peaks and proceeds, with the violation list
    visible to the CASE nmr-chemist agent)."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _hsqc_spectrum_with_one_peak()
    result = bridge_peak_pick(
        spectrum,
        experiment="HSQC",
        threshold=0.05,
        qc_report=_partial_report(),
        recon_meta={"backend": "nmrpipe_smile", "iterations": 250},
    )

    assert result["reconstruction"]["qc_verdict"] == "PARTIAL"
    assert result["reconstruction"]["violated_checks"] == ["edited_sign_consistency"]


def test_metadata_block_present_without_qc_report() -> None:
    """`bridge_peak_pick()` still emits a well-formed metadata block when
    called before QC has run (the causal-ordering fix: peaks must exist
    before QC can grade them) -- an honest "UNKNOWN" verdict, never a
    fabricated PASS/PARTIAL."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _hsqc_spectrum_with_one_peak()
    result = bridge_peak_pick(spectrum, experiment="HSQC", threshold=0.05)

    assert result["reconstruction"]["qc_verdict"] == "UNKNOWN"
    assert result["cross_peaks"][0]["confidence"] == "pending_qc"


def test_confidence_derived_from_verdict() -> None:
    """Per-peak `confidence` must be derived from the QC verdict (D-06):
    PASS -> high/medium, PARTIAL -> low. FAIL peaks never reach this code
    path at all (D-07 quarantines before write)."""
    from lucy_ng.nus.bridge import confidence_from_verdict

    assert confidence_from_verdict(QcVerdict.PASS) in {"high", "medium"}
    assert confidence_from_verdict(QcVerdict.PARTIAL) == "low"


def test_confidence_from_verdict_rejects_fail() -> None:
    """FAIL peaks are never consumable -- `confidence_from_verdict()` must
    not silently return a confidence value for a verdict that should never
    have reached the bridge in the first place (D-07)."""
    from lucy_ng.nus.bridge import confidence_from_verdict

    with pytest.raises(ValueError):
        confidence_from_verdict(QcVerdict.FAIL)


def test_bridge_peak_pick_confidence_matches_verdict_pass() -> None:
    """Every cross-peak's `confidence` reflects a PASS verdict end-to-end
    through `bridge_peak_pick()`, not just the standalone mapping function."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _hsqc_spectrum_with_one_peak()
    result = bridge_peak_pick(
        spectrum, experiment="HSQC", threshold=0.05, qc_report=_pass_report()
    )
    assert all(p["confidence"] == "high" for p in result["cross_peaks"])


def test_bridge_peak_pick_confidence_matches_verdict_partial() -> None:
    """Every cross-peak's `confidence` reflects a PARTIAL verdict end-to-end
    through `bridge_peak_pick()` -- replacing the old blanket "low"."""
    from lucy_ng.nus.bridge import bridge_peak_pick

    spectrum = _hsqc_spectrum_with_one_peak()
    result = bridge_peak_pick(
        spectrum, experiment="HSQC", threshold=0.05, qc_report=_partial_report()
    )
    assert all(p["confidence"] == "low" for p in result["cross_peaks"])
