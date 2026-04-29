# S7f outer window contract preflight

## Metadata

- doc_type: contract-preflight
- version: post-v1.5 follow-up / 8.5.0.beta reference
- status: drafted-for-java-review
- owner: root-controller
- java_reference_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- prerequisite: S7e Java + Python mirror complete

## Purpose

S7f should open outer window over `CompiledRelation` without reopening the
older `timeWindow + calculatedFields` post-window channel. The operation must
remain an explicit outer relation layer:

```text
QueryPlan -> CompiledRelation -> outer window query
```

The main goal is to let a stable relation be ranked, lagged, or smoothed while
preserving output schema meaning, datasource identity, CTE hoisting rules, and
fail-closed validation.

## Non-goals

- Do not allow arbitrary raw `OVER(...)` SQL.
- Do not reopen post-timeWindow calculatedFields `windowFrame`.
- Do not allow relation join / union in S7f.
- Do not make MySQL 5.7 support outer window.
- Do not make ratio / percent columns window input by default.
- Do not implement Python runtime before Java publishes S7f snapshot evidence.

## Contract Decisions

### Capability

`RelationCapabilities.supportsOuterWindow` should be true only when both
conditions hold:

- the relation can be safely wrapped for the dialect; and
- the dialect supports window functions.

Recommended dialect matrix:

| Dialect | No CTE | With CTE | Reason |
|---|---:|---:|---|
| `mysql8` | true | true | MySQL 8 supports window functions and CTE |
| `postgres` / `postgresql` | true | true | supports window functions and CTE |
| `sqlite` | true | true | modern SQLite supports window functions |
| `mssql` / `sqlserver` | true | true | supports window functions; CTE must be hoisted |
| `mysql` / `mysql57` | false | false | MySQL 5.7 has no window functions |

MySQL 5.7 with CTE remains `FAIL_CLOSED`; MySQL 5.7 without CTE must still
reject outer window with `RELATION_OUTER_WINDOW_NOT_SUPPORTED`.

### Reference Policy

S7f should not turn every readable/orderable column into a valid window input.

Recommended defaults:

- `DIMENSION_DEFAULT`: keep `readable`, `groupable`, `orderable`.
- `MEASURE_DEFAULT`: add `windowable` in addition to `readable`,
  `aggregatable`, `orderable`.
- `TIME_WINDOW_DERIVED_DEFAULT`: keep `readable`, `orderable` only.

Implications:

- `SUM(salesAmount) OVER (...)` is legal because `salesAmount` is windowable.
- `AVG(salesAmount__ratio) OVER (...)` is rejected because ratio is not
  windowable.
- `RANK() OVER (ORDER BY salesAmount__ratio DESC)` may be legal because ratio
  is used only as an order key and already has `orderable`.

### Window Expression Shape

S7f should use a restricted, parsed subset rather than arbitrary SQL text.
Either a structured request object or a strictly parsed select string is
acceptable, but validation must extract:

- window function
- input column if the function has one
- partition columns
- order columns
- optional frame
- output alias

Recommended first subset:

| Function family | Examples | Input policy |
|---|---|---|
| ranking | `ROW_NUMBER`, `RANK`, `DENSE_RANK` | no input column |
| offset | `LAG(col)`, `LEAD(col)` | input must be `windowable` |
| aggregate window | `SUM(col)`, `AVG(col)`, `MIN(col)`, `MAX(col)`, `COUNT(col)` | input must be `windowable`; `COUNT(*)` allowed |

Partition columns should require `groupable` or `readable` + explicit
partition allowance. For S7f first pass, prefer `groupable` to keep partition
semantics close to dimension grouping.

Order columns must require `orderable`.

### Output Schema

Window outputs must be re-derived as new `ColumnSpec` entries:

- `semanticKind = window_calc`
- `referencePolicy = {readable, orderable}` by default
- `lineage` includes input, partition, and order columns
- `valueMeaning` describes the function, partition, order, and frame

Do not mark window outputs as `aggregatable` or `windowable` by default. A
future stage can decide whether window-over-window is allowed.

### Error Codes

Recommended new error code:

```text
compose-compile-error/relation-column-not-windowable
```

Existing codes should remain:

- `RELATION_OUTER_WINDOW_NOT_SUPPORTED` for capability/dialect closed.
- `RELATION_COLUMN_NOT_FOUND` for unknown input/partition/order columns.
- `RELATION_COLUMN_NOT_ORDERABLE` for invalid order columns.
- `RELATION_COLUMN_NOT_READABLE` or a future group-specific code for invalid
  partition columns.

## Required Java Snapshot

Java should publish a new snapshot rather than changing S7a/S7e snapshots:

```text
target/parity/_stable_relation_outer_window_snapshot.json
contractVersion: S7f-1
```

Minimum cases:

1. `outer-rank-ratio-order-mysql8`
   - pass
   - ranking over `ORDER BY salesAmount__ratio DESC`
   - ratio is not window input; only order key
   - output schema contains `growthRank` as `window_calc`

2. `outer-moving-avg-measure-mysql8`
   - pass
   - `AVG(salesAmount) OVER (PARTITION BY storeName ORDER BY salesDate ... )`
   - `salesAmount` is windowable
   - `storeName` is groupable
   - `salesDate` is orderable

3. `outer-window-ratio-input-rejected-mysql8`
   - rejected
   - `AVG(salesAmount__ratio) OVER (...)`
   - error code `compose-compile-error/relation-column-not-windowable`

4. `outer-window-mysql57-rejected`
   - rejected even without CTE
   - error code `compose-compile-error/relation-outer-window-not-supported`

5. `outer-window-hoisted-sqlserver`
   - pass
   - SQL starts with `;WITH`
   - contains inner CTE before relation CTE
   - never contains `FROM (WITH`
   - params order is stable

## Verification Gate

Java focused verification should include:

```powershell
mvn test -pl foggy-dataset-model "-Dtest=RelationOuterQueryBuilderTest,StableRelationOuterWindowSnapshotTest,StableRelationOuterAggregateSnapshotTest,StableRelationSnapshotTest,RelationModelTest,ComposeRelationCompilerTest,ComposeCompileErrorCodesTest,ColumnSpecMetadataTest"
```

Python mirror should not start until Java snapshot exists. After Java publishes
the snapshot, Python should add a consumer test equivalent to S7e:

```powershell
pytest tests/compose/schema/test_column_spec_metadata.py tests/compose/relation -q
```

## Open Questions for Java Review

- Should partition columns require strictly `groupable`, or should S7f add a
  distinct `partitionable` reference policy in a later contract?
- Should S7f parse restricted SQL strings, or introduce a structured
  `WindowSelectSpec` to avoid fragile `OVER(...)` parsing?
- Should `COUNT(*) OVER (...)` produce lineage as an empty set or include
  partition/order columns only?
- Should window output columns be orderable by default across all dialects?

## Recommendation

Proceed with Java-first S7f only after confirming the two policy decisions:

1. `MEASURE_DEFAULT` gains `windowable`; `TIME_WINDOW_DERIVED_DEFAULT` does
   not.
2. MySQL 5.7 keeps `supportsOuterWindow=false` even for simple inline
   relations.

This keeps S7f useful for ranking and smoothing while preserving the business
guardrail that ratios are not silently averaged or recursively windowed.
