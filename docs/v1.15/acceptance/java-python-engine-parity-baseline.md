---
acceptance_scope: version
version: v1.15
target: java-python-engine-parity-baseline
doc_role: acceptance-record
doc_purpose: Record Python engine v1.15 Java/Python functional parity baseline and remaining test gaps.
status: signed-off
decision: accepted-with-risks
signed_off_by: root-controller
signed_off_at: 2026-05-03
reviewed_by: root-controller
blocking_items: []
follow_up_required: yes
evidence_count: 8
---

# Version Acceptance

## Background

v1.15 closes the current Java/Python engine parity review after the Python Pivot, timeWindow, CALCULATE, governance, compose, and stable relation evidence refreshes.

This is a documentation and acceptance baseline. It does not add runtime behavior, expand public Pivot DSL, or claim MDX compatibility.

The acceptance principle remains correctness-first:

- Supported paths need executable oracle or regression evidence.
- Unsupported or ambiguous paths must fail closed.
- Java deferred items must not be presented as Python-supported shortcuts.

## Acceptance Basis

- `docs/v1.15/README.md`
- `docs/v1.15/coverage/java-python-test-parity-coverage-audit.md`
- Python v1.9-v1.14 acceptance records
- Java `docs/9.1.0/acceptance/version-signoff.md`
- Java `docs/9.2.0/README.md`

## Module Summary

| Module / Area | Python Status | Decision | Notes |
|---|---|---|---|
| base queryModel lifecycle and governance | signed-off | accepted | systemSlice, deniedColumns, visible fields, masking, MCP routing covered in v1.11. |
| restricted CALCULATE | signed-off | accepted-with-profile-note | SQLite/MySQL8/PostgreSQL oracle; conservative MySQL remains fail-closed. |
| timeWindow | signed-off | accepted | SQLite/MySQL8/PostgreSQL/SQL Server matrix refreshed in v1.11. |
| Pivot Stage 5A DomainTransport | signed-off | accepted-with-risks | SQLite/MySQL8/PostgreSQL oracle; MySQL5.7 refusal aligned. |
| Pivot Stage 5B cascade | signed-off | accepted-with-risks | rows two-level cascade and cascade totals covered; SQL Server/tree/deeper cases refused/deferred. |
| stable relation outer aggregate/window | signed-off | accepted | SQLite/MySQL8/PostgreSQL/SQL Server live oracle complete by v1.14. |
| CTE / compose boundary | signed-off | accepted-with-boundary | Accepted runtime paths preserve authority and do not bypass queryModel lifecycle. |
| deferred Java 9.2 items | tracked | accepted-deferred/refusal | SQL Server cascade, MySQL5.7 live evidence, tree+cascade, outer Pivot cache. |

## Checklist

- [x] Java 9.1.0 accepted-with-risks boundary reviewed.
- [x] Java 9.2.0 follow-up roadmap reviewed.
- [x] Python v1.9-v1.14 acceptance records reviewed.
- [x] Supported Python paths have current test evidence.
- [x] Unsupported or deferred Python paths match Java refusal/deferred boundaries.
- [x] Stable relation outer runtime evidence has been refreshed through SQL Server.
- [x] Remaining missing tests are explicitly listed and are not current blockers.
- [x] No runtime code or public DSL changed in v1.15.

## Evidence

Historical signed evidence:

- Python Pivot v1.9: `pytest -q` -> `3928 passed`.
- Python Pivot v1.10: latest recorded full regression -> `3943 passed`.
- Python engine v1.11: latest recorded full regression -> `3952 passed`.
- Python stable relation v1.12: `pytest -q` -> `3961 passed`.
- Python stable relation v1.13: `pytest -q` -> `3973 passed`.
- Python stable relation v1.14: `pytest -q` -> `3977 passed`.
- Java 9.1.0 RC2: Stage 5A and C2 gates recorded as PASS in `docs/9.1.0/acceptance/version-signoff.md`.

v1.15 local verification:

```powershell
pytest tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 16 passed in 1.21s

pytest tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/integration/test_pivot_v9_cascade_mysql57_matrix.py -q -rs
# 44 passed in 1.66s

pytest -q
# 3977 passed in 17.98s
```

## Risks / Open Items

| Item | Status | Functional Impact |
|---|---|---|
| SQL Server Pivot cascade oracle | deferred/refused | SQL Server cascade requests remain refused; users must simplify or use supported dialects. |
| MySQL 5.7 live evidence | deferred/refused | MySQL5.7 cannot inherit MySQL8 cascade/domain behavior. |
| tree+cascade | deferred/refused | Tree-shaped top children per parent stays rejected until semantic oracle exists. |
| outer Pivot cache | deferred | Correctness unaffected; repeated expensive Pivot queries may not get extra cache acceleration. |
| Stable relation join / union source | not in current scope | Outer aggregate/window is complete; join/union as source requires separate requirement. |
| CALCULATE SQL Server oracle | optional follow-up | Current signed CALCULATE oracle is SQLite/MySQL8/PostgreSQL; SQL Server needs explicit product claim before adding. |

## Final Decision

Python engine v1.15 Java/Python parity baseline is **accepted with risks**.

Functionally, the Python engine is aligned with the Java engine for the current accepted runtime/public contract: supported paths have evidence, unsupported paths refuse explicitly, and Java 9.2 deferred work remains deferred in Python rather than being approximated.

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: root-controller
- signed_off_at: 2026-05-03
- acceptance_record: `docs/v1.15/acceptance/java-python-engine-parity-baseline.md`
- coverage_record: `docs/v1.15/coverage/java-python-test-parity-coverage-audit.md`
- blocking_items: none
- follow_up_required: yes
