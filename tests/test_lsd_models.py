"""Tests for LSD data models."""

import pytest

from ailsa.lsd.models import Hybridization, LSDAtom, LSDConstraint, LSDCorrelation, LSDProblem


class TestHybridization:
    """Tests for Hybridization enum."""

    def test_hybridization_values(self):
        """Test hybridization enum values match LSD format."""
        assert Hybridization.SP.value == 1
        assert Hybridization.SP2.value == 2
        assert Hybridization.SP3.value == 3


class TestLSDAtom:
    """Tests for LSDAtom dataclass."""

    def test_create_carbon_sp2(self):
        """Test creating sp2 carbon atom."""
        atom = LSDAtom(index=1, element="C", hybridization=Hybridization.SP2, hydrogen_count=0)
        assert atom.index == 1
        assert atom.element == "C"
        assert atom.hybridization == Hybridization.SP2
        assert atom.hydrogen_count == 0
        assert atom.charge == 0

    def test_create_carbon_sp3_with_hydrogens(self):
        """Test creating sp3 carbon with hydrogens."""
        atom = LSDAtom(index=2, element="C", hybridization=Hybridization.SP3, hydrogen_count=2)
        assert atom.hydrogen_count == 2

    def test_create_nitrogen_with_charge(self):
        """Test creating charged nitrogen."""
        atom = LSDAtom(
            index=3, element="N", hybridization=Hybridization.SP3,
            hydrogen_count=4, charge=1
        )
        assert atom.element == "N"
        assert atom.charge == 1

    def test_invalid_element_raises(self):
        """Test that invalid element raises ValueError."""
        with pytest.raises(ValueError, match="Invalid element"):
            LSDAtom(index=1, element="X", hybridization=Hybridization.SP3, hydrogen_count=0)

    def test_invalid_index_raises(self):
        """Test that index < 1 raises ValueError."""
        with pytest.raises(ValueError, match="index must be >= 1"):
            LSDAtom(index=0, element="C", hybridization=Hybridization.SP3, hydrogen_count=0)

    def test_invalid_hydrogen_count_raises(self):
        """Test that negative hydrogen count raises ValueError."""
        with pytest.raises(ValueError, match="Hydrogen count"):
            LSDAtom(index=1, element="C", hybridization=Hybridization.SP3, hydrogen_count=-1)

    def test_invalid_charge_raises(self):
        """Test that invalid charge raises ValueError."""
        with pytest.raises(ValueError, match="Charge"):
            LSDAtom(index=1, element="C", hybridization=Hybridization.SP3, hydrogen_count=0, charge=3)

    def test_to_mult_line_basic(self):
        """Test MULT line generation without charge."""
        atom = LSDAtom(index=1, element="C", hybridization=Hybridization.SP2, hydrogen_count=0)
        assert atom.to_mult_line() == "MULT 1 C 2 0"

    def test_to_mult_line_with_hydrogens(self):
        """Test MULT line with hydrogens."""
        atom = LSDAtom(index=5, element="C", hybridization=Hybridization.SP3, hydrogen_count=3)
        assert atom.to_mult_line() == "MULT 5 C 3 3"

    def test_to_mult_line_with_charge(self):
        """Test MULT line with charge."""
        atom = LSDAtom(
            index=2, element="N", hybridization=Hybridization.SP3,
            hydrogen_count=4, charge=1
        )
        assert atom.to_mult_line() == "MULT 2 N 3 4 1"

    def test_chemical_shifts(self):
        """Test storing chemical shift values."""
        atom = LSDAtom(
            index=1, element="C", hybridization=Hybridization.SP2,
            hydrogen_count=1, carbon_shift=129.5, proton_shift=7.25
        )
        assert atom.carbon_shift == 129.5
        assert atom.proton_shift == 7.25


