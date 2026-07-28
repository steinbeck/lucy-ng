"""CLI-surface tests for `lucy jcamp` (Phase 102, Plan 03), extended by
Plan 04 with fixture-backed end-to-end and QC-discrimination suites.

Covers registration, help text, D-01's "one command, no subcommands"
invariant, argument-validation error paths, and import safety.

Plan 04 additions -- proof-level honesty (102-RESEARCH.md Pitfall 6):

* `TestJcampEndToEnd` is FIXTURE-COVERED on real committed (trimmed) data --
  no test-double substitution anywhere in this class. It proves the CLI's
  read -> pick -> QC -> write chain actually runs over the six committed
  JCAMP fixtures, that NOESY is skipped non-fatally (D-06), that the
  edited-HSQC sign survives the round-trip, and that the QC verdict is
  embedded in the peak JSON. It does NOT prove the verdict is chemically
  correct or that peak counts are plausible on the full 2048x2048 real
  matrix -- those claims require the real, external, uncommitted
  `C20H32O2-jcamp` dataset and are Phase 103 / JVAL's job (D-05 boundary).
* `TestJcampQcDiscrimination` is MOCK-COVERED: the peaks staged into the QC
  gate are real, fixture-derived cross-peaks, but the `QcReport` verdict
  itself is injected via a test double over `lucy_ng.nus.qc.run_qc_checks`
  so the CLI's own PASS/PARTIAL/FAIL branch logic can be exercised without
  needing a genuinely Sec.8-quality spectrum (which the 16-row trimmed
  fixtures cannot provide -- see `test_observed_trimmed_fixture_verdict`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner

from lucy_ng.cli.jcamp import jcamp

FIXTURES = Path(__file__).parent / "fixtures" / "jcamp"
REAL_13C_FIXTURE = FIXTURES / "C20H32O2_13C.dx"

#: All six committed JCAMP fixtures (Phase 101 + 102-01), mirroring the real
#: 6-file `C20H32O2-jcamp` dataset in miniature.
ALL_FIXTURE_NAMES = (
    "C20H32O2_HSQC_trimmed.dx",
    "C20H32O2_HMBC_trimmed.dx",
    "C20H32O2_COSY_trimmed.dx",
    "C20H32O2_NOESY_trimmed.dx",
    "C20H32O2_1H.dx",
    "C20H32O2_13C.dx",
)


def _copy_fixtures(tmp_path: Path, names: tuple[str, ...] = ALL_FIXTURE_NAMES) -> Path:
    """Copy the named committed `.dx` fixtures into `tmp_path`.

    ALWAYS copy, never invoke the CLI against the tracked fixture directory
    directly -- the command creates `analysis/nmr_peaks/` and
    `analysis/jcamp_ingest/` side effects that must never pollute the
    committed `tests/fixtures/jcamp/` tree (the same `_copy_fixture`
    discipline Phase 98 Plan 06 established).
    """
    for name in names:
        src = FIXTURES / name
        assert src.exists(), f"missing fixture: {src}"
        (tmp_path / name).write_bytes(src.read_bytes())
    return tmp_path


def _find_json(root: Path, filename: str) -> Path:
    """Locate `filename` under `root`'s CONSUMABLE (`nmr_peaks/`) or
    QUARANTINE (`jcamp_ingest/qc_failed/`) location -- never the staged
    (verdict-less) directory, which also carries a same-named file with a
    `qc_verdict: "UNKNOWN"` placeholder (mirrors
    `tests/nus/test_write_boundary.py`'s staged-vs-consumable distinction).
    """
    matches = [p for p in root.rglob(filename) if "staged" not in p.parts]
    assert matches, f"{filename} not found under {root} (outside any staged/ directory)"
    assert len(matches) == 1, f"expected exactly one {filename} under {root}, found {matches}"
    return matches[0]


class TestJcampCliSurface:
    """Registration, help text, and argument-validation error paths."""

    def test_help_exits_zero_and_documents_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, ["--help"])
        assert result.exit_code == 0, result.output
        assert "--out" in result.output
        assert "--snr-floor" in result.output
        assert "--threshold" in result.output
        assert "--format" in result.output
        assert "lucy nus qc" in result.output

    def test_registered_on_top_level_group(self) -> None:
        from lucy_ng.cli.main import cli

        assert "jcamp" in cli.commands
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0, result.output
        assert "jcamp" in result.output

    def test_no_qc_subcommand_exists(self) -> None:
        """D-01: `lucy jcamp` is a single command, not a group with subcommands."""
        assert not isinstance(jcamp, click.Group)
        runner = CliRunner()
        result = runner.invoke(jcamp, ["qc", "/tmp"])
        assert result.exit_code != 0

    def test_missing_argument_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, [])
        assert result.exit_code != 0

    def test_nonexistent_path_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, ["/no/such/jcamp/dir"])
        assert result.exit_code != 0

    def test_empty_directory_exits_nonzero(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, [str(tmp_path)])
        assert result.exit_code != 0
        assert tmp_path.name in result.output or str(tmp_path) in result.output
        assert not (tmp_path / "analysis").exists()

    def test_directory_mixed_with_files_rejected(self, tmp_path: Path) -> None:
        assert REAL_13C_FIXTURE.exists(), f"missing fixture: {REAL_13C_FIXTURE}"
        runner = CliRunner()
        result = runner.invoke(jcamp, [str(tmp_path), str(REAL_13C_FIXTURE)])
        assert result.exit_code != 0

    def test_supported_sets_stay_in_sync_with_the_reused_subsystems(self) -> None:
        """WR-02: `SUPPORTED_2D`/`SUPPORTED_1D` are deliberate hand-copies
        (not imports) of `nus/bridge.py`'s `_VALID_BRIDGE_EXPERIMENTS` and
        `processing/jcamp_1d_bridge.py`'s `_VALID_1D_NUCLEI`. If a future
        phase extends either reused set (e.g. adds TOCSY) without updating
        this command's copy, the new experiment type would silently keep
        routing to the D-06 "skip" path instead of being picked -- this
        test fails loud in CI instead of relying on a human noticing the
        skip warning.
        """
        from lucy_ng.cli.jcamp import SUPPORTED_1D, SUPPORTED_2D
        from lucy_ng.nus.bridge import _VALID_BRIDGE_EXPERIMENTS
        from lucy_ng.processing.jcamp_1d_bridge import _VALID_1D_NUCLEI

        assert set(SUPPORTED_2D) == _VALID_BRIDGE_EXPERIMENTS
        assert set(SUPPORTED_1D) == _VALID_1D_NUCLEI


class TestJcampUnexpectedReadResultType:
    """WR-01 regression: the 2D-branch type-narrowing must fail loud (a
    real exception), not rely on `assert`, which `-O`/`-OO` strips.
    """

    def test_neither_1d_nor_2d_result_raises_type_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _copy_fixtures(tmp_path, names=(REAL_13C_FIXTURE.name,))

        class _NotASpectrum:
            pass

        monkeypatch.setattr(
            "lucy_ng.readers.jcamp.JcampReader.read",
            staticmethod(lambda path: _NotASpectrum()),
        )

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path)])
        assert isinstance(result.exception, TypeError), result.exception
        assert "Unexpected JcampReader.read() result type" in str(result.exception)


class TestJcampImportSafety:
    """Mirrors tests/test_cli_nus.py's TestImportSafety."""

    def test_module_imports_cleanly(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import lucy_ng.cli.jcamp"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"lucy_ng.cli.jcamp failed to import cleanly.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_no_eager_domain_imports(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys, lucy_ng.cli.jcamp; "
                    "assert 'lucy_ng.nus.qc' not in sys.modules; "
                    "assert 'lucy_ng.readers.jcamp' not in sys.modules; "
                    "print('OK')"
                ),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"lucy_ng.cli.jcamp leaked an eager domain import.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestJcampEndToEnd:
    """FIXTURE-COVERED (real committed data, 16 F1 rows per 2D file, whole
    real 1D files) -- no test-double substitution anywhere in this class.

    `CliRunner(mix_stderr=False)` is used throughout (rather than the
    default `mix_stderr=True`) so `json.loads(result.output)` is robust to
    nmrglue's `UserWarning: JCAMP-DX key without value: $RELAX` (emitted via
    `warnings.warn`, not `click.echo`), which Python's default "once per
    call-site" warning filter only shows the FIRST time that exact
    source line fires in a given interpreter session -- an ordering-
    dependent leak into stdout that would otherwise make JSON parsing flaky
    when this test file is run in isolation (verified empirically:
    `warnings.warn` output lands on stderr and is only mixed into
    `result.output` when `mix_stderr=True`).
    """

    def test_directory_run_write_boundary_invariant(self, tmp_path: Path) -> None:
        """Branch-agnostic invariant: whichever verdict the 16-row trimmed
        fixtures happen to produce, the D-07 write boundary must hold
        exactly one way or the other -- never a traceback, never both.
        """
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path)])

        assert result.exception is None or isinstance(result.exception, SystemExit), (
            f"unexpected exception: {result.exception!r}"
        )
        assert result.exit_code in (0, 1), result.output

        nmr_peaks = tmp_path / "analysis" / "nmr_peaks"
        if result.exit_code == 0:
            assert nmr_peaks.exists()
            names = {p.name for p in nmr_peaks.iterdir()}
            assert names == {"HSQC.json", "HMBC.json", "COSY.json", "13C.json", "1H.json"}
        else:
            assert not nmr_peaks.exists()
            quarantine = tmp_path / "analysis" / "jcamp_ingest" / "qc_failed"
            assert quarantine.exists()
            names = {p.name for p in quarantine.iterdir()}
            assert "qc_report.json" in names
            for expected in ("HSQC.json", "HMBC.json", "COSY.json", "13C.json", "1H.json"):
                assert expected in names

        # D-06: NOESY is read but never picked -- no NOESY.json anywhere.
        assert not list((tmp_path / "analysis").rglob("NOESY.json"))

    def test_noesy_is_skipped_not_failed(self, tmp_path: Path) -> None:
        """D-06: NOESY is a non-fatal skip, distinct from a read/pick failure."""
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])
        data = json.loads(result.output)

        noesy_skips = [e for e in data["skipped"] if e["file"] == "C20H32O2_NOESY_trimmed.dx"]
        assert len(noesy_skips) == 1
        assert "NOESY" in noesy_skips[0]["reason"]
        assert data["failed"] == []

    def test_all_six_fixtures_are_read_without_read_failures(self, tmp_path: Path) -> None:
        """Proves all four 2D fixtures (including the two homonuclear ones
        fixed in Plan 01) and both 1D files decoded without raising.
        """
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])
        data = json.loads(result.output)
        assert data["failed"] == []

    def test_edited_hsqc_sign_survives_round_trip(self, tmp_path: Path) -> None:
        """ROADMAP criterion 3, real committed data (not synthetic).

        Measured baseline (2026-07-25, `snr_floor=5.0` default, 16 F1 rows):
        115 cross-peaks, multiplicity_hint distribution {"CH_or_CH3": 70,
        "CH2": 45}, zero ambiguous "CH_or_CH2_or_CH3" entries -- the trimmed
        HSQC fixture has 33 detected negative cross-peaks
        (`detect_multiplicity_edited` == (True, 33)), so the whole spectrum
        is treated as multiplicity-edited and every peak's sign maps
        deterministically to CH2 (negative) or CH_or_CH3 (positive). Assert
        the distribution SHAPE (both hints present, zero ambiguous), not the
        exact 70/45 split, to stay robust to minor picker changes.
        """
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(jcamp, [str(tmp_path)])

        hsqc_path = _find_json(tmp_path / "analysis", "HSQC.json")
        payload = json.loads(hsqc_path.read_text())
        assert payload["n_cross_peaks"] > 0
        hints = {p["multiplicity_hint"] for p in payload["cross_peaks"]}
        assert "CH2" in hints
        assert "CH_or_CH3" in hints
        assert "CH_or_CH2_or_CH3" not in hints

    def test_qc_verdict_is_embedded_in_peak_json(self, tmp_path: Path) -> None:
        """JCLI-02: the unchanged QC gate's verdict reaches the peak JSON."""
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(jcamp, [str(tmp_path)])

        hsqc_path = _find_json(tmp_path / "analysis", "HSQC.json")
        payload = json.loads(hsqc_path.read_text())
        assert payload["reconstruction"]["qc_verdict"] in ("PASS", "PARTIAL", "FAIL")
        assert payload["reconstruction"]["backend"] == "jcamp"
        assert payload["reconstruction"]["thresholds_used"]
        assert payload["source"]["format"] == "JCAMP-DX"

    def test_1d_lists_are_qc_discoverable_in_the_output_directory(self, tmp_path: Path) -> None:
        """D-03/D-04: the picked 1D lists are the QC gate's own trusted
        1D reference -- proven via the REAL `QcReferenceData.resolve()`,
        not by inspecting the CLI's internal staging.
        """
        from lucy_ng.nus.qc import QcReferenceData

        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(jcamp, [str(tmp_path)])

        hsqc_path = _find_json(tmp_path / "analysis", "HSQC.json")
        written_dir = hsqc_path.parent
        ref = QcReferenceData.resolve(written_dir)
        assert ref.trusted_c13
        assert ref.trusted_h1
        # INHERITED byte-unchanged-qc.py behaviour (102-RESEARCH.md Pitfall
        # 4), NOT a choice this phase makes: with no DEPT `.dx` file present,
        # `QcConfig.default()`'s five compiled-in Sec.8 quaternary shifts are
        # used unconditionally as the tier-2 override.
        assert ref.classification_source == "override"

    def test_explicit_file_list_mode(self, tmp_path: Path) -> None:
        """D-01: an explicit file list (not a directory) is a supported input mode."""
        _copy_fixtures(tmp_path)
        files = [
            str(tmp_path / "C20H32O2_HSQC_trimmed.dx"),
            str(tmp_path / "C20H32O2_1H.dx"),
            str(tmp_path / "C20H32O2_13C.dx"),
        ]
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [*files, "--format", "json"])
        data = json.loads(result.output)
        assert data["verdict"] in ("PASS", "PARTIAL", "FAIL")
        # Written relative to <parent-of-first-file>/analysis/nmr_peaks, per
        # the same D-07 branch invariant as the directory-mode test.
        expected_out = tmp_path / "analysis" / "nmr_peaks"
        assert Path(data["out_dir"]) == expected_out

    def test_out_override(self, tmp_path: Path) -> None:
        """D-02: `--out` relocates the consumable/quarantine artefacts, and
        no `analysis/` tree is created under the input directory at all.
        """
        _copy_fixtures(tmp_path)
        custom = tmp_path / "custom"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--out", str(custom), "--format", "json"])
        data = json.loads(result.output)

        assert not (tmp_path / "analysis").exists()
        if data["verdict"] == "FAIL":
            assert Path(data["quarantine"]) == custom.parent / "jcamp_ingest" / "qc_failed"
        else:
            assert Path(data["out_dir"]) == custom

    def test_format_json_shape(self, tmp_path: Path) -> None:
        """The `--format json` output parses and carries the documented shape."""
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])
        data = json.loads(result.output)
        assert set(data.keys()) == {
            "verdict",
            "out_dir",
            "written",
            "skipped",
            "failed",
            "quarantine",
            "report",
        }
        assert len(data["report"]["checks"]) == 6

    def test_observed_trimmed_fixture_verdict(self, tmp_path: Path) -> None:
        """Observed (not invented) verdict for the six committed fixtures.

        RUN FIRST, then assert what was actually seen: the trimmed HSQC
        fixture covers only 16 F1 rows (~1.3 ppm of 13C), so it cannot reach
        the 0.8 `hsqc_coverage` floor against the whole-file 1D 13C
        reference (45 real picked 13C shifts) -- a FAIL verdict is the
        expected, honest outcome of testing on a deliberately small fixture,
        not a defect. Verified live 2026-07-25: `hsqc_coverage` reports
        "2/21 protonated carbons covered (10%)", `ppm_calibration` and
        `signal_to_ridge` also fail critically. Driving the REAL
        2048x2048 `C20H32O2-jcamp` dataset to a green Sec.8 verdict is
        Phase 103 / JVAL (D-05) -- explicitly NOT this phase's bar.
        """
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])
        data = json.loads(result.output)

        assert data["verdict"] == "FAIL", (
            "observed verdict changed from the recorded baseline (FAIL) -- "
            "if this is an intentional picker/QC-threshold change, update "
            "this test's assertion AND the comment above with the new "
            "observed reason; do not silently flip the expectation"
        )
        failed_checks = {c["name"] for c in data["report"]["checks"] if not c["passed"]}
        assert "hsqc_coverage" in failed_checks


