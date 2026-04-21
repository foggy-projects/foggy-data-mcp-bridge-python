# P1-Phase2 计算字段依赖图-需求

## 文档作用

- doc_type: workitem
- intended_for: execution-agent
- purpose: 在 Python 引擎里补齐 Java 的计算字段依赖图（拓扑排序 + 循环检测 + 传递依赖），支持 "calc B 引用 calc A" 这种链式场景

## 基本信息

- 版本：`v1.5`
- Phase：2 / 3
- 等级：`P1`
- 状态：`signed-off`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase2-计算字段依赖图-acceptance.md
- blocking_items: none
- follow_up_required: no
- 交付模式：`single-root-delivery`
- 对应 Java：
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/engine/expression/CalculatedFieldService.java#sortByDependencies`（Kahn 算法，lines 143-205）
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/engine/expression/SqlExpContext.java#resolveColumn`（lines 75-84）
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/ecommerce/CalculatedFieldTest.java`（transitive + cycle 用例）

## 背景

Phase 1 之后 Python 侧已经能做方言感知的函数翻译和 arity 校验，但计算字段本身的**编译顺序仍然是用户输入顺序**：

- `request.calculated_fields` 被 `for cf_dict in request.calculated_fields:` 线性遍历（`service.py:648`）
- 每个 calc field 独立按**模型列**解析表达式（`_resolve_expression_fields → _render_expression → _resolve_single_field`）
- `_resolve_single_field` 找不到 calc-to-calc 的引用时，走兜底返回原字面量，导致最终 SQL 里出现未限定的 identifier → 数据库执行期错误

后果：

1. **不支持传递依赖**：`calc_b = calc_a * 2`（其中 `calc_a = price - discount`）会编译出 `calc_a * 2` 这样的不合法 SQL
2. **无循环检测**：`calc_a = calc_b + 1`, `calc_b = calc_a - 1` 编译"成功"但数据库执行期两边都报 "column not found"
3. **slice / orderBy 不能引用 calc 字段**：同样问题

Java 对此有完整实现：Kahn 拓扑排序 + 循环检测 + 编译结果注册到 `SqlExpContext`，计算 B 时能把 A 的已编译 SQL 片段内联进去。

## 目标

### Scope-in

1. **新增模块** `src/foggy/dataset_model/semantic/calc_field_sorter.py`：
   - `sort_calc_fields_by_dependencies(calc_fields) -> List[CalculatedFieldDef]`：Kahn 算法按依赖拓扑排序
   - 循环时抛 `ValueError`，消息格式：
     `"Circular reference detected in calculated fields: ['a', 'b']. Check these expressions — each references another in the cycle."`
2. **传递依赖解析** —— `_resolve_single_field` 增加 `compiled_calcs: Optional[Dict[str, str]]` 参数：
   - 优先查 `compiled_calcs`（key = calc 字段名，value = 已渲染的 pre-wrap SQL 片段）
   - 命中则返回 `f"({compiled_calcs[name]})"`（外包一层括号防优先级漂移）
   - 未命中走现有 dim / measure / fallback 路径
3. **编译期注册** —— `SemanticQueryService.query_model` 的 calc 循环：
   - 入口先跑 `sort_calc_fields_by_dependencies`，替换掉原 `request.calculated_fields` 的遍历顺序
   - 初始化 `compiled_calcs: Dict[str, str] = {}` 本次查询上下文
   - 每个 calc 渲染完 `base_sql`（pre-agg/window）后立刻 `compiled_calcs[cf.name] = base_sql`
   - 之后的 WHERE / HAVING / ORDER BY / GROUP BY 都传入同一个 `compiled_calcs`
4. **链路覆盖**：把 `compiled_calcs` 从 `_build_calculated_field_sql` 一路透传到 `_resolve_expression_fields` → `_render_expression` → `_resolve_single_field` → 以及 `_add_filter`（slice / having） / orderBy / groupBy 的字段解析

### Scope-out（明确延后）

- ❌ fsscript 方法调用（`s.startsWith(x)` → SQL `LIKE`）→ Phase 3
- ❌ `+` 运算符按操作数类型推导 → Phase 3
- ❌ 把 `_resolve_single_field` 改成 AST-based visitor → Phase 3
- ❌ 高级场景：calc A 有 agg（`SUM(x)`）时 calc B 引用 A 是否保留 agg 层次 —— Phase 2 采用**pre-wrap 语义**（见下文）

## 关键设计决策

### Pre-wrap 注册语义

当 calc A 有 `agg=SUM`（emit `SUM(x) AS A`）而 calc B 写 `A * 2` 时，Python 把 A **pre-wrap** 的 `x` 注册到 `compiled_calcs`。因此 B 的最终 SQL 是 `(x) * 2`；如果 B 自己也有 `agg=SUM`，最终是 `SUM((x) * 2)`。

**理由**：

- 避免嵌套聚合 `SUM(SUM(x) * 2)` 这种非法 SQL
- 与"用表达式名代替表达式"的心理模型一致：`A` 就是 A 的表达式的别名
- 若用户确实想 `SUM(x)` 被嵌入 B，直接在 B 里写 `SUM(x) * 2` 即可
- 这对应 Java 文档里的 `CalculatedFieldTest` 正向用例（两边都无 agg，pre-wrap 即 final）

### 循环错误消息对齐

与 Java 的语义一致但用英文（Python 代码库惯例）：

```
Java:    "检测到计算字段循环引用，涉及字段: [a, b]。请检查这些字段的表达式，确保没有互相引用。"
Python:  "Circular reference detected in calculated fields: ['a', 'b']. Check these expressions — each references another in the cycle."
```

错误里必须**含全部参与循环的字段名**，便于用户定位。

### 稳定排序

Kahn 算法在"多个零入度"时的出队顺序决定输出顺序。为了让测试可验证、用户看到可预期的 SQL，入队顺序**严格按输入顺序**（不是按字母序）。

### 依赖提取

复用 Phase 1 已有的 `field_validator._extract_field_dependencies`（已被用于列治理）——它：

- 先剥字符串字面量
- 再分词
- 过滤 SQL 关键字

得到的集合再与 calc 字段名集合求交，就是这一 calc 的依赖。**不需要调用 fsscript AST**，零 Phase 3 耦合。

## 任务拆分

### 1. 新模块 `calc_field_sorter.py`

| 函数 | 职责 |
|---|---|
| `sort_calc_fields_by_dependencies(fields) -> List` | Kahn 算法；稳定排序；循环抛 ValueError |
| `_extract_calc_refs(expr, calc_names) -> Set[str]` | 调 `_extract_field_dependencies` + 交集 |

### 2. 修改 `service.py`

| 位置 | 改动 |
|---|---|
| `_resolve_single_field` 签名 | 增 `compiled_calcs: Optional[Dict[str, str]] = None` 参数 |
| `_resolve_single_field` 函数体 | 第一行检查 `compiled_calcs` 命中 |
| `_render_expression` 签名 | 增 `compiled_calcs` 参数，透传给内部 `_resolve_single_field` 调用 |
| `_resolve_expression_fields` 签名 | 增 `compiled_calcs` 参数 |
| `_build_calculated_field_sql` 签名 | 增 `compiled_calcs` 参数；在 base_sql 渲染完成后 `compiled_calcs[cf.name] = base_sql` |
| `query_model` 主流程 | 调 sorter、初始化 `compiled_calcs = {}`、替换 calc 循环用排序后的列表、所有后续调用传入 `compiled_calcs` |
| `_add_filter` 及其递归调用 | 同样链路传入 `compiled_calcs`（slice/having 能引用 calc） |
| GROUP BY / ORDER BY 字段解析 | 同上（都调用 `_resolve_single_field`） |

### 3. 测试

新文件：`tests/test_dataset_model/test_calc_field_dependency.py`

覆盖：

- **Sorter 独立单测**
  - 空列表 / 单元素 / 无依赖多元素（保序） / 简单链 A→B→C / 多入度 / 多源（多个根）
  - 循环：A↔B / A→B→A / A→B→C→A / 自循环（A→A 视为循环？还是忽略？—— 与 Java 一致，自循环忽略）
  - 稳定性：相同入度下按输入顺序出队
- **端到端**
  - 传递依赖：calc_b 引用 calc_a，SQL 应包含 `(calc_a 的 raw 表达式)` 内联
  - 深度链：`a=x+1, b=a*2, c=b-a` → `c = ((x+1) * 2) - (x+1)`
  - 循环：清晰 ValueError，消息含所有循环字段名
  - Slice/WHERE 引用 calc：`slice: [{field: "net", op: ">", value: 100}]` 成功
  - ORDER BY 引用 calc
- **回归**
  - 既有无依赖 calc 字段场景维持输出一致
  - v1.4 `in (...)` 表达式在 calc 字段里仍可用
  - Phase 1 的方言函数翻译在 calc 链里仍可用

## 验收标准

- [ ] 新文件 `calc_field_sorter.py` 实现 Kahn 算法，至少 12 个 sorter 单测全绿
- [ ] `SemanticQueryService` 链路全量支持 `compiled_calcs` 透传
- [ ] `test_calc_field_dependency.py` 覆盖上述所有场景，全绿
- [ ] 全量回归 `pytest -q`：`2087 → 2087+N`，0 failed
- [ ] 对齐 Java 契约对照表回写到 progress

## 非目标

- 不改 `_render_expression` 的字符级架构（Phase 3）
- 不支持 agg 嵌套场景的复杂语义（见"Pre-wrap 注册语义"决策）
- 不为 calc 字段添加 slice 下推优化

## Progress Tracking

### 开发进度

- [x] 1. `calc_field_sorter.py`：Kahn 算法 + 循环检测
- [x] 2. `_resolve_single_field` 增加 `compiled_calcs` 参数 + 优先查
- [x] 3. `_render_expression` / `_resolve_expression_fields` / `_build_calculated_field_sql` 透传
- [x] 4. `query_model` 主流程集成：sort → 注册 → slice/orderBy/groupBy/having 全覆盖
- [x] 5. `_add_filter` 及其递归调用透传 compiled_calcs

### 测试进度

- [x] Sorter 单测：28 passed（超出 12+ 目标）
- [x] 端到端：18 passed（超出 15+ 目标）
- [x] 全量回归 `pytest -q`：2133 passed, 0 failed

### 执行 Checkin

详见 `P1-Phase2-计算字段依赖图-progress.md`。
