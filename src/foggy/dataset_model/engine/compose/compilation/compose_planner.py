"""Plan-tree → (CteUnits + JoinSpecs + ComposedSql) lowering (M6 · 6.2 / 6.3 / 6.5 / 6.6).

Owns the recursive ``_compile_any`` dispatcher that walks a ``QueryPlan``
tree, producing a ``ComposedSql`` via ``CteComposer`` for
Base/Derived/Join shapes and via native ``UNION`` / ``UNION ALL`` SQL
for Union shapes.

Four sub-features live here because they share the same recursion:

- 6.2 · ``UnionPlan`` compilation (`_compile_union`)
- 6.3 · ``JoinPlan`` compilation (`_compile_join`)
- 6.5 · dialect-driven CTE-vs-subquery fallback (``_dialect_supports_cte``)
- 6.6 · MVP id-based dedup + MAX_PLAN_DEPTH DOS guard (``_CompileState``)

The Full-mode dedup keyed on ``plan_hash(plan)`` is also wired through
the same ``_CompileState``; ``id(plan)`` is checked first as a fast
path, then structural equality as a fallback.

Dialect-driven output:
  - ``dialect in {"mysql8", "postgres", "postgresql", "mssql", "sqlite"}``
    → ``use_cte=True`` (``WITH cte_0 AS (...) SELECT * FROM cte_0``)
  - ``dialect in {"mysql", "mysql57"}`` (legacy MySQL 5.7 without CTE
    support) → ``use_cte=False`` (``SELECT ... FROM (...) AS t0``)

Note: ``"mysql"`` alone is interpreted as "5.7-compat" for safety —
callers that know they're on MySQL 8+ should pass ``"mysql8"`` to opt
in to CTE emission. This is the conservative default documented in
the r2 spec §6.5.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from foggy.dataset_model.engine.compose import (
    ComposedSql,
    CteComposer,
    CteUnit,
    JoinSpec,
)
from foggy.dataset_model.engine.compose import feature_flags
from foggy.dataset_model.engine.compose.compilation import error_codes
from foggy.dataset_model.engine.compose.schema import error_codes as schema_error_codes
from foggy.dataset_model.engine.compose.schema.derive import derive_schema
from foggy.dataset_model.engine.compose.schema.alias import extract_column_alias
from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError
from foggy.dataset_model.engine.compose.security import (
    plan_aware_permission_validator,
)
from foggy.dataset_model.engine.compose.security.plan_field_access_context import (
    PlanFieldAccessContext,
)
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.compilation.per_base import (
    compile_base_model,
)
from foggy.dataset_model.engine.compose.compilation.plan_hash import (
    MAX_PLAN_DEPTH,
    CanonicalPlanTuple,
    plan_hash,
)
from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinOn,
    JoinPlan,
    QueryPlan,
    UnionPlan,
)
from foggy.dataset_model.engine.compose.security.models import ModelBinding
from foggy.dataset_model.order_by import normalize_order_by_item


# ---------------------------------------------------------------------------
# Dialect helpers (6.5)
# ---------------------------------------------------------------------------
#
# Why M6 doesn't just delegate to ``FDialect.supports_cte`` for everything:
# ``FDialect`` concrete classes (``MySqlDialect`` / ``PostgresDialect`` /
# ``SqliteDialect`` / ``SqlServerDialect``) all report ``supports_cte =
# True`` because they target modern versions. M6 needs to distinguish
# MySQL 5.7 (no CTE) from 8.0+ (CTE), which ``FDialect`` does not model.
# So M6 owns the MySQL version distinction, and for every *other* dialect
# we look up the ``FDialect`` instance by name and delegate to its
# ``supports_cte`` property — any new FDialect implementation is picked
# up automatically without touching this module.


_MYSQL_LEGACY_ALIASES: frozenset = frozenset({"mysql", "mysql57"})
"""M6 interprets a bare ``"mysql"`` as conservative 5.7-compat (no CTE).
Callers on modern MySQL must pass ``"mysql8"`` explicitly."""

_MYSQL_MODERN_ALIASES: frozenset = frozenset({"mysql8"})
"""Explicit opt-in to modern MySQL (CTE emission)."""


def _fdialect_for_name(name: str) -> Optional[Any]:
    """Return a cached ``FDialect`` instance for ``name`` (or ``None``
    when the name is not a known non-MySQL dialect).

    Lazily imports the concrete dialect classes on first use so the
    compilation subpackage does not pull the whole ``foggy.dataset.dialects``
    tree into its import graph at module load.
    """
    cache = _fdialect_for_name._cache  # type: ignore[attr-defined]
    if name in cache:
        return cache[name]
    from foggy.dataset.dialects.postgres import PostgresDialect
    from foggy.dataset.dialects.sqlite import SqliteDialect
    from foggy.dataset.dialects.sqlserver import SqlServerDialect

    # Intentionally NOT mapping ``mysql`` / ``mysql57`` / ``mysql8`` here —
    # those are owned by ``dialect_supports_cte`` directly.
    factory_table = {
        "postgres": PostgresDialect,
        "postgresql": PostgresDialect,
        "mssql": SqlServerDialect,
        "sqlserver": SqlServerDialect,
        "sqlite": SqliteDialect,
    }
    factory = factory_table.get(name)
    instance = factory() if factory else None
    cache[name] = instance
    return instance


_fdialect_for_name._cache = {}  # type: ignore[attr-defined]


def dialect_supports_cte(dialect: str) -> bool:
    """Return True when the dialect supports ``WITH cte_N AS (...)`` syntax.

    ``mysql`` (bare) is treated as the conservative MySQL 5.7 default
    that predates CTE support — callers that know they're on MySQL 8+
    must pass ``"mysql8"`` to enable CTE emission. For all non-MySQL
    dialects the decision is delegated to the corresponding
    ``FDialect.supports_cte`` (see module-level comment).
    """
    n = dialect.lower()
    if n in _MYSQL_LEGACY_ALIASES:
        return False
    if n in _MYSQL_MODERN_ALIASES:
        return True
    instance = _fdialect_for_name(n)
    if instance is None:
        # Unknown dialect — ``_assert_dialect`` is the sole source of
        # truth for rejection; return False to avoid raising here (keeps
        # the capability query pure).
        return False
    return instance.supports_cte


def _assert_dialect(dialect: str) -> None:
    """Fail-closed: reject unknown dialect strings early so downstream
    snapshot drift is caught here rather than at a live query.

    Known dialects are the two MySQL aliases plus every dialect for
    which ``_fdialect_for_name`` returns a non-None FDialect.
    """
    n = dialect.lower()
    if n in _MYSQL_LEGACY_ALIASES or n in _MYSQL_MODERN_ALIASES:
        return
    if _fdialect_for_name(n) is not None:
        return
    raise ComposeCompileError(
        code=error_codes.UNSUPPORTED_PLAN_SHAPE,
        phase="plan-lower",
        message=(
            f"Unknown dialect {dialect!r}; supported: "
            f"mysql / mysql57 / mysql8 / postgres(postgresql) / "
            f"mssql(sqlserver) / sqlite"
        ),
    )


# ---------------------------------------------------------------------------
# Compile state — carries dedup + alias counter across the recursion
# ---------------------------------------------------------------------------


@dataclass
class _CompileState:
    """Mutable state threaded through ``_compile_any``.

    Not public — callers use ``compile_to_composed_sql`` which hides
    the state machine.
    """

    bindings: Dict[str, ModelBinding]
    semantic_service: Any
    dialect: str
    # Monotonic ``cte_0 / cte_1 / ...`` alias sequence.
    alias_counter: int = 0
    # MVP dedup: same ``id(plan)`` hits → reuse the CteUnit directly.
    id_cache: Dict[int, CteUnit] = field(default_factory=dict)
    # Full-mode dedup: structurally equal plan subtrees share a CteUnit.
    hash_cache: Dict[CanonicalPlanTuple, CteUnit] = field(default_factory=dict)
    # ``(model_name, id(binding))`` → QueryBuildResult. Skips
    # re-running ``build_query_with_governance`` when the same QM is
    # compiled twice under the same binding (self-join / self-union).
    governance_cache: Dict[Tuple[str, int], Any] = field(default_factory=dict)
    # Recursion depth — bumped in/out by ``_compile_any`` via
    # ``enter_depth`` / ``exit_depth``; enforces ``MAX_PLAN_DEPTH`` at
    # entry to detect DOS-shaped plans before they eat the executor.
    current_depth: int = 0
    # G10 PR3 · Snapshot of ``feature_flags.g10_enabled()`` taken once at
    # construction so per-plan compile loops don't re-read env-var per
    # column. Ungated default = False; legacy hot path consults the
    # flag exactly zero times after this snapshot.
    g10_enabled: bool = False
    # G10 PR3 · Plan-tree → CTE alias mapping, identity-keyed via
    # ``id(plan)`` (plans are frozen dataclasses with value-equality, so
    # we cannot key by the plan itself — two structurally-equal plans
    # would collide). Populated by ``_compile_base`` / ``_compile_derived``
    # only when ``g10_enabled`` is True; legacy compile keeps the dict
    # empty so downstream consumers (PR4 validator routing) short-circuit
    # without consulting the flag again per column.
    plan_alias_map: Dict[int, str] = field(default_factory=dict)
    # F-7 · Per-model datasource identity mapping. When non-None, the
    # compiler checks that all leaf models in a union / join share the
    # same datasource. ``None`` means "skip check" (backward-compatible).
    datasource_ids: Optional[Dict[str, Optional[str]]] = None
    # Prerequisite CTEs for two-stage calculated field rendering.
    prerequisite_ctes: List[CteUnit] = field(default_factory=list)

    def next_alias(self) -> str:
        alias = f"cte_{self.alias_counter}"
        self.alias_counter += 1
        return alias

    def enter_depth(self) -> int:
        self.current_depth += 1
        return self.current_depth

    def exit_depth(self) -> None:
        self.current_depth -= 1


# ---------------------------------------------------------------------------
# Public entry used by ``compiler.compile_plan_to_sql``
# ---------------------------------------------------------------------------


def compile_to_composed_sql(
    plan: QueryPlan,
    *,
    bindings: Dict[str, ModelBinding],
    semantic_service: Any,
    dialect: str,
    datasource_ids: Optional[Dict[str, Optional[str]]] = None,
) -> ComposedSql:
    """Walk ``plan`` and return a ``ComposedSql`` via dialect-aware
    ``CteComposer`` or native UNION / JOIN SQL.

    Binding coverage is checked inline by ``_compile_base`` on a single
    tree pass (no pre-walk via ``collect_base_models``).

    Raises
    ------
    ComposeCompileError
        See ``error_codes`` — ``UNSUPPORTED_PLAN_SHAPE`` (depth / unknown
        dialect / full outer join on SQLite), ``MISSING_BINDING``,
        ``PER_BASE_COMPILE_FAILED``, ``CROSS_DATASOURCE_REJECTED`` (F-7).
    """
    _assert_dialect(dialect)
    state = _CompileState(
        bindings=bindings,
        semantic_service=semantic_service,
        dialect=dialect,
        g10_enabled=feature_flags.g10_enabled(),
        datasource_ids=datasource_ids,
    )
    # G10 PR4 · plan-aware permission validation. Runs only when the
    # G10 flag is on; under flag=off the legacy single-QM
    # ``SemanticServiceV3._resolve_effective_visible`` path continues
    # to enforce flat-whitelist semantics without any change.
    if state.g10_enabled:
        _run_plan_aware_permission_check(plan, bindings)
    result = _compile_any(plan, state)
    
    if state.prerequisite_ctes and not dialect_supports_cte(dialect):
        raise ComposeCompileError(
            code=error_codes.RELATION_CTE_HOIST_UNSUPPORTED,
            phase="plan-lower",
            message=(
                f"Dialect {dialect!r} does not support native CTEs, but the query requires "
                f"multi-stage CTE hoisting for window functions or calculations."
            ),
        )
        
    if isinstance(result, ComposedSql):
        return _prepend_prerequisite_ctes(result, state.prerequisite_ctes)
    
    # Top-level CteUnit (base / derived) — wrap for dialect-consistent output.
    # When prerequisite CTEs are present (from CTE-wrapped window CFs),
    # the root unit is the LAST in the chain (the outer window stage),
    # not the first (which is the inner aggregate stage). We must FROM
    # the root unit, matching Java's wrapSingleUnit behaviour.
    if state.prerequisite_ctes:
        all_params: list = []
        cte_parts: list = []
        for prereq in state.prerequisite_ctes:
            cte_parts.append(f"{prereq.alias} AS ({prereq.sql})")
            all_params.extend(prereq.params)
        cte_parts.append(f"{result.alias} AS ({result.sql})")
        all_params.extend(result.params)
        with_clause = "WITH " + ",\n".join(cte_parts)
        # FROM the root unit (the outer window stage), NOT the prerequisite
        from_clause = f"FROM {result.alias}"
        sql = f"{with_clause}\nSELECT *\n{from_clause}"
        return ComposedSql(sql=sql, params=all_params)

    return CteComposer.compose(
        units=[result],
        join_specs=[],
        use_cte=dialect_supports_cte(dialect),
    )


def _prepend_prerequisite_ctes(composed: ComposedSql, prereqs: List[CteUnit]) -> ComposedSql:
    """Prepend hoisted prerequisite CTEs to an already-composed SQL."""
    if not prereqs:
        return composed
        
    cte_parts = []
    all_params = []
    for unit in prereqs:
        cte_parts.append(f"{unit.alias} AS (\n{unit.sql}\n)")
        all_params.extend(unit.params)
        
    with_block = "WITH " + ",\n".join(cte_parts)
    
    sql = composed.sql
    if sql.upper().startswith("WITH "):
        sql = sql[4:].lstrip()
        final_sql = f"{with_block},\n{sql}"
    else:
        final_sql = f"{with_block}\n{sql}"
        
    return ComposedSql(sql=final_sql, params=all_params + composed.params)


# ---------------------------------------------------------------------------
# Dispatcher — recursion + depth guard + dedup
# ---------------------------------------------------------------------------


def _compile_any(plan: QueryPlan, state: _CompileState) -> Any:
    """Recursively compile ``plan`` — returns a ``CteUnit`` (base /
    derived, embeddable) or a ``ComposedSql`` (union / join, self-
    contained).

    Depth-first recursion with two-level dedup:
      1. MVP fast path — same ``id(plan)`` already compiled → reuse
      2. Full mode — structural ``plan_hash(plan)`` already compiled →
         reuse; rehashing is cheap for frozen dataclasses
    Depth tracked on ``state.current_depth``; ``MAX_PLAN_DEPTH`` rejects
    pathological nesting at plan-lower phase.
    """
    depth = state.enter_depth()
    try:
        if depth > MAX_PLAN_DEPTH:
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    f"Plan depth {depth} exceeds MAX_PLAN_DEPTH={MAX_PLAN_DEPTH}; "
                    "nested derivations beyond this depth are rejected as a "
                    "DOS safeguard (Compose Query typical depth is 3-5)."
                ),
            )
        # Union/Join emit ComposedSql — not reusable as embedded CTE, so
        # skip the CteUnit dedup cache entirely.
        if isinstance(plan, UnionPlan):
            return _compile_union(plan, state)
        if isinstance(plan, JoinPlan):
            return _compile_join(plan, state)

        # Fail-loud on plan_hash errors: unknown plan subclasses /
        # malformed plans surface immediately instead of silently
        # dropping Full-mode dedup. This closes r3 evaluation §4.2.
        id_key = id(plan)
        if id_key in state.id_cache:
            return state.id_cache[id_key]
        structural_key = plan_hash(plan)
        if structural_key in state.hash_cache:
            unit = state.hash_cache[structural_key]
            state.id_cache[id_key] = unit
            return unit

        if isinstance(plan, BaseModelPlan):
            unit = _compile_base(plan, state)
        elif isinstance(plan, DerivedQueryPlan):
            unit = _compile_derived(plan, state)
        else:
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    f"Unknown QueryPlan subclass {type(plan).__name__}; "
                    "extend compose_planner._compile_any if a new plan type "
                    "was added"
                ),
            )

        state.id_cache[id_key] = unit
        state.hash_cache[structural_key] = unit
        return unit
    finally:
        state.exit_depth()


# ---------------------------------------------------------------------------
# Per-shape compilers
# ---------------------------------------------------------------------------


def _compile_base(plan: BaseModelPlan, state: _CompileState) -> CteUnit:
    """Compile a ``BaseModelPlan`` — delegates to ``per_base.compile_base_model``.

    Does NOT append the returned unit to ``state.cte_units``; the caller
    (``_compile_join`` for joins, ``_compile_derived`` for embedding
    into an outer SELECT, or ``compile_to_composed_sql`` for a top-
    level single-unit wrap) decides whether to anchor it.
    """
    binding = state.bindings.get(plan.model)
    if binding is None:
        raise ComposeCompileError(
            code=error_codes.MISSING_BINDING,
            phase="plan-lower",
            message=(
                f"No ModelBinding provided for BaseModelPlan.model='{plan.model}'. "
                "Ensure resolve_authority_for_plan was called on the same plan "
                "tree and its result is passed via bindings=..."
            ),
        )
    alias = state.next_alias()
    _register_plan_alias(state, plan, alias)
    unit = compile_base_model(
        plan,
        binding,
        semantic_service=state.semantic_service,
        alias=alias,
        governance_cache=state.governance_cache,
        prerequisite_ctes=state.prerequisite_ctes,
        next_alias_fn=state.next_alias,
    )
    return _stabilize_base_output_names(unit, plan=plan, dialect=state.dialect)


def _register_plan_alias(state: _CompileState, plan: QueryPlan, alias: str) -> None:
    """G10 PR3 · Register ``plan → alias`` when the G10 flag is on.
    Skipping the put when the flag is off keeps ``state.plan_alias_map``
    empty so the PR4 validator's short-circuit path doesn't consult the
    flag again per column."""
    if state.g10_enabled:
        state.plan_alias_map[id(plan)] = alias


# ---------------------------------------------------------------------------
# G10 PR4 — plan-aware permission validation entry
# ---------------------------------------------------------------------------


def _run_plan_aware_permission_check(
    plan: QueryPlan, bindings: Dict[str, ModelBinding]
) -> None:
    """Walk the plan tree to build a :class:`PlanFieldAccessContext`,
    derive the root plan's :class:`OutputSchema`, then run the
    plan-aware permission validator.

    Pure pre-compile sub-step: no SQL is emitted here, no compile-state
    side effects beyond the validator's own throws. Failure surfaces as
    :class:`ComposeSchemaError` with phase ``permission-validate``.
    """
    plan_ctx = PlanFieldAccessContext()
    visited: set = set()
    _collect_plan_bindings(plan, bindings, plan_ctx, visited)
    schema = derive_schema(plan)
    plan_aware_permission_validator.validate(plan, schema, plan_ctx)


def _collect_plan_bindings(
    plan: Optional[QueryPlan],
    bindings: Dict[str, ModelBinding],
    plan_ctx: PlanFieldAccessContext,
    visited: set,
) -> None:
    """Tree walk: every :class:`BaseModelPlan` pairs with its model's
    :class:`ModelBinding`; ``visited`` prevents quadratic walks on
    shared plan subtrees (identity-keyed via ``id(plan)``)."""
    if plan is None:
        return
    plan_key = id(plan)
    if plan_key in visited:
        return
    visited.add(plan_key)
    if isinstance(plan, BaseModelPlan):
        binding = bindings.get(plan.model)
        if binding is not None:
            plan_ctx.bind(plan, binding)
        return
    if isinstance(plan, DerivedQueryPlan):
        _collect_plan_bindings(plan.source, bindings, plan_ctx, visited)
        return
    if isinstance(plan, JoinPlan):
        _collect_plan_bindings(plan.left, bindings, plan_ctx, visited)
        _collect_plan_bindings(plan.right, bindings, plan_ctx, visited)
        return
    if isinstance(plan, UnionPlan):
        _collect_plan_bindings(plan.left, bindings, plan_ctx, visited)
        _collect_plan_bindings(plan.right, bindings, plan_ctx, visited)


def _compile_derived(plan: DerivedQueryPlan, state: _CompileState) -> CteUnit:
    """Lower ``DerivedQueryPlan`` via string-template nesting.

    Emits ``SELECT <cols> FROM (<source_sql>) AS <alias> WHERE <slice>
    GROUP BY ... ORDER BY ... LIMIT ... OFFSET ...``. Derived plans
    reference their source's output schema, not a TableModel, so v1.3
    engine semantics do not apply.

    The inner unit is embedded directly into the outer SQL; neither
    inner nor outer is appended to ``state.cte_units`` (caller decides).
    Parameter ordering matches v1.3 engine emission (SELECT → WHERE →
    GROUP BY → HAVING → ORDER BY); inner params flow before outer.
    """
    inner = _compile_any(plan.source, state)
    if isinstance(inner, ComposedSql):
        # Union source → synthesise a CteUnit wrapper so the outer
        # SELECT has a stable inner alias to embed under.
        inner = CteUnit(
            alias=state.next_alias(),
            sql=inner.sql,
            params=list(inner.params or []),
            select_columns=None,
        )
    assert isinstance(inner, CteUnit)
    source_columns = _source_output_columns_for_derived(plan.source, inner)
    _validate_derived_slice_not_same_stage_alias(plan, source_columns)
    _validate_derived_output_refs(plan, source_columns)

    outer_sql, outer_params = _render_outer_select(
        plan=plan,
        inner_alias=inner.alias,
        inner_sql=inner.sql,
        dialect=state.dialect,
        source_columns=source_columns,
    )
    derived_alias = state.next_alias()
    _register_plan_alias(state, plan, derived_alias)
    return CteUnit(
        alias=derived_alias,
        sql=outer_sql,
        params=list(inner.params) + list(outer_params),
        select_columns=_derived_output_columns(plan, source_columns),
    )


def _compile_join(plan: JoinPlan, state: _CompileState) -> ComposedSql:
    """Compile a ``JoinPlan`` — produce a self-contained ``ComposedSql``.

    Both sides compile recursively (base/derived return ``CteUnit``,
    union/nested-join return ``ComposedSql`` which we wrap as a
    ``CteUnit``). A ``JoinSpec`` + the two anchor units are handed to
    ``CteComposer.compose`` LOCALLY so the join SQL is complete as
    returned — callers (``_compile_derived`` wrapping, top-level assembly,
    or an outer join recursing) can treat it uniformly.

    SQLite carve-out: ``type='full'`` + SQLite dialect is rejected as
    ``UNSUPPORTED_PLAN_SHAPE`` since SQLite pre-3.39 lacks ``FULL OUTER
    JOIN``.

    Dedup: if the same base plan appears on both sides (e.g. self-join),
    the two recursive calls return the same ``CteUnit`` (same alias)
    thanks to ``state.id_cache`` / ``state.hash_cache`` hits. The
    de-duped unit list fed to ``CteComposer`` has one entry in that
    case — no duplicate CTEs.

    F-7: cross-datasource detection is performed before recursion —
    same logic as ``_compile_union``.
    """
    _check_cross_datasource(plan, state, "join")

    if plan.type == "full" and state.dialect.lower() == "sqlite":
        raise ComposeCompileError(
            code=error_codes.UNSUPPORTED_PLAN_SHAPE,
            phase="plan-lower",
            message=(
                "JoinPlan(type='full') is not supported on SQLite dialect; "
                "use inner/left/right or switch dialects."
            ),
        )

    left_unit = _compile_any(plan.left, state)
    right_unit = _compile_any(plan.right, state)
    if isinstance(left_unit, ComposedSql):
        left_unit = _wrap_composed_as_unit(left_unit, state)
    if isinstance(right_unit, ComposedSql):
        right_unit = _wrap_composed_as_unit(right_unit, state)

    join_spec = JoinSpec(
        left_alias=left_unit.alias,
        right_alias=right_unit.alias,
        on_condition=" AND ".join(
            f"{_render_qualified_ref(left_unit.alias, o.left, state.dialect)} "
            f"{o.op} "
            f"{_render_qualified_ref(right_unit.alias, o.right, state.dialect)}"
            for o in plan.on
        ),
        join_type=_sql_join_type(plan.type),
    )
    # Dedup anchor units by alias so ``base.join(base)`` emits one CTE.
    anchors = [left_unit]
    if right_unit.alias != left_unit.alias:
        anchors.append(right_unit)
    return CteComposer.compose(
        units=anchors,
        join_specs=[join_spec],
        use_cte=dialect_supports_cte(state.dialect),
        select_columns=_join_projection_columns(
            left_unit, right_unit, dialect=state.dialect
        ),
    )


def _compile_union(plan: UnionPlan, state: _CompileState) -> ComposedSql:
    """Compile a ``UnionPlan`` — emits native ``UNION`` / ``UNION ALL`` SQL.

    Unions are NOT expressed through ``CteComposer.JoinSpec`` — that
    machinery is ON-condition-driven, and unions are column-aligned.
    Instead we render both sides (recursively), then concatenate with
    ``\\nUNION [ALL]\\n``. Params flow left → right.

    F-7: cross-datasource detection is performed before recursion —
    if the leaf models on both sides span multiple datasources, a
    ``CROSS_DATASOURCE_REJECTED`` error is raised at plan-lower phase.
    """
    _check_cross_datasource(plan, state, "union")

    left = _compile_any(plan.left, state)
    right = _compile_any(plan.right, state)

    left_sql, left_params = _unwrap_for_union(left)
    right_sql, right_params = _unwrap_for_union(right)

    keyword = "UNION ALL" if plan.all else "UNION"
    sql = f"({left_sql})\n{keyword}\n({right_sql})"
    return ComposedSql(sql=sql, params=list(left_params) + list(right_params))


# ---------------------------------------------------------------------------
# F-7 · Cross-datasource detection (post-v1.5 Stage 1)
# ---------------------------------------------------------------------------


def _check_cross_datasource(
    plan: QueryPlan, state: _CompileState, plan_kind: str
) -> None:
    """Reject union / join plans whose leaf models span multiple datasources.

    Called at the top of ``_compile_union`` and ``_compile_join``, before
    any SQL is generated. The check uses ``state.datasource_ids`` which
    was collected from the ``ModelInfoProvider`` before compilation.

    When ``state.datasource_ids`` is ``None`` (no provider, or provider
    does not implement ``get_datasource_id``), the check is skipped —
    this is the backward-compatible path for single-datasource hosts.

    When all leaf models map to ``None`` datasource IDs (unknown), the
    check is also skipped — ``None`` values are treated as "same unknown
    datasource" to maintain backward compatibility.

    Only when two or more distinct non-None datasource IDs are found
    among the leaf models is ``CROSS_DATASOURCE_REJECTED`` raised.
    """
    if state.datasource_ids is None:
        return

    bases = plan.base_model_plans()
    ds_ids = {state.datasource_ids.get(b.model) for b in bases}
    # Discard None — unknown datasources are permissive.
    ds_ids.discard(None)

    if len(ds_ids) > 1:
        sorted_ids = sorted(ds_ids)
        model_names = sorted({b.model for b in bases})
        raise ComposeCompileError(
            code=error_codes.CROSS_DATASOURCE_REJECTED,
            phase="plan-lower",
            message=(
                f"{plan_kind.capitalize()} operands span {len(ds_ids)} "
                f"datasources {sorted_ids}; models involved: "
                f"{model_names}. Cross-datasource composition is not "
                f"supported — all operands must belong to the same "
                f"datasource."
            ),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SIMPLE_OUTPUT_REF = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_DOTTED_REF = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*\.[A-Za-z_][A-Za-z0-9_$]*$")

# Slice DSL logical operators whose children are recursively traversed.
# Kept as module-level constants so _iter_slice_entries (validation) and
# _render_slice (SQL rendering) share the same authoritative source — adding a
# new operator only requires updating these two sets.
_SYMMETRIC_LOGICAL_OPS: frozenset = frozenset({"$or", "$and"})
_ALL_LOGICAL_OPS: frozenset = frozenset({"$or", "$and", "$not"})
_LOWER_SAFE_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _quote_identifier(name: str, dialect: str) -> str:
    n = dialect.lower()
    if n in {"mssql", "sqlserver"}:
        return "[" + name.replace("]", "]]") + "]"
    if n in {"mysql", "mysql57", "mysql8"}:
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


def _needs_identifier_quote(name: str, dialect: str) -> bool:
    if name == "*":
        return False
    if not _SIMPLE_OUTPUT_REF.match(name):
        return True
    if "$" in name:
        return True
    if dialect.lower() in {"postgres", "postgresql", "sqlite", "mssql", "sqlserver"}:
        return not _LOWER_SAFE_IDENT.match(name)
    return False


def _render_identifier(name: str, dialect: str) -> str:
    return _quote_identifier(name, dialect) if _needs_identifier_quote(name, dialect) else name


def _render_qualified_ref(alias: str, field: str, dialect: str) -> str:
    return f"{alias}.{_render_identifier(field, dialect)}"


def _join_projection_columns(
    left_unit: CteUnit, right_unit: CteUnit, *, dialect: str
) -> Optional[List[str]]:
    left_columns = list(left_unit.select_columns or [])
    right_columns = list(right_unit.select_columns or [])
    if not left_columns or not right_columns:
        return None

    projection: List[str] = [
        _render_qualified_ref(left_unit.alias, column, dialect)
        for column in left_columns
    ]
    seen = set(left_columns)
    for column in right_columns:
        if column in seen:
            continue
        projection.append(_render_qualified_ref(right_unit.alias, column, dialect))
        seen.add(column)
    return projection or None


def _stabilize_base_output_names(
    unit: CteUnit, *, plan: BaseModelPlan, dialect: str
) -> CteUnit:
    desired_columns = _base_declared_output_names(plan)
    actual_columns = list(unit.select_columns or [])
    if not desired_columns or actual_columns == desired_columns:
        return unit
    if len(actual_columns) < len(desired_columns):
        return unit

    inner_alias = f"{unit.alias}_src"
    projection = []
    stabilized_columns: List[str] = []
    for idx, actual in enumerate(actual_columns):
        desired = desired_columns[idx] if idx < len(desired_columns) else actual
        rendered = _render_qualified_ref(inner_alias, actual, dialect)
        if actual != desired:
            rendered += f" AS {_render_identifier(desired, dialect)}"
        projection.append(rendered)
        stabilized_columns.append(desired)
    sql = (
        "SELECT " + ", ".join(projection)
        + f"\nFROM ({unit.sql}) AS {inner_alias}"
    )
    return CteUnit(
        alias=unit.alias,
        sql=sql,
        params=list(unit.params or []),
        select_columns=stabilized_columns,
    )


def _base_declared_output_names(plan: BaseModelPlan) -> List[str]:
    names = [extract_column_alias(column).output_name for column in plan.columns]
    for cf in plan.calculated_fields:
        if isinstance(cf, dict):
            name = cf.get("alias") or cf.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return names


def _derived_output_columns(
    plan: DerivedQueryPlan,
    source_columns: List[str],
) -> List[str]:
    if not plan.columns:
        return list(source_columns)
    return [
        extract_column_alias(column).output_name
        for column in plan.columns
    ]


_DERIVED_EXPR_RESERVED_TOKENS: frozenset = frozenset({
    "SUM", "COUNT", "AVG", "MIN", "MAX",
    "IIF", "IF", "CASE", "WHEN", "THEN", "ELSE", "END",
    "COALESCE", "NULLIF",
    "IS_NULL", "IS_NOT_NULL", "BETWEEN", "IN", "NOT",
    "DATE_DIFF", "DATE_ADD", "NOW",
    "AND", "OR",
    "TRUE", "FALSE", "NULL",
    "DISTINCT",
})


def _source_output_columns_for_derived(
    source: QueryPlan,
    inner: CteUnit,
) -> List[str]:
    if isinstance(source, UnionPlan):
        return derive_schema(source).names()
    if inner.select_columns:
        return [
            extract_column_alias(column).output_name
            for column in inner.select_columns
        ]
    if isinstance(source, JoinPlan):
        return _declared_output_columns_for_plan(source)
    if isinstance(source, BaseModelPlan):
        return _base_declared_output_names(source)
    if isinstance(source, DerivedQueryPlan):
        return [
            extract_column_alias(column).output_name
            for column in source.columns
        ]
    return []


def _declared_output_columns_for_plan(plan: QueryPlan) -> List[str]:
    if isinstance(plan, BaseModelPlan):
        return _base_declared_output_names(plan)
    if isinstance(plan, DerivedQueryPlan):
        return [
            extract_column_alias(column).output_name
            for column in plan.columns
        ]
    if isinstance(plan, JoinPlan):
        left_columns = _declared_output_columns_for_plan(plan.left)
        right_columns = _declared_output_columns_for_plan(plan.right)
        seen = set(left_columns)
        out = list(left_columns)
        for column in right_columns:
            if column in seen:
                continue
            seen.add(column)
            out.append(column)
        return out
    if isinstance(plan, UnionPlan):
        return derive_schema(plan).names()
    return []


def _iter_slice_entries(slice_: Any) -> Any:
    if not isinstance(slice_, (list, tuple)):
        return
    for entry in slice_:
        if not isinstance(entry, dict):
            continue
        if len(entry) == 1:
            key, val = next(iter(entry.items()))
            if key in _SYMMETRIC_LOGICAL_OPS:
                if isinstance(val, (list, tuple)):
                    yield from _iter_slice_entries(val)
                continue
            if key == "$not":
                if isinstance(val, dict):
                    yield from _iter_slice_entries([val])
                elif isinstance(val, (list, tuple)):
                    yield from _iter_slice_entries(val)
                continue
        yield entry


def _validate_derived_output_refs(
    plan: DerivedQueryPlan,
    source_columns: List[str],
) -> None:
    if not source_columns:
        return
    source_names = set(source_columns)
    current_output_names = {
        extract_column_alias(column).output_name
        for column in plan.columns
    }
    order_by_names = source_names | current_output_names
    for column in plan.columns:
        parts = extract_column_alias(column)
        for ident in _iter_unquoted_identifiers(parts.expression):
            if ident.upper() in _DERIVED_EXPR_RESERVED_TOKENS:
                continue
            if ident not in source_names:
                raise ComposeSchemaError(
                    code=schema_error_codes.DERIVED_QUERY_UNKNOWN_FIELD,
                    message=(
                        f"derived query references unknown field {ident!r} "
                        "not present in source output schema "
                        f"(available: {sorted(source_names)!r})"
                    ),
                    phase=schema_error_codes.PHASE_SCHEMA_DERIVE,
                        plan_path="DerivedQueryPlan",
                        offending_field=ident,
                    )
    for entry in plan.order_by or []:
        field_name = normalize_order_by_item(entry).field
        if field_name not in order_by_names:
            raise ComposeSchemaError(
                code=schema_error_codes.DERIVED_QUERY_UNKNOWN_FIELD,
                message=(
                    f"derived query order_by references unknown field "
                    f"{field_name!r} not present in source output schema "
                    f"or this derived query's output columns "
                    f"(available: {sorted(order_by_names)!r})"
                ),
                phase=schema_error_codes.PHASE_SCHEMA_DERIVE,
                plan_path="DerivedQueryPlan",
                offending_field=field_name,
            )
    for entry in _iter_slice_entries(plan.slice_ or []):
        field_name = _slice_field_name(entry)
        if field_name:
            field_str = str(field_name).strip()
            if _DOTTED_REF.match(field_str):
                alias_part = field_str.split(".")[0]
                raise ComposeSchemaError(
                    code=schema_error_codes.DERIVED_QUERY_UNKNOWN_FIELD,
                    message=(
                        f"derived query slice references unknown field {alias_part!r} "
                        "not present in source output schema "
                        f"(available: {sorted(source_names)!r})"
                    ),
                    phase=schema_error_codes.PHASE_SCHEMA_DERIVE,
                    plan_path="DerivedQueryPlan",
                    offending_field=alias_part,
                )
            for ident in _iter_unquoted_identifiers(field_str):
                if ident.upper() in _DERIVED_EXPR_RESERVED_TOKENS:
                    continue
                if ident not in source_names:
                    raise ComposeSchemaError(
                        code=schema_error_codes.DERIVED_QUERY_UNKNOWN_FIELD,
                        message=(
                            f"derived query slice references unknown field {ident!r} "
                            "not present in source output schema "
                            f"(available: {sorted(source_names)!r})"
                        ),
                        phase=schema_error_codes.PHASE_SCHEMA_DERIVE,
                        plan_path="DerivedQueryPlan",
                        offending_field=ident,
                    )


def _validate_derived_slice_not_same_stage_alias(
    plan: DerivedQueryPlan,
    source_columns: List[str],
) -> None:
    """Reject filtering a SELECT alias in the same derived stage.

    ``DerivedQueryPlan.slice_`` renders as a WHERE clause against the
    source subquery. Aliases created by this plan's own ``columns`` only
    exist in the outer SELECT list, so filtering them in the same stage
    produces invalid SQL such as ``cte_0.decrease_amount does not exist``.
    """
    if not plan.slice_:
        return

    source_names = set(source_columns)
    current_stage_aliases = {
        parts.output_name
        for parts in (extract_column_alias(column) for column in plan.columns)
        if parts.has_alias and parts.output_name not in source_names
    }
    if not current_stage_aliases:
        return

    for entry in _iter_slice_entries(plan.slice_):
        field_name = _slice_field_name(entry)
        if field_name in current_stage_aliases:
            raise ComposeSchemaError(
                code=schema_error_codes.DERIVED_QUERY_SAME_STAGE_ALIAS,
                message=(
                    f"field {field_name!r} is created by this derived "
                    f"query's SELECT and cannot be filtered in the same "
                    f"stage; add another .query({{ slice: "
                    f"[{{field: {field_name!r}, ...}}] }}) stage"
                ),
                phase=schema_error_codes.PHASE_SCHEMA_DERIVE,
                plan_path="DerivedQueryPlan",
                offending_field=field_name,
            )


def _slice_field_name(entry: object) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    field_name = entry.get("field")
    if isinstance(field_name, str):
        return field_name
    if field_name is not None or len(entry) != 1:
        return None
    key = next(iter(entry.keys()))
    return key if isinstance(key, str) else None


def _iter_unquoted_identifiers(expression: str) -> List[str]:
    identifiers: List[str] = []
    i = 0
    length = len(expression)
    while i < length:
        ch = expression[i]
        if ch == "'":
            i = _consume_single_quoted(expression, i)
            continue
        if ch == '"':
            i = _consume_double_quoted(expression, i)
            continue
        if ch == "`":
            i = _consume_backtick_quoted(expression, i)
            continue
        if ch == "[":
            i = _consume_bracket_quoted(expression, i)
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < length and (
                expression[j].isalnum() or expression[j] in {"_", "$"}
            ):
                j += 1
            prev_char = expression[i - 1] if i > 0 else ""
            next_char = expression[j] if j < length else ""
            if prev_char != "." and next_char != ".":
                identifiers.append(expression[i:j])
            i = j
            continue
        i += 1
    return identifiers


def _is_simple_output_ref(expr: str) -> bool:
    return bool(_SIMPLE_OUTPUT_REF.match(expr.strip()))


def _render_select_column(
    column: str,
    inner_alias: str,
    dialect: str,
    source_columns: Optional[List[str]] = None,
) -> str:
    if column.strip() == "*":
        return "*"
    parts = extract_column_alias(column)
    if _is_simple_output_ref(parts.expression):
        rendered = _render_qualified_ref(inner_alias, parts.expression, dialect)
    else:
        rendered = _render_expression_output_refs(
            parts.expression,
            inner_alias=inner_alias,
            dialect=dialect,
            source_columns=source_columns or [],
        )
    if parts.has_alias:
        return f"{rendered} AS {_render_identifier(parts.output_name, dialect)}"
    return rendered


def _render_expression_output_refs(
    expression: str,
    *,
    inner_alias: str,
    dialect: str,
    source_columns: List[str],
) -> str:
    """Qualify output-schema references inside a derived expression.

    Derived queries select from a subquery, so identifiers in expressions
    refer to the source plan's output names. PostgreSQL folds unquoted
    camelCase identifiers to lowercase; qualifying and quoting matched
    output names preserves aliases such as ``currentMonthAmount``.
    """
    if not source_columns:
        return expression

    source_names = set(source_columns)
    out: List[str] = []
    i = 0
    length = len(expression)
    while i < length:
        ch = expression[i]
        if ch == "'":
            end = _consume_single_quoted(expression, i)
            out.append(expression[i:end])
            i = end
            continue
        if ch == '"':
            end = _consume_double_quoted(expression, i)
            out.append(expression[i:end])
            i = end
            continue
        if ch == "`":
            end = _consume_backtick_quoted(expression, i)
            out.append(expression[i:end])
            i = end
            continue
        if ch == "[":
            end = _consume_bracket_quoted(expression, i)
            out.append(expression[i:end])
            i = end
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < length and (
                expression[j].isalnum() or expression[j] in {"_", "$"}
            ):
                j += 1
            ident = expression[i:j]
            prev_char = expression[i - 1] if i > 0 else ""
            next_char = expression[j] if j < length else ""
            if ident in source_names and prev_char != "." and next_char != ".":
                out.append(_render_qualified_ref(inner_alias, ident, dialect))
            else:
                out.append(ident)
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _consume_single_quoted(text: str, start: int) -> int:
    i = start + 1
    while i < len(text):
        if text[i] == "'" and i + 1 < len(text) and text[i + 1] == "'":
            i += 2
            continue
        if text[i] == "'":
            return i + 1
        i += 1
    return len(text)


def _consume_double_quoted(text: str, start: int) -> int:
    i = start + 1
    while i < len(text):
        if text[i] == '"' and i + 1 < len(text) and text[i + 1] == '"':
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    return len(text)


def _consume_backtick_quoted(text: str, start: int) -> int:
    i = start + 1
    while i < len(text):
        if text[i] == "`" and i + 1 < len(text) and text[i + 1] == "`":
            i += 2
            continue
        if text[i] == "`":
            return i + 1
        i += 1
    return len(text)


def _consume_bracket_quoted(text: str, start: int) -> int:
    i = start + 1
    while i < len(text):
        if text[i] == "]" and i + 1 < len(text) and text[i + 1] == "]":
            i += 2
            continue
        if text[i] == "]":
            return i + 1
        i += 1
    return len(text)


def _sql_join_type(plan_type: str) -> str:
    """Map plan-level join type (lowercase) to SQL keyword."""
    mapping = {
        "inner": "INNER",
        "left": "LEFT",
        "right": "RIGHT",
        "full": "FULL OUTER",
    }
    return mapping.get(plan_type.lower(), "INNER")


def _unwrap_for_union(
    compiled: Any,
) -> Tuple[str, List[Any]]:
    """Return ``(sql, params)`` regardless of whether ``compiled`` is a
    ``CteUnit`` or a ``ComposedSql`` (nested union)."""
    if isinstance(compiled, CteUnit):
        return compiled.sql, list(compiled.params or [])
    if isinstance(compiled, ComposedSql):
        return compiled.sql, list(compiled.params or [])
    raise ComposeCompileError(
        code=error_codes.UNSUPPORTED_PLAN_SHAPE,
        phase="compile",
        message=f"Unexpected compile result type: {type(compiled).__name__}",
    )


def _wrap_composed_as_unit(composed: ComposedSql, state: _CompileState) -> CteUnit:
    """Wrap a union-produced ``ComposedSql`` as a single ``CteUnit`` so
    join compilation can treat both sides uniformly."""
    return CteUnit(
        alias=state.next_alias(),
        sql=composed.sql,
        params=list(composed.params or []),
        select_columns=None,
    )


# ---------------------------------------------------------------------------
# Outer-select rendering (derived chain)
# ---------------------------------------------------------------------------


def _render_outer_select(
    *,
    plan: DerivedQueryPlan,
    inner_alias: str,
    inner_sql: str,
    dialect: str,
    source_columns: List[str],
) -> Tuple[str, List[Any]]:
    """Render ``SELECT <cols> FROM (<inner_sql>) AS <inner_alias> …``.

    The inner SQL is embedded once as a subquery; the outer select is
    stateless (no TableModel available — derived plans reference their
    source's output schema). Parameters for slice are emitted in
    encounter order; LIMIT / OFFSET are inlined (integer literals, not
    parameters, to match v1.3 engine convention).

    Derived output references are rendered with dialect-aware identifier
    quoting so aliases projected by the source subquery keep their exact
    spelling on case-folding databases such as PostgreSQL.
    """
    distinct_kw = "DISTINCT " if plan.distinct else ""
    column_list = (
        ", ".join(
            _render_select_column(
                column,
                inner_alias,
                dialect,
                source_columns=source_columns,
            )
            for column in plan.columns
        )
        if plan.columns
        else "*"
    )

    parts: List[str] = [
        f"SELECT {distinct_kw}{column_list}",
        f"FROM ({inner_sql}) AS {inner_alias}",
    ]
    params: List[Any] = []

    # WHERE — one item per slice entry; each is a {field, op, value} dict
    if plan.slice_:
        where_fragments, where_params = _render_slice(
            list(plan.slice_),
            inner_alias=inner_alias,
            dialect=dialect,
            source_columns=source_columns,
        )
        if where_fragments:
            parts.append("WHERE " + " AND ".join(where_fragments))
            params.extend(where_params)

    # GROUP BY
    if plan.group_by:
        parts.append(
            "GROUP BY " + ", ".join(
                _render_identifier(field, dialect) for field in plan.group_by
            )
        )

    # ORDER BY — entries may be "name" or "name:asc|desc" / dict forms
    if plan.order_by:
        order_fragments = [
            _render_order_entry(entry, dialect) for entry in plan.order_by
        ]
        parts.append("ORDER BY " + ", ".join(order_fragments))

    # LIMIT / OFFSET — inline integers (matches v1.3)
    if plan.limit is not None:
        if plan.start is not None:
            parts.append(f"LIMIT {int(plan.limit)} OFFSET {int(plan.start)}")
        else:
            parts.append(f"LIMIT {int(plan.limit)}")
    elif plan.start is not None:
        parts.append(f"OFFSET {int(plan.start)}")

    return "\n".join(parts), params


def _render_slice(
    slice_: List[Any],
    *,
    inner_alias: str,
    dialect: str,
    source_columns: List[str],
) -> Tuple[List[str], List[Any]]:
    """Render each slice entry as a WHERE predicate.

    Accepts two shapes:
      - ``{"field": F, "op": OP, "value": V}``
      - ``{F: V}`` (single-key shortcut; op defaults to ``=``)
      - ``{"field": F, "op": OP, "value": {"$field": R}}`` for
        field-to-field predicates over the source output schema.

    M6 derived slice is intentionally simple — richer operators (IN,
    BETWEEN, IS NULL) flow through v1.3 engine at the base level. If a
    derived slice needs those, the user should express them at the base
    layer before derivation, or wait for M7's script-level DSL.
    """
    fragments: List[str] = []
    params: List[Any] = []
    for entry in slice_:
        if not isinstance(entry, dict):
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    f"Derived slice entries must be dict, got "
                    f"{type(entry).__name__}"
                ),
            )
        if len(entry) == 1:
            key, val = next(iter(entry.items()))
            if key in _SYMMETRIC_LOGICAL_OPS:
                if not isinstance(val, (list, tuple)):
                    raise ComposeCompileError(
                        code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                        phase="plan-lower",
                        message=f"Logical operator {key} requires a list, got {type(val).__name__}",
                    )
                if not val:
                    continue
                sub_fragments, sub_params = _render_slice(
                    list(val),
                    inner_alias=inner_alias,
                    dialect=dialect,
                    source_columns=source_columns,
                )
                if sub_fragments:
                    if len(sub_fragments) == 1:
                        fragments.append(sub_fragments[0])
                    else:
                        op_str = f" {key[1:].upper()} "
                        fragments.append("(" + op_str.join(sub_fragments) + ")")
                    params.extend(sub_params)
                continue
            if key == "$not":
                sub_slice = val if isinstance(val, (list, tuple)) else [val]
                if not sub_slice:
                    continue
                sub_fragments, sub_params = _render_slice(
                    list(sub_slice),
                    inner_alias=inner_alias,
                    dialect=dialect,
                    source_columns=source_columns,
                )
                if sub_fragments:
                    joined = " AND ".join(sub_fragments)
                    fragments.append(f"NOT ({joined})")
                    params.extend(sub_params)
                continue

        if "field" in entry:
            field_name = entry["field"]
            op = entry.get("op", "=")
            value = entry.get("value")
        else:
            # Single-key shortcut
            if len(entry) != 1:
                raise ComposeCompileError(
                    code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                    phase="plan-lower",
                    message=(
                        f"Derived slice shortcut must have exactly 1 key, "
                        f"got {list(entry.keys())}"
                    ),
                )
            field_name, value = next(iter(entry.items()))
            op = "="
        field_sql = (
            _render_qualified_ref(inner_alias, str(field_name), dialect)
            if _is_simple_output_ref(str(field_name))
            else _render_expression_output_refs(
                str(field_name),
                inner_alias=inner_alias,
                dialect=dialect,
                source_columns=source_columns,
            )
        )
        value_sql, value_params = _render_slice_value(
            value,
            op=op,
            inner_alias=inner_alias,
            dialect=dialect,
        )
        rendered_op = _normalize_slice_op(op)
        if value_sql:
            fragments.append(f"{field_sql} {rendered_op} {value_sql}")
        else:
            fragments.append(f"{field_sql} {rendered_op}")
        params.extend(value_params)
    return fragments, params


def _render_slice_value(
    value: Any,
    *,
    op: str,
    inner_alias: str,
    dialect: str,
) -> Tuple[str, List[Any]]:
    if isinstance(value, dict) and set(value.keys()) == {"$field"}:
        ref = value.get("$field")
        if not isinstance(ref, str) or not _is_simple_output_ref(ref):
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    "Derived slice value {'$field': ...} requires a simple "
                    f"output field name, got {ref!r}"
                ),
            )
        return _render_qualified_ref(inner_alias, ref, dialect), []
    if isinstance(value, dict):
        raise ComposeCompileError(
            code=error_codes.UNSUPPORTED_PLAN_SHAPE,
            phase="plan-lower",
            message=(
                "Derived slice object values are unsupported except "
                "{'$field': '<output_field>'}; raw expression objects such "
                "as {'$expr': ...} are not a public DSL feature."
            ),
        )
    op_upper = _normalize_slice_op(op)
    if op_upper in {"IS NULL", "IS NOT NULL"}:
        return "", []
    if op_upper in {"IN", "NOT IN"}:
        if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, set)):
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    f"Derived slice operator {op_upper!r} requires a "
                    "list/tuple/set value."
                ),
            )
        values = list(value)
        if not values:
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    f"Derived slice operator {op_upper!r} requires at "
                    "least one value."
                ),
            )
        if any(isinstance(item, dict) for item in values):
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    f"Derived slice operator {op_upper!r} does not support "
                    "object values; raw expression objects such as "
                    "{'$expr': ...} are not a public DSL feature."
                ),
            )
        return "(" + ", ".join("?" for _ in values) + ")", values
    return "?", [value]


def _normalize_slice_op(op: Any) -> str:
    return " ".join(str(op).strip().upper().split())


def _render_order_entry(entry: Any, dialect: str) -> str:
    """Render one ``order_by`` entry into a ``<name> [ASC|DESC]`` fragment."""
    try:
        spec = normalize_order_by_item(entry)
    except TypeError as exc:
        raise ComposeCompileError(
            code=error_codes.UNSUPPORTED_PLAN_SHAPE,
            phase="plan-lower",
            message=(
                f"order_by entries must be str or dict, got "
                f"{type(entry).__name__}"
            ),
        ) from exc
    return f"{_render_identifier(spec.field, dialect)} {spec.direction.upper()}"
