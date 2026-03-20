"""Scope chain for FSScript lexical scoping.

Implements a scope chain that behaves like a dict but manages nested scopes
internally. This enables proper closure capture: functions snapshot the scope
chain at definition time and restore it (plus a fresh local scope) at call time.

Design mirrors Java's Stack<FsscriptClosure> / savedStack mechanism.
"""

from typing import Any, Dict, Iterator, List, Optional


class ScopeChain:
    """Scope chain with dict-compatible interface.

    Maintains a list of scope dicts (innermost last). Variable lookup walks
    from the innermost scope outward. Assignment updates the variable in
    whichever scope already owns it; new variables go into the local (top)
    scope.

    Usage::

        sc = ScopeChain()          # global scope
        sc["x"] = 1                # declare in global
        child = ScopeChain(sc.snapshot_scopes())  # closure capture
        child.declare("y", 2)      # new local var
        child["x"] = 10            # updates parent's x
    """

    __slots__ = ("_scopes", "_local")

    def __init__(self, parent_scopes: Optional[List[dict]] = None):
        """Create a scope chain.

        Args:
            parent_scopes: List of parent scope dicts (shallow-copied).
                Each dict object is shared by reference so that closures
                can mutate captured variables.
        """
        self._scopes: List[dict] = list(parent_scopes) if parent_scopes else []
        self._local: dict = {}
        self._scopes.append(self._local)

    # ------------------------------------------------------------------
    # Core lookup / mutation
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Look up *key* from innermost scope outward."""
        for scope in reversed(self._scopes):
            if key in scope:
                return scope[key]
        return default

    def __getitem__(self, key: str) -> Any:
        for scope in reversed(self._scopes):
            if key in scope:
                return scope[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Assign *value* to *key*.

        If *key* already exists in any scope, update it **in place** (this is
        what makes closure mutation work).  Otherwise declare it in the local
        scope.
        """
        for scope in reversed(self._scopes):
            if key in scope:
                scope[key] = value
                return
        # New variable → local scope
        self._local[key] = value

    def __contains__(self, key: object) -> bool:
        return any(key in scope for scope in self._scopes)

    def __delitem__(self, key: str) -> None:
        for scope in reversed(self._scopes):
            if key in scope:
                del scope[key]
                return
        raise KeyError(key)

    # ------------------------------------------------------------------
    # Declaration helpers
    # ------------------------------------------------------------------

    def declare(self, key: str, value: Any) -> None:
        """Declare a variable in the **local** (top) scope.

        Used for function parameters and ``let``/``const`` declarations that
        must shadow outer variables rather than update them.
        """
        self._local[key] = value

    # ------------------------------------------------------------------
    # Scope stack management
    # ------------------------------------------------------------------

    def snapshot_scopes(self) -> List[dict]:
        """Return a shallow copy of the scopes list for closure capture.

        The individual dict objects are **shared** so that closures can
        mutate captured variables (counter pattern).
        """
        return list(self._scopes)

    def push_scope(self, scope: Optional[dict] = None) -> None:
        """Push a new scope (for block / iteration scoping)."""
        new_scope = scope if scope is not None else {}
        self._scopes.append(new_scope)
        self._local = new_scope

    def pop_scope(self) -> dict:
        """Pop the topmost scope and return it."""
        popped = self._scopes.pop()
        self._local = self._scopes[-1] if self._scopes else {}
        return popped

    # ------------------------------------------------------------------
    # dict-compatible interface (needed by existing codebase)
    # ------------------------------------------------------------------

    def copy(self) -> dict:
        """Return a flat dict snapshot (used by legacy code paths)."""
        result: Dict[str, Any] = {}
        for scope in self._scopes:
            result.update(scope)
        return result

    def update(self, other: dict = None, **kwargs: Any) -> None:  # type: ignore[override]
        """Merge *other* into the local scope."""
        if other:
            self._local.update(other)
        if kwargs:
            self._local.update(kwargs)

    def pop(self, key: str, *args: Any) -> Any:
        """Remove and return *key* (from innermost scope that has it)."""
        for scope in reversed(self._scopes):
            if key in scope:
                return scope.pop(key)
        if args:
            return args[0]
        raise KeyError(key)

    def keys(self):  # type: ignore[override]
        """All visible keys (innermost wins)."""
        seen: set = set()
        result: list = []
        for scope in reversed(self._scopes):
            for k in scope:
                if k not in seen:
                    seen.add(k)
                    result.append(k)
        return result

    def values(self):  # type: ignore[override]
        """All visible values."""
        return [self.get(k) for k in self.keys()]

    def items(self):  # type: ignore[override]
        """All visible (key, value) pairs."""
        return [(k, self.get(k)) for k in self.keys()]

    def setdefault(self, key: str, default: Any = None) -> Any:
        """Get *key* or set and return *default*."""
        if key in self:
            return self.get(key)
        self._local[key] = default
        return default

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(set().union(*self._scopes))

    def __repr__(self) -> str:
        depth = len(self._scopes)
        total = len(self)
        return f"ScopeChain(depth={depth}, vars={total})"


__all__ = ["ScopeChain"]
