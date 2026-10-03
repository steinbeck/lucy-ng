"""GET /api/tables/{carbon,hsqc,hmbc,cosy,constraints} router (TBL-01/02/03).

Five independent, read-only GET routes serving the Tables tab data:
  - /api/tables/carbon      -> analysis/peaks/carbon_signals.json
  - /api/tables/hsqc        -> analysis/peaks/hsqc.json
  - /api/tables/hmbc        -> analysis/peaks/hmbc.json (row.flag passthrough)
  - /api/tables/cosy        -> analysis/peaks/cosy.json
  - /api/tables/constraints -> newest iteration_NN[_family]/compound.lsd,
    CONSTRAINT INVENTORY v2 JSON block

Every route degrades to a "waiting" payload (HTTP 200) on any failure —
absent file, partial/malformed JSON, missing/malformed LSD inventory block.
Never raises a 500 (SC4).

WV-08 import-safety: this module imports fastapi at module level, which is
permitted because it is ONLY ever imported from inside create_app() and
from test bodies.  It must NOT be imported from webview/__init__.py,
webview/server.py, or webview/state.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter

# Broad except tuple for JSON-parsing readers (RESEARCH.md Pitfall 1 — the
# narrower (FileNotFoundError, OSError) used by log.py is insufficient once
# json.loads()/.get()/indexing are involved).
_JSON_READ_ERRORS = (
    FileNotFoundError,
    json.JSONDecodeError,
    OSError,
    KeyError,
    TypeError,
    ValueError,
)


def make_router(analysis_dir: Path) -> APIRouter:
    """Return an APIRouter(prefix='/api') with the 5 tables routes.

    Args:
        analysis_dir: Path to the CASE analysis directory (already resolved
            by create_app; do NOT call .resolve() here again).

    Returns:
        An APIRouter with GET /tables/{carbon,hsqc,hmbc,cosy,constraints}
        closed over analysis_dir.
    """
    router = APIRouter(prefix="/api")

    @router.get("/tables/carbon")
    def get_carbon() -> dict[str, Any]:
        return _read_carbon(analysis_dir)

    @router.get("/tables/hsqc")
    def get_hsqc() -> dict[str, Any]:
        return _read_hsqc(analysis_dir)

    @router.get("/tables/hmbc")
    def get_hmbc() -> dict[str, Any]:
        return _read_hmbc(analysis_dir)

    @router.get("/tables/cosy")
    def get_cosy() -> dict[str, Any]:
        return _read_cosy(analysis_dir)

    @router.get("/tables/constraints")
    def get_constraints() -> dict[str, Any]:
        return _read_constraints(analysis_dir)

    return router


# ---------------------------------------------------------------------------
# Internal helpers — peaks JSON readers (TBL-01 / TBL-02)
# ---------------------------------------------------------------------------


def _read_carbon(analysis_dir: Path) -> dict[str, Any]:
    """Read analysis/peaks/carbon_signals.json.

    Returns:
        {"state": "ok", "note", "counts", "rows"} on success.
        {"state": "waiting", "note": None, "counts": {}, "rows": []} on any
        failure (absent file, malformed/partial JSON — never raises).
    """
    p = analysis_dir / "peaks" / "carbon_signals.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        signals = data.get("signals", [])
        return {
            "state": "ok",
            "note": data.get("note"),
            "counts": {
                "formula": data.get("formula"),
                "dbe": data.get("dbe"),
                "solvent": data.get("solvent"),
                "count": len(signals),
            },
            "rows": signals,
        }
    except _JSON_READ_ERRORS:
        return {"state": "waiting", "note": None, "counts": {}, "rows": []}


def _read_hsqc(analysis_dir: Path) -> dict[str, Any]:
    """Read analysis/peaks/hsqc.json. Never raises — see _read_carbon."""
    p = analysis_dir / "peaks" / "hsqc.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        peaks = data.get("peaks", [])
        return {
            "state": "ok",
            "note": data.get("note"),
            "counts": {"count": data.get("count", len(peaks))},
            "rows": peaks,
        }
    except _JSON_READ_ERRORS:
        return {"state": "waiting", "note": None, "counts": {}, "rows": []}


def _read_hmbc(analysis_dir: Path) -> dict[str, Any]:
    """Read analysis/peaks/hmbc.json. Row `flag` values pass through verbatim.

    Never raises — see _read_carbon.
    """
    p = analysis_dir / "peaks" / "hmbc.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        peaks = data.get("peaks", [])
        return {
            "state": "ok",
            "note": data.get("note"),
            "counts": {
                "kept_count": data.get("kept_count", len(peaks)),
                "raw_count": data.get("raw_count"),
            },
            "rows": peaks,
        }
    except _JSON_READ_ERRORS:
        return {"state": "waiting", "note": None, "counts": {}, "rows": []}


def _read_cosy(analysis_dir: Path) -> dict[str, Any]:
    """Read analysis/peaks/cosy.json. Never raises — see _read_carbon."""
    p = analysis_dir / "peaks" / "cosy.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        peaks = data.get("peaks", [])
        return {
            "state": "ok",
            "note": data.get("note"),
            "counts": {"count": data.get("count", len(peaks))},
            "rows": peaks,
        }
    except _JSON_READ_ERRORS:
        return {"state": "waiting", "note": None, "counts": {}, "rows": []}


# ---------------------------------------------------------------------------
# Internal helpers — LSD constraint inventory (TBL-03)
# ---------------------------------------------------------------------------


def _newest_compound_lsd(analysis_dir: Path) -> Path | None:
    """Return the compound.lsd from the highest-numbered iteration_NN[_family] dir.

    Uses a PREFIX match (no `$` anchor) so family-suffixed directory names
    like `iteration_07_anchor_recovery` are matched (D-02) — the `$`-anchored
    regex used by structures.py::_newest_solutions_smi does NOT match these.
    mtime breaks ties when two dirs share the same numeric prefix (D-02).
    """
    candidates: list[tuple[int, float, Path]] = []
    for p in analysis_dir.glob("iteration_*/compound.lsd"):
        m = re.match(r"iteration_(\d+)", p.parent.name)
        if m:
            candidates.append((int(m.group(1)), p.stat().st_mtime, p))
    if not candidates:
        return None
    return max(candidates, key=lambda t: (t[0], t[1]))[2]


def _extract_inventory_block(content: str) -> str | None:
    """Extract JSON from between v2 inventory delimiters, stripping '; ' prefix.

    Webview-local sibling of cli/lsd.py::_extract_inventory_block — NOT
    imported directly, since that module's companion validator
    (_validate_and_parse_inventory) raises SystemExit on malformed input,
    the exact opposite of this router's never-500 contract.

    Returns the extracted JSON string, or None if no v2 inventory block is
    found or if the block is malformed (START delimiter present but END
    delimiter missing) — both collapse to the same "waiting" state at the
    route level (RESEARCH.md Pitfall 5).

    Lines that are exactly ';' (blank comment lines) are mapped to empty
    strings.
    """
    lines = content.splitlines()
    in_block = False
    found_end = False
    json_lines: list[str] = []
    for line in lines:
        if "=== CONSTRAINT INVENTORY v2 ===" in line:
            in_block = True
            continue
        if "=== END CONSTRAINT INVENTORY ===" in line and in_block:
            found_end = True
            break
        if in_block:
            if line.startswith("; "):
                json_lines.append(line[2:])  # strip "; " prefix (exactly 2 chars)
            elif line == ";":
                json_lines.append("")
    if not json_lines:
        return None
    if not found_end:
        # START delimiter was present but END was never found — malformed block.
        return None
    return "\n".join(json_lines)


def _read_constraints(analysis_dir: Path) -> dict[str, Any]:
    """Select the newest compound.lsd, parse its inventory block.

    Returns:
        {"state": "ok", "note": inventory.get("note"), "inventory": inventory}
        on success.
        {"state": "waiting", "note": None, "inventory": None} when no
        compound.lsd is found, the inventory block is absent/malformed, or
        the extracted JSON fails to parse — never raises (SC4).
    """
    waiting: dict[str, Any] = {"state": "waiting", "note": None, "inventory": None}

    lsd_path = _newest_compound_lsd(analysis_dir)
    if lsd_path is None:
        return waiting

    try:
        content = lsd_path.read_text(encoding="utf-8")
    except OSError:
        return waiting

    raw_json = _extract_inventory_block(content)
    if raw_json is None:
        return waiting

    try:
        inventory = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return waiting

    if not isinstance(inventory, dict):
        return waiting

    return {"state": "ok", "note": inventory.get("note"), "inventory": inventory}
