# P0-34 Compose Script Resolver Factory Exception Snapshot Replay Progress

Date: 2026-06-09

## Completed

- Extended the Java MCP compose-script error snapshot lane with
  `resolver-factory-exception`.
- Regenerated
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json` from the
  Java exporter through standalone compile and reflection execution.
- Aligned Python resolver factory exception handling from
  `host-misconfig/internal` to Java's `internal-error/internal`.
- Kept resolver factory `None` classified as `host-misconfig/internal`.
- Added Python replay routing for the new Java fixture case.
- Updated the manifest to mark resolver factory exception payload replay as an
  active exported contract.

## Verification

Passed:

- Java standalone compile:
  `javac -cp "foggy-dataset-mcp/target/classes:foggy-dataset-model/target/classes:foggy-mcp-spi/target/classes:$(cat /tmp/foggy-dataset-mcp-cp.txt)" -d /tmp/foggy-p0-34-test-classes foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaComposeScriptToolErrorSnapshotTest.java`
- Java reflection exporter execution:
  `jshell --class-path "/tmp/foggy-p0-34-test-classes:foggy-dataset-mcp/target/classes:foggy-dataset-model/target/classes:foggy-mcp-spi/target/classes:$(cat /tmp/foggy-dataset-mcp-cp.txt)"`
- Python focused replay, resolver factory unit checks, and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py::test_factory_raising_wraps_to_internal_error tests/test_mcp/test_compose_script_tool.py::test_factory_returning_none_is_host_misconfig tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `8 passed, 9 warnings in 0.51s`
- Full Python pytest:
  `.venv/bin/python -m pytest -q`
  - `4069 passed, 232 skipped, 52 warnings in 17.76s`

Blocked:

- Java focused Maven:
  `mvn -q -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest test`
  remains blocked before test execution by the existing
  `LocalDatasetAccessorGovernanceTest` testCompile drift around
  `SemanticQueryRequest.OutputFormattingItem` and `getOutputFormatting()`.
- Scoped ruff:
  `.venv/bin/ruff check src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py`
  remains blocked by existing file-wide lint debt in touched files:
  `src/foggy/mcp/tools/compose_script_tool.py` typing-modernization findings
  and `tests/test_mcp/test_compose_script_tool.py` unused import /
  typing-modernization findings. After removing P0-34's new E731 findings, the
  remaining scoped ruff output reports 34 existing errors.
