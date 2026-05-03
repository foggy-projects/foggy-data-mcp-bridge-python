---
doc_role: quality-record
doc_purpose: 记录 v1.12 stable relation outer query runtime 实现质量判断与风险
status: signed-off
---

# Stable Relation Outer Runtime Quality

## Document Purpose

- doc_type: quality-record
- intended_for: implementation-owner / reviewer / root-controller
- purpose: 记录 v1.12 P1 runtime compiler 的实现边界、质量判断和剩余风险。

## Implementation Notes

- New internal module: `src/foggy/dataset_model/engine/compose/relation/outer_query.py`.
- Public exports are internal library exports only; MCP schema and public query_model/compose DSL are unchanged.
- The compiler returns `RelationOuterQuery(sql, params, output_schema)`.
- Validation uses existing `ComposeCompileError` and S7 error codes.
- SQL wrapping is structured around `RelationSql.with_items` and `RelationCapabilities`.

## Quality Assessment

| Area | Assessment |
|---|---|
| Scope control | Good. No public DSL change and no raw SQL passthrough. |
| Fail-closed behavior | Good. Unsupported function, unsafe identifier, missing policy, unsupported dialect capability all raise structured compile errors. |
| SQL assembly | Acceptable for controlled relation metadata. CTE hoist avoids `FROM (WITH` and preserves params order. |
| Schema propagation | Acceptable. Aggregate/window outputs carry semantic kind, lineage and reference policy. |
| Testability | Good. Runtime tests execute SQLite SQL and check dialect-specific refusal/markers. |

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Restricted frame string remains string-based | Could allow unsupported window frame variants | First pass rejects statement breaks; keep API internal until structured frame spec is needed. |
| No live MySQL8/PostgreSQL execution for relation outer query | Dialect runtime evidence is weaker than SQLite | Add live matrix only if product requires stable relation execution outside SQLite. |
| Identifier policy is strict safe-identifier only | Some exotic aliases are rejected | This is acceptable fail-closed behavior for parity-first runtime work. |

## Gate Evidence

Completed before v1.12 version signoff:

```powershell
pytest tests/compose/relation -q -rs
# 106 passed in 0.15s

pytest -q
# 3961 passed in 12.14s

git diff --check
# clean
```
