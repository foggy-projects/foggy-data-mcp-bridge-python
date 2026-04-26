# -*- coding: utf-8 -*-
"""Plans interceptor — post-script ``{ plans, metadata }`` envelope handler.

When a Compose Query script returns ``{ "plans": <plans>, ... }``, each
:class:`QueryPlan` inside ``plans`` is replaced by either rows (default)
or a :class:`ComposedSql` (``preview_mode=True``). Three ``plans`` shapes
are recognised: dict (named map), list / tuple (ordered), single plan.

Python diverges from Java in one outer-branch behaviour: a bare
:class:`QueryPlan` returned at the script's top level passes through
verbatim instead of being auto-executed. This preserves the M7
unit-test contract that asserts on plan AST shape; production callers
always emit the envelope.

Cross-repo invariant: mirrors Java
``ScriptRuntime#interceptPlans`` and the vendored copy in
``foggy_mcp_pro/lib/foggy/dataset_model/engine/compose/runtime/``.

.. versionadded:: 8.2.0.beta (Phase 4 / Python Phase B)
"""

from __future__ import annotations

import logging
from typing import Any

from ..plan.plan import QueryPlan

__all__ = ["intercept_plans"]

_logger = logging.getLogger(__name__)


# Single-plan dispatch lives in its own helper so the three shape
# branches in :func:`_evaluate_plans_value` don't repeat the
# ``preview_mode`` ternary.
def _evaluate_plan(plan: QueryPlan, preview_mode: bool) -> Any:
    """Evaluate one :class:`QueryPlan` against the ambient
    :class:`ComposeRuntimeBundle` (``preview_mode`` toggles
    ``to_sql`` vs ``execute``)."""
    return plan.to_sql() if preview_mode else plan.execute()


def _evaluate_plans_value(plans_obj: Any, preview_mode: bool) -> Any:
    """Evaluate the ``plans`` field, which may be a dict, list, or single
    :class:`QueryPlan`. Returns the input identity-unchanged when the
    shape contains no plans, so callers can short-circuit the envelope
    copy.
    """
    # Branch 1: named plan map (dict).
    if isinstance(plans_obj, dict):
        mutated = False
        executed: dict[str, Any] = {}
        for key, value in plans_obj.items():
            if isinstance(value, QueryPlan):
                executed[key] = _evaluate_plan(value, preview_mode)
                mutated = True
            else:
                executed[key] = value
        return executed if mutated else plans_obj

    # Branch 2: ordered plan array (list / tuple).
    if isinstance(plans_obj, (list, tuple)):
        mutated = False
        executed_list: list[Any] = []
        for item in plans_obj:
            if isinstance(item, QueryPlan):
                executed_list.append(_evaluate_plan(item, preview_mode))
                mutated = True
            else:
                executed_list.append(item)
        return executed_list if mutated else plans_obj

    # Branch 3: single QueryPlan.
    if isinstance(plans_obj, QueryPlan):
        return _evaluate_plan(plans_obj, preview_mode)

    # Fallback: log because it usually signals a script bug (e.g. forgot
    # to wrap a literal in a dict). Pass-through so the literal survives.
    _logger.warning(
        "plans value is not a dict, list, or QueryPlan; passing through: %s",
        type(plans_obj).__name__,
    )
    return plans_obj


def intercept_plans(
    result: Any,
    *,
    preview_mode: bool = False,
) -> Any:
    """Auto-evaluate :class:`QueryPlan` instances inside a
    ``{ plans, ... }`` envelope.

    Parameters
    ----------
    result :
        The fsscript evaluator return value. The envelope is recognised
        as a dict containing the ``plans`` key; anything else (including
        bare plans) passes through unchanged.
    preview_mode :
        When ``True``, plans become :class:`ComposedSql` via ``to_sql()``
        instead of executing.

    Returns
    -------
    Any
        Same identity as ``result`` when no plans were evaluated; a new
        dict (with ``plans`` replaced) when at least one plan was
        evaluated. The input dict is never mutated.
    """
    if not (isinstance(result, dict) and "plans" in result):
        return result

    evaluated = _evaluate_plans_value(result["plans"], preview_mode)
    # Identity check: when ``plans`` had no QueryPlan inside,
    # ``_evaluate_plans_value`` returns the input unchanged — skip the
    # envelope copy too so literal-only scripts never allocate.
    if evaluated is result["plans"]:
        return result

    new_result = dict(result)
    new_result["plans"] = evaluated
    return new_result
