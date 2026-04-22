"""Compose Query SQL compilation subpackage (M6 · 8.2.0.beta).

Public API:
    compile_plan_to_sql  — main entry; QueryPlan → ComposedSql
    ComposeCompileError  — structured error type
    error_codes          — module carrying the 4 code constants + NAMESPACE

All other names (``per_base``, ``compose_planner``, ``plan_hash``) are
implementation details and should not be imported by downstream code.
"""
from foggy.dataset_model.engine.compose.compilation import error_codes
from foggy.dataset_model.engine.compose.compilation.compiler import (
    compile_plan_to_sql,
)
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)

__all__ = [
    "compile_plan_to_sql",
    "ComposeCompileError",
    "error_codes",
]
