"""NMR correlation diagram visualization.

This module provides tools for generating publication-quality diagrams
showing molecular structures with NMR correlation arrows.

Example:
    >>> from lucy_ng.visualization import CorrelationDiagramGenerator, Correlation, CorrelationType
    >>> gen = CorrelationDiagramGenerator()
    >>> result = gen.generate(
    ...     smiles="CCO",
    ...     correlations=[
    ...         Correlation(source_atom=0, target_atom=1, correlation_type=CorrelationType.HMBC),
    ...     ],
    ... )
    >>> print(result.svg_content[:50])
    <?xml version="1.0" encoding="UTF-8"?>
"""

from .arrow_router import ArrowRouter, fan_out_arrows
from .diagram_generator import CorrelationDiagramGenerator
from .models import (
    ArrowStyle,
    AtomPosition,
    Correlation,
    CorrelationType,
    DiagramConfig,
    DiagramResult,
    RoutedArrow,
)
from .svg_builder import SVGBuilder

__all__ = [
    # Main generator
    "CorrelationDiagramGenerator",
    # Models
    "ArrowStyle",
    "AtomPosition",
    "Correlation",
    "CorrelationType",
    "DiagramConfig",
    "DiagramResult",
    "RoutedArrow",
    # Utilities
    "ArrowRouter",
    "SVGBuilder",
    "fan_out_arrows",
]
