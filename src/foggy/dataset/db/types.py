"""Database type enumeration and type name mappings."""

from enum import Enum
from typing import Dict


class DbType(Enum):
    """Database type enumeration."""

    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"
    MONGODB = "mongodb"

    @property
    def is_relational(self) -> bool:
        """Check if database is relational."""
        return self in (
            DbType.MYSQL,
            DbType.POSTGRESQL,
            DbType.SQLITE,
            DbType.SQLSERVER,
            DbType.ORACLE,
        )

    @property
    def is_nosql(self) -> bool:
        """Check if database is NoSQL."""
        return self == DbType.MONGODB

    @classmethod
    def from_driver(cls, driver: str) -> "DbType":
        """Detect database type from driver class name."""
        driver_lower = driver.lower()

        if "mysql" in driver_lower:
            return cls.MYSQL
        if "postgres" in driver_lower or "pgsql" in driver_lower:
            return cls.POSTGRESQL
        if "sqlite" in driver_lower:
            return cls.SQLITE
        if "sqlserver" in driver_lower or "mssql" in driver_lower:
            return cls.SQLSERVER
        if "oracle" in driver_lower:
            return cls.ORACLE
        if "mongo" in driver_lower:
            return cls.MONGODB

        raise ValueError(f"Unknown database driver: {driver}")

    @classmethod
    def from_url(cls, url: str) -> "DbType":
        """Detect database type from JDBC URL or connection string."""
        url_lower = url.lower()

        if "mysql" in url_lower:
            return cls.MYSQL
        if "postgres" in url_lower or "pgsql" in url_lower:
            return cls.POSTGRESQL
        if "sqlite" in url_lower:
            return cls.SQLITE
        if "sqlserver" in url_lower or "mssql" in url_lower:
            return cls.SQLSERVER
        if "oracle" in url_lower:
            return cls.ORACLE
        if "mongo" in url_lower:
            return cls.MONGODB

        raise ValueError(f"Cannot determine database type from URL: {url}")


class TypeNames:
    """SQL type name mappings for different databases."""

    # Standard SQL type names
    VARCHAR = "VARCHAR"
    CHAR = "CHAR"
    TEXT = "TEXT"
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    SMALLINT = "SMALLINT"
    DECIMAL = "DECIMAL"
    NUMERIC = "NUMERIC"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIME = "TIME"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"
    BLOB = "BLOB"
    CLOB = "CLOB"
    JSON = "JSON"
    UUID = "UUID"

    # Type mappings by database
    MAPPINGS: Dict[DbType, Dict[str, str]] = {
        DbType.MYSQL: {
            "VARCHAR": "VARCHAR",
            "TEXT": "TEXT",
            "INTEGER": "INT",
            "BIGINT": "BIGINT",
            "DECIMAL": "DECIMAL",
            "FLOAT": "FLOAT",
            "DOUBLE": "DOUBLE",
            "BOOLEAN": "TINYINT(1)",
            "DATE": "DATE",
            "DATETIME": "DATETIME",
            "TIMESTAMP": "TIMESTAMP",
            "BLOB": "BLOB",
            "JSON": "JSON",
        },
        DbType.POSTGRESQL: {
            "VARCHAR": "VARCHAR",
            "TEXT": "TEXT",
            "INTEGER": "INTEGER",
            "BIGINT": "BIGINT",
            "DECIMAL": "NUMERIC",
            "FLOAT": "REAL",
            "DOUBLE": "DOUBLE PRECISION",
            "BOOLEAN": "BOOLEAN",
            "DATE": "DATE",
            "DATETIME": "TIMESTAMP",
            "TIMESTAMP": "TIMESTAMP",
            "BLOB": "BYTEA",
            "JSON": "JSONB",
            "UUID": "UUID",
        },
        DbType.SQLITE: {
            "VARCHAR": "TEXT",
            "TEXT": "TEXT",
            "INTEGER": "INTEGER",
            "BIGINT": "INTEGER",
            "DECIMAL": "REAL",
            "FLOAT": "REAL",
            "DOUBLE": "REAL",
            "BOOLEAN": "INTEGER",
            "DATE": "TEXT",
            "DATETIME": "TEXT",
            "TIMESTAMP": "TEXT",
            "BLOB": "BLOB",
            "JSON": "TEXT",
        },
        DbType.SQLSERVER: {
            "VARCHAR": "NVARCHAR",
            "TEXT": "NVARCHAR(MAX)",
            "INTEGER": "INT",
            "BIGINT": "BIGINT",
            "DECIMAL": "DECIMAL",
            "FLOAT": "FLOAT",
            "DOUBLE": "FLOAT",
            "BOOLEAN": "BIT",
            "DATE": "DATE",
            "DATETIME": "DATETIME2",
            "TIMESTAMP": "DATETIME2",
            "BLOB": "VARBINARY(MAX)",
            "JSON": "NVARCHAR(MAX)",
        },
    }

    @classmethod
    def get_type_name(cls, db_type: DbType, standard_type: str) -> str:
        """Get database-specific type name for a standard type.

        Args:
            db_type: Target database type
            standard_type: Standard SQL type name

        Returns:
            Database-specific type name
        """
        if db_type not in cls.MAPPINGS:
            return standard_type

        db_mappings = cls.MAPPINGS[db_type]
        return db_mappings.get(standard_type, standard_type)