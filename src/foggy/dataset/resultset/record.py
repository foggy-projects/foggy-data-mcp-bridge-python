"""Record protocol and implementations for foggy-dataset.

This module provides the Record interface and base implementations
for representing database result rows.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntFlag
from typing import Any, Dict, Generic, Iterator, List, Optional, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T")


class RecordState(IntFlag):
    """Record state flags for tracking modifications."""

    DELETE = 0x01  # Record marked for deletion
    UPDATE = 0x02  # Record has been updated
    NEW = 0x04  # Record is newly created
    EDITING = 0x08  # Record is being edited
    LEAF = 0x10  # Record is a leaf node (for tree data)
    XNEW = 0x20  # Record is detached/newly created


class RecordMetadata(BaseModel, Generic[T]):
    """Metadata for a record."""

    column_names: List[str] = []
    column_types: Dict[str, str] = {}
    table_name: Optional[str] = None


class Record(ABC, Generic[T]):
    """Record interface for database result rows.

    A Record represents a single row from a database result set.
    It provides dict-like access to column values and tracks
    modification state.

    Type parameter T is the underlying value type (e.g., dict, dataclass).
    """

    @abstractmethod
    def get(self, name: str) -> Any:
        """Get a column value by name.

        Args:
            name: Column name

        Returns:
            Column value
        """
        pass

    @abstractmethod
    def set(self, name: str, value: Any) -> None:
        """Set a column value.

        Args:
            name: Column name
            value: New value
        """
        pass

    @abstractmethod
    def get_value(self) -> T:
        """Get the underlying value object.

        Returns:
            Underlying value (dict, dataclass, etc.)
        """
        pass

    @abstractmethod
    def get_state(self) -> RecordState:
        """Get the current state flags.

        Returns:
            RecordState flags
        """
        pass

    @abstractmethod
    def is_modified(self) -> bool:
        """Check if record has been modified.

        Returns:
            True if modified
        """
        pass

    @abstractmethod
    def is_new(self) -> bool:
        """Check if record is newly created.

        Returns:
            True if new
        """
        pass

    @abstractmethod
    def is_deleted(self) -> bool:
        """Check if record is marked for deletion.

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    def begin_edit(self) -> None:
        """Begin editing the record."""
        pass

    @abstractmethod
    def end_edit(self) -> None:
        """End editing the record."""
        pass

    @abstractmethod
    def cancel_edit(self) -> None:
        """Cancel edits and restore original values."""
        pass

    @abstractmethod
    def delete(self) -> None:
        """Mark the record for deletion."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        pass

    @abstractmethod
    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string
        """
        pass

    def __getitem__(self, name: str) -> Any:
        """Get column value using bracket notation.

        Args:
            name: Column name

        Returns:
            Column value
        """
        return self.get(name)

    def __setitem__(self, name: str, value: Any) -> None:
        """Set column value using bracket notation.

        Args:
            name: Column name
            value: New value
        """
        self.set(name, value)


class DictRecord(Record[Dict[str, Any]]):
    """Record implementation backed by a dictionary.

    This is the most common record type for query results.
    """

    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[RecordMetadata] = None,
    ):
        """Initialize the record.

        Args:
            data: Initial data dictionary
            metadata: Record metadata
        """
        self._data: Dict[str, Any] = data or {}
        self._original_data: Dict[str, Any] = {}
        self._state = RecordState(0)
        self._metadata = metadata or RecordMetadata()

    def get(self, name: str, default: Any = None) -> Any:
        """Get a column value by name.

        Args:
            name: Column name
            default: Default value if not found

        Returns:
            Column value or default
        """
        return self._data.get(name, default)

    def set(self, name: str, value: Any) -> None:
        """Set a column value.

        Args:
            name: Column name
            value: New value
        """
        if self._state & RecordState.EDITING:
            if name not in self._original_data:
                self._original_data[name] = self._data.get(name)

        self._data[name] = value

        if not (self._state & RecordState.NEW):
            self._state |= RecordState.UPDATE

    def get_value(self) -> Dict[str, Any]:
        """Get the underlying dictionary.

        Returns:
            Data dictionary
        """
        return self._data

    def get_state(self) -> RecordState:
        """Get current state flags.

        Returns:
            RecordState flags
        """
        return self._state

    def is_modified(self) -> bool:
        """Check if record has been modified.

        Returns:
            True if UPDATE or DELETE flag is set
        """
        return bool(self._state & (RecordState.UPDATE | RecordState.DELETE))

    def is_new(self) -> bool:
        """Check if record is newly created.

        Returns:
            True if NEW flag is set
        """
        return bool(self._state & RecordState.NEW)

    def is_deleted(self) -> bool:
        """Check if record is marked for deletion.

        Returns:
            True if DELETE flag is set
        """
        return bool(self._state & RecordState.DELETE)

    def begin_edit(self) -> None:
        """Begin editing the record."""
        self._state |= RecordState.EDITING

    def end_edit(self) -> None:
        """End editing the record."""
        self._state &= ~RecordState.EDITING
        self._original_data.clear()

    def cancel_edit(self) -> None:
        """Cancel edits and restore original values."""
        if self._state & RecordState.NEW:
            # New records are removed
            self._state |= RecordState.DELETE
        else:
            # Restore original values
            self._data.update(self._original_data)
            self._state &= ~RecordState.UPDATE

        self._state &= ~RecordState.EDITING
        self._original_data.clear()

    def delete(self) -> None:
        """Mark the record for deletion."""
        self._state |= RecordState.DELETE

    def apply(self, obj: Union[Dict[str, Any], object]) -> None:
        """Apply values from another object.

        Args:
            obj: Source object (dict or object with __dict__)
        """
        self.begin_edit()
        try:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    self.set(key, value)
            else:
                for key, value in obj.__dict__.items():
                    if not key.startswith('_'):
                        self.set(key, value)
        finally:
            self.end_edit()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Copy of data dictionary
        """
        return self._data.copy()

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string
        """
        import json
        return json.dumps(self._data, ensure_ascii=False, default=str)

    def get_metadata(self) -> RecordMetadata:
        """Get record metadata.

        Returns:
            RecordMetadata instance
        """
        return self._metadata

    def keys(self) -> Iterator[str]:
        """Get column names.

        Returns:
            Iterator of column names
        """
        return iter(self._data.keys())

    def values(self) -> Iterator[Any]:
        """Get column values.

        Returns:
            Iterator of values
        """
        return iter(self._data.values())

    def items(self) -> Iterator[tuple]:
        """Get column name-value pairs.

        Returns:
            Iterator of (name, value) tuples
        """
        return iter(self._data.items())

    def __contains__(self, name: str) -> bool:
        """Check if column exists.

        Args:
            name: Column name

        Returns:
            True if column exists
        """
        return name in self._data

    def __repr__(self) -> str:
        """String representation."""
        return f"DictRecord({self._data})"


