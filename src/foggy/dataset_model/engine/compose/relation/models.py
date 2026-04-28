"""S7a Stable Relation dataclass models.

Cross-language parity: mirrors Java
``CteItem``, ``RelationSql``, ``RelationCapabilities``,
``CompiledRelation`` classes.

All classes are frozen dataclasses following the project convention.

.. versionadded:: S7a (8.5.0.beta)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from ..plan.plan_id import PlanId
from ..schema.output_schema import OutputSchema
from .constants import (
    RelationPermissionState,
    RelationWrapStrategy,
)


@dataclass(frozen=True)
class CteItem:
    """One ``name AS (sql)`` clause inside a :class:`RelationSql`."""

    name: str
    sql: str
    params: Tuple[object, ...] = ()
    recursive: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("CteItem.name must be non-empty")
        if not self.sql:
            raise ValueError("CteItem.sql must be non-empty")


@dataclass(frozen=True)
class RelationSql:
    """Structured SQL for a :class:`CompiledRelation`.

    Instead of a raw SQL string, the relation's SQL is decomposed into
    structured parts so the outer compiler can safely hoist CTE items,
    rewrite aliases, and validate params order without string parsing.
    """

    body_sql: str
    preferred_alias: str
    with_items: Tuple[CteItem, ...] = ()
    body_params: Tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not self.body_sql:
            raise ValueError("RelationSql.body_sql must be non-empty")
        if not self.preferred_alias:
            raise ValueError("RelationSql.preferred_alias must be non-empty")

    @property
    def contains_with_items(self) -> bool:
        return len(self.with_items) > 0

    def flatten_params(self) -> Tuple[object, ...]:
        """Flatten all params in render order:
        ``with_items[0].params + with_items[1].params + ... + body_params``.
        """
        result: list = []
        for item in self.with_items:
            result.extend(item.params)
        result.extend(self.body_params)
        return tuple(result)


@dataclass(frozen=True)
class RelationCapabilities:
    """Capability flags for a :class:`CompiledRelation`."""

    can_inline_as_subquery: bool = False
    can_hoist_cte: bool = False
    contains_with_items: bool = False
    supports_outer_aggregate: bool = False
    supports_outer_window: bool = False
    requires_top_level_with: bool = False
    relation_wrap_strategy: str = RelationWrapStrategy.FAIL_CLOSED

    @staticmethod
    def for_dialect(dialect: str, has_with_items: bool) -> RelationCapabilities:
        """Determine capabilities based on dialect and CTE presence.

        Mirrors Java ``RelationCapabilities.forDialect()``.
        """
        dl = (dialect or "mysql").lower()
        cte_capable = dl in ("mysql8", "postgres", "postgresql", "sqlite")
        is_sql_server = dl in ("mssql", "sqlserver")
        is_mysql57 = dl in ("mysql", "mysql57")

        if not has_with_items:
            return RelationCapabilities(
                can_inline_as_subquery=True,
                can_hoist_cte=cte_capable or is_sql_server,
                contains_with_items=False,
                supports_outer_aggregate=False,
                supports_outer_window=False,
                requires_top_level_with=False,
                relation_wrap_strategy=RelationWrapStrategy.INLINE_SUBQUERY,
            )

        if is_mysql57:
            return RelationCapabilities(
                can_inline_as_subquery=False,
                can_hoist_cte=False,
                contains_with_items=True,
                supports_outer_aggregate=False,
                supports_outer_window=False,
                requires_top_level_with=False,
                relation_wrap_strategy=RelationWrapStrategy.FAIL_CLOSED,
            )

        if is_sql_server:
            return RelationCapabilities(
                can_inline_as_subquery=False,
                can_hoist_cte=True,
                contains_with_items=True,
                supports_outer_aggregate=False,
                supports_outer_window=False,
                requires_top_level_with=True,
                relation_wrap_strategy=RelationWrapStrategy.HOISTED_CTE,
            )

        # CTE-capable (mysql8, postgres, sqlite)
        return RelationCapabilities(
            can_inline_as_subquery=False,
            can_hoist_cte=True,
            contains_with_items=True,
            supports_outer_aggregate=False,
            supports_outer_window=False,
            requires_top_level_with=False,
            relation_wrap_strategy=RelationWrapStrategy.HOISTED_CTE,
        )


@dataclass(frozen=True)
class CompiledRelation:
    """The formal S7a stable relation contract type.

    ``CteUnit`` remains an internal SQL assembly primitive. This class
    is the formal stable relation contract, facing outer query / LLM /
    validator / parity fixture consumers.
    """

    alias: str
    relation_sql: RelationSql
    output_schema: OutputSchema
    dialect: str
    capabilities: RelationCapabilities
    params: Tuple[object, ...] = ()
    datasource_id: Optional[str] = None
    source_plan_id: Optional[PlanId] = None
    permission_state: str = RelationPermissionState.UNKNOWN

    def __post_init__(self) -> None:
        if not self.alias:
            raise ValueError("CompiledRelation.alias must be non-empty")
        if not self.dialect:
            raise ValueError("CompiledRelation.dialect must be non-empty")
