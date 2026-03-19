"""Unit tests for database dialects."""

import pytest
from foggy.dataset import DbType, TypeNames
from foggy.dataset.dialects import (
    FDialect,
    MySqlDialect,
    PostgresDialect,
    SqliteDialect,
    SqlServerDialect,
)


class TestDbType:
    """Tests for DbType enumeration."""

    def test_all_database_types(self):
        """Test all database types exist."""
        assert DbType.MYSQL.value == "mysql"
        assert DbType.POSTGRESQL.value == "postgresql"
        assert DbType.SQLITE.value == "sqlite"
        assert DbType.SQLSERVER.value == "sqlserver"
        assert DbType.ORACLE.value == "oracle"
        assert DbType.MONGODB.value == "mongodb"

    def test_is_relational(self):
        """Test is_relational property."""
        assert DbType.MYSQL.is_relational
        assert DbType.POSTGRESQL.is_relational
        assert DbType.SQLITE.is_relational
        assert DbType.SQLSERVER.is_relational
        assert DbType.ORACLE.is_relational
        assert not DbType.MONGODB.is_relational

    def test_is_nosql(self):
        """Test is_nosql property."""
        assert DbType.MONGODB.is_nosql
        assert not DbType.MYSQL.is_nosql
        assert not DbType.POSTGRESQL.is_nosql

    def test_from_driver_mysql(self):
        """Test detecting MySQL from driver."""
        assert DbType.from_driver("com.mysql.cj.jdbc.Driver") == DbType.MYSQL
        assert DbType.from_driver("mysql") == DbType.MYSQL

    def test_from_driver_postgres(self):
        """Test detecting PostgreSQL from driver."""
        assert DbType.from_driver("org.postgresql.Driver") == DbType.POSTGRESQL
        assert DbType.from_driver("pgsql") == DbType.POSTGRESQL

    def test_from_driver_sqlite(self):
        """Test detecting SQLite from driver."""
        assert DbType.from_driver("sqlite") == DbType.SQLITE
        assert DbType.from_driver("SQLite.JDBCDriver") == DbType.SQLITE

    def test_from_driver_sqlserver(self):
        """Test detecting SQL Server from driver."""
        assert DbType.from_driver("com.microsoft.sqlserver.jdbc.SQLServerDriver") == DbType.SQLSERVER
        assert DbType.from_driver("mssql") == DbType.SQLSERVER

    def test_from_driver_mongodb(self):
        """Test detecting MongoDB from driver."""
        assert DbType.from_driver("mongodb") == DbType.MONGODB
        assert DbType.from_driver("mongo") == DbType.MONGODB

    def test_from_driver_unknown(self):
        """Test unknown driver raises error."""
        with pytest.raises(ValueError):
            DbType.from_driver("unknown.driver")

    def test_from_url_mysql(self):
        """Test detecting MySQL from URL."""
        assert DbType.from_url("jdbc:mysql://localhost:3306/db") == DbType.MYSQL
        assert DbType.from_url("mysql://localhost/db") == DbType.MYSQL

    def test_from_url_postgres(self):
        """Test detecting PostgreSQL from URL."""
        assert DbType.from_url("jdbc:postgresql://localhost:5432/db") == DbType.POSTGRESQL
        assert DbType.from_url("postgres://localhost/db") == DbType.POSTGRESQL

    def test_from_url_sqlite(self):
        """Test detecting SQLite from URL."""
        assert DbType.from_url("jdbc:sqlite:/path/to/db.sqlite") == DbType.SQLITE
        assert DbType.from_url("sqlite:///db.sqlite") == DbType.SQLITE

    def test_from_url_sqlserver(self):
        """Test detecting SQL Server from URL."""
        assert DbType.from_url("jdbc:sqlserver://localhost:1433") == DbType.SQLSERVER
        assert DbType.from_url("mssql://localhost/db") == DbType.SQLSERVER

    def test_from_url_mongodb(self):
        """Test detecting MongoDB from URL."""
        assert DbType.from_url("mongodb://localhost:27017/db") == DbType.MONGODB
        assert DbType.from_url("mongo://localhost/db") == DbType.MONGODB

    def test_from_url_unknown(self):
        """Test unknown URL raises error."""
        with pytest.raises(ValueError):
            DbType.from_url("unknown://localhost/db")


