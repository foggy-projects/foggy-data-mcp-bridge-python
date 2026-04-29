"""``QueryPlan`` object model — the logical-relation tree Compose Query
scripts build up.

Design constraints baked into this module
-----------------------------------------
1. **Layer-C whitelist**: every concrete plan exposes EXACTLY five
   methods (``query / union / join / execute / to_sql``). No iteration,
   no memory filter, no raw-SQL escape hatch. See
   ``M9-三层沙箱防护测试脚手架.md`` § Layer C.
2. **Immutable tree nodes**: frozen dataclasses so the same node can be
   shared across branches without aliasing bugs. This also ensures
   ``QueryPlan`` values are hashable — useful when the SQL compiler
   (M6) de-duplicates common subtrees into CTEs.
3. **No execution state**: nodes are pure descriptors. ``.execute()``
   and ``.to_sql()`` raise :class:`UnsupportedInM2Error` until M6/M7
   wire the runtime. This keeps M2 testable without DB / sandbox /
   compiler dependencies.
4. **Schema derivation deferred**: column reference validation (does
   ``derived.columns[*]`` actually exist in ``source`` output schema?)
   is M4 scope. M2 only enforces structural invariants (non-empty
   columns, ``model`` vs ``source`` mutual exclusion, union column-count
   parity, etc.).
5. **``from_()`` is the public constructor** — direct instantiation of
   the concrete classes is supported but not encouraged. The ``from_``
   function validates param shape; raw dataclass construction is for
   compiler/test internals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .result import SqlPreview, UnsupportedInM2Error

if TYPE_CHECKING:
    # Imported only for type hints; avoids circular import at runtime.
    from ..context.compose_query_context import ComposeQueryContext
    from ..sandbox import validate_derived_columns, validate_slice


# ---------------------------------------------------------------------------
# Abstract base and Ref Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProjectedColumn:
    ref: Any  # "PlanColumnRef" or "AggregateColumn" or "WindowColumn"
    alias: str
    caption: Optional[str] = None

    def as_(self, alias: str, caption: Optional[str] = None) -> "ProjectedColumn":
        """Re-alias an already-aliased projection. Useful for the union
        scenario where ``sales.sales_amount.as("amount")`` re-projects."""
        return ProjectedColumn(self.ref, alias, caption)

    def __getattr__(self, name: str) -> Any:
        # ``_alias_js_keyword`` is defined later in the module but resolved
        # at call time, so the forward reference is fine.
        return _alias_js_keyword(self, name)

    def to_column_expr(self) -> str:
        if hasattr(self.ref, "func"): # it's an AggregateColumn or WindowColumn
            base_expr = self.ref.to_column_expr()
        else:
            base_expr = self.ref.name
        
        if self.caption:
            return f"{base_expr}${self.caption} AS {self.alias}"
        return f"{base_expr} AS {self.alias}"

# JS-keyword aliases: scripts call ``.as("foo")`` (Python keyword), routed
# to ``.as_("foo")`` via ``__getattr__``. Same trick as ``QueryFactory.from``.

_JS_KEYWORD_ALIASES: Dict[str, str] = {
    "as": "as_",
}


def _alias_js_keyword(self: Any, name: str) -> Any:
    """Forward ``self.<JS-keyword>`` to the corresponding Python method.

    Raises :class:`AttributeError` if ``name`` is not in
    :data:`_JS_KEYWORD_ALIASES`, so the caller's normal attribute lookup
    can fall through (e.g. legitimate "missing attribute" bugs surface
    instead of being swallowed).
    """
    target = _JS_KEYWORD_ALIASES.get(name)
    if target is None:
        raise AttributeError(name)
    return getattr(self, target)


@dataclass(frozen=True)
class PlanColumnRef:
    plan: "QueryPlan"
    name: str

    def as_(self, alias: str, caption: Optional[str] = None) -> "ProjectedColumn":
        return ProjectedColumn(self, alias, caption)

    def __getattr__(self, name: str) -> Any:
        return _alias_js_keyword(self, name)

    def to_column_expr(self) -> str:
        return self.name

    def sum(self) -> "AggregateColumn":
        return AggregateColumn(self, "SUM")

    def count(self) -> "AggregateColumn":
        return AggregateColumn(self, "COUNT")

    def avg(self) -> "AggregateColumn":
        return AggregateColumn(self, "AVG")

    def max(self) -> "AggregateColumn":
        return AggregateColumn(self, "MAX")

    def min(self) -> "AggregateColumn":
        return AggregateColumn(self, "MIN")

    def lag(self, offset: int = 1) -> "WindowColumnBuilder":
        return WindowColumnBuilder("LAG", self, (offset,))

    def lead(self, offset: int = 1) -> "WindowColumnBuilder":
        return WindowColumnBuilder("LEAD", self, (offset,))

@dataclass(frozen=True)
class AggregateColumn:
    ref: "PlanColumnRef"
    func: str

    def as_(self, alias: str, caption: Optional[str] = None) -> "ProjectedColumn":
        return ProjectedColumn(self, alias, caption)

    def __getattr__(self, name: str) -> Any:
        return _alias_js_keyword(self, name)

    def to_column_expr(self) -> str:
        return f"{self.func}({self.ref.name})"

    def over(self, config: Dict[str, Any]) -> "WindowColumn":
        return WindowColumn(self.func, self.ref, (), OverClause.from_dict(config))

@dataclass(frozen=True)
class OverClause:
    partition_by: Tuple[str, ...] = ()
    order_by: Tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "OverClause":
        pb = config.get("partitionBy", [])
        pb_parsed = tuple(x.name if hasattr(x, "name") else str(x) for x in pb)
        
        ob = config.get("orderBy", [])
        ob_parsed = tuple(x.name if hasattr(x, "name") else str(x) for x in ob)
        
        return cls(partition_by=pb_parsed, order_by=ob_parsed)

@dataclass(frozen=True)
class WindowColumn:
    func: str
    ref: Optional["PlanColumnRef"]
    args: Tuple[Any, ...]
    over: OverClause

    def as_(self, alias: str, caption: Optional[str] = None) -> "ProjectedColumn":
        return ProjectedColumn(self, alias, caption)

    def __getattr__(self, name: str) -> Any:
        return _alias_js_keyword(self, name)

    def to_column_expr(self) -> str:
        parts = []
        if self.ref:
            parts.append(self.ref.name)
        if self.args:
            parts.extend(str(a) for a in self.args)
        
        args_str = ", ".join(parts)
        base = f"{self.func}({args_str}) OVER ("
        
        over_parts = []
        if self.over.partition_by:
            over_parts.append("PARTITION BY " + ", ".join(self.over.partition_by))
        
        if self.over.order_by:
            ob_strs = []
            for col in self.over.order_by:
                if col.startswith("-"):
                    ob_strs.append(f"{col[1:]} DESC")
                else:
                    ob_strs.append(f"{col} ASC")
            over_parts.append("ORDER BY " + ", ".join(ob_strs))
            
        return base + " ".join(over_parts) + ")"

@dataclass(frozen=True)
class WindowColumnBuilder:
    func: str
    ref: Optional["PlanColumnRef"]
    args: Tuple[Any, ...]

    def over(self, config: Dict[str, Any]) -> "WindowColumn":
        return WindowColumn(self.func, self.ref, self.args, OverClause.from_dict(config))

class ComposeJoinBuilder:
    def __init__(self, left: "QueryPlan", right: "QueryPlan", join_type: str):
        self.left = left
        self.right = right
        self.join_type = join_type

    def on(self, left_col: "PlanColumnRef", right_col: "PlanColumnRef") -> "JoinPlan":
        return JoinPlan(
            left=self.left,
            right=self.right,
            type=self.join_type,
            on=(JoinOn(left_col.name, "=", right_col.name),)
        )



class QueryPlan(ABC):
    """Base type for every Compose Query plan node.

    Concrete subclasses are frozen dataclasses (see below). The abstract
    layer exists so:

    * Type annotations can say ``QueryPlan`` without committing to a
      specific shape.
    * ``isinstance(x, QueryPlan)`` reliably filters plan-typed values in
      the compiler, resolver, and sandbox layers.
    * The five public methods live here, inherited by every subclass,
      so Layer-C enforcement can assert "surface area == these 5".

    Do NOT add ``__init__`` here — subclasses use ``@dataclass(frozen=True)``
    which synthesises its own constructor.
    """

    # ------------------------------------------------------------------
    # Layer-C public surface — 5 methods, no more. (M2 Core)
    # ------------------------------------------------------------------

    # Layer-C forbidden names — must NOT be exposed as field references.
    # These are the names that the sandbox scanner rejects; __getattr__
    # must agree, otherwise hasattr() returns True and the security
    # invariant breaks.
    _LAYER_C_FORBIDDEN = frozenset({
        "raw", "raw_sql", "memory_filter", "for_each", "forEach",
        "memoryFilter", "items", "rows", "to_array", "toArray",
    })

    def __getattr__(self, name: str) -> PlanColumnRef:
        if name.startswith("_") or name in self._LAYER_C_FORBIDDEN:
            raise AttributeError(name)
        return PlanColumnRef(self, name)

    # ---- Window Function Builders ----

    def rowNumber(self) -> WindowColumnBuilder:
        return WindowColumnBuilder("ROW_NUMBER", None, ())

    def rank(self) -> WindowColumnBuilder:
        return WindowColumnBuilder("RANK", None, ())

    def denseRank(self) -> WindowColumnBuilder:
        return WindowColumnBuilder("DENSE_RANK", None, ())

    def where(self, slice_: List[Dict[str, Any]]) -> "DerivedQueryPlan":
        return self.query(slice=slice_)

    def groupBy(self, *fields) -> "DerivedQueryPlan":
        # support both strings and PlanColumnRef/ProjectedColumn
        resolved = []
        for f in fields:
            if isinstance(f, PlanColumnRef):
                resolved.append(f.name)
            elif isinstance(f, ProjectedColumn):
                resolved.append(f.alias)
            elif isinstance(f, str):
                resolved.append(f)
            else:
                resolved.append(str(f))
        return self.query(group_by=resolved)

    def orderBy(self, *fields) -> "DerivedQueryPlan":
        resolved = []
        for f in fields:
            if isinstance(f, PlanColumnRef):
                resolved.append(f.name)
            elif isinstance(f, str):
                resolved.append(f)
            else:
                resolved.append(str(f))
        return self.query(order_by=resolved)

    def limit(self, n: int) -> "DerivedQueryPlan":
        return self.query(limit=n)

    def offset(self, n: int) -> "DerivedQueryPlan":
        return self.query(start=n)

    def select(self, *args) -> "DerivedQueryPlan":
        columns = []
        seen_aliases = set()
        for arg in args:
            if isinstance(arg, ProjectedColumn):
                expr = arg.to_column_expr()
                alias = arg.alias
            elif isinstance(arg, PlanColumnRef):
                expr = arg.to_column_expr()
                alias = arg.name
            elif isinstance(arg, AggregateColumn):
                expr = arg.to_column_expr()
                alias = expr  # without alias it's just the function string
            elif isinstance(arg, WindowColumn):
                expr = arg.to_column_expr()
                alias = expr
            elif isinstance(arg, str):
                expr = arg
                parts = arg.split(" AS ")
                if len(parts) == 2:
                    alias = parts[1].strip()
                elif " as " in arg.lower():
                    alias = arg.lower().split(" as ")[1].strip()
                else:
                    alias = arg
            else:
                raise TypeError(f"Invalid select argument type: {type(arg)}")
            
            if alias in seen_aliases:
                raise ValueError(
                    f"Column '{alias}' is ambiguous. Please use .as_('new_name') to disambiguate."
                )
            seen_aliases.add(alias)
            columns.append(expr)
        return self.query(columns=columns)

    def leftJoin(self, other: "QueryPlan") -> "ComposeJoinBuilder":
        return ComposeJoinBuilder(self, other, "left")

    def innerJoin(self, other: "QueryPlan") -> "ComposeJoinBuilder":
        return ComposeJoinBuilder(self, other, "inner")

    def rightJoin(self, other: "QueryPlan") -> "ComposeJoinBuilder":
        return ComposeJoinBuilder(self, other, "right")

    def fullJoin(self, other: "QueryPlan") -> "ComposeJoinBuilder":
        return ComposeJoinBuilder(self, other, "full")


    def query(
        self,
        options_dict: Optional[Dict[str, Any]] = None,
        *,
        columns: Optional[List[str]] = None,
        slice: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        start: Optional[int] = None,
        distinct: bool = False,
    ) -> "DerivedQueryPlan":
        """Build a derived plan whose ``source`` is this plan.

        Equivalent to the kernel ``from_(source=self, columns=..., ...)``
        — same validation rules apply. This method is the sugar entry
        point; scripts tend to read more naturally as a chain
        (``base.query(...).union(...)``) than as nested calls.
        """
        if options_dict is not None:
            if not isinstance(options_dict, dict):
                raise TypeError("options_dict must be a dictionary")
            columns = options_dict.get("columns", columns)
            slice = options_dict.get("slice", slice)
            group_by = options_dict.get("groupBy", group_by)
            order_by = options_dict.get("orderBy", order_by)
            limit = options_dict.get("limit", limit)
            start = options_dict.get("start", start)
            distinct = options_dict.get("distinct", distinct)

        from ..sandbox import validate_derived_columns, validate_slice
        validate_derived_columns(columns, "plan-build")
        validate_slice(slice, "plan-build")

        return DerivedQueryPlan(
            source=self,
            columns=_freeze_columns(columns),
            slice_=_freeze_opt_list(slice),
            group_by=_freeze_opt_str_list(group_by),
            order_by=_freeze_opt_str_list(order_by),
            limit=limit,
            start=start,
            distinct=distinct,
        )

    def union(
        self, other: "QueryPlan", options_dict: Optional[Dict[str, Any]] = None, *, all: bool = False
    ) -> "UnionPlan":
        """Build a union of this plan with ``other``. ``all=True`` selects
        ``UNION ALL``; any other truthy-ish rule is rejected to keep the
        contract sharp.

        M2 enforces structural rules only:
        * ``other`` must be a ``QueryPlan`` instance.
        * Column-count parity is NOT enforced here (M4 handles it once
          schema derivation lands). Passing mismatched plans is currently
          a deferred error — M4 raises at schema-derive time.
        """
        if options_dict is not None:
            if not isinstance(options_dict, dict):
                raise TypeError("options_dict must be a dictionary")
            all = options_dict.get("all", all)
            
        _require_plan(other, "union.other")
        return UnionPlan(left=self, right=other, all=bool(all))

    def join(
        self,
        other: "QueryPlan",
        options_dict: Optional[Dict[str, Any]] = None,
        on_arg: Optional[List["JoinOn"]] = None,
        *,
        type: str = "left",
        on: Optional[List["JoinOn"]] = None,
    ) -> "JoinPlan":
        """Build a join of this plan with ``other``.

        Parameters
        ----------
        other:
            Right-side plan. Must be a ``QueryPlan`` instance.
        type:
            Join type — one of ``"inner"``, ``"left"``, ``"right"``,
            ``"full"``. Case-insensitive; normalised to lowercase on
            the returned node.
        on:
            Non-empty list of :class:`JoinOn` conditions. Empty ``on``
            is rejected — cross joins are NOT in the M2 scope.
        """
        if options_dict is not None:
            if isinstance(options_dict, dict):
                type = options_dict.get("type", type)
                on = options_dict.get("on", on)
            elif isinstance(options_dict, str):
                type = options_dict
                on = on_arg if on_arg is not None else on
            else:
                raise TypeError("join options must be a dictionary or join type string")
        elif on_arg is not None:
            raise TypeError("positional join conditions require a join type string")
            
        _require_plan(other, "join.other")
        norm_type = _normalise_join_type(type)
        if not on:
            raise ValueError(
                "JoinPlan.on must be non-empty; cross joins are not "
                "supported in 8.2.0.beta M2. Provide at least one "
                "JoinOn condition."
            )
        return JoinPlan(
            left=self,
            right=other,
            type=norm_type,
            on=tuple(_coerce_join_on(o) for o in on),
        )

    def execute(
        self, context: Optional["ComposeQueryContext"] = None
    ) -> List[Dict[str, Any]]:
        """Compile this plan to SQL and execute it, returning rows.

        Wired in M7. Relies on an ambient :class:`ComposeRuntimeBundle`
        established by :func:`run_script` (or manually via
        :func:`set_bundle` for host-controlled scenarios). The bundle
        carries the ``semantic_service`` / ``dialect`` /
        :class:`ComposeQueryContext` that the compiler + executor need.

        Parameters
        ----------
        context:
            Optional explicit :class:`ComposeQueryContext`. When omitted,
            the bundle's ``ctx`` is used. A caller outside
            :func:`run_script` can pre-set a bundle to drive this path.

        Raises
        ------
        RuntimeError:
            When no ambient bundle is present (host configuration bug).
            The ``compose-compile-error/*`` family is reserved for
            compile-phase failures — host misconfiguration does not
            belong there.
        AuthorityResolutionError / ComposeSchemaError / ComposeCompileError:
            Propagated from the M6 compile pipeline.
        """
        from ..runtime.plan_execution import execute_plan
        from ..runtime.script_runtime import current_bundle

        bundle = current_bundle()
        if bundle is None:
            raise RuntimeError(
                "QueryPlan.execute requires an ambient ComposeRuntimeBundle; "
                "call from inside run_script(), or wrap manually via "
                "set_bundle(...). Host misconfiguration (semantic_service / "
                "dialect not bound) cannot be surfaced as ComposeCompileError "
                "— that family is reserved for compile-phase failures."
            )
        effective_ctx = context if context is not None else bundle.ctx
        return execute_plan(
            self,
            effective_ctx,
            semantic_service=bundle.semantic_service,
            dialect=bundle.dialect,
        )

    def to_sql(
        self,
        context: Optional["ComposeQueryContext"] = None,
        *,
        dialect: Optional[str] = None,
    ):
        """Compile this plan to dialect-aware SQL + params without
        executing it.

        Returns a :class:`ComposedSql` — the M6 compiler output. NOTE:
        M2 used :class:`SqlPreview` as a placeholder; M7 upgrades the
        return type to :class:`ComposedSql`. :class:`SqlPreview` is kept
        as a legacy export so downstream code that imported the name
        still works, but :meth:`to_sql` no longer returns it.

        Parameters
        ----------
        context:
            Optional explicit :class:`ComposeQueryContext`. When omitted,
            the ambient bundle's ``ctx`` is used.
        dialect:
            Optional dialect override (useful for multi-dialect snapshot
            testing). Falls back to the bundle's dialect, then to
            ``"mysql"``.

        Raises
        ------
        RuntimeError:
            No bundle and no explicit ``context``; or no bundle and no
            ``semantic_service`` available.
        """
        from ..compilation.compiler import compile_plan_to_sql
        from ..runtime.script_runtime import current_bundle

        bundle = current_bundle()
        if bundle is None and context is None:
            raise RuntimeError(
                "QueryPlan.to_sql requires either an explicit context or "
                "an ambient ComposeRuntimeBundle"
            )
        effective_ctx = context if context is not None else bundle.ctx
        effective_svc = bundle.semantic_service if bundle is not None else None
        effective_dialect = (
            dialect if dialect is not None
            else (bundle.dialect if bundle is not None else "mysql")
        )
        if effective_svc is None:
            raise RuntimeError(
                "QueryPlan.to_sql: semantic_service unbound (pass context + "
                "set_bundle, or call from inside run_script)"
            )
        return compile_plan_to_sql(
            self,
            effective_ctx,
            semantic_service=effective_svc,
            dialect=effective_dialect,
        )

    # ------------------------------------------------------------------
    # Internal helpers exposed on the base so the compiler can walk the
    # tree without importing every subclass.
    # ------------------------------------------------------------------

    @abstractmethod
    def base_model_plans(self) -> Tuple["BaseModelPlan", ...]:
        """Return the leaf ``BaseModelPlan`` nodes reachable from this
        node, in left-to-right preorder. Used by the authority-resolution
        pipeline (M5) to batch-resolve bindings before compilation."""

    @abstractmethod
    def collect_visible_plans(self) -> "Tuple[QueryPlan, ...]":
        """G5 Phase 2 (F5) · Return all plans visible from this plan node
        for F5 plan-qualified column reference validation per spec §5.1.

        The returned tuple includes ``self`` plus every plan transitively
        reachable through structural children:

        * ``BaseModelPlan`` — leaf, returns ``(self,)``
        * ``DerivedQueryPlan`` — ``(self,) + source.collect_visible_plans()``
        * ``JoinPlan`` / ``UnionPlan`` — ``(self,) + left.visible + right.visible``

        **Identity-keyed** per spec §5.1 warning: visibility-membership
        checks at call sites must use ``is`` (object identity), not
        ``==``. Same model name referenced via two distinct ``dsl()``
        calls produces two distinct plan instances that are NOT
        interchangeable.

        Returns a tuple (not a set) so duplicate plan instances in the
        same lineage stay distinguishable; membership testing uses
        ``any(p is needle for p in visible)``.
        """


# ---------------------------------------------------------------------------
# Join condition carrier
# ---------------------------------------------------------------------------


_ALLOWED_JOIN_OPS: frozenset = frozenset({"=", "!=", "<", ">", "<=", ">="})


@dataclass(frozen=True)
class JoinOn:
    """One ``ON`` predicate in a JoinPlan.

    Shape matches the spec examples literally:
        ``{"left": "partnerId", "op": "=", "right": "partnerId"}``

    M2 accepts only equality-family operators ({``=``, ``!=``, ``<``,
    ``>``, ``<=``, ``>=``}). Richer predicates (IN, BETWEEN, IS NULL) are
    deferred — they introduce compile-time vs runtime null-handling
    decisions that the M6 SQL compiler owns.
    """

    left: str
    op: str
    right: str

    def __post_init__(self) -> None:
        if not self.left:
            raise ValueError("JoinOn.left must be non-empty")
        if not self.right:
            raise ValueError("JoinOn.right must be non-empty")
        if self.op not in _ALLOWED_JOIN_OPS:
            raise ValueError(
                f"JoinOn.op must be one of {sorted(_ALLOWED_JOIN_OPS)}, "
                f"got {self.op!r}"
            )


# ---------------------------------------------------------------------------
# Concrete plan nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaseModelPlan(QueryPlan):
    """Leaf node pointing at a physical QM.

    Authority binding (M5) resolves per ``BaseModelPlan`` — that is why
    the same QM referenced twice in a script materialises as two distinct
    BaseModelPlan values, each with its own authority lifecycle.
    """

    model: str
    columns: Tuple[str, ...]
    slice_: Tuple[Any, ...] = ()
    group_by: Tuple[str, ...] = ()
    order_by: Tuple[str, ...] = ()
    limit: Optional[int] = None
    start: Optional[int] = None
    distinct: bool = False

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("BaseModelPlan.model must be non-empty")
        _validate_columns(self.columns, "BaseModelPlan.columns")
        _validate_pagination(self.limit, self.start, "BaseModelPlan")
        # No F5 plan-visibility check here: `_validate_columns` already
        # rejects non-string entries, and Python flattens F5 dicts to
        # strings at parse time (column_normalizer module docstring).

    def base_model_plans(self) -> Tuple["BaseModelPlan", ...]:
        return (self,)

    def collect_visible_plans(self) -> Tuple[QueryPlan, ...]:
        # BaseModelPlan is a leaf — visible set is just `(self,)`.
        # Identity comparison at call sites uses `is`.
        return (self,)


@dataclass(frozen=True)
class DerivedQueryPlan(QueryPlan):
    """Plan derived from another plan's output schema.

    Per spec §3, derived plans are restricted to references visible in
    ``source``'s output schema. M2 does not enforce this — M4 does —
    but the structural carriage is here so M4 has something to validate
    against.
    """

    source: QueryPlan
    columns: Tuple[str, ...]
    slice_: Tuple[Any, ...] = ()
    group_by: Tuple[str, ...] = ()
    order_by: Tuple[str, ...] = ()
    limit: Optional[int] = None
    start: Optional[int] = None
    distinct: bool = False

    def __post_init__(self) -> None:
        _require_plan(self.source, "DerivedQueryPlan.source")
        _validate_columns(self.columns, "DerivedQueryPlan.columns")
        _validate_pagination(self.limit, self.start, "DerivedQueryPlan")
        # F5 visibility no-op — see `BaseModelPlan.__post_init__`.

    def base_model_plans(self) -> Tuple[BaseModelPlan, ...]:
        return self.source.base_model_plans()

    def collect_visible_plans(self) -> Tuple[QueryPlan, ...]:
        # Derived = (self,) + source.visible — source's visible already
        # includes source itself recursively.
        return (self,) + self.source.collect_visible_plans()


@dataclass(frozen=True)
class UnionPlan(QueryPlan):
    """Set-union of two plans.

    Both branches must come from the same data source — cross-datasource
    union is rejected by the compiler (M6). M2 does not have datasource
    information available, so enforcement is deferred.
    """

    left: QueryPlan
    right: QueryPlan
    all: bool = False  # True => UNION ALL; False => UNION

    def __post_init__(self) -> None:
        _require_plan(self.left, "UnionPlan.left")
        _require_plan(self.right, "UnionPlan.right")

    def base_model_plans(self) -> Tuple[BaseModelPlan, ...]:
        return self.left.base_model_plans() + self.right.base_model_plans()

    def collect_visible_plans(self) -> Tuple[QueryPlan, ...]:
        # Union = (self,) + left.visible + right.visible
        return (self,) + self.left.collect_visible_plans() + self.right.collect_visible_plans()


@dataclass(frozen=True)
class JoinPlan(QueryPlan):
    """Relational join of two plans.

    Same-datasource constraint, like UnionPlan. ``on`` is a non-empty
    tuple of :class:`JoinOn`.
    """

    left: QueryPlan
    right: QueryPlan
    type: str  # "inner" | "left" | "right" | "full"
    on: Tuple[JoinOn, ...]

    def __post_init__(self) -> None:
        _require_plan(self.left, "JoinPlan.left")
        _require_plan(self.right, "JoinPlan.right")
        if self.type not in _VALID_JOIN_TYPES:
            raise ValueError(
                f"JoinPlan.type must be one of {sorted(_VALID_JOIN_TYPES)}, "
                f"got {self.type!r}"
            )
        if not self.on:
            raise ValueError("JoinPlan.on must be non-empty")
        for i, condition in enumerate(self.on):
            if not isinstance(condition, JoinOn):
                raise TypeError(
                    f"JoinPlan.on[{i}] must be a JoinOn instance, got "
                    f"{type(condition).__name__}"
                )

    def base_model_plans(self) -> Tuple[BaseModelPlan, ...]:
        return self.left.base_model_plans() + self.right.base_model_plans()

    def collect_visible_plans(self) -> Tuple[QueryPlan, ...]:
        # Join = (self,) + left.visible + right.visible — each branch's full subtree.
        return (self,) + self.left.collect_visible_plans() + self.right.collect_visible_plans()

    def and_(self, left_col: "PlanColumnRef", right_col: "PlanColumnRef") -> "JoinPlan":
        new_on = self.on + (JoinOn(left_col.name, "=", right_col.name),)
        return JoinPlan(left=self.left, right=self.right, type=self.type, on=new_on)


# ---------------------------------------------------------------------------
# Validation helpers (module-private)
# ---------------------------------------------------------------------------


_VALID_JOIN_TYPES: frozenset = frozenset({"inner", "left", "right", "full"})


def _normalise_join_type(raw: str) -> str:
    if not isinstance(raw, str):
        raise TypeError(
            f"join(type=...) must be a str, got {type(raw).__name__}"
        )
    lowered = raw.strip().lower()
    if lowered not in _VALID_JOIN_TYPES:
        raise ValueError(
            f"join(type=...) must be one of {sorted(_VALID_JOIN_TYPES)}, "
            f"got {raw!r}"
        )
    return lowered


def _coerce_join_on(value: Any) -> JoinOn:
    if isinstance(value, JoinOn):
        return value
    if isinstance(value, dict):
        try:
            return JoinOn(
                left=value["left"], op=value["op"], right=value["right"]
            )
        except KeyError as exc:  # missing key
            raise ValueError(
                f"JoinOn dict missing key {exc.args[0]!r}; required keys: "
                "left, op, right"
            ) from None
    raise TypeError(
        f"JoinOn entries must be JoinOn or dict, got {type(value).__name__}"
    )


def _require_plan(value: Any, field_name: str) -> None:
    if not isinstance(value, QueryPlan):
        raise TypeError(
            f"{field_name} must be a QueryPlan instance, got "
            f"{type(value).__name__}"
        )


def _validate_columns(columns: Tuple[str, ...], field_name: str) -> None:
    if not columns:
        return  # Allow empty columns for chained base plan
    for i, c in enumerate(columns):
        if not isinstance(c, str) or not c:
            raise ValueError(
                f"{field_name}[{i}] must be a non-empty str, got {c!r}"
            )


def _validate_pagination(
    limit: Optional[int], start: Optional[int], owner: str
) -> None:
    if limit is not None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise ValueError(
                f"{owner}.limit must be a non-negative int or None; "
                f"got {limit!r}"
            )
    if start is not None:
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            raise ValueError(
                f"{owner}.start must be a non-negative int or None; "
                f"got {start!r}"
            )


def _freeze_columns(columns: Optional[List[str]]) -> Tuple[str, ...]:
    if columns is None:
        return ()
    return tuple(columns)


def _freeze_opt_list(value: Optional[List[Any]]) -> Tuple[Any, ...]:
    if value is None:
        return ()
    return tuple(value)


def _freeze_opt_str_list(value: Optional[List[str]]) -> Tuple[str, ...]:
    if value is None:
        return ()
    out: List[str] = []
    for i, v in enumerate(value):
        if not isinstance(v, str) or not v:
            raise ValueError(
                f"list entry[{i}] must be a non-empty str, got {v!r}"
            )
        out.append(v)
    return tuple(out)
