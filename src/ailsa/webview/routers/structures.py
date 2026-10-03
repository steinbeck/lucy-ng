"""GET /api/structures and GET /api/structure/{i}.svg router.

Provides the candidate-structures widget: a ranked or unranked list of SMILES
and an on-demand RDKit SVG depiction endpoint.

Source fallback tiers (D-05 / D-06 / D-08):
  1. ranking_results.json (finalized)  → source "ranked",  top 10 by rank
  2. newest iteration_NN/solutions.smi → source "unranked", first 10 in file order
  3. no data at all                    → source "waiting",  structures=[]

SVG endpoint (D-09 / D-10 / D-11):
  - On-demand render; no server-side cache.
  - Index i is 0-based and resolved against the FULL (uncapped) list.
  - Out-of-range → HTTP 404 (generic detail, no length leakage — T-91-06).
  - Malformed SMILES → placeholder SVG, HTTP 200 (WV-06).

WV-08 import-safety: this module imports fastapi at module level (permitted —
only ever reached from inside create_app() or test bodies).  It imports RDKit
via ailsa.webview.depiction INSIDE make_router() so RDKit is never loaded
at package import time.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

_CAP = 10  # maximum structures returned in the /structures list (D-07)


def make_router(analysis_dir: Path) -> APIRouter:
    """Return an APIRouter(prefix='/api') with structures routes.

    Imports ailsa.webview.depiction (which loads RDKit) inside this factory
    so RDKit is never pulled in at webview package import time (WV-08).

    Args:
        analysis_dir: Path to the CASE analysis directory (already resolved
            by create_app; do NOT call .resolve() here again).

    Returns:
        An APIRouter with:
        - GET /structures  → JSON payload {source, total, structures}
        - GET /structure/{i}.svg → SVG response or 404
    """
    # Lazy RDKit import — only reached via create_app() (WV-08)
    from ailsa.webview.depiction import placeholder_svg, render_smiles

    router = APIRouter(prefix="/api")

    @router.get("/structures")
    def get_structures() -> dict[str, Any]:
        source, all_structs, total = _load_all_structures(analysis_dir)
        return {
            "source": source,
            "total": total,
            "structures": all_structs[:_CAP],
        }

    @router.get("/structure/{i}.svg")
    def get_structure_svg(i: int) -> Response:
        # Load the FULL (uncapped) list so index resolution is correct (D-07 note)
        _source, all_structs, _total = _load_all_structures(analysis_dir)

        if i < 0 or i >= len(all_structs):
            # T-91-06: generic detail only — do not leak list length
            raise HTTPException(status_code=404, detail="Structure not found")

        smiles = all_structs[i]["smiles"]
        svg = render_smiles(smiles)
        if svg is None:
            svg = placeholder_svg()  # D-11: malformed SMILES → placeholder

        return Response(content=svg, media_type="image/svg+xml")

    return router


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_all_structures(
    analysis_dir: Path,
) -> tuple[str, list[dict[str, Any]], int]:
    """Load structure entries from the best available source.

    Returns (source, all_entries, total) where:
    - source: "ranked" | "unranked" | "waiting"
    - all_entries: full (uncapped) list of {index, smiles, rank, mae, quality}
    - total: total number of solutions in the source file

    Never raises — all I/O is guarded (WV-06 / D-04).
    """
    # ------------------------------------------------------------------
    # Tier 1: ranking_results.json (finalized)
    # ------------------------------------------------------------------
    ranking_json = analysis_dir / "ranking_results.json"
    if ranking_json.exists():
        try:
            data = json.loads(ranking_json.read_text(encoding="utf-8"))
            solutions = data.get("solutions", [])
            total = int(data.get("total_solutions", len(solutions)))

            # Sort by rank ascending (rank 1 = best). A present-but-null rank
            # (partially-ranked run) must NOT reach sorted() as None — that
            # raises TypeError and silently drops the whole ranked tier
            # (caught below). Treat null rank as "last".
            solutions_sorted = sorted(
                solutions,
                key=lambda s: s["rank"] if s.get("rank") is not None else 999999,
            )

            entries: list[dict[str, Any]] = [
                {
                    "index": idx,
                    "smiles": str(s.get("smiles", "")),
                    "rank": s.get("rank"),
                    "mae": s.get("mae"),
                    "quality": s.get("quality"),
                }
                for idx, s in enumerate(solutions_sorted)
            ]
            return ("ranked", entries, total)
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
            pass  # fall through to unranked

    # ------------------------------------------------------------------
    # Tier 2: newest iteration_NN/solutions.smi (live run)
    # ------------------------------------------------------------------
    smi_path = _newest_solutions_smi(analysis_dir)
    if smi_path is not None:
        try:
            raw = smi_path.read_text(encoding="utf-8")
            smiles_lines = _parse_smi_lines(raw)
            total = len(smiles_lines)
            entries = [
                {
                    "index": idx,
                    "smiles": smi,
                    "rank": None,
                    "mae": None,
                    "quality": None,
                }
                for idx, smi in enumerate(smiles_lines)
            ]
            return ("unranked", entries, total)
        except OSError:
            pass  # file disappeared mid-read — fall through

    # ------------------------------------------------------------------
    # Tier 3: no data
    # ------------------------------------------------------------------
    return ("waiting", [], 0)


def _newest_solutions_smi(analysis_dir: Path) -> Path | None:
    """Return the solutions.smi from the highest-numbered iteration_NN folder.

    Uses integer suffix comparison (Pitfall 5 — string sort is wrong).
    """
    candidates: list[tuple[int, Path]] = []
    for p in analysis_dir.glob("iteration_*/solutions.smi"):
        m = re.match(r"iteration_(\d+)$", p.parent.name)
        if m:
            candidates.append((int(m.group(1)), p))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]


def _parse_smi_lines(content: str) -> list[str]:
    """Parse a solutions.smi file, returning only valid SMILES lines.

    Blank lines and lines starting with '#' or ';' are comments and
    are skipped, consistent with LSDOutputParser.parse_smiles_file.
    """
    result: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith(";"):
            continue
        result.append(stripped)
    return result
