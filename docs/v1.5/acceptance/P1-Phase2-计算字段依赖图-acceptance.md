---
acceptance_scope: feature
version: v1.5
target: P1-Phase2-计算字段依赖图
doc_role: acceptance-record
doc_purpose: 说明本文件用于功能级正式验收与签收结论记录
status: signed-off
decision: accepted
signed_off_by: execution-agent
signed_off_at: 2026-04-20
reviewed_by: foggy-test-coverage-audit
blocking_items: []
follow_up_required: no
evidence_count: 5
---

# Feature Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / owning-module
- purpose: 记录 v1.5 Phase 2（计算字段依赖图 + 循环检测）的功能级正式验收结论

## Background

- Version: v1.5
- Phase: 2 / 3
- Target: 为 Python 计算字段编译器补齐 Kahn 拓扑排序、传递依赖解析、循环检测
- Owner: `foggy-data-mcp-bridge-python` / `foggy.dataset_model.semantic`
- Goal: 支持 `c = a + b`、`d = c * 2` 这类 calc-to-calc 传递依赖；拒绝 `a = b+1, b = a-1` 循环并给出明确错误；让 slice / orderBy / groupBy / having 也能引用 calc 字段

## Acceptance Basis

- requirement: `docs/v1.5/P1-Phase2-计算字段依赖图-需求.md`
- progress: `docs/v1.5/P1-Phase2-计算字段依赖图-progress.md`
- coverage audit: `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md`
- Java 上游参照：
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/.../engine/expression/CalculatedFieldService.java#sortByDependencies`
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/.../engine/expression/SqlExpContext.java#resolveColumn`

## Checklist

- [x] scope 内功能点已全部交付
  - `src/foggy/dataset_model/semantic/calc_field_sorter.py`（新）
    - `sort_calc_fields_by_dependencies`：Kahn 算法（FIFO + 稳定输入顺序）
    - `extract_calc_refs`：复用 `field_validator._extract_field_dependencies`
    - `build_dependency_map`：调试 / 工具用
    - `CircularCalcFieldError(ValueError)`：含 `.fields` 属性保留循环参与者
  - `SemanticQueryService` 全链路透传 `compiled_calcs: Dict[str, str]`：
    - `_resolve_single_field` 首行查 `compiled_calcs`
    - `_render_expression` / `_resolve_expression_fields` / `_build_calculated_field_sql` 签名扩展
    - `_add_filter`（含 `$or`/`$and`/`$field`/shorthand 分支）扩展
    - GROUP BY / HAVING / ORDER BY 分支各自查 compiled_calcs
  - `query_model` 主流程：calc 段入口调 sort → 初始化 compiled_calcs → 每个 calc 渲染完 base_sql 立即注册（pre-wrap）
- [x] 原始 acceptance criteria 已逐项覆盖
  - 传递依赖（`c = b + a`，`b = a * 2`）→ 正确内联生成 SQL
  - 循环检测（2-cycle / 3-cycle / 混合好/坏）→ `CircularCalcFieldError` + 错误消息含所有参与者
  - 稳定性（零入度按输入顺序；依赖解锁后也按输入顺序）
  - slice/WHERE 引用 calc → `(raw_expr) > ?` 正确内联
  - ORDER BY / GROUP BY 引用 calc
  - HAVING 引用 calc
  - 向后兼容（无 calc / 单 calc / agg / v1.4 `in`）
  - Pre-wrap agg 交互（避免 `SUM(SUM(x))` 非法嵌套）
- [x] 关键测试已通过
  - `tests/test_dataset_model/test_calc_field_sorter.py`：28 passed
  - `tests/test_dataset_model/test_calc_field_dependency_e2e.py`：18 passed
  - 全量回归（Phase 2 末端）：2087 → 2133 passed, 0 failed
  - 全量回归（simplify + Phase 3 末端）：2209 passed, 0 failed
- [x] 体验验证：`N/A` —— 引擎编译层增强，无 UI 交互面
- [x] 文档、配置、依赖项已闭环
  - requirement 和 progress 全部 `[x]`
  - 契约对照表（Kahn 算法 + `SqlExpContext.resolveColumn`）回写 progress 文档
  - 关键设计决策（pre-wrap 注册、引用加括号、稳定性、自引用不算循环）落档

## Evidence

- Requirement:
  - `docs/v1.5/P1-Phase2-计算字段依赖图-需求.md`
- Test:
  - `tests/test_dataset_model/test_calc_field_sorter.py`（28 用例）
  - `tests/test_dataset_model/test_calc_field_dependency_e2e.py`（18 用例）
  - `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md` Coverage Matrix 的 R3.1–R3.9 行
- Experience:
  - `N/A`（见 Checklist）
- Artifact:
  - Python 源码改动：
    - 新文件 `src/foggy/dataset_model/semantic/calc_field_sorter.py`（~130 行）
    - 修改 `src/foggy/dataset_model/semantic/service.py`（compiled_calcs 全链路透传 + sorter 集成）
  - 端到端 SQL 样例：progress "端到端证据样例"章节

## Failed Items

- none

## Risks / Open Items

- **Pre-wrap 语义的 agg 边界**：当 calc A 有 `agg=SUM` 且 calc B 引用 A 时，B 内联 A 的 pre-wrap 表达式（不带 SUM）。Java 侧未在测试中充分暴露此场景，两边一致性仅对"无 agg 的 calc 链"严格保证。非阻断，已在 progress 文档"Python 侧刻意偏差"章节明示。
- **错误消息字符**：Java 用中文"检测到计算字段循环引用..."，Python 用英文"Circular reference detected..."。用户可见层一致传达循环字段集合，但措辞不同。属于本地化刻意偏差，非缺陷。

## Final Decision

- 结论：**accepted**
- 全部 5 项开发进度 + 3 项测试进度完成；46 个新增测试覆盖 sorter / e2e / 回归三层
- Kahn 算法对齐 Java 设计意图；错误消息语义一致（英文本地化）
- 传递依赖、循环检测、slice/groupBy/orderBy/having 引用 calc 均落地
- 无阻断项；风险项均为语义上的刻意偏差，已落档

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase2-计算字段依赖图-acceptance.md
- blocking_items: none
- follow_up_required: no
