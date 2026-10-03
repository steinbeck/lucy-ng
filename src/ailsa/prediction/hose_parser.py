"""Parse HOSE code sphere structure for element extraction."""

import re
from collections import Counter


def parse_sphere_1(hose_code: str) -> dict[str, int]:
    """Parse sphere 1 from HOSE code to extract bonded elements.

    HOSE format: "PREFIX;SPHERE1(SPHERE2/SPHERE3/...)"
    Sphere 1 contains bonded atoms as element symbols.

    Bond order prefixes:
    - "=" indicates double bond (e.g., "=O" is C=O)
    - "*" indicates aromatic bond (e.g., "*C" is aromatic C)
    - No prefix indicates single bond

    Args:
        hose_code: HOSE code string (e.g., "C-3;=OCO(,,//)")

    Returns:
        Dict mapping element symbol to count (e.g., {"O": 2, "C": 1})

    Example:
        parse_sphere_1("C-3;=OCO(,,//)") -> {"O": 2, "C": 1}
        parse_sphere_1("C-4;CCN(//)") -> {"C": 2, "N": 1}
        parse_sphere_1("C-3;*C*C(//)") -> {"C": 2}  # aromatic
    """
    # Split at semicolon to get prefix and spheres
    parts = hose_code.split(";", 1)
    if len(parts) < 2:
        return {}

    # Extract sphere 1 (before first parenthesis)
    spheres_part = parts[1]
    if "(" in spheres_part:
        sphere1 = spheres_part.split("(")[0]
    else:
        sphere1 = spheres_part

    # Parse element symbols
    # Remove bond order prefixes (=, *, /) and other HOSE syntax
    # Extract uppercase letters followed by optional lowercase
    elements = re.findall(r"[A-Z][a-z]?", sphere1)

    # Count occurrences
    return dict(Counter(elements))
