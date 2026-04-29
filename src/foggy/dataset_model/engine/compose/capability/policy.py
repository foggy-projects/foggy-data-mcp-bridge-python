"""Runtime capability policy — controls which registered capabilities
are visible to a given script execution.

Default policy is empty: no capabilities are allowed.  The host
application must explicitly list allowed functions, objects, and
auth scopes for each script invocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set


@dataclass(frozen=True)
class CapabilityPolicy:
    """Immutable runtime policy for a script execution.

    The policy acts as a second gate after registration:
    even if a capability is in the registry, it is only visible
    to the script if the policy allows it.

    Attributes
    ----------
    allowed_functions:
        Set of function names the script may call.
    allowed_objects:
        Mapping of object_name → set of allowed method names.
        An empty set means the object is visible but no methods
        are allowed (useless but safe).
    allowed_scopes:
        Set of auth_scope values the current execution is entitled to.
    allowed_libraries:
        Set of controlled fsscript library names the script may import.
    allowed_symbols:
        Optional per-library symbol allow-list. If a library is allowed
        but absent from this mapping, every descriptor-declared export is
        allowed. If present, only the listed symbols are importable.
    """

    allowed_functions: FrozenSet[str] = field(default_factory=frozenset)
    allowed_objects: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    allowed_scopes: FrozenSet[str] = field(default_factory=frozenset)
    allowed_libraries: FrozenSet[str] = field(default_factory=frozenset)
    allowed_symbols: Dict[str, FrozenSet[str]] = field(default_factory=dict)

    def is_function_allowed(self, name: str) -> bool:
        return name in self.allowed_functions

    def is_object_allowed(self, object_name: str) -> bool:
        return object_name in self.allowed_objects

    def is_method_allowed(self, object_name: str, method_name: str) -> bool:
        methods = self.allowed_objects.get(object_name)
        if methods is None:
            return False
        return method_name in methods

    def is_scope_allowed(self, scope: str) -> bool:
        return scope in self.allowed_scopes

    def is_library_allowed(self, name: str) -> bool:
        return name in self.allowed_libraries

    def is_symbol_allowed(self, library_name: str, symbol: str) -> bool:
        if not self.is_library_allowed(library_name):
            return False
        symbols = self.allowed_symbols.get(library_name)
        if symbols is None:
            return True
        return symbol in symbols

    @staticmethod
    def empty() -> CapabilityPolicy:
        """Return the default empty policy — no capabilities allowed."""
        return CapabilityPolicy()
