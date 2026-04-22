"""``apply_field_access_to_schema`` — filter an ``OutputSchema`` by a
``ModelBinding.field_access`` whitelist.

Scope (M5)
----------
This helper applies the QM-field-name whitelist only. It does NOT touch
``denied_columns`` — that filter requires v1.3
``PhysicalColumnMapping`` to translate physical table+column back to QM
fields, which lives in the SQL compiler layer (M6). Calling this helper
with a binding that has ``field_access=None`` is a no-op — the caller
gets the input schema back unchanged.

Semantics of ``field_access``
-----------------------------
* ``None`` — "no whitelist; deniedColumns owns visibility". No-op here.
  (Odoo Pro's embedded resolver returns ``None`` because its path is
  deniedColumns + systemSlice.)
* ``[]`` — "explicit: no field is visible". Returns an empty
  ``OutputSchema``.
* ``[names...]`` — whitelist. Output preserves the input schema's
  column order; columns whose ``name`` is absent from the whitelist
  are removed.

Why this helper lives next to the resolver and not in ``schema.derive``
----------------------------------------------------------------------
Schema derivation (M4) is pure — no authority. Applying a binding
produces an *effective* schema, which is an authority-layer concept.
Keeping the helper here means the authority subpackage owns the whole
"bind then filter" path; the ``schema`` subpackage stays authority-free
and reusable for test fixtures that don't want a resolver.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from ..schema import ColumnSpec, OutputSchema
from ..security import ModelBinding


def apply_field_access_to_schema(
    schema: OutputSchema, binding: ModelBinding
) -> OutputSchema:
    """Return a new :class:`OutputSchema` restricted to the columns
    whose ``name`` appears in ``binding.field_access``.

    Parameters
    ----------
    schema:
        The declared :class:`OutputSchema` to filter. Must not be ``None``.
    binding:
        The :class:`ModelBinding` whose ``field_access`` drives the
        filter. Must not be ``None``.

    Returns
    -------
    OutputSchema
        * Input ``schema`` (same instance) when
          ``binding.field_access is None``.
        * A new ``OutputSchema`` with only the matching columns,
          preserving the input order, otherwise.

    Raises
    ------
    TypeError
        When either argument is ``None`` or has the wrong type.

    Notes
    -----
    * The helper does not complain about whitelist entries that are
      absent from ``schema``. A binding may list fields the current
      plan never selected; dropping them silently is fine because the
      output schema is what matters. If strict validation is ever
      needed, wrap this with a caller-side check.
    * Duplicate entries in ``binding.field_access`` are harmless — set
      membership is what matters.
    """
    if schema is None:
        raise TypeError("apply_field_access_to_schema: schema must not be None")
    if not isinstance(schema, OutputSchema):
        raise TypeError(
            f"apply_field_access_to_schema: schema must be OutputSchema, "
            f"got {type(schema).__name__}"
        )
    if binding is None:
        raise TypeError("apply_field_access_to_schema: binding must not be None")
    if not isinstance(binding, ModelBinding):
        raise TypeError(
            f"apply_field_access_to_schema: binding must be ModelBinding, "
            f"got {type(binding).__name__}"
        )

    allow: Optional[Iterable[str]] = binding.field_access

    # None → no-op; the deniedColumns path (M6) owns visibility.
    if allow is None:
        return schema

    # Empty whitelist → explicit "no visible field". Returning a real
    # empty OutputSchema is legal; the spec says callers must surface a
    # permission error when the plan needs fields and gets none, but
    # this helper is pure — it does not decide.
    allow_set = frozenset(allow)
    if not allow_set:
        return OutputSchema.of([])

    kept: List[ColumnSpec] = [c for c in schema.columns if c.name in allow_set]
    return OutputSchema.of(kept)
