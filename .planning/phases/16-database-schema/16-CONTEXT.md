# Phase 16: Database Schema - Context

**Gathered:** 2026-01-15
**Status:** Ready for planning

<vision>
## How This Should Work

Extend the existing compounds.db with tables for HOSE-based shift prediction. The approach is precomputed statistics - store aggregated mean, std, and count per HOSE code rather than raw observations. This enables fast lookups at prediction time without computing aggregates on the fly.

When a prediction is requested, query the hose_stats table directly by HOSE code and radius to get the predicted shift and confidence metrics. The database should be optimized for these lookup queries since prediction speed is the priority.

</vision>

<essential>
## What Must Be Nailed

- **Query speed** - Fast lookups by HOSE code for real-time prediction is the top priority
- **Precomputed statistics** - Mean, std, and observation count per HOSE code at each radius (1-6)
- **Proper indexing** - HOSE code lookups must be indexed for O(1) access

</essential>

<boundaries>
## What's Out of Scope

- No strict boundaries defined - open to including related work if it makes sense
- HOSE code generation is primarily Phase 17, but schema should support it
- Prediction API changes are primarily Phase 18

</boundaries>

<specifics>
## Specific Ideas

- Store statistics in hose_stats table: (hose_code, radius, mean, std, count)
- Index on (hose_code, radius) for fast compound key lookups
- Schema should integrate with existing compounds.db structure
- Consider schema versioning for future migrations

</specifics>

<notes>
## Additional Context

- Existing compounds.db has 928K compounds from v1.1 milestone
- HOSE codes will be generated at radii 1-6 (extended from current 1-4)
- hosegen library is already integrated for HOSE code generation
- Statistics will be computed from ~895K COCONUT compounds

</notes>

---

*Phase: 16-database-schema*
*Context gathered: 2026-01-15*
