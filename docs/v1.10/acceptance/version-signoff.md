---
acceptance_scope: version
version: v1.10
target: python-pivot-9.2-followup
doc_role: acceptance-record
doc_purpose: 记录 Python Pivot 9.2 follow-up 的版本级正式验收与签收结论
status: signed-off
decision: accepted-with-risks
signed_off_by: root-controller
signed_off_at: 2026-05-03
reviewed_by: signoff-owner
blocking_items: []
follow_up_required: yes
evidence_count: 20
---

# Version Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / root-controller
- purpose: 记录 Python Pivot v1.10 / Pivot 9.2 follow-up 的版本级正式验收结论、证据摘要和后续边界。

## Background

- Version: v1.10
- Scope: Python Pivot 9.2 follow-up over the v1.9 accepted-with-risks boundary.
- Goal: 关闭 v1.9 延期项中可独立验证的部分，并对仍不具备语义或运行证据的项保持 fail-closed 或 accepted-deferred。

v1.10 不重新定义 public Pivot DSL，不声明 MDX 兼容，也不绕过 queryModel 生命周期。签收重点是：有 oracle 的能力才实现；无 oracle 或语义未签收的能力必须稳定拒绝或延期。

## Acceptance Basis

- `docs/v1.10/P0-Pivot-9.2-Followup-Requirement.md`
- `docs/v1.10/P0-Pivot-9.2-Followup-Implementation-Plan.md`
- `docs/v1.10/P0-Pivot-9.2-Followup-Code-Inventory.md`
- `docs/v1.10/P0-Pivot-9.2-Followup-progress.md`
- `docs/v1.10/README.md`
- `docs/v1.9/acceptance/python-pivot-9.1-release-readiness.md`

## Module Summary

| Module / Phase | Owner | Status | Acceptance Record | Notes |
|---|---|---|---|---|
| P0 planning docs | root-controller | accepted | `docs/v1.10/README.md` | Planning package reviewed before execution. |
| P1 cascade subtotal/grandTotal | python-engine-agent | signed-off | `acceptance/pivot-9.2-cascade-totals-acceptance.md` | Additive totals over surviving cascade domain accepted. |
| P2 SQL Server cascade evidence | python-engine-agent | signed-off | `acceptance/pivot-9.2-sqlserver-cascade-refusal-acceptance.md` | Accepted-refusal; no SQL Server oracle parity claimed. |
| P3 MySQL 5.7 evidence | python-engine-agent | signed-off | `acceptance/pivot-9.2-mysql57-refusal-acceptance.md` | Accepted-refusal; MySQL 5.7 does not impersonate MySQL8. |
| P4 tree + cascade semantic review | root-controller / semantic-reviewer | signed-off | `acceptance/pivot-9.2-tree-cascade-semantic-review.md` | Accepted-deferred; runtime remains `PIVOT_CASCADE_TREE_REJECTED`. |
| P5 outer Pivot cache feasibility | root-controller / performance-owner | signed-off | `acceptance/pivot-9.2-outer-cache-feasibility.md` | Accepted-deferred; no runtime cache added. |
| P6 production telemetry examples | python-engine-agent | signed-off | `acceptance/pivot-9.2-telemetry-docs-acceptance.md` | Docs-only acceptance for production log-query guidance. |

## Checklist

- [x] 所有 scope 内阶段均已有 feature-level acceptance 或明确 accepted-deferred / accepted-refusal 记录。
- [x] root requirement 中的 acceptance criteria 已覆盖。
- [x] 测试记录完整且结果可追溯。
- [x] UI / 体验验证不适用，标记为 `N/A`。
- [x] 无阻断项。
- [x] 未改变 public Pivot JSON DSL。
- [x] 未绕过 queryModel 生命周期、权限治理、systemSlice、deniedColumns 或 SQL sanitizer。
- [x] 未对 unsupported 方言、tree+cascade、outer cache 做不具备证据的 runtime 承诺。

## Evidence

Test:

- P1 targeted cascade totals: `39 passed in 1.59s`.
- P2 SQL Server refusal targeted: `8 passed in 0.48s`.
- P2 cascade regression: `32 passed in 1.38s`.
- P3 MySQL 5.7 refusal targeted: `2 passed in 0.25s`.
- P3 refusal/domain regression: `34 passed in 0.28s`.
- P4 tree+cascade targeted: `19 passed in 0.87s`.
- P4 cascade regression: `35 passed in 1.48s`.
- Latest full regression baseline recorded in progress: `pytest -q` -> `3943 passed in 11.79s`.

Coverage / Quality:

- `coverage/pivot-9.2-cascade-totals-coverage-audit.md`
- `quality/pivot-9.2-cascade-totals-quality.md`
- `coverage/pivot-9.2-sqlserver-cascade-refusal-coverage-audit.md`
- `quality/pivot-9.2-sqlserver-cascade-refusal-quality.md`
- `coverage/pivot-9.2-mysql57-refusal-coverage-audit.md`
- `quality/pivot-9.2-mysql57-refusal-quality.md`
- `coverage/pivot-9.2-tree-cascade-semantic-coverage-audit.md`
- `quality/pivot-9.2-tree-cascade-semantic-quality.md`
- `coverage/pivot-9.2-outer-cache-feasibility-coverage-audit.md`
- `quality/pivot-9.2-outer-cache-feasibility-quality.md`
- `coverage/pivot-9.2-telemetry-docs-coverage-audit.md`
- `quality/pivot-9.2-telemetry-docs-quality.md`

Delivery Artifacts:

- `operations/pivot-9.2-telemetry-log-query-examples.md`
- `docs/v1.10/README.md`
- `docs/v1.10/P0-Pivot-9.2-Followup-progress.md`

Experience:

- N/A. This is backend/query-engine and documentation work; no UI workflow is included.

## Blocking Items

- none

## Risks / Open Items

- SQL Server cascade remains accepted-refusal; no SQL Server oracle parity is claimed.
- MySQL 5.7 cascade and large-domain transport remain accepted-refusal; MySQL8 parity is not generalized to MySQL 5.7.
- `tree + cascade` remains deferred until a signed semantic spec and oracle matrix exist.
- outer Pivot cache remains deferred until production telemetry, permission-aware cache key, and invalidation strategy are signed.
- Future runtime changes for deferred items must repeat quality gate, coverage audit, and acceptance signoff.

## Final Decision

Python Pivot v1.10 / Pivot 9.2 follow-up is signed off as `accepted-with-risks`.

The accepted scope is complete: implemented items have test evidence, refusal paths are stable, deferred items are explicitly documented, and no blocker remains for closing v1.10 follow-up. The remaining risks are intentional future work, not defects in the signed scope.

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: root-controller
- signed_off_at: 2026-05-03
- acceptance_record: docs/v1.10/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: yes
