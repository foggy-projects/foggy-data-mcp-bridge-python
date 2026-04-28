"""Database executor for running queries.

This module provides async database execution capabilities using:
- aiomysql for MySQL
- asyncpg for PostgreSQL
- aiosqlite for SQLite
- pyodbc for SQL Server
"""

from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod
from datetime import datetime, date
import logging
import time

from pydantic import BaseModel


logger = logging.getLogger(__name__)


class QueryResult(BaseModel):
    """Result of a database query."""

    columns: List[str] = []
    rows: List[Dict[str, Any]] = []
    total: int = 0
    has_more: bool = False
    execution_time_ms: float = 0.0
    sql: Optional[str] = None
    error: Optional[str] = None


class DatabaseExecutor(ABC):
    """Abstract database executor."""

    @abstractmethod
    async def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        limit: Optional[int] = None,
    ) -> QueryResult:
        """Execute a SQL query and return results.

        Args:
            sql: SQL query string
            params: Query parameters
            limit: Maximum rows to return

        Returns:
            QueryResult with data or error
        """
        pass

    @abstractmethod
    async def execute_count(self, sql: str, params: Optional[List[Any]] = None) -> int:
        """Execute a COUNT query and return the count.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            Row count
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection."""
        pass


class MySQLExecutor(DatabaseExecutor):
    """MySQL database executor using aiomysql."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        database: str = "",
        user: str = "",
        password: str = "",
        pool_size: int = 5,
    ):
        """Initialize MySQL executor."""
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._pool_size = pool_size
        self._pool = None

    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import aiomysql
                self._pool = await aiomysql.create_pool(
                    host=self._host,
                    port=self._port,
                    db=self._database,
                    user=self._user,
                    password=self._password,
                    minsize=1,
                    maxsize=self._pool_size,
                    autocommit=True,
                )
            except ImportError:
                raise RuntimeError("aiomysql not installed. Run: pip install aiomysql")
        return self._pool

    async def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        limit: Optional[int] = None,
    ) -> QueryResult:
        """Execute a MySQL query."""
        import aiomysql
        start_time = time.time()

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # Apply limit
                    if limit and "LIMIT" not in sql.upper():
                        sql = f"{sql} LIMIT {limit}"

                    # Convert ? placeholders to %s for aiomysql
                    if params:
                        sql = sql.replace("?", "%s")

                    await cursor.execute(sql, params or ())

                    # Get column names
                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                    else:
                        columns = []

                    # Fetch rows
                    rows = await cursor.fetchall()

                    execution_time_ms = (time.time() - start_time) * 1000

                    return QueryResult(
                        columns=columns,
                        rows=list(rows) if rows else [],
                        total=len(rows) if rows else 0,
                        execution_time_ms=execution_time_ms,
                        sql=sql,
                    )

        except Exception as e:
            logger.error(f"MySQL query failed: {e}")
            return QueryResult(
                error=str(e),
                sql=sql,
            )

    async def execute_count(self, sql: str, params: Optional[List[Any]] = None) -> int:
        """Execute a COUNT query."""
        # Convert SELECT to COUNT
        count_sql = f"SELECT COUNT(*) as cnt FROM ({sql}) as subq"

        result = await self.execute(count_sql, params)
        if result.error or not result.rows:
            return 0
        return result.rows[0].get("cnt", 0)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


class PostgreSQLExecutor(DatabaseExecutor):
    """PostgreSQL database executor using asyncpg."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "",
        user: str = "",
        password: str = "",
        pool_size: int = 5,
    ):
        """Initialize PostgreSQL executor."""
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._pool_size = pool_size
        self._pool = None

    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(
                    host=self._host,
                    port=self._port,
                    database=self._database,
                    user=self._user,
                    password=self._password,
                    min_size=1,
                    max_size=self._pool_size,
                )
            except ImportError:
                raise RuntimeError("asyncpg not installed. Run: pip install asyncpg")
        return self._pool

    async def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        limit: Optional[int] = None,
    ) -> QueryResult:
        """Execute a PostgreSQL query."""
        start_time = time.time()

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Apply limit
                if limit and "LIMIT" not in sql.upper():
                    sql = f"{sql} LIMIT {limit}"

                # Convert ? to $1, $2, ... for asyncpg
                if params:
                    sql, param_list = self._convert_params(sql, params)
                    rows = await conn.fetch(sql, *param_list)
                else:
                    rows = await conn.fetch(sql)

                # Get column names
                if rows:
                    columns = list(rows[0].keys())
                    rows_data = [dict(row) for row in rows]
                else:
                    columns = []
                    rows_data = []

                execution_time_ms = (time.time() - start_time) * 1000

                return QueryResult(
                    columns=columns,
                    rows=rows_data,
                    total=len(rows_data),
                    execution_time_ms=execution_time_ms,
                    sql=sql,
                )

        except Exception as e:
            logger.error(f"PostgreSQL query failed: {e}")
            return QueryResult(
                error=str(e),
                sql=sql,
            )

    def _convert_params(self, sql: str, params: List[Any]) -> tuple:
        """Convert ? placeholders to $1, $2, ... for PostgreSQL."""
        result = []
        param_index = 0
        i = 0
        while i < len(sql):
            if sql[i] == '?':
                param_index += 1
                result.append(f'${param_index}')
            else:
                result.append(sql[i])
            i += 1
        return ''.join(result), self._auto_convert_params(params)

    @staticmethod
    def _auto_convert_params(params: List[Any]) -> List[Any]:
        """Convert string params to proper Python types for asyncpg.

        asyncpg uses PostgreSQL's prepared statement protocol which requires
        strict type matching. JSON string dates from MCP clients must be
        converted to Python datetime objects.
        """
        if not params:
            return params
        converted = []
        for p in params:
            if isinstance(p, str):
                # Try ISO date/datetime parsing (most specific first)
                for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                    try:
                        dt = datetime.strptime(p, fmt)
                        # Return date object for date-only strings
                        converted.append(dt.date() if fmt == '%Y-%m-%d' else dt)
                        break
                    except ValueError:
                        continue
                else:
                    converted.append(p)  # Keep as string if not a date
            else:
                converted.append(p)
        return converted

    async def execute_count(self, sql: str, params: Optional[List[Any]] = None) -> int:
        """Execute a COUNT query."""
        count_sql = f"SELECT COUNT(*) as cnt FROM ({sql}) as subq"

        result = await self.execute(count_sql, params)
        if result.error or not result.rows:
            return 0
        return result.rows[0].get("cnt", 0)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None


