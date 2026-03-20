"""SQL INSERT builder for foggy-dataset.

This module provides a fluent API for building INSERT SQL statements.
"""

from typing import Any, Dict, List, Optional, Union

from foggy.dataset.dialects.base import FDialect
from foggy.dataset.table.sql_column import SqlColumn
from foggy.dataset.table.sql_table import SqlTable


class InsertBuilder:
    """Fluent INSERT SQL builder.

    Provides a chainable API for building INSERT statements
    with support for multiple rows and ON DUPLICATE KEY.

    Example:
        >>> builder = InsertBuilder('users')
        >>> builder.columns('name', 'email').values('Alice', 'alice@example.com')
        >>> builder.build(mysql_dialect)
        'INSERT INTO users (name, email) VALUES (?, ?)'
    """

    def __init__(self, table: Union[str, SqlTable]):
        """Initialize the builder.

        Args:
            table: Table name or SqlTable object
        """
        if isinstance(table, SqlTable):
            self._table_name = table.name
            self._table = table
        else:
            self._table_name = table
            self._table = None

        self._columns: List[str] = []
        self._values: List[List[Any]] = []
        self._on_duplicate_key: Optional["OnDuplicateKeyBuilder"] = None

    def columns(self, *columns: str) -> "InsertBuilder":
        """Set the column names.

        Args:
            *columns: Column names

        Returns:
            self for chaining
        """
        self._columns = list(columns)
        return self

    def values(self, *values: Any) -> "InsertBuilder":
        """Add a row of values.

        Args:
            *values: Values for one row

        Returns:
            self for chaining
        """
        self._values.append(list(values))
        return self

    def values_dict(self, data: Dict[str, Any]) -> "InsertBuilder":
        """Add values from a dictionary.

        Sets columns from dict keys and values from dict values.

        Args:
            data: Dictionary of column -> value

        Returns:
            self for chaining
        """
        if not self._columns:
            self._columns = list(data.keys())
        self._values.append([data.get(col) for col in self._columns])
        return self

    def values_list(self, rows: List[Dict[str, Any]]) -> "InsertBuilder":
        """Add multiple rows from list of dictionaries.

        Args:
            rows: List of dictionaries

        Returns:
            self for chaining
        """
        for row in rows:
            self.values_dict(row)
        return self

    def on_duplicate_key_update(self, *columns: str) -> "InsertBuilder":
        """Add ON DUPLICATE KEY UPDATE clause (MySQL).

        Args:
            *columns: Columns to update on duplicate

        Returns:
            self for chaining
        """
        self._on_duplicate_key = OnDuplicateKeyBuilder(columns)
        return self

    def on_duplicate_key_ignore(self) -> "InsertBuilder":
        """Add ON DUPLICATE KEY IGNORE (do nothing on duplicate).

        Returns:
            self for chaining
        """
        self._on_duplicate_key = OnDuplicateKeyBuilder()
        return self

    def build(self, dialect: FDialect) -> str:
        """Build the INSERT SQL statement.

        Args:
            dialect: Database dialect

        Returns:
            INSERT SQL string
        """
        if not self._columns:
            raise ValueError("No columns specified for INSERT")

        if not self._values:
            raise ValueError("No values specified for INSERT")

        # Quote table name
        table_name = dialect.quote(self._table_name) if dialect.needs_quote(self._table_name) else self._table_name

        # Quote column names
        quoted_columns = [
            dialect.quote(col) if dialect.needs_quote(col) else col
            for col in self._columns
        ]

        # Build VALUES clause
        if len(self._values) == 1:
            # Single row
            placeholders = ", ".join(
                dialect.get_placeholder(i) for i in range(len(self._columns))
            )
            values_clause = f"VALUES ({placeholders})"
        else:
            # Multiple rows
            row_placeholders = ", ".join(
                dialect.get_placeholder(i) for i in range(len(self._columns))
            )
            values_rows = [f"({row_placeholders})" for _ in self._values]
            values_clause = f"VALUES {', '.join(values_rows)}"

        # Build INSERT statement
        columns_str = ", ".join(quoted_columns)
        sql = f"INSERT INTO {table_name} ({columns_str}) {values_clause}"

        # Add ON DUPLICATE KEY clause
        if self._on_duplicate_key:
            sql += " " + self._on_duplicate_key.build(dialect, self._columns)

        return sql

    def get_params(self) -> List[Any]:
        """Get parameter values for the prepared statement.

        Returns:
            Flat list of parameter values
        """
        params = []
        for row in self._values:
            params.extend(row)
        return params

    def reset(self) -> "InsertBuilder":
        """Reset the builder for reuse.

        Returns:
            self for chaining
        """
        self._columns = []
        self._values = []
        self._on_duplicate_key = None
        return self