class TestLSDConstraint:
    """Tests for LSDConstraint dataclass."""

    def test_create_bond_constraint(self):
        """Test creating BOND constraint."""
        constraint = LSDConstraint(atom1_index=1, atom2_index=10, constraint_type="BOND")
        assert constraint.atom1_index == 1
        assert constraint.atom2_index == 10
        assert constraint.constraint_type == "BOND"
        assert constraint.reason is None

    def test_create_fbnd_constraint(self):
        """Test creating FBND (forbidden bond) constraint."""
        constraint = LSDConstraint(
            atom1_index=2, atom2_index=3,
            constraint_type="FBND",
            reason="Forbidden due to distance"
        )
        assert constraint.constraint_type == "FBND"
        assert constraint.reason == "Forbidden due to distance"

    def test_invalid_constraint_type_raises(self):
        """Test that invalid constraint type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid constraint type"):
            LSDConstraint(atom1_index=1, atom2_index=2, constraint_type="INVALID")

    def test_invalid_index_raises(self):
        """Test that index < 1 raises ValueError."""
        with pytest.raises(ValueError, match="indices must be >= 1"):
            LSDConstraint(atom1_index=0, atom2_index=1, constraint_type="BOND")

    def test_to_lsd_line_bond(self):
        """Test BOND constraint line generation."""
        constraint = LSDConstraint(atom1_index=1, atom2_index=14, constraint_type="BOND")
        assert constraint.to_lsd_line() == "BOND 1 14"

    def test_to_lsd_line_fbnd(self):
        """Test FBND constraint line generation."""
        constraint = LSDConstraint(atom1_index=2, atom2_index=3, constraint_type="FBND")
        assert constraint.to_lsd_line() == "FBND 2 3"


class TestLSDCorrelation:
    """Tests for LSDCorrelation dataclass."""

    def test_create_hsqc_correlation(self):
        """Test creating HSQC correlation."""
        corr = LSDCorrelation(atom1_index=1, atom2_index=1, correlation_type="HSQC")
        assert corr.correlation_type == "HSQC"

    def test_create_hmbc_correlation(self):
        """Test creating HMBC correlation with bond distances."""
        corr = LSDCorrelation(
            atom1_index=1, atom2_index=2, correlation_type="HMBC",
            min_bonds=2, max_bonds=3
        )
        assert corr.min_bonds == 2
        assert corr.max_bonds == 3

    def test_create_cosy_correlation(self):
        """Test creating COSY correlation."""
        corr = LSDCorrelation(atom1_index=2, atom2_index=3, correlation_type="COSY")
        assert corr.correlation_type == "COSY"

    def test_invalid_type_raises(self):
        """Test that invalid correlation type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid correlation type"):
            LSDCorrelation(atom1_index=1, atom2_index=2, correlation_type="INVALID")

    def test_invalid_index_raises(self):
        """Test that index < 1 raises ValueError."""
        with pytest.raises(ValueError, match="indices must be >= 1"):
            LSDCorrelation(atom1_index=0, atom2_index=1, correlation_type="HSQC")

    def test_to_lsd_line_hsqc(self):
        """Test HSQC line generation."""
        corr = LSDCorrelation(atom1_index=4, atom2_index=4, correlation_type="HSQC")
        assert corr.to_lsd_line() == "HSQC 4 4"

    def test_to_lsd_line_hmbc(self):
        """Test HMBC line generation (2 params, LSD defaults to 2-3 bonds)."""
        corr = LSDCorrelation(
            atom1_index=1, atom2_index=3, correlation_type="HMBC",
            min_bonds=2, max_bonds=3
        )
        # LSD HMBC uses just 2 parameters; bond distance defaults to 2-3
        assert corr.to_lsd_line() == "HMBC 1 3"

    def test_to_lsd_line_cosy(self):
        """Test COSY line generation."""
        corr = LSDCorrelation(atom1_index=2, atom2_index=5, correlation_type="COSY")
        assert corr.to_lsd_line() == "COSY 2 5"

    def test_to_lsd_line_hmbc_extended(self):
        """Test HMBC extended bond range emits 4-parameter form."""
        # max_bonds=4 triggers extended syntax
        corr = LSDCorrelation(atom1_index=1, atom2_index=2, correlation_type="HMBC",
                              min_bonds=2, max_bonds=4)
        assert corr.to_lsd_line() == "HMBC 1 2 2 4"

    def test_to_lsd_line_hmbc_extended_non_standard_min(self):
        """Test HMBC with non-standard min_bonds also emits 4-parameter form."""
        corr = LSDCorrelation(atom1_index=5, atom2_index=8, correlation_type="HMBC",
                              min_bonds=3, max_bonds=4)
        assert corr.to_lsd_line() == "HMBC 5 8 3 4"

    def test_to_lsd_line_hsqc_unaffected_by_bond_range(self):
        """Test HSQC is unaffected by bond range parameters."""
        corr = LSDCorrelation(atom1_index=1, atom2_index=1, correlation_type="HSQC")
        assert corr.to_lsd_line() == "HSQC 1 1"

    def test_to_lsd_line_cosy_unaffected_by_bond_range(self):
        """Test COSY is unaffected by bond range parameters."""
        corr = LSDCorrelation(atom1_index=2, atom2_index=5, correlation_type="COSY")
        assert corr.to_lsd_line() == "COSY 2 5"


