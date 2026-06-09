# P0-40 Compose Script Resolver Resolve Exception Snapshot Replay Progress

Date: 2026-06-09

## Completed

- Extended the Java MCP compose-script error snapshot lane with
  `resolver-resolve-exception`.
- Regenerated
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json` from the
  Java MCP reactor exporter.
- Added Python replay routing for a resolver whose `resolve(...)` method raises
  a generic runtime exception.
- Confirmed Python already aligns to Java's structured payload:
  `compose-authority-resolve/upstream-failure` with tool phase
  `permission-resolve`.
- Updated the manifest to mark resolver `resolve(...)` upstream-failure replay
  as an active exported contract.

## Verification

Passed:

- Java MCP exporter with reactor dependencies:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaComposeScriptToolErrorSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
- Python focused replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `6 passed, 8 warnings in 0.51s`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`
  - passed
- Current worktree full Python pytest:
  `.venv/bin/python -m pytest -q`
  - `4076 passed, 232 skipped, 53 warnings in 23.44s`

Note: the full pytest run was executed with unrelated local compose alias
changes present in the worktree. P0-40 closeout relies on the focused Java
exporter, Python replay/manifest, and scoped lint checks above.
