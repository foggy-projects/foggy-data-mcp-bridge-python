# P0-41 Domain Question Report Metadata Snapshot Replay

Date: 2026-06-09

## Goal

Close the P0-38 follow-up by extending the neutral domain/question runner
fixture from warning markers to machine-checkable report metadata, without
introducing LLM, Odoo, registry, or generated model dependencies.

## Scope

- Java snapshot producer:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaDomainQuestionNeutralRunnerSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_domain_question_neutral_runner_parity.json`
- Python replay:
  `tests/integration/test_java_domain_fixture_runner.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contract Covered

Each neutral runner case may now include `expected.reports`, currently as one
`neutral-runner-case-summary` record with:

- `toolName`, `model`, and `mode`,
- `status` as `ok` or `error`,
- `warningCount`,
- `errorCount`,
- `warningMarkers`,
- optional `errorCode` for fail-closed cases.

Python replay validates report metadata against the deterministic semantic
response built from the Java-exported normalized tool arguments.

## Non-Scope

- Java `ToolCallCollector` transcript export.
- Live LLM prompt evaluation.
- Odoo domain packs or registry model refresh.
- AI report product UI.

## Acceptance

Required checks:

- Java MCP exporter with reactor dependencies:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
- Python replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_domain_fixture_runner.py`
