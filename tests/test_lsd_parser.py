"""Tests for LSD output parser."""

import pytest
from pathlib import Path
import tempfile

from ailsa.lsd.parser import LSDOutputParser, LSDSolution


class TestLSDSolution:
    """Tests for LSDSolution dataclass."""

    def test_create_solution(self):
        """Test creating a solution."""
        sol = LSDSolution(
            index=1,
            smiles="CC(C)Cc1ccc(cc1)C(C)C(=O)O",
        )
        assert sol.index == 1
        assert sol.smiles == "CC(C)Cc1ccc(cc1)C(C)C(=O)O"

    def test_summary(self):
        """Test solution summary."""
        sol = LSDSolution(
            index=1,
            smiles="C1CCCCC1",
        )
        summary = sol.summary()

        assert "Solution 1" in summary
        assert "C1CCCCC1" in summary


class TestParseSmiles:
    """Tests for parsing SMILES files."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_smiles_file(self, temp_dir):
        """Test parsing a SMILES file with one SMILES per line."""
        smiles_file = temp_dir / "solutions.smi"
        smiles_file.write_text("""CC(C)C
CCC
C1CCCCC1
""")
        solutions = LSDOutputParser.parse_smiles_file(smiles_file)

        assert len(solutions) == 3
        assert solutions[0].index == 1
        assert solutions[0].smiles == "CC(C)C"
        assert solutions[1].index == 2
        assert solutions[1].smiles == "CCC"
        assert solutions[2].index == 3
        assert solutions[2].smiles == "C1CCCCC1"

    def test_parse_smiles_file_with_comments(self, temp_dir):
        """Test that comments are skipped."""
        smiles_file = temp_dir / "solutions.smi"
        smiles_file.write_text("""# This is a comment
CC
; Another comment
CCC
""")
        solutions = LSDOutputParser.parse_smiles_file(smiles_file)

        assert len(solutions) == 2
        assert solutions[0].smiles == "CC"
        assert solutions[1].smiles == "CCC"

    def test_parse_smiles_file_with_empty_lines(self, temp_dir):
        """Test that empty lines are skipped."""
        smiles_file = temp_dir / "solutions.smi"
        smiles_file.write_text("""CC

CCC

C1CCCCC1
""")
        solutions = LSDOutputParser.parse_smiles_file(smiles_file)

        assert len(solutions) == 3

    def test_parse_smiles_file_filters_invalid(self, temp_dir):
        """Test that invalid lines are filtered."""
        smiles_file = temp_dir / "solutions.smi"
        smiles_file.write_text("""CC
This is not a SMILES string!
CCC
More text here with spaces
C1CCCCC1
""")
        solutions = LSDOutputParser.parse_smiles_file(smiles_file)

        # Should only include valid SMILES
        assert len(solutions) == 3
        assert solutions[0].smiles == "CC"
        assert solutions[1].smiles == "CCC"
        assert solutions[2].smiles == "C1CCCCC1"

    def test_parse_smiles_file_empty(self, temp_dir):
        """Test parsing empty file returns empty list."""
        smiles_file = temp_dir / "empty.smi"
        smiles_file.write_text("")

        solutions = LSDOutputParser.parse_smiles_file(smiles_file)

        assert solutions == []

    def test_parse_smiles_file_only_comments(self, temp_dir):
        """Test parsing file with only comments returns empty list."""
        smiles_file = temp_dir / "comments.smi"
        smiles_file.write_text("""# Comment 1
; Comment 2
# Comment 3
""")
        solutions = LSDOutputParser.parse_smiles_file(smiles_file)

        assert solutions == []

    def test_parse_smiles_file_not_found(self):
        """Test parsing non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            LSDOutputParser.parse_smiles_file("/nonexistent/file.smi")

    def test_parse_smiles_file_complex_smiles(self, temp_dir):
        """Test parsing complex SMILES with special characters."""
        smiles_file = temp_dir / "complex.smi"
        smiles_file.write_text("""CC(C)Cc1ccc(cc1)C(C)C(=O)O
[C@@H]1(O)CCC1
C/C=C/C
C#N
""")
        solutions = LSDOutputParser.parse_smiles_file(smiles_file)

        assert len(solutions) == 4
        assert solutions[0].smiles == "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
        assert solutions[1].smiles == "[C@@H]1(O)CCC1"
        assert solutions[2].smiles == "C/C=C/C"
        assert solutions[3].smiles == "C#N"

    def test_parse_outlsd_output_format(self, temp_dir):
        """Test parsing outlsd output (typical format)."""
        # outlsd produces SMILES with one per line
        outlsd_file = temp_dir / "outlsd.out"
        outlsd_file.write_text("""CC(C)Cc1ccc(cc1)C(C)C(=O)O
Cc1ccc(cc1)CC(C)(C)C(=O)O
CC(C)(C)c1ccc(cc1)CC(=O)O
""")
        solutions = LSDOutputParser.parse_smiles_file(outlsd_file)

        assert len(solutions) == 3
        assert solutions[0].index == 1
        assert solutions[1].index == 2
        assert solutions[2].index == 3


class TestParseSummaryOutput:
    """Tests for parsing LSD summary output."""

    def test_parse_summary_output(self):
        """Test parsing LSD summary output."""
        output = "Found 5 solutions in 0.25 seconds"
        stats = LSDOutputParser.parse_summary_output(output)

        assert stats["solution_count"] == 5
        assert stats["execution_time"] == 0.25
        assert stats["status"] == "success"

    def test_parse_summary_no_solution(self):
        """Test parsing output with no solutions."""
        output = "No solution found - contradictory constraints"
        stats = LSDOutputParser.parse_summary_output(output)

        assert stats["solution_count"] == 0
        assert stats["status"] == "no_solution"

    def test_parse_summary_error(self):
        """Test parsing output with error."""
        output = "Error: invalid input format"
        stats = LSDOutputParser.parse_summary_output(output)

        assert stats["status"] == "error"


class TestSolutionsToSmilesList:
    """Tests for utility functions."""

    def test_solutions_to_smiles_list(self):
        """Test extracting SMILES from solutions."""
        solutions = [
            LSDSolution(index=1, smiles="CC"),
            LSDSolution(index=2, smiles="CCC"),
            LSDSolution(index=3, smiles="CCCC"),
        ]

        smiles = LSDOutputParser.solutions_to_smiles_list(solutions)

        assert smiles == ["CC", "CCC", "CCCC"]

    def test_solutions_to_smiles_list_empty(self):
        """Test extracting SMILES from empty list."""
        smiles = LSDOutputParser.solutions_to_smiles_list([])
        assert smiles == []
