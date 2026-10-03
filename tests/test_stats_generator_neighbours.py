"""Test neighbour element tracking in HOSE stats generator."""

from ailsa.prediction.hose_parser import parse_sphere_1
from ailsa.prediction.stats_generator import WelfordAccumulator


def test_update_with_neighbors_counts():
    """Test update_with_neighbors increments correct element counters."""
    acc = WelfordAccumulator()

    # First observation: C and O present
    acc.update_with_neighbors(130.0, "sp2", {"C": 2, "O": 1})

    # Second observation: C, N present (no O)
    acc.update_with_neighbors(132.0, "sp2", {"C": 1, "N": 1})

    # Third observation: C only
    acc.update_with_neighbors(25.0, "sp3", {"C": 3})

    # Verify counts
    assert acc.count == 3
    assert acc.has_carbon_neighbor == 3  # All 3 had C
    assert acc.has_oxygen_neighbor == 1  # Only first had O
    assert acc.has_nitrogen_neighbor == 1  # Only second had N
    assert acc.has_sulfur_neighbor == 0  # None had S
    assert acc.has_halogen_neighbor == 0  # None had halogen


def test_update_with_neighbors_halogens():
    """Verify that F, Cl, Br, I all increment has_halogen_neighbor."""
    acc = WelfordAccumulator()

    # F present
    acc.update_with_neighbors(100.0, "sp3", {"C": 1, "F": 1})
    assert acc.has_halogen_neighbor == 1

    # Cl present
    acc.update_with_neighbors(100.0, "sp3", {"C": 1, "Cl": 1})
    assert acc.has_halogen_neighbor == 2

    # Br present
    acc.update_with_neighbors(100.0, "sp3", {"C": 1, "Br": 1})
    assert acc.has_halogen_neighbor == 3

    # I present
    acc.update_with_neighbors(100.0, "sp3", {"C": 1, "I": 1})
    assert acc.has_halogen_neighbor == 4

    # No halogen
    acc.update_with_neighbors(100.0, "sp3", {"C": 2})
    assert acc.has_halogen_neighbor == 4  # Still 4

    # Multiple halogens (counts as 1 increment)
    acc.update_with_neighbors(100.0, "sp3", {"C": 1, "F": 1, "Cl": 1})
    assert acc.has_halogen_neighbor == 5


def test_update_with_neighbors_preserves_hybridisation():
    """Verify that sp3_count, sp2_count, sp1_count are still updated correctly."""
    acc = WelfordAccumulator()

    acc.update_with_neighbors(25.0, "sp3", {"C": 2})
    acc.update_with_neighbors(130.0, "sp2", {"C": 2, "O": 1})
    acc.update_with_neighbors(135.0, "sp2", {"C": 1})
    acc.update_with_neighbors(80.0, "sp1", {"C": 1})

    # Verify hybridisation counts
    assert acc.sp3_count == 1
    assert acc.sp2_count == 2
    assert acc.sp1_count == 1

    # Verify neighbour counts
    assert acc.has_carbon_neighbor == 4  # All had C
    assert acc.has_oxygen_neighbor == 1  # Only second had O

    # Verify shift statistics
    assert acc.count == 4
    expected_mean = (25.0 + 130.0 + 135.0 + 80.0) / 4
    assert abs(acc.mean - expected_mean) < 0.01


def test_welford_merge_neighbours():
    """Test that merge() combines neighbour counts."""
    acc1 = WelfordAccumulator()
    acc1.update_with_neighbors(25.0, "sp3", {"C": 2, "O": 1})
    acc1.update_with_neighbors(30.0, "sp3", {"C": 1})

    acc2 = WelfordAccumulator()
    acc2.update_with_neighbors(130.0, "sp2", {"C": 2, "N": 1})
    acc2.update_with_neighbors(135.0, "sp2", {"C": 1, "O": 1, "Cl": 1})

    merged = acc1.merge(acc2)

    # Verify total observations
    assert merged.count == 4

    # Verify neighbour counts are summed
    assert merged.has_carbon_neighbor == 4  # 2 + 2 (all had C)
    assert merged.has_oxygen_neighbor == 2  # 1 + 1 (acc1 first, acc2 second)
    assert merged.has_nitrogen_neighbor == 1  # 0 + 1 (acc2 first)
    assert merged.has_sulfur_neighbor == 0  # 0 + 0
    assert merged.has_halogen_neighbor == 1  # 0 + 1 (acc2 second had Cl)

    # Verify hybridisation counts are summed
    assert merged.sp3_count == 2  # acc1
    assert merged.sp2_count == 2  # acc2


