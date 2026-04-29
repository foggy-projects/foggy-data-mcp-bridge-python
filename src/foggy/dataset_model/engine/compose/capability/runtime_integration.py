"""Capability runtime integration — wires registered capabilities into
the script evaluator context.

This module bridges :class:`CapabilityRegistry` + :class:`CapabilityPolicy`
into the fsscript evaluator context that :mod:`script_runtime` prepares.

Functions
---------
:func:`build_capability_context`
    Builds a dict of capability names → callables / proxies to inject into
    the evaluator context.  Only includes entries allowed by both the registry
    and the policy.

Design invariants
-----------------
- Returns an empty dict when registry or policy is None/empty.
- Never injects ``ComposeQueryContext``, ``semantic_service``, ``principal``,
  ``authority_resolver``, or any host context into the capability handlers.
- ``sql_scalar`` functions are NOT injected into the script runtime context;
  they live in the formula / compose column compilation layer.
- ``pure_runtime`` functions with ``compose_runtime`` in ``allowed_in`` are
  injected as callable wrappers.
- Object facades are injected as :class:`ObjectFacadeProxy` instances.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .descriptors import FunctionDescriptor
from .errors import (
    CapabilityNotAllowedError,
    CapabilityNotRegisteredError,
    CapabilityReturnTypeDeniedError,
)
from .facade_proxy import ObjectFacadeProxy, _is_safe_return_value
from .policy import CapabilityPolicy
from .registry import CapabilityRegistry


def build_capability_context(
    registry: Optional[CapabilityRegistry],
    policy: Optional[CapabilityPolicy],
) -> Dict[str, Any]:
    """Build evaluator context entries for allowed capabilities.

    Parameters
    ----------
    registry:
        The capability registry.  ``None`` or empty → empty result.
    policy:
        The runtime policy.  ``None`` or empty → empty result.

    Returns
    -------
    Dict[str, Any]
        name → callable (for ``pure_runtime`` functions) or
        :class:`ObjectFacadeProxy` (for object facades).
    """
    if registry is None or policy is None:
        return {}

    ctx: Dict[str, Any] = {}

    # Inject allowed pure_runtime functions.
    for fn_name in registry.function_names:
        entry = registry.get_function(fn_name)
        desc = entry.descriptor

        # Only inject pure_runtime functions with compose_runtime surface.
        if desc.kind != "pure_runtime":
            continue
        if "compose_runtime" not in desc.allowed_in:
            continue
        if not policy.is_function_allowed(fn_name):
            continue

        # Wrap handler to enforce return-type validation.
        ctx[fn_name] = _make_runtime_wrapper(fn_name, entry.handler)

    # Inject allowed object facades as proxies.
    for obj_name in registry.object_names:
        if not policy.is_object_allowed(obj_name):
            continue

        entry = registry.get_object(obj_name)
        proxy = ObjectFacadeProxy(
            descriptor=entry.descriptor,
            target=entry.target,
            policy=policy,
        )
        ctx[obj_name] = proxy

    return ctx


def _make_runtime_wrapper(fn_name: str, handler: Callable) -> Callable:
    """Create a wrapper that validates return types from pure_runtime handlers."""

    def wrapper(*args, **kwargs):
        result = handler(*args, **kwargs)
        if not _is_safe_return_value(result):
            raise CapabilityReturnTypeDeniedError(
                f"Function '{fn_name}' returned a value of disallowed type."
            )
        return result

    wrapper.__name__ = fn_name
    wrapper.__qualname__ = f"capability.{fn_name}"
    return wrapper
