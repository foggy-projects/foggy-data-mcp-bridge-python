---
doc_purpose: Record the Java v3 aggregate relation snapshot export used by Python alignment.
version: v3.8-python-alignment
priority: P0-92
status: complete
owner: python-engine
---

# P0-92 QueryModel Aggregate v3 Java Fixture Export

Date: 2026-06-13

## Scope

P0-92 exports the next Java aggregate relation parity snapshot for the Python
alignment line. It does not commit Java changes and does not touch registry or
Odoo business models.

The exported contract is `querymodel-aggregate-join-3`, expanding the previous
19-case v2 snapshot to 29 cases.

## Exported v3 Slices

- aggregate output `orderBy`
- QueryFacade-style `returnTotal`
- null-check outer-only predicates
- public `debug.extra.aggregateRelationDiagnostics`
- composite-key pushdown fixture
- structured accessBuilder pushdown fixture
- unsafe runtime filter refusal
- left dimension key fixture
- RHS dimension fixed filter fixture

## Worktree Guard

- Java, Python, and registry status were checked before the P0-92 through P0-95
  run.
- Existing uncommitted Java/Python changes were left in place.
- No commit, push, reset, or cleanup was performed.

## Verification

- Java exporter command:
  `mvn -pl foggy-dataset-model -P!multi-db -Dtest=JavaQueryModelAggregateJoinSnapshotTest -Dfoggy.parity.snapshot=true test`
- Result: `BUILD SUCCESS`.
- Generated snapshot:
  `foggy-dataset-model/target/parity/_querymodel_aggregate_join_snapshot.json`.
- Snapshot summary: `contractVersion=querymodel-aggregate-join-3`,
  `dialect=sqlite`, `caseCount=29`.

The `-P!multi-db` profile gate is required locally because the default
multi-DB profile attempts a Postgres fixture at `localhost:15432`.
