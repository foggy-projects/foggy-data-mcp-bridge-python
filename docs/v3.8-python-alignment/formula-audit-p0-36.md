# QM Formula Compatibility Audit

Scan roots:

- `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo` (ok)

## Summary

- QM files with formulas: **8**
- Formula expressions: **17**
- Compiler-compatible: **15**
- Compiler-incompatible: **0**
- Window-formula skipped: **2**
- `filter_condition` usages: **0**  (expected 0)

## Per-file breakdown

| QM file | formulas | pass | fail | skip | filter_condition |
|---|---:|---:|---:|---:|---:|
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/ecommerce/query/FactSalesQueryModel.qm` | 3 | 1 | 0 | 2 | 0 |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/odoo/query/OdooAccountMoveLineQueryModel.qm` | 4 | 4 | 0 | 0 | 0 |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/odoo/query/OdooAccountMoveQueryModel.qm` | 2 | 2 | 0 | 0 | 0 |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/odoo/query/OdooAccountPaymentQueryModel.qm` | 1 | 1 | 0 | 0 | 0 |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/odoo/query/OdooCrmLeadQueryModel.qm` | 2 | 2 | 0 | 0 | 0 |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/odoo/query/OdooPurchaseOrderQueryModel.qm` | 1 | 1 | 0 | 0 | 0 |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/odoo/query/OdooSaleOrderLineQueryModel.qm` | 3 | 3 | 0 | 0 | 0 |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/odoo/query/OdooSaleOrderQueryModel.qm` | 1 | 1 | 0 | 0 | 0 |

## Skipped window formulas

These formulas have window metadata and are validated by the
window-function query path instead of the scalar/aggregate
FormulaCompiler whitelist audit.

| QM file | line | expression | reason |
|---|---:|---|---|
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/ecommerce/query/FactSalesQueryModel.qm` | 116 | `RANK()` | window formula; covered by window-function path |
| `/Users/fengjianguang/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/demo/models/ecommerce/query/FactSalesQueryModel.qm` | 124 | `AVG(salesAmount)` | window formula; covered by window-function path |
