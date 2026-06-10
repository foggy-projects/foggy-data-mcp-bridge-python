# P0-47 Domain Question Unsupported Construct Snapshot Replay

Date: 2026-06-10

## Goal

Expand the neutral domain/question runner snapshot lane with non-Odoo
unsupported construct cases so Python can replay Java's fail-closed request
contract without an LLM, Odoo business packs, registry pull, or external DB.

## Scope

- Java snapshot producer:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaDomainQuestionNeutralRunnerSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_domain_question_neutral_runner_parity.json`
- Python replay:
  `tests/integration/test_java_domain_fixture_runner.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- `pivot + timeWindow` is represented as a rejected neutral
  `dataset.query_model` validate request.
- Hidden axis/cell functions such as `CELL_AT` are rejected before becoming
  executable calculated fields.
- Cross-model join intent is rejected in the query-model lane and records a
  `dataset.compose_script` recommendation through neutral hints.
- Unsupported construct names are carried in both `error_detail` and
  `neutral-runner-case-summary` report metadata.
- Odoo, concrete business tables, and LLM transcript markers remain forbidden.

## Non-Scope

- Live Java `ToolCallCollector` transcript export.
- AI prompt evaluation or productized question answering.
- Odoo direct-runner packs.
- Registry/model refresh.
- Implementing unsupported constructs in Python.

## Acceptance

Required checks:

- Java exporter when the Java test compile baseline is healthy:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
- Python replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_domain_fixture_runner.py`

## Follow-Ups

- Restore Java exporter execution once unrelated Java test compile drift is
  cleared.
- Add a deterministic `ToolCallCollector`-backed export when a non-LLM planner
  path is available.
- Add an optional script runner wrapper after the neutral request contract is
  stable.
