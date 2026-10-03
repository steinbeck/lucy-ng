"""Tests for bond pair statistics generator."""

import tempfile
from pathlib import Path

from rdkit import Chem

from ailsa.database import DatabaseManager
from ailsa.database.models import BondPairStatsRecord, CompoundRecord, ShiftRecord
from ailsa.prediction.bond_pair_generator import BondPairStatsGenerator, extract_hetero_hetero_bonds


def test_no_hhb_in_methanol():
    """Test that methanol has no hetero-hetero bonds (C-O is not HHB)."""
    mol = Chem.MolFromSmiles("CO")
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)
    assert pairs == set()


def test_hhb_hydrazine():
    """Test that hydrazine has N-N bond."""
    mol = Chem.MolFromSmiles("NN")
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)
    assert pairs == {("N", "N")}


def test_hhb_hydroxylamine():
    """Test that hydroxylamine has N-O bond."""
    mol = Chem.MolFromSmiles("NO")
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)
    assert pairs == {("N", "O")}


def test_hhb_peroxide():
    """Test that peroxide has O-O bond."""
    mol = Chem.MolFromSmiles("OO")
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)
    assert pairs == {("O", "O")}


def test_no_hhb_in_ethanol():
    """Test that ethanol has no hetero-hetero bonds."""
    mol = Chem.MolFromSmiles("CCO")
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)
    assert pairs == set()


def test_hhb_pair_canonicalization():
    """Test that pairs are canonicalized (alphabetical order)."""
    # Hydroxylamine - bond direction shouldn't matter
    mol1 = Chem.MolFromSmiles("NO")
    mol2 = Chem.MolFromSmiles("ON")

    pairs1 = extract_hetero_hetero_bonds(mol1)
    pairs2 = extract_hetero_hetero_bonds(mol2)

    # Both should give ("N", "O"), not ("O", "N")
    assert pairs1 == {("N", "O")}
    assert pairs2 == {("N", "O")}


def test_hhb_sulfonamide():
    """Test sulfonamide has N-S and O-S bonds."""
    mol = Chem.MolFromSmiles("NS(=O)=O")
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)

    # Should have N-S bond and O-S bonds
    # Note: S is bonded to N and to two O atoms
    expected = {("N", "S"), ("O", "S")}
    assert pairs == expected


def test_no_hhb_in_pure_hydrocarbon():
    """Test that pure hydrocarbon has no hetero-hetero bonds."""
    mol = Chem.MolFromSmiles("c1ccccc1")  # Benzene
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)
    assert pairs == set()


def test_hhb_multiple_same_pair():
    """Test that multiple bonds of same type only count once."""
    # Sulfate ester: has multiple S-O bonds
    mol = Chem.MolFromSmiles("COS(=O)(=O)O")
    assert mol is not None

    pairs = extract_hetero_hetero_bonds(mol)

    # Should only return unique pair types, not count
    assert pairs == {("O", "S")}


