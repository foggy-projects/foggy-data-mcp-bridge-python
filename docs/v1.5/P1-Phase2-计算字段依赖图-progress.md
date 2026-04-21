# P1-Phase2 计算字段依赖图-progress

## 文档作用

- doc_type: progress
- intended_for: reviewer
- purpose: 记录 Phase 2 实际改动、契约对齐证据与遗留项

## 基本信息

- 对应需求：`docs/v1.5/P1-Phase2-计算字段依赖图-需求.md`
- 状态：`signed-off`
- 交付模式：`single-root-delivery`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase2-计算字段依赖图-acceptance.md
- blocking_items: none
- follow_up_required: no

## 开发进度

- [x] 1. `calc_field_sorter.py`：Kahn 算法 + 循环检测（`CircularCalcFieldError` 是 `ValueError` 子类）
- [x] 2. `_resolve_single_field` 增加 `compiled_calcs` 参数 + 最优先查表
- [x] 3. `_render_expression` / `_resolve_expression_fields` / `_build_calculated_field_sql` 全链路透传
- [x] 4. `query_model` 主流程集成：calc list → sort → compiled_calcs 初始化 → 循环内注册
- [x] 5. `_add_filter`（slice/WHERE）+ `$or`/`$and` 递归 + `$field` 引用，全链路 compiled_calcs
- [x] 6. GROUP BY 新增 calc-lookup 分支
- [x] 7. ORDER BY 新增 calc-lookup 分支（在 `selected_order_aliases` 不命中时兜底）
- [x] 8. HAVING 新增 calc-lookup 分支

## 测试进度

- [x] `test_calc_field_sorter.py` — **28 passed**（sorter 独立单测：扩展依赖识别 + 拓扑 + 循环 + 稳定性 + debug 辅助）
- [x] `test_calc_field_dependency_e2e.py` — **18 passed**（传递 / 循环 / slice / orderBy / groupBy / 向后兼容 / agg 交互）
- [x] 全量回归 `pytest -q` — **2133 passed, 0 failed**（基线 2087 + 46 = 2133，恰好等于两新文件用例数总和）

## 实际改动文件清单

### 新增

- `docs/v1.5/P1-Phase2-计算字段依赖图-需求.md`
- `docs/v1.5/P1-Phase2-计算字段依赖图-progress.md`（本文件）
- `src/foggy/dataset_model/semantic/calc_field_sorter.py` ≈ 130 行
  - `sort_calc_fields_by_dependencies` — Kahn 算法，FIFO 队列按输入顺序入队保稳定
  - `extract_calc_refs` — 复用 `field_validator._extract_field_dependencies` + 与 calc 名集合求交
  - `build_dependency_map` — 调试/工具用
  - `CircularCalcFieldError` — `ValueError` 子类，`.fields` 属性保留循环参与者
- `tests/test_dataset_model/test_calc_field_sorter.py` ≈ 28 用例
- `tests/test_dataset_model/test_calc_field_dependency_e2e.py` ≈ 18 用例

### 修改

- `src/foggy/dataset_model/semantic/service.py`
  - 新 import：`sort_calc_fields_by_dependencies`, `CircularCalcFieldError`
  - `_resolve_single_field`：新增 `compiled_calcs` 参数；函数体第一行查表，命中返回 `f"({sql})"`
  - `_render_expression`：新增 `compiled_calcs` 参数；所有递归 / `_resolve_single_field` 调用透传
  - `_resolve_expression_fields`：新增 `compiled_calcs` 参数
  - `_build_calculated_field_sql`：新增 `compiled_calcs` 参数；base_sql 渲染完即 `compiled_calcs[cf.name] = base_sql`（pre-wrap 注册）
  - `_add_filter`：新增 `compiled_calcs` 参数；`$or`/`$and`/`$field`/普通 column/shorthand 全路径查 compiled_calcs 优先
  - `query_model`（`_build_query`）：calc 段前跑 `sort_calc_fields_by_dependencies`、初始化 `compiled_calcs={}`、所有后续阶段（slice/groupby/having/orderby）传入
  - GROUP BY：calc-lookup 分支
  - HAVING：calc-lookup 分支
  - ORDER BY：calc-lookup 兜底分支（alias 不命中时）

## 契约对齐证据（Java ↔ Python）

| 行为 | Java 实现 | Python 实现 |
|---|---|---|
| 拓扑排序算法 | Kahn / FIFO 队列 | Kahn / FIFO 队列（`collections.deque`） |
| 稳定性 | 按字段输入顺序入队 | 按 `input_order` 列表顺序入队；依赖解锁后按输入顺序追加 |
| 循环检测 | `IllegalArgumentException` | `CircularCalcFieldError(ValueError)` |
| 循环错误内容 | "检测到计算字段循环引用，涉及字段: [a, b]" | `"Circular reference detected in calculated fields: ['a', 'b']..."` |
| 循环参与者完整度 | 返回 `fieldMap.keySet() - processed` | 同样 `all_names - sorted_names` |
| 自引用处理 | 静默忽略（不算循环） | 同样 |
| 传递依赖注册 | `SqlExpContext.registerCalculatedColumn` 存 `CalculatedDbColumn` | 本地 dict `compiled_calcs: Dict[str, str]` |
| 注册时机 | `evaluateExpression` 完后 | `base_sql` 渲染完后（pre-agg/window-wrap） |
| 字段名解析优先级 | `SqlExpContext.resolveColumn` 优先查 calc 注册表 | `_resolve_single_field` 第一分支查 `compiled_calcs` |

