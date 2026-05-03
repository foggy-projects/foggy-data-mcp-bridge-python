# Python Pivot 9.1 Stage 5A Domain Relation Renderer Design

## 文档作用

- doc_type: detailed-design
- intended_for: python-engine-agent / reviewer / signoff-owner
- purpose: 定义 `PythonDomainRelationRenderer` 接口、SQL shape、params 顺序、NULL-safe matching、fail-closed 规则、oracle 测试矩阵。不实现运行时代码。
- created_at: 2026-05-03
- java_reference_commit: `10e863e9`

## Status

- phase: P3-A
- status: design-only
- production runtime implemented: no
- can sign off Stage 5A: no

---

## Java Reference Semantics

Java 9.1 Stage 5A (`PIVOT-91-B2`) 在 `NonAdditiveRollupExecutor` 中实现大域传输。

当 surviving domain 的 tuple 数量超过 500 条时（`domain > threshold`），不再使用 `OR-of-AND` 切片，改为构造 `DomainTransportPlan`，将 domain tuples 打包为 CTE（PostgreSQL/MySQL8）或 Derived Table（MySQL5.7）注入到辅助查询的 SQL 中。

关键约束：

1. **queryModel lifecycle 必须保留**：辅助查询仍然走 `SemanticQueryServiceV3Impl`，保留 `preAgg + systemSlice + fieldAccess + deniedColumns` 的完整治理链。
2. **DomainTransportPlan 通过内部 carrier 传递**：附着在 `SemanticRequestContext.extData`，不暴露到公开 DSL。
3. **DomainRelationRenderer 按方言渲染**：接收 domain tuples + 列名，生成 SQL fragment + params + join predicate + placement indicator。
4. **Params 顺序**：CTE 策略时 domain params **前置**到总参数列表。Derived Table 策略时按 AST 位置注入。
5. **NULL-safe tuple matching**：PostgreSQL 使用 `IS NOT DISTINCT FROM`，MySQL8 使用 `<=>`，SQLite 使用 `IS`。
6. **Fail-closed**：方言不支持或参数量溢出时抛异常，不允许 silent fallback 到内存。
7. **domain ≤ 500 不走 transport**：继续使用现有 `OR-of-AND` 切片逻辑。

---

## Python Design Decision

Python 引擎没有 Java 那样的 SQL AST 层（Java 通过 `JdbcModelQueryEngine` 在 render 阶段注入 CTE 前缀和 JOIN 谓词）。为了保证 non-additive rollup 的正确性，domain join 必须约束“聚合的输入行集”，而不能在已经聚合后的结果上再做 join/re-aggregate。

1. **Strategy: Renderer as Fragment Generator + Query Builder Injection**
   - `DomainRelationRenderer` **只负责**生成 domain relation 本身（CTE / Derived Table 声明，以及对应的 `INNER JOIN` 谓词和 domain params）。它不负责直接包装整个 SQL。
   - P3-B 需要在 `_build_query()` 内部或 `SqlQueryBuilder` 中实现 **domain-aware auxiliary query builder**。将生成的 domain relation fragment 注入到 base relation 的 `FROM`/`JOIN` 阶段。
   - 随后的 `GROUP BY` 和聚合函数（`SUM`, `COUNT_DISTINCT` 等）必须在 join 之后执行，以确保语义对所有指标类型完全正确。
   - **Fail-closed fallback**: 如果初期 P3-B 仅实现为 additive 的 subquery wrapper 原型（在外部再做聚合），则必须强制拦截 non-additive 聚合，继续抛出 `PIVOT_CASCADE_NON_ADDITIVE_REJECTED`。

2. **No public DSL change**: 所有 domain transport 逻辑是 pivot executor 内部行为。

3. **No compose/relation module reuse**: Python compose relation mirror 是面向 ComposeScript 的，与 Pivot domain transport 无共享代码需求。

---

## Proposed API

### `DomainTransportPlan` (dataclass)

