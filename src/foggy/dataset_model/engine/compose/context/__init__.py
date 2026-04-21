"""Compose Query execution context (8.2.0.beta M1).

This subpackage defines the server-side execution context for Compose Query
scripts. Scripts never observe these objects; they are constructed by the MCP
layer and threaded through ``QueryPlan`` evaluation.

Public API:
    - :class:`Principal`
    - :class:`ComposeQueryContext`

See ``foggy-data-mcp-bridge/docs/8.2.0.beta/M1-AuthorityResolver-SPI签名冻结-需求.md``
for the full signature-freeze specification.
"""

from __future__ import annotations

from .principal import Principal
from .compose_query_context import ComposeQueryContext

__all__ = [
    "Principal",
    "ComposeQueryContext",
]
