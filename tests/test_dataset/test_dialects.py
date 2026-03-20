"""Tests for database dialect implementations.

Aligned with Java's DialectTest.java, DialectBuildFunctionCallTest.java,
and DialectFunctionTranslationTest.java.
"""

import pytest

from foggy.dataset.dialects.base import FDialect
from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset.dialects.postgres import PostgresDialect
from foggy.dataset.dialects.sqlite import SqliteDialect
from foggy.dataset.dialects.sqlserver import SqlServerDialect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mysql():
    return MySqlDialect()


@pytest.fixture
def postgres():
    return PostgresDialect()


@pytest.fixture
def sqlite():
    return SqliteDialect()


@pytest.fixture
def sqlserver():
    return SqlServerDialect()


ALL_DIALECT_CLASSES = [MySqlDialect, PostgresDialect, SqliteDialect, SqlServerDialect]


# ===========================================================================
# TestMySqlDialect
# ===========================================================================

class TestMySqlDialect:
    """MySQL dialect tests (~10 tests)."""

    def test_quote_identifier_simple(self, mysql):
        assert mysql.quote_identifier("users") == "`users`"

    def test_quote_identifier_reserved_word(self, mysql):
        assert mysql.quote_identifier("select") == "`select`"

    def test_quote_identifier_with_space(self, mysql):
        assert mysql.quote_identifier("my table") == "`my table`"

    def test_quote_char(self, mysql):
        assert mysql.quote_char == "`"

    def test_generate_paging_sql_limit_only(self, mysql):
        result = mysql.get_pagination_sql("SELECT * FROM t", limit=10)
        assert result == "SELECT * FROM t LIMIT 10"

    def test_generate_paging_sql_limit_offset(self, mysql):
        result = mysql.get_pagination_sql("SELECT * FROM t", offset=20, limit=10)
        assert result == "SELECT * FROM t LIMIT 20, 10"

    def test_generate_paging_sql_no_paging(self, mysql):
        result = mysql.get_pagination_sql("SELECT * FROM t")
        assert result == "SELECT * FROM t"

    def test_get_db_type(self, mysql):
        assert mysql.name == "mysql"

    def test_get_count_sql(self, mysql):
        result = mysql.get_count_sql("SELECT id, name FROM users")
        assert "COUNT(*)" in result
        assert "SELECT id, name FROM users" in result

    def test_get_table_exists_sql_no_schema(self, mysql):
        result = mysql.get_table_exists_sql("users")
        assert "information_schema.tables" in result
        assert "users" in result

    def test_get_table_exists_sql_with_schema(self, mysql):
        result = mysql.get_table_exists_sql("users", schema="mydb")
        assert "mydb" in result
        assert "users" in result

    def test_get_current_timestamp_sql(self, mysql):
        assert mysql.get_current_timestamp_sql() == "NOW()"

    def test_get_auto_increment_sql(self, mysql):
        assert mysql.get_auto_increment_sql() == "AUTO_INCREMENT"

    def test_get_string_concat_sql(self, mysql):
        result = mysql.get_string_concat_sql("a", "b", "c")
        assert result == "CONCAT(a, b, c)"

    def test_get_if_null_sql(self, mysql):
        result = mysql.get_if_null_sql("col1", "'default'")
        assert result == "IFNULL(col1, 'default')"

    def test_get_date_format_sql(self, mysql):
        result = mysql.get_date_format_sql("created_at", "%Y-%m-%d")
        assert result == "DATE_FORMAT(created_at, '%Y-%m-%d')"

    def test_get_random_sql(self, mysql):
        assert mysql.get_random_sql() == "RAND()"

    def test_get_json_extract_sql(self, mysql):
        result = mysql.get_json_extract_sql("data", "$.name")
        assert result == "JSON_EXTRACT(data, '$.name')"

    def test_supports_limit_offset(self, mysql):
        assert mysql.supports_limit_offset is True

    def test_supports_returning(self, mysql):
        assert mysql.supports_returning is False

    def test_supports_on_duplicate_key(self, mysql):
        assert mysql.supports_on_duplicate_key is True

    def test_supports_json_type(self, mysql):
        assert mysql.supports_json_type is True

    def test_supports_cte(self, mysql):
        assert mysql.supports_cte is True


