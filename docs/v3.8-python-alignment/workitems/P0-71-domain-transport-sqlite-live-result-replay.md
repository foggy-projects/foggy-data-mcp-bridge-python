# P0-71 Domain Transport SQLite Live Result Replay

## Document Purpose

- doc_type: workitem
- intended_for: execution-agent, reviewer
- purpose: Track Java-fixture-driven SQLite live-result replay for Python domain transport SQL assembly.

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Background

P0-70 made the Java-exported domain transport boundary cases explicit in the
Python replay lane. The remaining evidence gap was that the Java fixture cases
proved renderer SQL shape and refusal behavior, while live-result checks still
mostly used Python-local oracle scenarios.

P0-71 keeps the scope narrow: use existing Java snapshot domain plans as the
input carrier, assemble Python SQLite domain transport SQL, execute that SQL
against an in-memory SQLite seed, and compare the result to independent oracle
SQL.

## Scope

- Reuse `tests/fixtures/java_pivot_domain_snapshot_parity.json`.
- Execute the Java-exported SQLite two-field NULL-safe domain case against
  SQLite.
- Execute the Java-exported SQLite 501-domain transport case against SQLite.
- Compare assembled SQL results with independent oracle SQL.
- Keep production renderer/compiler behavior unchanged.

## Out of Scope

- Java fixture export changes.
- External MySQL/PostgreSQL live DB expansion.
- MySQL 5.7 domain transport implementation.
- Direct axis-domain public API expansion.
- Odoo business models, registry pull, or generated model refresh.

## Acceptance Criteria

- The `domain-sqlite-two-field-null-safe` Java snapshot plan executes through
  Python assembled SQL and matches oracle rows, including `NULL` product
  matching.
- The `domain-sqlite-large-501-transport` Java snapshot plan executes through
  Python assembled SQL and matches oracle rows while excluding out-of-domain
  rows.
- The existing Java snapshot replay and renderer/oracle tests remain green.
- Focused pytest and ruff checks pass.

## Expected Follow-Up

The next domain transport step should require new fixture evidence before
changing behavior. Good candidates are direct axis-domain API snapshots or
live-result snapshots for supported external dialects. MySQL 5.7 remains a
documented Java-only gap until product confirms Python should implement the
derived-table strategy.
