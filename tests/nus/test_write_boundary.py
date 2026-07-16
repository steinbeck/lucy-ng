"""QC-03/D-07 stubs: the pipeline write/quarantine boundary.

RED-by-skip (Wave 0, Phase 99 Plan 01): `lucy_ng.nus.qc` does not exist yet
-- ships in Plan 02; the write-boundary enforcement itself lives in
`cli/nus.py::pipeline` (Plan 04, per RESEARCH.md Open Question 1's
resolution: `nus/qc.py` stays pure/verdict-only, branching lives in the
thin CLI command). D-07: `lucy nus pipeline` writes productive
`analysis/nmr_peaks/*.json` only when QC verdict is PASS or PARTIAL; on
FAIL, nothing is written to the consumable location -- output goes to a
quarantine/diagnostic path instead, and the command exits non-zero. This
extends the FIX-10 constraint-hardness-guard spirit to reconstruction-
derived peaks (QC-03) without touching `case.md`.

Implementing plan: Plan 04 (`cli/nus.py::pipeline` write/quarantine
branching over Plan 02's `QcReport`).
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 04")
def test_fail_verdict_quarantines_and_exits_nonzero(tmp_path) -> None:
    """On a FAIL verdict, `pipeline` must write nothing to
    `analysis/nmr_peaks/` and must exit non-zero -- productive peaks never
    reach the location CASE globs (D-07's fail-loud-at-creation-time
    barrier, extending FIX-10's spirit).

    Implementing plan: Plan 04 (`cli/nus.py::pipeline`, D-07 FAIL branch).
    """
    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(tmp_path)])
    assert result.exit_code != 0
    assert not (tmp_path / "analysis" / "nmr_peaks").exists()


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 04")
def test_pass_writes_consumable_peaks(tmp_path) -> None:
    """On a PASS verdict, `pipeline` must write the peak JSON to
    `analysis/nmr_peaks/*.json` with the D-05 metadata block and D-06
    high/medium per-peak confidence.

    Implementing plan: Plan 04 (`cli/nus.py::pipeline`, D-07 PASS branch).
    """
    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "analysis" / "nmr_peaks").exists()


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 04")
def test_partial_writes_with_warning(tmp_path) -> None:
    """On a PARTIAL verdict, `pipeline` must still write the peak JSON
    (D-01: only FAIL blocks) but the `partial` verdict + violated-checks
    list must be surfaced in the D-05 metadata block so CASE agents can see
    it, with D-06 low per-peak confidence.

    Implementing plan: Plan 04 (`cli/nus.py::pipeline`, D-07 PARTIAL branch).
    """
    import json

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(tmp_path)])
    assert result.exit_code == 0
    hsqc_path = next((tmp_path / "analysis" / "nmr_peaks").glob("HSQC_*.json"))
    data = json.loads(hsqc_path.read_text())
    assert data["reconstruction"]["verdict"] == "PARTIAL"
