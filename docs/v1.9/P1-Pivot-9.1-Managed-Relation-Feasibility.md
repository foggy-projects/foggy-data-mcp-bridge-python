# Python Pivot 9.1 Managed Relation Lifecycle Feasibility

## 文档作用

- doc_type: feasibility-record
- intended_for: python-engine-agent / reviewer / signoff-owner
- purpose: 回答 Python 是否具备等价 Java `prepareManagedRelation/executeManagedRelation` 的 lifecycle 能力，并明确 P3 Stage 5A / P4 C2 的解锁条件。
- created_at: 2026-05-03
- java_reference_commit: `10e863e9`

---

## Conclusion

- **Status: conditional-pass**
- **Can unlock P3 Stage 5A: yes, conditionally** — 现有 lifecycle 具备 Stage 5A 大域传输需要的基础能力（governance chain、params、dialect、logging/sanitizer 均已覆盖），但 Python 缺少等价 Java `DomainRelationRenderer` 的 SQL 包装原语，且 Python preAgg 与 Pivot 之间的 interaction 路径尚未有 oracle 证据。解锁条件：实现 Python-native `DomainRelationRenderer`（CTE/subquery 包装）并通过 SQLite/MySQL8/Postgres oracle parity 测试。
- **Can unlock P4 C2 staged SQL: no, remains blocked** — P4 依赖 P3 Stage 5A 的三库 oracle parity 通过。P2 只能证明 lifecycle 具备继续设计的可能性，不能直接解锁 C2 staged SQL。
- **Reason:** Python `query_model` lifecycle 已经保留了所有关键的治理入口（`fieldAccess`/`systemSlice`/`deniedColumns`、params order、dialect routing、SQL sanitizer/logging），且 `_build_query` 返回的 `QueryBuildResult` 包含完整的 SQL string 和 params list，具备作为 base relation 包装为 subquery/CTE 的原材料。差距在于：Python 没有 SQL AST 层，无法"注入"额外 CTE 前缀或修改 FROM 子句，需要通过 SQL string 拼接或 `SqlQueryBuilder` 扩展实现，且必须保证 params list 顺序正确。这是工程差距，不是架构性障碍。

---

## Java Reference Requirement

Java 9.1 Stage 5A / C2 需要的生命周期能力（从 `10e863e9` 读取）：

### Stage 5A (B2 - Large-Domain Transport)

1. **queryModel lifecycle preservation**: 通过 `SemanticQueryServiceV3Impl` 发起辅助查询，保留 `preAgg + systemSlice` 的 Base Relation。
2. **Stable SQL output**: `JdbcModelQueryEngine` 返回带稳定输出别名和 params list 的 JDBC query，可以作为子查询被包装。
3. **DomainRelationRenderer**: 接收 `DomainTransportPlan`（surviving domain tuples + dialect hint），生成 CTE 或 Derived Table SQL fragment + params。
4. **JOIN predicate injection**: 将 `IS NOT DISTINCT FROM` / `<=>` 谓词注入 base relation 的 WHERE 或 FROM 子句。
5. **Params order**: CTE 策略时 domain params 前置，Derived Table 策略时按 AST 注入顺序合并。
6. **Fail-closed**: `domain > 500` 时若方言不支持，必须抛 `NonAdditiveRollupDomainTooLargeException`，不允许内存 fallback。
7. **Internal carrier**: `DomainTransportPlan` 通过 `SemanticRequestContext.extData` 传递，不暴露公开 DSL。

### Stage 5B C2 (Cascade Generate)

1. 上述 Stage 5A 所有能力。
2. **Staged SQL**: 生成 `_row_domain_1`, `_row_ranked_1`, `_filtered_1` 等多阶段 CTE，parent domain 过滤在 child aggregation 之前执行。
3. **NULL bucket tie-breaking**: ORDER BY 中 NULL bucket 优先，dimension prefix key ASC。
4. **Additive subtotal/grandTotal**: 在 surviving domain 上聚合，不涉及跌出 TopN 的成员。
5. **No-memory-fallback guard**: cascade request 不得进入当前 in-memory pivot processor。

