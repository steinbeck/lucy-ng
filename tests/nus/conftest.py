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

import subprocess
from pathlib import Path
from typing import Callable

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
