# P0-47 Domain Question Unsupported Construct Snapshot Replay Progress

Date: 2026-06-10

## Completed

- Extended the Java neutral domain/question runner exporter source with three
  unsupported construct cases:
  `pivot-time-window-mutual-exclusion-unsupported`,
  `hidden-axis-function-calculated-field-unsupported`, and
  `cross-model-join-needs-compose-script-unsupported`.
- Updated the Python neutral runner fixture with the same cases.
- Added Python replay assertions for:
  - `unsupportedConstructs` in error details,
  - `unsupportedConstructs` in case-summary reports,
  - `pivot` request round-trip through `build_query_request`,
  - neutral `hints` round-trip for compose recommendation metadata.
- Updated the Java snapshot parity manifest to mark unsupported construct
  breadth as active in the domain/question runner lane.
- Kept the lane LLM-free, Odoo-free, registry-free, and external-DB-free.

## Verification

Passed:

- Python focused replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_domain_fixture_runner.py`
- Full Python pytest:
  `.venv/bin/python -m pytest -q`
  - `4082 passed, 232 skipped, 53 warnings in 18.04s`

Blocked:

- Java MCP exporter with reactor dependencies:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
  - blocked by an existing unrelated compile error in
    `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/compilation/JavaComposeSnapshotTest.java`
    at line 708.
- Java MCP exporter without reactor dependencies:
  `mvn -q -pl foggy-dataset-mcp -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
  - blocked by stale local dependency/test API mismatch around
    `SemanticQueryRequest.OutputFormattingItem` in
    `LocalDatasetAccessorGovernanceTest`.

Pending before closeout:

- Re-run the Java exporter once unrelated Java compile drift is cleared.
