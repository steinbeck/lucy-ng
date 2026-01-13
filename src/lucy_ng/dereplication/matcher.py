"""Spectrum matching for dereplication."""

from dataclasses import dataclass, field
from enum import Enum

from lucy_ng.dereplication.nmrshiftdb import CarbonSignal, HydrogenCount, NMRShiftDBEntry


class MatchMode(Enum):
    """Matching mode based on available data."""

    SHIFTS_ONLY = "shifts_only"  # Just chemical shifts
    DEPT_ENHANCED = "dept_enhanced"  # Shifts + hydrogen count from DEPT


@dataclass
class MatchingConfig:
    """Configuration for spectrum matching."""

    mode: MatchMode = MatchMode.SHIFTS_ONLY
    tolerance_ppm: float = 1.0  # Default tolerance
    use_variable_tolerance: bool = True  # Region-dependent tolerances
    aliphatic_tolerance: float = 0.8  # 0-80 ppm
    aromatic_tolerance: float = 1.2  # 100-160 ppm
    carbonyl_tolerance: float = 1.5  # 160-220 ppm
    dept_mismatch_penalty: float = 0.5  # Score multiplier when DEPT doesn't match

    def get_tolerance(self, shift: float) -> float:
        """Get tolerance for a given chemical shift region.

        Args:
            shift: Chemical shift in ppm

        Returns:
            Tolerance in ppm for this region
        """
        if not self.use_variable_tolerance:
            return self.tolerance_ppm
        if shift < 80:
            return self.aliphatic_tolerance
        elif shift < 100:
            return self.tolerance_ppm  # Transition region
        elif shift < 160:
            return self.aromatic_tolerance
        else:
            return self.carbonyl_tolerance


@dataclass
class PeakMatch:
    """Details of a single peak match."""

    observed_shift: float
    reference_shift: float
    deviation: float  # Absolute difference in ppm
    observed_h_count: HydrogenCount | None = None
    reference_h_count: HydrogenCount | None = None
    dept_match: bool | None = None  # None if DEPT not available


@dataclass
class MatchResult:
    """Result of matching observed peaks against a reference."""

    entry: NMRShiftDBEntry
    score: float  # 0-1, higher is better match
    matched_peaks: int
    total_observed: int
    total_reference: int
    expected_carbons: int  # From molecular formula
    dept_matches: int | None = None  # Count of peaks with matching DEPT
    peak_matches: list[PeakMatch] = field(default_factory=list)
    unmatched_observed: list[float] = field(default_factory=list)
    unmatched_reference: list[float] = field(default_factory=list)


@dataclass
class ObservedPeak:
    """Observed peak with optional DEPT info for matching."""

    shift: float
    hydrogen_count: HydrogenCount | None = None