---

## Python Current Lifecycle Inventory

### 主查询路径

| 入口 | 文件 | 描述 |
|---|---|---|
| `SemanticQueryService.query_model()` | `service.py:572` | 同步 Pivot 查询入口。先调用 `validate_and_translate_pivot()`，再走 governance → build → execute → memory shaping。 |
| `SemanticQueryService.query_model_async()` | `service.py:3082` | 异步等价版本，FastAPI/MCP 路径。 |
| `validate_and_translate_pivot()` | `pivot/executor.py` | Pivot 请求验证 + 翻译为标准 SemanticQueryRequest，包含 P1 cascade detector。 |
| `_apply_query_governance()` | `service.py:413` | 验证 `fieldAccess.visible/denied_columns`，合并 `system_slice` 到 `slice`。 |
| `validate_query_fields()` | `field_validator.py` | 模型字段合法性校验。 |
| `_build_query()` | `service.py:790` | 构建 `QueryBuildResult`（sql: str, params: List, columns: List）。内置 JOIN graph、GROUP BY、WHERE 子句构建。 |
| `_execute_query()` / `_execute_query_async()` | `service.py:2883/2913` | 将 `build_result.sql` 和 `build_result.params` 传递给 executor 执行。 |
| `_sanitize_response_error()` | `service.py:476` | 清洗物理列名，防止 error channel 泄露 governance boundary。 |

### Governance / Permission 相关

| 能力 | 实现位置 | 状态 |
|---|---|---|
| `fieldAccess.visible` whitelist | `service.py:432-444` + `field_validator.py` | 完整实现，执行前强制校验。 |
| `systemSlice` 合并 | `service.py:446-448` | 合并进 `slice`，在 SQL WHERE 子句中渲染。 |
| `deniedColumns` 转换 | `service.py:427-430` + `physical_column_mapping.py` | 物理列名 → QM 字段名映射，执行前黑名单验证。 |
| 结果列过滤 (`filter_response_columns`) | `service.py:666-668` | 执行后 QM 字段级别列过滤。 |
| 结果列 masking (`apply_masking`) | `service.py:670-672` | 执行后 masking 应用。 |

### Dialect / SQL 生成相关

| 能力 | 实现位置 | 状态 |
|---|---|---|
| Dialect 自动推断 | `service.py:186-203` (`_infer_dialect_from_executor`) | SQLite/MySQL/PostgreSQL 自动映射。 |
| SQL identifier quoting | `service.py:175` (`_qi`) + dialect 实现 | 正常工作。 |
| 函数翻译 (`translate_function`) | `service.py:2286` | 通过 dialect 路由。 |
| Params list 顺序 | `_build_query` 内联构建 | `QueryBuildResult.params` 是 `List[Any]`，按构建顺序追加，与 SQL 占位符顺序一一对应。 |

### PreAgg

| 能力 | 实现位置 | 状态 |
|---|---|---|
| `PreAggregationInterceptor` | `engine/preagg/interceptor.py` | 存在但**未集成到 `_build_query` 路径**。当前 preAgg 是独立的 `try_rewrite`，不在 Pivot translate 后的主路径中被调用。 |
| 与 Pivot 的交互 | — | **未覆盖**。当前 Pivot 查询经 `validate_and_translate_pivot` 翻译为普通 SemanticQueryRequest 后，preAgg interceptor 未在该路径中被触发。 |

### SQL Logging / Error Sanitizer

| 能力 | 实现位置 | 状态 |
|---|---|---|
| 执行错误 sanitizer | `error_sanitizer.py` + `service.py:476-485` | 完整实现。物理列别名（`t.col`, `j1.col`）被替换为 QM 字段名，HINT 被清洗。 |
| SQL logging | `service.py:610, 640` (`logger.exception`) | 基本 exception logging 存在；无 structured SQL audit log。 |
| Physical column 不泄露 | `_sanitize_error` + `physical_column_mapping` | 已验证（BUG-007 v1.3 修复）。 |

---

## Capability Mapping

