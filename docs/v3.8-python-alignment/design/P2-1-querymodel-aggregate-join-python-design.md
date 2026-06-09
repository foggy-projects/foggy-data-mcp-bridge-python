# P2-1 QueryModel Aggregate Join Python Design

Date: 2026-06-09

## Problem

Java 9.2 accepted QueryModel aggregate join, where the right-hand side is
preaggregated before a left join and then exposed through the query model.
Python has no implementation evidence for this feature.

## Proposed Python Shape

- Represent aggregate join as an explicit QueryModel relation contract rather
  than implicit formula expansion.
- Compile RHS as a grouped subquery with fixed slice and selected aggregate
  measures.
- Join the preaggregated RHS to the base/left query by validated group keys.
- Preserve permission/system slice on both sides before runtime filters.
- Allow only AND-only runtime pushdown that can be proven to target one side.
- Fail closed for cross-datasource joins, ambiguous fields, unsupported OR
  pushdown, and hidden/denied columns.

## Required Test Matrix

- AST/API parsing and loader validation.
- SQL generation for SQLite, MySQL, PostgreSQL, and SQL Server fallback shape.
- Runtime result parity on SQLite as the mandatory always-on DB.
- Optional MySQL/Postgres result parity behind profile gates.
- Permission propagation and sanitized governance errors.
- Pushdown/refusal matrix for AND, OR, side-qualified refs, hidden fields, and
  denied columns.

## Non-Scope

- Implementing this in P0.
- Odoo-specific aggregate join models before engine-neutral evidence exists.
- Product UI or AI orchestration changes.

## Acceptance

- Design is accepted before production behavior changes.
- Implementation lands behind focused tests and cross-language fixtures.
- Existing compose/query/pivot parity lanes remain green.
