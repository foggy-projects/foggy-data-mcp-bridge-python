"""ResultSet module for foggy-dataset.

This module provides classes for handling database result sets
including Record, RecordList, and paging support.
"""

from foggy.dataset.resultset.record import (
    Record,
    RecordState,
    RecordMetadata,
    DictRecord,
    ArrayRecord,
)
from foggy.dataset.resultset.record_list import RecordList
from foggy.dataset.resultset.paging import (
    PagingRequest,
    PagingResult,
    PagingObject,
)

__all__ = [
    # Record
    "Record",
    "RecordState",
    "RecordMetadata",
    "DictRecord",
    "ArrayRecord",
    # RecordList
    "RecordList",
    # Paging
    "PagingRequest",
    "PagingResult",
    "PagingObject",
]