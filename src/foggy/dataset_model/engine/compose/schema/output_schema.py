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
from enum import Enum
from typing import Dict, Iterator, List, Optional, Tuple

from .. import feature_flags
from ..plan.plan_id import PlanId
from . import error_codes


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


class _DuplicateOutcome(Enum):
    """Classification of a same-name duplicate against the active flag policy."""

    REJECT_LEGACY = "reject-legacy"
    REJECT_MIXED_FLAG = "reject-mixed-flag"
    REJECT_PURE_DUPLICATE = "reject-pure-duplicate"
    ACCEPT_AMBIGUOUS = "accept-ambiguous"


def _classify_duplicate(first: ColumnSpec, current: ColumnSpec, g10: bool) -> _DuplicateOutcome:
    if not g10:
        return _DuplicateOutcome.REJECT_LEGACY
    if not first.is_ambiguous or not current.is_ambiguous:
        return _DuplicateOutcome.REJECT_MIXED_FLAG
    if first.plan_provenance == current.plan_provenance:
        return _DuplicateOutcome.REJECT_PURE_DUPLICATE
    return _DuplicateOutcome.ACCEPT_AMBIGUOUS


def _duplicate_message(outcome: _DuplicateOutcome, name: str,
                       first: ColumnSpec, current: ColumnSpec,
                       first_index: int, i: int) -> str:
    prefix = (f"OutputSchema contains duplicate output column {name!r} "
              f"(first at index {first_index}, again at index {i})")
    if outcome is _DuplicateOutcome.REJECT_LEGACY:
        return prefix
    if outcome is _DuplicateOutcome.REJECT_MIXED_FLAG:
        return (prefix
                + f". G10 allows duplicates only when every occurrence has "
                + f"is_ambiguous=True; [first_ambiguous={first.is_ambiguous}, "
                + f"current_ambiguous={current.is_ambiguous}]")
    if outcome is _DuplicateOutcome.REJECT_PURE_DUPLICATE:
        return (f"OutputSchema rejects pure duplicate ambiguous column {name!r} "
                f"— both occurrences carry the same plan_provenance, which "
                f"indicates a plan-tree construction bug rather than a join "
                f"overlap (first at index {first_index}, again at index {i})")
    raise AssertionError(f"unreachable: {outcome}")


