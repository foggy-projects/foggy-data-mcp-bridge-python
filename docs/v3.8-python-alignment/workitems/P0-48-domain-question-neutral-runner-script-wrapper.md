# P0-48 Domain Question Neutral Runner Script Wrapper

Date: 2026-06-10

## Goal

Add a lightweight Python CLI wrapper for the active neutral domain/question
runner lane so developers can validate Java-exported neutral fixtures without
remembering pytest file names or fixture environment variables.

## Scope

- Script:
  `scripts/run-domain-question-neutral-runner.py`
- Python replay:
  `tests/integration/test_java_domain_fixture_runner.py`
- Script test:
  `tests/integration/test_domain_question_neutral_runner_script.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- Default fixture path is
  `tests/fixtures/java_domain_question_neutral_runner_parity.json`.
- `FOGGY_DOMAIN_QUESTION_NEUTRAL_FIXTURE` can override the fixture used by the
  replay test.
- `--dry-run` validates fixture readability and prints a deterministic summary
  without invoking pytest.
- Default execution runs the neutral runner replay and the parity manifest
  gate.
- Summary includes case count, error count, unsupported construct count, and
  unsupported case ids.

## Non-Scope

- No Odoo direct runner.
- No live LLM or transcript evaluation.
- No Java `ToolCallCollector` export.
- No generated model or registry refresh.
- No changes to the domain/question fixture contract beyond runner ergonomics.

## Acceptance

Required checks:

- Script dry run:
  `.venv/bin/python scripts/run-domain-question-neutral-runner.py --dry-run`
- Script default run:
  `.venv/bin/python scripts/run-domain-question-neutral-runner.py`
- Focused pytest:
  `.venv/bin/python -m pytest tests/integration/test_domain_question_neutral_runner_script.py tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check scripts/run-domain-question-neutral-runner.py tests/integration/test_domain_question_neutral_runner_script.py tests/integration/test_java_domain_fixture_runner.py`

## Follow-Ups

- Add a deterministic `ToolCallCollector`-backed Java export when a non-LLM
  planner path is available.
- Keep Odoo domain packs deferred until registry/model drift is resolved and
  explicitly approved.
