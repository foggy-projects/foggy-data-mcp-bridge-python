"""Datasource identity resolution for cross-datasource detection (F-7).

Collects per-model datasource identities from a :class:`ModelInfoProvider`
so the compose compiler can reject union / join plans whose leaf models
span multiple datasources at compile time.

This module is intentionally separate from ``resolver.py`` to keep the
``resolve_authority_for_plan`` return-type contract frozen — existing
callers that unpack ``Dict[str, ModelBinding]`` are not disturbed.

The compile entry point (``compile_plan_to_sql``) calls
:func:`collect_datasource_ids` independently when a
``model_info_provider`` is available.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..plan import BaseModelPlan, QueryPlan
from .collector import collect_base_models
from .model_info import ModelInfoProvider, NullModelInfoProvider


def collect_datasource_ids(
    plan: QueryPlan,
    *,
    model_info_provider: Optional[ModelInfoProvider] = None,
    namespace: str = "",
) -> Dict[str, Optional[str]]:
    """Walk ``plan``, call ``provider.get_datasource_id`` for each unique
    ``BaseModelPlan.model``, and return a ``{model_name: datasource_id}``
    dict.

    Parameters
    ----------
    plan:
        Root of the ``QueryPlan`` tree.
    model_info_provider:
        Host-supplied provider. When ``None`` (or a
        :class:`NullModelInfoProvider`), every model maps to ``None``
        (= "single datasource / unknown"), and the compiler skips the
        cross-datasource check.
    namespace:
        Active namespace forwarded to the provider.

    Returns
    -------
    Dict[str, Optional[str]]
        Keyed by QM model name. Values are datasource-id strings or
        ``None`` (unknown).
    """
    provider: ModelInfoProvider = (
        model_info_provider if model_info_provider is not None
        else NullModelInfoProvider()
    )

    base_plans = collect_base_models(plan)
    result: Dict[str, Optional[str]] = {}
    for bp in base_plans:
        if bp.model not in result:
            result[bp.model] = _safe_get_datasource_id(
                provider, bp.model, namespace
            )
    return result


def _safe_get_datasource_id(
    provider: ModelInfoProvider, model_name: str, namespace: str
) -> Optional[str]:
    """Call ``provider.get_datasource_id``; catch and coerce errors to
    ``None`` (permissive fallback).

    Providers that predate F-7 may not implement ``get_datasource_id``
    at all — ``AttributeError`` is caught to maintain backward
    compatibility with legacy host code.
    """
    try:
        return provider.get_datasource_id(model_name, namespace)
    except AttributeError:
        # Provider predates F-7 and doesn't have get_datasource_id
        return None
    except Exception:
        # Misbehaving provider — fail open (permissive) but log the
        # traceback so the host integration issue is visible.
        logging.warning(
            "ModelInfoProvider %r raised exception on get_datasource_id(%r, %r)",
            provider, model_name, namespace,
            exc_info=True
        )
        return None
