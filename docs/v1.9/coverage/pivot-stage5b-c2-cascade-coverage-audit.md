---
audit_scope: feature
audit_mode: pre-acceptance-check
version: v1.9
target: pivot-stage5b-c2-cascade
status: reviewed
conclusion: ready-for-acceptance
reviewed_by: root-controller
reviewed_at: 2026-05-03
follow_up_required: yes
---

# Test Coverage Audit

## Background

This audit maps the scoped Python Pivot 9.1 Stage 5B C2 requirements to test
evidence. The feature covers rows-axis exactly two-level cascade TopN with
additive native metrics and staged SQL execution. Unsupported shapes remain
fail-closed.

## Audit Basis

- `docs/v1.9/P0-Pivot-9.1-Java-Parity-Requirement.md`
- `docs/v1.9/P0-Pivot-9.1-Java-Parity-Implementation-Plan.md`
- `docs/v1.9/P0-Pivot-9.1-Java-Parity-progress.md`
- `tests/test_dataset_model/test_pivot_v9_cascade_validation.py`
- `tests/test_dataset_model/test_pivot_v9_cascade_semantics.py`
- `tests/integration/test_pivot_v9_cascade_real_db_matrix.py`
- `tests/test_dataset_model/test_pivot_v9_domain_transport.py`
- `tests/test_dataset_model/test_pivot_v9_domain_transport_query_model.py`
- `tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py`

## Coverage Matrix

| Requirement / acceptance item | Risk | Evidence layer | Evidence | Conclusion |
|---|---|---|---|---|
| Parent TopN + child TopN returns children only under surviving parents | critical | integration-test | `test_cascade_two_level_topn` in `test_pivot_v9_cascade_real_db_matrix.py` | covered |
| Real SQL oracle parity across SQLite, MySQL8, PostgreSQL | critical | integration-test | `test_pivot_v9_cascade_real_db_matrix.py`, 2 tests x 3 DBs, 0 skipped | covered |
| Parent ranking ignores child limit | critical | unit/integration-test | `test_parent_rank_unaffected_by_child_limit` | covered |
| Parent having runs before child rank | major | unit/integration-test | `test_parent_having_before_child_rank` | covered |
| Child having does not promote another parent | major | unit/integration-test | `test_child_having_not_affecting_parent` | covered |
| Deterministic NULL handling and tie behavior | major | unit/integration-test | `test_null_tie_breaking`, `test_cascade_null_parent_dimension` | covered |
| Missing orderBy on limited cascade rejects | major | unit-test | `test_missing_order_by_on_cascade_limit_rejected` | covered |
| Columns-axis cascade rejects | critical | unit-test | `test_columns_cascade_rejected`, `test_columns_having_rejected` | covered |
| Tree + cascade rejects | critical | unit-test | `test_tree_plus_cascade_rejected` | covered |
| Three-level cascade rejects | critical | unit-test | `test_three_level_cascade_rejected` | covered |
| Having-only / mixed unsupported cascade rejects | major | unit-test | `test_parent_having_plus_child_topn_rejected`, `test_parent_topn_plus_child_having_rejected` | covered |
| Non-additive / derived metrics reject | critical | unit-test | `test_non_additive_cascade_rejected`, `test_derived_metric_with_cascade_rejected`, `test_baseline_ratio_with_cascade_rejected`, `test_non_additive_cascade_rejection` | covered |
| Unsupported dialect rejects with no memory fallback | major | unit-test | `test_unsupported_dialect_fallback_rejection` | covered |
| Existing S3 Pivot behavior does not regress | major | unit/integration-test | `test_pivot_v9_contract_shell.py`, `test_pivot_v9_flat.py`, `test_pivot_v9_grid.py`, S3 regression tests in cascade validation | covered |
| Stage 5A DomainTransport remains covered | major | unit/integration-test | domain transport unit/queryModel/real DB matrix tests | covered |
| Full repository regression | critical | automated-test | `pytest -q` -> 3928 passed | covered |
| Cascade subtotal/grandTotal rows | major | N/A | Deferred out of scoped P4 signoff | not-covered / deferred |

## Evidence Summary

Executed verification:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
```

Result: `12 passed, 0 skipped`.

```powershell
pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/test_dataset_model/test_pivot_v9_grid.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_domain_transport.py tests/test_dataset_model/test_pivot_v9_domain_transport_query_model.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
```

Result: `105 passed, 0 skipped`.

```powershell
pytest -q
```

Result: `3928 passed`.

```powershell
git diff --check
```

Result: clean, with Windows CRLF warnings only.

## Gaps

- Cascade subtotal/grandTotal row parity is deferred to Python 9.2.
- SQL Server cascade oracle and MySQL 5.7 live evidence remain deferred.
- Telemetry dashboards and production log-query examples remain deferred.

## Recommended Next Skills

- `foggy-acceptance-signoff`

## Conclusion

Conclusion: `ready-for-acceptance`.

The scoped Stage 5B C2 cascade feature has sufficient automated evidence for
formal feature acceptance, with explicit follow-up required for cascade totals.
