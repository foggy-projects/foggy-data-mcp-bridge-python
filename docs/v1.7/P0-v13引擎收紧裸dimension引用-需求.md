# P0 · v1.3 引擎收紧裸 dimension 引用 + 修复 dimension AS alias 静默丢列

## 文档作用

- doc_type: workitem
- intended_for: execution-agent / reviewer / signoff-owner
- purpose: 把 backlog `B-03` 抬升为 v1.7 正式需求，记录改造路径 / 影响面 / 测试与验收标准

## 元数据

- 优先级：**P0**（治理项 · 影响 LLM 公开契约一致性 + 测试基线稳定性）
- 状态：`accepted`（待启动）
- 目标版本：`v1.7`（Python 端）· 与 Java 端 `8.4.0.beta` 同步
- 改造路径：**Path A · 严格化**
- 来源：G5 PR-P2 调试期复盘（commit `cf2ba9b` → `352a8bb`）
- 关联 backlog：[`B-03-v13-engine-bare-dimension-tightening.md`](../backlog/B-03-v13-engine-bare-dimension-tightening.md)（已抬升）

## 背景

Foggy QM 公开契约规定：**dimension 不是直接可投影的列**，必须通过 `$id` / `$caption` / `$<custom_attr>` 引用其属性。LLM 通过 `dataset.get_metadata` / `dataset.describe_model_internal` 看到的元数据**从不暴露裸 dimension** 作为可投影字段。

但 v1.3 引擎（Python `SemanticQueryService._build_query` + Java `SemanticQueryServiceV3Impl`）当前存在三类不符合公开契约的行为，是 G5 F5 集成测试调试期暴露出来的长期遗留 bug。

## 当前行为审计（Python 实测 · 2026-04-28）

### 行为 1 · 裸 dimension fallback（无报错）

```python
columns=["orderStatus"]
# 输出：SELECT t.order_status AS "订单状态" FROM fact_sales AS t
# warnings=[], columns=['orderStatus']
```

走 `service.py:798` 的 fallback 路径 `model.get_dimension(col_name)` 命中后用 `dim.alias or dim.name` 作 SQL alias。**无 warning、无 error**。这是公开契约不暴露但引擎"宽容兼容"的路径。

### 行为 2 · `dimension AS alias` 静默丢列（仅 warning）

```python
columns=["orderStatus AS status"]
# 输出：FROM fact_sales AS t LIMIT 1000   ← 注意没有 SELECT 子句
# warnings=['Column not found: orderStatus AS status']
# columns=[]
```

走 `service.py:809-810` 的 `warnings.append(f"Column not found: ...")` 分支——既不命中 inline-aggregate 解析，又不能 `resolve_field`，又不能 `get_dimension`。**warning 不抛错**，最终 SQL 等于 `SELECT * FROM fact_sales` 的空 cte_0。LLM/用户写错时无法立即发现。

### 行为 3 · `dimension$attr AS alias` 静默丢失用户 alias

```python
columns=["orderStatus$caption AS status"]
# 输出：SELECT t.order_status AS "订单状态" FROM fact_sales AS t   ← AS status 被吞，仍用 TM 声明的 dimension.alias
# warnings=[]
```

走 `resolve_field` → `parts = ["orderStatus", "caption AS status"]` → `suffix = "caption AS status"` 不匹配 `"id"` / `"caption"` → fallback 到 `get_dimension(dim_name)` → 返回 `{sql_expr, alias_label: dim.alias}`。**完全忽略 `$caption` 后缀的语义 + 用户给出的 `AS status` alias**，仍用 TM 中的 `dimension.alias`（如 "订单状态"）。

### Java 同源情况

Java `SemanticQueryServiceV3Impl` 走 `findJdbcQueryColumnByName(columnName, false)` 解析列；存在等价的"宽容裸 dimension + 忽略 AS alias"语义（具体行为细节由 M3 跨端审计 step 实测落档）。

## 目标（Path A · 严格化）

把 v1.3 引擎对 column 字符串的解析收紧为**只接受 LLM 公开契约的形态**，让 LLM/用户写错时立即 fail-loud：

### 接受的形态（白名单）

