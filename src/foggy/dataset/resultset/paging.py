"""Paging support for foggy-dataset.

This module provides classes for handling paginated query results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar

from foggy.dataset.resultset.record import Record
from foggy.dataset.resultset.record_list import RecordList

T = TypeVar("T")


@dataclass
class PagingRequest:
    """Request for paginated data.

    Attributes:
        page: Page number (1-based)
        page_size: Number of records per page
        sort_by: Column to sort by
        sort_desc: Sort in descending order
        filters: Filter conditions
    """

    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = None
    sort_desc: bool = False
    filters: Dict[str, Any] = field(default_factory=dict)

    @property
    def offset(self) -> int:
        """Calculate the offset for SQL LIMIT clause.

        Returns:
            Offset value
        """
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get the limit for SQL LIMIT clause.

        Returns:
            Limit value (page_size)
        """
        return self.page_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "page": self.page,
            "pageSize": self.page_size,
            "sortBy": self.sort_by,
            "sortDesc": self.sort_desc,
            "filters": self.filters,
        }


@dataclass
class PagingResult(Generic[T]):
    """Paginated query result.

    Attributes:
        records: List of records for current page
        total: Total number of records
        page: Current page number
        page_size: Number of records per page
        total_pages: Total number of pages
    """

    records: RecordList[T] = field(default_factory=RecordList)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages.

        Returns:
            Total pages
        """
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_more(self) -> bool:
        """Check if there are more pages.

        Returns:
            True if more pages exist
        """
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Check if there is a previous page.

        Returns:
            True if page > 1
        """
        return self.page > 1

    @property
    def is_empty(self) -> bool:
        """Check if result is empty.

        Returns:
            True if no records
        """
        return len(self.records) == 0

    @property
    def start_index(self) -> int:
        """Get the start index of current page (1-based).

        Returns:
            Start index
        """
        return (self.page - 1) * self.page_size + 1

    @property
    def end_index(self) -> int:
        """Get the end index of current page (1-based).

        Returns:
            End index
        """
        return min(self.start_index + len(self.records) - 1, self.total)

    @classmethod
    def empty(cls, page_size: int = 20) -> "PagingResult[T]":
        """Create an empty paging result.

        Args:
            page_size: Page size

        Returns:
            Empty PagingResult
        """
        return cls(records=RecordList(), total=0, page=1, page_size=page_size)

    @classmethod
    def from_records(
        cls,
        records: RecordList[T],
        total: int,
        request: PagingRequest,
    ) -> "PagingResult[T]":
        """Create PagingResult from records and request.

        Args:
            records: Record list
            total: Total count
            request: Paging request

        Returns:
            PagingResult instance
        """
        return cls(
            records=records,
            total=total,
            page=request.page,
            page_size=request.page_size,
        )

    @classmethod
    def from_dicts(
        cls,
        data: List[Dict[str, Any]],
        total: int,
        page: int = 1,
        page_size: int = 20,
    ) -> "PagingResult[Dict[str, Any]]":
        """Create PagingResult from list of dictionaries.

        Args:
            data: List of dictionaries
            total: Total count
            page: Current page
            page_size: Page size

        Returns:
            PagingResult instance
        """
        return cls(
            records=RecordList.from_dicts(data),
            total=total,
            page=page,
            page_size=page_size,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "records": self.records.to_dicts(),
            "total": self.total,
            "page": self.page,
            "pageSize": self.page_size,
            "totalPages": self.total_pages,
            "hasMore": self.has_more,
            "hasPrevious": self.has_previous,
            "isEmpty": self.is_empty,
            "startIndex": self.start_index,
            "endIndex": self.end_index,
        }

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string
        """
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def __repr__(self) -> str:
        """String representation."""
        return f"PagingResult(page={self.page}/{self.total_pages}, records={len(self.records)}, total={self.total})"


@dataclass
class PagingObject:
    """Helper object for building paginated queries.

    Provides utility methods for calculating offsets and limits
    for different database dialects.
    """

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """Get the offset for LIMIT clause.

        Returns:
            Offset value
        """
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get the limit for LIMIT clause.

        Returns:
            Limit value
        """
        return self.page_size

    def get_mysql_limit(self) -> str:
        """Get MySQL LIMIT clause.

        Returns:
            LIMIT clause string
        """
        return f"LIMIT {self.offset}, {self.limit}"

    def get_postgres_limit(self) -> str:
        """Get PostgreSQL LIMIT clause.

        Returns:
            LIMIT clause string
        """
        return f"LIMIT {self.limit} OFFSET {self.offset}"

    def get_sqlite_limit(self) -> str:
        """Get SQLite LIMIT clause.

        Returns:
            LIMIT clause string
        """
        return f"LIMIT {self.limit} OFFSET {self.offset}"

    def get_sqlserver_offset(self) -> str:
        """Get SQL Server OFFSET clause.

        Returns:
            OFFSET clause string
        """
        return f"OFFSET {self.offset} ROWS FETCH NEXT {self.limit} ROWS ONLY"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "page": self.page,
            "pageSize": self.page_size,
            "offset": self.offset,
            "limit": self.limit,
        }


__all__ = [
    "PagingRequest",
    "PagingResult",
    "PagingObject",
]