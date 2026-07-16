"""PICK-02/D-08 stubs: `lucy nus qc` + `lucy nus pipeline` CLI commands.

RED-by-skip (Wave 0, Phase 99 Plan 01): `lucy_ng.nus.qc` does not exist yet
-- ships in Plan 02; the `qc`/`pipeline` CLI commands themselves ship in
Plan 04 (`cli/nus.py`, deferred-import convention preserved -- see
99-PATTERNS.md's import-safe CLI section). D-08: `lucy nus qc <peaks-dir>`
is independently runnable against arbitrary peak-list directories (needed
for QC-02's FAIL/PASS proof); `lucy nus pipeline <expdir>` orchestrates
params -> schedule -> reconstruct -> process -> peak-pick -> QC end-to-end
and calls the same qc code internally. Every `lucy nus` subcommand supports
`--format json`.

Implementing plan: Plan 04 (`cli/nus.py::qc`, `cli/nus.py::pipeline`).
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 04")
def test_qc_command_json_format(known_bad_peaks_dir) -> None:
    """`lucy nus qc <peaks-dir> --format json` must emit a JSON-parseable
    `QcReport.to_dict()` payload (D-08's independently-runnable contract)
    and exit non-zero on a FAIL verdict.

    Implementing plan: Plan 04 (`cli/nus.py::qc`).
    """
    import json

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(known_bad_peaks_dir), "--format", "json"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "FAIL"


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 04")
def test_pipeline_command_wires_stages(tmp_path) -> None:
    """`lucy nus pipeline <expdir>` must wire
    params -> schedule -> reconstruct -> process -> peak-pick -> QC in
    strict order, reusing `NusRunner.reconstruct()` (Phase 98, unchanged)
    and the same `run_qc_checks()` the standalone `qc` command calls.

    Implementing plan: Plan 04 (`cli/nus.py::pipeline`).
    """
    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(tmp_path)])
    assert result.exit_code in (0, 1)


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 04")
def test_all_nus_subcommands_support_format_json() -> None:
    """Every `lucy nus` subcommand -- including the new `qc`/`pipeline`
    (and optional `peak-pick`) -- must support `--format json`, matching
    the existing `check`/`params`/`schedule`/`reconstruct` convention.

    Implementing plan: Plan 04 (`cli/nus.py` --format json coverage).
    """
    from lucy_ng.cli.nus import nus

    for command_name in ("qc", "pipeline"):
        command = nus.commands[command_name]
        assert "format" in [p.name for p in command.params]