# ===========================================================================
# TestPostgreSqlDialect
# ===========================================================================

class TestPostgreSqlDialect:
    """PostgreSQL dialect tests (~10 tests)."""

    def test_quote_identifier_simple(self, postgres):
        assert postgres.quote_identifier("users") == '"users"'

    def test_quote_identifier_reserved_word(self, postgres):
        assert postgres.quote_identifier("order") == '"order"'

    def test_quote_char(self, postgres):
        assert postgres.quote_char == '"'

    def test_generate_paging_sql_limit_only(self, postgres):
        result = postgres.get_pagination_sql("SELECT * FROM t", limit=10)
        assert result == "SELECT * FROM t LIMIT 10"

    def test_generate_paging_sql_limit_offset(self, postgres):
        result = postgres.get_pagination_sql("SELECT * FROM t", offset=5, limit=10)
        assert result == "SELECT * FROM t LIMIT 10 OFFSET 5"

    def test_generate_paging_sql_offset_only(self, postgres):
        result = postgres.get_pagination_sql("SELECT * FROM t", offset=5)
        assert result == "SELECT * FROM t OFFSET 5"

    def test_generate_paging_sql_no_paging(self, postgres):
        result = postgres.get_pagination_sql("SELECT * FROM t")
        assert result == "SELECT * FROM t"

    def test_get_db_type(self, postgres):
        assert postgres.name == "postgresql"

    def test_get_count_sql(self, postgres):
        result = postgres.get_count_sql("SELECT id FROM orders")
        assert "COUNT(*)" in result
        assert "SELECT id FROM orders" in result

    def test_get_table_exists_sql_default_schema(self, postgres):
        result = postgres.get_table_exists_sql("users")
        assert "public" in result
        assert "users" in result
        assert "information_schema.tables" in result

    def test_get_table_exists_sql_custom_schema(self, postgres):
        result = postgres.get_table_exists_sql("users", schema="myschema")
        assert "myschema" in result
        assert "users" in result

    def test_get_current_timestamp_sql(self, postgres):
        assert postgres.get_current_timestamp_sql() == "CURRENT_TIMESTAMP"

    def test_get_auto_increment_sql(self, postgres):
        assert postgres.get_auto_increment_sql() == "SERIAL"

    def test_get_string_concat_sql(self, postgres):
        result = postgres.get_string_concat_sql("a", "b", "c")
        assert result == "a || b || c"

    def test_get_if_null_sql(self, postgres):
        result = postgres.get_if_null_sql("col1", "0")
        assert result == "COALESCE(col1, 0)"

    def test_get_date_format_sql(self, postgres):
        result = postgres.get_date_format_sql("created_at", "YYYY-MM-DD")
        assert result == "TO_CHAR(created_at, 'YYYY-MM-DD')"

    def test_get_random_sql(self, postgres):
        assert postgres.get_random_sql() == "RANDOM()"

    def test_get_json_extract_sql(self, postgres):
        result = postgres.get_json_extract_sql("data", "$.name")
        assert "->>" in result

    def test_supports_returning(self, postgres):
        assert postgres.supports_returning is True

    def test_supports_on_duplicate_key(self, postgres):
        assert postgres.supports_on_duplicate_key is False


# ===========================================================================
# TestSqlServerDialect
# ===========================================================================