```python
@dataclass(frozen=True)
class DomainTransportPlan:
    """Internal carrier for surviving domain tuples.

    Not part of public DSL. Passed internally between pivot stages.
    """
    columns: Tuple[str, ...]          # e.g. ("category", "product")
    tuples: Tuple[Tuple[Any, ...], ...] # e.g. (("A", "X"), ("B", None))
    threshold: int = 500               # domain <= threshold → use OR-of-AND
```

- `columns`: domain 列名（QM 字段名，非物理列名）。
- `tuples`: 每个 tuple 是一行 surviving domain 值。可包含 `None`（NULL 成员）。
- `threshold`: 默认 500。domain 超过阈值时才走 transport 路径。

### `RenderedDomainRelation` (dataclass)

```python
@dataclass(frozen=True)
class RenderedDomainRelation:
    """Result of rendering a DomainTransportPlan into SQL."""
    cte_sql: str                       # e.g. "WITH _pivot_domain_transport(c1) AS (VALUES (?), (?))"
    join_predicate: str                 # e.g. "_base.c1 IS _d.c1"
    domain_params: Tuple[Any, ...]      # params for the CTE VALUES, in order
    placement: str                      # "CTE" or "DERIVED_TABLE"
    refusal_reason: Optional[str] = None  # set when rendering is refused
```

### `DomainRelationRenderer` (protocol / abstract)

```python
class DomainRelationRenderer(ABC):
    """Renders a DomainTransportPlan into dialect-specific SQL."""

    @abstractmethod
    def render(self, plan: DomainTransportPlan) -> RenderedDomainRelation:
        """Render the plan. Raises NotImplementedError if unsupported."""
        ...

    @abstractmethod
    def can_render(self, plan: DomainTransportPlan) -> bool:
        """Check if this renderer can handle the plan without exceeding safety limits."""
        ...
```

### Renderer implementations

| Class | Dialect | Strategy | Notes |
|---|---|---|---|
| `SqliteCteDomainRenderer` | SQLite | CTE with `VALUES (?)` | SQLite supports CTE since 3.8.3 (all supported Python versions). |
| `PostgresCteDomainRenderer` | PostgreSQL | CTE with `VALUES (?)` | Standard CTE syntax. |
| `Mysql8CteDomainRenderer` | MySQL 8.0 | CTE with `VALUES ROW(?)` | MySQL 8.0.19+ only. |
| `Mysql57DerivedTableRenderer` | MySQL 5.7 | `SELECT ? AS c1 UNION ALL SELECT ?` | Fallback for no-CTE dialects. Safety limits enforced. |

### Renderer resolution

```python
def resolve_renderer(dialect: FDialect) -> DomainRelationRenderer:
    """Return the appropriate renderer for the given dialect.

    Raises NotImplementedError for unsupported dialects (e.g. SQL Server).
    """
```

---

## SQL Shape By Dialect

### SQLite

Renderer 仅提供 Domain Fragment（不包含 base relation 的 aggregation）：

**CTE Definition Fragment**:
```sql
WITH _pivot_domain_transport("category") AS (
    VALUES (?), (?), (?)
)
```

**JOIN Fragment**:
```sql
INNER JOIN _pivot_domain_transport AS _d
  ON _base."category" IS _d."category"
```

**P3-B 最终组合的 Target SQL (由 query builder 组装)**:
```sql
WITH _pivot_domain_transport("category") AS (
    VALUES (?), (?), (?)
)
SELECT _base."category", COUNT(DISTINCT _base."user_id") AS "uniqueUsers"
FROM "sales_fact" AS _base
INNER JOIN _pivot_domain_transport AS _d
  ON _base."category" IS _d."category"
WHERE _base."tenant_id" = ?
GROUP BY _base."category"
```

**NULL matching**: SQLite `IS` operator is NULL-safe (`NULL IS NULL` → `TRUE`).

**Params order**: `[domain_param_1, domain_param_2, domain_param_3, ..., base_param_1, ...]`

