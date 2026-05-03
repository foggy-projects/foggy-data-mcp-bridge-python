# Pivot 9.2 Telemetry Docs Acceptance

## 文档作用

- doc_type: feature-acceptance
- status: accepted-docs
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 Python Pivot v1.10 P6 production telemetry / log-query examples 的文档签收结论。

## Scope

P6 只补运维文档，不改 runtime：

- existing telemetry markers
- refusal/error classification
- safe log-query examples
- privacy/safety rules
- known observability gaps

## Evidence

Created:

- `docs/v1.10/operations/pivot-9.2-telemetry-log-query-examples.md`

The guide covers:

- DomainTransport success marker.
- DomainTransport refusal.
- Cascade refusal categories.
- SQL Server / MySQL 5.7 accepted-refusal interpretation.
- Safe grep / LogQL / KQL / SQL-style examples.
- Explicit no-raw-values logging rules.

## Signoff

Status: accepted-docs for Python Pivot v1.10 P6.

P6 is sufficient for operational documentation. It does not claim structured telemetry dashboards or new runtime metrics.
