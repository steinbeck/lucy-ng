"""SQLite schema definitions for the dereplication database."""

# Schema version for migrations
SCHEMA_VERSION = 2

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
CREATE_HOSE_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS hose_stats (
    hose_code TEXT NOT NULL,
    radius INTEGER NOT NULL,
    mean REAL NOT NULL,
    std REAL NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (hose_code, radius)
)
"""

# Index on hose_code for fast lookups (primary query pattern)
CREATE_HOSE_STATS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_hose_stats_code
ON hose_stats(hose_code)
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
]