class TestSqlServerDialect:
    """SQL Server dialect tests (~10 tests)."""

    def test_quote_identifier_simple(self, sqlserver):
        assert sqlserver.quote_identifier("users") == "[users]"

    def test_quote_identifier_reserved_word(self, sqlserver):
        assert sqlserver.quote_identifier("select") == "[select]"

    def test_quote_char(self, sqlserver):
        assert sqlserver.quote_char == "[]"

    def test_generate_paging_sql_limit_only(self, sqlserver):
        result = sqlserver.get_pagination_sql(
            "SELECT * FROM t ORDER BY id", limit=10
        )
        assert "OFFSET 0 ROWS" in result
        assert "FETCH NEXT 10 ROWS ONLY" in result

    def test_generate_paging_sql_offset_and_limit(self, sqlserver):
        result = sqlserver.get_pagination_sql(
            "SELECT * FROM t ORDER BY id", offset=20, limit=10
        )
        assert "OFFSET 20 ROWS" in result
        assert "FETCH NEXT 10 ROWS ONLY" in result

    def test_generate_paging_sql_adds_order_by(self, sqlserver):
        """SQL Server requires ORDER BY for OFFSET/FETCH; dialect should add it."""
        result = sqlserver.get_pagination_sql("SELECT * FROM t", limit=10)
        assert "ORDER BY" in result.upper()

    def test_generate_paging_sql_no_paging(self, sqlserver):
        result = sqlserver.get_pagination_sql("SELECT * FROM t")
        assert result == "SELECT * FROM t"

    def test_get_db_type(self, sqlserver):
        assert sqlserver.name == "sqlserver"

    def test_get_count_sql(self, sqlserver):
        result = sqlserver.get_count_sql("SELECT id FROM orders")
        assert "COUNT(*)" in result

    def test_get_table_exists_sql_default_schema(self, sqlserver):
        result = sqlserver.get_table_exists_sql("users")
        assert "dbo" in result
        assert "users" in result

    def test_get_table_exists_sql_custom_schema(self, sqlserver):
        result = sqlserver.get_table_exists_sql("users", schema="myschema")
        assert "myschema" in result

    def test_get_current_timestamp_sql(self, sqlserver):
        assert sqlserver.get_current_timestamp_sql() == "GETDATE()"

    def test_get_auto_increment_sql(self, sqlserver):
        assert sqlserver.get_auto_increment_sql() == "IDENTITY(1,1)"

    def test_get_string_concat_sql(self, sqlserver):
        result = sqlserver.get_string_concat_sql("a", "b", "c")
        assert result == "a + b + c"

    def test_get_if_null_sql(self, sqlserver):
        result = sqlserver.get_if_null_sql("col1", "0")
        assert result == "ISNULL(col1, 0)"

    def test_get_date_format_sql(self, sqlserver):
        result = sqlserver.get_date_format_sql("created_at", "%Y-%m-%d")
        assert "CONVERT" in result

    def test_get_random_sql(self, sqlserver):
        assert sqlserver.get_random_sql() == "NEWID()"

    def test_get_json_extract_sql(self, sqlserver):
        result = sqlserver.get_json_extract_sql("data", "$.name")
        assert result == "JSON_VALUE(data, '$.name')"

    def test_supports_returning(self, sqlserver):
        assert sqlserver.supports_returning is True

    def test_supports_on_duplicate_key(self, sqlserver):
        assert sqlserver.supports_on_duplicate_key is False


# ===========================================================================
# TestSqliteDialect
# ===========================================================================

