# P0 Pivot 9.1 Java Parity Code Inventory

## 文档作用

- doc_type: code-inventory
- intended_for: python-engine-agent / reviewer
- purpose: 列出 Python v1.9 Pivot 9.1 parity 规划涉及的参考文档、源码触点、测试触点和预期改动类型。

## Java Reference Inventory

| Repo | Path | Role | Expected change | Notes |
|---|---|---|---|---|
| `foggy-data-mcp-bridge-wt-dev-compose` | `CLAUDE.md` | Java repo lifecycle / test expectations | read-only-analysis | 当前工作区文件树不是 9.1 签收态，需以 commit/tag 读取签收文件。 |
| `foggy-data-mcp-bridge-wt-dev-compose` | `docs/9.1.0/acceptance/version-signoff.md` | 9.1 RC2 签收边界 | read-only-analysis | 从 `10e863e9` 读取。 |
| same | `docs/9.1.0/detailed_design/10_pivot_stage5a_domain_transport_plan.md` | Stage 5A transport 设计 | read-only-analysis | 不改 Python DSL。 |
| same | `docs/9.1.0/detailed_design/12_pivot_stage5b_cascade_generate_disambiguation.md` | C1.1 语义与拒绝边界 | read-only-analysis | P1/P4 主要参考。 |
| same | `docs/9.1.0/detailed_design/13_pivot_stage5b_c2_implementation_plan.md` | C2 实施与测试矩阵 | read-only-analysis | P4 主要参考。 |
| same | `docs/9.1.0/detailed_design/14_llm_query_tool_capability_matrix.md` | LLM routing guidance | read-only-analysis | P0 文档/prompt 对齐。 |
| same | `docs/9.2.0/README.md` | 延后项 | read-only-analysis | Python 9.2 follow-up 对齐。 |

## Python Source Inventory

| Repo | Path | Role | Expected change | Notes |
|---|---|---|---|---|
| `foggy-data-mcp-bridge-python` | `docs/v1.9/` | Python 9.1 parity 文档包 | create | 当前 P0 落点。 |
| same | `src/foggy/mcp_spi/semantic.py` | Pivot DTO | update in P1 if needed | 当前已有 `PivotRequest/PivotAxisField/PivotMetricItem`。 |
| same | `src/foggy/mcp/schemas/query_model_v3_schema.json` | MCP schema | update only if validation contract missing | 不新增公开 DSL。 |
| same | `src/foggy/mcp/schemas/descriptions/query_model_v3*.md` | LLM prompt | update in P1/P5 | 对齐 Java 9.1 routing/fail-closed guidance。 |
| same | `src/foggy/dataset_model/semantic/pivot/executor.py` | Pivot validation + translation | update in P1 | 增加 cascade detector/refusal；禁止 cascade 进入内存路径。 |
| same | `src/foggy/dataset_model/semantic/pivot/memory_cube.py` | S3 memory having/TopN/crossjoin | update only for guard | 不把它扩展成 C2 fallback。 |
| same | `src/foggy/dataset_model/semantic/pivot/grid_shaper.py` | Grid shaping | likely no P1 change | P4 totals 可能涉及 shape，但 P1 不改。 |
| same | `src/foggy/dataset_model/semantic/service.py` | queryModel execution lifecycle | read/update in P1/P2 | P2 需评估 managed relation 可行性。 |
| same | `src/foggy/dataset_model/engine/compose/relation/*` | stable relation mirror | read-only-analysis first | 只是 compose relation mirror，不等价于 Pivot managed relation。 |
| same | `src/foggy/dataset_model/engine/preagg/*` | preAgg support | read-only-analysis in P2 | Stage 5A/C2 必须确认不会绕过。 |

## Python Test Inventory

| Repo | Path | Role | Expected change | Notes |
|---|---|---|---|---|
| `foggy-data-mcp-bridge-python` | `tests/test_dataset_model/test_pivot_v9_contract_shell.py` | Pivot contract/fail-closed | update | P1 增加 cascade refusal。 |
| same | `tests/test_dataset_model/test_pivot_v9_flat.py` | SQLite flat oracle parity | keep green | 不应回归。 |
| same | `tests/test_dataset_model/test_pivot_v9_grid.py` | SQLite grid oracle parity | update/keep green | P1 验证单层 TopN 不误拒绝。 |
| same | `tests/integration/test_pivot_v9_flat_real_db_matrix.py` | MySQL8/Postgres flat parity | keep green | 外部 DB 可用时运行。 |
| same | `tests/integration/test_pivot_v9_grid_real_db_matrix.py` | MySQL8/Postgres grid parity | keep green | 外部 DB 可用时运行。 |
| same | `tests/test_dataset_model/test_time_window*.py` | timeWindow parity | keep green | `pivot + timeWindow` 仍拒绝。 |
| same | `tests/compose/relation/*` | stable relation snapshot | read-only-analysis | P2 判断 relation lifecycle 能力。 |

## Proposed New Test Files

| Path | Expected change | Purpose |
|---|---|---|
| `tests/test_dataset_model/test_pivot_v9_cascade_validation.py` | create in P1 | 覆盖 `PIVOT_CASCADE_*` refusal matrix。 |
| `tests/test_dataset_model/test_pivot_v9_managed_relation_feasibility.py` | create in P2 if needed | 验证 queryModel relation wrapping 前置能力。 |
| `tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py` | create in P3 only | Stage 5A 三库 oracle parity。 |
| `tests/integration/test_pivot_v9_cascade_real_db_matrix.py` | create in P4 only | C2 三库 oracle parity。 |

## Do Not Touch in P1

- Do not implement Stage 5A transport.
- Do not implement C2 staged SQL planner.
- Do not change public Pivot JSON shape.
- Do not route Pivot through compose/CTE to bypass queryModel governance.
