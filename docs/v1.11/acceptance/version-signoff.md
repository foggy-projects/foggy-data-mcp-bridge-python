---
acceptance_scope: version
version: v1.11
target: python-engine-java-parity-audit
doc_role: acceptance-record
doc_purpose: 记录 Python engine v1.11 Java/Python parity audit 的版本级正式验收结论与证据摘要
status: signed-off
decision: accepted-with-risks
signed_off_by: root-controller
signed_off_at: 2026-05-03
reviewed_by: N/A
blocking_items: []
follow_up_required: yes
evidence_count: 12
---

# Version Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / root-controller
- purpose: 记录 v1.11 Python engine Java/Python parity audit 的版本级正式验收结论、证据和保留边界。

## Background

- Version: v1.11.
- Scope: Python engine Java/Python parity audit after Python Pivot v1.10 signoff.
- Goal: 从 Pivot 扩展到全 engine，确认 `query_model`、CALCULATE/formula、timeWindow、pivot、compose/stable relation、governance 的当前对齐状态。

v1.11 不扩展 public DSL，不新增 Pivot runtime feature。验收核心是把“runtime parity / contract mirror / accepted refusal / deferred”分清楚，并用当前测试证据替代历史迁移口径。

## Acceptance Basis

- `docs/v1.11/README.md`
- `docs/v1.11/P0-Java-Python-Engine-Parity-Audit.md`
- `docs/v1.11/P0-Java-Python-Engine-Parity-Execution-Plan.md`
- `docs/v1.11/acceptance/calculate-formula-parity-acceptance.md`
- `docs/v1.11/acceptance/timewindow-current-parity-acceptance.md`
- `docs/v1.11/acceptance/compose-stable-relation-boundary-acceptance.md`
- `docs/v1.11/acceptance/governance-cross-path-acceptance.md`
- Python Pivot v1.10 signoff: `docs/v1.10/acceptance/version-signoff.md`

## Module Summary

| Module | Owner | Status | Acceptance Record | Notes |
|---|---|---|---|---|
| P1 CALCULATE / formula parity | python-engine | signed-off | `docs/v1.11/acceptance/calculate-formula-parity-acceptance.md` | Restricted public subset accepted; default `mysql` profile remains conservative. |
| P2 timeWindow current evidence | python-engine | signed-off | `docs/v1.11/acceptance/timewindow-current-parity-acceptance.md` | SQLite/MySQL8/PostgreSQL/SQL Server current matrix refreshed. |
| P3 compose / stable relation boundary | python-engine | signed-off | `docs/v1.11/acceptance/compose-stable-relation-boundary-acceptance.md` | Compose runtime accepted; stable relation S7e/S7f runtime remains contract mirror only. |
| P4 governance cross-path matrix | python-engine | signed-off | `docs/v1.11/acceptance/governance-cross-path-acceptance.md` | base/timeWindow/pivot/compose/MCP router governance matrix accepted. |
| Pivot v1.10 baseline | python-engine | signed-off | `docs/v1.10/acceptance/version-signoff.md` | No new Pivot runtime scope in v1.11. |

## Checklist

- [x] 所有 v1.11 scope 内模块均已完成 feature-level acceptance。
- [x] P0 audit / execution plan 中的 P1-P4 acceptance criteria 已覆盖。
- [x] 测试记录完整且结果可追溯。
- [x] 体验验证为 `N/A`，本版本是后端/API/engine parity audit。
- [x] 阻断项已清零。
- [x] runtime parity、contract mirror、accepted refusal 和 deferred 已分开标注。

## Evidence

Test:

- P1 targeted: `19 passed in 0.59s`.
- P1 full regression: `3949 passed in 12.22s`.
- P2 targeted: `118 passed in 1.27s`.
- P2 full regression: `3949 passed in 16.51s`.
- P3 compose suite: `1146 passed in 1.54s`.
- P3 MCP compose binding: `10 passed in 0.30s`.
- P3 stable relation snapshots: `70 passed in 0.12s`.
- P3 full regression: `3949 passed in 12.29s`.
- P4 governance target matrix: `215 passed in 0.93s`.
- P4 MCP router + compose authority/security: `120 passed in 0.55s`.
- P4 timeWindow governance focused: `8 passed in 0.34s`.
- P4 full regression: `3952 passed in 13.14s`.

Experience:

- N/A. No UI or user-facing visual workflow changed.

Delivery Artifacts:

- `docs/v1.11/acceptance/*.md`
- `docs/v1.11/coverage/*.md`
- `docs/v1.11/quality/*.md`
- Runtime/test change: `tests/test_dataset_model/test_time_window_sqlite_execution.py`
- Dialect support addition from P1: `src/foggy/dataset/dialects/mysql.py`

## Blocking Items

- none

## Risks / Open Items

| Item | Status | Impact | Follow-Up |
|---|---|---|---|
| Stable relation outer aggregate/window runtime | contract-mirror-only | Python cannot claim full Java runtime parity for S7e/S7f relation wrapping. | Create a separate implementation plan only if product requires runtime parity. |
| Default `mysql` CALCULATE grouped-window behavior | accepted profile note | MySQL 5.7-compatible `mysql` remains fail-closed; MySQL8 requires explicit `MySql8Dialect`. | Keep documented; no public DSL change. |
| Pivot deferred items from v1.10 | accepted deferred | tree+cascade, outer Pivot cache, SQL Server cascade oracle remain outside v1.11. | Track under future version only when requirement is approved. |

## Final Decision

v1.11 is `accepted-with-risks`.

The accepted risks are explicit and non-blocking:

- Stable relation S7e/S7f remains contract mirror rather than Python runtime parity.
- Some dialect-specific behavior remains accepted-refusal or profile-gated.

For the public Python engine contract as of v1.11, the supported runtime paths have current evidence and the unsupported or mirror-only paths are documented fail-closed/deferred. No blocker remains for v1.11 signoff.

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: root-controller
- signed_off_at: 2026-05-03
- acceptance_record: docs/v1.11/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: yes
