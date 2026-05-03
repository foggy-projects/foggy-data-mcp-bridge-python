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
    def supports_grouped_aggregate_window(self) -> bool:
        """Whether grouped aggregate windows such as SUM(SUM(x)) OVER are supported."""
        return True

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

    def translate_function(self, func_name: str, args: List[str]) -> str:
        """Translate a function call to the dialect-specific SQL.

        Lookup order (mirrors Java ``FDialect.buildFunctionCall`` →
        ``translateFunction`` cascade in
        ``foggy-dataset/src/main/java/.../db/dialect/FDialect.java``):

        1. ``build_function_call(func_name, args)`` — complex translations
           that need argument re-ordering, format-string rewriting, or
           alternative SQL forms (e.g. ``DATE_FORMAT`` → ``TO_CHAR`` on
           Postgres, or ``YEAR(col)`` → ``EXTRACT(YEAR FROM col)``).  A
           dialect returns ``None`` here to signal "fall through".
        2. ``_get_function_mappings()`` — simple name rewrite (e.g. ``NVL``
           → ``IFNULL`` / ``COALESCE`` / ``ISNULL``).
        3. Default ``FUNC_NAME(args)`` emission, preserving the original
           case as passed in.

        Args:
            func_name: Function name (case-insensitive)
            args: Function arguments as already-rendered SQL expressions

        Returns:
            Translated SQL expression, e.g. ``"IFNULL(col, 0)"`` or
            ``"TO_CHAR(col, 'YYYY-MM')"``.
        """
        if func_name is None:
            return None
        # 1. Dialect-specific complex translation
        complex_sql = self.build_function_call(func_name, args)
        if complex_sql is not None:
            return complex_sql

        # 2. Simple rename
        upper_name = func_name.upper()
        mappings = self._get_function_mappings()
        translated = mappings.get(upper_name, upper_name)
        return f"{translated}({', '.join(args)})"

    def build_function_call(self, func_name: str, args: List[str]) -> Optional[str]:
        """Build a dialect-specific SQL expression for a function call.

        Override in subclasses to provide translations that cannot be
        expressed as a simple rename.  Return ``None`` to signal
        "no special handling — let translate_function fall through to
        the rename table".

        Mirrors Java ``FDialect.buildFunctionCall`` (default returns
        ``null`` / ``None``).

        Args:
            func_name: Function name (case-insensitive)
            args: Function arguments as already-rendered SQL expressions

        Returns:
            A fully-formed SQL call string, or ``None`` to fall through.
        """
        return None

    _FUNCTION_MAPPINGS: dict = {}

    def _get_function_mappings(self) -> dict:
        """Return a dict of function name mappings for this dialect.

        Override ``_FUNCTION_MAPPINGS`` class attribute in subclasses.
        Keys and values are UPPER CASE. E.g., ``{"NVL": "IFNULL"}``.
        """
        return self._FUNCTION_MAPPINGS

    @staticmethod
    def _translate_mysql_date_format(
        mysql_fmt_literal: str,
        format_map: dict,
    ) -> str:
        """Rewrite a MySQL ``DATE_FORMAT`` format literal using ``format_map``.

        The input is a SQL string literal like ``"'%Y-%m-%d'"`` (single-
        quoted, as emitted by upstream string-literal normalization).
        Only ``%X`` placeholders are substituted; other characters
        (including outer quotes, dashes, spaces) pass through verbatim.
        Unknown placeholders are left literal so any downstream SQL
        error still points at the original symbol.

        Shared between PostgresDialect / SqlServerDialect; each passes
        its own ``format_map``.
        """
        if len(mysql_fmt_literal) >= 2 and \
                mysql_fmt_literal[0] == "'" and mysql_fmt_literal[-1] == "'":
            inner = mysql_fmt_literal[1:-1]
            quoted = True
        else:
            inner = mysql_fmt_literal
            quoted = False
        out: List[str] = []
        i = 0
        n = len(inner)
        while i < n:
            if inner[i] == "%" and i + 1 < n:
                tok = inner[i : i + 2]
                out.append(format_map.get(tok, tok))
                i += 2
                continue
            out.append(inner[i])
            i += 1
        translated = "".join(out)
        return f"'{translated}'" if quoted else translated

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

    def quote(self, identifier: str) -> str:
        """Quote an identifier (alias for quote_identifier)."""
        return self.quote_identifier(identifier)

    def needs_quote(self, identifier: str) -> bool:
        """Check if an identifier needs to be quoted.

        Args:
            identifier: Identifier to check

        Returns:
            True if identifier should be quoted
        """
        # Reserved words or special characters require quoting
        reserved_words = {
            "select", "from", "where", "join", "left", "right", "inner", "outer",
            "on", "and", "or", "not", "null", "true", "false", "in", "like",
            "order", "by", "group", "having", "limit", "offset", "insert", "into",
            "values", "update", "set", "delete", "create", "table", "drop", "alter",
            "index", "key", "primary", "foreign", "references", "unique", "default",
            "asc", "desc", "union", "all", "distinct", "count", "sum", "avg", "max",
            "min", "case", "when", "then", "else", "end", "as", "exists", "between",
        }
        lower_id = identifier.lower()
        return lower_id in reserved_words or not identifier.isidentifier()

    def get_placeholder(self, index: int) -> str:
        """Get placeholder for parameterized query.

        Args:
            index: Parameter index (0-based)

        Returns:
            Placeholder string (default: '?')
        """
        return "?"

    def get_type_name(
        self,
        jdbc_type: int,
        length: int = 0,
        precision: int = 19,
        scale: int = 2,
    ) -> str:
        """Get SQL type name for a JDBC type.

        Args:
            jdbc_type: JDBC type constant
            length: Column length
            precision: Numeric precision
            scale: Numeric scale

        Returns:
            SQL type name string
        """
        from foggy.dataset.table.sql_column import JdbcType

        type_map = {
            JdbcType.VARCHAR: f"VARCHAR({length})" if length > 0 else "VARCHAR",
            JdbcType.CHAR: f"CHAR({length})" if length > 0 else "CHAR",
            JdbcType.LONGVARCHAR: "TEXT",
            JdbcType.NVARCHAR: f"NVARCHAR({length})" if length > 0 else "NVARCHAR",
            JdbcType.NCHAR: f"NCHAR({length})" if length > 0 else "NCHAR",
            JdbcType.CLOB: "CLOB",
            JdbcType.NCLOB: "NCLOB",
            JdbcType.BIT: "BIT",
            JdbcType.BOOLEAN: "BOOLEAN",
            JdbcType.TINYINT: "TINYINT",
            JdbcType.SMALLINT: "SMALLINT",
            JdbcType.INTEGER: "INTEGER",
            JdbcType.BIGINT: "BIGINT",
            JdbcType.FLOAT: "FLOAT",
            JdbcType.REAL: "REAL",
            JdbcType.DOUBLE: "DOUBLE",
            JdbcType.NUMERIC: f"NUMERIC({precision}, {scale})",
            JdbcType.DECIMAL: f"DECIMAL({precision}, {scale})",
            JdbcType.DATE: "DATE",
            JdbcType.TIME: "TIME",
            JdbcType.TIMESTAMP: "TIMESTAMP",
            JdbcType.BINARY: f"BINARY({length})" if length > 0 else "BINARY",
            JdbcType.VARBINARY: f"VARBINARY({length})" if length > 0 else "VARBINARY",
            JdbcType.BLOB: "BLOB",
            JdbcType.OTHER: "JSON",
            JdbcType.JAVA_OBJECT: "OBJECT",
        }

        return type_map.get(jdbc_type, "VARCHAR")

    def get_on_duplicate_key_ignore_sql(self) -> str:
        """Get SQL for ignoring duplicates (do nothing).

        Returns:
            SQL clause for ignoring duplicates
        """
        return ""  # Default: no special handling
