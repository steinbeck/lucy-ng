# lucy-ng State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-18)

**Core value:** AI-agent powered structure elucidation from NMR data
**Current focus:** Planning next milestone

## Current Position

**Milestone**: v1.2 HOSE Database Prediction ✅ ARCHIVED
**Status**: All milestones v1.0-v1.2 complete
**Last activity**: 2026-01-18 - v1.2 milestone archived

## Completed Milestones

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Core CASE Pipeline | 1-10 | 2026-01-12 |
| v1.1 Database-Backed Dereplication | 11-15 | 2026-01-15 |
| v1.2 HOSE Database Prediction | 16-19 | 2026-01-18 |

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
| Protocol pattern for backends | 2026-01-18 | HOSELookupProtocol for interchangeable prediction |
| Database-first auto-detection | 2026-01-18 | Prefer database over JSON table |
| Single database for both features | 2026-01-18 | Same DB powers dereplication AND prediction |

## Key Capabilities (v1.2)

- **16 MCP Tools**: Full AI agent integration including get_hose_stats_info
- **7 CLI Command Groups**: read, pick, analyze, dereplicate, predict, lsd, fetch
- **Python API**: Direct library access
- **642 Tests**: Comprehensive coverage
- **Documentation**: USER_GUIDE.md, CLAUDE.md, MCP_INTEGRATION.md, skill/SKILL.md

## Session Continuity

**Last session**: 2026-01-18
**Stopped at**: v1.2 milestone archived
**Resume file**: None (between milestones)

**Next steps**:
- Run `/gsd:discuss-milestone` to plan v1.3
- Or start a new feature directly

---
*Last updated: 2026-01-18 after v1.2 milestone archived*
