# timeWindow Current Parity Quality Record

## 文档作用

- doc_type: quality-record
- status: passed
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 v1.11 P2 timeWindow 当前版本证据刷新质量检查和边界。

## Change Surface

No runtime code changes were required for P2.

Documentation updates only:

- `docs/v1.11/acceptance/timewindow-current-parity-acceptance.md`
- `docs/v1.11/coverage/timewindow-current-parity-coverage-audit.md`
- `docs/v1.11/quality/timewindow-current-parity-quality.md`
- v1.11 README / audit / execution plan status updates.

## Quality Check

| Check | Result | Notes |
|---|---|---|
| scope conformance | pass | evidence refresh only; no DSL or runtime expansion |
| test freshness | pass | current main tests re-run after P1 changes |
| dialect evidence | pass | SQLite/MySQL8/PostgreSQL/SQL Server matrix passed |
| fail-closed semantics | pass | `timeWindow + pivot` rejected; unsupported post-calc semantics remain closed |
| documentation alignment | pass | historical v1.5 evidence promoted into v1.11 current signoff records |
| residual ambiguity | pass-with-note | no new Java/Python cross-process golden runner; existing fixture + DB matrix accepted |

## Risks / Follow-ups

| Risk | Impact | Disposition |
|---|---|---|
| No live Java engine golden runner in Python CI | Future Java changes might require manual fixture refresh | accepted; covered by fixture catalog + DB matrix |
| post-calc channel is scalar-only | Users cannot do outer aggregate/window over timeWindow output in one query_model call | deferred to stable relation / compose boundary work |
| SQL Server availability depends on local environment | Current run passed with no skips; CI may still need profile setup | track under later governance/CI work if required |

## Decision

Implementation quality and evidence quality are sufficient for P2 acceptance.
