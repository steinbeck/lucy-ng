"""Statistical detection of structural constraints from NMR shifts."""

from ailsa.detection.detector import StatisticalDetector
from ailsa.detection.grouping import group_signals
from ailsa.detection.models import (
    GroupingResult,
    HHBResult,
    HybridisationResult,
    NeighbourResult,
)

__all__ = [
    "StatisticalDetector",
    "GroupingResult",
    "HHBResult",
    "HybridisationResult",
    "NeighbourResult",
    "group_signals",
]
