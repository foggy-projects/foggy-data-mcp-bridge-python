"""RecordList implementation for foggy-dataset.

This module provides the RecordList class for managing collections
of Record objects with query and aggregation capabilities.
"""

from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar, Union
from dataclasses import dataclass, field

from foggy.dataset.resultset.record import Record, DictRecord, RecordState

T = TypeVar("T")


@dataclass
class RecordList(List[Record[T]], Generic[T]):
    """A list of Record objects with additional functionality.

    Extends Python list with methods for filtering, sorting,
    grouping, and aggregation operations.

    Example:
        >>> records = RecordList.from_dicts([{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}])
        >>> records.filter(lambda r: r['age'] > 25)
        [DictRecord({'name': 'Alice', 'age': 30})]
        >>> records.sum('age')
        55
    """

    _modified: bool = field(default=False, repr=False)

    def __init__(self, records: Optional[List[Record[T]]] = None):
        """Initialize with optional list of records.

        Args:
            records: Initial records
        """
        if records:
            super().__init__(records)
        else:
            super().__init__()
        self._modified = False

    @classmethod
    def from_dicts(
        cls,
        data: List[Dict[str, Any]],
        metadata: Optional[Any] = None,
    ) -> "RecordList[Dict[str, Any]]":
        """Create RecordList from list of dictionaries.

        Args:
            data: List of dictionaries
            metadata: Optional metadata for records

        Returns:
            RecordList instance
        """
        records = [DictRecord(d, metadata) for d in data]
        return cls(records)

    @classmethod
    def from_records(cls, records: List[Record[T]]) -> "RecordList[T]":
        """Create RecordList from list of Record objects.

        Args:
            records: List of Record objects

        Returns:
            RecordList instance
        """
        return cls(records)

    def commit(self) -> None:
        """Commit all pending changes to records.

        Clears the NEW and UPDATE states from all records.
        """
        for record in self:
            state = record.get_state()
            if state & RecordState.NEW:
                # New records become normal records
                record._state &= ~RecordState.NEW
            if state & RecordState.UPDATE:
                # Clear update flag
                record._state &= ~RecordState.UPDATE

        # Remove deleted records
        self[:] = [r for r in self if not (r.get_state() & RecordState.DELETE)]
        self._modified = False

    def delete(self) -> None:
        """Mark all records for deletion."""
        for record in self:
            record.delete()
        self._modified = True

    def delete_record(self, record: Record[T]) -> None:
        """Delete a specific record.

        Args:
            record: Record to delete
        """
        record.delete()
        self._modified = True

    def delete_at(self, index: int) -> None:
        """Delete record at index.

        Args:
            index: Index of record to delete
        """
        if 0 <= index < len(self):
            self[index].delete()
            self._modified = True

    def new_record(self, data: Optional[Dict[str, Any]] = None) -> DictRecord:
        """Create a new record with NEW state.

        Args:
            data: Initial data

        Returns:
            New DictRecord with NEW state
        """
        record = DictRecord(data or {})
        record._state = RecordState.NEW
        return record

    def add_record(self, record: Record[T]) -> None:
        """Add a record to the list.

        Args:
            record: Record to add
        """
        self.append(record)
        self._modified = True

    def add_new(self, data: Optional[Dict[str, Any]] = None) -> DictRecord:
        """Create and add a new record.

        Args:
            data: Initial data

        Returns:
            Created record
        """
        record = self.new_record(data)
        self.add_record(record)
        return record

    def filter(self, predicate: Callable[[Record[T]], bool]) -> "RecordList[T]":
        """Filter records by predicate.

        Args:
            predicate: Filter function

        Returns:
            New RecordList with matching records
        """
        return RecordList([r for r in self if predicate(r)])

    def find(self, predicate: Callable[[Record[T]], bool]) -> Optional[Record[T]]:
        """Find first record matching predicate.

        Args:
            predicate: Match function

        Returns:
            First matching record or None
        """
        for record in self:
            if predicate(record):
                return record
        return None

    def find_all(self, predicate: Callable[[Record[T]], bool]) -> "RecordList[T]":
        """Find all records matching predicate.

        Args:
            predicate: Match function

        Returns:
            RecordList with matching records
        """
        return self.filter(predicate)

    def sort_by(
        self,
        key: Union[str, Callable[[Record[T]], Any]],
        reverse: bool = False,
    ) -> "RecordList[T]":
        """Sort records by key.

        Args:
            key: Column name or key function
            reverse: Sort in descending order

        Returns:
            New sorted RecordList
        """
        if isinstance(key, str):
            key_func = lambda r: r.get(key, '')
        else:
            key_func = key

        return RecordList(sorted(self, key=key_func, reverse=reverse))

    def group_by(
        self,
        key: Union[str, Callable[[Record[T]], Any]],
    ) -> Dict[Any, "RecordList[T]"]:
        """Group records by key.

        Args:
            key: Column name or key function

        Returns:
            Dictionary mapping key to RecordList
        """
        if isinstance(key, str):
            key_func = lambda r: r.get(key)
        else:
            key_func = key

        groups: Dict[Any, List[Record[T]]] = {}
        for record in self:
            k = key_func(record)
            if k not in groups:
                groups[k] = []
            groups[k].append(record)

        return {k: RecordList(v) for k, v in groups.items()}

    def sum(self, column: str) -> float:
        """Sum values in a column.

        Args:
            column: Column name

        Returns:
            Sum of values
        """
        total = 0.0
        for record in self:
            value = record.get(column)
            if value is not None:
                try:
                    total += float(value)
                except (ValueError, TypeError):
                    pass
        return total

    def avg(self, column: str) -> float:
        """Calculate average of column values.

        Args:
            column: Column name

        Returns:
            Average value
        """
        if not self:
            return 0.0
        return self.sum(column) / len(self)

    def count(self, column: Optional[str] = None) -> int:
        """Count records or non-null values in column.

        Args:
            column: Optional column name for non-null count

        Returns:
            Count
        """
        if column is None:
            return len(self)

        count = 0
        for record in self:
            if record.get(column) is not None:
                count += 1
        return count

    def min(self, column: str) -> Any:
        """Get minimum value in column.

        Args:
            column: Column name

        Returns:
            Minimum value
        """
        values = [r.get(column) for r in self if r.get(column) is not None]
        return min(values) if values else None

    def max(self, column: str) -> Any:
        """Get maximum value in column.

        Args:
            column: Column name

        Returns:
            Maximum value
        """
        values = [r.get(column) for r in self if r.get(column) is not None]
        return max(values) if values else None

    def first(self) -> Optional[Record[T]]:
        """Get first record.

        Returns:
            First record or None
        """
        return self[0] if self else None

    def last(self) -> Optional[Record[T]]:
        """Get last record.

        Returns:
            Last record or None
        """
        return self[-1] if self else None

    def take(self, n: int) -> "RecordList[T]":
        """Take first n records.

        Args:
            n: Number of records

        Returns:
            New RecordList with first n records
        """
        return RecordList(self[:n])

    def skip(self, n: int) -> "RecordList[T]":
        """Skip first n records.

        Args:
            n: Number of records to skip

        Returns:
            New RecordList without first n records
        """
        return RecordList(self[n:])

    def each(self, func: Callable[[Record[T]], None]) -> None:
        """Execute function for each record.

        Args:
            func: Function to execute
        """
        for record in self:
            func(record)

    def map(self, func: Callable[[Record[T]], Any]) -> List[Any]:
        """Map records to values.

        Args:
            func: Transform function

        Returns:
            List of transformed values
        """
        return [func(r) for r in self]

    def get_values(self) -> List[T]:
        """Get underlying values from all records.

        Returns:
            List of values
        """
        return [r.get_value() for r in self]

    def to_dicts(self) -> List[Dict[str, Any]]:
        """Convert all records to dictionaries.

        Returns:
            List of dictionaries
        """
        return [r.to_dict() for r in self]

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string
        """
        import json
        return json.dumps(self.to_dicts(), ensure_ascii=False, default=str)

    def pluck(self, column: str) -> List[Any]:
        """Extract values from a single column.

        Args:
            column: Column name

        Returns:
            List of values
        """
        return [r.get(column) for r in self]

    def unique(self, column: str) -> List[Any]:
        """Get unique values from a column.

        Args:
            column: Column name

        Returns:
            List of unique values
        """
        seen = set()
        result = []
        for record in self:
            value = record.get(column)
            if value is not None and value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def is_modified(self) -> bool:
        """Check if any record has been modified.

        Returns:
            True if modified
        """
        if self._modified:
            return True
        for record in self:
            if record.is_modified():
                return True
        return False

    def get_modified_records(self) -> "RecordList[T]":
        """Get all modified records.

        Returns:
            RecordList of modified records
        """
        return RecordList([r for r in self if r.is_modified()])

    def get_new_records(self) -> "RecordList[T]":
        """Get all new records.

        Returns:
            RecordList of new records
        """
        return RecordList([r for r in self if r.is_new()])

    def get_deleted_records(self) -> "RecordList[T]":
        """Get all deleted records.

        Returns:
            RecordList of deleted records
        """
        return RecordList([r for r in self if r.is_deleted()])

    def __repr__(self) -> str:
        """String representation."""
        return f"RecordList({len(self)} records)"


__all__ = ["RecordList"]