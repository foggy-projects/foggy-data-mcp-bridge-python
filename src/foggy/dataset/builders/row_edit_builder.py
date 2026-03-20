"""SQL UPDATE/DELETE builder for foggy-dataset.

This module provides a fluent API for building UPDATE and DELETE SQL statements.
"""

from typing import Any, Dict, List, Optional, Union

from foggy.dataset.dialects.base import FDialect
from foggy.dataset.table.sql_table import SqlTable


class UpdateBuilder:
    """Fluent UPDATE SQL builder.

    Provides a chainable API for building UPDATE statements
    with support for WHERE clauses.

    Example:
        >>> builder = UpdateBuilder('users')
        >>> builder.set('name', 'Alice').set('age', 30).where('id = ?', [1])
        >>> builder.build(mysql_dialect)
        'UPDATE users SET name = ?, age = ? WHERE id = ?'
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

        self._set_values: Dict[str, Any] = {}
        self._where_conditions: List[str] = []
        self._where_params: List[Any] = []

    def set(self, column: str, value: Any) -> "UpdateBuilder":
        """Set a column value.

        Args:
            column: Column name
            value: New value

        Returns:
            self for chaining
        """
        self._set_values[column] = value
        return self

    def set_dict(self, values: Dict[str, Any]) -> "UpdateBuilder":
        """Set multiple column values from dictionary.

        Args:
            values: Dictionary of column -> value

        Returns:
            self for chaining
        """
        self._set_values.update(values)
        return self

    def where(self, condition: str, params: Optional[List[Any]] = None) -> "UpdateBuilder":
        """Add a WHERE condition.

        Args:
            condition: SQL condition (e.g., 'id = ?')
            params: Parameter values

        Returns:
            self for chaining
        """
        self._where_conditions.append(condition)
        if params:
            self._where_params.extend(params)
        return self

    def where_eq(self, column: str, value: Any) -> "UpdateBuilder":
        """Add a WHERE column = value condition.

        Args:
            column: Column name
            value: Value to compare

        Returns:
            self for chaining
        """
        self._where_conditions.append(f"{column} = ?")
        self._where_params.append(value)
        return self

    def where_in(self, column: str, values: List[Any]) -> "UpdateBuilder":
        """Add a WHERE column IN (values) condition.

        Args:
            column: Column name
            values: List of values

        Returns:
            self for chaining
        """
        placeholders = ", ".join("?" * len(values))
        self._where_conditions.append(f"{column} IN ({placeholders})")
        self._where_params.extend(values)
        return self

    def where_is_null(self, column: str) -> "UpdateBuilder":
        """Add a WHERE column IS NULL condition.

        Args:
            column: Column name

        Returns:
            self for chaining
        """
        self._where_conditions.append(f"{column} IS NULL")
        return self

    def where_is_not_null(self, column: str) -> "UpdateBuilder":
        """Add a WHERE column IS NOT NULL condition.

        Args:
            column: Column name

        Returns:
            self for chaining
        """
        self._where_conditions.append(f"{column} IS NOT NULL")
        return self

    def build(self, dialect: FDialect) -> str:
        """Build the UPDATE SQL statement.

        Args:
            dialect: Database dialect

        Returns:
            UPDATE SQL string
        """
        if not self._set_values:
            raise ValueError("No SET values specified for UPDATE")

        # Quote table name
        table_name = dialect.quote(self._table_name) if dialect.needs_quote(self._table_name) else self._table_name

        # Build SET clause
        set_parts = []
        for col, val in self._set_values.items():
            quoted_col = dialect.quote(col) if dialect.needs_quote(col) else col
            set_parts.append(f"{quoted_col} = ?")

        set_clause = ", ".join(set_parts)

        # Build WHERE clause
        sql = f"UPDATE {table_name} SET {set_clause}"
        if self._where_conditions:
            where_clause = " AND ".join(self._where_conditions)
            sql += f" WHERE {where_clause}"

        return sql

    def get_params(self) -> List[Any]:
        """Get parameter values for the prepared statement.

        Returns:
            List of parameter values (SET values first, then WHERE values)
        """
        params = list(self._set_values.values())
        params.extend(self._where_params)
        return params

    def reset(self) -> "UpdateBuilder":
        """Reset the builder for reuse.

        Returns:
            self for chaining
        """
        self._set_values = {}
        self._where_conditions = []
        self._where_params = []
        return self


class DeleteBuilder:
    """Fluent DELETE SQL builder.

    Provides a chainable API for building DELETE statements
    with support for WHERE clauses.

    Example:
        >>> builder = DeleteBuilder('users')
        >>> builder.where('id = ?', [1])
        >>> builder.build(mysql_dialect)
        'DELETE FROM users WHERE id = ?'
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

        self._where_conditions: List[str] = []
        self._where_params: List[Any] = []
        self._limit: Optional[int] = None

    def where(self, condition: str, params: Optional[List[Any]] = None) -> "DeleteBuilder":
        """Add a WHERE condition.

        Args:
            condition: SQL condition
            params: Parameter values

        Returns:
            self for chaining
        """
        self._where_conditions.append(condition)
        if params:
            self._where_params.extend(params)
        return self

    def where_eq(self, column: str, value: Any) -> "DeleteBuilder":
        """Add a WHERE column = value condition.

        Args:
            column: Column name
            value: Value to compare

        Returns:
            self for chaining
        """
        self._where_conditions.append(f"{column} = ?")
        self._where_params.append(value)
        return self

    def where_in(self, column: str, values: List[Any]) -> "DeleteBuilder":
        """Add a WHERE column IN (values) condition.

        Args:
            column: Column name
            values: List of values

        Returns:
            self for chaining
        """
        placeholders = ", ".join("?" * len(values))
        self._where_conditions.append(f"{column} IN ({placeholders})")
        self._where_params.extend(values)
        return self

    def limit(self, count: int) -> "DeleteBuilder":
        """Set LIMIT for DELETE (supported by some databases).

        Args:
            count: Maximum rows to delete

        Returns:
            self for chaining
        """
        self._limit = count
        return self

    def build(self, dialect: FDialect) -> str:
        """Build the DELETE SQL statement.

        Args:
            dialect: Database dialect

        Returns:
            DELETE SQL string
        """
        # Quote table name
        table_name = dialect.quote(self._table_name) if dialect.needs_quote(self._table_name) else self._table_name

        # Build DELETE statement
        sql = f"DELETE FROM {table_name}"

        if self._where_conditions:
            where_clause = " AND ".join(self._where_conditions)
            sql += f" WHERE {where_clause}"

        if self._limit is not None:
            sql += f" LIMIT {self._limit}"

        return sql

    def get_params(self) -> List[Any]:
        """Get parameter values for the prepared statement.

        Returns:
            List of parameter values
        """
        return self._where_params.copy()

    def reset(self) -> "DeleteBuilder":
        """Reset the builder for reuse.

        Returns:
            self for chaining
        """
        self._where_conditions = []
        self._where_params = []
        self._limit = None
        return self


