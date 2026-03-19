"""Model implementation classes for semantic layer."""

from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from datetime import datetime

from foggy.dataset_model.definitions.base import (
    AiDef,
    ColumnType,
    AggregationType,
    DimensionType,
    DbColumnDef,
)
from foggy.dataset_model.definitions.measure import DbMeasureDef, MeasureType
from foggy.dataset_model.definitions.access import DbAccessDef


class DbModelDimensionImpl(BaseModel):
    """Dimension implementation for semantic models.

    Represents a dimension (qualitative attribute) in a table model,
    such as product name, region, date, etc.
    """

    # Identity
    name: str = Field(..., description="Dimension name")
    alias: Optional[str] = Field(default=None, description="Display alias")

    # Column reference
    column: str = Field(..., description="Source column name")
    table: Optional[str] = Field(default=None, description="Source table name")

    # Type
    dimension_type: DimensionType = Field(
        default=DimensionType.REGULAR, description="Dimension type"
    )
    data_type: ColumnType = Field(default=ColumnType.STRING, description="Data type")

    # Hierarchy support
    is_hierarchical: bool = Field(default=False, description="Has hierarchy")
    hierarchy_table: Optional[str] = Field(default=None, description="Hierarchy table")
    parent_column: Optional[str] = Field(default=None, description="Parent column for hierarchy")
    level_column: Optional[str] = Field(default=None, description="Level column for hierarchy")

    # Display
    visible: bool = Field(default=True, description="Visible in UI")
    sortable: bool = Field(default=True, description="Can be sorted")
    filterable: bool = Field(default=True, description="Can be filtered")
    groupable: bool = Field(default=True, description="Can be grouped")

    # Default filter
    default_filter: Optional[str] = Field(default=None, description="Default filter value")

    # Dictionary reference
    dictionary: Optional[str] = Field(default=None, description="Dictionary name for lookup")

    model_config = {
        "extra": "allow",
    }

    def get_display_name(self) -> str:
        """Get display name (alias or name)."""
        return self.alias or self.name

    def get_full_column_name(self) -> str:
        """Get fully qualified column name."""
        if self.table:
            return f"{self.table}.{self.column}"
        return self.column

    def is_time_dimension(self) -> bool:
        """Check if this is a time dimension."""
        return self.dimension_type == DimensionType.TIME

    def supports_hierarchy_operators(self) -> bool:
        """Check if hierarchy operators are supported."""
        return self.is_hierarchical and self.hierarchy_table is not None


class DbModelMeasureImpl(BaseModel):
    """Measure implementation for semantic models.

    Represents a measure (quantitative value) in a table model,
    such as sales amount, quantity, profit, etc.
    """

    # Identity
    name: str = Field(..., description="Measure name")
    alias: Optional[str] = Field(default=None, description="Display alias")

    # Column reference (for basic measures)
    column: Optional[str] = Field(default=None, description="Source column name")
    table: Optional[str] = Field(default=None, description="Source table name")

    # Measure type
    measure_type: MeasureType = Field(default=MeasureType.BASIC, description="Measure type")

    # Aggregation
    aggregation: AggregationType = Field(
        default=AggregationType.SUM, description="Aggregation type"
    )
    distinct: bool = Field(default=False, description="Use DISTINCT")

    # Calculated measure
    expression: Optional[str] = Field(default=None, description="Expression for calculated measures")
    depends_on: List[str] = Field(default_factory=list, description="Dependent measures/columns")

    # Format
    format_pattern: Optional[str] = Field(default=None, description="Number format pattern")
    unit: Optional[str] = Field(default=None, description="Unit (%, $, etc.)")
    decimals: int = Field(default=2, description="Decimal places")

    # Display
    visible: bool = Field(default=True, description="Visible in UI")
    filterable: bool = Field(default=False, description="Can be filtered")

    model_config = {
        "extra": "allow",
    }

    def get_display_name(self) -> str:
        """Get display name (alias or name)."""
        return self.alias or self.name

    def get_sql_expression(self, column_alias: Optional[str] = None) -> str:
        """Get SQL expression for this measure.

        Args:
            column_alias: Optional column alias

        Returns:
            SQL expression
        """
        col = column_alias or self.column or "*"

        if self.expression:
            return self.expression

        if self.measure_type == MeasureType.CALCULATED:
            return self.expression or col

        # Basic aggregation
        agg = self.aggregation.value.upper()
        if agg == "COUNT_DISTINCT":
            return f"COUNT(DISTINCT {col})"
        else:
            return f"{agg}({col})"

    def is_aggregated(self) -> bool:
        """Check if measure has aggregation."""
        if self.measure_type == MeasureType.CALCULATED:
            return False
        return self.aggregation != AggregationType.NONE


