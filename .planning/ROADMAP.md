# lucy-ng Roadmap

## Milestones

- ✅ **v1.0 Core CASE Pipeline** - Phases 1-10 (complete 2026-01-12)
- 🚧 **v1.1 Database-Backed Dereplication** - Phases 11-15 (in progress)

---

<details>
<summary>✅ v1.0 Core CASE Pipeline (Phases 1-10) - COMPLETE 2026-01-12</summary>

### Phase 1: Foundation
**Goal**: Project structure, dependencies, and NMR library evaluation

- Set up Python package structure with modern tooling (pyproject.toml)
- Research and evaluate NMR parsing libraries (nmrglue, bruker-reader, etc.)
- Establish core data models for spectra and peaks
- Basic test infrastructure

**Research**: NMR parsing library selection

---

### Phase 2: 1D NMR Reading
**Goal**: Read Bruker 1D spectra (1H, 13C) reliably

- Implement Bruker 1D file reader (fid, acqus, procs)
- Parse acquisition and processing parameters
- Handle spectrum data (real/imaginary, processed)
- Data structures for 1D spectra with metadata

---

### Phase 2.1: 1D Carbon Dereplication (INSERTED)
**Goal**: Validate pipeline with 1D dereplication against nmrshiftdb

- Peak picking from 1D 13C spectrum
- Download/query reference data from nmrshiftdb by molecular formula
- Match observed peaks against reference spectra
- Score and rank candidate structures
- Return dereplication results (match/no match/candidates)

**Depends on:** Phase 2
**Research**: nmrshiftdb API/data format, matching algorithms

---

### Phase 3: 2D NMR Reading
**Goal**: Read Bruker 2D spectra (HSQC, HMBC)

- Implement Bruker 2D file reader (ser, acqu2s)
- Parse 2D acquisition parameters (F1/F2 dimensions)
- Handle 2D data matrices
- Data structures for 2D spectra with correlation information

---

### Phase 4: Peak Picking
**Goal**: Automated peak detection for 1D and 2D spectra

- 1D peak picking algorithm (threshold, noise estimation)
- 2D peak picking (local maxima, cross-peak detection)
- Peak list data structures
- Peak filtering and validation

**Research**: Peak picking algorithms and thresholds

---

### Phase 4.1: 2D Peak Picking Validation (INSERTED)
**Goal**: Validate that 2D peak picking produces scientifically reasonable results

- Cross-validate HSQC peaks against 1D 13C peaks
- Every HSQC F1 position should correspond to a 1D 13C peak
- Develop validation utility for peak list quality assurance
- Tolerance-based matching between 2D F1 and 1D peak positions

**Depends on:** Phase 4
**Rationale**: Ensure 2D peak picking is physically plausible before using peaks for structure elucidation

---

### Phase 4.2: DEPT-Guided Adaptive HSQC Peak Picking (INSERTED)
**Goal**: Use DEPT data as ground truth to adaptively tune HSQC peak picking

- Read DEPT-135 spectrum to identify all protonated carbons
- Use DEPT peaks as validation targets for HSQC
- Adaptively lower HSQC threshold until all DEPT carbons are matched
- Filter HSQC peaks to only those corresponding to real carbons
- Return validated, noise-free HSQC peak list

**Depends on:** Phase 4.1
**Rationale**: DEPT provides definitive ground truth for which carbons carry hydrogens; HSQC must find all of them

---

### Phase 5: LSD Integration
**Goal**: Generate input files and execute LSD/pyLSD solvers

- Research LSD/pyLSD input file format
- Generate constraint files from peak data
- Execute LSD/pyLSD as subprocess
- Parse and structure solution output

**Research**: LSD/pyLSD file formats and CLI interface

---

### Phase 5.1: HMBC-Guided Peak Picking (INSERTED)
**Goal**: Filter HMBC peaks using validated carbon and proton positions

- Use 13C/DEPT peaks as valid carbon positions
- Use HSQC proton positions as valid proton positions
- Filter HMBC to only peaks matching both constraints
- Reduce noise and improve LSD constraint quality

**Depends on:** Phase 5
**Rationale**: HMBC noise produces spurious correlations; filtering by known positions improves LSD results

---

### Phase 5.2: Symmetry Detection from Spectroscopic Data (INSERTED)
**Goal**: Detect molecular symmetry to properly handle equivalent atoms in LSD input

- Hydrogen counting: Compare MF hydrogen count with carbon-assigned H sum
- Detect "missing" hydrogens indicating equivalent carbons
- Intensity analysis: Identify doubled signals from relative peak intensities
- Pattern recognition: Recognize symmetric motifs (para-substituted benzene, isopropyl, etc.)
- Generate proper atom definitions for equivalent positions
- Support LSD SYME commands for equivalent atom constraints

**Depends on:** Phase 5.1
**Rationale**: Molecular symmetry causes fewer NMR signals than atoms; without handling this, LSD fails with valence errors

---

### Phase 6: CLI Interface
**Goal**: Command-line interface for all operations

- CLI framework setup (click or typer)
- Commands for reading spectra
- Commands for peak picking
- Commands for LSD execution
- Workflow commands (full pipeline)

---

### Phase 7: MCP Server
**Goal**: Model Context Protocol tools for Claude agent integration

- MCP server setup
- Tool definitions for all operations
- Structured input/output schemas
- Agent-friendly error handling and feedback

---

### Phase 8: HOSE-Based 13C Spectrum Predictor
**Goal**: Build pure Python 13C NMR predictor using HOSE codes and COCONUT database

