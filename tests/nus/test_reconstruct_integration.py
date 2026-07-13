"""Manual-Only real end-to-end reconstruction integration test (D-04).

A single `@pytest.mark.skipif`-guarded test that drives the ACTUAL
bruk2pipe -> nusExpand.tcl -> SMILE chain against the external C20H32O2 data
path (not copied into the repo -- large `ser` binaries stay out of version
control per D-04). This test is expected to SKIP (not fail) in CI and on
any dev machine without NMRPipe+SMILE installed or without the external
data path present -- that is correct, not a coverage gap. Actual
reconstruction-QUALITY judgement (fabricated peaks / t1-ridges) is the
Phase-99 QC gate and Phase-100 Sec.8 validation, NOT this test.

The external data path defaults to this project's own C20H32O2 test
dataset but is overridable via the `LUCY_NUS_TEST_DATA` environment
variable so the test remains meaningful on any machine with a different
external-data layout.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_DEFAULT_EXTERNAL_DATA = Path(
    "/Users/steinbeck/Dropbox/develop/data/nmrdata"
    "/active-lucy-ng-testprojects/C20H32O2"
)

_EXTERNAL_DATA = Path(os.environ.get("LUCY_NUS_TEST_DATA", str(_DEFAULT_EXTERNAL_DATA)))


def _backend_available() -> bool:
    try:
        from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend
    except ImportError:
        return False
    return NmrPipeSmileBackend.is_available()


@pytest.mark.skipif(
    not _backend_available() or not _EXTERNAL_DATA.exists(),
    reason=(
        "NMRPipe+SMILE backend or external C20H32O2 data (LUCY_NUS_TEST_DATA) "
        "not available -- this is a Manual-Only verification, correct to skip "
        "in CI and on dev machines without NMRPipe (D-04)."
    ),
)
def test_reconstruct_exp3_hsqc_end_to_end(tmp_path: Path) -> None:
    """Real end-to-end reconstruction of exp3 (HSQC, echo-antiecho, 25%
    density) against the external C20H32O2 data: `NusRunner.reconstruct()`
    drives the actual bruk2pipe/nusExpand.tcl/SMILE binaries and produces a
    processed, ppm-calibrated 2D spectrum.

    Implementing plan: Plan 05 (`nus/runner.py::NusRunner.reconstruct`).
    Quality judgement (ridges/fabricated peaks) belongs to Phase 99/100,
    not this test -- this test only asserts the pipeline completes and
    produces the expected, non-empty output artefact.
    """
    from lucy_ng.nus.runner import NusRunner

    expdir = _EXTERNAL_DATA / "3"
    runner = NusRunner()

    result = runner.reconstruct(expdir)

    assert result.success is True
    assert result.processed_spectrum is not None
    processed_path = Path(result.processed_spectrum)
    assert processed_path.exists()
    assert processed_path.stat().st_size > 0
