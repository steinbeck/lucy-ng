# lucy-ng State

## Current Position

**Milestone**: v1.1 — Database-Backed Dereplication
**Phase**: 14 of 15 (CLI Integration)
**Plan**: 14-01 Complete
**Status**: Ready for Phase 15 (MCP Integration)
**Last activity**: 2026-01-15 - Phase 14-01 complete

Progress: ████████░░ 80%

## Milestone 1.0 Complete

All phases of the Core CASE Pipeline have been implemented:

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation | Complete |
| 2 | 1D NMR Reading | Complete |
| 2.1 | 1D Carbon Dereplication | Complete |
| 3 | 2D NMR Reading | Complete |
| 4 | Peak Picking | Complete |
| 4.1 | 2D Peak Validation | Complete |
| 4.2 | DEPT-Guided HSQC | Complete |
| 5 | LSD Integration | Complete |
| 5.1 | HMBC-Guided Picking | Complete |
| 5.2 | Symmetry Detection | Complete |
| 6 | CLI Interface | Complete |
| 7 | MCP Server | Complete |
| 8 | HOSE Predictor | Complete |
| 9 | LSD Solution Ranking | Complete |
| 10 | NMRXiv Dataset Fetching | Complete |

## Roadmap Evolution

- Milestone v1.0: Core CASE Pipeline, 12 phases (Phase 1-10 + insertions), complete
- Milestone v1.1 created: Database-Backed Dereplication, 5 phases (Phase 11-15)

## Key Decisions

| Decision | Date | Context |
|----------|------|---------|
| Hybrid CLI + MCP interface | 2026-01-08 | MCP for agent iteration, CLI for testing |
| Bruker-only for v1 | 2026-01-08 | Focus on most common format |
| LSD/pyLSD as primary solvers | 2026-01-08 | Established CASE tools with CLI |
| nmrglue for NMR parsing | 2026-01-08 | Most mature, BSD licensed, native Bruker support |
| Pydantic v2 for models | 2026-01-08 | Type safety, validation, JSON serialization |
| hatch build system | 2026-01-08 | Modern Python packaging |
| Use processed data | 2026-01-08 | Read from pdata/1/ not raw FID |
| DEPT-guided adaptive thresholding | 2026-01-10 | Lower HSQC threshold until all DEPT carbons matched |
| HMBC-guided peak picking | 2026-01-10 | Filter by requiring C match in 13C/DEPT and H match in HSQC |
| Click CLI framework | 2026-01-10 | Simpler than Typer, no extra dependencies |
| N:1 shift matching for ranking | 2026-01-12 | Handles molecular symmetry correctly |
| DOI-based data fetching | 2026-01-12 | Parse NMRXiv DOIs directly for project/study IDs |
| SQLite for dereplication DB | 2026-01-13 | Portable, no server, formula-indexed for fast lookup |

## Key Capabilities (v1.0)

- **13 MCP Tools**: Full AI agent integration
- **7 CLI Command Groups**: read, pick, analyze, dereplicate, predict, lsd, fetch
- **Python API**: Direct library access
- **414+ Tests**: Comprehensive coverage
- **Documentation**: USER_GUIDE.md, CLAUDE.md, MCP_INTEGRATION.md

## Session Continuity

**Last session**: 2026-01-15
**Stopped at**: Phase 14-01 complete
**Resume file**: None

**Next steps**:
- Plan Phase 15 (MCP Integration)
- Update MCP `dereplicate_c13` tool to use database backend

---
*Last updated: 2026-01-15*