**Multi-column tuple JOIN Fragment**:
```sql
INNER JOIN _pivot_domain_transport AS _d
  ON _base."category" IS _d."category"
 AND _base."product" IS _d."product"
```

### PostgreSQL

**CTE Definition Fragment**:
```sql
WITH _pivot_domain_transport("category") AS (
    VALUES (?), (?)
)
```

**JOIN Fragment**:
```sql
INNER JOIN _pivot_domain_transport AS _d
  ON _base."category" IS NOT DISTINCT FROM _d."category"
```

**NULL matching**: `IS NOT DISTINCT FROM` (standard SQL:2003).

**Params order**: CTE 策略中 domain params 必须 **前置** 到总参数列表。

### MySQL 8.0

**CTE Definition Fragment**:
```sql
WITH _pivot_domain_transport(`category`) AS (
    VALUES ROW(?), ROW(?)
)
```

**JOIN Fragment**:
```sql
INNER JOIN _pivot_domain_transport AS _d
  ON _base.`category` <=> _d.`category`
```

**NULL matching**: `<=>` (MySQL NULL-safe equality operator).

**Params order**: CTE 策略中 domain params 必须 **前置** 到总参数列表。

**Version guard**: `VALUES ROW(?)` syntax requires MySQL 8.0.19+. If version is unknown or < 8.0.19, renderer must refuse (fail-closed).

### MySQL 5.7 / unsupported dialect fallback

MySQL 5.7 不支持 CTE（`WITH` clause）。使用 Derived Table 策略：

**Derived Table JOIN Fragment**:
```sql
INNER JOIN (
    SELECT ? AS `category`
    UNION ALL SELECT ?
    UNION ALL SELECT ?
) AS _d
  ON _base.`category` <=> _d.`category`
```

*(注意：对于 Derived Table，没有前置的 CTE Definition Fragment)*

**Safety limits** (aligned with Java):
- Max tuples: 2000
- Max bind params: 10000
- Max SQL length: 1 MB
- Exceeding any limit → refusal → `PIVOT_DOMAIN_TRANSPORT_REFUSED`

**Params order**: Derived Table params 出现在 `FROM (...) _base` 之后、`GROUP BY` 之前：
`[base_param_1, ..., domain_param_1, domain_param_2, ...]`

注意这和 CTE 策略的 params 顺序**相反**。renderer 必须在 `RenderedDomainRelation.placement` 中区分 `CTE` vs `DERIVED_TABLE`，调用方据此决定 params 合并顺序。

### SQL Server

当前 Python 不支持 SQL Server Pivot。Renderer 直接 refuse，不 fallback。

---

## Params Ordering

### 规则

| Strategy | Params Order | Reason |
|---|---|---|
| CTE | `domain_params + base_params` | CTE 声明在 SQL 文本最外层最前端，bind params 必须按占位符顺序最先提供。 |
| Derived Table | `base_params (before join) + domain_params + base_params (after join)` | Derived Table 嵌入在 `FROM ... INNER JOIN (...)` 之间，domain params 需严格按照 AST 拼接位置注入。 |

### 示例（CTE 策略，PostgreSQL）

Base query: `SELECT COUNT(DISTINCT user_id) FROM sales_fact AS _base WHERE tenant_id = ?`（base_params = `[42]`）

Domain: 3 categories → domain_params = `["A", "B", "C"]`

Final params: `["A", "B", "C", 42]`

Final SQL:
```sql
WITH _pivot_domain_transport("category") AS (VALUES (?), (?), (?))
SELECT _base."category", COUNT(DISTINCT _base."user_id")
FROM sales_fact AS _base
INNER JOIN _pivot_domain_transport AS _d ON ...
WHERE _base."tenant_id" = ?
GROUP BY _base."category"
```

Placeholder order in SQL: `?, ?, ?, ?` → matches `["A", "B", "C", 42]` ✓

### 实现策略

