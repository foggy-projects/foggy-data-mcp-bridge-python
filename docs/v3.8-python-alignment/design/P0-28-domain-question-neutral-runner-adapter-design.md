# P0-28 Domain Question Neutral Runner Adapter Design

Date: 2026-06-08

## Purpose

Python needs an engine-neutral way to replay Java domain/question fixtures
before any Odoo business model alignment. The adapter should validate the
translation boundary: question/request in, MCP tool argument out, and stable
SQL/result/error markers after execution.

## Fixture Shape

Proposed JSON schema:

```json
{
  "schemaVersion": 1,
  "feature": "domainQuestionNeutralRunner",
  "source": "JavaDomainQuestionNeutralSnapshotTest",
  "cases": [
    {
      "id": "sales-by-status-current-quarter",
      "question": "sales by status this quarter",
      "context": {
        "namespace": "demo",
        "principal": {
          "userId": "snapshot-user",
          "tenantId": "demo",
          "roles": ["analyst"]
        }
      },
      "expected": {
        "toolName": "dataset.query_model",
        "toolArguments": {},
        "sqlMarkers": [],
        "resultMarkers": [],
        "errorCode": null,
        "warnings": []
      }
    }
  ]
}
```

`toolArguments` should be a normalized semantic request payload, not a raw LLM
transcript. Java may include the original question for traceability, but Python
P0 replay should not require a live LLM.

## Java Export Requirements

- Export neutral sales/orders/service-ticket cases first.
- Include tool name and normalized tool arguments.
- Include stable SQL markers or result markers, not full physical SQL when
  dialect-specific formatting is not part of the contract.
- Include expected warning/report metadata for rule violations.
- Include fail-closed cases for invalid fields, denied columns, and unsupported
  constructs.
- Keep Odoo packs out of the P0 exporter.

## Python Replay Responsibilities

- Load the Java fixture from `tests/fixtures/`.
- Build a deterministic Python semantic service over existing demo-neutral
  models or local test models.
- Submit the expected tool arguments directly to the Python MCP tool or service
  boundary.
- Compare:
  - tool name
  - normalized request shape
  - stable SQL/result/error markers
  - warning metadata
- Skip only when the fixture declares an external dependency unavailable in the
  local test profile.

## Implementation Plan

1. Add Java neutral exporter and fixture path.
2. Add Python `tests/integration/test_java_domain_fixture_runner.py`.
3. Start with three non-Odoo cases:
   - simple grouped query
   - calculated/time-window query
   - denied field fail-closed query
4. Add manifest activation once fixture and replay both exist.

## Non-Scope

- LLM prompt evaluation.
- Odoo model registry pull.
- Odoo direct runner parity.
- Generated model updates.
