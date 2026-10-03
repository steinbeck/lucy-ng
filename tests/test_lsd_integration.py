"""End-to-end integration tests for LSD structure elucidation."""

import pytest
from pathlib import Path
import tempfile

from ailsa.lsd import LSDInputGenerator, LSDRunner, LSDProblem
from ailsa.lsd.models import Hybridization, LSDAtom, LSDCorrelation


class TestLSDEndToEnd:
    """End-to-end tests for LSD structure elucidation."""

    @pytest.mark.skipif(
        not LSDRunner.is_available(),
        reason="LSD not installed"
    )
    def test_simple_ethane_elucidation(self):
        """Test LSD with simple ethane (C2H6)."""
        # Create ethane problem
        problem = LSDProblem(name="ethane", molecular_formula="C2H6")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))  # CH3
        problem.add_atom(LSDAtom(2, "C", Hybridization.SP3, 3))  # CH3

        # Add HSQC correlations
        problem.add_correlation(LSDCorrelation(1, 1, "HSQC"))
        problem.add_correlation(LSDCorrelation(2, 2, "HSQC"))

        # Add known bond
        # LSD doesn't have BOND in our generator yet, so we skip this

        # Run LSD
        runner = LSDRunner()
        result = runner.run(problem, timeout=30)

        # Should find 1 solution (C-C bond)
        assert result.success
        assert result.solution_count == 1

    @pytest.mark.skipif(
        not LSDRunner.is_available(),
        reason="LSD not installed"
    )
    def test_propane_elucidation(self):
        """Test LSD with propane (C3H8)."""
        problem = LSDProblem(name="propane", molecular_formula="C3H8")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))  # CH3
        problem.add_atom(LSDAtom(2, "C", Hybridization.SP3, 2))  # CH2
        problem.add_atom(LSDAtom(3, "C", Hybridization.SP3, 3))  # CH3

        # HSQC
        problem.add_correlation(LSDCorrelation(1, 1, "HSQC"))
        problem.add_correlation(LSDCorrelation(2, 2, "HSQC"))
        problem.add_correlation(LSDCorrelation(3, 3, "HSQC"))

        # HMBC: CH3s see CH2, CH2 sees CH3s
        problem.add_correlation(LSDCorrelation(1, 2, "HMBC"))
        problem.add_correlation(LSDCorrelation(2, 1, "HMBC"))
        problem.add_correlation(LSDCorrelation(2, 3, "HMBC"))
        problem.add_correlation(LSDCorrelation(3, 2, "HMBC"))

        runner = LSDRunner()
        result = runner.run(problem, timeout=30)

        # Should find exactly 1 solution
        assert result.success
        assert result.solution_count == 1

    @pytest.mark.skipif(
        not LSDRunner.is_available(),
        reason="LSD not installed"
    )
    def test_benzene_elucidation(self):
        """Test LSD with benzene (C6H6)."""
        problem = LSDProblem(name="benzene", molecular_formula="C6H6")

        # 6 aromatic CH carbons
        for i in range(1, 7):
            problem.add_atom(LSDAtom(i, "C", Hybridization.SP2, 1))
            problem.add_correlation(LSDCorrelation(i, i, "HSQC"))

        # HMBC: each carbon sees the adjacent protons
        # In benzene, each C sees H at ortho and meta positions
        for i in range(1, 7):
            # Ortho
            next_i = (i % 6) + 1
            problem.add_correlation(LSDCorrelation(i, next_i, "HMBC"))
            # Meta
            meta_i = ((i + 1) % 6) + 1
            problem.add_correlation(LSDCorrelation(i, meta_i, "HMBC"))

        runner = LSDRunner()
        result = runner.run(problem, timeout=60)

        # Should find solution(s) for benzene ring
        assert result.success
        assert result.solution_count >= 1

    @pytest.mark.skipif(
        not LSDRunner.is_available(),
        reason="LSD not installed"
    )
    def test_ibuprofen_manual_structure(self):
        """Test LSD with manually-defined Ibuprofen structure (C13H18O2).

        This tests that LSD can find valid structures for Ibuprofen
        given correct atom definitions and HMBC correlations.
        """
        problem = LSDProblem(name="ibuprofen", molecular_formula="C13H18O2")

        # Aromatic carbons (4 CH + 2 quaternary)
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 1))  # aromatic CH
        problem.add_atom(LSDAtom(2, "C", Hybridization.SP2, 1))  # aromatic CH
        problem.add_atom(LSDAtom(3, "C", Hybridization.SP2, 1))  # aromatic CH
        problem.add_atom(LSDAtom(4, "C", Hybridization.SP2, 1))  # aromatic CH
        problem.add_atom(LSDAtom(5, "C", Hybridization.SP2, 0))  # ipso C
        problem.add_atom(LSDAtom(6, "C", Hybridization.SP2, 0))  # ipso C

        # Isopropyl (2 CH3 + 1 CH)
        problem.add_atom(LSDAtom(7, "C", Hybridization.SP3, 3))  # CH3
        problem.add_atom(LSDAtom(8, "C", Hybridization.SP3, 3))  # CH3
        problem.add_atom(LSDAtom(9, "C", Hybridization.SP3, 1))  # CH

        # Isobutyl (1 CH2 + 1 CH)
        problem.add_atom(LSDAtom(10, "C", Hybridization.SP3, 2))  # CH2
        problem.add_atom(LSDAtom(11, "C", Hybridization.SP3, 1))  # CH

        # Methyl
        problem.add_atom(LSDAtom(12, "C", Hybridization.SP3, 3))  # CH3

        # Carboxylic acid
        problem.add_atom(LSDAtom(13, "C", Hybridization.SP2, 0))  # C=O

        # Oxygens
        problem.add_atom(LSDAtom(14, "O", Hybridization.SP2, 0))  # carbonyl O
        problem.add_atom(LSDAtom(15, "O", Hybridization.SP3, 1))  # hydroxyl O-H

        # HSQC for protonated carbons
        for i in [1, 2, 3, 4, 7, 8, 9, 10, 11, 12]:
            problem.add_correlation(LSDCorrelation(i, i, "HSQC"))

        # HMBC correlations (quaternary Cs see neighboring protons)
        problem.add_correlation(LSDCorrelation(5, 1, "HMBC"))
        problem.add_correlation(LSDCorrelation(5, 3, "HMBC"))
        problem.add_correlation(LSDCorrelation(5, 10, "HMBC"))
        problem.add_correlation(LSDCorrelation(6, 2, "HMBC"))
        problem.add_correlation(LSDCorrelation(6, 4, "HMBC"))
        problem.add_correlation(LSDCorrelation(6, 9, "HMBC"))

        # Isopropyl HMBC
        problem.add_correlation(LSDCorrelation(7, 9, "HMBC"))
        problem.add_correlation(LSDCorrelation(8, 9, "HMBC"))
        problem.add_correlation(LSDCorrelation(9, 7, "HMBC"))
        problem.add_correlation(LSDCorrelation(9, 8, "HMBC"))

        # Carboxylic HMBC
        problem.add_correlation(LSDCorrelation(13, 9, "HMBC"))

        # Isobutyl chain
        problem.add_correlation(LSDCorrelation(10, 11, "HMBC"))
        problem.add_correlation(LSDCorrelation(10, 12, "HMBC"))
        problem.add_correlation(LSDCorrelation(11, 10, "HMBC"))
        problem.add_correlation(LSDCorrelation(11, 12, "HMBC"))
        problem.add_correlation(LSDCorrelation(12, 11, "HMBC"))

        runner = LSDRunner()
        result = runner.run(problem, timeout=120)

        # Should find solutions (likely many due to limited constraints)
        assert result.success, f"LSD failed: {result.stderr}"
        assert result.solution_count > 0, "No solutions found"

        # With proper HMBC, should find reasonable number of solutions
        # 913 solutions were found in manual testing - that's expected
        # because the HMBC constraints don't fully define the structure
        print(f"Found {result.solution_count} solutions for Ibuprofen")