class TestJcampStaleStateCleared:
    """CR-01 regression: a prior invocation's staged/quarantine/consumable
    state must never leak into a later invocation over the same output
    tree. Both scenarios were live-reproduced against the pre-fix code
    (102-REVIEW.md CR-01) and fail without the STEP 2.5 clearing logic.
    """

    def test_removed_input_does_not_pollute_the_next_runs_qc_verdict(
        self, tmp_path: Path
    ) -> None:
        """Deleting a `.dx` input and re-running must not let that
        experiment's stale staged JSON from run 1 leak into run 2's
        `run_qc_checks()` glob.
        """
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(jcamp, [str(tmp_path)])

        staged_dir = tmp_path / "analysis" / "jcamp_ingest" / "staged"
        assert (staged_dir / "COSY.json").exists()

        (tmp_path / "C20H32O2_COSY_trimmed.dx").unlink()
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])
        data = json.loads(result.output)

        # The removed file must never be re-staged, and no stale COSY
        # artifact from run 1 may remain in the staged directory that
        # run_qc_checks() globs over for run 2's verdict.
        assert not (staged_dir / "COSY.json").exists()
        assert not any(entry["file"].startswith("C20H32O2_COSY") for entry in data["failed"])
        checked_names = {c["name"] for c in data["report"]["checks"]}
        assert "cosy_diagonal_symmetry" in checked_names
        cosy_check = next(
            c for c in data["report"]["checks"] if c["name"] == "cosy_diagonal_symmetry"
        )
        # With no COSY staged at all this run, the COSY-specific check must
        # not be reporting a violation derived from run 1's stale file.
        assert cosy_check["passed"] is True

    def test_pass_then_fail_removes_the_stale_pass_graded_consumable_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale PASS-graded `analysis/nmr_peaks/HSQC.json` from an
        earlier run must not survive a later run whose QC verdict is FAIL --
        it must not still be sitting there advertising `qc_verdict: PASS`.
        """
        from lucy_ng.models.nus import QcReport, QcVerdict

        def fake_pass(peaks_dir: Any, config: Any = None) -> QcReport:
            return QcReport(
                verdict=QcVerdict.PASS,
                checks=TestJcampQcDiscrimination._six_checks(all_pass=True),
                thresholds_used={"c13_tol": 0.5},
                errors=[],
            )

        def fake_fail(peaks_dir: Any, config: Any = None) -> QcReport:
            return QcReport(
                verdict=QcVerdict.FAIL,
                checks=TestJcampQcDiscrimination._six_checks(
                    all_pass=True, failing={"quaternary_exclusion": True}
                ),
                thresholds_used={"c13_tol": 0.5},
                errors=[],
            )

        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)

        monkeypatch.setattr("lucy_ng.nus.qc.run_qc_checks", fake_pass)
        result_pass = runner.invoke(jcamp, [str(tmp_path)])
        assert result_pass.exit_code == 0, result_pass.output

        nmr_peaks = tmp_path / "analysis" / "nmr_peaks"
        hsqc_path = nmr_peaks / "HSQC.json"
        assert hsqc_path.exists()
        assert json.loads(hsqc_path.read_text())["reconstruction"]["qc_verdict"] == "PASS"

        monkeypatch.setattr("lucy_ng.nus.qc.run_qc_checks", fake_fail)
        result_fail = runner.invoke(jcamp, [str(tmp_path)])
        assert result_fail.exit_code != 0

        # The stale PASS-graded file must be gone, and so must the whole
        # now-empty consumable directory (D-07's "FAIL leaves out_root
        # absent" invariant must hold across a re-run, not just a fresh run).
        assert not hsqc_path.exists()
        assert not nmr_peaks.exists()
        quarantine_dir = tmp_path / "analysis" / "jcamp_ingest" / "qc_failed"
        assert quarantine_dir.exists()
        assert json.loads((quarantine_dir / "HSQC.json").read_text())[
            "reconstruction"
        ]["qc_verdict"] == "FAIL"


class TestJcampQcDiscrimination:
    """MOCK-COVERED (real peaks, injected verdict): the peaks staged into
    the QC gate below are real, fixture-derived cross-peaks (the same
    read -> pick chain `TestJcampEndToEnd` exercises unmocked); only the
    `QcReport` VERDICT itself is a test double over
    `lucy_ng.nus.qc.run_qc_checks` -- the CLI resolves that name via a
    deferred import inside the command body, so monkeypatching the source
    attribute intercepts it correctly. This lets D-05's "PASS/PARTIAL/FAIL
    all mechanically reachable" bar be proven without needing a genuinely
    Sec.8-quality spectrum, which the 16-row trimmed fixtures cannot
    provide (see `test_observed_trimmed_fixture_verdict` above).
    """

    @staticmethod
    def _six_checks(*, all_pass: bool, failing: dict[str, bool] | None = None) -> list[Any]:
        """Build all six named `QcCheckResult`s; `failing` names the subset
        that must report `passed=False` (`all_pass` documents the common
        case at each call site but every check not named in `failing`
        always passes).
        """
        from lucy_ng.models.nus import QcCheckResult

        assert all_pass, "this helper only builds the mostly-passing shape used by these tests"
        failing = failing or {}
        critical_by_name = {
            "quaternary_exclusion": True,
            "ppm_calibration": True,
            "hsqc_coverage": True,
            "signal_to_ridge": True,
            "edited_sign_consistency": False,
            "cosy_diagonal_symmetry": False,
        }
        return [
            QcCheckResult(
                name=name,
                passed=name not in failing,
                critical=critical,
                details="stand-in",
            )
            for name, critical in critical_by_name.items()
        ]

    def test_pass_verdict_writes_consumable_peaks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lucy_ng.models.nus import QcReport, QcVerdict

        def fake_run_qc_checks(peaks_dir: Any, config: Any = None) -> QcReport:
            return QcReport(
                verdict=QcVerdict.PASS,
                checks=self._six_checks(all_pass=True),
                thresholds_used={"c13_tol": 0.5},
                errors=[],
            )

        monkeypatch.setattr("lucy_ng.nus.qc.run_qc_checks", fake_run_qc_checks)

        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])

        assert result.exit_code == 0, result.output
        nmr_peaks = tmp_path / "analysis" / "nmr_peaks"
        hsqc_path = nmr_peaks / "HSQC.json"
        assert hsqc_path.exists()
        payload = json.loads(hsqc_path.read_text())
        assert payload["reconstruction"]["qc_verdict"] == "PASS"
        assert all(p["confidence"] == "high" for p in payload["cross_peaks"])
        assert not (tmp_path / "analysis" / "jcamp_ingest" / "qc_failed").exists()

    def test_partial_verdict_writes_and_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lucy_ng.models.nus import QcReport, QcVerdict

        def fake_run_qc_checks(peaks_dir: Any, config: Any = None) -> QcReport:
            return QcReport(
                verdict=QcVerdict.PARTIAL,
                checks=self._six_checks(
                    all_pass=True, failing={"cosy_diagonal_symmetry": True}
                ),
                thresholds_used={"cosy_symmetry_floor": 0.5},
                errors=[],
            )

        monkeypatch.setattr("lucy_ng.nus.qc.run_qc_checks", fake_run_qc_checks)

        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])

        assert result.exit_code == 0, result.output
        hsqc_path = tmp_path / "analysis" / "nmr_peaks" / "HSQC.json"
        payload = json.loads(hsqc_path.read_text())
        assert payload["reconstruction"]["qc_verdict"] == "PARTIAL"
        assert all(p["confidence"] == "low" for p in payload["cross_peaks"])
        assert "cosy_diagonal_symmetry" in payload["reconstruction"]["violated_checks"]
        assert "cosy_diagonal_symmetry" in result.output

    def test_fail_verdict_quarantines_and_exits_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mirrors `tests/nus/test_write_boundary.py`'s FAIL assertion shape.

        Also proves `confidence_from_verdict()` is never called for FAIL
        peaks (it raises by design, per `nus/bridge.py`) -- the CLI's FAIL
        branch hand-builds the metadata instead, and this test would raise
        `ValueError` if that contract were ever violated.
        """
        from lucy_ng.models.nus import QcReport, QcVerdict

        def fake_run_qc_checks(peaks_dir: Any, config: Any = None) -> QcReport:
            return QcReport(
                verdict=QcVerdict.FAIL,
                checks=self._six_checks(all_pass=True, failing={"quaternary_exclusion": True}),
                thresholds_used={"c13_tol": 0.5},
                errors=[],
            )

        monkeypatch.setattr("lucy_ng.nus.qc.run_qc_checks", fake_run_qc_checks)

        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])

        assert result.exit_code != 0
        assert not (tmp_path / "analysis" / "nmr_peaks").exists()
        quarantine_dir = tmp_path / "analysis" / "jcamp_ingest" / "qc_failed"
        assert quarantine_dir.exists()
        assert (quarantine_dir / "qc_report.json").exists()
        payload = json.loads((quarantine_dir / "HSQC.json").read_text())
        assert payload["reconstruction"]["qc_verdict"] == "FAIL"
        assert "quaternary_exclusion" in payload["caveat"]

    def test_read_failure_forces_nonzero_exit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T-102-07: a malformed `.dx` is never silently absorbed as clean,
        even when the QC verdict itself is forced to PASS.
        """
        from lucy_ng.models.nus import QcReport, QcVerdict

        def fake_run_qc_checks(peaks_dir: Any, config: Any = None) -> QcReport:
            return QcReport(
                verdict=QcVerdict.PASS,
                checks=self._six_checks(all_pass=True),
                thresholds_used={},
                errors=[],
            )

        monkeypatch.setattr("lucy_ng.nus.qc.run_qc_checks", fake_run_qc_checks)

        _copy_fixtures(tmp_path)
        (tmp_path / "broken.dx").write_text("not a jcamp file\njust some text\n")

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(jcamp, [str(tmp_path), "--format", "json"])

        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["verdict"] == "PASS"
        failed_names = {e["file"] for e in data["failed"]}
        assert "broken.dx" in failed_names


class TestJcampKnobOptions:
    """D-01/D-04: per-experiment `--threshold`/`--snr-floor` `KEY=value`
    wiring, added Phase 103. `bridge_peak_pick`/`bridge_peak_pick_1d` are
    wrapped with recording spies that DELEGATE to the real implementations
    (real peaks still get produced, so the QC gate and D-07 write boundary
    behave normally) while capturing the exact per-call
    `(experiment_or_nucleus, threshold, snr_floor)` triple -- both are
    imported inside the command body at call time, so patching the source
    module attribute intercepts the deferred import correctly (same
    convention `TestJcampQcDiscrimination` already establishes for
    `run_qc_checks`).
    """

    @staticmethod
    def _spy_bridges(
        monkeypatch: pytest.MonkeyPatch,
    ) -> tuple[
        list[tuple[str, float | None, float]], list[tuple[str, float | None, float | None]]
    ]:
        import lucy_ng.nus.bridge as bridge_mod
        import lucy_ng.processing.jcamp_1d_bridge as bridge_1d_mod

        calls_2d: list[tuple[str, float | None, float]] = []
        calls_1d: list[tuple[str, float | None, float | None]] = []
        real_2d = bridge_mod.bridge_peak_pick
        real_1d = bridge_1d_mod.bridge_peak_pick_1d

        def spy_2d(
            spectrum: Any,
            *,
            experiment: str,
            qc_report: Any = None,
            recon_meta: Any = None,
            threshold: float | None = None,
            snr_floor: float = 5.0,
        ) -> Any:
            calls_2d.append((experiment, threshold, snr_floor))
            return real_2d(
                spectrum,
                experiment=experiment,
                qc_report=qc_report,
                recon_meta=recon_meta,
                threshold=threshold,
                snr_floor=snr_floor,
            )

        def spy_1d(
            spectrum: Any, *, threshold: float | None = None, snr_floor: float | None = None
        ) -> Any:
            calls_1d.append((spectrum.nucleus, threshold, snr_floor))
            return real_1d(spectrum, threshold=threshold, snr_floor=snr_floor)

        monkeypatch.setattr(bridge_mod, "bridge_peak_pick", spy_2d)
        monkeypatch.setattr(bridge_1d_mod, "bridge_peak_pick_1d", spy_1d)
        return calls_2d, calls_1d

    @staticmethod
    def _by_experiment(
        calls: list[tuple[str, float | None, float]],
    ) -> dict[str, set[tuple[float | None, float]]]:
        by_experiment: dict[str, set[tuple[float | None, float]]] = {}
        for name, threshold, snr_floor in calls:
            by_experiment.setdefault(name, set()).add((threshold, snr_floor))
        return by_experiment

    def test_help_documents_threshold_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(jcamp, ["--help"])
        assert result.exit_code == 0, result.output
        assert "--threshold" in result.output

    def test_bare_snr_floor_applies_to_every_experiment_backwards_compatible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The plain `--snr-floor 5.0` form behaves exactly as before D-04."""
        calls_2d, calls_1d = self._spy_bridges(monkeypatch)
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(jcamp, [str(tmp_path), "--snr-floor", "5.0"])

        assert calls_2d, "no 2D bridge calls recorded"
        for _experiment, threshold, snr_floor in calls_2d:
            assert threshold is None
            assert snr_floor == 5.0
        for _nucleus, threshold, snr_floor in calls_1d:
            assert threshold is None
            assert snr_floor == 5.0

    def test_omitting_snr_floor_entirely_yields_the_shipped_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Omitting `--snr-floor` entirely still yields 5.0 everywhere."""
        calls_2d, _calls_1d = self._spy_bridges(monkeypatch)
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(jcamp, [str(tmp_path)])

        assert calls_2d
        for _experiment, threshold, snr_floor in calls_2d:
            assert threshold is None
            assert snr_floor == 5.0

    def test_keyed_form_routes_per_experiment_and_reaches_staging_and_rebuild_identically(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--threshold hsqc=1e4 --threshold hmbc=3e4 --snr-floor cosy=7`
        routes threshold=0.01 (fraction-of-max) to HSQC, threshold=0.02 to
        HMBC, snr_floor=7.0 to COSY -- and the staging call and the
        PASS/PARTIAL (or FAIL) rebuild call for the SAME experiment record
        the identical triple (asserted via the per-experiment call-set
        having exactly one member). Values kept in the real, meaningful
        fraction-of-max range (not an arbitrary large number) so the
        16-row trimmed fixture still yields at least one peak -- an
        all-zero pick is a pre-existing `PeakPicker2D`/nmrglue edge case
        unrelated to this option-parsing test.
        """
        calls_2d, _calls_1d = self._spy_bridges(monkeypatch)
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(
            jcamp,
            [
                str(tmp_path),
                "--threshold",
                "hsqc=0.01",
                "--threshold",
                "hmbc=0.02",
                "--snr-floor",
                "cosy=7",
            ],
        )

        per_experiment_count = Counter(name for name, _, _ in calls_2d)
        for experiment in ("HSQC", "HMBC", "COSY"):
            assert per_experiment_count[experiment] == 2, (
                f"expected one staging + one rebuild call for {experiment}, "
                f"got {per_experiment_count[experiment]} -- a deleted rebuild "
                "call site must fail this test"
            )

        by_experiment = self._by_experiment(calls_2d)
        assert by_experiment["HSQC"] == {(0.01, 5.0)}
        assert by_experiment["HMBC"] == {(0.02, 5.0)}
        assert by_experiment["COSY"] == {(None, 7.0)}

    def test_case_insensitive_keys_for_both_experiments_and_nuclei(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--threshold hsqc=...`/`--threshold HSQC=...` are equivalent;
        `--snr-floor 13c=20`/`--snr-floor 1h=10` resolve to `13C`/`1H`.
        """
        calls_2d, calls_1d = self._spy_bridges(monkeypatch)
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            jcamp,
            [
                str(tmp_path),
                "--threshold",
                "HSQC=1e4",
                "--snr-floor",
                "13c=20",
                "--snr-floor",
                "1h=10",
            ],
        )
        # click.BadParameter's usage error would land on stderr, not
        # result.output (stdout only under mix_stderr=False) -- assert on
        # the real channel it would appear on so a false rejection actually
        # fails this test.
        assert "unrecognized key" not in result.stderr

        by_experiment = self._by_experiment(calls_2d)
        assert by_experiment["HSQC"] == {(10000.0, 5.0)}
        by_nucleus = {nucleus: (t, s) for nucleus, t, s in calls_1d}
        assert by_nucleus["13C"] == (None, 20.0)
        assert by_nucleus["1H"] == (None, 10.0)

    def test_keyed_beats_bare_for_the_named_experiment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--snr-floor 5.0 --snr-floor hsqc=4000` gives HSQC 4000.0 and
        everyone else 5.0 (keyed always beats bare)."""
        calls_2d, _calls_1d = self._spy_bridges(monkeypatch)
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(
            jcamp,
            [str(tmp_path), "--snr-floor", "5.0", "--snr-floor", "hsqc=4000"],
        )

        by_experiment = self._by_experiment(calls_2d)
        assert by_experiment["HSQC"] == {(None, 4000.0)}
        assert by_experiment["HMBC"] == {(None, 5.0)}
        assert by_experiment["COSY"] == {(None, 5.0)}

    def test_unrecognized_key_exits_nonzero_and_names_it(self, tmp_path: Path) -> None:
        """Typo guard: `--threshold hqsc=1` must fail loud, not silently
        apply nothing."""
        _copy_fixtures(tmp_path)
        runner = CliRunner()
        result = runner.invoke(jcamp, [str(tmp_path), "--threshold", "hqsc=1"])
        assert result.exit_code != 0
        assert "hqsc" in result.output
        assert "HSQC" in result.output

    def test_malformed_value_exits_nonzero(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path)
        runner = CliRunner()
        result = runner.invoke(jcamp, [str(tmp_path), "--threshold", "hsqc=abc"])
        assert result.exit_code != 0

    def test_same_experiment_threshold_and_snr_floor_is_ambiguous(
        self, tmp_path: Path
    ) -> None:
        """A keyed `--threshold` and a keyed `--snr-floor` for the SAME
        experiment is rejected -- the two are mutually exclusive modes, so
        an explicit request for both is ambiguous, not a merge."""
        _copy_fixtures(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            jcamp,
            [str(tmp_path), "--threshold", "hsqc=0.02", "--snr-floor", "hsqc=4000"],
        )
        assert result.exit_code != 0
        assert "HSQC" in result.output

    def test_bare_threshold_with_keyed_snr_floor_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """CR-01 regression: a BARE `--threshold` combined with a KEYED
        `--snr-floor` for the same experiment must be rejected, not
        silently accepted with the snr-floor discarded. Before the CR-01
        fix, the old guard only compared the two KEYED sets, so a bare
        `--threshold` was invisible to it: `_resolved_threshold()` falls
        back to the bare value for every experiment, and
        `nus/bridge.py`'s `use_snr = threshold is None` then silently
        drops the explicitly requested `--snr-floor` for COSY with no
        warning and exit code 0/1 as if it had been honoured."""
        _copy_fixtures(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            jcamp, [str(tmp_path), "--threshold", "0.02", "--snr-floor", "cosy=7"]
        )
        assert result.exit_code == 2, result.output
        assert "COSY" in result.output

    def test_keyed_threshold_with_bare_snr_floor_is_legal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A keyed `--threshold` alongside a BARE `--snr-floor` is legal --
        it means fraction-of-max mode for that experiment, documented, not
        an error -- and every OTHER experiment still gets the bare
        snr-floor unchanged."""
        calls_2d, _calls_1d = self._spy_bridges(monkeypatch)
        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            jcamp,
            [str(tmp_path), "--threshold", "hsqc=0.02", "--snr-floor", "5.0"],
        )
        assert result.exit_code in (0, 1), result.output  # never a usage error (2)

        by_experiment = self._by_experiment(calls_2d)
        assert by_experiment["HSQC"] == {(0.02, 5.0)}
        assert by_experiment["HMBC"] == {(None, 5.0)}
        assert by_experiment["COSY"] == {(None, 5.0)}

    def test_run_qc_checks_called_exactly_once_regardless_of_knob_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """D-04: the QC gate stays a single call over the fully-staged set
        no matter how many distinct keyed values are supplied."""
        import lucy_ng.nus.qc as qc_mod

        calls: list[Path] = []
        real_run_qc_checks = qc_mod.run_qc_checks

        def spy_run_qc_checks(peaks_dir: Path, config: Any = None) -> Any:
            calls.append(peaks_dir)
            return real_run_qc_checks(peaks_dir, config)

        monkeypatch.setattr(qc_mod, "run_qc_checks", spy_run_qc_checks)

        _copy_fixtures(tmp_path)
        runner = CliRunner(mix_stderr=False)
        runner.invoke(
            jcamp,
            [
                str(tmp_path),
                "--threshold",
                "hsqc=0.01",
                "--threshold",
                "hmbc=0.02",
                "--snr-floor",
                "cosy=7",
                "--snr-floor",
                "13c=10",
                "--snr-floor",
                "1h=10",
            ],
        )

        assert len(calls) == 1
