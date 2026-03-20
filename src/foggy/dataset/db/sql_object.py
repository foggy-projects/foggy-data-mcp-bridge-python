"""SQL object base classes for foggy-dataset.

This module provides the base classes for SQL database objects
like tables, columns, indexes, etc.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DbObjectType(Enum):
    """Database object type enumeration."""

    TABLE = "TABLE"
    VIEW = "VIEW"
    COLUMN = "COLUMN"
    INDEX = "INDEX"
    PRIMARY_KEY = "PRIMARY_KEY"
    FOREIGN_KEY = "FOREIGN_KEY"
    SEQUENCE = "SEQUENCE"
    PROCEDURE = "PROCEDURE"
    FUNCTION = "FUNCTION"


class SqlObject(BaseModel, ABC):
    """Base class for all SQL database objects.

    Provides common properties and methods for database objects
    like tables, columns, indexes, etc.
    """

    name: str = Field(default="", description="Object name")
    caption: Optional[str] = Field(default=None, description="Object caption/description")

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    @abstractmethod
    def get_db_object_type(self) -> DbObjectType:
        """Get the database object type.

        Returns:
            DbObjectType enum value
        """
        pass

    def get_quoted_name(self, dialect: "FDialect") -> str:
        """Get the quoted name for SQL generation.

        Args:
            dialect: Database dialect for quoting

        Returns:
            Quoted name string
        """
        return dialect.quote(self.name)


__all__ = ["SqlObject", "DbObjectType"]