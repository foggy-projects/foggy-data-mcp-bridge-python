# P0-48 Domain Question Neutral Runner Script Wrapper Progress

Date: 2026-06-10

## Completed

- Added `scripts/run-domain-question-neutral-runner.py` as the local entrypoint
  for the neutral domain/question runner parity lane.
- Added deterministic `--dry-run` fixture summary output covering case count,
  error count, unsupported construct count, and unsupported case ids.
- Wired `FOGGY_DOMAIN_QUESTION_NEUTRAL_FIXTURE` into the existing Python replay
  so the script can invoke pytest with an explicit fixture path.
- Added an integration test for the script dry-run summary.
- Updated the Java snapshot parity manifest to mark the script wrapper as
  active verification instead of a planned extension.

## Verification

Passed:

- Java P0-47 exporter after Java compile drift was cleared:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
- Python script dry-run plus focused replay and manifest:
  `.venv/bin/python scripts/run-domain-question-neutral-runner.py --dry-run && .venv/bin/python -m pytest tests/integration/test_domain_question_neutral_runner_script.py tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `7 passed in 0.33s`
- Python script default run:
  `.venv/bin/python scripts/run-domain-question-neutral-runner.py`
  - `6 passed in 0.15s`
- Scoped lint:
  `.venv/bin/ruff check scripts/run-domain-question-neutral-runner.py tests/integration/test_domain_question_neutral_runner_script.py tests/integration/test_java_domain_fixture_runner.py`
- Full Python pytest:
  `.venv/bin/python -m pytest -q`
  - `4083 passed, 232 skipped, 53 warnings in 17.66s`
