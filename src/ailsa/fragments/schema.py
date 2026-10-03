"""SQLite schema definitions for the fragment (SSC) database.

This schema is INDEPENDENT of ``database/schema.py``.  The fragment database
lives in a separate file (``lucy-ng-fragments.db``) and has its own version
counter starting at 7.  Do NOT modify ``database/schema.py`` SCHEMA_VERSION —
that describes the compound/HOSE database (``lucy-ng-derep.db``).
"""

from __future__ import annotations

# Schema version for the fragment database.
# Starts at 7 to distinguish from the compound DB (currently at v6).
FRAGMENT_SCHEMA_VERSION = 7

# Schema metadata table — same pattern as the compound database.
# Stores key/value pairs such as ``schema_version`` and ``bin_size``.
CREATE_SCHEMA_META_TABLE = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

# SSC (Substructure-Subspectrum Correlation) table.
# One row per unique substructure, deduplicated by SMILES.
# shift_list is a JSON array of 13C shifts, e.g. "[45.1, 130.2]".
# UNIQUE(smiles) enforces global deduplication at the database level,
# enabling INSERT OR IGNORE for efficient batch insertion.
CREATE_SSC_TABLE = """
CREATE TABLE IF NOT EXISTS ssc (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    smiles     TEXT NOT NULL,
    atom_count INTEGER NOT NULL,
    shift_list TEXT NOT NULL,
    avg_shift  REAL NOT NULL,
    min_shift  REAL NOT NULL,
    max_shift  REAL NOT NULL,
    UNIQUE(smiles)
)
"""

# SSC bitset table — separated from the main ssc table to keep ssc rows
# slim when queries don't require bitset data (e.g. Phase 52 fine-matching).
# The 32-byte BLOB encodes a 256-bit fingerprint at 2 ppm bin resolution.
# ON DELETE CASCADE ensures bitsets are removed when their parent SSC is deleted.
CREATE_SSC_BITSET_TABLE = """
CREATE TABLE IF NOT EXISTS ssc_bitset (
    ssc_id INTEGER PRIMARY KEY,
    bitset BLOB NOT NULL,
    FOREIGN KEY (ssc_id) REFERENCES ssc(id) ON DELETE CASCADE
)
"""

# Index on atom_count for size-constrained fragment queries.
CREATE_SSC_ATOM_COUNT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_ssc_atom_count ON ssc(atom_count)
"""

# All schema statements in creation order.
# schema_meta must be first so that create_tables() can write version metadata
# immediately after executing DDL.
FRAGMENT_SCHEMA_STATEMENTS = [
    CREATE_SCHEMA_META_TABLE,
    CREATE_SSC_TABLE,
    CREATE_SSC_BITSET_TABLE,
    CREATE_SSC_ATOM_COUNT_INDEX,
]
