"""Tests for LSD runner."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from rdkit import Chem

from ailsa.lsd.models import Hybridization, LSDAtom, LSDCorrelation, LSDProblem
from ailsa.lsd.runner import LSDRunner, LSDResult, _invoke_outlsd


class TestLSDResult:
    """Tests for LSDResult dataclass."""

    def test_create_success_result(self):
        """Test creating successful result."""
        result = LSDResult(
            success=True,
            solution_count=5,
            return_code=0,
        )
        assert result.success is True
        assert result.solution_count == 5

    def test_create_failure_result(self):
        """Test creating failure result."""
        result = LSDResult(
            success=False,
            solution_count=0,
            stderr="Error message",
            return_code=1,
        )
        assert result.success is False
        assert "Error" in result.stderr

    def test_summary_success(self):
        """Test summary for successful result."""
        result = LSDResult(success=True, solution_count=3, return_code=0)
        summary = result.summary()

        assert "Success" in summary
        assert "3" in summary

    def test_summary_failure(self):
        """Test summary for failed result."""
        result = LSDResult(
            success=False,
            solution_count=0,
            stderr="Parse error",
            return_code=1,
        )
        summary = result.summary()

        assert "Failed" in summary
        assert "Parse error" in summary


class TestLSDRunnerAvailability:
    """Tests for LSD availability checking."""

    def test_is_available_returns_bool(self):
        """Test that is_available returns a boolean."""
        result = LSDRunner.is_available()
        assert isinstance(result, bool)

    def test_find_lsd_returns_path_or_none(self):
        """Test that _find_lsd returns Path or None."""
        result = LSDRunner._find_lsd()
        assert result is None or isinstance(result, Path)


class TestLSDRunnerInit:
    """Tests for LSDRunner initialization."""

    def test_init_with_path(self):
        """Test initialization with explicit path."""
        runner = LSDRunner(lsd_path="/usr/local/bin/lsd")
        assert runner.lsd_path == Path("/usr/local/bin/lsd")

    def test_init_with_expanduser(self):
        """Test that ~ is expanded in path."""
        runner = LSDRunner(lsd_path="~/bin/lsd")
        assert "~" not in str(runner.lsd_path)

    def test_init_without_path(self):
        """Test initialization without path (auto-detect)."""
        runner = LSDRunner()
        # Should be None if not installed, or a Path if found
        assert runner.lsd_path is None or isinstance(runner.lsd_path, Path)


class TestLSDRunnerExecution:
    """Tests for LSD execution."""

    @pytest.fixture
    def simple_problem(self):
        """Create a simple LSD problem for testing."""
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 0))
        problem.add_atom(LSDAtom(2, "C", Hybridization.SP3, 2))
        problem.add_correlation(LSDCorrelation(1, 2, "HMBC"))
        return problem

    def test_run_without_lsd_raises(self, simple_problem):
        """Test that run raises if LSD not found."""
        # Create runner with non-existent path
        runner = LSDRunner(lsd_path="/nonexistent/lsd")
        runner.lsd_path = None  # Force no LSD

        with pytest.raises(FileNotFoundError, match="LSD executable not found"):
            runner.run(simple_problem)

    def test_run_file_not_found_raises(self):
        """Test that run_file raises for missing file."""
        runner = LSDRunner()
        if runner.lsd_path is None:
            pytest.skip("LSD not installed")

        with pytest.raises(FileNotFoundError, match="Input file not found"):
            runner.run_file("/nonexistent/file.lsd")

    @pytest.mark.skipif(
        not LSDRunner.is_available(),
        reason="LSD not installed"
    )
    def test_run_with_real_lsd(self, simple_problem):
        """Test running with real LSD (if available)."""
        runner = LSDRunner()
        result = runner.run(simple_problem, timeout=30)

        assert isinstance(result, LSDResult)
        # May or may not succeed depending on problem validity
        assert result.return_code is not None

    def test_count_solutions_from_files(self):
        """Test solution counting from output files."""
        runner = LSDRunner()

        # Test with mock file list
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "sol1.sol").write_text("solution 1")
            (tmpdir / "sol2.sol").write_text("solution 2")
            (tmpdir / "output.out").write_text("log")

            files = list(tmpdir.glob("*"))
            count = runner._count_solutions("", files)

            assert count == 2  # Two .sol files

    def test_count_solutions_from_stdout(self):
        """Test solution counting from stdout."""
        runner = LSDRunner()

        stdout = "Found 5 solutions in 0.1 seconds"
        count = runner._count_solutions(stdout, [])

        assert count == 5


class TestLSDRunnerFileHandling:
    """Tests for file handling."""

    def test_creates_temp_dir_if_none(self):
        """Test that temp directory is created if output_dir not specified."""
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))

        runner = LSDRunner()
        if runner.lsd_path is None:
            # Test just the input file writing part
            with tempfile.TemporaryDirectory() as tmpdir:
                from ailsa.lsd.generator import LSDInputGenerator
                output_path = Path(tmpdir) / "test.lsd"
                LSDInputGenerator.write_file(problem, output_path)
                assert output_path.exists()
        else:
            # Full test with LSD
            result = runner.run(problem)
            # Result should exist regardless of success
            assert isinstance(result, LSDResult)

    def test_uses_specified_output_dir(self):
        """Test that specified output directory is used."""
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))

        runner = LSDRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            if runner.lsd_path is None:
                # Just test file writing
                from ailsa.lsd.generator import LSDInputGenerator
                output_path = tmpdir / "test.lsd"
                LSDInputGenerator.write_file(problem, output_path)
                assert output_path.exists()
            else:
                result = runner.run(problem, output_dir=tmpdir, keep_files=True)
                assert result.output_dir == tmpdir
                assert (tmpdir / "test.lsd").exists()


class TestLSDRunnerMocked:
    """Tests with mocked subprocess for consistent behavior."""

    def test_timeout_handling(self, monkeypatch):
        """Test timeout is properly handled."""
        import subprocess

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="lsd", timeout=1)

        monkeypatch.setattr(subprocess, "run", mock_run)

        runner = LSDRunner(lsd_path="/bin/true")  # Use any existing executable
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.run(problem, output_dir=Path(tmpdir), timeout=1)

        assert result.success is False
        assert "timed out" in result.stderr

    def test_exception_handling(self, monkeypatch):
        """Test general exception handling."""
        import subprocess

        def mock_run(*args, **kwargs):
            raise OSError("Execution failed")

        monkeypatch.setattr(subprocess, "run", mock_run)

        runner = LSDRunner(lsd_path="/bin/true")
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.run(problem, output_dir=Path(tmpdir))

        assert result.success is False
        assert "Execution failed" in result.stderr


# ---------------------------------------------------------------------------
# Phase 73 regression tests — TestLSDRunnerFixed
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "regression"


class TestLSDRunnerFixed:
    """Verify the Phase 73 plumbing fix: file-arg LSD invocation and
    correct outlsd conversion.

    Integration tests require LSD + outlsd on PATH (skipif-gated).
    The mock-based unit test (test_invoke_outlsd_unit) runs without LSD.
    """

    @pytest.mark.skipif(
        shutil.which("LSD") is None,
        reason="LSD binary not installed",
    )
    def test_runner_writes_sol_file(self, tmp_path: Path) -> None:
        """runner.run_file() writes a .sol file to output_dir.

        Currently FAILS because stdin invocation mode writes no .sol file.
        After the fix, LSD receives the input file as a positional argument
        and writes {stem}.sol to the CWD (output_dir).
        """
        lsd_fixture = FIXTURE_DIR / "ibuprofen_no_4j.lsd"
        runner = LSDRunner()
        runner.run_file(lsd_fixture, output_dir=tmp_path, timeout=120)

        sol_file = tmp_path / "ibuprofen_no_4j.sol"
        assert sol_file.exists(), (
            f"Expected .sol file at {sol_file} — "
            "runner must use file-argument invocation (not stdin) to produce .sol"
        )
        assert sol_file.stat().st_size > 0, ".sol file is empty"

    @pytest.mark.skipif(
        shutil.which("LSD") is None,
        reason="LSD binary not installed",
    )
    def test_runner_produces_smiles(self, tmp_path: Path) -> None:
        """runner.run_file() produces solutions.smi with 392 valid SMILES lines.

        Currently FAILS because outlsd.out contains a 10-line usage message
        (not SMILES) due to the missing '5' argument in _run_outlsd.
        After the fix, _invoke_outlsd uses [outlsd_path, '5'] with the .sol
        file as stdin, producing one SMILES per line.
        """
        outlsd_bin = shutil.which("outlsd")
        assert outlsd_bin is not None, "outlsd binary not found on PATH"

        lsd_fixture = FIXTURE_DIR / "ibuprofen_no_4j.lsd"
        runner = LSDRunner()
        runner.run_file(lsd_fixture, output_dir=tmp_path, timeout=120)

        smiles_file = tmp_path / "solutions.smi"
        assert smiles_file.exists(), (
            f"Expected solutions.smi at {smiles_file} — "
            "runner._run_outlsd must write to solutions.smi with [outlsd, '5', .sol]"
        )
        lines = [ln for ln in smiles_file.read_text().splitlines() if ln.strip()]
        assert len(lines) == 392, (
            f"Expected 392 SMILES lines, got {len(lines)}. "
            "If solutions.smi contains 'outlsd: usage:', the '5' argument is missing."
        )

    @pytest.mark.skipif(
        shutil.which("LSD") is None,
        reason="LSD binary not installed",
    )
    def test_no_header_only_output(self, tmp_path: Path) -> None:
        """solutions.smi first line must be a valid SMILES string.

        Currently FAILS because outlsd.out / solutions.smi first line is
        'outlsd: usage: outlsd p' (a usage header, not SMILES).
        After the fix, the first line is a valid RDKit-parseable SMILES.
        """
        outlsd_bin = shutil.which("outlsd")
        assert outlsd_bin is not None, "outlsd binary not found on PATH"

        lsd_fixture = FIXTURE_DIR / "ibuprofen_no_4j.lsd"
        runner = LSDRunner()
        runner.run_file(lsd_fixture, output_dir=tmp_path, timeout=120)

        smiles_file = tmp_path / "solutions.smi"
        assert smiles_file.exists(), "solutions.smi not written"
        lines = [ln for ln in smiles_file.read_text().splitlines() if ln.strip()]
        assert lines, "solutions.smi is empty"

        first_line = lines[0].split()[0]  # take first whitespace-delimited token
        mol = Chem.MolFromSmiles(first_line)
        assert mol is not None, (
            f"First line of solutions.smi is not a valid SMILES: {first_line!r}. "
            "Expected a molecular structure, not a usage message."
        )

    @pytest.mark.skipif(
        shutil.which("LSD") is None,
        reason="LSD binary not installed",
    )
    def test_lsd_rank_end_to_end(self, tmp_path: Path) -> None:
        """After runner.run_file(), _perform_ranking returns total_solutions=392.

        Currently FAILS because no solutions.smi is written (outlsd bug).
        After the fix, _perform_ranking can consume solutions.smi directly.
        """
        outlsd_bin = shutil.which("outlsd")
        assert outlsd_bin is not None, "outlsd binary not found on PATH"

        lsd_fixture = FIXTURE_DIR / "ibuprofen_no_4j.lsd"
        runner = LSDRunner()
        runner.run_file(lsd_fixture, output_dir=tmp_path, timeout=120)

        smiles_file = tmp_path / "solutions.smi"
        assert smiles_file.exists(), (
            "solutions.smi not written — cannot test ranking"
        )

        from ailsa.cli.lsd import _perform_ranking

        # Ibuprofen 13C shifts (no 4J correlations case)
        ibuprofen_shifts = [
            180.56, 141.37, 136.39, 129.38, 127.26, 45.03, 44.90,
            30.09, 25.54, 22.63, 18.36,
        ]
        result_data = _perform_ranking(
            smiles_file=smiles_file,
            experimental_shifts=ibuprofen_shifts,
            top=5,
            output_format="json",
            _silent=True,
        )
        assert result_data is not None, "_perform_ranking returned None for json format"
        assert result_data["total_solutions"] == 392, (
            f"Expected 392 total solutions, got {result_data['total_solutions']}"
        )
        assert result_data["ranked_count"] > 0, "No solutions could be ranked"

    @pytest.mark.skipif(
        shutil.which("LSD") is None,
        reason="LSD binary not installed",
    )
    def test_runner_success_semantics(self, tmp_path: Path) -> None:
        """result.success is True only when .sol exists AND solutions.smi exists.

        Currently FAILS — success is True even with no .sol file written
        (false-positive: success is determined by stderr solution count alone).
        After the fix, success requires sol_file.exists() AND smiles_path is
        not None.
        """
        outlsd_bin = shutil.which("outlsd")
        assert outlsd_bin is not None, "outlsd binary not found on PATH"

        lsd_fixture = FIXTURE_DIR / "ibuprofen_no_4j.lsd"
        runner = LSDRunner()
        result = runner.run_file(lsd_fixture, output_dir=tmp_path, timeout=120)

        sol_file = tmp_path / "ibuprofen_no_4j.sol"
        smiles_file = tmp_path / "solutions.smi"

        # After fix: both files must exist AND result.success must be True
        assert sol_file.exists(), (
            "result.success is True but no .sol file was written — "
            "success is a false-positive from stderr solution count"
        )
        assert smiles_file.exists(), (
            "result.success is True but no solutions.smi was written — "
            "outlsd conversion failed silently"
        )
        assert result.success is True, (
            "result.success must be True when .sol and solutions.smi both exist"
        )

    def test_invoke_outlsd_unit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_invoke_outlsd calls [outlsd_path, '5'] with the .sol file as stdin.

        Currently FAILS with ImportError because _invoke_outlsd does not
        exist yet in runner.py. After Task 2 creates it, this test verifies:
        1. The mock receives argv=[str(outlsd_path), '5'] and stdin=sol_file.
        2. Calling _invoke_outlsd with a non-existent sol_file returns None
           (the open() raises, except block returns None).
        """
        # Import the helper — fails with ImportError until Task 2 adds it
        from ailsa.lsd.runner import _invoke_outlsd  # noqa: F401 (import is the test)

        outlsd_path = Path("/fake/outlsd")

        # Create a fake .sol file with content that mimics a real solution file
        sol_file = tmp_path / "compound.sol"
        sol_file.write_text(
            "# From file: /path/to/compound.lsd\n"
            "; compound\n"
            "#\n"
            "OUTLSD\n"
            "1 1\n"
            " 1  C 4 0 3 3  0   2 2   3 1  10 1   0 0\n"
        )

        captured_calls: list[dict] = []

        def mock_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            captured_calls.append({"args": args, "kwargs": kwargs})
            # Return a mock completed process with valid SMILES-ish output
            class MockResult:
                stdout = "CC(C)Cc1ccc(cc1)C(C)C(=O)O\n"
                returncode = 0
            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_run)

        result_path = _invoke_outlsd(outlsd_path, sol_file, tmp_path)

        # Verify the mock was called with correct arguments
        assert len(captured_calls) == 1, "subprocess.run should be called exactly once"
        call_args = captured_calls[0]["args"][0]  # first positional arg = argv list
        assert call_args[0] == str(outlsd_path), (
            f"Expected first arg to be str(outlsd_path)={str(outlsd_path)!r}, "
            f"got {call_args[0]!r}"
        )
        assert call_args[1] == "5", (
            f"Expected second arg to be '5' (SMILES mode), got {call_args[1]!r}"
        )
        # Verify stdin was the sol_file handle (not text input=...)
        assert "stdin" in captured_calls[0]["kwargs"], (
            "subprocess.run must receive stdin= kwarg (file handle), not input= kwarg"
        )
        assert "input" not in captured_calls[0]["kwargs"], (
            "subprocess.run must NOT receive input= kwarg for outlsd — use stdin= with file handle"
        )

        # Verify solutions.smi was written
        assert result_path is not None, "_invoke_outlsd returned None (stdout was truthy)"
        assert (tmp_path / "solutions.smi").exists()

        # Test None-on-missing-sol path: non-existent sol file → open() raises → None
        missing_sol = tmp_path / "does_not_exist.sol"
        # monkeypatch is still active, but open() on missing file raises before run()
        result_none = _invoke_outlsd(outlsd_path, missing_sol, tmp_path)
        assert result_none is None, (
            "_invoke_outlsd must return None when sol_file does not exist"
        )


