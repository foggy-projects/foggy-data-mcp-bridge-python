# P3 Compose / Stable Relation Boundary Quality Record

## 文档作用

- doc_type: quality-record
- status: accepted-with-runtime-boundary
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 P3 compose/stable relation 边界验收的实现质量判断、风险和后续约束。

## Implementation Shape

P3 未修改运行时代码。质量判断基于现有代码结构和当前测试证据：

- Compose runtime 通过 `ComposeRuntimeBundle` / ContextVar 持有 host infrastructure，脚本不可直接访问 `semantic_service`。
- `execute_plan()` 将 compile 与 `execute_sql()` 分离，并保留 structured compile errors。
- `compose_script` MCP path 通过 authority envelope 将 Odoo 权限绑定接入 compose 权限解析。
- Stable relation models 使用 frozen dataclasses 和 closed string constants，与 Java snapshot 做合同级对齐。

## Quality Checks

| Check | Result |
|---|---|
| Runtime code changed | no |
| Public DSL changed | no |
| Compose tests | pass |
| MCP compose tool binding tests | pass |
| Stable relation Java snapshot tests | pass |
| Runtime-vs-contract boundary documented | yes |

## Design Strengths

- Compose runtime does not expose host infrastructure to the script evaluator surface.
- Route model is derived from left-preorder base model traversal, keeping multi-model SQL execution deterministic.
- Error routing distinguishes compile/authority errors from execute-phase driver failures.
- Stable relation support is explicit about capability flags and fail-closed wrap strategies.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Stakeholders may read S7e/S7f snapshot tests as runtime parity | medium | P3 acceptance explicitly labels them `contract-mirror-only`. |
| Future stable relation runtime work could bypass governance if implemented as raw SQL wrapping | high | Require P4 governance matrix and a separate runtime plan before implementation. |
| SQL Server / MySQL 5.7 evidence is not live runtime evidence | medium | Keep as accepted contract/refusal boundary until oracle coverage exists. |

## Decision

Implementation quality is acceptable for the current P3 boundary.

No runtime expansion should be performed under P3. Any full stable relation runtime parity work must be planned as a separate implementation phase with live dialect oracle tests.
