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

- Standalone compile for the updated Java MCP exporter with the module
  classpath:
  `javac ... JavaComposeScriptToolErrorSnapshotTest.java`
- Reflection execution of
  `shouldProduceComposeScriptToolErrorSnapshot`, which generated the seven-case
  Python fixture.
- Java focused Maven execution:
  `mvn -q -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest test`
- Python focused replay, runtime replay, header unit checks, and manifest:
  `12 passed, 8 warnings in 0.55s`
- Full Python pytest baseline:
  `4053 passed, 232 skipped, 51 warnings in 17.72s`

Blocked:

- Scoped ruff on touched files:
  `.venv/bin/ruff check src/foggy/dataset_model/engine/compose/runtime/script_runtime.py src/foggy/dataset_model/engine/compose/runtime/context_bridge.py src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_compose_script_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py`
  - blocked by existing file-wide typing-modernization and unused-import debt
  - final run reported 66 errors after import-order fixes

## Notes

- Resolver factory exception behavior remains a planned extension because Java
  currently falls through to broad `internal-error` while Python has explicit
  `host-misconfig` handling.
