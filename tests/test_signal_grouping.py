"""Tests for signal grouping algorithm."""

import pytest

from ailsa.detection.grouping import group_signals, is_multiplicity_compatible
from ailsa.detection.models import GroupingResult, SignalGroup


class TestMultiplicityCompatibility:
    """Test is_multiplicity_compatible() function."""

    def test_same_multiplicity_compatible(self):
        """Same multiplicities are compatible."""
        assert is_multiplicity_compatible("CH2", "CH2")
        assert is_multiplicity_compatible("CH", "CH")
        assert is_multiplicity_compatible("CH3", "CH3")

    def test_different_definite_multiplicities_incompatible(self):
        """Different definite multiplicities are incompatible."""
        assert not is_multiplicity_compatible("CH2", "CH")
        assert not is_multiplicity_compatible("CH2", "CH3")
        assert not is_multiplicity_compatible("CH", "CH3")

    def test_ambiguous_multiplicities_compatible(self):
        """Ambiguous multiplicities (CH/CH3) are compatible with CH or CH3."""
        assert is_multiplicity_compatible("CH", "CH/CH3")
        assert is_multiplicity_compatible("CH/CH3", "CH")
        assert is_multiplicity_compatible("CH3", "CH/CH3")
        assert is_multiplicity_compatible("CH/CH3", "CH3")
        assert is_multiplicity_compatible("CH/CH3", "CH/CH3")

    def test_none_multiplicity_compatible(self):
        """None multiplicity is compatible with everything (conservative)."""
        assert is_multiplicity_compatible(None, "CH2")
        assert is_multiplicity_compatible("CH2", None)
        assert is_multiplicity_compatible(None, None)


