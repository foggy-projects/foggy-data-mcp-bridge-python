"""SQLite dialect implementation."""

from typing import List, Optional

from foggy.dataset.dialects.base import FDialect


class SqliteDialect(FDialect):
    """SQLite database dialect."""

    @property
    def name(self) -> str:
        return "sqlite"

    @property
    def supports_limit_offset(self) -> bool:
        return True

    @property
    def supports_returning(self) -> bool:
        return False  # SQLite 3.35+ supports RETURNING, but not all versions

    @property
    def supports_on_duplicate_key(self) -> bool:
        return False  # Uses INSERT OR REPLACE instead

    @property
    def supports_json_type(self) -> bool:
        return False  # JSON is stored as TEXT

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
        # SQLite doesn't have schemas, but has sqlite_master
        # Use quote_identifier to prevent SQL injection via table names
        safe_name = table_name.replace("'", "''")
        return f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{safe_name}'"

    def get_current_timestamp_sql(self) -> str:
        """Get SQL for current timestamp."""
        return "CURRENT_TIMESTAMP"

    def get_auto_increment_sql(self) -> str:
        """Get SQL for auto-increment column."""
        return "AUTOINCREMENT"

    def get_string_concat_sql(self, *parts: str) -> str:
        """Get SQL to concatenate strings using || operator."""
        return " || ".join(parts)

    def get_if_null_sql(self, expr: str, default: str) -> str:
        """Get SQL for IFNULL."""
        return f"IFNULL({expr}, {default})"

    def get_date_format_sql(self, date_expr: str, format_str: str) -> str:
        """Get SQL to format date using strftime."""
        return f"strftime('{format_str}', {date_expr})"

    def get_random_sql(self) -> str:
        """Get SQL for random number."""
        return "RANDOM()"

    def get_json_extract_sql(self, json_expr: str, path: str) -> str:
        """Get SQL to extract value from JSON using json_extract."""
        return f"json_extract({json_expr}, '{path}')"

    # SQLite function mappings: NVL/ISNULL → IFNULL, LEN → LENGTH,
    # SUBSTRING → SUBSTR (SQLite prefers the short form).
    _FUNCTION_MAPPINGS: dict = {
        "NVL": "IFNULL",
        "COALESCE": "COALESCE",
        "ISNULL": "IFNULL",
        "LEN": "LENGTH",
        "SUBSTR": "SUBSTR",
        "SUBSTRING": "SUBSTR",
    }

    def build_function_call(self, func_name: str, args: List[str]) -> Optional[str]:
        """Complex SQLite translations.

        Mirrors Java ``SqliteDialect.buildFunctionCall`` (lines 190-211):

        - ``YEAR/MONTH/DAY/HOUR/MINUTE/SECOND(col)`` →
          ``CAST(strftime('%Y', col) AS INTEGER)`` etc.
        - ``DATE_FORMAT(col, fmt)`` → ``strftime(fmt, col)`` — arguments
          reversed; SQLite uses same MySQL ``%X`` placeholders natively so
          no format translation needed.
        """
        if func_name is None or args is None:
            return None
        upper = func_name.upper()
        _STRFTIME_MAP = {
            "YEAR": "%Y",
            "MONTH": "%m",
            "DAY": "%d",
            "HOUR": "%H",
            "MINUTE": "%M",
            "SECOND": "%S",
        }
        if upper in _STRFTIME_MAP and len(args) == 1:
            token = _STRFTIME_MAP[upper]
            return f"CAST(strftime('{token}', {args[0]}) AS INTEGER)"
        if upper == "DATE_FORMAT" and len(args) == 2:
            # SQLite strftime reverses the arg order.
            return f"strftime({args[1]}, {args[0]})"
        return None

    def get_create_table_sql(
        self,
        table_name: str,
        columns: list[str],
        primary_keys: Optional[list[str]] = None,
        if_not_exists: bool = True,
    ) -> str:
        """Generate CREATE TABLE SQL.

        SQLite specific: INTEGER PRIMARY KEY is an alias for ROWID.
        """
        parts = ["CREATE TABLE"]
        if if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.quote_identifier(table_name))
        parts.append("(")
        parts.append(", ".join(columns))

        if primary_keys and len(primary_keys) > 1:
            # Composite primary key
            pk_cols = ", ".join(self.quote_identifier(pk) for pk in primary_keys)
            parts.append(f", PRIMARY KEY ({pk_cols})")

        parts.append(")")

        return " ".join(parts)

    def get_insert_or_replace_sql(
        self,
        table_name: str,
        columns: list[str],
        values_placeholder: str = "?",
    ) -> str:
        """Generate INSERT OR REPLACE SQL.

        Args:
            table_name: Table name
            columns: Column names
            values_placeholder: Placeholder for values

        Returns:
            INSERT OR REPLACE SQL
        """
        cols = ", ".join(self.quote_identifier(c) for c in columns)
        placeholders = ", ".join([values_placeholder] * len(columns))
        return f"INSERT OR REPLACE INTO {self.quote_identifier(table_name)} ({cols}) VALUES ({placeholders})"

    def get_insert_or_ignore_sql(
        self,
        table_name: str,
        columns: list[str],
        values_placeholder: str = "?",
    ) -> str:
        """Generate INSERT OR IGNORE SQL."""
        cols = ", ".join(self.quote_identifier(c) for c in columns)
        placeholders = ", ".join([values_placeholder] * len(columns))
        return f"INSERT OR IGNORE INTO {self.quote_identifier(table_name)} ({cols}) VALUES ({placeholders})"