class DbTableModelImpl(BaseModel):
    """Table model implementation for semantic layer.

    A Table Model (TM) represents a semantic view over one or more
    database tables, with defined dimensions, measures, and access rules.
    """

    # Identity
    name: str = Field(..., description="Model name")
    alias: Optional[str] = Field(default=None, description="Display alias")
    description: Optional[str] = Field(default=None, description="Model description")

    # Source
    source_table: str = Field(..., description="Source table name")
    source_schema: Optional[str] = Field(default=None, description="Source schema")
    source_datasource: Optional[str] = Field(default=None, description="Data source name")

    # Dimensions
    dimensions: Dict[str, DbModelDimensionImpl] = Field(
        default_factory=dict, description="Dimensions by name"
    )

    # Measures
    measures: Dict[str, DbModelMeasureImpl] = Field(
        default_factory=dict, description="Measures by name"
    )

    # Columns (all columns, not just dimensions/measures)
    columns: Dict[str, DbColumnDef] = Field(
        default_factory=dict, description="All columns by name"
    )

    # Primary key
    primary_key: List[str] = Field(default_factory=list, description="Primary key columns")

    # Access control
    access: Optional[DbAccessDef] = Field(default=None, description="Access control")

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags")
    created_at: Optional[datetime] = Field(default=None, description="Creation time")
    updated_at: Optional[datetime] = Field(default=None, description="Update time")

    # Status
    enabled: bool = Field(default=True, description="Model is enabled")
    valid: bool = Field(default=True, description="Model is valid")

    model_config = {
        "extra": "allow",
    }

    def get_display_name(self) -> str:
        """Get display name (alias or name)."""
        return self.alias or self.name

    def get_dimension(self, name: str) -> Optional[DbModelDimensionImpl]:
        """Get dimension by name.

        Args:
            name: Dimension name

        Returns:
            Dimension or None
        """
        return self.dimensions.get(name)

    def get_measure(self, name: str) -> Optional[DbModelMeasureImpl]:
        """Get measure by name.

        Args:
            name: Measure name

        Returns:
            Measure or None
        """
        return self.measures.get(name)

    def get_column(self, name: str) -> Optional[DbColumnDef]:
        """Get column by name.

        Args:
            name: Column name

        Returns:
            Column or None
        """
        return self.columns.get(name)

    def get_dimension_names(self) -> List[str]:
        """Get all dimension names."""
        return list(self.dimensions.keys())

    def get_measure_names(self) -> List[str]:
        """Get all measure names."""
        return list(self.measures.keys())

    def get_column_names(self) -> List[str]:
        """Get all column names."""
        return list(self.columns.keys())

    def add_dimension(self, dimension: DbModelDimensionImpl) -> "DbTableModelImpl":
        """Add a dimension to the model.

        Args:
            dimension: Dimension to add

        Returns:
            Self for chaining
        """
        self.dimensions[dimension.name] = dimension
        return self

    def add_measure(self, measure: DbModelMeasureImpl) -> "DbTableModelImpl":
        """Add a measure to the model.

        Args:
            measure: Measure to add

        Returns:
            Self for chaining
        """
        self.measures[measure.name] = measure
        return self

    def validate(self) -> List[str]:
        """Validate the model and return errors.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not self.name:
            errors.append("name is required")

        if not self.source_table:
            errors.append("source_table is required")

        # Validate dimensions
        for dim_name, dim in self.dimensions.items():
            if not dim.column:
                errors.append(f"dimension '{dim_name}' has no column reference")

        # Validate measures
        for measure_name, measure in self.measures.items():
            if measure.measure_type == MeasureType.BASIC and not measure.column:
                errors.append(f"measure '{measure_name}' has no column reference")
            if measure.measure_type == MeasureType.CALCULATED and not measure.expression:
                errors.append(f"calculated measure '{measure_name}' has no expression")

        self.valid = len(errors) == 0
        return errors


class DbModelLoadContext(BaseModel):
    """Context for loading table models.

    Provides context information during model loading
    including data source, schema, and reference lookups.
    """

    # Data source
    datasource: str = Field(..., description="Data source name")

    # Schema
    schema_name: Optional[str] = Field(default=None, description="Schema name")

    # Loaded models (for reference resolution)
    loaded_models: Dict[str, DbTableModelImpl] = Field(
        default_factory=dict, description="Loaded models"
    )

    # Loaded dictionaries
    loaded_dictionaries: Dict[str, Any] = Field(
        default_factory=dict, description="Loaded dictionaries"
    )

    # Configuration
    validate_on_load: bool = Field(default=True, description="Validate during load")
    fail_on_error: bool = Field(default=False, description="Fail on validation error")

    model_config = {
        "extra": "allow",
    }

    def get_model(self, name: str) -> Optional[DbTableModelImpl]:
        """Get a loaded model by name.

        Args:
            name: Model name

        Returns:
            Model or None
        """
        return self.loaded_models.get(name)

    def register_model(self, model: DbTableModelImpl) -> None:
        """Register a loaded model.

        Args:
            model: Model to register
        """
        self.loaded_models[model.name] = model