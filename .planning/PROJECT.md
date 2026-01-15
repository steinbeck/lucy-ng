# lucy-ng

**AI-agent powered Computer-Assisted Structure Elucidation for organic natural products**

## Vision

Lucy-ng is the next-generation successor to Lucy, designed for AI-agent (Claude) driven structure elucidation from NMR spectroscopic data. Unlike GUI-focused tools like nmrium, lucy-ng is built for programmatic, unattended operation where an AI agent can iterate through the elucidation process until a structure is determined.

The system reads Bruker NMR data, performs peak picking, generates constraints, and interfaces with structure elucidation solvers (LSD/pyLSD) in a hybrid loop that combines constraint-based generation with prediction-based validation.

## Architecture

- **Core**: Python 3.10+ library for NMR processing and CASE workflow
- **CLI**: Command-line interface for testing, debugging, and scripting
- **MCP Server**: Model Context Protocol tools for Claude agent integration
- **Solver Interface**: Wrapper for LSD/pyLSD command-line tools

## Requirements

### Validated

- Read 1D Bruker NMR files (1H, 13C) — v1.0
- Read 2D Bruker NMR files (HSQC, HMBC, COSY) — v1.0
- Automated peak picking for 1D spectra — v1.0
- Automated peak picking for 2D spectra (DEPT-guided, HMBC-guided) — v1.0
- Generate LSD/pyLSD input file format — v1.0
- Execute LSD/pyLSD and parse results — v1.0
- CLI interface for all operations (7 command groups) — v1.0
- MCP server exposing tools for Claude (13 tools) — v1.0
- HOSE-based 13C shift prediction for solution ranking — v1.0
- NMRXiv dataset fetching — v1.0
- SQLite database for 928K compounds (COCONUT + NMRShiftDB) — v1.1
- Database-backed dereplication (~100x faster) — v1.1

### Active

- [ ] Support for COSY correlations in LSD constraints
- [ ] Stereochemistry handling (E/Z, R/S)
- [ ] Interactive CASE mode with user feedback loop

### Out of Scope

- NMR spectrum prediction from structures - use HOSE codes instead
- GUI or web visualization - purely programmatic interface
- Non-Bruker vendor formats (Varian, JEOL, etc.) - Bruker only for v1
- SENECA integration - requires Java GUI rebuild, deferred
- Natural products likeness scoring - later feature

## Constraints

- Python 3.10+ required
- Open source only - no proprietary dependencies
- Open data formats - no vendor lock-in
- Must interface with existing LSD/pyLSD CLI tools

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid CLI + MCP interface | MCP provides structured tools for agent iteration; CLI enables testing and scripting | Good |
| Bruker-only for v1 | Focus on most common format, expand vendor support later | Good |
| LSD/pyLSD as primary solvers | Established CASE tools with CLI interface | Good |
| nmrglue for NMR parsing | Most mature, BSD licensed, native Bruker support | Good |
| Pydantic v2 for models | Type safety, validation, JSON serialization | Good |
| DEPT-guided adaptive thresholding | Lower HSQC threshold until all DEPT carbons matched | Good |
| HMBC-guided peak picking | Filter by requiring C match in 13C/DEPT and H match in HSQC | Good |
| N:1 shift matching for ranking | Handles molecular symmetry correctly | Good |
| SQLite for dereplication DB | Portable, no server, formula-indexed for fast lookup | Good |
| HOSE codes for prediction | Pure Python, no external services, reasonable accuracy | Good |

## Context

### Background

Lucy was the original CASE software created by the project author and sold to Bruker. Lucy-ng represents a complete reimagining for the AI-agent era, prioritizing programmatic interfaces over GUI interactions.

### Problem

Existing NMR processing tools like nmrium are GUI-focused, making it difficult for AI agents to interact with them programmatically. An unattended system that can iterate through structure elucidation without human intervention requires a different architecture.

### Target Users

- Cheminformatics researchers
- Natural products chemists
- AI/ML researchers working on structure elucidation

### NMR Data Requirements

Minimum viable spectral data for v1:
- 1D: 1H and 13C spectra
- 2D: HSQC (direct C-H correlations) and HMBC (long-range correlations)

## Current State

**Version:** v1.1 (shipped 2026-01-15)
**Codebase:** 11,196 lines Python, 414+ tests
**Tech stack:** Python 3.10+, Pydantic v2, nmrglue, RDKit, SQLite, Click, FastMCP

**Capabilities:**
- 13 MCP tools for AI agent integration
- 7 CLI command groups (read, pick, analyze, dereplicate, predict, lsd, fetch)
- SQLite database with 928K compounds (COCONUT + NMRShiftDB)
- Full CASE pipeline: peak picking → LSD generation → solving → ranking

---
*Last updated: 2026-01-15 after v1.1 milestone*
