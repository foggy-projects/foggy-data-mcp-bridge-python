"""Database dialect base class and implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional


class FDialect(ABC):
    """Abstract base class for database dialects.

    Each database type (MySQL, PostgreSQL, etc.) should implement this
    to provide database-specific SQL syntax.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Dialect name (e.g., 'mysql', 'postgresql')."""
        pass

    @property
    @abstractmethod
    def supports_limit_offset(self) -> bool:
        """Whether this dialect supports LIMIT/OFFSET syntax."""
        pass

    @property
    @abstractmethod
    def supports_returning(self) -> bool:
        """Whether this dialect supports RETURNING clause."""
        pass

    @property
    @abstractmethod
    def supports_on_duplicate_key(self) -> bool:
        """Whether this dialect supports ON DUPLICATE KEY UPDATE."""
        pass

    @property
    @abstractmethod
    def supports_json_type(self) -> bool:
        """Whether this dialect supports native JSON type."""
        pass

    @property
    @abstractmethod
    def supports_cte(self) -> bool:
        """Whether this dialect supports Common Table Expressions (WITH clause)."""
        pass

    @property
    @abstractmethod
    def quote_char(self) -> str:
        """Character used to quote identifiers."""
        pass

    @abstractmethod
    def quote_identifier(self, identifier: str) -> str:
        """Quote an identifier (table name, column name, etc.)."""
        pass

    @abstractmethod
    def get_pagination_sql(
        self, sql: str, offset: Optional[int] = None, limit: Optional[int] = None
    ) -> str:
        """Add pagination to SQL query."""
        pass

    @abstractmethod
    def get_count_sql(self, sql: str) -> str:
        """Convert SELECT query to COUNT query."""
        pass

    @abstractmethod
    def get_table_exists_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        """Get SQL to check if table exists."""
        pass

    @abstractmethod
    def get_current_timestamp_sql(self) -> str:
        """Get SQL for current timestamp."""
        pass

    @abstractmethod
    def get_auto_increment_sql(self) -> str:
        """Get SQL for auto-increment column."""
        pass

    @abstractmethod
    def get_string_concat_sql(self, *parts: str) -> str:
        """Get SQL to concatenate strings."""
        pass

    @abstractmethod
    def get_if_null_sql(self, expr: str, default: str) -> str:
        """Get SQL for IFNULL/COALESCE."""
        pass

    @abstractmethod
    def get_date_format_sql(self, date_expr: str, format_str: str) -> str:
        """Get SQL to format date."""
        pass

    @abstractmethod
    def get_random_sql(self) -> str:
        """Get SQL for random number."""
        pass

    @abstractmethod
    def get_json_extract_sql(self, json_expr: str, path: str) -> str:
        """Get SQL to extract value from JSON."""
        pass

    def get_create_table_sql(
        self,
        table_name: str,
        columns: List[str],
        primary_keys: Optional[List[str]] = None,
        if_not_exists: bool = True,
    ) -> str:
        """Generate CREATE TABLE SQL.

        Args:
            table_name: Table name
            columns: Column definitions (e.g., ["id INT", "name VARCHAR(100)"])
            primary_keys: List of primary key column names
            if_not_exists: Whether to add IF NOT EXISTS

        Returns:
            CREATE TABLE SQL
        """
        parts = ["CREATE TABLE"]
        if if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.quote_identifier(table_name))
        parts.append("(")
        parts.append(", ".join(columns))

        if primary_keys:
            pk_cols = ", ".join(self.quote_identifier(pk) for pk in primary_keys)
            parts.append(f", PRIMARY KEY ({pk_cols})")

        parts.append(")")

        return " ".join(parts)

    def get_drop_table_sql(self, table_name: str, if_exists: bool = True) -> str:
        """Generate DROP TABLE SQL."""
        parts = ["DROP TABLE"]
        if if_exists:
            parts.append("IF EXISTS")
        parts.append(self.quote_identifier(table_name))
        return " ".join(parts)

    def get_truncate_table_sql(self, table_name: str) -> str:
        """Generate TRUNCATE TABLE SQL."""
        return f"TRUNCATE TABLE {self.quote_identifier(table_name)}"

    def get_insert_sql(
        self,
        table_name: str,
        columns: List[str],
        values_placeholder: str = "?",
    ) -> str:
        """Generate INSERT SQL.

        Args:
            table_name: Table name
            columns: Column names
            values_placeholder: Placeholder for values (default: '?')

        Returns:
            INSERT SQL
        """
        cols = ", ".join(self.quote_identifier(c) for c in columns)
        placeholders = ", ".join([values_placeholder] * len(columns))
        return f"INSERT INTO {self.quote_identifier(table_name)} ({cols}) VALUES ({placeholders})"

    def get_update_sql(
        self, table_name: str, set_columns: List[str], where_clause: str = ""
    ) -> str:
        """Generate UPDATE SQL."""
        set_clause = ", ".join(
            f"{self.quote_identifier(c)} = ?" for c in set_columns
        )
        sql = f"UPDATE {self.quote_identifier(table_name)} SET {set_clause}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        return sql

    def get_delete_sql(self, table_name: str, where_clause: str = "") -> str:
        """Generate DELETE SQL."""
        sql = f"DELETE FROM {self.quote_identifier(table_name)}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        return sql