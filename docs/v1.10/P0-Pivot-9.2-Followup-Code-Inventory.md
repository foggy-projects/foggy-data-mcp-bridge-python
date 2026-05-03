# P0 Pivot 9.2 Follow-Up Code Inventory

## 文档作用

- doc_type: code-inventory
- intended_for: python-engine-agent / reviewer
- purpose: 列出 Python Pivot 9.2 follow-up 涉及的参考文档、源码触点、测试触点和预期改动类型。

## Java Reference Inventory

| Repo | Path | Role | Expected change | Notes |
|---|---|---|---|---|
| `foggy-data-mcp-bridge-wt-dev-compose` | `docs/9.2.0/README.md` | Java 9.2 follow-up roadmap | read-only-analysis | Python v1.10 主要外部基线。 |
| same | `docs/9.1.0/acceptance/version-signoff.md` | 9.1 accepted-with-risks 边界 | read-only-analysis | 确认哪些是 9.1 非阻断风险。 |
| same | `docs/9.1.0/detailed_design/13_pivot_stage5b_c2_implementation_plan.md` | C2 staged SQL 语义 | read-only-analysis | P1/P2/P3 oracle 参考。 |
| same | `docs/9.1.0/acceptance/pivot-stage5b-c2-cascade-generate-acceptance.md` | C2 签收证据 | read-only-analysis | 不扩大 9.1 已签收范围。 |

## Python Docs Inventory

| Repo | Path | Role | Expected change | Notes |
|---|---|---|---|---|
| `foggy-data-mcp-bridge-python` | `docs/v1.10/` | Python 9.2 planning package | create/update | 当前 P0 落点。 |
| same | `docs/v1.9/acceptance/python-pivot-9.1-release-readiness.md` | v1.9 risk baseline | read-only-analysis | P1-P6 均需引用。 |
| same | `docs/v1.9/coverage/pivot-stage5b-c2-cascade-coverage-audit.md` | 已覆盖/未覆盖矩阵 | read-only-analysis | 避免重复声称已覆盖。 |
| same | `src/foggy/mcp/schemas/query_model_v3_schema.json` | public contract | update only after implementation | 不提前开放未实现能力。 |
| same | `src/foggy/mcp/schemas/descriptions/query_model_v3*.md` | LLM prompt | update only after implementation or refusal wording change | 必须与 runtime 一致。 |

## Python Source Inventory

| Repo | Path | Role | Expected change | Notes |
|---|---|---|---|---|
| `foggy-data-mcp-bridge-python` | `src/foggy/dataset_model/semantic/pivot/executor.py` | Pivot validation / translation entry | update in P1 if totals are enabled | 继续保证 unsupported shape fail-closed。 |
| same | `src/foggy/dataset_model/semantic/pivot/cascade_detector.py` | cascade refusal categories | update in P1/P2/P3 | 新能力放行必须先补拒绝测试。 |
| same | `src/foggy/dataset_model/semantic/pivot/cascade_staged_sql.py` | C2 staged SQL planner | update in P1/P2/P3 | P1 可能需要 surviving domain total relation。 |
| same | `src/foggy/dataset_model/semantic/pivot/memory_cube.py` | having/TopN/crossjoin memory processor | update cautiously in P1 | 不允许作为 cascade ranking fallback；仅可处理 result shaping 后的 subtotal rows，前提是 oracle 明确。 |
| same | `src/foggy/dataset_model/semantic/pivot/grid_shaper.py` | grid result shaper | update in P1 if subtotal rows emitted | 需要保证 rowHeaders/cells 结构稳定。 |
| same | `src/foggy/dataset_model/semantic/pivot/domain_transport.py` | DomainTransport renderers | update in P2/P3 if dialect evidence added | SQL Server/MySQL5.7 探针可能涉及。 |
| same | `src/foggy/dataset/dialects/sqlserver.py` | SQL Server dialect | read/update in P2 | 仅在 P2 oracle 证明需要时更新。 |
| same | `src/foggy/dataset/dialects/mysql.py` | MySQL/MySQL8 capability distinction | read/update in P3 | 不得把 MySQL5.7 当 MySQL8。 |

## Python Test Inventory

| Repo | Path | Role | Expected change | Notes |
|---|---|---|---|---|
| `foggy-data-mcp-bridge-python` | `tests/test_dataset_model/test_pivot_v9_cascade_validation.py` | cascade refusal tests | update | P1/P2/P3 fail-closed matrix。 |
| same | `tests/test_dataset_model/test_pivot_v9_cascade_semantics.py` | cascade semantic unit tests | update | P1 subtotal/grandTotal semantic tests。 |
| same | `tests/integration/test_pivot_v9_cascade_real_db_matrix.py` | SQLite/MySQL8/Postgres oracle | update | P1 totals parity。 |
| same | `tests/integration/test_time_window_real_db_matrix.py` | external DB fixture examples | read-only-analysis | SQL Server profile 参考。 |
| same | `tests/test_dataset/test_dialects.py` | dialect unit tests | update in P2/P3 if needed | SQL Server/MySQL5.7 capability flags。 |

## Proposed New Files

| Path | Expected change | Purpose |
|---|---|---|
| `docs/v1.10/acceptance/pivot-9.2-cascade-totals-acceptance.md` | create in P1 signoff | P1 feature acceptance。 |
| `docs/v1.10/coverage/pivot-9.2-cascade-totals-coverage-audit.md` | create in P1 | P1 coverage audit。 |
| `docs/v1.10/quality/pivot-9.2-cascade-totals-quality.md` | create in P1 | P1 implementation quality gate。 |
| `tests/integration/test_pivot_v9_cascade_totals_real_db_matrix.py` | create or merge in P1 | 三库 totals oracle parity。 |
| `tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py` | create in P2 if SQL Server enabled | SQL Server oracle/refusal evidence。 |
| `tests/integration/test_pivot_v9_cascade_mysql57_matrix.py` | create in P3 if live profile exists | MySQL 5.7 evidence。 |

## Do Not Touch in P0

- Do not implement runtime features.
- Do not change public Pivot JSON shape.
- Do not relax fail-closed guards.
- Do not update schema/prompt to claim 9.2 behavior before tests pass.

