"""Tests for LSD solution analyzer."""

import pytest
import tempfile
from pathlib import Path

from lucy_ng.lsd.analyzer import (
    AnalysisResult,
    HMBCCorrelation,
    LSDSolutionAnalyzer,
    SolutionAtom,
    SolutionGraph,
)


class TestSolutionAtom:
    """Tests for SolutionAtom dataclass."""

    def test_create_atom(self):
        """Test creating an atom."""
        atom = SolutionAtom(index=1, element="C", h_count=2, neighbors=[2, 3])
        assert atom.index == 1
        assert atom.element == "C"
        assert atom.h_count == 2
        assert atom.neighbors == [2, 3]

    def test_default_neighbors(self):
        """Test that neighbors default to empty list."""
        atom = SolutionAtom(index=1, element="O", h_count=1)
        assert atom.neighbors == []


class TestSolutionGraph:
    """Tests for SolutionGraph class."""

    def test_create_graph(self):
        """Test creating a molecular graph."""
        graph = SolutionGraph(solution_number=1)
        assert graph.solution_number == 1
        assert len(graph.atoms) == 0

    def test_shortest_path_direct_bond(self):
        """Test shortest path for directly bonded atoms."""
        graph = SolutionGraph(solution_number=1)
        graph.atoms[1] = SolutionAtom(index=1, element="C", h_count=2, neighbors=[2])
        graph.atoms[2] = SolutionAtom(index=2, element="C", h_count=3, neighbors=[1])
        graph._rebuild_adjacency()

        assert graph.shortest_path(1, 2) == 1
        assert graph.shortest_path(2, 1) == 1

    def test_shortest_path_two_bonds(self):
        """Test shortest path for atoms 2 bonds apart."""
        graph = SolutionGraph(solution_number=1)
        graph.atoms[1] = SolutionAtom(index=1, element="C", h_count=2, neighbors=[2])
        graph.atoms[2] = SolutionAtom(index=2, element="C", h_count=2, neighbors=[1, 3])
        graph.atoms[3] = SolutionAtom(index=3, element="C", h_count=3, neighbors=[2])
        graph._rebuild_adjacency()

        assert graph.shortest_path(1, 3) == 2
        assert graph.shortest_path(3, 1) == 2

    def test_shortest_path_same_atom(self):
        """Test shortest path to same atom is 0."""
        graph = SolutionGraph(solution_number=1)
        graph.atoms[1] = SolutionAtom(index=1, element="C", h_count=3, neighbors=[])
        graph._rebuild_adjacency()

        assert graph.shortest_path(1, 1) == 0

    def test_shortest_path_not_found(self):
        """Test shortest path returns -1 for disconnected atoms."""
        graph = SolutionGraph(solution_number=1)
        graph.atoms[1] = SolutionAtom(index=1, element="C", h_count=3, neighbors=[])
        graph.atoms[2] = SolutionAtom(index=2, element="C", h_count=3, neighbors=[])
        graph._rebuild_adjacency()

        assert graph.shortest_path(1, 2) == -1

    def test_shortest_path_ring(self):
        """Test shortest path in a ring (should find shortest)."""
        # Create a 6-membered ring: 1-2-3-4-5-6-1
        graph = SolutionGraph(solution_number=1)
        graph.atoms[1] = SolutionAtom(index=1, element="C", h_count=2, neighbors=[2, 6])
        graph.atoms[2] = SolutionAtom(index=2, element="C", h_count=2, neighbors=[1, 3])
        graph.atoms[3] = SolutionAtom(index=3, element="C", h_count=2, neighbors=[2, 4])
        graph.atoms[4] = SolutionAtom(index=4, element="C", h_count=2, neighbors=[3, 5])
        graph.atoms[5] = SolutionAtom(index=5, element="C", h_count=2, neighbors=[4, 6])
        graph.atoms[6] = SolutionAtom(index=6, element="C", h_count=2, neighbors=[5, 1])
        graph._rebuild_adjacency()

        # Path from 1 to 4 should be 3 (1-2-3-4), not 3 (1-6-5-4)
        assert graph.shortest_path(1, 4) == 3


