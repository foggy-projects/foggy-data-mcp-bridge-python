# P0-51 Domain Question ToolCallCollector Envelope Progress

## 2026-06-10

Status: complete.

Changes:

- Java neutral runner exporter now records each case through
  `ToolCallCollector` and exports a stable `collectorRecord` envelope.
- Python replay validates collector session, call count, tool names,
  normalized arguments, sequence, duration, success/error state, and error
  code.
- Python script dry-run summary includes `collectorRecordCount`.
- Snapshot parity manifest now treats the collector envelope as active
  exported evidence instead of a planned extension.

Evidence:

- Java MCP reactor exporter passed:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`.
- Python dry-run plus focused replay and manifest passed:
  `.venv/bin/python scripts/run-domain-question-neutral-runner.py --dry-run && .venv/bin/python -m pytest tests/integration/test_domain_question_neutral_runner_script.py tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  with `7 passed in 0.27s`.
- Python script default run passed:
  `.venv/bin/python scripts/run-domain-question-neutral-runner.py`
  with `6 passed in 0.15s`.
- Ruff passed:
  `.venv/bin/ruff check scripts/run-domain-question-neutral-runner.py tests/integration/test_domain_question_neutral_runner_script.py tests/integration/test_java_domain_fixture_runner.py`.
- `git diff --check` passed in both Java and Python worktrees.

Follow-up:

- Odoo/domain direct packs remain deferred until registry/model drift is
  resolved.
