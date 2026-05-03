---
acceptance_scope: feature
version: v1.9
target: python-pivot-9.1-release-readiness
status: signed-off
decision: accepted-with-risks
signed_off_by: Python Engine Owner
signed_off_at: 2026-05-03
reviewed_by: Root Controller
blocking_items: []
follow_up_required: yes
evidence_count: 3
doc_role: acceptance-record
doc_purpose: Record Python Pivot 9.1 public contract and release readiness signoff.
---

# Python Pivot 9.1 Release Readiness

## Overview
This document serves as the final release readiness sign-off for the Python Pivot 9.1 engine, covering the implementation of Stage 5A (DomainTransport) and Stage 5B (Cascade Generate).

## Implemented Capability Matrix
| Feature | Status | Notes |
|---|---|---|
| Pivot Contract & DTO parsing | **Done** | Runtime supports flat/grid; tree remains a contract-compatible shape that fails closed in Python 9.1 |
| Fail-Closed Guardrails | **Done** | Strictly rejects cross-axis cascade, tree+cascade, derived-metric cascade, and MDX operators (CELL_AT/AXIS_MEMBER) |
| Stage 5A: DomainTransport | **Done** | Implemented dialect-specific NULL-safe domain mapping via CTE (`IS`, `IS NOT DISTINCT FROM`, `<=>`) |
| Stage 5B: Cascade Generate | **Done** | Implemented rows-axis two-level cascade via staged SQL. No memory fallback permitted. |
| Supported Dialects | **Done** | SQLite, MySQL 8, PostgreSQL |
| Subtotals / GrandTotal | **Deferred** | Not part of scoped P4 signoff; Python 9.1 fails closed instead of producing partial totals |
| Derived metrics in cascade | **Refused** | `parentShare` / `baselineRatio` with cascade fail closed in Python 9.1 |

## Test Evidence
- **Targeted Semantic Coverage:** `12 passed` (`test_pivot_v9_cascade_semantics.py` and `test_pivot_v9_cascade_real_db_matrix.py`).
- **Pivot Regression Suite:** `105 passed` (`test_pivot_v9_contract_shell.py`, `test_pivot_v9_flat.py`, `test_pivot_v9_grid.py`, `test_pivot_v9_cascade_validation.py`).
- **Full Engine Regression Suite:** `3928 passed` (All dirty CALCULATE-related test branches verified isolated).

*Verification commands:*
```bash
pytest tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/test_dataset_model/test_pivot_v9_grid.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py -q
```

## Dirty Worktree Exclusions
The following files are modified/untracked in the local workspace but deliberately ignored as they belong to in-progress parallel features (`CALCULATE`/`timeWindow`/`Compose Suspension`/`FieldValidator`), not Pivot 9.1:
- `src/foggy/dataset_model/semantic/formula_compiler.py`
- `src/foggy/dataset_model/engine/compose/runtime/suspension_manager.py`
- `src/foggy/dataset_model/semantic/field_validator.py`
- `src/foggy/dataset/dialects/base.py` & `mysql.py`
- Scratch testing scripts (e.g., `fix_*.py`)

## Accepted Risks
- **Subtotal/GrandTotal Omission**: Subtotal calculation is deferred, as it natively belongs to the `MemoryCubeProcessor` architecture, which was out of scope for the P4 SQL generator milestone.

## Deferred 9.2 Items
- Cascade subtotal and grandTotal computation logic.
- Tree hierarchy + Cascade implementation (`tree+cascade`).
- SQL Server cascade oracle parity.
- MySQL 5.7 fallback or live evidence validation.
- Outer Pivot Cache layer integration.
- Production telemetry and log-query integration examples.

## Conclusion
**Signoff Status: Ready for Release with documented risks.**
The public contract DSL schemas and markdown descriptions have been explicitly updated to align with the supported implementation boundaries. All accepted risks and deferred items have been documented.

## Signoff Marker
- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: Python Engine Owner
- signed_off_at: 2026-05-03
- acceptance_record: docs/v1.9/acceptance/python-pivot-9.1-release-readiness.md
- blocking_items: none
- follow_up_required: yes