class TestHMBCCorrelation:
    """Tests for HMBCCorrelation dataclass."""

    def test_j_coupling_from_path_length(self):
        """Test J-coupling calculation."""
        corr = HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=1)
        assert corr.j_coupling == 2  # 1 bond = 2J

        corr = HMBCCorrelation(carbon_idx=1, proton_idx=3, path_length=2)
        assert corr.j_coupling == 3  # 2 bonds = 3J

    def test_j_coupling_none_when_no_path(self):
        """Test J-coupling is None when path_length is None."""
        corr = HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=None)
        assert corr.j_coupling is None

    def test_j_notation_2j(self):
        """Test J notation for 2J coupling."""
        corr = HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=1)
        assert corr.j_notation == "²J_CH"

    def test_j_notation_3j(self):
        """Test J notation for 3J coupling."""
        corr = HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=2)
        assert corr.j_notation == "³J_CH"

    def test_j_notation_4j(self):
        """Test J notation for 4J coupling."""
        corr = HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=3)
        assert corr.j_notation == "⁴J_CH"

    def test_j_notation_unknown(self):
        """Test J notation when path is unknown."""
        corr = HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=None)
        assert corr.j_notation == "?J_CH"


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_all_2j_3j_true(self):
        """Test all_2j_3j returns True when all correlations are 2J/3J."""
        correlations = [
            HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=1),  # 2J
            HMBCCorrelation(carbon_idx=1, proton_idx=3, path_length=2),  # 3J
            HMBCCorrelation(carbon_idx=2, proton_idx=3, path_length=2),  # 3J
        ]
        result = AnalysisResult(
            solution_number=1,
            correlations=correlations,
            graph=SolutionGraph(solution_number=1),
        )
        assert result.all_2j_3j is True

    def test_all_2j_3j_false(self):
        """Test all_2j_3j returns False when there's a 4J or higher."""
        correlations = [
            HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=1),  # 2J
            HMBCCorrelation(carbon_idx=1, proton_idx=3, path_length=3),  # 4J
        ]
        result = AnalysisResult(
            solution_number=1,
            correlations=correlations,
            graph=SolutionGraph(solution_number=1),
        )
        assert result.all_2j_3j is False

    def test_max_j(self):
        """Test max_j returns the maximum J coupling."""
        correlations = [
            HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=1),  # 2J
            HMBCCorrelation(carbon_idx=1, proton_idx=3, path_length=2),  # 3J
            HMBCCorrelation(carbon_idx=2, proton_idx=4, path_length=3),  # 4J
        ]
        result = AnalysisResult(
            solution_number=1,
            correlations=correlations,
            graph=SolutionGraph(solution_number=1),
        )
        assert result.max_j == 4

    def test_summary(self):
        """Test summary includes key information."""
        correlations = [
            HMBCCorrelation(carbon_idx=1, proton_idx=2, path_length=1),  # 2J
            HMBCCorrelation(carbon_idx=1, proton_idx=3, path_length=2),  # 3J
            HMBCCorrelation(carbon_idx=1, proton_idx=3, path_length=2),  # 3J
        ]
        result = AnalysisResult(
            solution_number=1,
            correlations=correlations,
            graph=SolutionGraph(solution_number=1),
        )
        summary = result.summary()
        assert "Solution 1" in summary
        assert "²J" in summary
        assert "³J" in summary


class TestLSDSolutionAnalyzer:
    """Tests for LSDSolutionAnalyzer class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_sol_file(self, temp_dir):
        """Test parsing a .sol file."""
        sol_file = temp_dir / "test.sol"
        sol_file.write_text("""# Comment
