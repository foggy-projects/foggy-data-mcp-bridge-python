"""SQL Table definition for foggy-dataset.

This module provides the SqlTable class for defining database table
structure including columns, primary keys, and indexes.
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

from foggy.dataset.db.sql_object import DbObjectType, SqlObject
from foggy.dataset.dialects.base import FDialect
from foggy.dataset.table.sql_column import SqlColumn


class SqlTable(SqlObject):
    """SQL Table definition.

    Represents a database table with its columns, primary keys,
    indexes, and other properties.

    Attributes:
        columns: List of column definitions
        id_column: Primary key column
        schema_name: Schema name (optional)
        indexes: List of index definitions
        foreign_keys: List of foreign key definitions
    """

    columns: List[SqlColumn] = Field(default_factory=list, description="Table columns")
    id_column: Optional[SqlColumn] = Field(default=None, description="Primary key column")
    schema_name: Optional[str] = Field(default=None, description="Schema name")
    indexes: List[Dict[str, Any]] = Field(default_factory=list, description="Index definitions")
    foreign_keys: List[Dict[str, Any]] = Field(default_factory=list, description="Foreign key definitions")

    # Internal column name mapping
    _column_map: Dict[str, SqlColumn] = {}

    def __init__(self, **data):
        super().__init__(**data)
        self._rebuild_column_map()

    def _rebuild_column_map(self) -> None:
        """Rebuild the column name to column mapping."""
        self._column_map = {}
        for col in self.columns:
            self._column_map[col.name.upper()] = col

    def get_db_object_type(self) -> DbObjectType:
        """Get the database object type."""
        return DbObjectType.TABLE

    def add_column(self, column: SqlColumn) -> "SqlTable":
        """Add a column to the table.

        Args:
            column: Column to add

        Returns:
            self for fluent API

        Raises:
            ValueError: If column name is empty or duplicate
        """
        if not column.name:
            raise ValueError(f"Column name cannot be empty")

        upper_name = column.name.upper()
        if upper_name in self._column_map:
            raise ValueError(f"Duplicate column name: {column.name}")

        self.columns.append(column)
        self._column_map[upper_name] = column
        return self

    def remove_column(self, name: str) -> Optional[SqlColumn]:
        """Remove a column by name.

        Args:
            name: Column name

        Returns:
            Removed column or None if not found
        """
        upper_name = name.upper()
        col = self._column_map.pop(upper_name, None)
        if col:
            self.columns.remove(col)
            if self.id_column and self.id_column.name.upper() == upper_name:
                self.id_column = None
        return col

    def get_column(self, name: str, error_if_not_found: bool = False) -> Optional[SqlColumn]:
        """Get a column by name.

        Args:
            name: Column name (case-insensitive)
            error_if_not_found: Raise error if not found

        Returns:
            SqlColumn or None

        Raises:
            KeyError: If not found and error_if_not_found is True
        """
        col = self._column_map.get(name.upper())
        if col is None and error_if_not_found:
            raise KeyError(f"Column '{name}' not found in table '{self.name}'")
        return col

    def get_column_safe(self, name: str) -> Optional[SqlColumn]:
        """Safely get a column by name (never raises).

        Args:
            name: Column name

        Returns:
            SqlColumn or None
        """
        return self._column_map.get(name.upper())

    def set_columns(self, columns: List[SqlColumn]) -> "SqlTable":
        """Set all columns.

        Args:
            columns: List of columns

        Returns:
            self for fluent API
        """
        self.columns = columns
        self._rebuild_column_map()
        return self

    def set_id_column(self, column: SqlColumn) -> "SqlTable":
        """Set the primary key column.

        Args:
            column: Column to set as primary key

        Returns:
            self for fluent API
        """
        self.id_column = column
        column.primary_key = True
        return self

    def set_id_column_by_name(self, name: str) -> "SqlTable":
        """Set the primary key column by name.

        Args:
            name: Column name

        Returns:
            self for fluent API
        """
        col = self.get_column(name, error_if_not_found=True)
        return self.set_id_column(col)

    def is_id_column(self, column: SqlColumn) -> bool:
        """Check if a column is the primary key.

        Args:
            column: Column to check

        Returns:
            True if column is the primary key
        """
        if self.id_column is None:
            return False
        return self.id_column.name.upper() == column.name.upper()

    def create_column(
        self,
        name: str,
        type_name: str,
        length: int = 0,
        caption: Optional[str] = None,
        nullable: bool = True,
    ) -> SqlColumn:
        """Create and add a new column.

        Args:
            name: Column name
            type_name: SQL type name
            length: Column length
            caption: Column caption
            nullable: Allow NULL

        Returns:
            Created column
        """
        col = SqlColumn.create(
            name=name,
            type_name=type_name,
            length=length,
            caption=caption,
            nullable=nullable,
        )
        self.add_column(col)
        return col

    def get_create_sql(self, dialect: FDialect, if_not_exists: bool = False) -> str:
        """Generate CREATE TABLE SQL.

        Args:
            dialect: Database dialect
            if_not_exists: Add IF NOT EXISTS clause

        Returns:
            CREATE TABLE SQL statement
        """
        if not self.columns:
            raise ValueError(f"Table '{self.name}' has no columns")

        lines = []
        table_name = self.get_quoted_name(dialect)

        # IF NOT EXISTS clause
        if_not_exists_str = "IF NOT EXISTS " if if_not_exists else ""

        # Column definitions
        for col in self.columns:
            col_sql = self._column_to_sql(col, dialect)
            lines.append(f"    {col_sql}")

        # Primary key constraint
        if self.id_column:
            pk_name = self.id_column.get_quoted_name(dialect)
            lines.append(f"    PRIMARY KEY ({pk_name})")

        columns_sql = ",\n".join(lines)
        return f"CREATE TABLE {if_not_exists_str}{table_name} (\n{columns_sql}\n)"

    def _column_to_sql(self, column: SqlColumn, dialect: FDialect) -> str:
        """Convert a column to SQL definition.

        Args:
            column: Column to convert
            dialect: Database dialect

        Returns:
            Column SQL definition
        """
        parts = [column.get_quoted_name(dialect)]

        # Type
        type_sql = column.get_sql_type(dialect)
        parts.append(type_sql)

        # NULL constraint
        if not column.nullable:
            parts.append("NOT NULL")

        # DEFAULT
        if column.default_value is not None:
            parts.append(f"DEFAULT {column.default_value}")

        # AUTO INCREMENT
        if column.auto_increment:
            parts.append(dialect.get_auto_increment_sql())

        return " ".join(parts)

    def get_drop_sql(self, dialect: FDialect, if_exists: bool = False) -> str:
        """Generate DROP TABLE SQL.

        Args:
            dialect: Database dialect
            if_exists: Add IF EXISTS clause

        Returns:
            DROP TABLE SQL statement
        """
        table_name = self.get_quoted_name(dialect)
        if_exists_str = "IF EXISTS " if if_exists else ""
        return f"DROP TABLE {if_exists_str}{table_name}"

    def get_select_sql(self, columns: Optional[List[str]] = None) -> str:
        """Generate SELECT SQL.

        Args:
            columns: Specific columns to select (None for all)

        Returns:
            SELECT SQL statement
        """
        if columns:
            col_names = ", ".join(columns)
        else:
            col_names = "*"
        return f"SELECT {col_names} FROM {self.name}"

    def get_insert_sql(self, dialect: FDialect, columns: Optional[List[str]] = None) -> str:
        """Generate INSERT SQL.

        Args:
            dialect: Database dialect
            columns: Specific columns (None for all non-auto-increment)

        Returns:
            INSERT SQL statement
        """
        if columns is None:
            columns = [c.name for c in self.columns if not c.auto_increment]

        col_names = ", ".join(f'"{c}"' if dialect.needs_quote(c) else c for c in columns)
        placeholders = ", ".join(dialect.get_placeholder(i) for i in range(len(columns)))
        table_name = self.get_quoted_name(dialect)

        return f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"

    def get_full_name(self) -> str:
        """Get fully qualified table name.

        Returns:
            schema.table or just table name
        """
        if self.schema_name:
            return f"{self.schema_name}.{self.name}"
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with table properties
        """
        return {
            "name": self.name,
            "caption": self.caption,
            "schemaName": self.schema_name,
            "columns": [c.model_dump() for c in self.columns],
            "idColumn": self.id_column.name if self.id_column else None,
            "indexes": self.indexes,
            "foreignKeys": self.foreign_keys,
        }

    @classmethod
    def create(
        cls,
        name: str,
        caption: Optional[str] = None,
        columns: Optional[List[SqlColumn]] = None,
        id_column: Optional[SqlColumn] = None,
    ) -> "SqlTable":
        """Factory method to create a SqlTable.

        Args:
            name: Table name
            caption: Table caption
            columns: List of columns
            id_column: Primary key column

        Returns:
            SqlTable instance
        """
        table = cls(name=name, caption=caption)
        if columns:
            table.set_columns(columns)
        if id_column:
            table.set_id_column(id_column)
        return table


