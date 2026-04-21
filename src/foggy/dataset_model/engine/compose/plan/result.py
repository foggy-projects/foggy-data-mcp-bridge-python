"""Placeholder return types for ``QueryPlan.execute()`` / ``.to_sql()``.

M2 does NOT implement execution or SQL compilation — those are M6 (compile)
and M7 (script runner) scope. Calling these methods on a plan built in M2
raises :class:`UnsupportedInM2Error` with a pointer to the owning
milestone. This preserves Layer-C whitelist semantics (the five methods
exist on every ``QueryPlan`` instance) without pretending the execution
pipeline is wired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


class UnsupportedInM2Error(NotImplementedError):
    """Marker subclass used by :meth:`QueryPlan.execute` /
    :meth:`QueryPlan.to_sql` to signal "implemented in a later milestone".

    Kept as a subclass of ``NotImplementedError`` so tests that use
    ``pytest.raises(NotImplementedError)`` remain valid.
    """


@dataclass(frozen=True)
class SqlPreview:
    """Debug-only SQL preview returned by :meth:`QueryPlan.to_sql`.

    **Not** a stable cross-system protocol. Format may change freely across
    minor versions; use only for logging, EXPLAIN tooling, or interactive
    development.

    Fields
    ------
    sql:
        Rendered SQL text. Parameter placeholders are intentionally left
        in-place (no string interpolation).
    params:
        Parameter values in the order they appear in ``sql``.
    """

    sql: str = ""
    params: List[Any] = field(default_factory=list)
