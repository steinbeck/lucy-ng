"""RDKit SVG depiction helpers for the ailsa webview dashboard.

Provides two public functions:
  render_smiles(smiles, width=300, height=300) -> str | None
  placeholder_svg(width=300, height=300) -> str

WV-08 import-safety: this module imports RDKit at module level.  It is only
ever reached via create_app() / the structures router, never imported at
package level — so the core CLI stays importable without RDKit.

RDKit import path (Pitfall 1): use ``from rdkit.Chem.Draw import rdMolDraw2D``
NOT ``from rdkit.Chem import rdMolDraw2D`` (the latter raises ImportError).

HOSE-code invariant: do NOT call AddHs() — render from implicit-H molecules
only, consistent with all other RDKit usage in this repo (CLAUDE.md).
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem.Draw import PrepareMolForDrawing, rdMolDraw2D


def render_smiles(smiles: str, width: int = 300, height: int = 300) -> str | None:
    """Render a SMILES string to an SVG string.

    Creates a fresh ``MolDraw2DSVG`` instance per call (Pitfall 6 — the
    drawer is stateful and must not be reused across calls).

    Args:
        smiles: A SMILES string to render.
        width:  SVG canvas width in pixels (default 300).
        height: SVG canvas height in pixels (default 300).

    Returns:
        An SVG string (starting with ``<?xml`` or ``<svg``) on success, or
        ``None`` if *smiles* is malformed and RDKit cannot parse it (D-11).
        Never raises.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None  # malformed SMILES — caller should use placeholder_svg()

    # Fresh drawer per call — MolDraw2DSVG is stateful (Pitfall 6)
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = drawer.drawOptions()
    opts.addAtomIndices = False  # type: ignore[assignment]  # RDKit stub limitation; clean publication style, no atom-index labels (D-09)
    opts.addStereoAnnotation = True  # type: ignore[assignment]  # RDKit stub limitation; keep stereo info — publication style

    try:
        PrepareMolForDrawing(mol)
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
    except Exception:
        # A SMILES can parse via MolFromSmiles yet fail 2D preparation/drawing
        # (e.g. KekulizeException for some aromatic systems). Treat as
        # unrenderable so the caller falls back to placeholder_svg(); the SVG
        # endpoint must never surface a 500 (D-11). Honours "Never raises".
        return None
    return drawer.GetDrawingText()


def placeholder_svg(width: int = 300, height: int = 300) -> str:
    """Return a minimal placeholder SVG for an entry that cannot be rendered.

    The placeholder is a static grey rectangle with a centred "?" glyph.
    It contains no ``<script>`` elements and no external references (D-11 /
    T-91-07 XSS mitigation).

    Args:
        width:  SVG canvas width in pixels (default 300).
        height: SVG canvas height in pixels (default 300).

    Returns:
        A self-contained SVG string.
    """
    cx = width // 2
    cy = height // 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="#f0f0f0" stroke="#ccc" stroke-width="1"/>'
        f'<text x="{cx}" y="{cy}" text-anchor="middle" '
        f'dominant-baseline="middle" font-size="48" fill="#999">?</text>'
        f"</svg>"
    )
