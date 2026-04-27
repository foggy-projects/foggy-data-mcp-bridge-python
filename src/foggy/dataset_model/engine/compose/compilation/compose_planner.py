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
from foggy.dataset_model.engine.compose.schema.derive import derive_schema
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
        ``PER_BASE_COMPILE_FAILED``.
    """
    _assert_dialect(dialect)
    state = _CompileState(
        bindings=bindings,
        semantic_service=semantic_service,
        dialect=dialect,
        g10_enabled=feature_flags.g10_enabled(),
    )
    # G10 PR4 · plan-aware permission validation. Runs only when the
    # G10 flag is on; under flag=off the legacy single-QM
    # ``SemanticServiceV3._resolve_effective_visible`` path continues
    # to enforce flat-whitelist semantics without any change.
    if state.g10_enabled:
        _run_plan_aware_permission_check(plan, bindings)
    result = _compile_any(plan, state)
    if isinstance(result, ComposedSql):
        return result
    # Top-level CteUnit (base / derived) — wrap for dialect-consistent output.
    return CteComposer.compose(
        units=[result],
        join_specs=[],
        use_cte=dialect_supports_cte(dialect),
    )


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
    return compile_base_model(
        plan,
        binding,
        semantic_service=state.semantic_service,
        alias=alias,
        governance_cache=state.governance_cache,
    )


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

    outer_sql, outer_params = _render_outer_select(
        plan=plan,
        inner_alias=inner.alias,
        inner_sql=inner.sql,
    )
    derived_alias = state.next_alias()
    _register_plan_alias(state, plan, derived_alias)
    return CteUnit(
        alias=derived_alias,
        sql=outer_sql,
        params=list(inner.params) + list(outer_params),
        select_columns=list(plan.columns),
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
    """
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
            f"{left_unit.alias}.{o.left} {o.op} {right_unit.alias}.{o.right}"
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
    )


def _compile_union(plan: UnionPlan, state: _CompileState) -> ComposedSql:
    """Compile a ``UnionPlan`` — emits native ``UNION`` / ``UNION ALL`` SQL.

    Unions are NOT expressed through ``CteComposer.JoinSpec`` — that
    machinery is ON-condition-driven, and unions are column-aligned.
    Instead we render both sides (recursively), then concatenate with
    ``\\nUNION [ALL]\\n``. Params flow left → right.
    """
    left = _compile_any(plan.left, state)
    right = _compile_any(plan.right, state)

    left_sql, left_params = _unwrap_for_union(left)
    right_sql, right_params = _unwrap_for_union(right)

    keyword = "UNION ALL" if plan.all else "UNION"
    sql = f"({left_sql})\n{keyword}\n({right_sql})"
    return ComposedSql(sql=sql, params=list(left_params) + list(right_params))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
) -> Tuple[str, List[Any]]:
    """Render ``SELECT <cols> FROM (<inner_sql>) AS <inner_alias> …``.

    The inner SQL is embedded once as a subquery; the outer select is
    stateless (no TableModel available — derived plans reference their
    source's output schema). Parameters for slice are emitted in
    encounter order; LIMIT / OFFSET are inlined (integer literals, not
    parameters, to match v1.3 engine convention).

    The SQL produced is intentionally plain-ANSI and **not** dialect-
    specific — dialect-aware paren / alias quoting is handled downstream
    by ``CteComposer``. Derived-chain snapshots in 6.5 verify 4 dialects
    still round-trip.
    """
    distinct_kw = "DISTINCT " if plan.distinct else ""
    column_list = ", ".join(plan.columns) if plan.columns else "*"

    parts: List[str] = [
        f"SELECT {distinct_kw}{column_list}",
        f"FROM ({inner_sql}) AS {inner_alias}",
    ]
    params: List[Any] = []

    # WHERE — one item per slice entry; each is a {field, op, value} dict
    if plan.slice_:
        where_fragments, where_params = _render_slice(list(plan.slice_))
        if where_fragments:
            parts.append("WHERE " + " AND ".join(where_fragments))
            params.extend(where_params)

    # GROUP BY
    if plan.group_by:
        parts.append("GROUP BY " + ", ".join(plan.group_by))

    # ORDER BY — entries may be "name" or "name:asc|desc" / dict forms
    if plan.order_by:
        order_fragments = [_render_order_entry(entry) for entry in plan.order_by]
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


def _render_slice(slice_: List[Any]) -> Tuple[List[str], List[Any]]:
    """Render each slice entry as ``<field> <op> ?`` with a bound param.

    Accepts two shapes:
      - ``{"field": F, "op": OP, "value": V}``
      - ``{F: V}`` (single-key shortcut; op defaults to ``=``)

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
        fragments.append(f"{field_name} {op} ?")
        params.append(value)
    return fragments, params


def _render_order_entry(entry: Any) -> str:
    """Render one ``order_by`` entry into a ``<name> [ASC|DESC]`` fragment."""
    if isinstance(entry, str):
        # Allow "name" or "name:desc"
        if ":" in entry:
            name, direction = entry.split(":", 1)
            direction = direction.strip().upper()
            if direction not in ("ASC", "DESC"):
                direction = "ASC"
            return f"{name.strip()} {direction}"
        return entry
    if isinstance(entry, dict):
        name = entry.get("field") or entry.get("column")
        direction = (entry.get("dir") or entry.get("direction") or "asc").upper()
        if direction not in ("ASC", "DESC"):
            direction = "ASC"
        return f"{name} {direction}"
    raise ComposeCompileError(
        code=error_codes.UNSUPPORTED_PLAN_SHAPE,
        phase="plan-lower",
        message=(
            f"order_by entries must be str or dict, got "
            f"{type(entry).__name__}"
        ),
    )