class SQLiteExecutor(DatabaseExecutor):
    """SQLite database executor using aiosqlite."""

    def __init__(self, database: str = ":memory:"):
        """Initialize SQLite executor."""
        self._database = database
        self._conn = None

    async def _get_connection(self):
        """Get or create connection."""
        if self._conn is None:
            try:
                import aiosqlite
                self._conn = await aiosqlite.connect(self._database)
                self._conn.row_factory = aiosqlite.Row
            except ImportError:
                raise RuntimeError("aiosqlite not installed. Run: pip install aiosqlite")
        return self._conn

    async def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        limit: Optional[int] = None,
    ) -> QueryResult:
        """Execute a SQLite query."""
        start_time = time.time()

        try:
            conn = await self._get_connection()

            # Apply limit
            if limit and "LIMIT" not in sql.upper():
                sql = f"{sql} LIMIT {limit}"

            cursor = await conn.execute(sql, params or ())
            rows = await cursor.fetchall()

            # Get column names
            if rows and cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows_data = [dict(row) for row in rows]
            else:
                columns = []
                rows_data = []

            execution_time_ms = (time.time() - start_time) * 1000

            return QueryResult(
                columns=columns,
                rows=rows_data,
                total=len(rows_data),
                execution_time_ms=execution_time_ms,
                sql=sql,
            )

        except Exception as e:
            logger.error(f"SQLite query failed: {e}")
            return QueryResult(
                error=str(e),
                sql=sql,
            )

    async def execute_count(self, sql: str, params: Optional[List[Any]] = None) -> int:
        """Execute a COUNT query."""
        count_sql = f"SELECT COUNT(*) as cnt FROM ({sql})"

        result = await self.execute(count_sql, params)
        if result.error or not result.rows:
            return 0
        return result.rows[0].get("cnt", 0)

    async def close(self) -> None:
        """Close the connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None


class SQLServerExecutor(DatabaseExecutor):
    """SQL Server database executor using pyodbc.

    pyodbc is synchronous, so the async methods wrap blocking calls.
    This is acceptable for test/demo usage; production should consider
    an async driver or thread-pool delegation.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1433,
        database: str = "",
        user: str = "",
        password: str = "",
        driver: str = "{SQL Server}",
    ):
        """Initialize SQL Server executor."""
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._driver = driver
        self._conn = None

    def _get_connection(self):
        """Get or create connection (synchronous)."""
        if self._conn is None:
            try:
                import pyodbc
            except ImportError:
                raise RuntimeError(
                    "pyodbc not installed. Run: pip install pyodbc"
                )
            conn_str = (
                f"DRIVER={self._driver};"
                f"SERVER={self._host},{self._port};"
                f"DATABASE={self._database};"
                f"UID={self._user};"
                f"PWD={self._password}"
            )
            self._conn = pyodbc.connect(conn_str)
        return self._conn

    async def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        limit: Optional[int] = None,
    ) -> QueryResult:
        """Execute a SQL Server query."""
        start_time = time.time()

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Hoist WITH clauses out of subqueries — SQL Server forbids
            # CTEs inside FROM (...) subqueries, but the Python engine's
            # post-calc wrapper produces this pattern.
            sql = self._hoist_cte_from_subquery(sql)

            # Convert MySQL/PostgreSQL-style LIMIT/OFFSET to SQL Server syntax.
            # The Python semantic engine emits ``LIMIT N`` or ``LIMIT N OFFSET M``
            # as inline SQL, which is invalid T-SQL.
            sql, params = self._convert_limit_to_tsql(sql, params)

            # Executor-level limit (externally requested, e.g. preview mode)
            if limit and "TOP" not in sql.upper():
                sql = f"SELECT TOP {limit} * FROM ({sql}) AS _lim"

            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            # Get column names
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
            else:
                columns = []

            # Fetch rows as dicts
            raw_rows = cursor.fetchall()
            rows_data = [
                {col: val for col, val in zip(columns, row)}
                for row in raw_rows
            ]

            execution_time_ms = (time.time() - start_time) * 1000

            return QueryResult(
                columns=columns,
                rows=rows_data,
                total=len(rows_data),
                execution_time_ms=execution_time_ms,
                sql=sql,
            )

        except Exception as e:
            logger.error(f"SQL Server query failed: {e}")
            return QueryResult(
                error=str(e),
                sql=sql,
            )

    async def execute_count(
        self, sql: str, params: Optional[List[Any]] = None
    ) -> int:
        """Execute a COUNT query."""
        count_sql = f"SELECT COUNT(*) as cnt FROM ({sql}) as subq"

        result = await self.execute(count_sql, params)
        if result.error or not result.rows:
            return 0
        return result.rows[0].get("cnt", 0)

    @staticmethod
    def _hoist_cte_from_subquery(sql: str) -> str:
        """Hoist ``WITH`` clauses out of ``FROM (...)`` subqueries.

        The Python engine's post-calc wrapper generates SQL like::

            SELECT tw_result.*, (expr) AS "alias"
            FROM (
              WITH __time_window_base AS (...)
              SELECT ... FROM __time_window_base ...
            ) tw_result

        SQL Server does not allow CTEs inside subqueries.  This method
        rewrites the pattern to::

            WITH __time_window_base AS (...)
            SELECT tw_result.*, (expr) AS "alias"
            FROM (
              SELECT ... FROM __time_window_base ...
            ) tw_result
        """
        import re

        # Pattern: detect "FROM (\n  WITH <name> AS ("
        # We need to:
        # 1. Find the CTE definition inside the subquery
        # 2. Extract it
        # 3. Hoist it to the top of the SQL

        # Quick bail: if the top-level SQL already starts with WITH or
        # doesn't contain a nested WITH, no rewrite needed.
        stripped = sql.lstrip()
        if stripped.upper().startswith("WITH "):
            return sql
        if "WITH " not in sql.upper():
            return sql

        # Find "FROM (\n ... WITH" pattern
        # The post-calc wrapper uses "FROM (\n  WITH __time_window_base AS ("
        m = re.search(
            r"FROM\s*\(\s*\n?\s*(WITH\s+\w+\s+AS\s*\()",
            sql,
            re.IGNORECASE,
        )
        if not m:
            return sql

        # Find the CTE body: we need to match balanced parentheses
        cte_keyword_start = m.start(1)

        # Find "WITH <name> AS (" then find the matching ")"
        # Then find the end: ")\n  SELECT ..."
        # Strategy: find the CTE definition up to the SELECT that follows it
        cte_header_match = re.search(
            r"(WITH\s+\w+\s+AS\s*\()", sql[cte_keyword_start:], re.IGNORECASE
        )
        if not cte_header_match:
            return sql

        # Walk from the opening "(" to find its matching ")"
        paren_start = cte_keyword_start + cte_header_match.end() - 1
        depth = 1
        pos = paren_start + 1
        while pos < len(sql) and depth > 0:
            if sql[pos] == "(":
                depth += 1
            elif sql[pos] == ")":
                depth -= 1
            pos += 1
        if depth != 0:
            return sql  # Unbalanced — don't rewrite

        cte_end = pos  # position just after the closing ")" of the CTE body

        # Extract the CTE definition
        cte_def = sql[cte_keyword_start:cte_end].strip()

        # Now we need to find the closing ")" of the FROM (...) subquery
        # that contained the CTE. The subquery starts at the "(" after FROM.
        from_open_paren = m.start() + len("FROM") + sql[m.start() + len("FROM"):].index("(")
        # Walk from from_open_paren to find its match
        depth = 1
        pos = from_open_paren + 1
        while pos < len(sql) and depth > 0:
            if sql[pos] == "(":
                depth += 1
            elif sql[pos] == ")":
                depth -= 1
            pos += 1
        subquery_close = pos - 1  # the closing ")"

        # The inner SELECT (after the CTE) becomes the subquery content
        inner_select = sql[cte_end:subquery_close].strip()

        # The part before FROM (...) is the outer SELECT
        outer_before = sql[:m.start()].rstrip()

        # The part after the subquery closing ")" + alias
        outer_after = sql[subquery_close + 1:]

        # Reconstruct: CTE at top, then outer SELECT with inner SELECT as subquery
        rewritten = (
            f"{cte_def}\n"
            f"{outer_before}\n"
            f"FROM (\n  {inner_select}\n){outer_after}"
        )
        return rewritten

    @staticmethod
    def _convert_limit_to_tsql(
        sql: str, params: Optional[List[Any]]
    ) -> tuple:
        """Strip trailing ``LIMIT N [OFFSET M]`` and rewrite for T-SQL.

        The Python semantic engine emits LIMIT/OFFSET as inline integer
        literals (not bind params), so we parse them directly.

        CTE-based SQL (``WITH ... SELECT``) cannot be wrapped in a
        subquery on SQL Server, so we inject ``TOP N`` into the
        outermost ``SELECT`` instead.

        Returns (rewritten_sql, params) — params unchanged, limit/offset
        are absorbed into the SQL rewrite.
        """
        import re

        def _is_cte(s: str) -> bool:
            return s.lstrip().upper().startswith("WITH ")

        def _inject_top_into_select(base: str, limit_val: int) -> str:
            """Inject ``TOP N`` after the outermost SELECT keyword.

            For CTE queries, find the final SELECT after the CTE body.
            For simple queries, find the first SELECT.
            """
            if _is_cte(base):
                # Find the last top-level SELECT (the one after the CTE body)
                # Walk from the end to find SELECT that is NOT inside the CTE
                # A safe heuristic: find the last occurrence of SELECT that
                # follows a ')' + whitespace (end of CTE body).
                last_select = -1
                for match in re.finditer(r'\bSELECT\b', base, re.IGNORECASE):
                    last_select = match.start()
                if last_select >= 0:
                    insert_pos = last_select + len("SELECT")
                    return (
                        base[:insert_pos]
                        + f" TOP {limit_val}"
                        + base[insert_pos:]
                    )
            else:
                # Simple query: inject TOP after first SELECT
                m = re.search(r'\bSELECT\b', base, re.IGNORECASE)
                if m:
                    insert_pos = m.start() + len("SELECT")
                    return (
                        base[:insert_pos]
                        + f" TOP {limit_val}"
                        + base[insert_pos:]
                    )
            # Fallback: if we can't find SELECT, just strip LIMIT
            return base

        # Try LIMIT N OFFSET M first (more specific)
        m = re.search(
            r"\bLIMIT\s+(\d+)\s+OFFSET\s+(\d+)\s*$", sql, re.IGNORECASE
        )
        if m:
            limit_val, offset_val = int(m.group(1)), int(m.group(2))
            base = sql[: m.start()].rstrip()
            # OFFSET-FETCH requires ORDER BY; if missing, add a no-op
            if "ORDER BY" not in base.upper():
                base += "\nORDER BY (SELECT NULL)"
            return (
                f"{base}\nOFFSET {offset_val} ROWS FETCH NEXT {limit_val} ROWS ONLY",
                params,
            )

        # Try bare LIMIT N (inline literal)
        m = re.search(r"\bLIMIT\s+(\d+)\s*$", sql, re.IGNORECASE)
        if m:
            limit_val = int(m.group(1))
            base = sql[: m.start()].rstrip()
            return _inject_top_into_select(base, limit_val), params

        # Also handle LIMIT ? (bind-param form)
        m = re.search(r"\bLIMIT\s+\?\s*$", sql, re.IGNORECASE)
        if m and params:
            limit_val = params[-1]
            base = sql[: m.start()].rstrip()
            remaining_params = list(params[:-1])
            return (
                _inject_top_into_select(base, limit_val),
                remaining_params or None,
            )

        return sql, params

    async def close(self) -> None:
        """Close the connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


def create_executor_from_url(connection_url: str) -> DatabaseExecutor:
    """Create a database executor from a connection URL.

    Args:
        connection_url: Database connection URL

    Returns:
        DatabaseExecutor instance

    Example URLs:
        mysql://user:pass@host:port/database
        postgresql://user:pass@host:port/database
        sqlite:///path/to/database.db
    """
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(connection_url)
    scheme = parsed.scheme.lower()

    if scheme in ("mysql", "mysql+aiomysql"):
        return MySQLExecutor(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            database=parsed.path.lstrip("/"),
            user=parsed.username or "",
            password=parsed.password or "",
        )

    elif scheme in ("postgresql", "postgres", "postgresql+asyncpg"):
        return PostgreSQLExecutor(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/"),
            user=parsed.username or "",
            password=parsed.password or "",
        )

    elif scheme in ("sqlite", "sqlite+aiosqlite"):
        # sqlite:///path/to/db.db or sqlite:///:memory:
        db_path = parsed.path
        if db_path.startswith("/"):
            db_path = db_path[1:]  # Remove leading slash
        return SQLiteExecutor(database=db_path or ":memory:")

    elif scheme in ("mssql", "mssql+pyodbc"):
        return SQLServerExecutor(
            host=parsed.hostname or "localhost",
            port=parsed.port or 1433,
            database=parsed.path.lstrip("/"),
            user=parsed.username or "",
            password=parsed.password or "",
        )

    else:
        raise ValueError(f"Unsupported database scheme: {scheme}")


class ExecutorManager:
    """Manages multiple named DatabaseExecutor instances.

    Provides named lookup with default fallback, mirroring the
    DataSourceManager API pattern.
    """

    def __init__(self):
        """Initialize with empty executor registry."""
        self._executors: Dict[str, DatabaseExecutor] = {}
        self._default_name: Optional[str] = None

    def register(self, name: str, executor: DatabaseExecutor, set_default: bool = False) -> None:
        """Register a named executor.

        Args:
            name: Data source name
            executor: Database executor instance
            set_default: Whether to set as default (also auto-set if first registration)
        """
        self._executors[name] = executor
        if set_default or self._default_name is None:
            self._default_name = name

    def get(self, name: Optional[str] = None) -> Optional[DatabaseExecutor]:
        """Get executor by name, falling back to default.

        Args:
            name: Data source name (None for default)

        Returns:
            DatabaseExecutor or None if not found
        """
        if name and name in self._executors:
            return self._executors[name]
        if self._default_name:
            return self._executors.get(self._default_name)
        return None

    def get_default(self) -> Optional[DatabaseExecutor]:
        """Get the default executor."""
        return self.get(None)

    def list_names(self) -> List[str]:
        """List all registered executor names."""
        return list(self._executors.keys())

    async def close_all(self) -> None:
        """Close all registered executors."""
        for name, executor in self._executors.items():
            try:
                await executor.close()
                logger.info(f"Closed executor: {name}")
            except Exception as e:
                logger.warning(f"Error closing executor '{name}': {e}")
        self._executors.clear()
        self._default_name = None


__all__ = [
    "QueryResult",
    "DatabaseExecutor",
    "MySQLExecutor",
    "PostgreSQLExecutor",
    "SQLiteExecutor",
    "SQLServerExecutor",
    "ExecutorManager",
    "create_executor_from_url",
]
