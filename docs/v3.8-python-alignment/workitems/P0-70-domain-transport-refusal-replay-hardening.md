# P0-70 Domain Transport Refusal Replay Hardening

## Document Purpose

- doc_type: workitem
- intended_for: execution-agent, reviewer
- purpose: Track explicit Python replay evidence for Java-exported domain transport boundary and refusal cases.

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Background

P0-7 and P0-15 activated the Java Pivot/domain transport neutral snapshot lane.
The fixture already contains important boundary cases for large SQLite domain
transport, Python's stricter SQLite bind guard, empty-column refusal, and the
Java-only MySQL 5.7 derived-table transport gap.

Before P0-70, these cases were covered by the broad all-case replay loop, but
they were not named as an explicit stability set. That made accidental fixture
removal or failure triage harder than necessary.

## Scope

- Keep Java and registry worktrees untouched.
- Keep production domain transport renderer behavior unchanged.
- Add explicit fixture-presence checks for the current boundary cases.
- Add parameterized replay for those cases so pytest output names the failing
  Java fixture id directly.
- Preserve the documented parity gaps instead of trying to implement MySQL 5.7
  transport or relax Python SQLite bind limits in this phase.

## Boundary Cases

| Case | Expected Python behavior |
| --- | --- |
| `domain-sqlite-large-501-transport` | Render SQLite CTE transport and preserve params/join markers. |
| `domain-sqlite-python-bind-limit-gap` | Fail closed with `PIVOT_DOMAIN_TRANSPORT_REFUSED` and SQLite `1000 > 999` marker. |
| `domain-empty-columns-refused` | Fail closed with `PIVOT_DOMAIN_TRANSPORT_REFUSED` and `empty columns`. |
| `domain-mysql57-derived-table-java-only-gap` | Fail closed for `mysql5.7`, documenting Java's derived-table support as a gap. |

## Out of Scope

- MySQL 5.7 domain transport implementation.
- Direct axis-domain public API expansion.
- Live DB result parity for domain transport.
- Odoo business models, registry pull, or generated model refresh.
- Java fixture export changes.

## Acceptance Criteria

- The Java Pivot/domain snapshot replay has an explicit guard that all four
  boundary case ids are present.
- Each boundary case is replayed through a named parameterized pytest case.
- Existing all-case Java snapshot replay remains active.
- Focused domain transport pytest and ruff checks pass.

## Expected Follow-Up

Next domain transport work should require new Java snapshot evidence before
changing production behavior. Good candidates are direct axis-domain API
fixtures, live DB result parity for current SQLite/Postgres/MySQL8 support, or
an explicit product decision on whether Python should implement Java's MySQL
5.7 derived-table transport.