class TestSqliteDialect:
    """SQLite dialect tests (~10 tests)."""

    def test_quote_identifier_simple(self, sqlite):
        assert sqlite.quote_identifier("users") == '"users"'

    def test_quote_identifier_reserved_word(self, sqlite):
        assert sqlite.quote_identifier("table") == '"table"'

    def test_quote_char(self, sqlite):
        assert sqlite.quote_char == '"'

    def test_generate_paging_sql_limit_only(self, sqlite):
        result = sqlite.get_pagination_sql("SELECT * FROM t", limit=10)
        assert result == "SELECT * FROM t LIMIT 10"

    def test_generate_paging_sql_limit_offset(self, sqlite):
        result = sqlite.get_pagination_sql("SELECT * FROM t", offset=5, limit=10)
        assert result == "SELECT * FROM t LIMIT 10 OFFSET 5"

    def test_generate_paging_sql_no_paging(self, sqlite):
        result = sqlite.get_pagination_sql("SELECT * FROM t")
        assert result == "SELECT * FROM t"

    def test_get_db_type(self, sqlite):
        assert sqlite.name == "sqlite"

    def test_get_count_sql(self, sqlite):
        result = sqlite.get_count_sql("SELECT id FROM t")
        assert "COUNT(*)" in result

    def test_get_table_exists_sql(self, sqlite):
        result = sqlite.get_table_exists_sql("users")
        assert "sqlite_master" in result
        assert "users" in result

    def test_get_table_exists_sql_escapes_quotes(self, sqlite):
        """Table names with single quotes should be escaped."""
        result = sqlite.get_table_exists_sql("user's_table")
        assert "user''s_table" in result

    def test_get_current_timestamp_sql(self, sqlite):
        assert sqlite.get_current_timestamp_sql() == "CURRENT_TIMESTAMP"

    def test_get_auto_increment_sql(self, sqlite):
        assert sqlite.get_auto_increment_sql() == "AUTOINCREMENT"

    def test_get_string_concat_sql(self, sqlite):
        result = sqlite.get_string_concat_sql("a", "b")
        assert result == "a || b"

    def test_get_if_null_sql(self, sqlite):
        result = sqlite.get_if_null_sql("col1", "0")
        assert result == "IFNULL(col1, 0)"

    def test_get_date_format_sql(self, sqlite):
        result = sqlite.get_date_format_sql("created_at", "%Y-%m-%d")
        assert result == "strftime('%Y-%m-%d', created_at)"

    def test_get_random_sql(self, sqlite):
        assert sqlite.get_random_sql() == "RANDOM()"

    def test_get_json_extract_sql(self, sqlite):
        result = sqlite.get_json_extract_sql("data", "$.name")
        assert result == "json_extract(data, '$.name')"

    def test_supports_json_type(self, sqlite):
        assert sqlite.supports_json_type is False

    def test_supports_returning(self, sqlite):
        assert sqlite.supports_returning is False


# ===========================================================================
# TestDialectCommon
# ===========================================================================

class TestDialectCommon:
    """Cross-dialect common behaviour tests."""

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_all_dialects_instantiate(self, dialect_cls):
        dialect = dialect_cls()
        assert isinstance(dialect, FDialect)
        assert isinstance(dialect.name, str)
        assert len(dialect.name) > 0

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_quote_identifier_returns_string(self, dialect_cls):
        dialect = dialect_cls()
        result = dialect.quote_identifier("test_col")
        assert isinstance(result, str)
        assert "test_col" in result

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_empty_identifier_quoting(self, dialect_cls):
        """Quoting an empty string should still return a quoted result."""
        dialect = dialect_cls()
        result = dialect.quote_identifier("")
        assert isinstance(result, str)
        # The result should contain the quote characters even for empty input
        assert len(result) >= 2

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_get_count_sql_wraps_query(self, dialect_cls):
        dialect = dialect_cls()
        original = "SELECT id, name FROM users WHERE active = 1"
        result = dialect.get_count_sql(original)
        assert "COUNT(*)" in result
        assert original in result

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_pagination_no_args_returns_original(self, dialect_cls):
        dialect = dialect_cls()
        original = "SELECT * FROM t"
        result = dialect.get_pagination_sql(original)
        assert result == original

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_supports_cte(self, dialect_cls):
        """All four supported dialects support CTEs."""
        dialect = dialect_cls()
        assert dialect.supports_cte is True

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_get_create_table_sql(self, dialect_cls):
        dialect = dialect_cls()
        result = dialect.get_create_table_sql(
            "test_table",
            ["id INTEGER", "name VARCHAR(100)"],
            primary_keys=["id"],
        )
        assert "CREATE TABLE" in result
        assert "IF NOT EXISTS" in result
        assert "id INTEGER" in result

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_get_drop_table_sql(self, dialect_cls):
        dialect = dialect_cls()
        result = dialect.get_drop_table_sql("my_table")
        assert "DROP TABLE" in result
        assert "IF EXISTS" in result

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_get_insert_sql(self, dialect_cls):
        dialect = dialect_cls()
        result = dialect.get_insert_sql("users", ["id", "name"])
        assert "INSERT INTO" in result
        assert "VALUES" in result

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_get_delete_sql(self, dialect_cls):
        dialect = dialect_cls()
        result = dialect.get_delete_sql("users", "id = 1")
        assert "DELETE FROM" in result
        assert "WHERE id = 1" in result

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_quote_alias(self, dialect_cls):
        """quote() is an alias for quote_identifier()."""
        dialect = dialect_cls()
        assert dialect.quote("col") == dialect.quote_identifier("col")

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_needs_quote_for_reserved_word(self, dialect_cls):
        dialect = dialect_cls()
        assert dialect.needs_quote("select") is True
        assert dialect.needs_quote("from") is True

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_needs_quote_for_plain_word(self, dialect_cls):
        dialect = dialect_cls()
        assert dialect.needs_quote("username") is False

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_get_truncate_table_sql(self, dialect_cls):
        dialect = dialect_cls()
        result = dialect.get_truncate_table_sql("my_table")
        assert "TRUNCATE TABLE" in result

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    def test_get_update_sql(self, dialect_cls):
        dialect = dialect_cls()
        result = dialect.get_update_sql("users", ["name", "email"], "id = 1")
        assert "UPDATE" in result
        assert "SET" in result
        assert "WHERE id = 1" in result


