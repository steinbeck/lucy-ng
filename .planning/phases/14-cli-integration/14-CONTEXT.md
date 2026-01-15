# Phase 14: CLI Integration - Context

**Gathered:** 2026-01-15
**Status:** Ready for planning

<vision>
## How This Should Work

The `lucy dereplicate c13` command seamlessly switches to using the SQLite database backend. Users don't notice the change — it just works. The command detects the database automatically in the expected location (`data/reference/compounds.db`) and uses it without requiring any flags or configuration.

If the database isn't there, it falls back gracefully to the existing SD file scanning behavior, possibly with a hint that building the database would be faster.

</vision>

<essential>
## What Must Be Nailed

- **Speed improvement** — Database queries should be dramatically faster than scanning 4GB SDF files
- **Zero config for users** — Works out of the box with the downloaded database, no flags or setup required

Both are equally important. The database is pointless if users have to jump through hoops to use it, and ease of use is pointless if it's not actually faster.

</essential>

<boundaries>
## What's Out of Scope

- MCP tool updates — that's Phase 15
- Database building/import — already complete in Phase 12
- This phase is focused purely on the CLI querying experience

</boundaries>

<specifics>
## Specific Ideas

- Default database location: `data/reference/compounds.db` (alongside existing SD files)
- Keep existing SD file path as fallback when database not found
- Consider environment variable override for custom database locations

</specifics>

<notes>
## Additional Context

No additional notes

</notes>

---

*Phase: 14-cli-integration*
*Context gathered: 2026-01-15*
