"""QC-02 stubs: the discrimination regression floor.

RED-by-skip (Wave 0, Phase 99 Plan 01): `lucy_ng.nus.qc` does not exist yet
-- ships in Plan 02. This is the calibration anchor for the whole QC gate
(D-02/D-04): the real known-bad home-IST HSQC/HMBC/COSY lists MUST verdict
FAIL (via the critical quaternary-exclusion + signal-to-ridge checks); the
hand-authored synthetic-clean set MUST verdict PASS (Plan 01's own
load-bearing fixture -- no real clean reconstruction exists until Phase
100, so this synthetic fixture is the only proof available in this phase).

Implementing plan: Plan 02 (`lucy_ng.nus.qc.run_qc_checks`).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_known_bad_dir_fails(known_bad_peaks_dir) -> None:
    """`run_qc_checks(known_bad_peaks_dir)` must verdict FAIL -- the known
    quaternary-exclusion (4/27 peaks at confirmed-quaternary shifts) and
    signal-to-ridge (COSY 7/7 sharing h1a=5.32) critical violations are
    both present in this fixture (RESEARCH.md Common Pitfalls #3/#5).

    Implementing plan: Plan 02 (`lucy_ng.nus.qc.run_qc_checks`).
    """
    from lucy_ng.nus.qc import run_qc_checks

    from lucy_ng.models.nus import QcVerdict

    report = run_qc_checks(known_bad_peaks_dir)
    assert report.verdict == QcVerdict.FAIL


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_synthetic_clean_dir_passes(clean_peaks_dir) -> None:
    """`run_qc_checks(clean_peaks_dir)` must verdict PASS -- the
    hand-authored synthetic-clean fixture has zero quaternary-shift HSQC
    hits, no ridge, self-consistent edited signs, and diagonal-symmetric
    COSY (Plan 01 Task 2 acceptance criteria).

    Implementing plan: Plan 02 (`lucy_ng.nus.qc.run_qc_checks`).
    """
    from lucy_ng.nus.qc import run_qc_checks

    from lucy_ng.models.nus import QcVerdict

    report = run_qc_checks(clean_peaks_dir)
    assert report.verdict == QcVerdict.PASS
