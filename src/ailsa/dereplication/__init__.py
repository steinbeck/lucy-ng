"""Dereplication module for matching compounds against reference databases."""

from ailsa.dereplication.coconut import CoconutLoader
from ailsa.dereplication.matcher import (
    MatchingConfig,
    MatchMode,
    MatchResult,
    ObservedPeak,
    PeakMatch,
    SpectrumMatcher,
)
from ailsa.dereplication.nmrshiftdb import (
    CarbonSignal,
    HydrogenCount,
    NMRShiftDBEntry,
    NMRShiftDBLoader,
)
from ailsa.dereplication.service import (
    DereplicationResult,
    DereplicationService,
    create_observed_peaks_with_dept,
)
from ailsa.dereplication.sherlock import (
    SherlockEntry,
    SherlockLoader,
)

__all__ = [
    # coconut
    "CoconutLoader",
    # nmrshiftdb
    "HydrogenCount",
    "CarbonSignal",
    "NMRShiftDBEntry",
    "NMRShiftDBLoader",
    # sherlock
    "SherlockEntry",
    "SherlockLoader",
    # matcher
    "MatchMode",
    "MatchingConfig",
    "PeakMatch",
    "MatchResult",
    "ObservedPeak",
    "SpectrumMatcher",
    # service
    "DereplicationResult",
    "DereplicationService",
    "create_observed_peaks_with_dept",
]
