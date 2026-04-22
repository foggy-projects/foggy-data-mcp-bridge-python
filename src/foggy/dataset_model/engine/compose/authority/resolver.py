"""``resolve_authority_for_plan`` — top-level M5 entry point.

Pipeline
--------
1. ``collect_base_models(plan)`` — walk the tree, dedup by ``.model``.
2. Build one ``ModelQuery`` per unique model (tables via
   :class:`ModelInfoProvider`, or ``[]`` fallback).
3. Build one ``AuthorityRequest`` and call
   ``context.authority_resolver.resolve(request)``.
4. Validate the response: key set must equal the requested model set,
   each value must be a :class:`ModelBinding`. Anything else raises
   :class:`AuthorityResolutionError`.
5. Return ``Dict[model_name, ModelBinding]`` to the caller — downstream
   consumers (M6 SQL compiler, M7 script runner) look up bindings by QM
   model name.

Fail-closed invariants
----------------------
* Missing resolver (``context.authority_resolver is None``) is a
  ``RESOLVER_NOT_AVAILABLE`` error. The :class:`ComposeQueryContext`
  ctor already rejects ``None``, but we double-check here in case a
  caller bypasses the context layer (test doubles, future integrations).
* Resolver-raised :class:`AuthorityResolutionError` propagates verbatim
  — we never swallow or remap.
* Resolver-raised unexpected exceptions become ``UPSTREAM_FAILURE``
  with ``__cause__`` preserved (so the log chain survives).
* Response dict with wrong key-set → ``MODEL_BINDING_MISSING`` for the
  first absent model (deterministic: iterate in request order).
* Response dict with non-``ModelBinding`` value → ``INVALID_RESPONSE``.

Request-level caching
---------------------
One call to :func:`resolve_authority_for_plan` performs **at most one**
resolver invocation — the collector deduplicates by model name before
we build the request. Per-session cross-request caching is NOT in M5
scope (the requirements doc explicitly defers it; per-script dedup is
the minimum the batch protocol needs).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..plan import BaseModelPlan, QueryPlan
from ..security import (
    AuthorityRequest,
    AuthorityResolution,
    AuthorityResolutionError,
    ModelBinding,
    ModelQuery,
    error_codes,
)
from .collector import collect_base_models
from .model_info import ModelInfoProvider, NullModelInfoProvider


def resolve_authority_for_plan(
    plan: QueryPlan,
    context: Any,  # ComposeQueryContext — typed as Any to avoid import cycle
    *,
    model_info_provider: Optional[ModelInfoProvider] = None,
) -> Dict[str, ModelBinding]:
    """Resolve per-model authority bindings for every ``BaseModelPlan``
    reachable from ``plan``.

    Parameters
    ----------
    plan:
        Root of the ``QueryPlan`` tree to bind authority for.
    context:
        :class:`ComposeQueryContext` with a valid ``authority_resolver``.
        Typed as ``Any`` to avoid a circular import (``context`` imports
        ``security.AuthorityResolver`` via TYPE_CHECKING, and the
        authority subpackage imports ``context`` in reverse would close
        the cycle).
    model_info_provider:
        Optional — host-supplied lookup of (model_name → physical
        tables). When ``None``, the resolver uses
        :class:`NullModelInfoProvider` which returns ``[]`` for every
        model. Odoo Pro's embedded resolver ignores ``tables`` anyway
        (it looks up ``ir.rule`` by Odoo model name); hosts that want
        HTTP-mode-style table-level filtering provide a real one.

    Returns
    -------
    Dict[str, ModelBinding]
        Keyed by QM model name. One entry per unique
        ``BaseModelPlan.model`` in the plan tree.

    Raises
    ------
    AuthorityResolutionError
        On any contract violation. Error codes::

            resolver-not-available   — context has no resolver
            upstream-failure         — resolver raised non-AuthorityResolutionError
            invalid-response         — resolver returned wrong type / non-ModelBinding
            model-binding-missing    — resolver returned dict missing an expected key
    """
    if context is None or getattr(context, "authority_resolver", None) is None:
        raise AuthorityResolutionError(
            code=error_codes.RESOLVER_NOT_AVAILABLE,
            message=(
                "ComposeQueryContext is missing an authority_resolver; "
                "fail-closed means we never resolve with a null resolver"
            ),
            phase=error_codes.PHASE_AUTHORITY_RESOLVE,
        )

    base_plans: List[BaseModelPlan] = collect_base_models(plan)

    # Degenerate case: a script with no model references has no
    # bindings. We still return {} (not None) so callers can unpack
    # uniformly with .get(model_name). This should not happen in
    # practice — every plan leaf is a BaseModelPlan — but is safe.
    if not base_plans:
        return {}

    provider: ModelInfoProvider = (
        model_info_provider if model_info_provider is not None
        else NullModelInfoProvider()
    )

    model_queries: List[ModelQuery] = []
    for bp in base_plans:
        tables = _safe_get_tables(provider, bp.model, context.namespace)
        model_queries.append(ModelQuery(model=bp.model, tables=list(tables)))

    request = AuthorityRequest(
        principal=context.principal,
        namespace=context.namespace,
        trace_id=getattr(context, "trace_id", None),
        models=model_queries,
        extensions=None,
    )

    try:
        resolution = context.authority_resolver.resolve(request)
    except AuthorityResolutionError:
        # Resolver spoke the structured protocol — propagate verbatim.
        raise
    except Exception as exc:
        # Anything else is an upstream failure; wrap with preserved cause.
        raise AuthorityResolutionError(
            code=error_codes.UPSTREAM_FAILURE,
            message=(
                "AuthorityResolver.resolve raised an unexpected exception; "
                "see __cause__ for details (message sanitised)"
            ),
            phase=error_codes.PHASE_AUTHORITY_RESOLVE,
            cause=exc,
        ) from exc

    _validate_resolution_shape(resolution)
    bindings = _validate_binding_coverage(resolution, request)
    return bindings


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _safe_get_tables(
    provider: ModelInfoProvider, model_name: str, namespace: str
) -> List[str]:
    """Call ``provider.get_tables_for_model``; treat ``None`` as ``[]``.

    ModelInfoProvider is an injected hook — a misbehaving implementation
    returning ``None`` should not break resolution. Wrap and coerce.
    """
    tables = provider.get_tables_for_model(model_name, namespace)
    if tables is None:
        return []
    return list(tables)


def _validate_resolution_shape(resolution: Any) -> None:
    """Reject non-``AuthorityResolution`` return values with INVALID_RESPONSE."""
    if not isinstance(resolution, AuthorityResolution):
        raise AuthorityResolutionError(
            code=error_codes.INVALID_RESPONSE,
            message=(
                f"AuthorityResolver.resolve must return an AuthorityResolution; "
                f"got {type(resolution).__name__}"
            ),
            phase=error_codes.PHASE_AUTHORITY_RESOLVE,
        )


def _validate_binding_coverage(
    resolution: AuthorityResolution, request: AuthorityRequest
) -> Dict[str, ModelBinding]:
    """Return ``resolution.bindings`` iff its key-set exactly covers the
    request's model-name set; otherwise raise MODEL_BINDING_MISSING or
    INVALID_RESPONSE.

    Order of checks matters for deterministic error reporting:

    1. Every requested model must be present (MODEL_BINDING_MISSING on
       first absent, in request order).
    2. No extra keys (INVALID_RESPONSE — this would be a resolver bug
       but is cheap to check).
    3. Every value must be a ``ModelBinding`` instance (belt-and-suspenders
       — :class:`AuthorityResolution`'s own ctor checks this, but we
       don't want to assume the resolver used the real ctor).
    """
    bindings = resolution.bindings
    requested_names = request.model_names()
    requested_set = set(requested_names)

    # (1) Missing key — first in request order for determinism.
    for name in requested_names:
        if name not in bindings:
            raise AuthorityResolutionError(
                code=error_codes.MODEL_BINDING_MISSING,
                message=(
                    f"AuthorityResolver returned a binding set that is "
                    f"missing model {name!r}"
                ),
                model_involved=name,
                phase=error_codes.PHASE_AUTHORITY_RESOLVE,
            )

    # (2) Extra key — deterministic sort for error messages.
    extra = sorted(k for k in bindings.keys() if k not in requested_set)
    if extra:
        raise AuthorityResolutionError(
            code=error_codes.INVALID_RESPONSE,
            message=(
                f"AuthorityResolver returned unexpected bindings for "
                f"models {extra!r}; resolution must cover exactly the "
                f"requested set"
            ),
            phase=error_codes.PHASE_AUTHORITY_RESOLVE,
        )

    # (3) Value-type check.
    for k, v in bindings.items():
        if not isinstance(v, ModelBinding):
            raise AuthorityResolutionError(
                code=error_codes.INVALID_RESPONSE,
                message=(
                    f"AuthorityResolver binding for {k!r} must be a "
                    f"ModelBinding; got {type(v).__name__}"
                ),
                model_involved=k,
                phase=error_codes.PHASE_AUTHORITY_RESOLVE,
            )

    return dict(bindings)
