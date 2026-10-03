"""Analysis tools for AI-driven structure elucidation.

This module provides convenience tools that expose spectroscopic data
in formats suitable for AI reasoning about molecular structure.

The philosophy is: **tools expose data; the AI provides reasoning**.

Available tools:

- **HydrogenBudgetAnalyzer**: Compare MF hydrogen count with observed
- **IntensityReporter**: Report relative HSQC peak intensities
- **SymmetryAnalyzer**: Combined symmetry analysis summary

Example:
    >>> from ailsa import BrukerReader
    >>> from ailsa.processing import DEPTGuidedPicker
    >>> from ailsa.analysis import SymmetryAnalyzer
    >>>
    >>> hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
    >>> dept = BrukerReader.read_1d("data/Ibuprofen/3")
    >>> dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)
    >>>
    >>> result = SymmetryAnalyzer.analyze("C13H18O2", dept_result, hsqc)
    >>> print(result.summary())
"""

from ailsa.analysis.hydrogen_budget import (
    CarbonHInfo,
    HydrogenBudgetAnalyzer,
    HydrogenBudgetResult,
)
from ailsa.analysis.intensity_reporter import (
    IntensityReport,
    IntensityReporter,
    PeakIntensityInfo,
)
from ailsa.analysis.symmetry_analysis import (
    SymmetryAnalysisResult,
    SymmetryAnalyzer,
)

__all__ = [
    # Hydrogen budget
    "CarbonHInfo",
    "HydrogenBudgetAnalyzer",
    "HydrogenBudgetResult",
    # Intensity reporter
    "IntensityReport",
    "IntensityReporter",
    "PeakIntensityInfo",
    # Symmetry analysis
    "SymmetryAnalysisResult",
    "SymmetryAnalyzer",
]