```python
if rendered.placement == "CTE":
    final_params = list(rendered.domain_params) + list(base_query.params)
elif rendered.placement == "DERIVED_TABLE":
    # 需要根据 query_builder 的内部结构，将 params 插在 FROM 子句和 WHERE 子句 params 之间
    pass
```

---

## QueryModel Lifecycle Preservation

### 保证 governance 不被绕过

Domain transport 的设计不绕过任何现有 governance 步骤。完整路径：

```
query_model()
  ├─ validate_and_translate_pivot()          # Pivot validation + cascade detection
  ├─ _apply_query_governance()               # fieldAccess / systemSlice / deniedColumns
  ├─ validate_query_fields()                 # model field legality
  ├─ _build_query()                          # 【注入点】生成带有 domain join 的 SQL
  │   ├─ query_builder.from_table()
  │   ├─ query_builder.join(domain_fragment) # <== domain relation injection
  │   └─ query_builder.group_by()            # aggregation applies AFTER join
  ├─ _execute_query()                        # 执行最终 SQL
  └─ _sanitize_response_error()              # 清洗错误信息
```

关键设计决策：

1. **domain transport 发生于 query builder 组装时**。这就保证了 domain tuples 约束的是事实明细级别的数据，随后的聚合（包含 non-additive 指标）均在正确过滤后的数据集上进行。
2. **systemSlice 保留**：systemSlice 已经被渲染为 base relation 的 WHERE 条件，domain join 只是新增了过滤层。
3. **deniedColumns 保留**：deniedColumns 在 `_apply_query_governance()` 中已经转化为 denied QM fields 并校验。
4. **fieldAccess 保留**：白名单验证在 `_apply_query_governance()` 中完成。结果列过滤在 `_execute_query()` 之后执行。
5. **sanitizer 保留**：`_sanitize_response_error()` 在执行路径末尾调用。

### SQL logging

当前 Python 的 SQL logging 是通过 `logger.exception()` 在错误路径中输出。建议 Stage 5A 新增以下 INFO-level log markers：

```python
logger.info(
    "PIVOT_DOMAIN_TRANSPORT: dialect=%s, strategy=%s, domain_size=%d, columns=%s",
    dialect_name, placement, len(plan.tuples), plan.columns,
)
```

这些 marker 不泄露具体 domain 值或物理列名。

---

## preAgg Interaction

### P3 策略：preAgg 不参与 Pivot auxiliary query

**决策：明确排除。**

**原因：**

1. **当前状态**：`PreAggregationInterceptor.try_rewrite()` 未在 `query_model()` 的 Pivot 分支中被调用（P2 feasibility 已确认）。Pivot 翻译后的 SemanticQueryRequest 走普通 `_build_query()` 路径，preAgg interceptor 没有入口点。

2. **安全边界**：preAgg 表的预聚合粒度可能与 Pivot 的 GROUP BY 不匹配。如果错误地让 preAgg 重写 Pivot 辅助查询的 FROM 子句，可能得到错误的聚合结果。Java 9.1 Stage 5A 中 preAgg 参与的前提是 `NonAdditiveRollupExecutor` 的显式协调，而 Python 没有这个协调器。

3. **影响评估**：不参与 preAgg 意味着 Pivot 辅助查询始终走原始事实表。这在性能上可能较差（大表全扫描），但**结果正确性有保证**。在 Python 引擎的规模下（通常 SQLite 嵌入式、中小 MySQL/Postgres），这是可接受的。

4. **未来路径**：如果 Python 需要 preAgg + Pivot 协调（性能优化），建议在 P5+ 中单独设计，不阻塞 P3 Stage 5A 的正确性验证。

**安全保证**：preAgg interceptor 当前不在 Pivot 路径中执行。即使未来有人注册了 preAgg 配置，只要 Pivot 翻译后不触发 interceptor，就不会产生交互。P3 实现时应在 domain transport wrapper 入口添加防御性断言，确认当前 base SQL 未被 preAgg 重写。

---

## Fail-Closed Rules

