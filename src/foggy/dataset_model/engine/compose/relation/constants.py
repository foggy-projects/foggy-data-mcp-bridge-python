"""Closed string constants for S7a Stable Relation metadata.

Cross-language parity: mirrors Java classes
``SemanticKind``, ``ReferencePolicy``, ``RelationWrapStrategy``,
``RelationPermissionState`` byte-for-byte.

String-backed (not Enum) to avoid Java/Python drift in first POC.

.. versionadded:: S7a (8.5.0.beta)
"""

from __future__ import annotations

from typing import FrozenSet


# ---------------------------------------------------------------------------
# SemanticKind — column semantic classification
# ---------------------------------------------------------------------------

class SemanticKind:
    """Closed string constants for column semantic kind."""

    BASE_FIELD: str = "base_field"
    AGGREGATE_MEASURE: str = "aggregate_measure"
    TIME_WINDOW_DERIVED: str = "time_window_derived"
    SCALAR_CALC: str = "scalar_calc"
    WINDOW_CALC: str = "window_calc"

    ALL: FrozenSet[str] = frozenset({
        BASE_FIELD, AGGREGATE_MEASURE, TIME_WINDOW_DERIVED,
        SCALAR_CALC, WINDOW_CALC,
    })

    @staticmethod
    def is_valid(kind: str) -> bool:
        return kind in SemanticKind.ALL


# ---------------------------------------------------------------------------
# ReferencePolicy — column reference capabilities
# ---------------------------------------------------------------------------

class ReferencePolicy:
    """Closed string constants for column reference policy."""

    READABLE: str = "readable"
    GROUPABLE: str = "groupable"
    AGGREGATABLE: str = "aggregatable"
    WINDOWABLE: str = "windowable"
    ORDERABLE: str = "orderable"

    ALL: FrozenSet[str] = frozenset({
        READABLE, GROUPABLE, AGGREGATABLE, WINDOWABLE, ORDERABLE,
    })

    #: Convenience: dimension fields — readable, groupable, orderable.
    DIMENSION_DEFAULT: FrozenSet[str] = frozenset({READABLE, GROUPABLE, ORDERABLE})

    #: Convenience: measure fields — readable, aggregatable, orderable.
    MEASURE_DEFAULT: FrozenSet[str] = frozenset({READABLE, AGGREGATABLE, ORDERABLE})

    #: Convenience: timeWindow derived fields — readable, orderable.
    TIME_WINDOW_DERIVED_DEFAULT: FrozenSet[str] = frozenset({READABLE, ORDERABLE})

    @staticmethod
    def is_valid(policy: str) -> bool:
        return policy in ReferencePolicy.ALL


# ---------------------------------------------------------------------------
# RelationWrapStrategy — how a relation is rendered in outer plan
# ---------------------------------------------------------------------------

class RelationWrapStrategy:
    """Closed string constants for relation wrapping strategy."""

    INLINE_SUBQUERY: str = "inline_subquery"
    HOISTED_CTE: str = "hoisted_cte"
    NATIVE_CTE: str = "native_cte"
    FAIL_CLOSED: str = "fail_closed"

    ALL: FrozenSet[str] = frozenset({
        INLINE_SUBQUERY, HOISTED_CTE, NATIVE_CTE, FAIL_CLOSED,
    })

    @staticmethod
    def is_valid(strategy: str) -> bool:
        return strategy in RelationWrapStrategy.ALL


# ---------------------------------------------------------------------------
# RelationPermissionState — permission tracking
# ---------------------------------------------------------------------------

class RelationPermissionState:
    """Closed string constants for relation permission state."""

    UNKNOWN: str = "unknown"
    PRE_AUTHORIZED: str = "pre_authorized"
    AUTHORIZED: str = "authorized"

    ALL: FrozenSet[str] = frozenset({UNKNOWN, PRE_AUTHORIZED, AUTHORIZED})

    @staticmethod
    def is_valid(state: str) -> bool:
        return state in RelationPermissionState.ALL
