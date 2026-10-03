"""Shared 13C-predictor backend resolution.

This module centralizes the backend-priority ladder that selects which HOSE
lookup backend a :class:`~ailsa.prediction.predictor.C13Predictor` uses, so
that both ``ailsa predict c13`` and ``ailsa lsd rank`` resolve the *same* backend
through one code path (RANK-01: single prediction path, no divergent code).

Backend priority (mirrors ``cli/predict.py``'s 4-tier ladder):

1. Explicit ``db`` path        -> :meth:`C13Predictor.from_database`
2. Explicit ``table`` path     -> :meth:`C13Predictor.from_table_file`
3. Auto-detected SQLite DB     -> :meth:`C13Predictor.from_database`
   (via :meth:`DatabaseFinder.find_hose_database`)
4. Auto-detected JSON table    -> :meth:`C13Predictor.from_table_file`
   (via :meth:`DatabaseFinder.find_hose_table`, then the shipped
   ``hose_nmrshiftdb.json.gz`` fallback -- see the filename trap below)

Layering: ``prediction/`` is a lower tier than ``cli/``. This module must
never reach into the CLI package (doing so would invert the cli -> prediction
dependency direction and risk an import cycle). The three shipped-table
candidate paths used by ``cli/lsd.py:_get_default_table_path``
are therefore *replicated* here rather than imported.

Filename trap (research Pitfall 3): ``DatabaseFinder.find_hose_table`` looks
for ``hose_lookup.json.gz``, which is NOT what ships on disk. The file that
actually ships is ``hose_nmrshiftdb.json.gz`` (located by lsd.py's
``_get_default_table_path``). Step 4 below therefore tries
``find_hose_table()`` first and, on a miss, falls back to the replicated
shipped-table candidates so the JSON fallback still resolves the real file.

This module emits NO ``click.echo`` output: it is library code. It raises
exceptions and lets the CLIs translate them to ``SystemExit``.
"""

from __future__ import annotations

from pathlib import Path

from ailsa.database.finder import DatabaseFinder

from .predictor import C13Predictor


def _shipped_table_candidates() -> list[Path]:
    """Return the candidate locations for the shipped JSON HOSE table.

    Replicates (does NOT import) the three candidate paths used by
    ``cli/lsd.py:_get_default_table_path`` so the JSON fallback locates the
    file that actually ships (``hose_nmrshiftdb.json.gz``):

    1. ``<project_root>/data/reference/hose_nmrshiftdb.json.gz``
    2. ``<package_dir>/data/hose_nmrshiftdb.json.gz``
    3. ``~/.lucy/hose_nmrshiftdb.json.gz``
    """
    import ailsa

    package_dir = Path(ailsa.__file__).parent
    # package_dir = .../ailsa/src/ailsa -> project_root = .../ailsa
    project_root = package_dir.parent.parent

    return [
        project_root / "data" / "reference" / "hose_nmrshiftdb.json.gz",
        package_dir / "data" / "hose_nmrshiftdb.json.gz",
        Path.home() / ".lucy" / "hose_nmrshiftdb.json.gz",
    ]


def _find_shipped_table() -> Path | None:
    """Return the first existing shipped JSON HOSE table, or None."""
    for candidate in _shipped_table_candidates():
        if candidate.exists():
            return candidate
    return None


def resolve_c13_predictor(
    db: str | Path | None = None,
    table: str | Path | None = None,
    max_radius: int = 6,
) -> C13Predictor:
    """Resolve a :class:`C13Predictor` using the canonical backend ladder.

    Applies the DB-first 4-tier priority shared by ``ailsa predict c13`` and
    ``ailsa lsd rank``. See the module docstring for the full priority order.

    Args:
        db: Explicit SQLite database path (priority 1).
        table: Explicit JSON HOSE-table path (priority 2).
        max_radius: Maximum HOSE radius for prediction (default 6).

    Returns:
        A configured :class:`C13Predictor` backed by the resolved lookup.

    Raises:
        RuntimeError: If no backend can be located.
    """
    # Priority 1: explicit database path
    if db:
        return C13Predictor.from_database(Path(db), max_radius=max_radius)

    # Priority 2: explicit table path
    if table:
        return C13Predictor.from_table_file(Path(table), max_radius=max_radius)

    # Priority 3: auto-detect database (DB-first)
    db_path = DatabaseFinder.find_hose_database()
    if db_path:
        return C13Predictor.from_database(db_path, max_radius=max_radius)

    # Priority 4: auto-detect JSON table.
    # Try the finder first, then the replicated shipped-table candidates
    # (the finder looks for hose_lookup.json.gz, which does not ship; the
    # shipped file is hose_nmrshiftdb.json.gz -- see filename trap above).
    table_path = DatabaseFinder.find_hose_table()
    if table_path is None:
        table_path = _find_shipped_table()
    if table_path is not None:
        return C13Predictor.from_table_file(table_path, max_radius=max_radius)

    # No backend found.
    raise RuntimeError(
        "No prediction backend found.\n\n"
        "Options:\n"
        "  1. Download database: ailsa database download\n"
        "  2. Build JSON table: ailsa predict build-table <coconut.sd>"
    )
