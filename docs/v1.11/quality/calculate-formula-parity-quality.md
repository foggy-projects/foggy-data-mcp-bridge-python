# CALCULATE / Formula Parity Quality Record

## 文档作用

- doc_type: quality-record
- status: passed
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 v1.11 P1 CALCULATE / formula parity 的实现质量检查、风险和边界。

## Code Changes Reviewed

| File | Change | Quality Note |
|---|---|---|
| `src/foggy/dataset/dialects/mysql.py` | added `MySql8Dialect` capability profile | scoped capability flag; keeps base MySQL fail-closed |
| `src/foggy/dataset/dialects/__init__.py` | exported `MySql8Dialect` | makes profile reusable outside tests |
| `tests/test_dataset_model/test_calculate_mvp_parity_catalog.py` | catalog path moved to repo root | removes parent-workspace dependency |
| `docs/v1.5.1/P1-CALCULATE-restricted-mvp-parity-catalog.json` | repo-local catalog copy | preserves historical catalog evidence |
| `tests/integration/test_calculate_mvp_real_db_matrix.py` | new three-DB oracle parity | verifies executed result values, not only SQL text |

## Design Check

- No public DSL change.
- No expansion beyond restricted `CALCULATE(SUM(metric), REMOVE(groupByDim...))`.
- Unsupported shapes continue to fail closed through `FormulaSyntaxError` codes.
- MySQL 8 support is capability-profile based. The base `mysql` dialect remains conservative for MySQL 5.7 deployments.
- Oracle tests compare real query_model execution output with handwritten SQL, including both global share and partitioned share.

## Residual Risks

| Risk | Impact | Disposition |
|---|---|---|
| Automatic MySQL server-version detection is not implemented | Deployments using MySQL 8 must opt into `MySql8Dialect` instead of relying on executor inference | accepted profile note |
| Full formula language parity is broader than CALCULATE MVP | This P1 only signs off the public restricted CALCULATE subset | out of scope |
| SQL Server grouped aggregate window evidence is not included | No public SQL Server CALCULATE parity claim in v1.11 P1 | deferred/refusal until requested |

## Decision

Implementation quality is sufficient for P1 acceptance.
