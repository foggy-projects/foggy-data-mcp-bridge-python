# S1-F7 Datasource Identity Contract — Progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer / signoff-owner
- purpose: 记录 post-v1.5 Stage 1 F-7 datasource identity contract 的 Python 实现、测试证据、剩余 Java 镜像工作和验收准备状态

**Status**: ✅ Python implementation complete | ⏳ Java implementation pending

## Contract Decision

**Option B: `ModelInfoProvider.get_datasource_id(model_name, namespace) → Optional[str]`**

Rationale:
- `ModelBinding` is a frozen contract shared with Odoo Pro — adding a field there
  would require updating initialization, resolution, and Python/Java sync.
- `ModelInfoProvider` is the host-facing injection point already scoped to model
  identity lookups. Adding a second lookup method is the minimal-impact path.
- Datasource IDs are stored in a **separate dict** (`Dict[str, Optional[str]]`)
  passed alongside bindings to the compiler, keeping the `ModelBinding` frozen.

## Python Changes

| File | Change |
|------|--------|
| `authority/model_info.py` | Added `get_datasource_id()` to `ModelInfoProvider` Protocol and `NullModelInfoProvider` |
| `authority/datasource_ids.py` | **NEW** — `collect_datasource_ids(plan, provider, namespace)` utility |
| `authority/__init__.py` | Export `collect_datasource_ids` |
| `compilation/compiler.py` | Added `datasource_ids` parameter; auto-collects from provider when available |
| `compilation/compose_planner.py` | Added `datasource_ids` to `_CompileState`; `_check_cross_datasource()` helper; wired into `_compile_union` and `_compile_join` |
| `tests/compose/compilation/conftest.py` | `_DatasourceAwareProvider` + `make_ds_provider` fixture factory |
| `tests/compose/compilation/test_union.py` | xfail → 8 real tests (detection, same-DS, unknown-DS, no-provider, 3-way, UNION ALL) |
| `tests/compose/compilation/test_join.py` | 5 new tests (detection, same-DS, unknown-DS, no-provider, LEFT join) |
| `tests/compose/authority/test_public_api.py` | Updated `__all__` assertion to include `collect_datasource_ids` |

## Test Results

```
Focused: tests/compose/compilation/test_union.py — 18 passed
Focused: tests/compose/compilation/test_join.py  — 17 passed
Suite:   tests/compose/                           — 754 passed, 0 failed
Full:    python -m pytest                         — 3313 passed, 0 xfailed
```

Previous baseline: `3301 passed, 1 xfailed` → now `3313 passed, 0 xfailed`.

Latest verification by root controller:

```
python -m pytest tests\compose\compilation\test_union.py tests\compose\compilation\test_join.py -q
  -> 35 passed
python -m pytest -q
  -> 3316 passed
```

## Execution Check-in

- completed_work: Python compile-time cross-datasource rejection is implemented for union and join through datasource IDs collected from `ModelInfoProvider`.
- touched_code_paths:
  - `src/foggy/dataset_model/engine/compose/authority/model_info.py`
  - `src/foggy/dataset_model/engine/compose/authority/datasource_ids.py`
  - `src/foggy/dataset_model/engine/compose/compilation/compiler.py`
  - `src/foggy/dataset_model/engine/compose/compilation/compose_planner.py`
  - `tests/compose/compilation/test_union.py`
  - `tests/compose/compilation/test_join.py`
- self_check:
  - scope implemented as intended: yes
  - non-goals avoided: yes; `ModelBinding` remains unchanged
  - public API change documented: yes; `collect_datasource_ids` exported and provider method documented
  - tests recorded: yes
  - experience impact: N/A, backend compiler contract only
- self_check_conclusion: formal quality gate completed in `docs/v1.5/quality/S1-S2-post-v1.5-followup-implementation-quality.md`, decision `ready-with-risks`.
- acceptance_readiness: Python side ready for coverage audit or Python-only signoff; Java side not accepted until mirror implementation or explicit deferral signoff.

## Java Execution Prompt (Pending)

The following changes are needed in `foggy-data-mcp-bridge-wt-dev-compose`:

1. **`ModelInfoProvider.java`** — Add `default Optional<String> getDatasourceId(String modelName, String namespace) { return Optional.empty(); }`.
2. **`NullModelInfoProvider.java`** — Override `getDatasourceId` returning `Optional.empty()`.
3. **`CompileOptions`** — Add `Map<String, String> datasourceIds` field (nullable).
4. **`CompileState`** — Add `datasourceIds` field.
5. **`ComposePlanner.compileUnion`** — Add cross-DS check before recursion.
6. **`ComposePlanner.compileJoin`** — Same cross-DS check.
7. **`UnionCompileTest.crossDatasourceRejectedPlaceholder`** — Remove `@Disabled`, implement real test.
8. **`JoinCompileTest`** — Add cross-DS rejection test.

All Java changes mirror the Python implementation byte-for-byte at the contract level.
