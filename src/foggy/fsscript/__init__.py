"""FSScript - Expression/Scripting Engine.

This module implements the FSScript scripting engine for the Foggy Framework.
FSScript is a lightweight expression language used for:
- Calculated measures and formulas
- Conditional logic in query models
- Dynamic data transformations

Key components:
- Bundle: Module/plugin system for loading scripts
- Expressions: AST nodes for expression parsing and evaluation
- Closures: Closure support for functional programming
- Built-in Globals: Array, Console, Json utilities
- Evaluator: Expression evaluation engine
- Module Loader: Import/export system for modules
"""

__all__ = [
    # Bundle
    "Bundle",
    "BundleImpl",
    "BundleResource",
    "BundleLoader",
    # Conversion
    "ConversionUtils",
    # Expressions
    "Expression",
    "LiteralExpression",
    "BinaryExpression",
    "UnaryExpression",
    "VariableExpression",
    "FunctionCallExpression",
    "BlockExpression",
    "IfExpression",
    "ForExpression",
    "WhileExpression",
    "ExportExpression",
    "ImportExpression",
    # Closures
    "Closure",
    "ClosureContext",
    # Built-in globals
    "ArrayGlobal",
    "ConsoleGlobal",
    "JsonGlobal",
    # Evaluator
    "ExpressionEvaluator",
    # Module Loader
    "ModuleLoader",
    "FileModuleLoader",
    "StringModuleLoader",
    "ChainedModuleLoader",
    "CircularImportError",
]

from foggy.fsscript.bundle import Bundle, BundleImpl, BundleResource, BundleLoader
from foggy.fsscript.conversion import ConversionUtils
from foggy.fsscript.expressions import Expression, LiteralExpression, BinaryExpression, UnaryExpression
from foggy.fsscript.expressions import VariableExpression, FunctionCallExpression
from foggy.fsscript.expressions import BlockExpression, IfExpression, ForExpression, WhileExpression
from foggy.fsscript.expressions.control_flow import ExportExpression, ImportExpression
from foggy.fsscript.closures import Closure, ClosureContext
from foggy.fsscript.globals import ArrayGlobal, ConsoleGlobal, JsonGlobal
from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.module_loader import (
    ModuleLoader,
    FileModuleLoader,
    StringModuleLoader,
    ChainedModuleLoader,
    CircularImportError,
)