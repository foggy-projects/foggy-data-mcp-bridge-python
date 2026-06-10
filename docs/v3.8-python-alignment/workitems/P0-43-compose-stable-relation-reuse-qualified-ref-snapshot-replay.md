# P0-43 Compose Stable Relation Reuse Qualified Ref Snapshot Replay

## Requirement

Close the P0-37 residual risk for stable relation reuse with qualified refs.

The replay lane must be able to express a Java plan where the same base
`QueryPlan` instance is reused under two derived branches, and the post-join
query still resolves `left.*` / `right.*` qualified refs after the branches
rename their outputs.

## Scope

- Extend the neutral Java compose snapshot fixture with a small `reuseKey`
  contract for test-only identity reconstruction.
- Add a reused-base derived-join case that projects distinct branch aliases and
  filters/orders through side-qualified refs.
- Replay the same fixture in Python by preserving `reuseKey` identity while
  rebuilding the plan tree.
- Add a focused Python regression that does not depend on a Java export.

## Non-Goals

- Do not add a general user-facing `reuseKey` API.
- Do not reopen P0-37 source-alias boundary signoff.
- Do not change stable relation S7a/S7e/S7f snapshot schemas.

## Acceptance

- Java `JavaComposeSnapshotTest` exports
  `stable-reused-base-qualified-ref-postgres`.
- Python `test_java_compose_snapshot_parity.py` replays the new case.
- Python local join coverage verifies reused base + derived branches +
  side-qualified projection/slice/order.
- Focused Java/Python tests pass.
