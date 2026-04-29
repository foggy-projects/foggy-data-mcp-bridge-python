"""SqlFragment — structured return type for ``sql_scalar`` renderers.

Renderers MUST return ``SqlFragment`` (never a raw SQL string). This
enforces parameterized SQL and prevents user-input string concatenation
at the type level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass(frozen=True)
class SqlFragment:
    """Parameterized SQL expression fragment.

    Attributes
    ----------
    sql:
        SQL text with ``?`` placeholders for bind parameters.
        Must not contain unbound user-controlled values.
    params:
        Bind parameter values, in order matching the ``?`` placeholders
        in *sql*.
    return_type:
        Declared return type of the SQL expression.
    """

    sql: str
    params: List[Any] = field(default_factory=list)
    return_type: str = "string"

    def __post_init__(self) -> None:
        if not isinstance(self.sql, str):
            raise TypeError(
                f"SqlFragment.sql must be str, got {type(self.sql).__name__}"
            )
        if not isinstance(self.params, list):
            raise TypeError(
                f"SqlFragment.params must be list, got {type(self.params).__name__}"
            )
