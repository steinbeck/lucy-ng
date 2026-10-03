"""Tests for ring membership tracking in WelfordAccumulator."""

from rdkit import Chem

from ailsa.prediction.stats_generator import WelfordAccumulator


def test_accumulator_ring_tracking():
    """Test that ring membership is tracked for aromatic atoms."""
    acc = WelfordAccumulator()

    # Create benzene (aromatic, no 3-ring or 4-ring)
    mol = Chem.MolFromSmiles("c1ccccc1")
    assert mol is not None

    # Carbon at index 0 is aromatic
    neighbors = {"C": 2}  # benzene carbon has 2 carbon neighbors

    acc.update_with_rings(
        value=128.5,
        hybridisation="sp2",
        neighbors=neighbors,
        atom_idx=0,
        mol=mol,
    )

    # Check ring flags
    assert acc.in_aromatic == 1
    assert acc.in_3ring == 0
    assert acc.in_4ring == 0

    # Check that neighbors/hybridisation still work
    assert acc.count == 1
    assert acc.sp2_count == 1
    assert acc.has_carbon_neighbor == 1


def test_accumulator_ring_3ring():
    """Test that 3-membered ring is detected."""
    acc = WelfordAccumulator()

    # Create cyclopropane
    mol = Chem.MolFromSmiles("C1CC1")
    assert mol is not None

    # Carbon at index 0 is in 3-ring
    neighbors = {"C": 2}

    acc.update_with_rings(
        value=20.5,
        hybridisation="sp3",
        neighbors=neighbors,
        atom_idx=0,
        mol=mol,
    )

    assert acc.in_3ring == 1
    assert acc.in_4ring == 0
    assert acc.in_aromatic == 0


def test_accumulator_ring_4ring():
    """Test that 4-membered ring is detected."""
    acc = WelfordAccumulator()

    # Create cyclobutane
    mol = Chem.MolFromSmiles("C1CCC1")
    assert mol is not None

    # Carbon at index 0 is in 4-ring
    neighbors = {"C": 2}

    acc.update_with_rings(
        value=23.3,
        hybridisation="sp3",
        neighbors=neighbors,
        atom_idx=0,
        mol=mol,
    )

    assert acc.in_3ring == 0
    assert acc.in_4ring == 1
    assert acc.in_aromatic == 0


def test_accumulator_no_rings():
    """Test that non-ring atoms have zero ring counts."""
    acc = WelfordAccumulator()

    # Create ethanol (no rings)
    mol = Chem.MolFromSmiles("CCO")
    assert mol is not None

    # Carbon at index 0 is not in any ring
    neighbors = {"C": 1}

    acc.update_with_rings(
        value=18.5,
        hybridisation="sp3",
        neighbors=neighbors,
        atom_idx=0,
        mol=mol,
    )

    assert acc.in_3ring == 0
    assert acc.in_4ring == 0
    assert acc.in_aromatic == 0


def test_accumulator_to_tuple_14_elements():
    """Test that to_tuple() returns 14 elements."""
    acc = WelfordAccumulator()

    # Create benzene
    mol = Chem.MolFromSmiles("c1ccccc1")
    neighbors = {"C": 2}

    acc.update_with_rings(
        value=128.5,
        hybridisation="sp2",
        neighbors=neighbors,
        atom_idx=0,
        mol=mol,
    )

    result = acc.to_tuple()

    # Should be 14 elements
    assert len(result) == 14

    # Unpack to verify structure
    (
        count,
        mean,
        m2,
        sp3_count,
        sp2_count,
        sp1_count,
        has_carbon_neighbor,
        has_oxygen_neighbor,
        has_nitrogen_neighbor,
        has_sulfur_neighbor,
        has_halogen_neighbor,
        in_3ring,
        in_4ring,
        in_aromatic,
    ) = result

    assert count == 1
    assert mean == 128.5
    assert sp2_count == 1
    assert has_carbon_neighbor == 1
    assert in_aromatic == 1
    assert in_3ring == 0
    assert in_4ring == 0


def test_accumulator_merge_with_rings():
    """Test that merge() correctly sums ring counts."""
    acc1 = WelfordAccumulator()
    acc2 = WelfordAccumulator()

    # Accumulator 1: benzene carbon (aromatic)
    mol1 = Chem.MolFromSmiles("c1ccccc1")
    neighbors1 = {"C": 2}
    acc1.update_with_rings(128.5, "sp2", neighbors1, 0, mol1)

    # Accumulator 2: cyclopropane carbon (3-ring)
    mol2 = Chem.MolFromSmiles("C1CC1")
    neighbors2 = {"C": 2}
    acc2.update_with_rings(20.5, "sp3", neighbors2, 0, mol2)

    # Merge
    merged = acc1.merge(acc2)

    assert merged.count == 2
    assert merged.in_aromatic == 1  # From acc1
    assert merged.in_3ring == 1  # From acc2
    assert merged.in_4ring == 0


def test_accumulator_update_with_rings_calls_neighbors():
    """Test that update_with_rings calls through to neighbor/hybridisation tracking."""
    acc = WelfordAccumulator()

    # Create benzene
    mol = Chem.MolFromSmiles("c1ccccc1")
    neighbors = {"C": 2, "O": 0, "N": 0}

    acc.update_with_rings(
        value=128.5,
        hybridisation="sp2",
        neighbors=neighbors,
        atom_idx=0,
        mol=mol,
    )

    # Verify that update_with_neighbors was called internally
    assert acc.count == 1
    assert acc.mean == 128.5
    assert acc.sp2_count == 1
    assert acc.has_carbon_neighbor == 1
    assert acc.has_oxygen_neighbor == 0
    assert acc.has_nitrogen_neighbor == 0

    # Also verify ring tracking worked
    assert acc.in_aromatic == 1


def test_accumulator_multiple_observations_with_rings():
    """Test multiple observations with ring tracking."""
    acc = WelfordAccumulator()

    # Create benzene
    mol = Chem.MolFromSmiles("c1ccccc1")
    neighbors = {"C": 2}

    # Add multiple observations
    for i in range(6):  # All 6 carbons in benzene
        acc.update_with_rings(128.5 + i, "sp2", neighbors, i, mol)

    assert acc.count == 6
    assert acc.in_aromatic == 6  # All aromatic
    assert acc.in_3ring == 0
    assert acc.in_4ring == 0
    assert acc.sp2_count == 6
    assert acc.has_carbon_neighbor == 6
