"""Pydantic models for statistical detection results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, computed_field


class HybridisationDistribution(BaseModel):
    """Distribution of hybridisation states for a carbon shift.

    Frequencies sum to ~1.0 (or 0.0 if no data).
    """

    sp3: float = 0.0  # Frequency 0.0-1.0
    sp2: float = 0.0
    sp1: float = 0.0

    @property
    def dominant(self) -> str:
        """Return the hybridisation state with highest frequency.

        Returns:
            "sp3", "sp2", "sp1", or "unknown" if all zero
        """
        if self.sp3 == 0.0 and self.sp2 == 0.0 and self.sp1 == 0.0:
            return "unknown"

        max_freq = max(self.sp3, self.sp2, self.sp1)
        if self.sp3 == max_freq:
            return "sp3"
        elif self.sp2 == max_freq:
            return "sp2"
        else:
            return "sp1"

    @property
    def is_definitive(self) -> bool:
        """Return True if one state has >95% frequency.

        A definitive result strongly suggests the hybridisation state
        with high confidence.
        """
        return max(self.sp3, self.sp2, self.sp1) > 0.95


class HybridisationResult(BaseModel):
    """Result of hybridisation detection query.

    Contains both the frequency distribution and metadata about
    the query parameters and data coverage.
    """

    shift_ppm: float  # Queried shift
    window_ppm: float  # Query window used
    radius: int  # HOSE radius used
    threshold: float  # Minimum frequency threshold used
    distribution: HybridisationDistribution  # Filtered distribution
    total_observations: int  # Total sp3+sp2+sp1 count across all matching HOSE codes
    unique_hose_codes: int  # Number of HOSE codes that contributed
    has_data: bool  # False if no matching HOSE codes or all counts are 0
    warning: str | None = None  # Warning message

    def summary(self) -> str:
        """Generate human-readable summary of detection result.

        Returns:
            Multi-line text summary
        """
        lines = []

        # Header
        lines.append(
            f"Hybridisation Detection: {self.shift_ppm} ppm "
            f"(window +/- {self.window_ppm} ppm, radius {self.radius})"
        )

        if not self.has_data:
            lines.append("No data available")
            if self.warning:
                lines.append(f"Warning: {self.warning}")
            return "\n".join(lines)

        # Distribution line
        dist_parts = []
        excluded_parts = []

        for state, freq in [("sp3", self.distribution.sp3),
                           ("sp2", self.distribution.sp2),
                           ("sp1", self.distribution.sp1)]:
            if freq > 0.0:
                dist_parts.append(f"{state}={freq*100:.1f}%")
            elif freq == 0.0 and self.threshold > 0.0:
                # This state was excluded by threshold
                excluded_parts.append(state)

        dist_line = "Distribution: " + ", ".join(dist_parts)
        if excluded_parts:
            excluded_str = ", ".join(excluded_parts)
            dist_line += f" ({excluded_str} excluded, <{self.threshold*100:.0f}%)"
        lines.append(dist_line)

        # Dominant state
        dominant = self.distribution.dominant
        if dominant != "unknown":
            definitive = "definitive" if self.distribution.is_definitive else "not definitive"
            lines.append(f"Dominant: {dominant} ({definitive})")

        # Data coverage
        lines.append(
            f"Based on {self.total_observations:,} observations from "
            f"{self.unique_hose_codes} HOSE codes"
        )

        return "\n".join(lines)


class ConstraintType(str, Enum):
    """Classification of element constraints based on frequency."""

    FORBIDDEN = "forbidden"  # Below forbidden_threshold
    TYPICAL = "typical"  # Between thresholds
    MANDATORY = "mandatory"  # Above mandatory_threshold


class ElementConstraint(BaseModel):
    """Constraint on an element's presence as a bond partner.

    Classifies an element (C, O, N, S, halogen) based on its observed
    frequency in the database.
    """

    element: str  # Element name
    frequency: float  # Observed frequency (0.0 to 1.0)
    constraint_type: ConstraintType  # Classification


class NeighbourDistribution(BaseModel):
    """Distribution of bond partner elements for a carbon shift.

    Frequencies represent the proportion of observations where the
    carbon has at least one bond to the specified element type.

    Frequencies are NOT mutually exclusive (sum can exceed 1.0).
    """

    carbon: float = 0.0  # Frequency 0.0-1.0
    oxygen: float = 0.0
    nitrogen: float = 0.0
    sulfur: float = 0.0
    halogen: float = 0.0

    def get_constraints(
        self,
        forbidden_threshold: float = 0.01,
        mandatory_threshold: float = 0.95,
    ) -> list[ElementConstraint]:
        """Classify each element as forbidden, typical, or mandatory.

        Args:
            forbidden_threshold: Elements below this frequency are forbidden
            mandatory_threshold: Elements above this frequency are mandatory

        Returns:
            List of ElementConstraint objects for all elements
        """
        constraints = []

        for element_name in ["carbon", "oxygen", "nitrogen", "sulfur", "halogen"]:
            frequency = getattr(self, element_name)

            if frequency < forbidden_threshold:
                constraint_type = ConstraintType.FORBIDDEN
            elif frequency > mandatory_threshold:
                constraint_type = ConstraintType.MANDATORY
            else:
                constraint_type = ConstraintType.TYPICAL

            constraints.append(
                ElementConstraint(
                    element=element_name,
                    frequency=frequency,
                    constraint_type=constraint_type,
                )
            )

        return constraints

    @property
    def dominant_element(self) -> str | None:
        """Return the element name with the highest frequency, or None if all zero.

        Returns:
            "carbon", "oxygen", "nitrogen", "sulfur", "halogen", or None
        """
        elements = ["carbon", "oxygen", "nitrogen", "sulfur", "halogen"]
        max_freq = max(getattr(self, e) for e in elements)
        if max_freq == 0.0:
            return None
        for element_name in elements:
            if getattr(self, element_name) == max_freq:
                return element_name
        return None  # unreachable

    @property
    def forbidden_elements(self) -> list[str]:
        """Return elements with frequency below 1% (forbidden).

        Returns:
            List of element names
        """
        forbidden = []
        for element_name in ["carbon", "oxygen", "nitrogen", "sulfur", "halogen"]:
            frequency = getattr(self, element_name)
            if frequency < 0.01:
                forbidden.append(element_name)
        return forbidden

    @property
    def mandatory_elements(self) -> list[str]:
        """Return elements with frequency above 95% (mandatory).

        Returns:
            List of element names
        """
        mandatory = []
        for element_name in ["carbon", "oxygen", "nitrogen", "sulfur", "halogen"]:
            frequency = getattr(self, element_name)
            if frequency > 0.95:
                mandatory.append(element_name)
        return mandatory


class NeighbourResult(BaseModel):
    """Result of neighbourhood detection query.

    Contains both the frequency distribution and metadata about
    the query parameters and data coverage.
    """

    shift_ppm: float  # Queried shift
    window_ppm: float  # Query window used
    radius: int  # HOSE radius used
    forbidden_threshold: float = 0.01  # Threshold for forbidden classification
    mandatory_threshold: float = 0.95  # Threshold for mandatory classification
    distribution: NeighbourDistribution  # Element frequencies
    constraints: list[ElementConstraint] = []  # Classified constraints
    total_observations: int = 0  # Total count across all matching HOSE codes
    unique_hose_codes: int = 0  # Number of HOSE codes that contributed
    has_data: bool = False  # False if no matching HOSE codes or all counts are 0
    warning: str | None = None  # Warning message
    advisory: bool = True
    advisory_note: str = (
        "statistical prior — do not encode as a hard LSD constraint "
        "without direct connectivity evidence (HMBC/HSQC/exchangeable-H) "
        "or convergent multi-source corroboration. See FIX-10."
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dominant_element(self) -> str | None:
        """Return the dominant neighbour element from the distribution."""
        return self.distribution.dominant_element

    def summary(self) -> str:
        """Generate human-readable summary of detection result.

        Returns:
            Multi-line text summary
        """
        lines: list[str] = []
        lines.insert(0, f"[ADVISORY] {self.advisory_note}")

        # Header
        lines.append(
            f"Neighbourhood Detection: {self.shift_ppm} ppm "
            f"(window +/- {self.window_ppm} ppm, radius {self.radius})"
        )

        if not self.has_data:
            lines.append("No data available")
            if self.warning:
                lines.append(f"Warning: {self.warning}")
            return "\n".join(lines)

        # Distribution line - show non-zero elements
        dist_parts = []
        for element in ["carbon", "oxygen", "nitrogen", "sulfur", "halogen"]:
            freq = getattr(self.distribution, element)
            if freq > 0.0:
                dist_parts.append(f"{element[0].upper()}={freq*100:.1f}%")

        if dist_parts:
            lines.append("Distribution: " + ", ".join(dist_parts))

        # Forbidden elements
        forbidden = [
            c.element
            for c in self.constraints
            if c.constraint_type == ConstraintType.FORBIDDEN
        ]
        if forbidden:
            forbidden_str = ", ".join(
                f"{e} (<{self.forbidden_threshold*100:.1f}%)" for e in forbidden
            )
            lines.append(f"Forbidden: {forbidden_str}")

        # Mandatory elements
        mandatory = [
            c.element
            for c in self.constraints
            if c.constraint_type == ConstraintType.MANDATORY
        ]
        if mandatory:
            mandatory_str = ", ".join(
                f"{e} (>{self.mandatory_threshold*100:.1f}%)" for e in mandatory
            )
            lines.append(f"Mandatory: {mandatory_str}")

        # Dominant-neighbour advisory
        if self.dominant_element == "carbon":
            lines.append(
                "Dominant neighbour: carbon — likely carbon-substituted; "
                "heteroatom placement uncertain at this shift."
            )
        elif self.dominant_element is not None:
            lines.append(f"Dominant neighbour: {self.dominant_element}")

        # Data coverage
        lines.append(
            f"Based on {self.total_observations:,} observations from "
            f"{self.unique_hose_codes} HOSE codes"
        )

        return "\n".join(lines)


class BondPairInfo(BaseModel):
    """Information about a hetero-hetero bond pair."""

    element1: str  # First element (alphabetically)
    element2: str  # Second element (alphabetically)
    frequency: float  # Frequency of this bond pair (0.0 to 1.0)
    compound_count: int  # Number of compounds with this pair


class HHBResult(BaseModel):
    """Result of hetero-hetero bond detection query.

    Contains allowed and forbidden bond pairs for a molecular formula,
    based on frequency analysis of the compound database.
    """

    formula: str  # Queried formula
    threshold: float  # Threshold used for classification
    allowed_pairs: list[BondPairInfo] = []  # Pairs at or above threshold
    forbidden_pairs: list[BondPairInfo] = []  # Pairs below threshold
    total_compounds: int = 0  # Compounds with this formula in database
    has_data: bool = False  # True if formula found in database
    has_heteroatoms: bool = True  # False if formula has no heteroatoms
    warning: str | None = None  # Warning message

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = []

        lines.append(f"Hetero-Hetero Bond Detection: {self.formula}")
        lines.append(f"Threshold: {self.threshold * 100:.1f}%")

        if not self.has_heteroatoms:
            lines.append("No heteroatoms in formula — HHB analysis not applicable")
            return "\n".join(lines)

        if not self.has_data:
            lines.append("No data available")
            if self.warning:
                lines.append(f"Warning: {self.warning}")
            return "\n".join(lines)

        lines.append(f"Total compounds: {self.total_compounds:,}")

        if self.allowed_pairs:
            lines.append("")
            lines.append("Allowed bonds (>= threshold):")
            for pair in self.allowed_pairs:
                lines.append(
                    f"  {pair.element1}-{pair.element2}: "
                    f"{pair.frequency * 100:.1f}% "
                    f"({pair.compound_count:,} compounds)"
                )
        else:
            lines.append("")
            lines.append("No hetero-hetero bonds above threshold")

        if self.forbidden_pairs:
            lines.append("")
            lines.append("Forbidden bonds (< threshold):")
            for pair in self.forbidden_pairs:
                lines.append(
                    f"  {pair.element1}-{pair.element2}: "
                    f"{pair.frequency * 100:.2f}% "
                    f"({pair.compound_count:,} compounds)"
                )

        return "\n".join(lines)


class SignalGroup(BaseModel):
    """A group of chemically equivalent carbon signals.

    Represents a cluster of carbon shifts within tolerance, potentially
    representing the same carbon in different molecular environments
    (e.g., conformational flexibility, minor tautomers).
    """

    indices: list[int]  # 0-based indices in original shift list
    shifts: list[float]  # Shift values (ppm)
    multiplicities: list[str | None] | None = None  # Optional multiplicity labels
    span: float  # Max - min shift (ppm)
    centroid: float  # Mean shift (ppm)

    @property
    def atom_ids(self) -> list[int]:
        """Return 1-based atom IDs for LSD.

        LSD uses 1-based atom numbering, Python uses 0-based.
        """
        return [idx + 1 for idx in self.indices]

    def lsd_atom_list(self) -> str:
        """Format atom IDs for LSD EXCH command.

        Returns:
            For multiple atoms: "(1 2 3)"
            For single atom: "1"
        """
        if len(self.indices) == 1:
            return str(self.atom_ids[0])
        else:
            return f"({' '.join(str(aid) for aid in self.atom_ids)})"


class GroupingResult(BaseModel):
    """Result of signal grouping analysis.

    Contains groups of equivalent signals and ungrouped singletons,
    plus metadata about the grouping parameters.
    """

    tolerance: float  # Grouping tolerance (ppm)
    groups: list[SignalGroup] = []  # Multi-signal groups
    ungrouped: list[int] = []  # 0-based indices of ungrouped signals
    total_signals: int = 0  # Total number of input signals
    warnings: list[str] = []  # Warning messages

    def summary(self) -> str:
        """Generate human-readable summary of grouping result.

        Returns:
            Multi-line text summary
        """
        lines = []

        lines.append(f"Signal Grouping (tolerance {self.tolerance} ppm)")
        lines.append(f"Total signals: {self.total_signals}")
        lines.append(f"Groups: {len(self.groups)}")
        lines.append(f"Ungrouped: {len(self.ungrouped)}")

        if self.groups:
            lines.append("")
            lines.append("Groups:")
            for i, group in enumerate(self.groups, 1):
                shifts_str = ", ".join(f"{s:.2f}" for s in group.shifts)
                lines.append(
                    f"  Group {i}: [{shifts_str}] "
                    f"(span={group.span:.2f}, centroid={group.centroid:.2f})"
                )

        if self.ungrouped:
            lines.append("")
            lines.append(f"Ungrouped indices: {self.ungrouped}")

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  {warning}")

        return "\n".join(lines)
