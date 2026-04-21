# P2-fsscript in / not in 算子对齐 Java-需求

## 文档作用

- doc_type: workitem
- intended_for: execution-agent
- purpose: Python 侧 fsscript 新增 SQL 风格 `v in (...)` / `v not in (...)` 成员测试算子，与 Java `foggy-fsscript` 8.1.11.beta 契约对齐

## 基本信息

- 目标版本：`v1.4`（对齐 Java `foggy-fsscript` 8.1.11.beta）
- 需求等级：`P2`
- 状态：`signed-off`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.4/acceptance/P2-fsscript-in-notin算子对齐Java-acceptance.md
- blocking_items: none
- follow_up_required: no
- 责任项目：`foggy-data-mcp-bridge-python` / `foggy.fsscript`
- 交付模式：`single-root-delivery`
- 来源：用户主动改进项，跨语言契约对齐
- 对应 Java 需求：
  `foggy-data-mcp-bridge/docs/8.1.11.beta/P2-fsscript支持in和not-in算子-需求.md`
- 对应 Java 实现：
  - `foggy-fsscript/src/main/java/com/foggyframework/fsscript/fun/IN.java`
  - `foggy-fsscript/src/main/java/com/foggyframework/fsscript/fun/NOT_IN.java`
  - `foggy-fsscript/src/main/resources/datasetexp.cup` (`term3` 产生式)

## 背景

fsscript 用于解析 TM/QM 文件里的表达式（筛选条件、计算字段、slice 条件等）。Java 侧已在 8.1.11.beta 为 fsscript 新增 SQL 风格：

```javascript
brand in ('Apple', 'Huawei', 'Xiaomi')
brand not in ('OEM1', 'OEM2')
```

Python 引擎必须跟进，以保证 TM/QM 在 Java / Python 两端可执行出同一结果；否则同一份 slice 表达式在 Python gateway 会直接解析失败。

## 现状关键事实（Python 侧已核验）

1. `TokenType.IN` 已注册为关键字（`parser/tokens.py:126, 166`）
2. `TokenType.NOT` 已注册为关键字（`parser/tokens.py:173`），当前只作前缀逻辑非
3. 优先级表已为 `IN` 挂位 `11`（`parser/parser.py:102`），与 `INSTANCEOF` / `LIKE` / `==` 同级
4. 但 `_parse_infix` 的 `op_map`（`parser.py:1070-1085`）**没有** `IN` 条目，也没有 `NOT IN` 的 lookahead 分支 → 当前写 `v in (1,2,3)` 直接解析失败
5. `_parse_paren_or_arrow`（`parser.py:1263-1319`）对 `(a, b, c)` 这种逗号列表不支持：先尝试作为箭头参数，然后回落到单值表达式，遇到第一个 `,` 就失败
6. `ArrayExpression`（`expressions/literals.py:92`）已支持 `[1, 2, 3]`，可直接复用
7. for-in 循环在独立的 `_parse_for_statement:485` 分支消费 `TokenType.IN`，**与中缀 in 无语法冲突**
8. Python 侧无 Java 的 `(item, index) in collection` 元组迭代场景（for-in 由 parser 层独立处理，不经过中缀 IN），故不需要为该语义做兼容分支
9. `BinaryExpression.evaluate()` 的分派模式（`expressions/operators.py:59-118`）已有 `INSTANCEOF` 的成熟模板，`IN` / `NOT_IN` 可照搬

## 目标

### 语法

- `v in (1, 2, 3)` → 布尔
- `v not in (1, 2, 3)` → 布尔
- 兼容数组字面量：`v in [1, 2, 3]` / `v not in [1, 2, 3]`
- 兼容变量：`v in someList` / `v not in someList`
- 兼容任意可迭代表达式：`v in foo.bar`, `v in f()`

### 语义（与 Java `IN.containsMember` + `looseEquals` 一一对齐）

1. 右操作数解析顺序：
   - `(a, b, c)` —— fsscript 语法层直接展开为 `ArrayExpression`（Python 特殊做法，见下文"方案选择"）
   - `[a, b, c]` —— `ArrayExpression`
   - 变量/表达式求值后按 Python 类型分派：
     - `list` / `tuple` / `set` → 原样
     - `dict` → `keys()`（对齐 Java `Map.keySet()`）
     - `str` → 按字符串成员测试（子串检测；对齐 Java `"a" in "a"` 走 singleton 语义，但 Python 字符串天然有 `in` 子串语义，需明确选择）
     - `None` → 整体返回 `False`
     - 其他标量 → 包成单元素集合（对齐 Java `Collections.singletonList(v)`）
