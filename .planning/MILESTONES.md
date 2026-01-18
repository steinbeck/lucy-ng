# Project Milestones: lucy-ng

## v1.2 HOSE Database Prediction (Shipped: 2026-01-18)

**Delivered:** Database-backed 13C shift prediction using 7.9M HOSE statistics from 895K compounds, enabling accurate solution ranking with O(1) lookups

**Phases completed:** 16-19 (4 plans total)

**Key accomplishments:**
- hose_stats table with 7.9M pre-computed statistics (mean, std, count) per HOSE code at radii 1-6
- HOSELookupProtocol for interchangeable prediction backends
- DatabaseHOSELookup adapter for O(1) database queries
- C13Predictor with dual-backend support (database preferred, JSON table fallback)
- ResumableHOSEStatsGenerator with checkpoint/resume for large dataset processing
- CLI `--db` option with intelligent auto-detection
- MCP `get_hose_stats_info` tool for agent capability checking
- Single database now powers both dereplication AND 13C prediction

**Stats:**
- 17,552 lines of Python
- 642 tests
- 4 phases, 4 plans, 16 tasks
- 3 days from v1.1 to v1.2 (2026-01-15 → 2026-01-18)

**Git range:** `feat(16-01)` → `feat(19-01)`

**What's next:** Planning next milestone

---

## v1.1 Database-Backed Dereplication (Shipped: 2026-01-15)

**Delivered:** SQLite database backend enabling ~100x faster dereplication against 928K compounds (COCONUT + NMRShiftDB)

**Phases completed:** 11-15 (5 plans total)

**Key accomplishments:**
- SQLite database schema for storing 928K compounds with formula-indexed queries
- Database importer for batch loading from NMRShiftDB and COCONUT SDF files
- DatabaseQueryService API for formula-based compound lookup
- CLI auto-detection of database with `LUCY_DATABASE` env var support
- MCP tool integration with `database_type` field for agent transparency
- ~100x faster dereplication vs. SD file scanning

**Stats:**
- 42 files created/modified
- 11,196 lines of Python
- 5 phases, 5 plans
- 7 days from v1.0 to v1.1 (2026-01-08 → 2026-01-15)

**Git range:** `feat(11-01)` → `feat(15-01)`

**What's next:** Planning next milestone

---

## v1.0 Core CASE Pipeline (Shipped: 2026-01-12)

**Delivered:** Complete Computer-Assisted Structure Elucidation pipeline with 13 MCP tools, 7 CLI command groups, and LSD solver integration

**Phases completed:** 1-10 (12 plans total, including decimal phases 2.1, 4.1, 4.2, 5.1, 5.2)

**Key accomplishments:**
- Bruker 1D/2D NMR spectrum reading (1H, 13C, DEPT, HSQC, HMBC, COSY)
- DEPT-guided adaptive HSQC peak picking with multiplicity detection
- HMBC-guided peak picking to filter noise correlations
- Symmetry detection for molecular equivalence handling
- LSD solver integration with constraint generation and solution parsing
- HOSE-based 13C shift prediction for solution ranking
- NMRXiv dataset fetching for research evaluation
- 13 MCP tools for Claude agent integration
- 7 CLI command groups for scripting and testing

**Stats:**
- 100+ files created
- ~8,000 lines of Python (before v1.1)
- 12 phases (10 integer + 5 decimal insertions), 12 plans
- 5 days from start to v1.0 (2026-01-08 → 2026-01-12)

**Git range:** `feat(01-01)` → `feat(10-01)`

**What's next:** Database-backed dereplication for v1.1

---
