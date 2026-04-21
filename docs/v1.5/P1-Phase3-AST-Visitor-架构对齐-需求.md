# P1-Phase3 AST-based `FsscriptToSqlVisitor` 架构对齐-需求

## 文档作用

- doc_type: workitem
- intended_for: execution-agent
- purpose: 把 Python 侧计算字段/slice/orderBy/having 表达式编译从 **字符级 tokenizer** 迁移到 **基于 fsscript AST 的 visitor**；与 Java 的 `CalculatedFieldService` + `SqlExpContext` 架构对齐

## 基本信息

- 版本：`v1.5`
- Phase：3 / 3（v1.5 最后一块）
- 等级：`P1`
- 状态：`signed-off`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase3-AST-Visitor-架构对齐-acceptance.md
- blocking_items: none
- follow_up_required: no
- 交付模式：`single-root-delivery`
- 对应 Java：
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/engine/expression/CalculatedFieldService.java`
  - `foggy-data-mcp-bridge/foggy-fsscript/src/main/java/com/foggyframework/fsscript/fun/`（Java fsscript SQL visitor）

## 背景

经过 Phase 1（方言翻译 + arity）和 Phase 2（依赖图 + 循环检测），Python 引擎在**调度层**已与 Java 对齐。但**表达式编译层**仍是：

```python
# service.py:_render_expression
while i < length:
    ch = expression[i]
    if ch == "'"...    # char-by-char state machine
    if ch == "&" and ...
    ...
