"""LSD (Logic for Structure Determination) integration.

This module provides tools for structure elucidation using the LSD solver:

- **Models**: Data structures for LSD input (atoms, correlations, problems)
- **Generator**: Convert NMR peak data to LSD input files
- **Runner**: Execute LSD as subprocess
- **Parser**: Parse LSD output (solutions, SMILES)

Example usage:

```python
from lucy_ng import BrukerReader, DEPTGuidedPicker
from lucy_ng.lsd import LSDInputGenerator, LSDRunner

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

from lucy_ng.lsd.analyzer import (
    AnalysisResult,
    HMBCCorrelation,
    LSDSolutionAnalyzer,
    SolutionGraph,
)
from lucy_ng.lsd.generator import LSDInputGenerator
from lucy_ng.lsd.models import Hybridization, LSDAtom, LSDConstraint, LSDCorrelation, LSDProblem
from lucy_ng.lsd.parser import LSDOutputParser, LSDSolution
from lucy_ng.lsd.runner import LSDResult, LSDRunner

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
    "LSDOutputParser",
    "LSDSolution",
    # Analyzer
    "LSDSolutionAnalyzer",
    "SolutionGraph",
    "HMBCCorrelation",
    "AnalysisResult",
]
