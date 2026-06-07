# P0-22 Compose Script Host-Misconfig Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Added Java MCP compose-script error snapshot producer for
  `resolver-null-host-misconfig`.
- Generated `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`.
- Added Python replay for the Java structured error payload fields and
  forbidden leakage markers.
- Added a dedicated active manifest entry:
  `compose-script-tool-error-snapshots`.
- Updated the alignment README and P0 gap matrix.

## Verification

Blocked:

- `mvn test -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest`
  - blocked before test execution during module `testCompile`
  - existing failing source:
    `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/spi/impl/LocalDatasetAccessorGovernanceTest.java`
  - missing symbols:
    `SemanticQueryRequest.OutputFormattingItem` and
    `SemanticQueryRequest.getOutputFormatting()`

Passed:

- Standalone compile for the new exporter with the module classpath:
  `javac ... JavaComposeScriptToolErrorSnapshotTest.java`
- Reflection execution of
  `shouldProduceComposeScriptToolErrorSnapshot`, which generated the Python
  fixture.
- Python focused replay plus manifest:
  `6 passed, 1 warning in 0.59s`
- Scoped ruff:
  `All checks passed!`
- Full Python pytest:
  `4051 passed, 232 skipped, 44 warnings in 17.70s`

## Notes

- This item does not change Python production script runtime behavior.
- The Java worktree remains clean except for the new P0-22 exporter.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-22 fixture, manifest, replay test, and alignment
  docs.
