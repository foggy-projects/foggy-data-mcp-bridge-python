"""``OutputSchema`` — the declared (pre-binding) output shape of one
``QueryPlan`` node.

M4 operates on *declared* schemas: what the user wrote in ``columns``.
Types are intentionally left unset here (``data_type`` is reserved for
M5/M6 when QM type info + authority binding become available).

Design
------
Frozen dataclasses throughout so schema values are value-equal, hashable,
and safe to share between plan nodes. ``OutputSchema`` is an ordered,
duplicate-free bag of ``ColumnSpec``; order matters because ``UnionPlan``
aligns columns positionally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from ..plan.plan_id import PlanId


@dataclass(frozen=True, eq=False)
class ColumnSpec:
    """One column in an :class:`OutputSchema`.

    Attributes
    ----------
    name:
        Output name. After alias resolution this is what the next plan
        layer references — e.g. ``"totalAmount"`` not
        ``"SUM(amount) AS totalAmount"``.
    expression:
        The full expression text before alias stripping. Preserved so M6
        can lower the expression to SQL without re-parsing the alias.
    source_model:
        QM name that originally produced this column (``BaseModelPlan``)
        or ``None`` when the column flows through a derived / union /
        join and source attribution is lost. Informational only in M4.
    data_type:
        Reserved for M5/M6 type inference; always ``None`` from M4
        derivation.
    has_explicit_alias:
        ``True`` iff the user wrote ``... AS <alias>``. Used only for
        error-message disambiguation; does not change behaviour.
    plan_provenance:
        **G10 PR1** · Plan-level identity of the node that produced this
        column, captured as a :class:`PlanId` (transient weak reference).
        ``None`` in PR1 — no producer sets it yet. Filled in by G10 PR2
        (flag-gated SchemaDerivation refactor) so post-join disambiguation
        (G5 F5) and plan-routed permissions can resolve a column back to
        its plan.
    is_ambiguous:
        **G10 PR1** · ``True`` when this column name occurs in multiple
        side schemas of a join (the same name appears on both ``left``
        and ``right``). ``False`` in PR1 — no producer sets it yet.
        Filled in by G10 PR2.

    G10 PR1 真零行为变化保证
    -----------------------
    The new ``plan_provenance`` / ``is_ambiguous`` fields default to
    ``None`` / ``False`` and are *not* read by any compiler / validator /
    lookup path in PR1. They are also **excluded** from ``__eq__`` /
    ``__hash__`` — the existing equality contract (name + expression +
    source_model + data_type + has_explicit_alias) is preserved
    bitwise. PR2 (when fields actually get set) will revisit whether to
    include ``plan_provenance`` in equality.
    """

    name: str
    expression: str
    source_model: Optional[str] = None
    data_type: Optional[str] = None
    has_explicit_alias: bool = False
    # G10 PR1 — types only, no producer sets these yet
    plan_provenance: Optional[PlanId] = None
    is_ambiguous: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError(
                f"ColumnSpec.name must be a non-empty str, got {self.name!r}"
            )
        if not isinstance(self.expression, str) or not self.expression:
            raise ValueError(
                f"ColumnSpec.expression must be a non-empty str, got "
                f"{self.expression!r}"
            )

    # G10 PR1 真零行为：equality unchanged from M4 era. ``plan_provenance``
    # / ``is_ambiguous`` are excluded from equality so existing tests / compare
    # paths see no behavior shift. PR2 will revisit when fields actually carry
    # meaningful values.
    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, ColumnSpec):
            return NotImplemented
        return (
            self.name == other.name
            and self.expression == other.expression
            and self.source_model == other.source_model
            and self.data_type == other.data_type
            and self.has_explicit_alias == other.has_explicit_alias
        )

    def __hash__(self) -> int:
        return hash((
            self.name,
            self.expression,
            self.source_model,
            self.data_type,
            self.has_explicit_alias,
        ))


@dataclass(frozen=True)
class OutputSchema:
    """Ordered, duplicate-free list of :class:`ColumnSpec`.

    Duplicate output names are rejected at construction — the spec
    requires ``JoinPlan`` to resolve column-name conflicts via explicit
    alias, so any duplicate surviving into an OutputSchema is a
    derivation bug the caller must fix (usually by writing ``... AS <x>``).

    Iteration order follows construction order. Positional lookup is
    ``O(1)`` via ``columns[i]``; name lookup is ``O(n)`` via
    :meth:`get` or ``O(1)`` via :meth:`index_of` (cached map).
    """

    columns: Tuple[ColumnSpec, ...] = ()

    def __post_init__(self) -> None:
        seen: Dict[str, int] = {}
        for i, c in enumerate(self.columns):
            if not isinstance(c, ColumnSpec):
                raise TypeError(
                    f"OutputSchema.columns[{i}] must be ColumnSpec, got "
                    f"{type(c).__name__}"
                )
            if c.name in seen:
                raise ValueError(
                    f"OutputSchema contains duplicate output column "
                    f"{c.name!r} (first at index {seen[c.name]}, "
                    f"again at index {i})"
                )
            seen[c.name] = i

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def of(cls, columns: List[ColumnSpec]) -> "OutputSchema":
        """Construct from a list of :class:`ColumnSpec`; convenience so
        callers don't have to build a tuple themselves."""
        return cls(columns=tuple(columns))

    # ------------------------------------------------------------------
    # Read accessors
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[ColumnSpec]:
        return iter(self.columns)

    def __len__(self) -> int:
        return len(self.columns)

    def names(self) -> List[str]:
        """Ordered list of output names — primary lookup surface for
        downstream plan validation."""
        return [c.name for c in self.columns]

    def name_set(self) -> frozenset:
        """Immutable set of output names; ``O(n)`` construction but
        convenient for membership tests."""
        return frozenset(c.name for c in self.columns)

    def get(self, name: str) -> Optional[ColumnSpec]:
        """Return the :class:`ColumnSpec` with the given output name,
        or ``None`` when absent. ``O(n)``; fine for the low cardinality
        schemas Compose Query produces."""
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def index_of(self, name: str) -> int:
        """Positional index of ``name``; raises ``KeyError`` when absent."""
        for i, c in enumerate(self.columns):
            if c.name == name:
                return i
        raise KeyError(name)

    def contains(self, name: str) -> bool:
        return any(c.name == name for c in self.columns)
