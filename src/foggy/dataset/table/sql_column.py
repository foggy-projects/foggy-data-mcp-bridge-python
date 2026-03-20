"""SQL Column definition for foggy-dataset.

This module provides the SqlColumn class for defining database column
properties including type, length, nullable, and default values.
"""

from enum import IntEnum
from typing import Any, Callable, Dict, Optional

from pydantic import Field

from foggy.dataset.db.sql_object import DbObjectType, SqlObject
from foggy.dataset.dialects.base import FDialect


class JdbcType(IntEnum):
    """JDBC type constants mapped from java.sql.Types."""

    # Character types
    CHAR = 1
    VARCHAR = 12
    LONGVARCHAR = -1
    NCHAR = -15
    NVARCHAR = -9
    LONGNVARCHAR = -16
    CLOB = 2005
    NCLOB = 2011

    # Boolean types
    BIT = -7
    BOOLEAN = 16

    # Integer types
    TINYINT = -6
    SMALLINT = 5
    INTEGER = 4
    BIGINT = -5

    # Decimal types
    FLOAT = 6
    REAL = 7
    DOUBLE = 8
    NUMERIC = 2
    DECIMAL = 3

    # Date/Time types
    DATE = 91
    TIME = 92
    TIMESTAMP = 93
    TIME_WITH_TIMEZONE = 2013
    TIMESTAMP_WITH_TIMEZONE = 2014

    # Binary types
    BINARY = -2
    VARBINARY = -3
    LONGVARBINARY = -4
    BLOB = 2004

    # Other types
    NULL = 0
    OTHER = 1111
    JAVA_OBJECT = 2000


# Type name to JDBC type mapping
TYPE_NAME_TO_JDBC: Dict[str, JdbcType] = {
    # Character types
    "VARCHAR": JdbcType.VARCHAR,
    "CHAR": JdbcType.CHAR,
    "NVARCHAR": JdbcType.NVARCHAR,
    "NCHAR": JdbcType.NCHAR,
    "TEXT": JdbcType.LONGVARCHAR,
    "LONGTEXT": JdbcType.LONGVARCHAR,
    "CLOB": JdbcType.CLOB,
    "NCLOB": JdbcType.NCLOB,
    # Boolean types
    "BIT": JdbcType.BIT,
    "BOOLEAN": JdbcType.BOOLEAN,
    "BOOL": JdbcType.BOOLEAN,
    # Integer types
    "TINYINT": JdbcType.TINYINT,
    "SMALLINT": JdbcType.SMALLINT,
    "INTEGER": JdbcType.INTEGER,
    "INT": JdbcType.INTEGER,
    "BIGINT": JdbcType.BIGINT,
    # Decimal types
    "NUMERIC": JdbcType.NUMERIC,
    "DECIMAL": JdbcType.DECIMAL,
    "NUMBER": JdbcType.DECIMAL,
    # Float types
    "FLOAT": JdbcType.FLOAT,
    "REAL": JdbcType.REAL,
    "DOUBLE": JdbcType.DOUBLE,
    # Date/Time types
    "DATE": JdbcType.DATE,
    "TIME": JdbcType.TIME,
    "TIMESTAMP": JdbcType.TIMESTAMP,
    "DATETIME": JdbcType.TIMESTAMP,
    # Binary types
    "BINARY": JdbcType.BINARY,
    "VARBINARY": JdbcType.VARBINARY,
    "BLOB": JdbcType.BLOB,
    "LONGBLOB": JdbcType.BLOB,
    # Other types
    "JSON": JdbcType.OTHER,
    "OBJECT": JdbcType.JAVA_OBJECT,
}

DEFAULT_PRECISION = 19
DEFAULT_SCALE = 2


class SqlColumnType:
    """Column type enumeration for convenience."""

    VARCHAR = "VARCHAR"
    CHAR = "CHAR"
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    DECIMAL = "DECIMAL"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIME = "TIME"
    TIMESTAMP = "TIMESTAMP"
    TEXT = "TEXT"
    BLOB = "BLOB"
    JSON = "JSON"


