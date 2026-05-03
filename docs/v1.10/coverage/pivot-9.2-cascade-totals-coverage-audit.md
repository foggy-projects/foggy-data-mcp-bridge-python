# Pivot 9.2 Cascade Totals Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: passed
- intended_for: coverage-auditor / signoff-owner
- purpose: 盘点 Python Pivot v1.10 P1 cascade totals 的需求、测试证据和剩余风险映射。

## Coverage Matrix

| Requirement | Evidence | Status |
|---|---|---|
| row subtotal over surviving child domain | `test_cascade_flat_row_subtotals_and_grand_total_surviving_domain` | covered |
| grid row subtotal over surviving domain | `test_cascade_grid_row_subtotals_and_grand_total_surviving_domain` | covered |
| grandTotal over surviving parent+child domain | same integration tests | covered |
| helper keeps column domain for grand totals | `test_grand_total_keeps_column_domain` | covered |
| empty surviving domain grandTotal metric is null | `test_empty_surviving_domain_grand_total_is_null_metric_row` | covered |
| columnSubtotals + cascade rejected | `test_column_subtotals_with_cascade_rejected` | covered |
| non-additive cascade rejected | existing cascade validation/semantic tests | covered |
| tree+cascade rejected | existing cascade validation tests | covered |
| three-level cascade rejected | existing cascade validation tests | covered |
| SQLite/MySQL8/PostgreSQL oracle parity | `test_pivot_v9_cascade_real_db_matrix.py` | covered |

## Commands

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
```

Result:

```text
39 passed in 1.59s
```

## Remaining Gaps

- SQL Server cascade oracle/refusal evidence remains P2.
- MySQL 5.7 live/refusal evidence remains P3.
- tree+cascade semantics remain deferred.
- non-additive cascade totals remain refused.

Coverage conclusion: P1 has sufficient unit, refusal, and three-database oracle evidence for acceptance.