class TestLSDProblem:
    """Tests for LSDProblem dataclass."""

    def test_create_empty_problem(self):
        """Test creating empty problem."""
        problem = LSDProblem(name="test")
        assert problem.name == "test"
        assert len(problem.atoms) == 0
        assert len(problem.correlations) == 0

    def test_add_atom(self):
        """Test adding atoms to problem."""
        problem = LSDProblem()
        atom = LSDAtom(index=1, element="C", hybridization=Hybridization.SP2, hydrogen_count=0)
        problem.add_atom(atom)
        assert len(problem.atoms) == 1

    def test_add_correlation(self):
        """Test adding correlations to problem."""
        problem = LSDProblem()
        corr = LSDCorrelation(atom1_index=1, atom2_index=1, correlation_type="HSQC")
        problem.add_correlation(corr)
        assert len(problem.correlations) == 1

    def test_get_atom_by_index(self):
        """Test retrieving atom by index."""
        problem = LSDProblem()
        atom = LSDAtom(index=5, element="C", hybridization=Hybridization.SP3, hydrogen_count=2)
        problem.add_atom(atom)

        found = problem.get_atom_by_index(5)
        assert found is atom

        not_found = problem.get_atom_by_index(99)
        assert not_found is None

    def test_get_correlations_for_atom(self):
        """Test getting correlations for a specific atom."""
        problem = LSDProblem()
        problem.add_correlation(LSDCorrelation(1, 1, "HSQC"))
        problem.add_correlation(LSDCorrelation(1, 2, "HMBC"))
        problem.add_correlation(LSDCorrelation(2, 3, "COSY"))

        corrs = problem.get_correlations_for_atom(1)
        assert len(corrs) == 2

    def test_carbon_count(self):
        """Test carbon count property."""
        problem = LSDProblem()
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 0))
        problem.add_atom(LSDAtom(2, "C", Hybridization.SP3, 2))
        problem.add_atom(LSDAtom(3, "O", Hybridization.SP3, 1))

        assert problem.carbon_count == 2
        assert problem.heteroatom_count == 1

    def test_validate_duplicate_indices(self):
        """Test validation catches duplicate atom indices."""
        problem = LSDProblem()
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 0))
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP3, 2))  # Duplicate

        issues = problem.validate()
        assert any("Duplicate" in issue for issue in issues)

    def test_validate_missing_correlation_atom(self):
        """Test validation catches correlations to non-existent atoms."""
        problem = LSDProblem()
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 0))
        problem.add_correlation(LSDCorrelation(99, 1, "HMBC"))  # Atom 99 doesn't exist

        issues = problem.validate()
        assert any("non-existent" in issue for issue in issues)

    def test_summary(self):
        """Test problem summary generation."""
        problem = LSDProblem(name="ibuprofen", molecular_formula="C13H18O2")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 0))
        problem.add_atom(LSDAtom(2, "O", Hybridization.SP2, 0))
        problem.add_correlation(LSDCorrelation(1, 1, "HSQC"))

        summary = problem.summary()
        assert "ibuprofen" in summary
        assert "C13H18O2" in summary
        assert "HSQC: 1" in summary

    def test_add_constraint(self):
        """Test adding constraints to problem."""
        problem = LSDProblem()
        constraint = LSDConstraint(atom1_index=1, atom2_index=10, constraint_type="BOND")
        problem.add_constraint(constraint)
        assert len(problem.constraints) == 1
        assert problem.constraints[0] is constraint

    def test_validate_missing_constraint_atom(self):
        """Test validation catches constraints to non-existent atoms."""
        problem = LSDProblem()
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 0))
        problem.add_constraint(LSDConstraint(1, 99, "BOND"))  # Atom 99 doesn't exist

        issues = problem.validate()
        assert any("non-existent" in issue for issue in issues)

    def test_pylsd_mode_default_false(self):
        """Test that LSDProblem.pylsd_mode defaults to False."""
        problem = LSDProblem()
        assert problem.pylsd_mode is False

    def test_pylsd_mode_can_be_set_true(self):
        """Test that LSDProblem.pylsd_mode can be set to True."""
        problem = LSDProblem(pylsd_mode=True)
        assert problem.pylsd_mode is True

    def test_elim_commands_default_empty(self):
        """Test that LSDProblem.elim_commands defaults to empty list."""
        problem = LSDProblem()
        assert problem.elim_commands == []

    def test_elim_commands_can_be_populated(self):
        """Test that LSDProblem.elim_commands accepts (N, M) tuples."""
        problem = LSDProblem(elim_commands=[(1, 2), (3, 5)])
        assert len(problem.elim_commands) == 2
        assert problem.elim_commands[0] == (1, 2)
        assert problem.elim_commands[1] == (3, 5)

    def test_elim_commands_independent_across_instances(self):
        """Test that elim_commands lists are not shared across instances."""
        p1 = LSDProblem()
        p2 = LSDProblem()
        p1.elim_commands.append((1, 2))
        assert p2.elim_commands == []

    def test_summary_with_constraints(self):
        """Test problem summary includes constraints."""
        problem = LSDProblem(name="test")
        problem.add_atom(LSDAtom(1, "C", Hybridization.SP2, 0, carbon_shift=180.0))
        problem.add_atom(LSDAtom(2, "O", Hybridization.SP2, 0))
        problem.add_constraint(LSDConstraint(1, 2, "BOND", reason="carbonyl"))
        problem.add_constraint(LSDConstraint(1, 3, "FBND", reason="too far"))

        summary = problem.summary()
        assert "Constraints: 2" in summary
        assert "BOND: 1" in summary
        assert "FBND: 1" in summary
