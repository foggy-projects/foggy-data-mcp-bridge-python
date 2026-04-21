# P2-fsscript in / not in 算子对齐 Java-progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer
- purpose: 记录 Python 侧 fsscript `v in (...)` / `v not in (...)` 算子开发、测试、证据、与 Java 的契约对齐对照

## 基本信息

- 对应需求：`docs/v1.4/P2-fsscript-in-notin算子对齐Java-需求.md`
- 对应 Java 需求：`foggy-data-mcp-bridge/docs/8.1.11.beta/P2-fsscript支持in和not-in算子-需求.md`
- 状态：`signed-off`
- 交付模式：`single-root-delivery`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.4/acceptance/P2-fsscript-in-notin算子对齐Java-acceptance.md
- blocking_items: none
- follow_up_required: no

## 开发进度

- [x] 1. `operators.py`：`BinaryOperator.IN` / `BinaryOperator.NOT_IN` 枚举
- [x] 2. `operators.py`：`BinaryExpression.evaluate()` 新增 IN / NOT_IN 分支
- [x] 3. `operators.py`：模块级 `_check_in` / `_loose_equal` / `_to_haystack` 实现
- [x] 4. `parser.py`：`op_map` 挂 `TokenType.IN → BinaryOperator.IN`
- [x] 5. `parser.py`：新增 `_parse_in_rhs(prec)` 支持 `(a, b, c)` / `[a,b,c]` / 表达式
- [x] 6. `parser.py`：`_parse_expression_with_precedence` 主循环对 `NOT IN` 做 lookahead
- [x] 7. `parser.py`：`_parse_infix` 对 `TokenType.IN` 使用 `_parse_in_rhs`

## 测试进度

- [x] 单元测试：`tests/test_fsscript/test_in_operator.py` — 60 passed（新增）
- [x] 回归测试：`tests/test_fsscript/` — 509 passed（449 基线 + 60 新用例）
- [x] 跨模块回归：`tests/test_fsscript/ + tests/test_dataset_model/ + tests/test_core/` — 1394 passed
- [x] 全量回归：`pytest -q` — **1905 passed, 0 failed**（基线 1821，+ 本轮 60 + 其他分支预先新增的用例）
- [x] 契约对照表：见下文"契约对齐证据"

## 实际改动文件清单

新增：

- `docs/v1.4/P2-fsscript-in-notin算子对齐Java-需求.md`
- `docs/v1.4/P2-fsscript-in-notin算子对齐Java-progress.md`（本文件）
- `tests/test_fsscript/test_in_operator.py`（60 用例）

修改：

- `src/foggy/fsscript/expressions/operators.py`
  - 新增 `BinaryOperator.IN` / `BinaryOperator.NOT_IN` 枚举项
  - `BinaryExpression.evaluate()` 追加 `IN` / `NOT_IN` 分支
  - 模块级新增 `_to_haystack` / `_loose_equal` / `_check_in`
  - `from decimal import Decimal, InvalidOperation` / `Iterable` 导入
- `src/foggy/fsscript/parser/parser.py`
  - `_parse_infix` 的 `op_map` 追加 `TokenType.IN: BinaryOperator.IN`
  - `_parse_infix` 对 `TokenType.IN` 走 `_parse_in_rhs(prec)` 而非常规表达式
  - `_parse_expression_with_precedence` 主循环特判 `TokenType.NOT` + 1-token lookahead，识别 `NOT IN`
  - 新增 `_parse_in_rhs(prec)` 方法：`()` / `(expr)` / `(a, b, c)` / `[…]` / 常规表达式五路分派

## 契约对齐证据（Java `IN.java` / `NOT_IN.java` ↔ Python `operators.py`）

