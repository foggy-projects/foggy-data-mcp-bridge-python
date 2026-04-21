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
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from .result import SqlPreview, UnsupportedInM2Error

if TYPE_CHECKING:
    # Imported only for type hints; avoids circular import at runtime.
    from ..context.compose_query_context import ComposeQueryContext


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


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
    # Layer-C public surface — 5 methods, no more.
    # ------------------------------------------------------------------

    def query(
        self,
        *,
        columns: List[str],
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
        self, other: "QueryPlan", *, all: bool = False
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
        _require_plan(other, "union.other")
        return UnionPlan(left=self, right=other, all=bool(all))

    def join(
        self,
        other: "QueryPlan",
        *,
        type: str = "left",
        on: List["JoinOn"],
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
    ) -> Any:
        """Placeholder — wired in M7 (script runner ties QueryPlan to
        real execution via the compiler produced in M6)."""
        raise UnsupportedInM2Error(
            "QueryPlan.execute() is not implemented in 8.2.0.beta M2. "
            "Wiring arrives in M6 (SQL compile) + M7 (script runner)."
        )

    def to_sql(self) -> SqlPreview:
        """Placeholder — wired in M6 (SQL compile + dialect rendering)."""
        raise UnsupportedInM2Error(
            "QueryPlan.to_sql() is not implemented in 8.2.0.beta M2. "
            "Arrives in M6 together with the SQL compiler."
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

    def base_model_plans(self) -> Tuple["BaseModelPlan", ...]:
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

    def base_model_plans(self) -> Tuple[BaseModelPlan, ...]:
        return self.source.base_model_plans()


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
        raise ValueError(f"{field_name} must be non-empty")
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


def _freeze_columns(columns: List[str]) -> Tuple[str, ...]:
    if columns is None:
        raise ValueError("columns must not be None")
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
