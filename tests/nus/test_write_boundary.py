"""QC-03/D-07: the pipeline write/quarantine boundary (Phase 99 Plan 04).

`lucy nus pipeline` writes productive `analysis/nmr_peaks/*.json` only when
the QC verdict is PASS or PARTIAL; on FAIL, nothing reaches the consumable
location -- output goes to `<stage_dir>/qc_failed/` instead, and the
command exits non-zero. This extends the FIX-10 constraint-hardness-guard
spirit to reconstruction-derived peaks (QC-03) without touching `case.md`.

Note on Wave 0 (Plan 01) provenance: the original RED-by-skip stubs invoked
`pipeline` against a bare `tmp_path` with no mocked reconstruction/QC
seams -- unrunnable as literally written (no Bruker `acqus`/`acqu2s`, no
NMRPipe+SMILE binary). This file replaces those placeholders with the real
`cli/nus.py::pipeline` write-boundary logic exercised via the
`mock_pipeline_stages` fixture (conftest.py): `NusRunner.reconstruct()`,
`read_nus_params()`, and `build_spectrum2d()` are mocked (no external
binary / real Bruker data needed); `bridge_peak_pick()` and
`write_peak_json()` run for real against a deterministic synthetic
`Spectrum2D`; `run_qc_checks()` is mocked to a caller-chosen verdict
(QC-01/QC-02's check algorithms are already proven real in Plan 02's
`test_qc_checks.py`/`test_qc_regression.py` -- this file's own scope is the
write/quarantine boundary, not a second proof of the check algorithms).
"""

from __future__ import annotations

import json


def test_fail_verdict_quarantines_and_exits_nonzero(tmp_path, mock_pipeline_stages) -> None:
    """On a FAIL verdict, `pipeline` must write nothing to
    `analysis/nmr_peaks/` and must exit non-zero -- productive peaks never
    reach the location CASE globs (D-07's fail-loud-at-creation-time
    barrier, extending FIX-10's spirit). The quarantine directory carries
    the verdict-annotated payload + the QC report for forensics.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    expdir = tmp_path / "expdir"
    expdir.mkdir()
    report = mock_pipeline_stages(verdict="FAIL", violated=["quaternary_exclusion"])

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(expdir)])

    assert result.exit_code != 0, result.output
    assert not (expdir / "analysis" / "nmr_peaks").exists()

    quarantine_dir = (
        expdir / "analysis" / "nus_recon" / expdir.name / "qc_failed"
    )
    assert quarantine_dir.exists()
    payload_path = quarantine_dir / "HSQC.json"
    assert payload_path.exists()
    payload = json.loads(payload_path.read_text())
    assert payload["reconstruction"]["qc_verdict"] == report.verdict.value == "FAIL"
    assert payload["reconstruction"]["violated_checks"] == ["quaternary_exclusion"]

    report_path = quarantine_dir / "qc_report.json"
    assert report_path.exists()
    report_data = json.loads(report_path.read_text())
    assert report_data["verdict"] == "FAIL"


def test_pass_writes_consumable_peaks(tmp_path, mock_pipeline_stages) -> None:
    """On a PASS verdict, `pipeline` must write the peak JSON to
    `analysis/nmr_peaks/*.json` with the D-05 metadata block carrying the
    real computed verdict and D-06 "high" per-peak confidence.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    expdir = tmp_path / "expdir"
    expdir.mkdir()
    mock_pipeline_stages(verdict="PASS")

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(expdir)])

    assert result.exit_code == 0, result.output
    nmr_peaks_dir = expdir / "analysis" / "nmr_peaks"
    assert nmr_peaks_dir.exists()
    payload_path = nmr_peaks_dir / "HSQC.json"
    assert payload_path.exists()
    payload = json.loads(payload_path.read_text())

    assert payload["reconstruction"]["qc_verdict"] == "PASS"
    assert payload["cross_peaks"], "expected at least one written cross-peak"
    assert all(peak["confidence"] == "high" for peak in payload["cross_peaks"])

    quarantine_dir = expdir / "analysis" / "nus_recon" / expdir.name / "qc_failed"
    assert not quarantine_dir.exists()


def test_partial_writes_with_warning(tmp_path, mock_pipeline_stages) -> None:
    """On a PARTIAL verdict, `pipeline` must still write the peak JSON
    (D-01: only FAIL blocks) but the `PARTIAL` verdict + violated-checks
    list must be surfaced in the D-05 metadata block, with D-06 "low"
    per-peak confidence -- proving the FINAL verdict-annotated payload was
    written, not the step-3 staged verdict-less one.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    expdir = tmp_path / "expdir"
    expdir.mkdir()
    mock_pipeline_stages(verdict="PARTIAL", violated=["edited_sign_consistency"])

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(expdir)])

    assert result.exit_code == 0, result.output
    hsqc_path = next((expdir / "analysis" / "nmr_peaks").glob("HSQC.json"))
    data = json.loads(hsqc_path.read_text())
    assert data["reconstruction"]["qc_verdict"] == "PARTIAL"
    assert data["reconstruction"]["violated_checks"] == ["edited_sign_consistency"]
    assert data["cross_peaks"]
    assert all(peak["confidence"] == "low" for peak in data["cross_peaks"])

    # A PARTIAL verdict must surface a warning to the user (D-01).
    assert "PARTIAL" in result.output


def test_fail_never_writes_staged_verdict_less_payload_to_consumable(
    tmp_path, mock_pipeline_stages
) -> None:
    """The staged (verdict-less, `qc_verdict="UNKNOWN"`) payload produced
    to feed `run_qc_checks()` must never leak into `analysis/nmr_peaks/`
    on any verdict -- only the staged dir under `<stage_dir>/staged/`
    should ever carry the placeholder metadata.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    expdir = tmp_path / "expdir"
    expdir.mkdir()
    mock_pipeline_stages(verdict="FAIL", violated=["signal_to_ridge"])

    runner = CliRunner()
    runner.invoke(nus, ["pipeline", str(expdir)])

    staged_path = (
        expdir / "analysis" / "nus_recon" / expdir.name / "staged" / "HSQC.json"
    )
    assert staged_path.exists()
    staged_payload = json.loads(staged_path.read_text())
    assert staged_payload["reconstruction"]["qc_verdict"] == "UNKNOWN"

    assert not (expdir / "analysis" / "nmr_peaks").exists()
