"""SQLite schema definitions for the dereplication database."""

import sqlite3

# Schema version for migrations
SCHEMA_VERSION = 6

# Compounds table - stores compound metadata
CREATE_COMPOUNDS_TABLE = """
CREATE TABLE IF NOT EXISTS compounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    smiles TEXT NOT NULL DEFAULT '',
    formula TEXT NOT NULL,
    formula_normalized TEXT NOT NULL,
    inchi TEXT NOT NULL DEFAULT '',
    inchi_key TEXT NOT NULL DEFAULT '',
    carbon_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT ''
)
"""

# Shifts table - stores 13C chemical shifts
CREATE_SHIFTS_TABLE = """
CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_id INTEGER NOT NULL,
    atom_index INTEGER,
    shift_ppm REAL NOT NULL,
    hydrogen_count INTEGER,
    FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
)
"""

# Index on formula_normalized for fast lookup
CREATE_FORMULA_INDEX = """
CREATE INDEX IF NOT EXISTS idx_compounds_formula_normalized
ON compounds(formula_normalized)
"""

# Index on compound_id for efficient shift lookups
CREATE_SHIFTS_COMPOUND_INDEX = """
CREATE INDEX IF NOT EXISTS idx_shifts_compound_id
ON shifts(compound_id)
"""

# Schema metadata table for version tracking
CREATE_SCHEMA_META_TABLE = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

# HOSE statistics table - precomputed mean/std/count per HOSE code at each radius
# m2 is the sum of squared differences from mean (for Welford's online algorithm)
# Hybridisation counts: sp3_count, sp2_count, sp1_count (v4+)
# Neighbour element counts: has_carbon_neighbor, has_oxygen_neighbor, etc. (v5+)
# Ring membership counts: in_3ring, in_4ring, in_aromatic (v6+)
CREATE_HOSE_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS hose_stats (
    hose_code TEXT NOT NULL,
    radius INTEGER NOT NULL,
    mean REAL NOT NULL,
    std REAL NOT NULL,
    count INTEGER NOT NULL,
    m2 REAL NOT NULL DEFAULT 0.0,
    sp3_count INTEGER NOT NULL DEFAULT 0,
    sp2_count INTEGER NOT NULL DEFAULT 0,
    sp1_count INTEGER NOT NULL DEFAULT 0,
    has_carbon_neighbor INTEGER NOT NULL DEFAULT 0,
    has_oxygen_neighbor INTEGER NOT NULL DEFAULT 0,
    has_nitrogen_neighbor INTEGER NOT NULL DEFAULT 0,
    has_sulfur_neighbor INTEGER NOT NULL DEFAULT 0,
    has_halogen_neighbor INTEGER NOT NULL DEFAULT 0,
    in_3ring INTEGER NOT NULL DEFAULT 0,
    in_4ring INTEGER NOT NULL DEFAULT 0,
    in_aromatic INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hose_code, radius)
)
"""

# Operation checkpoint table for resumable operations
CREATE_CHECKPOINT_TABLE = """
CREATE TABLE IF NOT EXISTS operation_checkpoint (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

# Index on hose_code for fast lookups (primary query pattern)
CREATE_HOSE_STATS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_hose_stats_code
ON hose_stats(hose_code)
"""

# Index on mean for shift-window detection queries (v4+)
CREATE_HOSE_STATS_MEAN_RADIUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_hose_stats_mean_radius
ON hose_stats(radius, mean)
"""

# Bond pair statistics table - formula-level HHB detection (v6+)
CREATE_BOND_PAIR_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS bond_pair_stats (
    formula_normalized TEXT NOT NULL,
    element1 TEXT NOT NULL,
    element2 TEXT NOT NULL,
    compound_count INTEGER NOT NULL,
    total_compounds INTEGER NOT NULL,
    frequency REAL NOT NULL,
    PRIMARY KEY (formula_normalized, element1, element2)
)
"""

# Index on formula for efficient formula-based HHB queries (v6+)
CREATE_BOND_PAIR_FORMULA_INDEX = """
CREATE INDEX IF NOT EXISTS idx_bond_pair_formula
ON bond_pair_stats(formula_normalized)
"""

# All schema statements in order
SCHEMA_STATEMENTS = [
    CREATE_COMPOUNDS_TABLE,
    CREATE_SHIFTS_TABLE,
    CREATE_FORMULA_INDEX,
    CREATE_SHIFTS_COMPOUND_INDEX,
    CREATE_SCHEMA_META_TABLE,
    CREATE_HOSE_STATS_TABLE,
    CREATE_HOSE_STATS_INDEX,
    CREATE_HOSE_STATS_MEAN_RADIUS_INDEX,
    CREATE_BOND_PAIR_STATS_TABLE,
    CREATE_BOND_PAIR_FORMULA_INDEX,
    CREATE_CHECKPOINT_TABLE,
]


# =========================================================================
# Migration Functions
# =========================================================================


def migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Migrate database from schema v3 to v4.

    Adds hybridisation count columns (sp3_count, sp2_count, sp1_count) to
    hose_stats table and creates the idx_hose_stats_mean_radius index for
    shift-window detection queries.

    Args:
        conn: SQLite connection to database
    """
    cursor = conn.cursor()

    # Add hybridisation count columns with DEFAULT 0
    # SQLite ALTER TABLE ADD COLUMN is safe and fast - only modifies schema
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN sp3_count INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN sp2_count INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN sp1_count INTEGER NOT NULL DEFAULT 0"
    )

    # Create the composite index for detection queries
    cursor.execute(CREATE_HOSE_STATS_MEAN_RADIUS_INDEX)

    # Update schema version
    cursor.execute(
        "UPDATE schema_meta SET value = ? WHERE key = ?",
        ("4", "schema_version"),
    )

    conn.commit()


def migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Migrate database from schema v4 to v5.

    Adds neighbour element count columns to hose_stats table for
    neighbourhood detection.

    Args:
        conn: SQLite connection to database
    """
    cursor = conn.cursor()

    # Add neighbour count columns with DEFAULT 0
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN has_carbon_neighbor INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN has_oxygen_neighbor INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN has_nitrogen_neighbor INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN has_sulfur_neighbor INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN has_halogen_neighbor INTEGER NOT NULL DEFAULT 0"
    )

    # Update schema version
    cursor.execute(
        "UPDATE schema_meta SET value = ? WHERE key = ?",
        ("5", "schema_version"),
    )

    conn.commit()


def migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """Migrate database from schema v5 to v6.

    Adds bond_pair_stats table for HHB detection and ring membership
    columns to hose_stats table for badlist filtering.

    Args:
        conn: SQLite connection to database
    """
    cursor = conn.cursor()

    # Create bond pair statistics table
    cursor.execute(CREATE_BOND_PAIR_STATS_TABLE)
    cursor.execute(CREATE_BOND_PAIR_FORMULA_INDEX)

    # Add ring membership columns to hose_stats
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN in_3ring INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN in_4ring INTEGER NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE hose_stats ADD COLUMN in_aromatic INTEGER NOT NULL DEFAULT 0"
    )

    # Update schema version
    cursor.execute(
        "UPDATE schema_meta SET value = ? WHERE key = ?",
        ("6", "schema_version"),
    )

    conn.commit()
