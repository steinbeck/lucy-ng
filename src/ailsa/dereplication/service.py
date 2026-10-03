"""Dereplication service for matching unknown compounds against nmrshiftdb."""

from dataclasses import dataclass

from ailsa.dereplication.matcher import (
    MatchingConfig,
    MatchMode,
    MatchResult,
    ObservedPeak,
    SpectrumMatcher,
)
from ailsa.dereplication.nmrshiftdb import HydrogenCount, NMRShiftDBLoader
from ailsa.models import Spectrum1D
from ailsa.processing import AdaptivePeakPicker


@dataclass
class DereplicationResult:
    """Complete dereplication result."""

    molecular_formula: str
    expected_carbons: int
    observed_peaks: int
    candidates_found: int
    top_matches: list[MatchResult]
    best_score: float
    is_match: bool  # True if best_score > threshold
    match_mode: MatchMode


class DereplicationService:
    """Main service for dereplicating unknown compounds.

    Provides three entry points for different data quality levels:
    - dereplicate_from_shifts: Just ppm values
    - dereplicate_from_peaks: With optional DEPT H-counts
    - dereplicate_from_spectrum: Full automation with peak picking
    """

    def __init__(
        self,
        db_loader: NMRShiftDBLoader,
        matcher: SpectrumMatcher | None = None,
    ):
        """Initialize with database loader and optional matcher.

        Args:
            db_loader: NMRShiftDBLoader instance (must call load() before use)
            matcher: Optional SpectrumMatcher. Creates default if None.
        """
        self.db_loader = db_loader
        self.matcher = matcher or SpectrumMatcher()

    def dereplicate_from_spectrum(
        self,
        spectrum: Spectrum1D,
        molecular_formula: str,
        peak_threshold: float = 0.05,
        top_n: int = 5,
        match_threshold: float = 0.7,
    ) -> DereplicationResult:
        """Dereplicate from raw spectrum (picks peaks automatically).

        Args:
            spectrum: 1D 13C spectrum
            molecular_formula: Molecular formula (e.g., "C13H18O2")
            peak_threshold: Intensity threshold for peak picking (fraction of max)
            top_n: Number of top matches to return
            match_threshold: Score above which to consider a match

        Returns:
            DereplicationResult with candidates and match status
        """
        # Pick peaks from spectrum
        peak_list = AdaptivePeakPicker.pick_peaks(spectrum, threshold=peak_threshold)

        # Convert to ObservedPeak (no DEPT info from raw spectrum)
        observed = [ObservedPeak(shift=p.position) for p in peak_list.peaks]

        return self._dereplicate(
            observed=observed,
            molecular_formula=molecular_formula,
            top_n=top_n,
            match_threshold=match_threshold,
            mode=MatchMode.SHIFTS_ONLY,
        )

    def dereplicate_from_peaks(
        self,
        peaks: list[ObservedPeak],
        molecular_formula: str,
        top_n: int = 5,
        match_threshold: float = 0.7,
    ) -> DereplicationResult:
        """Dereplicate from pre-picked peaks (with optional DEPT info).

        Use this when:
        - Peaks have been manually curated/verified
        - DEPT information is available from separate experiment
        - AI has processed and annotated the peak list

        Args:
            peaks: List of observed peaks with optional hydrogen counts
            molecular_formula: Molecular formula (e.g., "C13H18O2")
            top_n: Number of top matches to return
            match_threshold: Score above which to consider a match

        Returns:
            DereplicationResult with candidates and match status
        """
        # Determine mode based on whether DEPT info is present
        has_dept = any(p.hydrogen_count is not None for p in peaks)
        mode = MatchMode.DEPT_ENHANCED if has_dept else MatchMode.SHIFTS_ONLY

        return self._dereplicate(
            observed=peaks,
            molecular_formula=molecular_formula,
            top_n=top_n,
            match_threshold=match_threshold,
            mode=mode,
        )

    def dereplicate_from_shifts(
        self,
        shifts: list[float],
        molecular_formula: str,
        top_n: int = 5,
        match_threshold: float = 0.7,
    ) -> DereplicationResult:
        """Dereplicate from just a list of chemical shifts.

        Simplest interface for quick screening.

        Args:
            shifts: List of 13C chemical shifts in ppm
            molecular_formula: Molecular formula (e.g., "C13H18O2")
            top_n: Number of top matches to return
            match_threshold: Score above which to consider a match

        Returns:
            DereplicationResult with candidates and match status
        """
        observed = [ObservedPeak(shift=s) for s in shifts]

        return self._dereplicate(
            observed=observed,
            molecular_formula=molecular_formula,
            top_n=top_n,
            match_threshold=match_threshold,
            mode=MatchMode.SHIFTS_ONLY,
        )

    def _dereplicate(
        self,
        observed: list[ObservedPeak],
        molecular_formula: str,
        top_n: int,
        match_threshold: float,
        mode: MatchMode,
    ) -> DereplicationResult:
        """Internal dereplication implementation.

        Args:
            observed: List of observed peaks
            molecular_formula: Target molecular formula
            top_n: Number of top matches to return
            match_threshold: Score threshold for is_match
            mode: Matching mode to use

        Returns:
            DereplicationResult with match details
        """
        # Update matcher config for this mode
        self.matcher.config.mode = mode

        # Get candidates by formula
        candidates = self.db_loader.get_by_formula(molecular_formula)

        if not candidates:
            # No candidates found for this formula
            carbon_count = NMRShiftDBLoader.count_carbons(molecular_formula)
            return DereplicationResult(
                molecular_formula=molecular_formula,
                expected_carbons=carbon_count,
                observed_peaks=len(observed),
                candidates_found=0,
                top_matches=[],
                best_score=0.0,
                is_match=False,
                match_mode=mode,
            )

        # Match against all candidates
        results = self.matcher.match_all(observed, candidates)

        # Take top N
        top_matches = results[:top_n]

        # Determine if it's a match
        best_score = top_matches[0].score if top_matches else 0.0
        is_match = best_score >= match_threshold

        return DereplicationResult(
            molecular_formula=molecular_formula,
            expected_carbons=candidates[0].carbon_count if candidates else 0,
            observed_peaks=len(observed),
            candidates_found=len(candidates),
            top_matches=top_matches,
            best_score=best_score,
            is_match=is_match,
            match_mode=mode,
        )


def create_observed_peaks_with_dept(
    shifts: list[float],
    hydrogen_counts: list[HydrogenCount | None],
) -> list[ObservedPeak]:
    """Helper to create ObservedPeak list with DEPT info.

    Args:
        shifts: List of chemical shifts in ppm
        hydrogen_counts: List of hydrogen counts (same length as shifts)

    Returns:
        List of ObservedPeak with DEPT information
    """
    if len(shifts) != len(hydrogen_counts):
        raise ValueError("shifts and hydrogen_counts must have same length")

    return [
        ObservedPeak(shift=s, hydrogen_count=h) for s, h in zip(shifts, hydrogen_counts)
    ]
