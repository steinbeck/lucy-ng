"""RECON-05 tests: `lucy nus reconstruct <expdir>` CLI knob-flag surface.

Implemented in Plan 06 (`cli/nus.py::reconstruct` command). Exposes
lucy-ng's own descriptive flag names (`--iterations`/`--threshold`/
`--virtual-echo`/`--no-virtual-echo`, plus phase-override flags) that map
internally to SMILE's `-maxIter`/`-thresh`/`-nSigma`/`-EA` -- per
RESEARCH.md's Alternatives Considered recommendation (insulates the CLI
contract from SMILE's own flag-name churn).
"""

from __future__ import annotations

import shutil
from pathlib import Path


def _copy_fixture(nus_fixture_dir, tmp_path: Path, name: str) -> Path:
    """Copy a read-only tests/fixtures/nus/<name> dir into tmp_path.

    `NusRunner._stage_dir()` writes `analysis/nus_recon/<expN>/` under the
    resolved `expdir` (D-03) -- copying into `tmp_path` first keeps this
    test's stage-dir side effects contained to pytest's own tmp dir rather
    than polluting the tracked `tests/fixtures/nus/` tree (mirrors
    `tests/nus/test_reconstruct_orchestration.py::_copy_fixture`).
    """
    src = nus_fixture_dir(name)
    dst = tmp_path / name
    shutil.copytree(src, dst)
    return dst


def test_reconstruct_help_lists_knob_flags() -> None:
    """`lucy nus reconstruct --help` must list the RECON-05 knob flags:
    iteration-count upper bound, threshold, and the virtual-echo toggle
    (plus phase-override flags per D-02).
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["reconstruct", "--help"])

    assert result.exit_code == 0
    assert "--iterations" in result.output
    assert "--threshold" in result.output
    assert "--virtual-echo" in result.output
    assert "--no-virtual-echo" in result.output
    assert "--f2-p0" in result.output
    assert "--f2-p1" in result.output
    assert "--f1-p0" in result.output
    assert "--f1-p1" in result.output
    assert "--format" in result.output


def test_flags_thread_through_to_smile_invocation(
    mock_run_stage, nus_fixture_dir, tmp_path, monkeypatch
) -> None:
    """CLI flag values (`--iterations`, `--threshold`, `--no-virtual-echo`)
    must thread through, unmodified, to the underlying
    `NusRunner.reconstruct()` call and end up in SMILE's argv -- never
    silently dropped or overridden by a hard-coded default once explicitly
    passed by the caller.
    """
    from click.testing import CliRunner

    from lucy_ng.cli.nus import nus
    from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend

    # Neutralize the PORT-01 preflight gate (this dev machine has no real
    # NMRPipe+SMILE on PATH) so the CLI's real NusRunner().reconstruct(...)
    # passes the gate and still reaches run_stage/SMILE dispatch.
    monkeypatch.setattr(
        NmrPipeSmileBackend,
        "diagnose",
        classmethod(
            lambda cls: {
                "status": "available",
                "missing_tools": [],
                "smile_available": True,
                "hint": "",
                "platform": {
                    "critical_platform_issues": [],
                    "soft_platform_warnings": [],
                },
            }
        ),
    )

    runner = CliRunner()
    expdir = _copy_fixture(nus_fixture_dir, tmp_path, "exp3_hsqc")

    result = runner.invoke(
        nus,
        [
            "reconstruct",
            str(expdir),
            "--iterations",
            "750",
            "--threshold",
            "0.9",
            "--no-virtual-echo",
        ],
    )

    assert result.exit_code == 0, result.output
    smile_argv = next(
        call[1] for call in mock_run_stage["calls"] if call[0] == "SMILE"
    )
    argv_str = " ".join(str(a) for a in smile_argv)
    assert "750" in argv_str
    assert "0.9" in argv_str
    # exp3_hsqc is echo-antiecho (FnMODE=6, smile_ea=True) -- with
    # --no-virtual-echo passed, -EA must NOT appear in the SMILE argv.
    assert "-EA" not in smile_argv