2. `null in (1, null, 2)` → `True`；`null in (1, 2)` → `False`；`x in null` → `False`
3. `v in ()` → `False`（空括号视为空集合）；`v not in ()` → `True`
4. 数值归一：`1 in (1.0, 2)` → `True`，`1 in ("1", 2)` → `False`（仅跨 Number 类归一，不跨类型）—— 对齐 Java `BigDecimal.compareTo`
5. **Python 特有 bool 护栏**：`True in (1, 2)` → `False`；`1 in (True, False)` → `False`。Python 的 `bool` 是 `int` 子类，若不隔离会跟 Java `Boolean` 不归一于 Number 的行为漂移

## 方案选择

### 核心策略：照抄 Java"不改全局括号语义"的设计意图

Java 通过 CUP grammar 让 `(1, 2, 3)` 变成通用 `UnresolvedFunCall("()")`，运行时再在 `IN.resolveHaystack` 里对 `"()"` 手工展开。Python 当前语法不支持"通用 tuple"，且 `_parse_paren_or_arrow` 涉及箭头函数语义，改它风险大。

**解决：新增 `_parse_in_rhs(prec)` 仅在 `in` / `not in` 的 RHS 上下文接管括号**。

- 遇 `(`：先消费 `(`，解析第一项；若随后是 `,`，累积更多项并产出 `ArrayExpression`；若直接是 `)`，当作单值括号表达式透明透传
- 遇 `[`：走现有 `ArrayExpression`（不变）
- 其他：走常规 `_parse_expression_with_precedence(prec)`

这样既对齐 Java 用户面语法 `v in (1, 2, 3)`，又**不触碰** `_parse_paren_or_arrow` 的全局语义。

### `NOT IN` 的两 token lookahead

Python 侧无 CUP 级 grammar rule，需要在 Pratt 主循环 `_parse_expression_with_precedence` 里特判 `TokenType.NOT`：保存解析器状态 → 试探性消费 `NOT` → 若下一 token 是 `IN` 则吃掉并走 `_parse_in_rhs`；否则回滚让外层走"循环退出"路径（`NOT` 不具备中缀优先级）。

使用现有的 `_save_state` / `_restore_state`（`parser.py:148-172`），lexer 级保存完整。

## 任务拆分

### 1. AST：`BinaryOperator` 新增 `IN` / `NOT_IN`

文件：`src/foggy/fsscript/expressions/operators.py`

- `BinaryOperator` 枚举新增：
  ```python
  IN = "in"
  NOT_IN = "not in"
  ```
- `BinaryExpression.evaluate()` 在 `INSTANCEOF` 分支之后新增：
  ```python
  elif op == BinaryOperator.IN:
      return _check_in(left_val, right_val)
  elif op == BinaryOperator.NOT_IN:
      return not _check_in(left_val, right_val)
  ```
- 新增模块级 `_check_in` / `_loose_equal` 辅助，契约对齐 `IN.java:60-71` 与 `IN.java:142-171`

### 2. 解析器：`IN` 接入 + `NOT IN` lookahead + `_parse_in_rhs`

文件：`src/foggy/fsscript/parser/parser.py`

- `_parse_infix` 的 `op_map` 追加：
  ```python
  TokenType.IN: BinaryOperator.IN,
  ```
- `_parse_infix` 中对 `TokenType.IN` 的分支改用 `_parse_in_rhs(prec)` 作为右表达式
- `_parse_expression_with_precedence` 主循环在 `NOT` 位置做 1 token lookahead：若 `NOT IN` → 产出 `BinaryOperator.NOT_IN`；否则回滚并退出循环
- 新增 `_parse_in_rhs(prec)` 接管 `(`，产出 `ArrayExpression`（多元素）或单值（单元素括号）

### 3. 测试

文件：`tests/test_fsscript/test_in_operator.py`（新增）

覆盖：

