"""Compose Query runtime — script execution + plan-to-rows wiring.

Public surface (M7):

* :func:`run_script` — parse + evaluate a compose-query script.
* :class:`ScriptResult` — structured result of :func:`run_script`.
* :func:`execute_plan` — compile + execute a :class:`QueryPlan` tree.
* :class:`ComposeRuntimeBundle` — host-infrastructure bundle carried via
  ContextVar (not injected into the script).
* :func:`current_bundle` / :func:`set_bundle` — ContextVar accessors
  exposed for advanced hosts that want to pre-seed the runtime outside
  :func:`run_script`.
* :data:`ALLOWED_SCRIPT_GLOBALS` — frozen evaluator-visible surface
  (test-assertion target).

This subpackage does NOT introduce any new ``compose-*-error/*``
namespace codes. All structured errors come from M1–M6.
"""

from __future__ import annotations

from .context_bridge import to_compose_context
from .plan_execution import execute_plan, pick_route_model
from .plans_interceptor import intercept_plans
from .script_runtime import (
    ALLOWED_SCRIPT_GLOBALS,
    ComposeRuntimeBundle,
    ScriptResult,
    current_bundle,
    run_script,
    set_bundle,
)

__all__ = [
    "ALLOWED_SCRIPT_GLOBALS",
    "ComposeRuntimeBundle",
    "ScriptResult",
    "current_bundle",
    "execute_plan",
    "intercept_plans",
    "pick_route_model",
    "run_script",
    "set_bundle",
    "to_compose_context",
]
