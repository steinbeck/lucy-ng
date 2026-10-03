"""ailsa: AI-agent powered Computer-Assisted Structure Elucidation."""

from ailsa.analysis import (
    HydrogenBudgetAnalyzer,
    IntensityReporter,
    SymmetryAnalyzer,
)
from ailsa.models import Peak1D, Peak2D, PeakList1D, PeakList2D, Spectrum1D, Spectrum2D
from ailsa.prediction import C13Predictor, HOSECodeGenerator, HOSELookupTable
from ailsa.processing import (
    AdaptivePeakPicker,
    DEPTGuidedPicker,
    DEPTGuidedResult,
    PeakPicker2D,
    PeakValidator,
    ValidationResult,
)
from ailsa.readers import BrukerReader

# LSD integration (import from ailsa.lsd for full access)
from ailsa.lsd import LSDInputGenerator, LSDProblem, LSDRunner

# Ranking
from ailsa.ranking import SolutionRanker

# NMRXiv
from ailsa.nmrxiv import NMRXivClient

__version__ = "0.1.0"

__all__ = [
    # Readers
    "BrukerReader",
    # Models
    "Peak1D",
    "Peak2D",
    "PeakList1D",
    "PeakList2D",
    "Spectrum1D",
    "Spectrum2D",
    # Processing
    "AdaptivePeakPicker",
    "DEPTGuidedPicker",
    "DEPTGuidedResult",
    "PeakPicker2D",
    "PeakValidator",
    "ValidationResult",
    # Analysis
    "HydrogenBudgetAnalyzer",
    "IntensityReporter",
    "SymmetryAnalyzer",
    # Prediction
    "C13Predictor",
    "HOSECodeGenerator",
    "HOSELookupTable",
    # LSD
    "LSDInputGenerator",
    "LSDProblem",
    "LSDRunner",
    # Ranking
    "SolutionRanker",
    # NMRXiv
    "NMRXivClient",
]