1. `dimension$id` / `dimension$caption` / `dimension$<custom_attr>` — dimension 属性引用
2. `dimension$id AS alias` / `dimension$caption AS alias` / `dimension$<attr> AS alias` — 同上 + 用户级 alias 覆盖
3. `measureName` / `propertyName`（**FK 列等仅指 fact 自身列；不允许引用外部模型列**） — 度量 / fact 自身属性
4. `AGG(...)` / `AGG(...) AS alias` — 走 `parse_inline_aggregate` 的内联聚合（含 `SUM`/`COUNT`/`AVG`/`MIN`/`MAX`/`COUNT_DISTINCT` 等已支持的白名单）
5. F4 / F5 dict 形态（`{field, agg?, as?}` / `{plan, field, agg?, as?}`）— 经 column_normalizer flatten 到上述字符串形态

### 拒绝的形态（fail-loud）

1. **裸 `dimension`（无 `$<attr>`）** → `ValueError("COLUMN_FIELD_NOT_FOUND: '{col}' is a dimension; reference an attribute (e.g. '{col}$caption' or '{col}$id'). Hint: did you mean '{col}$caption'?")`
2. **`dimension AS alias`（裸 dimension + AS）** → 同上错误，hint 改写为 `"did you mean '{dim}$caption AS {alias}'?"`
3. **未识别的字符串** → 现行 `Column not found: <col>` warning 升级为 `ValueError("COLUMN_FIELD_NOT_FOUND: <col>")`，不再 silent-drop

### 修复的形态（保留接受 + 行为修正）

1. **`dimension$attr AS alias`** —— 必须正确解析 `AS alias`，覆盖 TM 声明的 `dimension.alias`，输出 `{sql_expr} AS "<alias>"`（而不是 `{sql_expr} AS "<dim.alias>"`）

## 改造方案

### Python 端（v1.7）

#### M2.1 · `_parse_inline_expression` 抽象升级

把"内联聚合解析"扩展为"内联表达式解析"，支持 `<expr> AS <alias>` 的非聚合形态：

- 输入 `"orderStatus$caption AS status"` → 返回 `{expr: "orderStatus$caption", alias: "status"}`
- 输入 `"SUM(salesAmount) AS total"` → 现有行为不变
- 输入 `"orderStatus AS s"` → 返回 `{expr: "orderStatus", alias: "s"}`（验证由下一步执行）

#### M2.2 · `_build_query` 列解析循环改造

```python
for col_name in request.columns:
    # Step A: 解析 AS alias（如有）
    parsed = _parse_column_with_alias(col_name)  # {expr, alias?}
    base_expr = parsed["expr"]
    user_alias = parsed.get("alias")

    # Step B: 内联聚合（保持原行为）
    inline = self._parse_inline_aggregate(base_expr, model, ensure_join, user_alias)
    if inline:
        ...

    # Step C: resolve_field 严格模式（只接受 $-form / measure / property）
    resolved = model.resolve_field_strict(base_expr)
    if resolved:
        # 如果有 user_alias，覆盖 alias_label
        label = user_alias or resolved["alias_label"]
        ...
        continue

    # Step D: 裸 dimension fail-loud（hint）
    if model.get_dimension(base_expr) is not None:
        raise ValueError(
            f"COLUMN_FIELD_NOT_FOUND: '{col_name}' references dimension '{base_expr}' "
            f"directly. Dimensions are not projectable; reference an attribute "
            f"(e.g. '{base_expr}$caption' or '{base_expr}$id'). "
            f"Hint: did you mean '{base_expr}$caption{' AS ' + user_alias if user_alias else ''}'?"
        )

    # Step E: 全失败 fail-loud（替换原 silent warning）
    raise ValueError(f"COLUMN_FIELD_NOT_FOUND: '{col_name}' is not a recognized column")
```

#### M2.3 · `resolve_field` 收紧 + alias 透传

`resolve_field` 增加 `strict` 模式（或新增 `resolve_field_strict`）：
- 不再 `parts = field_name.split("$", 1)` 后忽略 suffix——必须严格匹配 `"id"` / `"caption"` / `<custom_attr>`
- 不再走 fallback `get_dimension(dim_name)`（裸 dim 由调用方 fail-loud）
- 新增可选 `user_alias` 入参：返回的 `alias_label` 由调用方按 `user_alias or alias_label` 决定

### Java 端（8.4.0.beta）

镜像 Python 三步：

#### M3.1 · 跨端行为实测对比

