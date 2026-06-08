# P0-31 Domain Question Neutral Runner Snapshot Replay

Date: 2026-06-08

## Goal

Activate the P0-28 neutral domain/question runner design with a Java-exported
fixture and Python replay adapter that does not depend on LLM, Odoo business
packs, registry pull, or generated model refresh.

## Scope

- Java exporter:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaDomainQuestionNeutralRunnerSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_domain_question_neutral_runner_parity.json`
- Python replay:
  `tests/integration/test_java_domain_fixture_runner.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- Normalized `dataset.query_model` tool name and argument shape.
- Java camelCase `SemanticQueryRequest` payload conversion in Python.
- Grouped query request markers.
- Calculated-field plus time-window request markers.
- Denied-field fail-closed error contract.
- Warning/report metadata markers.
- Forbidden Odoo/LLM markers stay out of replay results.

## Non-Scope

- Live LLM prompt evaluation.
- Odoo direct-runner packs.
- Model registry pull or generated model update.
- Productized natural-language orchestration.

## Acceptance

Required focused checks:

- Java exporter standalone compile and reflection execution.
- Python replay:
  `.venv/bin/python -m pytest tests/integration/test_java_domain_fixture_runner.py -q`
- Manifest gate:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py -q`

## Follow-Ups

- Add a Java neutral exporter that captures real `ToolCallCollector` output
  when a deterministic non-LLM planner is available.
- Expand non-Odoo cases to unsupported constructs and warning/report summaries.
- Promote Odoo domain packs only after registry/model drift is resolved.
