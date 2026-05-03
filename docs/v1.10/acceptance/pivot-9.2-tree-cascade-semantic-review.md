# Pivot 9.2 Tree + Cascade Semantic Review

## 文档作用

- doc_type: semantic-decision
- status: accepted-deferred
- intended_for: root-controller / python-engine-agent / semantic-reviewer / signoff-owner
- purpose: 记录 Python Pivot v1.10 P4 `tree + cascade` 的语义评审结论、拒绝边界和后续条件。

## Scope

P4 只评审，不实现 runtime。

评审对象：

- `hierarchyMode=tree` 与 rows two-level cascade TopN/having 的组合。
- tree visible nodes、descendants、parent/child ranking、subtotal/tree totals 的语义边界。
- 当前 Python runtime 是否应该继续 fail-closed。

不改变 public Pivot DSL，不新增 schema 字段，不声明 tree+cascade 支持。

## Semantic Questions

| Question | Finding |
|---|---|
| parent rank 的输入是完整子树、可见节点，还是当前展开深度？ | 未签收。不同解释会改变 TopN parent domain。 |
| child rank 是否按 visible children、leaf descendants，还是直接子节点计算？ | 未签收。Tree shape 不等价于 flat two-level rows axis。 |
| `expandDepth` 与 TopN 的先后顺序是什么？ | 未签收。先展开再 rank 与先 rank 再展开结果不同。 |
| tree subtotal 是否包含被 TopN 剪掉的 descendants？ | 未签收。会影响总计和用户解释。 |
| parent having 在树上应用于整棵子树还是当前节点聚合？ | 未签收。LLM 很容易混淆。 |
| 是否能用现有 C2 staged SQL 近似？ | 不能。现有 C2 只证明 flat rows exactly two-level cascade。 |

## Decision

Status: accepted-deferred.

Python Pivot v1.10 继续拒绝 `tree + cascade`。当前没有足够稳定、LLM-safe、可跨数据库 oracle 化的语义定义。任何 runtime 实现都必须等单独的语义规格和 SQL oracle 矩阵签收后再开始。

Current runtime requirement:

- `hierarchyMode=tree` combined with any rows/columns `limit` or `having` returns `PIVOT_CASCADE_TREE_REJECTED`.
- No memory fallback.
- No approximate flat cascade fallback.
- No partial support for tree subtotals.

## Evidence

Targeted P4 command:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py -q
```

Result:

```text
19 passed in 0.87s
```

Coverage includes:

- same-field `hierarchyMode=tree + limit` refusal.
- sibling-field `tree + limit` refusal.
- generic standalone tree remains rejected by the existing unsupported feature guard.

Cascade regression command:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/integration/test_pivot_v9_cascade_mysql57_matrix.py -q -rs
```

Result:

```text
35 passed in 1.48s
```

Full regression command:

```powershell
pytest -q
```

Result:

```text
3943 passed in 11.79s
```

## Reopen Conditions

Tree+cascade can be reconsidered only when all of these exist:

1. A signed semantic spec defining visible nodes, descendants, `expandDepth`, ranking grain, having order, and totals.
2. SQLite/MySQL8/PostgreSQL SQL oracle parity cases.
3. Refusal matrix for SQL Server/MySQL 5.7 or new oracle evidence.
4. Explicit prompt/schema wording that prevents LLMs from inventing tree+cascade behavior.
5. Quality gate proving no memory ranking fallback was introduced.

## Signoff

Status: accepted-deferred for Python Pivot v1.10 P4.

Functional impact:

- `tree + cascade` remains unavailable.
- Existing flat/grid rows two-level cascade remains supported.
- Product can safely tell LLMs to avoid tree+cascade until a future semantic decision reopens it.
