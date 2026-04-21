---
acceptance_scope: feature
version: v1.5
target: P1-Phase1-Dialect函数翻译与arity校验
doc_role: acceptance-record
doc_purpose: 说明本文件用于功能级正式验收与签收结论记录
status: signed-off
decision: accepted
signed_off_by: execution-agent
signed_off_at: 2026-04-20
reviewed_by: foggy-test-coverage-audit
blocking_items: []
follow_up_required: no
evidence_count: 6
---

# Feature Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / owning-module
- purpose: 记录 v1.5 Phase 1（Dialect 函数翻译 + arity 校验）的功能级正式验收结论

## Background

- Version: v1.5
- Phase: 1 / 3
- Target: 为 Python 计算字段编译器补齐跨方言函数翻译 + 编译期 arity 校验
- Owner: `foggy-data-mcp-bridge-python` / `foggy.dataset_model.semantic` + `foggy.dataset.dialects`
- Goal: 让 QM/DSL 计算字段里的 `DATE_FORMAT(d, '%Y-%m')` 等表达式在不同方言（MySQL/Postgres/SQLite/SQL Server）下自动生成正确 SQL；同时在编译期拒绝参数数错误的函数调用，而不是推到数据库运行期才爆

## Acceptance Basis

- requirement: `docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-需求.md`
- progress: `docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-progress.md`
- coverage audit: `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md`
- Java 上游参照：
  - `foggy-data-mcp-bridge/foggy-dataset/src/main/java/com/foggyframework/dataset/db/dialect/FDialect.java#buildFunctionCall`
  - `foggy-data-mcp-bridge/foggy-dataset/src/main/java/com/foggyframework/dataset/db/dialect/PostgresDialect.java`
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/test/java/.../dialect/DialectFunctionTranslationTest.java`

## Checklist

- [x] scope 内功能点已全部交付
  - `FDialect.build_function_call(func_name, args) -> Optional[str]` 基类 hook
  - `translate_function` 级联 `build_function_call` → `_get_function_mappings`
  - Postgres：`EXTRACT` 日期族 + `DATE_FORMAT → TO_CHAR` + MySQL→Postgres 格式串翻译
  - SQLite：`strftime` 日期族 + `DATE_FORMAT` 参数反转
  - SQL Server：`DATEPART` + `FORMAT` + MySQL→SQL Server 格式串翻译 + `STDEV`/`VARP`/`CEILING`/`LEN`/`SUBSTRING` 重命名
  - MySQL：`TRUNC → TRUNCATE`（`POW` 保持 native 原生，与 Java 一致）
  - `SemanticQueryService._FUNCTION_ARITY` 65+ 项 arity 表 + `_validate_function_arity` + `_emit_function_call`（集成 dialect 路由）
  - simplify 复盘后：`_FUNCTION_MAPPINGS` 类级常量化、`_ALLOWED_FUNCTIONS` 派生自 `_FUNCTION_ARITY`、`_translate_mysql_date_format` 抽到 base、`_emit_function_call` 去除重复调用
- [x] 原始 acceptance criteria 已逐项覆盖
  - 4 方言 × `build_function_call` 行为：15+ 对照用例全部一致 Java `DialectFunctionTranslationTest`
  - arity 校验：`_ALLOWED_FUNCTIONS` 全函数（除 CAST / CONVERT / EXTRACT 显式排除项）覆盖 20+ 正面 + 10+ 负面
  - 端到端：`status in ('a','b')` + `DATE_FORMAT(d, '%Y-%m')` 在 Postgres 方言下渲染为 `TO_CHAR(...)`
  - 回归：`SemanticQueryService(dialect=None)` 路径保持 pre-v1.5 行为
- [x] 关键测试已通过
  - `tests/test_dataset_model/test_dialect_function_translation.py`：83 passed
  - `tests/test_dataset_model/test_function_arity_validation.py`：99 passed
  - 全量回归（Phase 1 末端）：1905 → 2087 passed, 0 failed
  - 全量回归（simplify + Phase 2/3 末端）：2209 passed, 0 failed
- [x] 体验验证：`N/A` —— 底层引擎能力增强，无 UI 交互面
- [x] 文档、配置、依赖项已闭环
  - requirement 和 progress 进度标记全部 `[x]`
  - 契约对照表（4 方言 × 8 典型函数）回写 progress 文档
  - simplify 修复（E1/Q3/R3/E2/Q2）已反映到最终代码

## Evidence

- Requirement:
  - `docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-需求.md`
- Test:
  - `tests/test_dataset_model/test_dialect_function_translation.py`（83 用例）
  - `tests/test_dataset_model/test_function_arity_validation.py`（99 用例）
  - `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md` Coverage Matrix 的 R2.1–R2.9 行
- Experience:
  - `N/A`（见 Checklist）
- Artifact:
  - Python 源码改动：
    - `src/foggy/dataset/dialects/base.py`（+53 行）
    - `src/foggy/dataset/dialects/postgres.py`（+80 行）
    - `src/foggy/dataset/dialects/sqlite.py`（+32 行）
    - `src/foggy/dataset/dialects/sqlserver.py`（+85 行）
    - `src/foggy/dataset/dialects/mysql.py`（+13 行）
    - `src/foggy/dataset_model/semantic/service.py`（新增 `_FUNCTION_ARITY` / `_KEYWORD_DELIMITED_FUNCTIONS` / `_validate_function_arity` / `_emit_function_call` / `_ALLOWED_FUNCTIONS` 派生）
  - 契约对照表：progress 文档"与 Java `FDialect.buildFunctionCall` 的对照表"章节

## Failed Items

- none

## Risks / Open Items

- **G1（跨层风险）**：无真实数据库执行链路测试；所有断言针对生成的 SQL 字符串。缓解：方言翻译直接镜像 Java 已在生产跑过的 `buildFunctionCall`，风险低；`tests/test_mcp/` + 既有 docker 化 MySQL 测试兜底。非阻断。
- **G2（跨仓风险）**：无 Java ↔ Python 跨语言自动化对照测试。缓解：首次对齐时密度足够，契约对照表落盘 progress。非阻断。

## Final Decision

- 结论：**accepted**
- 全部 7 项开发进度和 3 项测试进度完成；182 个新增测试 + 简化后的代码结构均通过 2209 全量回归
- 跨方言函数翻译、arity 校验、dialect 集成链路均达成 Java 对齐
- 无阻断项；Gap 均为基础设施级长期跟进项，不阻塞本次验收

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase1-Dialect函数翻译与arity校验-acceptance.md
- blocking_items: none
- follow_up_required: no