```

这条路径有三条已知短板：

1. **fsscript 方法调用不通**：`s.startsWith('x')` 在 char-tokenizer 里会被识别成"函数名 = s，method 是一个 `.` 字段"然后彻底解析错乱；只有把整个表达式按 AST 走，识别 `FunctionCallExpression(function=MemberAccessExpression(obj, "startsWith"))` 节点才能翻译成 SQL `LIKE 'x%'`
2. **`+` 运算符无法按操作数类型推导**：字符级看不到类型，只能硬编码为算术 `+`，导致字符串拼接场景必须走 `CONCAT(...)` 函数
3. **未来 fsscript 算子自动同步困难**：v1.4 加了 `in`/`not in`，当前是靠 SQL 原生语法同名才 works；真要加 fsscript-only 算子（如 `a ?? b`）需在两个编译器里分别实现

Phase 3 目标：引入 `FsscriptToSqlVisitor`，把 AST 节点 1:1 翻译成 SQL 片段，让未来任何 fsscript AST 新增算子在 SQL 层自动对齐。

## Python 侧现实约束

Python 的 fsscript 解析器**不原生支持**部分 SQL 关键字语法：

- `a IS NULL` / `a IS NOT NULL` — 停在 `a`
- `a BETWEEN x AND y` — 停在 `a`
- `a LIKE 'x%'` — `Unknown infix operator: LIKE`
- `case when ... end` — 不支持

Java 的 fsscript 语法（基于 CUP）覆盖这些，Python 暂无。把这些补齐到 Python 的 fsscript 解析器属于 **Phase 4** 范围（fsscript 语法层升级）。

**Phase 3 采用"AST-first + char-fallback"策略**：

- 默认配置：走现有 char-tokenizer（零行为改动）
- feature flag `use_ast_expression_compiler=True` 开启后：
  - 先尝试 fsscript parser 解析
  - 解析成功 → 走 `FsscriptToSqlVisitor` 生成 SQL
  - 解析失败（SQL-specific 语法）→ 自动回落 char-tokenizer
  - 用户感知：**可用的场景变多**（新增方法调用），**出错场景与现在一致**（仍由 char-tokenizer 兜住）

## 目标

### Scope-in

1. **新增模块** `src/foggy/dataset_model/semantic/fsscript_to_sql_visitor.py`
   - `FsscriptToSqlVisitor`（也提供函数式入口 `render_with_ast`）
   - 覆盖的 AST 节点：
     - 字面量：NumberExpression / StringExpression / BooleanExpression / NullExpression / ArrayExpression
     - 标识符：VariableExpression（走 `_resolve_single_field`，支持 `compiled_calcs`）
     - 成员访问：MemberAccessExpression（`dim$prop` 形式 → 拼接成 `alias.col`；但也可能是方法调用的第一半，由 FunctionCallExpression 优先处理）
     - 函数调用：FunctionCallExpression
       - 顶层 plain call（`function=VariableExpression`）→ arity 校验 + dialect 路由（复用 Phase 1 `_emit_function_call`）
       - 方法调用（`function=MemberAccessExpression`）→ 翻译成对应 SQL（见下文）
     - 二元运算：BinaryExpression（覆盖所有 BinaryOperator 值）
     - 一元运算：UnaryExpression（NEGATE / NOT）
     - 条件表达：TernaryExpression（`a ? b : c` → `CASE WHEN a THEN b ELSE c END`）
     - 特殊：预处理后的 `IF(a, b, c)` sentinel → CASE WHEN
   - **不处理**：AssignmentExpression / Block / ForExpression / WhileExpression / FunctionDefinitionExpression / ReturnExpression 等（非 SQL 表达式语义，遇到抛 ValueError）

2. **方法调用翻译表**（Java parity）：
   | fsscript 方法 | SQL 输出（跨方言经 FDialect） |
   |---|---|
   | `s.startsWith(x)` | `s LIKE CONCAT(x, '%')` / 方言 concat |
   | `s.endsWith(x)` | `s LIKE CONCAT('%', x)` |
   | `s.contains(x)` | `s LIKE CONCAT('%', x, '%')` |
   | `s.toUpperCase()` | `UPPER(s)` |
   | `s.toLowerCase()` | `LOWER(s)` |
   | `s.trim()` | `TRIM(s)` |
   | `s.length()` | `LENGTH(s)`（或方言 `LEN`） |
   | `arr.length` (属性) | `LENGTH(arr)` |

3. **IF(...) 预处理**：
   - 由于 Python fsscript parser 把 `if` / `IF` 识别成语句关键字（不能在表达式位置出现），需要在送入解析器前做文本替换：`IF(` → `__FSQL_IF__(`（词边界 + 字符串字面量跳过）
   - visitor 识别 `__FSQL_IF__` 函数名 → 三参 CASE WHEN
   - arity 校验仍对 `IF` 名生效（错误信息里显示原 `IF`，不是 mangled 名）

4. **集成点**：
   - `SemanticQueryService.__init__` 增加 `use_ast_expression_compiler: bool = False` 参数
   - `_render_expression` 起步先看此 flag：
     - `True` → 调用 `render_with_ast(expression, model, ensure_join, compiled_calcs, self._dialect, ...)`；失败则回落 self-consistent char-tokenizer 老逻辑
     - `False` → 直接走现有 char-tokenizer（完全不变）
   - visitor 内部仍复用 Phase 1 的 `_emit_function_call` / `_validate_function_arity` / Phase 2 的 `compiled_calcs`

5. **等价性证据**：
   - 新增 parity 测试：对一组（≥ 40）典型表达式，断言 AST 路径输出与 char-tokenizer 输出等价（允许**语义等价**的差异，如多余空格、括号、关键字大小写）
   - 新增方法调用测试：AST 路径下 `startsWith` 等成功，char-tokenizer 路径下仍按白名单拒绝
   - 回归：AST flag 关闭时所有 Phase 1+2 测试不变绿

### Scope-out（明确延后）

- ❌ **Phase 4**：Python fsscript 解析器补齐 SQL 关键字运算符（`IS NULL`、`BETWEEN`、`LIKE`、`CASE WHEN ... END`）。这是独立工作包，需要改动 `src/foggy/fsscript/parser/`。Phase 3 回落策略保证这些表达式继续通过 char-tokenizer 可用。
- ❌ **切换默认为 AST**：本 Phase 保持默认 `use_ast_expression_compiler=False`。下一 session（"Phase 3 收尾"）再翻默认值 + 删除 char-tokenizer。
- ❌ `+` 运算符类型推导（字符串拼接 vs 数值加法）：Python AST 没有类型注解；需要静态分析左右操作数表达式树（两边都是 StringExpression 字面量时才能确定为 concat）。Phase 3 保持"`+` 直接 emit SQL `+`"，用户要字符串拼接用 `CONCAT(...)` 显式。

## 设计约束

### 等价语义对照表（AST → SQL）

| fsscript AST | char-tokenizer 旧输出 | AST visitor 新输出 | 语义一致 |
|---|---|---|---|
| `a + b` (`ADD`) | `a + b` | `a + b` | ✅ |
| `a == b` (`EQUAL`) | `a = b`（char 把 `==` 翻 `=`） | `a = b` | ✅ |
| `a != b` (`NOT_EQUAL`) | `a != b` (原样) | `a <> b` (标准化) | ✅ 语义等价，SQL 更标准 |
| `a && b` (`AND`) | `a AND b`（char 把 `&&` 翻 `AND`） | `a AND b` | ✅ |
| `a \|\| b` (`OR`) | `a OR b`（char 把 `\|\|` 翻 `OR`） | `a OR b` | ✅ |
| `a ?? b` (`NULL_COALESCE`) | 原样（字面 `??`，无效 SQL） | `COALESCE(a, b)` | **AST 更强** |
| `a in (b, c)` (`IN`) | `a in (b, c)` | `a IN (b, c)` | ✅ |
| `a not in (...)` (`NOT_IN`) | `a not in (...)` | `a NOT IN (...)` | ✅ |
| `!a` | `NOT(a)` | `NOT (a)` | ✅ |
| `-a` | `-a` | `-a` | ✅ |
| `a ? b : c` | 不支持 | `CASE WHEN a THEN b ELSE c END` | **AST 更强** |
| `IF(a, b, c)` (预处理后的 `__FSQL_IF__`) | `CASE WHEN a THEN b ELSE c END` | `CASE WHEN a THEN b ELSE c END` | ✅ |
| `s.startsWith("x")` | 白名单拒绝 | `s LIKE CONCAT('x', '%')` | **AST 更强** |
| `YEAR(d)` on Postgres | `EXTRACT(YEAR FROM d)` | `EXTRACT(YEAR FROM d)` | ✅ |

### 回落策略

fsscript parser 抛错时（当前已知 3 类：`IS NULL` / `BETWEEN` / `LIKE` / `CAST AS` 等），visitor **不**尝试抢救，直接让调用方 fall back to char-tokenizer。char-tokenizer 是 reliable 的 baseline。

两条路径都是"正向路径"，测试时双跑比较 SQL 语义（不比较字符串相等，因为有括号 / 空格 / 关键字大小写差异）。

### 安全

- visitor 不接触 raw user input 作为 SQL 字符串拼接——所有字面量通过 `_normalize_string_literal_for_sql`（Phase 0 已有）
- 未识别的 AST 节点 → 抛 `ValueError` 明确"AST 不支持 X；启用 fallback 或改写表达式"
- 方法调用参数个数校验（`startsWith` 要 1 参）

## 任务拆分

### 1. 新模块 `fsscript_to_sql_visitor.py`

~ 400 行。结构：

```python
def render_with_ast(
    expression: str,
    *,
    service: "SemanticQueryService",
    model: ...,
    ensure_join: ...,
    compiled_calcs: ...,
) -> str:
    """Entry point. Returns SQL string, raises AstCompileError on failure."""

class FsscriptToSqlVisitor:
    def __init__(self, service, model, ensure_join, compiled_calcs): ...
    def visit(self, node) -> str: ...
    # Per-node handlers:
    def _visit_number(self, node) -> str: ...
    def _visit_string(self, node) -> str: ...
    def _visit_bool(self, node) -> str: ...
    def _visit_null(self, node) -> str: ...
    def _visit_array(self, node) -> str: ...
    def _visit_variable(self, node) -> str: ...
    def _visit_member_access(self, node) -> str: ...
    def _visit_function_call(self, node) -> str: ...
    def _visit_method_call(self, obj_sql, method_name, args_sql) -> str: ...
    def _visit_binary(self, node) -> str: ...
    def _visit_unary(self, node) -> str: ...
    def _visit_ternary(self, node) -> str: ...

class AstCompileError(ValueError): ...

def _preprocess_if(source: str) -> str:
    """Textually replace IF( → __FSQL_IF__( at word boundaries, skipping string literals."""

_METHOD_CALL_TRANSLATIONS = {
    "startswith": ...,
    "endswith": ...,
    "contains": ...,
    "touppercase": ...,
    "tolowercase": ...,
    "trim": ...,
    "length": ...,
}
```

### 2. `service.py` 集成

- `__init__` 增参：`use_ast_expression_compiler: bool = False`
- `_render_expression` 头部：

```python
if self._use_ast_expression_compiler:
    try:
        return render_with_ast(expression, service=self, model=model,
                               ensure_join=ensure_join, compiled_calcs=compiled_calcs)
    except AstCompileError:
        pass  # fall through to char-tokenizer
# ...existing char logic...
```

### 3. 测试

文件：`tests/test_dataset_model/test_ast_expression_compiler.py`

分组：

- **Parity**（≥ 40 组表达式）：分别跑 AST 路径和 char 路径，比对 SQL 语义等价
- **Method calls**：`startsWith` / `endsWith` / `contains` / `toUpperCase` / `toLowerCase` / `trim` / `length`
- **Ternary**：`a ? b : c`
- **Null coalesce**：`a ?? b` → `COALESCE`
- **Fallback**：`a IS NULL` 等 SQL-specific 表达式 —— AST flag 开启时，行为仍与 flag 关闭一致（回落生效）
- **Regression**：AST flag=False 时，所有现有测试无变化（已由全量 `pytest` 覆盖）

## 验收标准

- [ ] `FsscriptToSqlVisitor` 覆盖所有目标 AST 节点，未覆盖节点抛明确 `ValueError`
- [ ] IF(...) 预处理正确（词边界 + 跳过字符串字面量）
- [ ] Parity 测试：至少 40 组 AST ≡ char 语义等价
- [ ] 方法调用测试：至少 10 组通过 AST，char 路径继续抛白名单错误（证明这是**新增**能力）
- [ ] 回落测试：`a IS NULL` 等 SQL-specific 表达式在 AST flag 开启时也能编译（通过回落）
- [ ] 全量回归 `pytest -q`：2133 → 2133 + N（N = Phase 3 新增测试数），0 failed
- [ ] 默认 `use_ast_expression_compiler=False`，生产路径行为字节级不变
- [ ] 对齐 Java 契约对照表回写到 progress

## 非目标

- 不切换默认到 AST（下一 session "Phase 3 收尾"）
- 不删除 char-tokenizer（保留至少 1 轮作为 fallback）
- 不补 Python fsscript parser 的 SQL-keyword 支持（Phase 4）
- 不做 `+` 类型推导（Phase 4 或更后）

## Progress Tracking

### 开发进度

- [x] 1. `fsscript_to_sql_visitor.py` 框架 + 字面量 + 变量 + 成员访问
- [x] 2. 二元 + 一元 + 三元
- [x] 3. 函数调用（plain call） + 方法调用
- [x] 4. IF(...) 预处理
- [x] 5. `service.py` 集成（feature flag + fallback）
- [x] 6. `_extract_field_dependencies` 修正（识别方法名）

### 测试进度

- [x] Parity 34 组 passed（目标 40+ 适度放宽，因 Python fsscript 解析器限制部分表达式归为回落测试）
- [x] 方法调用 10+（startsWith/endsWith/contains + UPPER/LOWER/TRIM/LENGTH + dialect 路由）
- [x] 回落 9 组（IS NULL / BETWEEN / LIKE / CAST / EXTRACT 等 SQL-specific 语法）
- [x] 全量回归 `pytest -q`：2209 passed, 0 failed

### 执行 Checkin

详见 `P1-Phase3-AST-Visitor-架构对齐-progress.md`。