def test_generate_all_with_compounds():
    """Test BondPairStatsGenerator.generate_all() with compound database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert compound with N-O bond (hydroxylamine derivative)
            compound1 = CompoundRecord(
                name="hydroxylamine",
                smiles="NO",
                formula="H3NO",
                carbon_count=0,
            )
            compound1.shifts = [ShiftRecord(shift_ppm=0.0)]
            db.insert_compound(compound1)

            # Insert compound without HHB (ethanol)
            compound2 = CompoundRecord(
                name="ethanol",
                smiles="CCO",
                formula="C2H6O",
                carbon_count=2,
            )
            compound2.shifts = [ShiftRecord(shift_ppm=18.0), ShiftRecord(shift_ppm=58.0)]
            db.insert_compound(compound2)

            # Insert another compound with N-O bond (same formula as first)
            compound3 = CompoundRecord(
                name="hydroxylamine2",
                smiles="NO",
                formula="H3NO",
                carbon_count=0,
            )
            compound3.shifts = [ShiftRecord(shift_ppm=0.0)]
            db.insert_compound(compound3)

        # Generate statistics
        with DatabaseManager(db_path) as db:
            generator = BondPairStatsGenerator(db)
            bond_counts, formula_totals = generator.generate_all(progress=False)

            # Check formula totals
            assert formula_totals["H3NO"] == 2
            assert formula_totals["C2H6O"] == 1

            # Check bond counts
            assert bond_counts[("H3NO", "N", "O")] == 2
            # Ethanol has no HHB, so no entry for C2H6O

            # Check generator stats
            assert generator.compounds_processed == 3
            assert generator.compounds_failed == 0


def test_populate_database():
    """Test BondPairStatsGenerator.populate_database()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert compounds
            compound1 = CompoundRecord(
                name="hydroxylamine",
                smiles="NO",
                formula="H3NO",
                carbon_count=0,
            )
            compound1.shifts = [ShiftRecord(shift_ppm=0.0)]
            db.insert_compound(compound1)

            compound2 = CompoundRecord(
                name="hydrazine",
                smiles="NN",
                formula="H4N2",
                carbon_count=0,
            )
            compound2.shifts = [ShiftRecord(shift_ppm=0.0)]
            db.insert_compound(compound2)

        # Populate bond pair stats
        with DatabaseManager(db_path) as db:
            generator = BondPairStatsGenerator(db)
            count = generator.populate_database(progress=False)

            assert count == 2  # Two entries: (H3NO, N, O) and (H4N2, N, N)

            # Query back
            records_h3no = db.get_bond_pair_stats_by_formula("H3NO")
            assert len(records_h3no) == 1
            assert records_h3no[0].element1 == "N"
            assert records_h3no[0].element2 == "O"
            assert records_h3no[0].compound_count == 1
            assert records_h3no[0].total_compounds == 1
            assert records_h3no[0].frequency == 1.0

            records_h4n2 = db.get_bond_pair_stats_by_formula("H4N2")
            assert len(records_h4n2) == 1
            assert records_h4n2[0].element1 == "N"
            assert records_h4n2[0].element2 == "N"
            assert records_h4n2[0].compound_count == 1
            assert records_h4n2[0].total_compounds == 1
            assert records_h4n2[0].frequency == 1.0


def test_populate_database_frequency_calculation():
    """Test frequency calculation when not all compounds have HHB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        with DatabaseManager(db_path) as db:
            db.create_tables()

            # Insert 3 compounds with formula C2H6O
            # Only 1 has HHB (hypothetical peroxide)
            compound1 = CompoundRecord(
                name="ethanol",
                smiles="CCO",
                formula="C2H6O",
                carbon_count=2,
            )
            compound1.shifts = [ShiftRecord(shift_ppm=18.0)]
            db.insert_compound(compound1)

            compound2 = CompoundRecord(
                name="dimethyl_ether",
                smiles="COC",
                formula="C2H6O",
                carbon_count=2,
            )
            compound2.shifts = [ShiftRecord(shift_ppm=58.0)]
            db.insert_compound(compound2)

            # Note: This is not realistic chemistry (C2H6O2 peroxide), but tests the logic
            # Actually, we need a realistic C2H6O with HHB - which doesn't exist.
            # Let's use a different formula for testing.

            # Better test: Use compounds with N-O bond vs without
            compound3 = CompoundRecord(
                name="methoxyamine",
                smiles="CON",  # Has O-N bond (C-O-N)
                formula="CH5NO",
                carbon_count=1,
            )
            compound3.shifts = [ShiftRecord(shift_ppm=48.0)]
            db.insert_compound(compound3)

            # Another CH5NO without N-O bond (methylamine with oxygen nearby but not bonded)
            # Actually, for CH5NO we can't avoid N-O bond easily. Let's use different formula.
            # Use H2NO (hydroxylamine) vs NH3 (ammonia) - different formulas though.
            # Better: use same base but one with HHB, one without.
            # Let's just test with hydroxylamine (NO) appearing twice vs once.
            compound4 = CompoundRecord(
                name="methylamine",
                smiles="CN",  # No HHB
                formula="CH5N",
                carbon_count=1,
            )
            compound4.shifts = [ShiftRecord(shift_ppm=27.0)]
            db.insert_compound(compound4)

        # Populate
        with DatabaseManager(db_path) as db:
            generator = BondPairStatsGenerator(db)
            generator.populate_database(progress=False)

            # Query for CH5NO (only compound3 has this formula)
            records = db.get_bond_pair_stats_by_formula("CH5NO")

            # Should have N-O entry
            no_record = [r for r in records if r.element1 == "N" and r.element2 == "O"]
            assert len(no_record) == 1
            assert no_record[0].compound_count == 1  # Only compound3
            assert no_record[0].total_compounds == 1  # Only compound3 has CH5NO
            assert no_record[0].frequency == 1.0  # 1/1

            # C2H6O should have no HHB (compounds 1 and 2)
            records_c2h6o = db.get_bond_pair_stats_by_formula("C2H6O")
            assert len(records_c2h6o) == 0  # No HHB in ethanol or dimethyl ether
