# Pivot 9.2 Outer Pivot Cache Feasibility

## 文档作用

- doc_type: feasibility-decision
- status: accepted-deferred
- intended_for: root-controller / python-engine-agent / performance-owner / signoff-owner
- purpose: 记录 Python Pivot v1.10 P5 outer Pivot cache 的可行性结论、暂缓原因和后续重启条件。

## Scope

P5 只做 feasibility，不实现新的 runtime cache。

评估对象：

- 是否在当前 Python Pivot runtime 外层新增结果缓存。
- 现有 `SemanticQueryService` 通用缓存是否足以视为 outer Pivot cache。
- 未来实现专用 Pivot cache 前必须补齐的 cache key、权限、失效和遥测条件。

不改变 public Pivot DSL，不新增 schema 字段，不改变现有查询执行路径。

## Current Cache Inventory

Python 当前已有 `SemanticQueryService` 通用查询缓存：

- `enable_cache=True`
- `_cache: Dict[str, Tuple[SemanticQueryResponse, float]]`
- `invalidate_model_cache()` 清理 `_cache` 和 `_mapping_cache`
- sync / async `query_model` 均有读取和写入路径
- `_get_cache_key(model, request)` 当前仅包含：
  - `model`
  - `columns`
  - `slice`
  - `group_by`
  - `order_by`
  - `limit`
  - `start`

该缓存不是专用 outer Pivot cache。它没有显式建模 Pivot shape、权限上下文、dialect/datasource、masking、`systemSlice` 合并结果、`deniedColumns`、fieldAccess、以及内部执行计划。

## Key Findings

| Area | Finding |
|---|---|
| pivot shape | 当前 cache key 不包含 `pivot.rows/columns/metrics/options/layout`，不能作为 Pivot 结果缓存键。 |
| permissions | fieldAccess、masking、deniedColumns、systemSlice、principal/tenant 上下文未形成可审计 cache key。 |
| internal plan | `domain_transport_plan` 是 `PrivateAttr`，不会进入 public dump；未来如缓存相关路径必须额外加入内部 plan fingerprint。 |
| result shape | flat/grid/tree、subtotal/grandTotal、cascade surviving domain 都会改变结果形态。 |
| invalidation | 当前按 model 清理，没有覆盖 datasource/schema/version/permission 策略。 |
| telemetry | P6 已补日志查询示例，但还没有真实生产 latency/hit-rate/memory 压力证据证明需要缓存。 |

## Decision

Status: accepted-deferred.

Python Pivot v1.10 不新增 outer Pivot cache。现有通用缓存保持原样，不将其声明为 Pivot 9.2 follow-up 的完成能力。

原因：

1. 当前缺少生产遥测证据，无法证明 outer Pivot cache 是必要优化。
2. 现有 cache key 不足以安全覆盖 Pivot 语义和权限上下文。
3. Stage 5A/5B 引入的内部执行计划、surviving domain、DomainTransportPlan 等状态不能依赖 public request dump 推导。
4. 错误的缓存命中会造成权限数据泄漏或返回错误聚合结果，风险高于当前收益。

## Future Cache Key Requirements

未来如果重启 outer Pivot cache，cache key 至少必须包含：

- model name、model version 或 schema fingerprint。
- datasource / dialect / namespace / tenant / principal 上下文。
- post-governance request fingerprint，包括 `systemSlice` 合并后的有效过滤。
- visible/masking/deniedColumns 的权限 fingerprint。
- full pivot fingerprint：rows、columns、metrics、properties、options、layout、outputFormat、subtotals、grandTotal、cascade constraints。
- internal plan fingerprint：DomainTransportPlan tuples hash、cascade surviving domain hash、auxiliary query strategy。
- result-shape version 和 cache schema version。

缓存值必须只存储已经完成权限过滤和 masking 后、且与该权限 fingerprint 绑定的响应。

## Required Tests Before Implementation

未来 runtime 实现前必须先补：

1. Same public request but different `systemSlice` must not share cache.
2. Same public request but different `fieldAccess.visible` must not share cache.
3. Same public request but different masking rules must not share cache.
4. Same public request with different `domain_transport_plan` must not share cache.
5. flat/grid/subtotal/cascade result shapes must have distinct cache keys.
6. cache invalidation must clear model-level, datasource-level, and schema-version-specific entries.
7. concurrency and memory limit behavior must be bounded.

## Verification

No runtime code changed.

Validation command:

```powershell
git diff --check
```

Result:

```text
clean
```

Latest full regression baseline before this docs-only P5:

```text
pytest -q
3943 passed in 11.79s
```

## Reopen Conditions

Outer Pivot cache can be reopened only when all of these exist:

1. Production telemetry showing repeated expensive Pivot requests and measurable cache benefit.
2. Signed cache key spec covering permissions, systemSlice, masking, dialect/datasource, and internal plans.
3. Invalidation strategy for model/schema/datasource/permission changes.
4. Cache hit/miss/eviction telemetry and log-query examples.
5. Unit and integration tests proving no cross-permission or cross-domain leakage.

## Signoff

Status: accepted-deferred for Python Pivot v1.10 P5.

Functional impact:

- No new outer Pivot cache is implemented.
- Current Pivot correctness and fail-closed behavior remain unchanged.
- Future cache work remains gated by telemetry and a permission-aware key specification.
