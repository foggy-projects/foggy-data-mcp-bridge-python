"""Frozen data carriers for the ``AuthorityResolver`` SPI (8.2.0.beta M1).

Single module on purpose: these four dataclasses are always used together
and splitting them across files produces artificial import boundaries that
leak into every Protocol signature.

Cross-repo alignment
--------------------
* Java counterparts live in
  ``com.foggyframework.dataset.db.model.engine.compose.security`` as
  explicit-builder classes (``AuthorityRequest``, ``ModelQuery``,
  ``AuthorityResolution``, ``ModelBinding``). Field names differ by
  casing convention (camelCase vs snake_case); semantics must match.
* ``denied_columns`` reuses v1.3's ``DeniedColumn`` from
  ``foggy.mcp_spi.semantic``. We do NOT introduce a compose-specific
  duplicate.
* ``system_slice`` is a list of slice-condition dicts — the same shape
  v1.3 ``SemanticRequestContext.system_slice`` already accepts. Typing
  as ``List[Any]`` matches existing Python practice; Java side uses
  ``List<SliceRequestDef>``.

Invariants
----------
* ``request.models`` is non-empty even for single-model queries (batch
  protocol: size-1 list).
* ``resolution.bindings`` keys must equal ``{mq.model for mq in request.models}``
  — this is enforced at the resolver boundary (see ``AuthorityResolver``
  docstring), not on the dataclasses themselves, so that test doubles
  can construct partial responses for negative cases.
* ``ModelBinding.field_access = None`` means "no QM-field allowlist; fall
  back to deniedColumns"; ``field_access = []`` means "no field is visible".
  These two are semantically distinct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from foggy.mcp_spi.semantic import DeniedColumn

from ..context.principal import Principal


# ---------------------------------------------------------------------------
# Request side
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelQuery:
    """One (model, tables) pair the resolver needs to bind authority for.

    Fields
    ------
    model:
        Required, non-blank. The QM model name (e.g. ``"SaleOrderQM"``).
    tables:
        Required, non-null (may be empty). Physical tables derived from
        the model's ``JoinGraph``; an empty list is legal but unusual
        and the resolver may treat it as a no-op binding.
    """

    model: str
    tables: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.model is None or self.model == "":
            raise ValueError("ModelQuery.model must be non-blank")
        if self.tables is None:
            raise TypeError("ModelQuery.tables must not be None; use [] for empty")


@dataclass(frozen=True)
class AuthorityRequest:
    """Batch authority-resolution request.

    Always batched: even a single-model resolution sends ``models=[one]``.
    This prevents protocol drift when a future release adds a per-call
    batch optimisation.
    """

    principal: Principal
    namespace: str
    trace_id: Optional[str] = None
    models: List[ModelQuery] = field(default_factory=list)
    extensions: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.principal, Principal):
            raise TypeError("AuthorityRequest.principal must be a Principal")
        if self.namespace is None or self.namespace == "":
            raise ValueError("AuthorityRequest.namespace must be non-blank")
        if not self.models:
            raise ValueError(
                "AuthorityRequest.models must be non-empty; "
                "single-model requests use a size-1 list"
            )
        for i, mq in enumerate(self.models):
            if not isinstance(mq, ModelQuery):
                raise TypeError(
                    f"AuthorityRequest.models[{i}] must be a ModelQuery"
                )

    def model_names(self) -> List[str]:
        """Return the ordered list of model names in this request."""
        return [m.model for m in self.models]


# ---------------------------------------------------------------------------
# Response side
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelBinding:
    """Per-model authority binding returned by the resolver.

    Fields
    ------
    field_access:
        * ``None`` — no QM-field allowlist; deniedColumns drives visibility
          (v1.3 main path for Odoo Pro).
        * ``[]`` — explicit "no field is visible" (a pathological but
          legal state).
        * ``[names...]`` — whitelist; only these QM field names are
          visible.
    denied_columns:
        v1.3 physical-column blacklist entries. Never ``None``; empty list
        means "no physical columns blocked".
    system_slice:
        v1.3 ``ir.rule``-style row-level conditions, expressed as plain
        dicts (``{"field": ..., "op": ..., "value": ...}``). Reuses the
        existing shape consumed by ``SemanticRequestContext.system_slice``.
    """

    field_access: Optional[List[str]] = None
    denied_columns: List[DeniedColumn] = field(default_factory=list)
    system_slice: List[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.denied_columns is None:
            raise TypeError(
                "ModelBinding.denied_columns must not be None; use [] for empty"
            )
        if self.system_slice is None:
            raise TypeError(
                "ModelBinding.system_slice must not be None; use [] for empty"
            )


@dataclass(frozen=True)
class AuthorityResolution:
    """Batch authority-resolution response.

    Keyed by QM model name — resolver contract: the key set must equal the
    caller's ``request.model_names()`` set (see ``AuthorityResolver``
    docstring for full fail-closed requirements).
    """

    bindings: Dict[str, ModelBinding] = field(default_factory=dict)
    extensions: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        if self.bindings is None:
            raise TypeError(
                "AuthorityResolution.bindings must not be None; "
                "use {} for an (illegal) empty response"
            )
        for k, v in self.bindings.items():
            if not isinstance(k, str) or k == "":
                raise ValueError(
                    f"AuthorityResolution.bindings keys must be non-empty str; "
                    f"got {k!r}"
                )
            if not isinstance(v, ModelBinding):
                raise TypeError(
                    f"AuthorityResolution.bindings[{k!r}] must be a ModelBinding"
                )
