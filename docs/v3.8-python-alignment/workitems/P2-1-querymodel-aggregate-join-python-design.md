# P2-1 QueryModel Aggregate Join Python Design Workitem

Date: 2026-06-09

## Goal

Prepare Python aggregate join as a larger P2 engine feature with an explicit
design and test matrix before implementation.

## Scope

- Design doc:
  `docs/v3.8-python-alignment/design/P2-1-querymodel-aggregate-join-python-design.md`
- Java 9.2 aggregate join contract review.
- Python semantic/query/permission impact inventory.

## Non-Scope

- Production implementation in this step.
- Odoo aggregate join models.
- Productized analysis workflow.

## Acceptance

- Design records RHS preaggregation, same-datasource guard, permission
  propagation, runtime pushdown limits, and DB parity requirements.
- Aggregate join remains listed as P2 until implementation work is explicitly
  approved.
