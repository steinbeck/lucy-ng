"""Test hybridisation extraction in HOSE stats generator."""

from rdkit import Chem

from ailsa.prediction.stats_generator import WelfordAccumulator, extract_hybridisation


def test_extract_hybridisation_sp3():
    """Test that sp3 carbons are correctly identified."""
    # Ethane: both carbons are sp3
    ethane = Chem.MolFromSmiles("CC")
    assert ethane.GetNumAtoms() == 2  # Verify implicit H (not 8 atoms)
    assert extract_hybridisation(ethane.GetAtomWithIdx(0)) == "sp3"
    assert extract_hybridisation(ethane.GetAtomWithIdx(1)) == "sp3"

    # Cyclohexane: all carbons are sp3
    cyclohexane = Chem.MolFromSmiles("C1CCCCC1")
    for i in range(6):
        assert extract_hybridisation(cyclohexane.GetAtomWithIdx(i)) == "sp3"


def test_extract_hybridisation_sp2():
    """Test that sp2 carbons are correctly identified."""
    # Benzene: all carbons are sp2 (aromatic)
    benzene = Chem.MolFromSmiles("c1ccccc1")
    assert benzene.GetNumAtoms() == 6  # Verify implicit H
    for i in range(6):
        assert extract_hybridisation(benzene.GetAtomWithIdx(i)) == "sp2"

    # Acetic acid: carbonyl carbon is sp2
    acetic_acid = Chem.MolFromSmiles("CC(=O)O")
    assert extract_hybridisation(acetic_acid.GetAtomWithIdx(0)) == "sp3"  # Methyl
    assert extract_hybridisation(acetic_acid.GetAtomWithIdx(1)) == "sp2"  # Carbonyl

    # Ethylene: both carbons are sp2
    ethylene = Chem.MolFromSmiles("C=C")
    assert extract_hybridisation(ethylene.GetAtomWithIdx(0)) == "sp2"
    assert extract_hybridisation(ethylene.GetAtomWithIdx(1)) == "sp2"


def test_extract_hybridisation_sp1():
    """Test that sp1 (sp) carbons are correctly identified."""
    # Acetylene: both carbons are sp1
    acetylene = Chem.MolFromSmiles("C#C")
    assert acetylene.GetNumAtoms() == 2  # Verify implicit H
    assert extract_hybridisation(acetylene.GetAtomWithIdx(0)) == "sp1"
    assert extract_hybridisation(acetylene.GetAtomWithIdx(1)) == "sp1"

    # Propargyl alcohol: terminal alkyne carbons are sp1, methylene is sp3
    propargyl = Chem.MolFromSmiles("C#CCO")
    assert extract_hybridisation(propargyl.GetAtomWithIdx(0)) == "sp1"
    assert extract_hybridisation(propargyl.GetAtomWithIdx(1)) == "sp1"
    assert extract_hybridisation(propargyl.GetAtomWithIdx(2)) == "sp3"
    assert extract_hybridisation(propargyl.GetAtomWithIdx(3)) == "sp3"


def test_extract_hybridisation_no_explicit_h():
    """Verify function works on implicit-H molecules."""
    # Ethanol should have 3 atoms (not 9)
    ethanol = Chem.MolFromSmiles("CCO")
    assert ethanol.GetNumAtoms() == 3, "Molecule should have implicit H"

    # All atoms should still return correct hybridisation
    assert extract_hybridisation(ethanol.GetAtomWithIdx(0)) == "sp3"
    assert extract_hybridisation(ethanol.GetAtomWithIdx(1)) == "sp3"
    # Oxygen is not carbon, but function should not crash
    oxygen = ethanol.GetAtomWithIdx(2)
    result = extract_hybridisation(oxygen)
    assert result in ["sp3", "sp2", "sp1"]  # Any valid result is fine


def test_welford_accumulator_hybridisation_counts():
    """Test update_with_hybridisation increments correct counters."""
    acc = WelfordAccumulator()

    # Add 3 sp3, 2 sp2, 1 sp1
    acc.update_with_hybridisation(25.0, "sp3")
    acc.update_with_hybridisation(27.3, "sp3")
    acc.update_with_hybridisation(30.1, "sp3")
    acc.update_with_hybridisation(128.5, "sp2")
    acc.update_with_hybridisation(135.2, "sp2")
    acc.update_with_hybridisation(82.0, "sp1")

    assert acc.count == 6
    assert acc.sp3_count == 3
    assert acc.sp2_count == 2
    assert acc.sp1_count == 1

    # Verify mean is still calculated correctly
    expected_mean = (25.0 + 27.3 + 30.1 + 128.5 + 135.2 + 82.0) / 6
    assert abs(acc.mean - expected_mean) < 0.01


def test_welford_accumulator_merge_hybridisation():
    """Test that merge() combines hybridisation counts."""
    acc1 = WelfordAccumulator()
    acc1.update_with_hybridisation(25.0, "sp3")
    acc1.update_with_hybridisation(130.0, "sp2")

    acc2 = WelfordAccumulator()
    acc2.update_with_hybridisation(28.0, "sp3")
    acc2.update_with_hybridisation(135.0, "sp2")
    acc2.update_with_hybridisation(80.0, "sp1")

    merged = acc1.merge(acc2)

    assert merged.count == 5
    assert merged.sp3_count == 2  # 1 + 1
    assert merged.sp2_count == 2  # 1 + 1
    assert merged.sp1_count == 1  # 0 + 1


def test_welford_accumulator_to_tuple_extended():
    """Verify to_tuple returns 11-element tuple with hybridisation and neighbour counts."""
    acc = WelfordAccumulator()
    acc.update_with_hybridisation(25.0, "sp3")
    acc.update_with_hybridisation(130.0, "sp2")
    acc.update_with_hybridisation(135.0, "sp2")

    t = acc.to_tuple()

    # Should be 14 elements: (count, mean, m2, sp3, sp2, sp1, has_C, has_O, has_N, has_S, has_hal, in_3ring, in_4ring, in_aromatic)
    assert len(t) == 14, f"Expected 14-element tuple, got {len(t)}"
    assert t[0] == 3  # count
    assert isinstance(t[1], float)  # mean
    assert isinstance(t[2], float)  # m2
    assert t[3] == 1  # sp3_count
    assert t[4] == 2  # sp2_count
    assert t[5] == 0  # sp1_count
    # Neighbour counts should be 0 (used update_with_hybridisation, not update_with_neighbors)
    assert t[6] == 0  # has_carbon_neighbor
    assert t[7] == 0  # has_oxygen_neighbor
    assert t[8] == 0  # has_nitrogen_neighbor
    assert t[9] == 0  # has_sulfur_neighbor
    assert t[10] == 0  # has_halogen_neighbor


def test_welford_accumulator_backward_compat():
    """Verify that plain update() still works and does not affect hybridisation counts."""
    acc = WelfordAccumulator()

    # Use plain update (no hybridisation)
    acc.update(25.0)
    acc.update(30.0)
    acc.update(35.0)

    assert acc.count == 3
    assert acc.sp3_count == 0  # Should not increment
    assert acc.sp2_count == 0
    assert acc.sp1_count == 0

    # Verify statistics are correct
    assert abs(acc.mean - 30.0) < 0.01

    # Can still use update_with_hybridisation after plain update
    acc.update_with_hybridisation(128.0, "sp2")
    assert acc.count == 4
    assert acc.sp2_count == 1