| 条件 | 错误码 | 行为 |
|---|---|---|
| 方言无 CTE 且无 Derived Table renderer | `PIVOT_DOMAIN_TRANSPORT_REFUSED` | 拒绝，不 fallback 到内存 |
| MySQL 5.7 超过 safety limits (tuples > 2000 / params > 10000 / SQL > 1MB) | `PIVOT_DOMAIN_TRANSPORT_REFUSED` | 拒绝 |
| MySQL 8 版本 < 8.0.19（已知或假设） | `PIVOT_DOMAIN_TRANSPORT_REFUSED` | 降级到 Derived Table 策略或拒绝 |
| SQL Server | `PIVOT_DOMAIN_TRANSPORT_REFUSED` | 拒绝 |
| 未知方言 (dialect is None) | `PIVOT_DOMAIN_TRANSPORT_REFUSED` | 拒绝（不猜测语法） |
| Domain tuples 为空 | 不需要 transport | 正常执行，不注入 CTE |
| `domain ≤ threshold` (default 500) | 不需要 transport | 走现有 `OR-of-AND` 切片路径 |

错误码常量建议定义在 `pivot/domain_transport.py`（与 `cascade_detector.py` 同级），保持 `PIVOT_` 前缀稳定。

---

## Oracle Test Matrix

以下测试必须全部通过才能签收 P3 Stage 5A。

### Oracle Parity Tests (real SQL execution + result comparison)

| # | Test Case | Profiles | Method | Expected |
|---|---|---|---|---|
| 1 | Small single-column domain transport (10 tuples) | SQLite, MySQL8, Postgres | `test_single_column_domain_transport_parity` | PASS: domain-filtered result matches hand-written SQL oracle |
| 2 | Multi-column tuple domain transport (2 columns, 20 tuples) | SQLite, MySQL8, Postgres | `test_multi_column_domain_transport_parity` | PASS: multi-dim result matches oracle |
| 3 | NULL tuple matching (domain contains NULL member) | SQLite, MySQL8, Postgres | `test_null_tuple_domain_transport_parity` | PASS: NULL rows correctly matched |
| 4 | Domain params + base params ordering | SQLite, MySQL8, Postgres | `test_domain_params_ordering` | PASS: params align with SQL placeholders; no mismatch |
| 5 | systemSlice preserved through transport | SQLite | `test_system_slice_preserved_in_transport` | PASS: base relation includes tenant filter; domain filtering is additive |
| 6 | deniedColumns preserved through transport | SQLite | `test_denied_columns_preserved_in_transport` | PASS: denied fields not in result columns |
| 7 | Large domain transport (600 tuples, > threshold) | SQLite, MySQL8, Postgres | `test_large_domain_transport_parity` | PASS: transport-mode result matches oracle |
| 8 | Small domain (< threshold) → no transport, uses OR-of-AND | SQLite | `test_small_domain_no_transport` | PASS: OR-of-AND slice path, result matches oracle |

### Refusal / Fail-Closed Tests (no real DB needed)

| # | Test Case | Method | Expected |
|---|---|---|---|
| 9 | Unsupported dialect refuses transport | `test_unsupported_dialect_refuses` | REJECT: `PIVOT_DOMAIN_TRANSPORT_REFUSED` |
| 10 | MySQL 5.7 exceeds safety limits | `test_mysql57_safety_limit_refuses` | REJECT: `PIVOT_DOMAIN_TRANSPORT_REFUSED` |
| 11 | None dialect refuses transport | `test_none_dialect_refuses` | REJECT: `PIVOT_DOMAIN_TRANSPORT_REFUSED` |
| 12 | Empty domain → no transport needed | `test_empty_domain_no_transport` | PASS: no CTE injected, normal execution |

### Sanitizer / Logging Tests

| # | Test Case | Method | Expected |
|---|---|---|---|
| 13 | Error sanitizer does not leak `_pivot_domain_transport` / `_base` / `_d` aliases | `test_sanitizer_no_internal_alias_leak` | PASS: internal aliases not in error output |
| 14 | Domain transport log marker emitted at INFO level | `test_domain_transport_log_marker` | PASS: structured log contains dialect, strategy, domain_size |

