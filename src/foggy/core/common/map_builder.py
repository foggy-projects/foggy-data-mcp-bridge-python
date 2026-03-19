"""MapBuilder - Fluent dictionary builder utility."""

from typing import Any, Dict, Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class MapBuilder(Dict[K, V], Generic[K, V]):
    """Fluent dictionary builder with chainable methods.

    Usage:
        builder = MapBuilder[str, Any]()
        result = builder.put("name", "John").put("age", 30).build()

        # Or with initial values
        builder = MapBuilder[str, Any]({"initial": "value"})
    """

    def __init__(self, initial: Optional[Dict[K, V]] = None) -> None:
        """Initialize with optional initial values."""
        super().__init__()
        if initial:
            self.update(initial)

    def put(self, key: K, value: V) -> "MapBuilder[K, V]":
        """Add a key-value pair."""
        self[key] = value
        return self

    def put_if_not_none(self, key: K, value: Optional[V]) -> "MapBuilder[K, V]":
        """Add a key-value pair only if value is not None."""
        if value is not None:
            self[key] = value
        return self

    def put_object(self, key: K, value: Any) -> "MapBuilder[K, V]":
        """Add a key-value pair (alias for put, for compatibility)."""
        return self.put(key, value)

    def put_all(self, mapping: Dict[K, V]) -> "MapBuilder[K, V]":
        """Add all key-value pairs from a dictionary."""
        self.update(mapping)
        return self

    def remove(self, key: K) -> "MapBuilder[K, V]":
        """Remove a key."""
        if key in self:
            del self[key]
        return self

    def clear_all(self) -> "MapBuilder[K, V]":
        """Clear all entries."""
        self.clear()
        return self

    def build(self) -> Dict[K, V]:
        """Build and return the dictionary."""
        return dict(self)

    def to_map(self) -> Dict[K, V]:
        """Alias for build()."""
        return self.build()

    @classmethod
    def create(cls) -> "MapBuilder[K, V]":
        """Create a new empty MapBuilder."""
        return cls()

    @classmethod
    def from_dict(cls, data: Dict[K, V]) -> "MapBuilder[K, V]":
        """Create a MapBuilder from an existing dictionary."""
        return cls(data)