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

v1.9 P2.1 additions:

* :class:`ScriptRunState` / :class:`ScriptRunContext` — run lifecycle
  state machine.
* :class:`PauseRequest` / :class:`SuspensionResult` / :class:`ResumeCommand`
  / :class:`RejectCommand` — suspension data models.
* :class:`SuspensionManager` — in-process resume / reject API skeleton.
* :class:`ScriptSuspendError` (and subclasses) — ``script/*`` error codes.

Structured errors: M1–M6 codes from ``compose-*-error/*`` unchanged;
v1.9 adds the ``script/*`` namespace for suspend / resume errors.
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
from .suspend_errors import (
    ALL_SUSPEND_CODES,
    ScriptPauseNotAllowedError,
    ScriptPauseNotInRunError,
    ScriptResumePayloadInvalidError,
    ScriptResumeTokenInvalidError,
    ScriptSuspendError,
    ScriptSuspendLimitExceededError,
    ScriptSuspendRejectedError,
    ScriptSuspendStateInvalidError,
    ScriptSuspendTimeoutError,
)
from .suspension import (
    MAX_TIMEOUT_MS,
    PauseRequest,
    RejectCommand,
    ResumeCommand,
    ScriptRunContext,
    ScriptRunState,
    SuspensionResult,
    TERMINAL_STATES,
    VALID_TRANSITIONS,
)
from .suspension_manager import SuspensionManager

__all__ = [
    # --- M7 existing ---
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
    # --- v1.9 P2.1 ---
    "ALL_SUSPEND_CODES",
    "MAX_TIMEOUT_MS",
    "PauseRequest",
    "RejectCommand",
    "ResumeCommand",
    "ScriptRunContext",
    "ScriptRunState",
    "ScriptSuspendError",
    "ScriptPauseNotAllowedError",
    "ScriptPauseNotInRunError",
    "ScriptResumePayloadInvalidError",
    "ScriptResumeTokenInvalidError",
    "ScriptSuspendLimitExceededError",
    "ScriptSuspendRejectedError",
    "ScriptSuspendStateInvalidError",
    "ScriptSuspendTimeoutError",
    "SuspensionManager",
    "SuspensionResult",
    "TERMINAL_STATES",
    "VALID_TRANSITIONS",
]
