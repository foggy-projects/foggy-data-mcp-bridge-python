# P0-28 Domain Question Neutral Runner Adapter

Date: 2026-06-08

## Goal

Define the first neutral domain/question fixture adapter for Python alignment
without importing Odoo business packs or refreshing generated registry models.

## Scope

- Design doc:
  `docs/v3.8-python-alignment/design/P0-28-domain-question-neutral-runner-adapter-design.md`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`
- Future Python runner:
  `tests/integration/test_java_domain_fixture_runner.py`

## Contract Direction

Java should export engine-neutral fixtures with:

- request payload
- expected MCP tool name and arguments
- expected SQL/result/error summary
- warning/report metadata

Python should replay those fixtures through the Python MCP/semantic boundary
and compare normalized tool arguments and stable result markers.

## Explicit Non-Scope

- Odoo business model fixtures.
- Registry pull/update.
- Generated model refresh.
- Productized natural-language orchestration.

## Acceptance

- Adapter fixture schema is documented.
- Java export requirements are explicit.
- Python replay ownership and test path are explicit.
- Manifest keeps the lane `planned` and links the design doc until Java export
  and Python replay exist.
