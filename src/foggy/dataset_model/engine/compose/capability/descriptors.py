"""Capability descriptors for v1.7 controlled function and object facade registration.

Descriptors are immutable (frozen dataclass) declarations of what a
capability exposes, where it may be used, and what safety properties it
has.  They are validated on construction so that invalid registrations
fail fast before reaching the registry.

Field rules match the usage manual § descriptor constraints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import CapabilityInvalidDescriptorError, CapabilitySideEffectDeniedError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_FUNCTION_KINDS: frozenset[str] = frozenset({"sql_scalar", "pure_runtime"})
VALID_SIDE_EFFECTS: frozenset[str] = frozenset({"none"})  # v1.7 only allows "none"
VALID_ALLOWED_IN: frozenset[str] = frozenset({
    "formula", "compose_column", "compose_runtime",
})
VALID_RETURN_TYPES: frozenset[str] = frozenset({
    "string", "int", "float", "bool", "date", "datetime",
    "dict", "list", "null",
})

# Safe identifier: letters, digits, underscores; must start with a letter.
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

# Reserved names that cannot be overridden by capabilities.
RESERVED_NAMES: frozenset[str] = frozenset({
    "from", "dsl", "Query", "params",
    # Python builtins / sandbox escapes
    "eval", "exec", "import", "require",
    "__import__", "__builtins__",
    # QueryPlan methods
    "select", "where", "group_by", "order_by",
    "join", "union", "to_sql", "execute",
    # fsscript builtins
    "JSON", "parseInt", "parseFloat", "toString",
    "String", "Number", "Boolean",
    "isNaN", "isFinite", "Array", "Object", "Function",
    "typeof",
    # Additional safety
    "self", "cls", "None", "True", "False",
})


def _validate_name(name: str, label: str) -> None:
    """Validate a capability/method/object name."""
    if not name:
        raise CapabilityInvalidDescriptorError(
            f"{label} name must not be empty."
        )
    if not _SAFE_NAME_RE.match(name):
        raise CapabilityInvalidDescriptorError(
            f"{label} name '{name}' contains unsafe characters. "
            f"Only letters, digits, and underscores are allowed, "
            f"and it must start with a letter."
        )
    if name in RESERVED_NAMES:
        raise CapabilityInvalidDescriptorError(
            f"{label} name '{name}' is reserved and cannot be used."
        )
    if name.startswith("__"):
        raise CapabilityInvalidDescriptorError(
            f"{label} name '{name}' must not start with double underscore."
        )


def _validate_side_effect(side_effect: str) -> None:
    """v1.7 only allows side_effect='none'."""
    if side_effect not in VALID_SIDE_EFFECTS:
        raise CapabilitySideEffectDeniedError(
            f"side_effect must be 'none' in v1.7; got '{side_effect}'."
        )


def _validate_return_type(return_type: str) -> None:
    if return_type not in VALID_RETURN_TYPES:
        raise CapabilityInvalidDescriptorError(
            f"return_type '{return_type}' is not a recognized safe type. "
            f"Allowed: {sorted(VALID_RETURN_TYPES)}."
        )


# ---------------------------------------------------------------------------
# Function Descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionDescriptor:
    """Descriptor for a controlled function registration.

    Validated on construction; raises :class:`CapabilityInvalidDescriptorError`
    or :class:`CapabilitySideEffectDeniedError` on invalid fields.
    """

    name: str
    kind: str  # "sql_scalar" | "pure_runtime"
    args_schema: List[Dict[str, Any]]
    return_type: str
    deterministic: bool
    side_effect: str  # v1.7: must be "none"
    allowed_in: List[str]
    audit_tag: str
    dialects: Optional[List[str]] = None  # required for sql_scalar

    def __post_init__(self) -> None:
        _validate_name(self.name, "Function")

        if self.kind not in VALID_FUNCTION_KINDS:
            raise CapabilityInvalidDescriptorError(
                f"Function kind must be one of {sorted(VALID_FUNCTION_KINDS)}; "
                f"got '{self.kind}'."
            )

        _validate_side_effect(self.side_effect)
        _validate_return_type(self.return_type)

        if not self.allowed_in:
            raise CapabilityInvalidDescriptorError(
                f"Function '{self.name}': allowed_in must not be empty."
            )
        for surface in self.allowed_in:
            if surface not in VALID_ALLOWED_IN:
                raise CapabilityInvalidDescriptorError(
                    f"Function '{self.name}': allowed_in value '{surface}' "
                    f"is not recognized. Allowed: {sorted(VALID_ALLOWED_IN)}."
                )

        if not self.audit_tag:
            raise CapabilityInvalidDescriptorError(
                f"Function '{self.name}': audit_tag must not be empty."
            )

        if self.kind == "sql_scalar":
            if not self.dialects:
                raise CapabilityInvalidDescriptorError(
                    f"Function '{self.name}': sql_scalar functions must "
                    f"declare at least one dialect."
                )

        if not isinstance(self.args_schema, list):
            raise CapabilityInvalidDescriptorError(
                f"Function '{self.name}': args_schema must be a list."
            )

        # Validate each arg schema entry
        for idx, arg in enumerate(self.args_schema):
            if not isinstance(arg, dict):
                raise CapabilityInvalidDescriptorError(
                    f"Function '{self.name}': args_schema[{idx}] must be a dict."
                )
            if "name" not in arg:
                raise CapabilityInvalidDescriptorError(
                    f"Function '{self.name}': args_schema[{idx}] missing 'name'."
                )
            if "type" not in arg:
                raise CapabilityInvalidDescriptorError(
                    f"Function '{self.name}': args_schema[{idx}] missing 'type'."
                )


# ---------------------------------------------------------------------------
# Method Descriptor (for object facade)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MethodDescriptor:
    """Descriptor for a single method on an object facade."""

    name: str
    args_schema: List[Dict[str, Any]]
    return_type: str
    side_effect: str  # v1.7: must be "none"
    auth_scope: str
    timeout_ms: int
    audit_tag: str

    def __post_init__(self) -> None:
        _validate_name(self.name, "Method")
        _validate_side_effect(self.side_effect)
        _validate_return_type(self.return_type)

        if not self.auth_scope:
            raise CapabilityInvalidDescriptorError(
                f"Method '{self.name}': auth_scope must not be empty."
            )

        if self.timeout_ms <= 0:
            raise CapabilityInvalidDescriptorError(
                f"Method '{self.name}': timeout_ms must be positive; "
                f"got {self.timeout_ms}."
            )

        if not self.audit_tag:
            raise CapabilityInvalidDescriptorError(
                f"Method '{self.name}': audit_tag must not be empty."
            )

        if not isinstance(self.args_schema, list):
            raise CapabilityInvalidDescriptorError(
                f"Method '{self.name}': args_schema must be a list."
            )


# ---------------------------------------------------------------------------
# Object Facade Descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ObjectFacadeDescriptor:
    """Descriptor for a controlled object facade registration."""

    object_name: str
    methods: List[MethodDescriptor]

    def __post_init__(self) -> None:
        _validate_name(self.object_name, "Object facade")

        if not self.methods:
            raise CapabilityInvalidDescriptorError(
                f"Object facade '{self.object_name}': "
                f"must declare at least one method."
            )

        seen_names: set[str] = set()
        for method in self.methods:
            if method.name in seen_names:
                raise CapabilityInvalidDescriptorError(
                    f"Object facade '{self.object_name}': "
                    f"duplicate method name '{method.name}'."
                )
            seen_names.add(method.name)