class QuerySqlTable(SqlTable):
    """A read-only query table (FROM clause representation).

    Used for representing tables in SELECT queries with
    optional alias and join information.
    """

    alias: Optional[str] = Field(default=None, description="Table alias")
    join_type: Optional[str] = Field(default=None, description="Join type (INNER, LEFT, etc.)")
    join_condition: Optional[str] = Field(default=None, description="JOIN ON condition")

    def get_from_sql(self, dialect: FDialect) -> str:
        """Get FROM clause SQL.

        Args:
            dialect: Database dialect

        Returns:
            FROM clause SQL
        """
        table_name = self.get_quoted_name(dialect)
        if self.alias:
            return f"{table_name} AS {self.alias}"
        return table_name

    def get_join_sql(self, dialect: FDialect) -> Optional[str]:
        """Get JOIN clause SQL.

        Args:
            dialect: Database dialect

        Returns:
            JOIN clause SQL or None
        """
        if not self.join_type or not self.join_condition:
            return None

        table_name = self.get_quoted_name(dialect)
        alias_str = f" AS {self.alias}" if self.alias else ""
        return f"{self.join_type} JOIN {table_name}{alias_str} ON {self.join_condition}"


class EditSqlTable(SqlTable):
    """An editable table with INSERT/UPDATE/DELETE capabilities.

    Extends SqlTable with methods for generating DML statements
    and tracking changes.
    """

    def get_update_sql(
        self,
        dialect: FDialect,
        columns: List[str],
        where_columns: Optional[List[str]] = None,
    ) -> str:
        """Generate UPDATE SQL.

        Args:
            dialect: Database dialect
            columns: Columns to update
            where_columns: WHERE clause columns (defaults to id_column)

        Returns:
            UPDATE SQL statement
        """
        if not columns:
            raise ValueError("No columns specified for UPDATE")

        table_name = self.get_quoted_name(dialect)

        # SET clause
        set_parts = []
        for i, col in enumerate(columns):
            quoted_col = f'"{col}"' if dialect.needs_quote(col) else col
            set_parts.append(f"{quoted_col} = {dialect.get_placeholder(i)}")
        set_clause = ", ".join(set_parts)

        # WHERE clause
        if where_columns is None:
            if self.id_column:
                where_columns = [self.id_column.name]
            else:
                raise ValueError("No WHERE columns specified and no id_column")

        where_parts = []
        param_offset = len(columns)
        for i, col in enumerate(where_columns):
            quoted_col = f'"{col}"' if dialect.needs_quote(col) else col
            where_parts.append(f"{quoted_col} = {dialect.get_placeholder(param_offset + i)}")
        where_clause = " AND ".join(where_parts)

        return f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"

    def get_delete_sql(
        self,
        dialect: FDialect,
        where_columns: Optional[List[str]] = None,
    ) -> str:
        """Generate DELETE SQL.

        Args:
            dialect: Database dialect
            where_columns: WHERE clause columns (defaults to id_column)

        Returns:
            DELETE SQL statement
        """
        table_name = self.get_quoted_name(dialect)

        # WHERE clause
        if where_columns is None:
            if self.id_column:
                where_columns = [self.id_column.name]
            else:
                raise ValueError("No WHERE columns specified and no id_column")

        where_parts = []
        for i, col in enumerate(where_columns):
            quoted_col = f'"{col}"' if dialect.needs_quote(col) else col
            where_parts.append(f"{quoted_col} = {dialect.get_placeholder(i)}")
        where_clause = " AND ".join(where_parts)

        return f"DELETE FROM {table_name} WHERE {where_clause}"


__all__ = [
    "SqlTable",
    "QuerySqlTable",
    "EditSqlTable",
]