| Required Capability | Python Evidence | Status | Risk |
|---|---|---|---|
| 等价 `prepareManagedRelation` 入口 | `_build_query()` 返回 `QueryBuildResult(sql, params, columns)`；整个 lifecycle 在 `query_model()` 内封闭 | **partial** | Python 无 `getManagedRelation()` 独立 API，但 SQL + params 可提取为 base relation 原材料。 |
| 等价 `executeManagedRelation` 入口 | `_execute_query_async(build_result, executor)` 接受任意 sql+params 执行 | **pass** | 可以把修改后的 sql+params 直接交给该函数执行，接口已解耦。 |
| Stable output aliases | `build_result.columns` 包含 `{name, fieldName}` 映射；aliases 由 `SqlQueryBuilder` 稳定生成 | **pass** | 无法保证别名在 SQL 字符串中与 Java JDBC alias 一致，但 QM 字段名稳定。 |
| Params order | `build_result.params: List[Any]`，按 SQL 构建顺序追加 | **pass** | 在修改 sql 时追加 domain params 必须手动维护顺序——工程约束，不是架构缺口。 |
| Datasource / Dialect | `_infer_dialect_from_executor` 自动推断，dialect 在构建阶段传入 | **pass** | 三库（SQLite/MySQL8/Postgres）dialect 均已实现并测试。 |
| `fieldAccess` / `systemSlice` / `deniedColumns` | `_apply_query_governance()` 在 `validate_and_translate_pivot()` 之后立即执行，贯穿 build 和 execute 阶段 | **pass** | Pivot 翻译前后 governance chain 不会断裂。 |
| CTE / Subquery wrapping | **缺失**：Python 无 AST SQL 层，不能在已生成 sql string 中注入前缀 CTE 或修改 FROM 子句 | **missing** | 需要实现 `PythonDomainRelationRenderer`，通过 string template 或 `SqlQueryBuilder` 扩展包装 base relation 为 `(SELECT ... ) _base`，并前置 CTE 块。需要验证不会生成 `FROM (WITH ...)` 非法语法。 |
| PreAgg rewrite | `PreAggregationInterceptor` 存在但**未集成到 Pivot 路径** | **partial** | Stage 5A/C2 辅助查询必须先建立 preAgg + Pivot 的正确交互路径，否则 preAgg 会绕过 systemSlice 等治理。当前路径安全（preAgg 未触发），但解锁 P3 之前必须明确 preAgg 是否参与 Pivot 辅助查询，以及参与时的 interaction 顺序。 |
| SQL logging / sanitizer | `sanitize_engine_error` + `_sanitize_response_error` | **pass** | 执行错误不泄露物理列。但无结构化 SQL audit log，Stage 5A/C2 需要补充 "domain transport injection" 的 log marker。 |
| 三库 oracle 测试 | SQLite/MySQL8/Postgres 均已有 S3 测试基础设施（`test_pivot_v9_grid_real_db_matrix.py`） | **pass** | P3/P4 需要在现有框架上新增 domain transport 和 cascade oracle tests。 |
| NULL-safe tuple matching | **缺失** | **missing** | Python 无 IS NOT DISTINCT FROM / <=> 谓词构建能力，需要在方言层添加。 |
| Fail-closed for oversized domain | P1 cascade detector 拒绝所有 cascade；P3 需要实现 threshold guard（domain > 500）+ renderer refusal | **partial** | P1 保证了当前路径不会误执行 cascade，但 P3 需要实现正向 domain transport 才能解锁。 |

---

## Probe / Test Evidence

### 运行的测试命令

```powershell
pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/test_dataset_model/test_pivot_v9_grid.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py -q
```

**结果：36 passed**

```powershell
pytest -q
```

**结果：3859 passed in 8.98s（0 failed）**

### 未运行的外部 DB 测试

`tests/integration/test_pivot_v9_flat_real_db_matrix.py` 和 `tests/integration/test_pivot_v9_grid_real_db_matrix.py` 在本次 P2 分析中未重新运行，原因：P2 为纯分析阶段，无代码改动，这些测试在 S3 signoff 时已经通过。

### Code-level 验证（非 probe test，code review）

