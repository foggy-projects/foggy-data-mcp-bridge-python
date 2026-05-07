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


class DimensionPropertyDef(BaseModel):
    """A property column on a dimension table.

    Example: dim_product has properties like category_name, brand, unit_price.
    These are accessed as product$categoryName, product$brand, etc.
    """
    column: str = Field(..., description="Column name in the dimension table")
    name: Optional[str] = Field(default=None, description="Property name (defaults to camelCase of column)")
    caption: Optional[str] = Field(default=None, description="Display name")
    description: Optional[str] = Field(default=None, description="Description")
    data_type: str = Field(default="STRING", description="Data type: STRING, INTEGER, MONEY, etc.")
    formula_def_raw: Optional[Any] = Field(
        default=None, exclude=True,
        description="Raw formulaDef dict with builder callable for deferred SQL resolution",
    )
    dialect_formula_def_raw: Optional[Any] = Field(
        default=None, exclude=True,
        description="Raw dialectFormulaDef dict with builder callables for deferred SQL resolution",
    )

    model_config = {"extra": "allow"}

    def get_name(self) -> str:
        """Get property name (camelCase of column if not specified)."""
        if self.name:
            return self.name
        # Convert snake_case to camelCase
        parts = self.column.split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])


class DimensionJoinDef(BaseModel):
    """Defines a star-schema dimension JOIN.

    Aligned with Java TM dimension definition:
    {
        name: 'product',
        tableName: 'dim_product',
        foreignKey: 'product_key',
        primaryKey: 'product_key',
        captionColumn: 'product_name',
        properties: [{column: 'category_name', caption: '品类'}]
    }
    """
    name: str = Field(..., description="Dimension name (e.g., 'product')")
    table_name: Optional[str] = Field(default=None, description="Dimension table (e.g., 'dim_product')")
    foreign_key: str = Field(..., description="FK column on fact table")
    primary_key: str = Field(..., description="PK column on dimension table")
    caption_column: Optional[str] = Field(default=None, description="Display column (e.g., 'product_name')")
    caption: Optional[str] = Field(default=None, description="Dimension display name")
    description: Optional[str] = Field(default=None, description="Dimension description")
    key_description: Optional[str] = Field(default=None, description="Key format description")
    alias: Optional[str] = Field(default=None, description="Table alias in SQL (auto-generated if None)")
    join_to: Optional[str] = Field(default=None, description="Parent dimension name when the FK lives on another joined dimension")
    properties: List[DimensionPropertyDef] = Field(default_factory=list, description="Dimension properties")
    caption_def_raw: Optional[Any] = Field(
        default=None, exclude=True,
        description="Raw captionDef dict with builder callables for deferred formula resolution",
    )

    model_config = {"extra": "allow"}

    def get_alias(self) -> str:
        """Get SQL table alias (e.g., 'dp' for dim_product)."""
        if self.alias:
            return self.alias
        if not self.table_name:
            return "t"
        # Generate from table name: dim_product → dp, dim_date → dd
        parts = self.table_name.split("_")
        if len(parts) >= 2:
            return parts[0][0] + parts[1][0]  # d + p = dp
        return self.table_name[:2]

    def get_property(self, prop_name: str) -> Optional[DimensionPropertyDef]:
        """Find property by name (camelCase or column name)."""
        for p in self.properties:
            if p.get_name() == prop_name or p.column == prop_name:
                return p
        return None


class ExplicitJoinConditionDef(BaseModel):
    """Explicit QM join condition between two registered models."""

    left_model: str = Field(..., description="Left/source model name")
    left_field: str = Field(..., description="Left/source semantic field name")
    right_model: str = Field(..., description="Right/target model name")
    right_field: str = Field(..., description="Right/target semantic field name")

    model_config = {"extra": "allow"}


