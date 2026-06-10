# P0-58 Compose SQLite Lane Evaluation

## Requirement

Evaluate whether SQLite compose snapshots should be opened as a dedicated lane
after P0-55 through P0-57 close the PostgreSQL and SQL Server missing success
cells.

## Current Inventory Signal

The compose coverage inventory still reports all SQLite success cells missing:

- `sqlite/base`
- `sqlite/derived`
- `sqlite/union`
- `sqlite/join`

This is different from adding one more CTE-capable dialect case. SQLite would
be a new compose dialect lane and should start with the smallest stable
compiler contract.

## Recommendation

- Open SQLite compose separately, starting with a base-only strict snapshot if
  Java's compose compiler exposes a stable SQLite SQL shape.
- Do not bundle SQLite with PostgreSQL or SQL Server snapshot expansion.
- After base passes, add derived, union, and join one at a time.
- Keep live SQLite execution separate from compiler SQL-shape replay unless a
  later workitem explicitly asks for runtime result parity.

## Acceptance

- SQLite missing cells remain visible in `missingSuccessCells`.
- The next SQLite implementation step is explicitly staged rather than hidden
  inside the current dialect expansion.
- No SQLite behavior is claimed as implemented by this evaluation.
