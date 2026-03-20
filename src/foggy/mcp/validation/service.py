"""Semantic Layer Validation Service.

This module provides validation for semantic layer configurations,
including query models, table models, and query requests.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import re


class ValidationSeverity(str, Enum):
    """Validation severity level."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """Validation error details."""

    code: str
    message: str
    path: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity.value,
        }


@dataclass
class ValidationWarning:
    """Validation warning details."""

    code: str
    message: str
    path: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)

    def add_error(self, code: str, message: str, path: Optional[str] = None) -> None:
        """Add an error."""
        self.errors.append(ValidationError(code=code, message=message, path=path))
        self.valid = False

    def add_warning(
        self,
        code: str,
        message: str,
        path: Optional[str] = None,
        suggestion: Optional[str] = None
    ) -> None:
        """Add a warning."""
        self.warnings.append(
            ValidationWarning(code=code, message=message, path=path, suggestion=suggestion)
        )

    def merge(self, other: "ValidationResult") -> None:
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


@dataclass
class ValidationRequest:
    """Request for validation."""

    # Model validation
    model_name: Optional[str] = None
    model_type: Optional[str] = None  # "tm" or "qm"
    model_content: Optional[Dict[str, Any]] = None

    # Query validation
    query_model: Optional[str] = None
    query_content: Optional[Dict[str, Any]] = None

    # Connection validation
    datasource_name: Optional[str] = None
    connection_test: bool = False

    # Options
    strict: bool = False
    check_references: bool = True


class SemanticLayerValidationService:
    """Service for validating semantic layer components.

    This service validates:
    - Table Model (TM) definitions
    - Query Model (QM) definitions
    - Query requests
    - Data source connections
    - Model references and dependencies
    """

    # Reserved column names
    RESERVED_NAMES = {
        "limit", "offset", "order", "group", "select", "where",
        "having", "join", "from", "as", "on", "and", "or", "not",
        "in", "is", "null", "like", "between", "exists",
    }

    # Valid aggregation types
    VALID_AGGREGATIONS = {
        "SUM", "COUNT", "AVG", "MIN", "MAX", "DISTINCT_COUNT",
        "STDDEV", "VARIANCE", "MEDIAN", "PERCENTILE",
    }

    def __init__(
        self,
        strict_mode: bool = False,
        validate_references: bool = True
    ):
        """Initialize validation service.

        Args:
            strict_mode: Enable strict validation mode
            validate_references: Validate model references
        """
        self._strict_mode = strict_mode
        self._validate_references = validate_references
        self._models: Dict[str, Any] = {}  # Model registry for reference validation

    def register_model(self, name: str, model: Any) -> None:
        """Register a model for reference validation."""
        self._models[name] = model

    def validate(self, request: ValidationRequest) -> ValidationResult:
        """Validate based on request type.

        Args:
            request: Validation request

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Validate model definition
        if request.model_content:
            model_result = self.validate_model_definition(
                request.model_content,
                model_type=request.model_type or "tm"
            )
            result.merge(model_result)

        # Validate query
        if request.query_content:
            query_result = self.validate_query(request.query_content)
            result.merge(query_result)

        return result

    def validate_model_definition(
        self,
        model: Dict[str, Any],
        model_type: str = "tm"
    ) -> ValidationResult:
        """Validate a model definition.

        Args:
            model: Model definition dictionary
            model_type: Type of model (tm or qm)

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Check required fields
        if "name" not in model:
            result.add_error("MISSING_NAME", "Model must have a 'name' field")

        name = model.get("name", "")
        if not name:
            result.add_error("EMPTY_NAME", "Model name cannot be empty")
        elif not self._is_valid_identifier(name):
            result.add_error(
                "INVALID_NAME",
                f"Model name '{name}' is not a valid identifier",
                path="name"
            )

        # Check for reserved names
        if name.lower() in self.RESERVED_NAMES:
            result.add_warning(
                "RESERVED_NAME",
                f"Model name '{name}' is a reserved word",
                path="name",
                suggestion="Consider using a different name"
            )

        if model_type == "tm":
            result.merge(self._validate_table_model(model))
        elif model_type == "qm":
            result.merge(self._validate_query_model(model))

        return result

    def _validate_table_model(self, model: Dict[str, Any]) -> ValidationResult:
        """Validate a table model (TM) definition."""
        result = ValidationResult()
        name = model.get("name", "unknown")

        # Check table reference
        if "table" not in model and "sql" not in model:
            result.add_error(
                "MISSING_TABLE",
                f"Table model '{name}' must have 'table' or 'sql' defined"
            )

        # Validate columns
        columns = model.get("columns", [])
        if not columns:
            result.add_warning(
                "NO_COLUMNS",
                f"Table model '{name}' has no columns defined",
                suggestion="Add column definitions for better documentation"
            )
        else:
            column_names = set()
            for i, col in enumerate(columns):
                col_result = self._validate_column(col, f"columns[{i}]")
                result.merge(col_result)

                col_name = col.get("name", "")
                if col_name in column_names:
                    result.add_error(
                        "DUPLICATE_COLUMN",
                        f"Duplicate column name '{col_name}'",
                        path=f"columns[{i}].name"
                    )
                column_names.add(col_name)

        # Validate measures
        measures = model.get("measures", [])
        for i, measure in enumerate(measures):
            measure_result = self._validate_measure(measure, f"measures[{i}]")
            result.merge(measure_result)

        # Validate dimensions
        dimensions = model.get("dimensions", [])
        for i, dim in enumerate(dimensions):
            dim_result = self._validate_dimension(dim, f"dimensions[{i}]")
            result.merge(dim_result)

        return result

    def _validate_query_model(self, model: Dict[str, Any]) -> ValidationResult:
        """Validate a query model (QM) definition."""
        result = ValidationResult()
        name = model.get("name", "unknown")

        # Check base table model reference
        base_model = model.get("base_model") or model.get("table_model")
        if base_model:
            if self._validate_references and base_model not in self._models:
                result.add_warning(
                    "UNRESOLVED_REFERENCE",
                    f"Base model '{base_model}' not found in registry",
                    path="base_model",
                    suggestion="Ensure the table model is registered"
                )
        else:
            result.add_error(
                "MISSING_BASE_MODEL",
                f"Query model '{name}' must reference a base table model"
            )

        # Validate calculated fields
        calc_fields = model.get("calculated_fields", [])
        for i, field in enumerate(calc_fields):
            field_result = self._validate_calculated_field(field, f"calculated_fields[{i}]")
            result.merge(field_result)

        return result

    def _validate_column(self, column: Dict[str, Any], path: str) -> ValidationResult:
        """Validate a column definition."""
        result = ValidationResult()

        if "name" not in column:
            result.add_error("MISSING_COLUMN_NAME", "Column must have a 'name'", path=path)

        col_name = column.get("name", "")
        if not self._is_valid_identifier(col_name):
            result.add_error(
                "INVALID_COLUMN_NAME",
                f"Column name '{col_name}' is not a valid identifier",
                path=f"{path}.name"
            )

        # Validate data type
        col_type = column.get("type")
        if col_type:
            valid_types = {
                "STRING", "VARCHAR", "CHAR", "TEXT",
                "INTEGER", "BIGINT", "SMALLINT", "TINYINT",
                "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC",
                "BOOLEAN", "BOOL",
                "DATE", "DATETIME", "TIMESTAMP", "TIME",
                "JSON", "ARRAY", "MAP", "STRUCT",
            }
            if col_type.upper() not in valid_types:
                result.add_warning(
                    "UNKNOWN_TYPE",
                    f"Unknown column type '{col_type}'",
                    path=f"{path}.type"
                )

        return result

    def _validate_measure(self, measure: Dict[str, Any], path: str) -> ValidationResult:
        """Validate a measure definition."""
        result = ValidationResult()

        if "name" not in measure:
            result.add_error("MISSING_MEASURE_NAME", "Measure must have a 'name'", path=path)

        agg_type = measure.get("aggregation") or measure.get("agg")
        if agg_type and agg_type.upper() not in self.VALID_AGGREGATIONS:
            result.add_warning(
                "UNKNOWN_AGGREGATION",
                f"Unknown aggregation type '{agg_type}'",
                path=f"{path}.aggregation",
                suggestion=f"Valid types: {', '.join(self.VALID_AGGREGATIONS)}"
            )

        if "column" not in measure and agg_type != "COUNT":
            result.add_warning(
                "MISSING_MEASURE_COLUMN",
                f"Measure '{measure.get('name', 'unknown')}' has no column reference",
                path=path
            )

        return result

    def _validate_dimension(self, dimension: Dict[str, Any], path: str) -> ValidationResult:
        """Validate a dimension definition."""
        result = ValidationResult()

        if "name" not in dimension:
            result.add_error("MISSING_DIMENSION_NAME", "Dimension must have a 'name'", path=path)

        if "column" not in dimension:
            result.add_warning(
                "MISSING_DIMENSION_COLUMN",
                f"Dimension '{dimension.get('name', 'unknown')}' has no column reference",
                path=path
            )

        return result

    def _validate_calculated_field(
        self,
        field: Dict[str, Any],
        path: str
    ) -> ValidationResult:
        """Validate a calculated field definition."""
        result = ValidationResult()

        if "name" not in field:
            result.add_error("MISSING_FIELD_NAME", "Calculated field must have a 'name'", path=path)

        if "expression" not in field and "formula" not in field:
            result.add_error(
                "MISSING_EXPRESSION",
                f"Calculated field '{field.get('name', 'unknown')}' must have an expression",
                path=path
            )

        return result

    def validate_query(self, query: Dict[str, Any]) -> ValidationResult:
        """Validate a query request.

        Args:
            query: Query request dictionary

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Check model reference
        model_name = query.get("query_model") or query.get("model")
        if not model_name:
            result.add_error("MISSING_MODEL", "Query must specify a model")

        # Validate select columns
        select = query.get("select", [])
        if not select and not query.get("measures"):
            result.add_warning(
                "NO_SELECT",
                "Query has no columns selected",
                suggestion="Add columns to 'select' array"
            )

        # Validate limit
        limit = query.get("limit")
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                result.add_error("INVALID_LIMIT", f"Invalid limit value: {limit}", path="limit")
            elif limit > 100000:
                result.add_warning(
                    "LARGE_LIMIT",
                    f"Large limit ({limit}) may impact performance",
                    path="limit",
                    suggestion="Consider using pagination"
                )

        # Validate offset
        offset = query.get("offset")
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            result.add_error("INVALID_OFFSET", f"Invalid offset value: {offset}", path="offset")

        # Validate filters
        filters = query.get("filters", [])
        for i, f in enumerate(filters):
            filter_result = self._validate_filter(f, f"filters[{i}]")
            result.merge(filter_result)

        # Validate order by
        order_by = query.get("order_by", [])
        for i, order in enumerate(order_by):
            if "column" not in order and "field" not in order:
                result.add_error(
                    "MISSING_ORDER_COLUMN",
                    f"Order specification missing column",
                    path=f"order_by[{i}]"
                )

        # Validate group by
        group_by = query.get("group_by", [])
        measures = query.get("measures", [])
        if measures and not group_by:
            result.add_warning(
                "NO_GROUP_BY",
                "Query has measures but no group_by - will aggregate all rows",
                suggestion="Add dimensions to group_by for meaningful aggregation"
            )

        return result

    def _validate_filter(self, filter_def: Dict[str, Any], path: str) -> ValidationResult:
        """Validate a filter definition."""
        result = ValidationResult()

        # Check filter structure
        if "column" not in filter_def and "field" not in filter_def:
            result.add_error(
                "MISSING_FILTER_COLUMN",
                "Filter must specify a column",
                path=path
            )

        operator = filter_def.get("operator") or filter_def.get("op")
        if not operator:
            result.add_error(
                "MISSING_OPERATOR",
                "Filter must have an operator",
                path=path
            )

        # Validate operator
        valid_operators = {
            "eq", "ne", "gt", "gte", "lt", "lte",
            "in", "not_in", "like", "not_like",
            "is_null", "is_not_null", "between",
            "contains", "starts_with", "ends_with",
        }
        if operator and operator.lower() not in valid_operators:
            result.add_warning(
                "UNKNOWN_OPERATOR",
                f"Unknown operator '{operator}'",
                path=f"{path}.operator"
            )

        # Check value
        value = filter_def.get("value")
        if operator and operator.lower() not in ("is_null", "is_not_null"):
            if value is None:
                result.add_error(
                    "MISSING_VALUE",
                    f"Filter with operator '{operator}' requires a value",
                    path=path
                )

        return result

    def validate_datasource_connection(
        self,
        datasource_config: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a data source configuration.

        Args:
            datasource_config: Data source configuration

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        if "name" not in datasource_config:
            result.add_error("MISSING_NAME", "Data source must have a 'name'")

        if "type" not in datasource_config:
            result.add_error("MISSING_TYPE", "Data source must have a 'type'")

        ds_type = datasource_config.get("type", "").lower()
        valid_types = {"mysql", "postgresql", "postgres", "sqlite", "sqlserver", "oracle"}

        if ds_type not in valid_types:
            result.add_warning(
                "UNKNOWN_DATASOURCE_TYPE",
                f"Unknown data source type '{ds_type}'",
                suggestion=f"Valid types: {', '.join(valid_types)}"
            )

        # Check connection parameters
        if ds_type in ("mysql", "postgresql", "postgres", "sqlserver", "oracle"):
            if "host" not in datasource_config and "url" not in datasource_config:
                result.add_error(
                    "MISSING_CONNECTION_PARAMS",
                    f"Data source '{ds_type}' requires 'host' or 'url'"
                )

        return result

    def _is_valid_identifier(self, name: str) -> bool:
        """Check if a name is a valid identifier.

        Valid identifiers:
        - Start with a letter or underscore
        - Contain only letters, numbers, and underscores
        - Not a reserved word
        """
        if not name:
            return False

        # Check pattern
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            return False

        # Check reserved words (case insensitive)
        if name.lower() in self.RESERVED_NAMES:
            return self._strict_mode  # Warning in non-strict mode

        return True

    def validate_all_models(self) -> ValidationResult:
        """Validate all registered models.

        Returns:
            Combined ValidationResult for all models
        """
        result = ValidationResult()

        for name, model in self._models.items():
            if hasattr(model, "to_dict"):
                model_dict = model.to_dict()
            elif hasattr(model, "model_dump"):
                model_dict = model.model_dump()
            else:
                model_dict = model if isinstance(model, dict) else {}

            model_result = self.validate_model_definition(model_dict)
            result.merge(model_result)

        return result