class RowEditBuilder:
    """Builder for row-level edit operations (INSERT/UPDATE/DELETE).

    Combines InsertBuilder, UpdateBuilder, and DeleteBuilder for
    convenient row editing operations.
    """

    def __init__(self, table: Union[str, SqlTable]):
        """Initialize the builder.

        Args:
            table: Table name or SqlTable object
        """
        self._table_name = table.name if isinstance(table, SqlTable) else table
        self._table = table if isinstance(table, SqlTable) else None

        self._insert_builder: Optional[Any] = None
        self._update_builder: Optional[UpdateBuilder] = None
        self._delete_builder: Optional[DeleteBuilder] = None

    def for_insert(self, data: Dict[str, Any]) -> "RowEditBuilder":
        """Set up for INSERT operation.

        Args:
            data: Data to insert

        Returns:
            self for chaining
        """
        from foggy.dataset.builders.insert_builder import InsertBuilder
        self._insert_builder = InsertBuilder(self._table_name).values_dict(data)
        return self

    def for_update(
        self,
        data: Dict[str, Any],
        key_columns: List[str],
        key_values: List[Any],
    ) -> "RowEditBuilder":
        """Set up for UPDATE operation.

        Args:
            data: Data to update
            key_columns: Key column names (for WHERE)
            key_values: Key values (for WHERE)

        Returns:
            self for chaining
        """
        self._update_builder = UpdateBuilder(self._table_name).set_dict(data)
        for col, val in zip(key_columns, key_values):
            self._update_builder.where_eq(col, val)
        return self

    def for_delete(
        self,
        key_columns: List[str],
        key_values: List[Any],
    ) -> "RowEditBuilder":
        """Set up for DELETE operation.

        Args:
            key_columns: Key column names (for WHERE)
            key_values: Key values (for WHERE)

        Returns:
            self for chaining
        """
        self._delete_builder = DeleteBuilder(self._table_name)
        for col, val in zip(key_columns, key_values):
            self._delete_builder.where_eq(col, val)
        return self

    def build(self, dialect: FDialect) -> str:
        """Build the SQL statement.

        Args:
            dialect: Database dialect

        Returns:
            SQL string

        Raises:
            ValueError: If no operation is set
        """
        if self._insert_builder:
            return self._insert_builder.build(dialect)
        elif self._update_builder:
            return self._update_builder.build(dialect)
        elif self._delete_builder:
            return self._delete_builder.build(dialect)
        else:
            raise ValueError("No edit operation set")

    def get_params(self) -> List[Any]:
        """Get parameter values.

        Returns:
            List of parameter values
        """
        if self._insert_builder:
            return self._insert_builder.get_params()
        elif self._update_builder:
            return self._update_builder.get_params()
        elif self._delete_builder:
            return self._delete_builder.get_params()
        return []

    def get_operation(self) -> str:
        """Get the operation type.

        Returns:
            'INSERT', 'UPDATE', 'DELETE', or 'NONE'
        """
        if self._insert_builder:
            return "INSERT"
        elif self._update_builder:
            return "UPDATE"
        elif self._delete_builder:
            return "DELETE"
        return "NONE"


__all__ = [
    "UpdateBuilder",
    "DeleteBuilder",
    "RowEditBuilder",
]