OUTLSD
3 1
 1  C 4 2 2 2  0   2 1   0 0   0 0   0 0
 1  C 4 2 2 2  0   1 1   3 1   0 0   0 0
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
0
""")
        solutions = LSDSolutionAnalyzer.parse_sol_file(sol_file)

        assert len(solutions) == 1
        assert solutions[0].solution_number == 1
        assert len(solutions[0].atoms) == 3
        assert solutions[0].atoms[1].element == "C"
        assert solutions[0].atoms[1].h_count == 2
        assert 2 in solutions[0].atoms[1].neighbors

    def test_parse_sol_file_multiple_solutions(self, temp_dir):
        """Test parsing .sol file with multiple solutions."""
        sol_file = temp_dir / "test.sol"
        sol_file.write_text("""OUTLSD
2 1
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
2 2
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
0
""")
        solutions = LSDSolutionAnalyzer.parse_sol_file(sol_file)

        assert len(solutions) == 2
        assert solutions[0].solution_number == 1
        assert solutions[1].solution_number == 2

    def test_parse_lsd_file(self, temp_dir):
        """Test parsing .lsd file for HMBC correlations."""
        lsd_file = temp_dir / "test.lsd"
        lsd_file.write_text("""; Comment
MULT 1 C 2 0
MULT 2 C 2 1
MULT 3 C 3 3
SHIX 1 130.5
SHIX 2 125.0
SHIX 3 20.0
HSQC 2 2
HSQC 3 3
HMBC 1 2
HMBC 1 3
EXIT
""")
        correlations, shifts = LSDSolutionAnalyzer.parse_lsd_file(lsd_file)

        assert len(correlations) == 2
        assert (1, 2) in correlations
        assert (1, 3) in correlations
        assert shifts[1] == 130.5
        assert shifts[2] == 125.0
        assert shifts[3] == 20.0

    def test_analyze(self, temp_dir):
        """Test full analysis of J-coupling paths."""
        # Create a simple 3-atom chain: C1-C2-C3
        sol_file = temp_dir / "test.sol"
        sol_file.write_text("""OUTLSD
3 1
 1  C 4 0 2 2  0   2 1   0 0   0 0   0 0
 1  C 4 1 2 2  0   1 1   3 1   0 0   0 0
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
0
""")

        lsd_file = temp_dir / "test.lsd"
        lsd_file.write_text("""; Test LSD file
MULT 1 C 2 0
MULT 2 C 3 1
MULT 3 C 3 3
SHIX 1 130.0
SHIX 2 40.0
SHIX 3 20.0
HSQC 2 2
HSQC 3 3
HMBC 1 2
HMBC 1 3
EXIT
""")

        results = LSDSolutionAnalyzer.analyze(sol_file, lsd_file)

        assert len(results) == 1
        result = results[0]
        assert result.solution_number == 1
        assert len(result.correlations) == 2

        # HMBC 1 2: C1 to H on C2, path length 1 (directly bonded), so 2J
        hmbc_1_2 = next(c for c in result.correlations if c.carbon_idx == 1 and c.proton_idx == 2)
        assert hmbc_1_2.path_length == 1
        assert hmbc_1_2.j_coupling == 2

        # HMBC 1 3: C1 to H on C3, path length 2 (C1-C2-C3), so 3J
        hmbc_1_3 = next(c for c in result.correlations if c.carbon_idx == 1 and c.proton_idx == 3)
        assert hmbc_1_3.path_length == 2
        assert hmbc_1_3.j_coupling == 3

    def test_analyze_specific_solution(self, temp_dir):
        """Test analyzing only a specific solution."""
        sol_file = temp_dir / "test.sol"
        sol_file.write_text("""OUTLSD
2 1
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
2 2
 1  C 4 3 1 1  0   2 1   0 0   0 0   0 0
 1  C 4 3 1 1  0   1 1   0 0   0 0   0 0
0
""")

        lsd_file = temp_dir / "test.lsd"
        lsd_file.write_text("""MULT 1 C 3 3
MULT 2 C 3 3
HSQC 1 1
HSQC 2 2
HMBC 1 2
EXIT
""")

        results = LSDSolutionAnalyzer.analyze(sol_file, lsd_file, solution_number=2)

        assert len(results) == 1
        assert results[0].solution_number == 2