class SpectrumMatcher:
    """Match observed peaks against reference spectra with fuzzy tolerances."""

    def __init__(self, config: MatchingConfig | None = None):
        """Initialize with matching configuration.

        Args:
            config: Matching configuration. Uses defaults if None.
        """
        self.config = config or MatchingConfig()

    def match(
        self,
        observed: list[ObservedPeak],
        reference: NMRShiftDBEntry,
    ) -> MatchResult:
        """Score how well observed peaks match a reference.

        Algorithm:
        1. For each observed peak, find closest reference peak within tolerance
        2. Track matched, unmatched observed, and unmatched reference peaks
        3. If DEPT mode, track how many matches have consistent hydrogen counts
        4. Calculate score accounting for expected overlap

        Args:
            observed: List of observed peaks with optional DEPT info
            reference: Reference entry from nmrshiftdb

        Returns:
            MatchResult with score and match details
        """
        if not observed:
            return MatchResult(
                entry=reference,
                score=0.0,
                matched_peaks=0,
                total_observed=0,
                total_reference=len(reference.signals),
                expected_carbons=reference.carbon_count,
            )

        # Create a copy of reference signals to track which are matched
        available_refs = list(reference.signals)
        peak_matches: list[PeakMatch] = []
        unmatched_observed: list[float] = []
        dept_matches = 0

        # Sort observed peaks by shift for consistent matching
        sorted_observed = sorted(observed, key=lambda p: p.shift)

        for obs_peak in sorted_observed:
            best_ref, deviation = self._find_best_match(obs_peak.shift, available_refs)

            if best_ref is not None:
                # Check DEPT match if in DEPT mode
                dept_match = None
                if self.config.mode == MatchMode.DEPT_ENHANCED:
                    if obs_peak.hydrogen_count is not None and best_ref.hydrogen_count is not None:
                        dept_match = obs_peak.hydrogen_count == best_ref.hydrogen_count
                        if dept_match:
                            dept_matches += 1

                peak_matches.append(
                    PeakMatch(
                        observed_shift=obs_peak.shift,
                        reference_shift=best_ref.shift,
                        deviation=deviation,
                        observed_h_count=obs_peak.hydrogen_count,
                        reference_h_count=best_ref.hydrogen_count,
                        dept_match=dept_match,
                    )
                )
                # Remove matched reference from available pool
                available_refs.remove(best_ref)
            else:
                unmatched_observed.append(obs_peak.shift)

        # Unmatched reference peaks
        unmatched_reference = [sig.shift for sig in available_refs]

        # Calculate score
        score = self._calculate_score(
            matched_peaks=len(peak_matches),
            observed_peaks=len(observed),
            reference_peaks=len(reference.signals),
            expected_carbons=reference.carbon_count,
            dept_matches=dept_matches if self.config.mode == MatchMode.DEPT_ENHANCED else None,
        )

        return MatchResult(
            entry=reference,
            score=score,
            matched_peaks=len(peak_matches),
            total_observed=len(observed),
            total_reference=len(reference.signals),
            expected_carbons=reference.carbon_count,
            dept_matches=dept_matches if self.config.mode == MatchMode.DEPT_ENHANCED else None,
            peak_matches=peak_matches,
            unmatched_observed=unmatched_observed,
            unmatched_reference=unmatched_reference,
        )

    def match_all(
        self,
        observed: list[ObservedPeak],
        references: list[NMRShiftDBEntry],
    ) -> list[MatchResult]:
        """Match against all references, return sorted by score descending.

        Args:
            observed: List of observed peaks
            references: List of reference entries to match against

        Returns:
            List of MatchResult sorted by score (highest first), then by
            average deviation (lowest first) as tiebreaker
        """
        results = [self.match(observed, ref) for ref in references]
        # Sort by score descending, then by average deviation ascending as tiebreaker
        results.sort(key=lambda r: (-r.score, self._avg_deviation(r)))
        return results

    @staticmethod
    def _avg_deviation(result: MatchResult) -> float:
        """Calculate average deviation for a match result."""
        if result.peak_matches:
            return sum(pm.deviation for pm in result.peak_matches) / len(result.peak_matches)
        return float("inf")

    def _find_best_match(
        self,
        observed_shift: float,
        available_refs: list[CarbonSignal],
    ) -> tuple[CarbonSignal | None, float]:
        """Find best matching reference peak within tolerance.

        Args:
            observed_shift: The observed chemical shift
            available_refs: List of available (unmatched) reference signals

        Returns:
            Tuple of (matched_signal, deviation) or (None, inf) if no match
        """
        if not available_refs:
            return None, float("inf")

        tolerance = self.config.get_tolerance(observed_shift)
        best_match = None
        best_deviation = float("inf")

        for ref_signal in available_refs:
            deviation = abs(observed_shift - ref_signal.shift)
            if deviation <= tolerance and deviation < best_deviation:
                best_match = ref_signal
                best_deviation = deviation

        return best_match, best_deviation

    def _calculate_score(
        self,
        matched_peaks: int,
        observed_peaks: int,
        reference_peaks: int,
        expected_carbons: int,
        dept_matches: int | None,
    ) -> float:
        """Calculate match score accounting for expected overlap.

        The overlap_factor adjusts for the fact that observed peaks
        are often fewer than expected carbons due to signal overlap.

        Args:
            matched_peaks: Number of peaks that matched
            observed_peaks: Total observed peaks
            reference_peaks: Total reference peaks
            expected_carbons: Expected carbons from molecular formula
            dept_matches: Count of DEPT-matching peaks (or None if not in DEPT mode)

        Returns:
            Score between 0 and 1
        """
        if observed_peaks == 0 or reference_peaks == 0:
            return 0.0

        # Overlap factor: if observed < expected, don't penalize reference misses as harshly
        # This accounts for overlapping signals in real spectra
        overlap_factor = min(1.0, observed_peaks / expected_carbons) if expected_carbons > 0 else 1.0

        # How well do observed peaks match something?
        coverage = matched_peaks / observed_peaks

        # How much of the reference did we match?
        # Adjusted by overlap expectation, capped at 1.0
        adjusted_reference = reference_peaks * overlap_factor
        reference_coverage = min(
            1.0,
            matched_peaks / adjusted_reference if adjusted_reference > 0 else 0.0
        )

        # Base score: geometric mean of coverages (both are now <= 1.0)
        base_score = (coverage * reference_coverage) ** 0.5

        # DEPT: penalize mismatches (shifts match but DEPT doesn't)
        if dept_matches is not None and matched_peaks > 0:
            dept_ratio = dept_matches / matched_peaks
            # Penalize up to 20% for DEPT mismatches
            base_score *= 0.8 + 0.2 * dept_ratio

        return base_score
