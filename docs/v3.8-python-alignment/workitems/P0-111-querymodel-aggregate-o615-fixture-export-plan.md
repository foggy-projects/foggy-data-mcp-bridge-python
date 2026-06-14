---
doc_purpose: Record the executable Java fixture export plan for O615 aggregate relation explicit join graph parity.
version: v3.8-python-alignment
priority: P0-111
status: complete
owner: python-engine
---

# P0-111 QueryModel Aggregate O615 Fixture Export Plan

Date: 2026-06-14

## Scope

P0-111 records the next required fixture contract before Python opens broader
O615 explicit join graph behavior. Python already has a bounded neutral
O615-shaped slice from P0-102, plus dimension and nested fail-closed/runtime
evidence through P0-110. The remaining O615 behavior is tied to Java business
models and explicit join graph aliases, so Python should not infer support
without a Java-exported replay contract.

Covered by this planning item:

- exact Java O615 probe tests to export,
- expected neutral snapshot payload categories,
- Python replay and implementation use,
- fail-closed rule until the fixture exists.

Out of scope:

- implementing positive O615 explicit multi-join graph lowering in Python,
- touching generated Odoo/TMS business models,
- external dialect implementation,
- changing current SQLite aggregate relation runtime behavior.

## Java Evidence Read

Java O615 evidence is in
`foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/ecommerce/AggregateJoinQueryModelTest.java`.

The next exporter should include these cases:

| Java test | Model | Required fixture evidence |
| --- | --- | --- |
| `aggregateRelationO615ProbeNoColumnsWithAccessShouldResolveJoinPath` | `OrderStationStockProjectionO615ProbeQueryModel` | no-columns request shape, default projection, result row count, selected aliases, SQL join-path markers |
| `aggregateRelationO615ProbeExpressJoinNoColumnsShouldResolveJoinPath` | `OrderStationStockProjectionO615ExpressJoinProbeQueryModel` | explicit join alias no-columns request, orderNo slice, result row count, selected aliases, SQL join-path markers |
| `aggregateRelationO615TenantGuardShouldBypassFieldAccessWithoutLeaking` | `OrderStationStockProjectionO615ExpressJoinProbeQueryModel` | `systemSlice` tenant guard, fieldAccess bypass, RHS tenant pushdown, RHS groupBy tenant key marker, no returned tenant field |
| `aggregateRelationO615ProbeExpressJoinDimensionIdSliceShouldResolveJoinPath` | `OrderStationStockProjectionO615ExpressJoinProbeQueryModel` | `destinationServiceArea$id` request slice, selected dimension id value, SQL join-path markers, result row count |
| `aggregateRelationO615ProbeRhsDimensionFilterShouldResolveJoinPath` | `OrderStationStockProjectionO615RhsDimensionProbeQueryModel` | RHS dimension filter plus orderNo slice, RHS filter SQL markers, result row count |
| `aggregateRelationO615ProbeRhsJoinDimensionFilterShouldResolveJoinPath` | `OrderStationStockProjectionO615RhsJoinDimensionProbeQueryModel` | RHS aggregate-source internal dimension join filter plus orderNo slice, RHS join/filter SQL markers, result row count |

## Snapshot Contract

Recommended next aggregate snapshot name:

- `querymodel-aggregate-join-4`

Each exported case should include:

- stable `caseId`,
- `request` payload after Java normalization,
- `mode` and dialect profile,
- normalized SQL markers rather than full fragile SQL when alias names are
  implementation-defined,
- result row count and representative public field values,
- `debug.extra.aggregateRelationDiagnostics` markers where applicable,
- governance metadata for fieldAccess / systemSlice cases,
- forbidden markers for physical tenant fields, private aliases, and internal
  join table names where the public response must not leak them.

## Python Use

Before implementation:

- add manifest coverage for `querymodel-aggregate-join-4`,
- add replay-only assertions that either match Python-supported neutral slices
  or record unsupported O615 cases as expected gaps,
- keep unsupported positive O615 graph behavior outside runtime exposure.

After fixture replay is stable:

- decide which O615 cases can be mapped to neutral engine behavior,
- implement only the smallest graph-lowering slice with fixture-backed SQL and
  result markers,
- keep nested/multi-hop graph paths fail-closed if the fixture cannot be
  represented by the current Python model graph.

## Current Python Baseline

Already covered:

- P0-102: bounded neutral no-columns / aliased scalar key / tenant guard
  runtime slice,
- P0-103: non-join-key dimension property and `$id` request slices stay
  outer-only,
- P0-104/P0-105: RHS dimension `$id` fixed/runtime filters,
- P0-107/P0-108/P0-109/P0-110: nested dimension `$id` fail-closed boundaries
  across RHS filters and left/root request slices.

Still missing until Java exports the fixture:

- concrete O615 `destinationServiceArea$id` request slice replay,
- explicit join alias owner-resolution replay,
- O615 tenant guard no-leak replay on the real Java graph,
- RHS dimension filter and RHS internal dimension join filter replay,
- positive Python multi-join graph lowering.

## Verification

No Python runtime code changed in P0-111.

Doc-only checks:

- `git diff --check`

Result:

- passed

## Acceptance Decision

P0-111 is complete when this fixture plan is recorded and linked from the
alignment README/backlog. The actual Java exporter and Python replay should be
tracked as a later P0 item before any positive O615 graph implementation starts.
