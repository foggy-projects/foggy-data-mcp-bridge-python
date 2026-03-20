"""PostgreSQL dialect implementation."""

from typing import List, Optional

from foggy.dataset.dialects.base import FDialect


class PostgresDialect(FDialect):
    """PostgreSQL database dialect."""

    @property
    def name(self) -> str:
        return "postgresql"

    @property
    def supports_limit_offset(self) -> bool:
        return True

    @property
    def supports_returning(self) -> bool:
        return True

    @property
    def supports_on_duplicate_key(self) -> bool:
        return False  # Uses ON CONFLICT instead

    @property
    def supports_json_type(self) -> bool:
        return True

    @property
    def supports_cte(self) -> bool:
        return True

    @property
    def quote_char(self) -> str:
        return '"'

    def quote_identifier(self, identifier: str) -> str:
        """Quote identifier with double quotes."""
        return f'"{identifier}"'

    def get_pagination_sql(
        self, sql: str, offset: Optional[int] = None, limit: Optional[int] = None
    ) -> str:
        """Add LIMIT/OFFSET to SQL query."""
        if limit is None and offset is None:
            return sql

        result = sql
        if limit is not None:
            result += f" LIMIT {limit}"
        if offset is not None:
            result += f" OFFSET {offset}"
        return result

    def get_count_sql(self, sql: str) -> str:
        """Convert SELECT query to COUNT query."""
        return f"SELECT COUNT(*) FROM ({sql}) AS _count"

    def get_table_exists_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        """Get SQL to check if table exists."""
        schema = schema or "public"
        return (
            f"SELECT 1 FROM information_schema.tables "
            f"WHERE table_schema = '{schema}' AND table_name = '{table_name}'"
        )

    def get_current_timestamp_sql(self) -> str:
        """Get SQL for current timestamp."""
        return "CURRENT_TIMESTAMP"

    def get_auto_increment_sql(self) -> str:
        """Get SQL for auto-increment column (SERIAL or BIGSERIAL)."""
        return "SERIAL"  # or use GENERATED ALWAYS AS IDENTITY

    def get_string_concat_sql(self, *parts: str) -> str:
        """Get SQL to concatenate strings using || operator."""
        return " || ".join(parts)

    def get_if_null_sql(self, expr: str, default: str) -> str:
        """Get SQL for COALESCE."""
        return f"COALESCE({expr}, {default})"

    def get_date_format_sql(self, date_expr: str, format_str: str) -> str:
        """Get SQL to format date using TO_CHAR."""
        return f"TO_CHAR({date_expr}, '{format_str}')"

    def get_random_sql(self) -> str:
        """Get SQL for random number."""
        return "RANDOM()"

    def get_json_extract_sql(self, json_expr: str, path: str) -> str:
        """Get SQL to extract value from JSON using ->> operator."""
        # Convert JSONPath to PostgreSQL style
        pg_path = path.replace("$", "").replace("/", ".")
        if pg_path.startswith("."):
            pg_path = pg_path[1:]
        return f"{json_expr}->>'{pg_path}'"

    def _get_function_mappings(self) -> dict:
        """PostgreSQL function mappings: IFNULL→COALESCE, NVL→COALESCE."""
        return {
            "IFNULL": "COALESCE",
            "NVL": "COALESCE",
            "ISNULL": "COALESCE",
            "LEN": "LENGTH",
            "SUBSTR": "SUBSTR",
            "SUBSTRING": "SUBSTR",
        }

    def get_insert_on_conflict_sql(
        self,
        table_name: str,
        columns: List[str],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
        values_placeholder: str = "%s",
    ) -> str:
        """Generate INSERT ... ON CONFLICT DO UPDATE SQL.

        Args:
            table_name: Table name
            columns: Column names
            conflict_columns: Columns that trigger conflict
            update_columns: Columns to update on conflict (default: all columns except conflict columns)
            values_placeholder: Placeholder for values

        Returns:
            INSERT ... ON CONFLICT DO UPDATE SQL
        """
        insert_sql = self.get_insert_sql(table_name, columns, values_placeholder)

        conflict_cols = ", ".join(self.quote_identifier(c) for c in conflict_columns)

        if update_columns is None:
            update_columns = [c for c in columns if c not in conflict_columns]

        if not update_columns:
            return f"{insert_sql} ON CONFLICT ({conflict_cols}) DO NOTHING"

        update_clause = ", ".join(
            f"{self.quote_identifier(c)} = EXCLUDED.{self.quote_identifier(c)}"
            for c in update_columns
        )

        return f"{insert_sql} ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_clause}"

    def get_upsert_sql(
        self,
        table_name: str,
        columns: List[str],
        key_columns: List[str],
        values_placeholder: str = "%s",
    ) -> str:
        """Generate upsert (INSERT ... ON CONFLICT) SQL."""
        return self.get_insert_on_conflict_sql(
            table_name, columns, key_columns, None, values_placeholder
        )