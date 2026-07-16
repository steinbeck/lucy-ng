"""QC-01: the six individual QC check functions.

Implemented in Plan 02 (`lucy_ng.nus.qc`). One class per check (per D-02's
critical/soft split), each documenting the intended callable name.

Critical checks (D-02, any violation -> FAIL): quaternary exclusion, ppm
calibration, signal-to-ridge, HSQC coverage.
Soft checks (D-02, violation -> PARTIAL): edited-sign self-consistency,
COSY diagonal symmetry.
"""

from __future__ import annotations


class TestQuaternaryExclusion:
    """Critical check: no HSQC 1-bond correlation within tolerance of a
    known-quaternary shift (RESEARCH.md Pitfall 3; the primary defense
    against the known-bad HSQC's 4/27 false quaternary hits).

    Intended callable: `lucy_ng.nus.qc.quaternary_exclusion(hsqc_peaks,
    known_quaternary_shifts, tol=0.5) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.quaternary_exclusion`)."""
        import json

        from lucy_ng.nus.qc import quaternary_exclusion

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = quaternary_exclusion(peaks, [142.00, 135.86, 79.35, 36.23, 37.86])
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.quaternary_exclusion`)."""
        import json

        from lucy_ng.nus.qc import quaternary_exclusion

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = quaternary_exclusion(peaks, [142.00, 135.86, 79.35, 36.23, 37.86])
        assert result.passed is False


class TestPpmCalibration:
    """Critical check: reuse `nus/postprocess.py::check_calibration()`
    against `GUIDE_S10_C13` (Don't Hand-Roll -- do not reimplement).

    Intended callable: `lucy_ng.nus.qc.qc_check_ppm_calibration(hsqc_c13_shifts,
    tol=DEFAULT_CALIBRATION_TOL) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.qc_check_ppm_calibration`)."""
        import json

        from lucy_ng.nus.qc import qc_check_ppm_calibration

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        shifts = [p["c13_ppm"] for p in peaks]
        result = qc_check_ppm_calibration(shifts)
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.qc_check_ppm_calibration`)."""
        import json

        from lucy_ng.nus.qc import qc_check_ppm_calibration

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        shifts = [p["c13_ppm"] + 5.0 for p in peaks]  # simulate a gross offset
        result = qc_check_ppm_calibration(shifts)
        assert result.passed is False


class TestSignalToRidge:
    """Critical check: peak-list-only ridge_fraction() clustering (Pattern
    3, RESEARCH.md Pitfall 5). Known-bad COSY: 7/7 peaks share h1a=5.32
    (ridge_fraction == 1.0). Recommended starting FAIL threshold 0.5.

    Intended callable: `lucy_ng.nus.qc.ridge_fraction(peaks, axis_key,
    tol=0.05) -> float`, wrapped by `lucy_ng.nus.qc.signal_to_ridge(peaks,
    axis_key, threshold=0.5) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.signal_to_ridge`)."""
        import json

        from lucy_ng.nus.qc import signal_to_ridge

        peaks = json.loads((clean_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = signal_to_ridge(peaks, "h1a_ppm")
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.signal_to_ridge`)."""
        import json

        from lucy_ng.nus.qc import signal_to_ridge

        peaks = json.loads((known_bad_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = signal_to_ridge(peaks, "h1a_ppm")
        assert result.passed is False


class TestHsqcCoverage:
    """Critical check: >= floor fraction of trusted protonated carbons show
    >=1 HSQC correlation (RESEARCH.md Pitfall 3 -- does NOT catch the
    known-bad fixture alone, coverage is 100% there; quaternary-exclusion
    is the primary defense for that failure mode). Recommended floor 0.8.

    Intended callable: `lucy_ng.nus.qc.hsqc_coverage(hsqc_peaks,
    protonated_reference_shifts, floor=0.8) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.hsqc_coverage`)."""
        import json

        from lucy_ng.nus.qc import hsqc_coverage

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        protonated = [
            69.06, 67.06, 51.63, 37.19, 35.23, 34.21, 33.67,
            30.66, 29.77, 27.93, 27.15, 25.96, 23.43, 22.63, 21.78,
        ]
        result = hsqc_coverage(peaks, protonated)
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.hsqc_coverage`)."""
        import json

        from lucy_ng.nus.qc import hsqc_coverage

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        # Force a deliberately incomplete reference list to exercise the
        # violation path (the known-bad fixture alone is 100% coverage).
        protonated = [69.06, 67.06, 51.63, 999.99, 998.88, 997.77]
        result = hsqc_coverage(peaks, protonated, floor=0.8)
        assert result.passed is False


class TestEditedSignConsistency:
    """Soft check: every carbon with >1 HSQC peak must share ONE
    multiplicity_hint (RESEARCH.md Pitfall 4 / Code Examples). Known-bad
    HSQC: violations at 22.63, 23.43, 67.06 (3 of 7 multi-peak carbons).

    Intended callable: `lucy_ng.nus.qc.edited_sign_self_consistent(hsqc_peaks,
    tol=0.5) -> tuple[bool, list[float]]`, wrapped by
    `lucy_ng.nus.qc.edited_sign_consistency(hsqc_peaks) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.edited_sign_consistency`)."""
        import json

        from lucy_ng.nus.qc import edited_sign_consistency

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = edited_sign_consistency(peaks)
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.edited_sign_consistency`)."""
        import json

        from lucy_ng.nus.qc import edited_sign_consistency

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = edited_sign_consistency(peaks)
        assert result.passed is False


class TestCosyDiagonalSymmetry:
    """Soft check: for every (h1a, h1b) COSY cross-peak, a mirror (h1b, h1a)
    should also be present within tolerance -- known-bad COSY is a
    textbook one-sided t1-ridge (all 7 share h1a=5.32, no diagonal
    symmetry), synthetic-clean COSY is diagonal-symmetric by construction.

    Intended callable: `lucy_ng.nus.qc.cosy_diagonal_symmetry(cosy_peaks,
    tol=0.05) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.cosy_diagonal_symmetry`)."""
        import json

        from lucy_ng.nus.qc import cosy_diagonal_symmetry

        peaks = json.loads((clean_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = cosy_diagonal_symmetry(peaks)
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`lucy_ng.nus.qc.cosy_diagonal_symmetry`)."""
        import json

        from lucy_ng.nus.qc import cosy_diagonal_symmetry

        peaks = json.loads((known_bad_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = cosy_diagonal_symmetry(peaks)
        assert result.passed is False