class TestInvokeOutlsd:
    """Unit tests for _invoke_outlsd fail-loud behavior (FIX-01B).

    Do not require LSD/outlsd.
    """

    def test_fail_loud_on_error_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_invoke_outlsd raises RuntimeError when outlsd outputs the known error string."""
        sol_file = tmp_path / "compound.sol"
        sol_file.write_text("# header\n")

        def mock_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            class MockResult:
                stdout = "outlsd: This is not a file for OUTLSD.\n"
                returncode = 0

            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_run)

        with pytest.raises(RuntimeError, match="This is not a file for OUTLSD"):
            _invoke_outlsd(Path("/fake/outlsd"), sol_file, tmp_path)

    def test_fail_loud_on_empty_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_invoke_outlsd raises RuntimeError when outlsd produces no output."""
        sol_file = tmp_path / "compound.sol"
        sol_file.write_text("# header\n")

        def mock_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            class MockResult:
                stdout = ""
                returncode = 0

            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_run)

        with pytest.raises(RuntimeError, match="no output"):
            _invoke_outlsd(Path("/fake/outlsd"), sol_file, tmp_path)


# ---------------------------------------------------------------------------
# FIX-01A integration test — add to TestLSDRunnerFixed (append as standalone
# function after class to keep skipif gate readable; pytest collects it correctly)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("lsd") is None,  # matches LSDRunner._find_lsd() which uses "lsd" (lowercase)
    reason="LSD binary not installed",
)
def test_ring_exclusion_lsd_produces_smiles(tmp_path: Path) -> None:
    """run_file() with a ring-exclusion LSD file (DEFF F1/F2) produces valid SMILES.

    Regression for FIX-01A: _execute_lsd must copy ring3/ring4 filter files.
    Fixture: arm_a_ring_excl.lsd (has DEFF F1 "ring3" + DEFF F2 "ring4").
    Expected: 2 solutions, both aromatic (ibuprofen present).
    """
    outlsd_bin = shutil.which("outlsd")
    assert outlsd_bin is not None, "outlsd binary not found on PATH"

    lsd_fixture = FIXTURE_DIR / "arm_a_ring_excl.lsd"
    runner = LSDRunner()
    result = runner.run_file(lsd_fixture, output_dir=tmp_path, timeout=120)
    assert result.success is True, (
        f"LSDResult.success must be True after successful run. stderr: {result.stderr!r}"
    )

    smiles_file = tmp_path / "solutions.smi"
    assert smiles_file.exists(), (
        "solutions.smi not written — ring3/ring4 filter files likely not copied"
    )
    lines = [ln for ln in smiles_file.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2, (
        f"arm_a_ring_excl.lsd should produce exactly 2 solutions, got {len(lines)}. "
        "If 0: LSD failed (filter files missing). If 392: wrong fixture used."
    )
    # Both solutions must be valid SMILES with aromatic atoms
    for line in lines:
        smiles = line.split()[0]
        mol = Chem.MolFromSmiles(smiles)
        assert mol is not None, f"Not valid SMILES: {smiles!r}"
        aromatic_atoms = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
        assert aromatic_atoms >= 6, (
            f"Expected aromatic ring in solution, got {aromatic_atoms} aromatic atoms: "
            f"{smiles!r}"
        )
