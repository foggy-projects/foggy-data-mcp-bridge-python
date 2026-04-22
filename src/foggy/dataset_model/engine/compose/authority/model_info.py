"""``ModelInfoProvider`` — host-supplied lookup for QM → physical tables.

The ``AuthorityRequest`` protocol (M1) requires each ``ModelQuery`` to
carry the QM model name **and** the underlying physical table list.
Physical tables are not part of the ``QueryPlan`` object model itself —
they live in the v1.3 ``JoinGraph`` that the host (Foggy engine / Odoo
Pro bridge) owns.

Rather than drag ``JoinGraph`` into the compose subpackage (creating a
cross-layer dependency we'd regret at Odoo Pro vendored-sync time), we
accept a small injection point here. Hosts that know their physical
tables implement :class:`ModelInfoProvider`; hosts that don't (or plain
unit tests) fall back to :class:`NullModelInfoProvider` which returns
an empty list.

Fallback rationale
------------------
Empty ``tables`` is not a security hole — the resolver on the other
side of the SPI is what decides what to do with it. Odoo Pro's
``OdooEmbeddedAuthorityResolver`` ignores ``tables`` entirely (it looks
up ``ir.rule`` by Odoo model name directly). The HTTP resolver can
still request table info if it needs physical-table-level rule matching.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ModelInfoProvider(Protocol):
    """Structural hook for "QM name → physical tables" lookup.

    Called once per unique ``BaseModelPlan.model`` during
    :func:`resolve_authority_for_plan`. The returned list is forwarded
    verbatim into :class:`ModelQuery.tables`; ``None`` and ``[]`` are
    both legal.
    """

    def get_tables_for_model(
        self, model_name: str, namespace: str
    ) -> Optional[List[str]]:
        """Return the physical tables that back ``model_name``.

        Implementations should return ``[]`` (empty list) rather than
        ``None`` when the model is known but has no discoverable tables;
        reserve ``None`` for the "no lookup available" case.
        """
        ...


class NullModelInfoProvider:
    """Fallback implementation — always returns an empty table list.

    Used in unit tests that don't care about physical tables and by
    hosts that choose not to surface JoinGraph details. The resolver on
    the other side of the SPI still gets the model name, which is the
    minimum needed to bind authority.
    """

    def get_tables_for_model(
        self, model_name: str, namespace: str
    ) -> List[str]:
        return []