@dataclass(frozen=True)
class OutputSchema:
    """Ordered list of :class:`ColumnSpec`.

    Duplicate-name handling
    -----------------------

    The duplicate-name policy depends on the
    :func:`feature_flags.g10_enabled` flag:

    * **Flag OFF (legacy)** — duplicate output names are rejected at
      construction. ``JoinPlan`` must resolve column-name conflicts
      via explicit alias; any duplicate surviving into an
      ``OutputSchema`` is a derivation bug.
    * **Flag ON (G10)** — duplicate names are *allowed* when *every*
      column carrying that name has ``is_ambiguous=True``. Such
      duplicates are produced by ``derive_join`` when both join sides
      emit the same name. Each ambiguous occurrence must record a
      distinct ``plan_provenance`` — pure duplicates (same
      ``plan_provenance``) remain rejected. Non-ambiguous duplicates
      (any column lacking the ``is_ambiguous`` flag) are still
      rejected.

    Lookup API (G10 PR2)
    --------------------

    * :meth:`get` — fail-fast on ambiguity. Returns the single column
      for non-ambiguous names; raises ``ComposeSchemaError`` with
      code ``OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP`` when the name resolves
      to multiple ambiguous columns. Returns ``None`` when absent.
    * :meth:`require_unique` — same fail-fast semantics, but raises
      ``KeyError`` on absent.
    * :meth:`get_all` — returns every :class:`ColumnSpec` with this
      name (single-element list for non-ambiguous, multi-element for
      ambiguous, empty for absent).
    * :meth:`is_ambiguous` — ``True`` iff the name resolves to two or
      more columns.
    * :meth:`index_of` — fail-fast on ambiguity, raises ``KeyError``
      on absent.
    """

    columns: Tuple[ColumnSpec, ...] = ()

    def __post_init__(self) -> None:
        g10 = feature_flags.g10_enabled()
        seen: Dict[str, int] = {}
        for i, c in enumerate(self.columns):
            if not isinstance(c, ColumnSpec):
                raise TypeError(
                    f"OutputSchema.columns[{i}] must be ColumnSpec, got "
                    f"{type(c).__name__}"
                )
            if c.name not in seen:
                seen[c.name] = i
                continue
            first_index = seen[c.name]
            first = self.columns[first_index]
            outcome = _classify_duplicate(first, c, g10)
            if outcome is not _DuplicateOutcome.ACCEPT_AMBIGUOUS:
                raise ValueError(_duplicate_message(
                    outcome, c.name, first, c, first_index, i))

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
        """Ordered list of output names. Ambiguous names appear once
        per occurrence (mirrors the ``columns`` tuple)."""
        return [c.name for c in self.columns]

    def name_set(self) -> frozenset:
        """Immutable set of distinct output names — ambiguous names
        appear exactly once."""
        return frozenset(c.name for c in self.columns)

    def get(self, name: str) -> Optional[ColumnSpec]:
        """Single-column lookup by name.

        Returns ``None`` when absent. **Raises** ``ComposeSchemaError``
        with code ``OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP`` when the name
        resolves to multiple ambiguous columns — callers that may
        encounter ambiguity should use :meth:`get_all` or
        :meth:`require_unique` for explicit semantics.
        """
        i = self._unique_index_or_none(name)
        if i is None:
            return None
        return self.columns[i]

    def get_all(self, name: str) -> List[ColumnSpec]:
        """G10 PR2 · Return every :class:`ColumnSpec` carrying ``name``.

        Returns an empty list when absent, single-element list for
        non-ambiguous names, or multi-element list for ambiguous
        (join-overlap) names. Preserves construction order.
        """
        return [c for c in self.columns if c.name == name]

    def is_ambiguous(self, name: str) -> bool:
        """G10 PR2 · ``True`` iff ``name`` resolves to two or more
        columns (only possible when the G10 flag is on and an upstream
        join produced an overlap)."""
        count = 0
        for c in self.columns:
            if c.name == name:
                count += 1
                if count > 1:
                    return True
        return False

    def require_unique(self, name: str) -> ColumnSpec:
        """G10 PR2 · Same as :meth:`get` but raises ``KeyError`` when
        absent. Use when the caller logically expects a unique hit."""
        return self.columns[self._require_unique_index(name)]

    def index_of(self, name: str) -> int:
        """Positional index of ``name``; **fails fast on ambiguity**
        with ``OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP``; raises ``KeyError``
        when absent."""
        return self._require_unique_index(name)

    def contains(self, name: str) -> bool:
        return any(c.name == name for c in self.columns)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unique_index_or_none(self, name: str) -> Optional[int]:
        """Bucket → unique index, or None when absent.
        Raises ``OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP`` on multi-element
        buckets."""
        first: Optional[int] = None
        ambiguous = False
        for i, c in enumerate(self.columns):
            if c.name != name:
                continue
            if first is None:
                first = i
            else:
                ambiguous = True
                break
        if first is None:
            return None
        if not ambiguous:
            return first
        raise self._ambiguous_lookup(name)

    def _require_unique_index(self, name: str) -> int:
        i = self._unique_index_or_none(name)
        if i is None:
            raise KeyError(name)
        return i

    def _ambiguous_lookup(self, name: str) -> "Exception":
        # Local import avoids circular dependency at module load.
        from .errors import ComposeSchemaError
        candidates = [c for c in self.columns if c.name == name]
        rendered = ", ".join(
            f"{{plan_provenance={c.plan_provenance!r}}}" for c in candidates
        )
        return ComposeSchemaError(
            error_codes.OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP,
            f"OutputSchema lookup of {name!r} is ambiguous — "
            f"{len(candidates)} candidate columns. Use a plan-qualified "
            f"reference ({{plan: <handle>, field: {name!r}}}) or call "
            f"OutputSchema.get_all(name) explicitly. Candidates: [{rendered}]",
            phase=error_codes.PHASE_SCHEMA_DERIVE,
            offending_field=name,
        )
