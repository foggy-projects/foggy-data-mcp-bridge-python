# S5 calculatedFields alias projection contract progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer
- purpose: Stage 5 跟踪 Java/Python calculatedFields 输出别名在 request columns 中的合法性对齐

## 基本信息

- version: v1.5 follow-up / Java 8.5.0.beta
- priority: P2
- status: complete
- completed: 2026-04-28
- owning_repo: foggy-data-mcp-bridge-wt-dev-compose (Java) + foggy-data-mcp-bridge-python

## 问题根因

Java `SchemaAwareFieldValidationStep` 在 `@Order(8)` 执行字段校验。当 `timeWindow` 活跃时，`TimeWindowInterceptor`（`@Order(-22)`）先执行并设置 `skipQuery=true`，同时构建 `BaseModelPlan`。Compose 管线随后以 `PerBaseCompiler.compileBaseModel` 重新进入 `generateSql`，用 `buildRequest(plan)` 构建新的 `SemanticQueryRequest`——该请求不携带 `calculatedFields`。二次进入时 `SchemaAwareFieldValidationStep` 在新 context 上执行，`growthPercent`/`rollingGap` 不在 schema 中，被拒绝。

## 修复方案

### 1. `TimeWindowInterceptor`（runtime 改动）

从 `originalColumns` 中剥离 request-level `calculatedFields.name`，使它们不进入 `BaseModelPlan`。后计算别名由外层 `DerivedQueryPlan` wrapper 通过 `RawExpr` 投影。

### 2. `SemanticQueryServiceV3Impl`（runtime 改动）

将 `request.getCalculatedFields()` 放入 `generateSql()` 与 `queryModel(..., "execute", ...)` 的 `extData`，使 `TimeWindowInterceptor` 可以读取并构建 outer post-calc wrapper。此前 `calculatedFields` 仅存在于 `DbQueryRequestDef` 中，`TimeWindowInterceptor` 从 `extData.get("calculatedFields")` 读取时为 null。

### 3. `SchemaAwareFieldValidationStep`（未改动）

`collectSchemaFields()` 已在 lines 85-91 将 request-level `calculatedFields.name` 加入 `schemaFields`。非 timeWindow 场景下，calc alias 在 `columns` 中天然通过校验。无需修改。

## 最终契约

### 合法（accepted）

| 场景 | 示例 | 说明 |
|---|---|---|
| 非 TW calc alias in columns | `columns=["amount1"]` + `calcFields=[{name:"amount1"}]` | `collectSchemaFields` 已涵盖 |
| 非 TW calc alias in orderBy | `orderBy=[{field:"amount1"}]` | `validateOrderBy` 走 `calcFieldMap` 路径 |
| TW + post calc alias in columns | `columns=["growthPercent"]` + `calcFields=[{name:"growthPercent"}]` | 外层 DerivedQueryPlan 投影 |
| TW + post calc alias in columns | `columns=["rollingGap"]` + `calcFields=[{name:"rollingGap"}]` | 同上 |

### 非法（rejected）

| 场景 | 错误码 | 说明 |
|---|---|---|
| 未知列 | `INVALID_QUERY_FIELD` | `columns=["notExist"]` |
| calc alias 无定义 | `INVALID_QUERY_FIELD` | `columns=["growthPercent"]` 但无 `calculatedFields` |
| SQL alias string | `INVALID_QUERY_FIELD` or `COLUMN_FIELD_NOT_FOUND` | `columns=["amount as amount1"]` 走 InlineExpressionParser |
| targetMetrics 引用 calcField | `TIMEWINDOW_TARGET_CALCULATED_FIELD_UNSUPPORTED` | 不变 |
| post calc with agg | `TIMEWINDOW_POST_CALCULATED_FIELD_AGG_UNSUPPORTED` | 不变 |
| post calc with window | `TIMEWINDOW_POST_CALCULATED_FIELD_WINDOW_UNSUPPORTED` | 不变 |
| post calc unknown ref | `TIMEWINDOW_POST_CALCULATED_FIELD_NOT_FOUND` | 不变 |

## Java 变更

| 文件 | 类型 | 说明 |
|---|---|---|
| `TimeWindowInterceptor.java` | MODIFIED | 剥离 calc output names from originalColumns |
| `SemanticQueryServiceV3Impl.java` | MODIFIED | generateSql + execute 路径传递 calculatedFields 到 extData |
| `TimeWindowParitySnapshotTest.java` | MODIFIED | growthPercent/rollingGap 加入 request columns |
| `SchemaAwareCalcFieldAliasTest.java` | NEW | 7 tests: happy + negative + execute-mode |

## Python 变更

| 文件 | 类型 | 说明 |
|---|---|---|
| `tests/fixtures/java_time_window_parity_catalog.json` | MODIFIED | 新增 requestColumns 字段 |
| `tests/integration/_time_window_parity_snapshot.json` | AUTO | Java 测试自动写入 |

## 测试证据

- Java `TimeWindowParitySnapshotTest`: 1 passed
- Java `TimeWindowValidatorTest`: 19 passed
- Java `SchemaAwareCalcFieldAliasTest`: 7 passed
- Python `test_time_window_java_parity_catalog.py`: 17 passed
- Python `test_time_window_golden_diff.py`: 3 passed
- Python `test_time_window_real_db_matrix.py`: 28 passed
- Python focused regression (time_window + sqlite_execution + java_alignment): 66 passed
