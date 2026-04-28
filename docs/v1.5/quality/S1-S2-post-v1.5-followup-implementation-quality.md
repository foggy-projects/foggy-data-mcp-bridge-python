---
quality_scope: feature
quality_mode: pre-coverage-audit
version: v1.5 follow-up
target: S1-S2-post-v1.5-followup
status: reviewed
decision: ready-with-risks
reviewed_by: root-controller
reviewed_at: 2026-04-28
follow_up_required: yes
---

# Implementation Quality Gate

## Background

本质量门针对 post-v1.5 follow-up 的前两项并行交付：

- Stage 1: F-7 datasource identity contract。Python 侧通过 `ModelInfoProvider.get_datasource_id()` 为 compose union / join 补齐 cross-datasource compile-time rejection；Java 镜像仍待实现。
- Stage 2: formula parity snapshot CI solidification。Python 侧补齐 snapshot schema / catalog coverage / integrity drift detection；Java snapshot generation 已复验。

该检查聚焦实现质量和流转风险，不替代后续 coverage audit 或正式验收。

## Check Basis

| 类型 | 路径 / 证据 |
|---|---|
| execution plan | `docs/v1.5/P2-post-v1.5-followup-execution-plan.md` |
| Stage 1 progress | `docs/v1.5/S1-F7-datasource-identity-contract-progress.md` |
| Stage 2 progress | `docs/v1.5/S2-formula-parity-snapshot-ci-progress.md` |
| closeout writeback | `docs/v1.5/v1.4+v1.5-overall-progress-closeout.md` |
| latest focused tests | `python -m pytest tests\compose\compilation\test_union.py tests\compose\compilation\test_join.py -q` -> 35 passed |
| latest parity tests | `python -m pytest tests\integration\test_formula_parity.py -q` -> 50 passed |
| latest Java snapshot test | `mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest` -> BUILD SUCCESS |
| latest Python full regression | `python -m pytest -q` -> 3316 passed |

## Changed Surface

| Area | Paths |
|---|---|
| datasource identity SPI | `src/foggy/dataset_model/engine/compose/authority/model_info.py` |
| datasource ID collection | `src/foggy/dataset_model/engine/compose/authority/datasource_ids.py` |
| public authority exports | `src/foggy/dataset_model/engine/compose/authority/__init__.py` |
| compose compiler entrypoint | `src/foggy/dataset_model/engine/compose/compilation/compiler.py` |
| compose union / join lowering | `src/foggy/dataset_model/engine/compose/compilation/compose_planner.py` |
| compose tests | `tests/compose/compilation/conftest.py`, `tests/compose/compilation/test_union.py`, `tests/compose/compilation/test_join.py` |
| public API tests | `tests/compose/authority/test_public_api.py` |
| formula parity tests | `tests/integration/test_formula_parity.py` |
| docs | `docs/v1.5/P2-post-v1.5-followup-execution-plan.md`, `docs/v1.5/S1-F7-datasource-identity-contract-progress.md`, `docs/v1.5/S2-formula-parity-snapshot-ci-progress.md`, `docs/v1.5/README.md`, `docs/v1.5/v1.4+v1.5-overall-progress-closeout.md` |

## Quality Checklist

| Check | Result | Notes |
|---|---|---|
| scope conformance | pass-with-risk | Python Stage 1 and Stage 2 match the agreed scope. Full Stage 1 remains cross-repo incomplete until Java mirror lands. |
| code hygiene | pass | No debug prints, temporary branches, or untracked TODO-style implementation markers found in the changed surface. |
| duplication and consolidation | pass | Datasource lookup is centralized in `collect_datasource_ids`; union / join share a single `_check_cross_datasource` path. |
| complexity and abstraction | pass | Keeping datasource identity outside frozen `ModelBinding` avoids contract churn while still preserving explicit compiler input. No new abstraction is warranted yet. |
| error handling and edge cases | pass-with-note | Unknown datasource IDs are permissive by design. Provider lookup exceptions also fail open for compatibility; this is acceptable for a non-security compile-time guard but must stay documented. |
| readability and maintainability | pass | The new SPI method, helper, compile option, and tests map cleanly to the contract decision. |
| critical logic documentation | pass | Stage 1 documents Option B and Java mirror steps; Stage 2 documents artifact options and regeneration command. |
| contract and compatibility | pass-with-risk | Python preserves `ModelBinding` compatibility. Java has not yet mirrored the new provider method and planner rejection rule. |
| documentation and writeback | pass | Execution plan, README, progress docs, and closeout were updated to reflect Python completion, Stage 2 completion, and Java pending state. |
| test alignment | pass | Focused compose tests cover reject / same datasource / unknown datasource / no provider / multi-branch cases; parity tests cover snapshot integrity and strict compare. |
| release readiness | ready-with-risks | Python implementation can proceed to coverage audit. Do not mark F-7 two-engine complete before Java mirror verification. |

## Findings

- No blocking Python implementation issue found.
- No required refactor before coverage audit.
- The main delivery risk is status clarity: Stage 1 is Python-complete, not two-engine-complete. Any acceptance record must preserve that distinction.
- Stage 2 is complete as a repo-level regression guard, but actual CI workflow wiring is still an external infrastructure task because this repo does not currently contain CI config.

## Risks / Follow-ups

- Java F-7 mirror remains pending in `foggy-data-mcp-bridge-wt-dev-compose`. Required follow-up: add Java datasource identity SPI / compile options / union-join rejection tests, then rerun Java focused and snapshot lanes.
- `collect_datasource_ids` intentionally treats missing or failing provider datasource lookups as unknown. If future callers treat datasource identity as a security boundary instead of a compile-time compatibility guard, convert provider failures to fail-closed errors.
- CI artifact upload/download is documented but not implemented. When CI workflow files are introduced, choose and encode one of the documented Stage 2 artifact conventions.

## Recommended Next Skills

- `foggy-test-coverage-audit`: optional for Python-only Stage 1/2 evidence mapping before acceptance.
- `foggy-acceptance-signoff`: only after deciding whether to sign off Python-only results or wait for Java F-7 mirror.
- `google-antigravity-prompt`: if Java F-7 mirror is delegated to another session.

## Decision

- decision: `ready-with-risks`
- blocker: none for Python Stage 1/2 continuation
- follow_up_required: yes
- required_before_two_engine_signoff: Java F-7 mirror implementation and verification
