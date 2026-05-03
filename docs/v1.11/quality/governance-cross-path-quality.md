# P4 Governance Cross-Path Quality Record

## 文档作用

- doc_type: quality-record
- status: accepted
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 P4 governance 横向矩阵的实现质量判断、修改范围和风险。

## Changes

Runtime code changed: no.

Test code changed:

- `tests/test_dataset_model/test_time_window_sqlite_execution.py`

新增 3 个 timeWindow governance tests：

- `systemSlice` applied to the base CTE.
- `deniedColumns` blocks target metric access.
- `fieldAccess.masking` applies after timeWindow execution.

Docs changed:

- P4 acceptance / coverage / quality records.
- v1.11 README / audit / execution plan status updates.

## Quality Checks

| Check | Result |
|---|---|
| Public DSL changed | no |
| Runtime governance code changed | no |
| New tests are focused | yes |
| Existing governance tests reused | yes |
| Cross-path matrix documented | yes |
| Stable relation runtime boundary preserved | yes |

## Implementation Notes

- The `SemanticQueryService.query_model()` order remains: pivot lowering when needed, governance validation/merge, field validation, SQL build, execution, optional pivot memory shaping, response filtering/masking.
- P4 did not change this order. The new timeWindow tests prove current ordering is effective for timeWindow too.
- Compose authority continues to route host-controlled permissions through authority binding; script text cannot inject `systemSlice`, `deniedColumns`, or `fieldAccess`.

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Future runtime stable relation work could bypass query_model governance | high | P3/P4 docs require a separate runtime plan and oracle evidence. |
| New query features may forget response masking | medium | P4 matrix should be reused as a regression checklist. |
| `systemSlice` bypass semantics could be misunderstood as a leak | medium | P4 acceptance explicitly states it bypasses user-visible validation by design but must merge into SQL filters. |

## Decision

P4 implementation quality is acceptable.

The repository can proceed to v1.11 version signoff.
