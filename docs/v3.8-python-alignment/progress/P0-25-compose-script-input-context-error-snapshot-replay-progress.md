# P0-25 Compose Script Input/Context Error Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Extended `JavaComposeScriptToolErrorSnapshotTest` with:
  - `missing-script`
  - `missing-context`
- Regenerated
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json` with
  five cases.
- Aligned Python `ComposeScriptTool` with Java for:
  - missing script: `missing-script` in `internal`
  - missing context: `internal-error` in `internal`
- Updated Python replay to support Java snapshot cases with `context: null`.
- Updated Python unit assertions for missing script and missing context.
- Updated the Java snapshot manifest and alignment docs.

## Verification

Passed:

- Standalone compile for the updated Java exporter with the module classpath:
  `javac ... JavaComposeScriptToolErrorSnapshotTest.java`
- Reflection execution of
  `shouldProduceComposeScriptToolErrorSnapshot`, which generated the five-case
  Python fixture.
- Python focused replay, input/context unit checks, and manifest:
  `9 passed, 6 warnings in 0.54s`
- Full Python pytest baseline:
  `4051 passed, 232 skipped, 47 warnings in 19.98s`

Blocked:

- Java focused Maven execution:
  `mvn -q -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest test`
  - blocked before test execution during module `testCompile`
  - existing failing source:
    `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/spi/impl/LocalDatasetAccessorGovernanceTest.java`
  - missing symbols:
    `SemanticQueryRequest.OutputFormattingItem` and
    `SemanticQueryRequest.getOutputFormatting()`
- Scoped ruff on touched production/replay/unit files:
  `.venv/bin/ruff check src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py`
  - blocked by existing file-wide lint debt in
    `src/foggy/mcp/tools/compose_script_tool.py` typing-modernization findings
    and `tests/test_mcp/test_compose_script_tool.py` import/typing findings.

## Notes

- Resolver factory exception behavior remains a planned extension because Java
  currently falls through to broad `internal-error` while Python has explicit
  `host-misconfig` handling.
- Remaining header bridge cases should be added separately so message markers
  and error-code ownership are not mixed with basic input validation.
