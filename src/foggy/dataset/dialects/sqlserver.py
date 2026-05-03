"""SQL Server dialect implementation."""

from typing import List, Optional

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
    def supports_grouped_aggregate_window(self) -> bool:
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
        """Get SQL to check if table exists.

        Note: Uses quote-escaping for system catalog query (information_schema).
        These are system identifier names, not arbitrary user input.
        """
        schema = schema or "dbo"
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

    # SQL Server function mappings — aligned with Java ``SqlServerDialect``.
    #   NULL coalescing: IFNULL/NVL/ISNULL → ISNULL
    #   String:          LENGTH/CHAR_LENGTH → LEN, SUBSTR → SUBSTRING
    #   Math:            CEIL → CEILING, POW → POWER
    #   Statistical:     STDDEV_POP → STDEVP, STDDEV_SAMP → STDEV,
    #                    VAR_POP → VARP, VAR_SAMP → VAR
    _FUNCTION_MAPPINGS: dict = {
        "IFNULL": "ISNULL",
        "NVL": "ISNULL",
        "COALESCE": "COALESCE",
        "LENGTH": "LEN",
        "CHAR_LENGTH": "LEN",
        "SUBSTR": "SUBSTRING",
        "CEIL": "CEILING",
        "POW": "POWER",
        "STDDEV_POP": "STDEVP",
        "STDDEV_SAMP": "STDEV",
        "VAR_POP": "VARP",
        "VAR_SAMP": "VAR",
    }

    # MySQL → SQL Server DATE_FORMAT placeholder mapping.
    # 对齐 Java ``SqlServerDialect.translateMysqlDateFormatToSqlServer``.
    _MYSQL_TO_SQLSERVER_FORMAT: dict = {
        "%Y": "yyyy",    "%y": "yy",
        "%m": "MM",      "%d": "dd",
        "%H": "HH",      "%i": "mm",      "%s": "ss",
    }

    def build_function_call(self, func_name: str, args: List[str]) -> Optional[str]:
        """Complex SQL Server translations.

        Mirrors Java ``SqlServerDialect.buildFunctionCall``:
        - ``HOUR/MINUTE/SECOND(col)`` → ``DATEPART(HOUR, col)``
          (``YEAR/MONTH/DAY`` are native, handled via default rename.)
        - ``DATE_FORMAT(col, fmt)`` → ``FORMAT(col, translated_fmt)``
        """
        if func_name is None or args is None:
            return None
        upper = func_name.upper()
        if upper in ("HOUR", "MINUTE", "SECOND"):
            if len(args) == 1:
                return f"DATEPART({upper}, {args[0]})"
            return None
        if upper == "DATE_FORMAT" and len(args) == 2:
            translated_fmt = self._translate_mysql_date_format(args[1])
            return f"FORMAT({args[0]}, {translated_fmt})"
        return None

    @classmethod
    def _translate_mysql_date_format(cls, mysql_fmt_literal: str) -> str:
        """Translate MySQL format literal to SQL Server ``FORMAT`` form."""
        return FDialect._translate_mysql_date_format(
            mysql_fmt_literal, cls._MYSQL_TO_SQLSERVER_FORMAT,
        )

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