def test_to_tuple_eleven_elements():
    """Verify to_tuple() returns exactly 11 elements with correct positions."""
    acc = WelfordAccumulator()
    acc.update_with_neighbors(25.0, "sp3", {"C": 2, "O": 1})
    acc.update_with_neighbors(130.0, "sp2", {"C": 1, "N": 1, "F": 1})

    t = acc.to_tuple()

    # Should be 14 elements (11 + 3 ring columns added in Phase 36)
    assert len(t) == 14, f"Expected 14 elements, got {len(t)}"

    # Verify positions
    assert t[0] == 2  # count
    assert isinstance(t[1], float)  # mean
    assert isinstance(t[2], float)  # m2
    assert t[3] == 1  # sp3_count
    assert t[4] == 1  # sp2_count
    assert t[5] == 0  # sp1_count
    assert t[6] == 2  # has_carbon_neighbor (both had C)
    assert t[7] == 1  # has_oxygen_neighbor (only first had O)
    assert t[8] == 1  # has_nitrogen_neighbor (only second had N)
    assert t[9] == 0  # has_sulfur_neighbor (none had S)
    assert t[10] == 1  # has_halogen_neighbor (second had F)


def test_backward_compat_update_with_hybridisation():
    """Verify that update_with_hybridisation() still works and does NOT affect neighbour counts."""
    acc = WelfordAccumulator()

    # Use update_with_hybridisation (no neighbour tracking)
    acc.update_with_hybridisation(25.0, "sp3")
    acc.update_with_hybridisation(130.0, "sp2")

    # Verify shift and hybridisation tracked
    assert acc.count == 2
    assert acc.sp3_count == 1
    assert acc.sp2_count == 1

    # Verify neighbour counts remain 0
    assert acc.has_carbon_neighbor == 0
    assert acc.has_oxygen_neighbor == 0
    assert acc.has_nitrogen_neighbor == 0
    assert acc.has_sulfur_neighbor == 0
    assert acc.has_halogen_neighbor == 0


def test_backward_compat_plain_update():
    """Verify that plain update() does not affect hybridisation or neighbour counts."""
    acc = WelfordAccumulator()

    # Use plain update (no hybridisation or neighbours)
    acc.update(25.0)
    acc.update(30.0)
    acc.update(35.0)

    # Verify shift tracked
    assert acc.count == 3
    assert abs(acc.mean - 30.0) < 0.01

    # Verify hybridisation counts remain 0
    assert acc.sp3_count == 0
    assert acc.sp2_count == 0
    assert acc.sp1_count == 0

    # Verify neighbour counts remain 0
    assert acc.has_carbon_neighbor == 0
    assert acc.has_oxygen_neighbor == 0
    assert acc.has_nitrogen_neighbor == 0
    assert acc.has_sulfur_neighbor == 0
    assert acc.has_halogen_neighbor == 0


def test_parse_sphere_1_integration():
    """Test integration between parse_sphere_1 and update_with_neighbors."""
    acc = WelfordAccumulator()

    # Real HOSE code: carbonyl carbon (C=O with one C neighbor)
    hose_code = "C-3;=OCO(,,//)"
    neighbors = parse_sphere_1(hose_code)

    # Should extract O (double bonded) and C (single bonded)
    assert "O" in neighbors
    assert "C" in neighbors

    # Update accumulator with parsed neighbors
    acc.update_with_neighbors(200.0, "sp2", neighbors)

    # Verify counts
    assert acc.count == 1
    assert acc.has_carbon_neighbor == 1
    assert acc.has_oxygen_neighbor == 1

    # Real HOSE code: aromatic carbon with two aromatic C neighbors
    hose_code2 = "C-3;*C*C(//))"
    neighbors2 = parse_sphere_1(hose_code2)

    # Should extract two C (aromatic)
    assert "C" in neighbors2
    assert neighbors2["C"] == 2

    # Update same accumulator
    acc.update_with_neighbors(130.0, "sp2", neighbors2)

    # Verify updated counts
    assert acc.count == 2
    assert acc.has_carbon_neighbor == 2  # Both observations had C
    assert acc.has_oxygen_neighbor == 1  # Only first had O
