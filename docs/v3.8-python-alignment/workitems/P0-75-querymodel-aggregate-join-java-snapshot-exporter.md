---
doc_purpose: Track the Java QueryModel aggregate join neutral snapshot exporter for Python parity replay.
version: v3.8-python-alignment
priority: P0-75
status: implemented
owner: java/python-parity
---

# P0-75 QueryModel Aggregate Join Java Snapshot Exporter

Date: 2026-06-11

## Background

P0-72 froze the Python gap audit for Java 9.2 QueryModel aggregate join.
P0-73 defined the neutral snapshot contract, P0-74 added the Python manifest
and contract replay skeleton, and P1-2 added Python fail-closed handling for
recognized aggregate join declarations. P0-75 creates the Java-side exporter so
Python can promote a real neutral snapshot fixture next.

## Delivered

- Java exporter:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/parity/JavaQueryModelAggregateJoinSnapshotTest.java`.
- Target output:
  `foggy-dataset-model/target/parity/_querymodel_aggregate_join_snapshot.json`.
- Python manifest now records the exporter path, output path, and
  `javaExporterStatus: ready`.
- The exporter writes the 10 required contract cases:
  `aggregate-join-left-measure-not-multiplied`,
  `aggregate-join-sql-shape-sqlite`,
  `aggregate-join-missing-right-key-groupby-refusal`,
  `aggregate-join-fixed-rhs-filter`,
  `aggregate-join-runtime-extdata-filter`,
  `aggregate-join-runtime-extdata-missing-refusal`,
  `aggregate-join-and-pushdown-diagnostics`,
  `aggregate-join-or-outer-only-diagnostics`,
  `aggregate-join-denied-source-column-refusal`, and
  `aggregate-join-metadata-lineage`.

## Acceptance

- Java focused exporter command:
  `mvn -pl foggy-dataset-model -P!multi-db -Dtest=JavaQueryModelAggregateJoinSnapshotTest test`.
- The generated envelope was inspected with `schemaVersion = 1`,
  `feature = queryModelAggregateJoin`,
  `source = JavaQueryModelAggregateJoinSnapshotTest`, and 10 cases.
- Python production aggregate join remains unimplemented. The P1-2
  fail-closed guard is still the runtime boundary until a dedicated aggregate
  relation carrier and SQL lowering are implemented.

## Boundary

- No Odoo business model work is included.
- No Python aggregate join SQL lowering is included.
- The generated Java `target/parity` snapshot is not committed in this step;
  P0-76 should promote it into a Python fixture and add replay assertions.

## Progress

- 2026-06-11: Implemented the Java exporter, verified the SQLite-focused lane,
  and updated the Python manifest/docs so P0-76 has a concrete snapshot source.
