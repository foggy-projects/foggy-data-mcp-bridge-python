"""Measure and formula definitions for semantic layer."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from foggy.dataset_model.definitions.base import AiDef, AggregationType


class MeasureType(str, Enum):
    """Measure type enumeration."""

    BASIC = "basic"  # Simple aggregation
    CALCULATED = "calculated"  # Formula-based
    TIME_INTELLIGENT = "time_intelligent"  # Time-based (YoY, MoM, etc.)


class DbMeasureDef(AiDef):
    """Measure definition for quantitative values in semantic models.

    Measures represent numeric values that can be aggregated,
    such as sales amount, quantity, profit, etc.
    """

    # Measure type
    measure_type: MeasureType = Field(default=MeasureType.BASIC, description="Type of measure")

    # Column reference (for basic measures)
    column: Optional[str] = Field(default=None, description="Source column name")
    table: Optional[str] = Field(default=None, description="Source table name")

    # Aggregation
    aggregation: AggregationType = Field(
        default=AggregationType.SUM, description="Aggregation type"
    )
    distinct: bool = Field(default=False, description="Use DISTINCT in aggregation")

    # Format
    format_pattern: Optional[str] = Field(default=None, description="Number format pattern")
    unit: Optional[str] = Field(default=None, description="Unit of measure (%, $, etc.)")
    decimals: int = Field(default=2, description="Number of decimal places")

    # Filtering
    filter_condition: Optional[str] = Field(default=None, description="Filter condition for measure")

    # Time intelligence
    time_dimension: Optional[str] = Field(default=None, description="Time dimension for time measures")
    time_function: Optional[str] = Field(default=None, description="Time function (YoY, MoM, etc.)")

    model_config = {
        "extra": "allow",
    }

    def get_sql_aggregation(self, column_alias: Optional[str] = None) -> str:
        """Get the SQL aggregation expression.

        Args:
            column_alias: Optional alias for the aggregated column

        Returns:
            SQL aggregation expression
        """
        col = column_alias or self.column or "*"

        if self.aggregation == AggregationType.SUM:
            expr = f"SUM({col})"
        elif self.aggregation == AggregationType.COUNT:
            expr = f"COUNT({col})"
        elif self.aggregation == AggregationType.COUNT_DISTINCT:
            expr = f"COUNT(DISTINCT {col})"
        elif self.aggregation == AggregationType.AVG:
            expr = f"AVG({col})"
        elif self.aggregation == AggregationType.MIN:
            expr = f"MIN({col})"
        elif self.aggregation == AggregationType.MAX:
            expr = f"MAX({col})"
        elif self.aggregation == AggregationType.MEDIAN:
            expr = f"MEDIAN({col})"
        elif self.aggregation == AggregationType.STDDEV:
            expr = f"STDDEV({col})"
        elif self.aggregation == AggregationType.VARIANCE:
            expr = f"VARIANCE({col})"
        else:
            expr = col

        return expr

    def validate_definition(self) -> List[str]:
        """Validate the measure definition."""
        errors = super().validate_definition()

        if self.measure_type == MeasureType.BASIC and not self.column:
            errors.append("column is required for basic measures")

        return errors


class FormulaOperator(str, Enum):
    """Formula operator enumeration."""

    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MODULO = "%"


class DbFormulaDef(AiDef):
    """Formula definition for calculated measures.

    Formulas define calculated measures using expressions
    that reference other measures, columns, and constants.
    """

    # Expression
    expression: str = Field(..., description="Formula expression")

    # Dependencies
    depends_on: List[str] = Field(default_factory=list, description="Dependent measure/column names")

    # Return type
    return_type: str = Field(default="decimal", description="Return data type")

    # Format
    format_pattern: Optional[str] = Field(default=None, description="Number format pattern")
    unit: Optional[str] = Field(default=None, description="Unit of measure")
    decimals: int = Field(default=2, description="Number of decimal places")

    # Validation
    valid: bool = Field(default=True, description="Whether formula is valid")
    error_message: Optional[str] = Field(default=None, description="Validation error message")

    model_config = {
        "extra": "allow",
    }

    def evaluate(self, values: Dict[str, Any]) -> Optional[float]:
        """Evaluate the formula with given values.

        Uses ast.literal_eval-based safe expression evaluation instead of eval().

        Args:
            values: Dictionary of measure/column values

        Returns:
            Calculated result or None if evaluation fails
        """
        try:
            import ast
            import operator

            # Only allow numeric values
            safe_dict = {k: v for k, v in values.items() if isinstance(v, (int, float))}

            # Parse the expression into an AST and evaluate safely
            tree = ast.parse(self.expression, mode='eval')
            result = self._safe_eval_ast(tree.body, safe_dict)
            return float(result) if result is not None else None
        except Exception:
            return None

    @staticmethod
    def _safe_eval_ast(node, variables: Dict[str, float]) -> float:
        """Safely evaluate an AST node with only arithmetic operations.

        Supports: +, -, *, /, //, %, **, unary -, unary +, parentheses,
        numeric literals, and variable references.
        """
        import ast
        import operator

        _ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            raise ValueError(f"Unknown variable: {node.id}")
        elif isinstance(node, ast.BinOp):
            op_func = _ops.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            left = DbFormulaDef._safe_eval_ast(node.left, variables)
            right = DbFormulaDef._safe_eval_ast(node.right, variables)
            return op_func(left, right)
        elif isinstance(node, ast.UnaryOp):
            op_func = _ops.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            operand = DbFormulaDef._safe_eval_ast(node.operand, variables)
            return op_func(operand)
        else:
            raise ValueError(f"Unsupported AST node: {type(node).__name__}")

    def validate_definition(self) -> List[str]:
        """Validate the formula definition."""
        errors = super().validate_definition()

        if not self.expression:
            errors.append("expression is required")
        else:
            # Check for unsafe operations
            unsafe_keywords = ["import", "exec", "eval", "__", "open", "file"]
            for keyword in unsafe_keywords:
                if keyword in self.expression:
                    errors.append(f"unsafe keyword '{keyword}' in expression")

        return errors


class MeasureGroup(BaseModel):
    """Group of related measures."""

    name: str = Field(..., description="Group name")
    alias: Optional[str] = Field(default=None, description="Group alias")
    measures: List[str] = Field(default_factory=list, description="Measure names in group")
    display_order: int = Field(default=0, description="Display order")
    collapsed: bool = Field(default=False, description="Collapsed by default")

    model_config = {
        "extra": "allow",
    }