"""MySQL dialect implementation."""

from typing import Optional, List

from foggy.dataset.dialects.base import FDialect


class MySqlDialect(FDialect):
    """MySQL database dialect."""

    @property
    def name(self) -> str:
        return "mysql"

    @property
    def supports_limit_offset(self) -> bool:
        return True

    @property
    def supports_returning(self) -> bool:
        return False

    @property
    def supports_on_duplicate_key(self) -> bool:
        return True

    @property
    def supports_json_type(self) -> bool:
        return True

    @property
    def supports_cte(self) -> bool:
        return True

    @property
    def supports_grouped_aggregate_window(self) -> bool:
        return False

    @property
    def quote_char(self) -> str:
        return "`"

    def quote_identifier(self, identifier: str) -> str:
        """Quote identifier with backticks."""
        return f"`{identifier}`"

    def get_pagination_sql(
        self, sql: str, offset: Optional[int] = None, limit: Optional[int] = None
    ) -> str:
        """Add LIMIT/OFFSET to SQL query."""
        if limit is None:
            return sql
        if offset is None:
            return f"{sql} LIMIT {limit}"
        return f"{sql} LIMIT {offset}, {limit}"

    def get_count_sql(self, sql: str) -> str:
        """Convert SELECT query to COUNT query."""
        # Simple approach: wrap in subquery
        return f"SELECT COUNT(*) FROM ({sql}) AS _count"

    def get_table_exists_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        """Get SQL to check if table exists."""
        if schema:
            return (
                f"SELECT 1 FROM information_schema.tables "
                f"WHERE table_schema = '{schema}' AND table_name = '{table_name}'"
            )
        return (
            f"SELECT 1 FROM information_schema.tables "
            f"WHERE table_name = '{table_name}'"
        )

    def get_current_timestamp_sql(self) -> str:
        """Get SQL for current timestamp."""
        return "NOW()"

    def get_auto_increment_sql(self) -> str:
        """Get SQL for auto-increment column."""
        return "AUTO_INCREMENT"

    def get_string_concat_sql(self, *parts: str) -> str:
        """Get SQL to concatenate strings using CONCAT function."""
        return f"CONCAT({', '.join(parts)})"

    def get_if_null_sql(self, expr: str, default: str) -> str:
        """Get SQL for IFNULL."""
        return f"IFNULL({expr}, {default})"

    def get_date_format_sql(self, date_expr: str, format_str: str) -> str:
        """Get SQL to format date using DATE_FORMAT."""
        return f"DATE_FORMAT({date_expr}, '{format_str}')"

    def get_random_sql(self) -> str:
        """Get SQL for random number."""
        return "RAND()"

    def get_json_extract_sql(self, json_expr: str, path: str) -> str:
        """Get SQL to extract value from JSON."""
        return f"JSON_EXTRACT({json_expr}, '{path}')"

    # MySQL function mappings.  MySQL is the de-facto baseline, so
    # most functions pass through unchanged; only aliases from other
    # dialects need remapping.  Note: MySQL has native ``POW`` and
    # ``POWER`` as synonyms, so we deliberately do NOT remap ``POW``
    # here (mirrors Java ``MysqlDialect`` — POW stays POW).
    _FUNCTION_MAPPINGS: dict = {
        "NVL": "IFNULL",
        "COALESCE": "COALESCE",
        "SUBSTR": "SUBSTRING",
        "LEN": "LENGTH",
        "ISNULL": "IFNULL",
        "TRUNC": "TRUNCATE",  # Postgres alias
    }

    def get_insert_on_duplicate_key_update_sql(
        self,
        table_name: str,
        columns: List[str],
        update_columns: Optional[List[str]] = None,
        values_placeholder: str = "?",
    ) -> str:
        """Generate INSERT ... ON DUPLICATE KEY UPDATE SQL.

        Args:
            table_name: Table name
            columns: Column names
            update_columns: Columns to update on duplicate (default: all columns except first)
            values_placeholder: Placeholder for values

        Returns:
            INSERT ... ON DUPLICATE KEY UPDATE SQL
        """
        insert_sql = self.get_insert_sql(table_name, columns, values_placeholder)

        if update_columns is None:
            update_columns = columns[1:]  # Exclude first column (usually PK)

        update_clause = ", ".join(
            f"{self.quote_identifier(c)} = VALUES({self.quote_identifier(c)})"
            for c in update_columns
        )

        return f"{insert_sql} ON DUPLICATE KEY UPDATE {update_clause}"


class MySql8Dialect(MySqlDialect):
    """MySQL 8 dialect capability profile.

    The historical ``mysql`` dialect remains conservative for MySQL 5.7 style
    deployments. MySQL 8 supports grouped aggregate windows used by restricted
    CALCULATE lowering, so callers that know they are on MySQL 8 can opt in
    explicitly.
    """

    @property
    def supports_grouped_aggregate_window(self) -> bool:
        return True
