"""Tests for PyLSDOrchestrator and SolutionMerger.

TDD RED phase — all tests must fail before implementation.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ailsa.lsd.models import Hybridization, LSDAtom, LSDCorrelation, LSDProblem
from ailsa.lsd.runner import LSDResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_problem(name: str = "test") -> LSDProblem:
    """Create a minimal LSDProblem with atoms and correlations."""
    problem = LSDProblem(name=name, pylsd_mode=True)
    # Add 4 carbon atoms
    for i in range(1, 5):
        problem.add_atom(LSDAtom(
            index=i,
            element="C",
            hybridization=Hybridization.SP2,
            hydrogen_count=1,
        ))
    # Add non-suspect HSQC correlations
    for i in range(1, 5):
        problem.add_correlation(LSDCorrelation(
            atom1_index=i,
            atom2_index=i,
            correlation_type="HSQC",
        ))
    # Add 2 non-suspect HMBC correlations
    problem.add_correlation(LSDCorrelation(
        atom1_index=1,
        atom2_index=2,
        correlation_type="HMBC",
    ))
    problem.add_correlation(LSDCorrelation(
        atom1_index=2,
        atom2_index=3,
        correlation_type="HMBC",
    ))
    return problem


def _make_suspects(n: int, start_atom1: int = 4, start_atom2: int = 8) -> list[LSDCorrelation]:
    """Create N suspect HMBC correlations."""
    suspects = []
    for i in range(n):
        suspects.append(LSDCorrelation(
            atom1_index=start_atom1 + i,
            atom2_index=start_atom2 + i,
            correlation_type="HMBC",
        ))
    return suspects


def _make_lsd_result(solution_count: int = 3) -> LSDResult:
    """Create a fake LSDResult for mocking."""
    return LSDResult(
        success=True,
        solution_count=solution_count,
        return_code=0,
    )


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from ailsa.lsd.orchestrator import (
    OrchestrationResult,
    PermutationResult,
    PyLSDOrchestrator,
)


# ---------------------------------------------------------------------------
# Test: permutation directory generation
# ---------------------------------------------------------------------------

class TestGeneratesPermutationFiles:
    """PyLSDOrchestrator generates 2^K permutation directories."""

    def test_generates_permutation_files(self, tmp_path: Path) -> None:
        """3 suspects → 8 permutation directories, each with an LSD file."""
        problem = _make_problem()
        suspects = _make_suspects(3)
        # Add suspects to problem so they exist to be found during build
        for s in suspects:
            problem.add_atom(LSDAtom(
                index=s.atom1_index,
                element="C",
                hybridization=Hybridization.SP2,
                hydrogen_count=0,
            ))
            problem.add_correlation(s)

        orchestrator = PyLSDOrchestrator()

        with patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()) as mock_run, \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            result = orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        # Exactly 8 permutation directories created
        perm_dirs = sorted((tmp_path / "out").glob("perm_*"))
        assert len(perm_dirs) == 8, f"Expected 8 perm dirs, got {len(perm_dirs)}: {perm_dirs}"

        # Each directory must contain an LSD file
        for perm_dir in perm_dirs:
            lsd_files = list(perm_dir.glob("*.lsd"))
            assert len(lsd_files) == 1, f"{perm_dir.name} should have exactly 1 LSD file"

        # LSD runner was called 8 times
        assert mock_run.call_count == 8

    def test_k1_generates_2_permutations(self, tmp_path: Path) -> None:
        """1 suspect → 2 permutations."""
        problem = _make_problem()
        suspects = _make_suspects(1)
        for s in suspects:
            problem.add_atom(LSDAtom(
                index=s.atom1_index, element="C",
                hybridization=Hybridization.SP2, hydrogen_count=0,
            ))
            problem.add_correlation(s)

        orchestrator = PyLSDOrchestrator()
        with patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            result = orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        perm_dirs = sorted((tmp_path / "out").glob("perm_*"))
        assert len(perm_dirs) == 2


# ---------------------------------------------------------------------------
# Test: permutation content
# ---------------------------------------------------------------------------

class TestPermutationContent:
    """Each permutation correctly includes/excludes suspect correlations."""

    def test_permutation_content(self, tmp_path: Path) -> None:
        """Verify include/exclude per permutation for 2 suspects."""
        problem = _make_problem()
        # Create 2 suspects with distinct atom pairs
        suspect_a = LSDCorrelation(atom1_index=4, atom2_index=8, correlation_type="HMBC")
        suspect_b = LSDCorrelation(atom1_index=6, atom2_index=9, correlation_type="HMBC")
        suspects = [suspect_a, suspect_b]

        # Add atoms for suspects
        for atom_idx in [4, 6, 8, 9]:
            if problem.get_atom_by_index(atom_idx) is None:
                problem.add_atom(LSDAtom(
                    index=atom_idx, element="C",
                    hybridization=Hybridization.SP2, hydrogen_count=0,
                ))
        for s in suspects:
            problem.add_correlation(s)

        orchestrator = PyLSDOrchestrator()
        written_problems: list[LSDProblem] = []

        # Capture the problems passed to write_file
        from ailsa.lsd.generator import LSDInputGenerator
        original_write = LSDInputGenerator.write_file

        def capture_write(prob: LSDProblem, path: Path) -> Path:
            written_problems.append(prob)
            return original_write(prob, path)

        with patch("ailsa.lsd.orchestrator.LSDInputGenerator.write_file", side_effect=capture_write), \
             patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        # 4 permutations for K=2: TT, TF, FT, FF
        assert len(written_problems) == 4

        suspect_a_key = (suspect_a.atom1_index, suspect_a.atom2_index, suspect_a.correlation_type)
        suspect_b_key = (suspect_b.atom1_index, suspect_b.atom2_index, suspect_b.correlation_type)

        def has_correlation(prob: LSDProblem, key: tuple) -> bool:
            return any(
                (c.atom1_index, c.atom2_index, c.correlation_type) == key
                for c in prob.correlations
            )

        def get_max_bonds_for(prob: LSDProblem, key: tuple) -> int | None:
            for c in prob.correlations:
                if (c.atom1_index, c.atom2_index, c.correlation_type) == key:
                    return c.max_bonds
            return None

        # perm_00: TT — both present with max_bonds=4
        p00 = written_problems[0]
        assert has_correlation(p00, suspect_a_key), "perm_00 should include suspect_a"
        assert has_correlation(p00, suspect_b_key), "perm_00 should include suspect_b"
        assert get_max_bonds_for(p00, suspect_a_key) == 4
        assert get_max_bonds_for(p00, suspect_b_key) == 4

        # perm_01: TF — suspect_a present, suspect_b absent
        p01 = written_problems[1]
        assert has_correlation(p01, suspect_a_key), "perm_01 should include suspect_a"
        assert not has_correlation(p01, suspect_b_key), "perm_01 should exclude suspect_b"
        assert get_max_bonds_for(p01, suspect_a_key) == 4

        # perm_03: FF — neither suspect present
        p03 = written_problems[3]
        assert not has_correlation(p03, suspect_a_key), "perm_03 should exclude suspect_a"
        assert not has_correlation(p03, suspect_b_key), "perm_03 should exclude suspect_b"

        # Non-suspect correlations must be preserved in all permutations
        non_suspect_hmbc_keys = {
            (1, 2, "HMBC"),
            (2, 3, "HMBC"),
        }
        for i, prob in enumerate(written_problems):
            for ns_key in non_suspect_hmbc_keys:
                assert has_correlation(prob, ns_key), (
                    f"perm_{i:02d} missing non-suspect HMBC {ns_key}"
                )

    def test_included_suspects_use_extended_bond_range(self, tmp_path: Path) -> None:
        """Suspects that are included must have max_bonds=4."""
        problem = _make_problem()
        suspect = LSDCorrelation(atom1_index=4, atom2_index=8, correlation_type="HMBC",
                                 min_bonds=2, max_bonds=3)
        for atom_idx in [4, 8]:
            problem.add_atom(LSDAtom(
                index=atom_idx, element="C",
                hybridization=Hybridization.SP2, hydrogen_count=0,
            ))
        problem.add_correlation(suspect)

        orchestrator = PyLSDOrchestrator()
        captured: list[LSDProblem] = []

        def capture_write(prob: LSDProblem, path: Path) -> Path:
            from ailsa.lsd.generator import LSDInputGenerator as Gen
            captured.append(prob)
            return Gen.write_file.__wrapped__(prob, path) if hasattr(Gen.write_file, "__wrapped__") else path

        with patch("ailsa.lsd.orchestrator.LSDInputGenerator.write_file", side_effect=lambda p, path: (captured.append(p), path)[1]), \
             patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            orchestrator.run(problem, [suspect], output_dir=tmp_path / "out")

        # perm_00: True → suspect included with max_bonds=4
        assert len(captured) == 2
        key = (suspect.atom1_index, suspect.atom2_index, suspect.correlation_type)
        included_perm = captured[0]
        included_corr = next(
            c for c in included_perm.correlations
            if (c.atom1_index, c.atom2_index, c.correlation_type) == key
        )
        assert included_corr.max_bonds == 4, f"Expected max_bonds=4, got {included_corr.max_bonds}"


# ---------------------------------------------------------------------------
# Test: K>3 raises ValueError
# ---------------------------------------------------------------------------

class TestKCapEnforcement:
    """K > 3 raises ValueError before any I/O."""

    def test_k_greater_than_3_raises(self, tmp_path: Path) -> None:
        """4 suspects → ValueError with message, no directories created."""
        problem = _make_problem()
        suspects = _make_suspects(4)
        orchestrator = PyLSDOrchestrator()

        output_dir = tmp_path / "out"

        with pytest.raises(ValueError, match="Too many suspect correlations"):
            orchestrator.run(problem, suspects, output_dir=output_dir)

        # No directories should be created
        assert not output_dir.exists(), "Output dir should not be created when K>3"

    def test_k5_raises(self, tmp_path: Path) -> None:
        """5 suspects → ValueError."""
        problem = _make_problem()
        suspects = _make_suspects(5)
        orchestrator = PyLSDOrchestrator()

        with pytest.raises(ValueError, match="Too many suspect correlations"):
            orchestrator.run(problem, suspects, output_dir=tmp_path / "out")


# ---------------------------------------------------------------------------
# Test: K boundary cases
# ---------------------------------------------------------------------------

class TestKBoundary:
    """K=3 succeeds (8 perms), K=0 succeeds (1 perm), K=1 produces 2."""

    def test_k3_succeeds_8_permutations(self, tmp_path: Path) -> None:
        """K=3 must succeed and produce 8 permutations."""
        problem = _make_problem()
        suspects = _make_suspects(3)
        for s in suspects:
            problem.add_atom(LSDAtom(
                index=s.atom1_index, element="C",
                hybridization=Hybridization.SP2, hydrogen_count=0,
            ))
            problem.add_correlation(s)

        orchestrator = PyLSDOrchestrator()
        with patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            result = orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        assert len(result.permutation_results) == 8

    def test_k0_succeeds_single_permutation(self, tmp_path: Path) -> None:
        """K=0 suspects → single permutation run with unchanged base problem."""
        problem = _make_problem()
        suspects: list[LSDCorrelation] = []

        orchestrator = PyLSDOrchestrator()
        captured: list[LSDProblem] = []

        with patch("ailsa.lsd.orchestrator.LSDInputGenerator.write_file",
                   side_effect=lambda p, path: (captured.append(p), path)[1]), \
             patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            result = orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        assert len(result.permutation_results) == 1
        # Base problem correlations must be unchanged
        assert len(captured) == 1
        assert len(captured[0].correlations) == len(problem.correlations)

    def test_k1_produces_2_permutations(self, tmp_path: Path) -> None:
        """K=1 → 2 permutations."""
        problem = _make_problem()
        suspects = _make_suspects(1)
        problem.add_atom(LSDAtom(
            index=suspects[0].atom1_index, element="C",
            hybridization=Hybridization.SP2, hydrogen_count=0,
        ))
        problem.add_correlation(suspects[0])

        orchestrator = PyLSDOrchestrator()
        with patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            result = orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        assert len(result.permutation_results) == 2


# ---------------------------------------------------------------------------
# Test: outlsd bypass
# ---------------------------------------------------------------------------

class TestOutlsdBypass:
    """Orchestrator calls subprocess.run([outlsd_path, "5"]) directly."""

    def test_outlsd_bypass_subprocess_call(self, tmp_path: Path) -> None:
        """_run_outlsd uses subprocess.run with [outlsd_path, '5'] and stdin=sol_file."""
        perm_dir = tmp_path / "perm_00"
        perm_dir.mkdir()

        # Create a fake .sol file
        sol_file = perm_dir / "test.sol"
        sol_file.write_text("fake solution data")

        lsd_file = perm_dir / "test.lsd"
        lsd_file.write_text("; fake lsd input")

        # Mock shutil.which to return a fake outlsd path
        fake_outlsd = "/usr/local/bin/outlsd"
        fake_smiles = "CC(C)Cc1ccc(C(C)C(=O)O)cc1\nCCCCC\n"

        mock_proc = MagicMock()
        mock_proc.stdout = fake_smiles
        mock_proc.returncode = 0

        orchestrator = PyLSDOrchestrator()

        with patch("ailsa.lsd.orchestrator.shutil.which", return_value=fake_outlsd), \
             patch("ailsa.lsd.orchestrator.subprocess.run", return_value=mock_proc) as mock_subproc:
            result_path = orchestrator._run_outlsd(perm_dir, lsd_file)

        # Verify subprocess.run was called with [outlsd_path, "5"]
        assert mock_subproc.called
        call_args = mock_subproc.call_args
        cmd = call_args[0][0]  # First positional arg = command list
        assert cmd[0] == fake_outlsd, f"Expected outlsd path, got {cmd[0]}"
        assert cmd[1] == "5", f"Expected mode '5', got {cmd[1]}"

        # SMILES file should be written
        assert result_path is not None
        smiles_file = perm_dir / "solutions.smi"
        assert smiles_file.exists()
        assert smiles_file.read_text() == fake_smiles

    def test_outlsd_returns_none_when_no_outlsd(self, tmp_path: Path) -> None:
        """_run_outlsd returns None when outlsd not available."""
        perm_dir = tmp_path / "perm_00"
        perm_dir.mkdir()
        lsd_file = perm_dir / "test.lsd"

        orchestrator = PyLSDOrchestrator()
        with patch("ailsa.lsd.orchestrator.shutil.which", return_value=None):
            result = orchestrator._run_outlsd(perm_dir, lsd_file)

        assert result is None

    def test_outlsd_returns_none_when_no_sol_file(self, tmp_path: Path) -> None:
        """_run_outlsd returns None when no .sol file in perm_dir."""
        perm_dir = tmp_path / "perm_00"
        perm_dir.mkdir()
        lsd_file = perm_dir / "test.lsd"

        orchestrator = PyLSDOrchestrator()
        with patch("ailsa.lsd.orchestrator.shutil.which", return_value="/usr/bin/outlsd"):
            result = orchestrator._run_outlsd(perm_dir, lsd_file)

        assert result is None


# ---------------------------------------------------------------------------
# Test: PermutationResult structure
# ---------------------------------------------------------------------------

class TestPermutationResultStructure:
    """Each PermutationResult has the required fields."""

    def test_permutation_result_structure(self, tmp_path: Path) -> None:
        """PermutationResult has all required fields."""
        problem = _make_problem()
        suspects = _make_suspects(2)
        for s in suspects:
            problem.add_atom(LSDAtom(
                index=s.atom1_index, element="C",
                hybridization=Hybridization.SP2, hydrogen_count=0,
            ))
            problem.add_correlation(s)

        orchestrator = PyLSDOrchestrator()
        with patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            result = orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        assert len(result.permutation_results) == 4
        for perm_result in result.permutation_results:
            # Check required fields exist and have correct types
            assert isinstance(perm_result.perm_index, int)
            assert isinstance(perm_result.include_flags, list)
            assert all(isinstance(f, bool) for f in perm_result.include_flags)
            assert isinstance(perm_result.suspect_correlations, list)
            assert isinstance(perm_result.lsd_result, LSDResult)
            # smiles_file may be None or Path
            assert perm_result.smiles_file is None or isinstance(perm_result.smiles_file, Path)
            assert isinstance(perm_result.perm_dir, Path)
            assert perm_result.perm_dir.exists()

        # Indices are sequential 0..3
        indices = [r.perm_index for r in result.permutation_results]
        assert indices == [0, 1, 2, 3]

        # include_flags has length K=2
        for r in result.permutation_results:
            assert len(r.include_flags) == 2


# ---------------------------------------------------------------------------
# Test: SolutionMerger — deduplication
# ---------------------------------------------------------------------------

class TestSolutionMerger:
    """SolutionMerger deduplicates solutions via InChI key."""

    def _make_perm_result(
        self,
        perm_index: int,
        smiles_file: Path | None,
        include_flags: list[bool],
    ) -> PermutationResult:
        suspects = _make_suspects(len(include_flags))
        return PermutationResult(
            perm_index=perm_index,
            include_flags=include_flags,
            suspect_correlations=suspects,
            lsd_result=_make_lsd_result(),
            smiles_file=smiles_file,
            perm_dir=Path("/fake"),
        )

    def test_deduplication(self, tmp_path: Path) -> None:
        """Same structure in 3 permutations → appears once in merged output."""
        from ailsa.lsd.orchestrator import SolutionMerger

        # Ethanol SMILES variants (same InChI, different notation)
        ethanol_smiles = ["CCO", "OCC", "C(C)O"]

        perm_results = []
        for i, smi in enumerate(ethanol_smiles):
            smi_file = tmp_path / f"perm_{i:02d}" / "solutions.smi"
            smi_file.parent.mkdir()
            smi_file.write_text(smi + "\n")
            perm_results.append(self._make_perm_result(i, smi_file, [i % 2 == 0]))

        merger = SolutionMerger()
        merge_result = merger.merge(perm_results, output_dir=tmp_path / "merged")

        # All 3 are ethanol → should deduplicate to 1
        assert len(merge_result.merged_solutions) == 1
        assert merge_result.merged_solutions[0].provenance is not None
        assert len(merge_result.merged_solutions[0].provenance) == 3

    def test_merged_smi_written(self, tmp_path: Path) -> None:
        """merged.smi written with correct count of unique SMILES."""
        from ailsa.lsd.orchestrator import SolutionMerger

        # Two distinct molecules: ethanol + ibuprofen
        molecules = [
            ("CCO", tmp_path / "perm_00"),
            ("CC(C)Cc1ccc(C(C)C(=O)O)cc1", tmp_path / "perm_01"),
        ]

        perm_results = []
        for i, (smi, perm_dir) in enumerate(molecules):
            perm_dir.mkdir()
            smi_file = perm_dir / "solutions.smi"
            smi_file.write_text(smi + "\n")
            perm_results.append(self._make_perm_result(i, smi_file, [True]))

        merger = SolutionMerger()
        output_dir = tmp_path / "merged"
        merge_result = merger.merge(perm_results, output_dir=output_dir)

        # merged.smi should exist with 2 SMILES
        assert merge_result.merged_smi.exists()
        lines = [l for l in merge_result.merged_smi.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 2

    def test_skips_permutations_without_smiles_file(self, tmp_path: Path) -> None:
        """Permutation results without smiles_file are skipped gracefully."""
        from ailsa.lsd.orchestrator import SolutionMerger

        smi_file = tmp_path / "perm_00" / "solutions.smi"
        smi_file.parent.mkdir()
        smi_file.write_text("CCO\n")

        perm_results = [
            self._make_perm_result(0, smi_file, [True]),
            self._make_perm_result(1, None, [False]),  # No SMILES file
        ]

        merger = SolutionMerger()
        merge_result = merger.merge(perm_results, output_dir=tmp_path / "merged")

        assert len(merge_result.merged_solutions) == 1


# ---------------------------------------------------------------------------
# Test: run_report.json provenance
# ---------------------------------------------------------------------------

class TestRunReportProvenance:
    """run_report.json contains full provenance per solution."""

    def _make_smi_file(self, path: Path, smiles: list[str]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(smiles) + "\n")
        return path

    def test_run_report_provenance(self, tmp_path: Path) -> None:
        """run_report.json has perm_index, include_flags, active_correlations."""
        from ailsa.lsd.orchestrator import SolutionMerger

        suspects = [
            LSDCorrelation(atom1_index=4, atom2_index=8, correlation_type="HMBC"),
            LSDCorrelation(atom1_index=6, atom2_index=9, correlation_type="HMBC"),
        ]

        # Two permutations with different molecules
        smi0 = self._make_smi_file(tmp_path / "perm_00" / "solutions.smi", ["CCO"])
        smi1 = self._make_smi_file(tmp_path / "perm_01" / "solutions.smi", ["CCCO"])

        perm_results = [
            PermutationResult(
                perm_index=0,
                include_flags=[True, True],
                suspect_correlations=suspects,
                lsd_result=_make_lsd_result(1),
                smiles_file=smi0,
                perm_dir=tmp_path / "perm_00",
            ),
            PermutationResult(
                perm_index=1,
                include_flags=[True, False],
                suspect_correlations=suspects,
                lsd_result=_make_lsd_result(1),
                smiles_file=smi1,
                perm_dir=tmp_path / "perm_01",
            ),
        ]

        merger = SolutionMerger()
        merge_result = merger.merge(perm_results, output_dir=tmp_path / "merged")

        assert merge_result.run_report.exists()
        report = json.loads(merge_result.run_report.read_text())

        assert report["total_permutations"] == 2
        assert report["unique_solutions"] == 2

        # Each solution has provenance with required fields
        for sol in report["solutions"]:
            assert "inchi_key" in sol
            assert "smiles" in sol
            assert "provenance" in sol
            for prov in sol["provenance"]:
                assert "perm_index" in prov
                assert "include_flags" in prov
                assert "active_correlations" in prov

    def test_multi_perm_provenance(self, tmp_path: Path) -> None:
        """Structure in 3 permutations → 3 provenance entries in report."""
        from ailsa.lsd.orchestrator import SolutionMerger

        suspects = [LSDCorrelation(atom1_index=4, atom2_index=8, correlation_type="HMBC")]

        # Same molecule (ethanol) in 3 permutations
        perm_results = []
        for i in range(3):
            smi_file = self._make_smi_file(
                tmp_path / f"perm_{i:02d}" / "solutions.smi",
                ["CCO"],
            )
            perm_results.append(PermutationResult(
                perm_index=i,
                include_flags=[i % 2 == 0],
                suspect_correlations=suspects,
                lsd_result=_make_lsd_result(1),
                smiles_file=smi_file,
                perm_dir=tmp_path / f"perm_{i:02d}",
            ))

        merger = SolutionMerger()
        merge_result = merger.merge(perm_results, output_dir=tmp_path / "merged")

        report = json.loads(merge_result.run_report.read_text())
        assert len(report["solutions"]) == 1
        assert len(report["solutions"][0]["provenance"]) == 3


# ---------------------------------------------------------------------------
# Test: SolutionMerger — invalid SMILES and empty file handling
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test: Permutation constraint preservation
# ---------------------------------------------------------------------------


class TestPermutationConstraintPreservation:
    """Permutation .lsd files carry the FULL constraint set from base_problem.

    D-03 permutation path: PyLSDOrchestrator._build_permutation() uses
    copy.deepcopy(base_problem), so any new fields (constraints, ring_exclusion_enabled)
    propagate to every permutation file automatically.

    These tests prove this structural property by writing real perm files to
    disk and inspecting their content.
    """

    def test_perm_preserves_bond_constraints(self, tmp_path: Path) -> None:
        """Every perm_NN/compound.lsd contains BOND 10 11 and BOND 10 12.

        base_problem has BOND constraints on atoms 10→11 and 10→12 (gem-dimethyl).
        K=2 suspects → 4 permutations.  Every perm must carry both BOND lines.
        """
        problem = _make_problem()  # atoms 1-4, HSQC 1-4, HMBC 1-2 and 2-3

        # Add gem-dimethyl atoms and BOND constraints
        for idx in [10, 11, 12]:
            problem.add_atom(LSDAtom(
                index=idx,
                element="C",
                hybridization=Hybridization.SP3,
                hydrogen_count=1 if idx == 10 else 3,
            ))
        problem.add_equivalence_pair(parent_index=10, child1_index=11, child2_index=12)

        # Add 2 suspect HMBC correlations (start_atom1=5, start_atom2=9 to avoid overlap)
        suspects = _make_suspects(2, start_atom1=5, start_atom2=9)
        for s in suspects:
            for atom_idx in [s.atom1_index, s.atom2_index]:
                if problem.get_atom_by_index(atom_idx) is None:
                    problem.add_atom(LSDAtom(
                        index=atom_idx,
                        element="C",
                        hybridization=Hybridization.SP2,
                        hydrogen_count=0,
                    ))
            problem.add_correlation(s)

        orchestrator = PyLSDOrchestrator()
        with patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        perm_dirs = sorted((tmp_path / "out").glob("perm_*"))
        assert len(perm_dirs) == 4, f"Expected 4 perm dirs (K=2), got {len(perm_dirs)}"

        for perm_dir in perm_dirs:
            lsd_files = list(perm_dir.glob("*.lsd"))
            assert len(lsd_files) == 1, f"{perm_dir.name} should have exactly 1 LSD file"
            content = lsd_files[0].read_text()
            assert "BOND 10 11" in content, (
                f"{perm_dir.name}/compound.lsd missing BOND 10 11 (gem-dimethyl constraint lost)\n"
                f"Content:\n{content}"
            )
            assert "BOND 10 12" in content, (
                f"{perm_dir.name}/compound.lsd missing BOND 10 12 (gem-dimethyl constraint lost)\n"
                f"Content:\n{content}"
            )

    def test_perm_preserves_ring_exclusion(self, tmp_path: Path) -> None:
        """Every perm_NN/compound.lsd contains 'DEFF F1 "ring3"' and filter files.

        base_problem with ring_exclusion_enabled=True.
        K=1 suspect → 2 permutations.
        Each perm dir must contain: ring3, ring4 filter files AND DEFF/FEXP in the .lsd.
        """
        problem = _make_problem()
        problem.ring_exclusion_enabled = True

        # K=1 suspect (start_atom1=5 to avoid overlap with _make_problem atoms 1-4)
        suspects = _make_suspects(1, start_atom1=5, start_atom2=9)
        for s in suspects:
            for atom_idx in [s.atom1_index, s.atom2_index]:
                if problem.get_atom_by_index(atom_idx) is None:
                    problem.add_atom(LSDAtom(
                        index=atom_idx,
                        element="C",
                        hybridization=Hybridization.SP2,
                        hydrogen_count=0,
                    ))
            problem.add_correlation(s)

        orchestrator = PyLSDOrchestrator()
        with patch.object(orchestrator.runner, "run_file", return_value=_make_lsd_result()), \
             patch.object(orchestrator, "_run_outlsd", return_value=None):
            orchestrator.run(problem, suspects, output_dir=tmp_path / "out")

        perm_dirs = sorted((tmp_path / "out").glob("perm_*"))
        assert len(perm_dirs) == 2, f"Expected 2 perm dirs (K=1), got {len(perm_dirs)}"

        for perm_dir in perm_dirs:
            # Check .lsd file contains DEFF/FEXP lines
            lsd_files = list(perm_dir.glob("*.lsd"))
            assert len(lsd_files) == 1, f"{perm_dir.name} should have exactly 1 LSD file"
            content = lsd_files[0].read_text()
            assert 'DEFF F1 "ring3"' in content, (
                f"{perm_dir.name}/compound.lsd missing ring exclusion filter DEFF F1\n"
                f"Content:\n{content}"
            )
            assert 'FEXP "NOT F1 AND NOT F2"' in content, (
                f"{perm_dir.name}/compound.lsd missing FEXP line\n"
                f"Content:\n{content}"
            )

            # Check ring3 and ring4 filter files are present in perm dir
            assert (perm_dir / "ring3").exists(), (
                f"{perm_dir.name}/ring3 filter file missing — "
                f"write_file() must copy filter files to perm_dir"
            )
            assert (perm_dir / "ring4").exists(), (
                f"{perm_dir.name}/ring4 filter file missing"
            )


class TestSolutionMergerPostFix:
    """SolutionMerger post-Phase-73: non-empty smiles files produce non-zero results.

    Phase 73 fixed _invoke_outlsd so per-permutation solutions.smi files are
    populated with real SMILES lines (not just the 10-line outlsd header).
    This test confirms that SolutionMerger.merge() correctly collects those
    solutions — total_raw_solutions > 0 and merged.smi is non-empty.
    """

    def _make_perm_result(
        self,
        perm_index: int,
        smiles_file: Path | None,
        include_flags: list[bool],
    ) -> PermutationResult:
        suspects = _make_suspects(len(include_flags))
        return PermutationResult(
            perm_index=perm_index,
            include_flags=include_flags,
            suspect_correlations=suspects,
            lsd_result=_make_lsd_result(),
            smiles_file=smiles_file,
            perm_dir=Path("/fake"),
        )

    def test_merger_collects_from_non_empty_smiles_files(self, tmp_path: Path) -> None:
        """SolutionMerger given two PermutationResult objects with real SMILES files
        collects non-zero total_raw_solutions and non-empty merged.smi.

        This is the post-Phase-73 correctness test: with outlsd producing real
        SMILES content (not just a header), the merge pipeline works correctly.
        """
        from ailsa.lsd.orchestrator import SolutionMerger
        import json

        # Two distinct real molecules — not deduplicated (different InChI keys)
        molecules = [
            ("CCO", tmp_path / "perm_00"),          # ethanol
            ("CCCO", tmp_path / "perm_01"),          # propanol
        ]

        perm_results = []
        for i, (smi, perm_dir) in enumerate(molecules):
            perm_dir.mkdir()
            smi_file = perm_dir / "solutions.smi"
            smi_file.write_text(smi + "\n")
            perm_results.append(self._make_perm_result(i, smi_file, [True]))

        merger = SolutionMerger()
        output_dir = tmp_path / "merged"
        merge_result = merger.merge(perm_results, output_dir=output_dir)

        # merged.smi must be non-empty
        assert merge_result.merged_smi.exists()
        smi_content = merge_result.merged_smi.read_text().strip()
        assert smi_content, "merged.smi should not be empty"

        # total_raw_solutions in run_report must be >= 2 (1 from each perm)
        report = json.loads(merge_result.run_report.read_text())
        assert report["total_raw_solutions"] >= 2, (
            f"Expected total_raw_solutions >= 2, got {report['total_raw_solutions']}"
        )

        # unique_solutions = 2 (both ethanol and propanol are distinct)
        assert report["unique_solutions"] == 2

        # merged_solutions in result object is non-empty
        assert len(merge_result.merged_solutions) >= 2, (
            "merge_result.merged_solutions should have >= 2 entries"
        )


class TestSolutionMergerEdgeCases:
    """SolutionMerger handles invalid SMILES and missing files gracefully."""

    def _make_perm_result(
        self,
        perm_index: int,
        smiles_file: Path | None,
        include_flags: list[bool],
    ) -> PermutationResult:
        suspects = _make_suspects(len(include_flags))
        return PermutationResult(
            perm_index=perm_index,
            include_flags=include_flags,
            suspect_correlations=suspects,
            lsd_result=_make_lsd_result(),
            smiles_file=smiles_file,
            perm_dir=Path("/fake"),
        )

    def test_invalid_smiles_skipped(self, tmp_path: Path) -> None:
        """SMILES file containing an invalid SMILES string is skipped without error."""
        from ailsa.lsd.orchestrator import SolutionMerger

        # Write a file with one invalid SMILES and one valid SMILES
        smi_file_invalid = tmp_path / "perm_00" / "solutions.smi"
        smi_file_invalid.parent.mkdir()
        smi_file_invalid.write_text("INVALID_XYZ\n")

        smi_file_valid = tmp_path / "perm_01" / "solutions.smi"
        smi_file_valid.parent.mkdir()
        smi_file_valid.write_text("CCO\n")

        perm_results = [
            self._make_perm_result(0, smi_file_invalid, [True]),
            self._make_perm_result(1, smi_file_valid, [False]),
        ]

        merger = SolutionMerger()
        # Should not raise — invalid SMILES is silently skipped
        merge_result = merger.merge(perm_results, output_dir=tmp_path / "merged")

        # Only valid ethanol should appear in output
        assert len(merge_result.merged_solutions) == 1
        # merged.smi must not contain "INVALID_XYZ"
        merged_content = merge_result.merged_smi.read_text()
        assert "INVALID_XYZ" not in merged_content

    def test_empty_smiles_file(self, tmp_path: Path) -> None:
        """Permutation with smiles_file=None is skipped gracefully."""
        from ailsa.lsd.orchestrator import SolutionMerger

        smi_file = tmp_path / "perm_00" / "solutions.smi"
        smi_file.parent.mkdir()
        smi_file.write_text("CCO\n")

        perm_results = [
            self._make_perm_result(0, smi_file, [True]),
            self._make_perm_result(1, None, [False]),  # No SMILES file
        ]

        merger = SolutionMerger()
        merge_result = merger.merge(perm_results, output_dir=tmp_path / "merged")

        # Only ethanol from perm 0 should appear
        assert len(merge_result.merged_solutions) == 1
        # Report must still account for both permutations
        report = json.loads(merge_result.run_report.read_text())
        assert report["total_permutations"] == 2
