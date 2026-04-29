"""Controlled fsscript library loader for Compose Script v1.8."""

from __future__ import annotations

import threading
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.module_loader import ModuleLoader
from foggy.fsscript.parser import COMPOSE_QUERY_DIALECT, FsscriptParser

from ..sandbox import scan_script_source
from .errors import (
    CapabilityImportCycleError,
    CapabilityImportNotAllowedError,
    CapabilitySymbolCollisionError,
    CapabilitySymbolNotDeclaredError,
)
from .policy import CapabilityPolicy
from .registry import CapabilityRegistry


ImportBinding = Tuple[str, Optional[str]]


class ControlledLibraryModuleLoader(ModuleLoader):
    """ModuleLoader backed only by :class:`CapabilityRegistry` libraries.

    It never resolves physical paths.  The incoming module string is treated
    as a logical library name and must match a registered
    :class:`LibraryDescriptor`.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        policy: CapabilityPolicy,
        *,
        surface: str = "compose_runtime",
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._surface = surface
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._loading: set[str] = set()
        self._lock = threading.Lock()

    def has_module(self, module_path: str) -> bool:
        name = self._logical_name(module_path)
        return self._registry.has_library(name)

    def validate_import(
        self,
        module_path: str,
        *,
        bindings: Optional[Sequence[ImportBinding]] = None,
        namespace: Optional[str] = None,
        default_name: Optional[str] = None,
        context: Dict[str, Any],
    ) -> None:
        """Preflight an import before ``ImportExpression`` mutates context."""
        name = self._logical_name(module_path)
        entry = self._registry.get_library(name)
        descriptor = entry.descriptor
        self._ensure_library_allowed(name)

        current_library = context.get("__current_library__")
        if current_library:
            current = self._registry.get_library(current_library).descriptor
            if name not in current.dependencies:
                raise CapabilityImportNotAllowedError(
                    f"Library '{current_library}' does not declare dependency '{name}'."
                )

        if self._surface not in descriptor.allowed_in:
            raise CapabilityImportNotAllowedError(
                f"Library '{name}' is not allowed in surface '{self._surface}'."
            )

        if namespace:
            self._ensure_no_collision(namespace, context)
            return

        if default_name:
            self._ensure_export_allowed(name, "default", descriptor.exports)
            self._ensure_no_collision(default_name, context)
            return

        for symbol, alias in bindings or ():
            self._ensure_export_allowed(name, symbol, descriptor.exports)
            self._ensure_no_collision(alias or symbol, context)

    def load_module(self, module_path: str, context: Dict[str, Any]) -> Dict[str, Any]:
        name = self._logical_name(module_path)
        entry = self._registry.get_library(name)
        descriptor = entry.descriptor

        self._ensure_library_allowed(name)
        if self._surface not in descriptor.allowed_in:
            raise CapabilityImportNotAllowedError(
                f"Library '{name}' is not allowed in surface '{self._surface}'."
            )

        with self._lock:
            if name in self._cache:
                return dict(self._cache[name])
            if name in self._loading:
                raise CapabilityImportCycleError(
                    f"Circular library import detected for '{name}'."
                )
            self._loading.add(name)

        try:
            source = entry.source
            scan_script_source(source, allow_controlled_imports=True)
            parser = FsscriptParser(source, dialect=COMPOSE_QUERY_DIALECT)
            ast = parser.parse_program()
            evaluator = ExpressionEvaluator(
                context={
                    "__current_library__": name,
                    "__module_loader__": self,
                },
                module_loader=self,
                bean_registry=None,
            )
            evaluator.evaluate(ast)
            raw_exports = evaluator.get_exports()
            declared_exports = set(descriptor.exports)

            extra_exports = set(raw_exports) - declared_exports
            if extra_exports:
                raise CapabilitySymbolNotDeclaredError(
                    f"Library '{name}' exported undeclared symbols."
                )

            missing_exports = declared_exports - set(raw_exports)
            if missing_exports:
                raise CapabilitySymbolNotDeclaredError(
                    f"Library '{name}' did not export declared symbols."
                )

            visible_exports = {
                symbol: value
                for symbol, value in raw_exports.items()
                if self._policy.is_symbol_allowed(name, symbol)
            }
            with self._lock:
                self._cache[name] = dict(visible_exports)
            return dict(visible_exports)
        finally:
            with self._lock:
                self._loading.discard(name)

    def _logical_name(self, module_path: str) -> str:
        return str(module_path).strip("'\"")

    def _ensure_library_allowed(self, name: str) -> None:
        if not self._policy.is_library_allowed(name):
            raise CapabilityImportNotAllowedError(
                f"Library '{name}' is not allowed by policy."
            )

    def _ensure_export_allowed(
        self,
        library_name: str,
        symbol: str,
        declared_exports: Iterable[str],
    ) -> None:
        if symbol not in set(declared_exports):
            raise CapabilitySymbolNotDeclaredError(
                f"Library '{library_name}' does not declare symbol '{symbol}'."
            )
        if not self._policy.is_symbol_allowed(library_name, symbol):
            raise CapabilityImportNotAllowedError(
                f"Symbol '{symbol}' from library '{library_name}' is not allowed."
            )

    def _ensure_no_collision(self, binding_name: str, context: Dict[str, Any]) -> None:
        if binding_name in context and not binding_name.startswith("__"):
            raise CapabilitySymbolCollisionError(
                f"Import binding '{binding_name}' would overwrite an existing name."
            )


__all__ = ["ControlledLibraryModuleLoader"]