- HOSE code generation wrapper using hosegen library
- Build lookup table from COCONUT SD file (~895K molecules)
- Predictor class with fallback to shorter HOSE radii
- Confidence scoring based on match count and variance
- CLI command for shift prediction
- MCP tool for agent integration

**Research**: Completed - evaluated nmrgnn, CASCADE, nmr_mpnn (all had dependency issues); HOSE codes selected

---

### Phase 9: LSD Solution Ranking
**Goal**: Rank LSD solutions by similarity between experimental 13C spectrum and predicted spectrum

- Use Phase 8 predictor for candidate structure shifts
- Compare predicted shifts with experimental 13C peaks
- Score solutions by spectrum similarity (e.g., MAE, RMSE, or cosine similarity)
- Rank and filter solutions by prediction quality
- Return ranked solution list with confidence scores

**Depends on:** Phase 8 (HOSE Predictor)

---

### Phase 10: NMRXiv Dataset Fetching
**Goal**: Fetch spectroscopic datasets from nmrxiv.org for structure elucidation

- Research NMRXiv API and data access methods
- Implement dataset fetching by identifier or search criteria
- Parse and convert NMRXiv data to lucy-ng formats
- CLI command for dataset retrieval
- MCP tool for agent integration

**Depends on:** Phase 6 (CLI Interface)

</details>

---

## 🚧 v1.1 Database-Backed Dereplication (In Progress)

**Milestone Goal:** Enable efficient dereplication against large databases (COCONUT 895K compounds + NMRShiftDB 33K) using SQLite indexing by molecular formula.

### Phase 11: Database Schema
**Goal**: Design and implement SQLite schema for compounds and 13C shifts, indexed by molecular formula

- SQLite database schema for compounds (id, name, smiles, formula, source)
- Schema for 13C shifts (compound_id, atom_index, shift_ppm)
- Index on molecular formula for fast lookup
- Pydantic models for database entities

**Depends on**: Milestone 1.0 complete
**Research**: Unlikely (SQLite patterns established)

Plans:
- [ ] 11-01: TBD (run /gsd:plan-phase 11 to break down)

---

### Phase 12: Database Import
**Goal**: Build import scripts for NMRShiftDB and COCONUT SDF files

- SDF parser for NMRShiftDB format (existing `nmrshiftdb2withsignals.sd`)
- SDF parser for COCONUT format (`predicted_coconut.sdf` with CNMR_SHIFTS field)
- Batch import with progress reporting
- Deduplication handling
- CLI command for database building

**Depends on**: Phase 11
**Research**: Unlikely (RDKit SDF parsing exists)

Plans:
- [ ] 12-01: TBD

---

### Phase 13: Database Query API
**Goal**: Implement query interface for formula-based compound lookup

- Query by exact molecular formula
- Return compounds with their 13C shifts
- Efficient batch queries
- Python API for programmatic access

**Depends on**: Phase 12
**Research**: Unlikely (internal patterns)

Plans:
- [ ] 13-01: TBD

---

### Phase 14: CLI Integration
**Goal**: Update `lucy dereplicate c13` to use database backend

- Database path configuration (default location, env var, CLI flag)
- Fallback behavior if database not built
- Performance comparison vs. current SDF scanning
- Documentation updates

**Depends on**: Phase 13
**Research**: Unlikely (existing CLI patterns)

Plans:
- [ ] 14-01: TBD

---

### Phase 15: MCP Integration
**Goal**: Update MCP tool for database-backed dereplication

- Update `dereplicate_c13` MCP tool to use database
- Add database status/info tool
- Error handling for missing database
- Documentation updates

**Depends on**: Phase 14
**Research**: Unlikely (existing MCP patterns)

Plans:
- [ ] 15-01: TBD

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Foundation | v1.0 | 1/1 | Complete | 2026-01-08 |
| 2. 1D NMR Reading | v1.0 | 1/1 | Complete | 2026-01-08 |
| 2.1 1D Carbon Dereplication | v1.0 | 1/1 | Complete | 2026-01-09 |
| 3. 2D NMR Reading | v1.0 | 1/1 | Complete | 2026-01-09 |
| 4. Peak Picking | v1.0 | 1/1 | Complete | 2026-01-09 |
| 4.1 2D Peak Validation | v1.0 | 1/1 | Complete | 2026-01-10 |
| 4.2 DEPT-Guided HSQC | v1.0 | 1/1 | Complete | 2026-01-10 |
| 5. LSD Integration | v1.0 | 1/1 | Complete | 2026-01-10 |
| 5.1 HMBC-Guided Picking | v1.0 | — | Complete | 2026-01-10 |
| 5.2 Symmetry Detection | v1.0 | — | Complete | 2026-01-10 |
| 6. CLI Interface | v1.0 | 1/1 | Complete | 2026-01-11 |
| 7. MCP Server | v1.0 | 1/1 | Complete | 2026-01-11 |
| 8. HOSE Predictor | v1.0 | 1/1 | Complete | 2026-01-11 |
| 9. LSD Solution Ranking | v1.0 | 1/1 | Complete | 2026-01-12 |
| 10. NMRXiv Fetching | v1.0 | 1/1 | Complete | 2026-01-12 |
| 11. Database Schema | v1.1 | 0/? | Not started | - |
| 12. Database Import | v1.1 | 0/? | Not started | - |
| 13. Database Query API | v1.1 | 0/? | Not started | - |
| 14. CLI Integration | v1.1 | 0/? | Not started | - |
| 15. MCP Integration | v1.1 | 0/? | Not started | - |

---
*Last updated: 2026-01-13*
