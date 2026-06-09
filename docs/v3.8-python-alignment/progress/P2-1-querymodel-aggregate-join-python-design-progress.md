# P2-1 QueryModel Aggregate Join Python Design Progress

Date: 2026-06-09

## Completed

- Added the initial Python aggregate join design note.
- Kept implementation out of the current P0/P1 execution pass.
- Recorded mandatory test lanes for SQL, runtime result parity, governance,
  and runtime pushdown/refusal.

## Follow-Up

Before implementation:

- Compare the design against Java 9.2 aggregate join acceptance evidence.
- Build an engine-neutral fixture with SQLite result evidence.
- Decide whether MySQL/Postgres live DB parity is required in the first
  implementation batch or can remain profile-gated follow-up evidence.