- 基本真值：`2 in (1,2,3)` → true；`5 in (1,2,3)` → false
- `not in`：`5 not in (1,2,3)` → true；`2 not in (1,2,3)` → false
- 数组字面量：`2 in [1,2,3]` → true
- 变量 RHS：`x in arr`、`x in mapVar`（dict key 语义）
- null：`null in (1, null, 2)` → true；`null in (1,2)` → false；`x in null` → false
- 空括号：`1 in ()` → false；`1 not in ()` → true
- 数值混用：`1 in (1.0, 2)` → true；`1 in (2L, 1L)`（Python 没有 `1L`，改为 `Decimal('1')`）→ true
- 字符串：`'e' in 'hello'` → true；`'k' in ('a','b')` → false
- bool 护栏：`true in (1,2)` → false；`1 in (true, false)` → false
- 表达式左值：`(a+1) in (1,2,3)`
- 回归：`for (var x in arr) { ... }` 仍可解析且语义不变
- 回归：原有 `instanceof` / `==` / `&&` / 三元 不受影响（跑一遍 test_fsscript.py + test_parser.py + test_integration.py 全量）

### 4. 文档

- `docs/v1.4/P2-fsscript-in-notin算子对齐Java-progress.md`：progress / experience / evidence 回写
- 不新增面向最终用户的手册，Java 侧已在 `FSScript-Syntax-Manual`

## 验收标准

- `src/foggy/fsscript/` fast tests 全绿
- `tests/test_fsscript/test_in_operator.py` 新增用例全绿
- Python 侧 `python -m pytest tests/test_fsscript -q` 相对基线 `+N passed, 0 failed`，且 `N` ≥ 新增用例数
- 至少一个端到端证据：在 QM slice 表达式里写 `channel in ('online', 'offline')` 可被解析与求值（已有集成测试接入点，无需新增）
- `for (var x in arr)` for-in 语义零回归
- 契约对照表回写到 progress 文档：Java `IN.java` 关键行 ↔ Python `_check_in` 实现位置的一一映射

## 非目标

- 不实现 `value in (SELECT ...)` 子查询
- 不做 fsscript → DSL `list` 算子的下推（由 `foggy.dataset_model` query planner 独立评估；本需求只保证表达式层语义正确）
- 不改 `_parse_paren_or_arrow` 的全局语义
- 不在表达式层处理 Python `generator` / `range` 等惰性迭代器的一致性（若运行时拿到此类值，按 `toIterable` 兜底走 `list()` 也可；本轮不专门覆盖）
- 不实现 Java `InResult`（`(item, index) in collection` 元组迭代）—— Python 的 for-in 由 parser 独立分支承载，无需 IN 来扛这层语义

## Progress Tracking

### 开发进度

- [x] 1. `operators.py`：`BinaryOperator.IN` / `BinaryOperator.NOT_IN` 枚举
- [x] 2. `operators.py`：`BinaryExpression.evaluate()` 新增 IN / NOT_IN 分支
- [x] 3. `operators.py`：模块级 `_check_in` / `_loose_equal` 实现，契约对齐 Java `IN.java`
- [x] 4. `parser.py`：`op_map` 挂 `TokenType.IN → BinaryOperator.IN`
- [x] 5. `parser.py`：新增 `_parse_in_rhs(prec)` 支持 `(a, b, c)` / `[a,b,c]` / 表达式
- [x] 6. `parser.py`：`_parse_expression_with_precedence` 主循环对 `NOT IN` 做 lookahead
- [x] 7. `parser.py`：`_parse_infix` 对 `TokenType.IN` 使用 `_parse_in_rhs`

### 测试进度

- [x] 单元测试：`tests/test_fsscript/test_in_operator.py` 60 passed
- [x] 回归测试：`tests/test_fsscript/` 509 passed（449 基线 + 60 新用例，0 failed）
- [x] 全量回归：`pytest -q` 1905 passed, 0 failed
- [x] 契约对照表已写入 progress 文档

### 体验进度

- `N/A` — 本需求为语法引擎增强，无 UI 交互面；QM/TM 作者在 TM/QM 文件中书写表达式即可受益

### 执行 Checkin

待实现完成后回写本块，记录：

- 实际改动文件清单
- 回归测试基线 / 新基线对比
- 自检结论：`self-check-only` | `needs-formal-quality-gate`
- 与 Java 契约对齐证据
- 是否存在遗留 / 后续项（如 DSL 下推）