跑等价的 Java 单测验证 `findJdbcQueryColumnByName` 对四类输入（裸 dim / dim AS / dim$attr / dim$attr AS）的实际行为。对照 Python 行为表，找出差异点。

#### M3.2 · `findJdbcQueryColumnByName` 收紧

按 Python `resolve_field_strict` 同样的规则收紧：拒绝裸 dim、拒绝忽略 `$<attr>` suffix、支持 user_alias 透传。

#### M3.3 · 调用点同步改造

任何调用 `findJdbcQueryColumnByName(col, false)` 的位置（schema build / SQL gen / metadata enrichment）都需要按新 contract 调整，error 路径补 fail-loud。

## 影响面评估

### 内部代码（必须排查）

| 模块 | 路径 | 风险 |
|------|------|------|
| Python `SemanticQueryService._build_query` 列循环 | `src/foggy/dataset_model/semantic/service.py:765-810` | 主改造点 |
| Python `resolve_field` | `src/foggy/dataset_model/impl/model/__init__.py:489+` | 主改造点 |
| Python `_parse_inline_expression` | `src/foggy/dataset_model/semantic/service.py:961+` | 抽象升级 |
| Python `_parse_inline_expression` 调用方 | grep `_parse_inline_expression`、`resolve_field` 全仓 | 调用契约变化 |
| Java `SemanticQueryServiceV3Impl` 列循环 | `foggy-dataset-model/src/main/java/.../impl/SemanticQueryServiceV3Impl.java:200+` | 主改造点（Java 8.4.0.beta） |
| Java `findJdbcQueryColumnByName` | 待 M3.1 grep 定位 | 主改造点（Java 8.4.0.beta） |

### 外部依赖（需联调）

| 仓 | 路径 | 风险 |
|----|------|------|
| `foggy-odoo-bridge-pro` vendored Python lib | `foggy_mcp_pro/lib/foggy/dataset_model/semantic/service.py` | 需要 vendored sync |
| `foggy-data-mcp-bridge-python` AI Chat 历史会话 fixtures | `tests/fixtures/*` | 历史用例可能含裸 dim，需 grep 排查 |
| Compose Query F4/F5 normalizer | `column_normalizer.py` | 已对齐（PR-P1/P2 落盘）；本次改造不应回退 |
| Demo / E2E 测试 | `tests/integration/*`、`tests/e2e/*` | 用例若依赖裸 dim 需重写 |

### 历史测试影响

- Java `foggy-dataset-model` sqlite lane（基线 ~1809 passed）：grep `columns.*"\w+"` 在测试 fixture 中可能命中裸 dim 用法，需要逐个判定（QM 字段名 vs 公开契约）
- Python pytest 全仓（基线 3202 passed）：同样 grep 排查
- Odoo Pro embedded fast lane：vendored sync 后跑全量

## 验收标准

### A1 · 行为契约对齐（Python）

- A1-1 · 裸 `["dimension"]` 抛 `ValueError` 含 hint 字符串 `"did you mean 'dim$caption'"`
- A1-2 · `["dimension AS alias"]` 抛 `ValueError` 含 hint `"did you mean 'dim$caption AS alias'"`
- A1-3 · `["dimension$caption AS userAlias"]` SQL 输出 `... AS "userAlias"`（不再用 TM dimension.alias）
- A1-4 · `["dimension$id"]` / `["dimension$caption"]` / `["dimension$<custom_attr>"]` 行为不变（除非测试期发现 bug）
- A1-5 · `["measureName"]` / `["propertyName"]` / `["AGG(measure) AS alias"]` 行为不变

### A2 · 行为契约对齐（Java）

A1-1 ~ A1-5 镜像（Java 错误码 / 异常类型沿用 Java 现有约定）

### A3 · 跨端 parity

- A3-1 · 同一组输入在 Java + Python 双端产生**等价错误** / **等价 SQL**（错误消息文本可有本地化差异，但错误码 / 触发条件必须 1:1）
- A3-2 · F4/F5 normalizer flatten 出来的字符串经新引擎仍能正确路由（不破坏 G5 PR-P2 测试基线）

### A4 · 回归零退化

- A4-1 · Python `pytest -q` 全仓基线维持 3202+ passed（PR-P2 baseline + 新测试净增）
- A4-2 · Java `foggy-dataset-model` sqlite lane 基线维持 1809+ passed
- A4-3 · `FormulaParitySnapshotTest` / `DialectAwareFunctionExpTest` / G5 F5 集成测试零回归

