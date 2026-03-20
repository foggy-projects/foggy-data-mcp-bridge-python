"""SQL Table and Column definitions for foggy-dataset.

This module provides classes for defining database table structures
including columns, primary keys, and indexes.
"""

from foggy.dataset.table.sql_column import (
    SqlColumn,
    SqlColumnType,
    JdbcType,
    TYPE_NAME_TO_JDBC,
    get_jdbc_type_from_name,
    DEFAULT_PRECISION,
    DEFAULT_SCALE,
)
from foggy.dataset.table.sql_table import (
    SqlTable,
    QuerySqlTable,
    EditSqlTable,
)

__all__ = [
    # Column
    "SqlColumn",
    "SqlColumnType",
    "JdbcType",
    "TYPE_NAME_TO_JDBC",
    "get_jdbc_type_from_name",
    "DEFAULT_PRECISION",
    "DEFAULT_SCALE",
    # Table
    "SqlTable",
    "QuerySqlTable",
    "EditSqlTable",
]