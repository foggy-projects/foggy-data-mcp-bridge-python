---
doc_purpose: Freeze the public API metadata contract for QueryModel aggregate relation lineage.
version: v3.8-python-alignment
priority: P0-88
status: contract-ready
owner: python-engine
---

# P0-88 QueryModel Aggregate API Metadata Contract

Date: 2026-06-12

## Scope

P0-88 defines the Python public metadata contract for aggregate relation output
fields before any DTO/API exposure changes. It aligns with Java
`SemanticServiceV3Test#testMetadata_Json_ShouldExposeAggregateRelationMeasure`
and the Java 9.2 aggregate relation acceptance record.

This item freezes the contract only. Runtime/API implementation can follow in a
separate work item after fixture evidence and replay tests are prepared.

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

The public V3 metadata contract is not yet frozen for aggregate relation
outputs. Python must not expose internal-only lineage fields through the public
DTO unless Java adds them to the shared contract.

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

## Recommended Verification

Add tests only when the implementation work starts:

- A focused Python metadata test for aggregate relation output fields through
  the public V3 metadata path.
- A fixture-backed replay that checks the exact seven-key
  `aggregateRelation` DTO shape.
- Negative assertions that public metadata does not expose physical RHS column
  names or internal-only Python lineage keys.
- Regression checks that P0-84 internal build-column lineage remains available
  for compiler/runtime diagnostics.

## Non-Goals

- No UI/data-viewer metadata behavior.
- No registry-generated model refresh.
- No formula/calculated-field execution over aggregate outputs.
- No external dialect runtime support.

## Acceptance Criteria

- The Java public metadata key set is documented as the Python target.
- Internal compiler metadata and public DTO metadata are explicitly separated.
- Future implementation can add tests without re-deciding the public shape.
- No Python runtime/API code changes are required by this contract item.

## Execution Check-In

- Status: contract ready.
- Current Python code impact: none.
- Current fixture impact: none.
- Required next evidence: either a Java metadata snapshot case that includes
  the exact public DTO shape or a focused Python implementation test derived
  from the Java V3 metadata contract above.
- Verification on 2026-06-12: existing aggregate relation manifest/contract/
  parity replay stayed green with `10 passed in 0.05s`.
- `git diff --check` passed.
