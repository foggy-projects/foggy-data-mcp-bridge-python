"""``ModelInfoProvider`` — host-supplied lookup for QM → physical tables
and datasource identity.

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

Datasource identity (F-7)
-------------------------
``get_datasource_id`` was added in post-v1.5 Stage 1 (F-7) to support
compile-time cross-datasource detection in union / join plans. Hosts
that operate in a single-datasource environment can leave the default
(returns ``None``), which tells the compiler "no cross-DS check needed".
Multi-datasource hosts return a stable string identifier per QM model
name; the compose compiler rejects plans whose leaf models span more
than one datasource.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ModelInfoProvider(Protocol):
    """Structural hook for "QM name → physical tables" lookup and
    datasource identity resolution.

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

    def get_datasource_id(
        self, model_name: str, namespace: str
    ) -> Optional[str]:
        """Return the datasource identity for ``model_name``.

        The returned string must be stable and comparable — two models
        that share the same physical database / connection pool should
        return the same string. Examples: ``"main_mysql"``,
        ``"analytics_pg"``, ``"tenant_42:sales_db"``.

        Semantics:
          - ``None`` — "datasource unknown / single-datasource host";
            the compiler treats all ``None`` models as belonging to the
            same (unknown) datasource. This is the backward-compatible
            default for existing providers.
          - Non-empty string — explicit datasource identity. The compose
            compiler rejects union / join plans whose leaf models resolve
            to more than one distinct non-None datasource id.

        Added in post-v1.5 Stage 1 (F-7) to support compile-time
        cross-datasource detection.
        """
        return None


class NullModelInfoProvider:
    """Fallback implementation — always returns an empty table list
    and ``None`` datasource identity.

    Used in unit tests that don't care about physical tables and by
    hosts that choose not to surface JoinGraph details. The resolver on
    the other side of the SPI still gets the model name, which is the
    minimum needed to bind authority.
    """

    def get_tables_for_model(
        self, model_name: str, namespace: str
    ) -> List[str]:
        return []

    def get_datasource_id(
        self, model_name: str, namespace: str
    ) -> Optional[str]:
        return None
