# Pivot 9.2 Cascade Totals Acceptance

## 文档作用

- doc_type: feature-acceptance
- status: accepted
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 Python Pivot v1.10 P1 cascade subtotal / grandTotal 的语义、测试证据、拒绝边界和签收结论。

## Scope

P1 仅签收 rows-axis exactly two-level cascade 上的 additive `rowSubtotals` 与 `grandTotal`：

- `outputFormat`: `flat` / `grid`
- axes: rows exactly two-level cascade，columns 可存在但不能带 limit/having
- metrics: native additive metrics only (`SUM` / `COUNT`)
- totals domain: staged SQL 已筛出的 surviving cells

不改变 public Pivot DSL，不新增公开字段，不引入 MDX 坐标语义。

## Semantics

Cascade totals 在 C2 staged SQL 完成后执行，输入是已经经过 parent TopN/having 与 child TopN/having 筛选的 surviving cells。

- leaf rows: 保持 staged SQL 输出。
- row subtotal: 按 rows 前缀和 columns 坐标分组，最后一层 row 字段填充 `"ALL"`，并写入 `_sys_meta: {"isRowSubtotal": true}`。
- grandTotal: 按 columns 坐标分组，所有 row 字段填充 `"ALL"`，并写入 `_sys_meta: {"isGrandTotal": true}`。
- metric aggregation: 对 surviving cells 的 additive metric 求和；全 NULL 或 empty surviving domain 时 metric 为 `null`。
- grid shaping: row header 根据 `_sys_meta` 标记 `isSubtotal=true`，cells 从同一 surviving-domain totals rows 取值。

## Refused Cases

以下场景继续 fail-closed：

- `columnSubtotals` + cascade
- `tree` + cascade totals
- columns-axis cascade totals
- three-level cascade totals
- non-additive metrics such as `AVG` / `COUNT_DISTINCT`
- derived metrics such as `parentShare` / `baselineRatio`
- unsupported dialect cascade without oracle evidence

## Evidence

Targeted P1 command:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
```

Result:

```text
39 passed in 1.59s
```

The integration matrix includes SQLite, MySQL8, and PostgreSQL real SQL oracle parity in `tests/integration/test_pivot_v9_cascade_real_db_matrix.py`.

## Signoff

Status: accepted for Python Pivot v1.10 P1.

Functional impact:

- LLM-generated Pivot requests can now ask for `rowSubtotals` and/or `grandTotal` on the already-supported rows two-level cascade shape.
- Unsupported totals shapes still return explicit fail-closed errors.
- Existing S3/S5B cascade behavior is preserved.