class TestTypeNames:
    """Tests for TypeNames mappings."""

    def test_standard_type_names(self):
        """Test standard type name constants."""
        assert TypeNames.VARCHAR == "VARCHAR"
        assert TypeNames.INTEGER == "INTEGER"
        assert TypeNames.TEXT == "TEXT"
        assert TypeNames.BIGINT == "BIGINT"
        assert TypeNames.BOOLEAN == "BOOLEAN"
        assert TypeNames.DATE == "DATE"
        assert TypeNames.DATETIME == "DATETIME"

    def test_mysql_type_mapping(self):
        """Test MySQL type mappings."""
        assert TypeNames.get_type_name(DbType.MYSQL, "VARCHAR") == "VARCHAR"
        assert TypeNames.get_type_name(DbType.MYSQL, "INTEGER") == "INT"
        assert TypeNames.get_type_name(DbType.MYSQL, "BOOLEAN") == "TINYINT(1)"
        assert TypeNames.get_type_name(DbType.MYSQL, "BLOB") == "BLOB"

    def test_postgres_type_mapping(self):
        """Test PostgreSQL type mappings."""
        assert TypeNames.get_type_name(DbType.POSTGRESQL, "VARCHAR") == "VARCHAR"
        assert TypeNames.get_type_name(DbType.POSTGRESQL, "INTEGER") == "INTEGER"
        assert TypeNames.get_type_name(DbType.POSTGRESQL, "BLOB") == "BYTEA"
        assert TypeNames.get_type_name(DbType.POSTGRESQL, "JSON") == "JSONB"

    def test_sqlite_type_mapping(self):
        """Test SQLite type mappings."""
        assert TypeNames.get_type_name(DbType.SQLITE, "VARCHAR") == "TEXT"
        assert TypeNames.get_type_name(DbType.SQLITE, "INTEGER") == "INTEGER"
        assert TypeNames.get_type_name(DbType.SQLITE, "BOOLEAN") == "INTEGER"
        assert TypeNames.get_type_name(DbType.SQLITE, "JSON") == "TEXT"

    def test_sqlserver_type_mapping(self):
        """Test SQL Server type mappings."""
        assert TypeNames.get_type_name(DbType.SQLSERVER, "VARCHAR") == "NVARCHAR"
        assert TypeNames.get_type_name(DbType.SQLSERVER, "INTEGER") == "INT"
        assert TypeNames.get_type_name(DbType.SQLSERVER, "BOOLEAN") == "BIT"
        assert TypeNames.get_type_name(DbType.SQLSERVER, "TEXT") == "NVARCHAR(MAX)"

    def test_unknown_type_fallback(self):
        """Test unknown type returns original."""
        assert TypeNames.get_type_name(DbType.MYSQL, "CUSTOM_TYPE") == "CUSTOM_TYPE"


class TestMySqlDialect:
    """Tests for MySQL dialect."""

    @pytest.fixture
    def dialect(self):
        return MySqlDialect()

    def test_name(self, dialect):
        assert dialect.name == "mysql"

    def test_quote_identifier(self, dialect):
        assert dialect.quote_identifier("table") == "`table`"
        assert dialect.quote_identifier("column_name") == "`column_name`"

    def test_supports_properties(self, dialect):
        assert dialect.supports_limit_offset
        assert dialect.supports_json_type
        assert dialect.supports_cte
        assert not dialect.supports_returning

    def test_pagination_sql(self, dialect):
        sql = "SELECT * FROM users"
        assert dialect.get_pagination_sql(sql, limit=10) == "SELECT * FROM users LIMIT 10"
        assert dialect.get_pagination_sql(sql, limit=10, offset=20) == "SELECT * FROM users LIMIT 20, 10"

    def test_count_sql(self, dialect):
        sql = "SELECT * FROM users WHERE active = 1"
        assert "COUNT" in dialect.get_count_sql(sql)

    def test_current_timestamp(self, dialect):
        assert dialect.get_current_timestamp_sql() == "NOW()"

    def test_string_concat(self, dialect):
        result = dialect.get_string_concat_sql("a", "b", "c")
        assert "CONCAT" in result
        assert "a" in result and "b" in result

    def test_if_null(self, dialect):
        assert dialect.get_if_null_sql("col", "'default'") == "IFNULL(col, 'default')"

    def test_insert_sql(self, dialect):
        result = dialect.get_insert_sql("users", ["id", "name", "email"])
        assert "INSERT INTO" in result
        assert "`users`" in result
        assert "`id`" in result
        assert "VALUES" in result


