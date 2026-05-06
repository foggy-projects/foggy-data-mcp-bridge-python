# BUG · Compose derived plan `having` contract gap

## Document Purpose

- doc_type: design evaluation / workitem
- intended_for: compose-contract-owner / engine-maintainer / prompt-owner
- purpose: Evaluate whether `plan.query({...})` should support `having`, and how to handle same-stage aggregate alias filtering in derived queries.
- version: v1.16
- priority: P2
- status: ready-for-verification
- created_at: 2026-05-06

## Background

AR-014 benchmark question ("哪些客户连续两个月都存在逾期？") reproduced two compose errors in the `glm-5` high-variance run:

1. `QueryPlan.query() does not accept having; use slice for derived-plan post-result filters.`
2. `execute_sql failed: column cte_0.overdueMonths does not exist`

The LLM generated:

```javascript
const consecutiveOverdue = overdueByMonth.query({
  columns: [
    "partner$id", "partner$caption",
    "count(invoiceDate$month) as overdueMonths",
    "sum(arOverdueAmount) as totalOverdueAmount"
  ],
  groupBy: ["partner$id", "partner$caption"],
  having: [{ field: "overdueMonths", op: ">=", value: 2 }],
  orderBy: [{ field: "totalOverdueAmount", dir: "desc" }]
});
```

After the `having` rejection, the LLM changed to `slice`, but `overdueMonths` is a SELECT-stage alias of the current `.query()`, not a column from the source CTE. The compiler's `_render_slice` qualifies slice fields as `inner_alias.field_name` (e.g. `cte_0.overdueMonths`), which does not exist in the inner subquery's output.

The correct two-stage pattern is:

```javascript
const grouped = overdueByMonth.query({
  columns: ["partner$id", "partner$caption", "count(invoiceDate$month) as month_count"],
  groupBy: ["partner$id", "partner$caption"]
});
const filtered = grouped.query({
  slice: [{ field: "month_count", op: ">=", value: 2 }]
});
```

## Root Cause Analysis

### Error 1: `having` rejected by plan-build

- **Python**: `plan.py` line 394-398 — `QueryPlan.query()` accepts `having` as a parameter but immediately raises `ValueError` if it's truthy.
- **Python**: `dsl.py` line 137-141 — `from_(source=...)` has the same rejection.
- **Java**: `Dsl.java` line 91-93 — identical rejection.
- Both `DerivedQueryPlan` classes (Python and Java) do NOT have a `having` field.
- `BaseModelPlan` in both runtimes DOES support `having` — it's forwarded to the v1.3 engine which knows how to promote aggregate filters to SQL HAVING.

This is intentional design, not a bug. Base-model `having` works because the v1.3 engine has full access to the QM schema and can determine which filter fields are aggregate measures. Derived plans lack this context.

### Error 2: Same-stage alias in `slice` produces late SQL error

This IS a gap. The failure path:

1. `_render_outer_select` renders `SELECT ... count(invoiceDate$month) AS overdueMonths FROM (inner_sql) AS cte_0`
2. `_render_slice` renders `WHERE cte_0.overdueMonths > ?`
3. But `overdueMonths` is a SELECT alias of this outer query, not a column in `cte_0`'s output.
4. PostgreSQL rejects: `column cte_0.overdueMonths does not exist`.

Schema derivation (`derive.py`) validates `columns`, `group_by`, and `order_by` against the source output schema, but **does NOT validate `slice_` fields**. So the error escapes to SQL execution time.

## Evaluation: Four Design Options

### Option A: Keep current — no `having` on derived plans

- `plan.query()` and `dsl(source=...)` continue rejecting `having`.
- Document the two-stage pattern in tool descriptions.
- **Assessment**: Sound semantics, but does not address Error 2 (late SQL error on same-stage alias). The current error messages are clear for `having` rejection but opaque for same-stage alias misuse.

### Option B: `having` as `slice` alias on derived plans

- Accept `having` but silently convert to `slice` (i.e. WHERE on the source CTE output).
- Only works for fields that exist in the source schema, not for same-stage aliases.
- **Assessment**: Actively harmful. Calling it `having` but rendering it as WHERE creates a semantic trap. If the LLM sees `having` "working", it will assume it can filter on aggregate aliases — exactly the case it can't handle. This option makes the problem worse.

### Option C: Full SQL HAVING support on derived plans