class ExplicitJoinDef(BaseModel):
    """Explicit QM join between two fact-like models."""

    join_type: str = Field(default="LEFT", description="Join type (LEFT/INNER/RIGHT)")
    left_model: str = Field(..., description="Left/source model name")
    right_model: str = Field(..., description="Right/target model name")
    left_alias: str = Field(..., description="SQL alias of left/source model")
    right_alias: str = Field(..., description="SQL alias of right/target model")
    right_table_name: str = Field(..., description="Physical table name of right/target model")
    right_schema_name: Optional[str] = Field(default=None, description="Schema name of right/target model")
    conditions: List[ExplicitJoinConditionDef] = Field(default_factory=list, description="ON conditions")

    model_config = {"extra": "allow"}

    def get_right_table_expr(self) -> str:
        if self.right_schema_name:
            return f"{self.right_schema_name}.{self.right_table_name}"
        return self.right_table_name


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
    join_to: Optional[str] = Field(default=None, description="Parent dimension name when the FK lives on another joined dimension")

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

    # Description
    description: Optional[str] = Field(default=None, description="Human-readable description")

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
    description: Optional[str] = Field(default=None, description="Human-readable description")

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


def _resolve_formula_sql(
    formula_def: Optional[Any],
    dialect_formula_def: Optional[Any],
    table_alias: str,
    dialect_name: Optional[str] = None,
) -> Optional[str]:
    """Resolve formula SQL using the same priority as the Java loader."""
    if dialect_formula_def and isinstance(dialect_formula_def, dict):
        if dialect_name:
            candidates = _dialect_formula_candidates(dialect_name)
            by_lower_key = {
                str(key).lower(): value
                for key, value in dialect_formula_def.items()
            }
            for candidate in candidates:
                entry = by_lower_key.get(candidate)
                if isinstance(entry, dict) and callable(entry.get("builder")):
                    return entry["builder"](table_alias)
        else:
            for entry in dialect_formula_def.values():
                if isinstance(entry, dict) and callable(entry.get("builder")):
                    return entry["builder"](table_alias)

    if formula_def and isinstance(formula_def, dict) and callable(formula_def.get("builder")):
        return formula_def["builder"](table_alias)

    if dialect_formula_def and isinstance(dialect_formula_def, dict):
        for entry in dialect_formula_def.values():
            if isinstance(entry, dict) and callable(entry.get("builder")):
                return entry["builder"](table_alias)

    return None


def _dialect_formula_candidates(dialect_name: str) -> List[str]:
    raw = (dialect_name or "").strip().lower()
    candidates = [raw] if raw else []
    compact = raw.replace("_", "").replace("-", "").replace(".", "")
    if compact.startswith("mysql"):
        candidates.append("mysql")
    if compact.startswith("postgres") or compact.startswith("postgresql"):
        candidates.extend(["postgresql", "postgres"])
    if compact.startswith("sqlite"):
        candidates.append("sqlite")
    if compact.startswith("sqlserver") or compact.startswith("mssql"):
        candidates.extend(["sqlserver", "mssql"])
    result = []
    for candidate in candidates:
        if candidate and candidate not in result:
            result.append(candidate)
    return result


def _resolve_caption_sql(
    join_def: "DimensionJoinDef",
    table_alias: str,
    dialect_name: Optional[str] = None,
) -> str:
    """Resolve caption SQL expression for a dimension join."""
    cdr = getattr(join_def, "caption_def_raw", None)
    if cdr and isinstance(cdr, dict):
        sql = _resolve_formula_sql(
            cdr.get("formulaDef"),
            cdr.get("dialectFormulaDef"),
            table_alias,
            dialect_name,
        )
        if sql:
            return sql

    cap_col = join_def.caption_column or join_def.primary_key or join_def.foreign_key
    return f"{table_alias}.{cap_col}"


def _resolve_dimension_property_sql(
    prop: DimensionPropertyDef,
    table_alias: str,
    dialect_name: Optional[str] = None,
) -> str:
    sql = _resolve_formula_sql(
        getattr(prop, "formula_def_raw", None),
        getattr(prop, "dialect_formula_def_raw", None),
        table_alias,
        dialect_name,
    )
    if sql:
        return sql
    return f"{table_alias}.{prop.column}"


