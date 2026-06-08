# P0-26 Compose Script Header Bridge Error Snapshot Replay Progress

Date: 2026-06-08

## Completed

- Extended `JavaComposeScriptToolErrorSnapshotTest` with:
  - `missing-user-id-header`
  - `missing-namespace-header`
- Regenerated
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json` with
  seven cases.
- Aligned Python `ComposeScriptTool` context bridge failures to Java's
  `internal-error` payload.
- Updated Python bridge messages to include stable Java snapshot markers.
- Updated Python replay to use a permissive resolver for header bridge cases.
- Added unit coverage for missing user and missing namespace bridge errors.
- Updated the Java snapshot manifest and alignment docs.

## Verification

Passed:

- Java focused Maven exporter:
  `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-mcp -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest=JavaComposeScriptToolErrorSnapshotTest -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  - result: `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python focused replay, context bridge checks, MCP tool checks, and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py tests/compose/runtime/test_context_bridge.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `45 passed, 39 warnings in 0.19s`

Pending:

- Full Python pytest baseline.
- Scoped ruff on touched files.

## Notes

- Resolver factory exception behavior remains a planned extension because Java
  currently falls through to broad `internal-error` while Python has explicit
  `host-misconfig` handling.