- Add `having` field to `DerivedQueryPlan`.
- Compiler resolves aliases to expressions: `having: [{field: "overdueMonths", ...}]` → `HAVING COUNT(cte_0."invoiceDate$month") >= ?`.
- **Assessment**: High implementation complexity and risk.
  - Requires alias-to-expression reverse mapping in the compiler.
  - Must handle PostgreSQL alias visibility rules (HAVING cannot reference SELECT aliases directly in standard SQL; must repeat the aggregate expression).
  - Interacts with permission validation, dialect-specific identifier quoting, and camelCase folding.
  - Cross-repo parity burden: Python + Java + Odoo vendored runtime.
  - The use case (same-stage aggregate filter) is fully served by the two-stage pattern with zero SQL complexity.
  - Risk/reward ratio is poor.

### Option D: Add early schema validation for same-stage alias in `slice`

- At schema-derive or plan-build time, detect when `slice` references a column name that is a current-stage computed alias but does NOT exist in the source output schema.
- Raise a clear error: `"field '<alias>' is created by this derived query's SELECT and cannot be filtered in the same stage; add another .query({ slice: [...] })"`
- Continue requiring two-stage pattern for same-stage aggregate filtering.
- **Assessment**: Low risk, high value. Catches the most common LLM mistake at plan-build time with actionable guidance. The LLM can self-correct from this error message in one retry.

## Recommendation: Option A + D

**Keep the current contract (no `having` on derived plans) and add early schema-level validation for same-stage alias misuse in `slice`.**

### Rationale

1. **Semantic clarity**: Derived plans operate on a source plan's output. `slice` means "filter on source columns" (rendered as WHERE). `having` on a base model means "the engine decides if this is WHERE or HAVING based on QM metadata". Mixing `having` into derived plans where no QM metadata exists would create an inconsistent abstraction.

2. **LLM recovery**: The current `having` rejection error is already clear ("use slice for derived-plan post-result filters"). The missing piece is that the *second* error (same-stage alias in `slice`) gives a cryptic SQL message. Option D fixes exactly this gap: instead of `column cte_0.overdueMonths does not exist`, the LLM sees `field 'overdueMonths' is created by this derived query and cannot be filtered in the same stage; add another .query({ slice: [...] })`. This is directly actionable.

3. **Implementation simplicity**: Option D requires:
   - Extract current-stage alias names from `plan.columns` using the existing `extract_column_alias` function.
   - Subtract source schema column names (already computed in `_derive_derived`).
   - Check `plan.slice_` field references against the computed-alias set.
   - Raise `ComposeSchemaError` with the new error code and guidance message.
   - Estimated: ~30 lines of validation code in `derive.py`.

4. **Tool description already covers the contract**: `compose_script_m2.md` line 55 already says "如果某个 plan.query({...}) 同时新建聚合别名并要过滤该别名，先生成聚合 plan，再追加一层 .query()"

### Classification

- `plan.query({... having })` rejection: **Intentional contract**, not a BUG. No change needed.
- Same-stage alias in `slice` producing late SQL error: **BUG** (missing validation). Should be fixed with early schema error (Option D).

## Implementation Plan

### Python Changes

#### Schema validation (Option D core)

**File**: `src/foggy/dataset_model/engine/compose/schema/derive.py`

In `_derive_derived()`, after computing `source_names` and `parts_list`, add validation:

```python
# Detect same-stage alias references in slice
if plan.slice_:
    current_stage_aliases = set()
    for parts in parts_list:
        if parts.has_alias and parts.output_name not in source_names:
            current_stage_aliases.add(parts.output_name)
    
    if current_stage_aliases:
        for entry in plan.slice_:
            if isinstance(entry, dict):
                field_name = entry.get("field", next(iter(entry), None))
                if isinstance(field_name, str) and field_name in current_stage_aliases:
                    raise ComposeSchemaError(
                        code=error_codes.DERIVED_QUERY_SAME_STAGE_ALIAS,
                        message=(
                            f"field {field_name!r} is created by this derived "
                            f"query's SELECT and cannot be filtered in the same "
                            f"stage; add another .query({{ slice: "
                            f"[{{field: {field_name!r}, ...}}] }}) stage"
                        ),
                        phase=error_codes.PHASE_SCHEMA_DERIVE,
                        plan_path=current_path,
                        offending_field=field_name,
                    )
```

**File**: `src/foggy/dataset_model/engine/compose/schema/error_codes.py`

Add new error code:

```python
DERIVED_QUERY_SAME_STAGE_ALIAS = "derived-query/same-stage-alias"
```

#### Tests

**File**: `tests/compose/schema/test_derive.py` (or new file `tests/compose/schema/test_derived_slice_validation.py`)

1. Test: `plan.query({ columns: ["count(x) as month_count"], slice: [{field: "month_count", ...}] })` → raises `ComposeSchemaError` with `DERIVED_QUERY_SAME_STAGE_ALIAS`.
2. Test: `plan.query({ columns: ["count(x) as month_count"], slice: [{field: "existing_source_col", ...}] })` → no error (source column is valid).
3. Test: `plan.query({ columns: ["x"], slice: [{field: "x", ...}] })` → no error (passthrough column, not a new alias).

