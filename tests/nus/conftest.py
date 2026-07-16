"""Shared fixtures for tests/nus/ (Phase 98 Reconstruction + Processing).

Wave 0 scaffolding (98-01): this module provides the subprocess mock seam and
fake-intermediate-file factories that later plans' RED-by-skip stubs (and
their eventual GREEN implementations) will use to exercise `nus/runner.py` /
`nus/postprocess.py` / `nus/backends/nmrpipe_smile.py` without any real
NMRPipe/SMILE binary on PATH -- D-04's CI-safe mocked-subprocess-boundary
strategy.

CRITICAL (collection safety): this file must NOT import
`lucy_ng.nus.runner` or `lucy_ng.nus.postprocess` at module level -- neither
module exists yet in Wave 0 (they ship in Plans 02-05). All `lucy_ng.nus.*`
references are deferred as *string* monkeypatch targets inside fixture
bodies (`raising=False`), never as top-level imports, so `tests/nus/` stays
collectable on a machine with no NMRPipe and before those modules exist.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

# Directory holding the Phase-97 real-data fixtures (acqus/acqu2s/nuslist/
# pdata) for the three C20H32O2 NUS experiments. Pure pathlib -- no lucy_ng
# import required to resolve this path.
_NUS_FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "nus"

_FIXTURE_NAMES = {"exp2_cosy", "exp3_hsqc", "exp4_hmbc"}

# Phase 99 (Peak-Pick Bridge + QC Gate + CLI) Wave 0 fixture directories --
# real known-bad home-IST peak lists (QC-02 FAIL side) and hand-authored
# synthetic clean peak lists (QC-02 PASS side, no real clean reconstruction
# exists until Phase 100). Pure pathlib, no lucy_ng import required.
_KNOWN_BAD_PEAKS_DIR = _NUS_FIXTURES_ROOT / "known_bad_peaks"
_CLEAN_PEAKS_DIR = _NUS_FIXTURES_ROOT / "clean_peaks_synthetic"

# The 5 confirmed-quaternary 13C shifts (NUS-RECONSTRUCTION-GUIDE.md §8/§10)
# re-exported for QC-02/QC-01 tests -- a subset of nus/postprocess.py's
# GUIDE_S10_C13 20-shift list.
KNOWN_QUATERNARY_SHIFTS = [142.00, 135.86, 79.35, 36.23, 37.86]


@pytest.fixture
def known_bad_peaks_dir() -> Path:
    """Resolve `tests/fixtures/nus/known_bad_peaks` (QC-02 FAIL-side fixture)."""
    return _KNOWN_BAD_PEAKS_DIR


@pytest.fixture
def clean_peaks_dir() -> Path:
    """Resolve `tests/fixtures/nus/clean_peaks_synthetic` (QC-02 PASS-side fixture)."""
    return _CLEAN_PEAKS_DIR


@pytest.fixture
def nus_fixture_dir() -> Callable[[str], Path]:
    """Return a callable mapping a fixture name to its resolved Path.

    Usage: ``nus_fixture_dir("exp3_hsqc")`` -> ``tests/fixtures/nus/exp3_hsqc``

    Valid names: "exp2_cosy" (COSY, FnMODE=1), "exp3_hsqc" (HSQC, FnMODE=6),
    "exp4_hmbc" (HMBC, FnMODE=6). Raises ValueError on an unrecognized name
    (refuse-to-guess convention, matching nus/schedule.py).
    """

    def _resolve(name: str) -> Path:
        if name not in _FIXTURE_NAMES:
            raise ValueError(
                f"Unknown NUS fixture name: {name!r}. Valid: {sorted(_FIXTURE_NAMES)}"
            )
        resolved = _NUS_FIXTURES_ROOT / name
        return resolved

    return _resolve


@pytest.fixture
def make_valid_intermediate(tmp_path: Path) -> Callable[..., Path]:
    """Factory: write a non-empty fake NMRPipe intermediate file.

    Writes arbitrary non-zero bytes under `tmp_path` with a caller-chosen
    suffix (e.g. ".fid"/".ft2"), simulating a stage that reported exit 0 AND
    produced a real (non-empty) output file -- the exit-0-success path for
    RECON-04's fail-loud wrapper tests.
    """

    def _make(name: str = "intermediate", suffix: str = ".fid") -> Path:
        path = tmp_path / f"{name}{suffix}"
        # Arbitrary non-zero payload -- deliberately not a real NMRPipe
        # binary layout; RECON-04 stub tests only assert non-emptiness at
        # this Wave-0 stage. Later plans may swap in a minimal valid
        # nmrglue-readable payload if the GREEN implementation needs one.
        path.write_bytes(b"\x01\x02\x03\x04" * 16)
        return path

    return _make


@pytest.fixture
def make_empty_intermediate(tmp_path: Path) -> Callable[..., Path]:
    """Factory: write a zero-byte fake NMRPipe intermediate file.

    Simulates a stage that reported exit 0 but produced a zero-byte output
    file -- the RECON-04 fail-loud "empty output" case that must raise.
    """

    def _make(name: str = "empty_intermediate", suffix: str = ".fid") -> Path:
        path = tmp_path / f"{name}{suffix}"
        path.write_bytes(b"")
        return path

    return _make


@pytest.fixture
def make_truncated_intermediate(tmp_path: Path) -> Callable[..., Path]:
    """Factory: write a deliberately-too-short fake NMRPipe intermediate file.

    Simulates a stage that reported exit 0 and produced a *non-empty* but
    truncated/all-zero output file -- the RECON-04 fail-loud "truncated
    output" case (Pitfall 14: csh-piped NMRPipe stages can silently pass
    through truncated data) that must also raise.
    """

    def _make(name: str = "truncated_intermediate", suffix: str = ".fid") -> Path:
        path = tmp_path / f"{name}{suffix}"
        # Non-zero size but all-zero bytes -- deliberately too short/blank
        # to be a legitimate NMRPipe data file.
        path.write_bytes(b"\x00" * 8)
        return path

    return _make


@pytest.fixture
def make_valid_ft2(tmp_path: Path) -> Callable[..., Path]:
    """Factory: write a real, nmrglue-readable minimal NMRPipe `.ft2` file.

    Unlike `make_valid_intermediate` (arbitrary non-zero bytes -- fine for
    RECON-04's exit-0/non-empty checks, which never actually parse the
    file), Phase 99's `nus/bridge.py::build_spectrum2d()` genuinely reads
    the `.ft2` header via `ng.pipe.read()`/`ng.pipe.guess_udic()`, so its
    tests need a real, minimally-valid NMRPipe 2D data file. Built via
    `ng.fileiobase.create_blank_udic(2)` + `ng.pipe.create_dic()` +
    `ng.pipe.write()` -- small (8x16 real-valued float32 by default),
    round-trips cleanly through `ng.pipe.read()`.

    Optionally writes a `processed_ppm_axis.json` sidecar next to the
    `.ft2` file (99-PATTERNS.md Pattern 1's F1-axis-override path) when
    ``calibrated_f1_ppm_axis`` is given.
    """

    def _make(
        name: str = "processed",
        f1_size: int = 8,
        f2_size: int = 16,
        f1_car_ppm: float = 100.0,
        f1_obs_mhz: float = 125.0,
        f2_car_ppm: float = 4.0,
        f2_obs_mhz: float = 500.0,
        calibrated_f1_ppm_axis: list | None = None,
    ) -> Path:
        import nmrglue as ng
        import numpy as np

        udic = ng.fileiobase.create_blank_udic(2)
        udic[0].update(
            car=f1_car_ppm * f1_obs_mhz,
            complex=False,
            freq=True,
            time=False,
            label="13C",
            obs=f1_obs_mhz,
            size=f1_size,
            sw=f1_obs_mhz * 8,
            encoding="states",
        )
        udic[1].update(
            car=f2_car_ppm * f2_obs_mhz,
            complex=False,
            freq=True,
            time=False,
            label="1H",
            obs=f2_obs_mhz,
            size=f2_size,
            sw=f2_obs_mhz * 8,
            encoding="direct",
        )
        data = np.random.default_rng(0).random((f1_size, f2_size)).astype(np.float32)
        dic = ng.pipe.create_dic(udic)
        path = tmp_path / f"{name}.ft2"
        ng.pipe.write(str(path), dic, data, overwrite=True)

        if calibrated_f1_ppm_axis is not None:
            sidecar = path.parent / "processed_ppm_axis.json"
            sidecar.write_text(
                json.dumps({"calibrated_ppm_axis": calibrated_f1_ppm_axis})
            )

        return path

    return _make


@pytest.fixture
def mock_run_stage(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Monkeypatch `lucy_ng.nus.runner.run_stage` with a call recorder.

    `run_stage` does not exist yet in Wave 0 (ships Plan 02) -- monkeypatch
    BY STRING TARGET with `raising=False` so this fixture is safe to use
    (and to leave unused) both before and after that module exists.

    Returns the shared `captured` dict; each call appends a
    ``(name, argv, cwd, expected_output)`` tuple to ``captured["calls"]`` so
    tests can assert dispatch order/argv without a real subprocess.
    """
    captured: dict = {"calls": []}

    def _fake_run_stage(name, argv, cwd, expected_output, timeout=600):
        captured["calls"].append((name, argv, cwd, expected_output))

    monkeypatch.setattr(
        "lucy_ng.nus.runner.run_stage", _fake_run_stage, raising=False
    )
    return captured


@pytest.fixture
def mock_pipeline_stages(monkeypatch: pytest.MonkeyPatch) -> Callable[..., object]:
    """Factory: monkeypatch `lucy nus pipeline`'s three external-dependency
    seams for CLI tests (Phase 99 Plan 04) -- `NusRunner.reconstruct()`
    (no real NMRPipe+SMILE binary needed), `read_nus_params()` (no real
    Bruker `acqus`/`acqu2s` needed), and `build_spectrum2d()` (no real
    reconstructed `.ft2` needed, replaced by a deterministic synthetic
    `Spectrum2D` with one explicit strong peak, mirroring
    `tests/nus/test_bridge.py`'s synthetic-peak pattern) -- while keeping
    `bridge_peak_pick()` (Plan 03) and `write_peak_json()` genuinely real,
    so D-05/D-06/D-07's write-boundary logic in `cli/nus.py::pipeline`
    itself is exercised for real.

    `run_qc_checks()` is also monkeypatched to return a caller-supplied
    verdict/violated-checks combination directly -- QC-01/QC-02's six
    check algorithms are already proven real against real fixture data in
    `tests/nus/test_qc_checks.py`/`test_qc_regression.py` (Plan 02); this
    plan's own scope is the CLI wiring + write/quarantine boundary, not a
    second proof of the check algorithms.

    Usage: ``mock_pipeline_stages(verdict="FAIL", violated=["quaternary_exclusion"])``
    returns the `QcReport` the pipeline will receive, for assertion reuse.
    """

    def _setup(
        verdict: str,
        violated: list[str] | None = None,
    ) -> object:
        import numpy as np

        from lucy_ng.models import Spectrum2D
        from lucy_ng.models.nus import (
            NusAcquisitionParams,
            NusReconstructionResult,
            QcCheckResult,
            QcReport,
            QcVerdict,
        )

        params = NusAcquisitionParams(
            pulse_program="hsqcedetgpsisp2.3",
            f2_nucleus="1H",
            f2_sfo1=500.13,
            f2_sw_h=8000.0,
            f2_td=2048,
            byte_order=0,
            dtype_code=0,
            decim=32.0,
            dspfvs=20,
            grpdly=67.98,
            nus_amount_pct=25,
            nus_seed=1,
            f1_nucleus="13C",
            f1_sfo1=125.77,
            f1_sw_h=25000.0,
            f1_o1=10000.0,
            f1_td=256,
            fnmode_f1=6,
            nus_td=256,
        )
        monkeypatch.setattr(
            "lucy_ng.nus.params.read_nus_params", lambda expdir: params
        )

        def _fake_reconstruct(
            self: object, expdir: str | Path, **kwargs: object
        ) -> NusReconstructionResult:
            expdir = Path(expdir)
            stage_dir = expdir / "analysis" / "nus_recon" / expdir.name
            stage_dir.mkdir(parents=True, exist_ok=True)
            return NusReconstructionResult(
                success=True,
                backend="mock_backend",
                fnmode_f1=6,
                stage_dir=str(stage_dir),
                stage_outputs={},
                processed_spectrum=str(stage_dir / "processed.ft2"),
                smile_iterations=10,
            )

        monkeypatch.setattr(
            "lucy_ng.nus.runner.NusRunner.reconstruct", _fake_reconstruct
        )

        rng = np.random.default_rng(11)
        n1, n2 = 32, 48
        data = rng.normal(0.0, 50.0, size=(n1, n2))
        f1_scale = np.linspace(200.0, 0.0, n1, dtype=np.float64)
        f2_scale = np.linspace(10.0, 0.0, n2, dtype=np.float64)
        f1_idx = int(np.argmin(np.abs(f1_scale - 69.06)))
        f2_idx = int(np.argmin(np.abs(f2_scale - 0.99)))
        data[f1_idx, f2_idx] = 1.0e6
        spectrum = Spectrum2D(
            data=data,
            f1_ppm_scale=f1_scale,
            f2_ppm_scale=f2_scale,
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HSQC",
            frequency=500.13,
        )
        monkeypatch.setattr(
            "lucy_ng.nus.bridge.build_spectrum2d",
            lambda processed_ft2, params, experiment_type: spectrum,
        )

        critical_names = {
            "quaternary_exclusion", "ppm_calibration", "signal_to_ridge", "hsqc_coverage",
        }
        violated = violated or []
        checks = [
            QcCheckResult(
                name=name,
                passed=name not in violated,
                critical=name in critical_names,
                details="mocked",
            )
            for name in (
                "quaternary_exclusion",
                "ppm_calibration",
                "signal_to_ridge",
                "hsqc_coverage",
                "edited_sign_consistency",
                "cosy_diagonal_symmetry",
            )
        ]
        report = QcReport(
            verdict=QcVerdict(verdict),
            checks=checks,
            thresholds_used={"c13_tol": 0.5},
            errors=[],
        )
        monkeypatch.setattr(
            "lucy_ng.nus.qc.run_qc_checks", lambda peaks_dir, config=None: report
        )
        return report

    return _setup


@pytest.fixture
def mock_subprocess_run(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Monkeypatch `subprocess.run` with a configurable-returncode recorder.

    Mirrors tests/test_lsd_runner.py's `monkeypatch.setattr(subprocess,
    "run", ...)` shape. Returns a shared `captured` dict:
    ``captured["calls"]`` accumulates ``(args, kwargs)`` per invocation;
    ``captured["returncode"]`` (default 0) controls the fake process's
    `.returncode`; set it before invoking the code under test to simulate a
    failing stage.
    """
    captured: dict = {"calls": [], "returncode": 0, "stdout": "", "stderr": ""}

    class _FakeCompletedProcess:
        def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _fake_run(*args, **kwargs):
        captured["calls"].append((args, kwargs))
        return _FakeCompletedProcess(
            returncode=captured["returncode"],
            stdout=captured["stdout"],
            stderr=captured["stderr"],
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    return captured
