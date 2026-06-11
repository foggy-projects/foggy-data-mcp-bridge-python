# P0-68 TimeWindow SQLite Live Result Parity

## Document Purpose

- doc_type: workitem
- intended_for: execution-agent, reviewer
- purpose: Track the Python live-result evidence that executes the current Java timeWindow happy-case catalog against SQLite.

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Background

P0-66 refreshed the current Java timeWindow SQL snapshot and P0-67 closed the
`wow-week-happy` model/catalog drift, leaving the active timeWindow snapshot
lane at 9 Java-success happy cases with no Java generation errors.

Before P0-68, Python replay proved that every Java-success case compiled
through `SemanticQueryService` validate mode and that selected hand-written
SQLite execution scenarios worked. It did not yet execute the complete Java
happy-case catalog against SQLite with result-level checks.

## Scope

- Add a Java-catalog-driven SQLite execution test for all 9 current
  timeWindow happy cases.
- Keep the committed Java catalog immutable and clone `timeWindow.value` only
  inside the SQLite test so relative `now` and `-30D` ranges are deterministic.
- Verify expected Java catalog output columns are present in execute-mode
  response metadata and rows.
- Verify representative result semantics:
  - comparative `prior`, `diff`, and `ratio` arithmetic for YoY, MoM, and WoW;
  - cumulative first-row behavior for MTD and YTD;
  - rolling result materialization and post-calculated `rollingGap`;
  - post-calculated `growthPercent` equals `salesAmount__ratio * 100`.
- Extend the local SQLite seed with a February week-over-week pair without
  changing existing January YoY expectations.

## Out of Scope

- Java live-result snapshot export.
- Full normalized SQL token diff for multi-CTE timeWindow SQL.
- Pivot + timeWindow refusal lane changes.
- Odoo business model or generated model refresh.
- Changing production timeWindow compiler semantics.

## Acceptance Criteria

- `tests/test_dataset_model/test_time_window_sqlite_execution.py` executes all
  Java catalog happy cases in SQLite mode and asserts non-empty results.
- Existing hand-written SQLite timeWindow tests remain green.
- Java SQL snapshot replay and manifest checks remain green.
- The P0 alignment docs identify P0-68 as live SQLite result parity evidence,
  while preserving the remaining full SQL diff and Java live snapshot gaps.

## Constraints

- Do not stage unrelated Python `charts/`.
- Do not touch Java or registry dirty work for this item.
- Keep catalog range overrides local to the execution test; the catalog and
  Java snapshot fixtures remain source evidence, not mutated runtime data.

## Expected Follow-Up

Next timeWindow work should either add a Java live-result snapshot if Java has a
stable embedded result fixture, or move to pivot+timeWindow rejection stability.
Full normalized SQL diff remains a separate normalizer task because current
Java and Python timeWindow SQL use different multi-CTE shapes.