### Test File Locations

| File | Purpose |
|---|---|
| `tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py` | Cases 1-8: real SQL oracle parity across SQLite/MySQL8/Postgres |
| `tests/test_dataset_model/test_pivot_v9_domain_transport_validation.py` | Cases 9-14: refusal, sanitizer, logging (unit tests, no external DB) |

---

## Implementation Phases After Design

### P3-B: Renderer Prototype

- Implement `DomainTransportPlan`, `RenderedDomainRelation`, `DomainRelationRenderer` base class.
- Implement `SqliteCteDomainRenderer` first (simplest CTE syntax).
- Implement NULL-safe matching helper in dialect layer (`IS` for SQLite, `IS NOT DISTINCT FROM` for Postgres, `<=>` for MySQL).
- Wire renderer into pivot executor as internal code path (behind P1 cascade detector — cascade still fail-closed; only single-level large-domain transport is enabled).
- Write unit tests for SQL shape generation (cases 9-14).
- Run SQLite oracle parity (cases 1-8 on SQLite only).
- Does **not** sign off Stage 5A.

### P3-C: Real DB Oracle Parity

- Implement `PostgresCteDomainRenderer` and `Mysql8CteDomainRenderer`.
- Implement `Mysql57DerivedTableRenderer` (if MySQL 5.7 profile is available).
- Run full oracle parity matrix on SQLite / MySQL8 / Postgres.
- Run regression: existing S3 tests + P1 cascade validation must remain green.

### P3-D: Stage 5A Signoff

- All oracle parity tests pass.
- All refusal/fail-closed tests pass.
- All sanitizer/logging tests pass.
- Full test suite (current 3859+) passes.
- `git diff --check` passes.
- Update `docs/v1.9/P0-Pivot-9.1-Java-Parity-progress.md`.
- P3 Stage 5A can be signed off.
- P4 C2 staged SQL may be conditionally unblocked.

---

## Open Questions / Risks

1. **MySQL 5.7 availability**: Python CI 是否有 MySQL 5.7 测试 profile？如果没有，MySQL 5.7 Derived Table 策略只能有 unit test（SQL shape），不能有 oracle parity。建议记录为 "MySQL 5.7 fail-closed" 并延后 oracle 到 P5+ 如果 profile 不可用。

2. **preAgg future interaction**: 当前决策是 preAgg 不参与 Pivot auxiliary query。如果未来 Python 需要处理大表性能，需要独立设计 preAgg + Pivot 协调器。不阻塞 P3。

3. **Domain threshold tuning**: Java 使用 500 作为 threshold。Python 可能在嵌入式 SQLite 场景下需要更低的 threshold（SQLite 参数上限默认 999）。建议 P3-B 中 SQLite renderer 检查 `SQLITE_LIMIT_VARIABLE_NUMBER` 并在超过时 refuse。

4. **Domain column alias / expression stability during join injection**: P3-B 不应依赖已经包装后的 base SQL 输出 alias。Domain join 谓词应通过与 `_build_query()` 相同的模型 / QM 字段解析链路，将 `DomainTransportPlan.columns` 解析到注入点可用的事实表或维表 SQL 表达式。如果某个 domain column 无法在聚合前解析为稳定表达式，应 fail closed。

5. **CTE prefix placement / existing WITH detection**: renderer 可以生成顶层 CTE fragment，但 query builder 必须把它放在最终 SELECT 之前，同时把 domain JOIN 注入正常 FROM/JOIN 链路。P3-B 应拒绝或显式合并已经自带顶层 `WITH` 的查询，不得生成 `FROM (WITH ...)`，也不得回退到聚合后的 subquery wrapping。当前 Pivot `_build_query()` 不生成 CTE，因此首版可以对 existing-WITH 查询 fail closed。