@dataclass
class ArrayRecord(Record[List[Any]]):
    """Record implementation backed by an array (list).

    Used for high-performance scenarios where column order is fixed.
    """

    _values: List[Any] = field(default_factory=list)
    _column_names: List[str] = field(default_factory=list)
    _column_index: Dict[str, int] = field(default_factory=dict)
    _state: RecordState = RecordState(0)
    _original_values: Dict[int, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Build column index after initialization."""
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the column name to index mapping."""
        self._column_index = {
            name: i for i, name in enumerate(self._column_names)
        }

    def get(self, name: str, default: Any = None) -> Any:
        """Get a column value by name.

        Args:
            name: Column name
            default: Default value if not found

        Returns:
            Column value or default
        """
        idx = self._column_index.get(name)
        if idx is None:
            return default
        if idx >= len(self._values):
            return default
        return self._values[idx]

    def set(self, name: str, value: Any) -> None:
        """Set a column value.

        Args:
            name: Column name
            value: New value
        """
        idx = self._column_index.get(name)
        if idx is None:
            raise KeyError(f"Column '{name}' not found")

        if self._state & RecordState.EDITING:
            if idx not in self._original_values:
                self._original_values[idx] = self._values[idx] if idx < len(self._values) else None

        # Extend list if necessary
        while len(self._values) <= idx:
            self._values.append(None)

        self._values[idx] = value

        if not (self._state & RecordState.NEW):
            self._state |= RecordState.UPDATE

    def get_by_index(self, index: int) -> Any:
        """Get a column value by index.

        Args:
            index: Column index (0-based)

        Returns:
            Column value
        """
        if index >= len(self._values):
            return None
        return self._values[index]

    def set_by_index(self, index: int, value: Any) -> None:
        """Set a column value by index.

        Args:
            index: Column index (0-based)
            value: New value
        """
        while len(self._values) <= index:
            self._values.append(None)
        self._values[index] = value

    def get_value(self) -> List[Any]:
        """Get the underlying values list.

        Returns:
            Values list
        """
        return self._values

    def get_state(self) -> RecordState:
        """Get current state flags."""
        return self._state

    def is_modified(self) -> bool:
        """Check if record has been modified."""
        return bool(self._state & (RecordState.UPDATE | RecordState.DELETE))

    def is_new(self) -> bool:
        """Check if record is newly created."""
        return bool(self._state & RecordState.NEW)

    def is_deleted(self) -> bool:
        """Check if record is marked for deletion."""
        return bool(self._state & RecordState.DELETE)

    def begin_edit(self) -> None:
        """Begin editing the record."""
        self._state |= RecordState.EDITING

    def end_edit(self) -> None:
        """End editing the record."""
        self._state &= ~RecordState.EDITING
        self._original_values.clear()

    def cancel_edit(self) -> None:
        """Cancel edits and restore original values."""
        if self._state & RecordState.NEW:
            self._state |= RecordState.DELETE
        else:
            for idx, value in self._original_values.items():
                while len(self._values) <= idx:
                    self._values.append(None)
                self._values[idx] = value
            self._state &= ~RecordState.UPDATE

        self._state &= ~RecordState.EDITING
        self._original_values.clear()

    def delete(self) -> None:
        """Mark the record for deletion."""
        self._state |= RecordState.DELETE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            name: self._values[i] if i < len(self._values) else None
            for i, name in enumerate(self._column_names)
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        column_names: Optional[List[str]] = None,
    ) -> "ArrayRecord":
        """Create an ArrayRecord from a dictionary.

        Args:
            data: Source dictionary
            column_names: Ordered column names (None to use dict keys)

        Returns:
            ArrayRecord instance
        """
        if column_names is None:
            column_names = list(data.keys())

        values = [data.get(name) for name in column_names]
        return cls(
            _values=values,
            _column_names=column_names,
        )


__all__ = [
    "Record",
    "RecordState",
    "RecordMetadata",
    "DictRecord",
    "ArrayRecord",
]