def get_jdbc_type_from_name(type_name: str) -> JdbcType:
    """Get JDBC type from type name.

    Args:
        type_name: SQL type name (e.g., 'VARCHAR', 'INTEGER')

    Returns:
        JdbcType enum value

    Raises:
        ValueError: If type name is not recognized
    """
    jdbc_type = TYPE_NAME_TO_JDBC.get(type_name.upper())
    if jdbc_type is None:
        raise ValueError(
            f"Unknown type name: {type_name}. "
            f"Supported types: {list(TYPE_NAME_TO_JDBC.keys())}"
        )
    return jdbc_type


class SqlColumn(SqlObject):
    """SQL Column definition.

    Represents a column in a database table with its properties
    including type, length, nullable flag, and default value.

    Attributes:
        caption: Column display name/description
        type_name: SQL type name (VARCHAR, INTEGER, etc.)
        jdbc_type: JDBC type constant
        length: Column length (for string types)
        precision: Numeric precision
        scale: Numeric scale
        nullable: Whether column allows NULL
        default_value: Default value expression
        primary_key: Whether this is a primary key
        auto_increment: Whether column auto-increments
    """

    caption: Optional[str] = Field(default=None, description="Column caption")
    type_name: str = Field(default="VARCHAR", description="SQL type name")
    jdbc_type: JdbcType = Field(default=JdbcType.VARCHAR, description="JDBC type")
    length: int = Field(default=0, description="Column length")
    precision: int = Field(default=DEFAULT_PRECISION, description="Numeric precision")
    scale: int = Field(default=DEFAULT_SCALE, description="Numeric scale")
    nullable: bool = Field(default=True, description="Allow NULL values")
    default_value: Optional[str] = Field(default=None, description="Default value")
    primary_key: bool = Field(default=False, description="Is primary key")
    auto_increment: bool = Field(default=False, description="Auto increment")

    # Formatter function for value conversion
    _formatter: Optional[Callable[[Any], Any]] = None

    def __init__(self, **data):
        super().__init__(**data)
        self._setup_formatter()

    def _setup_formatter(self) -> None:
        """Set up the value formatter based on JDBC type."""
        type_formatters = {
            JdbcType.VARCHAR: str,
            JdbcType.CHAR: str,
            JdbcType.LONGVARCHAR: str,
            JdbcType.NVARCHAR: str,
            JdbcType.NCHAR: str,
            JdbcType.CLOB: str,
            JdbcType.NCLOB: str,
            JdbcType.BIT: bool,
            JdbcType.BOOLEAN: bool,
            JdbcType.TINYINT: int,
            JdbcType.SMALLINT: int,
            JdbcType.INTEGER: int,
            JdbcType.BIGINT: int,
            JdbcType.FLOAT: float,
            JdbcType.REAL: float,
            JdbcType.DOUBLE: float,
            JdbcType.NUMERIC: float,
            JdbcType.DECIMAL: float,
        }
        self._formatter = type_formatters.get(self.jdbc_type)

    def get_db_object_type(self) -> DbObjectType:
        """Get the database object type."""
        return DbObjectType.COLUMN

    def set_jdbc_type(self, jdbc_type: JdbcType) -> None:
        """Set JDBC type and update type name.

        Args:
            jdbc_type: JDBC type constant
        """
        self.jdbc_type = jdbc_type
        self._set_type_name_from_jdbc()
        self._setup_formatter()

    def _set_type_name_from_jdbc(self) -> None:
        """Set type name based on JDBC type."""
        type_map = {
            JdbcType.VARCHAR: "VARCHAR",
            JdbcType.CHAR: "CHAR",
            JdbcType.LONGVARCHAR: "TEXT",
            JdbcType.NVARCHAR: "NVARCHAR",
            JdbcType.NCHAR: "NCHAR",
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
            JdbcType.NUMERIC: "NUMERIC",
            JdbcType.DECIMAL: "DECIMAL",
            JdbcType.DATE: "DATE",
            JdbcType.TIME: "TIME",
            JdbcType.TIMESTAMP: "TIMESTAMP",
            JdbcType.BINARY: "BINARY",
            JdbcType.VARBINARY: "VARBINARY",
            JdbcType.BLOB: "BLOB",
            JdbcType.OTHER: "JSON",
            JdbcType.JAVA_OBJECT: "OBJECT",
        }
        self.type_name = type_map.get(self.jdbc_type, "UNKNOWN")

    def set_column_type(self, type_name: str) -> None:
        """Set column type from type name.

        Args:
            type_name: SQL type name
        """
        self.jdbc_type = get_jdbc_type_from_name(type_name)
        self.type_name = type_name.upper()
        self._setup_formatter()

    def format_value(self, value: Any) -> Any:
        """Format a value to the correct Python type for this column.

        Args:
            value: Value to format

        Returns:
            Formatted value
        """
        if value is None:
            return self._get_default_for_type()

        if self._formatter is not None:
            try:
                return self._formatter(value)
            except (ValueError, TypeError):
                return value

        return value

    def _get_default_for_type(self) -> Any:
        """Get the default value for NULL based on column type."""
        defaults = {
            JdbcType.VARCHAR: "",
            JdbcType.CHAR: "",
            JdbcType.LONGVARCHAR: "",
            JdbcType.NVARCHAR: "",
            JdbcType.NCHAR: "",
            JdbcType.CLOB: "",
            JdbcType.NCLOB: "",
            JdbcType.BIT: False,
            JdbcType.BOOLEAN: False,
            JdbcType.TINYINT: 0,
            JdbcType.SMALLINT: 0,
            JdbcType.INTEGER: 0,
            JdbcType.BIGINT: 0,
            JdbcType.FLOAT: 0.0,
            JdbcType.REAL: 0.0,
            JdbcType.DOUBLE: 0.0,
            JdbcType.NUMERIC: 0.0,
            JdbcType.DECIMAL: 0.0,
        }
        return defaults.get(self.jdbc_type, None)

    def get_sql_type(self, dialect: FDialect) -> str:
        """Get the SQL type string for this column.

        Args:
            dialect: Database dialect

        Returns:
            SQL type string
        """
        return dialect.get_type_name(
            self.jdbc_type,
            self.length,
            self.precision,
            self.scale
        )

    def get_constraint_sql(self, dialect: FDialect) -> Optional[str]:
        """Get constraint SQL for this column (e.g., PRIMARY KEY).

        Args:
            dialect: Database dialect

        Returns:
            Constraint SQL or None
        """
        if self.primary_key:
            return f"PRIMARY KEY ({self.get_quoted_name(dialect)})"
        return None

    def is_unique(self) -> bool:
        """Check if column has unique constraint.

        Returns:
            True if unique
        """
        return self.primary_key

    @classmethod
    def create(
        cls,
        name: str,
        type_name: str,
        caption: Optional[str] = None,
        length: int = 0,
        nullable: bool = True,
        default_value: Optional[str] = None,
        primary_key: bool = False,
    ) -> "SqlColumn":
        """Factory method to create a SqlColumn.

        Args:
            name: Column name
            type_name: SQL type name
            caption: Column caption
            length: Column length
            nullable: Allow NULL
            default_value: Default value expression
            primary_key: Is primary key

        Returns:
            SqlColumn instance
        """
        jdbc_type = get_jdbc_type_from_name(type_name)
        return cls(
            name=name,
            caption=caption,
            type_name=type_name.upper(),
            jdbc_type=jdbc_type,
            length=length,
            nullable=nullable,
            default_value=default_value,
            primary_key=primary_key,
        )


__all__ = [
    "SqlColumn",
    "SqlColumnType",
    "JdbcType",
    "TYPE_NAME_TO_JDBC",
    "get_jdbc_type_from_name",
    "DEFAULT_PRECISION",
    "DEFAULT_SCALE",
]