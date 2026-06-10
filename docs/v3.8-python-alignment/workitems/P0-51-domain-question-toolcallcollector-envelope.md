# P0-51 Domain Question ToolCallCollector Envelope

## Requirement

Close the neutral domain/question runner's remaining fixture-envelope gap by
exporting a deterministic `ToolCallCollector`-backed record for every Java
neutral case and replaying that envelope in Python.

The lane remains engine-neutral: no LLM transcript, no Odoo business model, no
registry pull, and no direct AI domain runner.

## Scope

- Use Java's real `ToolCallCollector` in
  `JavaDomainQuestionNeutralRunnerSnapshotTest`.
- Export stable collector fields only:
  - session id and call count,
  - original and Spring tool names,
  - normalized tool arguments,
  - deterministic result status,
  - success/error state,
  - duration and sequence.
- Validate the collector envelope in Python replay.
- Include the collector envelope count in the Python script dry-run summary.
- Update the snapshot parity manifest so this is no longer a planned extension.

## Non-Goals

- Do not introduce live LLM execution.
- Do not run or port Odoo direct packs.
- Do not change semantic query execution behavior.
- Do not export unstable collector timestamps.

## Acceptance

- Java exporter writes `collectorRecord` for every neutral case.
- Python replay validates collector tool names, arguments, sequence,
  success/error state, and error code.
- `scripts/run-domain-question-neutral-runner.py --dry-run` reports collector
  coverage for all cases.
- Focused Java/Python replay and manifest tests pass.
