"""Dataset module for Foggy Framework.

This module provides database abstraction, SQL generation, and result set handling
for the Foggy data platform.

Key components:
- SqlTable/SqlColumn: Table and column definitions
- Record/RecordList: Result row representation
- InsertBuilder/UpdateBuilder/DeleteBuilder: SQL statement builders
- Dialects: Database-specific SQL syntax (MySQL, PostgreSQL, etc.)
"""

# Database types
from foggy.dataset.db import DbType, TypeNames
from foggy.dataset.db.sql_object import SqlObject, DbObjectType

# Dialects
from foggy.dataset.dialects import (
    FDialect,
    MySqlDialect,
    PostgresDialect,
    SqliteDialect,
    SqlServerDialect,
)

# Table and Column
from foggy.dataset.table import (
    SqlTable,
    QuerySqlTable,
    EditSqlTable,
    SqlColumn,
    SqlColumnType,
    JdbcType,
    get_jdbc_type_from_name,
)

# ResultSet
from foggy.dataset.resultset import (
    Record,
    RecordState,
    RecordMetadata,
    DictRecord,
    ArrayRecord,
    RecordList,
    PagingRequest,
    PagingResult,
    PagingObject,
)

# Builders
from foggy.dataset.builders import (
    InsertBuilder,
    OnDuplicateKeyBuilder,
    BatchInsertBuilder,
    UpdateBuilder,
    DeleteBuilder,
    RowEditBuilder,
)

__all__ = [
    # Database types
    "DbType",
    "TypeNames",
    "SqlObject",
    "DbObjectType",
    # Dialects
    "FDialect",
    "MySqlDialect",
    "PostgresDialect",
    "SqliteDialect",
    "SqlServerDialect",
    # Table and Column
    "SqlTable",
    "QuerySqlTable",
    "EditSqlTable",
    "SqlColumn",
    "SqlColumnType",
    "JdbcType",
    "get_jdbc_type_from_name",
    # ResultSet
    "Record",
    "RecordState",
    "RecordMetadata",
    "DictRecord",
    "ArrayRecord",
    "RecordList",
    "PagingRequest",
    "PagingResult",
    "PagingObject",
    # Builders
    "InsertBuilder",
    "OnDuplicateKeyBuilder",
    "BatchInsertBuilder",
    "UpdateBuilder",
    "DeleteBuilder",
    "RowEditBuilder",
]