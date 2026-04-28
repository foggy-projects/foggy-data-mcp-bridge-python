"""Public entry point for Compose Query SQL compilation (M6).

``compile_plan_to_sql`` is the single exposed function; it takes a
``QueryPlan`` tree and a ``ComposeQueryContext`` and returns the
dialect-aware SQL + params via ``ComposedSql``.

Caller patterns:

1. One-shot — caller does not have bindings yet::

       composed = compile_plan_to_sql(plan, ctx,
                                       semantic_service=svc,
                                       dialect="postgres")
       # M6 internally calls resolve_authority_for_plan

2. Two-step — caller already resolved bindings externally (e.g. for
   multi-dialect snapshot, or because a caller cache owns the
   binding lifecycle)::

       bindings = resolve_authority_for_plan(plan, ctx)
       for dialect in ("mysql8", "postgres"):
           composed = compile_plan_to_sql(plan, ctx,
                                           semantic_service=svc,
                                           bindings=bindings,
                                           dialect=dialect)

See the M6 execution prompt §核心入口签名 for the rationale behind
``semantic_service`` being a required keyword-only argument (D2
decision; avoids touching ``ComposeQueryContext``'s frozen contract).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.authority.datasource_ids import (
    collect_datasource_ids,
)
from foggy.dataset_model.engine.compose.authority.resolver import (
    resolve_authority_for_plan,
)
from foggy.dataset_model.engine.compose.compilation.compose_planner import (
    compile_to_composed_sql,
)
from foggy.dataset_model.engine.compose.plan.plan import QueryPlan
from foggy.dataset_model.engine.compose.security.models import ModelBinding


def compile_plan_to_sql(
    plan: QueryPlan,
    context: Any,  # ComposeQueryContext — typed as Any to avoid import cycle
    *,
    semantic_service: Any,  # SemanticQueryService; Any avoids eager import
    bindings: Optional[Dict[str, ModelBinding]] = None,
    model_info_provider: Optional[Any] = None,  # ModelInfoProvider
    datasource_ids: Optional[Dict[str, Optional[str]]] = None,
    dialect: str = "mysql",
) -> ComposedSql:
    """Compile a ``QueryPlan`` tree to dialect-aware SQL + bind params.

    Parameters
    ----------
    plan:
        Root of the plan tree. Any concrete ``QueryPlan`` subclass
        (``BaseModelPlan`` / ``DerivedQueryPlan`` / ``UnionPlan`` /
        ``JoinPlan``).
    context:
        :class:`ComposeQueryContext` carrying the ``Principal`` and
        the ``AuthorityResolver``. Required even when ``bindings`` is
        pre-supplied — the context is passed through to M5 on the
        internal-resolve path, and it is part of the public contract
        so Java / Python stay aligned.
    semantic_service:
        The v1.3 :class:`SemanticQueryService` that owns
        ``_build_query``. Keyword-only; D2 decision keeps this out of
        ``ComposeQueryContext`` to preserve the frozen contract shared
        with M1/M5.
    bindings:
        Optional ``Dict[str, ModelBinding]``. When ``None``, M6
        internally calls
        ``resolve_authority_for_plan(plan, context, model_info_provider=...)``
        — the one-shot path. When provided, skips the resolve (two-step
        path, cheaper for repeated compilation).

        **Caching note (r3 Q2)**: M6 intentionally does NOT cache the
        resolved bindings internally. Callers that invoke
        ``compile_plan_to_sql`` multiple times on the same plan should
        resolve once externally and pass the result on each subsequent
        call.
    model_info_provider:
        Optional — forwarded to ``resolve_authority_for_plan`` on the
        internal-resolve path. Also used to collect datasource IDs
        (F-7) when ``datasource_ids`` is not pre-supplied. Ignored
        when both ``bindings`` and ``datasource_ids`` are provided.
    datasource_ids:
        Optional ``Dict[str, Optional[str]]`` — pre-collected datasource
        identities keyed by QM model name (F-7). When ``None`` and
        ``model_info_provider`` is available, datasource IDs are
        collected automatically. When ``None`` and no provider, the
        cross-datasource check is skipped (backward-compatible).
    dialect:
        ``"mysql"`` / ``"mysql8"`` / ``"postgres"`` / ``"mssql"`` /
        ``"sqlite"``. Drives CTE-vs-subquery fallback (see 6.5). Default
        ``"mysql"`` is conservative MySQL-5.7-compat — pass ``"mysql8"``
        to enable CTE emission on modern MySQL.

    Returns
    -------
    ComposedSql
        Immutable ``(sql, params)`` pair. Params are positional ``?``
        placeholders; the caller's executor is responsible for
        dialect-specific ``%s`` / ``$N`` translation (M6 does not
        execute anything — scope ends at SQL + params).

    Raises
    ------
    ComposeCompileError
        See :mod:`error_codes` — 4 codes total. Includes
        ``CROSS_DATASOURCE_REJECTED`` when union / join operands span
        multiple datasources (F-7).
    """
    if bindings is None:
        bindings = resolve_authority_for_plan(
            plan,
            context,
            model_info_provider=model_info_provider,
        )

    # F-7: collect datasource IDs if not pre-supplied and a provider
    # is available. This enables cross-datasource detection in the
    # compile phase without changing the resolver's return type.
    if datasource_ids is None and model_info_provider is not None:
        namespace = getattr(context, "namespace", "")
        datasource_ids = collect_datasource_ids(
            plan,
            model_info_provider=model_info_provider,
            namespace=namespace,
        )

    return compile_to_composed_sql(
        plan,
        bindings=bindings,
        semantic_service=semantic_service,
        dialect=dialect,
        datasource_ids=datasource_ids,
    )
