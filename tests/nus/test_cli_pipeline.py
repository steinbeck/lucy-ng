"""PICK-02/D-08: `lucy nus qc` + `lucy nus pipeline` CLI commands (Phase 99 Plan 04).

`lucy nus qc <peaks-dir>` is independently runnable against arbitrary
peak-list directories (needed for QC-02's FAIL/PASS proof); `lucy nus
pipeline <expdir>` orchestrates params -> schedule -> reconstruct ->
process -> peak-pick -> QC end-to-end and calls the same qc code
internally. Every `lucy nus` subcommand supports `--format json`.

Note on Wave 0 (Plan 01) provenance: the original RED-by-skip stubs
invoked `pipeline` against a bare `tmp_path` with no mocked
reconstruction/QC seams. This file replaces those placeholders with real
assertions against `lucy nus qc`'s real `run_qc_checks()` call (the
already-committed `known_bad_peaks_dir`/`clean_peaks_dir` fixtures, Plan
01/02). Task 1 of this plan ships `qc`; Task 2 adds the `pipeline`
command tests (this file grows in the next commit).
"""

from __future__ import annotations

import json


def test_qc_command_json_format(known_bad_peaks_dir) -> None:
    """`lucy nus qc <peaks-dir> --format json` must emit a JSON-parseable
    `QcReport.to_dict()` payload (D-08's independently-runnable contract)
    and exit non-zero on a FAIL verdict.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(known_bad_peaks_dir), "--format", "json"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "FAIL"


def test_qc_command_passes_on_clean_fixture(clean_peaks_dir) -> None:
    """`lucy nus qc <peaks-dir> --format json` exits 0 and reports PASS on
    the hand-authored synthetic-clean fixture -- the QC-02 PASS-side proof
    exercised via the CLI, not just `run_qc_checks()` directly.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(clean_peaks_dir), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["verdict"] == "PASS"


def test_qc_command_text_format_reports_verdict(known_bad_peaks_dir) -> None:
    """The default text format prints the verdict and violated check names."""
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(known_bad_peaks_dir)])
    assert result.exit_code != 0
    assert "FAIL" in result.output
    assert "Violated checks:" in result.output


def test_qc_command_help_lists_threshold_flags() -> None:
    """`lucy nus qc --help` lists the D-04 threshold-override flags."""
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", "--help"])
    assert result.exit_code == 0
    assert "--ridge-fail" in result.output
    assert "--coverage-floor" in result.output
    assert "--c13-tol" in result.output
    assert "--h1-tol" in result.output
    assert "--format" in result.output


def test_qc_command_threshold_override_changes_verdict(known_bad_peaks_dir) -> None:
    """An explicit `--coverage-floor 0.0` override must thread through to
    `QcConfig` (D-04) -- loosening the HSQC-coverage floor should not, by
    itself, flip the known-bad fixture's independently-critical
    quaternary-exclusion/signal-to-ridge violations, but it does change
    the hsqc_coverage check's own `passed` value in the report.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(
        nus,
        ["qc", str(known_bad_peaks_dir), "--coverage-floor", "0.0", "--format", "json"],
    )
    payload = json.loads(result.output)
    coverage_check = next(c for c in payload["checks"] if c["name"] == "hsqc_coverage")
    assert coverage_check["passed"] is True
    assert coverage_check["threshold"] == 0.0
    # Still FAIL overall -- quaternary_exclusion/signal_to_ridge remain critical violations.
    assert payload["verdict"] == "FAIL"
