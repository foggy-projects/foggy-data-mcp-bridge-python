---
doc_role: quality-record
doc_purpose: 记录 v1.14 stable relation outer SQL Server live oracle 的实现质量检查结果
status: signed-off
---

# Stable Relation Outer SQL Server Quality

## Document Purpose

- doc_type: quality-record
- intended_for: reviewer / maintainer / root-controller
- purpose: 确认 v1.14 只补 SQL Server live oracle 证据，不扩大 runtime surface。

## Quality Review

| Area | Result | Notes |
|---|---|---|
| Public contract | pass | No schema, prompt, or public DSL change. |
| Runtime code | pass | No production runtime code change required. |
| Test isolation | pass | Reuses existing SQL Server demo fixture and skips only if executor/env unavailable. |
| Oracle strength | pass | Compares executed SQL Server results against handwritten SQL oracle. |
| SQL Server CTE handling | pass | Explicitly asserts `;WITH` for compiled hoisted CTE relation. |
| Regression risk | pass | Existing SQLite/MySQL8/PostgreSQL matrix remains in the same test file. |

## Risk Review

| Risk | Status | Mitigation |
|---|---|---|
| SQL Server fixture availability | accepted | Test reports skips through `-rs`; v1.14 signoff evidence used 0 skipped. |
| Result numeric type variation | mitigated | Decimal quantization only for cross-driver representation differences. |
| Pivot cascade SQL Server remains refusal-only | accepted | Separate Pivot boundary; not affected by stable relation outer runtime. |

## Conclusion

Implementation quality is acceptable. v1.14 closes a live runtime evidence gap without changing public behavior.
