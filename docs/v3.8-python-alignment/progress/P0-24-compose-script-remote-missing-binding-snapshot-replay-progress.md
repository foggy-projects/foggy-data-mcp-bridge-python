# P0-24 Compose Script Remote Missing Binding Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Aligned Python remote compose missing authority-binding behavior to Java:
  `compose-authority-resolve/invalid-response` in `permission-resolve`.
- Extended `JavaComposeScriptToolErrorSnapshotTest` with
  `remote-missing-authority-binding`.
- Regenerated
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json` with
  three cases:
  - `resolver-null-host-misconfig`
  - `remote-principal-mismatch`
  - `remote-missing-authority-binding`
- Updated Python MCP binding unit coverage for the new error-code/phase
  contract.
- Updated the Java snapshot manifest and alignment docs.

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

- Standalone compile for the updated Java exporter with the module classpath:
  `javac ... JavaComposeScriptToolErrorSnapshotTest.java`
- Reflection execution of
  `shouldProduceComposeScriptToolErrorSnapshot`, which generated the three-case
  Python fixture.
- Python focused replay, binding test, and manifest:
  `7 passed, 4 warnings in 0.52s`
- Full Python pytest baseline:
  `4051 passed, 232 skipped, 46 warnings in 17.31s`

Blocked:

- Scoped ruff on touched production/replay/binding files:
  `.venv/bin/ruff check src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool_binding.py`
  - blocked by existing file-wide lint debt in
    `src/foggy/mcp/tools/compose_script_tool.py` typing modernization findings
    and `tests/test_mcp/test_compose_script_tool_binding.py`
    import/whitespace findings.

## Notes

- This item intentionally changes Python production tool behavior for the
  remote missing-binding branch to match Java's current contract.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages P0-24 production/tool tests, fixture, manifest, and
  alignment docs.
