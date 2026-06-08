# P0-31 Domain Question Neutral Runner Snapshot Replay Progress

Date: 2026-06-08

## Completed

- Added Java exporter
  `JavaDomainQuestionNeutralRunnerSnapshotTest`.
- Generated
  `tests/fixtures/java_domain_question_neutral_runner_parity.json`.
- Added Python replay
  `tests/integration/test_java_domain_fixture_runner.py`.
- Activated the `domain-question-neutral-runner` manifest entry with concrete
  Java exporter, Python fixture, Python test, and verification markers.
- Kept Odoo business packs, registry pulls, generated model changes, and LLM
  prompt evaluation out of scope.

## Verification

Passed:

- Standalone compile for the updated Java MCP exporter with the module
  classpath:
  `javac ... JavaDomainQuestionNeutralRunnerSnapshotTest.java`
- Reflection execution of
  `shouldProduceDomainQuestionNeutralRunnerSnapshot`, which generated the
  Python fixture.
- Python focused replay:
  `.venv/bin/python -m pytest tests/integration/test_java_domain_fixture_runner.py -q`
  - result: `2 passed in 0.15s`
- Python replay plus manifest gate:
  `.venv/bin/python -m pytest tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `6 passed in 0.16s`
- Scoped ruff:
  `.venv/bin/ruff check tests/integration/test_java_domain_fixture_runner.py`
  - result: `All checks passed!`

Blocked:

- Java focused Maven execution:
  `mvn -q -pl foggy-dataset-mcp -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest test`
  - blocked during testCompile by existing
    `LocalDatasetAccessorGovernanceTest` drift:
    `SemanticQueryRequest.OutputFormattingItem` /
    `getOutputFormatting()` missing.

## Notes

- The first fixture is intentionally normalized-tool-argument replay rather
  than LLM transcript replay.
- The Python semantic boundary is deterministic and local to the test, so this
  lane can run without Odoo demo pack freshness.
