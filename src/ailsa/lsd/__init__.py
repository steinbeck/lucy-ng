"""LSD (Logic for Structure Determination) integration.

This module provides tools for structure elucidation using the LSD solver:

- **Models**: Data structures for LSD input (atoms, correlations, problems)
- **Generator**: Convert NMR peak data to LSD input files
- **Runner**: Execute LSD as subprocess
- **Parser**: Parse LSD output (solutions, SMILES)

Example usage:

```python
from ailsa import BrukerReader, DEPTGuidedPicker
from ailsa.lsd import LSDInputGenerator, LSDRunner

# Load spectra and pick peaks
hsqc = BrukerReader.read_2d("data/sample/hsqc")
dept = BrukerReader.read_1d("data/sample/dept135")
result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept)

# Generate LSD problem
problem = LSDInputGenerator.from_dept_result(
    dept_result=result,
    molecular_formula="C10H12O2",
)

# Write input file
print(LSDInputGenerator.generate(problem))

# Run LSD (if installed)
if LSDRunner.is_available():
    runner = LSDRunner()
    lsd_result = runner.run(problem)
    print(f"Found {lsd_result.solution_count} solutions")
```
"""

from ailsa.lsd.analyzer import (
    AnalysisResult,
    HMBCCorrelation,
    LSDSolutionAnalyzer,
    SolutionGraph,
)
from ailsa.lsd.generator import LSDInputGenerator
from ailsa.lsd.models import Hybridization, LSDAtom, LSDConstraint, LSDCorrelation, LSDProblem
from ailsa.lsd.orchestrator import (
    MergeResult,
    MergedSolution,
    OrchestrationResult,
    PermutationResult,
    PyLSDOrchestrator,
    SolutionMerger,
)
from ailsa.lsd.parser import LSDInputParser, LSDOutputParser, LSDSolution
from ailsa.lsd.runner import LSDResult, LSDRunner

__all__ = [
    # Models
    "Hybridization",
    "LSDAtom",
    "LSDConstraint",
    "LSDCorrelation",
    "LSDProblem",
    # Generator
    "LSDInputGenerator",
    # Runner
    "LSDRunner",
    "LSDResult",
    # Parser
    "LSDInputParser",
    "LSDOutputParser",
    "LSDSolution",
    # Analyzer
    "LSDSolutionAnalyzer",
    "SolutionGraph",
    "HMBCCorrelation",
    "AnalysisResult",
    # Orchestrator
    "PyLSDOrchestrator",
    "PermutationResult",
    "OrchestrationResult",
    "SolutionMerger",
    "MergedSolution",
    "MergeResult",
]