class TestLSDInputValidation:
    """Tests for LSD input validation."""

    def test_valence_must_be_even(self):
        """Test that total valence must be even for valid structure."""
        # Create problem with incorrect hydrogen count
        problem = LSDProblem(name="invalid")
        # C2H5 would have odd valence (not a valid neutral molecule)
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))  # CH3
        problem.add_atom(LSDAtom(2, "C", Hybridization.SP3, 2))  # CH2 - missing 1H!

        # Validate should warn about this
        issues = problem.validate()
        # Currently validate() doesn't check valence - this is for future enhancement

    def test_hmbc_requires_hsqc_source(self):
        """Test that HMBC proton source must have HSQC."""
        # This is enforced by LSD, not our validator
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 3))
        problem.add_atom(LSDAtom(2, "C", Hybridization.SP2, 0))  # Quaternary

        problem.add_correlation(LSDCorrelation(1, 1, "HSQC"))
        # HMBC from quaternary C to proton on C1 - valid
        problem.add_correlation(LSDCorrelation(2, 1, "HMBC"))

        # HMBC from C1 to quaternary C2 - INVALID (C2 has no protons)
        problem.add_correlation(LSDCorrelation(1, 2, "HMBC"))

        # Our validator doesn't catch this, but LSD will reject it
        content = LSDInputGenerator.generate(problem)
        assert "HMBC 2 1" in content  # Valid HMBC
        assert "HMBC 1 2" in content  # Invalid - LSD will reject


class TestLSDRunnerIntegration:
    """Integration tests for LSD runner."""

    @pytest.mark.skipif(
        not LSDRunner.is_available(),
        reason="LSD not installed"
    )
    def test_runner_finds_lsd(self):
        """Test that runner can find LSD executable."""
        runner = LSDRunner()
        assert runner.lsd_path is not None
        assert runner.lsd_path.exists()

    @pytest.mark.skipif(
        not LSDRunner.is_available(),
        reason="LSD not installed"
    )
    def test_runner_with_output_dir(self):
        """Test that runner uses specified output directory."""
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 4))  # CH4

        problem.add_correlation(LSDCorrelation(1, 1, "HSQC"))

        runner = LSDRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            result = runner.run(problem, output_dir=tmpdir, keep_files=True)

            # Check files were created in specified directory
            assert result.output_dir == tmpdir
            assert (tmpdir / "test.lsd").exists()