### Java Parity

The Java compose workspace at `foggy-data-mcp-bridge-wt-dev-compose` has the same `DerivedQueryPlan` shape and the same `Dsl.from(source=...)` rejection. Java schema derivation should add the same same-stage alias validation.

**Required**: Yes, Java parity workitem needed.

**Files**:
- `foggy-dataset-model/src/main/java/.../engine/compose/schema/DeriveSchema.java` — add slice field validation in `deriveDerived()`.
- `foggy-dataset-model/src/main/java/.../engine/compose/schema/ErrorCodes.java` — add `DERIVED_QUERY_SAME_STAGE_ALIAS`.
- Unit test mirroring the Python test above.

### Odoo Vendored Runtime Sync

If the Python `derive.py` change affects the Odoo vendored runtime (`foggy_mcp_pro`), it should be synced after the Python canonical implementation is verified. The vendored compose engine should exhibit the same early schema error.

No changes to QM metadata, prompt rules, or tool descriptions beyond what's already in `compose_script_m2.md` line 55.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| New validation rejects valid existing scripts | Low | Only triggers when slice references a current-stage computed alias not present in source schema — this always fails at SQL time today |
| False positive: user aliases a column to the same name as a source column | None | Such aliases are passthrough renames, not new aggregates; `parts.output_name not in source_names` guard prevents false positive |
| LLM still writes `having` and gets rejected | Medium | Already handled by existing error message; no regression from this change |
| Java parity delay | Medium | Java workitem should be tracked separately but is not blocking for Python |

## Verification Plan

### Automated Tests

```powershell
cd D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python
python -m pytest tests\compose\schema\test_derive.py -q
python -m pytest tests\compose\plan\test_derived_query_plan.py -q
python -m pytest tests\compose\compilation\test_derived.py -q
python -m pytest tests\compose\runtime\test_script_runtime.py -q
```

### Regression

Existing compose test suite should pass unchanged — the new validation catches a case that previously produced a late SQL error, not a case that previously succeeded.

## Execution Check-in - 2026-05-06

Status: implemented in Python canonical runtime.

Changed files:

- `src/foggy/dataset_model/engine/compose/schema/error_codes.py`
- `src/foggy/dataset_model/engine/compose/schema/derive.py`
- `tests/compose/schema/test_derived_slice_same_stage_alias.py`
- `tests/compose/schema/test_schema_errors.py`

Verification:

- `python -m pytest tests\compose\schema\test_derived_slice_same_stage_alias.py tests\compose\schema\test_schema_errors.py tests\compose\schema tests\compose\compilation\test_derived.py tests\compose\runtime\test_script_runtime.py -q` -> 150 passed.
- `python -m pytest -q` -> 4100 passed, 4 failed. The 4 failures are outside this compose change path:
  - `tests/test_dataset_model/test_pivot_v9_contract_shell.py::test_query_model_v3_schema_exposes_pivot_contract_and_guards`
  - `tests/test_dataset_model/test_pivot_v9_contract_shell.py::test_query_model_description_variants_keep_python_pivot_boundaries`
  - `tests/test_dataset_model/test_python_gaps.py::TestFieldReference::test_field_reference_gt`
  - `tests/test_dataset_model/test_python_gaps.py::TestFieldReference::test_field_reference_no_bind_params`

Next verification steps:

- Sync the verified Python runtime files into `foggy-odoo-bridge-pro/foggy_mcp_pro/lib/foggy/...`.
- Run the Odoo embedded backend contract tests after sync.
- Track Java parity separately for `DeriveSchema.java` / `ErrorCodes.java`.

## Related Work

- `BUG-ar014-compose-join-duplicate-measure-alias-and-empty-probing.md`
- `OPT-qm-semantic-best-practice-separation.md`
- `compose_script_m2.md` line 55 (existing tool description guidance)
- Python commit `5481b57 docs: clarify derived compose filtering contract`
- Odoo commit `628ca1c docs: record glm47 high variance rerun`

## Summary

| Question | Answer |
|----------|--------|
| Should `plan.query()` support `having`? | **No.** Intentional contract boundary. |
| Classification of `having` rejection? | **Not a bug.** Explicit contract. |
| Classification of same-stage alias in `slice`? | **BUG.** Missing early validation. |
| Recommended design? | **A + D**: Keep no-`having` contract; add early schema error for same-stage alias. |
| Code changes needed? | Yes — `derive.py` + `error_codes.py` + tests. |
| Java parity needed? | Yes — separate workitem for `DeriveSchema.java`. |
| QM metadata changes? | None. |
| Odoo vendored sync? | After Python canonical is verified. |
