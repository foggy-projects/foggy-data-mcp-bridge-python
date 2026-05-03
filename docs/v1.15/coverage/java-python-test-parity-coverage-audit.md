---
audit_scope: version
audit_mode: post-acceptance-regression-review
version: v1.15
target: java-python-engine-parity-baseline
status: reviewed
conclusion: ready-with-gaps
reviewed_by: root-controller
reviewed_at: 2026-05-03
follow_up_required: yes
---

# Test Coverage Audit

## Background

This audit reviews whether Python engine test evidence is aligned with the current Java accepted boundary.

Java reference boundary:

- Java Pivot Engine 9.1.0 RC2: accepted with risks.
- Java 9.2.0 roadmap: SQL Server cascade, MySQL 5.7 live evidence, tree+cascade, outer Pivot cache, and telemetry dashboards remain follow-ups.

Python reference boundary:

- v1.9: Pivot Stage 5A / Stage 5B rows two-level cascade.
- v1.10: Pivot 9.2 follow-up subset: cascade totals, SQL Server refusal, MySQL5.7 refusal, tree+cascade semantic review, outer cache feasibility, telemetry docs.
- v1.11: CALCULATE, timeWindow, governance, compose boundary.
- v1.12-v1.14: stable relation outer aggregate/window runtime evidence through SQL Server.

## Audit Basis

- `docs/v1.9/acceptance/pivot-stage5b-c2-cascade-acceptance.md`
- `docs/v1.10/acceptance/version-signoff.md`
- `docs/v1.11/acceptance/version-signoff.md`
- `docs/v1.12/acceptance/version-signoff.md`
- `docs/v1.13/acceptance/version-signoff.md`
- `docs/v1.14/acceptance/version-signoff.md`
- Java: `docs/9.1.0/acceptance/version-signoff.md`
- Java: `docs/9.1.0/test_coverage/pivot-stage5b-c2-cascade-generate-coverage-audit.md`
- Java: `docs/9.2.0/README.md`

## Coverage Matrix

| Capability / Contract | Java Status | Python Evidence | Coverage Result |
|---|---|---|---|
| queryModel lifecycle preservation | accepted | v1.11 governance cross-path tests, compose binding tests, Pivot DomainTransport schema isolation | covered |
| systemSlice / deniedColumns / fieldAccess | accepted | v1.11 `215 passed` governance matrix plus MCP router checks | covered |
| restricted CALCULATE | accepted restricted subset | v1.11 `19 passed`, SQLite/MySQL8/PostgreSQL oracle; conservative MySQL fail-closed | covered with profile note |
| timeWindow current subset | accepted | v1.11 `111 passed` plus `timeWindow + pivot` refusal; SQLite/MySQL8/PostgreSQL/SQL Server matrix | covered |
| Pivot flat/grid and axis memory processing | accepted | v1.8/v1.9 flat/grid real SQL parity and regression suites | covered |
| Pivot Stage 5A DomainTransport | accepted with risks | v1.9 SQLite/MySQL8/PostgreSQL real DB oracle; v1.10 MySQL5.7 refusal | covered for supported dialects |
| Pivot Stage 5B rows two-level cascade | accepted with risks | v1.9 `12 passed` semantic/oracle, `105 passed` Pivot regression; v1.10 cascade totals `39 passed` | covered for supported dialects |
| Cascade subtotal/grandTotal over surviving domain | Java accepted in C2 scope | Python v1.10 P1 accepted with surviving-domain tests | covered |
| SQL Server cascade | Java refused/deferred | Python v1.10 SQL Server refusal tests `8 passed`, no runtime oracle claimed | aligned refusal |
| MySQL 5.7 cascade / large-domain transport | Java guarded/deferred | Python v1.10 MySQL5.7 refusal tests `2 passed`, no oracle claimed | aligned refusal |
| tree+cascade | Java deferred/refused | Python v1.10 semantic review and runtime refusal | aligned deferred |
| outer Pivot cache | Java deferred | Python v1.10 feasibility only, no runtime cache | aligned deferred |
| stable relation outer aggregate/window | Java reference capability | Python v1.12 SQLite runtime, v1.13 SQLite/MySQL8/PostgreSQL, v1.14 SQL Server; `16 passed` matrix and `3977 passed` full regression | covered |
| CTE / compose separation | accepted routing boundary | v1.11 compose boundary acceptance and stable relation runtime docs | covered for accepted paths |
| public DSL schema / prompt boundaries | accepted guardrail | v1.9 release readiness and later schema/prompt updates; fail-closed MDX operators documented | covered |

## Evidence Summary

Python evidence already recorded:

- Pivot v1.9 cascade signoff: `pytest -q` -> `3928 passed`.
- Pivot v1.10 follow-up signoff: latest recorded full regression -> `3943 passed`.
- Engine v1.11 parity signoff: latest recorded full regression -> `3952 passed`.
- Stable relation v1.12 signoff: `pytest -q` -> `3961 passed`.
- Stable relation v1.13 signoff: `pytest -q` -> `3973 passed`.
- Stable relation v1.14 signoff: `pytest -q` -> `3977 passed`.

Latest local verification for this v1.15 audit is recorded in `docs/v1.15/acceptance/java-python-engine-parity-baseline.md`.

v1.15 verification results:

- `pytest tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs` -> `16 passed in 1.21s`.
- `pytest tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/integration/test_pivot_v9_cascade_mysql57_matrix.py -q -rs` -> `44 passed in 1.66s`.
- `pytest -q` -> `3977 passed in 17.98s`.

## Gaps

| Gap | Blocking Current Parity? | Required Before Support Claim |
|---|---|---|
| SQL Server Pivot cascade oracle | no | SQL Server-specific staged SQL renderer, NULL-safe tuple predicate proof, live oracle matrix. |
| MySQL 5.7 live cascade / transport evidence | no | Dedicated MySQL 5.7 fixture or formal product decision to keep unsupported. |
| tree+cascade runtime | no | Signed semantic spec, rows/tree oracle matrix, subtotal/tree visibility rules. |
| outer Pivot cache | no | Permission-aware cache key, invalidation policy, telemetry, hit/miss correctness tests. |
| Stable relation join / union as source | no | Separate requirement and oracle matrix; current S7e/S7f outer query evidence is complete. |
| CALCULATE SQL Server real DB oracle | no | Only needed if SQL Server CALCULATE is promoted to an explicit parity claim. |

## Recommended Next Skills

- Use `foggy-plan-execution-docs` before implementing any currently deferred runtime capability.
- Use `foggy-test-coverage-audit` again after adding SQL Server cascade, MySQL5.7 live evidence, tree+cascade, or outer Pivot cache tests.
- Use `foggy-acceptance-signoff` before claiming support for any deferred item.

## Conclusion

`ready-with-gaps`

Python and Java are functionally aligned for the current signed public/runtime scope. Remaining gaps are not hidden defects; they are explicit refusal or deferred areas shared with the Java accepted-with-risks boundary, plus one optional Python-specific CALCULATE SQL Server evidence follow-up.
