# -*- coding: utf-8 -*-
"""Plans interceptor — post-script result processing.

Aligned with Java ``ScriptRuntime`` §5.5: when a script returns a dict
containing a ``plans`` key, this module auto-evaluates each
:class:`QueryPlan` found within it, according to the requested mode:

* **preview mode** (``preview_mode=True``): calls :meth:`QueryPlan.to_sql`
  on each plan, replacing it with a :class:`ComposedSql` (SQL text + params).
* **execution mode** (``preview_mode=False``): calls :meth:`QueryPlan.execute`
  on each plan, replacing it with the actual result rows.

Three ``plans`` shapes are supported inside the envelope (matching the
three inner branches of Java ``ScriptRuntime.interceptPlans``):

1. **dict** — named plan map: ``{ "summary": plan1, "detail": plan2 }``
2. **list** — ordered plan array: ``[ plan1, plan2 ]``
3. **single** — bare :class:`QueryPlan` object as the value of ``plans``

Divergence from Java
--------------------
Java has an additional outer branch that auto-executes a bare
:class:`QueryPlan` returned at the script's top level (``return finalPlan;``)
as a backward-compat for the M7 baseline. The Python side does NOT do
this — it preserves the M7 contract where bare plans pass through as the
AST so unit tests can assert on plan shape. The explicit
``{ plans: ..., metadata: ... }`` envelope is the **single** opt-in for
auto-execution. Scripts that want their plans executed must wrap in the
envelope.

Production callers (``script_controller.py`` in the embedded backend, the
MCP ``compose.script`` tool) always emit the envelope, so this is a
purely test-vs-production distinction.

Cross-repo invariant
--------------------
Mirrors:

* Java: ``foggy-dataset-model/.../engine/compose/runtime/ScriptRuntime#interceptPlans``
* Odoo Pro vendored copy: ``foggy_mcp_pro/lib/foggy/dataset_model/engine/compose/runtime/plans_interceptor.py``

When updating the contract, update all three to keep parity.

.. versionadded:: 8.2.0.beta (Phase 4 / Python Phase B)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..plan.plan import QueryPlan

__all__ = ["intercept_plans"]

_logger = logging.getLogger(__name__)


def _evaluate_plan(plan: QueryPlan, preview_mode: bool) -> Any:
    """Evaluate a single :class:`QueryPlan` in the requested mode.

    The plan reads the ambient :class:`ComposeRuntimeBundle` from
    ``script_runtime``'s ContextVar, so this function does NOT need
    ``semantic_service`` / ``dialect`` parameters. Callers MUST be
    inside a :func:`run_script` invocation (or have manually called
    :func:`set_bundle`).
    """
    if preview_mode:
        return plan.to_sql()
    return plan.execute()


def _evaluate_plans_value(plans_obj: Any, preview_mode: bool) -> Any:
    """Evaluate the ``plans`` field, which may be a dict, list, or single
    :class:`QueryPlan`.

    Mirrors the three-branch logic in Java ``ScriptRuntime.interceptPlans``.
    Non-plan values inside dicts/lists are passed through verbatim — the
    spec allows scripts to mix plans with literal placeholders/labels.
    """
    # Branch 1: named plan map (dict)
    if isinstance(plans_obj, dict):
        executed: dict[str, Any] = {}
        for key, value in plans_obj.items():
            if isinstance(value, QueryPlan):
                executed[key] = _evaluate_plan(value, preview_mode)
            else:
                executed[key] = value
        return executed

    # Branch 2: ordered plan array (list/tuple)
    if isinstance(plans_obj, (list, tuple)):
        executed_list: list[Any] = []
        for item in plans_obj:
            if isinstance(item, QueryPlan):
                executed_list.append(_evaluate_plan(item, preview_mode))
            else:
                executed_list.append(item)
        return executed_list

    # Branch 3: single QueryPlan
    if isinstance(plans_obj, QueryPlan):
        return _evaluate_plan(plans_obj, preview_mode)

    # Fallback: not a recognised shape — pass through unchanged so the
    # script's literal contract survives. We log because it usually
    # signals a script bug (e.g. forgot to wrap in a dict).
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
    """Intercept and auto-evaluate :class:`QueryPlan` instances in the
    script return value.

    Parameters
    ----------
    result :
        The raw return value from the fsscript evaluator. Two shapes
        are recognised:

        * ``{ "plans": <plans>, ... }`` — named-result envelope. ``plans``
          itself can be a dict, list, or single plan; each
          :class:`QueryPlan` inside is evaluated, others pass through.
        * Anything else — passed through unchanged. This includes bare
          :class:`QueryPlan` instances (so unit tests can keep asserting
          on AST shape) and rows / ``ComposedSql`` already produced by
          explicit ``.execute()`` / ``.to_sql()`` calls.
    preview_mode :
        When ``True``, plans inside the envelope are converted to
        :class:`ComposedSql` via ``to_sql()`` instead of being executed.

    Returns
    -------
    Any
        The processed result. When the envelope was matched, a NEW dict
        is returned (the script's literal dict is not mutated) with
        ``plans`` replaced by its evaluated form. Otherwise ``result``
        is returned unchanged.
    """
    # Envelope match: dict with a 'plans' key.
    if isinstance(result, dict) and "plans" in result:
        # Copy so we don't mutate the script's literal dict in place;
        # the contract is "the script's return value is read-only after
        # it returns".
        new_result = dict(result)
        new_result["plans"] = _evaluate_plans_value(result["plans"], preview_mode)
        return new_result

    # Anything else (bare plans, rows, ComposedSql, literals): pass
    # through unchanged. See module docstring §"Divergence from Java".
    return result