# ===========================================================================
# TestFunctionTranslation
# ===========================================================================

class TestFunctionTranslation:
    """Tests for function name translation across dialects.

    These tests verify that each dialect's helper methods produce the
    correct function calls for cross-database function equivalences.
    Since translate_function() does not exist on the dialect classes,
    we test the concrete helper methods that achieve the same result.
    """

    # -----------------------------------------------------------------------
    # IFNULL / COALESCE / ISNULL equivalences
    # -----------------------------------------------------------------------

    def test_mysql_ifnull(self, mysql):
        """MySQL uses IFNULL."""
        result = mysql.get_if_null_sql("col", "0")
        assert result.startswith("IFNULL(")

    def test_postgres_ifnull_becomes_coalesce(self, postgres):
        """PostgreSQL uses COALESCE instead of IFNULL."""
        result = postgres.get_if_null_sql("col", "0")
        assert result.startswith("COALESCE(")

    def test_sqlserver_ifnull_becomes_isnull(self, sqlserver):
        """SQL Server uses ISNULL instead of IFNULL."""
        result = sqlserver.get_if_null_sql("col", "0")
        assert result.startswith("ISNULL(")

    def test_sqlite_ifnull(self, sqlite):
        """SQLite uses IFNULL."""
        result = sqlite.get_if_null_sql("col", "0")
        assert result.startswith("IFNULL(")

    # -----------------------------------------------------------------------
    # String concatenation equivalences
    # -----------------------------------------------------------------------

    def test_mysql_concat_function(self, mysql):
        """MySQL uses CONCAT() function."""
        result = mysql.get_string_concat_sql("a", "b")
        assert result == "CONCAT(a, b)"

    def test_postgres_concat_operator(self, postgres):
        """PostgreSQL uses || operator."""
        result = postgres.get_string_concat_sql("a", "b")
        assert result == "a || b"

    def test_sqlserver_concat_plus(self, sqlserver):
        """SQL Server uses + operator."""
        result = sqlserver.get_string_concat_sql("a", "b")
        assert result == "a + b"

    def test_sqlite_concat_operator(self, sqlite):
        """SQLite uses || operator."""
        result = sqlite.get_string_concat_sql("a", "b")
        assert result == "a || b"

    # -----------------------------------------------------------------------
    # Date formatting equivalences
    # -----------------------------------------------------------------------

    def test_mysql_date_format(self, mysql):
        result = mysql.get_date_format_sql("d", "%Y")
        assert "DATE_FORMAT" in result

    def test_postgres_date_format(self, postgres):
        result = postgres.get_date_format_sql("d", "YYYY")
        assert "TO_CHAR" in result

    def test_sqlserver_date_format(self, sqlserver):
        result = sqlserver.get_date_format_sql("d", "%Y-%m-%d")
        assert "CONVERT" in result

    def test_sqlite_date_format(self, sqlite):
        result = sqlite.get_date_format_sql("d", "%Y")
        assert "strftime" in result

    # -----------------------------------------------------------------------
    # Current timestamp equivalences
    # -----------------------------------------------------------------------

    def test_mysql_current_timestamp(self, mysql):
        assert mysql.get_current_timestamp_sql() == "NOW()"

    def test_postgres_current_timestamp(self, postgres):
        assert postgres.get_current_timestamp_sql() == "CURRENT_TIMESTAMP"

    def test_sqlserver_current_timestamp(self, sqlserver):
        assert sqlserver.get_current_timestamp_sql() == "GETDATE()"

    def test_sqlite_current_timestamp(self, sqlite):
        assert sqlite.get_current_timestamp_sql() == "CURRENT_TIMESTAMP"

    # -----------------------------------------------------------------------
    # Random function equivalences
    # -----------------------------------------------------------------------

    def test_mysql_random(self, mysql):
        assert mysql.get_random_sql() == "RAND()"

    def test_postgres_random(self, postgres):
        assert postgres.get_random_sql() == "RANDOM()"

    def test_sqlserver_random(self, sqlserver):
        assert sqlserver.get_random_sql() == "NEWID()"

    def test_sqlite_random(self, sqlite):
        assert sqlite.get_random_sql() == "RANDOM()"

    # -----------------------------------------------------------------------
    # JSON extract equivalences
    # -----------------------------------------------------------------------

    def test_mysql_json_extract(self, mysql):
        result = mysql.get_json_extract_sql("j", "$.key")
        assert "JSON_EXTRACT" in result

    def test_postgres_json_extract(self, postgres):
        result = postgres.get_json_extract_sql("j", "$.key")
        assert "->>" in result

    def test_sqlserver_json_extract(self, sqlserver):
        result = sqlserver.get_json_extract_sql("j", "$.key")
        assert "JSON_VALUE" in result

    def test_sqlite_json_extract(self, sqlite):
        result = sqlite.get_json_extract_sql("j", "$.key")
        assert "json_extract" in result

    # -----------------------------------------------------------------------
    # translate_function stub tests (method not yet implemented)
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("dialect_cls", ALL_DIALECT_CLASSES)
    @pytest.mark.xfail(reason="translate_function() not yet implemented", strict=True)
    def test_translate_function_not_implemented(self, dialect_cls):
        """translate_function() should raise NotImplementedError until implemented."""
        dialect = dialect_cls()
        dialect.translate_function("NVL", ["col", "0"])

    @pytest.mark.xfail(reason="translate_function() not yet implemented", strict=True)
    def test_mysql_nvl_to_ifnull(self, mysql):
        result = mysql.translate_function("NVL", ["col", "0"])
        assert result == "IFNULL(col, 0)"

    @pytest.mark.xfail(reason="translate_function() not yet implemented", strict=True)
    def test_postgres_ifnull_to_coalesce(self, postgres):
        result = postgres.translate_function("IFNULL", ["col", "0"])
        assert result == "COALESCE(col, 0)"

    @pytest.mark.xfail(reason="translate_function() not yet implemented", strict=True)
    def test_sqlserver_ifnull_to_isnull(self, sqlserver):
        result = sqlserver.translate_function("IFNULL", ["col", "0"])
        assert result == "ISNULL(col, 0)"

    @pytest.mark.xfail(reason="translate_function() not yet implemented", strict=True)
    def test_sqlserver_length_to_len(self, sqlserver):
        result = sqlserver.translate_function("LENGTH", ["col"])
        assert result == "LEN(col)"

    @pytest.mark.xfail(reason="translate_function() not yet implemented", strict=True)
    def test_sqlite_nvl_to_ifnull(self, sqlite):
        result = sqlite.translate_function("NVL", ["col", "0"])
        assert result == "IFNULL(col, 0)"

    @pytest.mark.xfail(reason="translate_function() not yet implemented", strict=True)
    def test_postgres_substr_stays(self, postgres):
        result = postgres.translate_function("SUBSTR", ["col", "1", "3"])
        assert result == "SUBSTR(col, 1, 3)"


