# Deferred Items — Phase 94

## Plan 94-01

- **Pre-existing ruff E501** at `tests/test_webview_api.py:293` (line too long, 106 > 100),
  inside `TestStructuresEndpoint::test_malformed_smiles_returns_placeholder_svg`. This line
  pre-dates plan 94-01 (introduced in commit `0c1a8b8`, Phase 93) and is unrelated to the
  Phase 94 TestTablesEndpoint scaffold added by this plan. Out of scope per the executor's
  scope-boundary rule (only auto-fix issues directly caused by the current task's changes).
  Left unfixed; flagging here so it is not lost.