class TestGroupSignals:
    """Test group_signals() function."""

    def test_empty_list(self):
        """Empty list produces no groups or ungrouped."""
        result = group_signals([])
        assert isinstance(result, GroupingResult)
        assert len(result.groups) == 0
        assert len(result.ungrouped) == 0
        assert result.total_signals == 0

    def test_single_shift(self):
        """Single shift is ungrouped."""
        result = group_signals([44.90])
        assert len(result.groups) == 0
        assert result.ungrouped == [0]
        assert result.total_signals == 1

    def test_basic_grouping_within_tolerance(self):
        """Two shifts within tolerance form a group."""
        # Ibuprofen C4/C5 case: 44.90 and 45.03 (0.13 ppm apart)
        result = group_signals([44.90, 45.03], tolerance=0.25)
        assert len(result.groups) == 1
        assert len(result.ungrouped) == 0
        assert result.total_signals == 2

        group = result.groups[0]
        assert group.indices == [0, 1]
        assert group.shifts == [44.90, 45.03]
        assert group.span == pytest.approx(0.13, abs=0.001)
        assert group.centroid == pytest.approx(44.965, abs=0.001)

    def test_mixed_grouped_and_ungrouped(self):
        """Some shifts grouped, some not."""
        result = group_signals([44.90, 45.03, 129.38], tolerance=0.25)
        assert len(result.groups) == 1
        assert len(result.ungrouped) == 1
        assert result.total_signals == 3

        # First two should be grouped
        group = result.groups[0]
        assert group.indices == [0, 1]
        assert group.shifts == [44.90, 45.03]

        # Last should be ungrouped
        assert result.ungrouped == [2]

    def test_multiplicity_filtering_all_incompatible(self):
        """Multiplicity incompatible shifts are split into singletons."""
        result = group_signals(
            [44.90, 45.03, 45.20],
            multiplicities=["CH2", "CH", "CH3"],
            tolerance=0.25
        )
        # All three within 0.30 ppm but different multiplicities
        # Should produce 0 groups, 3 ungrouped
        assert len(result.groups) == 0
        assert len(result.ungrouped) == 3
        assert set(result.ungrouped) == {0, 1, 2}

    def test_multiplicity_filtering_all_compatible(self):
        """Ambiguous multiplicities allow grouping when ALL pairs compatible."""
        # Use all CH/CH3 - they're all compatible with each other
        result = group_signals(
            [44.90, 45.03, 45.15],
            multiplicities=["CH/CH3", "CH/CH3", "CH/CH3"],
            tolerance=0.25
        )
        # All three within 0.25 ppm and all multiplicities compatible
        # Should produce 1 group of 3
        assert len(result.groups) == 1
        assert len(result.ungrouped) == 0

        group = result.groups[0]
        assert group.indices == [0, 1, 2]
        assert group.multiplicities == ["CH/CH3", "CH/CH3", "CH/CH3"]

    def test_multiplicity_bridging_splits_group(self):
        """CH/CH3 doesn't bridge incompatible CH and CH3 - pairwise check fails."""
        result = group_signals(
            [44.90, 45.03, 45.15],
            multiplicities=["CH", "CH/CH3", "CH3"],
            tolerance=0.25
        )
        # CH and CH3 are incompatible, so despite CH/CH3 being compatible with both,
        # the pairwise check (CH vs CH3) fails and entire group splits
        assert len(result.groups) == 0
        assert len(result.ungrouped) == 3
        assert set(result.ungrouped) == {0, 1, 2}

    def test_complete_linkage_not_chaining(self):
        """Complete linkage prevents chaining beyond tolerance."""
        # [10.0, 10.1, 10.2, 10.5] with tolerance 0.25
        # Complete linkage:
        # - 10.0 to 10.1: 0.1 ✓
        # - 10.0 to 10.2: 0.2 ✓
        # - 10.1 to 10.2: 0.1 ✓
        # So [10.0, 10.1, 10.2] form group
        # - 10.5 to 10.0: 0.5 ✗ (exceeds tolerance)
        # So 10.5 is ungrouped
        result = group_signals([10.0, 10.1, 10.2, 10.5], tolerance=0.25)
        assert len(result.groups) == 1
        assert len(result.ungrouped) == 1

        group = result.groups[0]
        assert group.indices == [0, 1, 2]
        assert result.ungrouped == [3]

    def test_complete_linkage_multiple_groups(self):
        """Complete linkage creates multiple groups."""
        # [10.0, 10.2, 10.4, 10.6] with tolerance 0.25
        # - 10.0-10.2: 0.2 ✓, but 10.0-10.4: 0.4 ✗
        # - 10.4-10.6: 0.2 ✓, but 10.4-10.2: 0.2 ✓, and 10.6-10.2: 0.4 ✗
        # Should produce groups [10.0, 10.2] and [10.4, 10.6]
        result = group_signals([10.0, 10.2, 10.4, 10.6], tolerance=0.25)
        assert len(result.groups) == 2
        assert len(result.ungrouped) == 0

        assert result.groups[0].indices == [0, 1]
        assert result.groups[1].indices == [2, 3]

    def test_large_group_warning(self):
        """Warn when >50% of signals in one group."""
        # 6 shifts, all within tolerance - single group of 6 (>50%)
        shifts = [10.0, 10.1, 10.15, 10.2, 10.22, 10.25]
        result = group_signals(shifts, tolerance=0.25)
        assert len(result.groups) == 1
        assert result.groups[0].indices == [0, 1, 2, 3, 4, 5]
        assert len(result.warnings) > 0
        assert "Unusually large group" in result.warnings[0]

    def test_lsd_atom_list_multiple(self):
        """SignalGroup.lsd_atom_list() formats multiple indices."""
        # Indices [0, 1] should format as "(1 2)" (1-based)
        group = SignalGroup(
            indices=[0, 1],
            shifts=[44.90, 45.03],
            multiplicities=None,
            span=0.13,
            centroid=44.965
        )
        assert group.atom_ids == [1, 2]
        assert group.lsd_atom_list() == "(1 2)"

    def test_lsd_atom_list_single(self):
        """SignalGroup.lsd_atom_list() formats single index."""
        # Index [3] should format as "4" (1-based, no parentheses)
        group = SignalGroup(
            indices=[3],
            shifts=[129.38],
            multiplicities=None,
            span=0.0,
            centroid=129.38
        )
        assert group.atom_ids == [4]
        assert group.lsd_atom_list() == "4"

    def test_grouping_result_summary(self):
        """GroupingResult.summary() generates readable output."""
        result = group_signals([44.90, 45.03, 129.38], tolerance=0.25)
        summary = result.summary()
        assert "44.90" in summary
        assert "45.03" in summary
        assert "tolerance 0.25" in summary
        assert "Groups: 1" in summary  # Fixed: exact match for the format


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_identical_shifts(self):
        """Identical shifts form a group."""
        result = group_signals([44.90, 44.90])
        assert len(result.groups) == 1
        assert result.groups[0].indices == [0, 1]
        assert result.groups[0].span == 0.0

    def test_tolerance_zero_no_grouping(self):
        """Tolerance 0 means no grouping unless identical."""
        result = group_signals([44.90, 45.03], tolerance=0.0)
        assert len(result.groups) == 0
        assert len(result.ungrouped) == 2

    def test_unsorted_input(self):
        """Input doesn't need to be sorted."""
        result = group_signals([129.38, 44.90, 45.03], tolerance=0.25)
        assert len(result.groups) == 1
        # Groups should be sorted by shift
        assert result.groups[0].shifts[0] < result.groups[0].shifts[1]

    def test_none_multiplicities_allow_grouping(self):
        """None multiplicities don't block grouping."""
        result = group_signals(
            [44.90, 45.03],
            multiplicities=[None, None],
            tolerance=0.25
        )
        assert len(result.groups) == 1
        assert result.groups[0].multiplicities == [None, None]
