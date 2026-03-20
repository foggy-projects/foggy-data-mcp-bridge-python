"""SQL Server dialect implementation."""

from typing import Optional

from foggy.dataset.dialects.base import FDialect


class SqlServerDialect(FDialect):
    """Microsoft SQL Server database dialect."""

    @property
    def name(self) -> str:
        return "sqlserver"

    @property
    def supports_limit_offset(self) -> bool:
        return True  # Uses OFFSET FETCH syntax

    @property
    def supports_returning(self) -> bool:
        return True  # Uses OUTPUT clause

    @property
    def supports_on_duplicate_key(self) -> bool:
        return False  # Uses MERGE statement

    @property
    def supports_json_type(self) -> bool:
        return False  # JSON stored as NVARCHAR

    @property
    def supports_cte(self) -> bool:
        return True

    @property
    def quote_char(self) -> str:
        return "[]"

    def quote_identifier(self, identifier: str) -> str:
        """Quote identifier with brackets."""
        return f"[{identifier}]"

    def get_pagination_sql(
        self, sql: str, offset: Optional[int] = None, limit: Optional[int] = None
    ) -> str:
        """Add OFFSET/FETCH to SQL query.

        Note: SQL Server requires ORDER BY for OFFSET/FETCH.
        """
        if limit is None and offset is None:
            return sql

        # SQL Server requires ORDER BY for OFFSET/FETCH
        if "ORDER BY" not in sql.upper():
            sql += " ORDER BY 1"

        result = sql
        if offset is not None:
            result += f" OFFSET {offset} ROWS"
        else:
            result += " OFFSET 0 ROWS"

        if limit is not None:
            result += f" FETCH NEXT {limit} ROWS ONLY"

        return result

    def get_count_sql(self, sql: str) -> str:
        """Convert SELECT query to COUNT query."""
        return f"SELECT COUNT(*) FROM ({sql}) AS _count"

    def get_table_exists_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        """Get SQL to check if table exists."""
        schema = schema or "dbo"
        # Escape single quotes to prevent SQL injection
        safe_schema = schema.replace("'", "''")
        safe_name = table_name.replace("'", "''")
        return (
            f"SELECT 1 FROM information_schema.tables "
            f"WHERE table_schema = '{safe_schema}' AND table_name = '{safe_name}'"
        )

    def get_current_timestamp_sql(self) -> str:
        """Get SQL for current timestamp."""
        return "GETDATE()"

    def get_auto_increment_sql(self) -> str:
        """Get SQL for auto-increment column."""
        return "IDENTITY(1,1)"

    def get_string_concat_sql(self, *parts: str) -> str:
        """Get SQL to concatenate strings using + operator."""
        return " + ".join(parts)

    def get_if_null_sql(self, expr: str, default: str) -> str:
        """Get SQL for ISNULL."""
        return f"ISNULL({expr}, {default})"

    def get_date_format_sql(self, date_expr: str, format_str: str) -> str:
        """Get SQL to format date using CONVERT."""
        # SQL Server uses format codes
        # Common codes: 23 = yyyy-mm-dd, 120 = yyyy-mm-dd hh:mi:ss
        format_map = {
            "%Y-%m-%d": "23",
            "%Y-%m-%d %H:%M:%S": "120",
            "%Y%m%d": "112",
        }
        style = format_map.get(format_str, "120")
        return f"CONVERT(VARCHAR, {date_expr}, {style})"

    def get_random_sql(self) -> str:
        """Get SQL for random number."""
        return "NEWID()"

    def get_json_extract_sql(self, json_expr: str, path: str) -> str:
        """Get SQL to extract value from JSON using JSON_VALUE."""
        return f"JSON_VALUE({json_expr}, '{path}')"

    def _get_function_mappings(self) -> dict:
        """SQL Server function mappings: IFNULL→ISNULL, LENGTH→LEN, NVL→ISNULL."""
        return {
            "IFNULL": "ISNULL",
            "NVL": "ISNULL",
            "COALESCE": "COALESCE",
            "LENGTH": "LEN",
            "SUBSTR": "SUBSTRING",
        }

    def get_insert_with_output_sql(
        self,
        table_name: str,
        columns: list[str],
        output_columns: Optional[list[str]] = None,
        values_placeholder: str = "?",
    ) -> str:
        """Generate INSERT with OUTPUT clause.

        Args:
            table_name: Table name
            columns: Column names
            output_columns: Columns to output (default: all columns)
            values_placeholder: Placeholder for values

        Returns:
            INSERT ... OUTPUT ... SQL
        """
        cols = ", ".join(self.quote_identifier(c) for c in columns)
        placeholders = ", ".join([values_placeholder] * len(columns))

        if output_columns is None:
            output_cols = ", ".join(
                f"INSERTED.{self.quote_identifier(c)}" for c in columns
            )
        else:
            output_cols = ", ".join(
                f"INSERTED.{self.quote_identifier(c)}" for c in output_columns
            )

        return (
            f"INSERT INTO {self.quote_identifier(table_name)} ({cols}) "
            f"OUTPUT {output_cols} "
            f"VALUES ({placeholders})"
        )

    def get_top_sql(self, sql: str, top: int) -> str:
        """Add TOP clause to SELECT statement.

        Args:
            sql: SQL query
            top: Number of rows to return

        Returns:
            SQL with TOP clause
        """
        # Insert TOP after SELECT
        upper_sql = sql.upper()
        select_idx = upper_sql.find("SELECT")
        if select_idx == -1:
            return sql

        insert_pos = select_idx + len("SELECT")
        return sql[:insert_pos] + f" TOP {top}" + sql[insert_pos:]