# Pivot 9.2 Tree + Cascade Semantic Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: passed
- intended_for: coverage-auditor / signoff-owner
- purpose: 盘点 Python Pivot v1.10 P4 `tree + cascade` semantic review 的文档、测试和剩余缺口。

## Coverage Matrix

| Requirement | Evidence | Status |
|---|---|---|
| semantic questions documented | P4 semantic review `Semantic Questions` | covered |
| runtime remains fail-closed | `test_tree_plus_cascade_rejected` | covered |
| tree sibling constrained field remains fail-closed | `test_tree_sibling_limit_rejected` | covered |
| stable error prefix | both tests assert `PIVOT_CASCADE_TREE_REJECTED` | covered |
| standalone tree still unsupported | existing `test_grid_fail_closed_unsupported_features` | covered |
| no tree+cascade runtime support claimed | P4 decision says `accepted-deferred` | covered |

## Commands

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py -q
```

Result:

```text
19 passed in 0.87s
```

Regression commands:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/integration/test_pivot_v9_cascade_mysql57_matrix.py -q -rs
pytest -q
```

Results:

```text
35 passed in 1.48s
3943 passed in 11.79s
```

## Remaining Gaps

- No tree+cascade SQL oracle exists.
- No tree subtotal semantics are signed.
- No `expandDepth + TopN` precedence rule is signed.
- No production runtime support is claimed.

Coverage conclusion: passed for semantic-review-only P4.