class TestPostgresDialect:
    """Tests for PostgreSQL dialect."""

    @pytest.fixture
    def dialect(self):
        return PostgresDialect()

    def test_name(self, dialect):
        assert dialect.name == "postgresql"

    def test_quote_identifier(self, dialect):
        assert dialect.quote_identifier("table") == '"table"'

    def test_supports_properties(self, dialect):
        assert dialect.supports_limit_offset
        assert dialect.supports_returning
        assert dialect.supports_json_type
        assert dialect.supports_cte

    def test_pagination_sql(self, dialect):
        sql = "SELECT * FROM users"
        assert "LIMIT 10" in dialect.get_pagination_sql(sql, limit=10)
        assert "OFFSET 20" in dialect.get_pagination_sql(sql, limit=10, offset=20)

    def test_current_timestamp(self, dialect):
        assert dialect.get_current_timestamp_sql() == "CURRENT_TIMESTAMP"

    def test_string_concat(self, dialect):
        result = dialect.get_string_concat_sql("a", "b")
        assert result == "a || b"

    def test_if_null(self, dialect):
        assert dialect.get_if_null_sql("col", "0") == "COALESCE(col, 0)"

    def test_upsert_sql(self, dialect):
        result = dialect.get_upsert_sql("users", ["id", "name"], ["id"])
        assert "INSERT INTO" in result
        assert "ON CONFLICT" in result
        assert "DO UPDATE" in result


class TestSqliteDialect:
    """Tests for SQLite dialect."""

    @pytest.fixture
    def dialect(self):
        return SqliteDialect()

    def test_name(self, dialect):
        assert dialect.name == "sqlite"

    def test_quote_identifier(self, dialect):
        assert dialect.quote_identifier("table") == '"table"'

    def test_supports_properties(self, dialect):
        assert dialect.supports_limit_offset
        assert dialect.supports_cte
        assert not dialect.supports_returning
        assert not dialect.supports_json_type

    def test_pagination_sql(self, dialect):
        sql = "SELECT * FROM users"
        assert "LIMIT 10" in dialect.get_pagination_sql(sql, limit=10)

    def test_current_timestamp(self, dialect):
        assert dialect.get_current_timestamp_sql() == "CURRENT_TIMESTAMP"

    def test_string_concat(self, dialect):
        result = dialect.get_string_concat_sql("a", "b")
        assert result == "a || b"

    def test_if_null(self, dialect):
        assert dialect.get_if_null_sql("col", "0") == "IFNULL(col, 0)"

    def test_insert_or_replace(self, dialect):
        result = dialect.get_insert_or_replace_sql("users", ["id", "name"])
        assert "INSERT OR REPLACE" in result


class TestSqlServerDialect:
    """Tests for SQL Server dialect."""

    @pytest.fixture
    def dialect(self):
        return SqlServerDialect()

    def test_name(self, dialect):
        assert dialect.name == "sqlserver"

    def test_quote_identifier(self, dialect):
        assert dialect.quote_identifier("table") == "[table]"

    def test_supports_properties(self, dialect):
        assert dialect.supports_limit_offset
        assert dialect.supports_returning
        assert dialect.supports_cte
        assert not dialect.supports_json_type

    def test_pagination_sql(self, dialect):
        sql = "SELECT * FROM users ORDER BY id"
        result = dialect.get_pagination_sql(sql, limit=10, offset=20)
        assert "OFFSET 20 ROWS" in result
        assert "FETCH NEXT 10 ROWS ONLY" in result

    def test_current_timestamp(self, dialect):
        assert dialect.get_current_timestamp_sql() == "GETDATE()"

    def test_string_concat(self, dialect):
        result = dialect.get_string_concat_sql("a", "b")
        assert result == "a + b"

    def test_if_null(self, dialect):
        assert dialect.get_if_null_sql("col", "0") == "ISNULL(col, 0)"

    def test_top_sql(self, dialect):
        result = dialect.get_top_sql("SELECT * FROM users", 10)
        assert "TOP 10" in result


class TestDialectBaseMethods:
    """Tests for FDialect base class methods."""

    @pytest.fixture
    def dialect(self):
        return MySqlDialect()

    def test_create_table_sql(self, dialect):
        result = dialect.get_create_table_sql(
            "users",
            ["id INT", "name VARCHAR(100)"],
            ["id"],
            if_not_exists=True,
        )
        assert "CREATE TABLE IF NOT EXISTS" in result
        assert "PRIMARY KEY" in result

    def test_drop_table_sql(self, dialect):
        result = dialect.get_drop_table_sql("users")
        assert "DROP TABLE IF EXISTS" in result

    def test_truncate_table_sql(self, dialect):
        result = dialect.get_truncate_table_sql("users")
        assert "TRUNCATE TABLE" in result

    def test_update_sql(self, dialect):
        result = dialect.get_update_sql("users", ["name", "email"], "id = ?")
        assert "UPDATE" in result
        assert "SET" in result
        assert "WHERE" in result

    def test_delete_sql(self, dialect):
        result = dialect.get_delete_sql("users", "id = ?")
        assert "DELETE FROM" in result
        assert "WHERE" in result