### A5 · 影响面排查证据

- A5-1 · Odoo Pro vendored sync 完成 + fast lane 全绿
- A5-2 · 历史 AI Chat fixture grep 报告 + 全部用例已迁移到 `$attr` 形态
- A5-3 · backlog `B-03` 状态置 `resolved`

## 测试计划

### 新增 Python 单测

`tests/dataset_model/semantic/test_strict_column_resolution.py`（建议）：

| # | 用例 | 期望 |
|---|------|------|
| T1 | `columns=["orderStatus"]` | `ValueError` + hint `did you mean 'orderStatus$caption'` |
| T2 | `columns=["orderStatus AS status"]` | `ValueError` + hint `did you mean 'orderStatus$caption AS status'` |
| T3 | `columns=["orderStatus$caption"]` | SQL `SELECT t.order_status AS "订单状态"` |
| T4 | `columns=["orderStatus$caption AS userAlias"]` | SQL `SELECT t.order_status AS "userAlias"` ★关键 |
| T5 | `columns=["orderStatus$id"]` | SQL `SELECT t.order_status AS "<dim.alias or 'orderStatus'>"`（保留现行）|
| T6 | `columns=["unknownField"]` | `ValueError("COLUMN_FIELD_NOT_FOUND: ...")` |
| T7 | `columns=["customer_id$caption"]` (FK 维度) | SQL 走 join 路径，行为不变 |
| T8 | `columns=["customer_id$caption AS customer"]` (FK 维度 + alias) | SQL alias 用 user_alias |
| T9 | `columns=["SUM(salesAmount) AS total"]` | 行为不变（inline aggregate） |
| T10 | F5 dict `[{plan, field: "orderStatus$caption"}]` | flatten 后行为同 T3 |

### 新增 Java 单测

`SemanticQueryServiceV3StrictColumnResolutionTest.java`：T1-T10 镜像（用 `product$id` / `product$caption` / `salesAmount` 替换 demo 模型字段）

### 集成测试回归

- G5 F5 集成测试（PR-P2 + Java `F5ColumnObjectIntegrationTest`）零回归
- `EcommerceTestSupport` 系列零回归

## 非目标

- ❌ 不改 F4 / F5 normalizer 的 flatten 规则（已落盘契约）
- ❌ 不改 `parse_inline_aggregate` 的聚合白名单
- ❌ 不重构 metadata 暴露的字段形态（仍按 `$attr` 暴露）
- ❌ 不引入 deprecation warning compat layer（Path A 直接 fail-loud）

## 风险

- R1 · 内部历史测试 / fixture 大量依赖裸 dim → M2.4 grep 全仓 + 批量重写
- R2 · vendored Odoo Pro embedded 漂移 → M5 vendored sync 必做
- R3 · 跨端错误消息文本不一致 → A3-1 用错误码而非文本作 parity 校验维度
- R4 · `dimension$id` 在自属性 dim（如 `orderStatus`）上的语义模糊 → M2.3 在 `resolve_field_strict` 里明确：自属性 dim 的 `$id` 与 `$caption` 都映射到 `dim.column`，但保留 `$id` 标记便于 metadata 区分

## 工作量估算

| 阶段 | Python | Java | 备注 |
|------|--------|------|------|
| 跨端审计 | 0.5d | 0.5d | M3.1 实测 + 行为对照表 |
| 主改造 + 单测 | 1d | 1d | M2.x / M3.x |
| 调用点同步 + 影响排查 | 1d | 1d | grep 全仓 + fixture 迁移 |
| Odoo Pro vendored sync + fast lane | — | — | 由 Java/Python 落盘后并行 |
| 文档 + 验收 | 0.5d | — | 共享 acceptance |
| **合计** | ~3d | ~2.5d | 预计 1 周内双端落盘 |

## 后续衔接

- 完成后通知 root `CLAUDE.md` "已解决的问题" 区块新增条目（`v1.3 引擎收紧裸 dimension 引用`）
- backlog `B-03` 关闭并加链接到本 v1.7 / 8.4.0.beta 文档
- 影响 G5 F5 spec §4.2 "F5 用户级开放门"——本治理项落盘后，flag-flip rollout 的 C1-C4 决策门更接近成立
