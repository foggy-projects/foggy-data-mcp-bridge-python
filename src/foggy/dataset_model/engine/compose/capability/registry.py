"""Capability registry — default-empty, fail-closed function and object
facade registry for Compose Script.

The registry stores validated descriptors and their handlers / targets.
Registration validates descriptors; duplicate or reserved names are
rejected.  The registry itself does NOT decide runtime visibility — that
is the job of :class:`CapabilityPolicy`.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, Optional

from .descriptors import (
    FunctionDescriptor,
    LibraryDescriptor,
    ObjectFacadeDescriptor,
    RESERVED_NAMES,
)
from .errors import (
    CapabilityInvalidDescriptorError,
    CapabilityNotRegisteredError,
    CapabilityUnsupportedDialectError,
)
from .sql_fragment import SqlFragment


class CapabilityRegistry:
    """Default-empty capability registry.

    Thread safety: not thread-safe. Create per-application or guard
    externally.  Script execution should use a snapshot or reference
    to an immutable state.
    """

    def __init__(self) -> None:
        self._functions: Dict[str, _FunctionEntry] = {}
        self._objects: Dict[str, _ObjectEntry] = {}
        self._libraries: Dict[str, _LibraryEntry] = {}

    # ------------------------------------------------------------------
    # Function registration
    # ------------------------------------------------------------------

    def register_function(
        self,
        descriptor: FunctionDescriptor,
        *,
        renderer: Optional[Callable] = None,
        handler: Optional[Callable] = None,
    ) -> None:
        """Register a controlled function.

        Parameters
        ----------
        descriptor:
            Validated function descriptor.
        renderer:
            Required for ``sql_scalar``.  Signature:
            ``(args: dict, dialect: str, bind: Callable) -> SqlFragment``
        handler:
            Required for ``pure_runtime``.  Signature:
            ``(**kwargs) -> <safe return type>``

        Raises
        ------
        CapabilityInvalidDescriptorError
            On duplicate name, missing renderer/handler, or invalid descriptor.
        """
        name = descriptor.name

        if name in self._functions:
            raise CapabilityInvalidDescriptorError(
                f"Function '{name}' is already registered."
            )
        if name in self._objects:
            raise CapabilityInvalidDescriptorError(
                f"Name '{name}' is already used by an object facade."
            )

        if descriptor.kind == "sql_scalar":
            if renderer is None:
                raise CapabilityInvalidDescriptorError(
                    f"Function '{name}' (sql_scalar): renderer is required."
                )
            self._functions[name] = _FunctionEntry(
                descriptor=descriptor, renderer=renderer, handler=None,
            )
        elif descriptor.kind == "pure_runtime":
            if handler is None:
                raise CapabilityInvalidDescriptorError(
                    f"Function '{name}' (pure_runtime): handler is required."
                )
            self._functions[name] = _FunctionEntry(
                descriptor=descriptor, renderer=None, handler=handler,
            )
        else:
            raise CapabilityInvalidDescriptorError(
                f"Function '{name}': unknown kind '{descriptor.kind}'."
            )

    # ------------------------------------------------------------------
    # Object facade registration
    # ------------------------------------------------------------------

    def register_object_facade(
        self,
        descriptor: ObjectFacadeDescriptor,
        *,
        target: Any,
    ) -> None:
        """Register a controlled object facade.

        Parameters
        ----------
        descriptor:
            Validated object facade descriptor.
        target:
            The actual object instance.  Only descriptor-declared methods
            will be callable; everything else is blocked by the proxy.

        Raises
        ------
        CapabilityInvalidDescriptorError
            On duplicate object name or method not found on target.
        """
        obj_name = descriptor.object_name

        if obj_name in self._objects:
            raise CapabilityInvalidDescriptorError(
                f"Object facade '{obj_name}' is already registered."
            )
        if obj_name in self._functions:
            raise CapabilityInvalidDescriptorError(
                f"Name '{obj_name}' is already used by a function."
            )

        # Verify that declared methods actually exist on target.
        for method in descriptor.methods:
            if not hasattr(target, method.name):
                raise CapabilityInvalidDescriptorError(
                    f"Object facade '{obj_name}': declared method "
                    f"'{method.name}' not found on target object."
                )
            attr = getattr(target, method.name)
            if not callable(attr):
                raise CapabilityInvalidDescriptorError(
                    f"Object facade '{obj_name}': declared method "
                    f"'{method.name}' is not callable on target object."
                )

        self._objects[obj_name] = _ObjectEntry(
            descriptor=descriptor, target=target,
        )

    # ------------------------------------------------------------------
    # Library registration
    # ------------------------------------------------------------------

    def register_library(
        self,
        descriptor: LibraryDescriptor,
        *,
        source: str,
    ) -> None:
        """Register a controlled fsscript library source.

        ``source`` is trusted provider input, but the descriptor still
        anchors it with a sha256 hash so deployment drift is detected
        before script execution.
        """
        name = descriptor.name
        if name in self._libraries:
            raise CapabilityInvalidDescriptorError(
                f"Library '{name}' is already registered."
            )
        if not source or not str(source).strip():
            raise CapabilityInvalidDescriptorError(
                f"Library '{name}': source must not be empty."
            )

        expected = descriptor.source_hash.removeprefix("sha256:")
        actual = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if expected.lower() != actual.lower():
            raise CapabilityInvalidDescriptorError(
                f"Library '{name}': source_hash does not match source."
            )

        self._libraries[name] = _LibraryEntry(
            descriptor=descriptor,
            source=source,
        )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_function(self, name: str) -> _FunctionEntry:
        """Return the function entry or raise."""
        entry = self._functions.get(name)
        if entry is None:
            raise CapabilityNotRegisteredError(
                f"Function '{name}' is not registered."
            )
        return entry

    def get_object(self, name: str) -> _ObjectEntry:
        """Return the object entry or raise."""
        entry = self._objects.get(name)
        if entry is None:
            raise CapabilityNotRegisteredError(
                f"Object '{name}' is not registered."
            )
        return entry

    def get_library(self, name: str) -> _LibraryEntry:
        """Return the library entry or raise."""
        entry = self._libraries.get(name)
        if entry is None:
            raise CapabilityNotRegisteredError(
                f"Library '{name}' is not registered."
            )
        return entry

    def has_function(self, name: str) -> bool:
        return name in self._functions

    def has_object(self, name: str) -> bool:
        return name in self._objects

    def has_library(self, name: str) -> bool:
        return name in self._libraries

    @property
    def function_names(self) -> frozenset[str]:
        return frozenset(self._functions.keys())

    @property
    def object_names(self) -> frozenset[str]:
        return frozenset(self._objects.keys())

    @property
    def library_names(self) -> frozenset[str]:
        return frozenset(self._libraries.keys())

    def is_empty(self) -> bool:
        return not self._functions and not self._objects and not self._libraries


# ---------------------------------------------------------------------------
# Internal entry types
# ---------------------------------------------------------------------------

class _FunctionEntry:
    """Internal storage for a registered function."""

    __slots__ = ("descriptor", "renderer", "handler")

    def __init__(
        self,
        descriptor: FunctionDescriptor,
        renderer: Optional[Callable],
        handler: Optional[Callable],
    ) -> None:
        self.descriptor = descriptor
        self.renderer = renderer
        self.handler = handler


class _ObjectEntry:
    """Internal storage for a registered object facade."""

    __slots__ = ("descriptor", "target")

    def __init__(
        self,
        descriptor: ObjectFacadeDescriptor,
        target: Any,
    ) -> None:
        self.descriptor = descriptor
        self.target = target


class _LibraryEntry:
    """Internal storage for a registered fsscript library."""

    __slots__ = ("descriptor", "source")

    def __init__(
        self,
        descriptor: LibraryDescriptor,
        source: str,
    ) -> None:
        self.descriptor = descriptor
        self.source = source
