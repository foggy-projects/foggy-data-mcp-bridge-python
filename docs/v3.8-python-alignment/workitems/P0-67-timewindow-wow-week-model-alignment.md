# P0-67 TimeWindow WoW Week Model Alignment

## Document Purpose

- doc_type: workitem
- intended_for: execution-agent, reviewer
- purpose: Track the engine fixture/model alignment needed to turn the Java timeWindow WoW week snapshot from a documented generation drift into an executable parity case.

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Background

P0-66 refreshed the current Java timeWindow SQL snapshot and intentionally
recorded `wow-week-happy` as a Java-side generation error. The catalog and
`TimeWindowExpander` contract expect WoW to use `salesDate$week` plus
`salesDate$dayOfWeek`, while the Java ecommerce `FactSalesModel` and
`FactSalesQueryModel` did not expose `salesDate$week`.

The underlying `dim_date.week_of_year` physical column already exists. Python's
in-memory demo model already exposes the logical `week` date property, but the
Python FSScript demo fixture also needed the same logical field for loader-path
consistency.

## Scope

- Add the logical `week` property backed by `week_of_year` to Java ecommerce
  `FactSalesModel`.
- Expose `fs.salesDate$week` in Java ecommerce `FactSalesQueryModel`.
- Tighten Java `TimeWindowParitySnapshotTest` to require 9 successful
  timeWindow SQL snapshots and no generation errors.
- Refresh Python `tests/integration/_time_window_parity_snapshot.json` from
  the Java exporter.
- Update Python replay expectations to require 9 Java success cases and zero
  Java generation drift.
- Align Python FSScript ecommerce model/query fixtures with the Java fixture.

## Out of Scope

- Changing timeWindow compiler semantics.
- Full normalized SQL token diff for multi-CTE timeWindow SQL.
- Live DB/result parity beyond existing SQLite execution coverage.
- Odoo generated model refresh or registry bundle changes.

## Acceptance Criteria

- Java `TimeWindowParitySnapshotTest` passes with 9 generated SQL snapshots and
  an empty `generation_errors` list.
- The committed Python Java snapshot contains `wow-week-happy` SQL using
  `salesDate$week`.
- Python golden diff replay validates all 9 Java-success cases through
  `SemanticQueryService` validate mode.
- Existing Python Java catalog replay, SQLite timeWindow execution, manifest,
  FSScript loader, and lint gates remain green.
- Version docs state that the P0-66 `wow-week-happy` generation drift is now
  closed.

## Constraints

- Do not touch Odoo generated models.
- Do not stage unrelated untracked Python `charts/`.
- Preserve P0-66 as historical evidence; record the closure in P0-67 instead
  of rewriting the old work item as if the drift never happened.

## Expected Follow-Up

Next timeWindow work should move to SQLite live result parity for the current
9-case success set, then decide whether pivot+timeWindow refusal needs a
dedicated active snapshot lane.
