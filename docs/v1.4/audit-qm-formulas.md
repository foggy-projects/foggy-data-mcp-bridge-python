# QM Formula Compatibility Audit

Scan roots:

- `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo` (ok)
- `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models` (ok)

## Summary

- QM files with formulas: **19**
- Formula expressions: **27**
- Compiler-compatible: **23**
- Compiler-incompatible: **4**
- `filter_condition` usages: **0**  (expected 0)

## Per-file breakdown

| QM file | formulas | pass | fail | filter_condition |
|---|---:|---:|---:|---:|
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\ecommerce\query\FactSalesQueryModel.qm` | 3 | 1 | 2 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooAccountMoveLineQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooAccountMoveQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooAccountPaymentQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooCrmLeadQueryModel.qm` | 2 | 2 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooMrpProductionQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooProjectTaskQueryModel.qm` | 1 | 0 | 1 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooPurchaseOrderQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooSaleOrderLineQueryModel.qm` | 3 | 3 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooSaleOrderQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooAccountMoveLineQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooAccountMoveQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooAccountPaymentQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooCrmLeadQueryModel.qm` | 2 | 2 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooMrpProductionQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooProjectTaskQueryModel.qm` | 1 | 0 | 1 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooPurchaseOrderQueryModel.qm` | 1 | 1 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooSaleOrderLineQueryModel.qm` | 3 | 3 | 0 | 0 |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooSaleOrderQueryModel.qm` | 1 | 1 | 0 | 0 |

## Incompatible formulas

Each row is a formula the compiler rejected.  Fix before removing the legacy string-substitution fallback.

| QM file | line | expression | error |
|---|---:|---|---|
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\ecommerce\query\FactSalesQueryModel.qm` | 116 | `RANK()` | FormulaFunctionNotAllowedError: Function 'RANK' is not allowed in formula expression. Allowed: abs, avg, between, ceil, coalesce, count, date_add, date_diff, ... |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\ecommerce\query\FactSalesQueryModel.qm` | 124 | `AVG(salesAmount)` | FormulaFunctionNotAllowedError: Function 'AVG' is not allowed in formula expression. Allowed: abs, avg, between, ceil, coalesce, count, date_add, date_diff, ... |
| `D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python\src\foggy\demo\models\odoo\query\OdooProjectTaskQueryModel.qm` | 66 | `(taskCount WHERE state = "1_done") / taskCount * 100` | FormulaSyntaxError: Invalid formula syntax: Expected RPAREN, but got IDENTIFIER |
| `D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro\foggy_mcp_pro\setup\foggy-models\query\OdooProjectTaskQueryModel.qm` | 66 | `(taskCount WHERE state = "1_done") / taskCount * 100` | FormulaSyntaxError: Invalid formula syntax: Expected RPAREN, but got IDENTIFIER |
