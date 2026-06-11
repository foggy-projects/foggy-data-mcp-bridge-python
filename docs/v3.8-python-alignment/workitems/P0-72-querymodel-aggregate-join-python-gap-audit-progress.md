# P0-72 Progress

Date: 2026-06-11

## Status

- Status: docs-complete
- Owner: Python alignment line
- Scope: QueryModel aggregate join parity audit and Python landing-point freeze

## Documents Read

- Java:
  - `docs/9.2.0/workitems/query-model-aggregate-join.md`
  - `docs/9.2.0/acceptance/query-model-aggregate-join-acceptance.md`
  - Java ahead commit summary for `84000c81 feat: expose aggregate relation pushdown diagnostics`
  - `AggregateRelationDiagnostic.java`
  - `AggregateJoinTableModel.java` diagnostic/pushdown sections
- Python:
  - `docs/v3.8-python-alignment/P0-python-alignment-upgrade-plan.md`
  - `docs/v3.8-python-alignment/workitems/P2-1-querymodel-aggregate-join-python-design.md`
  - `src/foggy/dataset_model/impl/model/__init__.py`
  - `src/foggy/dataset_model/impl/loader/__init__.py`
  - `src/foggy/dataset_model/semantic/service.py`

## Findings

- Java aggregate join is a structured QueryModel feature, not a generic
  compose-query convenience and not an ordinary join variation.
- Python has ordinary explicit QM joins and compose derived/join SQL support,
  but no aggregate relation model, RHS preaggregation lowering, lineage,
  diagnostics, or aggregate-governance source mapping.
- Python should not start by modifying Odoo business models or generated
  registry content. The first useful step is a neutral Java snapshot/export
  contract that can drive Python replay.

## Files Updated

- `docs/v3.8-python-alignment/workitems/P0-72-querymodel-aggregate-join-python-gap-audit.md`
- `docs/v3.8-python-alignment/workitems/P0-72-querymodel-aggregate-join-python-gap-audit-progress.md`
- `docs/v3.8-python-alignment/README.md`
- `docs/v3.8-python-alignment/P0-python-alignment-upgrade-plan.md`

## Test Decision

This is a documentation-only audit. Verification is limited to markdown diff
sanity plus the existing lightweight Java snapshot manifest replay to ensure
the active manifest lane still imports and runs.

## Next Work

- P0-73: define/export Java aggregate-join neutral snapshot contract.
- P0-74: add Python manifest/replay skeleton for aggregate-join fixtures while
  keeping production aggregate-join behavior unimplemented.
- P1/P2: only after snapshots exist, add parser/fail-closed validation and then
  SQL/governance parity.

