"""Per-BaseModelPlan SQL compilation (M6 · 6.1).

Delegates to the v1.3 public ``SemanticQueryService.build_query_with_governance``
entry (added for M6 by batch 2 of the simplify cleanup). Binding's
``field_access`` / ``system_slice`` / ``denied_columns`` fields are
injected into ``SemanticQueryRequest`` so v1.3 column + slice
governance applies automatically.

Derived plans do NOT re-enter this function — :mod:`compose_planner`
lowers them via ``SELECT … FROM (<source_sql>) AS <alias>`` string
templating; only ``BaseModelPlan`` instances reach the v1.3 engine.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from foggy.dataset_model.engine.compose import CteUnit
from foggy.dataset_model.engine.compose.compilation import error_codes
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan
from foggy.dataset_model.engine.compose.security.models import ModelBinding
from foggy.mcp_spi.semantic import (
    FieldAccessDef,
    SemanticQueryRequest,
)


def compile_base_model(
    plan: BaseModelPlan,
    binding: ModelBinding,
    *,
    semantic_service: Any,
    alias: str,
    governance_cache: Optional[Dict[Tuple[str, int], Any]] = None,
) -> CteUnit:
    """Compile one ``BaseModelPlan`` against its ``ModelBinding``.

    Parameters
    ----------
    plan / binding:
        Frozen-dataclass inputs. Tuple-typed fields get converted to
        lists for the v1.3 request which expects List types.
    semantic_service:
        ``SemanticQueryService`` offering
        ``build_query_with_governance(model_name, request)``. Typed as
        ``Any`` to avoid a heavy import at module load.
    alias:
        Alias for the resulting ``CteUnit`` (caller owns numbering).
    governance_cache:
        Optional dict from ``_CompileState`` that memoises the
        ``QueryBuildResult`` across identical ``(model, binding)``
        pairs within a single compile pass — skips
        ``_apply_query_governance`` + ``validate_query_fields`` +
        ``_build_query`` re-execution for self-join / self-union cases.

    Returns
    -------
    CteUnit
        With ``alias``, ``sql``, ``params``, and ``select_columns``
        derived from ``QueryBuildResult.columns[*]["name"]``.

    Raises
    ------
    ComposeCompileError
        - ``MISSING_BINDING`` (phase=``plan-lower``) when the QM is
          not registered with the semantic service.
        - ``PER_BASE_COMPILE_FAILED`` (phase=``compile``) when v1.3
          rejects the request or raises during query build. Original
          exception preserved on ``__cause__``.
    """
    # Cache key: model + binding identity. ``ModelBinding`` is a frozen
    # dataclass with List fields (not hashable), so we key on id() —
    # correct within a single compile pass because bindings are not
    # mutated mid-compile.
    cache_key = (plan.model, id(binding))
    build_result = governance_cache.get(cache_key) if governance_cache is not None else None
    if build_result is None:
        request = _build_request(plan, binding)
        try:
            build_result = semantic_service.build_query_with_governance(
                plan.model, request,
            )
        except ValueError as exc:
            # ``build_query_with_governance`` raises ``ValueError`` for
            # "model not registered" and for governance / field-validation
            # rejections. The exact branch distinction is carried on the
            # message prefix when needed, but for M6 callers both map to
            # the same error code shape — governance rejection is a
            # "per-base compile failed" surface, and "model not found"
            # is re-classified as ``MISSING_BINDING`` at plan-lower phase.
            if _is_model_not_found(exc, plan.model):
                raise ComposeCompileError(
                    code=error_codes.MISSING_BINDING,
                    phase="plan-lower",
                    message=(
                        f"QM '{plan.model}' not registered with semantic service; "
                        "cannot compile BaseModelPlan (ensure svc.register_model "
                        "was called for this QM before compile_plan_to_sql)"
                    ),
                ) from exc
            raise ComposeCompileError(
                code=error_codes.PER_BASE_COMPILE_FAILED,
                phase="compile",
                message=(
                    f"v1.3 rejected request for model '{plan.model}': {exc}"
                ),
            ) from exc
        except Exception as exc:
            # Any other exception (e.g. ``_build_query`` internals raising) —
            # preserve ``__cause__`` for diagnostics.
            raise ComposeCompileError(
                code=error_codes.PER_BASE_COMPILE_FAILED,
                phase="compile",
                message=(
                    f"v1.3 engine build failed for model '{plan.model}': "
                    f"{type(exc).__name__}: {exc}"
                ),
            ) from exc

        if governance_cache is not None:
            governance_cache[cache_key] = build_result

    return CteUnit(
        alias=alias,
        sql=build_result.sql,
        params=list(build_result.params or []),
        select_columns=_extract_select_columns(build_result),
    )


def _is_model_not_found(exc: ValueError, model_name: str) -> bool:
    """Recognise the "Model not found: <name>" branch of
    ``build_query_with_governance`` so we can reclassify it as
    ``MISSING_BINDING`` at the plan-lower phase."""
    return "Model not found" in str(exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_request(
    plan: BaseModelPlan,
    binding: ModelBinding,
) -> SemanticQueryRequest:
    """Assemble the ``SemanticQueryRequest`` carrying binding three-field
    authority injection alongside plan-sourced shape fields.

    The binding → request mapping handles two type mismatches:

    - ``ModelBinding.field_access: Optional[List[str]]`` (a bare
      whitelist) → ``SemanticQueryRequest.field_access: Optional[FieldAccessDef]``
      (a richer governance object). We wrap the list in
      ``FieldAccessDef(visible=[...])``; masking stays empty (compose
      scope doesn't govern per-cell masking).
    - ``ModelBinding.denied_columns: List[DeniedColumn]`` (non-None
      contract) → ``SemanticQueryRequest.denied_columns: Optional[List[DeniedColumn]]``.
      We always pass a concrete list; empty list means "no physical
      columns blocked", which v1.3 engine handles as no-op.
    """
    field_access_def: Optional[FieldAccessDef]
    if binding.field_access is None:
        field_access_def = None
    else:
        field_access_def = FieldAccessDef(visible=list(binding.field_access))

    # ``SemanticQueryRequest.start`` is typed ``int`` (not Optional) with default 0.
    # ``BaseModelPlan.start`` is ``Optional[int]``; coerce None → 0 so pydantic
    # accepts the request.
    start_int: int = 0 if plan.start is None else int(plan.start)

    # ``BaseModelPlan.order_by`` is ``Tuple[str, ...]`` (bare field names).
    # v1.3 ``SemanticQueryRequest.order_by`` expects dict entries with
    # ``field`` + ``dir`` keys (the engine calls ``entry.get("field")``).
    # Convert plain strings into the dict form — ``"name:desc"`` sugar also
    # honored for parity with the plain DSL convention.
    order_by_entries: List[Any] = [_to_order_entry(e) for e in plan.order_by]

    return SemanticQueryRequest(
        columns=list(plan.columns),
        slice=list(plan.slice_),
        group_by=list(plan.group_by),
        order_by=order_by_entries,
        limit=plan.limit,
        start=start_int,
        distinct=bool(plan.distinct),
        # ★ M6 binding three-field injection
        field_access=field_access_def,
        system_slice=list(binding.system_slice) if binding.system_slice else None,
        denied_columns=list(binding.denied_columns),
    )


def _to_order_entry(entry: Any) -> Any:
    """Normalise one plan-level ``order_by`` entry to the dict shape v1.3 expects.

    Accepted inputs (in priority order):
      - already-dict entry (``{"field": "x", "dir": "asc"}``) — passed through
      - ``"name:asc"`` / ``"name:desc"`` — split and boxed
      - ``"name"`` — boxed with implicit ``dir="asc"``
    """
    if isinstance(entry, dict):
        return entry
    if isinstance(entry, str):
        if ":" in entry:
            name, direction = entry.split(":", 1)
            direction = direction.strip().lower()
            if direction not in ("asc", "desc"):
                direction = "asc"
            return {"field": name.strip(), "dir": direction}
        return {"field": entry, "dir": "asc"}
    # Fail-closed: plan layer should not allow other shapes; the v1.3
    # engine would raise unhelpfully further down.
    raise TypeError(
        f"BaseModelPlan.order_by entries must be str or dict, got "
        f"{type(entry).__name__}"
    )


def _extract_select_columns(build_result: Any) -> List[str]:
    """Pull a flat list of column names from ``QueryBuildResult.columns``.

    ``QueryBuildResult.columns`` is ``List[Dict[str, Any]]`` where each
    dict has at least a ``"name"`` key (the v1.3 service publishes
    column metadata this way). We return names in emission order,
    filtering out any dicts that happen to lack a ``"name"`` (defensive
    — existing v1.3 contract says they all have it, but M6 shouldn't
    crash if the contract slips).
    """
    cols = getattr(build_result, "columns", None) or []
    return [c["name"] for c in cols if isinstance(c, dict) and c.get("name")]
