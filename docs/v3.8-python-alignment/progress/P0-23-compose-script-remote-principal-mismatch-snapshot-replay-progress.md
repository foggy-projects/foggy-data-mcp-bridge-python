# P0-23 Compose Script Remote Principal-Mismatch Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Extended `JavaComposeScriptToolErrorSnapshotTest` with
  `remote-principal-mismatch`.
- Regenerated
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json` with two
  cases:
  - `resolver-null-host-misconfig`
  - `remote-principal-mismatch`
- Extended Python replay to dispatch remote authority-binding cases through a
  real `SemanticQueryService` registered with `FactSalesModel`.
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
  `shouldProduceComposeScriptToolErrorSnapshot`, which generated the two-case
  Python fixture.
- Python focused replay plus manifest:
  `6 passed, 2 warnings in 0.56s`
- Scoped ruff:
  `All checks passed!`
- Full Python pytest:
  `4051 passed, 232 skipped, 45 warnings in 18.01s`

## Notes

- This item does not change Python production script runtime behavior.
- Remote missing authority-binding remains a documented error-code/phase
  parity decision before replay activation.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-23 fixture, manifest, replay test, and alignment
  docs.
