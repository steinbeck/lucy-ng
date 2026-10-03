"""Signal grouping algorithm for detecting chemically equivalent carbons."""

from __future__ import annotations

from statistics import mean

from ailsa.detection.models import GroupingResult, SignalGroup


def is_multiplicity_compatible(mult1: str | None, mult2: str | None) -> bool:
    """Check if two multiplicities are compatible for grouping.

    Args:
        mult1: First multiplicity (e.g., "CH", "CH2", "CH3", "CH/CH3")
        mult2: Second multiplicity

    Returns:
        True if compatible (can be in same group), False otherwise

    Rules:
        - Same multiplicity -> compatible
        - Both ambiguous (contains "/") -> compatible
        - Either is None -> compatible (conservative)
        - Different definite multiplicities -> incompatible
    """
    # None is compatible with everything (conservative)
    if mult1 is None or mult2 is None:
        return True

    # Same multiplicity is always compatible
    if mult1 == mult2:
        return True

    # Ambiguous multiplicities (containing "/") are compatible with their components
    # and with each other
    mult1_is_ambiguous = "/" in mult1
    mult2_is_ambiguous = "/" in mult2

    # If both ambiguous, compatible
    if mult1_is_ambiguous and mult2_is_ambiguous:
        return True

    # If one is ambiguous and the other is a component, compatible
    if mult1_is_ambiguous:
        # mult1 contains mult2? (e.g., "CH/CH3" contains "CH")
        components = mult1.split("/")
        return mult2 in components

    if mult2_is_ambiguous:
        # mult2 contains mult1?
        components = mult2.split("/")
        return mult1 in components

    # Different definite multiplicities are incompatible
    return False


def group_signals(
    shifts: list[float],
    multiplicities: list[str | None] | None = None,
    tolerance: float = 0.25,
) -> GroupingResult:
    """Group carbon signals by proximity and multiplicity compatibility.

    Uses complete linkage clustering: all pairwise distances within a group
    must be <= tolerance. This prevents chaining (where A-B and B-C are close
    but A-C exceeds tolerance).

    After distance-based clustering, filters groups by multiplicity compatibility.
    If any pair in a group is multiplicity-incompatible, the entire group is
    split into singletons.

    Args:
        shifts: List of carbon shift values (ppm)
        multiplicities: Optional list of multiplicity labels (same length as shifts)
        tolerance: Maximum pairwise distance (ppm) for grouping

    Returns:
        GroupingResult with groups, ungrouped indices, and warnings
    """
    if not shifts:
        return GroupingResult(
            tolerance=tolerance,
            groups=[],
            ungrouped=[],
            total_signals=0,
            warnings=[],
        )

    # Validate multiplicities length
    if multiplicities is not None and len(multiplicities) != len(shifts):
        raise ValueError(
            f"Multiplicities length ({len(multiplicities)}) must match "
            f"shifts length ({len(shifts)})"
        )

    # Sort indices by shift value
    sorted_indices = sorted(range(len(shifts)), key=lambda i: shifts[i])

    # Complete linkage clustering
    groups: list[list[int]] = []
    current_group: list[int] = []

    for idx in sorted_indices:
        if not current_group:
            # Start first group
            current_group.append(idx)
        else:
            # Check if this point can join current group (complete linkage)
            # All pairwise distances must be <= tolerance
            can_join = all(
                abs(shifts[idx] - shifts[existing_idx]) <= tolerance
                for existing_idx in current_group
            )

            if can_join:
                current_group.append(idx)
            else:
                # Finalize current group (if >1 element) and start new
                if len(current_group) > 1:
                    groups.append(current_group)
                else:
                    # Single-element groups are ungrouped
                    pass

                current_group = [idx]

    # Don't forget the last group
    if len(current_group) > 1:
        groups.append(current_group)

    # Now filter by multiplicity compatibility
    final_groups: list[SignalGroup] = []
    ungrouped: list[int] = []

    for group_indices in groups:
        # Check if all pairs in group are multiplicity-compatible
        if multiplicities is None:
            # No multiplicity filtering
            is_compatible = True
        else:
            is_compatible = True
            for i in range(len(group_indices)):
                for j in range(i + 1, len(group_indices)):
                    mult_i = multiplicities[group_indices[i]]
                    mult_j = multiplicities[group_indices[j]]
                    if not is_multiplicity_compatible(mult_i, mult_j):
                        is_compatible = False
                        break
                if not is_compatible:
                    break

        if is_compatible:
            # Create SignalGroup
            group_shifts = [shifts[i] for i in group_indices]
            group_mults = (
                [multiplicities[i] for i in group_indices]
                if multiplicities is not None
                else None
            )
            span = max(group_shifts) - min(group_shifts)
            centroid = mean(group_shifts)

            final_groups.append(
                SignalGroup(
                    indices=group_indices,
                    shifts=group_shifts,
                    multiplicities=group_mults,
                    span=span,
                    centroid=centroid,
                )
            )
        else:
            # Split entire group into singletons
            ungrouped.extend(group_indices)

    # Add all single-element "groups" to ungrouped
    for idx in sorted_indices:
        # If this index is not in any final group
        if not any(idx in g.indices for g in final_groups):
            if idx not in ungrouped:
                ungrouped.append(idx)

    # Check for warnings
    warnings = []
    if final_groups:
        max_group_size = max(len(g.indices) for g in final_groups)
        if len(shifts) > 0 and max_group_size > len(shifts) * 0.5:
            warnings.append(
                f"Unusually large group: {max_group_size}/{len(shifts)} signals "
                f"({max_group_size/len(shifts)*100:.0f}%)"
            )

    return GroupingResult(
        tolerance=tolerance,
        groups=final_groups,
        ungrouped=sorted(ungrouped),
        total_signals=len(shifts),
        warnings=warnings,
    )
