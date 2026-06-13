---
doc_purpose: Harden fail-closed request-stage boundaries for Python QueryModel aggregate relation alignment.
version: v3.8-python-alignment
priority: P0-90
status: complete
owner: python-engine
---

# P0-90 QueryModel Aggregate Request-Stage Refusal

Date: 2026-06-13

## Scope

P0-90 continues the Python engine to Java engine alignment line after P0-89.
It does not add broad QueryModel stage support. It locks the current Python
SQLite aggregate relation path so request stages without Java snapshot/result
fixtures remain fail-closed before SQL generation.

Later status note: P0-92/P0-93 introduced the Java v3 29-case fixture and
Python replay, and P0-95 opened bounded support for aggregate output `orderBy`
and `returnTotal` in the narrow SQLite aggregate relation path. The P0-90
refusal matrix remains the historical guard that existed before v3 fixture
evidence; only `groupBy`, `having`, post stages, `timeWindow`, and `pivot`
remain active refused request stages from this matrix.

This item is intentionally Python-side only:

- Java worktree has unrelated uncommitted changes, so this item does not touch
  Java exporter code.
- No registry-generated model refresh is required.
- No Odoo business model expansion is in scope.
- Positive support for broader request stages remains blocked on Java
  snapshot/result fixtures and an API contract decision.

## Refusal Matrix

| Request stage | Java current evidence | Python P0-90 status | Risk | Next validation |
| --- | --- | --- | --- | --- |
| `groupBy` | Java aggregate relation acceptance includes broader QueryModel stages outside the committed Python replay fixture. | Explicitly refused in the aggregate relation SQLite path. | High | Export Java SQL/result fixture before enabling. |
| `having` | Java accepts aggregate relation filters and broader stage behavior in its implementation tests. | Explicitly refused in the broader request-stage gate. | High | Export Java diagnostics/result fixture for HAVING semantics. |
| `orderBy` | Java acceptance records aggregate relation `orderBy` behavior; P0-92 exports a v3 fixture case. | Historical P0-90 refusal is superseded by P0-95 for aggregate output aliases in the narrow SQLite path. | Medium | Keep Java v3 replay plus focused Python runtime SQL/result tests active. |
| `returnTotal` | Java QueryFacade has `returnTotal` aggregate relation behavior; P0-92 exports a v3 fixture case. | Historical P0-90 refusal is superseded by P0-95 for the narrow SQLite aggregate relation path. | Medium | Keep Java v3 replay plus focused Python total SQL/totalData execution tests active. |
| `postAggregateCalculations` | Java has post-stage behavior in the broader engine line, but no aggregate-relation Python fixture. | Explicitly refused before SQL generation. | High | Export Java calculated/result fixture. |
| `postSlice` | Java has post-stage behavior in the broader engine line, but no aggregate-relation Python fixture. | Explicitly refused before SQL generation. | High | Export Java post-stage result fixture. |
| `timeWindow` | Java supports time window in the broader engine, but aggregate-relation combination is not frozen for Python. | Explicitly refused in the aggregate relation SQLite path. | High | Export combined aggregate/time-window fixture before support. |
| `pivot` | Java supports Pivot V9 in the broader engine, but aggregate-relation combination is not frozen for Python. | Internal aggregate relation path refuses `pivot` before SQL generation; public pivot remains governed by existing pivot fail-closed/translation gates. | High | Export combined aggregate/pivot fixture before support. |

## Implementation Notes

- P0-90 originally treated `returnTotal` and `orderBy` like `groupBy`,
  `having`, and post stages: unsupported until a Java fixture defines
  SQL/result semantics.
- P0-95 supersedes that part of the gate after P0-92/P0-93 supplied v3 Java
  fixture evidence; `orderBy` and `returnTotal` are now implemented only for
  the narrow SQLite aggregate relation path.
- Focused runtime tests register both the left aggregate relation model and the
  RHS `FactSalesModel` so failures reach the request-stage gate instead of the
  older missing-RHS refusal.
- Error responses keep using `AGGREGATE_JOIN_UNSUPPORTED` with sanitized detail;
  physical table names are not leaked.

## Acceptance Evidence

- Focused refusal matrix on 2026-06-13:
  `.venv/bin/pytest tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
  with `13 passed in 0.58s`.
- Aggregate runtime/replay combined coverage on 2026-06-13:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  with `51 passed in 0.64s`.
- Full Python baseline on 2026-06-13:
  `.venv/bin/python -m pytest -q` with
  `4163 passed, 232 skipped, 53 warnings in 20.29s`.

## Follow-Up

P0-90 does not close broader QueryModel stage parity. After P0-95, the next
positive support step should focus on still-refused `groupBy/having`, post-stage
combinations, `timeWindow`, and pivot combinations. `orderBy` and `returnTotal`
must stay bounded to the narrow SQLite aggregate relation contract until
external dialect, multi-relation, and broader QueryModel total semantics have
their own fixtures.