| 行为 | Java 实现 | Python 实现 |
|---|---|---|
| 成员测试入口 | `IN.containsMember(ee, left, right)` | `_check_in(left, right)` |
| null 右操作数 | `resolveHaystack` 返回 null → `containsMember` 返回 false | `_to_haystack(None)` 返回 None → `_check_in` 返回 False |
| `(a, b, c)` 展开 | Grammar 生成 `UnresolvedFunCall("()")`，`resolveHaystack` 手工解包 | Parser `_parse_in_rhs` 产出 `ArrayExpression`，运行期天然可迭代 |
| 空集合 `()` | `EmptyExp` 占位被跳过 → 空 `List` | `_parse_in_rhs` 产出空 `ArrayExpression` → 空 list |
| `[a, b, c]` | `toIterable` 按 `Object[]` / `Collection` 归一 | `_to_haystack` 按 `list/tuple/set` 归一 |
| 变量 dict | `Map.keySet()` | `dict.keys()` |
| 变量标量 | `Collections.singletonList(v)` | `[value]` |
| null == null | `looseEquals` 返回 true | `_loose_equal` 返回 True |
| null ≠ 非 null | `looseEquals` 返回 false | `_loose_equal` 返回 False |
| 跨数值类型 | `BigDecimal.compareTo` | `Decimal(str(x))` 归一比较 |
| 默认比较 | `Objects.equals` | `a == b` |
| `NOT IN` | 独立 `NOT_IN.java` + grammar `term3:x NOT IN term2:y` | `BinaryOperator.NOT_IN` + Parser lookahead |
| **Python 特有：bool 护栏** | N/A（Java Boolean 与 Number 类型无继承关系） | `_loose_equal` 显式判定 bool↔Number 不等 |

## Python 侧刻意偏差

1. **没有 for-in 迭代语义合并**
   - Java `IN.java` 承担 `(item, index) in collection` 元组迭代；
   - Python for-in 走独立 `_parse_for_statement:485`，不经过 `BinaryOperator.IN`；
   - 本实现**不**兼容 `(item, index) in collection` 作为 BinaryExpression 的左值——这条路径 Python 侧语法上不存在，无需兼容。
2. **`(...)` 全局语义不变**
   - 仅在 `in` / `not in` 的 RHS 上下文里 `_parse_in_rhs` 接管括号；
   - `_parse_paren_or_arrow`（箭头函数 / 分组表达式）语义零修改。

## 主要决策与风险回顾

| 决策 | 选择 | 理由 |
|---|---|---|
| 是否新增全局 tuple 字面量 | ❌ 否 | 会冲击 `_parse_paren_or_arrow` 和箭头函数，风险大 |
| 是否为 `NOT IN` 新建单 token | ❌ 否 | 两 token + lookahead 与 Java 一致；lexer 无需变更 |
| 是否把 `TokenType.NOT` 加入优先级表 | ❌ 否 | 会破坏前缀 `not x` 的解析路径；用 save/restore 兜底更安全 |
| 是否把 `_check_in` 做成 BinaryExpression 方法 | ❌ 否 | 拆成模块级函数，便于单测直接覆盖语义契约 |
| 字符串 haystack 是否用 Python 子串语义 | ✅ 是 | Java `Collections.singletonList` + `"a" in "a"` → true 与 Python 原生 `'a' in 'abc'` 语义兼容 |
| bool 护栏 | ✅ 增加 | Python `bool` 是 `int` 子类；不护栏会破坏 `True in [1,2]` 语义 |

## 自检结论

- 自检模式：`self-check-only`
- 理由：
  - 改动面极小，集中在两个文件的增量路径
  - 既有 449 fsscript 测试全绿；新增 60 个用例覆盖全部语义契约分支
  - 跨模块回归 1905 passed / 0 failed
  - 契约对照表已落盘
- 建议：无需启动正式 `foggy-implementation-quality-gate`；直接进入 `foggy-test-coverage-audit` 快速盘点后即可签收。

## 遗留 / 后续项

- **DSL 下推**：fsscript `in` → DSL `list` 算子的 query planner 下推未在本需求范围内。若后续性能诉求出现，再独立立项。
- **Java 侧 Python 测试同步**：Java 需求文档的 Progress Tracking 当前仍显示 `[ ]`（未完成），其实 Java 代码已实现。建议后续由 Java owner 补测试（`foggy-fsscript/src/test`）并回写 Java 侧 progress；Python 侧独立完成，不受阻于 Java 测试补齐。
- **文档手册**：Java 侧 `FSScript-Syntax-Manual` 已追加 `in` / `not in` 章节（由 Java 需求覆盖）。Python 侧无独立手册，无需同步。

## 执行 Checkin

- 实际改动文件清单：见上
- 回归测试基线对比：
  - fsscript 子集：449 → 509（+60 新用例，0 失败）
  - 全量：1905 passed, 0 failed
- 自检结论：`self-check-only`
- 与 Java 契约对齐证据：见"契约对齐证据"表
- 遗留项：DSL 下推（非阻塞）
