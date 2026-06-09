# P0-38 Domain Question Warning Report Metadata

Date: 2026-06-09

## Goal

Extend the neutral domain/question runner lane from normalized tool arguments
to warning/report metadata shape without depending on LLM, Odoo, or generated
model refresh.

## Current Coverage

P0-31 already replays Java-exported neutral cases through
`tests/integration/test_java_domain_fixture_runner.py` and validates:

- normalized `dataset.query_model` tool argument shape,
- grouped query requests,
- calculated-field plus time-window requests,
- denied-field fail-closed behavior,
- `warnings` markers from the fixture.

Current fixture:

- `tests/fixtures/java_domain_question_neutral_runner_parity.json`

## Remaining Expansion

- Add report metadata to the neutral fixture envelope.
- Keep warning markers machine-readable and case-specific.
- Capture summary fields such as warning count, error count, tool name, and
  normalized request id where Java exports them.
- Distinguish direct semantic response warnings from runner/report warnings.

## Non-Scope

- Live LLM prompt evaluation.
- Odoo direct runner packs.
- AI report product UI.
- Registry model refresh.

## Acceptance

- Python replay validates both `warnings` and `reports` metadata when present.
- Missing optional report metadata stays backward-compatible for old fixtures.
- No Odoo or LLM dependency is introduced into the always-on Python test suite.