def _is_time_dimension_root(
    model: "DbTableModelImpl",
    field_name: str,
) -> bool:
    dim = model.get_dimension(field_name)
    return bool(
        dim
        and dim.data_type in {ColumnType.DATE, ColumnType.DATETIME, ColumnType.TIMESTAMP}
        and model.get_dimension_join(field_name)
    )


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

    # Predefined calculated fields (e.g. from columnGroups.formula)
    predefined_calculated_fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="Predefined calculated fields"
    )

    # Dimension JOINs (star schema)
    dimension_joins: List[DimensionJoinDef] = Field(
        default_factory=list,
        description="Dimension table JOIN definitions (star schema)",
    )

    explicit_joins: List[ExplicitJoinDef] = Field(
        default_factory=list,
        description="Explicit multi-model joins declared by a QM",
    )

    field_model_map: Dict[str, str] = Field(
        default_factory=dict,
        description="QM field -> source model name mapping for explicit joins",
    )

    model_alias_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Source model name -> SQL alias mapping",
    )

    model_table_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Source model name -> physical table name mapping",
    )

    model_schema_map: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Source model name -> physical schema name mapping",
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

    def get_dimension_join(self, dim_name: str) -> Optional[DimensionJoinDef]:
        """Get dimension JOIN definition by dimension name."""
        for dj in self.dimension_joins:
            if dj.name == dim_name:
                return dj
        return None

    def get_field_model_name(self, field_name: str) -> str:
        """Return the source model name for a QM field."""
        return self.field_model_map.get(field_name, self.name)

    def get_table_alias_for_model(self, model_name: Optional[str] = None) -> str:
        """Return SQL table alias for the given source model."""
        source_model = model_name or self.name
        return self.model_alias_map.get(source_model, "t")

    def get_table_expr_for_model(self, model_name: Optional[str] = None) -> str:
        """Return physical table expression for the given source model."""
        source_model = model_name or self.name
        table_name = self.model_table_map.get(source_model, self.source_table)
        schema_name = self.model_schema_map.get(source_model, self.source_schema)
        if schema_name:
            return f"{schema_name}.{table_name}"
        return table_name

    def resolve_field_for_model(
        self,
        field_name: str,
        source_model_name: Optional[str] = None,
        dialect_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a field against an explicit source model override."""
        if source_model_name is None or source_model_name == self.get_field_model_name(field_name):
            return self.resolve_field(field_name, dialect_name=dialect_name)

        original = self.field_model_map.get(field_name)
        self.field_model_map[field_name] = source_model_name
        try:
            return self.resolve_field(field_name, dialect_name=dialect_name)
        finally:
            if original is None:
                self.field_model_map.pop(field_name, None)
            else:
                self.field_model_map[field_name] = original

    def resolve_field(
        self,
        field_name: str,
        dialect_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a V3 field name to SQL column expression.

        Handles:
          - dim$id         → alias.FK_column (or alias.PK_column on dim table)
          - dim$caption    → alias.caption_column
          - dim$propName   → alias.prop_column
          - measureName    → t.column (with aggregation)
          - propertyName   → t.column (fact table own column)

        Returns:
            Dict with {sql_expr, alias_label, table_alias, is_measure, aggregation, join_def}
            or None if not found.
        """
        source_model_name = self.get_field_model_name(field_name)
        table_alias = self.get_table_alias_for_model(source_model_name)

        # Check for $ separator → dimension field
        if "$" in field_name:
            parts = field_name.split("$", 1)
            dim_name, suffix = parts[0], parts[1]

            join_def = self.get_dimension_join(dim_name)
            if not join_def:
                # Fallback: try as a simple dimension on fact table
                dim = self.get_dimension(dim_name)
                if dim:
                    return {
                        "sql_expr": f"{table_alias}.{dim.column}",
                        "alias_label": dim.alias or dim_name,
                        "table_alias": table_alias,
                        "is_measure": False,
                        "aggregation": None,
                        "join_def": None,
                        "source_model": source_model_name,
                    }
                return None

            is_tableless_join = not join_def.table_name
            ta = table_alias if is_tableless_join else join_def.get_alias()
            runtime_join_def = None if is_tableless_join else join_def

            if suffix == "id":
                id_column = join_def.primary_key
                if is_tableless_join:
                    id_column = join_def.foreign_key or join_def.primary_key
                return {
                    "sql_expr": f"{ta}.{id_column}",
                    "alias_label": f"{join_def.caption or dim_name}(ID)",
                    "table_alias": ta,
                    "is_measure": False,
                    "aggregation": None,
                    "join_def": runtime_join_def,
                    "source_model": source_model_name,
                }
            elif suffix == "caption":
                sql_expr = _resolve_caption_sql(join_def, ta, dialect_name)
                return {
                    "sql_expr": sql_expr,
                    "alias_label": f"{join_def.caption or dim_name}",
                    "table_alias": ta,
                    "is_measure": False,
                    "aggregation": None,
                    "join_def": runtime_join_def,
                    "source_model": source_model_name,
                }
            else:
                # Dimension property: product$categoryName
                prop = join_def.get_property(suffix)
                if prop:
                    return {
                        "sql_expr": _resolve_dimension_property_sql(prop, ta, dialect_name),
                        "alias_label": prop.caption or prop.get_name(),
                        "table_alias": ta,
                        "is_measure": False,
                        "aggregation": None,
                        "join_def": runtime_join_def,
                        "source_model": source_model_name,
                    }
                return None

        # Try measure
        measure = self.get_measure(field_name)
        if measure:
            agg = measure.aggregation.value.upper() if measure.aggregation else None
            return {
                "sql_expr": f"{table_alias}.{measure.column or measure.name}",
                "alias_label": measure.alias or measure.name,
                "table_alias": table_alias,
                "is_measure": True,
                "aggregation": agg,
                "join_def": None,
                "source_model": source_model_name,
            }

        # Time dimension root (for absolute date filtering/timeWindow).
        # Ordinary bare join dimensions remain non-projectable in strict mode.
        join_def = self.get_dimension_join(field_name)
        if join_def and _is_time_dimension_root(self, field_name):
            is_tableless_join = not join_def.table_name
            ta = table_alias if is_tableless_join else join_def.get_alias()
            runtime_join_def = None if is_tableless_join else join_def
            return {
                "sql_expr": _resolve_caption_sql(join_def, ta, dialect_name),
                "alias_label": join_def.caption or field_name,
                "table_alias": ta,
                "is_measure": False,
                "aggregation": None,
                "join_def": runtime_join_def,
                "source_model": source_model_name,
            }

        # Try simple dimension (on fact table)
        dim = self.get_dimension(field_name)
        if dim:
            return {
                "sql_expr": f"{table_alias}.{dim.column}",
                "alias_label": dim.alias or dim.name,
                "table_alias": table_alias,
                "is_measure": False,
                "aggregation": None,
                "join_def": None,
                "source_model": source_model_name,
            }

        # Try property (fact table own columns from TM properties section)
        col_def = self.columns.get(field_name)
        if col_def:
            return {
                "sql_expr": f"{table_alias}.{col_def.name}",
                "alias_label": col_def.alias or col_def.comment or col_def.name,
                "table_alias": table_alias,
                "is_measure": False,
                "aggregation": None,
                "join_def": None,
                "source_model": source_model_name,
            }

        return None

    def resolve_field_strict(
        self,
        field_name: str,
        dialect_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Strict variant of :meth:`resolve_field` aligned to the Foggy
        QM public contract: dimensions are not directly projectable.

        Compared to :meth:`resolve_field`:

        * Bare dimension references (no ``$``) return ``None`` — the caller
          is expected to fail-loud with a hint like
          ``"did you mean '<dim>$caption'?"``. Measures and fact-table
          properties continue to be accepted.
        * ``dim$<suffix>`` only matches when ``<suffix>`` is exactly
          ``"id"``, ``"caption"``, or a declared property name. Garbage
          suffixes (e.g. ``orderStatus$xyz``) return ``None`` instead of
          silently falling back to the dim's primary column.

        Returns ``None`` when the field is not resolvable under the
        strict contract; the caller decides the error code.
        """
        # `field$suffix` path
        if "$" in field_name:
            parts = field_name.split("$", 1)
            dim_name, suffix = parts[0], parts[1]
            # Reject empty suffix or compound (`dim$$x`, `dim$`, etc.)
            if not suffix or "$" in suffix:
                return None
            # Try join-attached dimension first
            join_def = self.get_dimension_join(dim_name)
            if join_def:
                source_alias = self.get_table_alias_for_model(
                    self.get_field_model_name(field_name)
                )
                is_tableless_join = not join_def.table_name
                table_alias_join = source_alias if is_tableless_join else join_def.get_alias()
                runtime_join_def = None if is_tableless_join else join_def
                if suffix == "id":
                    id_column = join_def.primary_key
                    if is_tableless_join:
                        id_column = join_def.foreign_key or join_def.primary_key
                    return {
                        "sql_expr": f"{table_alias_join}.{id_column}",
                        "alias_label": f"{join_def.caption or dim_name}(ID)",
                        "table_alias": table_alias_join,
                        "is_measure": False,
                        "aggregation": None,
                        "join_def": runtime_join_def,
                        "source_model": self.get_field_model_name(field_name),
                    }
                if suffix == "caption":
                    sql_expr = _resolve_caption_sql(join_def, table_alias_join, dialect_name)
                    return {
                        "sql_expr": sql_expr,
                        "alias_label": f"{join_def.caption or dim_name}",
                        "table_alias": table_alias_join,
                        "is_measure": False,
                        "aggregation": None,
                        "join_def": runtime_join_def,
                        "source_model": self.get_field_model_name(field_name),
                    }
                # Custom property — must be declared
                prop = join_def.get_property(suffix)
                if prop:
                    return {
                        "sql_expr": _resolve_dimension_property_sql(prop, table_alias_join, dialect_name),
                        "alias_label": prop.caption or prop.get_name(),
                        "table_alias": table_alias_join,
                        "is_measure": False,
                        "aggregation": None,
                        "join_def": runtime_join_def,
                        "source_model": self.get_field_model_name(field_name),
                    }
                # Unknown suffix on a join-attached dimension → reject
                return None

            # Self-attribute dim (no join_def): only `id` / `caption`
            # are valid suffixes; both map to the dim's own column.
            dim = self.get_dimension(dim_name)
            if dim and suffix in ("id", "caption"):
                table_alias_self = self.get_table_alias_for_model(
                    self.get_field_model_name(field_name)
                )
                return {
                    "sql_expr": f"{table_alias_self}.{dim.column}",
                    "alias_label": dim.alias or dim.name,
                    "table_alias": table_alias_self,
                    "is_measure": False,
                    "aggregation": None,
                    "join_def": None,
                    "source_model": self.get_field_model_name(field_name),
                }
            return None

        # No `$` — measure / property ONLY (bare dimension rejected)
        measure = self.get_measure(field_name)
        if measure:
            agg = measure.aggregation.value.upper() if measure.aggregation else None
            table_alias_m = self.get_table_alias_for_model(
                self.get_field_model_name(field_name)
            )
            return {
                "sql_expr": f"{table_alias_m}.{measure.column or measure.name}",
                "alias_label": measure.alias or measure.name,
                "table_alias": table_alias_m,
                "is_measure": True,
                "aggregation": agg,
                "join_def": None,
                "source_model": self.get_field_model_name(field_name),
            }

        # Time dimension root (for absolute date filtering/timeWindow).
        join_def = self.get_dimension_join(field_name)
        if join_def and _is_time_dimension_root(self, field_name):
            source_model = self.get_field_model_name(field_name)
            source_alias = self.get_table_alias_for_model(source_model)
            is_tableless_join = not join_def.table_name
            table_alias_join = source_alias if is_tableless_join else join_def.get_alias()
            runtime_join_def = None if is_tableless_join else join_def
            return {
                "sql_expr": _resolve_caption_sql(join_def, table_alias_join, dialect_name),
                "alias_label": join_def.caption or field_name,
                "table_alias": table_alias_join,
                "is_measure": False,
                "aggregation": None,
                "join_def": runtime_join_def,
                "source_model": source_model,
            }

        col_def = self.columns.get(field_name)
        if col_def:
            table_alias_c = self.get_table_alias_for_model(
                self.get_field_model_name(field_name)
            )
            return {
                "sql_expr": f"{table_alias_c}.{col_def.name}",
                "alias_label": col_def.alias or col_def.comment or col_def.name,
                "table_alias": table_alias_c,
                "is_measure": False,
                "aggregation": None,
                "join_def": None,
                "source_model": self.get_field_model_name(field_name),
            }

        # Bare dimension and unknown — both reject (caller distinguishes
        # via :meth:`get_dimension` to emit the hint message).
        return None

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