通过阅读 `service.py:572-693`、`service.py:2883-2958`、`preagg/interceptor.py`、`error_sanitizer.py`，完成了以下关键路径验证：

1. **params 顺序**: `build_result.params` 在 `_build_query` 内按 SQL 构建顺序 append，`executor.execute(sql, params)` 直接传入。结论：顺序已受控，Stage 5A 需手动维护 domain params 前置规则。

2. **governance 不会被绕过**: `validate_and_translate_pivot()` 先执行，然后才是 `_apply_query_governance()`，最后 `_build_query()` 和 `_execute_query()`。没有路径可以跳过 governance 直接执行。

3. **preAgg 当前未参与 Pivot 路径**: `PreAggregationInterceptor.try_rewrite()` 未在 `query_model()` 的 Pivot 分支中被调用，当前 Pivot 查询安全（不会被 preAgg 重写）。但 Stage 5A 辅助查询必须明确这条路径。

4. **error sanitizer 对 domain transport SQL 的适用性**: `_sanitize_response_error` 在所有执行路径末尾被调用，包括 cascade 辅助查询。domain transport 生成的物理别名（如 `_base`, `_pivot_domain_transport`）不在当前 `physical_column_mapping` 映射中，不会被意外替换。

---

## Blockers

### P3 Stage 5A 解锁条件

1. **[必须] `PythonDomainRelationRenderer` 实现**: 能够接收 surviving domain tuple list，生成方言对应的 CTE（PostgreSQL/MySQL8）或 Derived Table（MySQL5.7）SQL fragment，并正确前置/注入 params list，不产生 `FROM (WITH ...)` 非法语法。
2. **[必须] NULL-safe tuple matching**: 在 Python dialect 层实现 `IS NOT DISTINCT FROM`（Postgres/SQLite）和 `<=>`（MySQL8）谓词生成。
3. **[必须] SQLite/MySQL8/Postgres oracle parity tests**: `tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py` 覆盖 single-domain、multi-dim tuple、NULL tuple、大域 transport、fail-closed threshold。
4. **[应明确] preAgg interaction**: 明确 Pivot 辅助查询是否需要经过 preAgg interceptor，以及若需要，interaction 顺序和 governance 是否保持。建议明确结论后写入 P3 设计文档。
5. **[应明确] SQL audit log marker**: Stage 5A domain transport injection 的 structured log marker，与 Java `telemetry/logging` 对齐。

### P4 C2 额外解锁条件（在 P3 基础上）

6. **[必须] Staged CTE planner**: 能生成 `_level1_domain`, `_level1_ranked`, `_filtered_1`, `_level2_domain` 等多阶段 CTE，按照 having-before-TopN、parent-before-child 顺序生成。
7. **[必须] Deterministic tie-breaking**: NULL bucket 优先 + dimension prefix key ASC 的 ORDER BY 子句生成，且 cross-dialect 一致。
8. **[必须] C2 oracle parity tests**: `tests/integration/test_pivot_v9_cascade_real_db_matrix.py` 覆盖 parent TopN + child TopN、parent having + child TopN、child having isolation、NULL tie 等所有 Java C2 测试矩阵用例。

---

## Recommendation

- **P3 Stage 5A**: 解锁条件为 conditional-pass——工程可行，但必须先实现 `PythonDomainRelationRenderer` + NULL-safe tuple matching + oracle parity 测试，方可开始实现并签收。**建议开始 P3 设计文档和 renderer prototype，但不标记实现为完成，直至三库 oracle tests 通过。**
- **P4 C2 staged SQL**: 依赖 P3 完成，且需要额外的 staged CTE planner。**继续 blocked until P3 oracle tests pass。**
- **Needed next work**:
  1. 写 `docs/v1.9/P2-Pivot-9.1-Stage5A-Renderer-Design.md`（或同等设计文档），明确 `PythonDomainRelationRenderer` 接口、params 顺序规则、CTE vs Derived Table 策略、refusal threshold。
  2. 创建 `tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py` 并取得三库 oracle 通过证据。
  3. 在 P3 实现和测试通过后，解锁 P4 C2 staged SQL 设计。
