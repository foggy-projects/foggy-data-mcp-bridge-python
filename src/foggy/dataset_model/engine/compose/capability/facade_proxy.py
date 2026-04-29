"""ObjectFacadeProxy — controlled method dispatch for object facades.

The proxy intercepts ALL attribute access via ``__getattribute__`` and
only exposes descriptor-declared methods.  Dunder, private, reflection,
and undeclared attribute access is denied.

Return values are validated against safe types.  Method calls are
timeout-guarded and error-sanitized.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from .descriptors import MethodDescriptor, ObjectFacadeDescriptor
from .errors import (
    CapabilityMethodNotDeclaredError,
    CapabilityNotAllowedError,
    CapabilityReturnTypeDeniedError,
    CapabilityTimeoutError,
)
from .policy import CapabilityPolicy


# Types considered safe for return values (v1.7).
# Does NOT include QueryPlan, typed expression, or host objects.
_SAFE_RETURN_TYPES = (
    type(None), bool, int, float, str,
    dict, list, tuple,
)


def _is_safe_return_value(value: Any) -> bool:
    """Check that value is a safe return type recursively (1 level deep)."""
    if isinstance(value, _SAFE_RETURN_TYPES):
        if isinstance(value, dict):
            return all(
                isinstance(k, str) and isinstance(v, _SAFE_RETURN_TYPES)
                for k, v in value.items()
            )
        if isinstance(value, (list, tuple)):
            return all(isinstance(item, _SAFE_RETURN_TYPES) for item in value)
        return True
    return False


class ObjectFacadeProxy:
    """Controlled proxy for an object facade.

    Intercepts ALL attribute access via ``__getattribute__`` and only
    allows descriptor-declared method calls.  Dunder attributes, private
    attributes, reflection, and undeclared methods are denied.

    The proxy is what the script sees; the real target object is never
    directly accessible from script context.
    """

    def __init__(
        self,
        descriptor: ObjectFacadeDescriptor,
        target: Any,
        policy: CapabilityPolicy,
    ) -> None:
        # Use object.__setattr__ to bypass __setattr__ override.
        object.__setattr__(self, "_descriptor", descriptor)
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_policy", policy)
        object.__setattr__(
            self, "_method_map",
            {m.name: m for m in descriptor.methods},
        )

    def __getattribute__(self, name: str) -> Any:
        # Allow Python special methods defined on this class to work.
        if name in ("__repr__", "__dir__", "__setattr__", "__delattr__",
                     "__class__", "__doc__", "__getattribute__"):
            return object.__getattribute__(self, name)

        # Block all dunder / private access from scripts.
        if name.startswith("_"):
            obj_name = object.__getattribute__(self, "_descriptor").object_name
            raise CapabilityMethodNotDeclaredError(
                f"Access to '{name}' is denied on object '{obj_name}'."
            )

        # Look up in declared methods.
        method_map = object.__getattribute__(self, "_method_map")
        method_desc = method_map.get(name)
        if method_desc is None:
            obj_name = object.__getattribute__(self, "_descriptor").object_name
            raise CapabilityMethodNotDeclaredError(
                f"Method '{name}' is not declared on object '{obj_name}'."
            )

        # Check policy allows this object + method.
        descriptor = object.__getattribute__(self, "_descriptor")
        policy = object.__getattribute__(self, "_policy")
        obj_name = descriptor.object_name
        if not policy.is_method_allowed(obj_name, name):
            raise CapabilityNotAllowedError(
                f"Method '{name}' on object '{obj_name}' is not "
                f"allowed by the current policy."
            )

        # Check auth scope.
        if not policy.is_scope_allowed(method_desc.auth_scope):
            raise CapabilityNotAllowedError(
                f"Auth scope '{method_desc.auth_scope}' is not "
                f"allowed by the current policy."
            )

        # Return a bound dispatcher.
        target = object.__getattribute__(self, "_target")
        return _MethodDispatcher(
            target=target,
            method_desc=method_desc,
            obj_name=obj_name,
        )

    def __setattr__(self, name: str, value: Any) -> None:
        obj_name = object.__getattribute__(self, "_descriptor").object_name
        raise CapabilityMethodNotDeclaredError(
            f"Setting attributes is denied on object '{obj_name}'."
        )

    def __delattr__(self, name: str) -> None:
        obj_name = object.__getattribute__(self, "_descriptor").object_name
        raise CapabilityMethodNotDeclaredError(
            f"Deleting attributes is denied on object '{obj_name}'."
        )

    def __repr__(self) -> str:
        obj_name = object.__getattribute__(self, "_descriptor").object_name
        return f"<ObjectFacadeProxy '{obj_name}'>"

    def __dir__(self) -> list:
        method_map = object.__getattribute__(self, "_method_map")
        return list(method_map.keys())


class _MethodDispatcher:
    """Callable wrapper for a declared facade method.

    Enforces timeout and return-type validation.
    """

    __slots__ = ("_target", "_method_desc", "_obj_name")

    def __init__(
        self,
        target: Any,
        method_desc: MethodDescriptor,
        obj_name: str,
    ) -> None:
        self._target = target
        self._method_desc = method_desc
        self._obj_name = obj_name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        method_name = self._method_desc.name
        timeout_ms = self._method_desc.timeout_ms

        # Get the actual method.
        actual_method = getattr(self._target, method_name)

        # Execute with timeout.
        result = _SENTINEL
        error: Optional[BaseException] = None

        def _run():
            nonlocal result, error
            try:
                result = actual_method(*args, **kwargs)
            except Exception as exc:
                error = exc

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_ms / 1000.0)

        if thread.is_alive():
            raise CapabilityTimeoutError(
                f"Method '{method_name}' on object '{self._obj_name}' "
                f"exceeded timeout."
            )

        if error is not None:
            # Sanitize the error — do not expose internal details.
            raise CapabilityMethodNotDeclaredError(
                f"Method '{method_name}' on object '{self._obj_name}' "
                f"raised an error during execution."
            ) from None  # Suppress chaining to avoid leaking internals.

        # Validate return type.
        if not _is_safe_return_value(result):
            raise CapabilityReturnTypeDeniedError(
                f"Method '{method_name}' on object '{self._obj_name}' "
                f"returned a value of disallowed type."
            )

        return result

    def __repr__(self) -> str:
        return (
            f"<MethodDispatcher '{self._obj_name}.{self._method_desc.name}'>"
        )


_SENTINEL = object()
