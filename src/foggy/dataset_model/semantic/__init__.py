"""Semantic query service package."""

from foggy.dataset_model.semantic.service import SemanticQueryService, QueryBuildResult
from foggy.dataset_model.semantic.formula_compiler import (
    FormulaCompiler,
    FormulaCompilerConfig,
    CompiledFormula,
)
from foggy.dataset_model.semantic.formula_dialect import SqlDialect
from foggy.dataset_model.semantic.formula_errors import (
    FormulaError,
    FormulaSyntaxError,
    FormulaSecurityError,
    FormulaNodeNotAllowedError,
    FormulaFunctionNotAllowedError,
    FormulaDepthError,
    FormulaInListSizeError,
    FormulaNullComparisonError,
    FormulaAggNotOutermostError,
)

__all__ = [
    "SemanticQueryService",
    "QueryBuildResult",
    # M2 Step 2.1 脚手架（compile 未实装，仅骨架）
    "FormulaCompiler",
    "FormulaCompilerConfig",
    "CompiledFormula",
    "SqlDialect",
    "FormulaError",
    "FormulaSyntaxError",
    "FormulaSecurityError",
    "FormulaNodeNotAllowedError",
    "FormulaFunctionNotAllowedError",
    "FormulaDepthError",
    "FormulaInListSizeError",
    "FormulaNullComparisonError",
    "FormulaAggNotOutermostError",
]