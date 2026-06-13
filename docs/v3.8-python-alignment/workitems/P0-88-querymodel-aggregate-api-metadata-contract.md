---
doc_purpose: Track the public API metadata contract and implementation for QueryModel aggregate relation lineage.
version: v3.8-python-alignment
priority: P0-88
status: implemented
owner: python-engine
---

# P0-88 QueryModel Aggregate API Metadata Contract

Date: 2026-06-12

## Scope

P0-88 defines and implements the Python public metadata contract for aggregate
relation output fields through `get_metadata_v3(...)`. It aligns with Java
`SemanticServiceV3Test#testMetadata_Json_ShouldExposeAggregateRelationMeasure`
and the Java 9.2 aggregate relation acceptance record.

The runtime SQL path remains the narrow SQLite aggregate relation boundary.
This item only exposes the public V3 metadata DTO for aggregate relation output
measures and keeps internal compiler lineage separate.

## Java Contract

For an aggregate relation output measure such as `salesAmount`, Java V3
metadata exposes the field as a normal measure plus an `aggregateRelation`
lineage object.

Required parent field attributes:

| Attribute | Java Requirement |
| --- | --- |
| `fieldName` | The aggregate output alias, for example `salesAmount`. |
| `name` | The RHS business caption, for example `销售金额`. |
| `type` | The RHS measure type, for example `MONEY`. |
| `measure` | `true`. |
| `aggregatable` | `true`. |
| `aggregation` | The aggregate function, for example `SUM`. |
| `models` | Includes the owning QueryModel alias. |

Required `aggregateRelation` keys:

| Key | Required Value Shape |
| --- | --- |
| `aggregation` | String aggregate function, for example `SUM`. |
| `sourceCaption` | String RHS field caption. |
| `sourceMeasure` | String semantic source field alias. |
| `sourceAlias` | String aggregate output/source alias. |
| `sourceExpression` | String source expression from Java metadata. |
| `aggregateExpression` | String aggregate expression from Java metadata. |
| `sourceColumn` | String semantic source field alias, not the physical database column. |

The Java test asserts the exact `aggregateRelation` key set above and requires
all values to be strings. It also asserts that `sourceColumn`, `sourceAlias`,
and `sourceMeasure` are the semantic field alias (`salesAmount`) while
`sourceExpression` and `aggregateExpression` contain generated SQL expression
text.

## Python Current State

P0-84 added internal aggregate output lineage on `QueryBuildResult.columns`.
That internal metadata may contain engine-only fields such as semantic unit
information in addition to the Java metadata keys.

P0-88 now exposes aggregate relation output fields in public V3 metadata as
normal measures with a filtered `aggregateRelation` object. Python does not
expose internal-only lineage fields through the public DTO unless Java adds
them to the shared contract.

## Python Public Contract

When Python exposes aggregate relation lineage through V3 metadata:

1. The parent field must behave like the Java measure field:
   `measure=true`, `aggregatable=true`, Java-aligned aggregation, inherited
   RHS type/caption, and owning model attribution.
2. `aggregateRelation` must expose exactly the seven Java keys listed above.
3. `sourceColumn` must use the semantic source field alias, not the physical
   database column name.
4. Internal semantic-unit fields may remain available inside compiler/runtime
   metadata, but they must be filtered out of the public `aggregateRelation`
   DTO until Java defines a shared public key.
5. Python must not add Python-only public keys to `aggregateRelation` in this
   alignment line.

## Open Contract Question

Java currently exposes `sourceExpression` and `aggregateExpression` as strings
that can contain generated SQL expression text. For parity, Python should match
that behavior when the DTO is implemented. If the product later decides these
fields need sanitization or a different representation, that should be a joint
Java/Python API contract change rather than a Python-only divergence.

## Implementation

- Added public aggregate relation metadata generation in
  `SemanticQueryService.get_metadata_v3(...)`.
- Public aggregate output fields are emitted as measures with
  `measure=true`, `aggregatable=true`, Java-aligned aggregation, source type,
  source/output caption, owning model attribution, and top-level
  `sourceExpression` / `aggregateExpression` strings.
- Public `aggregateRelation` is filtered to exactly the seven Java keys:
  `aggregation`, `sourceCaption`, `sourceMeasure`, `sourceAlias`,
  `sourceExpression`, `aggregateExpression`, and `sourceColumn`.
- Internal `QueryBuildResult.columns[*].aggregateRelation` retains
  engine-only semantic-unit fields for compiler/runtime diagnostics.
- Metadata governance now handles aggregate relation output fields explicitly:
  `visible_fields` must include the aggregate output alias, and
  `denied_columns` hides aggregate outputs whose RHS physical source column is
  denied.

## Verification

- Added a focused Python metadata test for aggregate relation output fields
  through the public V3 metadata path.
- Added fixture-backed assertions that check the exact seven-key
  `aggregateRelation` DTO shape.
- Added negative assertions that public metadata does not expose physical RHS
  column names outside the generated expression fields or internal-only Python
  lineage keys.
- Added regression checks that P0-84 internal build-column lineage remains
  available for compiler/runtime diagnostics.
- Added metadata denied-column coverage for RHS source-column hiding.

## Non-Goals

- No UI/data-viewer metadata behavior.
- No registry-generated model refresh.
- No formula/calculated-field execution over aggregate outputs.
- No external dialect runtime support.

## Acceptance Criteria

- Completed. The Java public metadata key set is documented as the Python
  target.
- Completed. Internal compiler metadata and public DTO metadata are explicitly
  separated.
- Completed. Python public V3 metadata exposes aggregate relation output
  fields with exactly the seven-key Java lineage object.
- Completed. Public metadata hides aggregate outputs when `denied_columns`
  denies their RHS source physical column.
- Deferred. Broader external dialect/runtime behavior remains outside P0-88.

## Execution Check-In

- Status: implemented.
- Code paths touched:
  - `src/foggy/dataset_model/semantic/service.py`
  - `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
- Current fixture impact: no fixture file changes; tests use the committed
  `aggregate-join-metadata-lineage` Java snapshot case as the public shape
  oracle.
- Verification on 2026-06-13:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  (`22 passed in 0.61s`).
- P0 aggregate verification on 2026-06-13:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  (`37 passed in 0.57s`).
- Neighboring semantic regression on 2026-06-13:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_semantic_query.py tests/test_dataset_model/test_strict_column_resolution.py tests/test_dataset_model/test_window_functions.py -q`
  (`131 passed in 8.25s`).
- Full Python baseline on 2026-06-13:
  `.venv/bin/python -m pytest -q`
  (`4149 passed, 232 skipped, 53 warnings in 19.25s`).
- Static checks on 2026-06-13:
  `.venv/bin/ruff check --select F src/foggy/dataset_model/semantic/service.py tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
  and `git diff --check` passed.
- Remaining risk: external dialect parity, multi-relation metadata collisions,
  and broader QueryModel stage exposure still need follow-up fixtures before
  broad product/runtime rollout.