class OnDuplicateKeyBuilder:
    """Builder for ON DUPLICATE KEY UPDATE clause.

    Attributes:
        _update_columns: Columns to update on duplicate key conflict
        _ignore: Whether to ignore duplicates (do nothing)
    """

    def __init__(self, update_columns: Optional[tuple] = None):
        """Initialize the builder.

        Args:
            update_columns: Columns to update (None for IGNORE)
        """
        self._update_columns = list(update_columns) if update_columns else []
        self._ignore = len(self._update_columns) == 0

    def build(self, dialect: FDialect, all_columns: List[str]) -> str:
        """Build the ON DUPLICATE KEY clause.

        Args:
            dialect: Database dialect
            all_columns: All INSERT columns

        Returns:
            ON DUPLICATE KEY clause string
        """
        if self._ignore:
            return dialect.get_on_duplicate_key_ignore_sql()

        # Build ON DUPLICATE KEY UPDATE clause
        update_parts = []
        for i, col in enumerate(self._update_columns):
            quoted_col = dialect.quote(col) if dialect.needs_quote(col) else col
            placeholder = dialect.get_placeholder(len(all_columns) + i)
            update_parts.append(f"{quoted_col} = {placeholder}")

        if dialect.name.lower() == "mysql":
            return f"ON DUPLICATE KEY UPDATE {', '.join(update_parts)}"
        elif dialect.name.lower() == "postgres":
            # PostgreSQL uses ON CONFLICT
            conflict_cols = ", ".join(update_parts)
            return f"ON CONFLICT DO UPDATE SET {conflict_cols}"
        else:
            return f"ON DUPLICATE KEY UPDATE {', '.join(update_parts)}"


class BatchInsertBuilder:
    """Builder for batch INSERT statements.

    Optimized for inserting many rows efficiently.
    """

    def __init__(self, table: Union[str, SqlTable], batch_size: int = 1000):
        """Initialize the builder.

        Args:
            table: Table name or SqlTable
            batch_size: Maximum rows per INSERT statement
        """
        self._builder = InsertBuilder(table)
        self._batch_size = batch_size
        self._batches: List[tuple] = []  # (sql, params) tuples

    def add_row(self, data: Dict[str, Any]) -> "BatchInsertBuilder":
        """Add a row to the batch.

        Args:
            data: Row data dictionary

        Returns:
            self for chaining
        """
        self._builder.values_dict(data)
        return self

    def add_rows(self, rows: List[Dict[str, Any]]) -> "BatchInsertBuilder":
        """Add multiple rows to the batch.

        Args:
            rows: List of row data dictionaries

        Returns:
            self for chaining
        """
        for row in rows:
            self.add_row(row)
        return self

    def build_batches(self, dialect: FDialect) -> List[tuple]:
        """Build all batch INSERT statements.

        Args:
            dialect: Database dialect

        Returns:
            List of (sql, params) tuples
        """
        batches = []
        current_batch_values = []

        for row_values in self._builder._values:
            current_batch_values.append(row_values)

            if len(current_batch_values) >= self._batch_size:
                sql, params = self._build_single_batch(dialect, current_batch_values)
                batches.append((sql, params))
                current_batch_values = []

        # Final batch
        if current_batch_values:
            sql, params = self._build_single_batch(dialect, current_batch_values)
            batches.append((sql, params))

        return batches

    def _build_single_batch(
        self,
        dialect: FDialect,
        values: List[List[Any]],
    ) -> tuple:
        """Build a single batch INSERT.

        Args:
            dialect: Database dialect
            values: List of row values

        Returns:
            (sql, params) tuple
        """
        # Create temporary builder for this batch
        temp_builder = InsertBuilder(self._builder._table_name)
        temp_builder._columns = self._builder._columns
        temp_builder._values = values

        sql = temp_builder.build(dialect)
        params = temp_builder.get_params()

        return sql, params

    def reset(self) -> "BatchInsertBuilder":
        """Reset the builder.

        Returns:
            self for chaining
        """
        self._builder.reset()
        self._batches = []
        return self


__all__ = [
    "InsertBuilder",
    "OnDuplicateKeyBuilder",
    "BatchInsertBuilder",
]