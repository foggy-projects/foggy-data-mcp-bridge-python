"""AuthorityResolver Protocol — the SPI hosts implement to bind authority.

Host implementations live outside this module; ``foggy-odoo-bridge-pro`` will
provide ``OdooEmbeddedAuthorityResolver(env)`` that loops over
``compute_query_governance_with_result`` per model (v1.6 REQ-001).

Fail-closed contract (hosts MUST honour)
----------------------------------------
1. Return a :class:`AuthorityResolution` whose ``bindings`` key-set equals
   ``{mq.model for mq in request.models}``. Missing any key is a contract
   violation; callers raise
   :class:`AuthorityResolutionError` with
   :data:`error_codes.MODEL_BINDING_MISSING`.
2. On any internal failure (ir.rule evaluation error, upstream HTTP 5xx,
   principal mismatch, model-not-mapped, etc.), raise
   :class:`AuthorityResolutionError` with the appropriate code. Do NOT
   return a partial ``AuthorityResolution``.
3. Error messages MUST be sanitised — no raw physical column names, no raw
   ``ir.rule.domain_force`` text, no other users' identifiers.

Typing note
-----------
Protocol runtime-checkable so call sites can ``isinstance(x, AuthorityResolver)``
for defensive dependency-injection checks. Runtime ``isinstance`` on a
``@runtime_checkable`` Protocol is structural (duck-typed) — any object with
a compatible ``resolve`` method satisfies it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import AuthorityRequest, AuthorityResolution


@runtime_checkable
class AuthorityResolver(Protocol):
    """Contract for per-model authority binding resolution.

    Implementations are injected into :class:`ComposeQueryContext` and
    invoked exactly once per ``BaseModelPlan`` first use (after per-script
    deduplication).
    """

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        """Resolve per-model authority bindings for the given request.

        Parameters
        ----------
        request:
            Batch request with non-empty ``models``. Even a single-model
            call sends ``models=[one]``.

        Returns
        -------
        AuthorityResolution
            ``bindings`` keyed by QM model name; one entry per input model.

        Raises
        ------
        AuthorityResolutionError
            Any contract violation or upstream failure.
        """
        ...
