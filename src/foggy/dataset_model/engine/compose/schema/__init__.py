"""Compose Query declared-schema derivation (8.2.0.beta M4).

This subpackage provides the *structural* output-schema derivation that
``QueryPlan`` trees need before SQL compilation (M6) or authority-bound
effective schema (M5). It operates purely on the user-declared shape of
each plan — the alias-resolved output columns and their carry-over from
``source`` plans — without any interaction with QM type information,
``fieldAccess`` whitelists, or ``deniedColumns`` blacklists.

Scope boundaries
----------------
* **In M4 (this subpackage)**
    - Column alias extraction: ``"SUM(x) AS total"`` → output name ``"total"``
    - Per-plan output schema derivation (BaseModel / Derived / Union / Join)
    - Structural validation (missing field reference in derived plan,
      union column-count mismatch, join-on field not visible,
      duplicate output column, output column conflict after join)
* **Deferred to M5**
    - Authority binding applied to BaseModelPlan → *effective* schema
      (``fieldAccess`` intersection / ``deniedColumns`` subtraction)
* **Deferred to M6**
    - SQL type inference from QM column types
    - Union type-compatibility check

Public API
----------
* :class:`ColumnSpec` — one entry in an :class:`OutputSchema`
* :class:`OutputSchema` — frozen ordered bag of ``ColumnSpec``
* :func:`derive_schema` — walk a plan tree, returning its output schema
* :func:`extract_column_alias` — low-level alias parser (also reused by
  tests and future validators)
* :class:`ComposeSchemaError` — structured error raised by derivation
* ``error_codes`` — frozen-string catalogue
"""

from __future__ import annotations

from . import error_codes
from .alias import extract_column_alias
from .derive import derive_schema
from .errors import ComposeSchemaError
from .output_schema import ColumnSpec, OutputSchema

__all__ = [
    "ColumnSpec",
    "OutputSchema",
    "derive_schema",
    "extract_column_alias",
    "ComposeSchemaError",
    "error_codes",
]
