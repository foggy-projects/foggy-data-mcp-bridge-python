"""Base definition classes for semantic layer."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ColumnType(str, Enum):
    """Column type enumeration for semantic layer."""

    STRING = "string"
    INTEGER = "integer"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    TIME = "time"
    JSON = "json"
    ARRAY = "array"
    OBJECT = "object"


class AggregationType(str, Enum):
    """Aggregation type for measures."""

    SUM = "sum"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    STDDEV = "stddev"
    VARIANCE = "variance"
    NONE = "none"  # For non-aggregated measures


class DimensionType(str, Enum):
    """Dimension type enumeration."""

    REGULAR = "regular"
    TIME = "time"
    GEO = "geo"
    HIERARCHY = "hierarchy"


class AiDef(BaseModel):
    """Base class for AI-enabled definitions with metadata and validation support.

    This is the foundation class for all semantic layer definitions including
    Table Models (TM), Query Models (QM), and their component definitions.
    """

    # Identity
    name: str = Field(..., description="Unique identifier name")
    alias: Optional[str] = Field(default=None, description="Display name/alias")
    description: Optional[str] = Field(default=None, description="Human-readable description")

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # Audit fields
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    created_by: Optional[str] = Field(default=None, description="Creator user/entity")
    updated_by: Optional[str] = Field(default=None, description="Last updater user/entity")

    # AI integration
    ai_description: Optional[str] = Field(default=None, description="AI-friendly description")
    ai_examples: List[str] = Field(default_factory=list, description="Example queries for AI")

    model_config = {
        "extra": "allow",
        "populate_by_name": True,
    }

    def get_display_name(self) -> str:
        """Get the display name (alias or name)."""
        return self.alias or self.name

    def validate_definition(self) -> List[str]:
        """Validate the definition and return list of errors (empty if valid)."""
        errors = []
        if not self.name:
            errors.append("name is required")
        return errors


class DbDefSupport(ABC, BaseModel):
    """Support interface providing common definition utilities.

    This provides utility methods for definition classes that need
    serialization, validation, and introspection capabilities.
    """

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert definition to dictionary representation."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DbDefSupport":
        """Create definition from dictionary."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate the definition."""
        pass


class DbColumnDef(BaseModel):
    """Database column definition."""

    name: str = Field(..., description="Column name")
    alias: Optional[str] = Field(default=None, description="Column alias")
    column_type: ColumnType = Field(default=ColumnType.STRING, description="Column data type")
    nullable: bool = Field(default=True, description="Whether column can be null")
    primary_key: bool = Field(default=False, description="Whether column is primary key")
    auto_increment: bool = Field(default=False, description="Whether column auto-increments")
    default_value: Optional[Any] = Field(default=None, description="Default value")
    comment: Optional[str] = Field(default=None, description="Column comment/description")
    size: Optional[int] = Field(default=None, description="Column size/length")
    precision: Optional[int] = Field(default=None, description="Numeric precision")
    scale: Optional[int] = Field(default=None, description="Numeric scale")

    model_config = {
        "extra": "allow",
    }


class DbTableDef(BaseModel):
    """Database table definition."""

    name: str = Field(..., description="Table name")
    alias: Optional[str] = Field(default=None, description="Table alias")
    schema_name: Optional[str] = Field(default=None, description="Schema name")
    catalog_name: Optional[str] = Field(default=None, description="Catalog/database name")
    columns: List[DbColumnDef] = Field(default_factory=list, description="Column definitions")
    primary_keys: List[str] = Field(default_factory=list, description="Primary key column names")
    comment: Optional[str] = Field(default=None, description="Table comment/description")

    model_config = {
        "extra": "allow",
    }