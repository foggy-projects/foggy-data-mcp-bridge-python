# P0-41 Domain Question Report Metadata Snapshot Replay Progress

Date: 2026-06-09

## Completed

- Extended the Java neutral domain/question runner exporter with optional
  `expected.reports` metadata.
- Regenerated
  `tests/fixtures/java_domain_question_neutral_runner_parity.json`.
- Added Python replay assertions for report type, tool/model/mode, status,
  warning count, error count, warning markers, and error code.
- Kept replay backward-compatible for old fixtures that omit `reports`.
- Kept the lane LLM-free, Odoo-free, and registry-free.

## Verification

Passed:

- Java MCP exporter with reactor dependencies:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
- Python focused replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `6 passed in 0.17s`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_domain_fixture_runner.py`
  - passed

Pending before closeout:

- Full Python pytest:
  `.venv/bin/python -m pytest -q`
  - `4076 passed, 232 skipped, 53 warnings in 18.17s`
