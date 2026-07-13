"""RECON-05 stubs: `lucy nus reconstruct <expdir>` CLI knob-flag surface.

Implemented in Plan 06 (`cli/nus.py::reconstruct` command). Exposes
lucy-ng's own descriptive flag names (`--max-iter`/`--threshold`/
`--virtual-echo`/`--no-virtual-echo`, plus phase-override flags) that map
internally to SMILE's `-maxIter`/`-thresh`/`-nSigma`/`-EA` -- per
RESEARCH.md's Alternatives Considered recommendation (insulates the CLI
contract from SMILE's own flag-name churn).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 06")
def test_reconstruct_help_lists_knob_flags() -> None:
    """`lucy nus reconstruct --help` must list the RECON-05 knob flags:
    iteration-count upper bound, threshold, and the virtual-echo toggle
    (plus phase-override flags per D-02).

    Implementing plan: Plan 06 (`cli/nus.py::reconstruct`).
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["reconstruct", "--help"])

    assert result.exit_code == 0
    assert "--max-iter" in result.output
    assert "--threshold" in result.output
    assert "--virtual-echo" in result.output


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 06")
def test_flags_thread_through_to_smile_invocation(mock_run_stage, nus_fixture_dir) -> None:
    """CLI flag values (`--max-iter`, `--threshold`, `--no-virtual-echo`)
    must thread through, unmodified, to the underlying
    `NusRunner.reconstruct()` call and end up in SMILE's argv -- never
    silently dropped or overridden by a hard-coded default once explicitly
    passed by the caller.

    Implementing plan: Plan 06 (`cli/nus.py::reconstruct`).
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    expdir = str(nus_fixture_dir("exp3_hsqc"))

    result = runner.invoke(
        nus,
        [
            "reconstruct",
            expdir,
            "--max-iter",
            "750",
            "--threshold",
            "0.9",
            "--no-virtual-echo",
        ],
    )

    assert result.exit_code == 0
    smile_argv = next(
        call[1] for call in mock_run_stage["calls"] if call[0] == "smile"
    )
    argv_str = " ".join(str(a) for a in smile_argv)
    assert "750" in argv_str
    assert "0.9" in argv_str