# ===========================================================================
# TestDialectSpecificSQL
# ===========================================================================

class TestDialectSpecificSQL:
    """Tests for dialect-specific SQL generation methods."""

    def test_mysql_insert_on_duplicate_key(self, mysql):
        result = mysql.get_insert_on_duplicate_key_update_sql(
            "users", ["id", "name", "email"], update_columns=["name", "email"]
        )
        assert "ON DUPLICATE KEY UPDATE" in result
        assert "VALUES(`name`)" in result
        assert "VALUES(`email`)" in result

    def test_mysql_insert_on_duplicate_key_default_update_cols(self, mysql):
        result = mysql.get_insert_on_duplicate_key_update_sql(
            "users", ["id", "name", "email"]
        )
        assert "ON DUPLICATE KEY UPDATE" in result
        # Default: update all columns except the first (id)
        assert "`name`" in result
        assert "`email`" in result

    def test_postgres_insert_on_conflict_update(self, postgres):
        result = postgres.get_insert_on_conflict_sql(
            "users",
            ["id", "name", "email"],
            conflict_columns=["id"],
            update_columns=["name", "email"],
            values_placeholder="%s",
        )
        assert "ON CONFLICT" in result
        assert "DO UPDATE SET" in result
        assert "EXCLUDED" in result

    def test_postgres_insert_on_conflict_do_nothing(self, postgres):
        result = postgres.get_insert_on_conflict_sql(
            "users",
            ["id"],
            conflict_columns=["id"],
            update_columns=[],
            values_placeholder="%s",
        )
        assert "DO NOTHING" in result

    def test_sqlserver_insert_with_output(self, sqlserver):
        result = sqlserver.get_insert_with_output_sql(
            "users", ["id", "name"], output_columns=["id"]
        )
        assert "OUTPUT" in result
        assert "INSERTED.[id]" in result

    def test_sqlserver_top_sql(self, sqlserver):
        result = sqlserver.get_top_sql("SELECT * FROM users", 10)
        assert "TOP 10" in result
        assert result.startswith("SELECT TOP 10")

    def test_sqlite_insert_or_replace(self, sqlite):
        result = sqlite.get_insert_or_replace_sql("users", ["id", "name"])
        assert "INSERT OR REPLACE INTO" in result

    def test_sqlite_insert_or_ignore(self, sqlite):
        result = sqlite.get_insert_or_ignore_sql("users", ["id", "name"])
        assert "INSERT OR IGNORE INTO" in result

    def test_sqlite_create_table_composite_pk(self, sqlite):
        result = sqlite.get_create_table_sql(
            "mapping",
            ["user_id INTEGER", "role_id INTEGER"],
            primary_keys=["user_id", "role_id"],
        )
        assert "PRIMARY KEY" in result
        assert '"user_id"' in result
        assert '"role_id"' in result

    def test_sqlite_create_table_single_pk_no_explicit_constraint(self, sqlite):
        """SQLite with a single PK should not add a separate PRIMARY KEY clause
        (single-column PKs are declared inline with the column)."""
        result = sqlite.get_create_table_sql(
            "users",
            ["id INTEGER PRIMARY KEY", "name TEXT"],
            primary_keys=["id"],
        )
        # Single PK: SQLite override skips the separate constraint (len == 1)
        count = result.upper().count("PRIMARY KEY")
        # The column definition already has PRIMARY KEY; the SQLite override
        # only adds the constraint for composite (len > 1).
        assert count == 1
