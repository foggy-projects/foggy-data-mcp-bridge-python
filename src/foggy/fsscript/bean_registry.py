"""Bean registry for FSScript ``import '@beanName'`` support.

Python equivalent of Java's Spring ``ApplicationContext`` for FSScript.

The Java implementation (``ImportBeanExp``) looks up beans from the Spring
context, then exposes their properties and methods to the script.  This
module provides the same capability via a simple registry + a
``ModuleLoader`` that intercepts ``@``-prefixed module paths.

Usage::

    registry = BeanRegistry()

    # Register a Python object as a bean
    registry.register("myService", my_service_instance)

    # The evaluator wires it automatically
    evaluator = ExpressionEvaluator(
        context={},
        bean_registry=registry,
    )

    # Now FSScript can do:
    #   import { doWork } from '@myService';
    #   var result = doWork(42);
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from foggy.fsscript.module_loader import ModuleLoader


class BeanRegistry:
    """Registry that maps bean names to Python objects.

    Mirrors Java's ``ApplicationContext.getBean(name)`` pattern.
    """

    def __init__(self) -> None:
        self._beans: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, bean: Any) -> None:
        """Register a bean under *name*."""
        self._beans[name] = bean

    def register_all(self, beans: Dict[str, Any]) -> None:
        """Bulk-register multiple beans."""
        self._beans.update(beans)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Any:
        """Get a bean by name.

        Raises:
            KeyError: If no bean with that name is registered.
        """
        if name not in self._beans:
            raise KeyError(f"Bean not found: '{name}'")
        return self._beans[name]

    def has(self, name: str) -> bool:
        """Check if a bean with *name* exists."""
        return name in self._beans

    @property
    def names(self) -> list:
        """Return all registered bean names."""
        return list(self._beans.keys())

    # ------------------------------------------------------------------
    # Export extraction (mirrors Java ImportBeanExp.evalValue)
    # ------------------------------------------------------------------

    def get_exports(self, name: str) -> Dict[str, Any]:
        """Extract an exports dict from the bean.

        For named imports (``import { fn } from '@bean'``):
          - Public callable attributes  → exported as functions
          - Public non-callable attrs   → exported as values
        For default imports (``import bean from '@bean'``):
          - ``"default"`` key           → the bean itself

        This mirrors Java's ``BeanInfoHelper`` + ``BeanMethodFunction``
        pattern in ``ImportBeanExp``.
        """
        bean = self.get(name)
        exports: Dict[str, Any] = {"default": bean}

        if isinstance(bean, dict):
            # dict-bean: treat keys as named exports
            exports.update(bean)
            return exports

        # Object bean: introspect public attributes
        for attr_name in dir(bean):
            if attr_name.startswith("_"):
                continue
            try:
                val = getattr(bean, attr_name)
            except Exception:
                continue

            # Skip class-level descriptors that aren't useful
            if isinstance(val, (type, staticmethod, classmethod)):
                continue

            exports[attr_name] = val

        return exports


class BeanModuleLoader(ModuleLoader):
    """ModuleLoader that resolves ``@beanName`` paths from a BeanRegistry.

    Designed to be used inside a ``ChainedModuleLoader``::

        loader = ChainedModuleLoader(
            BeanModuleLoader(registry),   # try @bean first
            FileModuleLoader(base_path),  # then file system
        )
    """

    def __init__(self, registry: BeanRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> BeanRegistry:
        return self._registry

    @staticmethod
    def _strip_at(module_path: str) -> Optional[str]:
        """Return the bean name if *module_path* starts with ``@``, else None."""
        path = module_path.strip("'\"")
        if path.startswith("@"):
            return path[1:]
        return None

    def has_module(self, module_path: str) -> bool:
        bean_name = self._strip_at(module_path)
        if bean_name is None:
            return False
        return self._registry.has(bean_name)

    def load_module(self, module_path: str, context: Dict[str, Any]) -> Dict[str, Any]:
        bean_name = self._strip_at(module_path)
        if bean_name is None:
            from foggy.fsscript.module_loader import ModuleNotFoundError as MNF
            raise MNF(f"BeanModuleLoader: not a bean path: {module_path}")
        return self._registry.get_exports(bean_name)


class ModuleNotFoundError(Exception):
    """Raised when a bean is not found."""
    pass


__all__ = [
    "BeanRegistry",
    "BeanModuleLoader",
]