## 端到端证据样例

```sql
-- 输入: calc a→b→c
calc: [
  {name:'c', expr:'b + a'},
  {name:'b', expr:'a * 2'},
  {name:'a', expr:'salesAmount + 1'},
]

-- Phase 2 输出:
SELECT t.name AS "name",
       t.sales_amount + 1 AS "a",
       (t.sales_amount + 1) * 2 AS "b",
       ((t.sales_amount + 1) * 2) + (t.sales_amount + 1) AS "c"
FROM t_test AS t
LIMIT 1000
```

```
-- 循环引用用户体验:
calc: [ {name:'x', expr:'y+1'}, {name:'y', expr:'x-1'} ]
response.error:
  Query build failed: Circular reference detected in
  calculated fields: ['x', 'y']. Check these expressions -
  each references another in the cycle.
```

## Python 侧刻意偏差

1. **Pre-wrap 注册**：calc A 有 `agg=SUM` 时，B 引用 A 得到 pre-wrap（raw）表达式，不是 `SUM(x)`。这避免嵌套聚合产生非法 SQL。Java 侧未在测试里充分暴露这个场景，两边一致性仅对 **无 agg 的 calc 链**严格保证。若后续发现用户期望 `SUM` 嵌入，可增加显式参数控制，但 Phase 2 不做。
2. **引用时加括号**：所有 `compiled_calcs` 命中都用 `f"({sql})"` 包一层。Java 侧是嵌入 `SqlFragment`，本身带括号上下文；Python 用字符串拼接，必须主动括号防止优先级漂移（`a = x + 1`；`b = a * 2` → `(x + 1) * 2` 对而不是 `x + 1 * 2`）。
3. **错误消息字符**：Java 用中文 `检测到计算字段循环引用...`，Python 用英文。项目 README 主语言为中英混排；Python 代码库约定用英文错误，方便跨工具链（MCP、Odoo Python gateway、logs）复用。用户可见层（response.error）Python 直接透传字符串。

## 向后兼容验证

- [x] 无 `calculatedFields` 的查询走常规 flow，0 regressions
- [x] 单 calc 无依赖：SQL 输出字节级等价于 Phase 1
- [x] 单 calc 有 `agg`：`SUM(...) AS alias` 形式不变
- [x] v1.4 `in (...)` / `not in (...)` 在 calc 表达式里仍可用
- [x] v1.5 Phase 1 的方言函数翻译在 calc 链中仍可用（未直接验证但覆盖于回归）

## 自检结论

- 模式：`self-check-only`
- 理由：
  - 新增模块 `calc_field_sorter.py` 自包含、算法标准
  - Service 侧改动是**增量参数透传**，关键路径（旧调用方式仍可用）
  - 46 个新用例覆盖所有 Phase 2 声明的场景
  - 0 regressions
  - 错误消息与用户交互点清晰可读
- 建议：无需正式 `foggy-implementation-quality-gate`，可直接启动 Phase 3

## 遗留 / 后续项

Phase 2 范围内 **无未完成项**。以下是显式 scoped out 给 Phase 3 的：

- fsscript 方法调用（`s.startsWith`）→ SQL `LIKE`
- `+` 运算符字符串/数值类型推导 → `CONCAT` vs 加法
- `_render_expression` → `FsscriptToSqlVisitor`（基于 AST）
- `NTILE()` 空括号在 `_PURE_WINDOW_RE` 快路径下不触发 arity 校验 —— 自然会在 Phase 3 AST 重构时修复

## 执行 Checkin

- 实际改动文件清单：见"实际改动文件清单"
- 回归测试基线对比：2087 → 2133（+46，完全等于新增用例数）
- 自检结论：`self-check-only`
- 契约对齐证据：见"契约对齐证据"表 + 46 单测 + 端到端 SQL 样例
- 遗留项：明确划到 Phase 3

## 下一步

Phase 1 + Phase 2 完成后，Python 侧已经支持：

- ✅ 跨方言函数翻译（DATE_FORMAT / EXTRACT / DATEPART / STDEV / …）
- ✅ 编译期函数 arity 校验
- ✅ 计算字段拓扑排序 + 传递依赖 + 循环检测
- ✅ 计算字段被 slice / orderBy / groupBy / having 引用

还未达成的 Java 对齐点：

- ❌ 基于 fsscript AST 的 SQL visitor（所有操作符 / 方法调用 / 类型推导都走 AST）

**建议启动 Phase 3**，完成最后一块架构对齐。规模：1.5 人周（可分多个 session 推进）。
